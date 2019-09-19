using Go = import "/go.capnp";

@0xdb0016c88e4a89be;

$Go.package("schema");
$Go.import("talkycars/server/schema");

using import "relation.capnp".Vector3DRelation;
using import "relation.capnp".TextRelation;
using import "relation.capnp".RelativeBBoxRelation;
using import "relation.capnp".ActorTypeRelation;

enum ActorType {
    vehicle @0;
    pedestrian @1;
    unknown @2;
}

struct DynamicActor {
    id @0 :UInt32;
    type @1 :ActorTypeRelation;
    position @2 :Vector3DRelation;
    color @3 :TextRelation;
    boundingBox @4 :RelativeBBoxRelation;
    velocity @5 :Vector3DRelation;
    acceleration @6 :Vector3DRelation;
}