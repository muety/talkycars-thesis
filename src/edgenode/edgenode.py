import logging
from typing import Type, cast

from common.bridge import MqttBridge
from common.constants import *
from common.serialization.schema import CapnpObject
from common.serialization.schema.base import PEMTrafficScene
from edgenode.fusion import FusionService


class EdgeNode:
    def __init__(self):
        self.fusion_srvc: FusionService = FusionService()
        self.mqtt: MqttBridge = None

    def run(self):
        self.mqtt = MqttBridge()
        self.mqtt.subscribe(TOPIC_PREFIX_GRAPH_RAW_IN + '/#', self._on_graph)
        self.mqtt.listen()

    def _on_graph(self, message: bytes):
        graph: PEMTrafficScene = cast(PEMTrafficScene, self._decode_capnp_msg(message, target_cls=PEMTrafficScene))
        fused_graph: PEMTrafficScene = self.fusion_srvc.fuse([graph])  # TODO: Implement
        print(fused_graph)

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
