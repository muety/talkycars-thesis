from typing import TypeVar, Generic

T = TypeVar('T')


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class UncertainProperty(Generic[T]):
    def __init__(self, confidence: float = None, value: T = None):
        self.confidence: float = confidence
        self.value: T = value


from .actor import *
from .geom import *