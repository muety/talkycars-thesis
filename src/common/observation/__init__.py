from datetime import datetime
from typing import Tuple, List, Any, Dict, Union

import numpy as np
from pyquadkey2 import quadkey

from common.model import DynamicActor, UncertainProperty
from common.occupancy import Grid, GridCellState
from common.serialization.schema.base import PEMTrafficScene

_Vec3 = Tuple[float, float, float]
_Dynamics = Tuple[_Vec3]


class Observation(UncertainProperty[Any]):
    def __init__(self, local_timestamp: int = 0, confidence: float = 1, meta: Union[Dict[str, Any], None] = None):
        assert isinstance(local_timestamp, int) or isinstance(local_timestamp, float)

        # Caution: Uses local platform time!
        self.timestamp: float = datetime.now().timestamp() if local_timestamp == 0 else local_timestamp
        self.meta: Union[Dict[str, Any], None] = meta

        super(Observation, self).__init__(confidence=confidence, value=None)


class EmptyObservation(Observation):
    def __init__(self, timestamp, meta: Union[Dict[str, Any], None] = None):
        super().__init__(timestamp, meta=meta)

    def __str__(self):
        return f'[{self.timestamp}] Empty Observation'


class EgoObservation(Observation):
    pass


class GnssObservation(EgoObservation):
    def __init__(self, timestamp, coords: _Vec3, meta: Union[Dict[str, Any], None] = None):
        assert isinstance(coords, tuple)

        super().__init__(timestamp, meta=meta)
        self.value: _Vec3 = coords

    def to_quadkey(self, level=20) -> quadkey.QuadKey:
        return quadkey.from_geo(self.value[:2], level)

    def to_tile(self, level=20):
        return self.to_quadkey(level).to_tile()

    def __str__(self):
        return f'[{self.timestamp}] GPS Position: {self.value}'


class LidarObservation(EgoObservation):
    def __init__(self, timestamp, points: np.ndarray, meta: Union[Dict[str, Any], None] = None):
        super().__init__(timestamp, meta=meta)
        self.value: np.ndarray = points

    def __str__(self):
        return f'[{self.timestamp}] Point Cloud: {self.value.shape}'


class CameraRGBObservation(EgoObservation):
    def __init__(self, timestamp, image: np.ndarray, meta: Union[Dict[str, Any], None] = None):
        assert isinstance(image, np.ndarray)

        super().__init__(timestamp, meta=meta)
        self.value: np.ndarray = image

    def __str__(self):
        return f'[{self.timestamp}] RGB Image: {self.value.shape}'


class PositionObservation(Observation):
    def __init__(self, timestamp, coords: _Vec3, meta: Union[Dict[str, Any], None] = None):
        assert isinstance(coords, tuple)

        super().__init__(timestamp, meta=meta)
        self.value: _Vec3 = coords

    def __str__(self):
        return f'[{self.timestamp}] World Position: {self.value}'


class ActorsObservation(Observation):
    def __init__(self, timestamp, actors: List[DynamicActor], meta: Union[Dict[str, Any], None] = None):
        assert isinstance(actors, list)

        super().__init__(timestamp, meta=meta)
        self.value: List[DynamicActor] = actors

    def __str__(self):
        return f'[{self.timestamp}] Actor List of length {len(self.value)}'


class OccupancyGridObservation(Observation):
    def __init__(self, timestamp, grid: Grid, meta: Union[Dict[str, Any], None] = None):
        assert isinstance(grid, Grid)

        super().__init__(timestamp, meta=meta)
        self.value: Grid = grid

    def __str__(self):
        n_occupied = len(list(filter(lambda c: c.state.value == GridCellState.OCCUPIED, self.value.cells)))
        return f'[{self.timestamp}] Occupancy grid with {len(self.value.cells)} cells ({n_occupied} occupied)'


class RawBytesObservation(Observation):
    def __init__(self, timestamp, data: bytes, meta: Union[Dict[str, Any], None] = None):
        assert isinstance(data, bytes)

        super().__init__(timestamp, meta=meta)
        self.value: bytes = data

    def __str__(self):
        return f'[{self.timestamp}] Bytes of length {len(self.value)}'


class PEMTrafficSceneObservation(Observation):
    def __init__(self, timestamp, scene: PEMTrafficScene, meta: Union[Dict[str, Any], None] = None):
        assert isinstance(scene, PEMTrafficScene)

        super().__init__(timestamp, meta=meta)
        self.value: PEMTrafficScene = scene

    def __str__(self):
        return f'[{self.timestamp}] PEM traffic scene measured at {self.value.timestamp}'
