from common.observation import Observation
from .observation import ObservationManager
from .occupancy import OccupancyGridManager


class InboundController:
    def __init__(self, om: ObservationManager, gm: OccupancyGridManager):
        self.om = om
        self.gm = gm

    def publish(self, key: str, obs: Observation):
        self.om.add(key, obs)