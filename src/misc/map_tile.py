import logging
import time
from operator import attrgetter
from os.path import commonprefix

import carla
from common import quadkey
from common.constants import *

MAP = 'Town01'

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


def main():
    try:
        _client = carla.Client('localhost', 2000)
        _client.set_timeout(2.0)
        _world = _client.load_world(MAP)
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

        logging.info(f'Outer-most tiles for {MAP}\n------')
        logging.info(f'NW @ {OCCUPANCY_TILE_LEVEL}: {qk_nw.key}')
        logging.info(f'SE @ {OCCUPANCY_TILE_LEVEL}: {qk_se.key}')
        logging.info(f'Containing Tile @ {parent.level}: {parent.key}')


    except Exception as e:
        logging.error(e)


if __name__ == '__main__':
    main()
