from typing import Callable

from client.observation import ObservationManager
from client.occupancy import OccupancyGridManager


class OutboundController():
    def __init__(self, om: ObservationManager, gm: OccupancyGridManager):
        self.om = om
        self.gm = gm

    def subscribe(self, key: str, callback: Callable):
        return self.om.subscribe(key, callback)
