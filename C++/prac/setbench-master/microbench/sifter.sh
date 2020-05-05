#!/bin/bash

make_flag='false'
preload_flag='false'
files=''
verbose='false'

echo_color() {
    echo -e "\e[38;5;0;48;5;255m$1\e[0m"
}

print_usage() {
  echo -e "\e[38;5;0;48;5;255mUsage: -m to enable fresh compilation\n
-p to enable jemalloc preload\n
-v for verbose output\e[0m"
}

while getopts 'mpf:v' flag; do
  case "${flag}" in
    m) make_flag="true" ;;
    p) preload_flag="true" ;;
    f) files="${OPTARG}" ;;
    v) verbose='true' ;;
    *) print_usage
       exit 1 ;;
  esac
done

if [ $make_flag == 'true' ]
then
    echo_color "Fresh compilation started..."
    make ubench_howley_int_bst_lf.alloc_new.reclaim_none.pool_none.out 
fi

echo_color "removing previous info dump..."
rm info_t_dump.txt

if [ $preload_flag == 'true' ]
then
    echo_color "preloading jemalloc..."
    LD_PRELOAD=../lib/libjemalloc.so ./bin/ubench_howley_int_bst_lf.alloc_new.reclaim_none.pool_none.out -i 5 -d 5 -rq 0 -rqsize 1 -k 2000000 -nrq 0 -t 3000 -nwork 1
else
    echo_color "running without any special allocator..."
    ./bin/ubench_howley_int_bst_lf.alloc_new.reclaim_none.pool_none.out -i 5 -d 5 -rq 0 -rqsize 1 -k 2000000 -nrq 0 -t 3000 -nwork 1
fi

cd ../../../memhook

echo_color "removing previous temp db..."
rm db_output/temp.sqlite

echo_color "saving info_t_dump.txt to db_output/temp.sqlite..."
python3 saveallocstodb.py temp

cd ../visual
echo_color "starting visualisation routine..."
python3 bar_chart.py ../memhook/db_output/temp.sqlite 4096 64 "type like \"node_t<long long, void*>\" or type like \"operation_t<long long, void*>\""