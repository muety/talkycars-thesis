import random

import carla
from . import EgoStrategy


class EmptyEgoStrategy(EgoStrategy):
    def __init__(self):
        super().__init__()
        self._player = None

    def init(self, ego):
        self.ego = ego
        self._player = self._create_player()

    def step(self, **kwargs) -> bool:
        pass

    @property
    def player(self) -> carla.Vehicle:
        return self._player

    def _create_player(self) -> carla.Vehicle:
        blueprint = self.ego.world.get_blueprint_library().filter('vehicle.mini.cooperst')[0]
        blueprint.set_attribute('role_name', self.ego.name)
        if blueprint.has_attribute('color'):
            color = random.choice(blueprint.get_attribute('color').recommended_values)
            blueprint.set_attribute('color', color)

        spawn_points = self.ego.map.get_spawn_points()
        spawn_point = spawn_points[0] if spawn_points else carla.Transform()

        return self.ego.world.try_spawn_actor(blueprint, spawn_point)