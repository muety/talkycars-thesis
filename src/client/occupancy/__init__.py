from multiprocessing.pool import Pool
from typing import List, Set, Dict, Callable, Tuple

import numpy as np

from client.observation import LinearObservationTracker
from common import quadkey
from common.constants import *
from common.model import Point3D, UncertainProperty
from common.observation import GnssObservation, LidarObservation
from common.occupancy import Grid, GridCell, GridCellState
from common.raycast import raycast

N_PROC = 6  # Experimentally found to be best


class OccupancyGridManager:
    def __init__(self, level, radius, offset_z=0):
        self.level = level
        self.radius = radius
        self.location: Tuple[float, float, float] = None
        self.gnss_current: GnssObservation = None
        self.quadkey_current: quadkey.QuadKey = None
        self.quadkey_prev: quadkey.QuadKey = None
        self.offset_z = offset_z
        # TODO: Prevent memory leak
        self.grids: Dict[str, Grid] = dict()
        self.convert: Callable = lambda x: (x[0] * 4.77733545044234e-5 - 13715477.0910797, x[1] * 4.780960965231e-5 - 9026373.31437847)
        self.tracker: LinearObservationTracker = LinearObservationTracker(n=6)
        self.pool = Pool(processes=N_PROC)

    def update_gnss(self, obs: GnssObservation):
        key = obs.to_quadkey(self.level)
        self.gnss_current = obs

        if self.quadkey_current is None or key != self.quadkey_current:
            self.quadkey_current = key
            self._recompute()
            self.quadkey_prev = self.quadkey_current
            return True

        return False

    def set_position(self, position: Point3D):
        self.location = position.components()

    def get_grid(self) -> Grid:
        return self.grids[self.quadkey_current.key] if self.quadkey_current and self.quadkey_current.key in self.grids and self.grids[self.quadkey_current.key] else None

    def match_with_lidar(self, obs: LidarObservation):
        grid = self.get_grid()
        if grid is None or obs is None or self.location is None:
            return False

        n = len(grid.cells)
        grid_cells = list(grid.cells)
        batch_size = np.math.ceil(n / N_PROC)
        batches = [(
            np.array(list(map(lambda c: c.bounds, grid_cells[i * batch_size:i * batch_size + batch_size])), dtype=np.float32),
            obs.value,
            np.array(self.location, dtype=np.float32)
        ) for i in range(n)]

        result = self.pool.starmap(self._match_cells, batches)

        for i, r in enumerate(result):
            for j, s in enumerate(r):
                group_key = f'grid_cell_{i * batch_size + j}'
                self.tracker.track(group_key, s.value)
                self.tracker.cycle_group(group_key)
                grid_cells[i * batch_size + j].state = UncertainProperty(self.tracker.get(group_key, s.value), s)

        return True

    @staticmethod
    def _match_cells(bounds: np.ndarray, points: np.ndarray, loc: np.ndarray):
        if bounds.shape[0] == 0:
            return []

        def check_occupied(cell):
            for point in points:
                if raycast.aabb_contains(cell, point):
                    return True
            return False

        def check_intersect(cell):
            cell_dist = np.min(np.linalg.norm(loc - cell, axis=1))

            for point in points:
                direction = np.array(point - loc, dtype=np.float32)

                if raycast.aabb_intersect(cell, raycast.Ray3D(loc, direction)):
                    hit_dist = np.linalg.norm(loc - point)
                    if cell_dist < hit_dist:
                        return True
            return False

        states = np.full(bounds.shape[:1], GridCellState.UNKNOWN)
        occupied_mask = np.array(list(map(check_occupied, bounds)))
        states[occupied_mask] = GridCellState.OCCUPIED

        free_mask = np.array(list(map(check_intersect, bounds)))  # Discarding already occupied cells doesn't give performance
        states[free_mask & np.invert(occupied_mask)] = GridCellState.FREE

        return states

    def _recompute(self):
        key = self.quadkey_current
        if key.key in self.grids:
            return
        self.grids[key.key] = self._compute_grid()

    def _compute_grid(self) -> Grid:
        nearby: Set[str] = set()
        incremental: bool = False

        if self.quadkey_prev is not None and self.quadkey_prev.key in self.grids and self.grids[self.quadkey_prev.key] is not None:
            tile = self.quadkey_current.to_tile()[0]
            prev_tile = self.quadkey_prev.to_tile()[0]
            diff = (prev_tile[0] - tile[0], prev_tile[1] - tile[1])
            incremental = diff[0] <= 1 and diff[1] <= 1 and INCREMENTAL_GRIDS

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
            nearby = set(self.quadkey_current.nearby(self.radius))

        assert len(nearby) == (self.radius * 2 + 1) ** 2

        base_z = (self.gnss_current.value[2] - self.offset_z / 2) + OCCUPANCY_BBOX_OFFSET
        quadkeys: List[quadkey.QuadKey] = list(map(lambda k: quadkey.QuadKey(k), nearby))
        cells: Set[GridCell] = set(map(lambda q: GridCell(q, self.convert, base_z, OCCUPANCY_BBOX_HEIGHT), quadkeys))
        return Grid(cells)
