import numpy as np

from common.geom import BBox3D, Ray3D

if __name__ == '__main__':
    box = BBox3D.from_points((0,0,0), (10,10,10))
    r = Ray3D(np.array([12,12,12]), np.array([-1, -1, -1]))
    box.intersects(r)