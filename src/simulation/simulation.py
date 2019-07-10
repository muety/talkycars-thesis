#!/usr/bin/env python

from __future__ import print_function

import argparse
import logging
import random

import carla
import math
import pygame
from constants import OBS_POSITION_PLAYER_POS, OBS_GNSS_PLAYER_POS, OBS_LIDAR_POINTS, OBS_CAMERA_RGB_IMAGE
from hud import HUD
from keyboard_control import KeyboardControl
from lib.occupancy.grid_manager import OccupancyGridManager
from lib.quadkey import QuadKey
from observation import ObservationManager
from observation import PositionObservation, GnssObservation, LidarObservation, CameraRGBObservation
from sensors import CameraRGBSensor
from sensors import GnssSensor
from sensors import LidarSensor
from util import BBoxUtils

OCCUPANCY_RADIUS = 5
OCCUPANCY_TILE_LEVEL = 24
LIDAR_ANGLE = 12            # Caution: Choose Lidar angle depending on grid size
LIDAR_MAX_RANGE = 100

class World(object):
    def __init__(self, client, hud, actor_name='hero'):
        # Attributes
        self.client = client
        self.world = client.get_world()
        self.actor_name = actor_name
        self.spawn_point = None
        self.map = self.world.get_map()
        self.hud = hud
        self.om = ObservationManager()
        self.gm = OccupancyGridManager(OCCUPANCY_TILE_LEVEL, OCCUPANCY_RADIUS)
        self.player = None
        self.sensors = {
            'lidar': None,
            'camera_rgb': None,
            'gnss': None
        }
        self.npcs = [] # list of actor ids
        self.box_key = None
        self.debug = True

        self.init()
        self.world.on_tick(hud.on_world_tick)
        self.recording_enabled = False
        self.recording_start = 0

        logging.info('enabling synchronous mode.')
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        self.world.apply_settings(settings)

    def init(self):
        # Get a random blueprint.
        blueprint = self.world.get_blueprint_library().filter('vehicle.mini.cooperst')[0]
        blueprint.set_attribute('role_name', self.actor_name)
        if blueprint.has_attribute('color'):
            color = random.choice(blueprint.get_attribute('color').recommended_values)
            blueprint.set_attribute('color', color)
        # Spawn the player.
        if self.player is not None:
            spawn_point = self.player.get_transform()
            spawn_point.location.z += 2.0
            spawn_point.rotation.roll = 0.0
            spawn_point.rotation.pitch = 0.0
            self.destroy()
            self.player = self.world.try_spawn_actor(blueprint, spawn_point)
        while self.player is None:
            spawn_points = self.map.get_spawn_points()
            spawn_point = spawn_points[0] if spawn_points else carla.Transform()
            self.player = self.world.try_spawn_actor(blueprint, spawn_point)
        self.spawn_point = spawn_point

        # Type registrations
        self.om.register_key(OBS_POSITION_PLAYER_POS, PositionObservation)
        self.om.register_key(OBS_GNSS_PLAYER_POS, GnssObservation)
        self.om.register_key(OBS_LIDAR_POINTS, LidarObservation)
        self.om.register_key(OBS_CAMERA_RGB_IMAGE, CameraRGBObservation)

        # Set up the sensors.
        grid_range = OCCUPANCY_RADIUS * QuadKey('0' * OCCUPANCY_TILE_LEVEL).side()
        lidar_offset_z = 2.8
        lidar_min_range = (grid_range + .5) / math.cos(math.radians(LIDAR_ANGLE))
        lidar_range = min(LIDAR_MAX_RANGE, max(lidar_min_range, lidar_offset_z / math.sin(math.radians(LIDAR_ANGLE))) + 1)

        self.sensors['gnss'] = GnssSensor(self.player, self.om)
        self.sensors['lidar'] = LidarSensor(self.player, self.om, offset_z=lidar_offset_z, range=lidar_range, angle=LIDAR_ANGLE)
        self.sensors['camera_rgb'] = CameraRGBSensor(self.player, self.hud)

        self.gm.offset_z = lidar_offset_z

        # Set up listeners
        self.init_subscriptions()

        # Set up other actors, NPCs, ...
        self.init_scene() # TODO: use strategy pattern or so

    def init_scene(self):
        # Closest NPC stuff
        available_vehicles = self.world.get_blueprint_library().filter('vehicle.*')
        location = self.player.get_location()
        spawn_points = sorted(self.map.get_spawn_points(), key=lambda x: abs(x.location.x - location.x) + abs(x.location.y - location.y))

        bp1 = random.choice(available_vehicles)
        car1 = self.world.spawn_actor(bp1, spawn_points[1])
        logging.debug(f'Spawned car 1 at {spawn_points[1].location} [{car1.bounding_box}]')
        self.npcs.append(car1)

    def init_subscriptions(self):
        self.om.subscribe(OBS_GNSS_PLAYER_POS, self.gm.update_gnss)
        self.om.subscribe(OBS_POSITION_PLAYER_POS, self.gm.set_position)

    def tick(self, clock):
        clock.tick_busy_loop(60)
        self.world.tick()
        ts = self.world.wait_for_tick()
        self.hud.tick(self, clock)

        player_location = self.player.get_location()
        position_obs = PositionObservation(ts.elapsed_seconds, (player_location.x, player_location.y, player_location.z))
        self.om.add(OBS_POSITION_PLAYER_POS, position_obs)

        self.gm.match_with_lidar(self.om.latest(OBS_LIDAR_POINTS))

    def render_bboxes(self, display):
        if not self.debug or self.gm.get_grid() is None:
            return

        bboxes = []
        states = []
        for cell in self.gm.get_grid().cells:
            bb = cell.to_vertices()
            bb_cam = BBoxUtils.to_camera(bb.T, self.sensors['camera_rgb'].sensor, self.sensors['camera_rgb'].sensor)
            if not all(bb_cam[:, 2] > 0): continue
            bboxes.append(bb_cam)
            states.append(cell.state)
        BBoxUtils.draw_bounding_boxes(display, bboxes, states)

    def render(self, display):
        self.sensors['camera_rgb'].render(display)
        self.hud.render(display)
        self.render_bboxes(display)

    def destroy(self):
        actors = [
            self.sensors['camera_rgb'].sensor,
            self.sensors['lidar'].sensor,
            self.sensors['gnss'].sensor,
            self.player] + self.npcs
        for actor in actors:
            if actor is not None:
                actor.destroy()

def game_loop(args):
    pygame.init()
    pygame.font.init()
    world = None

    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(2.0)

        display = pygame.display.set_mode(
            (args.width, args.height),
            pygame.HWSURFACE | pygame.DOUBLEBUF)

        hud = HUD(args.width, args.height)
        world = World(client, hud, args.rolename)
        controller = KeyboardControl(world, args.autopilot)

        clock = pygame.time.Clock()

        while True:
            if controller.parse_events(client, world, clock):
                return
            world.tick(clock)
            world.render(display)
            pygame.display.flip()

    finally:
        if (world and world.recording_enabled):
            client.stop_recorder()

        if world is not None:
            world.destroy()

        pygame.quit()

def main():
    argparser = argparse.ArgumentParser(
        description='CARLA Manual Control Client')
    argparser.add_argument(
        '-v', '--verbose',
        action='store_true',
        dest='debug',
        help='print debug information')
    argparser.add_argument(
        '--host',
        metavar='H',
        default='127.0.0.1',
        help='IP of the host server (default: 127.0.0.1)')
    argparser.add_argument(
        '-p', '--port',
        metavar='P',
        default=2000,
        type=int,
        help='TCP port to listen to (default: 2000)')
    argparser.add_argument(
        '-a', '--autopilot',
        action='store_true',
        help='enable autopilot')
    argparser.add_argument(
        '--res',
        metavar='WIDTHxHEIGHT',
        default='1280x720',
        help='window resolution (default: 1280x720)')
    argparser.add_argument(
        '--rolename',
        metavar='NAME',
        default='hero',
        help='actor role name (default: "hero")')
    args = argparser.parse_args()

    args.width, args.height = [int(x) for x in args.res.split('x')]

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

    logging.info('listening to server %s:%s', args.host, args.port)

    try:
        game_loop(args)
    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')


if __name__ == '__main__':
    main()
