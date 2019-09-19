using Go = import "/go.capnp";

@0xe591f23a25bfde75;

$Go.package("schema");
$Go.import("talkycars/server/schema");

using import "vector3d.capnp".Vector3D;

struct RelativeBBox {
    lower @0 :Vector3D;
    higher @1 :Vector3D;
}