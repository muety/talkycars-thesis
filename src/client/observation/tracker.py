from collections import deque
from typing import Dict, Set

from common.model import Singleton


class LinearObservationTracker(metaclass=Singleton):
    def __init__(self, n: int = 10, offset: float = .05):
        self.n: int = n
        self.offset: float = offset
        self.groups: Dict[str, Dict[str, deque]] = dict()
        self.updated_keys: Dict[str, Set[str]] = dict()

    def track(self, group: str, key: str):
        if group not in self.groups:
            self.groups[group] = dict()
            self.updated_keys[group] = set()
        if key not in self.groups[group]:
            self.groups[group][key] = deque([False] * self.n, maxlen=self.n)

        self.groups[group][key].append(True)
        self.updated_keys[group].add(key)

    def get(self, group: str, key: str) -> float:
        if group not in self.groups or key not in self.groups[group]:
            return 0
        dq = self.groups[group][key]
        return max(0, sum(dq) / max(len(dq), 1) - self.offset)

    def cycle_group(self, group: str):
        if group not in self.groups:
            return

        for key in self.groups[group].keys():
            if key not in self.updated_keys[group]:
                self.groups[group][key].append(False)
        self.updated_keys[group].clear()
