from multiprocessing.pool import Pool
from typing import List, Set, Dict, Callable, FrozenSet

import numpy as np

from client.observation import LinearObservationTracker
from client.utils import ClientUtils
from common import quadkey
from common.constants import *
from common.model import UncertainProperty, DynamicActor
from common.observation import GnssObservation, LidarObservation
from common.occupancy import Grid, GridCell, GridCellState
from common.raycast import raycast
from common.util import proc_wrap

N_PROC = 6  # Experimentally found to be best


class OccupancyGridManager:
    def __init__(self, level, radius, offset_z=0):
        self.level = level
        self.radius = radius
        self.ego: DynamicActor = None

        self.gnss_current: GnssObservation = None
        self.quadkey_current: quadkey.QuadKey = None
        self.quadkey_prev: quadkey.QuadKey = None
        self.ego_occupied_cells: FrozenSet[quadkey.QuadKey] = frozenset()

        self.offset_z = offset_z
        # TODO: Prevent memory leak
        self.grids: Dict[str, Grid] = dict()
        self.convert: Callable = lambda x: (x[0] * 4.77733545044234e-5 - 13715477.0910797, x[1] * 4.780960965231e-5 - 9026373.31437847)
        self.tracker: LinearObservationTracker = LinearObservationTracker(n=6)
        self.pool = Pool(processes=N_PROC)

        self._cell_base_z: float = 0.0

    def update_gnss(self, obs: GnssObservation):
        key = obs.to_quadkey(self.level)
        self.gnss_current = obs
        self._cell_base_z = (self.gnss_current.value[2] - self.offset_z / 2) + OCCUPANCY_BBOX_OFFSET

        if self.quadkey_current is None or key != self.quadkey_current:
            self.quadkey_current = key
            self._recompute()
            self.quadkey_prev = self.quadkey_current
            return True

        return False

    def update_ego(self, ego: DynamicActor):
        self.ego = ego

    def get_grid(self) -> Grid:
        return self.grids[self.quadkey_current.key] if self.quadkey_current and self.quadkey_current.key in self.grids and self.grids[self.quadkey_current.key] else None

    def get_cell_base_z(self) -> float:
        return self._cell_base_z

    def match_with_lidar(self, obs: LidarObservation):
        grid = self.get_grid()
        if grid is None or obs is None or self.ego is None or self.ego.location is None:
            return False

        n = len(grid.cells)
        grid_cells = list(grid.cells)
        batch_size = np.math.ceil(n / N_PROC)
        batches = [(
            np.array(list(map(lambda c: c.bounds, grid_cells[i * batch_size:i * batch_size + batch_size])), dtype=np.float32),
            obs.value,
            np.array(self.ego.location.value.components(), dtype=np.float32)
        ) for i in range(n)]

        result: List[np.ndarray] = self.pool.starmap(self._wrapped_mcwl, batches)  # ndarray[GridCellState]

        for i, r in enumerate(result):
            for j, s in enumerate(r):
                s = GridCellState(s)
                group_key = f'grid_cell_{i * batch_size + j}'
                cell = grid_cells[i * batch_size + j]
                if cell.quad_key in self.ego_occupied_cells:
                    continue
                self.tracker.track(group_key, s)
                self.tracker.cycle_group(group_key)
                cell.state = UncertainProperty(self.tracker.get(group_key, s), s)

        return True

    def tear_down(self):
        self.pool.close()
        self.pool.join()
        self.pool.terminate()

    @staticmethod
    def _match_cells_with_lidar(bounds: np.ndarray, points: np.ndarray, loc: np.ndarray) -> np.ndarray:
        if bounds.shape[0] == 0:
            return np.array([])

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

    @classmethod
    def _wrapped_mcwl(cls, *args, **kwargs):
        return proc_wrap(cls._match_cells_with_lidar, *args, **kwargs)

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

        quadkeys: List[quadkey.QuadKey] = list(map(lambda k: quadkey.QuadKey(k), nearby))

        self.ego_occupied_cells: FrozenSet[quadkey.QuadKey] = ClientUtils.get_occupied_cells(self.ego) if self.ego else frozenset()

        cells: Set[GridCell] = set(map(lambda q: GridCell(
            quad_key=q,
            convert=self.convert,
            offset=self.get_cell_base_z(),
            height=OCCUPANCY_BBOX_HEIGHT,
            state=UncertainProperty(1., GridCellState.OCCUPIED if q in self.ego_occupied_cells else GridCellState.UNKNOWN)
        ), quadkeys))
        return Grid(cells)
