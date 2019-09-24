from agents.navigation.agent import Agent

import carla
from . import EgoStrategy


class Observer1EgoStrategy(EgoStrategy):
    def __init__(self):
        self.me: carla.Vehicle = None
        self.agent: Agent = None

        self.spawn_point: carla.Transform = carla.Transform(carla.Location(x=-203.9, y=-64.2, z=.1), carla.Rotation(yaw=90))
        self.done: bool = False

        super().__init__()

    def init(self, ego):
        super().init(ego)
        self.me = self._create_player()

    def step(self, clock=None) -> bool:
        if self.ego is None:
            return False

        # Basic Agent Example
        # control = self.agent.run_step()
        # control.manual_gear_shift = False
        # self.me.apply_control(control)

        if not self.done:
            control = carla.VehicleControl()
            control.manual_gear_shift = False
            if self.me.get_location().y < self.spawn_point.location.y + 7.5:
                control.throttle = .5
                control.brake = 0
            else:
                control.throttle = 0
                control.brake = 1
            self.me.apply_control(control)

            if self.me.get_location().y >= self.spawn_point.location.y + 7.5:
                self.done = True

    @property
    def player(self) -> carla.Vehicle:
        return self.me

    def _create_player(self) -> carla.Vehicle:
        blueprint = self.ego.world.get_blueprint_library().filter('vehicle.audi.a2')[0]
        blueprint.set_attribute('role_name', self.ego.name)
        if blueprint.has_attribute('color'):
            color = blueprint.get_attribute('color').recommended_values[0]
            blueprint.set_attribute('color', color)

        me: carla.Vehicle = self.ego.world.spawn_actor(blueprint, self.spawn_point)
        # Basic Agent Example
        # self.agent = BasicAgent(self.me)
        # self.agent.set_destination((
        #     spawn_point.location.x,
        #     spawn_point.location.y + 40,
        #     spawn_point.location.z), exact=True)

        return me
