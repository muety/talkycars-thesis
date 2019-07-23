import numpy as np
import pygame

from common.occupancy import GridCellState

BB_COLOR = (24, 64, 248)
BB_COLOR_OCCUPIED = (248, 64, 24)
BB_COLOR_FREE = (24, 248, 64)


class BBoxUtils(object):
    @staticmethod
    def draw_bounding_boxes(display, bounding_boxes, states):
        """
        Draws bounding boxes on pygame display.
        """

        info = pygame.display.Info()

        bb_surface = pygame.Surface((info.current_w, info.current_h))
        bb_surface.set_colorkey((0, 0, 0))
        for k, bbox in enumerate(bounding_boxes):
            if states[k] is GridCellState.FREE:
                color = BB_COLOR_FREE
            elif states[k] is GridCellState.OCCUPIED:
                color = BB_COLOR_OCCUPIED
            else:
                color = BB_COLOR

            points = [(int(bbox[i, 0]), int(bbox[i, 1])) for i in range(8)]
            # draw lines
            # base
            pygame.draw.line(bb_surface, color, points[0], points[1])
            pygame.draw.line(bb_surface, color, points[0], points[1])
            pygame.draw.line(bb_surface, color, points[1], points[2])
            pygame.draw.line(bb_surface, color, points[2], points[3])
            pygame.draw.line(bb_surface, color, points[3], points[0])
            # top
            pygame.draw.line(bb_surface, color, points[4], points[5])
            pygame.draw.line(bb_surface, color, points[5], points[6])
            pygame.draw.line(bb_surface, color, points[6], points[7])
            pygame.draw.line(bb_surface, color, points[7], points[4])
            # base-top
            pygame.draw.line(bb_surface, color, points[0], points[4])
            pygame.draw.line(bb_surface, color, points[1], points[5])
            pygame.draw.line(bb_surface, color, points[2], points[6])
            pygame.draw.line(bb_surface, color, points[3], points[7])
        display.blit(bb_surface, (0, 0))

    @classmethod
    def to_camera(cls, cords, sensor, camera):
        return cls._get_camera_bbox(cls._world_to_sensor(cords, sensor), camera)

    @staticmethod
    def get_matrix(transform):
        """
        Creates matrix from carla transform.
        """

        rotation = transform.rotation
        location = transform.location
        c_y = np.cos(np.radians(rotation.yaw))
        s_y = np.sin(np.radians(rotation.yaw))
        c_r = np.cos(np.radians(rotation.roll))
        s_r = np.sin(np.radians(rotation.roll))
        c_p = np.cos(np.radians(rotation.pitch))
        s_p = np.sin(np.radians(rotation.pitch))
        matrix = np.matrix(np.identity(4))
        matrix[0, 3] = location.x
        matrix[1, 3] = location.y
        matrix[2, 3] = location.z
        matrix[0, 0] = c_p * c_y
        matrix[0, 1] = c_y * s_p * s_r - s_y * c_r
        matrix[0, 2] = -c_y * s_p * c_r - s_y * s_r
        matrix[1, 0] = s_y * c_p
        matrix[1, 1] = s_y * s_p * s_r + c_y * c_r
        matrix[1, 2] = -s_y * s_p * c_r + c_y * s_r
        matrix[2, 0] = s_p
        matrix[2, 1] = -c_p * s_r
        matrix[2, 2] = c_p * c_r
        return matrix

    @staticmethod
    def _get_camera_bbox(cords, camera):
        cords_y_minus_z_x = np.concatenate([cords[1, :], -cords[2, :], cords[0, :]])
        bbox = np.transpose(np.dot(camera.calibration, cords_y_minus_z_x))
        camera_bbox = np.concatenate([bbox[:, 0] / bbox[:, 2], bbox[:, 1] / bbox[:, 2], bbox[:, 2]], axis=1)
        return camera_bbox

    @staticmethod
    def _world_to_sensor(cords, sensor):
        """
        Transforms world coordinates to sensor.
        """
        sensor_world_matrix = BBoxUtils.get_matrix(sensor.get_transform())
        world_sensor_matrix = np.linalg.inv(sensor_world_matrix)
        sensor_cords = np.dot(world_sensor_matrix, cords)
        return sensor_cords

    @staticmethod
    def _sensor_to_world(cords, sensor):
        """
        Transforms world coordinates to sensor.
        """
        sensor_world_matrix = BBoxUtils.get_matrix(sensor.get_transform())
        world_cords = np.dot(sensor_world_matrix, cords.T)
        return world_cords
