// go test -bench=.

package main

import (
	"testing"
)

func BenchmarkGob(b *testing.B) {
	for n := 0; n < b.N; n++ {
		CreateGob()
	}
}

func BenchmarkCapnp(b *testing.B) {
	for n := 0; n < b.N; n++ {
		CreateCapnp()
	}
}

func BenchmarkProto(b *testing.B) {
	for n := 0; n < b.N; n++ {
		CreateProto()
	}
}
