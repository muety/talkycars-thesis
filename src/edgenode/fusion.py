from collections import deque
from typing import TypeVar, Generic

from common.quadkey import QuadKey

T = TypeVar('T')


class FusionService(Generic[T]):
    def __init__(self):
        self.observations: deque[T] = deque(maxlen=10)

    def push(self, observation: T):
        # TODO: Implement
        self.observations.append(observation)

    def get(self, for_tile: QuadKey) -> T:
        # TODO: Implement
        if len(self.observations) == 0:
            return None
        return next(iter(self.observations))
