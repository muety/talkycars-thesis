from typing import List, Dict, Tuple

from common import quadkey, occupancy
from common.constants import *
from common.model import DynamicActor
from common.occupancy import Grid
from common.quadkey import QuadKey
from common.serialization.schema import RelativeBBox, Vector3D, ActorType
from common.serialization.schema.actor import PEMDynamicActor
from common.serialization.schema.relation import PEMRelation
from common.util import GeoUtils


class ClientUtils:
    @staticmethod
    def map_pem_actor(actor: DynamicActor) -> PEMDynamicActor:
        bbox_corners = (
            GeoUtils.gnss_add_meters(actor.gnss.value.components(), actor.props.extent.value, delta_factor=-1),
            GeoUtils.gnss_add_meters(actor.gnss.value.components(), actor.props.extent.value)
        )
        bbox = RelativeBBox(lower=Vector3D(bbox_corners[0]), higher=Vector3D(bbox_corners[1]))

        return PEMDynamicActor(
            id=actor.id,
            type=PEMRelation(confidence=actor.type.confidence, object=ActorType(actor.type.value)),
            position=PEMRelation(confidence=actor.gnss.confidence, object=Vector3D(actor.gnss.value.components())),
            color=PEMRelation(confidence=actor.props.color.confidence, object=actor.props.color.value),
            bounding_box=PEMRelation(confidence=actor.props.extent.confidence, object=bbox),
            velocity=PEMRelation(confidence=actor.dynamics.velocity.confidence, object=Vector3D(actor.dynamics.velocity.value)),
            acceleration=PEMRelation(confidence=actor.dynamics.acceleration.confidence, object=Vector3D(actor.dynamics.acceleration.value))
        )

        # TODO: Maybe abstract from Carla-specific classes?

    @staticmethod
    def match_actors_with_grid(grid: Grid, actors: List[DynamicActor]) -> Dict[str, List[DynamicActor]]:
        matches: Dict[str, List[DynamicActor]] = {}

        for a in actors:
            c1: Tuple[float, float] = GeoUtils.gnss_add_meters(a.gnss.value.components(), a.props.extent.value, delta_factor=-1)[:2]
            c2: Tuple[float, float] = GeoUtils.gnss_add_meters(a.gnss.value.components(), a.props.extent.value)[:2]
            c3: Tuple[float, float] = (c1[0], c2[1])
            c4: Tuple[float, float] = (c2[0], c1[1])
            quadkeys: List[QuadKey] = list(map(lambda c: quadkey.from_geo(c, OCCUPANCY_TILE_LEVEL), [c1, c2, c3, c4]))

            for qk in quadkeys:
                for cell in grid.cells:
                    if cell.quad_key.key not in matches:
                        matches[cell.quad_key.key] = []

                    if cell.state.value is not occupancy.GridCellState.OCCUPIED:
                        continue

                    if cell.quad_key == qk:
                        matches[cell.quad_key.key].append(a)

        return matches
