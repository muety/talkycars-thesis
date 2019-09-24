from abc import ABC, abstractmethod

import carla


class EgoStrategy(ABC):
    def __init__(self):
        self.ego = None

    def init(self, ego):
        self.ego = ego

    @abstractmethod
    def step(self, **kwargs) -> bool:
        pass

    @property
    @abstractmethod
    def player(self) -> carla.Vehicle:
        pass

from .empty import *
from .manual import *
from .observer_1 import *
from .random_path import *
