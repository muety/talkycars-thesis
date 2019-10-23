import argparse
import logging
import pickle
import sys
import time
from datetime import datetime
from threading import Thread
from typing import List, Iterator, FrozenSet, Iterable, Dict, Set

import carla
from client import map_dynamic_actor, get_occupied_cells
from common.constants import *
from common.constants import EVAL2_BASE_KEY, EVAL2_DATA_DIR
from common.model import DynamicActor
from common.quadkey import QuadKey
from common.util.process import GracefulKiller
from evaluation.perception import OccupancyGroundTruthContainer

FLUSH_AFTER = 1e4

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


def data_dir():
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '../../../data'))


class GridCollector:
    def __init__(
            self,
            base_tile: QuadKey,
            ego_prefix: str,
            carla_client: carla.Client,
            rate: int = 10,
            data_dir: str = '/tmp'
    ):
        self.killer: GracefulKiller = GracefulKiller()
        self.tick_rate: int = rate
        self.tick_timeout: float = 1 / rate
        self.data_dir: str = data_dir
        self.data_dir_actual: str = os.path.join(data_dir, 'actual')
        self.base_tile: QuadKey = base_tile
        self.ego_prefix: str = ego_prefix

        self.client: carla.Client = carla_client
        self.world: carla.World = carla_client.get_world()
        self.map: carla.Map = self.world.get_map()

        self.start_time: datetime = datetime.now()
        self.last_tick: float = 0
        self.tick_count: int = 0
        self.flush_count: int = 0

        self.ground_truth_buffer: List[OccupancyGroundTruthContainer] = []
        self.occupancy_ground_truth: List[OccupancyGroundTruthContainer] = []

        for d in [self.data_dir, self.data_dir_actual]:
            if not os.path.exists(d):
                os.makedirs(d)

    def start(self):
        self.run_loop()

    def run_loop(self):
        while True:
            # Generate ground truth
            self.push_ground_truth()

            # Sync ground truth and latest observations
            self.sync()

            # Sleep
            time.sleep(max(0.0, self.tick_timeout - (time.monotonic() - self.last_tick)))
            self.last_tick = time.monotonic()

            if self.killer.kill_now:
                self.sync()

                if len(self.occupancy_ground_truth) > 0:
                    self.flush()

                return

    def sync(self):
        # Flush actor buffer
        self.occupancy_ground_truth += self.ground_truth_buffer
        self.ground_truth_buffer.clear()

        if self.tick_count % 10 == 0:
            k_ground_truth = len(self.occupancy_ground_truth)
            n_ground_truth = k_ground_truth + (FLUSH_AFTER * self.flush_count)

            logging.debug(f'Ground Truth: {k_ground_truth} (~ {n_ground_truth})')

            if k_ground_truth > FLUSH_AFTER and k_ground_truth % (FLUSH_AFTER * (self.flush_count + 1)):
                Thread(target=self.flush).start()

        self.tick_count += 1

    def flush(self):
        tpl = f'{self.base_tile.key}_%Y-%m-%d_%H-%M-%S_part-{self.flush_count + 1}.pkl'

        logging.info('Flushing ground truth ...')
        with open(os.path.join(self.data_dir_actual, self.start_time.strftime(tpl)), 'wb') as f:
            pickle.dump(self.occupancy_ground_truth, f)
        self.occupancy_ground_truth.clear()

        self.flush_count += 1

    def push_ground_truth(self):
        now: float = time.time()

        occupied_cells: Dict[str, Set[QuadKey]] = self.split_by_level(
            self.fetch_occupied_cells(),
            level=REMOTE_GRID_TILE_LEVEL
        )

        for tile, cells in occupied_cells.items():
            self.ground_truth_buffer.append(OccupancyGroundTruthContainer(
                occupied_cells=frozenset(cells),
                tile=QuadKey(tile),
                ts=now
            ))

    def fetch_occupied_cells(self) -> FrozenSet[QuadKey]:
        carla_actors: List[carla.Actor] = []
        carla_actors += list(self.world.get_actors().filter('vehicle.*'))
        carla_actors += list(self.world.get_actors().filter('walker.*'))
        carla_actors = list(filter(lambda a: 'role_name' not in a.attributes or not a.attributes['role_name'].startswith(self.ego_prefix), carla_actors))  # Don't consider egos
        all_actors: Iterator[DynamicActor] = map(lambda a: map_dynamic_actor(a, self.map), carla_actors)

        occupied_cells: Iterator[FrozenSet[QuadKey]] = map(get_occupied_cells, all_actors)

        return frozenset().union(*occupied_cells)

    @staticmethod
    def split_by_level(quadkeys: Iterable[QuadKey], level=REMOTE_GRID_TILE_LEVEL) -> Dict[str, Set[QuadKey]]:
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
    argparser.add_argument('-o', '--out_dir', default=os.path.join(data_dir(), EVAL2_DATA_DIR), type=str, help='Directory to dump data to')

    args, _ = argparser.parse_known_args(args)

    # Initialize Carla client
    client = carla.Client(args.host, args.port)
    client.set_timeout(2.0)

    GridCollector(
        carla_client=client,
        base_tile=QuadKey(EVAL2_BASE_KEY),
        ego_prefix=SCENE2_EGO_PREFIX,
        rate=args.rate,
        data_dir=os.path.normpath(
            os.path.join(os.path.dirname(__file__), args.out_dir)
        )
    ).start()


if __name__ == '__main__':
    run()
