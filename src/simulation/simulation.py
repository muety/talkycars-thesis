#!/usr/bin/env python

from __future__ import print_function

import argparse
import logging
import sys
from typing import List

import pygame
from ego import Ego
from strategy import ManualStrategy
from util.simulation import SimulationUtils

import carla
from common.constants import *
from common.util import GracefulKiller


class World(object):
    def __init__(self, client: carla.Client, scene_name: str):
        # Attributes
        self.sim = client
        self.debug = True
        self.egos: List[Ego] = []
        self.npcs: List[carla.Agent] = []

        self.world = self.init_world(scene_name)
        self.map = self.world.get_map()

        self.init()
        self.init_scene(scene_name)

        logging.info('enabling synchronous mode.')
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)

    def init(self):
        pass

    def init_world(self, scene_name: str) -> carla.World:
        if scene_name == 'scene1':
            return self.sim.load_world('Town07')
        return None

    def init_scene(self, scene_name: str):
        if scene_name == 'scene1':
            # Create main player
            main_hero = Ego(self.sim,
                            strategy=ManualStrategy(config=0),
                            name='main_hero',
                            render=True,
                            debug=True,
                            record=True)
            self.egos.append(main_hero)
            self.world.wait_for_tick()

            second_hero = Ego(self.sim,
                              strategy=ManualStrategy(config=1),
                              name='second_hero',
                              render=False,
                              debug=False,
                              record=False)
            self.egos.append(second_hero)
            self.world.wait_for_tick()

            # Create observer player
            # observer_hero = Ego(self.sim,
            #                     strategy=Observer1Strategy(),
            #                     name='observer1',
            #                     render=False,
            #                     debug=False,
            #                     grid_radius=10,
            #                     lidar_angle=9)
            # self.egos.append(observer_hero)
            # self.world.wait_for_tick()

            # Create randomly roaming peds
            self.npcs += SimulationUtils.spawn_pedestrians(self.world, self.sim, N_PEDESTRIANS)

            # Create static vehicle
            bp1 = self.world.get_blueprint_library().filter('vehicle.volkswagen.t2')[0]
            spawn1 = carla.Transform(carla.Location(x=-198.2, y=-50.9, z=1.5), carla.Rotation(yaw=-90))
            cmd1 = carla.command.SpawnActor(bp1, spawn1)

            responses = self.sim.apply_batch_sync([cmd1])
            spawned_ids = list(map(lambda r: r.actor_id, filter(lambda r: not r.has_error(), responses)))
            spawned_actors = list(self.world.get_actors(spawned_ids))
            self.npcs += spawned_actors

    def tick(self, clock) -> bool:
        clock.tick_busy_loop(60)
        self.world.tick()

        for ego in self.egos:
            if ego.tick(clock):
                return True

    def destroy(self):
        for e in self.egos:
            e.destroy()
        SimulationUtils.multi_destroy(self.world, self.sim, self.npcs)

def game_loop(args):
    killer = GracefulKiller()
    world = None

    try:
        client = carla.Client(args.host, args.port)
        client.set_timeout(2.0)
        world = World(client, args.scene)
        clock = pygame.time.Clock()

        while True:
            if killer.kill_now or world.tick(clock):
                return world.destroy()

    finally:
        if world is not None:
            return world.destroy()


def run(args=sys.argv[1:]):
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
        '--scene',
        default='scene1',
        help='Scene to run (located in ./scenes) (default: \'scene1\')')

    args = argparser.parse_args(args)

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

    logging.info('listening to server %s:%s', args.host, args.port)

    try:
        game_loop(args)
    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')


if __name__ == '__main__':
    run()
