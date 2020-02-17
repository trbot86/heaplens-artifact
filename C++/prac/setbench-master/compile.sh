#!/bin/sh
# 
# File:   compile.sh
# Author: trbot
#
# Created on Jul 16, 2017, 8:53:32 PM
#

cd microbench
mkdir -p bin
make -j &
cd ..

cd macrobench
./compile.sh &
cd ..

wait
