#!/bin/sh
set -x

# cp -r $1 refactoring_practice/
cd refactoring_practice/$(basename $1)
#bear make
~/sifter/C++/type_analysis/refactor $2
#g++ $2 memhook.cpp -pthread -Wall -g -o a.out
#./a.out