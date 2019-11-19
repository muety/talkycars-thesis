#!/bin/bash

protoc -I ./schema/protobuf --go_out=./schema/protobuf ./schema/protobuf/schema.proto

capnp compile -I$GOPATH/src/zombiezen.com/go/capnproto2/std -ogo:./schema/capnp --src-prefix ./schema/capnp ./schema/capnp/*.capnp

go test -bench=.

go build
./serialization