/*
	Edge Node is able to handle ~ 50 incoming messages per second at ocupandy radius 20
	from random message_generator before tick rate drops below 10 Hz.
*/

package main

import (
	"fmt"
	"math"
	"os"
	"os/signal"
	"syscall"
	"time"

	MQTT "github.com/eclipse/paho.mqtt.golang"
	"github.com/n1try/tiles"
)

var sigs chan os.Signal
var client MQTT.Client
var inRateCount int
var outRateCount int
var graphInQueue chan []byte
var lastTick time.Time

var fusionService GraphFusionService

func listen() {
	// Listen for /graph_in_raw messages
	for payload := range graphInQueue {
		go func(payload []byte) {
			inRateCount++
			fusionService.Push(payload)
		}(payload)
	}
}

func tick() {
	lastTick = time.Now()

	m := fusionService.Get(GraphMaxAge)
	for k, msg := range m {
		client.Publish(TopicPrefixGraphFusedOut+"/"+string(k), 0, false, msg)
	}

	if len(m) > 0 {
		outRateCount++
	}
}

func loop(tickRate float64) {
	go func(tickRate float64) {
		for {
			sleep := math.Max(0, float64(time.Second)/tickRate-float64(time.Since(lastTick)))
			time.Sleep(time.Duration(sleep))
			tick()
		}
	}(tickRate)
}

func monitor() {
	go func(interval time.Duration) {
		for {
			time.Sleep(interval)
			fmt.Printf("In Rate: %v / sec, Out Rate: %v / sec\n", inRateCount, outRateCount)
			inRateCount = 0
			outRateCount = 0
		}
	}(time.Second)
}

func init() {
	var tile tiles.Quadkey

	// Read command-line args
	args := os.Args[1:]
	if len(args) == 2 && args[0] == "--tile" {
		tile = tiles.Quadkey(args[1]) // 1202032332303131
	} else {
		panic("You need to pass \"--tile\" parameter.")
	}

	sigs = make(chan os.Signal, 1)
	graphInQueue = make(chan []byte)

	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM, syscall.SIGKILL)

	fusionService = GraphFusionService{Sector: tile, Keep: FusionKeepObs, GridTileLevel: OccupancyTileLevel, RemoteTileLevel: RemoteGridTileLevel}
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
		graphInQueue <- msg.Payload()
	}); token.Wait() && token.Error() != nil {
		panic(token.Error())
	}

	go listen()
	go monitor()
	go loop(TickRate)

	<-sigs
}
