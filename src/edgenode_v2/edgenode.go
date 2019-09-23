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
var client MQTT.Client

var fusionService GraphFusionService

func listen() {
	// Listen for /graph_in_raw messages
	for payload := range graphIn {
		go func(payload []byte) {
			fusionService.Push(payload)
			// TODO: Fixed tick rate
			// TODO: Track in- and out rate
			m := fusionService.Get(time.Duration(30) * time.Second)

			for k, msg := range m {
				client.Publish(TopicPrefixGraphFusedOut+"/"+string(k), 0, false, msg)
			}
		}(payload)
	}
}

func init() {
	sigs = make(chan os.Signal, 1)
	graphIn = make(chan []byte, 10)

	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM, syscall.SIGKILL)

	fusionService = GraphFusionService{Sector: "1202032332303131", Keep: 3, GridTileLevel: OccupancyTileLevel, RemoteTileLevel: RemoteGridTileLevel} // TODO: Read from command-line params
	fusionService.Init()
}

func main() {
	opts := MQTT.NewClientOptions()
	opts.AddBroker("tcp://localhost:1883")

	client = MQTT.NewClient(opts)
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

	go listen()

	<-sigs
}
