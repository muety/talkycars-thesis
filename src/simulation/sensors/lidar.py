import weakref

import carla
from constants import OBS_LIDAR_POINTS
from observation import LidarObservation
from observation import ObservationManager
from sensors import Sensor


class LidarSensor(Sensor):
    def __init__(self, parent_actor, observation_manager: ObservationManager = None, range_m = 5):
        weak_self = weakref.ref(self)

        self.sensor = None
        self._parent = parent_actor
        self.recording = False
        super().__init__(observation_manager)

        world = self._parent.get_world()
        bp = world.get_blueprint_library().find('sensor.lidar.ray_cast')
        bp.set_attribute('range', str(int(range_m * 100)))

        self.sensor = world.spawn_actor(bp, carla.Transform(carla.Location(z=2.8), carla.Rotation(pitch=-15)), attach_to=self._parent)
        self.sensor.listen(lambda event: LidarSensor._on_image(weak_self, event))

    def toggle_recording(self):
        self.recording = not self.recording

    @staticmethod
    def _on_image(weak_self, image):
        self = weak_self()
        if not self:
            return

        points = map(image.transform.transform, image)
        points = list(map(lambda p: (p.x, p.y, p.z), points))

        obs = LidarObservation(image.timestamp, points)
        self.om.add(OBS_LIDAR_POINTS, obs)

        if self.recording:
            image.save_to_disk('_out/%08d' % image.frame_number)
