from typing import List, Dict, FrozenSet, Tuple, cast

import carla
from common import quadkey
from common.constants import *
from common.model import ActorType as At
from common.model import DynamicActor, Point2D, UncertainProperty, Point3D, ActorDynamics, ActorProperties
from common.quadkey import QuadKey
from common.serialization.schema import RelativeBBox, Vector3D, ActorType
from common.serialization.schema.actor import PEMDynamicActor
from common.serialization.schema.relation import PEMRelation
from common.util import geo


def map_dynamic_actor(actor: carla.Actor, world_map: carla.Map) -> DynamicActor:
    location: carla.Location = actor.get_location()
    gnss: carla.GeoLocation = world_map.transform_to_geolocation(location)
    velocity: carla.Vector3D = actor.get_velocity()
    acceleration: carla.Vector3D = actor.get_acceleration()
    color: str = str(actor.attributes['color']) if 'color' in actor.attributes else None
    extent: carla.Vector3D = actor.bounding_box.extent

    transform: carla.Transform = carla.Transform(rotation=actor.get_transform().rotation)

    transformed_extent: Tuple[carla.Location, carla.Location, carla.Location, carla.Location] = (
        transform.transform(carla.Location(+extent.x, +extent.y, 0)),
        transform.transform(carla.Location(+extent.x, -extent.y, 0)),
        transform.transform(carla.Location(-extent.x, -extent.y, 0)),
        transform.transform(carla.Location(-extent.x, +extent.y, 0)),
    )

    bbox: Tuple[Point2D, Point2D, Point2D, Point2D] = cast(Tuple[Point2D, Point2D, Point2D, Point2D], tuple(map(
        lambda t: geoloc2point2d(
            world_map.transform_to_geolocation(carla.Vector3D(location.x + t.x, location.y + t.y, location.z))
        ), transformed_extent)
    ))

    return DynamicActor(
        id=actor.id,
        type=UncertainProperty(1., resolve_carla_type(actor.type_id)),
        type_id=actor.type_id,
        location=UncertainProperty(1., Point3D(location.x, location.y, location.z)),
        gnss=UncertainProperty(1., Point3D(gnss.latitude, gnss.longitude, gnss.altitude)),
        dynamics=ActorDynamics(
            velocity=UncertainProperty(1., Point3D(velocity.x, velocity.y, velocity.z)),
            acceleration=UncertainProperty(1., Point3D(acceleration.x, acceleration.y, acceleration.z))
        ),
        props=ActorProperties(
            color=UncertainProperty(1., color),
            extent=UncertainProperty(1., Point3D(extent.x, extent.y, extent.z)),
            bbox=UncertainProperty(1., bbox)
        )
    )


def map_pem_actor(actor: DynamicActor) -> PEMDynamicActor:
    bbox_corners = (
        geo.gnss_add_meters(actor.gnss.value.components(), actor.props.extent.value.components(), delta_factor=-1),
        geo.gnss_add_meters(actor.gnss.value.components(), actor.props.extent.value.components())
    )
    bbox = RelativeBBox(lower=Vector3D(bbox_corners[0]), higher=Vector3D(bbox_corners[1]))

    return PEMDynamicActor(
        id=actor.id,
        type=PEMRelation(confidence=actor.type.confidence, object=ActorType(actor.type.value)),
        position=PEMRelation(confidence=actor.gnss.confidence, object=Vector3D(actor.gnss.value.components())),
        color=PEMRelation(confidence=actor.props.color.confidence, object=actor.props.color.value),
        bounding_box=PEMRelation(confidence=actor.props.extent.confidence, object=bbox),
        velocity=PEMRelation(confidence=actor.dynamics.velocity.confidence, object=Vector3D(actor.dynamics.velocity.value.components())),
        acceleration=PEMRelation(confidence=actor.dynamics.acceleration.confidence, object=Vector3D(actor.dynamics.acceleration.value.components()))
    )

    # TODO: Maybe abstract from Carla-specific classes?


def geoloc2point2d(location: carla.GeoLocation) -> Point2D:
    return Point2D(location.latitude, location.longitude, )


def resolve_carla_type(carla_type: str) -> At:
    if carla_type.startswith('vehicle'):
        return At.VEHICLE
    if carla_type.startswith('walker'):
        return At.PEDESTRIAN
    return At.UNKNOWN


def get_occupied_cells(for_actor: DynamicActor) -> FrozenSet[QuadKey]:
    qks: List[QuadKey] = list(map(lambda c: quadkey.from_geo(c.components(), OCCUPANCY_TILE_LEVEL), for_actor.props.bbox.value))

    return frozenset(quadkey.QuadKey.bbox_filled(qks))


# Assumes that a cell is tiny enough to contain at max one actor
def get_occupied_cells_multi(for_actors: List[DynamicActor]) -> Dict[str, DynamicActor]:
    matches: Dict[str, DynamicActor] = {}

    for a in for_actors:
        for c in get_occupied_cells(a):
            matches[c.key] = a

    return matches
