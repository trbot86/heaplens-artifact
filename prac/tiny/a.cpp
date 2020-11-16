#include "memhook_interface.h"
// #pragma once
#include <iostream>	
#include <stdlib.h>
#include <dlfcn.h>

#include "a.h"

int* foo() {
    int* ret = (int*)malloc(sizeof(int));
    int* p;
    
    if(true) {
    	if(ret) {
    		std::cout << "fjjgj";
    		*ret = 5;
    	}
    }
    else {
    
    }
    return ret;
}

int* foobar() {
	for(int i = 0;i < 100;i++)
    int* ptr = (int*)malloc<int*>(100*sizeof(int));
	return nullptr;
}
