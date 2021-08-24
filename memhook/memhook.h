// mention Curtis Bartley
#ifndef __MEMHOOK_H
#define __MEMHOOK_H
// #pragma once

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

#define MEMHOOK_BACKTRACE_DEPTH 2
#ifndef MEMHOOK_MAX_THREADS
    #define MEMHOOK_MAX_THREADS 8
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
typedef map<const char*, const char*> type_map;
typedef set<const char*> filenameset;

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

thread_local int fd;

int global_fd;

struct thread_record_array{
  int buffer_size_nbytes;
  struct info_t *allocation_log;
};

struct info_t {
    const char* file;
    type_index tindex;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;
    //char padding[PADDING];

    info_t() : file(nullptr), tindex(typeid(void)), line(0), timestamp(0), size(0), addr(nullptr) {}
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
	int total_byte_count = 0;

	//confirm this method works with trevor
	struct thread_record_array * destructor_mem_array = &memory_pool[0];

	char file_path[] = "binary_dump.txt";
  //fd = open(file_path,O_WRONLY|O_APPEND|O_CREAT);

	//instead of doing this, the memory_pool array can keep track of cumulative bytes

	for(int i = 0; i < memory_pool.size(); i++){
		total_byte_count += memory_pool[i].buffer_size_nbytes;
		write(global_fd, memory_pool[i].allocation_log, memory_pool[i].buffer_size_nbytes);
	}
  //close(fd);
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

  printf("within mem_pool add \n");
  this->memory_pool.push_back(thread_record_array());
  memory_pool[memory_pool.size() - 1].allocation_log = logarray;
  memory_pool[memory_pool.size() - 1].buffer_size_nbytes = buffer_size_nbytes;

  pthread_mutex_unlock(&lock);
}

/*
After some further refactoring we might be able to remove this class declaration from memhook.h
*/
class MemStamp
{
    public:
        char const * const filename;
        int const lineNum;
    public:
        MemStamp(char const *filename, int lineNum);
        ~MemStamp();
};

class MemStampCollector {
private:
    slot* sarr;
    info_t* allArrays;

    int get_slot(thread::id id);

public:
    MemStampCollector();

    ~MemStampCollector();

    void add(uint64_t timestamp, size_t size, void * addr, bool typeofop);
    void update(const char * file, unsigned int line, type_index tindex);
    void threadexit();
};

inline uint64_t memhook_get_server_clock() {
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

type_map tmap;
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

MemStamp::MemStamp(char const *filename, int lineNum)
    : filename(filename), lineNum(lineNum) { }
MemStamp::~MemStamp() { }
/*
struct info_t {
    const char* file;
    type_index tindex;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;
    // char padding[PADDING];

    info_t() : file(nullptr), tindex(typeid(void)), line(0), timestamp(0), size(0), addr(nullptr) {}
};*/

thread_local int iter = 0;

/*Iterator for individual thread allocation in
* tracking data structure
*/

thread_local int it = 0;
thread_local info_t* myArray = nullptr;
thread_local int max_retry = 0;

ostream& operator << (ostream& os, info_t& info);

int MemStampCollector::get_slot(thread::id id) {
  max_retry = 0;
  while(max_retry < MEMHOOK_MAX_RETRY) {
    while(sarr[iter].occupied && (max_retry < MEMHOOK_MAX_RETRY)) {
      // cout << "while" << endl;
      iter = (iter+1)%MEMHOOK_MAX_THREADS;
      max_retry++;
    }
    
    if(__sync_bool_compare_and_swap(&sarr[iter].occupied, false, true)) {
      // cout << iter << endl;
      sarr[iter].id = id;
      it = sarr[iter].offset;
      return iter;
    }
    // cout << "failed\n";
    iter = (iter+1)%MEMHOOK_MAX_THREADS;
    max_retry++;
  }
  return -1;
}


MemStampCollector::MemStampCollector() {
  allArrays = (info_t*)next_calloc(1, MEMHOOK_MAX_THREADS*MEMHOOK_MAX_TRACK*sizeof(info_t));

  if(allArrays == NULL) {
    printf("[Integer overflow]: either calloc failed or integer overflow. reduce MEMHOOK_MAX_TRACK or MEMHOOK_MAX_THREADS\n");
    exit(0);
  }

  sarr = (slot*)next_calloc(1, MEMHOOK_MAX_THREADS*sizeof(slot));

  if(sarr == NULL) {
    printf("[Integer Overflow]: either calloc failed or integer overflow. reduce MAX_THREADS\n");
  }
}

MemStampCollector::~MemStampCollector() {
  //printf("old memstamp collector destructor, empty for now \n");
  //commented out because we don't want double data to be printed
  /*it = INT_MAX;
  ofstream myfile("info_t_dump.txt", ios_base::out | ios_base::app);

  int status;
  char *demangled_name;

  for (int i = 0; i < MEMHOOK_MAX_TRACK * MEMHOOK_MAX_THREADS; i++)
  {
    if (allArrays[i].addr == nullptr)
      continue;
    else if (allArrays[i].file && allArrays[i].typeofop && !tmap.count(allArrays[i].tindex.name()))
    {
      demangled_name = abi::__cxa_demangle(allArrays[i].tindex.name(), 0, 0, &status);
      tmap[allArrays[i].tindex.name()] = demangled_name;
    }

    myfile << allArrays[i];
  }*/
}
void MemStampCollector::add(uint64_t timestamp, size_t size, void *addr, bool typeofop){
	if(thread_first_call){
		allocation_log = (struct info_t **)next_malloc(sizeof(struct info_t*)*number_of_buffers);
        for(int i = 0; i < 2; i++){
            allocation_log[i] = (struct info_t*) next_malloc(sizeof(struct info_t)*MEMHOOK_MAX_BUFFER_SIZE);
        }

        printf("%lu \n", sizeof(struct info_t));
        async_struct_array = (struct aiocb*)next_malloc(sizeof(struct aiocb)*number_of_buffers);
        async_api_struct_list = (struct aiocb **)next_malloc(sizeof(struct aiocb*)*1);

        //char file_path[] = "binary_dump.txt";
        //fd = open(file_path,O_WRONLY|O_APPEND|O_CREAT);

        thread_first_call = 0;
	}

	  allocation_log[buffer_index][log_index].timestamp = memhook_get_server_clock();
    allocation_log[buffer_index][log_index].size = size;
    allocation_log[buffer_index][log_index].addr = addr;
    allocation_log[buffer_index][log_index].typeofop = typeofop;
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

      if(first_filled_buffer_status == 0){
        first_filled_buffer_status = 1;
        buffer_index = 1;
        log_index = 0;
        return;
      }

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
void MemStampCollector::update(const char * file, unsigned int line, type_index tindex) {
    myArray[it-1].file = file;
    myArray[it-1].line = line;
    myArray[it-1].tindex = tindex;
}

void MemStampCollector::threadexit() {
    sarr[iter].offset = it++;
    __sync_bool_compare_and_swap(&sarr[iter].occupied, true, false);
}

MemStampCollector collector;

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
      printf("ThreadExiter Destructor has been called \n");

      int next_buffer = (buffer_index + 1) % 2;

      if(aio_error(&async_struct_array[next_buffer]) == EINPROGRESS){
        async_api_struct_list[0] = &async_struct_array[next_buffer];

        aio_suspend(async_api_struct_list,1,0);
      }

      int unfilled_buffer_size = sizeof(struct info_t)* log_index;
      mem_pool_obj.add(allocation_log[buffer_index], unfilled_buffer_size);
      //close(fd);
    }
    void add()
    {

    }
  };

//Keeps the total number of concurrent threads
int arrayCount = 0;

thread_local bool setup = false;

filenameset fset;

thread_local ThreadExiter exiter;
#endif