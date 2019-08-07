from enum import Enum
from typing import cast, List, Dict

from client.observation import ObservationManager, LinearObservationTracker
from client.subscription import TileSubscriptionService
from client.utils import ClientUtils
from common.constants import *
from common.model import DynamicActor
from common.observation import CameraRGBObservation, ActorsObservation
from common.observation import OccupancyGridObservation, LidarObservation, PositionObservation, \
    GnssObservation
from common.quadkey import QuadKey
from common.serialization.schema import GridCellState
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMOccupancyGrid, PEMGridCell
from common.serialization.schema.relation import PEMRelation
from .inbound import InboundController
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
        self.tss: TileSubscriptionService = TileSubscriptionService(self._on_remote_grid, rate_limit=.1)
        self.tracker: LinearObservationTracker = LinearObservationTracker(n=6)

        self.ego_id = str(for_subject_id)

        self.remote_grid_quadkey: QuadKey = None

        # Type registrations
        self.om.register_key(OBS_POSITION, PositionObservation)
        self.om.register_key(OBS_LIDAR_POINTS, LidarObservation)
        self.om.register_key(OBS_CAMERA_RGB_IMAGE, CameraRGBObservation)
        self.om.register_key(OBS_OCCUPANCY_GRID, OccupancyGridObservation)
        self.om.register_key(OBS_ACTOR_EGO, ActorsObservation)
        self.om.register_key(OBS_ACTORS_RAW, ActorsObservation)
        self.om.register_key(OBS_GNSS_PREFIX + self.ego_id, GnssObservation)

        self.om.register_alias(OBS_GNSS_PREFIX + self.ego_id, OBS_GNSS_PREFIX + ALIAS_EGO)

        # Miscellaneous
        self.gm.offset_z = LIDAR_Z_OFFSET

        # Business logic
        self.outbound.subscribe(OBS_LIDAR_POINTS, self._on_lidar)
        self.outbound.subscribe(OBS_OCCUPANCY_GRID, self._on_grid)
        self.outbound.subscribe(OBS_GNSS_PREFIX + ALIAS_EGO, self._on_gnss)

    def _on_lidar(self, obs: LidarObservation):
        if self.om.has(OBS_GNSS_PREFIX + ALIAS_EGO):
            self.gm.update_gnss(cast(GnssObservation, self.om.latest(OBS_GNSS_PREFIX + ALIAS_EGO)))

        if self.om.has(OBS_ACTOR_EGO):
            ego: DynamicActor = cast(ActorsObservation, self.om.latest(OBS_ACTOR_EGO)).value[0]
            self.gm.set_position(ego.location.value)

        # This is what takes most time
        if not self.gm.match_with_lidar(cast(LidarObservation, obs)):
            return

        grid = self.gm.get_grid()
        if not grid:
            return

        obs = OccupancyGridObservation(obs.timestamp, grid)
        self.om.add(OBS_OCCUPANCY_GRID, obs)

    def _on_gnss(self, obs: GnssObservation):
        qk = obs.to_quadkey(level=REMOTE_GRID_TILE_LEVEL)
        self.tss.update_position(qk)

    def _on_grid(self, obs: OccupancyGridObservation):
        ts1, grid = obs.timestamp, obs.value
        actors_ego_obs = self.om.latest(OBS_ACTOR_EGO)
        actors_others_obs = self.om.latest(OBS_ACTORS_RAW)

        if not grid or not actors_ego_obs or not actors_others_obs or not actors_ego_obs.value or len(actors_ego_obs.value) < 1:
            return

        ego_actor: DynamicActor = actors_ego_obs.value[0]
        visible_actors: Dict[str, List[DynamicActor]] = ClientUtils.match_actors_with_grid(grid, actors_others_obs.value)

        # Generate PEM complex object attributes
        ts = int(min([ts1, actors_ego_obs.timestamp, actors_others_obs.timestamp]))

        pem_ego = ClientUtils.map_pem_actor(ego_actor)

        pem_grid = PEMOccupancyGrid(cells=[])

        for cell in grid.cells:
            pem_cell = PEMGridCell(
                hash=cell.quad_key.key,
                state=PEMRelation(
                    confidence=cell.state.confidence,
                    object=GridCellState(cell.state.value))
            )

            group_key = f'cell_occupant_{cell.quad_key.key}'

            if len(visible_actors[cell.quad_key.key]) > 0:
                # TODO: Fix! This branch is called way too seldomly!!!
                # Assuming that a cell is tiny enough to contain at max one actor
                actor = visible_actors[cell.quad_key.key][0]

                self.tracker.track(group_key, str(actor.id))

                pem_cell.occupant = PEMRelation(
                    confidence=self.tracker.get(group_key, str(actor.id)),
                    object=ClientUtils.map_pem_actor(actor)
                )

            self.tracker.cycle_group(group_key)

            pem_grid.cells.append(pem_cell)

        # Generate PEM graph
        graph = PEMTrafficScene(timestamp=ts,
                                measured_by=pem_ego,
                                occupancy_grid=pem_grid)

        encoded_msg = graph.to_bytes()
        # logging.debug(f'Encoded state representation to {len(encoded_msg) / 1024} kBytes')

        contained_tiles = frozenset(map(lambda c: c.quad_key.key, grid.cells))
        self.tss.publish_graph(encoded_msg, contained_tiles)

    def _on_remote_grid(self, msg: bytes):
        # TODO: Maybe do asynchronously?
        decoded_msg = PEMTrafficScene.from_bytes(msg)
        # logging.debug(f'Decoded remote fused state representation from {len(msg) / 1024} kBytes')