# cd $1
# for f in $(for t in '*.h' '*.cpp' '*.c' '*.hpp' '*.cc' '*.hh' ; do find . -name "$t" ; done) ; do
#     if [[ "$f" =~ .*memhook.* ]]; then
#     	echo "   skipping file $f..."
#     	continue
#     fi
#     sed -i '1d' $f
# done
# echo "    Done."

cd $1
for f in $(for t in '*.h' '*.cpp' '*.c' '*.hpp' '*.cc' '*.hh' ; do find . -name "$t" ; done) ; do
    if [[ "$f" =~ .*memhook.* ]]; then
    	echo "   skipping file $f..."
    	continue
    fi
    sed -i "1s/^/#include \"memhook_interface.h\"\n/" $f
done
echo "    Done."