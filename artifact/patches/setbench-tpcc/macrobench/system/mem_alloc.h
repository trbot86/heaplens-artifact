#ifndef _MEM_ALLOC_H_
#define _MEM_ALLOC_H_

#include "global.h"
#include <map>

const int SizeNum = 4;
const UInt32 BlockSizes[] = {32, 64, 256, 1024};

typedef struct free_block {
    int size;
    struct free_block* next;
} FreeBlock;

class Arena {
public:
	void init(int arena_id, int size);
	void * alloc();
	void free(void * ptr);
private:
	char * 		_buffer;
	int 		_size_in_buffer;
	int 		_arena_id;
	int 		_block_size;
	FreeBlock * _head;
	char 		_pad[128 - sizeof(int)*3 - sizeof(void *)*2 - 8];
};

class mem_alloc {
public:
    void init(uint64_t part_cnt, uint64_t bytes_per_part);
    void register_thread(int thd_id);
    void unregister();
    void * alloc(uint64_t size, uint64_t part_id);
#ifdef __MEMHOOK_INTERFACE_H
    // HeapLENS/sifter instrumentation hook. AllocationLoggingCheck's
    // MATCH_FUNCTIONS registers the qualified name ::mem_alloc::alloc,
    // not every factory or arena method named alloc,
    // so `mem_allocator.alloc(size, part_id)` call sites get rewritten to
    // `mem_allocator.alloc<Type, __LINE__, fileID>(size, part_id)`. That
    // requires a matching template overload to exist, which the stock class
    // above doesn't have. This delegates straight to memhook_interface.h's
    // own malloc<T,line,filename> template (rather than duplicating its
    // unit_log/typetable/memhookCollector logic here). In the pinned TPC-C
    // source, mem_alloc::alloc unconditionally calls malloc(size); its pooling
    // branches are commented out. This wrapper preserves that allocation path
    // while recording the caller's type and source location exactly once.
    // Revalidate this wrapper if the underlying allocator implementation changes.
    // Guarded on __MEMHOOK_INTERFACE_H (memhook_interface.h's own include
    // guard macro) rather than an ad hoc flag: sifter.sh's --includes-only
    // step prepends `#include "memhook_interface.h"` as the literal first
    // line of every file (including this one), so by the time this class
    // body is parsed, __MEMHOOK_INTERFACE_H is already defined if and only
    // if this is an instrumented build -- meaning a stock (non-instrumented)
    // build of this exact same patched file compiles unaffected, with the
    // template overload simply absent (malloc<T,line,filename> wouldn't
    // even be declared for it to call).
    template <typename T, int line, uint16_t filename>
    void* alloc(uint64_t size, uint64_t part_id) {
        return malloc<T, line, filename>(size);
    }
#endif
    void free(void * block, uint64_t size);
	int get_arena_id();
private:
    void init_thread_arena();
	int get_size_id(UInt32 size);
	
	// each thread has several arenas for different block size
	Arena ** _arenas;
	int _bucket_cnt;
    std::pair<pthread_t, int>* pid_arena;//                     max_arena_id;
    pthread_mutex_t         map_lock; // only used for pid_to_arena update
};

#endif
