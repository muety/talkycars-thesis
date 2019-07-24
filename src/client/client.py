import logging
from enum import Enum
from typing import cast, List

from common.bridge import MqttBridge, MqttBridgeUtils
from common.constants import *
from common.observation import CameraRGBObservation
from common.observation import OccupancyGridObservation, LidarObservation, PositionObservation, \
    GnssObservation
from common.quadkey import QuadKey
from common.serialization.schema import Vector3D, RelativeBBox, GridCellState
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.ego_vehicle import PEMEgoVehicle
from common.serialization.schema.occupancy import PEMOccupancyGrid, PEMGridCell
from common.serialization.schema.relation import PEMRelation
from common.util import GeoUtils
from .inbound import InboundController
from .observation import ObservationManager
from .occupancy import OccupancyGridManager
from .outbound import OutboundController


class ClientDialect(Enum):
    CARLA = 0


class TalkyClient:
    def __init__(self,
                 for_subject_id: int,
                 dialect: ClientDialect = ClientDialect.CARLA,
                 grid_radius: int = OCCUPANCY_RADIUS_DEFAULT
                 ):
        self.dialect: ClientDialect = dialect
        self.om: ObservationManager = ObservationManager()
        self.gm: OccupancyGridManager = OccupancyGridManager(OCCUPANCY_TILE_LEVEL, grid_radius)
        self.inbound: InboundController = InboundController(self.om, self.gm)
        self.outbound: OutboundController = OutboundController(self.om, self.gm)
        self.mqtt: MqttBridge = MqttBridge()

        self.ego_id = str(for_subject_id)

        self.remote_grid_quadkey: QuadKey = None
        self.publish_topics: List[str] = []

        # Type registrations
        self.om.register_key(OBS_POSITION, PositionObservation)
        self.om.register_key(OBS_LIDAR_POINTS, LidarObservation)
        self.om.register_key(OBS_CAMERA_RGB_IMAGE, CameraRGBObservation)
        self.om.register_key(OBS_OCCUPANCY_GRID, OccupancyGridObservation)
        self.om.register_key(OBS_GNSS_PREFIX + self.ego_id, GnssObservation)
        self.om.register_key(OBS_DYNAMICS_PREFIX + self.ego_id, GnssObservation)
        self.om.register_key(OBS_PROPS_PREFIX + self.ego_id, GnssObservation)

        self.om.register_alias(OBS_GNSS_PREFIX + self.ego_id, OBS_GNSS_PREFIX + ALIAS_EGO)
        self.om.register_alias(OBS_DYNAMICS_PREFIX + self.ego_id, OBS_DYNAMICS_PREFIX + ALIAS_EGO)
        self.om.register_alias(OBS_PROPS_PREFIX + self.ego_id, OBS_PROPS_PREFIX + ALIAS_EGO)

        # Miscellaneous
        self.gm.offset_z = LIDAR_Z_OFFSET

        # Business logic
        self.outbound.subscribe(OBS_LIDAR_POINTS, self._on_lidar)
        self.outbound.subscribe(OBS_OCCUPANCY_GRID, self._on_grid)
        self.outbound.subscribe(OBS_GNSS_PREFIX + ALIAS_EGO, self._on_gnss)

        # Bridge initialization
        self.mqtt.listen(block=False)

    def _on_lidar(self, obs: LidarObservation):
        if self.om.has(OBS_GNSS_PREFIX + ALIAS_EGO):
            self.gm.update_gnss(cast(GnssObservation, self.om.latest(OBS_GNSS_PREFIX + ALIAS_EGO)))

        if self.om.has(OBS_POSITION):
            self.gm.set_position(cast(PositionObservation, self.om.latest(OBS_POSITION)))

        if not self.gm.match_with_lidar(cast(LidarObservation, obs)):
            return

        grid = self.gm.get_grid()
        if not grid:
            return

        obs = OccupancyGridObservation(obs.timestamp, grid)
        self.om.add(OBS_OCCUPANCY_GRID, obs)

    def _on_gnss(self, obs: GnssObservation):
        qk = obs.to_quadkey(level=REMOTE_GRID_TILE_LEVEL)
        self._update_topics(qk)

    def _on_grid(self, obs: OccupancyGridObservation):
        ts1, grid = obs.timestamp, obs.value
        ego_gnss_obs = self.om.latest(OBS_GNSS_PREFIX + ALIAS_EGO)
        ego_dynamics_obs = self.om.latest(OBS_DYNAMICS_PREFIX + ALIAS_EGO)
        ego_props_obs = self.om.latest(OBS_PROPS_PREFIX + ALIAS_EGO)

        if not grid or not ego_gnss_obs or not ego_dynamics_obs or not ego_props_obs:
            return

        # Generate PEM complex object attributes
        ts = int(min([ts1, ego_gnss_obs.timestamp, ego_dynamics_obs.timestamp]))
        bbox_corners = (
            GeoUtils.gnss_add_meters(ego_gnss_obs.value, ego_props_obs.value[1], delta_factor=-1),
            GeoUtils.gnss_add_meters(ego_gnss_obs.value, ego_props_obs.value[1])
        )
        bbox = RelativeBBox(lower=Vector3D(bbox_corners[0]), higher=Vector3D(bbox_corners[1]))

        pem_ego = PEMEgoVehicle(id=int(self.ego_id))
        pem_ego.position = PEMRelation(confidence=ego_gnss_obs.confidence, object=Vector3D(ego_gnss_obs.value))
        pem_ego.color = PEMRelation(confidence=ego_props_obs.confidence, object=str(ego_props_obs.value[0]))
        pem_ego.bounding_box = PEMRelation(confidence=ego_props_obs.confidence, object=bbox)
        pem_ego.velocity = PEMRelation(confidence=ego_dynamics_obs.confidence, object=Vector3D(ego_dynamics_obs.value[0]))
        pem_ego.acceleration = PEMRelation(confidence=ego_dynamics_obs.confidence, object=Vector3D(ego_dynamics_obs.value[1]))

        pem_grid = PEMOccupancyGrid()
        pem_grid.cells = [
            PEMGridCell(
                hash=cell.quad_key.key,
                state=PEMRelation(confidence=cell.confidence, object=GridCellState(cell.state)))
            for cell in grid.cells
        ]

        # Generate PEM graph
        graph = PEMTrafficScene(timestamp=ts,
                                measured_by=pem_ego,
                                occupancy_grid=pem_grid)

        encoded_msg = graph.to_bytes()
        logging.debug(f'Encoded state representation to {len(encoded_msg) / 1024} kBytes')

        for t in self.publish_topics:
            self.mqtt.publish(t, encoded_msg)

    def _on_remote_grid(self, msg: bytes):
        decoded_msg = PEMTrafficScene.from_bytes(msg)
        logging.debug(f'Decoded remote fused state representation from {len(msg) / 1024} kBytes')

    def _update_topics(self, qk: QuadKey):
        if self.mqtt.connected and qk and self.remote_grid_quadkey and qk == self.remote_grid_quadkey:
            return

        logging.debug(f'Subscription-relevant tile changed from {self.remote_grid_quadkey} to {qk}.')

        out_topics_old = MqttBridgeUtils.topics_fused_out(self.remote_grid_quadkey)
        out_topics_new = MqttBridgeUtils.topics_fused_out(qk)

        for t in out_topics_old:
            self.mqtt.unsubscribe(t, self._on_remote_grid)

        for t in out_topics_new:
            self.mqtt.subscribe(t, self._on_remote_grid)

        self.publish_topics = MqttBridgeUtils.topics_raw_in(qk)

        self.remote_grid_quadkey = qk
