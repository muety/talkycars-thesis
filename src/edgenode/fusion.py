import collections
import time
from abc import ABC, abstractmethod
from collections import deque
from itertools import starmap
from multiprocessing.pool import Pool
from typing import TypeVar, Generic, Type, Set, List, Dict, Tuple, Union, Deque, OrderedDict

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
    def __init__(self, sector: Union[QuadKey, str], keep=3):
        if isinstance(sector, str):
            sector = quadkey.from_str(sector)
        assert sector.level == EDGE_DISTRIBUTION_TILE_LEVEL

        self.keep: int = keep
        self.sector: QuadKey = sector
        self.sector_keys: Set[QuadKey] = set(sector.children(at_level=REMOTE_GRID_TILE_LEVEL))
        self.observations: Dict[int, Deque[PEMTrafficScene]] = {}

        self.fuse_pool: Pool = Pool(1)

    def push(self, sender_id: int, observation: PEMTrafficScene):
        if sender_id not in self.observations:
            self.observations[sender_id] = deque(maxlen=self.keep)
        self.observations[sender_id].append(observation)

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

        state_confs: np.ndarray[np.float32, np.float32] = np.array([[] for i in range(GridCellState.N)], dtype=np.float32)
        occ_confs: OrderedDict[int, float] = collections.OrderedDict([(-1, 0.0)])
        occupants: Dict[int, PEMDynamicActor] = dict()

        for ts, cell in cells:
            if cell.hash != cell_hash.key:
                continue

            # 1.: Cell State
            state_conf = cls._decay(ts) * cell.state.confidence
            state_conf_vec = np.array([state_conf if i == cell.state.object.index() else (1 - state_conf) / GridCellState.N for i in range(GridCellState.N)], dtype=np.float32)
            state_confs = np.hstack((state_confs, np.expand_dims(state_conf_vec, 1)))

            # 2.: Cell Occupant
            # occid = cell.occupant.object.id if cell.occupant else -1
            # if occid not in occ_confs:
            #     occ_confs[occid] = 0
            #     occupants[occid] = cell.occupant.object if occid > -1 else None
            # occ_confs[occid] += cls._decay(ts) * (cell.occupant.confidence if cell.occupant else cell.state.confidence)

        state_probs = np.mean(state_confs, axis=1)

        # occ_confs_arr = np.array(list(occ_confs.values()))
        # occ_probs = np.divide(occ_confs_arr, np.sum(occ_confs_arr))

        state = (float(np.max(state_probs)), GridCellState.options()[int(np.amax(state_probs))])
        #occ_id = (float(np.max(occ_probs)), list(occ_confs.keys())[int(np.amax(occ_probs))])

        fused_cell.state = PEMRelation[GridCellState](*state)
        # fused_cell.occupant = PEMRelation[PEMDynamicActor](
        #    confidence=occ_id[0],
        #    object=None  # TODO: Actually fuse actor properties
        #)

        return fused_cell

    @staticmethod
    def _decay(timestamp: int) -> float:
        return 1  # TODO
