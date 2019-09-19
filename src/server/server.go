package main

import (
	"fmt"

	"./schema"
	capnp "zombiezen.com/go/capnproto2"
)

func check(err error) {
	if err != nil {
		panic(err)
	}
}

func main() {
	// Encode
	msgIn, seg, err := capnp.NewMessage(capnp.SingleSegment(nil))
	check(err)

	cellIn, err := schema.NewRootGridCell(seg)
	check(err)

	state, err := cellIn.NewState()
	check(err)
	state.SetObject(schema.GridCellState_free)
	state.SetConfidence(0.8)

	cellIn.SetHash("3s57dr6czigvuhj")
	cellIn.SetState(state)

	encodedMsg, err := msgIn.MarshalPacked()
	check(err)

	// Decode
	decodedMsg, err := capnp.UnmarshalPacked(encodedMsg)
	check(err)

	cellOut, err := schema.ReadRootGridCell(decodedMsg)
	check(err)

	state, err = cellOut.State()
	fmt.Println(state.Object())
}
