from typing import cast

from common.constants import *
from common.observation import Observation, OccupancyGridObservation, LidarObservation, PositionObservation, \
    GnssObservation
from .observation import ObservationManager
from .occupancy import OccupancyGridManager


class InboundController:
    def __init__(self, om: ObservationManager, gm: OccupancyGridManager):
        self.om = om
        self.gm = gm

        self.om.subscribe(OBS_LIDAR_POINTS, self._on_lidar)

    def publish(self, key: str, obs: Observation):
        self.om.add(key, obs)

    def _on_lidar(self, obs: LidarObservation):
        if self.om.has(OBS_GNSS_PREFIX + ALIAS_EGO):
            self.gm.update_gnss(cast(GnssObservation, self.om.latest(OBS_GNSS_PREFIX + ALIAS_EGO)))

        if self.om.has(OBS_POSITION):
            self.gm.set_position(cast(PositionObservation, self.om.latest(OBS_POSITION)))

        if not self.gm.match_with_lidar(cast(LidarObservation, obs)):
            return

        grid = self.gm.get_grid()
        if not grid:
            return

        obs = OccupancyGridObservation(obs.timestamp, grid)
        self.om.add(OBS_OCCUPANCY_GRID, obs)
