#include <iostream>
#include <bits/stdc++.h>

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
  MyClass<int> mc;
  MyClass<double> md;
  // mc.field = new int;

  for(int i = 0;i < 10;i++) {
    ;
  }
}