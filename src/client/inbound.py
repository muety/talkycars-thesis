from multiprocessing.pool import ThreadPool

from common.observation import Observation
from .observation import ObservationManager
from .occupancy import OccupancyGridManager


class InboundController:
    def __init__(self, om: ObservationManager, gm: OccupancyGridManager):
        self.om: ObservationManager = om
        self.gm: OccupancyGridManager = gm
        self.thread_pool: ThreadPool = ThreadPool(6)  # Used for idly waiting for asynchronously running ObservationManager.add()

    def publish(self, key: str, obs: Observation):
        self.thread_pool.apply_async(self.om.add, (key, obs))
