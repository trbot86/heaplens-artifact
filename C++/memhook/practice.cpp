#include <iostream>
#include <thread>
#include <string>
#include <atomic>
#include <cstdlib>
#include <chrono>
#include <unistd.h>
#include <typeindex>
#include <experimental/source_location>
#include <execinfo.h>
#include <cxxabi.h>
#include <bits/stdc++.h>

#define MAX_THREADS 3
#define MAX_ALLOCS 1000
#define PADDING_BYTES 64

using namespace std;

struct info_t {
    string file;
    string type_name;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
};

struct slot {
	volatile bool occupied;
	thread::id id;
	int offset;
};

class ThreadExiter
  {
  public:
    int a;
    ThreadExiter() {
      cout << "thread Exiter ctor\n";
    }

    ThreadExiter(ThreadExiter const&) = delete;
    void operator=(ThreadExiter const&) = delete;
    ~ThreadExiter()
    {
      cout << "Destructor called\n";
    }
    void add()
    {
      // exit_funcs.push(std::move(func));
    }   
  };

thread_local ThreadExiter te;
info_t info[MAX_THREADS*MAX_ALLOCS];
thread_local int iter = 0;
slot sarr[MAX_THREADS];

atomic<info_t*> current_offset(info);

thread_local int offset;

__attribute__ ((constructor)) void setup();

void onexit(void* arg) {
  cout << "thread exit\n";
}

void setup() {
  // exiter.add();
}

void cleanup() {
	sleep(2);
	sarr[iter].occupied = false;
}

int get_slot(thread::id id) {
	while(true) {
		while(sarr[iter].occupied) {
			// cout << "while" << endl;
			iter = (iter+1)%MAX_THREADS;
		}
		
		if(__sync_bool_compare_and_swap(&sarr[iter].occupied, false, true)) {
			cout << iter << endl;
			sarr[iter].id = id;
			return sarr[iter].offset;
		}
		cout << "failed\n";
		iter = (iter+1)%MAX_THREADS;
	}
}

void spawn_thread() {
	// exiter.add();
  // pthread_cleanup_push(cleanup, nullptr);
	// function<void()> f = cleanup;
	// on_thread_exit(f);
	// get_slot(this_thread::get_id());
	// pthread_cleanup_pop(true);
   __cxxabiv1::__cxa_thread_atexit(onexit,nullptr,);
}

int main() {
// thread_local unique_ptr<ThreadExiter> te (new ThreadExiter()) ;
// for(int i = 0;i < 10;i++) {
// 	thread t(spawn_thread);
// 	// t.join();
// }

// delete te;
thread t1(spawn_thread);
// thread t2(spawn_thread);
// thread t3(spawn_thread);
// thread t4(spawn_thread);
// thread t5(spawn_thread);

t1.join();
// t2.join();
// t3.join();
// t4.join();
// t5.join();

return 0;
}