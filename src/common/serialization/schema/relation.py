import os
from typing import TypeVar, Generic, Type, Dict

import capnp

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
        from common.serialization.schema.actor import PEMDynamicActor

        is_primitive: bool = False

        if isinstance(self.object, Vector3D):
            relation_type = relation.Vector3DRelation
        elif isinstance(self.object, RelativeBBox):
            relation_type = relation.RelativeBBoxRelation
        elif isinstance(self.object, PEMDynamicActor):
            relation_type = relation.DynamicActorRelation
        elif isinstance(self.object, GridCellState):
            relation_type = relation.GridCellStateRelation
        elif isinstance(self.object, ActorType):
            relation_type = relation.ActorTypeRelation
        elif isinstance(self.object, str):
            relation_type = relation.TextRelation
            is_primitive = True
        else:
            raise TypeError('unknown relation type')

        return relation_type.new_message(
            confidence=self.confidence,
            object=self.object if is_primitive else self.object.to_message()
        )

    @classmethod
    def from_message_dict(cls, obj_dict: Dict, target_cls: Type[CapnpObject] = None) -> 'PEMRelation':
        obj = target_cls.from_message_dict(obj_dict['object']) if target_cls else obj_dict['object']
        return cls(confidence=obj_dict['confidence'], object=obj)
