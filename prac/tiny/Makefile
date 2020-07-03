all:
	clang++ -g -o bin test.cpp -lmemhook -ldl -L../../memhook/ -Wl,-rpath=../../memhook/ -I../../memhook/
	./bin