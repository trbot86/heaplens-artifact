#include <stdio.h>
#include <pthread.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#include <dlfcn.h>
#include <stddef.h>
#include <stdlib.h>
struct info_t {
    const char* file;
    type_index tindex;
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
    bool typeofop;
    char padding[PADDING];

    info_t() : file(nullptr), tindex(typeid(void)), line(0), timestamp(0), size(0), addr(nullptr) {}
};


int main(){
    FILE* fd = fopen("binary_dump.txt", "r");
    
    ofstream info_dump;
    info_dump.open("info_dump");
	
	if(fd ==  NULL ){
		printf("binary_dump.txt not found \n");
	}

	fseek(fd, 0L,SEEK_END);
	long file_size = ftell(fd);

	rewind(fd);

    //for now assume file_size doesn't exceed 1gb
    struct info_t *data_buffer = (struct info_t*)malloc(file_size);

	fread(data_buffer,byte_size, 1,fd);

	int num_records = file_size/sizeof(struct info_t);

	for(int i = 0; i < num_records; i++){
		info_dump << data_buffer[i].timestamp << "|" << data_buffer[i].size <<"|" << data_buffer[i].addr << "|" << data_buffer[i].typeofop << endl;
	}
}