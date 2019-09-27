import logging
import time

from util import simulation

import carla

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


# Check randomness of pedestrian spawn points

def main():
    try:
        client = carla.Client('localhost', 2000)
        client.set_timeout(2.0)
        world = client.get_world()

        peds = simulation.try_spawn_pedestrians(client, 10)

        time.sleep(1)

        for p in [peds[i] for i in range(0, len(peds), 2)]:
            logging.debug(f'{p.id} – {p.get_location()}')

        for i in range(500):
            world.wait_for_tick()

        simulation.multi_destroy(client, peds)
        world.wait_for_tick()

    except Exception as e:
        logging.error(e)


if __name__ == '__main__':
    main()
