import logging
import time
from multiprocessing.pool import ThreadPool
from threading import Lock
from typing import Iterable, Dict, Tuple, Callable, Set

from common import quadkey
from common.bridge import MqttBridge
from common.constants import *
from common.quadkey import QuadKey

'''
    In practice there is going to be multiple edge nodes with a separate MQTT broker alongside each.
    Every edge node is responsible for observation graphs / traffic scene representations from a 
    certain geographical region, e.g. a tile of level 15. 
    Multiple clients publish observations (for now, only occupancy grids) for another certain
    geographic area, e.g. a grid of 5x5 level 24 tiles, that lies at least partially within that tile.
    In return, every client receives a larger, fused scene representation from the edge node,
    e.g. all fused level 24 tiles within its surrounding 9 level 19 tiles. 

    Relations:      client <-> edge node ~ n:1, edge node <-> broker ~ 1:1
    Tiles Types:    "occupancy tile" (OT)   ~ what client observes multiple times within a grid
                    "node tile" (NT)        ~ what an edge node is responsible for
                    "remote grid tile" (RT) ~ what a client receives as cooperative perception
    Tile Levels:    OT < k * OT < RT < NT
    
    More schematic sketch: https://go.gliffy.com/go/html5/13072860
'''


class TileSubscriptionService:
    def __init__(
            self,
            on_graph_cb: Callable,
            rate_limit: float = 0.0,
            topic_prefix: str = TOPIC_PREFIX_GRAPH_FUSED_OUT,
            edge_node_level: int = EDGE_DISTRIBUTION_TILE_LEVEL,
            remote_tile_level: int = REMOTE_GRID_TILE_LEVEL,
    ):
        self.active_bridges: Dict[str, MqttBridge] = {}
        self.active_subscriptions: Set[str] = set()
        self.current_position: QuadKey = None
        self.current_parent: QuadKey = None
        self.on_graph_cb = self._wrap_graph_callback(on_graph_cb)
        self.rate_limit: float = rate_limit
        self.locks: Dict[str, Lock] = {'graph': Lock()}
        self.edge_node_level: int = edge_node_level
        self.remote_tile_level: int = remote_tile_level
        self.topic_prefix: int = topic_prefix

        self.pool: ThreadPool = ThreadPool(1)

    def update_position(self, qk: QuadKey):
        parent = quadkey.from_str(qk.key[:self.remote_tile_level])

        if self.current_parent and parent and self.current_parent == parent:
            return

        logging.debug(f'Subscription-relevant tile changed from {self.current_parent} to {parent}.')

        sub_tiles = frozenset(parent.nearby(1))
        node_tiles = frozenset([key[:self.edge_node_level] for key in sub_tiles])

        # Handle connections: clean up old
        for node_key in set(self.active_bridges.keys()).difference(node_tiles):
            logging.debug(f'Tearing down connection for {node_key}')

            self.active_bridges[node_key].disconnect()
            del self.active_bridges[node_key]

        # Handle connections: init new
        for node_key in node_tiles.difference(set(self.active_bridges.keys())):
            logging.debug(f'Connecting to {node_key}')

            bridge = MqttBridge(*self._resolve_mqtt_geodns(quadkey.from_str(node_key)))
            try:
                bridge.listen(block=False)
            except:
                logging.warning(f'Failed to connect to MQTT bridge at {bridge.broker_config}')
                return
            self.active_bridges[node_key] = bridge

        # Handle subscriptions: clean up old
        for sub_key in self.active_subscriptions.difference(sub_tiles):
            self.active_subscriptions.remove(sub_key)
            node_key = sub_key[:self.edge_node_level]
            if node_key not in self.active_bridges:
                continue

            logging.debug(f'Removing subscription for {sub_key} at {node_key}')

            bridge = self.active_bridges[node_key]
            bridge.unsubscribe(f'{self.topic_prefix}/{sub_key}', self.on_graph_cb)

        # Handle subscriptions: init new
        for sub_key in sub_tiles.difference(self.active_subscriptions):
            node_key = sub_key[:self.edge_node_level]

            logging.debug(f'Attempting to subscribe to {sub_key} at {node_key}')

            bridge = self._try_get_bridge(node_key)

            if not bridge:
                continue

            bridge.subscribe(f'{self.topic_prefix}/{sub_key}', self.on_graph_cb)
            self.active_subscriptions.add(sub_key)

        self.current_position = qk
        self.current_parent = parent

    # Maybe move graph generation logic into here?
    def publish_graph(self, encoded_msg: bytes, contained_tiles: Iterable[str]):
        if not self.current_parent:
            return

        # TODO: Publish to multiple bridges in case my observed grid stretches
        #  among more than one EDGE_DISTRIBUTION_TILE_LEVEL tiles
        bridge = self._try_get_bridge(self.current_parent.key)

        if not bridge:
            return

        bridge.publish(TOPIC_GRAPH_RAW_IN, encoded_msg)

    def active(self) -> bool:
        return len(self.active_bridges) > 0 and all(list(map(lambda b: b.connected, self.active_bridges.values())))

    def tear_down(self):
        for b in self.active_bridges.values():
            b.disconnect()

    def _try_get_bridge(self, for_key: str) -> MqttBridge:
        for_key = for_key[:self.edge_node_level]
        if for_key not in self.active_bridges:
            logging.warning(f'No active bridge responsible for {for_key} found.')
            return None
        return self.active_bridges[for_key]

    def _wrap_graph_callback(self, cb: Callable) -> Callable:
        def wcb(args):
            lock = self.locks['graph']
            if lock.locked():
                return

            lock.acquire()

            cb(args)

            if self.rate_limit > 0:
                def unlock():
                    time.sleep(self.rate_limit)
                    lock.release()

                self.pool.apply_async(unlock)
            else:
                lock.release()

        return wcb

    '''
        Mocks an actual DNS-like type of system to resolve quad keys of node tiles to broker addresses.
    '''

    @staticmethod
    def _resolve_mqtt_geodns(for_tile: QuadKey) -> Tuple[str, int]:
        return MQTT_BASE_HOSTNAME, 1883
