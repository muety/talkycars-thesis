from client.observation import ObservationManager
from client.occupancy import OccupancyGridManager
from common.constants import *
from common.observation import Observation, OccupancyGridObservation


class InboundController():
    def __init__(self, om: ObservationManager, gm: OccupancyGridManager):
        self.om = om
        self.gm = gm

        def on_lidar(obs: Observation):
            executed = self.gm.update_gnss(obs)
            if executed:
                self.gm.match_with_lidar(self.om.latest(OBS_LIDAR_POINTS))

                obs = OccupancyGridObservation(obs.timestamp, self.gm.get_grid())
                self.om.add(OBS_OCCUPANCY_GRID, obs)

        self.om.subscribe(OBS_GNSS_PLAYER_POS, on_lidar)
        self.om.subscribe(OBS_POSITION_PLAYER_POS, self.gm.set_position)

    def publish(self, key: str, obs: Observation):
        self.om.add(key, obs)