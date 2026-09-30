"""Apply the HashSkipList field-order fix to a fresh diagnostic source copy."""
from pathlib import Path
import sys


def apply(root):
    path=Path(root)/'memtable/skiplist.h'
    text=path.read_text()
    old='  Node** prev_;\n  int32_t prev_height_;'
    if text.count(old)!=1:
        raise RuntimeError('Unexpected SkipList fields; refusing an unverified layout edit')
    path.write_text(text.replace(old,'  int32_t prev_height_;\n  Node** prev_;'))


if __name__=='__main__': apply(sys.argv[1])
