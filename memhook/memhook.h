// mention Curtis Bartley
#ifndef __MEMHOOK_H
#define __MEMHOOK_H

#include <iostream>
#include <new>
#include <typeinfo>
#include <typeindex>
#include <bits/stdc++.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <execinfo.h>
#include <cxxabi.h>
#include <dlfcn.h>
#include <pthread.h>
#include <vector>
#include <stdio.h>
#include <aio.h>
#include <unordered_set>

#include "memhook_interface.h"
#include "memstamp.h"
#include "hash.h"
#include "memhook_ssmem.h"

#define MEMHOOK_BACKTRACE_DEPTH 2
#ifndef MEMHOOK_MAX_THREADS
  #define MEMHOOK_MAX_THREADS 1000
#endif
#define MEMHOOK_MAX_TRACK 1000000
#define MEMHOOK_MAX_TYPE_LENGTH 1000
#define MEMHOOK_MAX_RETRY 10
#define MEMHOOK_MAX_BUFFER_SIZE 1000000
#define PADDING 64

using namespace std;

struct slot;
struct memhook_info_t;
class ThreadExiter;
// thread_local unordered_set<const char*> threadFiles;
// thread_local unordered_set<const char*> typeFiles;
// unordered_set<const char*> globalTypes;
// unordered_set<const char*> globalFiles;

memhook_hashtable filetable;
memhook_hashtable typetable;

thread_local int thread_first_call = 1;
thread_local int first_filled_buffer_status = 0;
thread_local struct memhook_info_t ** allocation_log = NULL;
thread_local int log_index = 0;
thread_local struct aiocb * async_struct_first_buffer = NULL;
thread_local struct aiocb * async_struct_second_buffer = NULL;
thread_local struct aiocb * async_struct_array = NULL;

// double pointer variables are required for the aio_suspend api
thread_local struct aiocb ** async_api_struct_list = NULL;
thread_local struct aiocb ** async_api_first_buffer_req_list = NULL;
thread_local struct aiocb ** async_api_second_buffer_req_list = NULL;

//which buffer
thread_local int buffer_index = 0;
//how many buffers
thread_local int number_of_buffers = 2;

thread_local memhook_info_t unit_log;

thread_local int fileset_fd;

int global_fd;

/*#ifdef __cplusplus
extern "C" {
#endif
__attribute__((weak)) extern const char memhook_file_path[] = "binary_dump.txt";
__attribute__((weak)) extern const char memhook_typeset_path[] = "typeset_dump.txt";
__attribute__((weak)) extern const char memhook_fileset_path[] = "fileset_dump.txt";
#ifdef __cplusplus
}
#endif*/

uint64_t memhook_get_server_clock() {
#if defined(__i386__)
    uint64_t ret;
    __asm__ __volatile__("rdtsc" : "=A" (ret));
#elif defined(__x86_64__)
    unsigned hi, lo;
    __asm__ __volatile__ ("rdtsc" : "=a"(lo), "=d"(hi));
    uint64_t ret = ( (uint64_t)lo)|( ((uint64_t)hi)<<32 );
#else 
    #error Must support RDTSC instruction! Sorry...
#endif
    return ret;
}


struct thread_record_array{
  int buffer_size_nbytes;
  struct memhook_info_t *allocation_log;
};

class memhook_memory_pool {
 private:
  char padding1[PADDING];
  int array_count;

  // vector <memhook_info_t *> memory_pool;
  vector <thread_record_array> memory_pool;
  pthread_mutex_t lock;
  char padding2[PADDING];

  public:
  void add(memhook_info_t* logarray, int buffer_count);
  memhook_memory_pool();
  ~memhook_memory_pool();
    //virtual memhook_info_t* pop();
    //virtual void dumptodisk();
};


memhook_memory_pool mem_pool_obj;

class ThreadExiter
  {
    public:
    //ThreadExiter() = default;
   
    // ThreadExiter(ThreadExiter const&) = delete;
    
    //void operator=(ThreadExiter const&) = delete;
    
    ThreadExiter(){
      // printf("ThreadExiter Constructor has been called - v2\n");
    }
    ~ThreadExiter()
    {
      // printf("ThreadExiter Destructor has been called - v2\n");

      if(async_struct_array) {
        for (int i = 1; i < number_of_buffers; i++) {
          if (aio_error(&async_struct_array[(buffer_index + i) % number_of_buffers]) == EINPROGRESS){
            async_api_struct_list[0] = &async_struct_array[(buffer_index + i) % number_of_buffers];
            
            if (aio_suspend(async_api_struct_list, 1, NULL) != 0) {
              cout << "aio_suspend failed in thread destructor" << endl;
            }
          }
        }

        int unfilled_buffer_size = sizeof(struct memhook_info_t)* log_index;
        //ADD FILE AND TYPES TO MEMPOOL OBJECT
        mem_pool_obj.add(allocation_log[buffer_index], unfilled_buffer_size);
      }
      //close(fd);
    }
    void add()
    {

    }
  };


void  (memhook_free)(void *ptr, int line, bool log);
void* memhook_malloc(size_t size, int line, bool log);

#warning This binary is being compiled with memhook.

void   (*next_free)(void *ptr);
#if defined(MEMHOOK_ASCYLIB)
void   (*next_ssmem_free)(ssmem_allocator_t* a, void* ptr);
// void * (*ssmem_alloc)(ssmem_allocator_t* a, size_t size);
void   (*next_ssfree)(void* ptr);
#endif
#if defined(USE_RALLOC)
void (*next_RP_free)(void* ptr);
#endif
// void * (*ssalloc)(size_t size);
// void * (*ssalloc_aligned)(size_t alignment, size_t size);


struct slot {
	volatile bool occupied;
	thread::id id;
	int offset;
  char padding[128];
};

thread_local int iter = 0;

/*Iterator for individual thread allocation in
* tracking data structure
*/

thread_local int it = 0;
thread_local memhook_info_t* myArray = nullptr;
thread_local int max_retry = 0;

ostream& operator << (ostream& os, memhook_info_t& info);

MemStamp::MemStamp(char const *filename, int lineNum)
    : filename(filename), lineNum(lineNum) { }
MemStamp::~MemStamp() { }

MemStampCollector::MemStampCollector() {
  
}

MemStampCollector::~MemStampCollector() {
  
}

void MemStampCollector::copy(memhook_info_t &unit_log){
	if(thread_first_call) {
		allocation_log = (struct memhook_info_t **) malloc(sizeof(struct memhook_info_t*)*number_of_buffers);
    for(int i = 0; i < number_of_buffers; i++) {
      allocation_log[i] = (struct memhook_info_t*) malloc(sizeof(struct memhook_info_t)*MEMHOOK_MAX_BUFFER_SIZE);
    }

    // printf("%lu \n", sizeof(struct memhook_info_t));
    async_struct_array = (struct aiocb*) malloc(sizeof(struct aiocb)*number_of_buffers);
    async_api_struct_list = (struct aiocb **) malloc(sizeof(struct aiocb*)*1);

    thread_first_call = 0;
	}

  memcpy(&allocation_log[buffer_index][log_index], &unit_log, sizeof(memhook_info_t));
  //set unit_log to zero
  memset(&unit_log, 0, sizeof(unit_log));
  log_index++;

  if(log_index == MEMHOOK_MAX_BUFFER_SIZE) {
    async_struct_array[buffer_index].aio_buf = allocation_log[buffer_index];
    async_struct_array[buffer_index].aio_nbytes = sizeof(struct memhook_info_t)*MEMHOOK_MAX_BUFFER_SIZE;
    async_struct_array[buffer_index].aio_fildes = global_fd;
    async_struct_array[buffer_index].aio_offset = 0;
    async_struct_array[buffer_index].aio_reqprio = 0;
    async_struct_array[buffer_index].aio_sigevent.sigev_notify = SIGEV_NONE;

    if (aio_write(&async_struct_array[buffer_index]) != 0) {
      cout << "aio_write FAILED" << endl;
    }

    buffer_index = (buffer_index + 1) % number_of_buffers;
    log_index = 0;

    if (aio_error(&async_struct_array[buffer_index]) == EINPROGRESS){
      async_api_struct_list[0] = &async_struct_array[buffer_index];
      
      if(aio_suspend(async_api_struct_list, 1, NULL) != 0) {
        cout << "aio_suspend failed in copy" << endl;
      }
    }
  }
}

MemStampCollector memhookCollector;

//Keeps the total number of concurrent threads
int arrayCount = 0;

thread_local bool setup = false;

thread_local ThreadExiter exiter;
#endif
