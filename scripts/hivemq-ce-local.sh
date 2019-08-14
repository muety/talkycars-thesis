#!/bin/bash

HIVE_DIR="/opt/hivemq-ce/bin"
DIR="/media/hive_tmp"

# Mount RAM Disk
if [ ! -d "$DIR" ]; then
    sudo mkdir -p "$DIR"
    sudo mount -t tmpfs -o size=512M none "$DIR"
fi

export HIVEMQ_DATA_FOLDER="$DIR"
bash "$HIVE_DIR/run.sh"