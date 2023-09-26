#ifndef __HEADER_H
#define __HEADER_H

#include "memhook_interface.h"

#ifdef __cplusplus
#include <bits/stdc++.h>
#endif

// template <typename T>
// T* malloc(size_t size) {
//   cout << "templated malloc\n";
//   return (T*)malloc(size);
// }

struct stru {
  int a;
  int b;
};

#ifdef __cplusplus

// extern thread_local info_t unit_log;
// extern thread_local unordered_set<const char*> threadFiles;
// extern thread_local unordered_set<const char*> typeFiles;

// extern memhook_hashtable filetable;
// extern memhook_hashtable typetable;

class mem_alloc {
  public:
  void* alloc(size_t size) {
    void* ptr;
    ptr = malloc(size);
    return ptr;
  }

  template <class T, int line, char... filename>
  T* alloc(size_t size) {
    void* ptr;
    std::string filestring = {filename...};

    unit_log.file = filetable.insert(filestring.c_str());
    unit_log.tindex_name = typetable.insert(typeid(T).name());

    ptr = memhook_malloc(size, unit_log.file, line, true);

    collector.copy(unit_log);

    return (T*)ptr;
  }
};

#endif

typedef struct {
  int ak;
  int soj;
  struct stru stj;
} struj;

void func (size_t mem, const size_t abcd) {
  int* r;
  struj* sjj;
  void* ptr, *ptr2 = NULL;
  int * t = (int*)malloc(sizeof(int));//

  r = (int*)malloc(100*sizeof(int));//
  ptr = malloc(mem);
  ptr2 = malloc(abcd);

  #ifdef __cplusplus
  mem_alloc m;
  m.alloc<char, 74, MACRO_GET_STR("/home/gspathak/sifter/type_analysis/header.h")>(sizeof(char));
  #endif
}

// template < typename T, typename Y=int>
// class MyClass
// {
// public:
//   int a;
//   Y j;
//   bool b;
//   bool c;
//   T field;
//   // bool d;
//   // int e;
//   // bool f;
//   // long long arr[100];
//   T g;
// };

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

#endif