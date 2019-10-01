from typing import List, Tuple, cast

import carla
from client.client import TalkyClient
from common.constants import *
from common.model import DynamicActor, ActorType, ActorDynamics, Point3D, ActorProperties, UncertainProperty, Point2D
from common.observation import ActorsObservation
from . import Sensor


class ActorsEvent(carla.SensorData):
    def __init__(self, timestamp):
        self.ts = timestamp


class ActorsSensor(Sensor):
    def __init__(self, parent_actor, client: TalkyClient):
        self._parent = parent_actor
        self._world = parent_actor.get_world()
        self._map = self._world.get_map()
        self._ego_actor: carla.Actor = None
        self._non_ego_actors: List[carla.Actor] = []
        self._tick_count: int = 0

        super().__init__(client)

    def tick(self, timestamp):
        self._on_event(ActorsEvent(timestamp))
        self._tick_count += 1

    def _on_event(self, event):
        if self._tick_count % 10 == 0:
            self._update_actors()

        ego_actors: List[DynamicActor] = [self._map_to_actor(self._ego_actor)]
        other_actors: List[DynamicActor] = list(map(self._noisify_actor, map(self._map_to_actor, self._non_ego_actors)))

        self.client.inbound.publish(OBS_ACTOR_EGO, ActorsObservation(event.ts, actors=ego_actors))
        self.client.inbound.publish(OBS_ACTORS_RAW, ActorsObservation(event.ts, actors=other_actors))

    def _update_actors(self):
        actors: carla.ActorList = self._world.get_actors()
        vehicle_actors: List[carla.Actor] = list(actors.filter('vehicle.*')) if actors else []
        walker_actors: List[carla.Actor] = list(actors.filter('walker.*')) if actors else []

        self._non_ego_actors = walker_actors + list(filter(lambda a: a.id != self._parent.id, vehicle_actors))

        if not self._ego_actor:
            self._ego_actor = list(filter(lambda a: a.id == self._parent.id, vehicle_actors))[0]

    def _map_to_actor(self, carla_actor: carla.Actor) -> DynamicActor:
        location: carla.Location = carla_actor.get_location()
        gnss: carla.GeoLocation = self._map.transform_to_geolocation(location)
        velocity: carla.Vector3D = carla_actor.get_velocity()
        acceleration: carla.Vector3D = carla_actor.get_acceleration()
        color: str = str(carla_actor.attributes['color']) if 'color' in carla_actor.attributes else None
        extent: carla.Vector3D = carla_actor.bounding_box.extent

        transform: carla.Transform = carla.Transform(rotation=carla_actor.get_transform().rotation)

        transformed_extent: Tuple[carla.Location, carla.Location, carla.Location, carla.Location] = (
            transform.transform(carla.Location(+extent.x, +extent.y, 0)),
            transform.transform(carla.Location(+extent.x, -extent.y, 0)),
            transform.transform(carla.Location(-extent.x, -extent.y, 0)),
            transform.transform(carla.Location(-extent.x, +extent.y, 0)),
        )

        bbox: Tuple[Point2D, Point2D, Point2D, Point2D] = cast(Tuple[Point2D, Point2D, Point2D, Point2D], tuple(map(
            lambda t: self._geoloc2point2d(
                self._map.transform_to_geolocation(carla.Vector3D(location.x + t.x, location.y + t.y, location.z))
            ), transformed_extent)
        ))

        return DynamicActor(
            id=carla_actor.id,
            type=UncertainProperty(1., self._resolve_carla_type(carla_actor.type_id)),
            type_id=carla_actor.type_id,
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

    @staticmethod
    def _geoloc2point2d(location: carla.GeoLocation) -> Point2D:
        return Point2D(location.latitude, location.longitude, )

    @staticmethod
    def _resolve_carla_type(carla_type: str) -> ActorType:
        if carla_type.startswith('vehicle'):
            return ActorType.VEHICLE
        if carla_type.startswith('walker'):
            return ActorType.PEDESTRIAN
        return ActorType.UNKNOWN

    @staticmethod
    def _noisify_actor(actor: DynamicActor) -> DynamicActor:
        return DynamicActor(
            id=actor.id,
            type=actor.type.with_uncertainty(),
            type_id=actor.type_id,
            gnss=actor.gnss.with_uncertainty().with_gaussian_noise(sigma=1e-5),
            location=actor.location.with_uncertainty().with_gaussian_noise(sigma=1e-3),
            dynamics=ActorDynamics(
                velocity=actor.dynamics.velocity.with_uncertainty().with_gaussian_noise(sigma=1e-3),
                acceleration=actor.dynamics.acceleration.with_uncertainty().with_gaussian_noise(sigma=1e-3)
            ),
            props=ActorProperties(
                color=actor.props.color.with_uncertainty(),
                extent=actor.props.extent.with_uncertainty().with_gaussian_noise(sigma=.01),
                bbox=actor.props.bbox.with_uncertainty().with_gaussian_noise(sigma=1e-5)
            )
        )
