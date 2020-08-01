import sqlite3
import sys
from lark import Lark
import pandas as pd

l = Lark('''start: c
            c: a | a"::"c
            a: WORD "<" [c ("," c)*] ">" e | WORD "<" [c ("," c)*] ">" | WORD
            e: /[\*]+/
            WORD: /[A-Za-z0-9 _*]+/
            %import common.WS
            %ignore WS
            ''')

def parsetypeandpointer(inpt):
    t = l.parse(inpt)
    # print(t.pretty())

    t = t.children[0]

    while t.data == 'c' and len(t.children) == 2:
        t = t.children[1]
        # print(t.data)

    t = t.children[0]

    stars = ""

    if len(t.children) >= 3 and t.children[len(t.children)-1].data == 'e':
        stars = t.children[len(t.children)-1].children[0]
        # print("stars: ",stars)

    t = t.children[0]

    return t+stars

# print(parsetypeandpointer("blockpool<bst_glock_ns::Node<long long, void*>, void* >***"))
# print(parsetypeandpointer("abtree_ns::Node<11, long long>"))
# print(parsetypeandpointer("RecoveryMgr<record_manager<reclaimer_none<void, pool_interface<void, allocator_interface<void> > >, allocator_new<void>, pool_none<void, allocator_interface<void> >, abtree_ns::Node<11, long long>> >"))
# print(parsetypeandpointer("record_manager<reclaimer_none<void, pool_interface<void, allocator_interface<void> > >, allocator_new<void>, pool_none<void, allocator_interface<void> >, abtree_ns::Node<11, long long>>::MemoryReclamationGuard"))
# print(parsetypeandpointer("record_manager<reclaimer_none<void, pool_interface<void, allocator_interface<void> > >, allocator_new<void>, pool_none<void, allocator_interface<void> >, abtree_ns::Node<11, long long>>"))

allocscon = sqlite3.connect(sys.argv[1])
fieldscon = sqlite3.connect(sys.argv[2])

allocs_df = pd.read_sql_query("SELECT * FROM ALLOCS", allocscon)
fields_df = pd.read_sql_query("SELECT * FROM FIELDS", fieldscon)

allocs_df = allocs_df[:2000]

typedict = dict()

# print(allocs_df)
new_df = allocs_df.sort_values(by=['TYPE'])
print(type(new_df['TYPE'][0]))

for itr in new_df['TYPE']:
    if itr not in typedict:
        print(itr)
        typedict[itr] = parsetypeandpointer(itr)     
    
    new_df['NEWTYPE'] = typedict[itr]

print(new_df)

join_df = pd.merge(new_df, fields_df, how='inner', left_on='NEWTYPE', right_on='CLASS')

print(join_df)