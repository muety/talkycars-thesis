import random

import carla
from keyboard_control import KeyboardControl

from .strategy import Strategy


class ManualStrategy(Strategy):
    def __init__(self):
        self.controller: KeyboardControl = None
        super().__init__()

    def init(self, subject):
        super().init(subject)

    def step(self, clock=None) -> bool:
        if self.subject is None:
            return False

        if not self.controller:
            self.controller = KeyboardControl(self.subject, False)

        return self.controller.parse_events(self.subject, clock)

    def spawn(self) -> carla.Vehicle:
        blueprint = self.subject.world.get_blueprint_library().filter('vehicle.mini.cooperst')[0]
        blueprint.set_attribute('role_name', self.subject.name)
        if blueprint.has_attribute('color'):
            color = random.choice(blueprint.get_attribute('color').recommended_values)
            blueprint.set_attribute('color', color)

        spawn_points = self.subject.map.get_spawn_points()
        spawn_point = spawn_points[0] if spawn_points else carla.Transform()

        return self.subject.world.try_spawn_actor(blueprint, spawn_point)