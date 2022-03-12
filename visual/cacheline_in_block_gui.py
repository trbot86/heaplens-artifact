from audioop import minmax
from random import randint, randrange
import tkinter as tk
from tkinter import *
import matplotlib
import sys, sqlite3, matplotlib.pyplot as plt
from pyrsistent import b
from utils import insertnewrow

matplotlib.use('TkAgg')
from matplotlib.cm import get_cmap
from matplotlib.lines import Line2D
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import pandas as pd
import argparse
from scipy import rand
from tkinter import ttk

LARGEFONT = ("Verdana", 35)


def setcolormap(barchartdf):
    d = dict([(y, x + 1)
              for x, y in enumerate(sorted(set(barchartdf['TYPE'])))])
    # print("DICTIONARY: ", d)
    cmap = get_cmap("rainbow", len(d))
    scheme = [(d[x] - 1) / len(d) for x in barchartdf['TYPE']]
    # print(scheme)
    return d, sorted(set(scheme)), cmap, cmap(scheme)



# def getbarchartdf(blocknodf, blockno="random", timestamp = 40905123453463716):
def getbarchartdf(blocknodf, blockno="random", timestamp = 40905123444586470):
    if(blockno=="random"):
        blockno = str(blocknodf['blockno'][randint(0, blocknodf.size - 1)])

    print(blockno)

    print("**************")
    # PRINT CACHE QUERY
    print(cache_query)
    print("**************")

    barchartdf = pd.read_sql_query(cache_query + "and blockno like " + blockno,
                                   con)

    print("BEFORE LATEST TIMESTAMP FILTERING")
    print("**************")
    print(barchartdf)
    print("**************")

    #FILTER ACCD. TO LATEST TIMESTAMP
    latest_allocs_set = {}

    for i in range(0, barchartdf.shape[0]):
        # print(type(barchartdf['TIMESTAMP'][i]))
        # print(barchartdf['TIMESTAMP'][i])
        if barchartdf['TIMESTAMP'][i] < timestamp:
            if barchartdf['ADDRESS'][i] in latest_allocs_set:
                if barchartdf['TIMESTAMP'][i] > latest_allocs_set[barchartdf['ADDRESS'][i]]['TIMESTAMP']:
                    latest_allocs_set[barchartdf['ADDRESS'][i]] = barchartdf.iloc[i]
            else:
                latest_allocs_set[barchartdf['ADDRESS'][i]] = barchartdf.iloc[i]

    newdf = pd.DataFrame()

    # for key, val in latest_allocs_set.items():
    #     if val['isNew'] == 1:
    #         print(val)
    #         newdf = newdf.append(val)

    newdf = newdf.append([v for k,v in latest_allocs_set.items() if v['isNew'] == 1], ignore_index=True)
    print(newdf)

    barchartdf = newdf
    print("AFTER LATEST TIMESTAMP FILTERING")
    print("**************")
    print(barchartdf)
    print("**************")

    #create new rows for cache allocations that span more than one cache line
    newdf = pd.DataFrame(columns=[
        'CLASS', 'TYPE', 'ADDRESS', 'clno', 'blockno', 'cloff', 'SIZE', 'TIMESTAMP', 'isNew'
    ])
    barchartdf = insertnewrow(barchartdf, newdf=newdf, verbose=True)

    barchartdf['ADDRESS'] = barchartdf['ADDRESS'].apply(hex)

    print("AFTER INSERTNEWROW")
    print("**************")
    print(barchartdf)
    print("**************")

    #putting "" where type is None
    barchartdf['TYPE'] = [str(x) for x in barchartdf['TYPE']]

    return barchartdf


def getblocknodf():
    print("**************")

    print(blocklistquery)

    blocknodf = pd.read_sql_query(blocklistquery, con)

    print(blocknodf)
    return blocknodf


class StartPage(tk.Frame):

    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.createWidgets()

    def createWidgets(self):
        blocknodf = getblocknodf()
        barchartdf = getbarchartdf(blocknodf)

        fig, self.gnt = plt.subplots()
        self.plot_chart(barchartdf, self.gnt)

        self.canvas = FigureCanvasTkAgg(fig, master=root)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky=(N, S, E, W))

        ##################
        #     LISTBOX    #
        ##################
        # canvas.draw()
        self.listbox = Listbox(root)
        self.populate_listbox(blocknodf)
        self.listbox.grid(row=0, column=1, sticky=(E, W))
        self.listbox.bind('<Double-1>', lambda x: self.selectblock())

        # self.scrollbar = Scrollbar(root)

        # self.listbox.config(yscrollcommand = self.scrollbar.set)
        # self.scrollbar.config(command = self.listbox.yview)
        # self.scrollbar.grid(row=0, column=2)


        ##################
        #     TOOLBAR    #
        ##################
        self.toolbarFrame = Frame(master=root)
        self.toolbarFrame.grid(row=1, column=0, sticky=(N, S, E, W))
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbarFrame)
        # self.toolbar.update()

        ##################
        #     SLIDER     #
        ##################
        self.label = tk.Label(root, text='Slider')
        self.label.grid(row=1, column=2, sticky=(N, S, E, W))
        self.label.config(width=20)
        minmaxtimedf = pd.read_sql_query(get_min_max_timestamps, con)
        self.scaleVar = tk.IntVar()
        print("min timestamp: ")
        print(minmaxtimedf)
        self.scaleVar = tk.IntVar()
        self.scale = ttk.Scale(root, from_=minmaxtimedf['min(TIMESTAMP)'][0], to=minmaxtimedf['max(TIMESTAMP)'][0], variable=self.scaleVar)
        self.scale.grid(row=1, column=1, sticky=(E, W))
        self.scale.config(command=self._callback)

        ##################
        #  PLOT BUTTON   #
        ##################
        self.plotbutton = tk.Button(
            master=root,
            text="plot",
            command=lambda: self.plot(self.canvas, self.gnt, isRandom=True))
        self.plotbutton.grid(row=1, column=3)

    def _callback(self, event):
        v = self.scaleVar.get()
        self.label.config(text=v)
        return

    def selectblock(self):
        print("selected: " + self.listbox.get(ANCHOR))
        self.plot(self.canvas, self.gnt, isRandom=False, blockno=self.listbox.get(ANCHOR))

    def populate_listbox(self, blocknodf):
        print(blocknodf)
        for i in range(len(blocknodf)):
            self.listbox.insert(i, blocknodf.loc[i, 'blockno'])

    def plot_chart(self, barchartdf, gnt):
        gnt.clear()
        gnt.set_xlabel('cache offset')
        gnt.set_ylabel('cacheline')

        plt.xticks(ticks=range(0, int(xbytes), 8))
        plt.yticks(ticks=range(0, int(barchartdf['clno'].max()), 8))

        gnt.set_xticks(ticks=range(0, int(xbytes), 4), minor=True)
        gnt.set_yticks(ticks=range(0, int(barchartdf['clno'].max()), 2),
                       minor=True)

        gnt.grid(which='minor', alpha=0.8)
        gnt.grid(True)

        dct, mapping, clrmap, colormap = setcolormap(barchartdf)

        custom_lines = [
            Line2D([0], [0], color=clrmap(x), lw=4) for x in mapping
        ]

        print(mapping)
        print(clrmap)
        print("custom_lines: ", [clrmap(x) for x in mapping])

        gnt.set_prop_cycle(color=colormap)

        gnt.hlines(barchartdf['clno'],
                   barchartdf['cloff'],
                   barchartdf['cloff'] + barchartdf['SIZE'],
                   color=colormap,
                   linewidth=7)

        gnt.legend(custom_lines, list(dct.keys()))

        lastaddr = set()

        for i, j, k in zip(barchartdf['clno'], barchartdf['cloff'],
                           barchartdf['ADDRESS']):
            if not k in lastaddr:
                plt.text(j, i, str(k), ha='left', va='center')
            lastaddr.add(k)

    def plot(self, canvas, gnt, isRandom=True, blockno=None):
        blocknodf = getblocknodf()
        if(isRandom == True):
            barchartdf = getbarchartdf(blocknodf, "random")
        else:
            barchartdf = getbarchartdf(blocknodf, blockno)
        self.plot_chart(barchartdf, gnt)
        canvas.draw()

def display(var):
    import inspect, re
    callingframe = inspect.currentframe().f_back
    cntext = "".join(inspect.getframeinfo(callingframe, 5)[3])
    m = re.search("display\s*\(\s*(\w+)\s*\)", cntext, re.MULTILINE)
    print(m.group(1), type(var), var)


# Driver Code
con = sqlite3.connect(sys.argv[1])

# blocksize = input("Enter block size: ")
# xbytes = input("Enter x bytes: ")

blocksize = sys.argv[2]
xbytes = sys.argv[3]
typequery = sys.argv[4]

display(xbytes)

get_typenames = "select distinct ALLOCSWITHTYPES.TYPE from ALLOCSWITHTYPES;"

blocklistquery = "select distinct address/" + blocksize + " as blockno from ALLOCSWITHTYPES where (" + typequery + ")"

cache_query = "select type ,\
    address, \
    (address%" + blocksize + ")/" + xbytes + " as clno ,\
    address/" + blocksize + " as blockno ,\
    (address%" + xbytes + ") as cloff ,\
    size ,\
    TIMESTAMP ,\
    isNew \
from ALLOCSWITHTYPES where '1==1' "

#  where (" + typequery + ") "

get_min_max_timestamps = "select min(TIMESTAMP), max(TIMESTAMP) from ALLOCSWITHTYPES; "

xbytes = int(xbytes)

typedf = pd.read_sql_query(get_typenames, con)

print(typedf)

print("**************")

root = tk.Tk()
root.columnconfigure(0, weight=3)
root.columnconfigure(1, weight=3)
root.columnconfigure(2, weight=3)
root.columnconfigure(3, weight=3)
root.rowconfigure(1, weight=3)
app = StartPage(master=root)
app.mainloop()