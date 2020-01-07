#define _GNU_SOURCE

#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>

static void* (*real_malloc) (size_t);

char tmpbuff[1024];
unsigned long tmppos = 0;
unsigned long tempallocs = 0;


static void mtrace_init(void) {
    real_malloc = dlsym(RTLD_NEXT,"malloc");
    if(NULL == real_malloc) {
        fprintf(stderr,"Error in `dlsym`: %s\n",dlerror());
    }
}

// void* malloc(size_t size) {
//     static int initialising = 0;
//     if(real_malloc == NULL) {
//         if(!initialising) {
//             initialising = 1;
//             mtrace_init();
//             initialising = 0;
//         }
//         else {
//             if(tmppos + size < sizeof(tmpbuff)) {
//                 void* ret = tmpbuff + tmppos;
//                 tmppos += size;
//                 tempallocs++;
//                 return ret;
//             }
//             else {
//                 exit(1);
//             }
//         }
//     }

//     void* return_address = real_malloc(size);
//     // fprintf(stderr,"%p\n",return_address);
//     printf("ole");
//     return return_address;
// }

void* malloc(size_t size) {
    static int no_hook = 0;
    static int initialising = 0;

    if(real_malloc == NULL && !initialising) {
        initialising = 1;
        mtrace_init();
        initialising = 0;
    }
    else {
            if(tmppos + size < sizeof(tmpbuff)) {
                void* ret = tmpbuff + tmppos;
                tmppos += size;
                tempallocs++;
                return ret;
            }
            else {
                exit(1);
            }
    }
    
    if(no_hook)
        return real_malloc(size);

    no_hook = 1;
    void* return_address = real_malloc(size);
    printf("%p\n",return_address);
    fflush(stdout);
    // printf("ole");
    no_hook = 0;

    return return_address;
}