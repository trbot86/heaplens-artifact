import sqlite3
import csv
from pandas import DataFrame
from lark import Lark


def extract_type(full_type):
    l = Lark('''start: c
            c: a | a"::"c
            a: WORD "<" [c ("," c)*] ">" (\*+)| WORD
            WORD: /[A-Za-z0-9 _*]+/
            %import common.WS
            %ignore WS
            ''')
    t = l.parse(full_type)
# t = l.parse("std::bst_glock_ns<void*, long long>::Node<long long <bla bla>, void*>")
# print(t.children[0].children[1].children[0].children[1].children[0])
    # print(t.data)

    t = t.children[0]

    while t.data == 'c' and len(t.children) == 2:
        t = t.children[1]

    # print(t.data)

    t = t.children[0].children[0]

    print(t)
    return t

con = sqlite3.connect("./allocdb")
cur = con.cursor()
cur.execute("CREATE TABLE ALLOCS(FILE CHAR(50)    NOT NULL, TYPE CHAR(100), LINE INT    NOT NULL, TIMESTAMP INT PRIMARY KEY    NOT NULL, SIZE INT, ADDRESS INT    NOT NULL, isNew INT NOT NULL);") # use your column names here

dr = csv.reader(open("../prac/setbench-master/microbench/info_t_dump.txt",'r'), delimiter='|') # comma is default delimiter
# to_db = [(i[0], i[1], i[2], i[3], i[4], i[5], i[6]) for i in dr]

# for row in dr:
    # row[1] = extract_type(row[1])
    # quit()

cur.executemany("INSERT INTO ALLOCS VALUES (?, ?, ?, ?, ?, ?, ?);", dr)

con.commit()
con.close()
