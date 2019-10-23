# http://code.activestate.com/recipes/577346-getattr-with-arbitrary-depth/#c1
from itertools import chain


def multi_getattr(obj, attr, **kw):
    attributes = attr.split(".")
    for i in attributes:
        try:
            obj = getattr(obj, i)
            if callable(obj):
                obj = obj()
        except AttributeError:
            if kw.has_key('default'):
                return kw['default']
            else:
                raise
    return obj


def flatmap(f, items):
    return chain.from_iterable(map(f, items))
