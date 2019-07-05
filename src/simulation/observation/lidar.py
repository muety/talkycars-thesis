import numpy as np

from .observation import Observation


class LidarObservation(Observation):
    def __init__(self, timestamp, points: np.ndarray):
        assert isinstance(points, np.ndarray)

        super().__init__(timestamp)
        self.value = points