#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <sys/mman.h>

static void* (*real_malloc)(size_t)         = NULL;
static void* (*real_realloc)(void*, size_t) = NULL;
static void* (*real_calloc)(size_t, size_t) = NULL;
static void  (*real_free)(void*)            = NULL;

static int alloc_init_pending = 0;

/* Load original allocation routines at first use */
static void alloc_init(void)
{
  alloc_init_pending = 1;
  real_malloc  = dlsym(RTLD_NEXT, "malloc");
  real_realloc = dlsym(RTLD_NEXT, "realloc");
  real_calloc  = dlsym(RTLD_NEXT, "calloc");
  real_free    = dlsym(RTLD_NEXT, "free");
  if (!real_malloc || !real_realloc || !real_calloc || !real_free) {
    fputs("alloc.so: Unable to hook allocation!\n", stderr);
    fputs(dlerror(), stderr);
    exit(1);
  } else {
    fputs("alloc.so: Successfully hooked\n", stderr);
  }
  alloc_init_pending = 0;
}

#define ZALLOC_MAX 1024
static void* zalloc_list[ZALLOC_MAX];
static size_t zalloc_cnt = 0;

/* dlsym needs dynamic memory before we can resolve the real memory 
 * allocator routines. To support this, we offer simple mmap-based 
 * allocation during alloc_init_pending. 
 * We support a max. of ZALLOC_MAX allocations.
 * 
 * On the tested Ubuntu 16.04 with glibc-2.23, this happens only once.
 */
void* zalloc_internal(size_t size)
{
  fputs("alloc.so: zalloc_internal called", stderr);
  if (zalloc_cnt >= ZALLOC_MAX-1) {
    fputs("alloc.so: Out of internal memory\n", stderr);
    return NULL;
  }
  /* Anonymous mapping ensures that pages are zero'd */
  void* ptr = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_ANONYMOUS | MAP_PRIVATE, 0, 0);
  if (MAP_FAILED == ptr) {
    perror("alloc.so: zalloc_internal mmap failed");
    return NULL;
  }
  zalloc_list[zalloc_cnt++] = ptr; /* keep track for later calls to free */
  return ptr;
}

void free(void* ptr)
{
  if (alloc_init_pending) {
    fputs("alloc.so: free internal\n", stderr);
    /* Ignore 'free' during initialization and ignore potential mem leaks 
     * On the tested system, this did not happen
     */
    return;
  }
  if(!real_malloc) {
    alloc_init();
  }
  for (size_t i = 0; i < zalloc_cnt; i++) {
    if (zalloc_list[i] == ptr) {
      /* If dlsym cleans up its dynamic memory allocated with zalloc_internal,
       * we intercept and ignore it, as well as the resulting mem leaks.
       * On the tested system, this did not happen
       */
      return;
    }
  }
  real_free(ptr);
}

void *malloc(size_t size)
{
  if (alloc_init_pending) {
    fputs("alloc.so: malloc internal\n", stderr);
    return zalloc_internal(size);
  }
  if(!real_malloc) {
    alloc_init();
  }
  void* result = real_malloc(size);
  //fprintf(stderr, "alloc.so: malloc(0x%zx) = %p\n", size, result);
  return result;
}

void *realloc(void* ptr, size_t size)
{
  if (alloc_init_pending) {
    fputs("alloc.so: realloc internal\n", stderr);
    if (ptr) {
      fputs("alloc.so: realloc resizing not supported\n", stderr);
      exit(1);
    }
    return zalloc_internal(size);
  }
  if(!real_malloc) {
    alloc_init();
  }
  return real_realloc(ptr, size);
}

void *calloc(size_t nmemb, size_t size)
{
  if (alloc_init_pending) {
    fputs("alloc.so: calloc internal\n", stderr);
    /* Be aware of integer overflow in nmemb*size.
     * Can only be triggered by dlsym */
    return zalloc_internal(nmemb * size);
  }
  if(!real_malloc) {
    alloc_init();
  }
  return real_calloc(nmemb, size);
}