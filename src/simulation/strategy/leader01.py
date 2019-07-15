import carla

from .strategy import Strategy


class Leader01Strategy(Strategy):
    def __init__(self):
        self.me: carla.Vehicle = None
        super().__init__()

    def init(self, subject):
        super().init(subject)

    def step(self, clock=None) -> bool:
        if self.subject is None:
            return False

    def spawn(self) -> carla.Vehicle:
        blueprint = self.subject.world.get_blueprint_library().filter('vehicle.audi.tt')[0]
        blueprint.set_attribute('role_name', self.subject.name)
        if blueprint.has_attribute('color'):
            color = blueprint.get_attribute('color').recommended_values[0]
            blueprint.set_attribute('color', color)

        spawn_point = self.subject.map.get_spawn_points()[0]
        spawn_point.location.y -= 10

        self.me = self.subject.world.try_spawn_actor(blueprint, spawn_point)
        return self.me