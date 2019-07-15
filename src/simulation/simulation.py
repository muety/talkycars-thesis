#!/usr/bin/env python

from __future__ import print_function

import argparse
import logging
from typing import List

import carla
import pygame
from ego import Ego
from strategy import ManualStrategy
from util import GracefulKiller

from client.client import TalkyClient, ClientDialect


class World(object):
    def __init__(self, client: carla.Client, scene_name: str):
        # Attributes
        self.sim = client
        self.world = client.get_world()
        self.client = TalkyClient(dialect=ClientDialect.CARLA)
        self.map = self.world.get_map()
        self.debug = True

        self.egos: List[Ego] = []
        self.npcs: List[carla.Agent] = []

        self.init()
        self.init_scene(scene_name)

        logging.info('enabling synchronous mode.')
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)

    def init(self):
        pass

    def init_scene(self, scene_name: str):
        if scene_name == 'scene1':
            main_hero = Ego(self.sim, strategy=ManualStrategy(), name='main_hero', render=True, debug=True)
            self.egos.append(main_hero)

    def tick(self, clock) -> bool:
        clock.tick_busy_loop(60)
        self.world.tick()

        for ego in self.egos:
            if ego.tick(clock):
                return True

    def destroy(self):
        for a in self.npcs:
            if a: a.destroy()

        for a in self.egos:
            if a: a.destroy()

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
            world.destroy()
            return

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
        '--scene',
        default='scene1',
        help='Scene to run (located in ./scenes) (default: \'scene1\')')

    args = argparser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

    logging.info('listening to server %s:%s', args.host, args.port)

    try:
        game_loop(args)
    except KeyboardInterrupt:
        print('\nCancelled by user. Bye!')


if __name__ == '__main__':
    main()
