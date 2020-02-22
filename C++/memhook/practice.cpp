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

const double M=8e8;

class Shared_Work {
public:
    Shared_Work():n1(1),n2(1),flag1(0),flag2(0) {}
 
    void part1() {
        for(; n1<M; n1+=n1%3);
        flag1=1;
        cond.notify_one();
    }
 
    void part2() {
        for(; n2<M; n2+=n2%3);
        flag2=1;
        cond.notify_one();
    }
 
    long int result() {
        std::unique_lock<std::mutex> lk(mt);
        while(flag1==0||flag2==0)
            cond.wait(lk);
        return n1+n2;
    }
 
private:
    std::mutex mt;
    std::condition_variable cond;
    long int n1;
    //char chuck[64];//cache line seperation
    long int n2;
    bool flag1;
    bool flag2;
};

template<class T>
class Do_Work {
public:
    typedef void (T::*action)();
    Do_Work(std::shared_ptr<Shared_Work>& x, action y):_p(x),_fptr(y) {}
    void operator()() {
        (*_p.*_fptr)();
    }
private:
    std::shared_ptr<Shared_Work> _p;
    action _fptr;
};
 
//single thread work to do
void one_thread() {
    long int n1=1, n2=1;
    for(; n1<M; n1+=n1%3);
    for(; n2<M; n2+=n2%3);
    cout<<n1+n2<<endl;
}
 
time_t start, en;
double diff;

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
thread_local int iter = 0;
slot sarr[MAX_THREADS];

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
    std::shared_ptr<Shared_Work> p(new Shared_Work);
    Do_Work<Shared_Work> d1(p, &Shared_Work::part1);
    Do_Work<Shared_Work> d2(p, &Shared_Work::part2);
 
    time(&start);
    std::thread t1( d1 );
    std::thread t2( d2 );
    t1.detach();//release the ownership to C++ runtime library.
    t2.detach();//release the ownership to C++ runtime library.
    cout<<p->result()<<endl;
    time(&en);
    diff=difftime(en, start);
    cout<<diff<<" seconds elapsed for 2 threads calculation."<<endl;
 
    time(&start);
    one_thread();
    time(&en);
    diff=difftime(en, start);
    cout<<diff<<" seconds elapsed for 1 thread calculation."<<endl;

return 0;
}