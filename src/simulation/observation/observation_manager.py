from collections import deque
from threading import Thread
from typing import Callable

from observation import Observation


class ObservationManager:
    def __init__(self):
        self.observations = {}
        self.key_types = {}
        self.subscribers = {}

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

        self.observations[key].append(observation)

        if key in self.subscribers:
            for f in self.subscribers[key]:
                t = Thread(target=lambda o: f(o), args=(observation,))
                t.start()

    def latest(self, key):
        if not key in self.observations or len(self.observations[key]) == 0:
            return None
        return self.observations[key][-1]
