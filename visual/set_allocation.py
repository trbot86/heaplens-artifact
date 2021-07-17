# 1st stage- ad-hoc filter for specific reult.
# 2nd stage- pivot the data, and group accordingly
# 3rd stage- plot the data

import sys, sqlite3, matplotlib.pyplot as plt
import math
import numpy as np
import pandas as pd
from matplotlib.cm import get_cmap

# pd.set_option('display.max_rows', None)

def display(var):
    import inspect, re
    callingframe = inspect.currentframe().f_back
    cntext = "".join(inspect.getframeinfo(callingframe, 5)[3])
    m = re.search("display\s*\(\s*(\w+)\s*\)", cntext, re.MULTILINE)
    print(m.group(1), type(var), var)

def insertnewrow():
    global barchartdf
    global ycount
    global setnum
    print(len(ycount))
    for i in range(0, barchartdf.shape[0]):
        sno = int((int(barchartdf['ADDRESS'][i], 16)/xbytes)%setnum)
        # print(barchartdf['ADDRESS'][i],sno)
        # print(barchartdf['SIZE'][i])
        it = int(math.ceil(barchartdf['SIZE'][i]/xbytes))
        # print("it: ",it)
        for j in range(sno,sno+it):
            ycount[j%setnum] = ycount[j%setnum]+1
            # print(ycount[j%setnum])
            # print(j,setnum, j%setnum)
            # quit()
        # quit()
    # print(ycount)

def setcolormap():
    global barchartdf
    d = dict([(y,x+1) for x,y in enumerate(sorted(set(barchartdf['TYPE'])))])
    cmap = get_cmap("rainbow", len(d))
    scheme = [(d[x]-1)/len(d) for x in barchartdf['TYPE']]
    return cmap(scheme)


con = sqlite3.connect(sys.argv[1])

# blocksize = input("Enter block size: ")
# xbytes = input("Enter x bytes: ")

setnum = sys.argv[2]
xbytes = sys.argv[3]
typequery = sys.argv[4]

display(xbytes)

get_typenames = "SELECT DISTINCT ALLOCSWITHTYPES.TYPE FROM ALLOCSWITHTYPES;"

# blocklistquery = "select distinct address/" + blocksize + " as blockno from ALLOCS where (" + typequery + ")"

cache_query = "select type ,\
    address, \
    (address%" + xbytes + ") as cloff ,\
    size \
from ALLOCSWITHTYPES where (" + typequery + ") "

ways = 8

xbytes = int(xbytes)

setnum = int(setnum)

typedf = pd.read_sql_query(get_typenames, con)

print(typedf)

# blocknodf = pd.read_sql_query(blocklistquery, con)

print("**************")

print(cache_query)

print("**************")

barchartdf = pd.read_sql_query(cache_query, con)

barchartdf['ADDRESS'] = barchartdf['ADDRESS'].apply(hex)

ycount = [0 for x in range(setnum)]

# print(ycount)

# quit()
print(barchartdf)

print("**************")

insertnewrow()

rownum = int(math.ceil(math.sqrt(setnum)))

# hmap = [[(ycount[y*rownum + x] if y*rownum + x < setnum else 0) for x in range(rownum)] for y in range(rownum+1)]
hmap = [[(ycount[y*rownum + x] if y*rownum + x < setnum else 0) for x in range(rownum)] for y in range(rownum)]

print(hmap)

fig, gnt = plt.subplots()

# # gnt.set_xlabel('set number')
# gnt.set_ylabel('allocation frequency')

# # plt.xticks(ticks=range(0,int(setnum),8))
# plt.yticks(ticks=range(0,ways,1))

# # gnt.set_xticks(ticks=range(0,int(setnum),4), minor=True)
# gnt.set_yticks(ticks=range(0,ways,2), minor=True)

# gnt.grid(which='minor', alpha=0.8)
# gnt.grid(True)

# # colormap = setcolormap()

# # gnt.set_prop_cycle(color=colormap)

# # gnt.hlines(barchartdf['clno'], barchartdf['cloff'], barchartdf['cloff']+barchartdf['SIZE'], color=colormap, linewidth=7)

# rect = gnt.bar(range(100,500), ycount[100:500], label='frequency')

# # lastaddr = set()

# # for i, j , k in zip(barchartdf['clno'], barchartdf['cloff'], barchartdf['ADDRESS']):
# #         if not k in lastaddr:
# #             plt.text(j, i, str(k) , ha='left', va='center')
# #         lastaddr.add(k)

# plt.show()

plt.imshow(hmap, cmap='hot', interpolation='nearest')
plt.clim(vmin=0)
plt.show()