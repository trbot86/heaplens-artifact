"""Context-label C++ new allocations inside searchKnn; preserve STL/libc allocation."""
def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("HNSW query allocation source anchor mismatch")
    return text.replace(old, new, 1)

def logger(text):
    if 'hl_hnsw_new' in text:
        raise ValueError('HNSW query allocation overlay already applied')
    anchor='void * operator new(size_t size) {'
    helper='''extern "C" void memhook_record_alloc(void*,size_t,int,uint16_t,uint16_t);
static thread_local uint16_t hl_query_type = 0;
static thread_local bool hl_query_new_busy = false;
extern "C" uint16_t memhook_hnsw_query_type(uint16_t next) {
    uint16_t previous = hl_query_type; hl_query_type = next; return previous;
}
static void* hl_hnsw_new(size_t size) {
    const bool previous_busy = hl_query_new_busy;
    hl_query_new_busy = true;
    void* mem = memhook_malloc(size, 0, false);
    if (mem && hl_query_type && !previous_busy)
        memhook_record_alloc(mem, size, 0, 65001, hl_query_type);
    hl_query_new_busy = previous_busy;
    return mem;
}
'''
    text=replace_once(text,anchor,helper+anchor)
    # Exactly the scalar and array new implementations, not malloc wrappers.
    old='    void* mem = memhook_malloc(size, 0, false);'
    # Helper uses the same line; replace only after its definition.
    prefix,rest=text.split(anchor,1)
    if rest.count(old)!=2: raise ValueError('two frozen new implementations')
    return prefix+anchor+rest.replace(old,'    void* mem = hl_hnsw_new(size);')

def hooks(text):
    if 'QueryAllocationScope' in text:
        raise ValueError('HNSW query allocation hooks already applied')
    return text+'''
#if defined(HEAPLENS_ENABLE)
extern "C" uint16_t memhook_hnsw_query_type(uint16_t);
namespace hnswlib { namespace heaplens {
struct HeapLensHnswQueryScratch {};
struct QueryAllocationScope {
    uint16_t previous;
    QueryAllocationScope(const QueryAllocationScope&) = delete;
    QueryAllocationScope& operator=(const QueryAllocationScope&) = delete;
    QueryAllocationScope() : previous(memhook_hnsw_query_type(
        typetable.insert(&typeid(HeapLensHnswQueryScratch)))) {}
    ~QueryAllocationScope() { memhook_hnsw_query_type(previous); }
};
}}
#endif
'''

def algorithm(text):
    if 'hl_query_scope' in text:
        raise ValueError('HNSW query allocation scope already applied')
    anchor='    searchKnn(const void *query_data, size_t k, BaseFilterFunctor* isIdAllowed = nullptr) const {'
    return replace_once(text,anchor,anchor+'\n#if defined(HEAPLENS_ENABLE)\n        heaplens::QueryAllocationScope hl_query_scope;\n#endif')
