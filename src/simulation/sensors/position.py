import carla
from client.client import TalkyClient
from common.constants import *
from common.observation import PositionObservation, ActorDynamicsObservation
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
        player_location: carla.Location = self._parent.get_location()
        player_velocity: carla.Vector3D = self._parent.get_velocity()
        player_acceleration: carla.Vector3D = self._parent.get_acceleration()
        obs_pos = PositionObservation(event.ts, (player_location.x, player_location.y, player_location.z))
        obs_dyn = ActorDynamicsObservation(event.ts,
            velocity=(player_velocity.x, player_velocity.y, player_velocity.z),
            acceleration=(player_acceleration.x, player_acceleration.y, player_acceleration.z)
        )

        self.client.inbound.publish(OBS_POSITION, obs_pos)
        self.client.inbound.publish(OBS_DYNAMICS_PREFIX + ALIAS_EGO, obs_dyn)