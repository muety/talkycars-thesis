# python3 setup.py build_ext --inplace

from distutils.core import setup

from Cython.Build import cythonize

setup(
    ext_modules = cythonize("raycast.pyx")
)