import logging
import random

from agents.navigation.basic_agent import BasicAgent
from util import simulation

import carla
from common.constants import *
from common.util.waypoint import WaypointProvider
from . import EgoStrategy

DISTANCE_THRESHOLD_METERS = 15.


class RandomPathEgoStrategy(EgoStrategy):
    def __init__(self, id: int, waypoint_provider: WaypointProvider = None, wait_for_egos: int = 0, **kwargs):
        super().__init__()

        self.id: int = id
        self.ready: bool = False
        self.point_start: carla.Transform = None
        self.point_end: carla.Transform = None
        self.agent: BasicAgent = None
        self.wait_for: int = wait_for_egos
        self.wpp: WaypointProvider = waypoint_provider

        self.kwargs = kwargs

        self._player: carla.Vehicle = None
        self._step_count: int = 0

    def init(self, ego):
        super().init(ego)

        if not self.wpp:
            self._init_missing_waypoint_provider(ego)

        self.point_start = self.wpp.get()
        self.point_end = self.wpp.get()

        self._player = self._create_player()
        self.agent = BasicAgent(self.player, target_speed=30)
        self.agent.set_destination((
            self.point_end.location.x,
            self.point_end.location.y,
            self.point_end.location.z,
        ))

    def step(self, clock=None) -> bool:
        if self.ego is None or not self.ready and simulation.count_present_vehicles(SCENE2_ROLE_NAME_PREFIX, self.ego.world) < self.wait_for:
            return False

        self.ready = True

        control: carla.VehicleControl = self.agent.run_step(debug=False)
        self._step_count += 1

        if self._step_count % 10 == 0 and self.agent.done():
            logging.info(f'{self.ego.name} has reached its destination.')
            return True

        return self.player.apply_control(control)

    @property
    def player(self) -> carla.Vehicle:
        return self._player

    def _create_player(self) -> carla.Vehicle:
        blueprint = random.choice(self.ego.world.get_blueprint_library().filter('vehicle.tesla.model3'))
        blueprint.set_attribute('role_name', self.ego.name)
        if blueprint.has_attribute('color'):
            colors = blueprint.get_attribute('color').recommended_values
            blueprint.set_attribute('color', colors[self.id % (len(colors) - 1)])

        return self.ego.world.spawn_actor(blueprint, self.point_start)

    def _init_missing_waypoint_provider(self, ego: 'ego.Ego'):
        seed: int = self.kwargs['seed'] if 'seed' in self.kwargs else 0
        self.wpp = WaypointProvider([], seed=seed)
        self.wpp.update(ego.world)
