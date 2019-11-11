from typing import List, Tuple

from keyboard_control import KeyboardControl

import carla
from common.constants import SCENE2_AREA_CENTER
from . import EgoStrategy


class ManualEgoStrategy(EgoStrategy):
    def __init__(self, config: int = 0):
        self.configs: List[Tuple[str, carla.Transform, bool]] = [
            # vehicle, spawn point, fixed
            ('vehicle.tesla.model3', None, False),
            ('vehicle.tesla.model3', carla.Transform(carla.Location(x=-155.2, y=-36.1, z=1.5), carla.Rotation(yaw=180)), False),
            ('vehicle.tesla.model3', carla.Transform(carla.Location(*SCENE2_AREA_CENTER), carla.Rotation(yaw=90)), False),
            ('vehicle.tesla.model3', carla.Transform(carla.Location(x=-155.2, y=-36.1, z=1.5), carla.Rotation(yaw=180)), True),
            ('vehicle.mercedes-benz.coupe', carla.Transform(carla.Location(x=-170.2, y=-36.1, z=1.5), carla.Rotation(yaw=180)), True),
        ]

        assert config < len(self.configs)

        self.vehicle_filter: str = self.configs[config][0]
        self.spawn_point: str = self.configs[config][1]
        self.fixed: bool = self.configs[config][2]
        self.controller: KeyboardControl = None
        self._player: carla.Vehicle = None

        super().__init__()

    def init(self, ego):
        super().init(ego)

        if not self.spawn_point:
            self.spawn_point = ego.map.get_spawn_points()[0]

        self._player = self._create_player()

    def step(self, clock=None) -> bool:
        if self.ego is None or self.fixed:
            return False

        if not self.controller:
            self.controller = KeyboardControl(self.ego, False)

        return self.controller.parse_events(self.ego, clock)

    @property
    def player(self) -> carla.Vehicle:
        return self._player

    def _create_player(self) -> carla.Vehicle:
        blueprint = self.ego.world.get_blueprint_library().filter(self.vehicle_filter)[0]
        blueprint.set_attribute('role_name', self.ego.name)
        if blueprint.has_attribute('color'):
            color = blueprint.get_attribute('color').recommended_values[0]
            blueprint.set_attribute('color', color)

        return self.ego.world.spawn_actor(blueprint, self.spawn_point)
