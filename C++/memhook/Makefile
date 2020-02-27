CC=g++
Includes= /usr/lib/llvm-6.0/include/
Libs=

all:
	$(CC) memhook.cpp -shared -fPIC -g -o libmemhook.so

link:
	$(CC) memhook.cpp memalloc.cpp -pthread -Wall -g -o b.out

prac:
	$(CC) a.cpp -I./ -L./ -Wl,-rpath=./ -pthread -lmemhook -g -o a.out

install:
	cp libmemhook.so ../prac/setbench-master/lib
	cp memhook.h ../prac/setbench-master/microbench

clean:
	rm libmemhook.so info_t_dump.txt
