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
    def get(self, for_tile: QuadKey) -> T:
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

    def get(self, for_tile: QuadKey) -> PEMTrafficScene:
        if len(self.observations) == 0:
            return None
        t0 = time.time()
        all_obs = [dq.pop() for dq in self.observations.values() for i in range(len(dq))]
        a = self._fuse_scene(for_tile, all_obs)  # TODO: Make order of magnitude faster!!
        print(time.time() - t0)
        return a

    def _fuse_scene(self, for_tile: QuadKey, scenes: List[PEMTrafficScene]) -> PEMTrafficScene:
        fused_scene: PEMTrafficScene = PEMTrafficScene(timestamp=int(time.time()))
        fused_grid: PEMOccupancyGrid = self._fuse_grid(for_tile, list(map(lambda t: (t.timestamp, t.occupancy_grid), scenes)))

        fused_scene.occupancy_grid = fused_grid

        return fused_scene

    def _fuse_grid(self, for_tile: QuadKey, grids: List[Tuple[int, PEMOccupancyGrid]]) -> PEMOccupancyGrid:
        fused_grid: PEMOccupancyGrid = PEMOccupancyGrid()
        fused_cells: List[PEMGridCell] = self._fuse_cells(for_tile, list(map(lambda t: (t[0], t[1].cells), grids)))

        fused_grid.cells = fused_cells

        return fused_grid

    def _fuse_cells(self, for_tile: QuadKey, cells: List[Tuple[int, List[PEMGridCell]]]) -> List[PEMGridCell]:
        fused_cells: List[PEMGridCell] = []

        tiles: List[QuadKey] = for_tile.children(at_level=OCCUPANCY_TILE_LEVEL)
        cells_flattened: List[Tuple[int, PEMGridCell]] = [(t1[0], t2) for t1 in cells for t2 in t1[1]]

        for qk in tiles:
            cells_filtered: List[Tuple[int, PEMGridCell]] = list(filter(lambda e: e[1].hash == qk.key, cells_flattened))
            fused_cells.append(self._fuse_cell(qk, cells_filtered))

        return fused_cells

    def _fuse_cell(self, cell_hash: QuadKey, cells: List[Tuple[int, PEMGridCell]]) -> PEMGridCell:
        fused_cell: PEMGridCell = PEMGridCell(hash=cell_hash.key)

        # 1.: Cell State
        state_obs = [[] for i in range(len(GridCellState.options()))]
        for ts, cell in cells:
            if cell.hash != cell_hash.key:
                continue
            state_obs[cell.state.object.index()].append(self._decay(ts) * cell.state.confidence)
        state_probs = [float(np.mean(p)) if len(p) > 0 else 0 for p in state_obs]
        fused_cell.state = PEMRelation[GridCellState](
            confidence=np.max(state_probs),
            object=GridCellState.options()[np.amax(state_probs)]
        )

        return fused_cell

    def _decay(self, timestamp: int) -> float:
        return 1  # TODO
