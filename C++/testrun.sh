(cd type_analysis && make refactor)
./type_analysis/refactor $1 > $2
g++ $2 memhook.cpp -pthread -Wall -g -o a.out
./a.out | grep "templated malloc"