import argparse
import datetime
import logging
import pickle
import sys
import time
from typing import List

import carla
from common.bridge import MqttBridge
from common.constants import *
from common.quadkey import QuadKey
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMOccupancyGrid
from common.util import GracefulKiller

BASE_KEY = '120203233231202'  # Town01
DATA_DIR = '../../../data/evaluation/perception'

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


class PEMGridContainer:
    def __init__(self, grid: PEMOccupancyGrid, tile: QuadKey):
        self.grid = grid
        self.tile = tile
        self.ts = time.time()

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
        self.data_dir_observed: str = os.path.join(data_dir, 'observed')
        self.data_dir_actual: str = os.path.join(data_dir, 'actual')
        self.base_tile: QuadKey = base_tile
        self.tiles: List[QuadKey] = base_tile.children(at_level=REMOTE_GRID_TILE_LEVEL)

        self.bridge: MqttBridge = MqttBridge()
        self.client: carla.Client = carla_client

        self.last_tick: float = 0
        self.tick_count: int = 0

        self.observation_buffer: List[PEMGridContainer] = []
        self.occupancy_observations: List[PEMGridContainer] = []

        for d in [self.data_dir, self.data_dir_observed, self.data_dir_actual]:
            if not os.path.exists(d):
                os.makedirs(d)

    def start(self):
        for t in self.tiles:
            def cb(payload):
                return self.on_remote_grid(t, payload)

            self.bridge.subscribe(f'{TOPIC_PREFIX_GRAPH_FUSED_OUT}/{t.key}', cb)

        self.bridge.listen(block=False)

        self.run_sync_loop()

    def run_sync_loop(self):
        while True:
            self.tick()
            time.sleep(max(0.0, self.tick_timeout - (time.monotonic() - self.last_tick)))
            self.last_tick = time.monotonic()

            if self.killer.kill_now:
                self.flush()
                return

    def tick(self):
        # Flush observation buffer
        self.occupancy_observations += self.observation_buffer[:]
        self.observation_buffer = []

        if self.tick_count % 10 == 0:
            logging.debug(f'{len(self.occupancy_observations)}')

        self.tick_count += 1

    def flush(self):
        dt = datetime.datetime.now()
        tpl = f'{self.base_tile.key}_%Y-%m-%d_%H-%M-%S.pkl'

        logging.info('Flushing observations ...')
        with open(os.path.join(self.data_dir_observed, dt.strftime(tpl)), 'wb') as f:
            pickle.dump(self.occupancy_observations, f)

    def on_remote_grid(self, tile: QuadKey, msg: bytes):
        scene: PEMTrafficScene = PEMTrafficScene.from_bytes(msg)
        self.observation_buffer.append(PEMGridContainer(scene.occupancy_grid, tile))


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
