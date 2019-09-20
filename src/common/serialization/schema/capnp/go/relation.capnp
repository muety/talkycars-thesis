using Go = import "/go.capnp";

@0xdaf7aa50cdd411e4;

# TODO: https://github.com/capnproto/pycapnp/issues/188

$Go.package("schema");
$Go.import("talkycars/server/schema");

using import "vector3d.capnp".Vector3D;
using import "relative_bbox.capnp".RelativeBBox;
using import "occupancy.capnp".GridCellState;
using import "actor.capnp".ActorType;
using import "actor.capnp".DynamicActor;

struct TextRelation {
    confidence @0 :Float32;
    object @1 :Text;
}

struct Vector3DRelation {
    confidence @0 :Float32;
    object @1 :Vector3D;
}

struct RelativeBBoxRelation {
    confidence @0 :Float32;
    object @1 :RelativeBBox;
}

struct GridCellStateRelation {
    confidence @0 :Float32;
    object @1 :GridCellState;
}

struct ActorTypeRelation {
    confidence @0 :Float32;
    object @1 :ActorType;
}

struct DynamicActorRelation {
    confidence @0 :Float32;
    object @1 :DynamicActor;
}