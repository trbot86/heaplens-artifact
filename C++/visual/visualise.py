# 1st stage- ad-hoc filter for specific reult.
# 2nd stage- pivot the data, and group accordingly
# 3rd stage- plot the data

import sys, sqlite3, matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from typeparser import parsetypeandpointer

con = sqlite3.connect(sys.argv[1])

cur = con.cursor()

get_typenames = "SELECT DISTINCT ALLOCS.TYPE FROM ALLOCS;"

print("this program shows the cache line offsets for the given type\n")

print("the types are as follows\n")

for t in cur.execute(get_typenames):
    print(t)

get_offsets = "SELECT ALLOCS.TYPE, ALLOCS.ADDRESS + FIELDS.SIZE as offset, FIELDS.FIELD, FIELDS.TYPE \
FROM ALLOCS JOIN FIELDS \
ON ALLOCS.TYPE = FIELDS.CLASS;"

# typename = input("Enter one of the above type:\n")

# cl_offsets = "SELECT (TEMP.ADDRESS + FIELDS.SIZE)%64 as offset \
# FROM (SELECT * FROM ALLOCS WHERE ALLOCS.TYPE = '" + typename + "' ) AS TEMP JOIN FIELDS ON TEMP.TYPE = FIELDS.CLASS \
# ;"

simple_join = "CREATE VIEW simple_join AS \
                    SELECT ALLOCS.TYPE, ALLOCS.TIMESTAMP, FIELDS.FIELD, FIELDS.TYPE, FIELDS.SIZE \
                        FROM ALLOCS JOIN FIELDS \
                            ON ALLOCS.TYPE = FIELDS.CLASS;"

timewise_allocation = "select \
    (timestamp/1000000 \
        - (select min(timestamp)/1000000 from allocs)) \
        as tsdiv, type, \
    sum(size) as sz \
from allocs group by tsdiv, type;"

df = pd.read_sql_query(timewise_allocation, con)

df['TYPE'] = df['TYPE'].apply(parsetypeandpointer)

print(df)

pivot_table = pd.pivot_table(df,index=['tsdiv'] ,values=['sz'], columns='TYPE', fill_value = 0, aggfunc='first')

pivot_table = pivot_table[1:]

pivot_table.columns = ['_'.join(col) for col in pivot_table.columns]

print(pivot_table.cumsum()[0:1000])

pivot_table.cumsum().plot()
plt.show()

# keys, counts = np.unique(result, return_counts=True)

# plt.bar(keys, counts)
# plt.show()


#############################################################################################################