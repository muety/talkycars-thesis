@0x9d133106862be018;

using import "ego_vehicle.capnp".EgoVehicle;
using import "occupancy.capnp".OccupancyGrid;

struct TrafficScene {
    timestamp @0 :UInt32;
    measuredBy @1 :EgoVehicle;
    occupancyGrid @2 :OccupancyGrid;
}