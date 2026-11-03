"""Apply the final walkthrough's HJ64 descriptor setting to a fresh source copy."""
import hashlib
from pathlib import Path
import sys

def apply(root):
    header=root/'ds/howley_int_bst_lf/howley_impl.h'
    text=header.read_text()
    if text.count('#define LARGE_DES\n')!=1:
        raise ValueError('Expected one LARGE_DES definition in pinned HJ source')
    allocator=root/'lib/libjemalloc.so'
    if hashlib.sha256(allocator.read_bytes()).hexdigest()!='a279897f69625d2ab983cc4d5ed62e7ebf6856fc061248c26850d4e1683b479f':
        raise ValueError('HJ walkthrough requires the pinned jemalloc 5.0.1 allocator')
    header.write_text(text.replace('#define LARGE_DES\n','// HJ64 walkthrough: LARGE_DES disabled\n'))

if __name__=='__main__':apply(Path(sys.argv[1]))
