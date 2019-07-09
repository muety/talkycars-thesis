from lib import quadkey
from lib.occupancy.grid_manager import OccupancyGridManager
from observation import GnssObservation

if __name__ == '__main__':
    obs1 = GnssObservation(0.0, (49.010852, 8.396301, 12.3))
    obs2 = GnssObservation(0.0, (49.013590, 8.396387, 12.3))

    m = OccupancyGridManager(24, 1)

    m.update_gnss(obs1)
    print(list(m.get_grid())[0])
    print(list(m.get_grid())[1])
    print(list(m.get_grid())[2])
    print(list(m.get_grid())[3])

    m.update_gnss(obs2)
    print(list(m.get_grid())[0])
    print(list(m.get_grid())[1])
    print(list(m.get_grid())[2])
    print(list(m.get_grid())[3])

    qk1 = quadkey.from_geo((49.010852, 8.396301), 10)
    qk2 = quadkey.from_str(qk1.key + (13 * '0'))
    print(qk1.to_pixel())
    print(qk2.to_pixel())

    # 1202032333
    # 12020323312222222222222
    # 12020323330000000000000