from typing import cast

from common.serialization.schema import Vector3D, RelativeBBox, GridCellState
from common.serialization.schema.ego_vehicle import PEMEgoVehicle
from common.serialization.schema.occupancy import PEMOccupancyGrid, PEMGridCell
from common.serialization.schema.relation import PEMRelation

if __name__ == '__main__':
    ego = PEMEgoVehicle()
    ego.id = 1
    ego.color = PEMRelation(
        confidence=1,
        object='blue'
    )
    ego.position = PEMRelation(
        confidence=0.88,
        object=Vector3D((49.553, -112.932111111, 0))
    )
    ego.bounding_box = PEMRelation(
        confidence=1,
        object=RelativeBBox(
            lower=Vector3D((-2.56, -1.48, 0)),
            higher=Vector3D((2.56, 1.48, 1.55))
        )
    )
    ego.velocity = PEMRelation(
        confidence=1,
        object=Vector3D((0, 0, 0))
    )
    ego.acceleration = PEMRelation(
        confidence=1,
        object=Vector3D((0, 0, 0))
    )

    encoded_ego = ego.to_bytes()
    print(len(encoded_ego))

    decoded_ego = cast(PEMEgoVehicle, PEMEgoVehicle.from_bytes(encoded_ego))
    print(decoded_ego.id)
    print(decoded_ego.color.object)
    print(decoded_ego.position.object)
    print(decoded_ego.bounding_box.object)
    print(decoded_ego.acceleration.object)
    print(decoded_ego.velocity.object)

    grid = PEMOccupancyGrid()
    grid.cells = [
        PEMGridCell(hash='3120312', state=PEMRelation(confidence=0.67, object=GridCellState.unknown())),
        PEMGridCell(hash='3120310', state=PEMRelation(confidence=0.92, object=GridCellState.free()))
    ]

    encoded_grid = grid.to_bytes()
    print(len(encoded_grid))

    decoded_grid = PEMOccupancyGrid.from_bytes(encoded_grid)
    print(decoded_grid)
    print(decoded_grid.cells[0].hash)
    print(decoded_grid.cells[0].state.object)