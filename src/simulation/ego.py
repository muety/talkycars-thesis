import argparse
import logging
import math
from threading import Lock
from typing import Dict

import pygame
from hud import HUD
from sensors import GnssSensor, LidarSensor, CameraRGBSensor
from sensors.position import PositionSensor
from strategy import Strategy, ManualStrategy
from strategy.empty import EmptyStrategy
from util import BBoxUtils, GracefulKiller

import carla
from client import ClientDialect, TalkyClient
from common.constants import *
from common.observation import OccupancyGridObservation, ActorPropertiesObservation
from common.occupancy import Grid
from common.quadkey import QuadKey


class Ego:
    def __init__(self,
                 client: carla.Client,
                 strategy: Strategy = None,
                 name: str = 'hero',
                 render: bool=False,
                 debug: bool = False,
                 is_standalone: bool = False,
                 grid_radius: float = OCCUPANCY_RADIUS_DEFAULT,
                 lidar_angle: float = LIDAR_ANGLE_DEFAULT
                 ):
        self.client: TalkyClient = None
        self.world: carla.World = client.get_world()
        self.map: carla.Map = self.world.get_map()
        self.name: str = name
        self.vehicle: carla.Vehicle = None
        self.player: carla.Vehicle = None # for compatibility
        self.grid: Grid = None
        self.hud: HUD = None
        self.strategy: Strategy = strategy
        self.display = None
        self.debug = debug
        self.n_ticked = 0
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
            self.strategy = ManualStrategy() if render else EmptyStrategy()

        self.strategy.init(self)

        # Initialize callbacks
        if self.hud:
            self.world.on_tick(self.hud.on_world_tick)

        # Initialize player vehicle
        self.vehicle = self.strategy.spawn()
        self.player = self.vehicle

        # Initialize Talky Client
        self.client = TalkyClient(for_subject_id=self.vehicle.id, dialect=ClientDialect.CARLA)
        self.client.gm.radius = grid_radius

        # Initialize sensors
        grid_range = grid_radius * QuadKey('0' * OCCUPANCY_TILE_LEVEL).side()
        lidar_min_range = (grid_range + .5) / math.cos(math.radians(lidar_angle))
        lidar_range = min(LIDAR_MAX_RANGE, max(lidar_min_range, LIDAR_Z_OFFSET / math.sin(math.radians(lidar_angle))) * 2)

        self.sensors['gnss'] = GnssSensor(self.vehicle, self.client)
        self.sensors['lidar'] = LidarSensor(self.vehicle, self.client, offset_z=LIDAR_Z_OFFSET, range=lidar_range, angle=lidar_angle)
        self.sensors['position'] = PositionSensor(self.vehicle, self.client)
        if render:
            self.sensors['camera_rgb'] = CameraRGBSensor(self.vehicle, self.hud)

        # Initialize subscriptions
        def on_grid(grid: OccupancyGridObservation):
            self.grid = grid.value

        self.client.outbound.subscribe(OBS_OCCUPANCY_GRID, on_grid)

        if is_standalone:
            lock = Lock()
            clock = pygame.time.Clock()
            killer = GracefulKiller()

            def on_tick(*args):
                if lock.locked() or killer.kill_now:
                    return

                lock.acquire()
                clock.tick_busy_loop(60)
                if self.tick(clock):
                    killer.kill_now = True
                lock.release()

            self.world.on_tick(on_tick)

            while True:
                if killer.kill_now:
                    try:
                        self.destroy()
                    finally:
                        return

                self.world.wait_for_tick()

    def tick(self, clock: pygame.time.Clock) -> bool:
        snap = self.world.get_snapshot()
        self.sensors['position'].tick(snap.timestamp.platform_timestamp)

        self.on_kth_tick(self.n_ticked + 1, snap)

        if self.strategy.step(clock=clock):
            return True

        if self.hud:
            self.hud.tick(self, clock)

        if self.display:
            self.render()
            pygame.display.flip()

        self.n_ticked += 1

        return False

    def on_kth_tick(self, k: int, snap: carla.WorldSnapshot):
        if k == 1:
            extent: carla.BoundingBox = self.vehicle.bounding_box.extent
            props_obs = ActorPropertiesObservation(
                snap.timestamp.platform_timestamp,
                color=self.vehicle.attributes['color'],
                extent=(extent.x, extent.y, extent.z,)
            )
            self.client.om.add(OBS_PROPS_PREFIX + ALIAS_EGO, props_obs)

    def render(self):
        if 'camera_rgb' not in self.sensors or not self.hud or not self.display:
            return
        self.sensors['camera_rgb'].render(self.display)
        self.hud.render(self.display)

        if self.debug:
            self._render_bboxes()

    def destroy(self):
        sensors = [
            self.sensors['camera_rgb'],
            self.sensors['lidar'],
            self.sensors['gnss'],
        ]

        for sensor in sensors:
            if sensor and sensor.sensor:
                sensor.sensor.destroy()

        self.vehicle.destroy()

    def _render_bboxes(self):
        if not self.grid:
            return

        bboxes = []
        states = []
        for cell in self.grid.cells:
            bb = cell.to_vertices()
            bb_cam = BBoxUtils.to_camera(bb.T, self.sensors['camera_rgb'].sensor, self.sensors['camera_rgb'].sensor)
            if not all(bb_cam[:, 2] > 0): continue
            bboxes.append(bb_cam)
            states.append(cell.state)
        BBoxUtils.draw_bounding_boxes(self.display, bboxes, states)

if __name__ == '__main__':
    # CAUTION: Client is not synchronized with server's tick rate in standalone mode !

    argparser = argparse.ArgumentParser(description='TalkyCars Ego Agent')
    argparser.add_argument('--strategy', default='manual', type=str, help='Strategy to run for this agent')
    argparser.add_argument('--host', default='127.0.0.1', help='IP of the host server (default: 127.0.0.1)')
    argparser.add_argument('-p', '--port', default=2000, type=int, help='TCP port to listen to (default: 2000)')
    argparser.add_argument('--rolename', default='hero', help='actor role name (default: "hero")')
    argparser.add_argument('--debug', default='true', help='whether or not to show debug information (default: true)')
    argparser.add_argument('--render', default='true', help='whether or not to render the actor\'s camera view (default: true)')

    args = argparser.parse_args()
    width, height = 1280, 720

    logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

    logging.info('listening to server %s:%s', args.host, args.port)

    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(2.0)

        strategy: Strategy = None
        if args.strategy == 'manual':
            strategy = ManualStrategy()

        ego = Ego(client,
                  name=args.rolename,
                  render=args.render.lower() == 'true',
                  debug=args.debug.lower() == 'true',
                  is_standalone=True)

    finally:
        pygame.quit()
