from itertools import starmap
from typing import List, Set, Callable

from common.constants import *
from common.model import UncertainProperty
from common.occupancy import Grid, GridCell
from common.quadkey import QuadKey
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMGridCell
from common.util import flatmap


class FusionUtils:
    """
    Maps list of PEMTrafficScenes from different tiles (REMOTE_GRID_TILE_LEVEL) to a single one
    """

    @classmethod
    def scenes_to_single_grid(cls, scenes: List[PEMTrafficScene], convert: Callable, offset: float, height: float = OCCUPANCY_BBOX_HEIGHT) -> Grid:
        cells: Set[GridCell] = set(starmap(cls._convert_cell, map(lambda c: (c, convert, offset, height), flatmap(lambda s: s.occupancy_grid.cells, scenes))))
        return Grid(cells=cells)

    @staticmethod
    def _convert_cell(c: PEMGridCell, convert: Callable, offset: float, height: float = OCCUPANCY_BBOX_HEIGHT) -> GridCell:
        return GridCell(
            quad_key=QuadKey(c.hash),
            state=UncertainProperty(c.state.confidence, c.state.object.value),
            convert=convert,
            offset=offset,
            height=height)
