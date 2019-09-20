import logging
import os
from typing import TypeVar, Generic, Type, Dict, Tuple, Union

import capnp

from common.serialization.schema import Vector3D, RelativeBBox, GridCellState, ActorType, CapnpObject

capnp.remove_import_hook()

dirname = os.path.dirname(__file__)

relation = capnp.load(os.path.join(dirname, './capnp/python/relation.capnp'))

T = TypeVar('T')
_RelationType = Union[type(relation.TextRelation),
                      type(relation.Vector3DRelation),
                      type(relation.RelativeBBoxRelation),
                      type(relation.GridCellStateRelation),
                      type(relation.ActorTypeRelation),
                      type(relation.DynamicActorRelation)]


class PEMRelation(Generic[T], CapnpObject):
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

            msg = relation_type.new_message(confidence=self.confidence)
            if self.object is not None:
                msg.object = self.object if is_primitive else self.object.to_message()
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
        obj: CapnpObject = None
        if 'object' in obj_dict:
            obj = target_cls.from_message_dict(obj_dict['object']) if target_cls else obj_dict['object']
        return cls(confidence=obj_dict['confidence'], object=obj)
