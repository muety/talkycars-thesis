import importlib
from abc import ABC, abstractmethod
from typing import List

from ego import Ego

import carla


class SceneFactory():
    @staticmethod
    def get(scene_name: str, sim: carla.Client):
        # Throws ModuleNotFound error if given name does not correspond to an actual module
        scene = importlib.import_module('.scene1', 'simulation.scenes')
        return scene.Scene(sim)


class AbstractScene(ABC):
    @abstractmethod
    def create_and_spawn(self):
        pass

    @abstractmethod
    def get_egos(self) -> List[Ego]:
        pass

    @abstractmethod
    def get_npcs(self) -> List[carla.Actor]:
        pass
