CC=gcc

a.out: memalloc.o btree.o malloc_custom.so
	$(CC) memalloc.o btree.o -g -o a.out

memalloc.o: memalloc.c
	$(CC) -g -c memalloc.c

btree.o: btree.c btree.h
	$(CC) -g -c btree.c

malloc_custom.so: malloc_custom.c
	$(CC) -Wall -shared -fPIC malloc_custom.c -g -o mallocc.so -ldl

clean:
	rm malloc_custom.so a.out btree.o memalloc.o