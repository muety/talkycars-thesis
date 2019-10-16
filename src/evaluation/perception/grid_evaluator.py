import argparse
import logging
import pickle
import sys
from operator import attrgetter
from typing import List, Tuple, Dict, Set

from tqdm import tqdm

from common.constants import *
from common.quadkey import QuadKey
from common.serialization.schema import GridCellState
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMGridCell
from common.serialization.schema.relation import PEMRelation
from evaluation.perception import OccupancyGroundTruthContainer as Ogtc
from evaluation.perception import OccupancyObservationContainer as Ooc
from evaluation.perception import OccupancyUnfoldedObservationContainer as Ouoc

DATA_DIR = '../../../data/evaluation/perception'

logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)


class GridEvaluator:
    def __init__(self, file_prefix: str, data_dir: str = '/tmp'):
        self.file_prefix: str = file_prefix
        self.data_dir: str = data_dir
        self.data_dir_observed: str = os.path.join(data_dir, 'observed')
        self.data_dir_actual: str = os.path.join(data_dir, 'actual')

    def run(self):
        occupancy_observations: List[Ouoc] = None
        occupancy_ground_truth: List[Ogtc] = None
        occupancy_observations, occupancy_ground_truth = self.read_data()

        logging.info('Computing closest matches between ground truth and observations.')
        matching: [List[Tuple[PEMGridCell, PEMGridCell]]] = self.compute_matching(occupancy_observations, occupancy_ground_truth)

        logging.info('Computing score.')
        mse: float = self.compute_mse(matching)

        logging.info(f'MSE: {mse}')

    def read_data(self) -> Tuple[List[Ouoc], List[Ogtc]]:
        logging.info('Reading directory info.')

        files_observed: List[str] = list(filter(lambda s: s.startswith(self.file_prefix), os.listdir(self.data_dir_observed)))
        files_actual: List[str] = list(filter(lambda s: s.startswith(self.file_prefix), os.listdir(self.data_dir_actual)))

        occupancy_observations: List[Ouoc] = []
        occupancy_ground_truth: List[Ogtc] = []

        logging.info('Reading ground truth.')

        for file_name in files_actual:
            with open(os.path.join(self.data_dir_actual, file_name), 'rb') as f:
                occupancy_ground_truth += pickle.load(f)

        logging.info('Reading and decoding observations.')

        for file_name in files_observed:
            encoded_observations: List[Ooc] = []
            with open(os.path.join(self.data_dir_observed, file_name), 'rb') as f:
                encoded_observations += pickle.load(f)

            for o in encoded_observations:
                try:
                    cells = PEMTrafficScene.from_bytes(o.msg).occupancy_grid.cells
                    occupancy_observations.append(Ouoc(
                        cells=cells,
                        tile=o.tile,
                        ts=o.ts
                    ))
                except KeyError:
                    continue

        return occupancy_observations, occupancy_ground_truth

    @staticmethod
    def compute_mse(matching: List[Tuple[PEMGridCell, PEMGridCell]]) -> float:
        error_sum: float = 0
        for m in matching:
            error_sum += (m[0].state.confidence - m[1].state.confidence) ** 2 if m[0].state.object == m[1].state.object else 1
        return error_sum / len(matching)

    @staticmethod
    def compute_matching(occupancy_observations: List[Ouoc], occupancy_ground_truth: List[Ogtc]) -> List[Tuple[PEMGridCell, PEMGridCell]]:
        # Simply use PEMGridCell class as a container here
        matches: List[Tuple[PEMGridCell, PEMGridCell]] = []

        observed: Dict[QuadKey, List[Ouoc]] = dict.fromkeys(map(attrgetter('tile'), occupancy_observations), [])
        actual: Dict[QuadKey, List[Ogtc]] = dict.fromkeys(map(attrgetter('tile'), occupancy_ground_truth), [])

        def find_closest_match(key: QuadKey, item: Ogtc):
            return min(observed[key], key=lambda o: abs(o.ts - item.ts))

        for k in observed.keys():
            observed[k] = list(filter(lambda o: o.tile == k, occupancy_observations))

        for k in actual.keys():
            actual[k] = list(filter(lambda o: o.tile == k, occupancy_ground_truth))

        parents: Set[QuadKey] = set(actual.keys()).intersection(set(observed.keys()))
        total: int = len(parents) * 4 ** (OCCUPANCY_TILE_LEVEL - REMOTE_GRID_TILE_LEVEL)

        with tqdm(total=total) as pbar:
            for parent in parents:
                items_actual: List[Ogtc] = actual[parent]
                children: List[QuadKey] = parent.children(at_level=OCCUPANCY_TILE_LEVEL)

                for item_actual in items_actual:
                    item_observed: Ouoc = find_closest_match(parent, item_actual)

                    for qk in children:
                        inthash: int = qk.to_quadint()

                        if qk in item_actual.occupied_cells:
                            s1: PEMRelation[GridCellState] = PEMRelation(1., GridCellState.occupied())
                        else:
                            s1: PEMRelation[GridCellState] = PEMRelation(1., GridCellState.unknown())

                        try:
                            s2: PEMRelation[GridCellState] = next(filter(lambda c: c.hash == inthash, item_observed.cells)).state
                        except StopIteration:
                            s2: PEMRelation[GridCellState] = PEMRelation(1., GridCellState.unknown())

                        c1: PEMGridCell = PEMGridCell(**{'hash': inthash, 'state': s1})
                        c2: PEMGridCell = PEMGridCell(**{'hash': inthash, 'state': s2})

                        matches.append((c1, c2))

                        pbar.update(1)

        return matches


def run(args=sys.argv[1:]):
    argparser = argparse.ArgumentParser(description='TalkyCars Grid Evaluator')
    argparser.add_argument('-p', '--file_prefix', required=True, type=str, help='File prefix of the data collection to be read (e.g. "120203233231202_2019-10-15_15-46-00")')
    argparser.add_argument('-d', '--in_dir', default=DATA_DIR, type=str, help='Directory to read data from')

    args, _ = argparser.parse_known_args(args)

    GridEvaluator(
        file_prefix=args.file_prefix,
        data_dir=os.path.normpath(
            os.path.join(os.path.dirname(__file__), args.in_dir)
        )
    ).run()


if __name__ == '__main__':
    run()
