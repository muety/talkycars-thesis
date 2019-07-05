from collections import deque
from threading import Lock
from typing import Callable

from observation.observation import Observation


class ObservationManager:
    def __init__(self):
        self.observations = {}
        self.key_types = {}
        self.subscribers = {}
        self.lock = Lock()

    def register_key(self, key, obs_type, keep=10):
        assert isinstance(key, str)
        assert isinstance(obs_type, type)

        self.observations[key] = deque(maxlen=keep)
        self.key_types[key] = obs_type

    def subscribe(self, key, callable: Callable):
        if not key in self.subscribers:
            self.subscribers[key] = [callable]
        else:
            self.subscribers[key].append(callable)

    def unregister_key(self, key):
        self.observations.pop(key, None)

    def add(self, key, observation):
        assert isinstance(key, str)
        assert isinstance(observation, Observation)

        if self.lock.locked():
            return

        self.lock.acquire()

        self.observations[key].append(observation)

        if not key in self.subscribers:
            self.lock.release()
            return

        for f in self.subscribers[key]:
            f(observation)

        self.lock.release()

    def latest(self, key):
        return self.observations[key][-1]