package main

import (
	"testing"
)

func BenchmarkPlain(b *testing.B) {
	for n := 0; n < b.N; n++ {
		CreatePlain()
	}
}

func BenchmarkCapnp(b *testing.B) {
	for n := 0; n < b.N; n++ {
		CreateCapnp()
	}
}