import os
from typing import Dict, Type

import capnp

from common.serialization.schema import CapnpObject, Vector3D, RelativeBBox, ActorType
from .relation import PEMRelation

capnp.remove_import_hook()

dirname = os.path.dirname(__file__)

dynamic_actor = capnp.load(os.path.join(dirname, './capnp/actor.capnp'))


class PEMDynamicActor(CapnpObject):
    def __init__(self, **entries):
        self.id: int = None
        self.type: PEMRelation[ActorType] = None
        self.color: PEMRelation[str] = None
        self.position: PEMRelation[Vector3D] = None
        self.bounding_box: PEMRelation[RelativeBBox] = None
        self.velocity: PEMRelation[Vector3D] = None
        self.acceleration: PEMRelation[Vector3D] = None

        if len(entries) > 0:
            self.__dict__.update(**entries)

    def to_message(self):
        me = dynamic_actor.DynamicActor.new_message()

        me.id = self.id
        if self.color and self.color.object:
            me.color = self.color.to_message()
        if self.position and self.position.object:
            me.position = self.position.to_message()
        if self.bounding_box and self.bounding_box.object:
            me.boundingBox = self.bounding_box.to_message()
        if self.velocity and self.velocity.object:
            me.velocity = self.velocity.to_message()
        if self.acceleration and self.acceleration.object:
            me.acceleration = self.acceleration.to_message()

        return me

    @classmethod
    def from_message_dict(cls, object_dict: Dict, target_cls: Type = None) -> 'PEMDynamicActor':
        id = object_dict['id'] if 'id' in object_dict else None
        type = PEMRelation.from_message_dict(object_dict['type']) if 'type' in object_dict else None
        color = PEMRelation.from_message_dict(object_dict['color']) if 'color' in object_dict else None
        position = PEMRelation.from_message_dict(object_dict['position'], target_cls=Vector3D) if 'position' in object_dict else None
        bounding_box = PEMRelation.from_message_dict(object_dict['boundingBox'], target_cls=RelativeBBox) if 'boundingBox' in object_dict else None
        velocity = PEMRelation.from_message_dict(object_dict['velocity'], target_cls=Vector3D) if 'velocity' in object_dict else None
        acceleration = PEMRelation.from_message_dict(object_dict['acceleration'], target_cls=Vector3D) if 'acceleration' in object_dict else None

        return cls(
            id=id,
            type=type,
            color=color,
            position=position,
            bounding_box=bounding_box,
            velocity=velocity,
            acceleration=acceleration
        )

    @classmethod
    def _get_capnp_class(cls):
        return dynamic_actor.EgoVehicle

    def __str__(self):
        return f'Dynamic Actor [{self.id}]'
