#!/bin/bash

# Run inside Carla distribution folder !!!

if [ "$1" = "true" ]; then
	USE_DISPLAY=":0"
fi

DISPLAY=$USE_DISPLAY ./CarlaUE4.sh -carla-server -windowed -ResX=1024 -ResY=768 -opengl