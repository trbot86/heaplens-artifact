#!/bin/bash

## edit _fields_user.inc to change the data columns that are available to plot
source _fields_include_this.inc ## note: this include prints its own instructions when you run...

files=$(echo *_data/data*.txt)
echo "num_steps=$(echo $files | wc -w)"
eval "parallel \" ../../tools/fields.sh {} ${fields[@]} | tee {}.csv \" ::: $files"
echo "${fields[@]}" | tee data.csv
cat *_data/data*.txt.csv | sort -n >> data.csv
rm *_data/data*.txt.csv
