from multiprocessing.pool import Pool
from typing import List, Set, Dict, Callable

import numpy as np
from lib import quadkey
from lib.occupancy.grid import Grid, GridCell, GridCellState
from lib.raycast import raycast
from observation import GnssObservation, LidarObservation, PositionObservation

OCCUPANCY_BBOX_OFFSET = .1
OCCUPANCY_BBOX_HEIGHT = 3.5
N_THREADS = 4

class OccupancyGridManager:
    def __init__(self, level, radius, offset_z=0):
        self.level = level
        self.radius = radius
        self.location = None
        self.gnss_current: GnssObservation = None
        self.quadkey_current: quadkey.QuadKey = None
        self.quadkey_prev: quadkey.QuadKey = None
        self.offset_z = offset_z
        # TODO: Prevent memory leak
        self.grids: Dict[str, Grid] = dict()
        self.convert: Callable = lambda x: (x[0] * 4.78296128064646e-5 - 13731628.4846192, x[1] * -4.7799656322138e-5 + 9024494.06807157)
        self.pool = Pool(processes=N_THREADS)

    def update_gnss(self, obs: GnssObservation):
        key = obs.to_quadkey(self.level)
        self.gnss_current = obs

        if self.quadkey_current is None or key != self.quadkey_current:
            self.quadkey_current = key
            self._recompute()
            self.quadkey_prev = self.quadkey_current
            return True

        return False

    def set_position(self, obs: PositionObservation):
        self.location = obs.value

    def get_grid(self) -> Grid:
        return self.grids[self.quadkey_current.key] if self.quadkey_current.key in self.grids else None

    def match_with_lidar(self, obs: LidarObservation):
        grid = self.get_grid()
        if grid is None or obs is None:
            return

        n = len(grid.cells)
        grid_cells = list(grid.cells)
        batch_size = np.math.ceil(n / N_THREADS)
        batches = [(list(map(lambda c: c.bounds, grid_cells[i*batch_size:i*batch_size+batch_size])), obs.value, self.location) for i in range(n)]

        # Doing this as sub-processes actually adds ~4 FPS on average
        result = self.pool.map(self._match_cells, batches)

        for i, r in enumerate(result):
            for j, s in enumerate(r):
                grid_cells[i * batch_size + j].state = s

    @staticmethod
    def _match_cells(args):
        cells, obs, loc = args
        states = [GridCellState.UNKNOWN] * len(cells)

        for i, cell in enumerate(cells):
            for point in obs:
                direction = point - loc
                if raycast.aabb_contains(cell, point):
                    states[i] = GridCellState.OCCUPIED
                    break
                if raycast.aabb_intersect(cell, raycast.Ray3D(loc, direction)):
                    states[i] = GridCellState.FREE
                    break

        return states

    def _recompute(self):
        key = self.quadkey_current
        if key.key in self.grids:
            return
        self.grids[key.key] = self._compute_grid()

    def _compute_grid(self) -> Grid:
        incremental = False

        if self.quadkey_prev is not None and self.quadkey_prev.key in self.grids and self.grids[self.quadkey_prev.key] is not None:
            tile = self.quadkey_current.to_tile()[0]
            prev_tile = self.quadkey_prev.to_tile()[0]
            diff = (prev_tile[0] - tile[0], prev_tile[1] - tile[1])
            if diff[0] <= 1 and diff[1] <= 1:
                incremental = True

        if incremental:
            add, remove = set(), set()

            if diff[0] != 0:
                remove_config = ((int(np.sign(diff[0]) * self.radius + diff[0]),), range(-self.radius, self.radius + 1))
                add_config = ((int(-np.sign(diff[0]) * self.radius),), range(-self.radius, self.radius + 1))
                add = add.union(set(self.quadkey_current.nearby_custom(add_config)))
                remove = remove.union(set(self.quadkey_current.nearby_custom(remove_config)))
            if diff[1] != 0:
                remove_config = (range(-self.radius, self.radius + 1), (int(np.sign(diff[1]) * self.radius + diff[1]),))
                add_config = (range(-self.radius, self.radius + 1), (int(-np.sign(diff[1]) * self.radius),))
                add = add.union(set(self.quadkey_current.nearby_custom(add_config)))
                remove = remove.union(set(self.quadkey_current.nearby_custom(remove_config)))
            if diff[0] != 0 and diff[1] != 0:
                remove_config = ((diff[0] * (self.radius + 1),), (diff[1] * (self.radius + 1),))
                add_config = ((diff[0] * (self.radius),), (diff[1] * (self.radius),))
                add = add.union(set(self.quadkey_current.nearby_custom(add_config)))
                remove = remove.union(set(self.quadkey_current.nearby_custom(remove_config)))

            nearby = self.grids[self.quadkey_prev.key].to_quadkeys_str() \
                .difference(remove) \
                .union(add)

            if len(nearby) != (self.radius * 2 + 1) ** 2:
                incremental = False

        if not incremental:
            nearby = self.quadkey_current.nearby(self.radius)

        assert len(nearby) == (self.radius * 2 + 1) ** 2

        base_z = (self.gnss_current.value[2] - self.offset_z) + OCCUPANCY_BBOX_OFFSET
        quadkeys: List[quadkey.QuadKey] = list(map(lambda k: quadkey.QuadKey(k), nearby))
        cells: Set[GridCell] = set(map(lambda q: GridCell(q, self.convert, base_z, OCCUPANCY_BBOX_HEIGHT), quadkeys))
        return Grid(cells)