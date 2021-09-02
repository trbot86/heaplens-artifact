CC = g++
#clang++-6.0

all: test.o byte_reader
	$(CC) -Wall -g -o bin test.o -L../../memhook/ -Wl,-rpath=../../memhook/ -I../../memhook/ -lpthread -lmemhook -ldl

byte_reader: byte_rw.cpp
	$(CC) byte_rw.cpp -g -o byte_rw.bin

stack: stack.o
	$(CC) -Wall -g -pthread -o bin stack.o -L../../memhook/ -Wl,-rpath=../../memhook/ -I../../memhook/ -lmemhook -ldl

thread_test: test.o a.o
	$(CC) -Wall -g -pthread -o bin test.o a.o -L../../memhook/ -Wl,-rpath=../../memhook/ -I../../memhook/ -lmemhook -ldl

stack.o: stack.cpp
	$(CC) -Wall -pthread -c -g -mrdrnd stack.cpp -I../../memhook/

test.o: test.c
	$(CC) -c -g test.c -I../../memhook/ -pthread
a.o: a.cpp a.h
	$(CC) -c -g a.cpp -I../../memhook/

preprocessor:
	$(CC) -E test.cpp -I../../memhook/ > preprocessor_output.cpp

clean:
	rm bin test.o a.o compile_commands.json info_t_dump.txt preprocessor_output.cpp binary_dump.txt info_dump byte_rw.bin
