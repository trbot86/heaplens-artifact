# Helper script for running the entire workflow of setbench with sifter
# TODO: check for correctness of script

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
    bash -c "cd ./memhook; make ubench_brown_ext_abtree_lf.alloc_new.reclaim_none.pool_none.out"
fi

echo_color "removing previous info dump..."
bash -c "cd prac/setbench/microbench/ ; rm info_t_dump.txt new_info_t_dump.txt"

if [ $preload_flag == 'true' ]
then
    echo_color "preloading jemalloc..."
    bash -c "cd ./prac/setbench/microbench/ ; LD_PRELOAD=../lib/libjemalloc.so ./bin/ubench_brown_ext_abtree_lf.alloc_new.reclaim_none.pool_none.out -nprefill 4 -i 0 -d 0 -rq 0 -rqsize 1 -k 200000 -nrq 0 -t 3000 -nwork 4"
else
    echo_color "running without any special allocator..."
    bash -c "cd ./prac/setbench/microbench/ ; ./bin/ubench_brown_ext_abtree_lf.alloc_new.reclaim_none.pool_none.out -nprefill 4 -i 0 -d 0 -rq 0 -rqsize 1 -k 200000 -nrq 0 -t 3000 -nwork 4"
fi

echo_color "removing spaces from class names in info_t_dump.txt"
bash -c "cd ./prac/setbench/microbench/ ; python3 ../../../type_analysis/trim_name.py ./info_t_dump.txt"

echo_color "removing previous temp db..."
bash -c "cd ./prac/setbench/microbench/ ; rm allocs.sqlite 2>/dev/null"

echo_color "saving info_t_dump.txt to allocs.sqlite..."
bash -c "cd ./prac/setbench/microbench/ ; python3 ../../../memhook/saveallocstodb.py new_info_t_dump.txt allocs.sqlite"

echo_color "starting visualisation routine..."
# python3 ../../../visual/cacheline_in_block.py allocs.sqlite 4096 64 "type like \"node_t<longlong,void*>\" or type like \"operation_t<longlong,void*>\""
# python3 ../../../visual/set_allocation.py allocs.sqlite 1024 64 "type like \"node_t<longlong,void*>\" or type like \"operation_t<longlong,void*>\""
# python3 ../../../visual/set_allocation.py allocs.sqlite 1024 64 "type like \"node_t<longlong,void*>\""
# python3 field_block_view.py ../prac/setbench_master/microbench/allocs.sqlite ../prac/setbench_master/microbench/fields.sqlite 1024 64 "type like \"node_t<longlong,void*>\""