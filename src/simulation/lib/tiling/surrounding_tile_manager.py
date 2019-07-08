from typing import Tuple, List, Set, Dict, Callable

import numpy as np
from lib import quadkey
from lib.geom import BBox3D, BBox2D
from lib.quadkey import TileSystem
from observation.observation import GnssObservation
from util import TransformUtils

OCCUPANCY_BBOX_HEIGHT = 3.5

class SurroundingTileManager:
    def __init__(self, level, radius):
        self.level = level
        self.radius = radius
        self.gnss_current: GnssObservation = None
        self.quadkey_current: quadkey.QuadKey = None
        # TODO: Prevent memory leak
        self.surrounding_tiles: Dict[str, Set[BBox3D]] = dict()
        self.convert: Callable = TransformUtils.get_tile2world_conversion(self.level)

    def update_gnss(self, obs: GnssObservation):
        key = obs.to_quadkey(self.level)
        self.gnss_current = obs

        if self.quadkey_current is None or key != self.quadkey_current:
            self.quadkey_current = key
            self._recompute(key)

    def get_surrounding(self) -> Set[BBox3D]:
        return self.surrounding_tiles[self.quadkey_current.key] if self.quadkey_current.key in self.surrounding_tiles else set()

    def _recompute(self, key=None):
        key = key if key is not None else self.quadkey_current
        if key.key in self.surrounding_tiles:
            return
        self.surrounding_tiles[key.key] = self._nearby_bboxes_world()

    def _nearby_bboxes_world(self) -> Set[BBox3D]:
        quadkeys: List[quadkey.QuadKey] = list(map(lambda k: quadkey.QuadKey(k), self.quadkey_current.nearby(self.radius)))
        return self._quadkeys_to_bboxes3d(quadkeys)

    def _quadkeys_to_bboxes3d(self, quadkeys) -> Set[BBox3D]:
        pixel_boxes: List[List[Tuple[float, float], Tuple[float, float], Tuple[float, float], Tuple[float, float]]]

        base_z = self.gnss_current.value[2]
        pixel_boxes = list(map(self._map_to_pixel_box, quadkeys))
        world_boxes = list(map(self._map_to_world, pixel_boxes))
        bboxes_2d = list(map(self._map_to_bbox, world_boxes))
        return set([b.to_3d(offset=base_z - OCCUPANCY_BBOX_HEIGHT, height=OCCUPANCY_BBOX_HEIGHT) for b in bboxes_2d])

    def _map_to_world(self, coords: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        return list(map(lambda c: self.convert(c), coords))

    @staticmethod
    def _map_to_pixel_box(qk: quadkey.QuadKey) -> List[Tuple[float, float]]:
        return [
            quadkey.from_geo(qk.to_geo(TileSystem.ANCHOR_NW), 31).to_pixel(TileSystem.ANCHOR_CENTER),
            quadkey.from_geo(qk.to_geo(TileSystem.ANCHOR_NE), 31).to_pixel(TileSystem.ANCHOR_CENTER),
            quadkey.from_geo(qk.to_geo(TileSystem.ANCHOR_SW), 31).to_pixel(TileSystem.ANCHOR_CENTER),
            quadkey.from_geo(qk.to_geo(TileSystem.ANCHOR_SE), 31).to_pixel(TileSystem.ANCHOR_CENTER)
        ]

    @staticmethod
    def _map_to_bbox(pixel_box: List[Tuple[float, float]]) -> BBox2D:
        return BBox2D.from_points(*[
            tuple(np.min(pixel_box, axis=0)),
            tuple(np.max(pixel_box, axis=0))
        ])
