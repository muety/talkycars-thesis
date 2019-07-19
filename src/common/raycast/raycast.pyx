cimport numpy as np

cdef class Ray3D:
    cdef public float origin[3]
    cdef public float direction[3]

    def __cinit__(self, object origin, object direction):
        self.origin = origin
        self.direction = direction

# https://gamedev.stackexchange.com/a/103714
def aabb_intersect(list bounds, Ray3D ray):
    cdef float t[9]
    cdef float vmin[3], vmax[3]

    vmin = bounds[0]
    vmax = bounds[1]

    t[1] = (vmin[0] - ray.origin[0])/ray.direction[0]
    t[2] = (vmax[0] - ray.origin[0])/ray.direction[0]
    t[3] = (vmin[1] - ray.origin[1])/ray.direction[1]
    t[4] = (vmax[1] - ray.origin[1])/ray.direction[1]
    t[5] = (vmin[2] - ray.origin[2])/ray.direction[2]
    t[6] = (vmax[2] - ray.origin[2])/ray.direction[2]
    t[7] = max(max(min(t[1], t[2]), min(t[3], t[4])), min(t[5], t[6]))
    t[8] = min(min(max(t[1], t[2]), max(t[3], t[4])), max(t[5], t[6]))
    return not (t[8] < 0 or t[7] > t[8])

def aabb_contains(list bounds, np.ndarray point):
    return all([
        bounds[0][0] <= point[0] <= bounds[1][0],
        bounds[0][1] <= point[1] <= bounds[1][1],
        bounds[0][2] <= point[2] <= bounds[1][2]
    ])