import random
from typing import List

import carla


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

    def get(self) -> carla.Transform:
        if len(self.waypoints) == 0:
            return None

        wp: carla.Transform = random.choice(self.waypoints)

        while len(self.waypoints) - len(self.picked) > 1 and not self.valid(wp):
            wp = random.choice(self.waypoints)

        if wp is None or not self.valid(wp):
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
        for w in self.picked:
            if w.location.distance(wp.location) <= self.min_spacing:
                return False
        return True
