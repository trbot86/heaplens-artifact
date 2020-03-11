import sys
import sqlite3

con = sqlite3.connect(sys.argv[0])
cur = con.cursor()

cur.execute("SELECT DISTINCT ")