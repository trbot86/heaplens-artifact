#include <iostream>
#include <new>
#include <typeinfo>
#include <typeindex>
#include <bits/stdc++.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <execinfo.h>
#include <cxxabi.h>
#include <dlfcn.h>
#include <pthread.h>
#include <vector>
#include <stdio.h>
#include <aio.h>
#include <stdint.h>
#include <inttypes.h>

#define PADDING 64
#ifndef STRUCTS_PER_BLOCK
  #define STRUCTS_PER_BLOCK 1000000
#endif

#define MINIMUM_STRUCT_PER_BLOCK 1000000
using namespace std;

typedef map<type_index, const char*> type_map;
struct info_t {
    const char* file;
    type_index tindex;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;
  //char padding[PADDING];

    info_t() : file(nullptr), tindex(typeid(void)), line(0), timestamp(0), size(0), addr(nullptr) {}
};


int main(){

  unsigned long int file_byte_size = 0;
  unsigned long int block_size = STRUCTS_PER_BLOCK *sizeof(struct info_t);
  unsigned long int number_of_blocks = 0;
  unsigned long int remainders = 0;
  struct info_t ** inmemory_data_ptr = NULL;
  if(block_size < sizeof(struct info_t)){
    block_size = MINIMUM_STRUCT_PER_BLOCK*sizeof(struct info_t);
  }

  FILE* fd = fopen("binary_dump.txt", "r");
  ofstream info_dump;
  info_dump.open("info_dump");

	if(fd ==  NULL ){
		printf("binary_dump.txt not found \n");
	}

	fseek(fd, 0L,SEEK_END);
	file_byte_size = ftell(fd);

	rewind(fd);

  number_of_blocks = floor(file_byte_size/block_size);
  remainders = file_byte_size - block_size*number_of_blocks;
  if(remainders != 0){
    number_of_blocks ++;
  }

  inmemory_data_ptr = (struct info_t **) calloc(number_of_blocks, sizeof(struct info_t *));

  for(unsigned long int i = 0; i < number_of_blocks; i++){
    inmemory_data_ptr[i] = (struct info_t*)malloc(block_size);

    //block_size needs to change when file doesnt have enough bytes
    //do same for next byte
    fread(inmemory_data_ptr[i], block_size, 1, fd);
  }

  unsigned int long structs_per_block = block_size / sizeof(struct info_t);
  for(unsigned int long i  = 0; i < number_of_blocks; i++){
    if(remainders != 0 && i == number_of_blocks - 1){
      structs_per_block = remainders/sizeof(struct info_t) ;
    }
    for(unsigned int long j = 0; j < structs_per_block;j++){
      info_dump << inmemory_data_ptr[i][j].timestamp << "|" << inmemory_data_ptr[i][j].size << "|" << inmemory_data_ptr[i][j].addr << "|" << inmemory_data_ptr[i][j].typeofop << endl;
    }
  }

}
