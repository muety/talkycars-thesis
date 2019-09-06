import carla
from client.client import TalkyClient
from common.constants import *
from common.observation import PositionObservation
from . import Sensor


class PositionEvent(carla.SensorData):
    def __init__(self, timestamp):
        self.ts = timestamp


class PositionSensor(Sensor):
    def __init__(self, parent_actor, client: TalkyClient):
        self._parent = parent_actor
        self._map = parent_actor.get_world().get_map()
        super().__init__(client)

    def tick(self, timestamp):
        self._on_event(PositionEvent(timestamp))

    def _on_event(self, event):
        location: carla.Location = self._parent.get_location()
        self.client.inbound.publish(OBS_POSITION, PositionObservation(event.ts, coords=(location.x, location.y, location.z)))
