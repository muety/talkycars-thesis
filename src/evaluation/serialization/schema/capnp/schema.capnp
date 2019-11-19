# capnp compile -I$GOPATH/src/zombiezen.com/go/capnproto2/std -ogo:./schema/capnp --src-prefix ./schema/capnp ./schema/capnp/*.capnp

using Go = import "/go.capnp";

@0xc77abe9e219ad98d;

$Go.package("schema");
$Go.import("talkycars/server/schema");

enum GridCellState {
    free @0;
    occupied @1;
    unknown @2;
}

struct GridCellStateRelation {
    confidence @0 :Float32;
    object @1 :GridCellState;
}

struct GridCell {
    hash @0 :UInt64;
    state @1 :GridCellStateRelation;
}

struct OccupancyGrid {
    cells @0 :List(GridCell);
}