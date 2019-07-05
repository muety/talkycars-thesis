from typing import Tuple

from .observation import Observation


class GnssObservation(Observation):
    def __init__(self, timestamp, lat_lon: Tuple[float, float]):
        assert isinstance(lat_lon, tuple)

        super().__init__(timestamp)
        self.value = lat_lon