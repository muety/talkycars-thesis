from typing import List

from common.serialization.schema import Vector3D, RelativeBBox, ActorType, GridCellState
from common.serialization.schema.actor import PEMDynamicActor
from common.serialization.schema.base import PEMTrafficScene
from common.serialization.schema.occupancy import PEMOccupancyGrid, PEMGridCell
from common.serialization.schema.relation import PEMRelation

if __name__ == '__main__':
    ego1: PEMDynamicActor = PEMDynamicActor(
        id=1337,
        type=PEMRelation[ActorType](confidence=1, object=ActorType.vehicle()),
        color=PEMRelation[str](confidence=1, object='blue'),
        position=PEMRelation[Vector3D](confidence=1, object=Vector3D((49.1, -122.2, 0))),
        bounding_box=PEMRelation[RelativeBBox](confidence=1, object=RelativeBBox(
            lower=Vector3D((-1, -1, -1)),
            higher=Vector3D((1, 1, 1))
        ))
    )

    ego2: PEMDynamicActor = PEMDynamicActor(
        id=1338,
        type=PEMRelation[ActorType](confidence=.8, object=ActorType.vehicle()),
        color=PEMRelation[str](confidence=.54, object='red')
    )

    grid1: PEMOccupancyGrid = PEMOccupancyGrid()
    cells: List[PEMGridCell] = [
        PEMGridCell(**{
            'hash': 1111,
            'state': PEMRelation[GridCellState](confidence=0.65, object=GridCellState.occupied()),
            'occupant': PEMRelation[PEMDynamicActor](confidence=0.91, object=ego2)
        }),
        PEMGridCell(**{
            'hash': 2222,
            'state': PEMRelation[GridCellState](confidence=0.88, object=GridCellState.free()),
            'occupant': None
        })
    ]
    grid1.cells = cells

    scene1: PEMTrafficScene = PEMTrafficScene()
    scene1.occupancy_grid = grid1
    scene1.measured_by = ego1

    encoded_msg: bytes = scene1.to_bytes()

    scene1: PEMTrafficScene = PEMTrafficScene.from_bytes(encoded_msg)
    print(scene1.measured_by.id)
    print(scene1.measured_by.position.object.x)
    print(scene1.occupancy_grid.cells[0].state.confidence)
    print(scene1.occupancy_grid.cells[0].state.object)
    print(scene1.occupancy_grid.cells[0].occupant.object.id)
