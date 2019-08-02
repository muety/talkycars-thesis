from typing import List

import carla
from client.client import TalkyClient
from common.constants import *
from common.model import DynamicActor, ActorType, ActorDynamics, Point3D, ActorProperties, UncertainProperty
from common.observation import ActorsObservation
from . import Sensor


class ActorsEvent(carla.SensorData):
    def __init__(self, timestamp):
        self.ts = timestamp


class ActorsSensor(Sensor):
    def __init__(self, parent_actor, client: TalkyClient):
        self._parent = parent_actor
        self._map = parent_actor.get_world().get_map()
        super().__init__(client)

    def tick(self, timestamp):
        self._on_event(ActorsEvent(timestamp))

    def _on_event(self, event):
        ego_id: int = self._parent.id
        actors: carla.ActorList = self._parent.get_world().get_actors()
        vehicle_actors: List[carla.Actor] = list(actors.filter('vehicle.*')) if actors else []
        walker_actors: List[carla.Actor] = list(actors.filter('walker.*')) if actors else []

        all_actors = list(map(self._map_to_actor, vehicle_actors + walker_actors))
        ego_actors: List[DynamicActor] = list(filter(lambda a: a.id == ego_id, all_actors))
        other_actors: List[DynamicActor] = list(map(self._noisify_actor, filter(lambda a: a.id != ego_id, all_actors)))

        self.client.inbound.publish(OBS_ACTOR_EGO, ActorsObservation(event.ts, actors=ego_actors))
        self.client.inbound.publish(OBS_ACTORS_RAW, ActorsObservation(event.ts, actors=other_actors))

    def _map_to_actor(self, carla_actor: carla.Actor) -> DynamicActor:
        location: carla.Location = carla_actor.get_location()
        gnss: carla.GeoLocation = self._map.transform_to_geolocation(location)
        velocity: carla.Vector3D = carla_actor.get_velocity()
        acceleration: carla.Vector3D = carla_actor.get_acceleration()
        color: str = str(carla_actor.attributes['color']) if 'color' in carla_actor.attributes else None
        extent: carla.BoundingBox = carla_actor.bounding_box.extent

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
                extent=UncertainProperty(1., Point3D(extent.x, extent.y, extent.z))
            )
        )

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
            gnss=actor.gnss.with_uncertainty().with_gaussian_noise(sigma=.001),
            location=actor.location.with_uncertainty().with_gaussian_noise(sigma=.01),
            dynamics=ActorDynamics(
                velocity=actor.dynamics.velocity.with_uncertainty().with_gaussian_noise(sigma=.01),
                acceleration=actor.dynamics.acceleration.with_uncertainty().with_gaussian_noise(sigma=.01)
            ),
            props=ActorProperties(
                color=actor.props.color.with_uncertainty(),
                extent=actor.props.extent.with_gaussian_noise(sigma=.1)
            )
        )
