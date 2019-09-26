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

    def valid(self, wp: carla.Transform) -> bool:
        for w in self.picked:
            if w.location.distance(wp.location) <= self.min_spacing:
                return False
        return True
