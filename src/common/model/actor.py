from enum import Enum
from typing import Tuple

from .geom import Point3D

_Vec3 = Tuple[float, float, float]


class ActorType(Enum):
    VEHICLE = 'vehicle'
    PEDESTRIAN = 'pedestrian'
    UNKNOWN = 'unknown'


class ActorDynamics:
    def __init__(self, velocity: _Vec3 = None, acceleration: _Vec3 = None):
        self.velocity: _Vec3 = velocity
        self.acceleration: _Vec3 = acceleration


class ActorProperties:
    def __init__(self, color: str = None, extent: _Vec3 = None):
        self.color: str = color
        self.extent: _Vec3 = extent


class DynamicActor:
    def __init__(self, id: int, type: ActorType, type_id: str = None, location: Point3D = None, gnss: Point3D = None, dynamics: ActorDynamics = None, props: ActorProperties = None):
        self.id: int = id
        self.type: ActorType = type
        self.type_id: str = type_id
        self.location: Point3D = location
        self.gnss: Point3D = gnss
        self.dynamics: ActorDynamics = dynamics
        self.props: ActorProperties = props

    def __str__(self):
        return f'Dynamic actor {self.id} ({self.type_id}) of type {self.type}'
