from datetime import datetime
from typing import Tuple, List, Callable

import numpy as np
from geom import BBox3D
from lib import quadkey
from lib.quadkey.tile_system import TileSystem
from util import TileUtils


class Observation:
    def __init__(self, local_timestamp):
        assert isinstance(local_timestamp, int) or isinstance(local_timestamp, float)

        self.local_timestamp = local_timestamp
        # Caution: Uses local platform time!
        self.timestamp = datetime.now().timestamp()

class GnssObservation(Observation):
    def __init__(self, timestamp, coords: Tuple[float, float, float]):
        assert isinstance(coords, tuple)

        super().__init__(timestamp)
        self.value = coords

    def to_quadkey(self, level=20) -> quadkey.QuadKey:
        return quadkey.from_geo(self.value[:2], level)

    def to_tile(self, level=20):
        return self.to_quadkey(level).to_tile()

    def nearby_tiles(self, radius=10, level=25) -> List[quadkey.QuadKey]:
        qk = self.to_quadkey(level)
        return qk.nearby(radius)

    def nearby_bboxes_world(self, radius=10, level=24, height=3) -> List[BBox3D]:
        quadkeys: List[quadkey.QuadKey]
        pixel_boxes: List[List[Tuple[float, float], Tuple[float, float], Tuple[float, float], Tuple[float, float]]]
        convert: Callable = TileUtils.get_tile2world_conversion(level)

        assert convert is not None

        def map_to_pixel_box(qk: quadkey.QuadKey) -> List[Tuple[float, float]]:
            return [
                qk.to_pixel(TileSystem.ANCHOR_NW),
                qk.to_pixel(TileSystem.ANCHOR_NE),
                qk.to_pixel(TileSystem.ANCHOR_SW),
                qk.to_pixel(TileSystem.ANCHOR_SE)
            ]

        def map_to_bbox(pixel_box: List[Tuple[float, float]]) -> BBox3D:
            return BBox3D.from_points(*[
                tuple(np.min(pixel_box, axis=0)) + (0,),
                tuple(np.max(pixel_box, axis=0)) + (height,)
            ])

        def map_to_world(bbox: BBox3D) -> BBox3D:
            zipped = tuple(zip(bbox.xrange, bbox.yrange, bbox.zrange))
            c1 = zipped[0]
            c2 = zipped[1]
            return BBox3D.from_points(convert(c1), convert(c2))

        quadkeys = list(map(lambda k: quadkey.QuadKey(k), self.nearby_tiles(radius, level)))
        pixel_boxes = list(map(map_to_pixel_box, quadkeys))
        pixel_bboxes = list(map(map_to_bbox, pixel_boxes))
        return list(map(map_to_world, pixel_bboxes))

    def __str__(self):
        return f'[{self.timestamp}] GPS Position: {self.value}'

class LidarObservation(Observation):
    def __init__(self, timestamp, points: np.ndarray):
        assert isinstance(points, np.ndarray)

        super().__init__(timestamp)
        self.value = points

    def __str__(self):
        return f'[{self.timestamp}] Point Cloud: {self.value.shape}'

class PositionObservation(Observation):
    def __init__(self, timestamp, coords: Tuple[float, float, float]):
        assert isinstance(coords, tuple)

        super().__init__(timestamp)
        self.value = coords

    def __str__(self):
        return f'[{self.timestamp}] World Position: {self.value}'

class CameraRGBObservation(Observation):
    def __init__(self, timestamp, image: np.ndarray):
        assert isinstance(image, np.ndarray)

        super().__init__(timestamp)
        self.value = image

    def __str__(self):
        return f'[{self.timestamp}] RGB Image: {self.value.shape}'