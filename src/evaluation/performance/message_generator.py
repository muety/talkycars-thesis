'''
CAUTION: Since messages are pre-generated, the timestamp will be out-dated pretty soon. Don't forget to set MAX_AGE to a very high tolerance in the edge node.
'''

import argparse
import logging
import random
import sys
import time
from threading import Thread, Lock
from typing import Tuple, List, Union

from tqdm import trange

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


class MessageGenerator:
    def __init__(
            self,
            grid_tile_level: int = OCCUPANCY_TILE_LEVEL,
            grid_radius: int = OCCUPANCY_RADIUS_DEFAULT,
            max_rate: float = 5.,  # Hz
            n_sample_scenes: int = 128,
    ):
        self.actor_id = random.randint(1, 9999)
        self.grid_tile_level = grid_tile_level
        self.grid_radius = grid_radius
        self.max_rate: float = max_rate
        self.n_sample_scenes: int = n_sample_scenes

        self.start_location: Tuple[float, float, float] = (49.000324, 7.997861, 2.8)
        self.types: List[ActorType] = [ActorType.vehicle(), ActorType.pedestrian(), ActorType.unknown()]
        self.states: List[GridCellState] = GridCellState.options()

        self.gen_msgs: List[bytes] = None
        self.gen_ego: PEMDynamicActor = None
        self.gen_others: List[PEMDynamicActor] = None
        self.gen_quads: List[QuadKey] = None
        self.gen_keys: List[str] = None
        self.gen_pixels: List[int] = None

        self.tss: TileSubscriptionService = TileSubscriptionService(on_graph_cb=lambda a: a)

        self.rate_count_thread: Thread = Thread(target=self._eval_rate, daemon=True)
        self.lock: Lock = Lock()
        self.msg_count: int = 0
        self.bytes_count: int = 0
        self.last_tick: float = -1
        self.start_time: float = 0

    def run(self):
        self.init_ego()
        self.init_others()
        self.init_quad_keys()
        self.init_msgs()
        self.tss.update_position(quadkey.from_geo(self.start_location[:2], self.grid_tile_level))
        self.rate_count_thread.start()

        time.sleep(1)
        self.start_time = time.time()

        while True:
            msg: bytes = random.choice(self.gen_msgs)
            self.tss.publish_graph(msg, frozenset(self.gen_keys))

            with self.lock:
                self.msg_count += 1
                self.bytes_count += len(msg)

            if self.last_tick >= 0 and time.monotonic() - self.last_tick < 1 / self.max_rate:
                time.sleep(1 / self.max_rate - (time.monotonic() - self.last_tick))

            self.last_tick = time.monotonic()

    def init_msgs(self):
        logging.info(f'Generating and serializing {self.n_sample_scenes} scenes.')
        self.gen_msgs = [self.gen_scene().to_bytes() for _ in trange(self.n_sample_scenes)]

    def init_ego(self):
        bbox_corners = (
            geo.gnss_add_meters(self.start_location, (2.2, 1.1, 0.8), delta_factor=-1),
            geo.gnss_add_meters(self.start_location, (2.2, 1.1, 0.8), delta_factor=1)
        )
        bbox = RelativeBBox(lower=Vector3D(bbox_corners[0]), higher=Vector3D(bbox_corners[1]))

        self.gen_ego = PEMDynamicActor(
            id=self.actor_id,
            type=PEMRelation(1., ActorType.vehicle()),
            position=PEMRelation(.9, Vector3D(self.start_location)),
            color=PEMRelation(1., 'blue'),
            bounding_box=PEMRelation(.9, bbox),
            velocity=PEMRelation(.99, Vector3D((0., 0., 0.))),
            acceleration=PEMRelation(.99, Vector3D((0., 0., 0.)))
        )

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
                color=PEMRelation(self.rand_prob(),
                                  random.choice(['blue', 'red', 'green', 'yellow', 'black', 'white'])),
                bounding_box=PEMRelation(self.rand_prob(), bbox),
                velocity=PEMRelation(self.rand_prob(), Vector3D((random.uniform(-1, 1), random.uniform(-1, 1), 0))),
                acceleration=PEMRelation(self.rand_prob(), Vector3D((random.uniform(-1, 1), random.uniform(-1, 1), 0)))
            ))

    def init_quad_keys(self):
        center: QuadKey = quadkey.from_geo(self.start_location[:2], self.grid_tile_level)
        self.gen_keys = center.nearby(self.grid_radius)
        self.gen_quads = [QuadKey(k) for k in self.gen_keys]
        self.gen_pixels = [qk.to_pixel() for qk in self.gen_quads]

    def gen_scene(self) -> PEMTrafficScene:
        return PEMTrafficScene(
            timestamp=time.time(),
            measured_by=self.gen_ego,
            occupancy_grid=self.gen_grid()
        )

    def gen_grid(self) -> PEMOccupancyGrid:
        grid: PEMOccupancyGrid = PEMOccupancyGrid(cells=[])

        for qk in self.gen_quads:
            state: GridCellState = random.choice(self.states)
            occupant: Union[PEMDynamicActor, None] = random.choice(
                self.gen_others) if state == GridCellState.occupied() else None

            grid.cells.append(PEMGridCell(
                hash=qk.key,
                state=PEMRelation(self.rand_prob(), state),
                occupant=PEMRelation(self.rand_prob(), occupant)
            ))

        return grid

    @staticmethod
    def rand_prob() -> float:
        return max(0, min(1, random.gauss(.5, .25)))

    def _eval_rate(self):
        while True:
            with self.lock:
                diff: float = time.time() - self.start_time
                logging.info(
                    f'Average Rate: {round(self.msg_count / diff)} msg / sec, {round(self.bytes_count / diff / 1000)} kBytes / sec')
            time.sleep(1)


def run(args=sys.argv[1:]):
    argparser = argparse.ArgumentParser(description='TalkyCars Message Generator')
    argparser.add_argument('--rate', '-r', default=5, type=int, help='Message Rate')
    argparser.add_argument('--level', '-l', default=OCCUPANCY_TILE_LEVEL, type=int, help='Occupancy Grid Tile Level')
    argparser.add_argument('--radius', '-R', default=OCCUPANCY_RADIUS_DEFAULT, type=int, help='Occupancy Grid Radius')

    args, _ = argparser.parse_known_args(args)
    print(f'Rate: {args.rate}, Level: {args.level}, Radius: {args.radius}')

    gen = MessageGenerator(grid_radius=args.radius, grid_tile_level=args.level, max_rate=args.rate)
    gen.run()


if __name__ == '__main__':
    run()
