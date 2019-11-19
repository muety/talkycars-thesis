package main

import (
	"bytes"
	"encoding/gob"
	"math/rand"
)

type GridCellState uint16

const (
	GridCellState_free     GridCellState = 0
	GridCellState_occupied GridCellState = 1
	GridCellState_unknown  GridCellState = 2
)

type GridCellStateRelation struct {
	Confidence float32
	Object     GridCellState
}

type GridCell struct {
	Hash  uint64
	State GridCellStateRelation
}

type Grid struct {
	Cells []GridCell
}

func CreateGob() []byte {
	var outBuf bytes.Buffer
	enc := gob.NewEncoder(&outBuf)

	cells := make([]GridCell, NCells, NCells)

	for i := 0; i < NCells; i++ {
		cells[i] = GridCell{
			Hash: uint64(rand.Int()),
			State: GridCellStateRelation{
				Confidence: rand.Float32(),
				Object:     GridCellState_free,
			},
		}
	}

	grid := Grid{
		Cells: cells,
	}

	err := enc.Encode(&grid)
	if err != nil {
		panic(err)
	}

	return outBuf.Bytes()
}
