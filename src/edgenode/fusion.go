package main

import (
	"bytes"
	"container/list"
	"math"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"time"

	"./log"
	"./schema"
	"./timing"
	"github.com/golang/protobuf/proto"
	"github.com/n1try/tiles"
)

type CellObservation struct {
	Timestamp    time.Time
	MinTimestamp time.Time
	MaxTimestamp time.Time
	Hash         tiles.Quadkey
	Cell         *schema.GridCell
}

type CellFuseJob struct {
	Hash         tiles.Quadkey
	Observations *list.List
}

type GraphFusionService struct {
	Sector          tiles.Quadkey
	GridTileLevel   int
	RemoteTileLevel int
	In              chan []byte
	remoteKeys      []tiles.Quadkey
	gridKeys        map[tiles.Quadkey][]tiles.Quadkey
	observations    sync.Map
	presentCells    sync.Map
	timingService   *timing.TimingService
}

var (
	lock1        sync.RWMutex = sync.RWMutex{}
	nFuseWorkers int          = int(math.Pow(4, OccupancyTileLevel-RemoteGridTileLevel))
	nPushWorkers int          = runtime.NumCPU()
)

func (s *GraphFusionService) Init() {
	if remoteKeys, err := s.Sector.ChildrenAt(s.RemoteTileLevel); err == nil {
		s.remoteKeys = remoteKeys
	} else {
		panic(err.Error())
	}

	s.gridKeys = make(map[tiles.Quadkey][]tiles.Quadkey)
	for _, parent := range s.remoteKeys {
		if childrenKeys, err := parent.ChildrenAt(OccupancyTileLevel); err == nil {
			s.gridKeys[parent] = childrenKeys
		} else {
			panic(err.Error())
		}
	}

	s.In = make(chan []byte)
	s.observations = sync.Map{}
	s.presentCells = sync.Map{}

	// Start push worker pool
	for w := 0; w < nPushWorkers; w++ {
		go s.pushWorker(w, s.In)
	}

	s.timingService = timing.New()
}

// Don't call Push() directly from the outside, but push graphs into s.In channel
func (s *GraphFusionService) Push(msg []byte) {
    t0 := time.Now()

	graph, err := decodeGraph(msg)
	if err != nil {
		log.Error(err)
		return
	}

	ts := floatToTime(graph.Timestamp)
	if time.Since(ts) > GraphMaxAge {
		log.Info("Discarded incoming graph due to timeout.")
		return
	}

	lastTs := floatToTime(graph.LastTimestamp)
	s.timingService.StartCustom("d2", lastTs)
	s.timingService.Stop("d2")

	senderId := int(graph.MeasuredBy.Id)

	if len(graph.OccupancyGrid.Cells) == 0 {
		log.Errorf("Got graph with empty cell list from %d.\n", senderId)
	}

	for i := 0; i < len(graph.OccupancyGrid.Cells); i++ {
		cell := graph.OccupancyGrid.Cells[i]
		hash := tiles.Quadkey(quadInt2QuadKey(cell.Hash))

		// Store latest timestamp for this cell in presentCells
		if ts1, ok := s.presentCells.Load(hash); !ok || ts1.(time.Time).Before(ts) {
			s.presentCells.Store(hash, ts)
		}

		// TODO: Introduce clean-up to prevent memory leak
		s.observations.Store(getKey(hash, senderId, 0), &CellObservation{
			Timestamp: ts,
			Hash:      hash,
			Cell:      cell,
		})
	}

	s.timingService.StartCustom("d3", t0)
	s.timingService.Stop("d3")
}

func (s *GraphFusionService) Get(maxAge time.Duration) map[tiles.Quadkey][]byte {
	t0 := time.Now()
	t0Float := timeToFloat(t0)

	tickDelay := 0.5 / float64(TickRate)
	tickDelayDuration := time.Duration(tickDelay * float64(time.Second))

	minTs := sync.Map{}
	maxTs := sync.Map{}

	cells := sync.Map{}

	var wg sync.WaitGroup
	jobs := make(chan CellFuseJob)
	results := make(chan *CellObservation)

	defer close(jobs)
	defer close(results)

	// Start fuseWorker pool
	for w := 0; w < nFuseWorkers; w++ {
		go s.fuseWorker(w, jobs, results)
	}

	// Wait for results
	go func() {
		for obs := range results {
			if obs != nil {
				parent := obs.Hash[:RemoteGridTileLevel]
				if l, ok := cells.Load(parent); ok {
					currentTs1, ok2 := minTs.Load(parent)
					if !ok2 || obs.MinTimestamp.Before(currentTs1.(time.Time)) {
						minTs.Store(parent, obs.MinTimestamp)
					}

					currentTs2, ok2 := maxTs.Load(parent)
					if !ok2 || obs.MaxTimestamp.After(currentTs2.(time.Time)) {
						maxTs.Store(parent, obs.MaxTimestamp)
					}

					l.(*list.List).PushBack(obs.Cell)
				}
			}
			wg.Done()
		}
	}()

	cellObservations := make(map[tiles.Quadkey]*list.List)

	s.observations.Range(func(_, val interface{}) bool {
		obs := val.(*CellObservation)
		hash := obs.Hash
		parent := hash[:RemoteGridTileLevel]

		if _, ok := cells.Load(parent); !ok {
			cells.Store(parent, list.New())
		}

		if t0.Sub(obs.Timestamp) <= GraphMaxAge {
			if _, ok := cellObservations[hash]; !ok {
				cellObservations[hash] = list.New()
			}
			cellObservations[hash].PushBack(obs)
		}

		return true
	})

	for hash, observations := range cellObservations {
		job := CellFuseJob{
			Hash:         hash,
			Observations: observations,
		}

		wg.Add(1)
		jobs <- job
	}

	wg.Wait()

	t1Float := timeToFloat(time.Now())
	encodedMessages := make(map[tiles.Quadkey][]byte)

	cells.Range(func(key, val interface{}) bool {
		parent := key.(tiles.Quadkey)
		cellz := val.(*list.List)
		cellList := make([]*schema.GridCell, cellz.Len(), cellz.Len())

		var (
			minTimestamp float64
			maxTimestamp float64
		)

		if t, ok := minTs.Load(parent); ok {
			minTimestamp = timeToFloat(t.(time.Time))
		}
		if t, ok := maxTs.Load(parent); ok {
			maxTimestamp = timeToFloat(t.(time.Time))
		}

		i := 0
		elem := cellz.Front()
		for elem != nil {
			cellList[i] = (elem.Value.(*schema.GridCell))
			elem = elem.Next()
			i++
		}

		grid := &schema.OccupancyGrid{Cells: cellList}
		scene := &schema.TrafficScene{
			Timestamp:     t0Float,
			LastTimestamp: t1Float,
			MinTimestamp:  minTimestamp,
			MaxTimestamp:  maxTimestamp,
			OccupancyGrid: grid,
		}

		out, err := proto.Marshal(scene)
		if err != nil {
			log.Error(err)
			return false
		}
		encodedMessages[parent] = out

		return true
	})

	s.timingService.StartCustom("d4", t0.Add(-tickDelayDuration))
	s.timingService.Stop("d4")

	return encodedMessages
}

func fuseCell(hash tiles.Quadkey, obs *list.List) (*CellObservation, error) {
	now := time.Now()
	minTimestamp := now
	maxTimestamp := now.Add(-24 * time.Hour)
	states := []float32{0, 0, 0}
	stateWeights := []float32{0, 0, 0}

	listItem := obs.Front()
	for listItem != nil {
		o := listItem.Value.(*CellObservation)

		conf, state := o.Cell.State.Confidence, o.Cell.State.Object
		weight := decay(1, o.Timestamp, now)

		states[int(state)] += conf * weight
		stateWeights[int(state)] += weight

		if o.Timestamp.Before(minTimestamp) {
			minTimestamp = o.Timestamp
		}
		if o.Timestamp.After(maxTimestamp) {
			maxTimestamp = o.Timestamp
		}

		listItem = listItem.Next()
	}

	lock1.Lock()
	defer lock1.Unlock()

	// TODO: Also fix min- / max timestamps in case unknown-observations are discarded
	if states[schema.GridCellState_STATE_FREE] > 0 || states[schema.GridCellState_STATE_OCCUPIED] > 0 {
		states[schema.GridCellState_STATE_UNKNOWN] = 0
		stateWeights[schema.GridCellState_STATE_UNKNOWN] = 0
	}

	meanStateVector := meanCellState(states, vectorSum(stateWeights), 1.0)
	maxConf, maxState := getMaxState(meanStateVector)
	quadInt, err := quadKey2QuadInt(string(hash))
	if err != nil {
		log.Error(err)
		return nil, err
	}

	newCell := &schema.GridCell{
		Hash: quadInt,
		State: &schema.GridCellStateRelation{
			Confidence: maxConf,
			Object:     maxState,
		},
	}

	fusedObs := &CellObservation{
		Timestamp:    time.Now(), // shouldn't matter ever, could be anything
		MinTimestamp: minTimestamp,
		MaxTimestamp: maxTimestamp,
		Hash:         hash,
		Cell:         newCell,
	}

	return fusedObs, nil
}

func decodeGraph(msg []byte) (*schema.TrafficScene, error) {
	graph := &schema.TrafficScene{}
	if err := proto.Unmarshal(msg, graph); err != nil {
		log.Error(err)
		return nil, err
	}
	return graph, nil
}

func (s *GraphFusionService) countPresentCells(parent tiles.Quadkey, now time.Time) int32 {
	var count int32

	s.presentCells.Range(func(key, val interface{}) bool {
		if strings.HasPrefix(string(key.(tiles.Quadkey)), string(parent)) {
			if now.Sub(val.(time.Time)) <= GraphMaxAge {
				count++
			} else {
				s.presentCells.Delete(key)
			}
		}
		return true
	})

	return count
}

func (s *GraphFusionService) pushWorker(id int, messages <-chan []byte) {
	for msg := range messages {
		s.Push(msg)
	}
}

func (s *GraphFusionService) fuseWorker(id int, jobs <-chan CellFuseJob, results chan<- *CellObservation) {
	for job := range jobs {
		results <- runFuseJob(&job)
	}
}

// Will always exit normally, regardless whether fuseCell() panicked.
func runFuseJob(job *CellFuseJob) *CellObservation {
	defer func() {
		if r := recover(); r != nil {
			log.Warnf("Had to recover while processing cell %s.", string(job.Hash))
		}
	}()

	// Do fusion work
	result, err := fuseCell(job.Hash, job.Observations)
	if err != nil {
		log.Error(err)
	}

	return result
}

func getMaxState(states []float32) (float32, schema.GridCellState) {
	state := schema.GridCellState_STATE_UNKNOWN
	maxConf := float32(0.0)

	for i, conf := range states {
		if conf > maxConf {
			maxConf = conf
			state = schema.GridCellState(i)
		}
	}
	return maxConf, state
}

func meanCellState(stateSumVector []float32, weightSum, normalizeTo float32) []float32 {
	return []float32{
		stateSumVector[0] / weightSum * normalizeTo,
		stateSumVector[1] / weightSum * normalizeTo,
		stateSumVector[2] / weightSum * normalizeTo,
	}
}

func vectorSum(vec []float32) float32 {
	var sum float32
	for _, v := range vec {
		sum += v
	}
	return sum
}

func timeToFloat(t time.Time) float64 {
	return float64(t.UnixNano()) / 1e9
}

func floatToTime(ts float64) time.Time {
	return time.Unix(0, int64(ts*1e9))
}

func decay(val float32, t, now time.Time) float32 {
	tdiff := now.Sub(t).Milliseconds() / 100
	factor := math.Exp(float64(tdiff) * -1.0 * FusionDecayLambda)
	return val * float32(factor)
}

func getKey(qk tiles.Quadkey, senderId int, ts int64) string {
	// https://hermanschaaf.com/efficient-string-concatenation-in-go/
	var buffer bytes.Buffer
	buffer.WriteString(string(qk))
	buffer.WriteString(strconv.Itoa(senderId))
	buffer.WriteString(strconv.FormatInt(ts, 10))
	return buffer.String()
}
