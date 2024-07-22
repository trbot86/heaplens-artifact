#!/bin/bash

indir=""
outdir=""
database=false
template=false
skipRefactor=false
includesOnly=false
subdirectory=""
buildcmd="bear make"
perffile=""
fielddump=""
pagespertype=""
sample=""
cutoff=""

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
        -s | --subdir)
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
        --perf-file)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a file name with option --perf-file." >&2
                exit 1
            fi
            perffile="--perf-file $2"
            shift
        ;;
        --field-dump)
            if [[ -z "$2" || "$2" == -* ]]; then
                echo "Must specify a file name with option --field-dump." >&2
                exit 1
            fi
            fielddump="--field-dump $2"
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
    cd /root/sifter/$1
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
    if ! [ -f $indir/binary_dump.txt ]; then
        echo "ERROR the directory $indir does not contain binary_dump.txt"
        echo "(Did you forget to run your application?)"
        exit 1
    fi
    mv $indir/binary_dump.txt type_analysis ; mv $indir/fileset_dump.txt type_analysis ; mv $indir/typeset_dump.txt type_analysis
    mv $indir/perfout.txt type_analysis ; mv $indir/fielddump.txt type_analysis

    cd type_analysis
    make convert_to_db
    echo "./bin/convert_to_db $perffile $fielddump $pagespertype $sample $cutoff"
    ./bin/convert_to_db $perffile $fielddump $pagespertype $sample $cutoff
    exit 0
elif [ "$includesOnly" = true ]; then
    add_includes $indir
    exit 0
fi

cd clang-tidy-standalone
rm -rf build
mkdir build
cd build
if [ "$template" = true ]; then
    echo "About to build clang-tidy with templating ON"
    cmake -DCPP_TEMPLATE=ON ..
else
    echo "About to build clang-tidy with templating OFF"
    cmake -DCPP_TEMPLATE=OFF ..
fi
cmake --build .
cd ../..
echo "Done building clang-tidy"
echo ""

## goto memhook and compile

bash -c 'cd memhook ; make -j'
if [ "$?" -ne 0 ]; then echo "ERROR building memhook" ; exit 1 ; fi

## then goto type_analysis and compile

cd type_analysis
if ! [[ -d ./bin ]]; then
    mkdir bin
fi
make fieldandtypedumper
cd ..
if [ "$?" -ne 0 ]; then echo "ERROR building type analysis tool" ; exit 1 ; fi

## copy the project
rm -r $outdir ; cp -r $indir $outdir

echo ""
echo "codebase copied to $outdir"
echo ""
echo "next step: we will navigate to $outdir/$subdirectory and build your application using $buildcmd"
echo "           to generate a compilation_commands.json file."

cd $outdir/$subdirectory
eval "$buildcmd"
if [ "$?" -ne 0 ]; then echo "ERROR running build command" ; exit 1 ; fi
echo ""

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
    python3 /root/sifter/clang-tidy-standalone/tool/run-clang-tidy.py -clang-tidy-binary /root/sifter/clang-tidy-standalone/build/tool/clang-tidy -clang-apply-replacements-binary clang-apply-replacements-10 -checks=misc-malloc-checker -export-fixes=fixes.yaml
    echo "skipped refactoring step - fixes written to fixes.yaml"
else
    python3 /root/sifter/clang-tidy-standalone/tool/run-clang-tidy.py -clang-tidy-binary /root/sifter/clang-tidy-standalone/build/tool/clang-tidy -clang-apply-replacements-binary clang-apply-replacements-10 -checks=misc-malloc-checker -fix
    echo "performed refactoring with clang-tidy"
    add_includes $outdir
fi
# clang-apply-replacements-10 ./
if [ "$?" -ne 0 ]; then echo "ERROR templating mallocs" ; exit 1 ; fi
# rm fixes.yaml # commented for debugging
echo ""

echo "You need to include the memhook library in your Makefile:"
echo "-I/root/sifter/memhook/ -L/root/sifter/memhook/ -Wl,-rpath=/root/sifter/memhook/ -lmemhook -ldl"
echo ""
echo "Then compile (again) and run your application."
echo "  Note: if you want to include perf c2c data, run your application using"
echo "      perf c2c record <your_application>"
echo "  Then, run the following command:"
echo "      perf c2c report --stdio > perfout.txt"
echo "Afterwards, return to this directory and run sifter.sh --database $outdir/$subdir"
