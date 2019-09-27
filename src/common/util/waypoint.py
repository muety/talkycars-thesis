import random
from typing import List

import carla


class WaypointProvider:
    def __init__(self, waypoints: List[carla.Transform] = [], min_spacing: float = 4., seed: int = 10):
        self.waypoints: List[carla.Transform] = waypoints
        self.picked: List[carla.Transform] = []
        self.min_spacing: float = min_spacing

        random.seed(seed)

    def set_waypoints(self, waypoints: List[carla.Transform]):
        self.waypoints: List[carla.Transform] = waypoints

    def get(self) -> carla.Waypoint:
        if len(self.waypoints) == 0:
            return None

        wp: carla.Transform = random.choice(self.waypoints)

        while len(self.waypoints) > 1 and not self.valid(wp):
            wp = random.choice(self.waypoints)

        if not self.valid(wp):
            return None

        self.waypoints.remove(wp)
        self.picked.append(wp)

        return wp

    # Initializes this instance's waypoints as all unoccupied waypoints in a map
    def update(self, world: carla.World):
        spawn_points: List[carla.Transform] = world.get_map().get_spawn_points()
        vehicles: List[carla.Vehicle] = world.get_actors().filter('vehicle.*')
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

        self.waypoints = free_spawn_points

    def valid(self, wp: carla.Transform) -> bool:
        for w in self.picked:
            if w.location.distance(wp.location) <= self.min_spacing:
                return False
        return True
