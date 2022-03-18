import pandas as pd

# def insertnewrow(barchartdf, xbytes):
#     rows = []
#     # print(barchartdf.shape[0])
#     for i in range(0, barchartdf.shape[0]):
#         # print(i)
#         if barchartdf['cloff'][i] + barchartdf['SIZE'][i] > xbytes:
#             s = barchartdf.at[i, 'SIZE']
#             barchartdf.at[i, 'SIZE'] = xbytes - barchartdf['cloff'][i]
#             new_s = barchartdf.at[i, 'SIZE']

#             # print("s = "+ str(s))
#             # print(new_s)

#             quo = (s - new_s) // xbytes
#             rem = (s - new_s) % xbytes
#             # print(quo)
#             for j in range(0, quo):
#                 new_row = pd.DataFrame(barchartdf[:][i:i + 1]).copy(deep=True)
#                 new_row['clno'] = new_row['clno'] + j + 1
#                 new_row['cloff'] = 0
#                 new_row['SIZE'] = xbytes
#                 rows.append(new_row)

#             if rem != 0:
#                 new_row = pd.DataFrame(barchartdf[:][i:i + 1]).copy(deep=True)
#                 new_row['clno'] = new_row['clno'] + quo + 1
#                 new_row['cloff'] = 0
#                 new_row['SIZE'] = rem
#                 rows.append(new_row)

#     return barchartdf.append(rows)

def insertnewrow(barchartdf, newdf, fieldstypedf=None, xbytes=64, fieldtohighlight=None, verbose=False):
    print("field to highlight: ", fieldtohighlight)
    typedict = {}

    if(fieldstypedf is not None):
        # Convert field df to dictionary for fast access
        # for i in range(0, fieldstypedf.shape[0]):
        #     if fieldstypedf['CLASS'][i] in typedict:
        #         typedict[fieldstypedf['CLASS'][i]].append(
        #             (fieldstypedf['FIELD'][i], fieldstypedf['OFFSET'][i], fieldstypedf['SIZE'][i]))
        #     else:
        #         typedict[fieldstypedf['CLASS'][i]] = [
        #             (fieldstypedf['FIELD'][i], fieldstypedf['OFFSET'][i], fieldstypedf['SIZE'][i])]

        typedict = {fieldstypedf['CLASS'][i]: (fieldstypedf['FIELD'][i], fieldstypedf['OFFSET'][i], fieldstypedf['SIZE'][i]) for i in range(0, fieldstypedf.shape[0])}

        if verbose:
            print("*********")
            print(typedict)
            # print(typedict['node_t<longlong,void*>'])
            print("*********")

    rows = []
    
    #TODO: FIX
    #if no particular field to highlight
    if not fieldtohighlight:
        for i in range(0, barchartdf.shape[0]):
            if barchartdf['TYPE'][i] in typedict:
                for field, off, sz in typedict[barchartdf['TYPE'][i]]:
                    if verbose:
                        print(barchartdf['TYPE'][i], field, off, sz)
                    # ADDRESS redundant as clno and offset are already in use
                    newdf = newdf.append({'CLASS': field, 'TYPE': barchartdf['TYPE'][i], 'ADDRESS': barchartdf['ADDRESS'][i], 'clno': barchartdf['clno'][i], 
                                            'blockno': barchartdf['blockno'][i], 'cloff': off, 'SIZE': sz}, ignore_index=True)
                    print("PRINTTTTTTTTTTTTTTTTTTTTT:")
                    print(newdf)
            else:
                newdf = newdf.append(barchartdf.iloc[i], ignore_index=True)
    else:
        for i in range(0, barchartdf.shape[0]):
            if barchartdf['TYPE'][i] in typedict:
                    for field, off, sz in typedict[barchartdf['TYPE'][i]]:
                        if verbose:
                            print(barchartdf['TYPE'][i], field, off, sz)
                        # ADDRESS redundant as clno and offset are already in use
                        if field == fieldtohighlight:
                            newdf = newdf.append({'CLASS': field, 'TYPE': barchartdf['TYPE'][i], 'ADDRESS': barchartdf['ADDRESS'][i], 'clno': barchartdf['clno']
                                                [i], 'blockno': barchartdf['blockno'][i], 'cloff': off, 'SIZE': sz}, ignore_index=True)
                            print("PRINTTTTTTTTTTTTTTTTTTTTT:")
                            print(newdf)
                        else:
                            newdf = newdf.append({'CLASS': "nohighlight", 'TYPE': barchartdf['TYPE'][i], 'ADDRESS': barchartdf['ADDRESS'][i], 'clno': barchartdf['clno']
                                                [i], 'blockno': barchartdf['blockno'][i], 'cloff': off, 'SIZE': sz}, ignore_index=True)
                            print("PRINTTTTTTTTTTTTTTTTTTTTT:")
                            print(newdf)
            else:
                newdf = newdf.append(barchartdf.iloc[i], ignore_index=True)

    if verbose:
        print("*********")
        print("newdf:")
        print(newdf)
        print("*********")

    for i in range(0, newdf.shape[0]):
        if newdf['cloff'][i] + newdf['SIZE'][i] > xbytes:
            s = newdf.at[i, 'SIZE']
            newdf.at[i, 'SIZE'] = xbytes - newdf['cloff'][i]
            new_s = newdf.at[i, 'SIZE']

            # print("s = "+ str(s))
            # print(new_s)

            quo = (s-new_s)//xbytes
            rem = (s-new_s) % xbytes
            # print(quo)
            for j in range(0, quo):
                new_row = pd.DataFrame(newdf[:][i:i+1]).copy(deep=True)
                new_row['clno'] = new_row['clno'] + j + 1
                new_row['cloff'] = 0
                new_row['SIZE'] = xbytes
                rows.append(new_row)

            if rem != 0:
                new_row = pd.DataFrame(newdf[:][i:i+1]).copy(deep=True)
                new_row['clno'] = new_row['clno'] + quo + 1
                new_row['cloff'] = 0
                new_row['SIZE'] = rem
                rows.append(new_row)

    return newdf.append(rows)