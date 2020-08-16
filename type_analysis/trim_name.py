import sys
import pandas as pd


def trim_allocs(filename):
    df = pd.read_csv(filename, delimiter='|', header=None)
    # print(df[:50])

    df.iloc[:, 1] = df.iloc[:, 1].str.replace(" ", "")
    df.to_csv("new_info_t_dump.txt", index=False, header=None, sep="|")

    # print(df)


def trim_fields(filename):
    df = pd.read_csv(filename, delimiter='|', header=None)
    # print(df.iloc[:50])

    df.iloc[:, 0] = df.iloc[:, 2].str.replace(" ", "")
    # print(df.iloc[:50])

    df.iloc[:, 0] = df.iloc[:, 0].str.rsplit(':', n=2).str[0]
    # print(df.iloc[:50])
    
    df.iloc[:, 2] = df.iloc[:, 2].str.rsplit(':', n=1).str[1]
    # print(df[:50])

    df.to_csv("new_fielddump.txt", index=False, header=None, sep="|")