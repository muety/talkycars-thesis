from typing import List, Set, Callable

from common.constants import *
from common.model import UncertainProperty
from common.occupancy import Grid, GridCell
from common.quadkey import QuadKey
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMGridCell


class FusionUtils:
    @staticmethod
    def scenes_to_single_grid(scenes: List[PEMTrafficScene], convert: Callable, offset: float, height: float = OCCUPANCY_BBOX_HEIGHT) -> Grid:
        pem_cells: Set[PEMGridCell] = set().union(*list(map(lambda g: set(g.cells), map(lambda s: s.occupancy_grid, scenes))))
        cells: Set[GridCell] = set(map(
            lambda c: GridCell(
                quad_key=QuadKey(c.hash),
                state=UncertainProperty(c.state.confidence, c.state.object.value),
                convert=convert,
                offset=offset,
                height=height)
            , pem_cells)
        )
        return Grid(cells=cells)
