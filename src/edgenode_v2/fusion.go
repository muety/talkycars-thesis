package main

import (
	"math"
	"runtime"
	"sync"
	"sync/atomic"
	"time"

	"./deque"
	"./schema"
	"github.com/n1try/tiles"
	cmap "github.com/orcaman/concurrent-map"
	log "github.com/sirupsen/logrus"
	capnp "zombiezen.com/go/capnproto2"
)

// TODO: Min Timestamp

type CellObservation struct {
	Timestamp time.Time
	Hash      tiles.Quadkey
	Cell      *schema.GridCell
}

type CellFuseJob struct {
	Hash         tiles.Quadkey
	CellCount    *uint32
	Observations []*CellObservation
	OutGrid      *schema.OccupancyGrid
}

type GraphFusionService struct {
	Sector          tiles.Quadkey
	Keep            int
	GridTileLevel   int
	RemoteTileLevel int
	In              chan []byte
	remoteKeys      []tiles.Quadkey
	observations    cmap.ConcurrentMap
	gridKeys        map[tiles.Quadkey][]tiles.Quadkey
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
	s.observations = cmap.New()

	// Start push worker pool
	for w := 0; w < nPushWorkers; w++ {
		go s.pushWorker(w, s.In)
	}
}

// Don't call Push() directly from the outside, but push graphs into s.In channel
func (s *GraphFusionService) Push(msg []byte) {
	t0 := time.Now()

	graph, err := decodeGraph(msg)
	if err != nil {
		return
	}

	//measuredBy, err := graph.MeasuredBy()
	if err != nil {
		return
	}

	grid, err := graph.OccupancyGrid()
	if err != nil {
		return
	}

	cellList, err := grid.Cells()
	if err != nil {
		return
	}

	ts := floatToTime(graph.Timestamp())
	//senderId := int(measuredBy.Id())

	for i := 0; i < cellList.Len(); i++ {
		cell := cellList.At(i)
		hash := tiles.Quadkey(quadInt2QuadKey(cell.Hash()))
		strHash := string(hash)

		s.observations.SetIfAbsent(strHash, deque.NewCappedDeque(FusionKeepObs))

		dq, _ := s.observations.Get(strHash)
		dq.(*deque.Deque).Append(&CellObservation{
			Timestamp: ts,
			Hash:      hash,
			Cell:      &cell,
		})
	}

	log.Debug(time.Since(t0))
}

func (s *GraphFusionService) Get(maxAge time.Duration) map[tiles.Quadkey][]byte {

	now := time.Now()
	nowFloat := timeToFloat(now)
	messages := make(map[tiles.Quadkey]*capnp.Message)
	scenes := make(map[tiles.Quadkey]schema.TrafficScene)
	grids := make(map[tiles.Quadkey]schema.OccupancyGrid)
	cells := make(map[tiles.Quadkey][]schema.GridCell)
	cellCount := make(map[tiles.Quadkey]*uint32)

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
			parent := obs.Hash[:RemoteGridTileLevel]

			lock1.Lock()
			cells[parent] = append(cells[parent], *obs.Cell)
			lock1.Unlock()

			wg.Done()
		}
	}()

	for tuple := range s.observations.IterBuffered() {
		hash := tiles.Quadkey(tuple.Key)
		cellDeque := tuple.Val.(*deque.Deque)
		parent := hash[:RemoteGridTileLevel]

		if _, ok := messages[parent]; !ok {
			msg, seg, _ := capnp.NewMessage(capnp.SingleSegment(nil))

			scene, err := schema.NewRootTrafficScene(seg)
			if err != nil {
				continue
			}

			grid, err := scene.NewOccupancyGrid()
			if err != nil {
				continue
			}

			count := s.countPresentCells(parent)

			cellList, err := grid.NewCells(count)
			if err != nil {
				continue
			}

			for i := 0; i < int(count); i++ {
				schema.NewGridCell(cellList.Segment())
			}

			c := uint32(0)
			cellCount[parent] = &c

			grid.SetCells(cellList)
			scene.SetTimestamp(nowFloat)
			scene.SetOccupancyGrid(grid)

			messages[parent] = msg
			scenes[parent] = scene
			grids[parent] = grid

			lock1.Lock()
			cells[parent] = make([]schema.GridCell, 0)
			lock1.Unlock()
		}

		sz := cellDeque.Size()
		cellObservations := make([]*CellObservation, sz)
		previousItem := cellDeque.LastElement()

		for i := sz - 1; i >= 0 && previousItem != nil; i-- {
			if i < sz-1 && previousItem.Prev() != nil {
				previousItem = previousItem.Prev()
			}

			if obs := previousItem.Value.(*CellObservation); now.Sub(obs.Timestamp) < maxAge {
				cellObservations[i] = previousItem.Value.(*CellObservation)
			}
		}

		grid := grids[parent]
		job := CellFuseJob{
			Hash:         hash,
			CellCount:    cellCount[parent],
			Observations: cellObservations,
			OutGrid:      &grid,
		}

		wg.Add(1)
		jobs <- job
	}

	wg.Wait()

	encodedMessages := make(map[tiles.Quadkey][]byte)

	// TODO: Multi-threaded encoding
	for parent, cellz := range cells {
		cellList, err := grids[parent].Cells()
		if err != nil {
			continue
		}

		for i, c := range cellz {
			cellList.Set(i, c)
		}

		encodedMessage, err := messages[parent].MarshalPacked()
		if err != nil {
			continue
		}

		encodedMessages[parent] = encodedMessage
	}

	return encodedMessages
}

func fuseCell(hash tiles.Quadkey, cellCount *uint32, obs []*CellObservation, outGrid *schema.OccupancyGrid) (*CellObservation, error) {
	stateVector := []float32{0, 0, 0}
	now := time.Now()

	for _, o := range obs {
		stateRelation, err := o.Cell.State()
		if err != nil {
			continue
		}

		conf, state := stateRelation.Confidence(), stateRelation.Object()

		for i := 0; i < NStates; i++ {
			if i == int(state) {
				stateVector[i] += decay(conf, o.Timestamp, now)
			} else {
				stateVector[i] += decay(float32(math.Min(float64((1.0-conf)/NStates), 1.0/NStates))-0.001, o.Timestamp, now)
			}
		}
	}

	outCellList, err := outGrid.Cells()
	if err != nil {
		return nil, err
	}

	j := int(atomic.AddUint32(cellCount, 1) - 1)
	newCell := outCellList.At(j)

	newStateRelation, err := newCell.NewState()
	if err != nil {
		return nil, err
	}

	newOccupantRelation, err := newCell.NewOccupant()
	if err != nil {
		return nil, err
	}

	quadInt, err := quadKey2QuadInt(string(hash))
	if err != nil {
		return nil, err
	}

	meanStateVector := meanCellState(stateVector, int32(len(obs)))
	maxConf, maxState := getMaxState(meanStateVector)
	newStateRelation.SetConfidence(maxConf)
	newStateRelation.SetObject(maxState)

	newCell.SetHash(quadInt)
	newCell.SetState(newStateRelation)
	newCell.SetOccupant(newOccupantRelation)

	fusedObs := &CellObservation{
		Timestamp: time.Now(), // shouldn't matter ever, could be anything
		Hash:      hash,
		Cell:      &newCell,
	}

	return fusedObs, nil
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

func (s *GraphFusionService) countPresentCells(parent tiles.Quadkey) int32 {
	var count int32

	for _, qk := range s.gridKeys[parent] {
		if s.observations.Has(string(qk)) {
			count++
		}
	}

	return count
}

func (s *GraphFusionService) pushWorker(id int, messages <-chan []byte) {
	for msg := range messages {
		s.Push(msg)
	}
}

func (s *GraphFusionService) fuseWorker(id int, jobs <-chan CellFuseJob, results chan<- *CellObservation) {
	for job := range jobs {
		defer func() {
			recover()
			return
		}()

		// Do fusion work
		result, err := fuseCell(job.Hash, job.CellCount, job.Observations, job.OutGrid)
		if err != nil {
			return
		}
		results <- result
	}
}

func getMaxState(stateVector []float32) (float32, schema.GridCellState) {
	state := schema.GridCellState_unknown
	maxConf := float32(0.0)

	for i, conf := range stateVector {
		if conf > maxConf {
			maxConf = conf
			state = schema.GridCellState(i)
		}
	}
	return maxConf, state
}

func meanCellState(stateSumVector []float32, count int32) []float32 {
	return []float32{stateSumVector[0] / float32(count), stateSumVector[1] / float32(count), stateSumVector[2] / float32(count)}
}

func timeToFloat(t time.Time) float64 {
	return float64(t.UnixNano()) / math.Pow(10, 9)
}

func floatToTime(ts float64) time.Time {
	return time.Unix(int64(ts), int64(math.Remainder(ts, 1)*math.Pow(10, 9)))
}

func decay(val float32, t, now time.Time) float32 {
	tdiff := now.Sub(t).Milliseconds() / 100
	factor := math.Exp(float64(tdiff) * -1.0 * FusionDecayLambda)
	return val * float32(factor)
}
