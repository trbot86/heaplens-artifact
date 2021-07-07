CC = g++ 
#clang++-6.0

all: test.o
	$(CC) -Wall -g -o bin test.o -L../../memhook/ -Wl,-rpath=../../memhook/ -I../../memhook/ -lpthread -lmemhook -ldl

stack: stack.o
	$(CC) -Wall -g -pthread -o bin stack.o -L../../memhook/ -Wl,-rpath=../../memhook/ -I../../memhook/ -lmemhook -ldl

thread_test: test.o a.o
	$(CC) -Wall -g -pthread -o bin test.o a.o -L../../memhook/ -Wl,-rpath=../../memhook/ -I../../memhook/ -lmemhook -ldl

stack.o: stack.cpp
	$(CC) -Wall -pthread -c -g -mrdrnd stack.cpp -I../../memhook/

test.o: test.cpp
	$(CC) -c -g test.cpp -I../../memhook/ -pthread
a.o: a.cpp a.h
	$(CC) -c -g a.cpp -I../../memhook/

preprocessor:
	$(CC) -E test.cpp -I../../memhook/ > preprocessor_output.cpp

clean:
	rm bin test.o a.o compile_commands.json info_t_dump.txt preprocessor_output.cpp
