# HAVE TO INCLUDE SIZE IN FIELDDUMP.TXT SOMEHOW

import sqlite3
import csv
from pandas import DataFrame
import sys

con = sqlite3.connect("./db_output/" + sys.argv[1])
cur = con.cursor()
cur.execute("CREATE TABLE FIELDS(CLASS CHAR(100) NOT NULL, TYPE CHAR (100), FIELD CHAR (100), SIZE INT, OFFSET INT, PRIMARY KEY (CLASS, TYPE, FIELD));") # use your column names here

dr = csv.reader(open("../type_analysis/fielddump.txt",'r'), delimiter='|') # comma is default delimiter
# to_db = [(i[0], i[1], i[2], i[3], i[4], i[5], i[6]) forfielddump

cur.executemany("INSERT OR IGNORE INTO FIELDS VALUES (?, ?, ?, ?, ?);", dr)

con.commit()
con.close()
