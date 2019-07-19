import os
from typing import Dict, Type, List

import capnp

from common.serialization.schema import CapnpObject, GridCellState
from .relation import PEMRelation

capnp.remove_import_hook()

dirname = os.path.dirname(__file__)

occupancy = capnp.load(os.path.join(dirname, './capnp/occupancy.capnp'))

class PEMGridCell(CapnpObject):
    def __init__(self, **entries):
        self.hash: str = None
        self.state: PEMRelation[GridCellState] = None

        if len(entries) > 0:
            self.__dict__.update(**entries)

    def to_message(self):
        cell = occupancy.GridCell.new_message()

        if self.hash:
            cell.hash = self.hash
        if self.state:
            cell.state = self.state.to_message()

        return cell

    @classmethod
    def from_message_dict(cls, object_dict: Dict, target_cls: Type = None):
        hash = object_dict['hash'] if 'hash' in object_dict else None
        state = PEMRelation.from_message_dict(object_dict['state'], target_cls=GridCellState)
        return cls(hash=hash, state=state)


class PEMOccupancyGrid(CapnpObject):
    def __init__(self, **entries):
        self.cells: List[PEMGridCell] = None

        if len(entries) > 0:
            self.__dict__.update(**entries)

    def to_message(self):
        grid = occupancy.OccupancyGrid.new_message()

        if self.cells:
            cells = grid.init('cells', len(self.cells))
            for i, c in enumerate(self.cells):
                cells[i] = c.to_message()

        return grid

    @classmethod
    def from_message_dict(cls, object_dict: Dict, target_cls: Type = None):
        cells = [PEMGridCell.from_message_dict(c) for c in object_dict['cells']] if 'cells' in object_dict else None
        return cls(cells=cells)

    @classmethod
    def _get_capnp_class(cls):
        return occupancy.OccupancyGrid

    def __str__(self):
        return f'Occupancy Grid with {len(self.cells)} cells'