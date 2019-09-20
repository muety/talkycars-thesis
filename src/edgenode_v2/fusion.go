package main

import (
	"./schema"
	"github.com/n1try/tiles"
)

type FusionService interface {
	Init()
	Push(senderId int, data interface{})
}

type TrafficSceneFusionService struct {
	Sector        tiles.Quadkey
	Keep          int
	GridTileLevel int
	gridKeys      []tiles.Quadkey
	observations  map[int][]schema.TrafficScene
}

func (s TrafficSceneFusionService) Init() {
	if gridKeys, err := s.Sector.ChildrenAt(s.GridTileLevel); err == nil {
		s.gridKeys = gridKeys
	} else {
		panic(err.Error())
	}
	s.observations = make(map[int][]schema.TrafficScene)
}

func (s TrafficSceneFusionService) Push(senderId int, data interface{}) {
	graph := data.(schema.TrafficScene)
	if _, ok := s.observations[senderId]; !ok {
		s.observations[senderId] = make([]schema.TrafficScene, 0)
	}
	s.observations[senderId] = append(s.observations[senderId], graph)
	if len(s.observations[senderId]) > s.Keep {
		s.observations[senderId] = s.observations[senderId][1:]
	}
}
