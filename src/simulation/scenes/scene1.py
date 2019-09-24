from typing import List

from ego import Ego
from scenes import AbstractScene
from strategy import ManualStrategy
from util import SimulationUtils

import carla

N_PEDESTRIANS = 50


class Scene(AbstractScene):
    def __init__(self, sim: carla.Client):
        self.egos: List[Ego] = []
        self.npcs: List[carla.Actor] = []
        self._sim: carla.Client = sim
        self._world: carla.World = sim.get_world()

    def create_and_spawn(self):
        # Create egos
        main_hero = Ego(self._sim,
                        strategy=ManualStrategy(config=0),
                        name='main_hero',
                        render=True,
                        debug=False,
                        record=False)

        self.egos.append(main_hero)

        # Create walkers
        self.npcs += SimulationUtils.spawn_pedestrians(self._sim, N_PEDESTRIANS)

        # Create static vehicles
        bp1 = self._world.get_blueprint_library().filter('vehicle.volkswagen.t2')[0]
        spawn1 = carla.Transform(carla.Location(x=-198.2, y=-50.9, z=1.5), carla.Rotation(yaw=-90))
        cmd1 = carla.command.SpawnActor(bp1, spawn1)

        responses = self._sim.apply_batch_sync([cmd1])
        spawned_ids = list(map(lambda r: r.actor_id, filter(lambda r: not r.has_error(), responses)))
        spawned_actors = list(self._world.get_actors(spawned_ids))
        self.npcs += spawned_actors

    def get_egos(self) -> List[Ego]:
        return self.egos

    def get_npcs(self) -> List[carla.Actor]:
        return self.npcs
