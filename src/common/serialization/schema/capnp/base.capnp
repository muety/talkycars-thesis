@0x9d133106862be018;

using import "actor.capnp".DynamicActor;
using import "occupancy.capnp".OccupancyGrid;

struct TrafficScene {
    timestamp @0 :UInt32;
    measuredBy @1 :DynamicActor;
    occupancyGrid @2 :OccupancyGrid;
}