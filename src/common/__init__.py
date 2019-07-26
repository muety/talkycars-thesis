from enum import Enum
from typing import Tuple

from common.geom import BBox3D, Point3D

_Vec3 = Tuple[float, float, float]


class ActorType(Enum):
    VEHICLE = 'vehicle'
    PEDESTRIAN = 'pedestrian'
    UNKNOWN = 'unknown'


class ActorDynamics:
    def __init__(self, velocity: _Vec3 = None, acceleration: _Vec3 = None):
        self.velocity = velocity
        self.acceleration = acceleration


class ActorProperties:
    def __init__(self, color: str = None, extent: _Vec3 = None):
        self.color = color
        self.extent = extent


class DynamicActor:
    def __init__(self, id: int, type: ActorType, location: Point3D = None, gnss: Point3D = None, dynamics: ActorDynamics = None, props: ActorProperties = None):
        self.id = id
        self.type = type
        self.location = location
        self.gnss = gnss
        self.dynamics = dynamics
        self.props = props
