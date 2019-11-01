import time
from collections import deque
from threading import Lock
from typing import Callable, Dict, List, Type

from common.observation import Observation


class ObservationManager:
    def __init__(self, keep=10):
        self.default_keep: int = keep
        self.observations: Dict[str, deque] = {}
        self.types: Dict[str, Type[Observation]] = {}
        self.last_update: Dict[str, float] = {}
        self.subscribers: Dict[str, List[Callable]] = {}
        self.locks: Dict[str, Lock] = {}
        self.aliases: Dict[str, str] = {}

    '''
    Optional method to explicitly initialize an observation queue for a specific key upfront.
    '''

    def register_key(self, key: str, obs_type: Type[Observation], keep: int = 10, ttl: float = float('inf')):
        assert isinstance(key, str)
        assert isinstance(obs_type, type)

        self.observations[key] = deque(maxlen=keep)
        self.types[key] = obs_type
        self.locks[key] = Lock()
        self.last_update[key] = float('inf')

    def unregister_key(self, key: str):
        self.observations.pop(key, None)
        del self.types[key]
        del self.locks[key]
        del self.last_update[key]

    def register_alias(self, key: str, alias: str):
        if key not in self.observations:
            raise KeyError('key not found')

        self.aliases[alias] = key

    def subscribe(self, key: str, callable: Callable):
        if key in self.aliases:
            key = self.aliases[key]

        if key not in self.subscribers:
            self.subscribers[key] = [callable]
        else:
            self.subscribers[key].append(callable)

    def add(self, key: str, observation: Observation):
        assert isinstance(key, str)
        assert isinstance(observation, Observation)

        if key in self.aliases:
            key = self.aliases[key]

        if key not in self.observations:
            self.register_key(key, observation.__class__, keep=self.default_keep)

        lock = self.locks[key]
        if lock.locked():
            return

        with lock:
            self.observations[key].append(observation)
            self.last_update[key] = observation.timestamp

            for f in self.subscribers[key]:
                f(observation)

    def has(self, key: str, max_age: float = float('inf')) -> bool:
        if key in self.aliases:
            key = self.aliases[key]

        return key in self.observations \
               and len(self.observations[key]) > 0 \
               and time.time() - self.last_update[key] <= max_age

    def get(self, key: str, index: int = -1, max_age: float = float('inf')):
        if key in self.aliases:
            key = self.aliases[key]

        if key not in self.observations \
                or len(self.observations[key]) == 0 \
                or time.time() - self.last_update[key] >= max_age:
            return None

        return self.observations[key][index]

    def latest(self, key: str, max_age: float = float('inf')) -> Observation:
        return self.get(key, -1, max_age)

    def tear_down(self):
        pass
