import argparse
import logging
import sys
from typing import List

from common.bridge import MqttBridge
from common.constants import *
from common.quadkey import QuadKey
from common.serialization.schema.base import PEMTrafficScene

BASE_KEY = '120203233231202'  # Town01

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


class GridCollector:
    def __init__(self, base_tile: QuadKey, rate: int = 10):
        self.tick_rate: int = rate
        self.base_tile: QuadKey = base_tile
        self.tiles: List[QuadKey] = base_tile.children(at_level=REMOTE_GRID_TILE_LEVEL)
        self.bridge: MqttBridge = MqttBridge()

    def start(self):
        for t in self.tiles:
            self.bridge.subscribe(f'{TOPIC_PREFIX_GRAPH_FUSED_OUT}/{t.key}', self.on_remote_grid)
        self.bridge.listen()

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


if __name__ == '__main__':
    run()
