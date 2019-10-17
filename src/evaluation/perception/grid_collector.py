import argparse
import logging
import pickle
import sys
import time
from datetime import datetime
from threading import Thread, Lock
from typing import List, Iterator, FrozenSet, Iterable, Dict, Set, Callable

import carla
from client import map_dynamic_actor, get_occupied_cells
from common.bridge import MqttBridge
from common.constants import *
from common.model import DynamicActor
from common.quadkey import QuadKey
from common.util import GracefulKiller
from evaluation.perception import OccupancyObservationContainer, OccupancyGroundTruthContainer

BASE_KEY = '120203233231202'  # Town01
DATA_DIR = '../../../data/evaluation/perception'
FLUSH_AFTER = 1e4

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


class GridCollector:
    def __init__(
            self,
            base_tile: QuadKey,
            carla_client: carla.Client,
            rate: int = 10,
            data_dir: str = '/tmp'
    ):
        self.killer: GracefulKiller = GracefulKiller()
        self.tick_rate: int = rate
        self.tick_timeout: float = 1 / rate
        self.data_dir: str = data_dir
        self.data_dir_actual: str = os.path.join(data_dir, 'actual')
        self.data_dir_observed: str = os.path.join(data_dir, 'observed')
        self.data_dir_observed_local: str = os.path.join(self.data_dir_observed, 'local')
        self.data_dir_observed_remote: str = os.path.join(self.data_dir_observed, 'remote')
        self.base_tile: QuadKey = base_tile
        self.tiles: List[QuadKey] = base_tile.children(at_level=REMOTE_GRID_TILE_LEVEL)

        self.bridge: MqttBridge = MqttBridge()
        self.client: carla.Client = carla_client
        self.world: carla.World = carla_client.get_world()
        self.map: carla.Map = self.world.get_map()

        self.start_time: datetime = datetime.now()
        self.last_tick: float = 0
        self.last_msg: float = 0
        self.tick_count: int = 0
        self.flush_count: int = 0
        self.active_threads: List[Thread] = []
        self.lock1: Lock = Lock()

        self.observation_buffer: List[OccupancyObservationContainer] = []
        self.ground_truth_buffer: List[OccupancyGroundTruthContainer] = []
        self.occupancy_observations: List[OccupancyObservationContainer] = []
        self.occupancy_ground_truth: List[OccupancyGroundTruthContainer] = []

        for d in [self.data_dir, self.data_dir_observed, self.data_dir_actual, self.data_dir_observed_local, self.data_dir_observed_remote]:
            if not os.path.exists(d):
                os.makedirs(d)

    def start(self):
        def get_cb(tile: QuadKey) -> Callable:
            def cb(payload):
                return self.on_graph_msg(tile, payload)

            return cb

        for t in self.tiles:
            self.bridge.subscribe(f'{TOPIC_PREFIX_GRAPH_FUSED_OUT}/{t}', get_cb(t))

        self.bridge.listen(block=False)

        self.run_loop()

    def run_loop(self):
        while True:
            # Generate ground truth
            if time.monotonic() - self.last_msg <= GRID_TTL_SEC:
                self.push_ground_truth()

            # Sync ground truth and latest observations
            self.sync()

            # Sleep
            time.sleep(max(0.0, self.tick_timeout - (time.monotonic() - self.last_tick)))
            self.last_tick = time.monotonic()

            if self.killer.kill_now:
                self.sync()

                if len(self.occupancy_observations) > 0 and len(self.occupancy_ground_truth) > 0:
                    self.flush()

                return

    def sync(self):
        with self.lock1:
            buffer_len = min(len(self.ground_truth_buffer), len(self.observation_buffer))

            # Flush observation buffer
            self.occupancy_observations += self.observation_buffer[-buffer_len:]
            self.observation_buffer.clear()

        # Flush actor buffer
        self.occupancy_ground_truth += self.ground_truth_buffer[-buffer_len:]
        self.ground_truth_buffer.clear()

        if self.tick_count % 10 == 0:
            k_observations = len(self.occupancy_observations)
            n_observations = k_observations + (FLUSH_AFTER * self.flush_count)

            k_ground_truth = len(self.occupancy_ground_truth)
            n_ground_truth = k_ground_truth + (FLUSH_AFTER * self.flush_count)

            k = min(k_observations, k_ground_truth)

            logging.debug(f'Observations: {k_observations} (~ {n_observations}); Ground Truth: {k_ground_truth} (~ {n_ground_truth})')

            if k > FLUSH_AFTER and k % (FLUSH_AFTER * (self.flush_count + 1)):
                Thread(target=self.flush).start()

        self.tick_count += 1

    def flush(self):
        tpl = f'{self.base_tile.key}_%Y-%m-%d_%H-%M-%S_part-{self.flush_count + 1}.pkl'

        logging.info('Flushing observations ...')
        with open(os.path.join(self.data_dir_observed_remote, self.start_time.strftime(tpl)), 'wb') as f:
            pickle.dump(self.occupancy_observations, f)
        self.occupancy_observations.clear()

        logging.info('Flushing ground truth ...')
        with open(os.path.join(self.data_dir_actual, self.start_time.strftime(tpl)), 'wb') as f:
            pickle.dump(self.occupancy_ground_truth, f)
        self.occupancy_ground_truth.clear()

        self.flush_count += 1

    def on_graph_msg(self, tile: QuadKey, msg: bytes):
        if not self.lock1.locked():
            self.observation_buffer.append(OccupancyObservationContainer(msg, tile))
            self.last_msg = time.monotonic()

    def push_ground_truth(self):
        occupied_cells: Dict[str, Set[QuadKey]] = self.split_by_level(
            self.fetch_occupied_cells(),
            level=REMOTE_GRID_TILE_LEVEL
        )

        for tile, cells in occupied_cells.items():
            self.ground_truth_buffer.append(OccupancyGroundTruthContainer(
                occupied_cells=frozenset(cells),
                tile=QuadKey(tile)
            ))

    def fetch_occupied_cells(self) -> FrozenSet[QuadKey]:
        carla_actors: List[carla.Actor] = []
        carla_actors += list(self.world.get_actors().filter('vehicle.*'))
        carla_actors += list(self.world.get_actors().filter('walker.*'))
        all_actors: Iterator[DynamicActor] = map(lambda a: map_dynamic_actor(a, self.map), carla_actors)

        occupied_cells: Iterator[FrozenSet[QuadKey]] = map(get_occupied_cells, all_actors)

        return frozenset().union(*occupied_cells)

    def split_by_level(self, quadkeys: Iterable[QuadKey], level=REMOTE_GRID_TILE_LEVEL) -> Dict[str, Set[QuadKey]]:
        key_map: Dict[str, Set[QuadKey]] = dict()

        for q in quadkeys:
            parent = q.key[:level]
            if parent not in key_map:
                key_map[parent] = set()
            key_map[parent].add(q)

        return key_map

def run(args=sys.argv[1:]):
    argparser = argparse.ArgumentParser(description='TalkyCars Grid Collector')
    argparser.add_argument('--rate', '-r', default=10, type=int, help='Tick Rate')
    argparser.add_argument('--host', default='127.0.0.1', help='IP of the host server (default: 127.0.0.1)')
    argparser.add_argument('-p', '--port', default=2000, type=int, help='TCP port to listen to (default: 2000)')
    argparser.add_argument('-o', '--out_dir', default=DATA_DIR, type=str, help='Directory to dump data to')

    args, _ = argparser.parse_known_args(args)

    # Initialize Carla client
    client = carla.Client(args.host, args.port)
    client.set_timeout(2.0)

    GridCollector(
        carla_client=client,
        base_tile=QuadKey(BASE_KEY),
        rate=args.rate,
        data_dir=os.path.normpath(
            os.path.join(os.path.dirname(__file__), args.out_dir)
        )
    ).start()


if __name__ == '__main__':
    run()
