from typing import Callable, Tuple, Iterable

import numpy as np


class Point:
    def components(self) -> Tuple:
        raise NotImplementedError('subclasses must override components()!')

class Point2D(Point):
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def components(self) -> Tuple[float, float]:
        return self.x, self.y

class Point3D(Point):
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def components(self) -> Tuple[float, float, float]:
        return self.x, self.y, self.z

# https://stackoverflow.com/a/29720938

class BBox3D(object):
    def __init__(self, xrange, yrange, zrange):
        self.xrange = xrange  # (xmin, xmax)
        self.yrange = yrange
        self.zrange = zrange

    def contains(self, p: Point3D):
        if not all(hasattr(p, loc) for loc in 'xyz'):
            raise TypeError("Can only check if 3D points are in the rect")
        return all([self.xrange[0] <= p.x <= self.xrange[1],
                    self.yrange[0] <= p.y <= self.yrange[1],
                    self.zrange[0] <= p.z <= self.zrange[1]])

    def contains_point(self, p: Iterable[float]):
        return all([self.xrange[0] <= p[0] <= self.xrange[1],
                    self.yrange[0] <= p[1] <= self.yrange[1],
                    self.zrange[0] <= p[2] <= self.zrange[1]])

    def to_points(self):
        return tuple(zip(self.xrange, self.yrange, self.zrange))

    def to_vertices(self):
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

    def convert(self, convert: Callable):
        # TODO: Implement!
        pass

    def __str__(self):
        return str(sorted(list(zip(self.xrange, self.yrange, self.zrange))))

    def __repr__(self):
        return self.__str__()

    def __hash__(self):
        return hash(hash(self.xrange[0]) + hash(self.xrange[1]) + hash(self.yrange[0]) + hash(self.yrange[1]) + hash(self.zrange[0]) + hash(self.zrange[1]))

    def __eq__(self, other):
        return self.__hash__() == other.__hash__()

    @classmethod
    def from_points(cls, firstcorner, secondcorner):
        return cls(*zip(firstcorner, secondcorner))