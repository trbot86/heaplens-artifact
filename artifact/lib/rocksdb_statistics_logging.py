"""Explicit tagged adapter for the pinned RocksDB cache-aligned allocator.

Apply before annotation. Original ordinary new/delete functions remain intact;
the tag overloads delegate to them and record compiler-supplied byte extents.
This also works in CoreLocalArray<T>, where ordinary and custom allocation
instantiations share one source-level new[] expression.
"""
from pathlib import Path
import sys


def apply(root):
    header=Path(root)/'monitoring/statistics_impl.h'
    source=header.read_text()
    marker='// HeapLENS explicit StatisticsData allocation adapter'
    if marker in source:
        raise RuntimeError('StatisticsData adapter already present; preserve this attempt')
    declarations='''// HeapLENS explicit StatisticsData allocation adapter
template <class T> struct MemhookNew;
#if defined(__clang__)
#define HEAPLENS_STATISTICS_ALLOCATION __attribute__((annotate("heaplens_tagged_allocation")))
#else
#define HEAPLENS_STATISTICS_ALLOCATION
#endif
'''
    anchor='namespace ROCKSDB_NAMESPACE {'
    if source.count(anchor)!=1:
        raise RuntimeError('Unexpected StatisticsData namespace')
    source=source.replace(anchor,declarations+'\n'+anchor)
    for brackets in ('','[]'):
        original='    void* operator new'+brackets+'(size_t s) { return port::cacheline_aligned_alloc(s); }'
        if source.count(original)!=1:
            raise RuntimeError('Unexpected pinned StatisticsData allocation function')
        replacement=original.replace('    void*','    HEAPLENS_STATISTICS_ALLOCATION void*')+'''
    template <class T>
    static void* operator newBRACKETS(size_t s, const ::MemhookNew<T>& site) {
      void* p = StatisticsData::operator newBRACKETS(s);
      site.record(p, s);
      return p;
    }
    template <class T>
    static void operator deleteBRACKETS(void* p, const ::MemhookNew<T>&) noexcept {
      StatisticsData::operator deleteBRACKETS(p);
    }'''.replace('BRACKETS',brackets)
        source=source.replace(original,replacement)
    source += '\n#undef HEAPLENS_STATISTICS_ALLOCATION\n'
    header.write_text(source)


if __name__=='__main__':apply(sys.argv[1])
