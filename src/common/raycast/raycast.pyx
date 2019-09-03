#!python
#cython: boundscheck=False
#cython: wraparound=False
#cython: nonecheck=False
#cython: cdivision=True

cimport numpy as np
import numpy

cdef class Ray3D:
    cdef public const np.float32_t[:] origin
    cdef public const np.float32_t[:] direction

    def __cinit__(self, const np.float32_t[:] origin, const np.float32_t[:] direction):
        self.origin = origin
        self.direction = direction

# https://gamedev.stackexchange.com/a/103714
cpdef bint aabb_intersect(const np.float32_t[:,:] bounds, Ray3D ray):
    cdef np.float32_t[:] t = numpy.zeros((9,)).astype(numpy.float32)
    cdef const np.float32_t[:] vmin, vmax

    vmin = bounds[0]
    vmax = bounds[1]

    t[1] = (vmin[0] - ray.origin[0]) / ray.direction[0]
    t[2] = (vmax[0] - ray.origin[0]) / ray.direction[0]
    t[3] = (vmin[1] - ray.origin[1]) / ray.direction[1]
    t[4] = (vmax[1] - ray.origin[1]) / ray.direction[1]
    t[5] = (vmin[2] - ray.origin[2]) / ray.direction[2]
    t[6] = (vmax[2] - ray.origin[2]) / ray.direction[2]
    t[7] = max(max(min(t[1], t[2]), min(t[3], t[4])), min(t[5], t[6]))
    t[8] = min(min(max(t[1], t[2]), max(t[3], t[4])), max(t[5], t[6]))
    return not (t[8] < 0 or t[7] > t[8])

cpdef bint aabb_contains(const np.float32_t[:,:] bounds, const np.float32_t[:] point):
    return all([
        bounds[0][0] <= point[0] <= bounds[1][0],
        bounds[0][1] <= point[1] <= bounds[1][1],
        bounds[0][2] <= point[2] <= bounds[1][2]
    ])
