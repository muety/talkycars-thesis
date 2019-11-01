package main

import (
	"bytes"
	"container/list"
	"math"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"./log"
	"./schema"
	"./timing"
	"github.com/n1try/tiles"
	capnp "zombiezen.com/go/capnproto2"
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
	CellCount    *uint32
	Observations *list.List
	OutGrid      *schema.OccupancyGrid
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
	s.timingService.Start("d3")

	graph, err := decodeGraph(msg)
	if err != nil {
		log.Error(err)
		return
	}

	ts := floatToTime(graph.Timestamp())
	if time.Since(ts) > GraphMaxAge {
		log.Info("Discarded incoming graph due to timeout.")
		return
	}

	lastTs := floatToTime(graph.LastTimestamp())
	s.timingService.StartCustom("d2", lastTs)
	s.timingService.Stop("d2")

	measuredBy, err := graph.MeasuredBy()
	if err != nil {
		log.Error(err)
		return
	}

	grid, err := graph.OccupancyGrid()
	if err != nil {
		log.Error(err)
		return
	}

	cellList, err := grid.Cells()
	if err != nil {
		log.Error(err)
		return
	}

	senderId := int(measuredBy.Id())

	if cellList.Len() == 0 {
		log.Errorf("Got graph with empty cell list from %d.\n", senderId)
	}

	for i := 0; i < cellList.Len(); i++ {
		cell := cellList.At(i)
		hash := tiles.Quadkey(quadInt2QuadKey(cell.Hash()))

		// Store latest timestamp for this cell in presentCells
		if ts1, ok := s.presentCells.Load(hash); !ok || ts1.(time.Time).Before(ts) {
			s.presentCells.Store(hash, ts)
		}

		// TODO: Introduce clean-up to prevent memory leak
		s.observations.Store(getKey(hash, senderId, 0), &CellObservation{
			Timestamp: ts,
			Hash:      hash,
			Cell:      &cell,
		})
	}

	s.timingService.Stop("d3")
}

func (s *GraphFusionService) Get(maxAge time.Duration) map[tiles.Quadkey][]byte {
	now := time.Now()
	nowFloat := timeToFloat(now)

	tickDelay := 0.5 / float64(TickRate)
	tickDelayDuration := time.Duration(tickDelay * float64(time.Second))
	s.timingService.StartCustom("d4", now.Add(-tickDelayDuration))

	minTs := sync.Map{}
	maxTs := sync.Map{}

	cellCount := make(map[tiles.Quadkey]*uint32)
	messages := make(map[tiles.Quadkey]*capnp.Message)
	scenes := make(map[tiles.Quadkey]schema.TrafficScene)
	grids := make(map[tiles.Quadkey]schema.OccupancyGrid)
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
		parent := tiles.Quadkey(string(hash)[:RemoteGridTileLevel])

		if now.Sub(obs.Timestamp) <= GraphMaxAge {
			if _, ok := messages[parent]; !ok {
				msg, seg, _ := capnp.NewMessage(capnp.SingleSegment(nil))

				scene, err := schema.NewRootTrafficScene(seg)
				if err != nil {
					log.Error(err)
					return false
				}

				grid, err := scene.NewOccupancyGrid()
				if err != nil {
					log.Error(err)
					return false
				}

				count := s.countPresentCells(parent, now)

				cellList, err := grid.NewCells(count)
				if err != nil {
					log.Error(err)
					return false
				}

				for i := 0; i < int(count); i++ {
					schema.NewGridCell(cellList.Segment())
				}

				var c uint32
				cellCount[parent] = &c

				grid.SetCells(cellList)
				scene.SetTimestamp(nowFloat)
				scene.SetOccupancyGrid(grid)

				messages[parent] = msg
				scenes[parent] = scene
				grids[parent] = grid

				cells.Store(parent, list.New())
			}

			if _, ok := cellObservations[hash]; !ok {
				cellObservations[hash] = list.New()
			}

			cellObservations[hash].PushBack(obs)
		}

		return true
	})

	for hash, observations := range cellObservations {
		parent := hash[:RemoteGridTileLevel]
		grid := grids[parent]

		job := CellFuseJob{
			Hash:         hash,
			CellCount:    cellCount[parent],
			Observations: observations,
			OutGrid:      &grid,
		}

		wg.Add(1)
		jobs <- job
	}

	wg.Wait()

	nowFloat = timeToFloat(time.Now())
	encodedMessages := make(map[tiles.Quadkey][]byte)

	cells.Range(func(key, val interface{}) bool {
		parent := key.(tiles.Quadkey)
		cellz := val.(*list.List)

		cellList, err := grids[parent].Cells()
		if err != nil {
			log.Error(err)
			return false
		}

		i := 0
		elem := cellz.Front()
		for elem != nil {
			cellList.Set(i, *(elem.Value.(*schema.GridCell)))
			elem = elem.Next()
			i++
		}

		scenes[parent].SetLastTimestamp(nowFloat)
		if t, ok := minTs.Load(parent); ok {
			scenes[parent].SetMinTimestamp(timeToFloat(t.(time.Time)))
		}
		if t, ok := maxTs.Load(parent); ok {
			scenes[parent].SetMaxTimestamp(timeToFloat(t.(time.Time)))
		}

		encodedMessage, err := messages[parent].MarshalPacked()
		if err != nil {
			log.Error(err)
			return false
		}
		encodedMessages[parent] = encodedMessage

		return true
	})

	s.timingService.Stop("d4")

	return encodedMessages
}

func fuseCell(hash tiles.Quadkey, cellCount *uint32, obs *list.List, outGrid *schema.OccupancyGrid) (*CellObservation, error) {
	now := time.Now()
	minTimestamp := now
	maxTimestamp := now.Add(-24 * time.Hour)
	states := []float32{0, 0, 0}
	stateWeights := []float32{0, 0, 0}

	listItem := obs.Front()
	for listItem != nil {
		o := listItem.Value.(*CellObservation)

		stateRelation, err := o.Cell.State()
		if err != nil {
			log.Error(err)
			continue
		}

		conf, state := stateRelation.Confidence(), stateRelation.Object()
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

	outCellList, err := outGrid.Cells()
	if err != nil {
		log.Error(err)
		return nil, err
	}

	j := int(atomic.AddUint32(cellCount, 1) - 1)
	newCell := outCellList.At(j)

	newStateRelation, err := newCell.NewState()
	if err != nil {
		log.Error(err)
		return nil, err
	}

	newOccupantRelation, err := newCell.NewOccupant()
	if err != nil {
		log.Error(err)
		return nil, err
	}

	quadInt, err := quadKey2QuadInt(string(hash))
	if err != nil {
		log.Error(err)
		return nil, err
	}

	// TODO: Also fix min- / max timestamps in case unknown-observations are discarded
	if states[schema.GridCellState_free] > 0 || states[schema.GridCellState_occupied] > 0 {
		states[schema.GridCellState_unknown] = 0
		stateWeights[schema.GridCellState_unknown] = 0
	}

	meanStateVector := meanCellState(states, vectorSum(stateWeights), 1.0)
	maxConf, maxState := getMaxState(meanStateVector)
	newStateRelation.SetConfidence(maxConf)
	newStateRelation.SetObject(maxState)

	newCell.SetHash(quadInt)
	newCell.SetState(newStateRelation)
	newCell.SetOccupant(newOccupantRelation)

	fusedObs := &CellObservation{
		Timestamp:    time.Now(), // shouldn't matter ever, could be anything
		MinTimestamp: minTimestamp,
		MaxTimestamp: maxTimestamp,
		Hash:         hash,
		Cell:         &newCell,
	}

	return fusedObs, nil
}

func decodeGraph(msg []byte) (*schema.TrafficScene, error) {
	decodedMsg, err := capnp.UnmarshalPacked(msg)
	if err != nil {
		log.Error(err)
		return nil, err
	}
	graph, err := schema.ReadRootTrafficScene(decodedMsg)
	if err != nil {
		log.Error(err)
		return nil, err
	}
	return &graph, nil
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
	result, err := fuseCell(job.Hash, job.CellCount, job.Observations, job.OutGrid)
	if err != nil {
		log.Error(err)
	}

	return result
}

func getMaxState(states []float32) (float32, schema.GridCellState) {
	state := schema.GridCellState_unknown
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
