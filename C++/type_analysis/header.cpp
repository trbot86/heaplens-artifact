#include <iostream>
#include <stdlib.h>
// #include <string>
// #include <bits/stdc++.h>
using namespace std;

template <typename T>
T* malloc(size_t size) {
  cout << "templated malloc\n";
  return (T*)malloc(size);
}

template < typename T, typename Y=int>
class MyClass
{
public:
  int a;
  Y j;
  // bool b;
  // bool c;
  // T field;
  // bool d;
  // int e;
  // bool f;
  // long long arr[100];
  T g;
};

#define CLASS myClass<int>

template < typename T>
class newclass {
  int h;
  struct myStruct {
    T x;
    long long l;
  };

  myStruct y;
};

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

int main() {
  // MyClass<int> mc;
  // MyClass<double> md;
  // mc.field = new int;
  // int f;
  // f = (unsigned long long)5;
  // int a = (int)f;
  // int* r = (int*)malloc(sizeof(int));
  // float* g = (float*)func();

  // A* a = new class A;
  // MyClass<float>* mclass = (MyClass<float>*)malloc<MyClass<float>>(8);
  // MyClass<float>* mc2 = new MyClass<float>;

  // newclass<float>* n = new newclass<float>;
  // n.x = 0;
  // MyClass<int>* mc2 = new MyClass<int>;
  CLASS* arr = new CLASS;
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