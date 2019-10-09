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
        self._static: List[carla.Actor] = None
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

        self._waypoint_provider: WaypointProvider = WaypointProvider(
            self._world,
            center=carla.Location(*SCENE2_AREA_CENTER),
            center_dist=SCENE2_CENTER_DIST
        )
        self._waypoint_provider.update(free_only=True)

        self.initialized = True

    def create_and_spawn(self):
        self.init()

        n_present: int = simulation.count_present_vehicles(SCENE2_ROLE_NAME_PREFIX, self._world)
        while n_present < SCENE2_N_EGOS:
            logging.info(f'Waiting for {SCENE2_N_EGOS - n_present} / {SCENE2_N_EGOS} to join the simulation.')
            time.sleep(1)
            n_present = simulation.count_present_vehicles(SCENE2_ROLE_NAME_PREFIX, self._world)

        self._waypoint_provider.update(free_only=True)

        # Create walkers
        logging.info(f'Attempting to spawn {SCENE2_N_PEDESTRIANS} pedestrians.')
        self._peds = simulation.try_spawn_pedestrians(self._sim, SCENE2_N_PEDESTRIANS)

        # Create static vehicles
        logging.info(f'Attempting to spawn {SCENE2_N_STATIC} static vehicles.')
        self._static = simulation.spawn_static_vehicles(self._sim, SCENE2_N_STATIC)

        # Create moving vehicles
        logging.info(f'Attempting to spawn {SCENE2_N_VEHICLES} NPC vehicles.')
        self._agents = simulation.spawn_npcs(self._sim, self._waypoint_provider, SCENE2_N_VEHICLES)

    def tick(self, clock: pygame.time.Clock) -> bool:
        for a in self._agents:
            a.run_and_apply()
            if a.done():
                logging.info(f'Replanning NPC agent {a.vehicle.id}.')
                self._waypoint_provider.update(self._world)
                a.set_location_destination(self._waypoint_provider.get().location)

        return False

    @property
    def egos(self) -> List[Ego]:
        return self._egos

    @property
    def npcs(self) -> List[carla.Actor]:
        return self._peds + self._static

    @property
    def world(self) -> carla.World:
        return self._world

    @property
    def agents(self) -> List[Agent]:
        return self._agents
