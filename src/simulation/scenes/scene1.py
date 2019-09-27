from typing import List

import pygame
from agents.navigation.agent import Agent
from ego import Ego
from scenes import AbstractScene
from strategy import ManualEgoStrategy
from util import simulation

import carla

N_PEDESTRIANS = 50
MAP_NAME = 'Town07'


class Scene(AbstractScene):
    def __init__(self, sim: carla.Client):
        self._egos: List[Ego] = []
        self._npcs: List[carla.Actor] = []
        self._world: carla.World = None
        self._sim: carla.Client = sim

    def init(self):
        pass

    def create_and_spawn(self):
        # Load world
        self._world = self._sim.load_world(MAP_NAME)

        # Create egos
        main_hero = Ego(self._sim,
                        strategy=ManualEgoStrategy(config=0),
                        name='main_hero',
                        render=True,
                        debug=False,
                        record=False)

        self.egos.append(main_hero)

        # Create walkers
        self._npcs += simulation.try_spawn_pedestrians(self._sim, N_PEDESTRIANS)

        # Create static vehicles
        bp1 = self._world.get_blueprint_library().filter('vehicle.volkswagen.t2')[0]
        spawn1 = carla.Transform(carla.Location(x=-198.2, y=-50.9, z=1.5), carla.Rotation(yaw=-90))
        cmd1 = carla.command.SpawnActor(bp1, spawn1)

        responses = self._sim.apply_batch_sync([cmd1], True)
        spawned_ids = list(map(lambda r: r.actor_id, filter(lambda r: not r.has_error(), responses)))
        spawned_actors = list(self._world.get_actors(spawned_ids))
        self._npcs += spawned_actors

    def tick(self, clock: pygame.time.Clock) -> bool:
        for ego in self.egos:
            if ego.tick(clock):
                return True

        return False

    @property
    def egos(self) -> List[Ego]:
        return self._egos

    @property
    def npcs(self) -> List[carla.Actor]:
        return self._npcs

    @property
    def world(self) -> carla.World:
        return self._world

    @property
    def agents(self) -> List[Agent]:
        return []
