import argparse
import logging
import sys
import time
from multiprocessing.pool import ThreadPool
from threading import RLock, Thread
from typing import Type, cast, List, Set, Dict

from common import quadkey
from common.bridge import MqttBridge
from common.constants import *
from common.quadkey import QuadKey
from common.serialization.schema import CapnpObject
from common.serialization.schema.base import PEMTrafficScene
from edgenode.fusion import FusionService, FusionServiceFactory

EVAL_RATE_SECS = 5  # hertz⁻¹
TICK_RATE = 10  # hertz

class EdgeNode:
    def __init__(self, covered_tile: QuadKey):
        self.mqtt: MqttBridge = None
        self.fusion_srvc: FusionService[PEMTrafficScene] = FusionServiceFactory.get(PEMTrafficScene, covered_tile)
        self.covered_tile: QuadKey = covered_tile
        self.children_tiles: List[QuadKey] = covered_tile.children(REMOTE_GRID_TILE_LEVEL)
        self.children_tile_keys: Set[str] = set(map(lambda t: t.key, self.children_tiles))

        self.in_rate_count_thread: Thread = Thread(target=self._eval_rate)
        self.in_rate_lock: RLock = RLock()
        self.in_rate_count: int = 0

        self.tick_timeout: float = 1 / TICK_RATE
        self.last_tick: float = time.monotonic()

        self.send_pool: ThreadPool = ThreadPool(12)  # GIL Thread Pool

    def run(self):
        self.in_rate_count_thread.start()

        self.mqtt = MqttBridge()
        self.mqtt.subscribe(TOPIC_PREFIX_GRAPH_RAW_IN + '/#', self._on_graph)
        self.mqtt.listen(block=False)

        while True:
            self.last_tick = time.monotonic()
            self.tick()
            diff = time.monotonic() - self.last_tick
            time.sleep(max(0.0, self.tick_timeout - diff))

    def tick(self):
        # TODO: Maybe try to speed up a little more. Currently takes ~ 0.12 sec for two agents with 10x10 grids
        fused_graphs: Dict[str, PEMTrafficScene] = self.fusion_srvc.get()
        if not fused_graphs:
            return

        self.send_pool.starmap_async(self._publish_graph, fused_graphs.items())

    def _on_graph(self, message: bytes):
        graph: PEMTrafficScene = cast(PEMTrafficScene, self._decode_capnp_msg(message, target_cls=PEMTrafficScene))
        self.fusion_srvc.push(graph.measured_by.id, graph)

        with self.in_rate_lock:
            self.in_rate_count += 1

    def _publish_graph(self, for_tile: str, graph: PEMTrafficScene):
        try:
            encoded_graph: bytes = graph.to_bytes()
            self.mqtt.publish(f'{TOPIC_PREFIX_GRAPH_FUSED_OUT}/{for_tile}', encoded_graph)
        except Exception as e:
            logging.warning(e)

    def _eval_rate(self):
        while not self.mqtt or not self.mqtt.connected:
            time.sleep(.5)

        while self.mqtt.connected:
            time.sleep(EVAL_RATE_SECS)
            logging.debug(f'Current message rate: {self.in_rate_count / EVAL_RATE_SECS} msgs / sec')

            with self.in_rate_lock:
                self.in_rate_count = 0

    def _decode_capnp_msg(self, bytes: bytes, target_cls: Type[CapnpObject]) -> CapnpObject:
        try:
            return target_cls.from_bytes(bytes)
        except Exception as e1:
            e2 = SyntaxError('unknown or invalid message')
            logging.debug(e1)
            logging.error(e2)
            raise e2


def run(args=sys.argv[1:]):
    argparser = argparse.ArgumentParser(description='TalkyCars Edge Node Server')
    argparser.add_argument('--tile', default='0' * EDGE_DISTRIBUTION_TILE_LEVEL, type=str, help=f'Tile at level {EDGE_DISTRIBUTION_TILE_LEVEL} that this node is responsible for')
    argparser.add_argument('--debug', action='store_true', help='Whether or not to print debug output (default: true)')

    args = argparser.parse_args(args)

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=level)

    assert (len(args.tile) == EDGE_DISTRIBUTION_TILE_LEVEL)

    EdgeNode(covered_tile=quadkey.from_str(args.tile)).run()
