from random import randint, randrange
import tkinter as tk
from tkinter import ANCHOR, RIGHT, Y, Frame, Listbox, Scrollbar, messagebox
import matplotlib
import sys, sqlite3, matplotlib.pyplot as plt

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


def insertnewrow(barchartdf):
    rows = []
    # print(barchartdf.shape[0])
    for i in range(0, barchartdf.shape[0]):
        # print(i)
        if barchartdf['cloff'][i] + barchartdf['SIZE'][i] > xbytes:
            s = barchartdf.at[i, 'SIZE']
            barchartdf.at[i, 'SIZE'] = xbytes - barchartdf['cloff'][i]
            new_s = barchartdf.at[i, 'SIZE']

            # print("s = "+ str(s))
            # print(new_s)

            quo = (s - new_s) // xbytes
            rem = (s - new_s) % xbytes
            # print(quo)
            for j in range(0, quo):
                new_row = pd.DataFrame(barchartdf[:][i:i + 1]).copy(deep=True)
                new_row['clno'] = new_row['clno'] + j + 1
                new_row['cloff'] = 0
                new_row['SIZE'] = xbytes
                rows.append(new_row)

            if rem != 0:
                new_row = pd.DataFrame(barchartdf[:][i:i + 1]).copy(deep=True)
                new_row['clno'] = new_row['clno'] + quo + 1
                new_row['cloff'] = 0
                new_row['SIZE'] = rem
                rows.append(new_row)

    return barchartdf.append(rows)
    # quit()


def setcolormap(barchartdf):
    d = dict([(y, x + 1)
              for x, y in enumerate(sorted(set(barchartdf['TYPE'])))])
    # print("DICTIONARY: ", d)
    cmap = get_cmap("rainbow", len(d))
    scheme = [(d[x] - 1) / len(d) for x in barchartdf['TYPE']]
    # print(scheme)
    return d, sorted(set(scheme)), cmap, cmap(scheme)


# class tkinterApp(tk.Tk):

# 	# __init__ function for class tkinterApp
# 	def __init__(self, *args, **kwargs):

# 		# __init__ function for class Tk
# 		tk.Tk.__init__(self, *args, **kwargs)

# 		# creating a container
# 		container = tk.Frame(self)
# 		container.pack(side = "top", fill = "both", expand = True)

# 		container.grid_rowconfigure(0, weight = 1)
# 		container.grid_columnconfigure(0, weight = 1)

# 		# initializing frames to an empty array
# 		self.frames = {}

# 		# iterating through a tuple consisting
# 		# of the different page layouts
# 		for F in (StartPage, Page1, Page2):

# 			frame = F(container, self)

# 			# initializing frame of that object from
# 			# startpage, page1, page2 respectively with
# 			# for loop
# 			self.frames[F] = frame

# 			frame.grid(row = 0, column = 0, sticky ="nsew")

# 		self.show_frame(StartPage)

# 	# to display the current frame passed as
# 	# parameter
# 	def show_frame(self, cont):
# 		frame = self.frames[cont]
# 		frame.tkraise()

# first window frame startpage

def getbarchartdf(blocknodf):
    blockno = str(blocknodf['blockno'][randint(0, blocknodf.size - 1)])

    print(blockno)

    print("**************")
    # PRINT CACHE QUERY
    print(cache_query)

    print("**************")

    barchartdf = pd.read_sql_query(cache_query + "and blockno like " + blockno,
                                con)

    #create new rows for cache allocations that span more than one cache line
    print("BEFORE INSERTNEWROW")
    print(barchartdf)
    
    barchartdf = insertnewrow(barchartdf)

    barchartdf['ADDRESS'] = barchartdf['ADDRESS'].apply(hex)

    print("AFTER INSERTNEWROW")
    print(barchartdf)

    #putting "" where type is None
    barchartdf['TYPE'] = [str(x) for x in barchartdf['TYPE']]

    print("**************")
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

        toplevel = tk.Toplevel(width=2000)


        fig, gnt = plt.subplots()
        self.plot_chart(barchartdf, gnt)

        canvas = FigureCanvasTkAgg(fig, master=root)
        canvas.get_tk_widget().pack(side="top", fill='both', expand=True)

        # canvas.draw()
        self.listbox = Listbox(root)
        self.populate_listbox(blocknodf)
        self.listbox.pack(side="right")
        self.listbox.bind('<Double-1>', lambda x: self.selectblock())

        # self.scrollbar = Scrollbar(root)

        # self.listbox.config(yscrollcommand = self.scrollbar.set)
        # self.scrollbar.config(command = self.listbox.yview)
        # self.scrollbar.grid(row=0, column=2)

        toolbarFrame = Frame(master=root)
        toolbarFrame.pack(side="bottom")
        toolbar = NavigationToolbar2Tk(canvas, toolbarFrame)
        toolbar.update()

        self.plotbutton = tk.Button(master=root,
                                    text="plot",
                                    command=lambda: self.plot(canvas, gnt))
        self.plotbutton.pack(side="left")

    def selectblock(self):
        print("selected: " + self.listbox.get(ANCHOR))
        self.plot(self.canvas, self.gnt)
    
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

        custom_lines = [Line2D([0], [0], color=clrmap(x), lw=4) for x in mapping]

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

    def plot(self, canvas, gnt):
        blocknodf = getblocknodf()
        barchartdf = getbarchartdf(blocknodf)
        self.plot_chart(barchartdf, gnt)
        canvas.draw()


# # second window frame page1
# class Page1(tk.Frame):

# 	def __init__(self, parent, controller):

# 		tk.Frame.__init__(self, parent)
# 		label = ttk.Label(self, text ="Page 1", font = LARGEFONT)
# 		label.grid(row = 0, column = 4, padx = 10, pady = 10)

# 		# button to show frame 2 with text
# 		# layout2
# 		button1 = ttk.Button(self, text ="StartPage",
# 							command = lambda : controller.show_frame(StartPage))

# 		# putting the button in its place
# 		# by using grid
# 		button1.grid(row = 1, column = 1, padx = 10, pady = 10)

# 		# button to show frame 2 with text
# 		# layout2
# 		button2 = ttk.Button(self, text ="Page 2",
# 							command = lambda : controller.show_frame(Page2))

# 		# putting the button in its place by
# 		# using grid
# 		button2.grid(row = 2, column = 1, padx = 10, pady = 10)

# # third window frame page2
# class Page2(tk.Frame):
# 	def __init__(self, parent, controller):
# 		tk.Frame.__init__(self, parent)
# 		label = ttk.Label(self, text ="Page 2", font = LARGEFONT)
# 		label.grid(row = 0, column = 4, padx = 10, pady = 10)

# 		# button to show frame 2 with text
# 		# layout2
# 		button1 = ttk.Button(self, text ="Page 1",
# 							command = lambda : controller.show_frame(Page1))

# 		# putting the button in its place by
# 		# using grid
# 		button1.grid(row = 1, column = 1, padx = 10, pady = 10)

# 		# button to show frame 3 with text
# 		# layout3
# 		button2 = ttk.Button(self, text ="Startpage",
# 							command = lambda : controller.show_frame(StartPage))

# 		# putting the button in its place by
# 		# using grid
# 		button2.grid(row = 2, column = 1, padx = 10, pady = 10)


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
    size \
from ALLOCSWITHTYPES where '1==1' "

#  where (" + typequery + ") "

xbytes = int(xbytes)

typedf = pd.read_sql_query(get_typenames, con)

print(typedf)

print("**************")

root = tk.Tk()
app = StartPage(master=root)
app.mainloop()