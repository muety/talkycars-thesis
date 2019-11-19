import os
from typing import Type, List

from common.serialization.schema import ProtobufObject, GridCellState
from common.serialization.schema.actor import PEMDynamicActor
from common.serialization.schema.proto import occupancy_pb2, actor_pb2
from .relation import PEMRelation

dirname = os.path.dirname(__file__)


class PEMGridCell(ProtobufObject):
    def __init__(self, **entries):
        self.hash: int = None
        self.state: PEMRelation[GridCellState] = None
        self.occupant: PEMRelation[PEMDynamicActor] = None

        if len(entries) > 0:
            self.__dict__.update(**entries)

    def to_message(self):
        return occupancy_pb2.GridCell(
            hash=self.hash,
            state=self.state.to_message() if self.state else None,
            occupant=self.occupant.to_message(type_hint=actor_pb2.DynamicActorRelation) if self.occupant else None
        )

    @classmethod
    def from_message(cls, msg, target_cls: Type['ProtobufObject'] = None) -> 'PEMGridCell':
        hash = msg.hash
        state = PEMRelation.from_message(msg.state, target_cls=GridCellState) if msg.state.confidence > 0 else None
        occupant = PEMRelation.from_message(msg.occupant, target_cls=PEMDynamicActor) if msg.occupant.confidence > 0 else None
        return cls(hash=hash, state=state, occupant=occupant)

    @classmethod
    def get_protobuf_class(cls):
        return occupancy_pb2.GridCell

    def __str__(self):
        return f'PEM Grid Cell @ {self.hash} : {self.state.object} [{self.state.confidence}]'

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return all([
            self.hash == other.hash,
            self.state.object == other.state.object,
            self.state.confidence == other.state.confidence,
            (self.occupant is None) == (other.occupant is None)
        ])

    def __hash__(self):
        return hash(self.__str__())


class PEMOccupancyGrid(ProtobufObject):
    def __init__(self, **entries):
        self.cells: List[PEMGridCell] = None

        if len(entries) > 0:
            self.__dict__.update(**entries)

    def to_message(self):
        return occupancy_pb2.OccupancyGrid(
            cells=[c.to_message() for c in self.cells]
        )

    @classmethod
    def from_message(cls, msg, target_cls: Type['ProtobufObject'] = None) -> 'PEMOccupancyGrid':
        cells = [PEMGridCell.from_message(c) for c in msg.cells]
        return cls(cells=cells)

    @classmethod
    def get_protobuf_class(cls):
        return occupancy_pb2.OccupancyGrid

    def __str__(self):
        return f'Occupancy Grid with {len(self.cells)} cells'
