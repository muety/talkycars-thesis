import pickle
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Any, cast

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
