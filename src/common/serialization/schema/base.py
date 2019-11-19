import datetime
import os
import time
from typing import Type

from common.serialization.schema import ProtobufObject
from common.serialization.schema.actor import PEMDynamicActor
from common.serialization.schema.occupancy import PEMOccupancyGrid
from common.serialization.schema.proto import base_pb2

dirname = os.path.dirname(__file__)


class PEMTrafficScene(ProtobufObject):
    def __init__(self, **entries):
        # NOTE: This is only the default. You might wanna set this explicitly.
        self.timestamp: float = time.time()  # UTC Unix timestamp
        self.min_timestamp: float = time.time()  # UTC Unix timestamp
        self.max_timestamp: float = time.time()  # UTC Unix timestamp
        self.last_timestamp: float = time.time()  # UTC Unix timestamp
        self.measured_by: PEMDynamicActor = None
        self.occupancy_grid: PEMOccupancyGrid = None

        if len(entries) > 0:
            self.__dict__.update(**entries)

    def to_message(self):
        return base_pb2.TrafficScene(
            timestamp=self.timestamp,
            minTimestamp=self.min_timestamp,
            maxTimestamp=self.max_timestamp,
            lastTimestamp=self.last_timestamp,
            measuredBy=self.measured_by.to_message(),
            occupancyGrid=self.occupancy_grid.to_message(),
        )

    @classmethod
    def from_message(cls, msg, target_cls: Type['ProtobufObject'] = None) -> 'PEMTrafficScene':
        timestamp = msg.timestamp
        min_timestamp = msg.minTimestamp
        max_timestamp = msg.maxTimestamp
        last_timestamp = msg.lastTimestamp
        ego = PEMDynamicActor.from_message(msg.measuredBy) if msg.measuredBy.id != 0 else None
        grid = PEMOccupancyGrid.from_message(msg.occupancyGrid)

        return cls(
            timestamp=timestamp,
            min_timestamp=min_timestamp,
            max_timestamp=max_timestamp,
            last_timestamp=last_timestamp,
            measured_by=ego,
            occupancy_grid=grid
        )

    @classmethod
    def get_protobuf_class(cls):
        return base_pb2.TrafficScene

    def __str__(self):
        return f'Traffic scene representation measured at {datetime.datetime.fromtimestamp(self.timestamp).isoformat()}'
