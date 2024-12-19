#!/bin/bash

hugepage=""
name="sifter"

while [ $# -gt 0 ]; do
    case $1 in
        -h | --help)
            echo "HELP"
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
