#include "memhook_interface.h"
#include <stdio.h>
#include <stdlib.h>
/* This test never uses ssalloc; satisfy the logger's otherwise unused imports. */
void* ssalloc(size_t size) { abort(); }
void* ssalloc_aligned(size_t alignment, size_t size) { abort(); }
int main(void) {
    ssmem_allocator_t allocator;
    ssmem_alloc_init_fs_size(&allocator, 32768, 16, 0);
    void* pointers[4];
    for (int i=0; i<4; ++i) {
        pointers[i]=ssmem_alloc_s(&allocator, 64, 77, 3, 7);
        printf("target %p\n", pointers[i]);
    }
    for (int i=0; i<4; ++i) ssmem_free(&allocator,pointers[i]);
    return 0;
}
