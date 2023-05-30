set -x
#delete old info_t, new_info_t_dump.txt, allocs.sqlite
bash -c "cd prac/$1/microbench/; rm info_dump allocs.sqlite binary_dump.txt fielddump.txt new_field_dump.txt fileset_dump.txt typedump.txt typeset_dump.txt malloc_type_dump.txt fixes.yaml"

#run static analysis to templatize malloc
bash -c "cd prac/$1/microbench/; python3 ~/sifter/type_analysis/run-clang-tidy.py -clang-tidy-binary ../../../type_analysis/clang-tidy-standalone/build/tool/clang-tidy -checks=misc-malloc-checker -header-filter=.* -j10 -p=./ "