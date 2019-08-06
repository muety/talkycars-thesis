import time
from abc import ABC, abstractmethod
from collections import deque
from typing import TypeVar, Generic, Type, Set, List, Dict, Tuple, Union, Deque

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
    def get(for_class: Type, *args):
        if for_class == PEMTrafficScene:
            return PEMFusionService(*args)

        raise ModuleNotFoundError('no implementation available for given type')


class FusionService(Generic[T], ABC):
    @abstractmethod
    def push(self, sender_id: int, observation: T):
        pass

    @abstractmethod
    def get(self) -> Dict[str, T]:
        pass


class PEMFusionService(FusionService[PEMTrafficScene]):
    def __init__(self, sector: Union[QuadKey, str], keep=5):
        if isinstance(sector, str):
            sector = quadkey.from_str(sector)
        assert sector.level == EDGE_DISTRIBUTION_TILE_LEVEL

        self.keep: int = keep
        self.sector: QuadKey = sector
        self.sector_keys: Set[QuadKey] = set(sector.children(at_level=REMOTE_GRID_TILE_LEVEL))
        self.observations: Dict[int, Deque[PEMTrafficScene]] = {}

    def push(self, sender_id: int, observation: PEMTrafficScene):
        if sender_id not in self.observations:
            self.observations[sender_id] = deque(maxlen=self.keep)
        self.observations[sender_id].append(observation)

    def get(self) -> Dict[str, PEMTrafficScene]:
        if len(self.observations) == 0:
            return None
        all_obs = [dq[i] for dq in self.observations.values() for i in range(len(dq))]
        a = self._fuse_scene(all_obs)
        return a

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
        cell_map: Dict[str, List[Tuple[int, PEMGridCell]]] = dict()

        for cell_obs in cells:
            for cell in cell_obs[1]:
                hash = cell.hash[:REMOTE_GRID_TILE_LEVEL]
                if hash not in cell_map:
                    cell_map[hash] = []
                    fused_cells[hash] = []
                cell_map[hash].append((cell_obs[0], cell))

        for tile in cell_map.keys():
            tiles: List[QuadKey] = quadkey.from_str(tile).children(at_level=OCCUPANCY_TILE_LEVEL)

            for qk in tiles:
                hash = qk.key[:REMOTE_GRID_TILE_LEVEL]
                if hash not in cell_map:
                    continue
                a = self._fuse_cell(qk, cell_map[hash])
                fused_cells[hash].append(a)

        return fused_cells

    def _fuse_cell(self, cell_hash: QuadKey, cells: List[Tuple[int, PEMGridCell]]) -> PEMGridCell:
        fused_cell: PEMGridCell = PEMGridCell(hash=cell_hash.key)

        # 1.: Cell State
        state_count = np.zeros((3,))
        state_confs = np.zeros((3,))
        for ts, cell in cells:
            if cell.hash != cell_hash.key:
                continue
            state_confs[cell.state.object.index()] += self._decay(ts) * cell.state.confidence
            state_count[cell.state.object.index()] += 1
        state_probs = np.nan_to_num(state_confs / state_count)
        fused_cell.state = PEMRelation[GridCellState](
            confidence=float(np.max(state_probs)),
            object=GridCellState.options()[int(np.amax(state_probs))]
        )

        return fused_cell

    def _decay(self, timestamp: int) -> float:
        return 1  # TODO
