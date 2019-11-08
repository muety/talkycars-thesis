import logging
import time
from operator import attrgetter
from os.path import commonprefix

from pyquadkey2 import quadkey

import carla
from common.constants import *

MAPS = ['Town01', 'Town02', 'Town03', 'Town04', 'Town05', 'Town07']

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


def main():
    try:
        _client = carla.Client('localhost', 2000)
        _client.set_timeout(CARLA_CONNECT_TIMEOUT)

        for m in MAPS:
            _world = _client.load_world(m)
            _map = _world.get_map()

            time.sleep(1)

            spawn_points = list(map(attrgetter('location'), _map.get_spawn_points()))

            point_nw = min(spawn_points, key=lambda p: abs(p.x + p.y))
            point_se = max(spawn_points, key=lambda p: abs(p.x + p.y))

            coord_nw = _map.transform_to_geolocation(point_nw)
            coord_se = _map.transform_to_geolocation(point_se)

            qk_nw = quadkey.from_geo((coord_nw.latitude, coord_nw.longitude), OCCUPANCY_TILE_LEVEL)
            qk_se = quadkey.from_geo((coord_se.latitude, coord_se.longitude), OCCUPANCY_TILE_LEVEL)
            parent = quadkey.from_str(commonprefix([qk_nw.key, qk_se.key]))

            logging.info(f'{m}\n------')
            logging.info(f'NW @ {OCCUPANCY_TILE_LEVEL}: {qk_nw.key}')
            logging.info(f'SE @ {OCCUPANCY_TILE_LEVEL}: {qk_se.key}')
            logging.info(f'Containing Tile @ {parent.level}: {parent.key}\n')


    except Exception as e:
        logging.error(e)


if __name__ == '__main__':
    main()

'''
INFO: Town01
------
INFO: NW @ 24: 120203233231202021013003
INFO: SE @ 24: 120203233231202303013220
INFO: Containing Tile @ 15: 120203233231202

INFO: Town02
------
INFO: NW @ 24: 120203233231202023011320
INFO: SE @ 24: 120203233231202211232330
INFO: Containing Tile @ 15: 120203233231202

INFO: Town03
------
INFO: NW @ 24: 120203233231202020321033
INFO: SE @ 24: 120203233231202033112332
INFO: Containing Tile @ 16: 1202032332312020

INFO: Town04
------
INFO: NW @ 24: 120203233231202011011032
INFO: SE @ 24: 120203233231202103322003
INFO: Containing Tile @ 15: 120203233231202

INFO: Town05
------
INFO: NW @ 24: 120203233231202022003332
INFO: SE @ 24: 120203233230313112321213
INFO: Containing Tile @ 11: 12020323323

INFO: Town07
------
INFO: NW @ 24: 120203233231202021010333
INFO: SE @ 24: 120203233230311333300220
INFO: Containing Tile @ 11: 12020323323
'''
