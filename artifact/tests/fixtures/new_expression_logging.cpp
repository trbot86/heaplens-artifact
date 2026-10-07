#include <cstdio>
#include <cstdlib>
#include <new>
#include <cstddef>
#include <type_traits>
#include <pthread.h>

struct Leaf { long values[2]; };
struct Owner {
    Leaf* child;
    Owner() : child(new Leaf) {
        void* scratch = malloc(23);
        free(scratch);
    }
    ~Owner() { delete child; }
};
struct StorageOwner {
    long prefix;
    alignas(Leaf) unsigned char storage[sizeof(Leaf)];
    Leaf* placed;
    Owner* allocated;
    StorageOwner() : prefix(1), placed(new(storage) Leaf), allocated(new Owner) {}
    ~StorageOwner() { delete allocated; }
};
struct Throwing {
    long value[3];
    Throwing() {
        printf("EXPECT Throwing %p %zu 1\n", (void*)this, sizeof(*this));
        throw 7;
    }
};
struct alignas(64) Aligned { long value[8]; };
struct ThreadNode { long value[4]; };
static void* worker(void*) {
    for (int i=0; i<20; ++i) {
        ThreadNode* p = new ThreadNode;
        printf("EXPECT ThreadNode %p %zu 1\n", (void*)p, sizeof(*p));
        delete p;
    }
    return nullptr;
}

Leaf* global_leaf = new Leaf;
Leaf* bound_leaf;
size_t array_bound() { bound_leaf = new Leaf; return 3; }

static void expect(const char* type, void* ptr, size_t size, int frees=1) {
    printf("EXPECT %s %p %zu %d\n", type, ptr, size, frees);
}
static void expect_owner(Owner* p) {
    expect("Owner", p, sizeof(*p));
    expect("Leaf", p->child, sizeof(*p->child));
}
int main() {
    Owner* owner = new Owner;
    StorageOwner* storage = new StorageOwner;
    Leaf* leaves = new Leaf[array_bound()];
    Leaf* quiet = new(std::nothrow) Leaf[5];
    Owner* quiet_owner = new(std::nothrow) Owner;
    Owner* owners = new Owner[4];
    expect("Leaf", global_leaf, sizeof(Leaf));
    expect_owner(owner);
    expect("StorageOwner", storage, sizeof(*storage));
    expect("Leaf", storage->placed, sizeof(Leaf), 0);
    expect_owner(storage->allocated);
    expect("Leaf", leaves, 3*sizeof(Leaf));
    expect("Leaf", bound_leaf, sizeof(Leaf));
    expect("Leaf", quiet, 5*sizeof(Leaf));
    expect_owner(quiet_owner);
    // This Linux test targets the Itanium C++ ABI used by the artifact image.
    // A nontrivial array has one size_t cookie before the first object; compare
    // the whole physical allocation, not only the first element's sizeof.
    expect("Owner", (char*)owners-sizeof(size_t), 4*sizeof(Owner)+sizeof(size_t));
    for (int i=0; i<4; ++i) expect("Leaf", owners[i].child, sizeof(Leaf));
    try { new Throwing; } catch (int n) { if (n != 7) return 2; }
    try { new(std::nothrow) Throwing; } catch (int n) { if (n != 7) return 3; }
#if defined(__cpp_aligned_new)
    Aligned* a = new Aligned;
    Aligned* b = new(std::nothrow) Aligned[3];
    expect("Aligned", a, sizeof(*a));
    expect("Aligned", b, 3*sizeof(*b));
    if ((size_t)a % 64 || (size_t)b % 64) return 4;
    delete a; delete[] b;
#endif
    // Preserve dereference/member-access precedence around placement new.
    alignas(Leaf) unsigned char local[sizeof(Leaf)];
    long* values = (new(local) Leaf)->values;
    values[0] = 42;
    expect("Leaf", local, sizeof(Leaf), 0);
    delete owner; delete storage; delete[] leaves; delete[] quiet;
    delete quiet_owner; delete[] owners; delete bound_leaf; delete global_leaf;
    pthread_t threads[3];
    for (auto& thread : threads) if (pthread_create(&thread, nullptr, worker, nullptr)) return 5;
    for (auto thread : threads) if (pthread_join(thread, nullptr)) return 6;
#ifdef __MEMHOOK_INTERFACE_H
    volatile size_t impossible = size_t(-1);
    void* failed = ::operator new(impossible, MemhookNew<char>(0, __LINE__), std::nothrow);
    if (failed) return 7;
#endif
}
