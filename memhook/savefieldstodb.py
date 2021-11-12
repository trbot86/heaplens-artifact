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

    # drop old table
    cur.execute("DROP TABLE IF EXISTS " + tablename)
    cur.execute(execstring)

    dr = csv.reader(open(infile,'r'), delimiter='|') # comma is default delimiter
    # to_db = [(i[0], i[1], i[2], i[3], i[4], i[5], i[6]) forfielddump

    cur.executemany("INSERT OR IGNORE INTO " + tablename + " VALUES (" + "?,"*(numfields-1) + "?" + ");", dr)

    con.commit()
    con.close()

def updatetable(createstring, updatestring, tablename, drop):
    infile = sys.argv[1]
    outfile = sys.argv[2]

    con = sqlite3.connect(outfile)
    cur = con.cursor()
    
    # drop old table
    if drop == True:
        cur.execute("DROP TABLE IF EXISTS " + tablename)
    if createstring:
        cur.execute(createstring) # use your column names here
    cur.execute(updatestring)

    con.commit()
    con.close()

if __name__ == "__main__":
    createfieldstable = "CREATE TABLE FIELDS(CLASS CHAR(100), TYPE CHAR(100) NOT NULL, FIELD CHAR (100), SIZE INT, OFFSET INT, PRIMARY KEY (CLASS, TYPE, FIELD));"
    createallocstable = "CREATE TABLE ALLOCS(FILE CHAR(50)    NOT NULL, TYPE CHAR(100), LINE INT    NOT NULL, TIMESTAMP INT  NOT NULL, SIZE INT, ADDRESS INT    NOT NULL, isNew INT NOT NULL);"
    createmallocstable = "CREATE TABLE MALLOCS(FILE CHAR(50)    NOT NULL, LINE INT    NOT NULL,TYPE CHAR(50) NOT NULL);"
    createfilemaptable = "CREATE TABLE FILEMAP(FILEPTR CHAR(100) NOT NULL, FILE CHAR(100));"
    createtypemaptable = "CREATE TABLE TYPEMAP(TYPEPTR CHAR(100) NOT NULL, TYPE CHAR(100));"
    updateallocstablewithfile = "replace into ALLOCS \
        (ROWID, file, type, line, TIMESTAMP, address, isNew, size) \
        select allocs.rowid, filemap.file, allocs.type, allocs.line, allocs.TIMESTAMP, allocs.ADDRESS, allocs.isNew, allocs.SIZE \
        from allocs left join filemap on allocs.file = filemap.FILEPTR;"
    updateallocstablewithtype = "replace into ALLOCS \
        (ROWID, file, type, line, TIMESTAMP, address, isNew, size) \
        select allocs.rowid, allocs.file, typemap.type, allocs.line, allocs.TIMESTAMP, allocs.ADDRESS, allocs.isNew, allocs.SIZE \
        from allocs left join typemap on allocs.type = typemap.TYPEPTR;"
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
    elif sys.argv[3] == "FILEMAP":
        savefiletodb(createfilemaptable, 2, "FILEMAP")
    elif sys.argv[3] == "TYPEMAP":
        savefiletodb(createtypemaptable, 2, "TYPEMAP")
    elif sys.argv[3] == "UPDATEALLOCSWITHFILE":
        updatetable("", updateallocstablewithfile, "ALLOCS", False)
    elif sys.argv[3] == "UPDATEALLOCSWITHTYPE":
        updatetable("", updateallocstablewithtype, "ALLOCS", False)
    elif sys.argv[3] == "ALLOCSWITHTYPES":
        updatetable(createallocswithtypetable, updateallocswithtypetable, "ALLOCSWITHTYPES", True)