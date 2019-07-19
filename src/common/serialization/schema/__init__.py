import os
from typing import Tuple, Type, Dict, cast

import capnp

from common import occupancy as model

capnp.remove_import_hook()

dirname = os.path.dirname(__file__)

vector3d = capnp.load(os.path.join(dirname, './capnp/vector3d.capnp'))
relative_bbox = capnp.load(os.path.join(dirname, './capnp/relative_bbox.capnp'))

class CapnpObject:
    def to_message(self):
        """
        Converts Python object to Cap'n'Proto message
        :return: [_DynamicStructReader] A Cap'n'Proto message
        """
        raise NotImplementedError('abstract class')

    def to_bytes(self) -> bytes:
        """
        Converts Python object to packed Cap'n'Proto byte array. Only makes sense for "top-level" classes.
        :return: Packed bytes array
        """
        return self.to_message().to_bytes_packed()

    @classmethod
    def from_message_dict(cls, object_dict: Dict, target_cls: Type = None):
        """
        Converts dict-serialized Cap'n'Proto message to Python object
        :param object_dict: A dict obtained by calling to_dict() on a deserialized Cap'n'Proto message
        :param target_cls: Optional Python class to decode to or None for primitives. Used for generic classes. May be ignored by class-specific implementation if target type is unambiguos. NOTE: Usually, you won't want to set this.
        :return: [CapnpObject] Resulting Python object instance
        """
        raise NotImplementedError('abstract class')

    @classmethod
    def from_bytes(cls, bytes: bytes):
        """
        Reads a packed Cap'n'Proto byte array into a Python object. Requires _get_capnp_class() to be implemented by sub-class. Only makes sense for "top-level" classes.
        :param bytes:
        :return: [CapnpObject] Resulting Python object instance
        """
        object_dict = cls._get_capnp_class().from_bytes_packed(bytes).to_dict()
        return cls.from_message_dict(object_dict)

    @classmethod
    def _get_capnp_class(cls):
        """
        Returns the current object's corresponding Cap'n'Proto message class, e.g. ego_vehicle.EgoVehicle. To be implemented sub-classes.
        :return: A Cap'n'Proto message class
        """
        raise NotImplementedError('not specified')

class Vector3D(CapnpObject):
    def __init__(self, components: Tuple[float, float, float] = None):
        self.x: float = components[0]
        self.y: float = components[1]
        self.z: float = components[2]

    def to_message(self):
        return vector3d.Vector3D.new_message(
            x=self.x,
            y=self.y,
            z=self.z
        )

    @classmethod
    def from_message_dict(cls, object_dict: Dict, target_cls: Type[CapnpObject] = None) -> CapnpObject:
        return cls((*object_dict.values(),))

    def __str__(self):
        return f'({self.x}, {self.y}, {self.z})'

class RelativeBBox(CapnpObject):
    def __init__(self, lower: Vector3D, higher: Vector3D):
        self.lower: Vector3D = lower
        self.higher: Vector3D = higher

    def to_message(self):
        return relative_bbox.RelativeBBox.new_message(
            lower=self.lower.to_message(),
            higher=self.higher.to_message()
        )

    @classmethod
    def from_message_dict(cls, object_dict: Dict, target_cls: Type[CapnpObject] = None) -> CapnpObject:
        lower: Vector3D = cast(Vector3D, Vector3D.from_message_dict(object_dict['lower']))
        higher: Vector3D = cast(Vector3D, Vector3D.from_message_dict(object_dict['higher']))
        return cls(lower, higher)

    def __str__(self):
        return f'({self.lower}, {self.higher})'

class GridCellState(CapnpObject):
    def __init__(self, value: model.GridCellState = None):
        self.value: GridCellState = value

    @staticmethod
    def free():
        return GridCellState(value=model.GridCellState.FREE)

    @staticmethod
    def occupied():
        return GridCellState(value=model.GridCellState.OCCUPIED)

    @staticmethod
    def unknown():
        return GridCellState(value=model.GridCellState.UNKNOWN)

    def to_message(self):
        return str(self.value).split('.')[1].lower()

    @classmethod
    def from_message_dict(cls, object_dict: Dict, target_cls: Type = None):
        if object_dict == 'free':
            return GridCellState(value=model.GridCellState.FREE)
        if object_dict == 'occupied':
            return GridCellState(value=model.GridCellState.OCCUPIED)
        if object_dict == 'unknown':
            return GridCellState(value=model.GridCellState.UNKNOWN)

    def __str__(self):
        return str(self.value)