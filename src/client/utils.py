from typing import List, Dict, Tuple, FrozenSet

from common import quadkey
from common.constants import *
from common.model import DynamicActor
from common.quadkey import QuadKey
from common.serialization.schema import RelativeBBox, Vector3D, ActorType
from common.serialization.schema.actor import PEMDynamicActor
from common.serialization.schema.relation import PEMRelation
from common.util import GeoUtils


class ClientUtils:
    @staticmethod
    def map_pem_actor(actor: DynamicActor) -> PEMDynamicActor:
        bbox_corners = (
            GeoUtils.gnss_add_meters(actor.gnss.value.components(), actor.props.extent.value.components(), delta_factor=-1),
            GeoUtils.gnss_add_meters(actor.gnss.value.components(), actor.props.extent.value.components())
        )
        bbox = RelativeBBox(lower=Vector3D(bbox_corners[0]), higher=Vector3D(bbox_corners[1]))

        return PEMDynamicActor(
            id=actor.id,
            type=PEMRelation(confidence=actor.type.confidence, object=ActorType(actor.type.value)),
            position=PEMRelation(confidence=actor.gnss.confidence, object=Vector3D(actor.gnss.value.components())),
            color=PEMRelation(confidence=actor.props.color.confidence, object=actor.props.color.value),
            bounding_box=PEMRelation(confidence=actor.props.extent.confidence, object=bbox),
            velocity=PEMRelation(confidence=actor.dynamics.velocity.confidence, object=Vector3D(actor.dynamics.velocity.value.components())),
            acceleration=PEMRelation(confidence=actor.dynamics.acceleration.confidence, object=Vector3D(actor.dynamics.acceleration.value.components()))
        )

        # TODO: Maybe abstract from Carla-specific classes?

    @staticmethod
    def get_occupied_cells(for_actor: DynamicActor) -> FrozenSet[QuadKey]:
        c1: Tuple[float, float] = GeoUtils.gnss_add_meters(for_actor.gnss.value.components(), for_actor.props.extent.value.components(), perm=(1, 0, 2))[:2]
        c2: Tuple[float, float] = GeoUtils.gnss_add_meters(for_actor.gnss.value.components(), for_actor.props.extent.value.components(), perm=(1, 0, 2), delta_factor=-1)[:2]
        c3: Tuple[float, float] = (c1[0], c2[1])
        c4: Tuple[float, float] = (c2[0], c1[1])

        qks: List[QuadKey] = list(map(lambda c: quadkey.from_geo(c, OCCUPANCY_TILE_LEVEL), [c1, c2, c3, c4]))
        qks += qks[0].difference(qks[1])
        qks += qks[2].difference(qks[3])
        qks += qks[0].difference(qks[2])
        qks += qks[1].difference(qks[3])

        return frozenset(qks)

    @classmethod
    # Assumes that a cell is tiny enough to contain at max one actor
    def get_occupied_cells_multi(cls, for_actors: List[DynamicActor]) -> Dict[str, DynamicActor]:
        matches: Dict[str, DynamicActor] = {}

        for a in for_actors:
            for c in cls.get_occupied_cells(a):
                matches[c.key] = a

        return matches
