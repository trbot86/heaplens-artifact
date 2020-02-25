#include "memhook.h"

#include "a.h"
#include "b.h"
#include <stdlib.h>


int main() {
    long* ret = new long;   
    goo1();
    return 0;
}
