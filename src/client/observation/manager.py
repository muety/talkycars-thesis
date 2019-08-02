from collections import deque
from multiprocessing.dummy import Pool
from multiprocessing.pool import AsyncResult
from threading import Lock
from typing import Callable, Dict, List, Type

from common.observation import Observation


class ObservationManager:
    def __init__(self, keep=10):
        self.default_keep: int = keep
        self.observations: Dict[str, deque] = {}
        self.key_types: Dict[str, Type[Observation]] = {}
        self.subscribers: Dict[str, List[Callable]] = {}
        self.locks: Dict[str, Lock] = {}
        self.aliases: Dict[str, str] = {}
        self.pool: Pool = Pool(processes=4)

    '''
    Optional method to explicitly initialize an observation queue for a specific key upfront.
    '''

    def register_key(self, key: str, obs_type: Type[Observation], keep=10):
        assert isinstance(key, str)
        assert isinstance(obs_type, type)

        self.observations[key] = deque(maxlen=keep)
        self.key_types[key] = obs_type
        self.locks[key] = Lock()

    def unregister_key(self, key: str):
        self.observations.pop(key, None)

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
            async_results: List[AsyncResult] = []
            self.observations[key].append(observation)

            if key in self.subscribers:
                for f in self.subscribers[key]:
                    async_results.append(self.pool.apply_async(f, (observation,)))

            for r in async_results:
                r.wait()

    def has(self, key: str) -> bool:
        if key in self.aliases:
            key = self.aliases[key]

        return key in self.observations and len(self.observations[key]) > 0

    def latest(self, key: str) -> Observation:
        if key in self.aliases:
            key = self.aliases[key]

        if key not in self.observations or len(self.observations[key]) == 0:
            return None
        return self.observations[key][-1]
