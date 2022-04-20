import matplotlib
matplotlib.use('TkAgg')
from audioop import minmax
from random import randint, randrange
import tkinter as tk
from tkinter import *
import sys, sqlite3, matplotlib.pyplot as plt
from pyrsistent import b
from utils import insertnewrow

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
def getbarchartdf(blocknodf, timestamp, blockno="random"):
    if(blockno=="random"):
        blockno = str(blocknodf['blockno'][randint(0, blocknodf.size - 1)])

    print(blockno)

    print("**************")
    # PRINT CACHE QUERY
    print("cache_query: " + cache_query + str(timestamp) + " and blockno like " + blockno)
    print("**************")

    barchartdf = pd.read_sql_query(cache_query + str(timestamp) + " and blockno like " + blockno,
                                   con, dtype={'TYPE': str, 'ADDRESS': int, 'clno': int, 'blockno': int, 'cloff': int, 'SIZE': int, 'TIMESTAMP': int, 'isNew': int})

    print("BEFORE LATEST TIMESTAMP FILTERING")
    print("**************")
    print(barchartdf.dtypes)
    print(barchartdf)
    print("TIMESTAMP IS: ")
    print(timestamp)
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

    return barchartdf, blockno


def getblocknodf(timestamp):
    print("**************")

    print("blocklistquery: " + blocklistquery + str(timestamp))

    blocknodf = pd.read_sql_query(blocklistquery + str(timestamp), con)

    print(blocknodf)
    return blocknodf


class StartPage(tk.Frame):

    def __init__(self, master=None):
        tk.Frame.__init__(self, master)
        self.bottomframe = Frame(root)
        self.bottomframe.grid(row=1, column=0)
        self.sideframe = Frame(root)
        self.sideframe.grid(row=0, column=1)
        self.chartframe = Frame(root)
        self.chartframe.grid(row=0, column=0)

        self.blockno = 0

        self.createWidgets()

    def createWidgets(self):
        self.minmaxtimedf = pd.read_sql_query(get_min_max_timestamps, con)

        print("minmaxtimedf: ")
        print(self.minmaxtimedf)

        #First chart should be max timestamp random dataframe
        blocknodf = getblocknodf(self.minmaxtimedf['max(TIMESTAMP)'][0])
        barchartdf, self.blockno = getbarchartdf(blocknodf, timestamp=self.minmaxtimedf['max(TIMESTAMP)'][0])

        fig, self.gnt = plt.subplots()

        self.canvas = FigureCanvasTkAgg(fig, master=self.chartframe)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky=(N, S, E, W))

        self.plot_chart(barchartdf, self.gnt)

        #########################
        #   BLOCKNO ENTRY BOX   #
        #########################
        self.entrybox = tk.Entry(self.sideframe)
        self.entrybox.grid(row=1, column=0, sticky=(E, W))

        #######################
        #   UPPER  SLIDER     #
        #######################

        self.scaleVarUp = tk.IntVar()
        self.scaleVarDwn = tk.IntVar(value=self.minmaxtimedf['max(TIMESTAMP)'][0])

        print(barchartdf['TIMESTAMP'])
        if not barchartdf.empty:
            print("min: " + str(barchartdf['TIMESTAMP'].min()))
            print("max: " + str(barchartdf['TIMESTAMP'].max()))

        #ERROR: CHECK THIS!!!
        if barchartdf.empty:
            self.scaleUp = Scale(self.chartframe, from_=0, to=0, variable=self.scaleVarUp, orient=tk.HORIZONTAL)
        else:
            self.scaleUp = Scale(self.chartframe, from_=barchartdf['TIMESTAMP'].min(), to=barchartdf['TIMESTAMP'].max(), variable=self.scaleVarUp, orient=tk.HORIZONTAL)
            # self.scaleUp = Scale(self.chartframe, from_=10, to=100, variable=self.scaleVarUp, orient=tk.HORIZONTAL)

        self.scaleUp.grid(row=1, column=0, sticky=(E, W))
        self.scaleUp.config(command=self._callbackUp)

        self.scaleUp.bind("<ButtonRelease-1>", lambda x: self.plot(self.canvas, self.gnt, isRandom=False, blockno=self.entrybox.get(), timestamp=self.scaleVarUp))
        # self.scaleUp.bind("<ButtonRelease-1>", lambda x: print("Hello world"))

        self.labelUp = tk.Label(self.chartframe, text='Block Filter')
        self.labelUp.grid(row=2, column=0, sticky=(N, S, E, W))
        self.labelUp.config(width=20)


        #######################
        #   LOWER  SLIDER     #
        #######################

        self.scaleDwn = Scale(self.chartframe, from_=self.minmaxtimedf['min(TIMESTAMP)'][0], to=self.minmaxtimedf['max(TIMESTAMP)'][0], variable=self.scaleVarDwn, orient=tk.HORIZONTAL)
        self.scaleDwn.grid(row=3, column=0, sticky=(E, W))
        self.scaleDwn.config(command=self._callbackDwn)

        self.scaleDwn.bind("<ButtonRelease-1>", self.update_listbox)

        self.labelDwn = tk.Label(self.chartframe, text='Total Time Filter')
        self.labelDwn.grid(row=4, column=0, sticky=(N, S, E, W))
        self.labelDwn.config(width=20)

        ##################
        #     TOOLBAR    #
        ##################
        self.toolbarFrame = Frame(master=self.bottomframe)
        self.toolbarFrame.grid(row=0, column=0, sticky=(N, S, E, W))
        self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbarFrame)
        # self.toolbar.update()


        ##################
        #     LISTBOX    #
        ##################
        # canvas.draw()
        self.listbox = Listbox(self.sideframe)
        blocknodf.sort_values(by='blockno', inplace=True)
        blocknodf.reset_index(drop=True, inplace=True)
        self.populate_listbox(blocknodf)
        self.listbox.grid(row=0, column=0, sticky=(E, W))
        self.listbox.bind('<Double-1>', lambda x: self.selectblock())

        self.scrollbar = Scrollbar(self.sideframe)
        self.scrollbar.config(command = self.listbox.yview)
        self.scrollbar.grid(row=0, column=1, sticky=(N, S))

        self.listbox.config(yscrollcommand = self.scrollbar.set)

        #########################
        #  RANDOM PLOT BUTTON   #
        #########################
        self.randplotbutton = tk.Button(
            master=self.sideframe,
            text="Plot Random",
            command=lambda: self.plot_set_scale(canvas=self.canvas, gnt=self.gnt, isRandom=True))
        self.randplotbutton.grid(row=2, column=0)

        #################################
        #  SELECTED BLOCK PLOT BUTTON   #
        #################################
        self.plotbutton = tk.Button(
            master=self.sideframe,
            text="Plot Selected",
            command=lambda: self.plot_set_scale(canvas=self.canvas, gnt=self.gnt, isRandom=False, blockno=self.entrybox.get()))
        self.plotbutton.grid(row=3, column=0)

    def _callbackUp(self, event):
        v = self.scaleVarUp.get()
        # self.labelUp.config(text=v)
        return

    def _callbackDwn(self, event):
        v = self.scaleVarDwn.get()
        # self.labelDwn.config(text=v)
        return

    def update_listbox(self, event):
        v = self.scaleVarDwn.get()
        blocknodf = getblocknodf(v)
        self.populate_listbox(blocknodf)

    def selectblock(self):
        print("selected: " + self.listbox.get(ANCHOR))
        self.plot(self.canvas, self.gnt, isRandom=False, blockno=self.listbox.get(ANCHOR))

    def populate_listbox(self, blocknodf):
        self.listbox.delete(0, END)
        for i in range(len(blocknodf)):
            self.listbox.insert(i, blocknodf.loc[i, 'blockno'])

    def plot_chart(self, barchartdf, gnt):
        gnt.clear()
        gnt.set_xlabel('cache offset')
        gnt.set_ylabel('cacheline')

        plt.xticks(ticks=range(0, int(xbytes), 8))
        if barchartdf.empty:
            plt.yticks(ticks=range(0, 0, 8))
        else:
            plt.yticks(ticks=range(0, int(barchartdf['clno'].max()), 8))

        gnt.set_xticks(ticks=range(0, int(xbytes), 4), minor=True)
        if barchartdf.empty:
            gnt.set_yticks(ticks=range(0, 0, 2),
                       minor=True)
        else:
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

    def plot(self, canvas, gnt, isRandom=True, blockno=None, timestamp=None):
        blocknodf = getblocknodf(self.scaleVarDwn.get())
        if(isRandom == True):
            barchartdf, self.blockno = getbarchartdf(blocknodf, self.scaleVarDwn.get(), "random")
        else:
            barchartdf, self.blockno = getbarchartdf(blocknodf, self.scaleVarUp.get(), blockno)

        self.entrybox.delete(0, END)
        self.entrybox.insert(0, self.blockno)

        print(barchartdf['TIMESTAMP'])
        if not barchartdf.empty:
            print("min: ")
            print(barchartdf['TIMESTAMP'].min())
            print("max: ")
            print(barchartdf['TIMESTAMP'].max())

        self.plot_chart(barchartdf, gnt)
        canvas.draw()
        return barchartdf

    def plot_set_scale(self, canvas, gnt, isRandom=True, blockno=None, timestamp=None):
        barchartdf = self.plot(canvas=canvas, gnt=gnt, isRandom=isRandom, blockno=blockno, timestamp=timestamp)
        if barchartdf.empty:
            self.scaleUp.config(from_=0, to=0)
        else:
            self.scaleUp.config(from_=barchartdf['TIMESTAMP'].min(), to=barchartdf['TIMESTAMP'].max())

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

blocklistquery = "select distinct address/" + blocksize + " as blockno from ALLOCSWITHTYPES where (" + typequery + ") and TIMESTAMP <= "

cache_query = "select type ,\
    address, \
    (address%"               + blocksize + ")/" + xbytes + " as clno ,\
    address/"              + blocksize + " as blockno ,\
    (address%"               + xbytes + ") as cloff ,\
    size ,\
    TIMESTAMP ,\
    isNew \
from ALLOCSWITHTYPES where '1==1' and TIMESTAMP <= "

#  where (" + typequery + ") "

get_min_max_timestamps = "select min(TIMESTAMP), max(TIMESTAMP) from ALLOCSWITHTYPES; "

xbytes = int(xbytes)

typedf = pd.read_sql_query(get_typenames, con)

print(typedf)

print("**************")

root = tk.Tk()
app = StartPage(master=root)
app.mainloop()