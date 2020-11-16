CC = clang++-6.0

all: test.o a.o d.o
	$(CC) -Wall -g -o bin test.o a.o d.o -L../../memhook/ -Wl,-rpath=../../memhook/ -I../../memhook/ -lmemhook -ldl

test.o: test.cpp
	$(CC) -c -g test.cpp -I../../memhook/

d.o: d.cpp
	$(CC) -c -g d.cpp -I../../memhook/

# b.o: b.cpp
# 	$(CC) -c -g b.cpp -I../../memhook/

a.o: a.cpp b.cpp
	$(CC) -c -g a.cpp b.cpp -I../../memhook/

preprocessor:
	$(CC) -E test.cpp -I../../memhook/ > preprocessor_output.cpp

clean:
	rm bin *.o *.tmp compile_commands.json info_t_dump.txt preprocessor_output.cpp
