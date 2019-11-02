import time
from typing import List

import carla
from client import map_dynamic_actor
from client.client import TalkyClient
from common.constants import *
from common.model import DynamicActor, ActorDynamics, ActorProperties
from common.observation import ActorsObservation
from . import Sensor


class ActorsEvent(carla.SensorData):
    def __init__(self, timestamp):
        self.ts = timestamp


class ActorsSensor(Sensor):
    def __init__(self, parent_actor, client: TalkyClient, with_noise: bool = True):
        self._parent = parent_actor
        self._world = parent_actor.get_world()
        self._map = self._world.get_map()
        self._with_noise: bool = with_noise
        self._ego_actor: carla.Actor = None
        self._non_ego_actors: List[carla.Actor] = []
        self._tick_count: int = 0

        super().__init__(client)

    def tick(self, timestamp):
        self._on_event(ActorsEvent(time.time()))
        self._tick_count += 1

    def _on_event(self, event):
        if self._tick_count % 10 == 0:
            self._update_actors()

        ego_actors: List[DynamicActor] = [map_dynamic_actor(self._ego_actor, self._map)]
        self.client.inbound.publish(OBS_ACTOR_EGO, ActorsObservation(event.ts, actors=ego_actors))

        if self._with_noise:
            other_actors: List[DynamicActor] = list(map(self._noisify_actor, map(lambda a: map_dynamic_actor(a, self._map), self._non_ego_actors)))
        else:
            other_actors: List[DynamicActor] = list(map(lambda a: map_dynamic_actor(a, self._map), self._non_ego_actors))
        self.client.inbound.publish(OBS_ACTORS_RAW, ActorsObservation(event.ts, actors=other_actors))

    def _update_actors(self):
        actors: carla.ActorList = self._world.get_actors()
        vehicle_actors: List[carla.Actor] = list(actors.filter('vehicle.*')) if actors else []
        walker_actors: List[carla.Actor] = list(actors.filter('walker.*')) if actors else []

        self._non_ego_actors = walker_actors + list(filter(lambda a: a.id != self._parent.id, vehicle_actors))

        if not self._ego_actor:
            self._ego_actor = list(filter(lambda a: a.id == self._parent.id, vehicle_actors))[0]

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
