import argparse
import itertools
import logging
import math
import pickle
import sys
import time
from multiprocessing.pool import Pool, AsyncResult
from operator import attrgetter
from typing import List, Tuple, Dict, Set, Any, Union

from tqdm import tqdm

from common import quadkey
from common.constants import *
from common.observation import PEMTrafficSceneObservation
from common.occupancy import GridCellState as Gss
from common.quadkey import QuadKey
from common.serialization.schema import GridCellState
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMOccupancyGrid, PEMGridCell
from common.serialization.schema.relation import PEMRelation
from evaluation.perception import OccupancyGroundTruthContainer as Ogtc

DATA_DIR = '../../../data/evaluation/perception'

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

# TODO: Multi-threading
# TODO: Optimize Big-O complexity

State5Tuple = Tuple[QuadKey, float, Gss, int, float]  # Cell, Confidence, State, SenderId, Timestamp

quad_str_lookup: Dict[int, str] = {}


def data_dir():
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '../../../data'))


class GridEvaluator:
    def __init__(self, file_prefix: str, data_dir: str = '/tmp'):
        self.file_prefix: str = file_prefix
        self.data_dir: str = data_dir
        self.data_dir_actual: str = os.path.join(data_dir, 'actual')
        self.data_dir_observed: str = os.path.join(data_dir, 'observed')

    def run(self):
        occupancy_ground_truth: List[Ogtc] = None
        occupancy_observations_local: List[PEMTrafficSceneObservation] = None
        occupancy_observations_remote: List[PEMTrafficSceneObservation] = None
        occupancy_observations_fused: List[PEMTrafficSceneObservation] = None

        occupancy_observations_local, occupancy_observations_remote, occupancy_ground_truth = self.read_data()

        if len(occupancy_observations_remote) > 0:
            logging.info('Fusing local and remote observations.')
            occupancy_observations_fused = self.fuse_observations(occupancy_observations_local, occupancy_observations_remote)
            logging.info(f'Got {len(occupancy_observations_fused)} observations after fusion.')

            logging.info('[FUSED] Computing closest matches between ground truth and observations.')
            matching: Set[Tuple[State5Tuple, State5Tuple]] = self.compute_matching(occupancy_observations_fused, occupancy_ground_truth)

            if len(matching) < 1:
                logging.warning('Did not find any match.')
            else:
                logging.info('[FUSED] Computing score.')
                mse: float = self.compute_mse(matching)
                acc: float = self.compute_accuracy(matching)
                logging.info(f'[FUSED] MSE: {mse}, ACC: {acc}')

        logging.info('[LOCAL ONLY] Computing closest matches between ground truth and observations.')
        matching: Set[Tuple[State5Tuple, State5Tuple]] = self.compute_matching(occupancy_observations_local, occupancy_ground_truth)

        if len(matching) < 1:
            logging.warning('Did not find any match.')
        else:
            logging.info('[LOCAL ONLY] Computing score.')
            mse: float = self.compute_mse(matching)
            acc: float = self.compute_accuracy(matching)
            logging.info(f'[LOCAL ONLY] MSE: {mse}, ACC: {acc}')

    @classmethod
    def fuse_observations(cls, local_observations: List[PEMTrafficSceneObservation], remote_observations: List[PEMTrafficSceneObservation]) -> List[PEMTrafficSceneObservation]:
        if len(remote_observations) < 1:
            return local_observations

        n_threads: int = 5
        fuse_pool: Pool = Pool(processes=n_threads)
        mapping_result1 = cls.map_by_parent_and_sender(remote_observations)
        mapping_result2 = cls.map_by_parent_and_sender(local_observations)

        mapping1: Dict[QuadKey, Dict[int, List[PEMTrafficSceneObservation]]] = mapping_result1[0]
        mapping2: Dict[QuadKey, Dict[int, List[PEMTrafficSceneObservation]]] = mapping_result2[0]

        fuse_jobs: List[Tuple[PEMTrafficSceneObservation, PEMTrafficSceneObservation]] = []
        fused_observations: List[PEMTrafficSceneObservation] = []

        for lo in local_observations:
            # TODO: binary search tree
            sid: int = lo.meta['sender']
            parent: QuadKey = lo.meta['parent']

            if parent in mapping1 and sid in mapping1[parent]:
                # A remote observation, that has just arrived at the ego, can be combined with a local
                # observation from either direction of time.
                # fuse() will later take care of that a data point won't be available ahead of time.
                ro1 = cls.find_closest_match(lo, 'timestamp', mapping1[parent][sid], op='-')
                ro2 = cls.find_closest_match(lo, 'timestamp', mapping1[parent][sid], op='+')
                fuse_jobs.extend([(lo, ro) for ro in [ro1, ro2] if ro is not None])

        batch_size: int = len(fuse_jobs) // n_threads + 1
        jobs: List[AsyncResult] = []

        for i in range(n_threads):
            jobs.append(fuse_pool.starmap_async(cls.fuse, fuse_jobs[i * batch_size:(i + 1) * batch_size], callback=fused_observations.extend, error_callback=logging.warning))

        for j in jobs:
            j.wait()

        fuse_pool.close()

        return fused_observations

    @classmethod
    def fuse(cls, local_observation: PEMTrafficSceneObservation, remote_observation: PEMTrafficSceneObservation) -> PEMTrafficSceneObservation:
        assert local_observation.meta['parent'] == remote_observation.meta['parent']

        cells: List[PEMGridCell] = []

        t1, t2 = min([local_observation.timestamp, remote_observation.timestamp]), max([local_observation.timestamp, remote_observation.timestamp])
        weight: float = cls._decay(t1, t2)
        states: List[GridCellState] = GridCellState.options()
        local_cells: Dict[QuadKey, PEMGridCell] = {QuadKey(cls.cache_get(c.hash)): c for c in local_observation.value.occupancy_grid.cells}
        remote_cells: Dict[QuadKey, PEMGridCell] = {QuadKey(cls.cache_get(c.hash)): c for c in remote_observation.value.occupancy_grid.cells}
        keys: Set[QuadKey] = set().union(set(local_cells.keys()), set(remote_cells.keys()))

        for qk in keys:
            if qk in local_cells and qk not in remote_cells:
                cells.append(local_cells[qk])
            elif qk in local_cells and qk in remote_cells:
                weight_sum: float = 1 + weight
                new_cell: PEMGridCell = PEMGridCell(hash=local_cells[qk].hash)
                state_vec: List[float] = [0] * GridCellState.N

                for i in range(len(state_vec)):
                    v1: float = local_cells[qk].state.confidence * 1 if local_cells[qk].state.object == states[i] else 0
                    v2: float = remote_cells[qk].state.confidence * weight if remote_cells[qk].state.object == states[i] else 0

                    # Override unknown
                    if i == Gss.UNKNOWN and sum(state_vec[:Gss.UNKNOWN]) > 0:
                        if v1 > 0:
                            v1 = 0
                            weight_sum -= 1
                        elif v2 > 0:
                            v2 = 0
                            weight_sum -= weight

                    state_vec[i] = v1 + v2

                state_vec = [c / weight_sum for c in state_vec]
                max_conf: float = max(state_vec)
                max_state: int = state_vec.index(max_conf)
                new_cell.state = PEMRelation(object=GridCellState(value=Gss(max_state)), confidence=max_conf)

                cells.append(new_cell)

        return PEMTrafficSceneObservation(
            timestamp=t2,
            scene=PEMTrafficScene(**{
                'occupancy_grid': PEMOccupancyGrid(cells=cells)
            }),
            meta=local_observation.meta
        )

    def read_data(self) -> Tuple[List[PEMTrafficSceneObservation], List[PEMTrafficSceneObservation], List[Ogtc]]:
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
        logging.info(f'Reading observations.')

        for file_name in files_observed:
            with open(os.path.join(self.data_dir_observed, file_name), 'rb') as f:
                try:
                    if 'remote' in file_name:
                        occupancy_observations_remote += pickle.load(f)
                    else:
                        occupancy_observations_local += pickle.load(f)
                except EOFError:
                    logging.warning(f'File {file_name} corrupt.')

        logging.info(f'Got {len(occupancy_observations_local)} local and {len(occupancy_observations_remote)} remote observations.')

        logging.info(f'Re-arranging observations.')
        occupancy_observations_local = self.split_by_level(occupancy_observations_local)
        occupancy_observations_remote = self.split_by_level(occupancy_observations_remote)
        logging.info(f'Got {len(occupancy_observations_local)} local and {len(occupancy_observations_remote)} remote observations after re-arranging.')

        min_obs_ts: float = min(occupancy_observations_local, key=lambda o: o.value.min_timestamp).value.min_timestamp
        max_obs_ts: float = max(occupancy_observations_local, key=lambda o: o.value.max_timestamp).value.max_timestamp
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
                        # Unneeded information like timestamp and observer is omitted for simplicity
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

    @classmethod
    def compute_matching(cls, occupancy_observations: List[PEMTrafficSceneObservation], occupancy_ground_truth: List[Ogtc]) -> Set[Tuple[State5Tuple, State5Tuple]]:
        matches: Set[Tuple[State5Tuple, State5Tuple]] = set()
        mapping_result = cls.map_by_parent_and_sender(occupancy_observations)
        sender_ids: Set[int] = mapping_result[1]
        actual: Dict[QuadKey, List[Ogtc]] = dict.fromkeys(map(attrgetter('tile'), occupancy_ground_truth), [])  # Parent tile keys -> Ogtc
        observed: Dict[QuadKey, Dict[int, List[PEMTrafficSceneObservation]]] = mapping_result[0]  # Parent tile keys -> (ego ids -> observation)

        quadint_map: Dict[QuadKey, int] = {}

        # Populate ground truth map
        for k in actual.keys():
            actual[k] = list(filter(lambda o: o.tile == k, occupancy_ground_truth))

        # Compute match for every cell
        parent_quads: Set[QuadKey] = set(actual.keys()).intersection(set(observed.keys()))
        for parent in tqdm(parent_quads):
            items_actual: List[Ogtc] = sorted(actual[parent], key=attrgetter('ts'))

            # Iterate over ground truth grids at parent tile level
            for i, item_actual in enumerate(items_actual):

                # Consider every vehicle's observations
                for sid in sender_ids:

                    # Find grid (PEMTrafficSceneObservation) for current sender and current parent tile of interest
                    if item_actual.tile in observed and sid in observed[item_actual.tile]:
                        item_observed: Union[PEMTrafficSceneObservation, None] = cls.find_closest_match(item_actual, 'ts', observed[item_actual.tile][sid])
                    else:
                        item_observed: Union[PEMTrafficSceneObservation, None] = None

                    # Parent tile was not in this vehicle's range
                    if not item_observed:
                        continue

                    # Thin out: we want to avoid having the exact same match multiple times. Therefore, if two ground-truth
                    # items are time-wise closer than the next observation, skip.
                    if i > 0 and abs(item_actual.ts - items_actual[i - 1].ts) < abs(item_actual.ts - item_observed.timestamp):
                        continue

                    # For each truly occupied cell, first, check if it was even observed by some vehicle and, second, get its state.
                    # Currently, only occupied cells (~ false negatives) are considered.
                    for qk in item_actual.occupied_cells:

                        # For simplicity, items_actual[parent] might also contain grids that don't match parent -> ignore them
                        if not qk.is_ancestor(parent):
                            continue

                        if qk not in quadint_map:
                            quadint_map[qk] = qk.to_quadint()

                        inthash: int = quadint_map[qk]

                        # True state is occupied with 100 % confidence, because only occupied cells were even recorded by the ground truth data collector
                        s1: Tuple[float, Gss] = (1., Gss.OCCUPIED)

                        try:
                            tmp_state: PEMRelation = next(filter(lambda c: c.hash == inthash, item_observed.value.occupancy_grid.cells)).state
                            s2: Tuple[float, Gss] = (tmp_state.confidence, tmp_state.object.value)
                        except StopIteration:
                            # Cell was not observed, e.g. because not in any vehicle's field of view -> ignore
                            continue

                        c1: State5Tuple = (qk, s1[0], s1[1], sid, item_actual.ts)
                        c2: State5Tuple = (qk, s2[0], s2[1], sid, item_actual.ts)

                        # A match corresponds to one cell that is (a) actually occupied and (b) contained in the current sender's observed grid
                        # with some state and some confidence
                        matches.add((c1, c2))

        logging.info(f'Matching has {len(matches)} entries.')

        return matches

    @staticmethod
    def map_by_parent_and_sender(observations: List[PEMTrafficSceneObservation]) -> Tuple[Dict[QuadKey, Dict[int, List[PEMTrafficSceneObservation]]], Set[int]]:
        mapping: Dict[QuadKey, Dict[int, List[PEMTrafficSceneObservation]]] = {}
        sender_ids: Set[int] = set()

        for obs in observations:
            sender_id: int = obs.meta['sender']
            parent: QuadKey = obs.meta['parent']

            if parent not in mapping:
                mapping[parent] = {}

            if sender_id not in mapping[parent]:
                mapping[parent][sender_id] = []

            mapping[parent][sender_id].append(obs)
            sender_ids.add(sender_id)

        return mapping, sender_ids

    @staticmethod
    def find_closest_match(needle: Any, needle_attr: str, haystack: List[PEMTrafficSceneObservation], op: str = 'o'):
        if op == '-':
            candidates: List[PEMTrafficSceneObservation] = list(filter(lambda o: 0 < getattr(needle, needle_attr) - o.timestamp < GRID_TTL_SEC, haystack))
        elif op == '+':
            candidates: List[PEMTrafficSceneObservation] = list(filter(lambda o: 0 > getattr(needle, needle_attr) - o.timestamp > -GRID_TTL_SEC, haystack))
        else:
            candidates: List[PEMTrafficSceneObservation] = list(filter(lambda o: abs(getattr(needle, needle_attr) - o.timestamp) < GRID_TTL_SEC, haystack))

        if len(candidates) < 1:
            return None

        return min(candidates, key=lambda o: abs(getattr(needle, needle_attr) - o.timestamp))

    @staticmethod
    def cache_get(quadint: int) -> str:
        if quadint not in quad_str_lookup:
            quad_str_lookup[quadint] = quadkey.from_int(quadint).key
        return quad_str_lookup[quadint]

    @staticmethod
    def _decay(timestamp: float, ref_time: float = time.time()) -> float:
        t = int((ref_time - timestamp) * 10)  # t in 100ms
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
