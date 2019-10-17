import logging
import time
from collections import deque
from datetime import datetime
from enum import Enum
from threading import Thread
from typing import cast, Dict, Optional, Deque

import numpy as np

from client.observation import ObservationManager, LinearObservationTracker
from client.observation.sink import CsvTrafficSceneSink, ObservationSink
from client.subscription import TileSubscriptionService
from client.utils import map_pem_actor, get_occupied_cells_multi
from common.constants import *
from common.model import DynamicActor
from common.observation import CameraRGBObservation, ActorsObservation, EmptyObservation
from common.observation import OccupancyGridObservation, LidarObservation, PositionObservation, \
    GnssObservation
from common.quadkey import QuadKey
from common.serialization.schema import GridCellState
from common.serialization.schema.actor import PEMDynamicActor
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
        self.sink: ObservationSink = None
        self.alive: bool = True
        self.recording: bool = False
        self.ego_id = str(for_subject_id)

        self.remote_grid_quadkey: QuadKey = None

        self.recording_thread: Thread = Thread(target=self._record, daemon=True)
        self.recording_thread.start()

        # Type registrations
        self.om.register_key(OBS_POSITION, PositionObservation)
        self.om.register_key(OBS_LIDAR_POINTS, LidarObservation)
        self.om.register_key(OBS_CAMERA_RGB_IMAGE, CameraRGBObservation)
        self.om.register_key(OBS_GRID_LOCAL, OccupancyGridObservation)
        self.om.register_key(OBS_GRID_COMBINED, OccupancyGridObservation)
        self.om.register_key(OBS_GRAPH_LOCAL, EmptyObservation)
        self.om.register_key(OBS_ACTOR_EGO, ActorsObservation)
        self.om.register_key(OBS_ACTORS_RAW, ActorsObservation)
        self.om.register_key(OBS_GNSS_PREFIX + self.ego_id, GnssObservation)

        self.om.register_alias(OBS_GNSS_PREFIX + self.ego_id, OBS_GNSS_PREFIX + ALIAS_EGO)

        # Miscellaneous
        self.gm.offset_z = LIDAR_Z_OFFSET

        # Business logic
        self.outbound.subscribe(OBS_GNSS_PREFIX + ALIAS_EGO, self._on_gnss)
        self.outbound.subscribe(OBS_LIDAR_POINTS, self._on_lidar)
        self.outbound.subscribe(OBS_GRID_LOCAL, self._on_grid)

        # Debugging stuff
        self.last_publish: float = time.monotonic()
        self.tsdiffhistory1: Deque[float] = deque(maxlen=100)
        self.tsdiffhistory2: Deque[float] = deque(maxlen=100)
        self.tsdiffhistory3: Deque[float] = deque(maxlen=100)

    def tear_down(self):
        self.alive = False
        self.recording = False
        self.tss.tear_down()
        self.om.tear_down()
        self.gm.tear_down()

    def toggle_recording(self):
        if not self.recording:
            self.sink = CsvTrafficSceneSink(
                keys=[OBS_GRID_COMBINED, OBS_ACTOR_EGO],
                outpath=os.path.join(
                    os.path.normpath(
                        os.path.join(
                            os.path.dirname(__file__),
                            '../../'
                        )
                    ),
                    datetime.now()
                        .strftime(RECORDING_FILE_TPL)
                        .replace('<id>', self.ego_id)
                )
            )
        self.recording = not self.recording

    def _on_lidar(self, obs: LidarObservation):
        _ts = time.monotonic()

        if self.om.has(OBS_GNSS_PREFIX + ALIAS_EGO):
            self.gm.update_gnss(cast(GnssObservation, self.om.latest(OBS_GNSS_PREFIX + ALIAS_EGO)))

        if self.om.has(OBS_ACTOR_EGO):
            ego: DynamicActor = cast(ActorsObservation, self.om.latest(OBS_ACTOR_EGO)).value[0]
            self.gm.update_ego(ego)

        if not self.gm.match_with_lidar(cast(LidarObservation, obs)):
            return

        grid = self.gm.get_grid()
        if not grid:
            return

        obs = OccupancyGridObservation(obs.timestamp, grid)
        self.inbound.publish(OBS_GRID_LOCAL, obs)

        self.tsdiffhistory1.append(time.monotonic() - _ts)
        logging.debug(f'LIDAR: {np.mean(self.tsdiffhistory1)}')

    def _on_gnss(self, obs: GnssObservation):
        qk: QuadKey = obs.to_quadkey(level=REMOTE_GRID_TILE_LEVEL)
        if qk != self.tss.current_position:
            self.tss.update_position(qk)

    def _on_grid(self, obs: OccupancyGridObservation):
        _ts = time.monotonic()

        ts1, grid = obs.timestamp, obs.value
        # TODO: Solve properly. Cell state (computed in gm) lags behind ego position by 1
        actors_ego_obs = self.om.latest(OBS_ACTOR_EGO)
        actors_others_obs = self.om.latest(OBS_ACTORS_RAW)

        if not grid or not actors_ego_obs or not actors_others_obs or not actors_ego_obs.value or len(actors_ego_obs.value) < 1:
            return

        ego_actor: DynamicActor = actors_ego_obs.value[0]
        visible_actors: Dict[str, DynamicActor] = get_occupied_cells_multi(actors_others_obs.value + [ego_actor])

        # Generate PEM complex object attributes
        ts: float = min([ts1, actors_ego_obs.timestamp, actors_others_obs.timestamp])
        pem_ego = map_pem_actor(ego_actor)
        pem_grid = PEMOccupancyGrid(cells=[])

        for cell in grid.cells:
            group_key = f'cell_occupant_{cell.quad_key.key}'

            occupant_relation: PEMRelation[Optional[PEMDynamicActor]] = None
            state_relation: PEMRelation[GridCellState] = PEMRelation(cell.state.confidence, GridCellState(cell.state.value))

            if cell.quad_key.key in visible_actors:
                actor = visible_actors[cell.quad_key.key]
                self.tracker.track(group_key, str(actor.id))
                occupant_relation = PEMRelation(self.tracker.get(group_key, str(actor.id)), map_pem_actor(actor))
            else:
                occupant_relation = PEMRelation(cell.state.confidence, None)

            self.tracker.cycle_group(group_key)

            # Consistency between state and occupant presence
            if occupant_relation.object and state_relation.object != GridCellState.occupied():
                if occupant_relation.confidence > state_relation.confidence:
                    state_relation = PEMRelation(occupant_relation.confidence, GridCellState.occupied())
                else:
                    occupant_relation = PEMRelation(state_relation.confidence, None)

            pem_grid.cells.append(PEMGridCell(
                hash=cell.quad_key.to_quadint(),
                state=state_relation,
                occupant=occupant_relation
            ))

        # Generate PEM graph
        graph = PEMTrafficScene(timestamp=ts,
                                measured_by=pem_ego,
                                occupancy_grid=pem_grid)

        encoded_msg = graph.to_bytes()
        # logging.debug(f'Encoded state representation to {len(encoded_msg) / 1024} kBytes')

        contained_tiles = frozenset(map(lambda c: c.quad_key.key, grid.cells))
        self.tss.publish_graph(encoded_msg, contained_tiles)
        self.inbound.publish(OBS_GRAPH_LOCAL, obs)

        # Debug logging
        self.tsdiffhistory3.append(time.monotonic() - self.last_publish)
        self.last_publish = time.monotonic()
        logging.debug(f'PUBLISH: {np.mean(self.tsdiffhistory3)}')

        self.tsdiffhistory2.append(time.monotonic() - _ts)
        logging.debug(f'GRID: {np.mean(self.tsdiffhistory2)}')

    def _on_remote_grid(self, msg: bytes):
        # TODO: Maybe do asynchronously?
        decoded_msg = PEMTrafficScene.from_bytes(msg)

    def _record(self):
        while True:
            time.sleep(1 / RECORDING_RATE)

            if not self.alive:
                return

            if not self.recording or not self.sink:
                continue

            obs1 = self.inbound.om.latest(OBS_GRID_COMBINED)
            obs2 = self.inbound.om.latest(OBS_ACTOR_EGO)

            if obs1 and obs2:
                self.sink.push(OBS_GRID_COMBINED, obs1)
                self.sink.push(OBS_ACTOR_EGO, obs2)
