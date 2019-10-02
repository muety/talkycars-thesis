# TalkyCars

## Limitations
* Does not consider security
* Does only consider 2-dimensional road scenes (i.e. no bridges)
* Intersections and more complex lane types are not modeled
* Clock inconsistencies are neglected (i.e. it is assumed that all clients as well as the server can retrieve a perfectly accurate and synchronized time)
* Low FPS and sensor rate 😞

## Requirements
* Python 3.7
  * You might want to use [pyenv](https://github.com/pyenv/pyenv) for version management
* Go 1.13
* [Carla](https://github.com/carla-simulator/carla) 0.9.6
* [Cap'n'Proto](https://capnproto.org/install.html) 0.7.0

## Setup
* `python3 -m venv ./venv`
* `pip3 install -r requirements.txt`
* `go get ./...`
* `go get -u -t zombiezen.com/go/capnproto2/...`

## Run
### Preparations
* Activate virtualenv: `source venv/bin/activate`
* Set some paths
  * `export PYTHONPATH=$PYTHONPATH:"$('pwd')/src/simulation"`
  * `export PYTHONPATH=$PYTHONPATH:"$('pwd')/carla"`
  * `export PYTHONPATH=$PYTHONPATH:"$('pwd')/carla/dist/carla-0.9.6-py3.7-linux-x86_64.egg"`
* Compile Cap'n'Proto schemas: `capnp compile -I$GOPATH/src/zombiezen.com/go/capnproto2/std -ogo:src/edgenode_v2/schema --src-prefix src/common/serialization/schema/capnp/go src/common/serialization/schema/capnp/go/*.capnp`
* Compile Cython extensions: `cd src/common/quadkey/tilesystem && python3 setup.py build_ext --inplace && cd ../../raycast && python3 setup.py build_ext --inplace && cd ../../..`
* Start Carla: `DISPLAY= ./CarlaUE4.sh -carla-server -windowed -ResX=800 -ResY=600 -opengl`
* Start HiveMQ: `docker run -p 1883:1883 --rm skobow/hivemq-ce`
  * If the broker is started on a different machine as any of the other modules, you need to specify `MQTT_BASE_HOSTNAME=<BROKER_IP>` as an environment variable on the machine running the respective module (e.g. `simulation` or `ego`)

### Run Modules (examples)
* Run a **simulation**: `src && python3 run.py sim --scene scene1`
* Run the **edge node** / server / RSU: `cd src && python3 run.py edge --debug --tile 1202032332303131`
  * **Alternatively:** Run **v2** (Go implementation) of the edge node: `cd src && python3 run.py edge2 --tile 1202032332303131`
* Run a standalone **ego** vehicle: `cd src && python3 run.py ego --rolename dummy --render false --debug true`
  * When running on a different machine as the simulator, add the `--host <HOST_IP>` argument.
* Run the **web** dashboard: `cd src && python3 run.py web`

### Further Improvements
* **QuadInt**s: Currently, an unpacked Cap'n'Proto message containing a radius-20 grid with level-24 cells without occupants is ~ 340 kBytes in size. By representing QuadKeys as 64-bit integers instead of strings (as done in [jquad](https://github.com/ethlo/jquad), for instance) could reduce the size to ~ 130 kBytes ([Trello Ticket #89](https://trello.com/c/BrxwRiMd)).  

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

## Compile Notes
* `export CPLUS_INCLUDE_PATH="$CPLUS_INCLUDE_PATH:/home/ferdinand/.pyenv/versions/3.7.4/include/python3.7m"`
* `export UE4_ROOT=/media/ferdinand/builddisk/UnrealEngine`
* Unreal: `./Engine/Build/BatchFiles/Mac/Build.sh ShaderCompileWorker Linux Development -verbose`
* Carla: `make package -j 8` 