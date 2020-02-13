#include <iostream>
#include <bits/stdc++.h>
#include <thread>

#include "memhook.h"

using namespace std;

struct algo {
    int a;
    int b;
};

void alloc1(void) {
    // for(int i = 0;i < 1;i++)
    int* n = new int(4);
}

void alloc2(void) {
    unsigned long* p = new unsigned long(6);
}

int main() {
    // thread t1(alloc1);
    // thread t2(alloc2);
// unsigned long* p = new unsigned long(6);
    // t1.join();
    // t2.join();

    malloc<int*>(sizeof(int));

    // dumpentirestatstofile("info_t_dump.txt");
    return 0;
}