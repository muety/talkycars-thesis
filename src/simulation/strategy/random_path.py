import logging
import random
from typing import List

from agents.navigation.basic_agent import BasicAgent
from util.waypoint import WaypointProvider

import carla
from . import EgoStrategy

DISTANCE_THRESHOLD_METERS = 15.


class RandomPathEgoStrategy(EgoStrategy):
    def __init__(self, id: int, waypoint_provider: WaypointProvider = None, **kwargs):
        super().__init__()

        self.id: int = id
        self.point_start: carla.Transform = None
        self.point_end: carla.Transform = None
        self.agent: BasicAgent = None
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
        if self.ego is None:
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
        spawn_points: List[carla.Transform] = ego.map.get_spawn_points()
        vehicles: List[carla.Vehicle] = ego.world.get_actors().filter('vehicle.*')
        vehicle_locations: List[carla.Location] = [v.get_transform() for v in vehicles]

        def is_occupied(t: carla.Transform) -> bool:
            for p in vehicle_locations:
                if p.location.distance(t.location) <= 10:
                    return True
            return False

        free_spawn_points: List[carla.Transform] = []
        for p1 in spawn_points:
            if is_occupied(p1):
                break
            free_spawn_points.append(p1)

        seed: int = 0
        for k, v in self.kwargs.items():
            if k == 'seed':
                seed = v
                break

        self.wpp = WaypointProvider(free_spawn_points, seed=seed)
