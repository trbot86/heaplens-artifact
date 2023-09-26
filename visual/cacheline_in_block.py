# 1st stage- ad-hoc filter for specific reult.
# 2nd stage- pivot the data, and group accordingly
# 3rd stage- plot the data

from random import randint, randrange
import tkinter as tk
from tkinter import messagebox
import matplotlib
import sys, sqlite3, matplotlib.pyplot as plt
matplotlib.use('Agg')
from matplotlib.cm import get_cmap
from matplotlib.lines import Line2D
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import pandas as pd
import argparse
from scipy import rand

# pd.set_option('display.max_rows', None)

def display(var):
    import inspect, re
    callingframe = inspect.currentframe().f_back
    cntext = "".join(inspect.getframeinfo(callingframe, 5)[3])
    m = re.search("display\s*\(\s*(\w+)\s*\)", cntext, re.MULTILINE)
    print(m.group(1), type(var), var)

def insertnewrow(barchartdf):
    rows = []
    # print(barchartdf.shape[0])
    for i in range(0, barchartdf.shape[0]):
        # print(i)
        if barchartdf['cloff'][i] + barchartdf['SIZE'][i] > xbytes:
            s = barchartdf.at[i,'SIZE']
            barchartdf.at[i,'SIZE'] = xbytes - barchartdf['cloff'][i]
            new_s = barchartdf.at[i,'SIZE']

            # print("s = "+ str(s))
            # print(new_s)

            quo = (s-new_s)//xbytes
            rem = (s-new_s)%xbytes
            # print(quo)
            for j in range(0,quo):
                new_row = pd.DataFrame(barchartdf[:][i:i+1]).copy(deep=True)
                new_row['clno'] = new_row['clno'] + j +1
                new_row['cloff'] = 0
                new_row['SIZE'] = xbytes
                rows.append(new_row)

            if rem != 0:
                new_row = pd.DataFrame(barchartdf[:][i:i+1]).copy(deep=True)
                new_row['clno'] = new_row['clno'] + quo + 1
                new_row['cloff'] = 0
                new_row['SIZE'] = rem
                rows.append(new_row)

    return barchartdf.append(rows)
    # quit()

def setcolormap(barchartdf):
    d = dict([(y,x+1) for x,y in enumerate(sorted(set(barchartdf['TYPE'])))])
    # print("DICTIONARY: ", d)
    cmap = get_cmap("rainbow", len(d))
    scheme = [(d[x]-1)/len(d) for x in barchartdf['TYPE']]
    # print(scheme)
    return d, sorted(set(scheme)), cmap, cmap(scheme)

def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            root.destroy()
            exit()

def renderchart(barchartdf):

    fig, gnt = plt.subplots()

    gnt.set_xlabel('cache offset')
    gnt.set_ylabel('cacheline')

    plt.xticks(ticks=range(0,int(xbytes),8))
    plt.yticks(ticks=range(0,int(barchartdf['clno'].max()),8))

    gnt.set_xticks(ticks=range(0,int(xbytes),4), minor=True)
    gnt.set_yticks(ticks=range(0,int(barchartdf['clno'].max()),2), minor=True)

    gnt.grid(which='minor', alpha=0.8)
    gnt.grid(True)

    dct, mapping, clrmap, colormap = setcolormap(barchartdf)

    custom_lines = [Line2D([0], [0], color=clrmap(x), lw=4) for x in mapping]

    print(mapping)
    print(clrmap)
    print("custom_lines: ", [clrmap(x) for x in mapping])

    gnt.set_prop_cycle(color=colormap)

    gnt.hlines(barchartdf['clno'], barchartdf['cloff'], barchartdf['cloff']+barchartdf['SIZE'], color=colormap, linewidth=7)

    gnt.legend(custom_lines, list(dct.keys()))

    lastaddr = set()

    for i, j , k in zip(barchartdf['clno'], barchartdf['cloff'], barchartdf['ADDRESS']):
            if not k in lastaddr:
                plt.text(j, i, str(k) , ha='left', va='center')
            lastaddr.add(k)

    chart = FigureCanvasTkAgg(fig, root)
    chart.get_tk_widget().pack()
    # plt.show()
    chart.draw()

con = sqlite3.connect(sys.argv[1])

# blocksize = input("Enter block size: ")
# xbytes = input("Enter x bytes: ")

blocksize = sys.argv[2]
xbytes = sys.argv[3]
typequery = sys.argv[4]

display(xbytes)

get_typenames = "select distinct SUPERTABLE.TYPE from SUPERTABLE;"

blocklistquery = "select distinct address/" + blocksize + " as blockno from SUPERTABLE where (" + typequery + ")"

cache_query = "select type ,\
    address, \
    (address%" + blocksize + ")/" + xbytes + " as clno ,\
    address/" + blocksize + " as blockno ,\
    (address%" + xbytes + ") as cloff ,\
    size \
from SUPERTABLE where '1==1' "
#  where (" + typequery + ") "

xbytes = int(xbytes)

typedf = pd.read_sql_query(get_typenames, con)

print(typedf)

print("**************")

print(blocklistquery)

blocknodf = pd.read_sql_query(blocklistquery, con)

print(blocknodf)

print("**************")

root = tk.Tk()

while True:
    # blockno = input("Enter block number: ")
    # PICK RANDOM BLOCK
    blockno = str(blocknodf['blockno'][randint(0, blocknodf.size-1)])

    print(blockno)

    print("**************")
    # PRINT CACHE QUERY
    print(cache_query)

    print("**************")

    barchartdf = pd.read_sql_query(cache_query + "and blockno like " + blockno, con)

    #create new rows for cache allocations that span more than one cache line
    barchartdf = insertnewrow(barchartdf)

    barchartdf['ADDRESS'] = barchartdf['ADDRESS'].apply(hex)

    print(barchartdf)

    #putting "" where type is None
    barchartdf['TYPE'] = [str(x) for x in barchartdf['TYPE']]

    print("**************")

    renderchart(barchartdf)
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()