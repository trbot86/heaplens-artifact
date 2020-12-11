#!/bin/bash

## edit _fields_user.inc to change the data columns that are available to plot
source _fields_include_this.inc ## note: this include prints its own instructions when you run...

fcsv=data.csv
outdir=output

me=$(basename $0)

####################################################
## identify unique experiments in the data and store them in array ${experiments[@]}
####################################################

get_unique_experiments "$fcsv"

####################################################
## create one or more plots for each unique experiment.
## do this in parallel (for speed)
##   by creating strings for each plot construction command
##   then using gnu parallel to run all commands.
####################################################

##
## function to create a grouped bar plot from space-separated input data
##
plot_bars() {         ## arguments:
    local _fin=$1       ## input file containing space-separated data
    local _fout=$2      ## output image filename
    local _filter=$3    ## string to grep to filter data for this experiment
    local _ix_s=$4      ## index of a field in the ${fields[]} array to plot as series
    local _ix_fx=$5     ## index of a field in the ${fields[]} array to plot as x-axis values
    local _ix_fy=$6     ## index of a field in the ${fields[]} array to plot as y-axis values
    local _title=$7     ## title for graph

    ## note: we grep with SPACE/NEWLINE BEFORE/AFTER _filter
    ##       to ensure we are searching for an EXACT match over fields
    ##       (not searching neighbouring fields)
    grep -E "(^| )${_filter}( |$)" ${_fin} \
            | awk "{ print \$$((1+${_ix_s})), \$$((1+${_ix_fx})), \$$((1+${_ix_fy})) }" \
            | ../../tools/plotbars.py \
                    -o ${_fout} \
                    -t "${_title}" \
                    --legend-include \
                    --legend-columns 3 \
                    --width 12 \
                    --height 8
}
export -f plot_bars ## make function callable from subprocesses (like gnu parallel)

##
## function to append a visually distinct looking title to a file
##
append_title() {        ## arguments:
    local _fname=$1     ## file to which we should append
    local _title=$2     ## title to embed in the header
    echo "################################################################################" >> ${_fname}
    echo "################################################################################" >> ${_fname}
    echo "#### ${_title}" >> ${_fname}
    echo "################################################################################" >> ${_fname}
    echo "################################################################################" >> ${_fname}
    echo >> ${_fname}
}
export -f append_title  ## make function callable from subprocesses (like gnu parallel)

##
## function to create a data-log (for more info on a particular plot)
## by concatenating all of the raw data files that are used to produce the plot
##
create_datalog() {      ## arguments:
    local _fin=$1       ## input file containing space-separated data
    local _fout=$2      ## output filename
    local _filter=$3    ## string to grep to filter data for this experiment
    local _ix_f=$4      ## index in the ${fields[]} array of a column containing raw data filenames

    ## note: we grep with SPACE/NEWLINE BEFORE/AFTER _filter
    ##       to ensure we are searching for an EXACT match over fields
    ##       (not searching neighbouring fields)

    rm ${_fout} 2>/dev/null
    append_title ${_fout} "Table of space-separated values"

    ## add header + filtered rows to outfile
    ( (head -1 ${_fin} && grep -E "(^| )${_filter}( |$)" ${_fin}) | column -t ) >> ${_fout}

    ## get list of files to include from filtered rows
    files=$(grep -E "(^| )${_filter}( |$)" ${_fin} | awk "{print \$$((1+${_ix_f}))}")

    ## add some white space
    for ((_i=0;_i<30;++_i)) ; do echo >> ${_fout} ; done

    for f in $files ; do
        ## harness current working directory to shorten filename
        dir="$(pwd)/"
        dir_escaped=${dir//\//\\/}
        fshort=$(echo $f | sed "s/${dir_escaped}//g")

        # echo "f=$f fshort=$fshort dir=$dir"

        ## append raw data file f
        append_title ${_fout} "file: ${fshort}"
        cat ${f} >> ${_fout}
        for ((_i=0;_i<30;++_i)) ; do echo >> ${_fout} ; done
    done
}
export -f create_datalog ## make function callable from subprocesses (like gnu parallel)

echo
echo "$me: ####################################################"
echo "$me: ## Building commands for plot generation"
echo "$me: ####################################################"
cmds=()
for ((i=0; i<${#experiments[@]}; ++i)); do

    ## create data log file (text) for each experiment
    outfile="${outdir}/datalog${experiments_tagged[$i]}.txt"
    cmd="create_datalog '$fcsv' '${outfile}' '${experiments[$i]}' '$ix_ffile'"
    cmds+=("$cmd") ; echo "$me: ## $cmd"

    ## create a plot for EACH value field (each choice of y-axis)
    for ((ix_fy=${ix_fvalues_start}; ix_fy<=${ix_fvalues_end}; ++ix_fy)) ; do
        outfile="${outdir}/${fields[$ix_fy]}${experiments_tagged[$i]}.png"
        title="${fields[$ix_fy]} vs ${fields[$ix_fx]}"
        cmd="plot_bars '$fcsv' '${outfile}' '${experiments[$i]}' '$ix_fseries' '$ix_fx' '$ix_fy' '$title'"
        cmds+=("$cmd") ; echo "$me: ## $cmd"
    done
done

echo
echo "$me: ####################################################"
echo "$me: ## Running commands with GNU parallel"
echo "$me: ####################################################"
echo
rm -rf $outdir
mkdir $outdir
parallel ::: "${cmds[@]}"
# parallel ::: "${cmds[0]}" "${cmds[1]}"

echo
echo "$me: ####################################################"
echo "$me: ## Verifying number of images created"
echo "$me: ####################################################"
echo
numpng=`ls ${outdir}/*.png | wc -l`
exp_numpng=$((${#experiments[@]} * ${#fvalues[@]}))
if [ "$numpng" != "$exp_numpng" ]; then
    echo
    echo "$me: ######################################################"
    echo "$me: ## ERROR: we were supposed to create $exp_numpng new images, but there are $numpng in ${outdir}"
    echo "$me: ######################################################"
    echo
    exit 1
else
    echo "Done."
fi
