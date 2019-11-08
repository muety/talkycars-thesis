from typing import List, Tuple, Set

from pyquadkey2.quadkey import QuadKey

from common.observation import PEMTrafficSceneObservation
from common.serialization.schema import GridCellState
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMOccupancyGrid, PEMGridCell
from common.serialization.schema.relation import PEMRelation
from evaluation.perception import OccupancyGroundTruthContainer as Ogtc
from evaluation.perception.grid_evaluator import GridEvaluator, State5Tuple

REF_TIME_1: float = 1573220495.8997931
REF_PARENT_1: QuadKey = QuadKey('120203233')
REF_TILE_1_1: QuadKey = QuadKey('1202032330')
REF_TILE_1_2: QuadKey = QuadKey('1202032331')

MOCK_ACTUAL_1: List[Ogtc] = [Ogtc(
    tile=REF_PARENT_1,
    occupied_cells=frozenset([REF_TILE_1_1]),
    ts=REF_TIME_1
)]

MOCK_LOCAL_1: List[PEMTrafficSceneObservation] = [
    PEMTrafficSceneObservation(
        timestamp=REF_TIME_1 + 1.0,
        scene=PEMTrafficScene(
            timestamp=REF_TIME_1 + 0.15,
            occupancy_grid=PEMOccupancyGrid(
                cells=[
                    PEMGridCell(
                        hash=REF_TILE_1_1.to_quadint(),
                        state=PEMRelation(confidence=.5, object=GridCellState.occupied())
                    ),
                    PEMGridCell(
                        hash=REF_TILE_1_2.to_quadint(),
                        state=PEMRelation(confidence=.5, object=GridCellState.free())
                    )
                ]
            )
        ),
        meta={'sender': 1, 'parent': REF_PARENT_1}
    ),
    PEMTrafficSceneObservation(
        timestamp=REF_TIME_1 + 2.0,
        scene=PEMTrafficScene(),
        meta={'sender': 1, 'parent': REF_PARENT_1}
    )
]

MOCK_REMOTE_1: List[PEMTrafficSceneObservation] = [
    PEMTrafficSceneObservation(
        timestamp=REF_TIME_1 + 1.1,
        scene=PEMTrafficScene(
            timestamp=REF_TIME_1 + 0.3,
            min_timestamp=REF_TIME_1 + 0.1,
            max_timestamp=REF_TIME_1 + 0.15,
            occupancy_grid=PEMOccupancyGrid(
                cells=[
                    PEMGridCell(
                        hash=REF_TILE_1_1.to_quadint(),
                        state=PEMRelation(confidence=.5, object=GridCellState.free())
                    )
                ]
            )
        ),
        meta={'sender': 1, 'parent': REF_PARENT_1}
    )
]

MOCK_REMOTE_2: List[PEMTrafficSceneObservation] = [
    PEMTrafficSceneObservation(
        timestamp=REF_TIME_1 + 1.1,
        scene=PEMTrafficScene(
            timestamp=REF_TIME_1 + 0.3,
            min_timestamp=REF_TIME_1 + 0.1,
            max_timestamp=REF_TIME_1 + 0.15,
            occupancy_grid=PEMOccupancyGrid(
                cells=[
                    PEMGridCell(
                        hash=REF_TILE_1_1.to_quadint(),
                        state=PEMRelation(confidence=1, object=GridCellState.unknown())
                    )
                ]
            )
        ),
        meta={'sender': 1, 'parent': REF_PARENT_1}
    )
]


def test_compute_matching():
    sut: GridEvaluator = GridEvaluator(file_prefix='')

    matching: List[Tuple[State5Tuple, State5Tuple]] = list(sut.compute_matching(MOCK_LOCAL_1, [], MOCK_ACTUAL_1))
    assert len(matching) == 1
    assert matching[0][0][1] == 1.0
    assert matching[0][1][1] == 0.5

    matching: List[Tuple[State5Tuple, State5Tuple]] = list(sut.compute_matching(MOCK_LOCAL_1, MOCK_REMOTE_1, MOCK_ACTUAL_1))
    assert len(matching) == 1
    assert matching[0][0][1] == 1.0
    assert .24 < matching[0][1][1] < .26
    assert matching[0][1][2] == GridCellState.occupied()


def test_override_unknown():
    sut: GridEvaluator = GridEvaluator(file_prefix='')

    matching: List[Tuple[State5Tuple, State5Tuple]] = list(sut.compute_matching(MOCK_LOCAL_1, MOCK_REMOTE_2, MOCK_ACTUAL_1))
    assert len(matching) == 1
    assert matching[0][0][1] == 1.0
    assert .4 < matching[0][1][1] < .6
    assert matching[0][1][2] == GridCellState.occupied()


def test_compute_scores():
    sut: GridEvaluator = GridEvaluator(file_prefix='')

    matching: Set[Tuple[State5Tuple, State5Tuple]] = sut.compute_matching(MOCK_LOCAL_1, [], MOCK_ACTUAL_1)
    acc: float = sut.compute_accuracy(matching)
    mae: float = sut.compute_mae(matching)
    assert acc == 1
    assert mae == 0.5

    matching: Set[Tuple[State5Tuple, State5Tuple]] = sut.compute_matching(MOCK_LOCAL_1, MOCK_REMOTE_1, MOCK_ACTUAL_1)
    acc: float = sut.compute_accuracy(matching)
    mae: float = sut.compute_mae(matching)
    assert acc == 1
    assert .74 < mae < .76


if __name__ == '__main__':
    test_compute_matching()
    test_override_unknown()
    test_compute_scores()
