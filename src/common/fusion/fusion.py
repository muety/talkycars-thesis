import math
import time
from abc import ABC, abstractmethod
from collections import deque
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
        self.grid_keys: Set[QuadKey] = None

        self.keep: int = keep
        self.indices: Dict[str, int] = {}
        self.reverse_indices: List[QuadKey] = []
        self.observations: Dict[int, Deque[PEMTrafficScene]] = {}
        self.state_matrices: Dict[int, Deque[np.ndarray]] = {}

        self.set_sector(sector)

    def set_sector(self, sector: Union[QuadKey, str]):
        if isinstance(sector, str):
            sector = quadkey.from_str(sector)

        self.sector = sector
        self.grid_keys = set(sector.children(at_level=OCCUPANCY_TILE_LEVEL))

        if len(self.reverse_indices) != len(self.grid_keys):
            self.reverse_indices = [None] * len(self.grid_keys)

        for i, qk in enumerate(sorted(self.grid_keys)):
            self.indices[qk.key] = i
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
        pass

    def _grid2states(self, grid: PEMOccupancyGrid) -> np.ndarray:
        n_states: int = GridCellState.N
        cell_matrix: np.ndarray = np.full((len(self.grid_keys), n_states), np.nan)

        for cell in grid.cells:
            qk: QuadKey = quadkey.from_int(cell.hash)
            if qk.key not in self.indices:
                continue

            for i in range(n_states):
                s: int = cell.state.object.value
                c: float = cell.state.confidence
                cell_matrix[self.indices[qk.key], i] = c if s == i else 0

        return cell_matrix

    # TODO: Make consistent with fusion.go::fuseCell()
    def _fuse_scenes(self, scenes: List[PEMTrafficScene], states: List[np.ndarray]) -> Dict[str, PEMTrafficScene]:
        fused_scenes: Dict[str, PEMTrafficScene] = dict()

        # Only a temporary hack
        states = states[:len(scenes)]
        if len(states) == 0:
            return fused_scenes

        timestamps: List[float] = list(map(lambda t: t.timestamp, scenes))
        fused_grids: Dict[str, PEMOccupancyGrid] = self._fuse_grids(timestamps, states)

        for k, grid in fused_grids.items():
            fused_scenes[k] = PEMTrafficScene(
                timestamp=time.time(),
                min_timestamp=max(timestamps),  # How old is the latest value that was included here?
                occupancy_grid=grid
            )

        return fused_scenes

    def _fuse_grids(self, timestamps: List[float], states: List[np.ndarray]) -> Dict[str, PEMOccupancyGrid]:
        if len(timestamps) != len(states):
            return dict()

        now: float = time.time()
        weights: np.ndarray = np.array([self._decay(t, now) for t in timestamps], dtype=np.float32)
        max_weight: Union[float, np.ndarray] = np.max(weights)
        total_weights: Union[float, np.ndarray] = np.sum(weights)

        states: List[np.ndarray] = [np.array(states[i]) * w for i, w in enumerate(weights)]
        fused_grids: Dict[str, PEMOccupancyGrid] = {}
        fused_cells: Dict[str, List[PEMGridCell]] = {}  # REMOTE_GRID_TILE_LEVEL keys to cells

        # Step 1: Fuse states
        fused_states: np.ndarray = (np.nansum(states, axis=0) / total_weights) * max_weight
        mask: np.ndarray = np.isnan(fused_states).sum(axis=1) == 0
        fused_states_masked: np.ndarray = fused_states[mask]
        idx_lookup: np.ndarray = np.searchsorted(mask.cumsum(), range(fused_states_masked.shape[0]))

        max_confs: np.ndarray = np.max(fused_states_masked, axis=1)
        max_states: np.ndarray = np.argmax(fused_states_masked, axis=1)

        for idx in range(0, fused_states_masked.shape[0]):
            trueidx: int = int(idx_lookup[idx])
            qk: QuadKey = self.reverse_indices[trueidx]

            key: str = qk.key[:REMOTE_GRID_TILE_LEVEL]
            if key not in fused_cells:
                fused_cells[key] = []

            fused_cells[key].append(PEMGridCell(
                hash=qk.to_quadint(),
                state=PEMRelation(float(max_confs[idx]), GridCellState(int(max_states[idx]))),
                occupant=PEMRelation(0., None)  # TODO: Fuse occupant again
            ))

        for qk, items in fused_cells.items():
            fused_grids[qk] = PEMOccupancyGrid(cells=items)

        return fused_grids

    @staticmethod
    def _decay(timestamp: float, ref_time: float = time.time()) -> float:
        t = int((ref_time - timestamp) * 10)  # t in 100ms
        return math.exp(-t * FUSION_DECAY_LAMBDA)
