# HAVE TO INCLUDE SIZE IN FIELDDUMP.TXT SOMEHOW

import sqlite3
import csv
import sys
from pandas import DataFrame

if len(sys.argv) != 4:
    print("USAGE: python {} INPUT_TXT_FILE OUTPUT_SQLITE_FILE".format(sys.argv[0]))
    quit()

def savefiletodb(execstring, numfields, tablename):
    infile = sys.argv[1]
    outfile = sys.argv[2]

    con = sqlite3.connect(outfile)
    cur = con.cursor()
    cur.execute(execstring) # use your column names here

    dr = csv.reader(open(infile,'r'), delimiter='|') # comma is default delimiter
    # to_db = [(i[0], i[1], i[2], i[3], i[4], i[5], i[6]) forfielddump

    cur.executemany("INSERT OR IGNORE INTO " + tablename + " VALUES (" + "?,"*(numfields-1) + "?" + ");", dr)

    con.commit()
    con.close()

def allocswithtypestablefunc(createstring, updatestring):
    infile = sys.argv[1]
    outfile = sys.argv[2]

    con = sqlite3.connect(outfile)
    cur = con.cursor()
    cur.execute(createstring) # use your column names here
    cur.execute(updatestring)

    con.commit()
    con.close()

if __name__ == "__main__":
    createfieldstable = "CREATE TABLE FIELDS(CLASS CHAR(100), TYPE CHAR(100) NOT NULL, FIELD CHAR (100), SIZE INT, OFFSET INT, PRIMARY KEY (CLASS, TYPE, FIELD));"
    createallocstable = "CREATE TABLE ALLOCS(FILE CHAR(50)    NOT NULL, TYPE CHAR(100), LINE INT    NOT NULL, TIMESTAMP INT  NOT NULL, SIZE INT, ADDRESS INT    NOT NULL, isNew INT NOT NULL);"
    createmallocstable = "CREATE TABLE MALLOCS(FILE CHAR(50)    NOT NULL, LINE INT    NOT NULL,TYPE CHAR(50) NOT NULL);"
    createallocswithtypetable = "create table ALLOCSWITHTYPES as \
        select t1.file, t1.type, t2.type as malloctype, t1.line, t1.TIMESTAMP, t1.size, t1.ADDRESS, t1.isNew \
        from allocs t1 left join mallocs t2 on t1.file = t2.file and t1.line = t2.line"
    updateallocswithtypetable = "update ALLOCSWITHTYPES \
        set TYPE = malloctype \
        where malloctype not NULL"

    if sys.argv[3] == "FIELDS":
        savefiletodb(createfieldstable, 5, "FIELDS")
    elif sys.argv[3] == "ALLOCS":
        savefiletodb(createallocstable, 7, "ALLOCS")
    elif sys.argv[3] == "MALLOCS":
        savefiletodb(createmallocstable, 3, "MALLOCS")
    elif sys.argv[3] == "ALLOCSWITHTYPES":
        allocswithtypestablefunc(createallocswithtypetable, updateallocswithtypetable)