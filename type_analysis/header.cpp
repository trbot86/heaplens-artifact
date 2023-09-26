// ****************************************************************
// This file is a sample file to test the limits of the tool in C++
// ****************************************************************

// #include <iostream>
#include <stdlib.h>
#include "mm_malloc.h"
#include "header.h"
#include "memhook_interface.h"
// #include <string>
// #include <bits/stdc++.h>
// using namespace std;

// template <typename T>
// T* malloc(size_t size) {
//   cout << "templated malloc\n";
//   return (T*)malloc(size);
// }

template < typename T, typename Y=int>
class MyClass
{
public:
  int a;
  Y j;
  bool b;
  bool c;
  T field;
  // bool d;
  // int e;
  // bool f;
  // long long arr[100];
  T g;
};

// #define CLASS myClass<int>

// template < typename T>
// class newclass {
//   int h;
//   struct myStruct {
//     T x;
//     long long l;
//   };

//   myStruct y;
// };

// class A {
//   public:
//   bool x;
//   int a;
//   int b;
//   bool c;
//   bool d;
//   long l;
// };

// template <typename T>
// float* func() {
  // T* t = new T;
// }

class Column {
  int j;
};

class myconstructor {
  int m;
  public:
  myconstructor(int m = -1): m(m) {
    std::cout << "m allocated" << std::endl;
  }
};

int main() {
  // int a = 0;
  // int b = 24;
  // MyClass<int> mc;
  // MyClass<A, newclass<newclass<newclass<A>>>> random;
  // MyClass<double> md;
  // mc.field = new int;
  // int f;
  // f = (unsigned long long)5;double
  // int a = (int)f;
  int* r;
  struj sjj;

  int * t = (int*)malloc(sizeof(int));

  r = (int*)malloc(100*sizeof(int));

  int* s = (int*)malloc(100);
  // struj* z = (struj *)malloc_s(sizeof(sjj.stj));

  auto _latch = (pthread_mutex_t *) _mm_malloc<pthread_mutex_t, 96, MACRO_GET_STR("header.cpp")>(sizeof(pthread_mutex_t), 64);
  int field_cnt = 6;
  auto columns = new Column [field_cnt];
  delete columns;

  // t += 0x5;
  // printf("%d", t);
  // float* g = (float*)func();

  // A* a = new class A;
  // MyClass<float>* mclass = (MyClass<float>*)malloc<MyClass<float>>(8);
  MyClass<float>* mc2 = new MyClass<float>;

  mem_alloc m;
  m.alloc<char, 110, MACRO_GET_STR("header.cpp")>(sizeof(char));
  int queries[10];
  new(&queries[5]) myconstructor(7);
  // newclass<float>* n = new newclass<float>;
  // n.x = 0;
  // MyClass<int>* mc2 = new MyClass<int>;
  // CLASS* arr = new CLASS;
  // MyClass<long>* mc2 = new MyClass<long>;
  // char* arr = new char[10];
  // string* p = new (arr) string("hi");
  // int* str = (int*)(operator new (sizeof(string)));
  // malloc(sizeof(int));
  // delete mc2;
  // delete mc.field;
  // delete ([]{return new int; })();
  return 0;
}