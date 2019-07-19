import os
from typing import cast

import capnp

from common.serialization.schema import Vector3D, RelativeBBox
from common.serialization.schema.ego_vehicle import PEMEgoVehicle
from common.serialization.schema.relation import PEMRelation

capnp.remove_import_hook()

dirname = os.path.dirname(__file__)
ego_vehicle = capnp.load(os.path.join(dirname, './capnp/ego_vehicle.capnp'))

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

    decoded_message = ego_vehicle.EgoVehicle.from_bytes_packed(encoded_ego)

    decoded_ego = cast(PEMEgoVehicle, PEMEgoVehicle.from_bytes(encoded_ego))
    print(decoded_ego.id)
    print(decoded_ego.color.object)
    print(decoded_ego.position.object)
    print(decoded_ego.bounding_box.object)
    print(decoded_ego.acceleration.object)
    print(decoded_ego.velocity.object)