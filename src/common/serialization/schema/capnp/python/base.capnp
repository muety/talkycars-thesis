@0x9d133106862be018;

using import "actor.capnp".DynamicActor;
using import "occupancy.capnp".OccupancyGrid;

struct TrafficScene {
    timestamp @0 :Float64;
    minTimestamp @1 :Float64;
    maxTimestamp @2 :Float64;
    lastTimestamp @3 :Float64;
    measuredBy @4 :DynamicActor;
    occupancyGrid @5 :OccupancyGrid;
}