import os
from typing import Dict, Type

import capnp

from common.serialization.schema import CapnpObject, Vector3D, RelativeBBox
from .relation import PEMRelation

capnp.remove_import_hook()

dirname = os.path.dirname(__file__)

ego_vehicle = capnp.load(os.path.join(dirname, './capnp/ego_vehicle.capnp'))


class PEMEgoVehicle(CapnpObject):
    def __init__(self, **entries):
        self.id: int = None
        self.color: PEMRelation[str] = None
        self.position: PEMRelation[Vector3D] = None
        self.bounding_box: PEMRelation[RelativeBBox] = None
        self.velocity: PEMRelation[Vector3D] = None
        self.acceleration: PEMRelation[Vector3D] = None

        if len(entries) > 0:
            self.__dict__.update(**entries)

    def to_message(self):
        me = ego_vehicle.EgoVehicle.new_message()

        me.id = self.id
        if self.color is not None:
            me.color = self.color.to_message()
        if self.position is not None:
            me.position = self.position.to_message()
        if self.bounding_box is not None:
            me.boundingBox = self.bounding_box.to_message()
        if self.velocity is not None:
            me.velocity = self.velocity.to_message()
        if self.acceleration is not None:
            me.acceleration = self.acceleration.to_message()

        return me

    @classmethod
    def from_message_dict(cls, object_dict: Dict, target_cls: Type = None) -> 'PEMEgoVehicle':
        id = object_dict['id'] if 'id' in object_dict else None
        color = PEMRelation.from_message_dict(object_dict['color']) if 'color' in object_dict else None
        position = PEMRelation.from_message_dict(object_dict['position'], target_cls=Vector3D) if 'position' in object_dict else None
        bounding_box = PEMRelation.from_message_dict(object_dict['boundingBox'], target_cls=RelativeBBox) if 'boundingBox' in object_dict else None
        velocity = PEMRelation.from_message_dict(object_dict['velocity'], target_cls=Vector3D) if 'velocity' in object_dict else None
        acceleration = PEMRelation.from_message_dict(object_dict['acceleration'], target_cls=Vector3D) if 'acceleration' in object_dict else None

        return cls(
            id=id,
            color=color,
            position=position,
            bounding_box=bounding_box,
            velocity=velocity,
            acceleration=acceleration
        )

    @classmethod
    def _get_capnp_class(cls):
        return ego_vehicle.EgoVehicle

    def __str__(self):
        return f'Ego Vehicle [{self.id}]'
