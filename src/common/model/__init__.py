from abc import ABC, abstractmethod
from typing import TypeVar, Generic, cast

T = TypeVar('T')


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Noisifiable(ABC):
    @abstractmethod
    def with_gaussian_noise(self, mu: float, sigma: float) -> 'Noisifiable':
        pass


class UncertainProperty(Generic[T]):
    def __init__(self, confidence: float = None, value: T = None):
        self.confidence: float = confidence
        self.value: T = value

    def with_uncertainty(self) -> 'UncertainProperty':
        conf = self.confidence - abs(random.gauss(0, .1))
        return UncertainProperty(conf, self.value)

    def with_gaussian_noise(self, mu: float = 0, sigma: float = .1) -> 'UncertainProperty':
        e: NotImplementedError = NotImplementedError('value does not support noise simulation')

        if isinstance(self.value, Noisifiable):
            return UncertainProperty(self.confidence, self.value.with_gaussian_noise(mu, sigma))
        elif isinstance(self.value, list):
            if not all([isinstance(v, Noisifiable) for v in self.value]): raise e
            return UncertainProperty(self.confidence, [cast(Noisifiable, v).with_gaussian_noise(mu, sigma) for v in self.value])
        elif isinstance(self.value, tuple):
            if not all([isinstance(v, Noisifiable) for v in self.value]): raise e
            return UncertainProperty(self.confidence, tuple([cast(Noisifiable, v).with_gaussian_noise(mu, sigma) for v in self.value]))
        raise e


from .actor import *
from .geom import *
