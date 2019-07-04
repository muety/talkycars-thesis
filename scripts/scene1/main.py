#!/usr/bin/env python

# Copyright (c) 2019 Computer Vision Center (CVC) at the Universitat Autonoma de
# Barcelona (UAB).
#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

# Allows controlling a vehicle with a keyboard. For a simpler and more
# documented example, please take a look at tutorial.py.

from __future__ import print_function

import argparse
import collections
import datetime
import logging
import math
import random
import re
import weakref
import os
import sys
import numpy as np

import pygame

import carla
from carla import ColorConverter as cc
from scene_layout import get_scene_layout, get_dynamic_objects

from hud import HUD
from keyboard_control import KeyboardControl
from sensors.gnss import GnssSensor
from sensors.camera_rgb import CameraRGBSensor
from sensors.lidar import LidarSensor

class World(object):
    def __init__(self, client, hud, actor_role_name='hero'):
        # Attributes
        self.client = client
        self.world = client.get_world()
        self.actor_role_name = actor_role_name
        self.map = self.world.get_map()
        self.hud = hud
        self.player = None
        self.gnss_sensor = None
        self.camera_rgb_sensor = None
        self.lidar_sensor = None
        self._weather_index = 0
        self.npcs = [] # list of actor ids
        
        self.restart()
        self.world.on_tick(hud.on_world_tick)
        self.recording_enabled = False
        self.recording_start = 0

        logging.info('enabling synchronous mode.')
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        self.world.apply_settings(settings)

    def restart(self):
        # Get a random blueprint.
        blueprint = self.world.get_blueprint_library().filter('vehicle.mini.cooperst')[0]
        blueprint.set_attribute('role_name', self.actor_role_name)
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

        # Set up the sensors.
        self.gnss_sensor = GnssSensor(self.player)
        self.camera_rgb_sensor = CameraRGBSensor(self.player, self.hud)
        self.lidar_sensor = LidarSensor(self.player)

        # Set up other actors, NPCs, ...
        self.init_scene() # TODO: use strategy pattern or so

    def init_scene(self):
        available_vehicles = self.world.get_blueprint_library().filter('vehicle.*')
        location = self.player.get_location()
        spawn_points = sorted(self.map.get_spawn_points(), key=lambda x: abs(x.location.x - location.x) + abs(x.location.y - location.y))

        bp1 = random.choice(available_vehicles)
        car1 = self.world.spawn_actor(bp1, spawn_points[1])
        logging.debug(f'Spawned car 1 at {spawn_points[1].location} [{car1.bounding_box}]')
        self.npcs.append(car1)

    def tick(self, clock):
        clock.tick_busy_loop(60)
        self.world.tick()
        ts = self.world.wait_for_tick()
        self.hud.tick(self, clock)

        if ts.frame_count % 100 == 0:
            pass

            # Lane information
            # wp = self.map.get_waypoint(self.player.get_location())
            # logging.debug(wp.get_right_lane())
            # logging.debug(wp.get_left_lane())

            # Vehicle bounds
            # loc = self.map.transform_to_geolocation(self.player.get_location())
            # bb = self.player.bounding_box
            # logging.debug(f'({loc.latitude}, {loc.longitude}: [{bb.extent}])')

    def render(self, display):
        self.camera_rgb_sensor.render(display)
        self.hud.render(display)

    def destroy(self):
        actors = [
            self.camera_rgb_sensor.sensor,
            self.lidar_sensor.sensor,
            self.gnss_sensor.sensor,
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
