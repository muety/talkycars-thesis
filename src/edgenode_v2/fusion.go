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
	remoteKeys      []tiles.Quadkey
	gridKeys        map[tiles.Quadkey][]tiles.Quadkey
	observations    map[tiles.Quadkey]*deque.Deque
	cellCount       map[tiles.Quadkey]*uint32
	mutex1          *sync.Mutex
	mutex2          *sync.Mutex
}

var (
	lock1 sync.RWMutex = sync.RWMutex{}
	lock2 sync.RWMutex = sync.RWMutex{}
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

	s.observations = make(map[tiles.Quadkey]*deque.Deque)
	s.mutex1 = &sync.Mutex{}
	s.mutex2 = &sync.Mutex{}
}

func (s *GraphFusionService) Push(msg []byte) {
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

		lock1.Lock()
		if _, ok := s.observations[hash]; !ok {
			s.observations[hash] = deque.NewCappedDeque(FusionKeepObs)
		}

		s.observations[hash].Append(&CellObservation{
			Timestamp: ts,
			Hash:      hash,
			Cell:      &cell,
		})
		lock1.Unlock()
	}
}

func (s *GraphFusionService) Get(maxAge time.Duration) map[tiles.Quadkey][]byte {
	s.cellCount = make(map[tiles.Quadkey]*uint32)

	messages := make(map[tiles.Quadkey]*capnp.Message)
	scenes := make(map[tiles.Quadkey]schema.TrafficScene)
	grids := make(map[tiles.Quadkey]schema.OccupancyGrid)
	cells := make(map[tiles.Quadkey][]schema.GridCell)

	var wg sync.WaitGroup
	jobs := make(chan CellFuseJob)
	results := make(chan *CellObservation)

	defer close(jobs)
	defer close(results)

	// Start fuseWorker pool
	for w := 0; w < runtime.NumCPU(); w++ {
		go fuseWorker(w, jobs, results)
	}

	// Wait for results
	go func() {
		for obs := range results {
			parent := obs.Hash[:RemoteGridTileLevel]

			lock2.Lock()
			cells[parent] = append(cells[parent], *obs.Cell)
			lock2.Unlock()

			wg.Done()
		}
	}()

	lock1.RLock()

	for hash, cellDeque := range s.observations {
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
			s.cellCount[parent] = &c

			grid.SetCells(cellList)
			scene.SetTimestamp(timeToFloat(time.Now()))
			scene.SetOccupancyGrid(grid)

			messages[parent] = msg
			scenes[parent] = scene
			grids[parent] = grid

			lock2.Lock()
			cells[parent] = make([]schema.GridCell, 0)
			lock2.Unlock()
		}

		cellObservations := make([]*CellObservation, cellDeque.Size())
		previousItem := cellDeque.FirstElement()

		for i := 0; i < cellDeque.Size() && previousItem != nil; i++ {
			if i > 0 {
				previousItem = previousItem.Next()
			}

			if obs := previousItem.Value.(*CellObservation); time.Since(obs.Timestamp) < maxAge {
				cellObservations[i] = previousItem.Value.(*CellObservation)
			}
		}

		grid := grids[parent]
		job := CellFuseJob{
			Hash:         hash,
			CellCount:    s.cellCount[parent],
			Observations: cellObservations,
			OutGrid:      &grid,
		}

		wg.Add(1)
		jobs <- job
	}

	lock1.RUnlock()

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

	for _, o := range obs {
		stateRelation, err := o.Cell.State()
		if err != nil {
			continue
		}

		conf, state := stateRelation.Confidence(), stateRelation.Object()

		for i := 0; i < NStates; i++ {
			if i == int(state) {
				stateVector[i] += decay(conf, o.Timestamp)
			} else {
				stateVector[i] += decay(float32(math.Min(float64((1.0-conf)/NStates), 1.0/NStates))-0.001, o.Timestamp)
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
		if _, ok := s.observations[qk]; ok {
			count++
		}
	}

	return count
}

func fuseWorker(id int, jobs <-chan CellFuseJob, results chan<- *CellObservation) {
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

func decay(val float32, t time.Time) float32 {
	tdiff := time.Since(t).Milliseconds() / 100
	factor := math.Exp(float64(tdiff) * -1.0 * FusionDecayLambda)
	return val * float32(factor)
}
