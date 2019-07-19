@0xdaf7aa50cdd411e4;

# TODO: https://github.com/capnproto/pycapnp/issues/188

using import "vector3d.capnp".Vector3D;
using import "relative_bbox.capnp".RelativeBBox;

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