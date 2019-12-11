@0xc77abe9e219ad98d;

enum OccupancyState {
    free @0;
    occupied @1;
    unknown @2;
}

struct OccupancyStateRelation {
    confidence @0 :Float32;
    object @1 :GridCellState;
}

struct OccupancyCell {
    hash @0 :UInt64;
    state @1 :OccupancyStateRelation;
}

struct OccupancyGrid {
    cells @0 :List(OccupancyCell);
}