package main

import (
	"bytes"
	"strconv"
	"sync"
)

var (
	qi2qkCache sync.Map = sync.Map{}
	qk2qiCache sync.Map = sync.Map{}
)

func quadInt2QuadKey(quadint uint64) string {
	if qk, ok := qi2qkCache.Load(quadint); ok {
		return qk.(string)
	}

	var buffer bytes.Buffer
	zoom := int(quadint & 0b11111)

	for i := 0; i < zoom; i++ {
		bit_loc := (64 - ((i + 1) * 2))
		char_bits := ((quadint & (0b11 << bit_loc)) >> bit_loc)
		buffer.WriteString(strconv.Itoa(int(char_bits)))
	}

	qk := buffer.String()
	qi2qkCache.Store(quadint, qk)

	return qk
}

func quadKey2QuadInt(quadkey string) (uint64, error) {
	if qi, ok := qk2qiCache.Load(quadkey); ok {
		return qi.(uint64), nil
	}

	var qi uint64
	zoom := len(quadkey)

	for i := 0; i < zoom; i++ {
		bit_loc := (64 - ((i + 1) * 2))
		char, err := strconv.Atoi(string(quadkey[i]))
		if err != nil {
			return 0, err
		}
		qi |= uint64(char) << bit_loc
	}
	qi |= uint64(zoom)

	qk2qiCache.Store(quadkey, qi)

	return qi, nil
}
