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
	"sync/atomic"
	"syscall"
	"time"

	MQTT "github.com/eclipse/paho.mqtt.golang"
	"github.com/n1try/tiles"
	"github.com/pkg/profile"
)

var (
	sigs                      chan os.Signal
	graphInQueue              chan []byte
	client                    MQTT.Client
	fusionService             GraphFusionService
	inRateCount, outRateCount uint32
	outDelayCount             int64
	lastTick                  time.Time
	kill                      bool
)

func listen() {
	// Listen for /graph_in_raw messages
	for payload := range graphInQueue {
		if kill {
			return
		}
		atomic.AddUint32(&inRateCount, 1)
		fusionService.In <- payload
	}
}

func tick() {
	lastTick = time.Now()

	m := fusionService.Get(GraphMaxAge)

	for k, msg := range m {
		client.Publish(TopicPrefixGraphFusedOut+"/"+string(k), 0, false, msg)
	}

	if len(m) > 0 {
		atomic.AddUint32(&outRateCount, 1)
		atomic.AddInt64(&outDelayCount, int64(time.Since(lastTick)))
	}
}

func loop(tickRate float64) {
	for !kill {
		sleep := math.Max(0, float64(time.Second)/tickRate-float64(time.Since(lastTick)))
		time.Sleep(time.Duration(sleep))
		tick()
	}
}

func monitor() {
	for !kill {
		time.Sleep(time.Second)

		ir := atomic.LoadUint32(&inRateCount)
		or := atomic.LoadUint32(&outRateCount)

		var od int64
		if or > 0 {
			od = int64(outDelayCount) / int64(or)
		}

		fmt.Printf("In Rate: %v / sec, Out Rate: %v / sec., Avg. fusion time: %v\n", ir, or, time.Duration(od))
		atomic.StoreUint32(&inRateCount, 0)
		atomic.StoreUint32(&outRateCount, 0)
		atomic.StoreInt64(&outDelayCount, 0)
	}
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
	pprof := profile.Start(profile.MemProfileRate(256))
	go func() {
		time.Sleep(30 * time.Second)
		pprof.Stop()
	}()

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

	for _ = range sigs {
		kill = true
		close(sigs)
	}
}
