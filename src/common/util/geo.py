import math
from typing import Tuple

EARTH_RADIUS = 6378137
_Vec3 = Tuple[float, float, float]


def gnss_add_meters(coords: _Vec3, delta: _Vec3, perm: Tuple[int, int, int] = (0, 1, 2), delta_factor: float = 1) -> _Vec3:
    return (
        coords[0] + ((delta[perm[0]] * delta_factor) / EARTH_RADIUS) * (180 / math.pi),
        coords[1] + ((delta[perm[1]] * delta_factor) / EARTH_RADIUS) * (180 / math.pi) / math.cos(coords[0] * (math.pi / 180)),
        coords[2] + (delta[perm[2]] * delta_factor),
    )
