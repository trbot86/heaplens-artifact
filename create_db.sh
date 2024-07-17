if [ "$#" -ne "1" ]; then
	echo "USAGE: $0 PROJECT_FOLDER"
	exit 1
fi

if ! [ -f $1/binary_dump.txt ]; then
    echo "ERROR the directory $1 does not contain binary_dump.txt"
    echo "(Did you forget to run your application?)"
    exit 1
fi

mv $1/binary_dump.txt type_analysis ; mv $1/fileset_dump.txt type_analysis ; mv $1/typeset_dump.txt type_analysis
mv $1/perfout.txt type_analysis ; mv $1/fielddump.txt type_analysis

cd type_analysis
if [ -f ./perfout.txt ]; then
    ./bin/convert_to_db --perf-file perfout.txt --field-dump fielddump.txt -t 2 -s 0.001 -c 4.0
else
    ./bin/convert_to_db --field-dump fielddump.txt -t 2 -s 0.001 -c 4.0
fi

echo "Done! Your database is in type_analysis/allocs.sqlite"