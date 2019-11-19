package main

import (
	pb "./schema/protobuf"
	"github.com/golang/protobuf/proto"
	"math/rand"
)

func CreateProto() []byte {
	cells := make([]*pb.GridCell, NCells, NCells)

	for i := 0; i < NCells; i++ {
		cells[i] = &pb.GridCell{
			Hash: uint64(rand.Int()),
			State: &pb.GridCellStateRelation{
				Confidence: rand.Float32(),
				Object:     pb.GridCellState_FREE,
			},
		}
	}

	grid := &pb.OccupancyGrid{
		Cells: cells,
	}

	out, err := proto.Marshal(grid)
	if err != nil {
		panic(err)
	}

	return out
}
