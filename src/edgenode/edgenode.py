import argparse
import logging
import multiprocessing
import sys
import time
from collections import deque
from multiprocessing.pool import ThreadPool, Pool, AsyncResult
from threading import RLock, Thread, Lock, BoundedSemaphore
from typing import Type, cast, List, Set, Dict, Deque

import numpy as np

from common import quadkey
from common.bridge import MqttBridge
from common.constants import *
from common.fusion import FusionServiceFactory, PEMFusionService
from common.quadkey import QuadKey
from common.serialization.schema import CapnpObject
from common.serialization.schema.base import PEMTrafficScene
from common.util import GracefulKiller, proc_wrap

EVAL_RATE_SECS = 5  # hertz⁻¹
TICK_RATE = 10  # hertz

class EdgeNode:
    def __init__(self, covered_tile: QuadKey):
        self.killer: GracefulKiller = GracefulKiller()

        self.mqtt: MqttBridge = None
        self.fusion_srvc: PEMFusionService = FusionServiceFactory.get(PEMTrafficScene, covered_tile)
        self.covered_tile: QuadKey = covered_tile
        self.children_tiles: List[QuadKey] = covered_tile.children(REMOTE_GRID_TILE_LEVEL)
        self.children_tile_keys: Set[str] = set(map(lambda t: t.key, self.children_tiles))
        self.in_queue: Dict[int, PEMTrafficScene] = {}

        self.rate_count_thread: Thread = Thread(target=self._eval_rate, daemon=True)
        self.rate_lock: RLock = RLock()
        self.in_rate_count: int = 0
        self.fuse_delay_tracker: Deque[float] = deque(maxlen=100)

        self.tick_timeout: float = 1 / TICK_RATE
        self.last_tick: float = time.monotonic()
        self.tick_lock: Lock = Lock()

        self.send_pool: ThreadPool = ThreadPool(12, )  # GIL Thread Pool
        self.decode_pool: Pool = Pool(6, )
        self.semaphore: BoundedSemaphore = BoundedSemaphore(value=6)

    def run(self):
        self.rate_count_thread.start()

        self.mqtt = MqttBridge()
        self.mqtt.subscribe(TOPIC_GRAPH_RAW_IN, self._on_graph)
        self.mqtt.listen(block=False)

        while True:
            if self.killer.kill_now:
                self.mqtt.disconnect()
                self.decode_pool.close()
                self.decode_pool.join()
                self.decode_pool.terminate()
                break

            self.last_tick = time.monotonic()
            self.tick()
            self.flush()

            diff = time.monotonic() - self.last_tick

            self.fuse_delay_tracker.append(diff)

            time.sleep(max(0.0, self.tick_timeout - diff))

    def tick(self):
        t0 = time.monotonic()
        fused_graphs: Dict[str, PEMTrafficScene] = self.fusion_srvc.get(max_age=GRID_TTL_SEC)
        if not fused_graphs:
            return

        self.send_pool.starmap_async(self._wrapped_pg, fused_graphs.items())
        print(time.monotonic() - t0)

    def flush(self):
        for sender_id, graph in self.in_queue.items():
            self.fusion_srvc.push(sender_id, graph)
        self.in_queue.clear()

    def _on_graph(self, message: bytes):
        if not self.semaphore.acquire(blocking=False):
            return

        graph_promise: AsyncResult = self.decode_pool.apply_async(proc_wrap,
                                                                  (self._decode_capnp_msg, message, PEMTrafficScene))
        t: Thread = Thread(target=proc_wrap, args=(self._wait_for_decode, graph_promise,), daemon=True)
        t.start()

    def _wait_for_decode(self, promise: AsyncResult):
        try:
            graph: PEMTrafficScene = cast(PEMTrafficScene, promise.get(GRID_TTL_SEC))
            with self.tick_lock:
                self.in_queue[graph.measured_by.id] = graph

            with self.rate_lock:
                self.in_rate_count += 1
        except multiprocessing.context.TimeoutError:
            pass

        self.semaphore.release()

    def _publish_graph(self, for_tile: str, graph: PEMTrafficScene):
        try:
            encoded_graph: bytes = graph.to_bytes()
            self.mqtt.publish(f'{TOPIC_PREFIX_GRAPH_FUSED_OUT}/{for_tile}', encoded_graph)
        except Exception as e:
            logging.warning(e)

    def _wrapped_pg(self, *args, **kwargs):
        return proc_wrap(self._publish_graph, *args, **kwargs)

    def _eval_rate(self):
        while not self.mqtt or not self.mqtt.connected:
            time.sleep(.5)

        while self.mqtt.connected:
            time.sleep(EVAL_RATE_SECS)
            logging.debug(
                f'Ø Message Rate: {self.in_rate_count / EVAL_RATE_SECS} msgs / sec, Ø Fusion Delay: {np.around(np.mean(self.fuse_delay_tracker), decimals=2)} sec')

            with self.rate_lock:
                self.in_rate_count = 0

    @staticmethod
    def _decode_capnp_msg(bytes: bytes, target_cls: Type[CapnpObject]) -> CapnpObject:
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
