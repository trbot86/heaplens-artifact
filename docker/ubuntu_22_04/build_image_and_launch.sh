#!/bin/bash

hugepage=""
name="sifter"

while [ $# -gt 0 ]; do
    case $1 in
        -h | --help)
            echo "Usage: ./build_image_and_launch.sh [options]"
            echo "options:"
            echo "-h/--help         Print this message"
            echo "-p/--huge-page    Mount huge pages at /dev/hugepages"
            echo "-n/--name [name]  Specify Docker container name"
            exit 0
        ;;
        -p | --huge-page)
            hugepage="--huge-page"
        ;;
        -n | --name)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a container name with option -n/--name." >&2
                exit 1
            fi
            name=$2
            shift
        ;;
    esac
    shift
done

./build_image.sh
./launch_built_image.sh --name "$name" "$hugepage"
