#include "memhook_interface.h"
#include "b.h"

#include <stdlib.h>

int bar() {
    int* ptr = (int*)malloc(sizeof(int));
return 5;
}
