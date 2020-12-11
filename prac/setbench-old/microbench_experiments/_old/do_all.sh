#!/bin/bash

if [ "$#" -ne "0" ]; then
    testing="testing"
else
    testing=""
fi

outdir=output
flog=_log_do_all.txt
./_run_experiments.sh $testing | tee $flog \
    && ./_create_csv.sh | tee -a $flog \
    && ./_create_plots.sh | tee -a $flog \
    && cp ../../tools/gen_html/* ${outdir}/ \
    && cd ${outdir} \
    && ./_gen.sh "A simple experiment" "With rather sophisticated automated tooling!" | tee -a ../$flog

## cd .. && ../../tools/deploy_dir.sh ${outdir} setbench
