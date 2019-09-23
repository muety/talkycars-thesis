// Plain class instantiation is almost 3x as fast as with Cap'n'Proto classes.

package main

import (
	"fmt"
	"math/rand"
	"sync"
	"time"

	"./schema"

	capnp "zombiezen.com/go/capnproto2"
)

const letterBytes = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

type GridCell struct {
	Hash  string
	State int
	Conf  float64
}

type Grid struct {
	Cells []GridCell
}

func CreatePlain() {
	grid := Grid{}
	cells := make([]GridCell, 100, 100)
	for i := 0; i < 100; i++ {
		cells = append(cells, GridCell{Hash: RandString(3), State: 1, Conf: 0.95})
	}
	grid.Cells = cells
}

func CreateCapnp() {
	_, seg, _ := capnp.NewMessage(capnp.SingleSegment(nil))
	grid, err := schema.NewRootOccupancyGrid(seg)
	if err != nil {
		panic(err)
	}

	cells, err := grid.NewCells(100)
	if err != nil {
		panic(err)
	}

	for i := 0; i < cells.Len(); i++ {
		c, err := schema.NewGridCell(cells.Segment())
		if err != nil {
			panic(err)
		}

		c.SetHash(RandString(3))
		cells.Set(i, c)
	}
}

func RandString(n int) string {
	b := make([]byte, n)
	for i := range b {
		b[i] = letterBytes[rand.Intn(len(letterBytes))]
	}
	return string(b)
}

func main() {
	N := 100000
	var wg sync.WaitGroup
	var d0, d1 time.Duration

	wg.Add(2)

	go func() {
		defer wg.Done()
		t0 := time.Now()
		for i := 0; i < N; i++ {
			CreatePlain()
		}
		d0 = time.Since(t0)
	}()

	go func() {
		defer wg.Done()
		t0 := time.Now()
		for i := 0; i < N; i++ {
			CreateCapnp()
		}
		d1 = time.Since(t0)
	}()

	wg.Wait()

	avg0 := float64(N) / d0.Seconds()
	avg1 := float64(N) / d1.Seconds()

	fmt.Printf("CreatePlain: %v (%v)\nCreateCapnp: %v (%v)\n", avg0, d0, avg1, d1)
}
