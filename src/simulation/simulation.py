#!/usr/bin/env python

from __future__ import print_function

import argparse
import sys

import pygame
from ego import Ego
from scenes import SceneFactory, AbstractScene
from strategy import *
from util import simulation

import carla
from common.constants import FRAMERATE
from common.util import GracefulKiller, proc_wrap


class World(object):
    def __init__(self, client: carla.Client, scene_name: str):
        # Attributes
        self.sim: carla.Client = client
        self.debug: bool = True
        self.n_ticks: int = 0

        self.scene: AbstractScene = None
        self.egos: List[Ego] = []
        self.npcs: List[carla.Agent] = []
        self.agents: List[Agent] = []

        self.world: carla.World = None
        self.map: carla.Map = None

        self.init()
        self.init_scene(scene_name)

        logging.info('Enabling synchronous mode.')

    def init(self):
        pass

    def init_scene(self, scene_name: str):
        logging.info(f'Attempting to load scene: {scene_name}.')
        self.scene = SceneFactory.get(scene_name, self.sim)
        self.scene.init()
        self.scene.create_and_spawn()
        self.world, self.egos, self.npcs, self.agents = self.scene.world, self.scene.egos, self.scene.npcs, self.scene.agents
        self.world.apply_settings(simulation.get_world_settings())

    def tick(self, clock) -> bool:
        clock.tick(FRAMERATE)
        proc_wrap(self.world.tick)
        if proc_wrap(self.scene.tick, clock):
            return True

        if self.debug and self.n_ticks % (FRAMERATE * 3) == 0:  # every 3 seconds
            logging.debug(f'FPS: {clock.get_fps()}')

        self.n_ticks += 1

    def destroy(self):
        for e in self.egos:
            e.destroy()

        simulation.multi_destroy(self.sim, self.npcs)
        simulation.multi_destroy(self.sim, [a.vehicle for a in self.agents])

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
