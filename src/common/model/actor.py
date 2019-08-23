from enum import Enum
from typing import Tuple

from common.model import UncertainProperty
from .geom import Point3D, Point2D

_Vec3 = Tuple[float, float, float]
_BBox = Tuple[Point2D, Point2D, Point2D, Point2D]


class ActorType(Enum):
    VEHICLE = 'vehicle'
    PEDESTRIAN = 'pedestrian'
    UNKNOWN = 'unknown'


class ActorDynamics:
    def __init__(self, velocity: UncertainProperty[Point3D] = None, acceleration: UncertainProperty[Point3D] = None):
        self.velocity: UncertainProperty[Point3D] = velocity
        self.acceleration: UncertainProperty[Point3D] = acceleration


class ActorProperties:
    def __init__(self, color: UncertainProperty[str] = None, extent: UncertainProperty[Point3D] = None, bbox: UncertainProperty[_BBox] = None):
        self.color: UncertainProperty[str] = color
        self.extent: UncertainProperty[Point3D] = extent
        self.bbox: UncertainProperty[_BBox] = bbox


class DynamicActor:
    def __init__(self, id: int, type: UncertainProperty[ActorType], type_id: str = None, location: UncertainProperty[Point3D] = None, gnss: UncertainProperty[Point3D] = None, dynamics: ActorDynamics = None, props: ActorProperties = None):
        self.id: int = id
        self.type: UncertainProperty[ActorType] = type
        self.type_id: str = type_id
        self.location: UncertainProperty[Point3D] = location
        self.gnss: UncertainProperty[Point3D] = gnss
        self.dynamics: ActorDynamics = dynamics
        self.props: ActorProperties = props

    def __str__(self):
        return f'Dynamic actor {self.id} ({self.type_id}) of type {self.type}'
