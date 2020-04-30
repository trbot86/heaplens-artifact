import sqlite3
import csv
import sys
from pandas import DataFrame

con = sqlite3.connect("./db_output/" + sys.argv[1])
cur = con.cursor()
cur.execute("CREATE TABLE ALLOCS(FILE CHAR(50)    NOT NULL, TYPE CHAR(100), LINE INT    NOT NULL, TIMESTAMP INT  NOT NULL, SIZE INT, ADDRESS INT    NOT NULL, isNew INT NOT NULL);") # use your column names here

dr = csv.reader(open("../prac/setbench-master/microbench/info_t_dump.txt",'r'), delimiter='|') # comma is default delimiter
# to_db = [(i[0], i[1], i[2], i[3], i[4], i[5], i[6]) for i in dr]

# for row in dr:
    # row[1] = extract_type(row[1])
    # quit()

cur.executemany("INSERT INTO ALLOCS VALUES (?, ?, ?, ?, ?, ?, ?);", dr)

con.commit()
con.close()
