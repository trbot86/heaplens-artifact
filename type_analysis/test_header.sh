#!/bin/bash

set -x

#delete old info_t, new_info_t_dump.txt, allocs.sqlite, fixes.yaml
rm info_dump new_info_t_dump.txt fielddump.txt new_field_dump.txt typedump.txt malloc_type_dump.txt fixes.yaml allocs.sqlite binary_dump.txt fileset_dump.txt typedump.txt typeset_dump.txt malloc_type_dump.txt

#generate fielddump.txt and typedump.txt
./fieldandtypedumper compile_commands.json

#generate new_fielddump.txt
bash -c "python3 -c \"import sys;import trim_name; trim_name.trim_fields(\\\"fielddump.txt\\\")\""

#generate malloc_type_dump.txt
bash -c "./malloctypedumper compile_commands.json"

#run clang-tidy on project-->generate fixes.yaml -p=path/to/directory of compilecommands.json/
# ./run-clang-tidy.py -clang-tidy-binary=./clang-tidy -checks=misc-malloc-checker,misc-cstylemalloc-checker -header-filter=.* -export-fixes=fixes.yaml -j10 -p=./

#run clang-apply-replacements (supply directory path where files to refactor reside. Put fixes.yaml in the same folder)
# clang-apply-replacements ./

#make and run the project
make header
./header

#demarshall the data
./byte_rw binary_dump.txt

#generate allocs.sqlite table ALLOCS
bash -c "python3 ../memhook/savefieldstodb.py info_dump allocs.sqlite ALLOCS "

#generate allocs.sqlite FIELDS
bash -c "python3 ../memhook/savefieldstodb.py new_field_dump.txt allocs.sqlite FIELDS "

#generate allocs.sqlite MALLOCS
bash -c "python3 ../memhook/savefieldstodb.py malloc_type_dump.txt allocs.sqlite MALLOCS "

#generate allocs.sqlite FILEMAP
bash -c "python3 ../memhook/savefieldstodb.py fileset_dump.txt allocs.sqlite FILEMAP "

#generate allocs.sqlite TYPEMAP
bash -c "python3 ../memhook/savefieldstodb.py typeset_dump.txt allocs.sqlite TYPEMAP "

#update allocs with filename
bash -c "python3 ../memhook/savefieldstodb.py filename allocs.sqlite UPDATEALLOCSWITHFILE "

#update allocs with typename
bash -c "python3 ../memhook/savefieldstodb.py filename allocs.sqlite UPDATEALLOCSWITHTYPE "

#update allocs.sqlite
bash -c "python3 ../memhook/savefieldstodb.py filename allocs.sqlite ALLOCSWITHTYPES "

#run visualisation scripts
bash -c "python3 ../visual/cacheline_in_block.py allocs.sqlite 4096 64 \'1==1\' "

set +x