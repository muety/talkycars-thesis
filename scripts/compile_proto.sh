#!/bin/bash
SCRIPT_DIR=$(cd `dirname $0` && pwd)
SRC_DIR=$(realpath "$SCRIPT_DIR/../src")
SCHEMA_DIR="$SRC_DIR/common/serialization/schema/proto"

protoc -I $SCHEMA_DIR --python_out=$SCHEMA_DIR --go_out=$SCHEMA_DIR $SCHEMA_DIR/*.proto
sed -i -E "s/^(import \w+_pb2)/from . \1/" $SCHEMA_DIR/*_pb2.py