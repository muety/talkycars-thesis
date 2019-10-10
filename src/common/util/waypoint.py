import random
from abc import ABC
from typing import List, Union, cast

import carla


class WaypointPickPolicy(ABC):
    pass


class RandomPickPolicy(WaypointPickPolicy):
    pass


class MaxDistancePolicy(WaypointPickPolicy):
    def __init__(self, ref: carla.Location):
        self.ref: carla.Location = ref

class WaypointProvider:
    def __init__(
            self,
            world: carla.World,
            min_spacing: float = 4.,
            center: carla.Location = carla.Location(0, 0, 0),
            center_dist: float = float('inf'),
            seed: int = 10
    ):
        self.world: carla.World = world
        self.waypoints: List[carla.Transform] = []
        self.picked: List[carla.Transform] = []
        self.min_spacing: float = min_spacing
        self.center: carla.Location = center
        self.center_dist: float = center_dist

        random.seed(seed)

    def set_waypoints(self, waypoints: List[carla.Transform]):
        self.waypoints: List[carla.Transform] = waypoints

    def get(self, policy: WaypointPickPolicy = RandomPickPolicy()) -> carla.Transform:
        wp: carla.Transform = self._pick(policy)

        if wp is None:
            return None

        self.waypoints.remove(wp)
        self.picked.append(wp)

        return wp

    # Initializes this instance's waypoints as all unoccupied waypoints in a map
    def update(self, free_only: bool = False):
        spawn_points: List[carla.Transform] = self.world.get_map().get_spawn_points()

        # Return only waypoints in a radius of x meters around a specified point on the map
        if self.center_dist < float('inf'):
            spawn_points = [p for p in spawn_points if p is not None and p.location.distance(self.center) <= self.center_dist]

        if not free_only:
            self.waypoints = spawn_points
            return

        vehicles: List[carla.Vehicle] = self.world.get_actors().filter('vehicle.*')
        vehicle_locations: List[carla.Location] = [v.get_transform() for v in vehicles]

        def is_occupied(t: carla.Transform) -> bool:
            for p in vehicle_locations:
                if p.location.distance(t.location) <= 10:
                    return True
            return False

        free_spawn_points: List[carla.Transform] = []
        for p1 in spawn_points:
            if is_occupied(p1):
                continue

            free_spawn_points.append(p1)

        self.waypoints = free_spawn_points

    def valid(self, wp: carla.Transform) -> bool:
        if not wp:
            return False

        for w in self.picked:
            if w.location.distance(wp.location) <= self.min_spacing:
                return False
        return True

    @property
    def n_available(self):
        return len(self.waypoints) - len(self.picked)

    # Picks a waypoint that is not necessarily valid
    def _pick(self, policy: WaypointPickPolicy) -> Union[carla.Transform, None]:
        if len(self.waypoints) == 0 or self.n_available <= 1:
            return None

        choice: List[carla.Transform] = [w for w in self.waypoints if w not in self.picked and self.valid(w)]
        if len(choice) == 0:
            return None

        if isinstance(policy, RandomPickPolicy):
            return random.choice(choice)
        elif isinstance(policy, MaxDistancePolicy):
            p: MaxDistancePolicy = cast(MaxDistancePolicy, policy)
            return sorted(choice, key=lambda w: w.location.distance(p.ref), reverse=True)[0]

        return None
