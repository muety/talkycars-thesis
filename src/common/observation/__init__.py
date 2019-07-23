from datetime import datetime
from typing import Tuple, Iterable

import numpy as np

from common import quadkey
from common.occupancy import Grid, GridCellState

_Vec3 = Tuple[float, float, float]
_Dynamics = Tuple[_Vec3]


class Observation:
    def __init__(self, local_timestamp: int = 0, confidence: float = 1):
        assert isinstance(local_timestamp, int) or isinstance(local_timestamp, float)

        self.local_timestamp = local_timestamp
        # Caution: Uses local platform time!
        self.timestamp = datetime.now().timestamp()
        self.confidence = confidence


class EgoObservation(Observation):
    pass


class GnssObservation(EgoObservation):
    def __init__(self, timestamp, coords: _Vec3):
        assert isinstance(coords, tuple)

        super().__init__(timestamp)
        self.value = coords

    def to_quadkey(self, level=20) -> quadkey.QuadKey:
        return quadkey.from_geo(self.value[:2], level)

    def to_tile(self, level=20):
        return self.to_quadkey(level).to_tile()

    def __str__(self):
        return f'[{self.timestamp}] GPS Position: {self.value}'


class LidarObservation(EgoObservation):
    def __init__(self, timestamp, points: Iterable):
        super().__init__(timestamp)
        self.value = points

    def __str__(self):
        return f'[{self.timestamp}] Point Cloud: {self.value.shape}'


class CameraRGBObservation(EgoObservation):
    def __init__(self, timestamp, image: np.ndarray):
        assert isinstance(image, np.ndarray)

        super().__init__(timestamp)
        self.value = image

    def __str__(self):
        return f'[{self.timestamp}] RGB Image: {self.value.shape}'


class PositionObservation(Observation):
    def __init__(self, timestamp, coords: _Vec3):
        assert isinstance(coords, tuple)

        super().__init__(timestamp)
        self.value = coords

    def __str__(self):
        return f'[{self.timestamp}] World Position: {self.value}'


class ActorDynamicsObservation(Observation):
    def __init__(self, timestamp, velocity: _Vec3, acceleration: _Vec3):
        super().__init__(timestamp)
        self.value = (velocity, acceleration,)

    def __str__(self):
        return f'[{self.timestamp}] Velocity: {self.value[0]}, Acceleration: {self.value[1]}'


class ActorPropertiesObservation(Observation):
    def __init__(self, timestamp, color: str, extent: _Vec3):
        super().__init__(timestamp)
        self.value = (color, extent,)

    def __str__(self):
        return f'[{self.timestamp}] Properties'


class OccupancyGridObservation(Observation):
    def __init__(self, timestamp, grid: Grid):
        assert isinstance(grid, Grid)

        super().__init__(timestamp)
        self.value = grid

    def __str__(self):
        n_occupied = len(list(filter(lambda c: c.state == GridCellState.OCCUPIED, self.value.cells)))
        return f'[{self.timestamp}] Occupancy grid with {len(self.value.cells)} cells ({n_occupied} occupied)'