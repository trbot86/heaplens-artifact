This project is compatible to be used with both C and C++.
sifter/include contains the headers which have to be included in the main file of your project. sifter/memhook/ contains the .so for libmemhook which may be copied
into your project folder. libmemhook.so must be linked with your project. You may choose to run refactor tool in type_analysis/ to
change the malloc calls but it holds no guarantees for correct use as it is highly syntax dependent.

prac/setbench-master/microbench/sifter.sh does a complete toolchain run from running setbench to generating db to visualising it.

POSSIBLE ERROR SCENARIO:
--> trim_allocs_name.py removes all spaces in the class name column in info_t_dump.txt in order to join successfully with fields.sqlite. This may be error
prone in case where the condensed name matches a user specified class such as long long matching longlong. Keep this in mind while using the tool as SQL queries
won't work without condensed naming (You'll keep wondering why the tools won't work).
--> malloc type matching depends on file and line number of malloc call. If absolute file path is not used, then malloc type matching can fail.

List of file uses:
memhook.* : The main hook containing the overloaded alloc, dealloc calls with integrated tracking support.
type_analysis:
    clang_parser.cpp : parses test file to collect all record names (i.e. class, struct and union names).
    source_refactor.cpp : parses test file to replace alloc, dealloc calls with respective templated versions.
        memhook.* will later use the templated functions to log type information.
info_t_dump.txt:
list of alloc, frees in the following format:
	filename|type|line number|timestamp|memory size|address(in decimal)|typeofop
	typeofop = 1 if alloc
	typeofop = 0 if free
NOTE:

# THIS HAS CHANGED TO A DIFFERENT MECHANISM AND IS NOW OBSOLETE
# Always keep MEMHOOK_MAX_THREADS > 1 as it is highly likely that the parent thread will get slot first,
# and will never give up the only slot if MEMHOOK_MAX_THREADS = 1 as it is the last thread to exit, resulting in infinite loop for
# child threads.

## start in sifter/

./step1_copy.sh ../test_project ../test_project_refactored
./step2_refactor.sh ../test_project_refactored ../test_project_refactored/workload_timed.cpp

cd ../test_project_refactored
pico Makefile
make

## RUN THE TEST PROJECT WITH DESIRED SETTINGS

cd ../sifter
./step3_dbimport.sh ../test_project_refactored ../test_project_refactored/workload_timed.cpp

cd visual
python3 cacheline_in_block.py ../../test_project_refactored/allocs.sqlite 4096 64 '1==1'
python3 cacheline_in_block.py ../../test_project_refactored/allocs.sqlite 4096 64 'type like \"std::thread\"'
python3 cacheline_in_block.py ../../test_project_refactored/allocs.sqlite 2097152 4096 '1==1'

DEPLOYMENT:

In order to deploy sifter and capture the allocations in a real program, the program needs to be compiled with the memhook interface header, "memhook_interface.h"
Add the statement '#include "memhook_interface.h"' in the file that contains your main() function.

When building your project, make sure that the libmemhook.so shared object gets linked before any other shared library object that may have the same allocation symbols,
i.e libc and libstdc++.
Example of a correct linked order confirmed through ldd:$ ldd bin
	linux-vdso.so.1 (0x00007ffef5ee9000)
	libmemhook.so => ../../memhook/libmemhook.so (0x00007ff024658000)
	libdl.so.2 => /lib/x86_64-linux-gnu/libdl.so.2 (0x00007ff024454000)
	libstdc++.so.6 => /usr/lib/x86_64-linux-gnu/libstdc++.so.6 (0x00007ff0240cb000)
	libm.so.6 => /lib/x86_64-linux-gnu/libm.so.6 (0x00007ff023d2d000)
	libgcc_s.so.1 => /lib/x86_64-linux-gnu/libgcc_s.so.1 (0x00007ff023b15000)
	libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007ff023724000)
	/lib64/ld-linux-x86-64.so.2 (0x00007ff02495f000)

Here you can see that libmemhook.so is second from the top of the stack, before libstdc++.so and libc.so.

If you are preloading another memory allocator, or any other shared library and would like libmemhook to profile these allocations, make sure that you preload libmemhook, before
said shared libraries.
Example:
$ LD_PRELOAD="../../memhook/libmemhook.so:../setbench_master/lib/libjemalloc.so" bin

In this example ../setbench_master/lib/libjemalloc.so is a relative path to an instance of the jemalloc shared object.

DETAILED WORKFLOW (for general projects):
1. Copy your project into prac
2. Run static analysis to get type information from malloc and generate malloc_type_dump.txt, fielddump.txt, typedump.txt
	./bin/malloctypdumper compile_commands.json
	./bin/fieldandtypedumper compile_commands.json

	% This creates the files fielddump.txt, typedump.txt, malloc_type_dump.txt
   You may also choose to templatize any allocation function of your choice by using clang-tidy. If you do this and it works
   well, you don't need malloctypedumper.
   ./run-clang-tidy.py -clang-tidy-binary clang-tidy-standalone/build/tool/clang-tidy -checks=misc-malloc-checker -p=./ -export-fixes=fixes.yaml
    clang-apply-replacements ./
5. Trim names of object types:
	**don't know when to do this right now** python3 trim_name.py info_dump new_info_t_dump.txt
	python3 -c "import trim_name; trim_name.trim_fields(\"fielddump.txt\");"
3. Integrate memhook into project by changing Makefile, and adding memhook_interface.h in each c/cpp/h file.
4. Compile and run project.
	% Creates typeset_dump.txt, fileset_dump.txt, binary_dump.txt
5. convert binary_dump.txt to info_dump.
6. Import to DB:
	% creates DBs
	python3 savefieldstodb.py info_dump allocs.sqlite ALLOCS
	python3 savefieldstodb.py new_field_dump.txt allocs.sqlite FIELDS
	python3 savefieldstodb.py malloc_type_dump.txt allocs.sqlite MALLOCS
	python3 savefieldstodb.py fileset_dump.txt allocs.sqlite FILEMAP
	python3 savefieldstodb.py typeset_dump.txt allocs.sqlite TYPEMAP
	% does join
	python3 savefieldstodb.py placeholder allocs.sqlite UPDATEALLOCSWITHFILEANDTYPE
	python3 savefieldstodb.py placeholder allocs.sqlite ALLOCSWITHTYPES
7. Run visualisation scripts:
	python3 field_block_view.py allocsdb fieldsdb blocksize xbytes typequery
	python3 cacheline_in_block.py allocsdb blocksize xbytes typequery
	python3 cumulative_memory.py allocsdb allocsdb
	python3 set_allocation.py allocsdb setnum xbytes typequery

FUTURE DIRECTIONS, NOTES:
dump ast for easy traversal.

Command for finding a particular class in llvm library.
(find /lib/llvm-10/lib/ -type f -name "*.a" -exec nm --print-file-name "{}" \;) 2>1 | grep IncludeCategoryManager