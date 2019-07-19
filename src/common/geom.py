from typing import Tuple, Iterable

import numpy as np


class Point:
    def components(self) -> Tuple:
        raise NotImplementedError('subclasses must override components()!')

class Point2D(Point):
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

    def components(self) -> Tuple[float, float]:
        return self.x, self.y

class Point3D(Point):
    def __init__(self, x: float, y: float, z: float):
        self.x = x
        self.y = y
        self.z = z

    def __str__(self):
        return f'{self.x}, {self.y}, {self.z}'

    def __repr__(self):
        return self.__str__()

    def components(self) -> Tuple[float, float, float]:
        return self.x, self.y, self.z

class Ray3D:
    def __init__(self, origin: Tuple[float, float, float], direction: Tuple[float, float, float]):
        self.origin = origin
        self.direction = direction

# https://stackoverflow.com/a/29720938

class BBox3D:
    def __init__(self, xrange: Tuple[float, float], yrange: Tuple[float, float], zrange: Tuple[float, float], precomputed_bounds: Iterable[Tuple[float, float, float]]=None):
        self.xrange = xrange  # (xmin, xmax)
        self.yrange = yrange
        self.zrange = zrange
        self.bounds = list(precomputed_bounds if precomputed_bounds is not None else self.to_points())

    def contains(self, p: Point3D) -> bool:
        if not all(hasattr(p, loc) for loc in 'xyz'):
            raise TypeError("Can only check if 3D points are in the rect")
        return all([self.xrange[0] <= p.x <= self.xrange[1],
                    self.yrange[0] <= p.y <= self.yrange[1],
                    self.zrange[0] <= p.z <= self.zrange[1]])

    def intersects(self, ray: Ray3D) -> bool:
        # https://gamedev.stackexchange.com/a/103714
        vmin = self.bounds[0]
        vmax = self.bounds[1]
        t = np.zeros((9,))

        t[1] = (vmin[0] - ray.origin[0]) / ray.direction[0]
        t[2] = (vmax[0] - ray.origin[0]) / ray.direction[0]
        t[3] = (vmin[1] - ray.origin[1]) / ray.direction[1]
        t[4] = (vmax[1] - ray.origin[1]) / ray.direction[1]
        t[5] = (vmin[2] - ray.origin[2]) / ray.direction[2]
        t[6] = (vmax[2] - ray.origin[2]) / ray.direction[2]
        t[7] = max(max(min(t[1], t[2]), min(t[3], t[4])), min(t[5], t[6]))
        t[8] = min(min(max(t[1], t[2]), max(t[3], t[4])), max(t[5], t[6]))
        return not (t[8] < 0 or t[7] > t[8])

    def to_points(self) -> Iterable[Tuple[float, float, float]]:
        return tuple(zip(self.xrange, self.yrange, self.zrange))

    def to_vertices(self) -> np.ndarray:
        rect_low, rect_high = self.to_points()
        cords = np.zeros((8, 4))
        cords[0, :] = np.array([rect_high[0], rect_high[1], rect_low[2], 1])
        cords[1, :] = np.array([rect_low[0], rect_high[1], rect_low[2], 1])
        cords[2, :] = np.array([rect_low[0], rect_low[1], rect_low[2], 1])
        cords[3, :] = np.array([rect_high[0], rect_low[1], rect_low[2], 1])
        cords[4, :] = np.array([rect_high[0], rect_high[1], rect_high[2], 1])
        cords[5, :] = np.array([rect_low[0], rect_high[1], rect_high[2], 1])
        cords[6, :] = np.array([rect_low[0], rect_low[1], rect_high[2], 1])
        cords[7, :] = np.array([rect_high[0], rect_low[1], rect_high[2], 1])
        return cords

    def __str__(self):
        return str(sorted(list(zip(self.xrange, self.yrange, self.zrange))))

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash(hash(self.xrange[0]) + hash(self.xrange[1]) + hash(self.yrange[0]) + hash(self.yrange[1]) + hash(self.zrange[0]) + hash(self.zrange[1]))

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    @classmethod
    def from_points(cls, firstcorner: Tuple[float, float, float], secondcorner: Tuple[float, float, float]):
        return cls(*zip(firstcorner, secondcorner), precomputed_bounds=[firstcorner, secondcorner])
