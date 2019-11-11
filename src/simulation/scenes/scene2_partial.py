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
        self._peds: List[carla.Actor] = []
        self._static: List[carla.Actor] = []
        self._world: carla.World = None
        self._map: carla.Map = None
        self._sim: carla.Client = sim
        self._waypoint_provider = None
        self._start_time: float = 0.
        self._tick_count: int = 0

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

        n_present: int = simulation.count_present_vehicles(SCENE2_EGO_PREFIX, self._world)
        while n_present < SCENE2_N_EGOS:
            logging.info(f'Waiting for {SCENE2_N_EGOS - n_present} / {SCENE2_N_EGOS} to join the simulation.')
            time.sleep(1)
            n_present = simulation.count_present_vehicles(SCENE2_EGO_PREFIX, self._world)
        self._start_time = time.time()

        self._waypoint_provider.update(free_only=True, anywhere=False)

        # Create walkers
        logging.info(f'Attempting to spawn {SCENE2_N_PEDESTRIANS} pedestrians.')
        retry_count: int = 0
        while self.n_peds < SCENE2_N_PEDESTRIANS and retry_count < 3:
            retry_count += 1
            self._peds += simulation.try_spawn_pedestrians(
                self._sim,
                n=SCENE2_N_PEDESTRIANS - self.n_peds
            )

        # Create static vehicles
        logging.info(f'Attempting to spawn {SCENE2_N_STATIC} static vehicles.')
        retry_count: int = 0
        while self.n_static < SCENE2_N_PEDESTRIANS and retry_count < 3:
            retry_count += 1
            self._static += simulation.spawn_static_vehicles(
                self._sim,
                n=SCENE2_N_STATIC - self.n_static,
                role_name_prefix=SCENE2_STATIC_PREFIX
            )

        # Create moving vehicles
        logging.info(f'Attempting to spawn {SCENE2_N_VEHICLES} NPC vehicles.')
        self._agents = simulation.spawn_npcs(
            self._sim,
            self._waypoint_provider,
            n=SCENE2_N_VEHICLES,
            role_name_prefix=SCENE2_NPC_PREFIX
        )

        self.print_scene_status()

    def tick(self, clock: pygame.time.Clock) -> bool:
        self._tick_count += 1

        if self._tick_count % 10 == 0 and self.done(SCENE2_MIN_REMAINING_EGOS):
            logging.info(f'Finished simulation after {time.time() - self._start_time} s')
            return True

        for a in self._agents:
            a.run_and_apply()
            if a.done():
                logging.info(f'Replanning NPC agent {a.vehicle.id}.')
                self._waypoint_provider.update(free_only=True)

                try:
                    a.set_location_destination(self._waypoint_provider.get().location)
                except AttributeError:
                    logging.warning(f'Couldn\'t find new destination for agent {a.vehicle.id}. Removing ...')
                    self._agents.remove(a)

        return False

    def done(self, n_remaining: int = 0):
        return simulation.count_present_vehicles(SCENE2_EGO_PREFIX, self._world) <= n_remaining

    def print_scene_status(self):
        logging.info(f'# Active pedestrians: {self.n_peds}')
        logging.info(f'# Active static vehicles: {self.n_static}')
        logging.info(f'# Active NPC vehicles: {self.n_npcs}')

    @property
    def n_peds(self) -> int:
        return len(list(filter(lambda a: a.is_alive, self._peds))) // 2

    @property
    def n_static(self) -> int:
        return len(list(filter(lambda a: a.is_alive, self._static)))

    @property
    def n_npcs(self) -> int:
        return len(list(filter(lambda a: a.vehicle.is_alive, self._agents)))

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
