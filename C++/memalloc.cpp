#include <iostream>
#include <bits/stdc++.h>
#include <thread>
// #define new new (__FILE__,__LINE__,__FUNCTION__)
using namespace std;

void alloc1(void) {
    // for(int i = 0;i < 1001;i++)
    int* n = new int(4);
}

void alloc2(void) {
    unsigned long* p = new unsigned long(6);
}

int main() {
    string* s = new string;
    int* n = new int(6);
    thread t1(alloc1);
    thread t2(alloc2);

    // delete(s);
    t1.join();
    t2.join();
    return 0;
}