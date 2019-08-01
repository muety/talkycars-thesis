from typing import TypeVar, Generic

T = TypeVar('T')


class UncertainProperty(Generic[T]):
    def __init__(self, confidence: float = None, value: T = None):
        self.confidence: float = confidence
        self.value: T = value

from .actor import *
from .geom import *