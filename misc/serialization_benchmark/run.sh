#!/bin/bash

cp -R ../../src/edgenode_v2/schema .
go test -bench=.
go build
./serialization_benchmark