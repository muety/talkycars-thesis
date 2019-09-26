import logging
from multiprocessing.pool import ThreadPool
from typing import List

import pygame
from agents.navigation.agent import Agent
from agents.navigation.basic_agent import BasicAgent
from ego import Ego
from scenes import AbstractScene
from util import SimulationUtils
from util.waypoint import WaypointProvider

import carla

N_VEHICLES = 1
N_PEDESTRIANS = 50
MAP_NAME = 'Town07'


class Scene(AbstractScene):
    def __init__(self, sim: carla.Client):
        self._egos: List[Ego] = []
        self._agents: List[BasicAgent] = []
        self._peds: List[carla.Actor] = None
        self._world: carla.World = None
        self._map: carla.Map = None
        self._sim: carla.Client = sim
        self._pool: ThreadPool = None

    def create_and_spawn(self):
        # Load world
        self._world = self._sim.load_world(MAP_NAME)
        self._map = self._world.get_map()

        spawn_points: List[carla.Transform] = self._world.get_map().get_spawn_points()
        waypoint_provider: WaypointProvider = WaypointProvider(spawn_points)

        # Create walkers
        logging.info(f'Attempting to spawn {N_PEDESTRIANS} pedestrians.')
        self._peds = SimulationUtils.try_spawn_pedestrians(self._sim, N_PEDESTRIANS)

        # Create static vehicles
        logging.info(f'Attempting to spawn {N_VEHICLES} NPC vehicles.')
        self._agents = SimulationUtils.spawn_npcs(self._sim, waypoint_provider, N_VEHICLES)

        self._pool = ThreadPool(max(len(self._egos), len(self.agents)))

    def tick(self, clock: pygame.time.Clock) -> bool:
        # TODO: Wait for all egos to be spawned before starting

        self._pool.map(self.step_agent, self.agents)

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

    @staticmethod
    def step_agent(agent: Agent):
        agent.run_and_apply()
