package main

import "time"

const (
	TickRate                 = 10
	OccupancyTileLevel       = 24
	RemoteGridTileLevel      = 19
	FusionDecayLambda        = 0.2 // 0.05, 0.1, 0.2, 0.3
	TopicGraphRawIn          = "/graph_raw_in"
	TopicPrefixGraphFusedOut = "/graph_fused_out"
	GraphMaxAge              = time.Duration(3 * time.Second)
	MqttQos                  = 1
)
