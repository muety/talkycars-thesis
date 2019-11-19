# Serialization Benchmark

Compares three different serialization methods:
1. [Gob](https://godoc.org/encoding/gob)
2. [Cap'n'Proto](https://capnproto.org)
3. [Protocol Buffers](https://developers.google.com/protocol-buffers/docs/overview)

## Setup
* Install Protobuf
  * Download `protoc` from [GitHub](https://github.com/google/protobuf/releases) and add the binary to `$PATH`
  * `go get github.com/golang/protobuf/proto`
  * `go get -u github.com/golang/protobuf/protoc-gen-go`
* Install Cap'n'Proto
  * Install `capnp` compiler. See [official instructions](https://capnproto.org/install.html).
  * `go get -u -t zombiezen.com/go/capnproto2/...`

## Run
* `bash run.sh`

## Results
```
goos: linux
goarch: amd64
BenchmarkGob-12             5172            222607 ns/op
BenchmarkCapnp-12           4129            317576 ns/op
BenchmarkProto-12           7460            169135 ns/op
PASS
ok      _/home/ferdinand/dev/talkycars-thesis/src/evaluation/serialization      3.804s
CreateGob:       0.5322 ms/msg,         8.9372 KB/msg
CreateCapnp:     0.5907 ms/msg,         15.8170 KB/msg
CreateProto:     0.4396 ms/msg,         8.3755 KB/msg
```