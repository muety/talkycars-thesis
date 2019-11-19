import logging
import os
from typing import TypeVar, Generic, Type, Tuple, Union

from common.serialization.schema import Vector3D, RelativeBBox, GridCellState, ProtobufObject, ActorType
from common.serialization.schema.proto import misc_pb2, occupancy_pb2, actor_pb2

dirname = os.path.dirname(__file__)

T = TypeVar('T')
_RelationType = Union[type(misc_pb2.TextRelation),
                      type(misc_pb2.Vector3DRelation),
                      type(misc_pb2.RelativeBBoxRelation),
                      type(occupancy_pb2.GridCellStateRelation),
                      type(actor_pb2.ActorTypeRelation),
                      type(actor_pb2.DynamicActorRelation)]


class PEMRelation(Generic[T], ProtobufObject):
    def __init__(self, confidence: float, object: T):
        self.confidence: float = confidence
        self.object: T = object

    def to_message(self, type_hint: Type[_RelationType] = None):
        relation_type, is_primitive = self._resolve_relation_type(self.object)

        try:
            if not relation_type and not type_hint:
                raise TypeError('unknown relation type')
            elif not relation_type and type_hint:
                relation_type = type_hint

            obj = None
            if self.object is not None:
                obj = self.object if is_primitive else self.object.to_message()

            msg = relation_type(
                confidence=self.confidence,
                object=obj
            )

            return msg

        except TypeError as e:
            logging.warning(e)
            return None

    @staticmethod
    def _resolve_relation_type(obj) -> Tuple[Type[_RelationType], bool]:
        from common.serialization.schema.actor import PEMDynamicActor

        if obj is None:
            return None, True
        elif isinstance(obj, Vector3D):
            return misc_pb2.Vector3DRelation, False
        elif isinstance(obj, RelativeBBox):
            return misc_pb2.RelativeBBoxRelation, False
        elif isinstance(obj, PEMDynamicActor):
            return actor_pb2.DynamicActorRelation, False
        elif isinstance(obj, GridCellState):
            return occupancy_pb2.GridCellStateRelation, False
        elif isinstance(obj, ActorType):
            return actor_pb2.ActorTypeRelation, False
        elif isinstance(obj, str):
            return misc_pb2.TextRelation, True
        else:
            raise TypeError(f'unknown relation type "{type(obj)}"')

    @classmethod
    def get_protobuf_class(cls):
        raise NotImplementedError('not implemented')

    @classmethod
    def from_message(cls, msg, target_cls: Type[ProtobufObject] = None) -> 'PEMRelation':
        obj: ProtobufObject = None
        obj = target_cls.from_message(msg.object) if target_cls else msg.object
        return cls(confidence=msg.confidence, object=obj)
