#include <cassert>
#include "globals.h"
#include "allocator_new.h"

struct TestNode { unsigned long value; char padding[56]; };

int main() {
    debugInfo debug(1);
    allocator_new<TestNode> allocator(1, &debug);
    for (unsigned long i = 0; i != 10000; ++i) {
        TestNode* node = allocator.allocate(0);
        node->value = i;
        assert(node->value == i);
        allocator.deallocate(0, node);
    }
    return 0;
}
