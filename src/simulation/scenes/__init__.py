import importlib
from abc import ABC, abstractmethod
from typing import List

import pygame
from agents.navigation.agent import Agent
from ego import Ego

import carla


class SceneFactory:
    @staticmethod
    def get(scene_name: str, sim: carla.Client) -> 'AbstractScene':
        # Throws ModuleNotFound error if given name does not correspond to an actual module
        scene = importlib.import_module(f'.{scene_name}', 'simulation.scenes')
        return scene.Scene(sim)


class AbstractScene(ABC):
    @abstractmethod
    def tick(self, clock: pygame.time.Clock) -> bool:
        pass

    @abstractmethod
    def init(self):
        pass

    @abstractmethod
    def create_and_spawn(self):
        pass

    @property
    @abstractmethod
    def egos(self) -> List[Ego]:
        pass

    @property
    @abstractmethod
    def npcs(self) -> List[carla.Actor]:
        pass

    @property
    @abstractmethod
    def agents(self) -> List[Agent]:
        pass

    @property
    @abstractmethod
    def world(self) -> carla.World:
        pass
