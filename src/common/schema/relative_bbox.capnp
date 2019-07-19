@0xe591f23a25bfde75;

using import "vector3d.capnp".Vector3D;

struct RelativeBBox {
    lower @0 :Vector3D;
    higher @1 :Vector3D;
}