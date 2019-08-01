import os
from typing import TypeVar, Generic, Type, Dict, Tuple

import capnp
from capnp.lib.capnp import _StructModule

from common.serialization.schema import Vector3D, RelativeBBox, GridCellState, ActorType, CapnpObject

capnp.remove_import_hook()

T = TypeVar('T')

dirname = os.path.dirname(__file__)

relation = capnp.load(os.path.join(dirname, './capnp/relation.capnp'))


class PEMRelation(Generic[T], CapnpObject):
    def __init__(self, confidence: float, object: T):
        self.confidence: float = confidence
        self.object: T = object

    def to_message(self):
        relation_type, is_primitive = self._resolve_relation_type(self.object)
        try:
            return relation_type.new_message(
                confidence=self.confidence,
                object=self.object if is_primitive else self.object.to_message()
            )
        except TypeError:
            return None

    @staticmethod
    def _resolve_relation_type(obj) -> Tuple[Type[_StructModule], bool]:
        from common.serialization.schema.actor import PEMDynamicActor

        if isinstance(obj, Vector3D):
            return relation.Vector3DRelation, False
        elif isinstance(obj, RelativeBBox):
            return relation.RelativeBBoxRelation, False
        elif isinstance(obj, PEMDynamicActor):
            return relation.DynamicActorRelation, False
        elif isinstance(obj, GridCellState):
            return relation.GridCellStateRelation, False
        elif isinstance(obj, ActorType):
            return relation.ActorTypeRelation, False
        elif isinstance(obj, str):
            return relation.TextRelation, True
        else:
            raise TypeError(f'unknown relation type "{type(obj)}"')

    @classmethod
    def from_message_dict(cls, obj_dict: Dict, target_cls: Type[CapnpObject] = None) -> 'PEMRelation':
        obj = target_cls.from_message_dict(obj_dict['object']) if target_cls else obj_dict['object']
        return cls(confidence=obj_dict['confidence'], object=obj)
