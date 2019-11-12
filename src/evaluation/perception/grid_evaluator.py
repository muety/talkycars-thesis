import argparse
import gc
import itertools
import logging
import math
import pickle
import random
import sys
import time
from operator import attrgetter
from typing import List, Tuple, Dict, Set, Any, Union, cast

from pyquadkey2 import quadkey
from pyquadkey2.quadkey import QuadKey
from tqdm import tqdm

from common.bst.rb_tree import RedBlackTree
from common.constants import *
from common.observation import PEMTrafficSceneObservation, Observation, RawBytesObservation
from common.occupancy import GridCellState as Gss
from common.serialization.schema import GridCellState
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMOccupancyGrid, PEMGridCell
from common.serialization.schema.relation import PEMRelation
from common.util.misc import multi_getattr
from evaluation.perception import OccupancyGroundTruthContainer as Ogtc

DATA_DIR = '../../../data/evaluation/perception'

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)
random.seed(0)

# TODO: Multi-threading
# TODO: Optimize Big-O complexity

State5Tuple = Tuple[QuadKey, float, Gss, int, float]  # Cell, Confidence, State, SenderId, Timestamp

quad_str_lookup: Dict[int, str] = {}
quad_int_lookup: Dict[str, int] = {}


def data_dir():
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '../../../data'))


class ObservationTree:
    def __init__(self, key_attr: str, items: List[Observation] = None):
        self.mapping: Dict[float, Observation] = {}
        self.tree: RedBlackTree = RedBlackTree()
        self.key_attr: str = key_attr

        self.extend(items if items else [])

    def add(self, obj: Observation, overwrite=True):
        key: float = multi_getattr(obj, self.key_attr)
        if not overwrite and key in self.mapping:
            return
        self.mapping[key] = obj
        self.tree.add(key)

    def delete(self, obj: Observation):
        key: float = multi_getattr(obj, self.key_attr)
        del self.mapping[key]
        self.tree.remove(key)

    def extend(self, objs: List[Observation]):
        for obj in objs:
            self.add(obj)

    def find_ceil(self, val: float) -> Observation:
        match: float = self.tree.ceil(val)
        return self.mapping[match] if match else None

    def find_floor(self, val: float) -> Observation:
        match: float = self.tree.floor(val)
        return self.mapping[match] if match else None

    @property
    def size(self) -> int:
        return self.tree.count


class GridEvaluator:
    def __init__(self, file_prefix: str, data_dir: str = '/tmp'):
        self.file_prefix: str = file_prefix
        self.data_dir: str = data_dir
        self.data_dir_actual: str = os.path.join(data_dir, 'actual')
        self.data_dir_observed: str = os.path.join(data_dir, 'observed')
        self.n_proc: int = 1
        self.consider_neighborhood: bool = True

    def run(self):
        # empirically found that down-sampling by factor of 4 makes effectively no difference in output
        occupancy_observations_local, occupancy_observations_remote, occupancy_ground_truth = self.read_data(
            downsample_ground_truth=.25, downsample_observations=1
        )

        logging.info('Evaluating average observation delays.')
        d1, d2 = self.eval_mean_delays(occupancy_observations_local, occupancy_observations_remote)
        logging.info(f'Ø local delay: {d1} sec; Ø remote delay: {d2} sec')

        occupancy_observations_local, occupancy_observations_remote, occupancy_ground_truth = self.preprocess_data(
            occupancy_observations_local,
            occupancy_observations_remote,
            occupancy_ground_truth
        )

        tags: List[str] = ['LOCAL', 'FUSED']

        logging.info(f'[{tags[0]}] Computing closest matches between ground truth and observations.')
        matching1: Set[Tuple[Tuple[QuadKey, float, GridCellState, int, float], Tuple[QuadKey, float, GridCellState, int, float]]] = self.compute_matching(
            occupancy_observations_local,
            occupancy_observations_remote,
            occupancy_ground_truth,
            True,
            self.consider_neighborhood
        )
        logging.info(f'[{tags[0]}] Finished matching computation.')
        self.print_scores(matching1, tags[0])

        logging.info(f'[{tags[1]}] Computing closest matches between ground truth and observations.')
        matching2: Set[Tuple[Tuple[QuadKey, float, GridCellState, int, float], Tuple[QuadKey, float, GridCellState, int, float]]] = self.compute_matching(
            occupancy_observations_local,
            occupancy_observations_remote,
            occupancy_ground_truth,
            False,
            self.consider_neighborhood
        )
        logging.info(f'[{tags[1]}] Finished matching computation.')
        self.print_scores(matching2, tags[1])

        assert len(matching1) == len(matching2)

    @staticmethod
    def eval_mean_delays(local_observations: List[PEMTrafficSceneObservation], remote_observations: List[PEMTrafficSceneObservation]) -> Tuple[float, float]:
        local_ordered: List[PEMTrafficSceneObservation] = sorted(local_observations, key=lambda v: (v.meta['sender'], v.timestamp))
        remote_ordered: List[PEMTrafficSceneObservation] = sorted(remote_observations, key=lambda v: (v.meta['sender'], v.timestamp))

        ts1_local: List[float] = list(map(attrgetter('value.timestamp'), local_ordered))
        ts2_local: List[float] = list(map(attrgetter('timestamp'), local_ordered))
        ts1_remote_min: List[float] = list(map(attrgetter('value.min_timestamp'), remote_ordered))
        ts2_remote_min: List[float] = list(map(attrgetter('timestamp'), remote_ordered))
        ts1_remote_max: List[float] = list(map(attrgetter('value.max_timestamp'), remote_ordered))
        ts2_remote_max: List[float] = ts2_remote_min

        lag_local: float = sum(map(lambda t: abs(t[0] - t[1]), zip(ts1_local, ts2_local))) / len(local_ordered)
        lag_remote_min: float = sum(map(lambda t: abs(t[0] - t[1]), zip(ts1_remote_min, ts2_remote_min))) / len(remote_ordered)
        lag_remote_max: float = sum(map(lambda t: abs(t[0] - t[1]), zip(ts1_remote_max, ts2_remote_max))) / len(remote_ordered)

        return lag_local, (lag_remote_min + lag_remote_max) / 2

    @classmethod
    def print_scores(cls, matching: Set[Tuple[State5Tuple, State5Tuple]], tag: str = ''):
        if len(matching) < 1:
            logging.warning('Did not find any match.')
        else:
            logging.info(f'[{tag}] Computing score.')
            mse: float = cls.compute_mse(matching)
            acc: float = cls.compute_accuracy(matching)
            logging.info(f'[{tag}] MSE: {mse}, ACC: {acc}')

    @classmethod
    def fuse(cls, local_observation: PEMTrafficSceneObservation, remote_observation: PEMTrafficSceneObservation, ref_time: float) -> PEMTrafficSceneObservation:
        assert local_observation.meta['parent'] == remote_observation.meta['parent']

        cells: List[PEMGridCell] = []
        ts1: float = local_observation.value.timestamp
        ts2: float = remote_observation.value.min_timestamp + (remote_observation.value.max_timestamp - remote_observation.value.min_timestamp) / 2
        weights: Tuple[float, float] = (cls._decay(ts1, ref_time), cls._decay(ts2, ref_time))
        states: List[GridCellState] = GridCellState.options()
        local_cells: Dict[QuadKey, PEMGridCell] = {QuadKey(cls.cache_get(c.hash)): c for c in local_observation.value.occupancy_grid.cells}
        remote_cells: Dict[QuadKey, PEMGridCell] = {QuadKey(cls.cache_get(c.hash)): c for c in remote_observation.value.occupancy_grid.cells}
        keys: Set[QuadKey] = set().union(set(local_cells.keys()), set(remote_cells.keys()))

        for qk in keys:
            if qk in local_cells and qk not in remote_cells:
                cells.append(local_cells[qk])
            elif qk not in local_cells and qk in remote_cells:
                cells.append(remote_cells[qk])
            else:
                weight_sum: float = sum(weights)
                new_cell: PEMGridCell = PEMGridCell(hash=local_cells[qk].hash)
                state_vec: List[float] = [0] * GridCellState.N

                for i in range(len(state_vec)):
                    v1: float = local_cells[qk].state.confidence * weights[0] if local_cells[qk].state.object == states[i] else 0
                    v2: float = remote_cells[qk].state.confidence * weights[1] if remote_cells[qk].state.object == states[i] else 0

                    # Override unknown
                    if i == Gss.UNKNOWN and sum(state_vec[:Gss.UNKNOWN]) > 0:
                        if v1 > 0:
                            v1 = 0
                            weight_sum -= weights[0]
                        elif v2 > 0:
                            v2 = 0
                            weight_sum -= weights[1]

                    state_vec[i] = v1 + v2

                state_vec = [c / weight_sum for c in state_vec]
                max_conf: float = max(state_vec)
                max_state: int = state_vec.index(max_conf)
                new_cell.state = PEMRelation(object=GridCellState(value=Gss(max_state)), confidence=max_conf)

                cells.append(new_cell)

        return PEMTrafficSceneObservation(
            timestamp=ref_time,  # shouldn't matter
            scene=PEMTrafficScene(**{
                'occupancy_grid': PEMOccupancyGrid(cells=cells)
            }),
            meta=local_observation.meta
        )

    def read_data(self, downsample_ground_truth: float = 1., downsample_observations: float = 1.) -> Tuple[List[PEMTrafficSceneObservation], List[PEMTrafficSceneObservation], List[Ogtc]]:
        assert downsample_ground_truth <= 1 and downsample_observations <= 1

        logging.info(f'downsample_ground_truth={downsample_ground_truth}, downsample_observations={downsample_observations}')
        logging.info('Reading directory info.')

        files_actual: List[str] = list(filter(lambda s: s.startswith(self.file_prefix), os.listdir(self.data_dir_actual)))
        files_observed: List[str] = list(filter(lambda s: s.startswith(self.file_prefix), os.listdir(self.data_dir_observed)))

        occupancy_ground_truth: List[Ogtc] = []
        occupancy_observations_local: List[PEMTrafficSceneObservation] = []
        occupancy_observations_remote: List[PEMTrafficSceneObservation] = []

        logging.info('Reading ground truth.')

        for file_name in files_actual:
            with open(os.path.join(self.data_dir_actual, file_name), 'rb') as f:
                try:
                    occupancy_ground_truth += pickle.load(f)
                except EOFError:
                    logging.warning(f'File {file_name} corrupt.')

        logging.info(f'Got {len(occupancy_ground_truth)} ground truth data points.')
        logging.info(f'Reading and decoding observations.')

        for file_name in files_observed:
            with open(os.path.join(self.data_dir_observed, file_name), 'rb') as f:
                try:
                    if 'remote' not in file_name:
                        occupancy_observations_local.extend(pickle.load(f))
                    else:
                        data = pickle.load(f)
                        assert isinstance(data, list)

                        if len(data) < 1:
                            continue

                        if isinstance(data[0], RawBytesObservation):
                            for obs in data:
                                try:
                                    occupancy_observations_remote.append(PEMTrafficSceneObservation(
                                        timestamp=obs.timestamp,
                                        scene=PEMTrafficScene.from_bytes(obs.value),
                                        meta=obs.meta
                                    ))
                                except KeyError:
                                    continue
                        elif isinstance(data[0], PEMTrafficSceneObservation):
                            occupancy_observations_remote.extend(data)
                except EOFError:
                    logging.warning(f'File {file_name} corrupt.')

        logging.info(f'Got {len(occupancy_observations_local)} local and {len(occupancy_observations_remote)} remote observations.')

        occupancy_ground_truth = sorted(random.sample(occupancy_ground_truth, k=math.floor(len(occupancy_ground_truth) * downsample_ground_truth)), key=attrgetter('ts'))
        occupancy_observations_local = sorted(random.sample(occupancy_observations_local, k=math.floor(len(occupancy_observations_local) * downsample_observations)), key=attrgetter('timestamp'))
        occupancy_observations_remote = sorted(random.sample(occupancy_observations_remote, k=math.floor(len(occupancy_observations_remote) * downsample_observations)), key=attrgetter('timestamp'))

        return occupancy_observations_local, occupancy_observations_remote, occupancy_ground_truth

    @classmethod
    def preprocess_data(cls, occupancy_observations_local: List[PEMTrafficSceneObservation], occupancy_observations_remote: List[PEMTrafficSceneObservation], occupancy_ground_truth: List[Ogtc]) -> Tuple[List[PEMTrafficSceneObservation], List[PEMTrafficSceneObservation], List[Ogtc]]:
        logging.info(f'Re-arranging observations.')
        occupancy_observations_local = cls.split_by_level(occupancy_observations_local)
        occupancy_observations_remote = cls.split_by_level(occupancy_observations_remote)
        logging.info(f'Got {len(occupancy_observations_local)} local and {len(occupancy_observations_remote)} remote observations after re-arranging.')

        min_obs_ts_local: float = min(occupancy_observations_local, key=lambda o: o.value.min_timestamp).value.min_timestamp
        max_obs_ts_local: float = max(occupancy_observations_local, key=lambda o: o.value.max_timestamp).value.max_timestamp
        min_obs_ts_remote: float = min(occupancy_observations_remote, key=lambda o: o.value.min_timestamp).value.min_timestamp if len(occupancy_observations_remote) else time.time()
        max_obs_ts_remote: float = max(occupancy_observations_remote, key=lambda o: o.value.max_timestamp).value.max_timestamp if len(occupancy_observations_remote) else 0
        min_obs_ts: float = min([min_obs_ts_local, min_obs_ts_remote])
        max_obs_ts: float = max([max_obs_ts_local, max_obs_ts_remote])
        occupancy_ground_truth = list(filter(lambda o: max_obs_ts >= o.ts >= min_obs_ts, occupancy_ground_truth))

        return occupancy_observations_local, occupancy_observations_remote, occupancy_ground_truth

    @classmethod
    def split_by_level(cls, observations: List[PEMTrafficSceneObservation]) -> List[PEMTrafficSceneObservation]:
        scenes: Dict[str, List[PEMTrafficSceneObservation]] = {}  # parent tile to scene

        for o in observations:
            contained_parents: Set[str] = set()

            for cell in o.value.occupancy_grid.cells:
                parent_str: str = cls.cache_get(cell.hash)[:REMOTE_GRID_TILE_LEVEL]
                contained_parents.add(parent_str)
                if parent_str not in scenes:
                    scenes[parent_str] = []

            for parent in contained_parents:
                scenes[parent].append(PEMTrafficSceneObservation(
                    timestamp=o.timestamp,
                    scene=PEMTrafficScene(**{
                        'timestamp': o.value.timestamp,
                        'min_timestamp': o.value.min_timestamp,
                        'max_timestamp': o.value.max_timestamp,
                        'occupancy_grid': PEMOccupancyGrid(**{
                            'cells': [c for c in o.value.occupancy_grid.cells if cls.cache_get(c.hash).startswith(parent)]
                        })
                    }),
                    meta={'parent': QuadKey(parent), **o.meta}
                ))

        return list(itertools.chain(*list(scenes.values())))

    @staticmethod
    def compute_mse(matching: Set[Tuple[State5Tuple, State5Tuple]]) -> float:
        error_sum: float = 0
        for m in matching:
            error_sum += (m[0][1] - m[1][1]) ** 2 if m[0][2] == m[1][2] else 1
        return error_sum / len(matching) if len(matching) > 0 else 1

    @staticmethod
    def compute_mae(matching: Set[Tuple[State5Tuple, State5Tuple]]) -> float:
        error_sum: float = 0
        for m in matching:
            error_sum += abs(m[0][1] - m[1][1]) if m[0][2] == m[1][2] else 1
        return error_sum / len(matching) if len(matching) > 0 else 1

    @staticmethod
    def compute_accuracy(matching: Set[Tuple[State5Tuple, State5Tuple]]) -> float:
        count: int = 0
        for m in matching:
            count += m[0][2] == m[1][2]
        return count / len(matching) if len(matching) > 0 else 0

    '''
    See https://go.gliffy.com/go/share/s27a2t2njhihpntoqe81 [1] for an illustration
    '''

    @classmethod
    def compute_matching(cls,
                         local_observations: List[PEMTrafficSceneObservation],
                         remote_observations: List[PEMTrafficSceneObservation],
                         ground_truth: List[Ogtc],
                         exclude_remote: bool,
                         consider_neighborhood: bool) -> Set[Tuple[State5Tuple, State5Tuple]]:
        matches: Set[Tuple[State5Tuple, State5Tuple]] = set()
        sender_ids: Set[int] = set()
        actual: Dict[QuadKey, List[Ogtc]] = dict.fromkeys(map(attrgetter('tile'), ground_truth), [])  # Parent tile keys -> Ogtc

        mapping_result = cls.map_by_parent_and_sender(local_observations)
        sender_ids = sender_ids.union(mapping_result[1])
        observed_local: Dict[QuadKey, Dict[int, ObservationTree]] = mapping_result[0]  # Parent tile keys -> (ego ids -> observation)

        mapping_result = cls.map_by_parent_and_sender(remote_observations)
        sender_ids = sender_ids.union(mapping_result[1])
        observed_remote: Dict[QuadKey, Dict[int, ObservationTree]] = mapping_result[0]

        local_count: int = 0
        remote_count: int = 0
        cell_tracker: List[int] = [0] * (GridCellState.N + 1)

        # Populate ground truth map
        for k in actual.keys():
            actual[k] = list(filter(lambda o: o.tile == k, ground_truth))

        del local_observations
        del remote_observations
        del ground_truth
        gc.collect()

        parent_quads: Set[QuadKey] = set(actual.keys()).intersection(set(observed_local.keys()).union(set(observed_remote.keys())))
        for parent in tqdm(parent_quads):
            items_actual: List[Ogtc] = sorted(actual[parent], key=attrgetter('ts'))

            # Iterate over ground truth grids at parent tile level
            for i, item_actual in enumerate(items_actual):

                # Consider every vehicle's observations
                for sid in sender_ids:

                    item_local: Union[PEMTrafficSceneObservation, None] = None
                    item_remote: Union[PEMTrafficSceneObservation, None] = None

                    # Find grid (PEMTrafficSceneObservation) for current sender and current parent tile of interest
                    # For every ground truth data point, get closest local- and remote observations and fuse them (later)
                    if item_actual.tile in observed_local and sid in observed_local[item_actual.tile]:
                        item_local: Union[PEMTrafficSceneObservation, None] = cls.find_closest_match(item_actual, 'ts', observed_local[item_actual.tile][sid], sign=+1)
                    if not exclude_remote and item_actual.tile in observed_remote and sid in observed_remote[item_actual.tile]:
                        item_remote: Union[PEMTrafficSceneObservation, None] = cls.find_closest_match(item_actual, 'ts', observed_remote[item_actual.tile][sid], sign=+1)

                    '''
                    Example in [1]:
                    – Case 2.1 -> Tile C
                      --> this block will find a hit -> tile C will be considered for ground truth (denominator), because it's in the local neighborhood
                    – Case 2.1 -> Tile A
                      --> this block won't find a hit -> breaking loop iteration here
                    – Case 2.2 -> Tile H
                      --> this block won't get executed, as item_remote is not None
                    – Case 2.2 -> Tile C
                      -> this block will find a hit -> tile C will be considered for ground truth (denominator), because it's in the local neighborhood
                    – Case 2.1 -> Tile A
                      --> this block won't find a hit -> breaking loop iteration here
                    '''
                    if consider_neighborhood and not item_local:
                        neighbors: Set[QuadKey] = set(map(QuadKey, parent.nearby(1)))
                        for neighbor in neighbors:
                            # This block returning true means the ego was subscribed to the given tile at given time.
                            # Note: This is logically not symmetric. We can check whether an ego WAS subscribed to a parent, but
                            # not whether is WAS NOT. But that's ok since it does only marginally bias the absolute scores later, not their relations.
                            if neighbor in observed_local and sid in observed_local[neighbor] and cls.find_closest_match(item_actual, 'ts', observed_local[neighbor][sid], sign=+1):
                                # Timestamp as well as any other properties than occupancy grid cells should not matter anymore from here on
                                item_local = cls.get_empty_observation(item_actual.ts)
                                break

                    '''
                    Example in [1]:
                    – Case 1.1, 1.2 -> Tile H
                    – Case 2.1, 2.2 -> Tile A
                    '''
                    if not item_local:
                        continue

                    if item_local and 'empty' not in item_local.meta:
                        local_count += 1
                    if item_remote:
                        remote_count += 1

                    if item_local and not item_remote:
                        item: PEMTrafficSceneObservation = item_local
                    elif item_remote and (not item_local or 'empty' in item_local.meta):
                        item: PEMTrafficSceneObservation = item_remote
                    else:
                        item: PEMTrafficSceneObservation = cls.fuse(item_local, item_remote, item_actual.ts)

                    # For each truly occupied cell, first, check if it was even observed by some vehicle and, second, get its state.
                    # Currently, only occupied cells (~ false negatives) are considered.
                    for qk in item_actual.occupied_cells:

                        # For simplicity, items_actual[parent] might also contain grids that don't match parent -> ignore them
                        if not qk.is_ancestor(parent):
                            continue

                        inthash: int = cls.cache_get_inverse(qk.key)

                        # True state is occupied with 100 % confidence, because only occupied cells were even recorded by the ground truth data collector
                        s1: Tuple[float, Gss] = (1., Gss.OCCUPIED)

                        try:
                            tmp_state: PEMRelation = next(filter(lambda c: c.hash == inthash, item.value.occupancy_grid.cells)).state
                            s2: Tuple[float, Gss] = (tmp_state.confidence, tmp_state.object.value)
                        except StopIteration:
                            # Current parent tile was in observation range, but cell was not observed, although it could have been -> consider it unknown
                            s2: Tuple[float, Gss] = (1, Gss.UNKNOWN)

                        cell_tracker[0] += 1
                        cell_tracker[s2[1] + 1] += 1

                        c1: State5Tuple = (qk, s1[0], s1[1], sid, item_actual.ts)
                        c2: State5Tuple = (qk, s2[0], s2[1], sid, item_actual.ts)

                        # A match corresponds to one cell that is (a) actually occupied and (b) contained in the current sender's observed grid
                        # with some state and some confidence
                        matches.add((c1, c2))

        # Print cell statistics
        total: int = cell_tracker[0] + 1
        free: float = round((cell_tracker[Gss.FREE + 1] / total) * 100, 2)
        occupied: float = round((cell_tracker[Gss.OCCUPIED + 1] / total) * 100, 2)
        unknown: float = round((cell_tracker[Gss.UNKNOWN + 1] / total) * 100, 2)
        logging.info(f'Free: {free} %, Occupied: {occupied} %, Unknown: {unknown} %')
        logging.info(f'Matching has {len(matches)} entries ({round((remote_count / (remote_count + local_count)) * 100, 2)} % remote).')

        return matches

    @staticmethod
    def map_by_parent_and_sender(observations: List[PEMTrafficSceneObservation]) -> Tuple[Dict[QuadKey, Dict[int, ObservationTree]], Set[int]]:
        mapping: Dict[QuadKey, Dict[int, ObservationTree]] = {}
        sender_ids: Set[int] = set()

        for obs in observations:
            sender_id: int = obs.meta['sender']
            parent: QuadKey = obs.meta['parent']

            if parent not in mapping:
                mapping[parent] = {}

            if sender_id not in mapping[parent]:
                mapping[parent][sender_id] = ObservationTree(key_attr='timestamp')

            mapping[parent][sender_id].add(obs, overwrite=False)
            sender_ids.add(sender_id)

        return mapping, sender_ids

    @staticmethod
    def find_closest_match(needle: Any, needle_attr: str, haystack: ObservationTree, sign: int = 0, offset: float = 0.0) -> Union[PEMTrafficSceneObservation, None]:
        match: Union[Observation, None] = None
        ref_ts: float = getattr(needle, needle_attr) + offset

        if sign == 0:
            match1 = haystack.find_ceil(ref_ts)
            match2 = haystack.find_floor(ref_ts)
            match = min([m for m in [match1, match2] if m is not None], key=lambda o: abs(o.timestamp - ref_ts))
        elif sign > 0:  # greater than needle
            match = haystack.find_ceil(ref_ts)
        elif sign < 0:  # less than needle
            match = haystack.find_floor(ref_ts)

        if match is None or abs(match.timestamp - ref_ts) > GRID_TTL_SEC:
            return None

        return cast(PEMTrafficSceneObservation, match)

    @staticmethod
    def cache_get(quadint: int) -> str:
        if quadint not in quad_str_lookup:
            quad_str_lookup[quadint] = quadkey.from_int(quadint).key
        return quad_str_lookup[quadint]

    @staticmethod
    def cache_get_inverse(quadstr: str) -> int:
        if quadstr not in quad_int_lookup:
            quad_int_lookup[quadstr] = QuadKey(quadstr).to_quadint()
        return quad_int_lookup[quadstr]

    @staticmethod
    # Caution: Most values, like timestamps, meta data, etc. are not set
    def get_empty_observation(with_ts: float) -> PEMTrafficSceneObservation:
        return PEMTrafficSceneObservation(
            timestamp=with_ts,
            scene=PEMTrafficScene(
                occupancy_grid=PEMOccupancyGrid(cells=[])
            ),
            meta={'empty': True}
        )

    @staticmethod
    def _decay(timestamp: float, ref_time: float = time.time()) -> float:
        t = (ref_time - timestamp) * 10  # t in 100ms
        return math.exp(-t * FUSION_DECAY_LAMBDA)


def run(args=sys.argv[1:]):
    argparser = argparse.ArgumentParser(description='TalkyCars Grid Evaluator')
    argparser.add_argument('-p', '--file_prefix', required=True, type=str, help='File prefix of the data collection to be read (e.g. "120203233231202_2019-10-15_15-46-00")')
    argparser.add_argument('-d', '--in_dir', default=os.path.join(data_dir(), EVAL2_DATA_DIR), type=str, help='Directory to read data from')

    args, _ = argparser.parse_known_args(args)

    GridEvaluator(
        file_prefix=args.file_prefix,
        data_dir=os.path.normpath(
            os.path.join(os.path.dirname(__file__), args.in_dir)
        )
    ).run()


if __name__ == '__main__':
    run()
