from common.serialization.schema import Vector3D, RelativeBBox, GridCellState
from common.serialization.schema.base import PEMTrafficScene
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

    grid = PEMOccupancyGrid()
    grid.cells = [
        PEMGridCell(hash='3120312', state=PEMRelation(confidence=0.67, object=GridCellState.unknown())),
        PEMGridCell(hash='3120310', state=PEMRelation(confidence=0.92, object=GridCellState.free()))
    ]

    scene = PEMTrafficScene(
        measured_by=ego,
        occupancy_grid=grid
    )

    encoded_msg = scene.to_bytes()
    print(len(encoded_msg))

    decoded_msg = PEMTrafficScene.from_bytes(encoded_msg)
    print(decoded_msg)
    print(decoded_msg.occupancy_grid)
    print(decoded_msg.occupancy_grid.cells[0].hash)
    print(decoded_msg.occupancy_grid.cells[0].state.object)
    print(decoded_msg.measured_by.id)
    print(decoded_msg.measured_by.color.object)
    print(decoded_msg.measured_by.position.object)
    print(decoded_msg.measured_by.bounding_box.object)
    print(decoded_msg.measured_by.acceleration.object)
    print(decoded_msg.measured_by.velocity.object)