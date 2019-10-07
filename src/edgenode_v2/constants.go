package main

import "time"

const (
	TickRate                 = 10
	OccupancyTileLevel       = 24
	RemoteGridTileLevel      = 19
	FusionDecayLambda        = 0.05
	TopicGraphRawIn          = "/graph_raw_in"
	TopicPrefixGraphFusedOut = "/graph_fused_out"
	GraphMaxAge              = time.Duration(1 * time.Hour) // time.Duration(5 * time.Second)
	FusionKeepObs            = 300                          // Important: Make sure this is AT LEAST is large as the maximum number of concurrent producers
	NStates                  = 3
)
