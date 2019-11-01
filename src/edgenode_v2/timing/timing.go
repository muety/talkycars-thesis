// TODO: Make thread-safe

package timing

import (
	"bytes"
	"fmt"
	"math"
	"sort"
	"sync"
	"time"
)

type TimingService struct {
	Infos chan string

	startTimestamps sync.Map
	stopTimestamps  sync.Map
	callCount       sync.Map
	startTimes      sync.Map
}

var instantiated *TimingService
var once sync.Once

func New() *TimingService {
	once.Do(func() {
		instantiated = &TimingService{}
		instantiated.init()
	})
	return instantiated
}

func (s *TimingService) init() {
	s.Infos = make(chan string)
	s.startTimestamps = sync.Map{}
	s.stopTimestamps = sync.Map{}
	s.callCount = sync.Map{}
	s.startTimes = sync.Map{}

	go func() {
		for {
			time.Sleep(5 * time.Second)
			s.Infos <- s.Info()
		}
	}()
}

func (s *TimingService) Start(key string) {
	s.StartCustom(key, time.Now())
}

func (s *TimingService) StartCustom(key string, t time.Time) {
	if _, ok := s.startTimestamps.Load(key); !ok {
		s.startTimestamps.Store(key, make([]time.Time, 0))
	}
	if _, ok := s.stopTimestamps.Load(key); !ok {
		s.stopTimestamps.Store(key, make([]time.Time, 0))
	}
	if _, ok := s.callCount.Load(key); !ok {
		s.callCount.Store(key, 0)
	}
	if _, ok := s.startTimes.Load(key); !ok {
		s.startTimes.Store(key, time.Now())
	}

	startSlice, _ := s.startTimestamps.Load(key)
	castedStartSlice := startSlice.([]time.Time)
	s.startTimestamps.Store(key, append(castedStartSlice, t))
}

func (s *TimingService) Stop(key string) {
	s.StopCustom(key, time.Now())
}

func (s *TimingService) StopCustom(key string, t time.Time) {
	if _, ok := s.stopTimestamps.Load(key); !ok {
		return
	}

	slice, _ := s.stopTimestamps.Load(key)
	castedSlice := slice.([]time.Time)
	s.stopTimestamps.Store(key, append(castedSlice, t))

	count, _ := s.callCount.Load(key)
	s.callCount.Store(key, count.(int)+1)
}

func (s *TimingService) GetMean(key string) time.Duration {
	starts, ok := s.startTimestamps.Load(key)
	if !ok {
		return time.Duration(0)
	}

	stops, ok := s.stopTimestamps.Load(key)
	if !ok {
		return time.Duration(0)
	}

	var sum float64
	var n int = int(math.Min(float64(len(stops.([]time.Time))), float64(len(starts.([]time.Time)))))

	for i := 0; i < n; i++ {
		sum += float64(stops.([]time.Time)[i].Sub(starts.([]time.Time)[i]))
	}

	return time.Duration(sum / float64(n))
}

func (s *TimingService) GetCallRate(key string) float32 {
	count, ok := s.callCount.Load(key)
	if !ok {
		return 0
	}

	start, ok := s.startTimes.Load(key)
	if !ok {
		return 0
	}

	return float32(count.(int)) / float32(time.Since(start.(time.Time))/time.Second)
}

func (s *TimingService) Info() string {
	var buffer bytes.Buffer
	keys := make([]string, 0)

	s.startTimes.Range(func(key, _ interface{}) bool {
		keys = append(keys, key.(string))
		return true
	})

	sort.Strings(keys)

	buffer.WriteString("\n-------\nTIMINGS\n")
	for _, key := range keys {
		buffer.WriteString(fmt.Sprintf("[%s] %v (Rate: %.2f / sec)\n", key, s.GetMean(key), s.GetCallRate(key)))
	}
	buffer.WriteString("-------")

	return buffer.String()
}
