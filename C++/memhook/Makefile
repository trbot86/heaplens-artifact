CC=g++
Includes= /usr/lib/llvm-6.0/include/
Libs=

all:
	$(CC) memhook.cpp -shared -fPIC -g -o libmemhook.so

link:
	$(CC) memhook.cpp memalloc.cpp -pthread -Wall -g -o b.out

install:
	cp libmemhook.so ../lib/
	cp memhook.h ../include

clean:
	rm libmemhook.so info_t_dump.txt