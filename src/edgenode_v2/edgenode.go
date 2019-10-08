/*
	Edge Node is able to handle ~ 50 incoming messages per second at ocupandy radius 20
	from random message_generator before tick rate drops below 10 Hz.
*/

package main

import (
	"math"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"

	MQTT "github.com/eclipse/paho.mqtt.golang"
	"github.com/n1try/tiles"
	log "github.com/sirupsen/logrus"
)

var (
	sigs                        chan os.Signal
	graphInQueue                chan []byte
	client                      MQTT.Client
	fusionService               GraphFusionService
	inRateCount, outRateCount   uint32
	inBytesCount, outBytesCount uint32
	outDelayCount               int64
	lastTick                    time.Time = time.Now()
	lastEval                    time.Time = time.Now()
	kill                        bool
)

func listen() {
	// Listen for /graph_in_raw messages
	for payload := range graphInQueue {
		if kill {
			return
		}
		atomic.AddUint32(&inRateCount, 1)
		atomic.AddUint32(&inBytesCount, uint32(len(payload)))
		fusionService.In <- payload
	}
}

func tick() {
	lastTick = time.Now()

	m := fusionService.Get(GraphMaxAge)

	for k, msg := range m {
		client.Publish(TopicPrefixGraphFusedOut+"/"+string(k), 0, false, msg)
		atomic.AddUint32(&outBytesCount, uint32(len(msg)))
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
		tdelta := float32(time.Since(lastEval)) / float32(time.Second)

		ir := float32(atomic.LoadUint32(&inRateCount)) / tdelta
		or := float32(atomic.LoadUint32(&outRateCount)) / tdelta
		ib := float32(atomic.LoadUint32(&inBytesCount)) / tdelta
		ob := float32(atomic.LoadUint32(&outBytesCount)) / tdelta

		var od int64
		if or > 0 {
			od = int64(outDelayCount) / int64(or)
		}

		fmt.Printf("%.4f, %.4f, %.4f, %.4f, %.4f\n", ir, or, ib, ob, float32(od)/float32(time.Second))

		atomic.StoreUint32(&inRateCount, 0)
		atomic.StoreUint32(&outRateCount, 0)
		atomic.StoreUint32(&inBytesCount, 0)
		atomic.StoreUint32(&outBytesCount, 0)
		atomic.StoreInt64(&outDelayCount, 0)

		lastEval = time.Now()
	}
}

func init() {
	// Set up logging
	plainFormatter := new(PlainFormatter)
	plainFormatter.TimestampFormat = "2006-01-02 15:04:05"
	plainFormatter.LevelDesc = []string{"PANC", "FATL", "ERRO", "WARN", "INFO", "DEBG"}
	log.SetFormatter(plainFormatter)

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

	fusionService = GraphFusionService{Sector: tile, GridTileLevel: OccupancyTileLevel, RemoteTileLevel: RemoteGridTileLevel}
	fusionService.Init()
}

func main() {
	/*
		//pprof := profile.Start(profile.MemProfileRate(256))
		pprof := profile.Start(profile.CPUProfile)
		go func() {
			time.Sleep(30 * time.Second)
			pprof.Stop()
		}()
	*/

	opts := MQTT.NewClientOptions()
	opts.AddBroker("tcp://localhost:1883")

	client = MQTT.NewClient(opts)
	if token := client.Connect(); token.Wait() && token.Error() != nil {
		panic(token.Error())
	}
	log.Info("Connected to broker.")
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
