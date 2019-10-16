import time
from typing import FrozenSet, List

from common.quadkey import QuadKey
from common.serialization.schema.occupancy import PEMGridCell


class OccupancyObservationContainer:
    def __init__(self, msg: bytes, tile: QuadKey, ts: float = time.time()):
        self.msg = msg
        self.tile = tile  # parent
        self.ts = ts


class OccupancyUnfoldedObservationContainer:
    def __init__(self, cells: List[PEMGridCell], tile: QuadKey, ts: float = time.time()):
        self.cells = cells
        self.tile = tile  # parent
        self.ts = ts


class OccupancyGroundTruthContainer:
    def __init__(self, occupied_cells: FrozenSet[QuadKey], tile: QuadKey, ts: float = time.time()):
        self.occupied_cells = occupied_cells
        self.tile = tile  # parent
        self.ts = ts
