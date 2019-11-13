package main

import "time"

const (
	TickRate                 = 15
	OccupancyTileLevel       = 24
	RemoteGridTileLevel      = 19
	FusionDecayLambda        = 0.14 // 0.05, 0.08, 0.11, 0.14
	TopicGraphRawIn          = "/graph_raw_in"
	TopicPrefixGraphFusedOut = "/graph_fused_out"
	GraphMaxAge              = time.Duration(2 * time.Second)
	MqttQos                  = 1
)
