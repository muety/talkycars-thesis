import logging
import time

from util import SimulationUtils, WaypointProvider

import carla

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


# NPC tests

def main():
    try:
        client = carla.Client('localhost', 2000)
        client.set_timeout(2.0)
        world = client.get_world()

        wpp = WaypointProvider(world.get_map().get_spawn_points(), seed=20)
        agents = SimulationUtils.spawn_npcs(client, wpp, n=10)

        time.sleep(1)

        for a in agents:
            logging.debug(f'{a.vehicle.id} – {a.vehicle.get_location()}')

        for i in range(500):
            world.wait_for_tick()

            for a in agents:
                a.run_and_apply()

        SimulationUtils.multi_destroy(client, [a.vehicle for a in agents])
        world.wait_for_tick()

    except Exception as e:
        logging.error(e)


if __name__ == '__main__':
    main()
