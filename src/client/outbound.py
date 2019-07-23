from typing import Callable

from .observation import ObservationManager
from .occupancy import OccupancyGridManager


class OutboundController:
    def __init__(self, om: ObservationManager, gm: OccupancyGridManager, subject_id: int):
        self.om = om
        self.gm = gm
        self.subject_id = subject_id

    def subscribe(self, key: str, callback: Callable):
        return self.om.subscribe(key, callback)
