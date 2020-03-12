# 1st stage- ad-hoc filter for specific reult.
# 2nd stage- pivot the data, and group accordingly
# 3rd stage- plot the data

import sys, sqlite3, matplotlib.pyplot as plt
import numpy as np

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

typename = input("Enter one of the above type:\n")

cl_offsets = "SELECT (TEMP.ADDRESS + FIELDS.SIZE)%64 as offset \
FROM (SELECT * FROM ALLOCS WHERE ALLOCS.TYPE = '" + typename + "' ) AS TEMP JOIN FIELDS ON TEMP.TYPE = FIELDS.CLASS \
;"

simple_join = "CREATE VIEW simple_join AS \
                    SELECT ALLOCS.TYPE, ALLOCS.TIMESTAMP, FIELDS.FIELD, FIELDS.TYPE, FIELDS.SIZE \
                        FROM ALLOCS JOIN FIELDS \
                            ON ALLOCS.TYPE = FIELDS.CLASS;"

pivot_command = "SELECT 'AverageCost' AS Cost_Sorted_By_Production_Days,
[0], [1], [2], [3], [4]  
FROM  
(SELECT DaysToManufacture, StandardCost   
    FROM Production.Product) AS SourceTable  
PIVOT  
(  
AVG(StandardCost)  
FOR DaysToManufacture IN ([0], [1], [2], [3], [4])  
) AS PivotTable;"

cur.execute(cl_offsets)

result = cur.fetchall()

keys, counts = np.unique(result, return_counts=True)

plt.bar(keys, counts)
plt.show()