# 1st stage- ad-hoc filter for specific reult.
# 2nd stage- pivot the data, and group accordingly
# 3rd stage- plot the data

import sys, sqlite3, matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.cm import get_cmap
from matplotlib.lines import Line2D

# pd.set_option('display.max_rows', None)

def display(var):
    import inspect, re
    callingframe = inspect.currentframe().f_back
    cntext = "".join(inspect.getframeinfo(callingframe, 5)[3])
    m = re.search("display\s*\(\s*(\w+)\s*\)", cntext, re.MULTILINE)
    print(m.group(1), type(var), var)

def insertnewrow():
    global barchartdf
    global newdf
    global fieldstypedf

    typedict = {}
    # print(fieldstypedf.shape[1])
    for i in range(0,fieldstypedf.shape[0]):
        # print(fieldstypedf['CLASS'][i])
        if fieldstypedf['CLASS'][i] in typedict:
            typedict[fieldstypedf['CLASS'][i]].append((fieldstypedf['FIELD'][i], fieldstypedf['OFFSET'][i], fieldstypedf['SIZE'][i]))
        else:
            typedict[fieldstypedf['CLASS'][i]] = [(fieldstypedf['FIELD'][i], fieldstypedf['OFFSET'][i], fieldstypedf['SIZE'][i])]

    print("*********")
    print(typedict)
    print(typedict['node_t<longlong,void*>'])
    print("*********")

    rows = []
    # print(barchartdf.shape[0])
    for i in range(0, barchartdf.shape[0]):
        if barchartdf['TYPE'][i] in typedict:
            for cl, off, sz in typedict[barchartdf['TYPE'][i]]:
                print(barchartdf['TYPE'][i], cl, off, sz)
                # ADDRESS field redundant as clno and offset are already in use
                newdf = newdf.append({'CLASS': cl, 'ADDRESS': barchartdf['ADDRESS'][i], 'clno': barchartdf['clno'][i], 'blockno': barchartdf['blockno'][i], 'cloff': off, 'SIZE': sz}, ignore_index=True)
        # quit()
    print("*********")
    print("newdf:")
    print(newdf)
    print("*********")
    
    for i in range(0, newdf.shape[0]):
        if newdf['cloff'][i] + newdf['SIZE'][i] > xbytes:
            s = newdf.at[i,'SIZE']
            newdf.at[i,'SIZE'] = xbytes - newdf['cloff'][i]
            new_s = newdf.at[i,'SIZE']
            
            # print("s = "+ str(s))
            # print(new_s)
            
            quo = (s-new_s)//xbytes
            rem = (s-new_s)%xbytes
            # print(quo)
            for j in range(0,quo):
                new_row = pd.DataFrame(newdf[:][i:i+1]).copy(deep=True)
                new_row['clno'] = new_row['clno'] + j +1
                new_row['cloff'] = 0
                new_row['SIZE'] = xbytes
                rows.append(new_row)
            
            if rem != 0:
                new_row = pd.DataFrame(newdf[:][i:i+1]).copy(deep=True)
                new_row['clno'] = new_row['clno'] + quo + 1
                new_row['cloff'] = 0
                new_row['SIZE'] = rem
                rows.append(new_row)

    temp = newdf.append(rows)
    newdf = temp
    # # quit()

# This function gets the unique types in barchartdf and generates a dictionary of type -> unique color index (from 1 to Total number of distinct types)
# scheme represents the unique color index for every row in barchartdf
# function returns dict, the unique color indices, cmap, and the actual color values for each barchartdf row

def setcolormap():
    global barchartdf
    d = dict([(y,x+1) for x,y in enumerate(sorted(set(newdf['CLASS'])))])
    # print("DICTIONARY: ", d)
    cmap = get_cmap("rainbow", len(d))
    scheme = [(d[x]-1)/len(d) for x in newdf['CLASS']]
    # print(scheme)
    return d, set(scheme), cmap, cmap(scheme)


allocscon = sqlite3.connect(sys.argv[1])
fieldscon = sqlite3.connect(sys.argv[2])
blocksize = sys.argv[3]
xbytes = sys.argv[4]
typequery = sys.argv[5]

display(xbytes)

get_allocstypenames = "SELECT DISTINCT ALLOCS.TYPE FROM ALLOCS;"

get_fieldstypenames = "SELECT DISTINCT FIELDS.CLASS, FIELDS.FIELD, FIELDS.OFFSET, FIELDS.SIZE FROM FIELDS ORDER BY FIELDS.CLASS, FIELDS.OFFSET;"

blocklistquery = "select distinct address/" + blocksize + " as blockno from ALLOCS where (" + typequery + ")"

cache_query = "select type ,\
    address, \
    (address%" + blocksize + ")/" + xbytes + " as clno ,\
    address/" + blocksize + " as blockno ,\
    (address%" + xbytes + ") as cloff ,\
    size \
from \
    ALLOCS \
where (" + typequery + ") "

xbytes = int(xbytes)

allocstypedf = pd.read_sql_query(get_allocstypenames, allocscon)

print("**************")
print("printing distinct allocs types")
print(allocstypedf)
print("**************")

fieldstypedf = pd.read_sql_query(get_fieldstypenames, fieldscon)

print("**************")
print("printing classes, fields, offset and size")
print(fieldstypedf)
print("**************")

blocknodf = pd.read_sql_query(blocklistquery, allocscon)

print(blocknodf)

blockno = input("Enter block number: ")

cache_query += "and blockno like " + blockno 

print("**************")

print(cache_query)

print("**************")

barchartdf = pd.read_sql_query(cache_query, allocscon)

barchartdf['ADDRESS'] = barchartdf['ADDRESS'].apply(hex)

newdf = pd.DataFrame(columns=['CLASS', 'ADDRESS', 'clno', 'blockno', 'cloff', 'SIZE'])

print(barchartdf)

print("**************")

insertnewrow()

fig, gnt = plt.subplots()

gnt.set_xlabel('cache offset')
gnt.set_ylabel('cacheline')

plt.xticks(ticks=range(0,int(xbytes),8))
plt.yticks(ticks=range(0,int(newdf['clno'].max()),8))

gnt.set_xticks(ticks=range(0,int(xbytes),4), minor=True)
gnt.set_yticks(ticks=range(0,int(newdf['clno'].max()),2), minor=True)

gnt.grid(which='minor', alpha=0.8)
gnt.grid(True)

dct, mapping, clrmap, colormap = setcolormap()

custom_lines = [Line2D([0], [0], color=clrmap(x), lw=4) for x in mapping]
print(mapping)
print(clrmap)
print("custom_lines: ", [clrmap(x) for x in mapping])

gnt.set_prop_cycle(color=colormap)

gnt.hlines(newdf['clno'], newdf['cloff'], newdf['cloff']+newdf['SIZE'], color=colormap, linewidth=7)

gnt.legend(custom_lines, list(dct.keys()))

lastaddr = set()

for i, j , k in zip(newdf['clno'], newdf['cloff'], newdf['ADDRESS']):
        if not k in lastaddr:
            plt.text(j, i, str(k) , ha='left', va='center')
        lastaddr.add(k)

plt.show()