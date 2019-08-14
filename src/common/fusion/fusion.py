import math
import time
from abc import ABC, abstractmethod
from collections import deque
from itertools import starmap
from multiprocessing.pool import Pool
from typing import TypeVar, Generic, Type, Set, List, Dict, Tuple, Union, Deque

import numpy as np

from common import quadkey
from common.constants import *
from common.quadkey import QuadKey
from common.serialization.schema import GridCellState
from common.serialization.schema.actor import PEMDynamicActor
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
    def get(self) -> Dict[str, T]:
        pass

    @abstractmethod
    def set_sector(self, sector: Union[QuadKey, str]):
        pass


class PEMFusionService(FusionService[PEMTrafficScene]):
    def __init__(self, sector: Union[QuadKey, str], keep=3):
        self.sector: QuadKey = None
        self.sector_keys: Set[str] = None

        self.keep: int = keep
        self.observations: Dict[int, Deque[PEMTrafficScene]] = {}

        self.fuse_pool: Pool = Pool(6, )

        self.set_sector(sector)

    def set_sector(self, sector: Union[QuadKey, str]):
        if isinstance(sector, str):
            sector = quadkey.from_str(sector)
        assert sector.level == EDGE_DISTRIBUTION_TILE_LEVEL

        self.sector = sector
        self.sector_keys = set(map(lambda qk: qk.key, sector.children(at_level=REMOTE_GRID_TILE_LEVEL)))

    def push(self, sender_id: int, observation: PEMTrafficScene):
        if sender_id not in self.observations:
            self.observations[sender_id] = deque(maxlen=self.keep)
        self.observations[sender_id].append(observation)

    '''
    Returns a map from tiles at REMOTE_GRID_TILE_LEVEL to fused PEMTrafficScenes
    '''
    def get(self) -> Dict[str, PEMTrafficScene]:
        if len(self.observations) == 0:
            return None
        all_obs = [dq[i] for dq in self.observations.values() for i in range(len(dq))]
        return self._fuse_scene(all_obs)

    def _fuse_scene(self, scenes: List[PEMTrafficScene]) -> Dict[str, PEMTrafficScene]:
        fused_scenes: Dict[str, PEMTrafficScene] = dict()
        fused_grids: Dict[str, PEMOccupancyGrid] = self._fuse_grid(list(map(lambda t: (t.timestamp, t.occupancy_grid), scenes)))

        for k, grid in fused_grids.items():
            fused_scenes[k] = PEMTrafficScene(ts=time.time(), occupancy_grid=grid)

        return fused_scenes

    def _fuse_grid(self, grids: List[Tuple[int, PEMOccupancyGrid]]) -> Dict[str, PEMOccupancyGrid]:
        fused_grids: Dict[str, PEMOccupancyGrid] = dict()
        fused_cells: Dict[str, List[PEMGridCell]] = self._fuse_cells(list(map(lambda t: (t[0], t[1].cells), grids)))

        for k, cells in fused_cells.items():
            fused_grids[k] = PEMOccupancyGrid(cells=cells)

        return fused_grids

    def _fuse_cells(self, cells: List[Tuple[int, List[PEMGridCell]]]) -> Dict[str, List[PEMGridCell]]:
        fused_cells: Dict[str, List[PEMGridCell]] = dict()
        used_cells: Dict[str, Set[QuadKey]] = dict()
        cell_map: Dict[str, Deque[Tuple[int, PEMGridCell]]] = dict()

        for cell_obs in cells:
            for cell in cell_obs[1]:
                hash = cell.hash[:REMOTE_GRID_TILE_LEVEL]
                if hash not in self.sector_keys:
                    continue
                if hash not in cell_map:
                    cell_map[hash] = deque(maxlen=4 ** (len(cell.hash) - REMOTE_GRID_TILE_LEVEL))
                    used_cells[hash] = set()
                cell_map[hash].append((cell_obs[0], cell))
                used_cells[hash].add(quadkey.from_str(cell.hash))

        # Performance bottleneck -> need to multi-thread for large number of vehicles and larger grids
        result: List[Tuple[str, List[PEMGridCell]]] = self.fuse_pool.starmap(self._fuse_tile_cells, list(map(lambda k: (k, cell_map[k], used_cells[k]), cell_map.keys())))
        for tile, cells in result:
            fused_cells[tile] = cells

        return fused_cells

    @classmethod
    def _fuse_tile_cells(cls, tile: str, cells: Deque[Tuple[int, PEMGridCell]], used_keys: Set[QuadKey]) -> Tuple[str, List[PEMGridCell]]:
        return tile, list(starmap(cls._fuse_tile_cell, list(map(lambda qk: (qk, cells), used_keys))))

    @classmethod
    def _fuse_tile_cell(cls, cell_hash: QuadKey, cells: Deque[Tuple[int, PEMGridCell]]) -> PEMGridCell:
        fused_cell: PEMGridCell = PEMGridCell(hash=cell_hash.key)

        state_confs: np.ndarray[np.float32, np.float32] = np.empty((3, 0), dtype=np.float32)
        occ_confs: np.ndarray[np.float32, np.float32] = np.empty((0, 0), dtype=np.float32)

        occ_weightsum: float = 0.0
        state_weightsum: float = 0.0

        states: List[GridCellState] = GridCellState.options()
        occupants: Dict[int, PEMDynamicActor] = dict()

        for ts, cell in cells:
            if cell.hash != cell_hash.key:
                continue

            # 1.: Cell State
            weight = cls._decay(ts)
            state_conf_vec = weight * np.array([cell.state.confidence
                                       if i == cell.state.object.index()
                                                else np.minimum((1 - cell.state.confidence) / GridCellState.N, 1 / GridCellState.N)
                                                for i in range(GridCellState.N)], dtype=np.float32)
            state_confs = np.hstack((state_confs, state_conf_vec.reshape(-1, 1)))
            state_weightsum += weight

            # 2.: Cell Occupant
            occ_id = cell.occupant.object.id if cell.occupant.object else -1
            if occ_id not in occupants:
                occupants[occ_id] = cell.occupant.object if occ_id > -1 else None
                occ_confs = np.vstack((occ_confs, np.zeros(occ_confs.shape[1:])))
            occ_confs = weight * np.hstack((occ_confs, np.vstack((np.zeros((max(occ_confs.shape[0] - 1, 0), 1)), [cell.occupant.confidence]))))
            occ_weightsum += weight

        # 1.: Cell State
        state_probs = np.sum(state_confs, axis=1) / state_weightsum
        state = (float(np.max(state_probs)), states[int(np.argmax(state_probs))])

        # 2.: Cell Occupant
        occ_probs = np.sum(occ_confs, axis=1) / occ_weightsum
        occ = (float(np.max(occ_probs)), list(occupants.values())[int(np.argmax(occ_probs))])

        fused_cell.state = PEMRelation[GridCellState](*state)
        fused_cell.occupant = PEMRelation[PEMDynamicActor](*occ)

        return fused_cell

    @staticmethod
    def _decay(timestamp: float) -> float:
        t = int((time.time() - timestamp) * 10)  # t in 100ms
        return math.exp(-t * FUSION_DECAY_LAMBDA)
