#!/bin/bash

### no need to edit this file
### edit <_fields_user.inc> instead

source _fields_user.inc

_me="_fields_include_this.inc" #$(basename $0)

fields+=( ${fexp[@]} )
fields+=( ${fseries} )
fields+=( ${fx} )
fields+=( ${fvalues[@]} )
fields+=( ${fnoplot[@]} )
fields+=( ${ffile} )

num_fexp=${#fexp[@]}
num_fvalues=${#fvalues[@]}
num_fields=${#fields[@]}
num_fnoplot=${#fnoplot[@]}

ix_fexp_start=0
ix_fexp_end=$(($ix_fexp_start + $num_fexp - 1))
ix_fseries=$(($ix_fexp_end + 1))
ix_fx=$(($ix_fseries + 1))
ix_fvalues_start=$(($ix_fx + 1))
ix_fvalues_end=$(($ix_fvalues_start + $num_fvalues - 1))
ix_fnoplot_start=$(($ix_fvalues_end + 1))
ix_fnoplot_end=$(($ix_fnoplot_start + $num_fnoplot - 1))
ix_ffile=$(($ix_fnoplot_end + 1))

awkcols=""
for ((_i=$ix_fexp_start; _i<=$ix_fexp_end; ++_i)) ; do
    awkcols="$awkcols \" \" \$$((1+_i))"
done

echo
echo "$_me: ####################################################"
echo "$_me: ## Since you have included $_me"
echo "$_me: ## the following variables are available to you"
echo "$_me: ####################################################"
for ((_i=0;_i<${#fields[@]};++_i)) ; do
    echo "$_me: ## \${fields[$_i]}=${fields[$_i]}"
done
echo "$_me: ## "
for ((_i=0;_i<${#fexp[@]};++_i)) ; do
    echo "$_me: ## \${fexp[$_i]}=${fexp[$_i]}"
done
echo "$_me: ## "
for ((_i=0;_i<${#fvalues[@]};++_i)) ; do
    echo "$_me: ## \${fvalues[$_i]}=${fvalues[$_i]}"
done
echo "$_me: ## "
for ((_i=0;_i<${#fnoplot[@]};++_i)) ; do
    echo "$_me: ## \${fnoplot[$_i]}=${fnoplot[$_i]}"
done
echo "$_me: ## "
echo "$_me: ## \$ffile=$ffile"
echo "$_me: ## \$fseries=$fseries"
echo "$_me: ## \$fx=$fx"
echo "$_me: ## "
echo "$_me: ## \$ix_fexp_start=$ix_fexp_start"
echo "$_me: ## \$ix_fexp_end=$ix_fexp_end"
echo "$_me: ## \$ix_fseries=$ix_fseries"
echo "$_me: ## \$ix_fx=$ix_fx"
echo "$_me: ## \$ix_fvalues_start=$ix_fvalues_start"
echo "$_me: ## \$ix_fvalues_end=$ix_fvalues_end"
echo "$_me: ## "
for ((_i=0;_i<${#fexp_short[@]};++_i)) ; do
    echo "$_me: ## \${fexp_short[$_i]}=${fexp_short[$_i]}"
done
echo "$_me: ## "
# echo "$_me: ## For a list of columns defining an 'experiment'"
# echo "$_me: ## in a format that awk can print, we have:"
# echo "$_me: ##   \$awkcols='$awkcols'"
# echo "$_me: ## To use it, try: cat data.csv | awk \"{print \$awkcols}\""
# echo "$_me: ## "
echo "$_me: ## You also have access to function(s):"
echo "$_me: ##   get_unique_experiments"
echo "$_me: ##     --> produces global array \${experiments[@]}"
echo "$_me: ##     --> produces global array \${experiments_tagged[@]}"
echo "$_me: ####################################################"
echo

prepend_shortnames() {
    ## argument: a line containing a token for each column in ${fexp_short[@]}
    ## output: result of prepending each token in line with its short name (and deleting all spaces)
    local _line=$1
    local _i=0
    local _output=""
    for _w in $_line ; do
        _output="${_output}${fexp_short[$_i]}${_w} "
        _i=$((1+_i))
    done
    echo $(echo $_output | tr -d " ")
}

experiments=()
experiments_tagged=()
get_unique_experiments() {
    ## argument: name of a file containing space separated columns
    ## output: global array ${experiments[@]}
    local fcsv=$1
    local _i=0

    echo "$_me: ####################################################"
    echo "$_me: ## Verifying data contains the expected columns"
    echo "$_me: ## (as defined in _fields_user.inc)"
    echo "$_me: ####################################################"
    echo
    expheader="${fields[@]}"
    header=$(head -1 $fcsv)
    if [ "$header" != "$expheader" ]; then
        echo "UNEXPECTED HEADER $header"
        echo "Likely solution is to rerun _create_csv.sh"
        exit 1
    fi

    echo "$_me: ####################################################"
    echo "$_me: ## Reading data to determine unique experiments"
    echo "$_me: ####################################################"
    while read -r _exp ; do
        experiments[$_i]="$_exp"
        _i=$((1+_i))
    done < <(awk "{print $awkcols}" $fcsv | tail +2 | sort | uniq)

    for ((_i=0;_i<${#experiments[@]};++_i)) ; do
        echo "$_me: ## \${experiments[$_i]}=\"${experiments[$_i]}\""
    done
    echo "$_me: ####################################################"
    echo "$_me: ## Also producing 'tagged' experiment strings"
    echo "$_me: ####################################################"
    for ((_i=0;_i<${#experiments[@]};++_i)) ; do
        experiments_tagged[$_i]=$(prepend_shortnames "${experiments[$_i]}")
        echo "$_me: ## \${experiments_tagged[$_i]}=\"${experiments_tagged[$_i]}\""
    done
    echo "$_me: ####################################################"
    echo
}
