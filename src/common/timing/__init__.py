import logging
import time
from collections import deque
from threading import Thread
from typing import Dict, Deque

from common.model import Singleton


class TimingService(metaclass=Singleton):
    def __init__(self, max_keep: int = 10000):
        self.active: bool = True
        self.max_keep: int = max_keep
        self.start_timestamps: Dict[str, Deque[float]] = {}
        self.stop_timestamps: Dict[str, Deque[float]] = {}
        self.call_count: Dict[str, float] = {}
        self.start_times: Dict[str, float] = {}
        self.logging_thread: Thread = Thread(target=self._info_loop, daemon=True)

        self.logging_thread.start()

    def start(self, key: str, custom_time: float = None):
        assert (key not in self.start_timestamps or key not in self.stop_timestamps) or (len(self.start_timestamps[key]) == len(self.stop_timestamps[key]))

        if key not in self.start_timestamps:
            self.start_timestamps[key] = deque(maxlen=self.max_keep)
        if key not in self.stop_timestamps:
            self.stop_timestamps[key] = deque(maxlen=self.max_keep)
        if key not in self.call_count:
            self.call_count[key] = 0
        if key not in self.start_times:
            self.start_times[key] = time.time()

        if len(self.start_timestamps[key]) == self.max_keep:
            self.stop_timestamps[key].popleft()
        self.start_timestamps[key].append(time.time() if not custom_time else custom_time)

    def stop(self, key: str, custom_time: float = None):
        assert key in self.stop_timestamps

        self.stop_timestamps[key].append(time.time() if not custom_time else custom_time)
        self.call_count[key] += 1

    def tear_down(self):
        self.active = False

    def get_mean(self, key: str) -> float:
        assert key in self.start_timestamps and key in self.stop_timestamps
        return sum(map(lambda t: t[0] - t[1], zip(self.stop_timestamps[key], self.start_timestamps[key]))) / len(self.stop_timestamps[key])

    def get_call_rate(self, key: str) -> float:
        assert key in self.call_count and key in self.start_times
        return round(self.call_count[key] / (time.time() - self.start_times[key]), 2)

    def info(self):
        txt: str = '\n-------\nTIMINGS\n'
        for key in sorted(list(self.start_timestamps.keys())):
            txt += f'[{key}]: {self.get_mean(key) * 1000} ms (Rate: {self.get_call_rate(key)} / sec)\n'
        txt += '-------'
        logging.info(txt)

    def _info_loop(self):
        while self.active:
            time.sleep(5.0)
            self.info()
