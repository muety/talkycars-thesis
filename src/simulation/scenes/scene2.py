import logging
from typing import List, cast

from ego import Ego
from scenes import AbstractScene
from strategy import RandomPathEgoStrategy
from util import SimulationUtils
from util.waypoint import WaypointProvider

import carla

N_PEDESTRIANS = 50
MAP_NAME = 'Town01'


class Scene(AbstractScene):
    def __init__(self, sim: carla.Client):
        self._egos: List[Ego] = []
        self._npcs: List[carla.Actor] = []
        self._world: carla.World = None
        self._sim: carla.Client = sim

    def create_and_spawn(self):
        # Load world
        self._world = self._sim.load_world(MAP_NAME)

        spawn_points: List[carla.Transform] = self._world.get_map().get_spawn_points()
        waypoint_provider: WaypointProvider = WaypointProvider(spawn_points)

        # Create egos
        main_hero = Ego(self._sim,
                        strategy=RandomPathEgoStrategy(0, waypoint_provider),
                        name='random_hero',
                        render=True,
                        debug=False,
                        record=False)

        self.egos.append(main_hero)

        # Create walkers
        self._npcs += SimulationUtils.try_spawn_pedestrians(self._sim, N_PEDESTRIANS)

        # Create static vehicles

        # Print info
        for a in [main_hero]:
            strat: RandomPathEgoStrategy = cast(RandomPathEgoStrategy, a.strategy)
            logging.info(f'{a.name} will be driving from {strat.point_start.location} to {strat.point_end.location}.')

    @property
    def egos(self) -> List[Ego]:
        return self._egos

    @property
    def npcs(self) -> List[carla.Actor]:
        return self._npcs

    @property
    def world(self) -> carla.World:
        return self._world
