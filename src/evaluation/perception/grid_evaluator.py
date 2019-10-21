import argparse
import itertools
import logging
import pickle
import sys
from operator import attrgetter
from typing import List, Tuple, Dict, Set

from tqdm import tqdm

from common import quadkey
from common.constants import *
from common.observation import PEMTrafficSceneObservation
from common.occupancy import GridCellState
from common.quadkey import QuadKey
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMOccupancyGrid
from common.serialization.schema.relation import PEMRelation
from evaluation.perception import OccupancyGroundTruthContainer as Ogtc

DATA_DIR = '../../../data/evaluation/perception'

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

# TODO: Multi-threading
# TODO: Optimize Big-O complexity

State5Tuple = Tuple[QuadKey, float, GridCellState, int, float]  # Cell, Confidence, State, SenderId, Timestamp


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
        occupancy_observations: List[PEMTrafficSceneObservation] = None
        occupancy_observations, occupancy_ground_truth = self.read_data()

        logging.info('Computing closest matches between ground truth and observations.')
        matching: Set[Tuple[State5Tuple, State5Tuple]] = self.compute_matching(occupancy_observations, occupancy_ground_truth)

        if len(matching) < 1:
            logging.warning('Did not find any match.')
            return

        logging.info('Computing score.')
        mse: float = self.compute_mse(matching)
        mae: float = self.compute_mae(matching)
        acc: float = self.compute_accuracy(matching)

        logging.info(f'MSE: {mse}, MAE: {mae}, ACC: {acc}')

    def read_data(self) -> Tuple[List[PEMTrafficSceneObservation], List[Ogtc]]:
        logging.info('Reading directory info.')

        files_actual: List[str] = list(filter(lambda s: s.startswith(self.file_prefix), os.listdir(self.data_dir_actual)))
        files_observed: List[str] = list(filter(lambda s: s.startswith(self.file_prefix), os.listdir(self.data_dir_observed)))

        occupancy_ground_truth: List[Ogtc] = []
        occupancy_observations: List[PEMTrafficSceneObservation] = []

        logging.info('Reading ground truth.')

        for file_name in files_actual:
            with open(os.path.join(self.data_dir_actual, file_name), 'rb') as f:
                try:
                    occupancy_ground_truth += pickle.load(f)
                except EOFError:
                    logging.warning(f'File {file_name} corrupt.')

        logging.info(f'Reading observations.')

        for file_name in files_observed:
            with open(os.path.join(self.data_dir_observed, file_name), 'rb') as f:
                try:
                    occupancy_observations += pickle.load(f)
                except EOFError:
                    logging.warning(f'File {file_name} corrupt.')

        logging.info(f'Re-arranging observations.')
        occupancy_observations = self.split_by_level(occupancy_observations)

        min_obs_ts: float = min(occupancy_observations, key=lambda o: o.value.min_timestamp).value.min_timestamp
        max_obs_ts: float = max(occupancy_observations, key=lambda o: o.value.min_timestamp).value.min_timestamp
        occupancy_ground_truth = list(filter(lambda o: max_obs_ts >= o.ts >= min_obs_ts, occupancy_ground_truth))

        return occupancy_observations, occupancy_ground_truth

    @staticmethod
    def split_by_level(observations: List[PEMTrafficSceneObservation]) -> List[PEMTrafficSceneObservation]:
        scenes: Dict[str, List[PEMTrafficSceneObservation]] = {}  # parent tile to scene
        quad_str_lookup: Dict[int, str] = {}

        for o in observations:
            contained_parents: Set[str] = set()

            for cell in o.value.occupancy_grid.cells:
                parent_int: int = cell.hash
                if parent_int not in quad_str_lookup:
                    quad_str_lookup[parent_int] = quadkey.from_int(parent_int).key[:REMOTE_GRID_TILE_LEVEL]
                parent_str: str = quad_str_lookup[parent_int]

                contained_parents.add(parent_str)

                if parent_str not in scenes:
                    scenes[parent_str] = []

            for parent in contained_parents:
                scenes[parent].append(PEMTrafficSceneObservation(
                    timestamp=o.timestamp,
                    scene=PEMTrafficScene(**{
                        'timestamp': o.value.timestamp,
                        'min_timestamp': o.value.min_timestamp,
                        'measured_by': o.value.measured_by,
                        'occupancy_grid': PEMOccupancyGrid(**{
                            'cells': [c for c in o.value.occupancy_grid.cells if quad_str_lookup[c.hash].startswith(parent)]
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

    @staticmethod
    def compute_matching(occupancy_observations: List[PEMTrafficSceneObservation], occupancy_ground_truth: List[Ogtc]) -> Set[Tuple[State5Tuple, State5Tuple]]:
        sender_ids: Set[int] = set()
        matches: Set[Tuple[State5Tuple, State5Tuple]] = set()

        actual: Dict[QuadKey, List[Ogtc]] = dict.fromkeys(map(attrgetter('tile'), occupancy_ground_truth), [])  # Parent tile keys -> Ogtc
        observed: Dict[QuadKey, Dict[int, List[PEMTrafficSceneObservation]]] = dict.fromkeys(actual.keys(), {})  # Parent tile keys -> (ego ids -> observation)

        quadint_map: Dict[QuadKey, int] = {}

        def find_closest_match(item: Ogtc, sender_id: int):
            if item.tile not in observed or sender_id not in observed[item.tile] or len(observed[item.tile][sender_id]) < 1:
                return None
            return min(observed[item.tile][sender_id], key=lambda o: abs(o.value.min_timestamp - item.ts))

        # Populate ground truth map
        for k in actual.keys():
            actual[k] = list(filter(lambda o: o.tile == k, occupancy_ground_truth))

        # Populate per-vehicle observation maps
        for obs in occupancy_observations:
            sender_id: int = obs.meta['sender']
            parent: QuadKey = obs.meta['parent']

            if parent not in observed:
                continue

            if sender_id not in observed[parent]:
                observed[parent][sender_id] = []

            observed[parent][sender_id].append(obs)
            sender_ids.add(sender_id)

        # Compute match for every cell
        parent_quads: Set[QuadKey] = set(actual.keys()).intersection(set(observed.keys()))
        for parent in tqdm(parent_quads):
            items_actual: List[Ogtc] = sorted(actual[parent], key=attrgetter('ts'))

            # Iterate over ground truth grids at parent tile level
            for i, item_actual in enumerate(items_actual):

                # Consider every vehicle's observations
                for sid in sender_ids:

                    # Find grid (PEMTrafficSceneObservation) for current sender and current parent tile of interest
                    item_observed: PEMTrafficSceneObservation = find_closest_match(item_actual, sid)

                    # Parent tile was not in this vehicle's range
                    if not item_observed:
                        continue

                    # Thin out: we want to avoid having the exact same match multiple times. Therefore, if two ground-truth
                    # items are time-wise closer than the next observation, skip.
                    if i > 0 and abs(item_actual.ts - items_actual[i - 1].ts) < abs(item_actual.ts - item_observed.value.min_timestamp):
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
                        s1: Tuple[float, GridCellState] = (1., GridCellState.OCCUPIED)

                        try:
                            tmp_state: PEMRelation = next(filter(lambda c: c.hash == inthash, item_observed.value.occupancy_grid.cells)).state
                            s2: Tuple[float, GridCellState] = (tmp_state.confidence, tmp_state.object.value)
                        except StopIteration:
                            # Cell was not observed, e.g. because not in any vehicle's field of view -> ignore
                            continue

                        c1: State5Tuple = (qk, s1[0], s1[1], sid, item_actual.ts)
                        c2: State5Tuple = (qk, s2[0], s2[1], sid, item_actual.ts)

                        # A match corresponds to one cell that is (a) actually occupied and (b) contained in the current sender's observed grid
                        # with some state and some confidence
                        matches.add((c1, c2))

        logging.debug(f'Matching has {len(matches)} entries.')

        return matches


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
