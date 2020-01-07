#include <stdio.h>
#include <stdlib.h>

typedef struct node{
	struct node * l, * r;
	int value;
} node;

void in(node * n);
void pre(node * n);
void post(node * n);
node * new(int value);
void insert(node ** root, node * child);
node * search(node * root, int value);
void searchByPointer(node * root, int value, node ** save);