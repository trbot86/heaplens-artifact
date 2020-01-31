// #include <iostream>
#include <stdlib.h>
// #include <string>
// #include <bits/stdc++.h>
using namespace std;

// template <typename T>
// T* malloc(size_t size) {
//   return (T*)malloc(size);
// }

template < typename T>
class MyClass
{
public:
  T* field;
};

class A {
  public:
  int a;
};

template <typename T>
void func() {
  T* t = new T;
}

int main() {
  // MyClass<int> mc;
  // MyClass<double> md;
  // mc.field = new int;
  int* r = (int*)malloc(sizeof(int));
  // MyClass<int>* mc2 = new MyClass<int>;
  // char* arr = new char[10];
  // string* p = new (arr) string("hi");
  // int* str = (int*)(operator new (sizeof(string)));
  // malloc(sizeof(int));
  // delete mc2;
  // delete mc.field;
  // delete ([]{return new int; })();
}