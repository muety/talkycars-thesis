using Go = import "/go.capnp";

@0xeaa9f019f64e1e95;

$Go.package("schema");
$Go.import("talkycars/server/schema");

struct Vector3D {
    x @0 :Float64;
    y @1 :Float64;
    z @2 :Float64;
}