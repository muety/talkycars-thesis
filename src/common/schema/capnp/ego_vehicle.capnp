@0xdb0016c88e4a89be;

using import "vector3d.capnp".Vector3D;
using import "coordinate.capnp".Coordinate;
using import "relation.capnp".CoordinateRelation;
using import "relation.capnp".Vector3DRelation;
using import "relation.capnp".TextRelation;
using import "relation.capnp".RelativeBBoxRelation;

struct EgoVehicle {
    id @0 :UInt32;
    position @1 :CoordinateRelation;
    color @2 :TextRelation;
    boundingBox @3 :RelativeBBoxRelation;
    velocity @4 :Vector3DRelation;
    acceleration @5 :Vector3DRelation;
}