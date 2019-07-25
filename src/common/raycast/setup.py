# python3 setup.py build_ext --inplace

from distutils.core import setup
from distutils.extension import Extension

import numpy
from Cython.Build import cythonize

setup(
    name='raycast',
    ext_modules=cythonize(
        Extension(
            'raycast',
            sources=['raycast.pyx'],
            include_dirs=[numpy.get_include()]
        )
    )
)
