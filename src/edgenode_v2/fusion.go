package main

import (
	"math"
	"time"

	"./schema"
	"github.com/n1try/tiles"
	capnp "zombiezen.com/go/capnproto2"
)

type GraphFusionService struct {
	Sector          tiles.Quadkey
	Keep            int
	GridTileLevel   int
	RemoteTileLevel int
	gridKeys        []tiles.Quadkey
	remoteKeys      []tiles.Quadkey
	observations    map[int][]schema.TrafficScene
}

func (s *GraphFusionService) Init() {
	if gridKeys, err := s.Sector.ChildrenAt(s.GridTileLevel); err == nil {
		s.gridKeys = gridKeys
	} else {
		panic(err.Error())
	}

	if remoteKeys, err := s.Sector.ChildrenAt(s.RemoteTileLevel); err == nil {
		s.remoteKeys = remoteKeys
	} else {
		panic(err.Error())
	}

	s.observations = make(map[int][]schema.TrafficScene)
}

func (s *GraphFusionService) Push(msg []byte) {
	graph, err := DecodeGraph(msg)
	if err != nil {
		return
	}

	measuredBy, err := graph.MeasuredBy()
	if err != nil {
		return
	}

	senderId := int(measuredBy.Id())

	if _, ok := s.observations[senderId]; !ok {
		s.observations[senderId] = make([]schema.TrafficScene, 0)
	}
	s.observations[senderId] = append(s.observations[senderId], *graph)
	if len(s.observations[senderId]) > s.Keep {
		s.observations[senderId] = s.observations[senderId][1:]
	}
}

func (s *GraphFusionService) Get(maxAge time.Duration) map[tiles.Quadkey][]byte {
	allObs := make([]schema.TrafficScene, 0, len(s.observations)*s.Keep)
	for _, observations := range s.observations {
		for _, o := range observations {
			ts := floatToTime(o.Timestamp())
			if time.Since(ts) < maxAge {
				allObs = append(allObs, o)
			}
		}
	}

	encodedMsgs := make(map[tiles.Quadkey][]byte)
	for parent, scene := range s.fuseScenes(allObs) {
		msg, err := scene.MarshalPacked()
		if err != nil {
			continue
		}
		encodedMsgs[parent] = msg
	}

	return encodedMsgs
}

func DecodeGraph(msg []byte) (*schema.TrafficScene, error) {
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

func (s *GraphFusionService) fuseScenes(scenes []schema.TrafficScene) map[tiles.Quadkey]*capnp.Message {
	cells := make([]schema.GridCell, 0)
	timestamps := make([]time.Time, 0)
	minTimestamp := timeToFloat(time.Now())

	messages := make(map[tiles.Quadkey]*capnp.Message)
	fusedScenes := make(map[tiles.Quadkey]schema.TrafficScene)
	fusedGrids := make(map[tiles.Quadkey]schema.OccupancyGrid)

	for _, parent := range s.remoteKeys {
		msg, seg, _ := capnp.NewMessage(capnp.SingleSegment(nil))
		fusedScene, err := schema.NewRootTrafficScene(seg)
		if err != nil {
			continue
		}

		fusedGrid, err := fusedScene.NewOccupancyGrid()
		if err != nil {
			continue
		}

		fusedScene.SetOccupancyGrid(fusedGrid)
		fusedScenes[parent] = fusedScene
		fusedGrids[parent] = fusedGrid
		messages[parent] = msg
	}

	for _, scene := range scenes {
		grid, err := scene.OccupancyGrid()
		if err != nil {
			continue
		}

		gridCells, err := grid.Cells()
		if err != nil {
			continue
		}

		for i := 0; i < gridCells.Len(); i++ {
			cells = append(cells, gridCells.At(i))
			timestamps = append(timestamps, floatToTime(scene.Timestamp()))
		}

		if scene.Timestamp() < minTimestamp {
			minTimestamp = scene.Timestamp()
		}
	}

	fusedCells := s.fuseCells(cells, timestamps, fusedGrids)
	for parent, cells := range fusedCells {
		fusedGrids[parent].SetCells(cells)
		fusedScenes[parent].SetTimestamp(timeToFloat(time.Now()))
		fusedScenes[parent].SetMinTimestamp(minTimestamp)
	}

	for parent := range messages {
		if _, ok := fusedCells[parent]; !ok {
			delete(messages, parent)
		}
	}

	return messages
}

func (s *GraphFusionService) fuseCells(cells []schema.GridCell, timestamps []time.Time, outGrids map[tiles.Quadkey]schema.OccupancyGrid) map[tiles.Quadkey]schema.GridCell_List {
	fusedCells := make(map[tiles.Quadkey]schema.GridCell_List)
	fusedCellCount := make(map[tiles.Quadkey]int)

	cellStateCount := make(map[tiles.Quadkey]int)
	cellStateVectors := make(map[tiles.Quadkey][]float32)

	for j, c := range cells {
		key, err := c.Hash()
		if err != nil {
			continue
		}
		hash := tiles.Quadkey(key)

		// 1. Fuse State Vector
		// TODO: Fuse occupants

		if _, ok := cellStateVectors[hash]; !ok {
			cellStateVectors[hash] = []float32{0, 0, 0} // Better: Use NStates
		}

		stateRelation, err := c.State()
		if err != nil {
			continue
		}

		conf, state := stateRelation.Confidence(), stateRelation.Object()

		for i := 0; i < NStates; i++ {
			if i == int(state) {
				cellStateVectors[hash][i] += decay(conf, timestamps[j])
				cellStateCount[hash]++
			} else {
				cellStateVectors[hash][i] += decay(float32(math.Min(float64((1.0-conf)/NStates), 1.0/NStates))-0.001, timestamps[j])
			}
		}
	}

	cellCount := int32(len(cellStateCount))

	for qk := range cellStateCount {
		parent := tiles.Quadkey(qk[:s.RemoteTileLevel])

		if _, ok := outGrids[parent]; !ok {
			continue
		}

		if _, ok := fusedCells[parent]; !ok {
			cellList, _ := outGrids[parent].NewCells(cellCount)
			fusedCells[parent] = cellList
			fusedCellCount[parent] = 0
		}

		cell, err := schema.NewGridCell(fusedCells[parent].Segment())
		if err != nil {
			continue
		}

		cellStateRelation, err := cell.NewState()
		if err != nil {
			continue
		}

		cellOccupantRelation, err := cell.NewOccupant()
		if err != nil {
			continue
		}

		if stateVector, ok := cellStateVectors[qk]; ok {
			meanStateVector := meanCellState(stateVector, cellStateCount[qk])
			maxConf, maxState := getMaxState(meanStateVector)
			cellStateRelation.SetConfidence(maxConf)
			cellStateRelation.SetObject(maxState)
		} else {
			cellStateRelation.SetConfidence(float32(0))
			cellStateRelation.SetObject(schema.GridCellState_unknown)
		}

		cell.SetHash(string(qk))
		cell.SetState(cellStateRelation)
		cell.SetOccupant(cellOccupantRelation)

		fusedCells[parent].Set(fusedCellCount[parent], cell)
		fusedCellCount[parent]++
	}

	return fusedCells
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

func meanCellState(stateSumVector []float32, count int) []float32 {
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
