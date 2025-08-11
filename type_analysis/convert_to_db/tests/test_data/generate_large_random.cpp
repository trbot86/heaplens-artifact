#include "memhook_interface.h"
#include "sampler_test_paths.h"
#include <iostream>
#include <fstream>
#include <thread>
#include <random>
#include <mutex>

#define NUM_THREADS 8
#define NUM_BLOCKS_PER_THREAD 100000
#define SIZE_BLOCK 128

class Base {
public:
    virtual void print() const = 0;
};

#define CHAR_TYPE 0
class CharType : public Base {
private:
    char value;
public:
    CharType(char c) : value(c) {}

    void print() const override {
        std::cout << "char: " << value << std::endl;
    }
};

#define INT_TYPE 1
class IntType : public Base {
private:
    int value;
public:
    IntType(int v) : value(v) {}

    void print() const override {
        std::cout << "int: " << value << std::endl;
    }
};

#define LONG_TYPE 2
class LongType : public Base {
private:
    int value;
public:
    LongType(int l) : value(l) {}

    void print() const override {
        std::cout << "long: " << value << std::endl;
    }
};

typedef struct alloc_free {
    size_t alloc;
    size_t free;
} alloc_free_t;

void allocate_work(std::unordered_map<std::string, alloc_free_t>& type_counts,
                    std::unordered_map<std::string, alloc_free_t>& type_sizes,
                    std::mutex& print_m) {
    char* blocks[NUM_BLOCKS_PER_THREAD];
    std::mt19937 rng(std::random_device{}());
    std::uniform_int_distribution<int> type_dist(0, 2);
    std::uniform_int_distribution<int> inner_size_dist(2, ((SIZE_BLOCK * sizeof(char)) / sizeof(LongType)) - 1);

    for (int i = 0; i < NUM_BLOCKS_PER_THREAD; i++) {
        blocks[i] = (char*) malloc<char, __LINE__, 0>(SIZE_BLOCK * sizeof(char));
        // {
        //     std::unique_lock<std::mutex> lock{print_m};
        //     std::cout << "Thread " << std::this_thread::get_id();
        //     printf(": %p\n", blocks[i]);
        // }
        int inner_block_size = inner_size_dist(rng) * sizeof(LongType);
        char* inner_block = blocks[i] + (SIZE_BLOCK * sizeof(char)) - inner_block_size;
        MEMHOOK_LOG_CPP_ALLOC(inner_block, inner_block_size, typeid(char))

        type_counts["char"].alloc += 2;
        type_sizes["char"].alloc += SIZE_BLOCK*sizeof(char) + inner_block_size;

        size_t pre_count_char = type_counts["CharType"].alloc,
            pre_count_int = type_counts["IntType"].alloc,
            pre_count_long = type_counts["LongType"].alloc;
        int rem_inner_block_size = inner_block_size;
        while (rem_inner_block_size >= sizeof(LongType)) {
            switch (type_dist(rng)) {
                case CHAR_TYPE:
                    MemStamp(0, __LINE__) * (CharType*) new (inner_block) CharType{0};
                    type_counts["CharType"].alloc += 1;
                    type_sizes["CharType"].alloc += sizeof(CharType);
                    inner_block += sizeof(CharType);
                    rem_inner_block_size -= sizeof(CharType);
                    break;
                case INT_TYPE:
                    MemStamp(0, __LINE__) * (IntType*) new (inner_block) IntType{0};
                    type_counts["IntType"].alloc += 1;
                    type_sizes["IntType"].alloc += sizeof(IntType);
                    inner_block += sizeof(IntType);
                    rem_inner_block_size -= sizeof(IntType);
                    break;
                case LONG_TYPE:
                    MemStamp(0, __LINE__) * (LongType*) new (inner_block) LongType{0};
                    type_counts["LongType"].alloc += 1;
                    type_sizes["LongType"].alloc += sizeof(LongType);
                    inner_block += sizeof(LongType);
                    rem_inner_block_size -= sizeof(LongType);
                    break;
                default:
                    break;
            }
        }
        MEMHOOK_LOG_CPP_ALLOC(blocks[i], inner_block_size, typeid(char))
        type_counts["char"].alloc += 1;
        type_sizes["char"].alloc += inner_block_size;
        if (inner_block_size > SIZE_BLOCK / 2) {
            type_counts["char"].free += 1;
            type_sizes["char"].free += inner_block_size;
            type_counts["CharType"].free += (type_counts["CharType"].alloc - pre_count_char);
            type_sizes["CharType"].free += (type_counts["CharType"].alloc - pre_count_char) * sizeof(CharType);
            type_counts["IntType"].free += (type_counts["IntType"].alloc - pre_count_int);
            type_sizes["IntType"].free += (type_counts["IntType"].alloc - pre_count_int) * sizeof(IntType);
            type_counts["LongType"].free += (type_counts["LongType"].alloc - pre_count_long);
            type_sizes["LongType"].free += (type_counts["LongType"].alloc - pre_count_long) * sizeof(LongType);
        }
    }
}

int main() {
    std::vector<std::unordered_map<std::string, alloc_free_t>> type_counts{};
    type_counts.reserve(NUM_THREADS);
    std::vector<std::unordered_map<std::string, alloc_free_t>> type_sizes{};
    type_sizes.reserve(NUM_THREADS);
    std::vector<std::thread> threads{};
    std::unordered_map<std::string, alloc_free_t> combined_count = {
        {"char", {0, 0}},
        {"CharType", {0, 0}},
        {"IntType", {0, 0}},
        {"LongType", {0, 0}}
    };
    auto combined_size{combined_count};

    std::mutex print_m;

    for (int i = 0; i < NUM_THREADS; i++) {
        type_counts.push_back(combined_count);
        type_sizes.push_back(combined_count);
        threads.emplace_back(allocate_work, std::ref(type_counts[i]), std::ref(type_sizes[i]), std::ref(print_m));
    }

    for (int i = 0; i < NUM_THREADS; i++) {
        threads[i].join();
        for (auto& entry : combined_count) {
            combined_count[entry.first].alloc += type_counts[i][entry.first].alloc;
            combined_size[entry.first].alloc += type_sizes[i][entry.first].alloc;
            combined_count[entry.first].free += type_counts[i][entry.first].free;
            combined_size[entry.first].free += type_sizes[i][entry.first].free;
        }
    }

    std::ofstream ans_file;
    ans_file.open(TEST_DATA_DIR "generate_large_random.ans");
    for (auto& entry : combined_count) {
        ans_file << entry.first << " " << entry.second.alloc << " " << combined_size[entry.first].alloc << " alloc" << std::endl;
        ans_file << entry.first << " " << entry.second.free << " " << combined_size[entry.first].free << " free" << std::endl;
    }
    ans_file.close();
}