import logging
from multiprocessing.pool import ThreadPool
from typing import List, cast, Callable

import pygame
from agents.navigation.agent import Agent
from agents.navigation.basic_agent import BasicAgent
from ego import Ego
from scenes import AbstractScene
from strategy import RandomPathEgoStrategy
from util import SimulationUtils
from util.waypoint import WaypointProvider

import carla
from common import quadkey
from common.constants import *
from common.quadkey import QuadKey

N_EGOS = 1
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

        # Create egos
        for i in range(N_EGOS):
            logging.info(f'Creating ego {i + 1} of {N_EGOS}.')
            ego: Ego = Ego(self._sim,
                           strategy=RandomPathEgoStrategy(0, waypoint_provider),
                           name=f'random_hero_{i}',
                           render=i == 0,
                           debug=False,
                           record=False)
            self._egos.append(ego)

        # Create walkers
        logging.info(f'Attempting to spawn {N_PEDESTRIANS} pedestrians.')
        self._peds = SimulationUtils.try_spawn_pedestrians(self._sim, N_PEDESTRIANS)

        # Create static vehicles
        logging.info(f'Attempting to spawn {N_VEHICLES} NPC vehicles.')
        self._agents = SimulationUtils.spawn_npcs(self._sim, waypoint_provider, N_VEHICLES)

        # Print info
        for a in self.egos:
            strat: RandomPathEgoStrategy = cast(RandomPathEgoStrategy, a.strategy)
            geo_start: carla.GeoLocation = self._map.transform_to_geolocation(strat.point_start.location)
            geo_end: carla.GeoLocation = self._map.transform_to_geolocation(strat.point_end.location)
            qk_start: QuadKey = quadkey.from_geo((geo_start.latitude, geo_start.longitude), REMOTE_GRID_TILE_LEVEL)
            qk_end: QuadKey = quadkey.from_geo((geo_end.latitude, geo_end.longitude), REMOTE_GRID_TILE_LEVEL)
            logging.info(f'{a.name} will be driving from {strat.point_start.location} ({qk_start.key}) to {strat.point_end.location} ({qk_end.key}).')

        self._pool = ThreadPool(max(len(self._egos), len(self.agents)))

    def tick(self, clock: pygame.time.Clock) -> bool:
        n_dead_egos: int = 0

        for ego in self.egos:
            n_dead_egos += ego.tick(clock)

        self._pool.map(self.wrap_step_ego(clock), self._egos)
        self._pool.map(self.step_agent, self.agents)

        if n_dead_egos == len(self.egos):
            return True

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

    @staticmethod
    def wrap_step_ego(clock: pygame.time.Clock) -> Callable:
        def step_ego(ego: Ego) -> bool:
            return ego.tick(clock)

        return step_ego
