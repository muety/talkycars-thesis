import pickle
import typing
import uuid
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Dict, List, Any, cast

from common.constants import *
from common.observation import OccupancyGridObservation, ActorsObservation
from evaluation.perception import OccupancyObservationContainer


class Sink(ABC):
    @abstractmethod
    def __init__(self, keys: List[str], auto_flush: bool = True):
        self.keys: List[str] = keys
        self.accumulator: Dict[str, Any] = {}
        self.auto_flush: bool = auto_flush

    def push(self, key: str, data: Any):
        assert key not in self.accumulator

        self.accumulator[key] = data
        if self.auto_flush and len(self.accumulator) == len(self.keys):
            self._dump()
            self.accumulator.clear()

    def force_flush(self):
        self._dump()

    @abstractmethod
    def _dump(self):
        pass


class PklOocSink(Sink, ABC):
    def __init__(self, outpath: str):
        self.only_key: str = str(uuid.uuid4())

        super().__init__([self.only_key], auto_flush=False)

        self.outpath: str = outpath
        self.filehandle = open(outpath, 'wb')

        self.accumulator[self.only_key] = []

    def push(self, key: str, data: OccupancyObservationContainer):
        cast(List[OccupancyObservationContainer], self.accumulator[self.only_key]).append(data)

    def __del__(self):
        self.filehandle.close()

    def _dump(self):
        pickle.dump(self.accumulator[self.only_key], self.filehandle)


class CsvObservationSink(Sink, ABC):
    def __init__(self, keys: List[str], outpath: str):
        super().__init__(keys)
        self.outpath: str = outpath
        self.filehandle = open(outpath, 'a')  # buffer 20 kBytes

    def __del__(self):
        self.filehandle.close()

    @abstractmethod
    def _get_property_dict(self) -> Dict[str, Any]:
        pass

    def _dump(self):
        data: Dict[str, Any] = self._get_property_dict()

        if not data:
            return

        initialized: bool = os.path.exists(self.outpath)

        if not initialized:
            self.filehandle.write(','.join(list(data.keys())) + '\n')
        self.filehandle.write(','.join(list(data.values())) + '\n')


class CsvTrafficSceneSink(CsvObservationSink):
    def _get_property_dict(self) -> typing.Union[typing.OrderedDict[str, Any], None]:
        if OBS_ACTOR_EGO not in self.accumulator or OBS_GRID_LOCAL not in self.accumulator:
            return None

        grid: OccupancyGridObservation = cast(OccupancyGridObservation, self.accumulator[OBS_GRID_LOCAL])
        ego: ActorsObservation = cast(ActorsObservation, self.accumulator[OBS_ACTOR_EGO])

        assert len(ego.value) == 1

        ego_velo: typing.Tuple[float, float, float] = ego.value[0].dynamics.velocity.value.components()
        ego_velo_conf: float = ego.value[0].dynamics.velocity.confidence

        props_dict: OrderedDict[str, Any] = OrderedDict()
        props_dict['timestamp'] = str(min(grid.timestamp, ego.timestamp))
        props_dict['velocity_x'] = str(ego_velo[0])
        props_dict['velocity_y'] = str(ego_velo[1])
        props_dict['velocity_z'] = str(ego_velo[2])
        props_dict['velocity_conf'] = '{:.3f}'.format(ego_velo_conf)

        for i, cell in enumerate(sorted(list(grid.value.cells), key=lambda c: c.quad_key.key)):
            props_dict[f'cell_state_{i}'] = str(int(cell.state.value))
            props_dict[f'cell_state_conf_{i}'] = '{:.3f}'.format(cell.state.confidence)

        return props_dict
