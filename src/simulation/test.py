from lib import quadkey
from observation.observation import GnssObservation

if __name__ == '__main__':
    qk = quadkey.from_geo((49.010852, 8.396301), 16)
    n1 = quadkey.from_str(qk.nearby(1)[0])

    print(n1.to_geo(quadkey.TileSystem.ANCHOR_NW))
    print(n1.to_geo(quadkey.TileSystem.ANCHOR_NE))
    print(n1.to_geo(quadkey.TileSystem.ANCHOR_SW))
    print(n1.to_geo(quadkey.TileSystem.ANCHOR_SE))

    obs = GnssObservation(0.0, (49.010852, 8.396301, 12.3))
    print(len(obs.nearby_bboxes_world(radius=1)))
    print(obs.nearby_bboxes_world(radius=1)[0])
    print(obs.nearby_bboxes_world(radius=1)[1])
    print(obs.nearby_bboxes_world(radius=1)[2])
    print(obs.nearby_bboxes_world(radius=1)[3])