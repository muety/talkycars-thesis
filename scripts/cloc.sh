#!/bin/bash
SCRIPT_DIR=$(cd `dirname $0` && pwd)
SRC_DIR=$(realpath "$SCRIPT_DIR/../src")
cloc $SRC_DIR --exclude-lang C --not-match-f .*\.capnp\.go