using Go = import "/go.capnp";

@0x9d133106862be018;

$Go.package("schema");
$Go.import("talkycars/server/schema");

using import "actor.capnp".DynamicActor;
using import "occupancy.capnp".OccupancyGrid;

struct TrafficScene {
    timestamp @0 :Float64;
    minTimestamp @1 :Float64;
    measuredBy @2 :DynamicActor;
    occupancyGrid @3 :OccupancyGrid;
}