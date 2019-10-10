import argparse
import math
import sys
from multiprocessing.pool import ThreadPool
from threading import Lock
from typing import Dict

import pygame
from hud import HUD
from sensors import GnssSensor, LidarSensor, CameraRGBSensor
from sensors.actors import ActorsSensor
from sensors.position import PositionSensor
from strategy import *
from strategy.empty import EmptyEgoStrategy
from util import bbox, simulation

import carla
from client import ClientDialect, TalkyClient
from common.constants import *
from common.observation import OccupancyGridObservation
from common.occupancy import Grid
from common.quadkey import QuadKey
from common.util import GracefulKiller, proc_wrap

ADD_ARGS_PREFIX = '--strat-'


class Ego:
    def __init__(self,
                 client: carla.Client,
                 strategy: EgoStrategy = None,
                 name: str = 'hero',
                 render: bool = False,
                 debug: bool = False,
                 record: bool = False,
                 is_standalone: bool = False,
                 grid_radius: float = OCCUPANCY_RADIUS_DEFAULT,
                 lidar_angle: float = LIDAR_ANGLE_DEFAULT
                 ):
        self.killer: GracefulKiller = GracefulKiller() if is_standalone else None
        self.sim: carla.Client = client
        self.client: TalkyClient = None
        self.world: carla.World = client.get_world()
        self.map: carla.Map = self.world.get_map()
        self.alive: bool = True
        self.name: str = name
        self.vehicle: carla.Vehicle = None
        self.player: carla.Vehicle = None  # for compatibility
        self.grid: Grid = None
        self.hud: HUD = None
        self.strategy: EgoStrategy = strategy
        self.debug: bool = debug
        self.record: bool = record
        self.n_ticked: int = 0
        self.display = None
        self.sensor_tick_pool: ThreadPool = ThreadPool(processes=6)
        self.sensors: Dict[str, carla.Sensor] = {
            'gnss': None,
            'lidar': None,
            'camera_rgb': None,
            'position': None,
        }

        # Initialize visual stuff
        if render:
            pygame.init()
            pygame.font.init()
            self.display = pygame.display.set_mode((RES_X, RES_Y), pygame.HWSURFACE | pygame.DOUBLEBUF)
            self.hud = HUD(RES_X, RES_X)

        # Initialize strategy
        if not self.strategy:
            self.strategy = ManualEgoStrategy() if render else EmptyEgoStrategy()
        self.strategy.init(self)

        # Initialize callbacks
        if self.hud:
            self.world.on_tick(self.hud.on_world_tick)

        # Initialize player vehicle
        self.vehicle = self.strategy.player
        self.player = self.vehicle

        # Initialize Talky Client
        self.client = TalkyClient(for_subject_id=self.vehicle.id, dialect=ClientDialect.CARLA)
        self.client.gm.radius = grid_radius

        # Initialize sensors
        grid_range = grid_radius * QuadKey('0' * OCCUPANCY_TILE_LEVEL).side()
        lidar_min_range = (grid_range + .5) / math.cos(math.radians(lidar_angle))
        lidar_range = min(LIDAR_MAX_RANGE, max(lidar_min_range, LIDAR_Z_OFFSET / math.sin(math.radians(lidar_angle))) * 2)

        self.sensors['gnss'] = GnssSensor(self.vehicle, self.client, offset_z=GNSS_Z_OFFSET)
        self.sensors['lidar'] = LidarSensor(self.vehicle, self.client, offset_z=LIDAR_Z_OFFSET, range=lidar_range, angle=lidar_angle)
        self.sensors['actors'] = ActorsSensor(self.vehicle, self.client)
        self.sensors['position'] = PositionSensor(self.vehicle, self.client)
        if render:
            self.sensors['camera_rgb'] = CameraRGBSensor(self.vehicle, self.hud)

        # Initialize subscriptions
        def on_grid(grid: OccupancyGridObservation):
            self.grid = grid.value

        self.client.outbound.subscribe(OBS_GRID_COMBINED, on_grid)

        if is_standalone:
            lock = Lock()
            clock = pygame.time.Clock()

            def on_tick(*args):
                if lock.locked() or self.killer.kill_now:
                    return

                lock.acquire()
                clock.tick_busy_loop(60)
                if self.tick(clock):
                    self.killer.kill_now = True
                lock.release()

            self.world.on_tick(on_tick)

            while True:
                if self.killer.kill_now:
                    try:
                        self.destroy()
                        return
                    finally:
                        return

                self.world.wait_for_tick()

    def tick(self, clock: pygame.time.Clock) -> bool:
        if not self.alive:
            return True

        snap = self.world.get_snapshot()
        self.sensor_tick_pool.apply_async(proc_wrap, (self.sensors['actors'].tick, snap.timestamp.platform_timestamp))
        self.sensor_tick_pool.apply_async(proc_wrap, (self.sensors['position'].tick, snap.timestamp.platform_timestamp))

        self.on_kth_tick(self.n_ticked + 1, snap)

        if self.strategy.step(clock=clock):
            self.alive = False
            return True

        if self.hud:
            self.hud.tick(self, clock)

        if self.display:
            self.render()
            pygame.display.flip()

        self.n_ticked += 1

        return False

    def on_kth_tick(self, k: int, snap: carla.WorldSnapshot):
        if k == 10:
            if self.record:
                self.client.toggle_recording()

    def render(self):
        if 'camera_rgb' not in self.sensors or not self.hud or not self.display:
            return
        self.sensors['camera_rgb'].render(self.display)
        self.hud.render(self.display)

        if self.debug:
            self._render_bboxes()

    def destroy(self):
        sensors = list(map(lambda s: s.sensor, filter(lambda s: hasattr(s, 'sensor'), self.sensors.values())))

        simulation.multi_destroy(self.sim, sensors + [self.vehicle])

        if self.client:
            self.client.tear_down()

    def _render_bboxes(self):
        if not self.grid:
            return

        bboxes = []
        states = []
        for cell in self.grid.cells:
            bb = cell.to_vertices()
            bb_cam = bbox.to_camera(bb.T, self.sensors['camera_rgb'].sensor, self.sensors['camera_rgb'].sensor)
            if not all(bb_cam[:, 2] > 0): continue
            bboxes.append(bb_cam)
            states.append(cell.state.value)
        bbox.draw_bounding_boxes(self.display, bboxes, states)


def run(args=sys.argv[1:]):
    # CAUTION: Client is not synchronized with server's tick rate in standalone mode !

    argparser = argparse.ArgumentParser(description='TalkyCars Ego Agent', epilog=f'Arguments specific to the selected strategy can be passed using the "{ADD_ARGS_PREFIX}" prefix (E.g. "{ADD_ARGS_PREFIX}config 1").')
    argparser.add_argument('--strategy', default='manual', type=str, help='Strategy to run for this agent')
    argparser.add_argument('--host', default='127.0.0.1', help='IP of the host server (default: 127.0.0.1)')
    argparser.add_argument('-p', '--port', default=2000, type=int, help='TCP port to listen to (default: 2000)')
    argparser.add_argument('--rolename', default='hero', help='actor role name (default: "hero")')
    argparser.add_argument('--debug', default='true', help='whether or not to show debug information (default: true)')
    argparser.add_argument('--render', default='true', help='whether or not to render the actor\'s camera view (default: true)')
    args, additional_args = argparser.parse_known_args(args)

    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
    logging.info('listening to server %s:%s', args.host, args.port)

    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(2.0)

        strat: EgoStrategy = None

        # Case 1: Manual Strategy (with additional options)
        if args.strategy == 'manual':
            arg_config: int = 0
            for i, a in enumerate(additional_args):
                if a == f'{ADD_ARGS_PREFIX}config' and len(additional_args) > i:
                    arg_config = int(additional_args[i + 1])
                    break
            strat = ManualEgoStrategy(arg_config)

        # Case 2: Observer Strategy
        elif args.strategy == 'observer':
            strat = ObserverEgoStrategy()

        # Case 3: Random Path Strategy (with additional options)
        elif args.strategy == 'random_path':
            arg_id: int = random.randint(0, 9999)
            arg_seed: int = 0
            args.rolename = f'{SCENE2_ROLE_NAME_PREFIX}_{arg_id}'
            for i, a in enumerate(additional_args):
                if a == f'{ADD_ARGS_PREFIX}seed' and len(additional_args) > i:
                    arg_seed = int(additional_args[i + 1])

            strat = RandomPathEgoStrategy(
                id=arg_id,
                wait_for_egos=SCENE2_N_EGOS,
                seed=arg_seed,
                center=SCENE2_AREA_CENTER,
                center_dist=SCENE2_CENTER_DIST
            )

        ego = Ego(client,
                  name=args.rolename,
                  render=args.render.lower() == 'true',
                  debug=args.debug.lower() == 'true',
                  strategy=strat,
                  is_standalone=True)

    finally:
        pygame.quit()


if __name__ == '__main__':
    run()
