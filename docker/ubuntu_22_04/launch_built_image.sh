#!/bin/bash

args=(-it --privileged)

while [ $# -gt 0 ]; do
    case $1 in
        -h | --help)
            echo "HELP"
        ;;
        -p | --huge-page)
            echo "Launching image with hugepages mounted at /dev/hugepages"
            args=("-v/dev/hugepages:/dev/hugepages" "${args[@]}")
        ;;
        -n | --name)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a container name with option -n/--name." >&2
                exit 1
            fi
            args=("${args[@]}" --name "$2")
            shift
        ;;
    esac
    shift
done

docker images | grep -E "^sifter\s*latest "
if [ "$?" -ne "0" ]; then
    echo "Must build image before starting a container."
    exit 1
fi

## stop and remove any existing docker container named $name
#docker stop "$name" 2>/dev/null
#echo y | docker container rm "$name" 2>/dev/null

## launch built docker image in a container
echo "docker run ${args[@]} sifter"
docker run "${args[@]}" sifter
