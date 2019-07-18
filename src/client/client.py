from enum import Enum

from common.constants import *
from common.observation import CameraRGBObservation, PositionObservation, GnssObservation, LidarObservation, \
    OccupancyGridObservation
from .inbound import InboundController
from .observation import ObservationManager
from .occupancy import OccupancyGridManager
from .outbound import OutboundController


class ClientDialect(Enum):
    CARLA = 0

class TalkyClient:
    def __init__(self,
                 dialect: ClientDialect = ClientDialect.CARLA,
                 grid_radius: int = OCCUPANCY_RADIUS_DEFAULT
                 ):
        self.dialect: ClientDialect = dialect
        self.om: ObservationManager = ObservationManager()
        self.gm: OccupancyGridManager = OccupancyGridManager(OCCUPANCY_TILE_LEVEL, grid_radius)
        self.inbound: InboundController = InboundController(self.om, self.gm)
        self.outbound: OutboundController = OutboundController(self.om, self.gm)

        # Type registrations
        self.om.register_key(OBS_POSITION_PLAYER_POS, PositionObservation)
        self.om.register_key(OBS_GNSS_PLAYER_POS, GnssObservation)
        self.om.register_key(OBS_LIDAR_POINTS, LidarObservation)
        self.om.register_key(OBS_CAMERA_RGB_IMAGE, CameraRGBObservation)
        self.om.register_key(OBS_OCCUPANCY_GRID, OccupancyGridObservation)

        # Miscallaneaous
        self.gm.offset_z = LIDAR_Z_OFFSET