class Rectangle(object):
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

    # BONUS!
    @classmethod
    def from_points(cls, firstcorner, secondcorner):
        """Builds a rectangle from the bounding points

        Rectangle.from_points(Point(0, 10, -10),
                              Point(10, 20, 0)) == \
                Rectangle((0, 10), (10, 20), (-10, 0))

        This also works with sets of tuples, e.g.:
        corners = [(0, 10, -10), (10, 20, 0)]
        Rectangle.from_points(*corners) == \
                Rectangle((0, 10), (10, 20), (-10, 0))
        """
        return cls(*zip(firstcorner, secondcorner))

class Point(object):
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

if __name__ == '__main__':
    rect = Rectangle.from_points(*[(2,2,1), (4,4,2)])
    p = Point(3,3,.99)
    print(rect.contains_point(p))