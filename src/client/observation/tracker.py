from collections import deque
from typing import Dict, Set


class ObservationTracker:
    def __init__(self, n: int):
        self.n: int = n
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
        return sum(dq) / max(len(dq), 1)

    def cycle_group(self, group: str):
        for key in self.groups[group].keys():
            if key not in self.updated_keys[group]:
                self.groups[group][key].append(False)
        self.updated_keys[group].clear()
