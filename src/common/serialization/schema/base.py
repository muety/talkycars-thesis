import datetime
import os
import time
from typing import Dict, Type

import capnp

from common.serialization.schema import CapnpObject
from common.serialization.schema.actor import PEMDynamicActor
from common.serialization.schema.occupancy import PEMOccupancyGrid

capnp.remove_import_hook()

dirname = os.path.dirname(__file__)

occupancy = capnp.load(os.path.join(dirname, './capnp/python/occupancy.capnp'))
base = capnp.load(os.path.join(dirname, './capnp/python/base.capnp'))


class PEMTrafficScene(CapnpObject):
    def __init__(self, **entries):
        # NOTE: This is only the default. You might wanna set this explicitly.
        self.timestamp: float = time.time()  # UTC Unix timestamp
        self.min_timestamp: float = time.time()  # UTC Unix timestamp
        self.measured_by: PEMDynamicActor = None
        self.occupancy_grid: PEMOccupancyGrid = None

        if len(entries) > 0:
            self.__dict__.update(**entries)

    def to_message(self):
        scene = base.TrafficScene.new_message()

        if self.timestamp:
            scene.timestamp = self.timestamp
        if self.min_timestamp:
            scene.minTimestamp = self.min_timestamp
        if self.measured_by:
            scene.measuredBy = self.measured_by.to_message()
        if self.occupancy_grid:
            scene.occupancyGrid = self.occupancy_grid.to_message()

        return scene

    @classmethod
    def from_message_dict(cls, object_dict: Dict, target_cls: Type = None) -> 'PEMTrafficScene':
        timestamp = object_dict['timestamp'] if 'timestamp' in object_dict else None
        min_timestamp = object_dict['minTimestamp'] if 'minTimestamp' in object_dict else None
        ego = PEMDynamicActor.from_message_dict(object_dict['measuredBy']) if 'measuredBy' in object_dict else None
        grid = PEMOccupancyGrid.from_message_dict(object_dict['occupancyGrid']) if 'occupancyGrid' in object_dict else None
        return cls(
            timestamp=timestamp,
            min_timestamp=min_timestamp,
            measured_by=ego,
            occupancy_grid=grid
        )

    @classmethod
    def _get_capnp_class(cls):
        return base.TrafficScene

    def __str__(self):
        return f'Traffic scene representation measured at {datetime.datetime.fromtimestamp(self.timestamp).isoformat()}'
