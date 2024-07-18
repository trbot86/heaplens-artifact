#!/bin/bash

docker images | grep -E "^sifter\s*latest "
if [ "$?" -ne "0" ]; then
    echo "Must build image before starting a container."
    exit 1
fi

## stop and remove any existing docker container named setbench
docker stop sifter 2>/dev/null
echo y | docker container rm sifter 2>/dev/null

## launch built docker image in a container
docker run -it --privileged --name sifter sifter