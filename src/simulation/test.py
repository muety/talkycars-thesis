from lib import quadkey
from lib.quadkey import TileSystem
from lib.tiling.surrounding_tile_manager import SurroundingTileManager
from observation.observation import GnssObservation

if __name__ == '__main__':
    obs1 = GnssObservation(0.0, (49.010852, 8.396301, 12.3))
    obs2 = GnssObservation(0.0, (49.013590, 8.396387, 12.3))

    m = SurroundingTileManager(24, 1)

    m.update_gnss(obs1)
    print(list(m.get_surrounding())[0])
    print(list(m.get_surrounding())[1])
    print(list(m.get_surrounding())[2])
    print(list(m.get_surrounding())[3])

    m.update_gnss(obs2)
    print(list(m.get_surrounding())[0])
    print(list(m.get_surrounding())[1])
    print(list(m.get_surrounding())[2])
    print(list(m.get_surrounding())[3])