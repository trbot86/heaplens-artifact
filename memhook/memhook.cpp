/**
 * List of functions to overload obtained from mimalloc:
 *      https://github.com/microsoft/mimalloc/blob/master/src/alloc-override.c
 *
 * Simple tmpbuff allocator to avoid bad LD_PRELOAD interaction with DLSYM init adapted from:
 *      https://stackoverflow.com/questions/6083337/overriding-malloc-using-the-ld-preload-mechanism
 *
 * Caveat: until init() is complete, malloc should only be called by a single thread (in dl_init()).
 *         (This should essentially always be true...)
 */
#if defined(_WIN32) || defined(__APPLE__) || defined(__ANDROID__)
#error "Currently we do not support Windows, Apple, Android"
#endif

#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include <dlfcn.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <cstring>
#include "memhook.h"

// #define MEMHOOK_FORCE_MALLOC

#undef new
#undef delete

#ifndef mallog_likely
    #if defined(__GNUC__) || defined(__clang__)
        #define mallog_unlikely(x)     __builtin_expect((x),0)
        #define mallog_likely(x)       __builtin_expect((x),1)
    #else
        #define mallog_unlikely(x)     (x)
        #define mallog_likely(x)       (x)
    #endif
#endif

const char * memhook_file_path;
const char * memhook_typeset_path;
// const char * memhook_fileset_path;

static char tmpbuff[1<<20];
static unsigned long tmppos = 0;
static unsigned long tmpallocs = 0;
// void *memset(void*, int, size_t);
// void *memmove(void *to, const void *from, size_t size);
// ------------------------------------------------------
// Override system malloc
// ------------------------------------------------------

// static void * (*next_valloc)(size_t size) = 0;
// static void * (*next_pvalloc)(size_t size) = 0;
// static void * (*next_memalign)(size_t blocksize, size_t bytes) = 0;
// static int    (*next_posix_memalign)(void **memptr, size_t alignment, size_t size) = 0;
// static void * (*next_aligned_alloc)(size_t alignment, size_t size) = 0;
// static void * (*next_realloc)(void *ptr, size_t size) = 0;
// static void * (*next_reallocf)(void *ptr, size_t size) = 0;
// static void * (*next_reallocarray)(void *ptr, size_t nmemb, size_t size) = 0;

static volatile int initialized = 0;

__attribute__((constructor)) static void init() {
    const char* file_env_path = std::getenv("MEMHOOK_OUTPUT_DUMP_FILE");
    // const char* fileset_env_path = std::getenv("MEMHOOK_OUTPUT_FILE_FILE");

    if (file_env_path) {
	    memhook_file_path = file_env_path;
    }
    else {
	    memhook_file_path = "binary_dump.txt";
    }
#ifdef USE_TEMPLATE
    const char* typeset_env_path = std::getenv("MEMHOOK_OUTPUT_TYPE_FILE");
    if (typeset_env_path) {
	    memhook_typeset_path = typeset_env_path;
    }
    else {
	    memhook_typeset_path = "typeset_dump.txt";
    }
#endif

    // if (fileset_env_path) {
	//     memhook_fileset_path = fileset_env_path;
    // }
    // else {
	//     memhook_fileset_path = "fileset_dump.txt";
    // }

    next_free = (void (*)(void *)) dlsym(RTLD_NEXT, "free");
    if (!next_free) {
        fprintf(stderr, "Error in `dlsym`: %s\n", dlerror());
        exit(1);
    }

    global_fd = open(memhook_file_path, O_RDWR | O_APPEND | O_CREAT, S_IRWXU | S_IRWXG | S_IRWXO);
    initialized = 1;
    fprintf(stdout, "Done memhook constructor\n");
}

memhook_memory_pool::memhook_memory_pool(){
  //dummy constructor
  printf("memory_pool Constructor \n");
}

memhook_memory_pool::~memhook_memory_pool(){
    cout << "MEMHOOK POOL DESTRUCTOR" << endl;
	int total_byte_count = 0, status = 0;

	//confirm this method works with trevor
	struct thread_record_array * destructor_mem_array = &memory_pool[0];

    // std::ofstream fileset;
//   fileset.open(memhook_fileset_path, std::ofstream::out | std::ofstream::app);

	//instead of doing this, the memory_pool array can keep track of cumulative bytes

	for (int i = 0; i < memory_pool.size(); i++) {
		total_byte_count += memory_pool[i].buffer_size_nbytes;
		write(global_fd, memory_pool[i].allocation_log, memory_pool[i].buffer_size_nbytes);
	}

//   for (int i = 0;i < MEMHOOK_HASH_TABLE_SIZE;i++) {
//     // if(filetable.bucket[i] != NULL)
//     if(filetable.bucket[i].full) {
//       printf("Filetable bucket is: %p\n", (void*) filetable.bucket[i].str);
//       fileset << (void*)filetable.bucket[i].str << "|" << filetable.bucket[i].str << endl;
//     }
//   }

#ifdef USE_TEMPLATE
    std::ofstream typeset;
    typeset.open(memhook_typeset_path, std::ofstream::out | std::ofstream::app);

    for(int i = 0; i < MEMHOOK_HASH_TABLE_SIZE; i++) {
        // if(typetable.bucket[i] != NULL) {
        if(typetable.bucket[i].full) {
            char* real_tname = abi::__cxa_demangle((*typetable.bucket[i].typeid_ptr).name(), 0, 0, &status);
            assert(real_tname != nullptr);
            // if (real_tname) {
            printf("(C++) Typetable bucket is: %p\n", typetable.bucket[i].typeid_ptr);
            typeset << (void*)typetable.bucket[i].typeid_ptr << "|" << real_tname << endl;
            // }
            // else {
            //     printf("(C) Typetable bucket is: %p\n", typetable.bucket[i].str);
            //     typeset << (void*)typetable.bucket[i].str << "|" << typetable.bucket[i].str << endl;
            // }
        // cout << typetable.bucket[i] << endl;
        }
    }

    // fileset.close();
    typeset.close();
#endif
}

//max buffer size is already known
void memhook_memory_pool::add(memhook_info_t *logarray, int buffer_size_nbytes){

  if(buffer_size_nbytes == 0)
    return;

  pthread_mutex_lock(&lock);

  //thread_first_call = 0;
  // makes sure that calling thread never calls add function again
  //this.memory_pool.push_back(logarray);

  // printf("within mem_pool add \n");
  this->memory_pool.push_back(thread_record_array());
  memory_pool[memory_pool.size() - 1].allocation_log = logarray;
  memory_pool[memory_pool.size() - 1].buffer_size_nbytes = buffer_size_nbytes;

  // for(auto const& i : threadFiles) {
  //   globalFiles.insert(i);
  // }

  // for(auto const& i : typeFiles) {
  //   globalTypes.insert(i);
  // }

  
  pthread_mutex_unlock(&lock);
}

void *memhook_malloc(size_t size, int line = 0, bool log = true) {
    if (!initialized) {
        if (tmppos + size < sizeof(tmpbuff)) {
            void *retptr = tmpbuff + tmppos;
            tmppos += size;
            ++tmpallocs;
            if (!retptr) exit(72);
            return retptr;
        } else {
            // fprintf(stdout, "jcheck: too much memory requested during initialisation - increase tmpbuff size\n");
            exit(99);
        }
    }

    // if (!next_malloc) next_malloc = (void * (*)(size_t ))dlsym(RTLD_NEXT, "malloc");
    // if (!next_malloc) fprintf(stdout, "failed to find next malloc\n");

    if(!setup) {
        exiter.add();
        setup = true;
    }

    void* mem;
    mem = malloc(size);

    if(mem == 0) {
        throw bad_alloc();
    }
    
    unit_log.timestamp = memhook_get_server_clock();
    unit_log.size = size;
    unit_log.addr = mem;
    unit_log.typeofop = true;
    unit_log.line = line;
    // if (log) {
    //     unit_log.file = filetable.insert(file);
    //     unit_log.line = line;
    // }

    return mem;
}

void memhook_free(void *ptr, int line = 0, bool log = false) {
    if (!setup) {
        exiter.add();
        setup = true;
    }
    
    if (!initialized || (ptr >= (void*) tmpbuff && ptr <= (void*)(tmpbuff + tmppos))) { // possible off-by-one error at right endpoint...
        // fprintf(stdout, "freeing temp memory\n");
        return;
    }

    // if (!next_free) next_free = (void (*)(void *))dlsym(RTLD_NEXT, "free");
    // if (!next_free) fprintf(stdout, "failed to find next free\n");
    next_free(ptr);

    unit_log.timestamp = memhook_get_server_clock();
    unit_log.size = 0;
    unit_log.addr = ptr;
    unit_log.typeofop = false;
    // if (log) {
    //     unit_log.file = file;
    //     unit_log.line = line;
    // }
}


extern "C" {

    // Used for C/C++ projects which do not support templating
    void* malloc_s(size_t size, int line, uint16_t fid, uint16_t tid) {
        void* ptr = memhook_malloc(size, line, true);
        if (initialized) {
            unit_log.file = fid;
            unit_log.tindex_name = tid;
            // cout << "CALLED CUSTOM MALLOC, TYPE: " << (void*) unit_log.tindex_name << endl;
            memhookCollector.copy(unit_log);
        }
        return ptr;
    }

    void free_log(void* ptr) {
        MEMHOOK_LOG_FREE(ptr)
    }

    void free(void* ptr) {
        if (!ptr) return;
        memhook_free(ptr, 0, false);
        if (initialized) {
            // cout << "CALLED CUSTOM FREE" << endl;
            memhookCollector.copy(unit_log);
        }
    }

    #ifdef USE_RALLOC
    void RP_free(void* ptr) {
        if (!next_RP_free) next_RP_free = (void (*)(void *))dlsym(RTLD_NEXT, "RP_free");
        if (!next_RP_free) fprintf(stdout, "failed to find next RP_free\n");
        next_RP_free(ptr);
        MEMHOOK_LOG_FREE(ptr)
    }
    #endif

    // void free_s(void* ptr, int line, const char* filename, const char* typename) {
    //     filetable.insert(filename);
    //     if (!ptr) return;
    //     memhook_free(ptr, filename, line, false);
    //     if (initialized) {
    //         // cout << "CALLED CUSTOM FREE" << endl;
    //         memhookCollector.copy(unit_log);
    //     }
    // }

    #if defined(MEMHOOK_GZIP)
    void* xmalloc_s(size_t size, int line, uint16_t fid, uint16_t tid) {
        void* ptr = xmalloc(size);
        MEMHOOK_LOG_C_ALLOC(ptr, size, line, fid, tid)
        return ptr;
    }

    void* xcalloc_s(size_t nmemb, size_t size, int line, uint16_t fid, uint16_t tid) {
        void* ptr = xcalloc(nmemb, size);
        MEMHOOK_LOG_C_ALLOC(ptr, size * nmemb, line, fid, tid)
        return ptr;
    }
    #endif

    #if defined(MEMHOOK_ASCYLIB)
    void* ssmem_alloc_s(ssmem_allocator_t* a, size_t size, int line, uint16_t fid, uint16_t tid) {
        // if (!next_ssmem_alloc) next_ssmem_alloc = (void * (*)(ssmem_allocator_t*, size_t))dlsym(RTLD_NEXT, "ssmem_alloc");
        // if (!next_ssmem_alloc) fprintf(stdout, "failed to find next ssmem alloc\n");

        // cout << "CALLED ssmem_alloc" << endl;
        #ifdef MEMHOOK_FORCE_MALLOC
        void* ptr = malloc_s(size, line, fid, tid);
        #endif
        #ifndef MEMHOOK_FORCE_MALLOC
        void* ptr = ssmem_alloc(a, size);
        MEMHOOK_LOG_C_ALLOC(ptr, size, line, fid, tid)
        #endif

        return ptr;
    }

    void ssmem_free(ssmem_allocator_t* a, void* ptr) {
        #ifdef MEMHOOK_FORCE_MALLOC
        free(ptr);
        #endif
        #ifndef MEMHOOK_FORCE_MALLOC
        if (!next_ssmem_free) next_ssmem_free = (void (*)(ssmem_allocator_t*, void*))dlsym(RTLD_NEXT, "ssmem_free");
        if (!next_ssmem_free) fprintf(stdout, "failed to find next ssmem free\n");

        next_ssmem_free(a, ptr);
        
        MEMHOOK_LOG_FREE(ptr)
        #endif
    }

    void* ssalloc_s(size_t size, int line, uint16_t fid, uint16_t tid) {
        // if (!next_ssalloc) next_ssalloc = (void * (*)(size_t))dlsym(RTLD_NEXT, "ssalloc");
        // if (!next_ssalloc) fprintf(stdout, "failed to find next ssalloc\n");

        #ifdef MEMHOOK_FORCE_MALLOC
        void* ptr = malloc_s(size, line, fid, tid);
        #endif
        #ifndef MEMHOOK_FORCE_MALLOC
        void* ptr = ssalloc(size);
        MEMHOOK_LOG_C_ALLOC(ptr, size, line, fid, tid)
        #endif

        return ptr;
    }

    void* ssalloc_aligned_s(size_t alignment, size_t size, int line, uint16_t fid, uint16_t tid) {
        // if (!next_ssalloc_aligned) next_ssalloc_aligned = (void * (*)(size_t, size_t))dlsym(RTLD_NEXT, "ssalloc_aligned");
        // if (!next_ssalloc_aligned) fprintf(stdout, "failed to find next ssalloc_aligned\n");

        #ifdef MEMHOOK_FORCE_MALLOC
        void* ptr = _mm_malloc(size, alignment);
        #endif
        #ifndef MEMHOOK_FORCE_MALLOC
        void* ptr = ssalloc_aligned(alignment, size);
        #endif

        MEMHOOK_LOG_C_ALLOC(ptr, memhook_roundUp(size, alignment), line, fid, tid)

        return ptr;
    }

    void ssfree(void* ptr) {
        #ifdef MEMHOOK_FORCE_MALLOC
        free(ptr);
        #endif
        #ifndef MEMHOOK_FORCE_MALLOC
        if (!next_ssfree) next_ssfree = (void (*)(void*))dlsym(RTLD_NEXT, "ssfree");
        if (!next_ssfree) fprintf(stdout, "failed to find next ssfree\n");

        next_ssfree(ptr);
        
        MEMHOOK_LOG_FREE(ptr)
        #endif
    }
    #endif // MEMHOOK_ASCYLIB

    int posix_memalign_s(void** memptr, size_t alignment, size_t size, int line, uint16_t fid, uint16_t tid) {
        int ret = posix_memalign(memptr, alignment, size);
        MEMHOOK_LOG_C_ALLOC(memptr, memhook_roundUp(size, alignment), line, fid, tid)
        return ret;
    }

    void* memalign_s(size_t alignment, size_t size, int line, uint16_t fid, uint16_t tid) {
        void* ptr = memalign(alignment, size);
        MEMHOOK_LOG_C_ALLOC(ptr, memhook_roundUp(size, alignment), line, fid, tid)
        return ptr;
    }

    void* calloc_s(size_t nmemb, size_t size, int line, uint16_t fid, uint16_t tid) {
        if (!initialized) {
            void *ptr = memhook_malloc(nmemb*size, line, false);
            if (ptr) memset(ptr, 0, nmemb*size);
            if (!ptr) exit(70);
            return ptr;
        }

        void* ptr = calloc(nmemb, size);
        MEMHOOK_LOG_C_ALLOC(ptr, size * nmemb, line, fid, tid)

        return ptr;
    }
}

/**********************
 * TODO:
 * Add bound checking for number of allocations
 * Do we need to initialize as zero first in order
 * to know when to stop while printing?
 * 
 **********************/
void * operator new(size_t size) {
    void* mem = memhook_malloc(size, 0, false);

    if(mem == 0) {
        throw bad_alloc();
    }

    return mem;
}

void *operator new[] (size_t size) {
    void* mem = memhook_malloc(size, 0, false);
    
    if(mem == 0) {
        throw bad_alloc();
    }

    return mem;
}

void operator delete(void * mem) _GLIBCXX_USE_NOEXCEPT {
    memhook_free(mem, 0, false);
    memhookCollector.copy(unit_log);
    return;
}

void operator delete[](void *mem)  _GLIBCXX_USE_NOEXCEPT {
    memhook_free(mem, 0, false);
    memhookCollector.copy(unit_log);
    return;
}
