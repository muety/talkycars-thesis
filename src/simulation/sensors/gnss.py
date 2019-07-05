import weakref

import carla
from constants import OBS_GNSS_PLAYER_POS
from observation.observation import GnssObservation
from observation.observation_manager import ObservationManager
from sensors.sensor import Sensor


class GnssSensor(Sensor):
    def __init__(self, parent_actor, observation_manager: ObservationManager = None):
        weak_self = weakref.ref(self)

        self.sensor = None
        self._parent = parent_actor
        self.lat = 0.0
        self.lon = 0.0
        super().__init__(observation_manager)

        observation_manager.register_key(OBS_GNSS_PLAYER_POS, GnssObservation)
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
        self.om.add(OBS_GNSS_PLAYER_POS, obs)
