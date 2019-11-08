import time
from typing import FrozenSet

from pyquadkey2.quadkey import QuadKey


class OccupancyGroundTruthContainer:
    def __init__(self, occupied_cells: FrozenSet[QuadKey], tile: QuadKey, ts: float = time.time()):
        self.occupied_cells = occupied_cells
        self.tile = tile  # parent
        self.ts = ts

