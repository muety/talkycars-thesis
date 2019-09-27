import logging
import time
from typing import List

import pygame
from agents.navigation.agent import Agent
from agents.navigation.basic_agent import BasicAgent
from ego import Ego
from scenes import AbstractScene
from util import simulation

import carla
from common.constants import *
from common.constants import SCENE2_N_EGOS, SCENE2_N_VEHICLES, SCENE2_N_PEDESTRIANS, SCENE2_MAP_NAME
from common.util.waypoint import WaypointProvider


class Scene(AbstractScene):
    def __init__(self, sim: carla.Client):
        self.initialized: bool = False
        self._egos: List[Ego] = []
        self._agents: List[BasicAgent] = []
        self._peds: List[carla.Actor] = None
        self._world: carla.World = None
        self._map: carla.Map = None
        self._sim: carla.Client = sim
        self._waypoint_provider = None

    def init(self):
        if self.initialized:
            return

        # Load world
        self._world = self._sim.load_world(SCENE2_MAP_NAME)
        self._map = self._world.get_map()

        spawn_points: List[carla.Transform] = self._world.get_map().get_spawn_points()
        self._waypoint_provider: WaypointProvider = WaypointProvider(spawn_points)

        self.initialized = True

    def create_and_spawn(self):
        self.init()

        n_present: int = simulation.count_present_vehicles(SCENE2_ROLE_NAME_PREFIX, self._world)
        while n_present < SCENE2_N_EGOS:
            logging.info(f'Waiting for {SCENE2_N_EGOS - n_present} / {SCENE2_N_EGOS} to join the simulation.')
            time.sleep(1)
            n_present = simulation.count_present_vehicles(SCENE2_ROLE_NAME_PREFIX, self._world)

        self._waypoint_provider.update(self._world)

        # Create walkers
        logging.info(f'Attempting to spawn {SCENE2_N_PEDESTRIANS} pedestrians.')
        self._peds = simulation.try_spawn_pedestrians(self._sim, SCENE2_N_PEDESTRIANS)

        # Create static vehicles
        logging.info(f'Attempting to spawn {SCENE2_N_VEHICLES} NPC vehicles.')
        self._agents = simulation.spawn_npcs(self._sim, self._waypoint_provider, SCENE2_N_VEHICLES)

    def tick(self, clock: pygame.time.Clock) -> bool:
        # TODO: Wait for all egos to be spawned before starting

        for a in self.agents:
            a.run_and_apply()

        # TODO: return True on condition

        return False

    @property
    def egos(self) -> List[Ego]:
        return self._egos

    @property
    def npcs(self) -> List[carla.Actor]:
        return self._peds

    @property
    def world(self) -> carla.World:
        return self._world

    @property
    def agents(self) -> List[Agent]:
        return self._agents
