cd $1
for f in $(for t in '*.h' '*.cpp' '*.c' '*.hpp' '*.cc' '*.hh' ; do find . -name "$t" ; done) ; do
    if [[ "$f" =~ .*memhook.* ]]; then
        echo "   skipping file $f..."
        continue
    fi
    if [[ "$2" == "delete" ]];
    then
        sed -i '1d' $f
    elif [[ "$2" == "add" ]];
    then
        sed -i "1s/^/#include \"memhook_interface.h\"\n/" $f
    fi
done
echo "    Done."
