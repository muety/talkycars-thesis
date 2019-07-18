@0xdb0016c88e4a89be;

using import "vector3d.capnp".Vector3D;
using import "coordinate.capnp".Coordinate;
using import "relation.capnp".Relation;

struct EgoVehicle {
    id @0 :UInt32;
    position @1 :Relation(Coordinate);
    color @2 :Relation(Text);
    boundingBox @3 :Relation(List(Coordinate));
    velocity @4 :Relation(Vector3D);
    acceleration @5 :Relation(Vector3D);
}