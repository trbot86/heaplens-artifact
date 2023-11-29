#include <iostream>
#include <new>
#include <thread>
#include <algorithm>
#include <typeinfo>
#include <typeindex>
#include <cstdio>
#include <bits/stdc++.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/mman.h>
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
#define NUMBER_OF_THREADS_BYTERW 8

using namespace std;

FILE* outfile;
void* filemap;
thread_local struct aiocb** aio_control;

typedef map<type_index, const char*> type_map;
struct info_t {
    const char* file;
    const char* tindex_name;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;
  //char padding[PADDING];

    info_t() : file(nullptr), tindex_name(nullptr), line(0), timestamp(0), size(0), addr(nullptr) {}
};

void read_block(int id, unsigned long int fsize) {
  unsigned long int bsize = STRUCTS_PER_BLOCK * sizeof(struct info_t);
  int num_my_blocks = ceil((double) (fsize - (id * bsize)) / (double) (NUMBER_OF_THREADS_BYTERW * bsize));
  char* charmap = (char *) malloc(num_my_blocks * STRUCTS_PER_BLOCK * 200 * sizeof(char));
  unsigned long int curr_byte = 0;

  aio_control = (struct aiocb**) malloc(num_my_blocks * sizeof(struct aiocb*));
  
  for (int i = 0; i < num_my_blocks; i++) {
    aio_control[i] = (struct aiocb*) malloc(sizeof(struct aiocb));
    memset(aio_control[i], 0, sizeof(struct aiocb));
    struct info_t* start = ((struct info_t*) filemap) + (id * STRUCTS_PER_BLOCK) + (i * NUMBER_OF_THREADS_BYTERW * STRUCTS_PER_BLOCK);
    unsigned long int remainder_of_file = (fsize / sizeof(struct info_t)) - (id * STRUCTS_PER_BLOCK) - (i * NUMBER_OF_THREADS_BYTERW * STRUCTS_PER_BLOCK);
    int bytes_copied = 0;
    for (int j = 0; j < min<unsigned long int>(remainder_of_file, (unsigned long int) STRUCTS_PER_BLOCK); j++) {
      struct info_t event = *(start + j);
      bytes_copied += sprintf(charmap + curr_byte + bytes_copied, "%s%lx|%s%lx|%d|%lu|%lu|%ld|%d\n",
                                                event.file ? "0x" : "",
                                                (uintptr_t) event.file,
                                                event.tindex_name ? "0x" : "",
                                                (uintptr_t) event.tindex_name,
                                                event.line,
                                                event.timestamp,
                                                event.size,
                                                (long) event.addr,
                                                event.typeofop);
    }

    aio_control[i]->aio_buf = charmap + curr_byte;
    aio_control[i]->aio_nbytes = bytes_copied;
    aio_control[i]->aio_fildes = fileno(outfile);
    aio_control[i]->aio_offset = 0;
    aio_control[i]->aio_reqprio = 0;
    aio_control[i]->aio_sigevent.sigev_notify = SIGEV_NONE;

    if (aio_write(aio_control[i]) != 0) {
      cout << "aio_write FAILED" << endl;
    }

    curr_byte += bytes_copied;
  }

  for (int i = 0; i < num_my_blocks; i++) {
    if (aio_error(aio_control[i]) == EINPROGRESS) {
      if (aio_suspend(&aio_control[i], 1, NULL) != 0) {
        cout << "aio_suspend FAILED" << endl;
      }
    }
    free(aio_control[i]);
  }
  free(aio_control);
  free(charmap);
}

int main(int argc, char* argv[]){
  const char* filename;
  unsigned long int file_byte_size = 0;
  unsigned long int block_size = STRUCTS_PER_BLOCK * sizeof(struct info_t);
  unsigned long int number_of_blocks = 0;
  unsigned long int remainders = 0;
  struct stat sb;
  struct info_t ** inmemory_data_ptr = NULL;

  if (argc >= 2) {
    filename = argv[1];
  }
  else {
    filename = "binary_dump.txt";
  }

  if (block_size < sizeof(struct info_t)) {
    block_size = MINIMUM_STRUCT_PER_BLOCK * sizeof(struct info_t);
  }

  FILE* fd = fopen(filename, "r");
  outfile = fopen("info_dump", "a");
  // ofstream info_dump;
  // info_dump.open("info_dump");

	if(fd ==  NULL ){
		printf("%s not found \n", filename);
	}

	fstat(fileno(fd), &sb);
  file_byte_size = (unsigned long int) sb.st_size;

  printf("Number of structs in file: %ld\n", file_byte_size / sizeof(struct info_t));

  number_of_blocks = ceil((double) file_byte_size / (double) block_size);
  int threads_needed = min<unsigned long int>(number_of_blocks, (unsigned long int) NUMBER_OF_THREADS_BYTERW);

  thread workers[threads_needed];
  filemap = mmap(NULL, file_byte_size, PROT_READ, MAP_SHARED, fileno(fd), 0);
  // struct aiocb* aio_control[NUMBER_OF_THREADS_BYTERW];

  // for (int i = 0; i < NUMBER_OF_THREADS_BYTERW; i++) {
  //   aio_control[i] = (struct aiocb*) malloc(sizeof(struct aiocb));
  //   memset(aio_control[i], 0, sizeof(struct aiocb));
  // }

  // for (int i = 0; i < number_of_blocks; i++) {
  //   unsigned long int struct_num = i * STRUCTS_PER_BLOCK;
  //   aio_control[i]->aio_buf = ((struct info_t*) filemap) + struct_num;
  //   aio_control[i]->aio_nbytes = struct_num * sizeof(struct info_t)
  // }

  // for (int i = 0; i < NUMBER_OF_THREADS_BYTERW; i++) {
  //   free(aio_control[i]);
  // }

  for (int i = 0; i < threads_needed; i++) {
    workers[i] = thread(read_block, i, file_byte_size);
  }

  for (int i = 0; i < threads_needed; i++) {
    workers[i].join();
  }

  fclose(outfile);

  // inmemory_data_ptr = (struct info_t**) calloc(number_of_blocks, sizeof(struct info_t*));

  // for (unsigned long int i = 0; i < number_of_blocks; i++) {
  //   inmemory_data_ptr[i] = (struct info_t*) malloc(block_size);

  //   //block_size needs to change when file doesnt have enough bytes
  //   //do same for next byte
  //   fread(inmemory_data_ptr[i], block_size, 1, fd);
  // }

  // unsigned int long structs_per_block = block_size / sizeof(struct info_t);
  // for (unsigned int long i  = 0; i < number_of_blocks; i++) {
  //   if (remainders != 0 && i == number_of_blocks - 1) {
  //     structs_per_block = remainders / sizeof(struct info_t);
  //   }
  //   for (unsigned int long j = 0; j < structs_per_block;j++) {
  //     // cout<<inmemory_data_ptr[i][j].tindex.hash_code();
  //     // if(inmemory_data_ptr[i][j].file == nullptr)
  //     // info_dump << "no tindex";
  //     // else
  //     info_dump << (void*)inmemory_data_ptr[i][j].file << "|" << (void*)inmemory_data_ptr[i][j].tindex_name << "|" << inmemory_data_ptr[i][j].line << "|" << inmemory_data_ptr[i][j].timestamp << "|" << inmemory_data_ptr[i][j].size << "|" << (long)inmemory_data_ptr[i][j].addr << "|" << inmemory_data_ptr[i][j].typeofop << endl;
  //   }
  // }
}
