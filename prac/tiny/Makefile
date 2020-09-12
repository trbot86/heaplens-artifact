CC = clang++-6.0

all: test.o a.o
	$(CC) -Wall -g -o bin test.o a.o -L../../memhook/ -Wl,-rpath=../../memhook/ -I../../memhook/ -lmemhook -ldl

test.o: test.cpp a.h
	$(CC) -c test.cpp -I../../memhook/

a.o: a.cpp a.h
	$(CC) -c a.cpp -I../../memhook/

clean:
	rm bin test.o a.o compile_commands.json info_t_dump.txt