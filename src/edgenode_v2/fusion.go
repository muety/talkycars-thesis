package main

import (
	"math"
	"sync"
	"time"

	"./schema"
	"github.com/n1try/tiles"
	capnp "zombiezen.com/go/capnproto2"
)

type CellObservation struct {
	Timestamp time.Time
	Hash      tiles.Quadkey
	Cell      *schema.GridCell
}

type CellFuseJob struct {
	Hash         tiles.Quadkey
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
	observations    map[tiles.Quadkey][]*CellObservation
	mutex1          *sync.Mutex
	mutex2          *sync.Mutex
}

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

	s.observations = make(map[tiles.Quadkey][]*CellObservation)
	s.mutex1 = &sync.Mutex{}
	s.mutex2 = &sync.Mutex{}

	go func() {
		for {
			time.Sleep(1 * time.Second)
			s.cleanUp()
		}
	}()
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

		s.mutex1.Lock()
		if _, ok := s.observations[hash]; !ok {
			s.observations[hash] = make([]*CellObservation, 0)
		}

		s.observations[hash] = append(s.observations[hash], &CellObservation{
			Timestamp: ts,
			Hash:      hash,
			Cell:      &cell,
		})
		s.mutex1.Unlock()
	}

	// TODO: Clear out-dated observations
}

func (s *GraphFusionService) Get(maxAge time.Duration) map[tiles.Quadkey][]byte {
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
	for w := 0; w < 8; w++ {
		go fuseWorker(w, jobs, results)
	}

	// Wait for results
	go func() {
		for obs := range results {
			parent := obs.Hash[:RemoteGridTileLevel]

			s.mutex2.Lock()
			cells[parent] = append(cells[parent], *obs.Cell)
			s.mutex2.Unlock()

			wg.Done()
		}
	}()

	s.mutex1.Lock()
	for hash, cellObservations := range s.observations {
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

			cellList, err := grid.NewCells(s.countPresentCells(parent))
			if err != nil {
				continue
			}

			grid.SetCells(cellList)
			scene.SetTimestamp(timeToFloat(time.Now()))
			scene.SetOccupancyGrid(grid)

			messages[parent] = msg
			scenes[parent] = scene
			grids[parent] = grid
			s.mutex2.Lock()
			cells[parent] = make([]schema.GridCell, 0)
			s.mutex2.Unlock()
		}

		grid := grids[parent]
		job := CellFuseJob{
			Hash:         hash,
			Observations: cellObservations,
			OutGrid:      &grid,
		}
		wg.Add(1)
		jobs <- job
	}
	s.mutex1.Unlock()

	wg.Wait()

	encodedMessages := make(map[tiles.Quadkey][]byte)

	s.mutex2.Lock()
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
	s.mutex2.Unlock()

	return encodedMessages
}

func fuseCell(hash tiles.Quadkey, obs []*CellObservation, outGrid *schema.OccupancyGrid) (*CellObservation, error) {
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

	newCell, err := schema.NewGridCell(outCellList.Segment())
	if err != nil {
		return nil, err
	}

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

func (s *GraphFusionService) cleanUp() {
	s.mutex1.Lock()
	for hash, observations := range s.observations {
		c := 0
		deleteIdxs := make([]bool, len(observations))

		for i, obs := range observations {
			deleteIdxs[i] = time.Since(obs.Timestamp) > GraphMaxAge
			if !deleteIdxs[i] {
				c++
			}
		}

		newObservations := make([]*CellObservation, c)
		for i, b := range deleteIdxs {
			if !b {
				newObservations = append(newObservations, observations[i])
			}
		}

		if len(newObservations) > 0 {
			s.observations[hash] = newObservations
		} else {
			delete(s.observations, hash)
		}
	}
	s.mutex1.Unlock()
}

func fuseWorker(id int, jobs <-chan CellFuseJob, results chan<- *CellObservation) {
	for job := range jobs {
		defer func() {
			recover()
			return
		}()

		result, err := fuseCell(job.Hash, job.Observations, job.OutGrid)
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
