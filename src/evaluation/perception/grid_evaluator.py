import argparse
import logging
import pickle
import sys
from itertools import chain
from multiprocessing.pool import Pool
from operator import attrgetter
from typing import List, Tuple, Dict, Union

from tqdm import tqdm

from common.constants import *
from common.occupancy import GridCellState
from common.quadkey import QuadKey
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.relation import PEMRelation
from evaluation.perception import OccupancyGroundTruthContainer as Ogtc
from evaluation.perception import OccupancyObservationContainer as Ooc
from evaluation.perception import OccupancyUnfoldedObservationContainer as Ouoc

DATA_DIR = '../../../data/evaluation/perception'

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

# TODO: Multi-threading
# TODO: Optimize Big-O complexity

StateTriple = Tuple[QuadKey, float, GridCellState]

class GridEvaluator:
    def __init__(self, file_prefix: str, data_dir: str = '/tmp'):
        self.file_prefix: str = file_prefix
        self.data_dir: str = data_dir
        self.data_dir_actual: str = os.path.join(data_dir, 'actual')
        self.data_dir_observed: str = os.path.join(data_dir, 'observed')
        self.data_dir_observed_local: str = os.path.join(self.data_dir_observed, 'local')
        self.data_dir_observed_remote: str = os.path.join(self.data_dir_observed, 'remote')

    def run(self):
        occupancy_observations: List[Ouoc] = None
        occupancy_ground_truth: List[Ogtc] = None
        occupancy_observations, occupancy_ground_truth = self.read_data()

        logging.info('Computing closest matches between ground truth and observations.')
        matching: [List[Tuple[StateTriple, StateTriple]]] = self.compute_matching(occupancy_observations, occupancy_ground_truth)

        logging.info('Computing score.')
        mse: float = self.compute_mse(matching)
        mae: float = self.compute_mae(matching)

        logging.info(f'MSE: {mse}, MAE: {mae}')

    def read_data(self) -> Tuple[List[Ouoc], List[Ogtc]]:
        pool: Pool = Pool()

        logging.info('Reading directory info.')

        files_observed: List[str] = list(filter(lambda s: s.startswith(self.file_prefix), os.listdir(self.data_dir_observed_remote)))
        files_actual: List[str] = list(filter(lambda s: s.startswith(self.file_prefix), os.listdir(self.data_dir_actual)))

        occupancy_observations: List[Ouoc] = []
        occupancy_ground_truth: List[Ogtc] = []

        logging.info('Reading ground truth.')

        for file_name in files_actual:
            with open(os.path.join(self.data_dir_actual, file_name), 'rb') as f:
                occupancy_ground_truth += pickle.load(f)

        logging.info(f'Reading and decoding observations.')

        with tqdm(total=len(files_observed)) as pbar:
            for file_name in files_observed:
                encoded_observations: List[Ooc] = []
                with open(os.path.join(self.data_dir_observed_remote, file_name), 'rb') as f:
                    encoded_observations += pickle.load(f)

                batch_size: int = len(encoded_observations) // os.cpu_count()
                batches: List[List[Ooc]] = [encoded_observations[i * batch_size:(i + 1) * batch_size] for i in range((len(encoded_observations) // batch_size) + 1)]
                occupancy_observations += list(chain(*pool.map(self.decode_oocs, batches)))
                pbar.update(1)

        return occupancy_observations, occupancy_ground_truth

    @classmethod
    def decode_oocs(cls, obs: List[Ooc]) -> List[Ouoc]:
        return list(filter(lambda m: m is not None, map(cls.decode_ooc, obs)))

    @staticmethod
    def decode_ooc(obs: Ooc) -> Union[Ouoc, None]:
        try:
            return Ouoc(PEMTrafficScene.from_bytes(obs.msg).occupancy_grid.cells, obs.tile, obs.ts)
        except KeyError:
            return None

    @staticmethod
    def compute_mse(matching: List[Tuple[StateTriple, StateTriple]]) -> float:
        error_sum: float = 0
        for m in matching:
            error_sum += (m[0][1] - m[1][1]) ** 2 if m[0][2] == m[1][2] else 1
        return error_sum / len(matching)

    @staticmethod
    def compute_mae(matching: List[Tuple[StateTriple, StateTriple]]) -> float:
        error_sum: float = 0
        for m in matching:
            error_sum += abs(m[0][1] - m[1][1]) if m[0][2] == m[1][2] else 1
        return error_sum / len(matching)

    @staticmethod
    def compute_matching(occupancy_observations: List[Ouoc], occupancy_ground_truth: List[Ogtc]) -> List[Tuple[StateTriple, StateTriple]]:
        total: int = 0
        matches: List[Tuple[StateTriple, StateTriple]] = []

        observed: Dict[QuadKey, List[Ouoc]] = dict.fromkeys(map(attrgetter('tile'), occupancy_observations), [])
        actual: Dict[QuadKey, List[Ogtc]] = dict.fromkeys(map(attrgetter('tile'), occupancy_ground_truth), [])

        def find_closest_match(item: Ogtc):
            return min(observed[item.tile], key=lambda o: abs(o.ts - item.ts))

        for k in observed.keys():
            observed[k] = list(filter(lambda o: o.tile == k, occupancy_observations))

        for k in actual.keys():
            actual[k] = list(filter(lambda o: o.tile == k, occupancy_ground_truth))
            total += len(actual[k])

        for parent in set(actual.keys()).intersection(set(observed.keys())):
            items_actual: List[Ogtc] = actual[parent]

            for item_actual in items_actual:
                item_observed: Ouoc = find_closest_match(item_actual)

                for qk in item_actual.occupied_cells:
                    if not qk.key.startswith(parent):
                        continue

                    inthash: int = qk.to_quadint()

                    # Currently, only occupied cells (~ false negatives) are considered
                    s1: Tuple[float, GridCellState] = (1., GridCellState.OCCUPIED)

                    try:
                        tmp_state: PEMRelation = next(filter(lambda c: c.hash == inthash, item_observed.cells)).state
                        s2: Tuple[float, GridCellState] = (tmp_state.confidence, tmp_state.object.value)
                    except StopIteration:
                        # Cell was not observed, e.g. because not in any vehicle's field of view -> ignore
                        continue

                    c1: StateTriple = (qk, s1[0], s1[1])
                    c2: StateTriple = (qk, s2[0], s2[1])

                    matches.append((c1, c2))

        return matches


def run(args=sys.argv[1:]):
    argparser = argparse.ArgumentParser(description='TalkyCars Grid Evaluator')
    argparser.add_argument('-p', '--file_prefix', required=True, type=str, help='File prefix of the data collection to be read (e.g. "120203233231202_2019-10-15_15-46-00")')
    argparser.add_argument('-d', '--in_dir', default=EVAL2_DATA_DIR, type=str, help='Directory to read data from')

    args, _ = argparser.parse_known_args(args)

    GridEvaluator(
        file_prefix=args.file_prefix,
        data_dir=os.path.normpath(
            os.path.join(os.path.dirname(__file__), args.in_dir)
        )
    ).run()


if __name__ == '__main__':
    run()
