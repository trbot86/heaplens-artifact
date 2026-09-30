#!/bin/bash
set -eo pipefail

indir=""
outdir=""
database=false
template=false
skipRefactor=false
includesOnly=false
placementNew=true
subdirectory=""
buildcmd="bear -- make"
perffile=""
fielddump=""
pagespertype=""
sample=""
samplingSeed=()
cutoff=""
threads=1
pageSize="--page-size 4096"
fragGran=""

while [ $# -gt 0 ]; do
    case $1 in
        -h | --help)
            echo "HELP"
        ;;
        -d | --database)
            database=true
        ;;
        -t | --template)
            template=true
        ;;
        -s | --subdirectory)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a subdirectory with option -s/--subdir." >&2
                exit 1
            fi
            subdirectory=$2
            shift
        ;;
        -b | --build)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a build command with option -b/--build." >&2
                exit 1
            fi
            buildcmd=$2
            shift
        ;;
        --no-pnew)
            placementNew=false
        ;;
        -j | --threads)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify number of threads with option -j/--threads." >&2
                exit 1
            fi
            threads=$2
            shift
        ;;
        --perf-file)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a file name with option --perf-file." >&2
                exit 1
            fi
            perffile=$2
            shift
        ;;
        --field-dump)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a file name with option --field-dump." >&2
                exit 1
            fi
            fielddump=$2
            shift
        ;;
        --pages-per-type)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a number with option --pages-per-type." >&2
                exit 1
            fi
            pagespertype="-t $2"
            shift
        ;;
        --seed)
            if ! [[ "$2" =~ ^[0-9]+$ ]]; then
                echo "Must specify a nonnegative integer with option --seed." >&2
                exit 1
            fi
            samplingSeed=(--seed "$2")
            shift
        ;;
        --sample)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a number between 0.0 and 1.0 with option --sample." >&2
                exit 1
            fi
            sample="-s $2"
            shift
        ;;
        --cutoff)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a number between 0.0 and 100.0 with option --cutoff." >&2
                exit 1
            fi
            cutoff="-c $2"
            shift
        ;;
        --skip-refactor)
            skipRefactor=true
        ;;
        --includes-only)
            includesOnly=true
        ;;
        --page-size)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a page size with option --page-size." >&2
                exit 1
            fi
            pageSize="--page-size $2"
            shift
        ;;
        -r | --fragmentation)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a fragmentation granularity with option -r/--fragmentation." >&2
                exit 1
            fi
            fragGran="-r $2"
            shift
        ;;
        *)
            if [ -z "$indir" ]; then
                indir=$1
            elif [ -z "$outdir" ]; then
                outdir=$1
            else
                echo "Unknown option $1." >&2
                exit 1
            fi
        ;;
    esac
    shift
done

add_includes () {
    echo "refactoring all c h cc hh cpp hpp files to include memhook_interface.h..."
    # NOTE: was `cd ./$1`, which silently resolves to a bogus, nonexistent
    # relative path (and fails to cd, without aborting the script) whenever
    # $1 is an absolute path -- e.g. `./sifter.sh /abs/path --includes-only`.
    # The `find . -name ...` below then ran from whatever directory the cd
    # left it in instead, in practice injecting memhook_interface.h includes
    # into every source file in the repository, including vendored/unrelated
    # ones. `cd -- "$1"` works for both relative and absolute paths.
    cd -- "$1" || { echo "ERROR: add_includes: cannot cd to '$1'" >&2; exit 1; }
    for f in $(for t in '*.h' '*.cpp' '*.c' '*.hpp' '*.cc' '*.hh' ; do find . -name "$t" ; done) ; do
        if [[ "$f" =~ .*memhook.* ]] || grep -q '#include "memhook_interface.h"' $f; then
            echo "   skipping file $f..."
            continue
        fi
        echo '#include "memhook_interface.h"' >> TEMP_MEMHOOK_INCLUDE
        cat $f >> TEMP_MEMHOOK_INCLUDE
        mv TEMP_MEMHOOK_INCLUDE $f
    done
    echo "    Done."
    echo ""
}

if [ -z "$indir" ]; then
    echo "Must specify an input directory"
    exit 1
elif [ -z "$outdir" -a "$database" = false -a "$includesOnly" = false ]; then
    echo "USAGE: sifter.sh INPUT_FOLDER OUTPUT_FOLDER"
	echo "      output folder will be created"
    echo "      (or run with --database flag to create a database after running experiment)"
    exit 1
elif [ "$database" = true ]; then
    if ! [ -z $subdirectory ]; then
        indir="$indir"/"$subdirectory"
    fi
    if ! [ -f $indir/binary_dump.txt ]; then
        echo "ERROR the directory $indir does not contain binary_dump.txt"
        echo "(Did you forget to run your application?)"
        exit 1
    fi
    # Preserve this run's trace when another conversion reuses the scratch area.
    # Reflinks avoid a full copy where the filesystem supports them.
    cp --reflink=auto -- "$indir/binary_dump.txt" type_analysis/ || exit 1
    cp -- "$indir/typeset_dump.txt" type_analysis/ || exit 1
    cp -- "$indir/fileset_dump.txt" type_analysis/ || exit 1
    if ! [[ -z "$perffile" ]]; then
        cp "$indir"/"$perffile" type_analysis || exit 1
        perffile="--perf-file $perffile"
    fi
    if ! [[ -z "$fielddump" ]]; then
        cp "$indir/$fielddump" type_analysis || exit 1
        fielddump="--field-dump $fielddump"
    fi

    cd type_analysis || exit 1
    rm -f allocs.sqlite
    make bin/convert_to_db || exit 1
    echo "./bin/convert_to_db -j $threads $pageSize $perffile $fielddump $pagespertype $sample $cutoff $fragGran ${samplingSeed[*]}"
    ./bin/convert_to_db -j $threads $pageSize $perffile $fielddump $pagespertype $sample $cutoff $fragGran "${samplingSeed[@]}"
    exit $?
elif [ "$includesOnly" = true ]; then
    add_includes $indir
    exit 0
fi

cd clang-tidy-standalone
# Do not reuse the distributed cache, which embeds its author's absolute paths.
mkdir -p build-heaplens
cd build-heaplens

cmakeOptions=""
if [ "$template" = true ]; then
    echo "About to build clang-tidy with templating ON"
    cmakeOptions="-DCPP_TEMPLATE=ON"
else
    echo "About to build clang-tidy with templating OFF"
    cmakeOptions="-DCPP_TEMPLATE=OFF"
fi
if [ "$placementNew" = true ]; then
    echo "About to build clang-tidy with placement new logging ON"
    cmakeOptions="$cmakeOptions -DCPP_PLACEMENT_NEW=ON"
else
    echo "About to build clang-tidy with placement new logging OFF"
    cmakeOptions="$cmakeOptions -DCPP_PLACEMENT_NEW=OFF"
fi

cmake $cmakeOptions ..
cmake --build .
cd ../..
echo "Done building clang-tidy"
echo ""

## goto memhook and compile

if [ "$template" = true ]; then
    bash -c 'cd memhook ; make USE_TEMPLATE=1 -j'
else
    bash -c 'cd memhook ; make -j'
fi
if [ "$?" -ne 0 ]; then echo "ERROR building memhook" ; exit 1 ; fi

## then goto type_analysis and compile

cd type_analysis
rm -f binary_dump.txt fileset_dump.txt typeset_dump.txt
if ! [[ -d ./bin ]]; then
    mkdir bin
fi
make fieldandtypedumper
cd ..
if [ "$?" -ne 0 ]; then echo "ERROR building type analysis tool" ; exit 1 ; fi

## copy the project
if [[ -e "$outdir" ]]; then
    echo "ERROR: output directory already exists: $outdir (use a fresh directory)" >&2
    exit 1
fi
cp -r "$indir" "$outdir"

echo ""
echo "codebase copied to $outdir"
echo ""
echo "next step: we will navigate to $outdir/$subdirectory and build your application using $buildcmd"
echo "           to generate a compilation_commands.json file."

cd $outdir/$subdirectory
eval "$buildcmd"
if [ "$?" -ne 0 ]; then echo "ERROR running build command" ; exit 1 ; fi
echo ""

# TODO fix this
echo "performing field extraction..."
/root/sifter/type_analysis/bin/fieldandtypedumper compile_commands.json
if [ "$?" -ne 0 ]; then echo "ERROR running field extraction" ; exit 1 ; fi
echo ""

if [ "$template" = true ]; then
    echo "templating mallocs..."
else
    echo "replacing malloc with malloc_s..."
fi
if [ "$skipRefactor" = true ]; then
    python3 /root/sifter/clang-tidy-standalone/tool/run-clang-tidy.py -j 1 -clang-tidy-binary /root/sifter/clang-tidy-standalone/build-heaplens/tool/clang-tidy -clang-apply-replacements-binary clang-apply-replacements-14 -checks=-*,misc-allocation-logging -export-fixes=fixes.yaml
    echo "skipped refactoring step - fixes written to fixes.yaml"
else
    python3 /root/sifter/clang-tidy-standalone/tool/run-clang-tidy.py -j 1 -clang-tidy-binary /root/sifter/clang-tidy-standalone/build-heaplens/tool/clang-tidy -clang-apply-replacements-binary clang-apply-replacements-14 -checks=-*,misc-allocation-logging -fix
    echo "performed refactoring with clang-tidy"
    add_includes $outdir
fi
if [ "$?" -ne 0 ]; then echo "ERROR templating mallocs" ; exit 1 ; fi
echo ""

cd /root/sifter
cp type_analysis/fileset_dump.txt $outdir/$subdirectory
if [ "$template" = false ]; then
    cp type_analysis/typeset_dump.txt $outdir/$subdirectory
fi

echo "You need to include the memhook library in your Makefile:"
echo "-I/root/sifter/memhook/ -L/root/sifter/memhook/ -Wl,-rpath=/root/sifter/memhook/ -lmemhook -ldl"
echo ""
echo "Then compile (again) and run your application."
echo "  Note: if you want to include perf c2c data, run your application using"
echo "      perf c2c record --all-user <your_application>"
echo "  Then, run the following command:"
echo "      perf c2c report --stdio > perfout.txt"
echo "Afterwards, return to this directory and run sifter.sh --database $outdir/$subdir"
