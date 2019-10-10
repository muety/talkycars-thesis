import typing
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Dict, List, Any, cast, Tuple

from common.constants import *
from common.observation import Observation, OccupancyGridObservation, ActorsObservation


class ObservationSink(ABC):
    @abstractmethod
    def __init__(self, keys: List[str]):
        self.keys: List[str] = keys
        self.accumulator: Dict[str, Observation] = {}

    def push(self, key: str, obs: Observation):
        assert key not in self.accumulator

        self.accumulator[key] = obs
        if len(self.accumulator) == len(self.keys):
            self._dump()
            self.accumulator.clear()

    @abstractmethod
    def _get_property_dict(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def _dump(self):
        pass


class CsvObservationSink(ObservationSink, ABC):
    def __init__(self, keys: List[str], outpath: str):
        super().__init__(keys)
        self.outpath: str = outpath
        self.filehandle = open(outpath, 'a', buffering=1024 * 20)  # buffer 20 kBytes

    def __del__(self):
        self.filehandle.close()

    def _dump(self):
        data: Dict[str, Any] = self._get_property_dict()

        if not data:
            return

        initialized: bool = os.path.exists(self.outpath)

        if not initialized:
            self.filehandle.write(','.join(list(data.keys())) + '\n')
        self.filehandle.write(','.join(list(data.values())) + '\n')


class CsvTrafficSceneSink(CsvObservationSink):
    def _get_property_dict(self) -> typing.OrderedDict[str, Any]:
        if OBS_ACTOR_EGO not in self.accumulator or OBS_GRID_COMBINED not in self.accumulator:
            return None

        grid: OccupancyGridObservation = cast(OccupancyGridObservation, self.accumulator[OBS_GRID_COMBINED])
        ego: ActorsObservation = cast(ActorsObservation, self.accumulator[OBS_ACTOR_EGO])

        assert len(ego.value) == 1

        ego_velo: Tuple[float, float, float] = ego.value[0].dynamics.velocity.value.components()
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
