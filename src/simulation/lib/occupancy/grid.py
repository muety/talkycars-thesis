from enum import Enum
from typing import Callable, List, Tuple, Set

import numpy as np
from lib import quadkey
from lib.geom import BBox3D, Point3D, Point2D
from lib.quadkey import QuadKey


class GridCellState(Enum):
    FREE = 0
    OCCUPIED = 1
    UNKNOWN = 2

class GridCell(BBox3D):
    def __init__(self, quad_key: QuadKey, convert: Callable, offset: float = 0, height: float = 3):
        self.quad_key: QuadKey = quad_key
        self.convert: Callable = convert
        self.offset: float = offset
        self.height: float = height
        self.state: GridCellState = GridCellState.UNKNOWN

        pixel_corners: List[Point2D] = self._quadkey_to_box(quad_key)
        world_corners: List[Point2D] = list(map(self._map_to_world, pixel_corners))
        self.corners: Tuple[Point3D, Point3D] = self._map_to_bbox_corners(world_corners)

        super().__init__(*zip(self.corners[0].components(), self.corners[1].components()))

    def _map_to_world(self, corner: Point2D) -> Point2D:
        return Point2D(*(self.convert(corner.components())))

    def _map_to_bbox_corners(self, corners: List[Point2D]) -> Tuple[Point3D, Point3D]:
        c1 = np.min(list(map(lambda c: c.components(), corners)), axis=0)
        c2 = np.max(list(map(lambda c: c.components(), corners)), axis=0)
        return Point3D(*c1, self.offset), Point3D(*c2, self.offset + self.height)

    @staticmethod
    def _quadkey_to_box(qk: QuadKey) -> List[Point2D]:
        return [
            Point2D(*(quadkey.from_geo(qk.to_geo(quadkey.TileSystem.ANCHOR_NW), 31).to_pixel(quadkey.TileSystem.ANCHOR_CENTER))),
            Point2D(*(quadkey.from_geo(qk.to_geo(quadkey.TileSystem.ANCHOR_NE), 31).to_pixel(quadkey.TileSystem.ANCHOR_CENTER))),
            Point2D(*(quadkey.from_geo(qk.to_geo(quadkey.TileSystem.ANCHOR_SW), 31).to_pixel(quadkey.TileSystem.ANCHOR_CENTER))),
            Point2D(*(quadkey.from_geo(qk.to_geo(quadkey.TileSystem.ANCHOR_SE), 31).to_pixel(quadkey.TileSystem.ANCHOR_CENTER)))
        ]

    def __str__(self):
        return f'Grid Cell @ {self.quad_key}'

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        return self.quad_key == other.quad_key

    def __hash__(self):
        return hash(self.__str__())


class Grid:
    def __init__(self, cells=set()):
        self.cells = cells

    def add(self, cell: GridCell):
        self.cells.add(cell)

    def to_quadkeys(self) -> Set[QuadKey]:
        return set(map(lambda c: c.quad_key, self.cells))

    def to_quadkeys_str(self) -> Set[str]:
        return set(map(lambda c: c.quad_key.key, self.cells))