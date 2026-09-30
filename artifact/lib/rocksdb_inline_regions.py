"""Log arena-carved InlineSkipList regions without changing their allocation."""
from pathlib import Path
import sys
import sqlite3


def apply(root):
    root=Path(root)
    header=root/'memtable/inlineskiplist.h'
    source=header.read_text()
    anchor='  Node* x = reinterpret_cast<Node*>(raw + prefix);'
    if source.count(anchor)!=1 or 'HeapLENS arena-carved regions' in source:
        raise RuntimeError('Unexpected InlineSkipList source; refusing duplicate region annotations')
    files=root/'fileset_dump.txt'
    mapping=files.read_text()
    ids=[int(line.split('|',1)[0]) for line in mapping.splitlines() if '|' in line]
    fid=max(ids,default=0)+1
    if fid>65535:raise RuntimeError('No file identifier available')
    annotation=f'''
  // HeapLENS arena-carved regions: the upper-level pointer array precedes
  // the Node, whose variable-length key follows its level-zero pointer.
  if (prefix > 0) {{
    unit_log.file = {fid};
    MEMHOOK_LOG_CPP_ALLOC(raw, prefix, typeid(std::atomic<Node*>));
  }}
  unit_log.file = {fid};
  MEMHOOK_LOG_CPP_ALLOC(x, sizeof(Node) + key_size, typeid(Node));
'''
    header.write_text(source.replace(anchor,anchor+annotation))
    files.write_text(mapping.rstrip()+f'\n{fid}|memtable/inlineskiplist.h\n')


def verify(database, optimized=False):
    with sqlite3.connect(database) as db:
        rows=db.execute("SELECT DISTINCT TYPE,ACTUALADDR,ACTUALSIZE FROM SUPERTABLE WHERE isNew=1 AND TYPE LIKE '%InlineSkipList%Node%'").fetchall()
    nodes=[row for row in rows if row[0].endswith('::Node')]
    prefixes=[row for row in rows if row[0].startswith('std::atomic<')]
    if not nodes or not prefixes:
        raise RuntimeError('Trace is missing typed InlineSkipList nodes or upper-level pointer arrays')
    tall=[row for row in prefixes if row[2]>=24]
    if optimized and any(address%64 for _,address,_ in tall):
        raise RuntimeError('Optimized tall-node pointer array is not cache-line aligned')
    print(f'InlineSkipList: {len(nodes)} sampled node regions, {len(prefixes)} pointer arrays, {len(tall)} tall arrays')


if __name__=='__main__':
    if sys.argv[1]=='--verify':verify(sys.argv[2],len(sys.argv)>3 and sys.argv[3]=='optimized')
    else:apply(sys.argv[1])
