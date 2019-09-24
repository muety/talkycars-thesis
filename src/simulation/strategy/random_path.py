import logging
import random
from typing import List

from agents.navigation.basic_agent import BasicAgent

import carla
from . import EgoStrategy

DISTANCE_THRESHOLD_METERS = 15.


class RandomPathEgoStrategy(EgoStrategy):
    def __init__(self):
        super().__init__()

        self.point_start: carla.Transform = None
        self.point_end: carla.Transform = None

        self.agent: BasicAgent = None
        self._player: carla.Vehicle = None

        self.step_count: int = 0

    def init(self, ego):
        super().init(ego)

        # TODO: make sure start and end are different and avoid collisions with other egos
        spawn_points: List[carla.Transforma] = self.ego.map.get_spawn_points()
        self.point_start = random.choice(spawn_points)
        self.point_end = random.choice(spawn_points)

        self._player = self._create_player()
        self.agent = BasicAgent(self.player, target_speed=30)
        self.agent.set_destination((
            self.point_end.location.x,
            self.point_end.location.y,
            self.point_end.location.z,
        ))

    def step(self, clock=None) -> bool:
        if self.ego is None:
            return False

        control: carla.VehicleControl = self.agent.run_step(debug=False)

        self.step_count += 1

        if self.step_count % 10 == 0 and self._probably_done():
            logging.info(f'{self.ego.name} has reached its destination.')
            return True

        return self.player.apply_control(control)

    @property
    def player(self) -> carla.Vehicle:
        return self._player

    def _create_player(self) -> carla.Vehicle:
        blueprint = random.choice(self.ego.world.get_blueprint_library().filter('vehicle.*'))
        blueprint.set_attribute('role_name', self.ego.name)
        if blueprint.has_attribute('color'):
            color = random.choice(blueprint.get_attribute('color').recommended_values)
            blueprint.set_attribute('color', color)

        return self.ego.world.spawn_actor(blueprint, self.point_start)

    def _probably_done(self):
        return self.player.get_location().distance(self.point_end.location) < DISTANCE_THRESHOLD_METERS
