import logging
import random
import time

from agents.navigation.basic_agent import BasicAgent
from util import simulation

import carla
from common.constants import *
from common.util.waypoint import WaypointProvider
from . import EgoStrategy

DISTANCE_THRESHOLD_METERS = 15.


class ConvoyStrategy(EgoStrategy):
    def __init__(self, id: int, waypoint_provider: WaypointProvider = None, config: int = 0, wait_for_egos: int = 0, **kwargs):
        super().__init__()

        self.id: int = id
        self.config: int = config
        self.ready: bool = False
        self.point_start: carla.Transform = None
        self.point_end: carla.Transform = None
        self.agent: BasicAgent = None
        self.wait_for: int = wait_for_egos
        self.wpp: WaypointProvider = waypoint_provider

        self.kwargs = kwargs

        self._player: carla.Vehicle = None
        self._step_count: int = 0
        self._start_time: float = 0

    def init(self, ego):
        super().init(ego)

        if not self.wpp:
            self._init_missing_waypoint_provider(ego)

        n_egos_present: int = simulation.count_present_vehicles(SCENE2_EGO_PREFIX, self.ego.world)
        self.point_start = self.wpp.get_by_index(n_egos_present)
        self.point_end = self.wpp.get_by_index(-1)
        self._player = self._create_player()  # Create player

        self.agent = BasicAgent(self.player, target_speed=EGO_TARGET_SPEED, ignore_traffic_lights=True)
        self.agent.set_location_destination(self.point_end.location)

    def step(self, clock=None) -> bool:
        if self.ego is None or not self.ready and simulation.count_present_vehicles(SCENE2_EGO_PREFIX, self.ego.world) < self.wait_for:
            return False

        if self._start_time == 0:
            self._start_time = time.monotonic()

        self.ready = True

        # Wait some time before starting
        if time.monotonic() - self._start_time < 3.0:
            return False

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
        logging.info(f'Using {seed} as a random seed.')

        self.wpp = WaypointProvider(ego.world, seed=seed)

        if self.config == 0:
            self.wpp.set_waypoints([
                carla.Transform(location=carla.Location(296, 55, .1), rotation=carla.Rotation(0, 180, 0)),
                carla.Transform(location=carla.Location(302, 55, .1), rotation=carla.Rotation(0, 180, 0)),
                carla.Transform(location=carla.Location(308, 55, .1), rotation=carla.Rotation(0, 180, 0)),
                carla.Transform(location=carla.Location(314, 55, .1), rotation=carla.Rotation(0, 180, 0)),
                carla.Transform(location=carla.Location(320, 55, .1), rotation=carla.Rotation(0, 180, 0)),
                carla.Transform(location=carla.Location(326, 55, .1), rotation=carla.Rotation(0, 180, 0)),
                carla.Transform(location=carla.Location(92, 36, .1), rotation=carla.Rotation(0, -90, 0))
            ])
