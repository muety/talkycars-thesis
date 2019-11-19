import os
from typing import Type

from common.serialization.schema import ProtobufObject, Vector3D, RelativeBBox, ActorType
from common.serialization.schema.proto import actor_pb2
from .relation import PEMRelation

dirname = os.path.dirname(__file__)


class PEMDynamicActor(ProtobufObject):
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
        return actor_pb2.DynamicActor(
            id=self.id,
            type=self.type.to_message() if self.type and self.type.object else None,
            color=self.color.to_message() if self.color and self.color.object else None,
            position=self.position.to_message() if self.position and self.position.object else None,
            boundingBox=self.bounding_box.to_message() if self.bounding_box and self.bounding_box.object else None,
            velocity=self.velocity.to_message() if self.velocity and self.velocity.object else None,
            acceleration=self.acceleration.to_message() if self.acceleration and self.acceleration.object else None,
        )

    @classmethod
    def from_message(cls, msg, target_cls: Type[ProtobufObject] = None) -> 'PEMDynamicActor':
        id = msg.id
        type = PEMRelation.from_message(msg.type, target_cls=ActorType) if msg.type.confidence > 0 else None
        color = PEMRelation.from_message(msg.color) if msg.color.confidence > 0 else None
        position = PEMRelation.from_message(msg.position, target_cls=Vector3D) if msg.position.confidence > 0 else None
        bounding_box = PEMRelation.from_message(msg.boundingBox, target_cls=RelativeBBox) if msg.boundingBox.confidence > 0 else None
        velocity = PEMRelation.from_message(msg.velocity, target_cls=Vector3D) if msg.velocity.confidence > 0 else None
        acceleration = PEMRelation.from_message(msg.acceleration, target_cls=Vector3D) if msg.acceleration.confidence > 0 else None

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
    def get_protobuf_class(cls):
        return actor_pb2.DynamicActor

    def __str__(self):
        return f'Dynamic Actor [{self.id}]'
