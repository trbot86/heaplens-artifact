#!/bin/bash
set -x
if [ "$#" -ne "3" ] ; then
    echo "USAGE: %0 INPUT_FOLDER_PATH NAME_OF_INFO_T_DUMP.TXT C_CPP_MAINFILE_PATH"
    echo "    input folder should be the copied source folder (that resulted from step1)"
    exit 1
fi

base=$(pwd)
cd $1
target=$(pwd)



cd $base
infile=$1/$2
outfile=$1/allocs.sqlite

rows=$(cat $infile | wc -l)
echo "Importing $rows allocations into new sqlite db: \"$outfile\" ... "
rm $outfile 2>/dev/null
python3 memhook/saveallocstodb.py $infile $outfile
if [ "$?" -ne "0" ]; then echo "    ERROR importing allocations" ; exit 1 ; fi
echo "    Done."
echo



cd $target

echo "Running type_analysis/tool on $3... "
$base/type_analysis/tool $3 > /dev/null
if [ "$?" -ne "0" ]; then echo "    ERROR running type analysis tool" ; exit 1 ; fi
echo "    Done."
echo



cd $base

infile=$1/fielddump.txt
outfile=$1/fields.sqlite
rows=$(cat $infile | wc -l)
echo "Importing fields into sqlite db: \"$outfile\" ... "
rm $outfile 2>/dev/null
python3 memhook/savefieldstodb.py $infile $outfile
if [ "$?" -ne "0" ]; then echo "    ERROR importing fields" ; exit 1 ; fi
echo "Done."
echo

echo "Now you can visualize results using python scripts in visual/"
echo
set +x