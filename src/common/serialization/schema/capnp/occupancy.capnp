@0xc77abe9e219ad98d;

using import "relation.capnp".GridCellStateRelation;

enum GridCellState {
    free @0;
    occupied @1;
    unknown @2;
}

struct GridCell {
    hash @0 :Text;
    state @1 :GridCellStateRelation;
}

struct OccupancyGrid {
    cells @0 :List(GridCell);
}