import weakref

import carla
import numpy as np
from constants import OBS_LIDAR_POINTS
from observation.lidar import LidarObservation
from observation.observation_manager import ObservationManager
from sensors.sensor import Sensor


class LidarSensor(Sensor):
    def __init__(self, parent_actor, observation_manager: ObservationManager = None):
        weak_self = weakref.ref(self)

        self.sensor = None
        self._parent = parent_actor
        self.recording = False
        super().__init__(observation_manager)

        observation_manager.register_key(OBS_LIDAR_POINTS, carla.LidarMeasurement)
        world = self._parent.get_world()
        bp = world.get_blueprint_library().find('sensor.lidar.ray_cast')
        bp.set_attribute('range', '5000')

        self.sensor = world.spawn_actor(bp, carla.Transform(carla.Location(x=-5.5, z=2.8), carla.Rotation(pitch=-15)), attach_to=self._parent)
        self.sensor.listen(lambda event: LidarSensor._on_image(weak_self, event))

    def toggle_recording(self):
        self.recording = not self.recording

    @staticmethod
    def _on_image(weak_self, image):
        self = weak_self()
        if not self:
            return
        points = np.frombuffer(image.raw_data, dtype=np.dtype('f4'))
        points = np.reshape(points, (int(points.shape[0] / 3), 3))

        obs = LidarObservation(image.timestamp, points)
        self.om.add(OBS_LIDAR_POINTS, obs)

        if self.recording:
            image.save_to_disk('_out/%08d' % image.frame_number)
