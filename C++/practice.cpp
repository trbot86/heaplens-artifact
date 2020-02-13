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

#define MAX_THREADS 5
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
	bool occupied;
	thread::id id;
	int offset;
};

info_t info[MAX_THREADS*MAX_ALLOCS];
thread_local int iter = 0;
slot sarr[MAX_THREADS];

__attribute__ ((destructor)) void cleanup();

void cleanup() {
	sarr[iter].occupied = false;
}

int get_slot(thread::id id) {
	bool desired = false;
	while(true) {
		while(sarr[iter].occupied) iter = (iter+1)%MAX_THREADS;
		if(__sync_bool_compare_and_swap(&sarr[iter].occupied, false, true)) {
			cout << iter << endl;
			sarr[iter].id = id;
			return sarr[iter].offset;
		}
		iter = (iter+1)%MAX_THREADS;
	}
	// sleep(5);
}

void init_info(info_t *i) {
	auto thread_local start = chrono::high_resolution_clock::now();
	for(int k = 0;k < 10000;k++) {
		
	}
	auto thread_local end = chrono::high_resolution_clock::now();
	cout << chrono::duration_cast<chrono::microseconds>(end - start).count() << endl;
}

atomic<info_t*> current_offset(info);

thread_local int offset;

void spawn_thread() {
	thread t(get_slot, t.get_id());
	t.join();
}

int main() {

for(int i = 0;i < 10;i++) {
	spawn_thread();
}

// chrono::high_resolution_clock::now();

// ifstream is("info_t_dump.txt", ios_base::in);
// info_t inf;

// getline(is, inf.file, '\0');
// cout << inf.file << endl;
// cout << inf.type_name << endl;
return 0;
}