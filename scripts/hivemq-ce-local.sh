#!/bin/bash

DIR="/media/hive_tmp"

if [ ! -d "$DIR" ]; then
    sudo mkdir -p "$DIR"
fi

sudo mount -t tmpfs -o size=512M none "$DIR"

export HIVEMQ_DATA_FOLDER="$DIR"
echo "$HIVEMQ_DATA_FOLDER"
bash /opt/hivemq-ce/bin/run.sh