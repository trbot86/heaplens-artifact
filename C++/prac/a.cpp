#include "a.h"
#include "b.h"
#include <stdlib.h>

#include "memhook.h"

class dumbclass {

};


int main() {
    long* ret = new long;   
    goo1();
    return 0;
}
