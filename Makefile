CC=gcc

a.out: memalloc.o btree.o mallocc.so
	$(CC) memalloc.o btree.o -g -o a.out

memalloc.o: memalloc.c
	$(CC) -g -c memalloc.c

btree.o: btree.c btree.h
	$(CC) -g -c btree.c

mallocc.so: maddress.c
	$(CC) -Wall -shared -fPIC maddress.c -g -o mallocc.so -ldl

clean:
	rm mallocc.so a.out btree.o memalloc.o