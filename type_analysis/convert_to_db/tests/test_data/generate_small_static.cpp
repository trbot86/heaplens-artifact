#include "memhook_interface.h"
#include <iostream>
#include <fstream>

#define NUM_BLOCKS 10
#define SIZE_BLOCK 50
#define NUM_NESTED 5

int main() {
    char* blocks[NUM_BLOCKS];

    for (int i = 0; i < NUM_BLOCKS; i++) {
        blocks[i] = (char*) malloc<char, 7, MACRO_GET_STR("generate_small_static.cpp")>(SIZE_BLOCK*sizeof(char));
        for (int j = 0; j < NUM_NESTED; j++) {
            MemStamp(__FILE__, __LINE__) * (int*) new (blocks[i] + (j*sizeof(int))) int{j};
        }
    }

    delete blocks[1];

    std::ofstream ans_file;
    ans_file.open("generate_small_static.ans");
    ans_file << "char " << NUM_BLOCKS << " " << NUM_BLOCKS*SIZE_BLOCK*sizeof(char) << " alloc" << std::endl;
    ans_file << "char " << 1 << " " << SIZE_BLOCK*sizeof(char) << " free" << std::endl;
    ans_file << "int " << NUM_BLOCKS*NUM_NESTED << NUM_BLOCKS*NUM_NESTED*sizeof(int) << " alloc";
    ans_file << "int " << NUM_NESTED << NUM_NESTED*sizeof(int) << " free";
    ans_file.close();
}