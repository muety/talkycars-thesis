package main

import (
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	MQTT "github.com/eclipse/paho.mqtt.golang"
)

var sigs chan os.Signal
var graphIn chan []byte

var fusionService GraphFusionService

func listen() {
	// Listen for /graph_in_raw messages
	go func() {
		for payload := range graphIn {
			fusionService.Push(payload)
			m := fusionService.Get(time.Duration(30) * time.Second)

			// DEBUG CODE
			for k, msg := range m {
				if k == "1202032332303131133" {
					g, err := DecodeGraph(msg)
					if err != nil {
						fmt.Println(err)
						break
					}

					grid, err := g.OccupancyGrid()
					if err != nil {
						fmt.Println(err)
						break
					}
					cells, err := grid.Cells()
					if err != nil {
						fmt.Println(err)
						break
					}

					for i := 0; i < cells.Len(); i++ {
						cell := cells.At(i)
						hash, err := cell.Hash()
						if err != nil {
							fmt.Println(err)
							break
						}

						stateRelation, err := cell.State()
						if err != nil {
							fmt.Println(err)
							break
						}

						conf := stateRelation.Confidence()
						state := stateRelation.Object()
						fmt.Println(g.Timestamp(), g.MinTimestamp(), hash, conf, state)
					}
				}
			}
			// END DEBUG CODE
		}
	}()
}

func init() {
	sigs = make(chan os.Signal, 1)
	graphIn = make(chan []byte)

	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM, syscall.SIGKILL)

	fusionService = GraphFusionService{Sector: "1202032332303131", Keep: 3, GridTileLevel: OccupancyTileLevel, RemoteTileLevel: RemoteGridTileLevel}
	fusionService.Init()
}

func main() {
	opts := MQTT.NewClientOptions()
	opts.AddBroker("tcp://localhost:1883")

	client := MQTT.NewClient(opts)
	if token := client.Connect(); token.Wait() && token.Error() != nil {
		panic(token.Error())
	}
	fmt.Println("Connected to broker.")
	defer client.Disconnect(100)

	if token := client.Subscribe(TopicGraphRawIn, 0, func(client MQTT.Client, msg MQTT.Message) {
		graphIn <- msg.Payload()
	}); token.Wait() && token.Error() != nil {
		panic(token.Error())
	}

	listen()

	<-sigs
}
