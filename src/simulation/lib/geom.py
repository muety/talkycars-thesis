from typing import Callable

import numpy as np


# https://stackoverflow.com/a/29720938

# TODO: Use inheritance for less duplicated code

class BBox2D(object):
    def __init__(self, xrange, yrange):
        self.xrange = xrange  # (xmin, xmax)
        self.yrange = yrange

    def contains_point(self, p):
        if not all(hasattr(p, loc) for loc in 'xy'):
            raise TypeError("Can only check if 3D points are in the rect")
        return all([self.xrange[0] <= p.x <= self.xrange[1],
                    self.yrange[0] <= p.y <= self.yrange[1]])

    def __str__(self):
        return str(list(zip(self.xrange, self.yrange)))

    def __hash__(self):
        return hash(str(self))

    def to_3d(self, offset=0, height=3):
        p1, p2 = self.to_points()
        p1 += (offset,)
        p2 += (height,)
        return BBox3D.from_points(p1, p2)

    def to_points(self):
        return tuple(zip(self.xrange, self.yrange))

    def to_coords(self):
        rect_low, rect_high = self.to_points()
        cords = np.zeros((8, 4))
        cords[0, :] = np.array([rect_high[0], rect_high[1], 1])
        cords[1, :] = np.array([rect_low[0], rect_high[1], 1])
        cords[2, :] = np.array([rect_low[0], rect_low[1], 1])
        cords[3, :] = np.array([rect_high[0], rect_low[1], 1])
        return cords

    def convert(self, convert: Callable):
        # TODO: Implement!
        pass

    @classmethod
    def from_points(cls, firstcorner, secondcorner):
        return cls(*zip(firstcorner, secondcorner))

class BBox3D(object):
    def __init__(self, xrange, yrange, zrange):
        self.xrange = xrange  # (xmin, xmax)
        self.yrange = yrange
        self.zrange = zrange

    def contains_point(self, p):
        if not all(hasattr(p, loc) for loc in 'xyz'):
            raise TypeError("Can only check if 3D points are in the rect")
        return all([self.xrange[0] <= p.x <= self.xrange[1],
                    self.yrange[0] <= p.y <= self.yrange[1],
                    self.zrange[0] <= p.z <= self.zrange[1]])

    def to_points(self):
        return tuple(zip(self.xrange, self.yrange, self.zrange))

    def to_coords(self):
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

class Point3D(object):
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
