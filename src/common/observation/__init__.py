from datetime import datetime
from typing import Tuple, List, Any

import numpy as np

from common import quadkey
from common.model import DynamicActor, UncertainProperty
from common.occupancy import Grid, GridCellState

_Vec3 = Tuple[float, float, float]
_Dynamics = Tuple[_Vec3]


class Observation(UncertainProperty[Any]):
    def __init__(self, local_timestamp: int = 0, confidence: float = 1):
        assert isinstance(local_timestamp, int) or isinstance(local_timestamp, float)

        self.local_timestamp = local_timestamp
        # Caution: Uses local platform time!
        self.timestamp = datetime.now().timestamp()

        super(Observation, self).__init__(confidence=confidence, value=None)


class EmptyObservation(Observation):
    def __init__(self, timestamp):
        super().__init__(timestamp)

    def __str__(self):
        return f'[{self.timestamp}] Empty Observation'


class EgoObservation(Observation):
    pass


class GnssObservation(EgoObservation):
    def __init__(self, timestamp, coords: _Vec3):
        assert isinstance(coords, tuple)

        super().__init__(timestamp)
        self.value: _Vec3 = coords

    def to_quadkey(self, level=20) -> quadkey.QuadKey:
        return quadkey.from_geo(self.value[:2], level)

    def to_tile(self, level=20):
        return self.to_quadkey(level).to_tile()

    def __str__(self):
        return f'[{self.timestamp}] GPS Position: {self.value}'


class LidarObservation(EgoObservation):
    def __init__(self, timestamp, points: np.ndarray):
        super().__init__(timestamp)
        self.value: np.ndarray = points

    def __str__(self):
        return f'[{self.timestamp}] Point Cloud: {self.value.shape}'


class CameraRGBObservation(EgoObservation):
    def __init__(self, timestamp, image: np.ndarray):
        assert isinstance(image, np.ndarray)

        super().__init__(timestamp)
        self.value: np.ndarray = image

    def __str__(self):
        return f'[{self.timestamp}] RGB Image: {self.value.shape}'


class PositionObservation(Observation):
    def __init__(self, timestamp, coords: _Vec3):
        assert isinstance(coords, tuple)

        super().__init__(timestamp)
        self.value: _Vec3 = coords

    def __str__(self):
        return f'[{self.timestamp}] World Position: {self.value}'


class ActorsObservation(Observation):
    def __init__(self, timestamp, actors: List[DynamicActor]):
        assert isinstance(actors, list)

        super().__init__(timestamp)
        self.value: List[DynamicActor] = actors

    def __str__(self):
        return f'[{self.timestamp}] Actor List of length {len(self.value)}'


class OccupancyGridObservation(Observation):
    def __init__(self, timestamp, grid: Grid):
        assert isinstance(grid, Grid)

        super().__init__(timestamp)
        self.value: Grid = grid

    def __str__(self):
        n_occupied = len(list(filter(lambda c: c.state.value == GridCellState.OCCUPIED, self.value.cells)))
        return f'[{self.timestamp}] Occupancy grid with {len(self.value.cells)} cells ({n_occupied} occupied)'
