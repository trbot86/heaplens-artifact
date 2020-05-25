# HAVE TO INCLUDE SIZE IN FIELDDUMP.TXT SOMEHOW

import sqlite3
import csv
import sys
from pandas import DataFrame

if len(sys.argv) != 3:
    print("USAGE: python {} INPUT_TXT_FILE OUTPUT_SQLITE_FILE".format(sys.argv[0]))
    quit()

infile = sys.argv[1]
outfile = sys.argv[2]

con = sqlite3.connect(outfile)
cur = con.cursor()
cur.execute("CREATE TABLE FIELDS(CLASS CHAR(100), TYPE CHAR(100) NOT NULL, FIELD CHAR (100), SIZE INT, OFFSET INT, PRIMARY KEY (CLASS, TYPE, FIELD));") # use your column names here

dr = csv.reader(open(infile,'r'), delimiter='|') # comma is default delimiter
# to_db = [(i[0], i[1], i[2], i[3], i[4], i[5], i[6]) forfielddump

cur.executemany("INSERT OR IGNORE INTO FIELDS VALUES (?, ?, ?, ?, ?);", dr)

con.commit()
con.close()
