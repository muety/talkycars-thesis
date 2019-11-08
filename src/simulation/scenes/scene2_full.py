import logging
from typing import cast

import pygame
from ego import Ego
from pyquadkey2 import quadkey
from pyquadkey2.quadkey import QuadKey
from scenes import scene2_partial
from strategy import RandomPathEgoStrategy

import carla
import common.constants
from common.constants import *


class Scene(scene2_partial.Scene):
    def __init__(self, sim: carla.Client):
        super().__init__(sim)

    def create_and_spawn(self):
        self.init()

        # Create egos
        for i in range(common.constants.SCENE2_N_EGOS):
            logging.info(f'Creating ego {i + 1} of {common.constants.SCENE2_N_EGOS}.')
            ego: Ego = Ego(self._sim,
                           strategy=RandomPathEgoStrategy(i, self._waypoint_provider),
                           name=f'{SCENE2_EGO_PREFIX}_{i}',
                           render=i == 0,
                           debug=False,
                           record=False)
            self._egos.append(ego)

        # Print info
        for a in self.egos:
            strat: RandomPathEgoStrategy = cast(RandomPathEgoStrategy, a.strategy)
            geo_start: carla.GeoLocation = self._map.transform_to_geolocation(strat.point_start.location)
            geo_end: carla.GeoLocation = self._map.transform_to_geolocation(strat.point_end.location)
            qk_start: QuadKey = quadkey.from_geo((geo_start.latitude, geo_start.longitude), REMOTE_GRID_TILE_LEVEL)
            qk_end: QuadKey = quadkey.from_geo((geo_end.latitude, geo_end.longitude), REMOTE_GRID_TILE_LEVEL)
            logging.info(f'{a.name} will be driving from {strat.point_start.location} ({qk_start.key}) to {strat.point_end.location} ({qk_end.key}).')

        super().create_and_spawn()

    def tick(self, clock: pygame.time.Clock) -> bool:
        n_dead_egos: int = 0

        for ego in self.egos:
            n_dead_egos += ego.tick(clock)

        if n_dead_egos == len(self.egos) and len(self.egos) > 0:
            return True

        return super().tick(clock)
