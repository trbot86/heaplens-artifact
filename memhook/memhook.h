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

#include "memstamp.h"

#define MEMHOOK_BACKTRACE_DEPTH 2
#ifndef MEMHOOK_MAX_THREADS
    #define MEMHOOK_MAX_THREADS 1000
#endif
#define MEMHOOK_MAX_TRACK 1000000
#define MEMHOOK_MAX_TYPE_LENGTH 1000
#define MEMHOOK_MAX_RETRY 10
#define MEMHOOK_MAX_BUFFER_SIZE 10000
#define PADDING 64

using namespace std;

struct slot;
struct info_t;
class ThreadExiter;
thread_local unordered_set<const char*> threadFiles;
thread_local unordered_set<const char*> typeFiles;
unordered_set<const char*> globalTypes;
unordered_set<const char*> globalFiles;

thread_local int thread_first_call = 1;
thread_local int first_filled_buffer_status = 0;
thread_local struct info_t ** allocation_log = NULL;
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

thread_local info_t unit_log;

thread_local int fileset_fd;

int global_fd;

struct thread_record_array{
  int buffer_size_nbytes;
  struct info_t *allocation_log;
};

class memhook_memory_pool {
 private:
  char padding1[PADDING];
  int array_count;

  // vector <info_t *> memory_pool;
  vector <thread_record_array> memory_pool;
  pthread_mutex_t lock;
  char padding2[PADDING];

  public:
  void add(info_t* logarray, int buffer_count);
  memhook_memory_pool();
  ~memhook_memory_pool();
    //virtual info_t* pop();
    //virtual void dumptodisk();
};

memhook_memory_pool::memhook_memory_pool(){
  //dummy constructor
  printf("memory_pool Constructor \n");
}

memhook_memory_pool::~memhook_memory_pool(){
	int total_byte_count = 0, status = 0;

	//confirm this method works with trevor
	struct thread_record_array * destructor_mem_array = &memory_pool[0];

	char file_path[] = "binary_dump.txt";
  char fileset_path[] = "fileset_dump.txt";
  char typeset_path[] = "typeset_dump.txt";
  ofstream fileset, typeset;
  fileset.open(fileset_path);
  typeset.open(typeset_path);

	//instead of doing this, the memory_pool array can keep track of cumulative bytes

	for(int i = 0; i < memory_pool.size(); i++){
		total_byte_count += memory_pool[i].buffer_size_nbytes;
		write(global_fd, memory_pool[i].allocation_log, memory_pool[i].buffer_size_nbytes);
	}

  for(auto const& i:globalFiles) {
    fileset << (void*)i << "|" << i << endl;
  }

  for(auto const& i:globalTypes) {
    typeset << (void*)i << "|" << abi::__cxa_demangle(i, 0, 0, &status) << endl;
  }

  fileset.close();
  typeset.close();
}
/*
memhook_memory_pool::~memhook_memory_pool(){

  printf("memory_pool Destructor \n");
  ofstream dump_file;

  dump_file.open("debug_dump.txt");
  //really nasty, just used to get functionality restored will disappear after optimization
  for(int i = 0; i < memory_pool.size(); i ++){
    for(int j = 0; j < memory_pool[i].number_of_buffers; j++){
      for(int k = 0; k < MAX_BUFFER_SIZE;k++){
      	if(memory_pool[i].allocation_log[j][k].timestamp > 0){
         dump_file << memory_pool[i].allocation_log[j][k].timestamp << "|" << memory_pool[i].allocation_log[j][k].size << "|" << memory_pool[i].allocation_log[j][k].addr << "|" << memory_pool[i].allocation_log[j][k].typeofop << endl;
        }else {
        	break;
        }  
      }
    }
  }
}*/

//max buffer size is already known
void memhook_memory_pool::add(info_t *logarray, int buffer_size_nbytes){

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

  for(auto const& i : threadFiles) {
    globalFiles.insert(i);
  }

  for(auto const& i : typeFiles) {
    globalTypes.insert(i);
  }

  pthread_mutex_unlock(&lock);
}

memhook_memory_pool mem_pool_obj;

class ThreadExiter
  {
    public:
    //ThreadExiter() = default;
   
    // ThreadExiter(ThreadExiter const&) = delete;
    
    //void operator=(ThreadExiter const&) = delete;
    
    ThreadExiter(){
      printf("ThreadExiter Constructor has been called - v2\n");
    }
    ~ThreadExiter()
    {
      printf("ThreadExiter Destructor has been called - v2\n");

      int next_buffer = (buffer_index + 1) % 2;

      if(async_struct_array) {
        if(aio_error(&async_struct_array[buffer_index]) == EINPROGRESS){
          async_api_struct_list[0] = &async_struct_array[next_buffer];

          aio_suspend(async_api_struct_list,1,0);
        }

        int unfilled_buffer_size = sizeof(struct info_t)* log_index;
        //ADD FILE AND TYPES TO MEMPOOL OBJECT
        mem_pool_obj.add(allocation_log[buffer_index], unfilled_buffer_size);
      }
      //close(fd);
    }
    void add()
    {

    }
  };

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

int get_slot(thread::id id);
void insert_type(void *p, const MemStamp &stamp, const type_index);
void insert_info(size_t size, void* ptr, type_index tindex);

void   (memhook_free)(void *ptr, bool log);
void *memhook_malloc(size_t size, char* file, int line, bool log);

#warning This binary is being compiled with memhook. Running it will produce a text file (info_t_dump.txt) that should be provided as an argument to the shell script for step3.

void   (*next_free)(void *ptr);
void * (*next_malloc)(size_t size);
void * (*next_calloc)(size_t nmemb, size_t size);

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
thread_local info_t* myArray = nullptr;
thread_local int max_retry = 0;

ostream& operator << (ostream& os, info_t& info);

MemStamp::MemStamp(char const *filename, int lineNum)
    : filename(filename), lineNum(lineNum) { }
MemStamp::~MemStamp() { }

MemStampCollector::MemStampCollector() {
  
}

MemStampCollector::~MemStampCollector() {
  
}
void MemStampCollector::copy(info_t &unit_log){
	if(thread_first_call) {
		allocation_log = (struct info_t **)next_malloc(sizeof(struct info_t*)*number_of_buffers);
        for(int i = 0; i < 2; i++){
            allocation_log[i] = (struct info_t*) next_malloc(sizeof(struct info_t)*MEMHOOK_MAX_BUFFER_SIZE);
        }

        // printf("%lu \n", sizeof(struct info_t));
        async_struct_array = (struct aiocb*)next_malloc(sizeof(struct aiocb)*number_of_buffers);
        async_api_struct_list = (struct aiocb **)next_malloc(sizeof(struct aiocb*)*1);

        //char file_path[] = "binary_dump.txt";
        //fd = open(file_path,O_WRONLY|O_APPEND|O_CREAT);

        thread_first_call = 0;
	}

    memcpy(&allocation_log[buffer_index][log_index], &unit_log, sizeof(info_t));
    log_index++;

    if(log_index == MEMHOOK_MAX_BUFFER_SIZE){
    	async_struct_array[buffer_index].aio_buf = allocation_log[buffer_index];
    	async_struct_array[buffer_index].aio_nbytes = sizeof(struct info_t)*MEMHOOK_MAX_BUFFER_SIZE;
    	async_struct_array[buffer_index].aio_fildes = global_fd;
    	async_struct_array[buffer_index].aio_offset = 0;
    	async_struct_array[buffer_index].aio_reqprio = 0;
    	async_struct_array[buffer_index].aio_sigevent.sigev_notify = SIGEV_NONE;

    	aio_write(&async_struct_array[buffer_index]);
    	aio_fsync(O_SYNC, &async_struct_array[buffer_index]);

      //NOT NEEDED
      // if(first_filled_buffer_status == 0){
      //   first_filled_buffer_status = 1;
      //   buffer_index = 1;
      //   log_index = 0;
      //   return;
      // }

    	buffer_index = (buffer_index + 1) % 2;
    	log_index = 0;

      if(aio_error(&async_struct_array[buffer_index]) == EINPROGRESS){
        async_api_struct_list[0] = &async_struct_array[buffer_index];
        int aio_error_code = aio_suspend(async_api_struct_list,1,0);

        if(aio_error_code == -1)
          printf("suspend returned -1\n");
      }
    }
}

MemStampCollector collector;

//Keeps the total number of concurrent threads
int arrayCount = 0;

thread_local bool setup = false;

thread_local ThreadExiter exiter;
#endif