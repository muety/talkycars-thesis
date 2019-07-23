from typing import Callable

from .observation import ObservationManager
from .occupancy import OccupancyGridManager


class OutboundController:
    def __init__(self, om: ObservationManager, gm: OccupancyGridManager):
        self.om = om
        self.gm = gm

    def subscribe(self, key: str, callback: Callable):
        return self.om.subscribe(key, callback)
