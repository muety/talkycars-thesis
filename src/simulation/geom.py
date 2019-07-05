# https://stackoverflow.com/a/29720938

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

    def __str__(self):
        return str(list(zip(self.xrange, self.yrange, self.zrange)))

    @classmethod
    def from_points(cls, firstcorner, secondcorner):
        return cls(*zip(firstcorner, secondcorner))

class Point3D(object):
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
