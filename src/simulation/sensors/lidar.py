import weakref

import carla
from constants import OBS_LIDAR_POINTS
from observation import LidarObservation
from observation import ObservationManager
from sensors import Sensor


class LidarSensor(Sensor):
    def __init__(self, parent_actor, observation_manager: ObservationManager = None, offset_z = 2.8, range = 5, angle = 15):
        weak_self = weakref.ref(self)
        print(angle)
        self.sensor = None
        self._parent = parent_actor
        self.recording = False
        self.offset_z = offset_z
        super().__init__(observation_manager)
        world = self._parent.get_world()
        bp = world.get_blueprint_library().find('sensor.lidar.ray_cast')
        bp.set_attribute('range', str(int(range * 100)))
        bp.set_attribute('upper_fov', '10')
        bp.set_attribute('lower_fov', str(int(-angle)))
        bp.set_attribute('sensor_tick', '0.1')

        self.sensor = world.spawn_actor(bp, carla.Transform(carla.Location(z=self.offset_z), carla.Rotation()), attach_to=self._parent)
        self.sensor.listen(lambda event: LidarSensor._on_image(weak_self, event))

    def toggle_recording(self):
        self.recording = not self.recording

    @staticmethod
    def _on_image(weak_self, image):
        self = weak_self()
        if not self:
            return

        # Dirty hack and idk why it's needed, but it works
        t = carla.Transform(
            image.transform.location,
            carla.Rotation(roll=image.transform.rotation.roll, pitch=image.transform.rotation.pitch, yaw=image.transform.rotation.yaw + 90)
        )

        # TODO: Make sure transformations are actually correct
        points = map(t.transform, image)
        points = map(lambda p: (p.x, p.y, p.z - self.offset_z), points)
        points = list(filter(lambda p: p[2] >= 0, points))

        obs = LidarObservation(image.timestamp, points)
        self.om.add(OBS_LIDAR_POINTS, obs)

        if self.recording:
            image.save_to_disk('_out/%08d' % image.frame_number)
