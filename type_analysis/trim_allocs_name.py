import sys
import pandas as pd

df = pd.read_csv(sys.argv[1], delimiter='|')
print(df[:50])

df.iloc[:, 1] = df.iloc[:, 1].str.replace(" ", "")
df.to_csv("new_info_t_dump.txt", index=False, sep="|")

print(df)