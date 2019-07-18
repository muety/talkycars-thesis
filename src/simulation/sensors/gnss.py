import weakref

import carla
from client.client import TalkyClient
from common.constants import OBS_GNSS_PLAYER_POS
from common.observation import GnssObservation
from . import Sensor


class GnssSensor(Sensor):
    def __init__(self, parent_actor, client: TalkyClient):
        weak_self = weakref.ref(self)

        self.sensor = None
        self._parent = parent_actor
        self.lat = 0.0
        self.lon = 0.0
        super().__init__(client)

        world = self._parent.get_world()
        bp = world.get_blueprint_library().find('sensor.other.gnss')

        self.sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=1.0, z=2.8)), attach_to=self._parent)
        self.sensor.listen(lambda event: GnssSensor._on_gnss_event(weak_self, event))

    @staticmethod
    def _on_gnss_event(weak_self, event):
        self = weak_self()
        if not self:
            return
        self.lat = event.latitude
        self.lon = event.longitude

        obs = GnssObservation(event.timestamp, (event.latitude, event.longitude, event.altitude))
        self.client.inbound.publish(OBS_GNSS_PLAYER_POS, obs)