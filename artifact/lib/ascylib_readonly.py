"""Make the diagnostic uniform zero-update workload strictly read-only."""
from pathlib import Path
import sys

def apply(root):
    path=Path(root)/'include/main_test_loop.h'
    source=path.read_text()
    marker='// HeapLENS: zero update rate must not insert when the RNG returns zero.'
    if marker in source:raise RuntimeError('Read-only guard already present')
    start=source.index('#elif WORKLOAD == 0')
    end=source.index('#  define TEST_LOOP_ONLY_UPDATES()',start)
    section=source[start:end]
    for threshold in ('scale_put','scale_rem'):
        old='unlikely(c <= '+threshold+')'
        if section.count(old)!=1:raise RuntimeError('Unexpected pinned uniform operation selector')
        section=section.replace(old,'unlikely(scale_rem != 0 && c <= '+threshold+')')
    source=source[:start]+marker+'\n'+section+source[end:]
    path.write_text(source)

if __name__=='__main__':apply(sys.argv[1])
