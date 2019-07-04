from lib.quadkey import TileSystem
from tile_factory import TileFactory

if __name__ == '__main__':
    qk = TileFactory.gnss_to_quadkey((49.010852, 8.396301), 16)
    print(qk.key)
    print(qk.nearby(2))
    print(len(qk.nearby(2)))
    print('---')
    print(qk.to_geo(TileSystem.ANCHOR_NW))
    print(qk.to_geo(TileSystem.ANCHOR_NE))
    print(qk.to_geo(TileSystem.ANCHOR_SW))
    print(qk.to_geo(TileSystem.ANCHOR_SE))