// mention Curtis Bartley
#pragma once

#include "memhook_extern.h"

// #warning This binary is being compiled with memhook. Running it will produce a text file that should be provided as an argument to the shell script for step3.

struct slot {
	volatile bool occupied;
	thread::id id;
	int offset;
  char padding[128];
};

// class MemStamp
// {
//     public:
//         char const * const filename;
//         int const lineNum;
//     public:
//         MemStamp(char const *filename, int lineNum)
//             : filename(filename), lineNum(lineNum) { }
//         ~MemStamp() { }
// };

MemStamp::MemStamp(char const *filename, int lineNum)
    : filename(filename), lineNum(lineNum) { }
MemStamp::~MemStamp() { }

struct info_t {
    const char* file;
    type_index tindex;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;
    char padding[PADDING];

    info_t() : file(nullptr), tindex(typeid(void)), line(0), timestamp(0), size(0), addr(nullptr) {}
};

thread_local int iter = 0;

/*Iterator for individual thread allocation in
* tracking data structure
*/

thread_local int it;
thread_local info_t* myArray = nullptr;

// class MemStampCollector {
// private:
//     slot* sarr;
//     info_t* allArrays;

//     int get_slot(thread::id id) {
//       while(true) {
//         while(sarr[iter].occupied) {
//           // cout << "while" << endl;
//           iter = (iter+1)%MAX_THREADS;
//         }
        
//         if(__sync_bool_compare_and_swap(&sarr[iter].occupied, false, true)) {
//           // cout << iter << endl;
//           sarr[iter].id = id;
//           it = sarr[iter].offset;
//           return iter;
//         }
//         // cout << "failed\n";
//         iter = (iter+1)%MAX_THREADS;
//       }
//     }

// public:
//     MemStampCollector() {
//       allArrays = (info_t*)next_calloc(1, MAX_THREADS*MAX_TRACK*sizeof(info_t));
//       sarr = (slot*)next_calloc(1, MAX_THREADS*sizeof(slot));
//     }

//     ~MemStampCollector() {
//       it = INT_MAX;
//       ofstream myfile("info_t_dump.txt", ios_base::out | ios_base::app);

//       int status;
//       char *demangled_name;

//       for (int i = 0; i < MAX_TRACK * MAX_THREADS; i++)
//       {
//         if (allArrays[i].addr == nullptr)
//           continue;
//         else if (allArrays[i].file && allArrays[i].typeofop && !tmap.count(allArrays[i].tindex))
//         {
//           demangled_name = abi::__cxa_demangle(allArrays[i].tindex.name(), 0, 0, &status);
//           tmap[allArrays[i].tindex] = demangled_name;
//         }

//         myfile << allArrays[i];
//       }
//     }

//     void add(uint64_t timestamp, size_t size, void * addr, bool typeofop) {
//       if(myArray == nullptr) {
//         int result = get_slot(this_thread::get_id());
//         it = sarr[result].offset;
//         myArray = allArrays + MAX_TRACK*result;
//       }
      
//       if(it < MAX_TRACK) {
//         myArray[it].timestamp = get_server_clock();
//         myArray[it].size = size;
//         myArray[it].addr = addr;
//         myArray[it].typeofop = typeofop;
//         it++;
//       }
//     }

//     void update(const char * file, unsigned int line, type_index tindex) {      
//         myArray[it-1].file = file;
//         myArray[it-1].line = line;
//         myArray[it-1].tindex = tindex;
//     }
// };

ostream& operator << (ostream& os, info_t& info);

int MemStampCollector::get_slot(thread::id id) {
  while(true) {
    while(sarr[iter].occupied) {
      // cout << "while" << endl;
      iter = (iter+1)%MAX_THREADS;
    }
    
    if(__sync_bool_compare_and_swap(&sarr[iter].occupied, false, true)) {
      // cout << iter << endl;
      sarr[iter].id = id;
      it = sarr[iter].offset;
      return iter;
    }
    // cout << "failed\n";
    iter = (iter+1)%MAX_THREADS;
  }
}


MemStampCollector::MemStampCollector() {
  allArrays = (info_t*)next_calloc(1, MAX_THREADS*MAX_TRACK*sizeof(info_t));
  sarr = (slot*)next_calloc(1, MAX_THREADS*sizeof(slot));
}

MemStampCollector::~MemStampCollector() {
  it = INT_MAX;
  ofstream myfile("info_t_dump.txt", ios_base::out | ios_base::app);

  int status;
  char *demangled_name;

  for (int i = 0; i < MAX_TRACK * MAX_THREADS; i++)
  {
    if (allArrays[i].addr == nullptr)
      continue;
    else if (allArrays[i].file && allArrays[i].typeofop && !tmap.count(allArrays[i].tindex))
    {
      demangled_name = abi::__cxa_demangle(allArrays[i].tindex.name(), 0, 0, &status);
      tmap[allArrays[i].tindex] = demangled_name;
    }

    myfile << allArrays[i];
  }
}

void MemStampCollector::add(uint64_t timestamp, size_t size, void * addr, bool typeofop) {
  if(myArray == nullptr) {
    int result = get_slot(this_thread::get_id());
    it = sarr[result].offset;
    myArray = allArrays + MAX_TRACK*result;
  }
  
  if(it < MAX_TRACK) {
    myArray[it].timestamp = get_server_clock();
    myArray[it].size = size;
    myArray[it].addr = addr;
    myArray[it].typeofop = typeofop;
    it++;
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

class ThreadExiter
  {
    // std::stack<std::function<void()>> exit_fun
    public:
    ThreadExiter() = default;
    
    ThreadExiter(ThreadExiter const&) = delete;
    
    void operator=(ThreadExiter const&) = delete;
    
    ~ThreadExiter()
    {
      // while(!exit_funcs.empty())
      // {
      //   exit_funcs.top()();
      //   exit_funcs.pop();
      // }
      // cout << "ThreadExiter dtor\n";
      collector.threadexit();
      // sarr[iter].occupied = false;
    }
    void add()
    {
      // exit_funcs.push(std::move(func));
    }
  };

//Keeps the total number of concurrent threads
int arrayCount = 0;

thread_local bool setup = false;

type_map tmap;

filenameset fset;

thread_local ThreadExiter exiter;
