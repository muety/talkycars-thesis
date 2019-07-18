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
        super().__init__(client)

    def tick(self, timestamp):
        self._on_event(PositionEvent(timestamp))

    def _on_event(self, event):
        player_location = self._parent.get_location()
        obs = PositionObservation(event.ts, (player_location.x, player_location.y, player_location.z))
        self.client.inbound.publish(OBS_POSITION_PLAYER_POS, obs)