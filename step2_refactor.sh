#!/bin/bash

if [ "$#" -ne "2" ] ; then
	echo "USAGE: %0 INPUT_FOLDER_PATH C_CPP_MAINFILE_PATH"
	echo "    input folder should be the copied source folder (that resulted from step1)"
	echo "    it will be refactored IN-PLACE."
#	echo "$# $0 $1 $2"
	exit 1
fi

	base=$(pwd)
	cd $1
	target=$(pwd)
	mainfile=$2

    cd $target
    echo -n "Copying memhook.h memhook_extern.h libmemhook.so to $target... "
    mkdir memhook
    cp $base/memhook/libmemhook.so .
    cp $base/memhook/memhook.h .
    cp $base/memhook/memhook_extern.h .
    echo "Done."
    echo

	echo "Refactoring malloc calls in $mainfile... refactored calls appear below."
	cd $target
	#for f in $(for t in '*.cpp' '*.c' '*.cc' ; do find . -name "$t" ; done) ; do
		$base/type_analysis/refactor $mainfile | grep "malloc<"
	#done
	echo "    Done."
	echo

	echo "Refactoring all c h cc hh cpp hpp files to include memhook_extern.h..."
	cd $target
    for f in $(for t in '*.h' '*.cpp' '*.c' '*.hpp' '*.cc' '*.hh' ; do find . -name "$t" ; done) ; do
    	if [[ "$f" =~ .*memhook.* ]]; then
    		echo "   skipping file $f..."
    		continue
    	fi
    	sed -i "1s/^/#include \"memhook_extern.h\"\n/" $f
   	done
   	echo "    Done."
	
	echo -n "Refactoring $mainfile to include memhook.h... "
   	sed -i "1s/^/#include \"memhook.h\"\n/" $mainfile
   	echo "Done."

	echo
    echo "Next you must modify your project build system to add: -lmemhook -L. -I." # as appropriate so that binaries are built with
#    echo
#    echo "    Then compile your project."
#    echo

#    export LD_LIBRARY_PATH=.

    echo "    ALSO NOTE: 'export LD_LIBRARY_PATH=.' is needed at runtime (to locate libmemhook.so)." ##" Done for you now..."
	echo
	read -p "Press any key to continue..."
	