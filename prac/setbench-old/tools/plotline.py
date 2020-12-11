#!/usr/bin/python3

import numpy as np
import platform
import sys, getopt
import fileinput
import argparse

######################
## parse arguments
######################

parser = argparse.ArgumentParser(description='Produce a single-curve (x,y)-line plot from TWO COLUMN data provided via a file or stdin.')
parser.add_argument('-i', dest='infile', type=argparse.FileType('r'), default=sys.stdin, help='input file containing lines of form <x> <y>; if none specified then will use stdin')
parser.add_argument('-o', dest='outfile', type=argparse.FileType('w'), default=None, help='output file with any image format extension such as .png or .svg; if none specified then plt.show() will be used')
args = parser.parse_args()

# parser.print_usage()
if len(sys.argv) < 2:
    parser.print_usage()
    print('waiting on stdin for histogram data...')

print('args={}'.format(args))

WIN = (platform.system() == 'Windows' or 'CYGWIN' in platform.system())

######################
## load data
######################

x = []
y = []

i=0
# print(args.infile)
for line in args.infile:
    i=i+1
    line = line.rstrip('\r\n')
    if (line == '' or line == None):
        continue

    tokens = line.split(" ")
    if len(tokens) != 2:
        print("ERROR at line {}: '{}'".format(i, line))
        exit(1)

    x.append(int(tokens[0]))
    y.append(int(tokens[1]))

######################
## setup matplotlib
######################

import matplotlib as mpl
if WIN:
    mpl.use('TkAgg')
else:
    mpl.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
plt.style.use('dark_background')

######################
## setup plot
######################

dots_per_inch = 200
height_inches = 5
width_inches = 12

fig = plt.figure(figsize=(width_inches, height_inches), dpi=dots_per_inch)

print('data len={}'.format(len(x)))
plt.plot(x, y, color='red')

######################
## y axis major, minor
######################

ax = plt.gca()

ax.grid(which='major', axis='y', linestyle='-', color='lightgray')

ax.yaxis.set_minor_locator(ticker.AutoMinorLocator())
ax.grid(which='minor', axis='y', linestyle='dotted', color='gray')

######################
## x axis major, minor
######################

ax.grid(which='major', axis='x', linestyle='-', color='lightgray')

ax.xaxis.set_minor_locator(ticker.AutoMinorLocator())
ax.grid(which='minor', axis='x', linestyle='dotted', color='gray')

######################
## do the plot
######################

plt.tight_layout()

if args.outfile == None:
    if WIN:
        mng = plt.get_current_fig_manager()
        mng.window.state('zoomed')
    plt.show()
else:
    print("saving figure image %s\n" % args.outfile.name)
    plt.savefig(args.outfile.name)
