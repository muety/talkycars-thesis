from enum import Enum
from typing import Tuple

from common.model import UncertaintyAware
from .geom import Point3D

_Vec3 = Tuple[float, float, float]


class ActorType(Enum):
    VEHICLE = 'vehicle'
    PEDESTRIAN = 'pedestrian'
    UNKNOWN = 'unknown'


class ActorDynamics:
    def __init__(self, velocity: UncertaintyAware[_Vec3] = None, acceleration: UncertaintyAware[_Vec3] = None):
        self.velocity: UncertaintyAware[_Vec3] = velocity
        self.acceleration: UncertaintyAware[_Vec3] = acceleration


class ActorProperties:
    def __init__(self, color: UncertaintyAware[str] = None, extent: UncertaintyAware[_Vec3] = None):
        self.color: UncertaintyAware[str] = color
        self.extent: UncertaintyAware[_Vec3] = extent


class DynamicActor:
    def __init__(self, id: int, type: UncertaintyAware[ActorType], type_id: str = None, location: UncertaintyAware[Point3D] = None, gnss: UncertaintyAware[Point3D] = None, dynamics: ActorDynamics = None, props: ActorProperties = None):
        self.id: int = id
        self.type: UncertaintyAware[ActorType] = type
        self.type_id: str = type_id
        self.location: UncertaintyAware[Point3D] = location
        self.gnss: UncertaintyAware[Point3D] = gnss
        self.dynamics: ActorDynamics = dynamics
        self.props: ActorProperties = props

    def __str__(self):
        return f'Dynamic actor {self.id} ({self.type_id}) of type {self.type}'
