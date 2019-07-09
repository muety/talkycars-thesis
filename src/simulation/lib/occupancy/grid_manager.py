from typing import List, Set, Dict, Callable

from lib import quadkey
from lib.occupancy.grid import Grid, GridCell
from observation import GnssObservation

OCCUPANCY_BBOX_HEIGHT = 3.5

class OccupancyGridManager:
    def __init__(self, level, radius):
        self.level = level
        self.radius = radius
        self.gnss_current: GnssObservation = None
        self.quadkey_current: quadkey.QuadKey = None
        # TODO: Prevent memory leak
        self.grids: Dict[str, Grid] = dict()
        self.convert: Callable = lambda x: (x[0] * 4.78296128064646e-5 - 13731628.4846192, x[1] * -4.7799656322138e-5 + 9024494.06807157)

    def update_gnss(self, obs: GnssObservation):
        key = obs.to_quadkey(self.level)
        self.gnss_current = obs

        if self.quadkey_current is None or key != self.quadkey_current:
            self.quadkey_current = key
            self._recompute()

    def get_grid(self) -> Grid:
        return self.grids[self.quadkey_current.key] if self.quadkey_current.key in self.grids else None

    def _recompute(self):
        key = self.quadkey_current
        if key.key in self.grids:
            return
        self.grids[key.key] = self._compute_grid()

    def _compute_grid(self) -> Grid:
        base_z = self.gnss_current.value[2]
        offset = base_z - OCCUPANCY_BBOX_HEIGHT
        height = OCCUPANCY_BBOX_HEIGHT

        quadkeys: List[quadkey.QuadKey] = list(map(lambda k: quadkey.QuadKey(k), self.quadkey_current.nearby(self.radius)))
        cells: Set[GridCell] = set(map(lambda q: GridCell(q, self.convert, offset, height), quadkeys))
        return Grid(cells)