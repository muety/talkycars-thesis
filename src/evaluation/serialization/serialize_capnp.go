// Plain class instantiation is almost 3x as fast as with Cap'n'Proto classes.

package main

import (
	"math/rand"

	schema "./schema/capnp"

	capnp "zombiezen.com/go/capnproto2"
)

func CreateCapnp() []byte {
	msg, seg, _ := capnp.NewMessage(capnp.SingleSegment(nil))
	grid, err := schema.NewRootOccupancyGrid(seg)
	if err != nil {
		panic(err)
	}

	cells, err := grid.NewCells(int32(NCells))
	if err != nil {
		panic(err)
	}

	for i := 0; i < cells.Len(); i++ {
		c, err := schema.NewGridCell(cells.Segment())
		if err != nil {
			panic(err)
		}

		c.SetHash(uint64(rand.Int()))

		state, err := c.NewState()
		if err != nil {
			panic(err)
		}

		state.SetConfidence(rand.Float32())
		state.SetObject(schema.GridCellState_free)

		cells.Set(i, c)
	}

	out, err := msg.MarshalPacked()
	if err != nil {
		panic(err)
	}

	return out
}
