// go run serialize_gob.go serialize_capnp.go serialize_protobuf.go serialize.go

package main

import (
	"fmt"
	"sync"
	"sync/atomic"
	"time"
)

const (
	N      int = 100000
	NCells int = 441
)

func main() {
	var wg sync.WaitGroup
	var d0, d1, d2 time.Duration
	var b0, b1, b2 uint64

	wg.Add(3)

	go func() {
		defer wg.Done()
		t0 := time.Now()
		for i := 0; i < N; i++ {
			atomic.AddUint64(&b0, uint64(len(CreateGob())))
		}
		d0 = time.Since(t0)
	}()

	go func() {
		defer wg.Done()
		t0 := time.Now()
		for i := 0; i < N; i++ {
			atomic.AddUint64(&b1, uint64(len(CreateCapnp())))
		}
		d1 = time.Since(t0)
	}()

	go func() {
		defer wg.Done()
		t0 := time.Now()
		for i := 0; i < N; i++ {
			atomic.AddUint64(&b2, uint64(len(CreateProto())))
		}
		d2 = time.Since(t0)
	}()

	wg.Wait()

	avg0 := (d0.Seconds() / float64(N)) * 1000
	avg1 := (d1.Seconds() / float64(N)) * 1000
	avg2 := (d2.Seconds() / float64(N)) * 1000

	avgBytes0 := float64(b0) / (float64(N) * 1000)
	avgBytes1 := float64(b1) / (float64(N) * 1000)
	avgBytes2 := float64(b2) / (float64(N) * 1000)

	fmt.Printf("CreateGob:\t %.4f ms/msg, \t%.4f KB/msg\nCreateCapnp:\t %.4f ms/msg, \t%.4f KB/msg\nCreateProto:\t %.4f ms/msg, \t%.4f KB/msg\n", avg0, avgBytes0, avg1, avgBytes1, avg2, avgBytes2)
}
