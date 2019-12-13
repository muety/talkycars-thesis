import logging
import time
from collections import deque
from datetime import datetime
from enum import Enum
from threading import Thread, Lock
from typing import cast, Dict, Optional, Deque, List

from pyquadkey2.quadkey import QuadKey

from client.observation import ObservationManager, LinearObservationTracker
from client.observation.sink import Sink, PickleObservationSink
from client.subscription import TileSubscriptionService
from client.utils import map_pem_actor
from common.constants import *
from common.constants import EVAL2_BASE_KEY
from common.model import DynamicActor
from common.observation import CameraRGBObservation, ActorsObservation, PEMTrafficSceneObservation, RawBytesObservation
from common.observation import OccupancyGridObservation, LidarObservation, PositionObservation, \
    GnssObservation
from common.serialization.schema import GridCellState
from common.serialization.schema.actor import PEMDynamicActor
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMOccupancyGrid, PEMGridCell
from common.serialization.schema.relation import PEMRelation
from common.timing import TimingService
from .inbound import InboundController
from .occupancy import OccupancyGridManager
from .outbound import OutboundController


class ClientDialect(Enum):
    CARLA = 0


class TalkyClient:
    def __init__(self,
                 for_subject_id: int,
                 dialect: ClientDialect = ClientDialect.CARLA,
                 grid_radius: int = OCCUPANCY_RADIUS_DEFAULT,
                 ):
        self.ego_id: str = str(for_subject_id)
        self.dialect: ClientDialect = dialect
        self.om: ObservationManager = ObservationManager()
        # Please Note: The occupancy grid manager might also be part of the simulation-related code, e.g. as a
        # virtual sensor of the ego vehicle. The current implementation assumes that a vehicle can only deliver
        # low-level fused raw sensor data and does not know about occupancy grids or object lists
        self.gm: OccupancyGridManager = OccupancyGridManager(OCCUPANCY_TILE_LEVEL, grid_radius)
        self.inbound: InboundController = InboundController(self.om, self.gm)
        self.outbound: OutboundController = OutboundController(self.om, self.gm)
        self.tss: TileSubscriptionService = TileSubscriptionService(self._on_remote_graph, client_id=self.ego_id)
        self.tracker: LinearObservationTracker = LinearObservationTracker(n=10)
        self.timings: TimingService = TimingService()
        self.quadint_cache: Dict[str, int] = {}
        self.remote_grid_sink: Sink = None
        self.local_grid_sink: Sink = None
        self.alive: bool = True
        self.recording: bool = False

        self.recording_thread: Thread = Thread(target=self._record, daemon=True)
        self.recording_thread.start()
        self.decode_lock: Lock = Lock()

        # Type registrations
        self.om.register_key(OBS_POSITION, PositionObservation)
        self.om.register_key(OBS_LIDAR_POINTS, LidarObservation)
        self.om.register_key(OBS_CAMERA_RGB_IMAGE, CameraRGBObservation)
        self.om.register_key(OBS_GRID_LOCAL, OccupancyGridObservation)
        self.om.register_key(OBS_GRAPH_LOCAL, PEMTrafficSceneObservation)
        self.om.register_key(OBS_GRAPH_REMOTE, RawBytesObservation)
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
        self.outbound.subscribe(OBS_GRAPH_LOCAL, self._on_local_graph)

        # Debugging stuff
        self.last_publish: float = time.monotonic()
        self.tsdiffhistory1: Deque[float] = deque(maxlen=100)
        self.tsdiffhistory2: Deque[float] = deque(maxlen=100)
        self.tsdiffhistory3: Deque[float] = deque(maxlen=100)

        logging.info(f'Hi, I\'m {self.ego_id}!')

    def tear_down(self):
        logging.info(f'Stopping client in {GRID_TTL_SEC} seconds.')
        time.sleep(GRID_TTL_SEC)

        self.alive = False
        self.recording = False
        self.om.tear_down()
        self.gm.tear_down()
        self.timings.tear_down()

        if self.tss:
            self.tss.tear_down()

        for sink in [self.remote_grid_sink, self.local_grid_sink]:
            if sink:
                Thread(target=sink.flush).start()

    def toggle_recording(self):
        if not self.recording:
            now: datetime = datetime.now()

            self.local_grid_sink = PickleObservationSink(
                key=OBS_GRAPH_LOCAL,
                outpath=os.path.join(
                    self.data_dir, EVAL2_DATA_DIR, 'observed',  # No evaluation-related code is supposed to be here
                    now.strftime(f'{EVAL2_BASE_KEY}_{FUSION_DECAY_LAMBDA}-decay_%Y-%m-%d_%H-%M-%S_local_ego-{self.ego_id}.pkl')
                )
            )

            self.remote_grid_sink = PickleObservationSink(
                key=OBS_GRAPH_REMOTE,
                outpath=os.path.join(
                    self.data_dir, EVAL2_DATA_DIR, 'observed',  # No evaluation-related code is supposed to be here
                    now.strftime(f'{EVAL2_BASE_KEY}_{FUSION_DECAY_LAMBDA}-decay_%Y-%m-%d_%H-%M-%S_remote_ego-{self.ego_id}.pkl')
                )
            )

        self.recording = not self.recording

    @property
    def data_dir(self):
        return os.path.normpath(os.path.join(os.path.dirname(__file__), '../../data'))

    def _on_lidar(self, obs: LidarObservation):
        _ts = time.monotonic()

        if self.om.has(OBS_ACTOR_EGO):
            ego_obs: ActorsObservation = cast(ActorsObservation, self.om.latest(OBS_ACTOR_EGO))
            ego: DynamicActor = cast(ActorsObservation, ego_obs).value[0]

            actors: List[DynamicActor] = [ego]
            if self.om.has(OBS_ACTORS_RAW):
                actors += cast(ActorsObservation, self.om.latest(OBS_ACTORS_RAW)).value

            self.gm.update_actors(actors)
            self.gm.update_gnss(GnssObservation(timestamp=ego_obs.timestamp, coords=ego.gnss.value.components()))

        if not self.gm.match_with_lidar(cast(LidarObservation, obs)):
            return

        grid = self.gm.get_grid()
        if not grid:
            return

        obs = OccupancyGridObservation(obs.timestamp, grid)
        self.inbound.publish(OBS_GRID_LOCAL, obs)

        self.tsdiffhistory1.append(time.monotonic() - _ts)
        # logging.debug(f'LIDAR: {np.mean(self.tsdiffhistory1)}')

    def _on_gnss(self, obs: GnssObservation):
        qk: QuadKey = obs.to_quadkey(level=REMOTE_GRID_TILE_LEVEL)

        if qk != self.tss.current_parent:
            self.tss.update_position(qk)

    def _on_grid(self, obs: OccupancyGridObservation):
        _ts = time.monotonic()

        ts1, grid = obs.timestamp, obs.value
        actors_ego_obs = self.om.latest(OBS_ACTOR_EGO)
        actors_others_obs = self.om.latest(OBS_ACTORS_RAW)

        if not grid or not actors_ego_obs or not actors_others_obs or not actors_ego_obs.value or len(actors_ego_obs.value) < 1:
            return

        ts: float = min([ts1, actors_ego_obs.timestamp, actors_others_obs.timestamp])

        self.timings.start('d0', custom_time=ts)
        self.timings.stop('d0')

        ts2: float = time.time()

        ego_actor: DynamicActor = actors_ego_obs.value[0]
        # Turned off for evaluation, because occupants are not fused anyway
        # visible_actors: Dict[str, DynamicActor] = get_occupied_cells_multi_map(actors_others_obs.value + [ego_actor])
        visible_actors: Dict[str, DynamicActor] = {}

        # Generate PEM complex object attributes
        pem_ego = map_pem_actor(ego_actor)
        pem_grid = PEMOccupancyGrid(cells=[])

        for cell in grid.cells:
            group_key = f'cell_occupant_{cell.quad_key.key}'

            state_relation: PEMRelation[GridCellState] = PEMRelation(cell.state.confidence, GridCellState(cell.state.value))
            occupant_relation: PEMRelation[Optional[PEMDynamicActor]] = PEMRelation(0, None)

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
                hash=self._get_quadint(cell.quad_key),
                state=state_relation,
                occupant=occupant_relation
            ))

        now = time.time()

        # Generate PEM graph
        graph = PEMTrafficScene(timestamp=ts,
                                last_timestamp=now,
                                measured_by=pem_ego,
                                occupancy_grid=pem_grid)

        encoded_msg = graph.to_bytes()
        self.timings.start('d1', custom_time=ts2)
        self.timings.stop('d1')

        obs: PEMTrafficSceneObservation = PEMTrafficSceneObservation(now, graph, meta={'sender': int(self.ego_id)})
        self.inbound.publish(OBS_GRAPH_LOCAL, obs)

        if self.alive and self.recording and self.local_grid_sink:
            if OBS_GRAPH_LOCAL not in self.local_grid_sink.accumulator:
                self.local_grid_sink.push(OBS_GRAPH_LOCAL, [obs])
            else:
                self.local_grid_sink.accumulator[OBS_GRAPH_LOCAL].append(obs)

        if self.tss.active:
            self.tss.publish_graph(encoded_msg)

            # Debug logging
            self.tsdiffhistory3.append(time.monotonic() - self.last_publish)
            self.last_publish = time.monotonic()
            # logging.debug(f'PUBLISH: {np.mean(self.tsdiffhistory3)}')

        self.tsdiffhistory2.append(time.monotonic() - _ts)
        # logging.debug(f'GRID: {np.mean(self.tsdiffhistory2)}')

    def _on_local_graph(self, obs: PEMTrafficSceneObservation):
        pass

    def _on_remote_graph(self, msg: bytes):
        in_time: float = time.time()

        try:
            scene: PEMTrafficScene = PEMTrafficScene.from_bytes(msg)
            obs: PEMTrafficSceneObservation = PEMTrafficSceneObservation(time.time(), scene, meta={'sender': int(self.ego_id)})

            if self.alive and self.recording and self.remote_grid_sink:
                if OBS_GRAPH_REMOTE not in self.remote_grid_sink.accumulator:
                    self.remote_grid_sink.push(OBS_GRAPH_REMOTE, [obs])
                else:
                    self.remote_grid_sink.accumulator[OBS_GRAPH_REMOTE].append(obs)

            self.timings.start('d6', custom_time=in_time)
            self.timings.stop('d6')
        except KeyError:
            return

        self.timings.start('d5', custom_time=scene.last_timestamp)
        self.timings.stop('d5', custom_time=in_time)

    def _get_quadint(self, qk: QuadKey) -> int:
        if qk.key not in self.quadint_cache:
            self.quadint_cache[qk.key] = qk.to_quadint()
        return self.quadint_cache[qk.key]

    def _record(self):
        while True:
            time.sleep(1 / RECORDING_RATE)
            pass
