from client.observation import ObservationManager
from client.occupancy import OccupancyGridManager
from common.constants import *
from common.observation import Observation, OccupancyGridObservation


class InboundController():
    def __init__(self, om: ObservationManager, gm: OccupancyGridManager):
        self.om = om
        self.gm = gm

        def on_lidar(obs: Observation):
            if self.om.has(OBS_GNSS_PLAYER_POS):
                self.gm.update_gnss(self.om.latest(OBS_GNSS_PLAYER_POS))

            if self.om.has(OBS_POSITION_PLAYER_POS):
                self.gm.set_position(self.om.latest(OBS_POSITION_PLAYER_POS))

            if not self.gm.match_with_lidar(obs):
                return

            grid = self.gm.get_grid()
            if not grid:
                return

            obs = OccupancyGridObservation(obs.timestamp, grid)
            self.om.add(OBS_OCCUPANCY_GRID, obs)

        self.om.subscribe(OBS_LIDAR_POINTS, on_lidar)

    def publish(self, key: str, obs: Observation):
        self.om.add(key, obs)