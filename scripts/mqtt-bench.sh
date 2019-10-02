#!/bin/bash

# https://github.com/takanorig/mqtt-bench

# 100 concurrent clients, each sending messages of ~ 250 kb (~ one PEMTrafficScene @ radius 20)
# Requirement: For 10 Hz message rate, broker needs to be able to handle >= 1,000 msgs / sec
# Result : broker=tcp://localhost:1883, clients=100, totalCount=100000, duration=31949ms, throughput=3129.99messages/sec

mqtt-bench -action p -broker tcp://localhost:1883 -clients 100 -count 1000 -size 256000