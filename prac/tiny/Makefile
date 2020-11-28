CC = clang++-6.0

all: test.o a.o d.o
	$(CC) -Wall -g -o bin test.o a.o d.o -L../../memhook/ -Wl,-rpath=../../memhook/ -I../../memhook/ -lmemhook -ldl

stack: test.o a.o
	$(CC) -Wall -g -lpthread -o bin test.o a.o -L../../memhook/ -Wl,-rpath=../../memhook/ -I../../memhook/ -lmemhook -ldl

thread_test: test.o a.o
	$(CC) -Wall -g -lpthread -o bin test.o a.o -L../../memhook/ -Wl,-rpath=../../memhook/ -I../../memhook/ -lmemhook -ldl

test.o: test.cpp a.h
	$(CC) -pthread -c -g test.cpp -I../../memhook/
a.o: a.cpp a.h
	$(CC) -c -g a.cpp -I../../memhook/

preprocessor:
	$(CC) -E test.cpp -I../../memhook/ > preprocessor_output.cpp

clean:
	rm bin *.o *.tmp compile_commands.json info_t_dump.txt preprocessor_output.cpp
