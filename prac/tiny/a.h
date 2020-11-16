#include "memhook_interface.h"
// #define _GNU_SOURCE
#ifndef A_H
#define A_H

#include <iostream>
#include <stdlib.h>
#include <stdio.h>
#include <dlfcn.h>

int* foo ();
int* foobar ();

/*
int* aprilfool() {
	int* p = (int*)malloc(sizeof(int));
	return p;
}
*/
#endif
