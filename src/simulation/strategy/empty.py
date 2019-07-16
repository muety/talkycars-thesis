import random

import carla
from .strategy import Strategy


class EmptyStrategy(Strategy):
    def __init__(self):
        self.ego = None

    def init(self, ego):
        self.ego = ego

    def step(self, **kwargs) -> bool:
        pass

    def spawn(self):
        blueprint = self.ego.world.get_blueprint_library().filter('vehicle.mini.cooperst')[0]
        blueprint.set_attribute('role_name', self.ego.name)
        if blueprint.has_attribute('color'):
            color = random.choice(blueprint.get_attribute('color').recommended_values)
            blueprint.set_attribute('color', color)

        spawn_points = self.ego.map.get_spawn_points()
        spawn_point = spawn_points[0] if spawn_points else carla.Transform()

        return self.ego.world.try_spawn_actor(blueprint, spawn_point)
