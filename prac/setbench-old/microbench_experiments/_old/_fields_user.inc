#!/bin/bash

#################################
## fill the following variables/arrays with <FIELD NAMES>
## to get the desired results.
## - each <FIELD NAME> will be extracted from raw data files by grepping
##   for lines consisting of "<FIELD NAME>=[DATA]"
##
## ffile must contain a path to a *unique* source file for each row.
## fexp will determine which experimental configurations are plotted.
## fseries will determine the series for the plots.
## fx will determine the x-axis for the plots.
## fvalues will determine the y-axes for various plots.
##   note: if there are many fields in fvalues, you will get many plots
##         (one for each field in fvalues)
## fnoplot is for fields that you want in your CSV but NOT plotted
##
## a plot will be produced for each element in the cross product of:
## (unique sets of values taken on by the (set of) fields in fexp) and
## (the set of fields in fvalues).
##
## in other words, imagine you filter your data to the fields in fexp,
## then sort and unique that data to obtain rows {r1, r2, ...}, then take
## the cross product of {r1, r2, ...} and {fvalues[0], fvalues[1], ...}.
## there will be a plot for each element of that cross product.
## each such plot will have series fseries, x-axis fx, and
##   the y-axis will be one of {fvalues[0], fvalues[1], ...}.
##
## you should also provide a short name for each field in fexp,
##   starting with a hyphen ("-"). these go in fexp_short[].
## the purpose of short names is to label fexp fields in filenames.
## if you want to MERGE some fexp fields in output filenames,
##   just skip the leading "-" in the short name.
#################################

fexp+=( hostname )
fexp+=( INS_FRAC )
fexp+=( DEL_FRAC )
fexp+=( MAXKEY )

fseries=DS_TYPENAME
fx=TOTAL_THREADS

fvalues+=( total_throughput )
fvalues+=( PAPI_L2_TCM )
fvalues+=( PAPI_L3_TCM )
fvalues+=( PAPI_TOT_CYC )
fvalues+=( PAPI_TOT_INS )
fvalues+=( maxresident_mb )

fnoplot+=( step )

ffile=fname

fexp_short=( "-" "-i" "d" "-k" ) ## example: we are merging INS_FRAC and DEL_FRAC into a single field in the tagged experiment string (which will be used to create a filename for any output plots)
