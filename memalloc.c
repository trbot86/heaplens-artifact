#include <stdio.h>
#include <stdlib.h>
#include "btree.h"
#include <time.h>

#define TEST_NUMBER 10

int main() {
	int test, c, success;
	test = c = success = 0;

	node * root = NULL;

    srand(time(NULL));
	// INSERTION TEST 

	while(c++ < TEST_NUMBER)
		insert(&root, new(rand() % 150));	

	// PRINT TEST

	printf("\n > IN ORDER -> ");
	in(root);

	printf("\n\n > PRE ORDER -> ");
	pre(root);

	printf("\n\n > POST ORDER -> ");
	post(root);

	// SEARCH TEST

	puts("\n\n > TEST SEARCH:");

	while(test++ < TEST_NUMBER)
		if(search(root, test) > 0){
	 		printf("  - %d\n", test);
	 		success++;
		}

	printf("\n <SUCCESS> = %d <FAILED> = %d\n", success, TEST_NUMBER - success);
    return 0;
}