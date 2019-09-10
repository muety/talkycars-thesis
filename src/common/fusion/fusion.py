import math
import time
from abc import ABC, abstractmethod
from collections import deque
from multiprocessing.pool import Pool
from typing import TypeVar, Generic, Type, Set, List, Dict, Union, Deque

import numpy as np

from common import quadkey
from common.constants import *
from common.quadkey import QuadKey
from common.serialization.schema import GridCellState
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMGridCell, PEMOccupancyGrid
from common.serialization.schema.relation import PEMRelation

T = TypeVar('T')


class FusionServiceFactory:
    @staticmethod
    def get(for_class: Type, *args, **kwargs):
        if for_class == PEMTrafficScene:
            return PEMFusionService(*args, **kwargs)

        raise ModuleNotFoundError('no implementation available for given type')


class FusionService(Generic[T], ABC):
    @abstractmethod
    def push(self, sender_id: int, observation: T):
        pass

    @abstractmethod
    def get(self, max_age: float) -> Dict[str, T]:
        pass

    @abstractmethod
    def set_sector(self, sector: Union[QuadKey, str]):
        pass

    @abstractmethod
    def tear_down(self):
        pass


class PEMFusionService(FusionService[PEMTrafficScene]):
    def __init__(self, sector: Union[QuadKey, str], keep=3):
        self.sector: QuadKey = None
        self.sector_keys: Set[str] = None
        self.grid_keys: Set[str] = None

        self.keep: int = keep
        self.indices: Dict[str, int] = {}
        self.reverse_indices: List[str] = []
        self.observations: Dict[int, Deque[PEMTrafficScene]] = {}

        self.state_matrices: Dict[int, Deque[np.ndarray]] = {}

        self.fuse_pool: Pool = Pool(6, )

        self.set_sector(sector)

    def set_sector(self, sector: Union[QuadKey, str]):
        if isinstance(sector, str):
            sector = quadkey.from_str(sector)
        assert sector.level == EDGE_DISTRIBUTION_TILE_LEVEL

        self.sector = sector
        self.sector_keys = set(map(lambda qk: qk.key, sector.children(at_level=REMOTE_GRID_TILE_LEVEL)))
        self.grid_keys = set(map(lambda qk: qk.key, sector.children(at_level=OCCUPANCY_TILE_LEVEL)))

        self.reverse_indices = [''] * len(self.grid_keys)

        for i, qk in enumerate(sorted(self.grid_keys)):
            self.indices[qk] = i
            self.reverse_indices[i] = qk

    def push(self, sender_id: int, observation: PEMTrafficScene):
        if sender_id not in self.observations:
            self.observations[sender_id] = deque(maxlen=self.keep)
            self.state_matrices[sender_id] = deque(maxlen=self.keep)

        self.observations[sender_id].append(observation)
        self.state_matrices[sender_id].append(self._grid2states(observation.occupancy_grid))

    '''
    Returns a map from tiles at REMOTE_GRID_TILE_LEVEL to fused PEMTrafficScenes
    '''

    def get(self, max_age: float = float('inf')) -> Dict[str, PEMTrafficScene]:
        if len(self.observations) == 0:
            return None
        now: float = time.time()
        all_obs: List[PEMTrafficScene] = [dq[i]
                                          for dq in self.observations.values()
                                          for i in range(len(dq))
                                          if now - dq[i].timestamp < max_age]
        all_states: List[np.ndarray] = [a[i]
                                        for a in self.state_matrices.values()
                                        for i in range(len(a))]  # TODO

        return self._fuse_scenes(all_obs, all_states)

    def tear_down(self):
        self.fuse_pool.close()
        self.fuse_pool.join()
        self.fuse_pool.terminate()

    def _grid2states(self, grid: PEMOccupancyGrid) -> np.ndarray:
        n_states: int = GridCellState.N
        cell_matrix: np.ndarray = np.full((len(self.indices), n_states), np.nan)

        for cell in grid.cells:
            if cell.hash not in self.indices:
                continue

            for i in range(n_states):
                s: int = cell.state.object.value
                c: float = cell.state.confidence
                cell_matrix[self.indices[cell.hash], i] = c if s == i else (1 - c) / n_states

        return cell_matrix

    def _fuse_scenes(self, scenes: List[PEMTrafficScene], states: List[np.ndarray]) -> Dict[str, PEMTrafficScene]:
        fused_scenes: Dict[str, PEMTrafficScene] = dict()

        # Only a temporary hack
        states = states[:len(scenes)]
        if len(states) == 0:
            return fused_scenes

        fused_grids: Dict[str, PEMOccupancyGrid] = self._fuse_grids(
            list(map(lambda t: t.timestamp, scenes)),
            states
        )

        for k, grid in fused_grids.items():
            fused_scenes[k] = PEMTrafficScene(ts=time.time(), occupancy_grid=grid)

        return fused_scenes

    def _fuse_grids(self, timestamps: List[int], states: List[np.ndarray]) -> Dict[str, PEMOccupancyGrid]:
        if len(timestamps) != len(states):
            return dict()

        states: List[np.ndarray] = [np.array(states[i]) * self._decay(timestamps[i]) for i in range(len(timestamps))]
        fused_grids: Dict[str, PEMOccupancyGrid] = {}
        fused_cells: Dict[str, List[PEMGridCell]] = {}  # REMOTE_GRID_TILE_LEVEL keys to cells

        # Step 1: Fuse states
        fused_states: np.ndarray = np.nanmean(states, axis=0)
        mask: np.ndarray = np.isnan(fused_states).sum(axis=1) == 0
        idx_lookup: np.ndarray = mask.cumsum()
        fused_states_masked: np.ndarray = fused_states[mask]

        max_confs: np.ndarray = np.max(fused_states_masked, axis=1)
        max_states: np.ndarray = np.argmax(fused_states_masked, axis=1)

        for idx in range(0, fused_states_masked.shape[0]):
            trueidx: int = int(np.argmax(idx_lookup > idx))
            qk: str = self.reverse_indices[trueidx]

            key: str = qk[:REMOTE_GRID_TILE_LEVEL]
            if key not in fused_cells:
                fused_cells[key] = []

            fused_cells[key].append(PEMGridCell(
                hash=qk,
                state=PEMRelation(float(max_confs[idx]), GridCellState(int(max_states[idx]))),
                occupant=PEMRelation(0., None)
            ))

        for qk, items in fused_cells.items():
            fused_grids[qk] = PEMOccupancyGrid(cells=items)

        return fused_grids

    @staticmethod
    def _decay(timestamp: float) -> float:
        t = int((time.time() - timestamp) * 10)  # t in 100ms
        return math.exp(-t * FUSION_DECAY_LAMBDA)
