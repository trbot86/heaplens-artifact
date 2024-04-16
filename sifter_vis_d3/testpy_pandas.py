import pandas as pd

data = {
    'alloc_ts': [1,     4,      8,      12,     30,     45,     46,     50],
    'free_ts':  [4,     10,     13,     20,     51,     50,     60,     55],
    'addr':     [100,   104,    100,    104,    100,    108,    112,    118],
    'size':     [4,     4,      4,      8,      8,      2,      4,      6],
    'type':     ['int', 'int', 'int', 'long', 'double', 'short', 'int', 'Descriptor']
}

cls = 6
page_size = 10