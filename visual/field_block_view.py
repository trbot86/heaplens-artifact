# 1st stage- ad-hoc filter for specific reult.
# 2nd stage- pivot the data, and group accordingly
# 3rd stage- plot the data

import sys
import sqlite3
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import argparse
from matplotlib.cm import get_cmap
from matplotlib.lines import Line2D
from utils import insertnewrow

# pd.set_option('display.max_rows', None)


def display(var):
    import inspect
    import re
    callingframe = inspect.currentframe().f_back
    cntext = "".join(inspect.getframeinfo(callingframe, 5)[3])
    m = re.search("display\s*\(\s*(\w+)\s*\)", cntext, re.MULTILINE)
    print(m.group(1), type(var), var)


# def insertnewrow(barchartdf, newdf, fieldstypedf, xbytes, fieldtohighlight=None, verbose=False):
#     print("field to highlight: ", fieldtohighlight)
#     typedict = {}

#     # Convert field df to dictionary for fast access
#     for i in range(0, fieldstypedf.shape[0]):
#         if fieldstypedf['CLASS'][i] in typedict:
#             typedict[fieldstypedf['CLASS'][i]].append(
#                 (fieldstypedf['FIELD'][i], fieldstypedf['OFFSET'][i], fieldstypedf['SIZE'][i]))
#         else:
#             typedict[fieldstypedf['CLASS'][i]] = [
#                 (fieldstypedf['FIELD'][i], fieldstypedf['OFFSET'][i], fieldstypedf['SIZE'][i])]

#     if verbose:
#         print("*********")
#         print(typedict)
#         print(typedict['node_t<longlong,void*>'])
#         print("*********")

#     rows = []

#     if not fieldtohighlight:
#         for i in range(0, barchartdf.shape[0]):
#             if barchartdf['TYPE'][i] in typedict:
#                 for field, off, sz in typedict[barchartdf['TYPE'][i]]:
#                     if verbose:
#                         print(barchartdf['TYPE'][i], field, off, sz)
#                     # ADDRESS redundant as clno and offset are already in use
#                     newdf = newdf.append({'CLASS': field, 'ADDRESS': barchartdf['ADDRESS'][i], 'clno': barchartdf['clno']
#                                         [i], 'blockno': barchartdf['blockno'][i], 'cloff': off, 'SIZE': sz}, ignore_index=True)
#             else:
#                 newdf = newdf.append(barchartdf.iloc[i], ignore_index=True)
#     else:
#         for i in range(0, barchartdf.shape[0]):
#             if barchartdf['TYPE'][i] in typedict:
#                     for field, off, sz in typedict[barchartdf['TYPE'][i]]:
#                         if verbose:
#                             print(barchartdf['TYPE'][i], field, off, sz)
#                         # ADDRESS redundant as clno and offset are already in use
#                         if field == fieldtohighlight:
#                             newdf = newdf.append({'CLASS': field, 'TYPE':barchartdf['TYPE'][i], 'ADDRESS': barchartdf['ADDRESS'][i], 'clno': barchartdf['clno']
#                                                 [i], 'blockno': barchartdf['blockno'][i], 'cloff': off, 'SIZE': sz}, ignore_index=True)
#                         else:
#                             newdf = newdf.append({'CLASS': "nohighlight", 'TYPE':barchartdf['TYPE'][i], 'ADDRESS': barchartdf['ADDRESS'][i], 'clno': barchartdf['clno']
#                                                 [i], 'blockno': barchartdf['blockno'][i], 'cloff': off, 'SIZE': sz}, ignore_index=True)
#             else:
#                 print("type not in typedict: " + barchartdf.iloc[i])
#                 newdf = newdf.append(barchartdf.iloc[i], ignore_index=True)


#     if verbose:
#         print("*********")
#         print("newdf:")
#         print(newdf)
#         print("*********")

#     for i in range(0, newdf.shape[0]):
#         if newdf['cloff'][i] + newdf['SIZE'][i] > xbytes:
#             s = newdf.at[i, 'SIZE']
#             newdf.at[i, 'SIZE'] = xbytes - newdf['cloff'][i]
#             new_s = newdf.at[i, 'SIZE']

#             # print("s = "+ str(s))
#             # print(new_s)

#             quo = (s-new_s)//xbytes
#             rem = (s-new_s) % xbytes
#             # print(quo)
#             for j in range(0, quo):
#                 new_row = pd.DataFrame(newdf[:][i:i+1]).copy(deep=True)
#                 new_row['clno'] = new_row['clno'] + j + 1
#                 new_row['cloff'] = 0
#                 new_row['SIZE'] = xbytes
#                 rows.append(new_row)

#             if rem != 0:
#                 new_row = pd.DataFrame(newdf[:][i:i+1]).copy(deep=True)
#                 new_row['clno'] = new_row['clno'] + quo + 1
#                 new_row['cloff'] = 0
#                 new_row['SIZE'] = rem
#                 rows.append(new_row)

#     return newdf.append(rows)

# This function gets the unique types in barchartdf and generates a dictionary of type -> unique color index (from 1 to Total number of distinct types)
# scheme represents the unique color index for every row in barchartdf
# function returns dict, the unique color indices, cmap, and the actual color values for each barchartdf row

def setcolormap(barchartdf, newdf, verbose=True):
    d = dict([(y, x+1) for x, y in enumerate(sorted(set(newdf['CLASS'])))])
    
    if verbose:
        print("DICTIONARY: ", d)
    
    # Generate unique colors
    cmap = get_cmap("rainbow", len(d))

    # Assign color index [0, len(d)-1/len(d)] to each class
    scheme = [(d[x]-1)/len(d) for x in newdf['CLASS']]
    
    if verbose:
        print(scheme)
    
    # Return the dictionary mapping, unique color indices, color map, color values
    return d, sorted(set(scheme)), cmap, cmap(scheme)

def main():
    parser = argparse.ArgumentParser(
        description='Displays field-wise allocation pattern in caches')

    parser.add_argument("allocsdb", help="Path of allocation database")
    parser.add_argument("fielddb", help="Path of field database")
    parser.add_argument(
        "blocksize", help="Size of the block captured", type=int)
    parser.add_argument("xbytes", help="Size of cache line", type=int)
    parser.add_argument("typequery", help="SQL query to filter types")
    parser.add_argument("-v", "--verbose", help="Increase verbosity of output", action="store_true")
    parser.add_argument("-f", "--field", help="Highlight particular field")

    args = parser.parse_args()

    allocscon = sqlite3.connect(args.allocsdb)
    fieldscon = sqlite3.connect(args.fielddb)
    blocksize = args.blocksize
    xbytes = args.xbytes
    typequery = args.typequery
    fieldtohighlight = args.field

    display(xbytes)

    get_allocstypenames = "SELECT DISTINCT ALLOCSWITHTYPES.TYPE FROM ALLOCSWITHTYPES;"

    get_fieldstypenames = "SELECT DISTINCT FIELDS.CLASS, FIELDS.FIELD, FIELDS.OFFSET, FIELDS.SIZE FROM FIELDS ORDER BY FIELDS.CLASS, FIELDS.OFFSET;"

    blocklistquery = "select distinct address/" + str(blocksize) + "\
        as blockno from ALLOCSWITHTYPES where (" + typequery + ")"

    cache_query = "select type ,\
        address, \
        (address%" + str(blocksize) + ")/" + str(xbytes) + " as clno ,\
        address/" + str(blocksize) + " as blockno ,\
        (address%" + str(xbytes) + ") as cloff ,\
        size \
    from \
        ALLOCSWITHTYPES \
    where (" + typequery + ") "

    allocstypedf = pd.read_sql_query(get_allocstypenames, allocscon)

    if args.verbose:
        print("**************")
        print("printing distinct allocs types")
        print(allocstypedf)
        print("**************")

    fieldstypedf = pd.read_sql_query(get_fieldstypenames, fieldscon)

    if args.verbose:
        print("**************")
        print("printing classes, fields, offset and size")
        print(fieldstypedf)
        print("**************")

    blocknodf = pd.read_sql_query(blocklistquery, allocscon)

    print(blocknodf)

    blockno = input("Enter block number: ")

    cache_query += "and blockno like " + blockno

    if args.verbose:
        print("**************")
        print(cache_query)
        print("**************")

    barchartdf = pd.read_sql_query(cache_query, allocscon)

    barchartdf['ADDRESS'] = barchartdf['ADDRESS'].apply(hex)

    newdf = pd.DataFrame(
        columns=['CLASS', 'ADDRESS', 'clno', 'blockno', 'cloff', 'SIZE'])

    if args.verbose:
        print("**************")
        print("barchartdf:")
        print(barchartdf)
        print("**************")

    newdf = insertnewrow(barchartdf, newdf, fieldstypedf, xbytes, fieldtohighlight, args.verbose)

    fig, gnt = plt.subplots()

    gnt.set_xlabel('cache offset')
    gnt.set_ylabel('cacheline')

    plt.xticks(ticks=range(0, xbytes, 8))
    plt.yticks(ticks=range(0, int(newdf['clno'].max()), 8))

    gnt.set_xticks(ticks=range(0, xbytes, 4), minor=True)
    gnt.set_yticks(ticks=range(0, int(newdf['clno'].max()), 2), minor=True)

    gnt.grid(which='minor', alpha=0.8)
    gnt.grid(True)

    dct, mapping, clrmap, colormap = setcolormap(barchartdf, newdf, args.verbose)

    custom_lines = [Line2D([0], [0], color=clrmap(x), lw=4) for x in mapping]

    if args.verbose:
        print("**************")
        print(mapping)
        print(clrmap)
        print("custom_lines: ", [clrmap(x) for x in mapping])
        print("**************")

    gnt.set_prop_cycle(color=colormap)

    gnt.hlines(newdf['clno'], newdf['cloff'], newdf['cloff'] +
               newdf['SIZE'], color=colormap, linewidth=7)

    gnt.legend(custom_lines, list(dct.keys()))

    lastaddr = set()

    for i, j, k in zip(newdf['clno'], newdf['cloff'], newdf['ADDRESS']):
        if not k in lastaddr:
            plt.text(j, i, str(k), ha='left', va='center')
        lastaddr.add(k)

    plt.show()


if __name__ == "__main__":
    main()