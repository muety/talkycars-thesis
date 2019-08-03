from abc import ABC, abstractmethod
from collections import deque
from typing import TypeVar, Generic, Type

from common.quadkey import QuadKey
from common.serialization.schema.base import PEMTrafficScene

T = TypeVar('T')


class FusionServiceFactory:
    @staticmethod
    def get(for_class: Type, *args):
        if for_class == PEMTrafficScene:
            return PEMFusionService(args)

        raise ModuleNotFoundError('no implementation available for given type')


class FusionService(Generic[T], ABC):
    @abstractmethod
    def push(self, observation: T):
        pass

    @abstractmethod
    def get(self, for_tile: QuadKey) -> T:
        pass


class PEMFusionService(FusionService[PEMTrafficScene]):
    def __init__(self, sector: QuadKey):
        self.sector: QuadKey = sector
        self.observations: deque = deque(maxlen=10)

    def push(self, observation: T):
        # TODO: Implement
        self.observations.append(observation)

    def get(self, for_tile: QuadKey) -> T:
        # TODO: Implement
        if len(self.observations) == 0:
            return None
        return next(iter(self.observations))
