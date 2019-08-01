from collections import deque
from threading import Lock, Thread
from typing import Callable

from common.observation import Observation


class ObservationManager:
    def __init__(self, keep=10):
        self.default_keep = keep
        self.observations = {}
        self.key_types = {}
        self.subscribers = {}
        self.locks = {}
        self.aliases = {}

    '''
    Optional method to explicitly initialize an observation queue for a specific key upfront.
    '''

    def register_key(self, key, obs_type, keep=10):
        assert isinstance(key, str)
        assert isinstance(obs_type, type)

        self.observations[key] = deque(maxlen=keep)
        self.key_types[key] = obs_type
        self.locks[key] = Lock()

    def unregister_key(self, key):
        self.observations.pop(key, None)

    def register_alias(self, key: str, alias: str):
        if key not in self.observations:
            raise KeyError('key not found')

        self.aliases[alias] = key

    def subscribe(self, key, callable: Callable):
        if key in self.aliases:
            key = self.aliases[key]

        if key not in self.subscribers:
            self.subscribers[key] = [callable]
        else:
            self.subscribers[key].append(callable)

    def add(self, key, observation: Observation):
        assert isinstance(key, str)
        assert isinstance(observation, Observation)

        if key in self.aliases:
            key = self.aliases[key]

        if key not in self.observations:
            self.register_key(key, observation.__class__, keep=self.default_keep)

        lock = self.locks[key]
        if lock.locked():
            return

        lock.acquire()

        self.observations[key].append(observation)

        threads = []
        if key in self.subscribers:
            for f in self.subscribers[key]:
                t = Thread(target=f, args=(observation,))
                t.start()
                threads.append(t)

        for t in threads:
            t.join()

        lock.release()

    def has(self, key) -> bool:
        if key in self.aliases:
            key = self.aliases[key]

        return key in self.observations and len(self.observations[key]) > 0

    def latest(self, key) -> Observation:
        if key in self.aliases:
            key = self.aliases[key]

        if key not in self.observations or len(self.observations[key]) == 0:
            return None
        return self.observations[key][-1]
