package main

import (
	"fmt"
	"os"
	"os/signal"
	"syscall"

	"zombiezen.com/go/capnproto2"

	"./schema"

	MQTT "github.com/eclipse/paho.mqtt.golang"
)

var sigs chan os.Signal
var graphIn chan []byte

var fusionService FusionService

func listen() {
	// Listen for /graph_in_raw messages
	go func() {
		for payload := range graphIn {
			graph, err := decodeGraph(payload)
			if err != nil {
				continue
			}

			measuredBy, _ := graph.MeasuredBy()
			fmt.Printf("Got traffic scene measured by %v.", measuredBy.Id())
		}
	}()
}

func decodeGraph(msg []byte) (*schema.TrafficScene, error) {
	decodedMsg, err := capnp.UnmarshalPacked(msg)
	if err != nil {
		return nil, err
	}
	graph, err := schema.ReadRootTrafficScene(decodedMsg)
	if err != nil {
		return nil, err
	}
	return &graph, nil
}

func init() {
	sigs = make(chan os.Signal, 1)
	graphIn = make(chan []byte)

	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM, syscall.SIGKILL)

	fusionService = TrafficSceneFusionService{Sector: "1021113201201201", Keep: 3, GridTileLevel: OccupancyTileLevel}
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
