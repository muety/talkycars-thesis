# TalkyCars

## Limitations
* Does not consider security
* Does only consider 2-dimensional road scenes (i.e. no bridges)
* Intersections and more complex lane types are not modeled

## Requirements
* Carla 0.9.6
* Python 3.7

## Setup
* `export PYTHONPATH=$PYTHONPATH:"$('pwd')/src/simulation"`
* `export PYTHONPATH=$PYTHONPATH:"$('pwd')/carla"`
* `export PYTHONPATH=$PYTHONPATH:"$('pwd')/carla/dist/carla-0.9.6-py3.5-linux-x86_64.egg"`
* `python3 -m venv .`
* `pip3 install -r requirements.txt`
* `cd src && python3 simulation/simulation.py`

## QuadTiles
| Tile Level | Ground Resolution @ Equator (m) |
|------------|---------------------------------|
| 1          | 20037508.352                    |
| 2          | 10018754.176                    |
| 3          | 5009377.088                     |
| 4          | 2504688.544                     |
| 5          | 1252344.272                     |
| 6          | 626172.136                      |
| 7          | 313086.068                      |
| 8          | 156543.034                      |
| 9          | 78271.517                       |
| 10         | 39135.758                       |
| 11         | 19567.879                       |
| 12         | 9783.939                        |
| 13         | 4891.969                        |
| 14         | 2445.984                        |
| 15         | 1222.992                        |
| 16         | 611.496                         |
| 17         | 305.748                         |
| 18         | 152.874                         |
| 19         | 76.437                          |
| 20         | 38.218                          |
| 21         | 19.109                          |
| 22         | 9.554                           |
| 23         | 4.777                           |
| 24         | 2.388                           |
| 25         | 1.194                           |
| 26         | 0.597                           |
| 27         | 0.298                           |
| 28         | 0.149                           |
| 29         | 0.074                           |
| 30         | 0.037                           |
| 31         | 0.018                           |

## Available Cars
* `vehicle.ford.mustang`
* `vehicle.audi.a2`
* `vehicle.audi.tt`
* `vehicle.bmw.isetta`
* `vehicle.carlamotors.carlacola`
* `vehicle.citroen.c3`
* `vehicle.harley-davidson.low rider`
* `vehicle.bmw.grandtourer`
* `vehicle.mercedes-benz.coupe`
* `vehicle.toyota.prius`
* `vehicle.dodge_charger.police`
* `vehicle.yamaha.yzf`
* `vehicle.nissan.patrol`
* `vehicle.bh.crossbike`
* `vehicle.tesla.model3`
* `vehicle.diamondback.century`
* `vehicle.gazelle.omafiets`
* `vehicle.seat.leon`
* `vehicle.lincoln.mkz2017`
* `vehicle.kawasaki.ninja`
* `vehicle.volkswagen.t2`
* `vehicle.nissan.micra`
* `vehicle.chevrolet.impala`
* `vehicle.mini.cooperst`
* `vehicle.jeep.wrangler_rubicon`