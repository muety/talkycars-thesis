#!/bin/bash
tar cf - data/evaluation/perception/actual/* | pigz > actual.tar.gz
tar cf - data/evaluation/perception/observed/* | pigz > observed.tar.gz