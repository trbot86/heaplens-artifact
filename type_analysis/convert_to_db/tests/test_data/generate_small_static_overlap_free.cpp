#include "memhook_interface.h"
#include "sampler_test_paths.h"
#include <iostream>
#include <fstream>

#define NUM_BLOCKS 10
#define SIZE_BLOCK 50
#define NUM_NESTED 5

int main() {
    char* blocks[NUM_BLOCKS];

    for (int i = 0; i < NUM_BLOCKS; i++) {
        blocks[i] = (char*) malloc<char, __LINE__, 0>(SIZE_BLOCK*sizeof(char));
        for (int j = 0; j < NUM_NESTED; j++) {
            MemStamp(0, __LINE__) * (int*) new (blocks[i] + (j*sizeof(int))) int{j};
        }
        // Following long allocation overlaps the first three int allocations in this block
        MemStamp(0, __LINE__) * (long*) new (blocks[i] + sizeof(char)) long{i};
    }

    delete blocks[1];

    size_t num_int_overlapped = (sizeof(long) / sizeof(int)) + 1;
    std::ofstream ans_file;
    ans_file.open(TEST_DATA_DIR "generate_small_static_overlap_free.ans");
    ans_file << "char " << NUM_BLOCKS << " " << NUM_BLOCKS*SIZE_BLOCK*sizeof(char) << " alloc" << std::endl;
    ans_file << "char " << 1 << " " << SIZE_BLOCK*sizeof(char) << " free" << std::endl;
    ans_file << "int " << NUM_BLOCKS*NUM_NESTED << " " << NUM_BLOCKS*NUM_NESTED*sizeof(int) << " alloc" << std::endl;
    ans_file << "int " << NUM_NESTED + (num_int_overlapped * (NUM_BLOCKS-1)) << " "
            << (NUM_NESTED + (num_int_overlapped * (NUM_BLOCKS-1)))*sizeof(int) << " free" << std::endl;
    ans_file << "long " << NUM_BLOCKS << " " << NUM_BLOCKS*sizeof(long) << " alloc" << std::endl;
    ans_file << "long " << 1 << " " << sizeof(long) << " free" << std::endl;
    ans_file.close();
}