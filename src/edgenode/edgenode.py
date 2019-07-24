import logging
from typing import Type, cast, Iterable, Set

from common.bridge import MqttBridge
from common.constants import *
from common.serialization.schema import CapnpObject
from common.serialization.schema.base import PEMTrafficScene
from edgenode.fusion import FusionService


class EdgeNode:
    def __init__(self):
        self.mqtt: MqttBridge = None
        self.fusion_srvc: FusionService = FusionService()
        self.covered_quadkeys: Set[str] = set()  # TODO: Read from env

    def run(self):
        self.mqtt = MqttBridge()
        self.mqtt.subscribe(TOPIC_PREFIX_GRAPH_RAW_IN + '/#', self._on_graph)
        self.mqtt.listen()

    def _on_graph(self, message: bytes):
        graph: PEMTrafficScene = cast(PEMTrafficScene, self._decode_capnp_msg(message, target_cls=PEMTrafficScene))
        self.fusion_srvc.push(graph)

        fused_graph: PEMTrafficScene = cast(PEMTrafficScene, self.fusion_srvc.get())

        covered_keys: Iterable[str] = self.covered_quadkeys if len(self.covered_quadkeys) > 0 else fused_graph.occupancy_grid.get_parent_tiles(REMOTE_GRID_TILE_LEVEL)
        encoded_graph: bytes = fused_graph.to_bytes()
        for k in covered_keys:
            self.mqtt.publish(f'{TOPIC_PREFIX_GRAPH_FUSED_OUT}/{k}', encoded_graph)

    def _decode_capnp_msg(self, bytes: bytes, target_cls: Type[CapnpObject]) -> CapnpObject:
        try:
            return target_cls.from_bytes(bytes)
        except Exception as e1:
            e2 = SyntaxError('unknown or invalid message')
            logging.debug(e1)
            logging.error(e2)
            raise e2

def run():
    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
    EdgeNode().run()
