import math

cdef class Ray3D:
    cdef public float origin[3]
    cdef public float direction[3]
    cdef public float invdir[3]
    cdef public int sign[3]

    def __cinit__(self, object origin, object direction):
        self.origin = origin
        self.direction = direction
        self.invdir = [1 / d if d > 0 else math.inf for d in direction[:3]]
        self.sign = [v < 0 for v in self.invdir[:3]]

def aabb_intersect(object bounds, object ray):
    cdef float tmin, tmax, tymin, tymax, tzmin, tzmax

    tmin = (bounds[ray.sign[0]][0] - ray.origin[0]) * ray.invdir[0]
    tmax = (bounds[1 - ray.sign[0]][0] - ray.origin[0]) * ray.invdir[0]
    tymin = (bounds[ray.sign[1]][1] - ray.origin[1]) * ray.invdir[1]
    tymax = (bounds[1 - ray.sign[1]][1] - ray.origin[1]) * ray.invdir[1]

    if tmin > tymax or tymin > tmax:
        return False

    tmin = max([tmin, tymin])
    tmax = min([tmax, tymax])

    tzmin = (bounds[ray.sign[2]][2] - ray.origin[2]) * ray.invdir[2]
    tzmax = (bounds[1 - ray.sign[2]][2] - ray.origin[2]) * ray.invdir[2]

    if tmin > tzmax or tzmin > tmax:
        return False

    return True

def aabb_contains(object bounds, object point):
    return all([
        bounds[0][0] <= point[0] <= bounds[1][0],
        bounds[0][1] <= point[1] <= bounds[1][1],
        bounds[0][2] <= point[2] <= bounds[1][2]
    ])