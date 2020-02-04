#include <iostream>
#include <bits/stdc++.h>
#include <thread>

using namespace std;



struct algo {
    int a;
    int b;
};

void alloc1(void) {
    for(int i = 0;i < 1001;i++)
    int* n = new int(4);
}

void alloc2(void) {
    unsigned long* p = new unsigned long(6);
}

int main() {
    string* s = new string;
    algo* al;
    al = (algo*)malloc(sizeof(algo));
    return 0;
}