import logging
from typing import cast

import pygame
from ego import Ego
from scenes import scene2_environment
from strategy import RandomPathEgoStrategy

import carla
from common import quadkey
from common.constants import *
from common.quadkey import QuadKey

N_EGOS = 1


class Scene(scene2_environment.Scene):
    def __init__(self, sim: carla.Client):
        super().__init__(sim)

    def create_and_spawn(self):
        super().create_and_spawn()

        # Create egos
        for i in range(N_EGOS):
            logging.info(f'Creating ego {i + 1} of {N_EGOS}.')
            ego: Ego = Ego(self._sim,
                           strategy=RandomPathEgoStrategy(i, self._waypoint_provider),
                           name=f'random_hero_{i}',
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

    def tick(self, clock: pygame.time.Clock) -> bool:
        n_dead_egos: int = 0

        for ego in self.egos:
            n_dead_egos += ego.tick(clock)

        if n_dead_egos == len(self.egos):
            return True

        return super().tick(clock)
