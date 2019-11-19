import os
from abc import ABC, abstractmethod
from typing import Tuple, List, Type

from common.model import ActorType as At
from common.occupancy import GridCellState as Gss
from common.serialization.schema.proto import actor_pb2
from .proto import misc_pb2

dirname = os.path.dirname(__file__)


class ProtobufObject(ABC):
    @abstractmethod
    def to_message(self):
        pass

    @classmethod
    def from_message(cls, msg, target_cls: Type['ProtobufObject'] = None) -> 'ProtobufObject':
        pass

    def to_bytes(self) -> bytes:
        return self.to_message().SerializeToString()

    @classmethod
    def from_bytes(cls, bytes: bytes, target_cls: Type['ProtobufObject'] = None) -> 'ProtobufObject':
        msg = target_cls.get_protobuf_class()() if target_cls else cls.get_protobuf_class()()
        msg.ParseFromString(bytes)

        return cls.from_message(msg)

    @classmethod
    def get_protobuf_class(cls):
        raise NotImplementedError('not implemented for this subtype')


class Vector3D(ProtobufObject):
    def __init__(self, components: Tuple[float, float, float] = None):
        self.x: float = components[0]
        self.y: float = components[1]
        self.z: float = components[2]

    def to_message(self):
        return misc_pb2.Vector3D(x=self.x, y=self.y, z=self.z)

    def as_tuple(self) -> Tuple[float, float, float]:
        return self.x, self.y, self.z

    @classmethod
    def from_message(cls, msg, target_cls: Type[ProtobufObject] = None) -> 'Vector3D':
        return cls((msg.x, msg.y, msg.z))

    @classmethod
    def get_protobuf_class(cls):
        return misc_pb2.Vector3D

    def __str__(self):
        return f'({self.x}, {self.y}, {self.z})'


class RelativeBBox(ProtobufObject):
    def __init__(self, lower: Vector3D, higher: Vector3D):
        self.lower: Vector3D = lower
        self.higher: Vector3D = higher

    def to_message(self):
        return misc_pb2.RelativeBBox(
            lower=self.lower.to_message(),
            higher=self.higher.to_message()
        )

    @classmethod
    def from_message(cls, msg, target_cls: Type[ProtobufObject] = None) -> 'RelativeBBox':
        return cls(
            lower=Vector3D.from_message(msg.lower),
            higher=Vector3D.from_message(msg.higher),
        )

    @classmethod
    def get_protobuf_class(cls):
        return misc_pb2.RelativeBBox

    def __str__(self):
        return f'({self.lower}, {self.higher})'


class GridCellState(ProtobufObject):
    N: int = 3

    def __init__(self, value: Gss = None):
        self.value: Gss = value
        self._as_string: List[str] = ['free', 'occupied', 'unknown']

    @staticmethod
    def free() -> 'GridCellState':
        return GridCellState(value=Gss.FREE)

    @staticmethod
    def occupied() -> 'GridCellState':
        return GridCellState(value=Gss.OCCUPIED)

    @staticmethod
    def unknown() -> 'GridCellState':
        return GridCellState(value=Gss.UNKNOWN)

    @staticmethod
    def options():
        return [GridCellState.free(), GridCellState.occupied(), GridCellState.unknown()]

    def to_message(self):
        return self.value

    @classmethod
    def from_message(cls, msg, target_cls: Type[ProtobufObject] = None) -> 'GridCellState':
        return cls(msg)

    @classmethod
    def get_protobuf_class(cls):
        raise NotImplementedError('not implemented')

    def __str__(self):
        return str(self.value)

    def __eq__(self, other):
        return isinstance(other, GridCellState) and other.value == self.value or isinstance(other, int) and other == self.value

    def __ne__(self, other):
        return not self.__eq__(other)


class ActorType(ProtobufObject):
    def __init__(self, value: At = None):
        self.value: ActorType = value

    @staticmethod
    def vehicle() -> 'ActorType':
        return ActorType(value=At.VEHICLE)

    @staticmethod
    def pedestrian() -> 'ActorType':
        return ActorType(value=At.PEDESTRIAN)

    @staticmethod
    def unknown() -> 'ActorType':
        return ActorType(value=At.UNKNOWN)

    @staticmethod
    def _map_to_int(type: At) -> int:
        options = [At.VEHICLE, At.PEDESTRIAN, At.UNKNOWN]
        try:
            return options.index(type)
        except ValueError:
            return 2

    def to_message(self):
        options = [actor_pb2.TYPE_VEHICLE, actor_pb2.TYPE_PEDESTRIAN, actor_pb2.TYPE_UNKNOWN]
        return options[self._map_to_int(self.value)]

    @classmethod
    def from_message(cls, msg, target_cls: Type[ProtobufObject] = None) -> 'ActorType':
        return cls(msg)

    @classmethod
    def get_protobuf_class(cls):
        raise NotImplementedError('not implemented')

    def __str__(self):
        return str(self.value)