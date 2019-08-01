from abc import ABC, abstractmethod


class Strategy(ABC):
    def __init__(self):
        self.ego = None

    def init(self, ego):
        self.ego = ego

    @abstractmethod
    def step(self, **kwargs) -> bool:
        pass

    @abstractmethod
    def spawn(self):
        pass

from .empty import *
from .manual import *
from .observer_1 import *
