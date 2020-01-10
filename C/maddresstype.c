#define _GNU_SOURCE

#define malloc(size_t) mymalloc(size_t,const char*)

#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>

static void* (*real_malloc) (size_t);
static void* (*real_free) (void*);

static int no_hook = 0;
static int initialising = 0;

char tmpbuff[10240];
unsigned long tmppos = 0;
unsigned long tempallocs = 0;


static void mtrace_init(void) {
    real_malloc = dlsym(RTLD_NEXT,"malloc");
    real_free = dlsym(RTLD_NEXT,"free");

    if(NULL == real_malloc) {
        fprintf(stderr, "Error in `dlsym`: %s\n",dlerror());
    }

    if(NULL == real_free) {
        fprintf(stderr, "Error in `dlsym`: %s\n",dlerror());
    }
}

// void* malloc(size_t size) {
//     static int initialising = 0;
//     if(real_malloc == NULL) {
//         if(!initialisin(exception=exception@entry=0x7fffffffda30, objname=<optimized out>, fmt=fmt@entry=0x7ffff7df5fe6 "undefined symbol: %s%s%s") at dl-exception.c:131
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

void* mymalloc(size_t size,const char* type) {

    if(real_malloc == NULL) {
        if(!initialising) {
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
    }
    
    if(no_hook)
        return real_malloc(size);

    no_hook = 1;
    void* return_address = real_malloc(size);
    fprintf(stdout,"%p type: %s\n",return_address,type);
    // fflush(stdout);
    // printf("ole");
    no_hook = 0;

    return return_address;
}

void free(void* ptr) {
    
    if(ptr >= (void*)tmpbuff && ptr <= (void*)(tmpbuff+tmppos)) {
        tmppos -= (void*)(tmpbuff + tmppos) - ptr;
        tempallocs--;
    }
    else {
        printf("freeing %p\n",ptr);
        real_free(ptr);
    }
    return;
}