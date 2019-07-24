from typing import TypeVar, Generic, List

T = TypeVar('T')


class FusionService(Generic[T]):
    def __init__(self):
        self.observations: List[T] = []

    def push(self, observation: T):
        # TODO: Implement
        self.observations.append(observation)

    def get(self) -> T:
        # TODO: Implement
        if len(self.observations) == 0:
            return None
        return self.observations[0]
