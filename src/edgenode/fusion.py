from typing import TypeVar, Generic, Iterable

T = TypeVar('T')


class FusionService(Generic[T]):
    def __init__(self):
        # TODO: Implement
        pass

    def fuse(self, observations: Iterable[T]) -> T:
        # TODO: Implement
        return next(iter(observations))
