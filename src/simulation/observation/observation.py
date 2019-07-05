from datetime import datetime
from typing import Tuple

import numpy as np


class Observation:
    def __init__(self, local_timestamp):
        assert isinstance(local_timestamp, int) or isinstance(local_timestamp, float)

        self.local_timestamp = local_timestamp
        # Caution: Uses local platform time!
        self.timestamp = datetime.now().timestamp()

class GnssObservation(Observation):
    def __init__(self, timestamp, coords: Tuple[float, float, float]):
        assert isinstance(coords, tuple)

        super().__init__(timestamp)
        self.value = coords

    def __str__(self):
        return f'[{self.timestamp}] GPS Position: {self.value}'

class LidarObservation(Observation):
    def __init__(self, timestamp, points: np.ndarray):
        assert isinstance(points, np.ndarray)

        super().__init__(timestamp)
        self.value = points

    def __str__(self):
        return f'[{self.timestamp}] Point Cloud: {self.value.shape}'

class PositionObservation(Observation):
    def __init__(self, timestamp, coords: Tuple[float, float, float]):
        assert isinstance(coords, tuple)

        super().__init__(timestamp)
        self.value = coords

    def __str__(self):
        return f'[{self.timestamp}] World Position: {self.value}'