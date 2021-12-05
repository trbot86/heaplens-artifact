set -x
#delete old info_t, new_info_t_dump.txt, allocs.sqlite
bash -c "cd prac/setbench/macrobench/; rm info_dump allocs.sqlite binary_dump.txt fielddump.txt new_field_dump.txt fileset_dump.txt typedump.txt typeset_dump.txt malloc_type_dump.txt"

# Run macrobench
bash -c "cd prac/setbench/macrobench/; numactl -i all ./bin/rundb_TPCC_brown_ext_abtree_lf -t10 -s10000000 -r0.9 -w0.1 "

#demarshall data
bash -c "cd prac/setbench/macrobench/; ../../tiny/byte_rw.bin binary_dump.txt "

# #generate fielddump.txt and typedump.txt
# bash -c "cd prac/setbench/macrobench/; ../../../type_analysis/fieldandtypedumper compile_commands.json"

# #generate new_fielddump.txt
# bash -c "cd prac/setbench/macrobench/; python3 -c \"import sys;sys.path.append(\\\"../../../type_analysis/\\\");import trim_name; trim_name.trim_fields(\\\"fielddump.txt\\\")\""

# #generate malloc_type_dump.txt
# bash -c "cd prac/setbench/macrobench/; ../../../type_analysis/malloctypedumper compile_commands.json"

#generate allocs.sqlite table ALLOCS
bash -c "cd prac/setbench/macrobench/; python3 ../../../memhook/savefieldstodb.py info_dump allocs.sqlite ALLOCS "

#generate allocs.sqlite FIELDS
bash -c "cd prac/setbench/macrobench/; python3 ../../../memhook/savefieldstodb.py new_field_dump.txt allocs.sqlite FIELDS "

#generate allocs.sqlite MALLOCS
bash -c "cd prac/setbench/macrobench/; python3 ../../../memhook/savefieldstodb.py malloc_type_dump.txt allocs.sqlite MALLOCS "

#generate allocs.sqlite FILEMAP
bash -c "cd prac/setbench/macrobench/; python3 ../../../memhook/savefieldstodb.py fileset_dump.txt allocs.sqlite FILEMAP "

#generate allocs.sqlite TYPEMAP
bash -c "cd prac/setbench/macrobench/; python3 ../../../memhook/savefieldstodb.py typeset_dump.txt allocs.sqlite TYPEMAP "

#update allocs with filename
bash -c "cd prac/setbench/macrobench/; python3 ../../../memhook/savefieldstodb.py filename allocs.sqlite UPDATEALLOCSWITHFILE "

#update allocs with typename
bash -c "cd prac/setbench/macrobench/; python3 ../../../memhook/savefieldstodb.py filename allocs.sqlite UPDATEALLOCSWITHTYPE "

#update allocs.sqlite
bash -c "cd prac/setbench/macrobench/; python3 ../../../memhook/savefieldstodb.py filename allocs.sqlite ALLOCSWITHTYPES "

#run visualisation scripts
bash -c "cd prac/setbench/macrobench/; python3 ../../../visual/cacheline_in_block.py allocs.sqlite 4096 64 \'1==1\' "

set +x