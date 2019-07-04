import weakref

import carla
import numpy as np


class LidarSensor(object):
    def __init__(self, parent_actor):
        self.sensor = None
        self._parent = parent_actor
        self.recording = False

        world = self._parent.get_world()
        weak_self = weakref.ref(self)

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

        # TODO
        location = self._parent.get_location()
        np_location = np.array([[location.x, location.y, location.z]])
        closest = points[(points - np_location).sum(axis=1).argmin()]

        if self.recording:
            image.save_to_disk('_out/%08d' % image.frame_number)
