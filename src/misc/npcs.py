import logging
import time

from util import simulation

import carla
from common.constants import CARLA_CONNECT_TIMEOUT
from common.util.waypoint import WaypointProvider

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


# NPC tests

def main():
    try:
        client = carla.Client('localhost', 2000)
        client.set_timeout(CARLA_CONNECT_TIMEOUT)
        world = client.get_world()

        wpp = WaypointProvider(world.get_map().get_spawn_points(), seed=20)
        agents = simulation.try_spawn_npcs(client, wpp, n=10)

        time.sleep(1)

        for a in agents:
            logging.debug(f'{a.vehicle.id} – {a.vehicle.get_location()}')

        for i in range(500):
            world.wait_for_tick()

            for a in agents:
                a.run_and_apply()

        simulation.multi_destroy(client, [a.vehicle for a in agents])
        world.wait_for_tick()

    except Exception as e:
        logging.error(e)


if __name__ == '__main__':
    main()
