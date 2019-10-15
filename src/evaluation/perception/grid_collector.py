import argparse
import logging
import sys
import time
from typing import List

from client import TileSubscriptionService
from common.constants import *
from common.quadkey import QuadKey
from common.serialization.schema.base import PEMTrafficScene

BASE_KEY = '120203233231202'

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


class GridCollector:
    def __init__(self, base_tile: QuadKey, rate: int = 10):
        self.tick_rate: int = rate
        self.base_tile: QuadKey = base_tile
        self.tiles: List[QuadKey] = base_tile.children(at_level=REMOTE_GRID_TILE_LEVEL)
        self.tss: TileSubscriptionService = TileSubscriptionService(
            self.on_remote_grid,
            manual_mode=True,
            edge_node_level=15  # Determined using map_tiles.py for Town01
        )

    def start(self):
        self.tss.update_subscriptions(
            frozenset(map(str, self.tiles)),
            frozenset(map(str, [self.base_tile]))
        )

    def on_remote_grid(self, msg: bytes):
        scene: PEMTrafficScene = PEMTrafficScene.from_bytes(msg)
        logging.debug(f'Got message: {len(msg)}')


def run(args=sys.argv[1:]):
    argparser = argparse.ArgumentParser(description='TalkyCars Grid Collector')
    argparser.add_argument('--rate', '-r', default=10, type=int, help='Tick Rate')

    args, _ = argparser.parse_known_args(args)

    GridCollector(
        base_tile=QuadKey(BASE_KEY),
        rate=args.rate
    ).start()

    time.sleep(10)


if __name__ == '__main__':
    run()
