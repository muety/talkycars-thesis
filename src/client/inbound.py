import logging
from typing import cast

from common.constants import *
from common.observation import Observation, OccupancyGridObservation, LidarObservation, PositionObservation, \
    GnssObservation
from common.serialization.schema import Vector3D, RelativeBBox, GridCellState
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.ego_vehicle import PEMEgoVehicle
from common.serialization.schema.occupancy import PEMOccupancyGrid, PEMGridCell
from common.serialization.schema.relation import PEMRelation
from common.util import GeoUtils
from .observation import ObservationManager
from .occupancy import OccupancyGridManager


class InboundController:
    def __init__(self, om: ObservationManager, gm: OccupancyGridManager, subject_id: int):
        self.om = om
        self.gm = gm
        self.subject_id = subject_id

        self.om.subscribe(OBS_LIDAR_POINTS, self._on_lidar)
        self.om.subscribe(OBS_OCCUPANCY_GRID, self._on_grid)

    def publish(self, key: str, obs: Observation):
        self.om.add(key, obs)

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

    def _on_grid(self, obs: OccupancyGridObservation):
        ts1, grid = obs.timestamp, obs.value
        ego_gnss_obs = self.om.latest(OBS_GNSS_PREFIX + ALIAS_EGO)
        ego_dynamics_obs = self.om.latest(OBS_DYNAMICS_PREFIX + ALIAS_EGO)
        ego_props_obs = self.om.latest(OBS_PROPS_PREFIX + ALIAS_EGO)

        if not grid or not ego_gnss_obs or not ego_dynamics_obs or not ego_props_obs:
            return

        # Generate PEM complex object attributes
        ts = int(min([ts1, ego_gnss_obs.timestamp, ego_dynamics_obs.timestamp, ego_props_obs.timestamp]))
        bbox_corners = (
            GeoUtils.gnss_add_meters(ego_gnss_obs.value, ego_props_obs.value[1], delta_factor=-1),
            GeoUtils.gnss_add_meters(ego_gnss_obs.value, ego_props_obs.value[1])
        )
        bbox = RelativeBBox(lower=Vector3D(bbox_corners[0]), higher=Vector3D(bbox_corners[1]))

        pem_ego = PEMEgoVehicle(id=self.subject_id)
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
