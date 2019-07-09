from typing import List, Set, Dict, Callable

from lib import quadkey
from lib.occupancy.grid import Grid, GridCell, GridCellState
from observation import GnssObservation, LidarObservation

OCCUPANCY_BBOX_OFFSET = .1
OCCUPANCY_BBOX_HEIGHT = 3.5

class OccupancyGridManager:
    def __init__(self, level, radius, offset_z=0):
        self.level = level
        self.radius = radius
        self.gnss_current: GnssObservation = None
        self.quadkey_current: quadkey.QuadKey = None
        self.offset_z = offset_z
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

    def match_with_lidar(self, obs: LidarObservation):
        grid = self.get_grid()
        if grid is None:
            return

        # TODO: Use KD-Tree for lookup ?
        # TODO: Detect free cells by intersecting every lidar ray with every box
        # TODO: Multi-threading
        n_matches = 0

        for cell in grid.cells:
            for point in obs.value:
                if cell.contains_point(point):
                    cell.state = GridCellState.OCCUPIED
                    n_matches += 1
                    break
            cell.state = GridCellState.UNKNOWN

        # print(n_matches)

    def _recompute(self):
        key = self.quadkey_current
        if key.key in self.grids:
            return
        self.grids[key.key] = self._compute_grid()

    def _compute_grid(self) -> Grid:
        base_z = (self.gnss_current.value[2] - self.offset_z) + OCCUPANCY_BBOX_OFFSET
        quadkeys: List[quadkey.QuadKey] = list(map(lambda k: quadkey.QuadKey(k), self.quadkey_current.nearby(self.radius)))
        cells: Set[GridCell] = set(map(lambda q: GridCell(q, self.convert, base_z, OCCUPANCY_BBOX_HEIGHT), quadkeys))
        return Grid(cells)