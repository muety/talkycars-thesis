using Go = import "/go.capnp";

@0xc77abe9e219ad98d;

$Go.package("schema");
$Go.import("talkycars/server/schema");

using import "relation.capnp".GridCellStateRelation;
using import "relation.capnp".DynamicActorRelation;

enum GridCellState {
    free @0;
    occupied @1;
    unknown @2;
}

struct GridCell {
    hash @0 :UInt64;
    state @1 :GridCellStateRelation;
    occupant @2 :DynamicActorRelation;
}

struct OccupancyGrid {
    cells @0 :List(GridCell);
}