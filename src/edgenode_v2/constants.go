package main

import "time"

const (
	TickRate                 = 10
	OccupancyTileLevel       = 24
	RemoteGridTileLevel      = 19
	FusionDecayLambda        = 0.05
	TopicGraphRawIn          = "/graph_raw_in"
	TopicPrefixGraphFusedOut = "/graph_fused_out"
	GraphMaxAge              = time.Duration(10 * time.Second)
)
