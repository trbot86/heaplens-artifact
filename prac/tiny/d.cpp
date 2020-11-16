#include "memhook_interface.h"
#include "d.h"

int* barfoo() {
	int* pointer = foo();
	int* pointer2 = foobar();
	
	int* pointer3 = (int*)malloc(sizeof(int));
	return pointer3;
}
