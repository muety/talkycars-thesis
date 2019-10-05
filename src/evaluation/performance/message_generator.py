'''
CAUTION: Since messages are pre-generated, the timestamp will be out-dated pretty soon. Don't forget to set MAX_AGE to a very high tolerance in the edge node.
'''

import argparse
import logging
import random
import os
import sys
import time
from multiprocessing import current_process
from multiprocessing.pool import Pool
from threading import Thread, Lock
from typing import Tuple, List, Union, FrozenSet

from client import TileSubscriptionService
from common import quadkey
from common.constants import *
from common.quadkey import QuadKey
from common.serialization.schema import Vector3D, RelativeBBox, ActorType, GridCellState
from common.serialization.schema.actor import PEMDynamicActor
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMOccupancyGrid, PEMGridCell
from common.serialization.schema.relation import PEMRelation
from common.util import geo

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

STATES: List[GridCellState] = GridCellState.options()
COLORS: List[str] = ['blue', 'red', 'green', 'yellow', 'black', 'white']

class MessageGenerator:
    def __init__(
            self,
            grid_tile_level: int = OCCUPANCY_TILE_LEVEL,
            grid_radius: int = OCCUPANCY_RADIUS_DEFAULT,
            max_rate: float = 100,  # msgs / sec (total)
            n_sample_egos: int = 100,
            n_sample_scenes: int = 256,
    ):
        # Parameters
        self.grid_tile_level = grid_tile_level
        self.grid_radius = grid_radius
        self.max_rate: float = max_rate
        self.n_sample_scenes: int = n_sample_scenes
        self.n_sample_egos: int = n_sample_egos
        self.parallel: bool = True

        # Derived parameters
        self.start_location: Tuple[float, float, float] = (49.000494, 7.995230, 2.8)
        self.types: List[ActorType] = [ActorType.vehicle(), ActorType.pedestrian(), ActorType.unknown()]

        # Pre-generated pools of sample data to randomly choose from
        self.gen_ego_pool: List[PEMDynamicActor] = None
        self.gen_quads_pool: List[List[QuadKey]] = None
        self.gen_msgs: List[Tuple[bytes, FrozenSet[str]]] = None  # Tuples of serialized message and list of contained tiles' quadkeys

        # Pre-generated fixed data to be used in every message
        self.gen_others: List[PEMDynamicActor] = None

        # Services
        self.tss: TileSubscriptionService = TileSubscriptionService(on_graph_cb=lambda a: a)

        # Misc
        self.rate_count_thread: Thread = Thread(target=self._eval_rate, daemon=True)
        self.lock: Lock = Lock()
        self.msg_count: int = 0
        self.bytes_count: int = 0
        self.last_tick: float = -1
        self.start_time: float = 0

    def run(self):
        self.init_egos()
        self.init_others()
        self.init_quad_keys()
        self.init_msgs()

        self.tss.update_position(quadkey.from_geo(self.start_location[:2], self.grid_tile_level))
        self.rate_count_thread.start()

        time.sleep(1)
        self.start_time = time.time()

        while True:
            msg, tiles = random.choice(self.gen_msgs)
            self.tss.publish_graph(msg, tiles)

            with self.lock:
                self.msg_count += 1
                self.bytes_count += len(msg)

            if self.last_tick >= 0 and time.monotonic() - self.last_tick < 1 / self.max_rate:
                time.sleep(max(0.0, 1 / self.max_rate - (time.monotonic() - self.last_tick)))

            self.last_tick = time.monotonic()

    def init_egos(self):
        self.gen_ego_pool = []

        for _ in range(self.n_sample_egos):
            start: Tuple[float, float, float] = geo.gnss_add_meters(
                self.start_location,
                (random.uniform(-10, 10), random.uniform(-10, 10), 0)
            )

            bbox_corners = (
                geo.gnss_add_meters(start, (2.2, 1.1, 0.8), delta_factor=-1),
                geo.gnss_add_meters(start, (2.2, 1.1, 0.8), delta_factor=1)
            )
            bbox = RelativeBBox(lower=Vector3D(bbox_corners[0]), higher=Vector3D(bbox_corners[1]))

            self.gen_ego_pool.append(PEMDynamicActor(
                id=random.randint(1, 9999),
                type=PEMRelation(1., ActorType.vehicle()),
                position=PEMRelation(.9, Vector3D(start)),
                color=PEMRelation(1., random.choice(COLORS)),
                bounding_box=PEMRelation(.9, bbox),
                velocity=PEMRelation(.99, Vector3D((0., 0., 0.))),
                acceleration=PEMRelation(.99, Vector3D((0., 0., 0.)))
            ))

    def init_others(self):
        self.gen_others = []

        for i in range(2):
            extent = random.uniform(1.5, 3.5), random.uniform(1, 2), random.uniform(.5, 1.5)
            pos: Tuple[float, float, float] = geo.gnss_add_meters(self.start_location, (
                random.uniform(-10, 10), random.uniform(-10, 10), 0))

            bbox_corners = (
                geo.gnss_add_meters(pos, extent, delta_factor=-1),
                geo.gnss_add_meters(pos, extent, delta_factor=1)
            )
            bbox = RelativeBBox(lower=Vector3D(bbox_corners[0]), higher=Vector3D(bbox_corners[1]))

            self.gen_others.append(PEMDynamicActor(
                id=random.randint(2, 9999),
                type=PEMRelation(self.rand_prob(), random.choice(self.types)),
                position=PEMRelation(self.rand_prob(), Vector3D(pos)),
                color=PEMRelation(self.rand_prob(), random.choice(COLORS)),
                bounding_box=PEMRelation(self.rand_prob(), bbox),
                velocity=PEMRelation(self.rand_prob(), Vector3D((random.uniform(-1, 1), random.uniform(-1, 1), 0))),
                acceleration=PEMRelation(self.rand_prob(), Vector3D((random.uniform(-1, 1), random.uniform(-1, 1), 0)))
            ))

    def init_quad_keys(self):
        self.gen_quads_pool = []

        for ego in self.gen_ego_pool:
            center: QuadKey = quadkey.from_geo(ego.position.object.as_tuple()[:2], self.grid_tile_level)
            self.gen_quads_pool.append([QuadKey(k) for k in center.nearby(self.grid_radius)])

    def init_msgs(self):
        logging.info(f'Generating and serializing {self.n_sample_scenes} scenes for {self.n_sample_egos} ego vehicles.')

        # not within a daemon process, but standalone
        # TODO: Make batches of data to prevent from redundant data copying to processes
        if self.parallel and current_process().name == 'MainProcess':  
            args = [(self.gen_quads_pool, self.gen_others, self.gen_ego_pool) for _ in range(self.n_sample_scenes)]
            with Pool(processes=os.cpu_count()) as pool:
                self.gen_msgs = pool.starmap(self.generate_message, args)
        else:
            self.gen_msgs = [self.generate_message(self.gen_quads_pool, self.gen_others, self.gen_ego_pool) for _ in range(self.n_sample_scenes)]

    @classmethod
    def generate_scene(cls, quads: List[List[QuadKey]], others: List[PEMDynamicActor], egos: List[PEMDynamicActor]) -> Tuple[PEMTrafficScene, FrozenSet[str]]:
        grid: PEMOccupancyGrid = PEMOccupancyGrid(cells=[])

        idx: int = random.randint(0, len(egos) - 1)
        ego: PEMDynamicActor = egos[idx]
        quadkeys: List[QuadKey] = quads[idx]
        hashes: List[str] = []

        for qk in quadkeys:
            state: GridCellState = random.choice(STATES)
            occupant: Union[PEMDynamicActor, None] = random.choice(others) if state == GridCellState.occupied() else None

            grid.cells.append(PEMGridCell(
                hash=qk.to_quadint(),
                state=PEMRelation(cls.rand_prob(), state),
                occupant=PEMRelation(cls.rand_prob(), occupant)
            ))

            hashes.append(qk.key)

        scene: PEMTrafficScene = PEMTrafficScene(
            timestamp=time.time(),
            measured_by=ego,
            occupancy_grid=grid
        )

        return scene, frozenset(hashes)

    @classmethod
    def generate_message(cls, quads: List[List[QuadKey]], others: List[PEMDynamicActor], egos: List[PEMDynamicActor]) -> Tuple[bytes, FrozenSet[str]]:
        scene, tiles = cls.generate_scene(quads, others, egos)
        return scene.to_bytes(), tiles

    @staticmethod
    def rand_prob() -> float:
        return max(0, min(1, random.gauss(.5, .25)))

    def _eval_rate(self):
        while True:
            with self.lock:
                diff: float = time.time() - self.start_time
                logging.info(
                    f'Average Rate: {round(self.msg_count / diff)} msg / sec, {round((self.bytes_count / 1024) / diff)} kBytes / sec')
            time.sleep(1)


def run(args=sys.argv[1:]):
    argparser = argparse.ArgumentParser(description='TalkyCars Message Generator')
    argparser.add_argument('--rate', '-r', default=5, type=int, help='Message Rate')
    argparser.add_argument('--level', '-l', default=OCCUPANCY_TILE_LEVEL, type=int, help='Occupancy Grid Tile Level')
    argparser.add_argument('--radius', '-R', default=OCCUPANCY_RADIUS_DEFAULT, type=int, help='Occupancy Grid Radius')
    argparser.add_argument('--egos', '-e', default=1, type=int, help='Number of different ego vehicles to simulate sending data from')

    args, _ = argparser.parse_known_args(args)
    print(f'Rate: {args.rate}, Level: {args.level}, Radius: {args.radius}')

    gen = MessageGenerator(grid_radius=args.radius, grid_tile_level=args.level, max_rate=args.rate, n_sample_egos=args.egos)
    gen.run()


if __name__ == '__main__':
    run()
