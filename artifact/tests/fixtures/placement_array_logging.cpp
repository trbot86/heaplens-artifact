#include <new>
#include <cstdio>
#include <cstddef>
#include <cstdlib>
struct Placed { long data[2]; Placed() { void* p=malloc(17); free(p); } ~Placed() {} };
struct alignas(64) PlacedAligned { long data[8]; ~PlacedAligned() {} };
struct PlacedThrow { PlacedThrow() { throw 7; } };
alignas(Placed) unsigned char global_storage[sizeof(Placed)*2];
Placed* global_placed = new(global_storage) Placed[2];
static int bound_calls=0;
static int bound() { ++bound_calls; return 3; }
static int negative() { return -1; }
template <class T> T* make_placed(void* storage, int n) { return new(storage) T[n]; }
int main() {
    alignas(Placed) unsigned char storage[sizeof(Placed)*3];
    alignas(Placed) unsigned char second[sizeof(Placed)*4];
    alignas(PlacedAligned) unsigned char aligned[sizeof(PlacedAligned)*2];
    Placed* p=new(storage) Placed[bound()];
    Placed* q=make_placed<Placed>(second,4);
    PlacedAligned* a=make_placed<PlacedAligned>(aligned,2);
    if (bound_calls!=1 || (void*)p!=storage || (void*)q!=second || (void*)a!=aligned) return 2;
    printf("EXPECT Placed %p %zu\n",(void*)global_placed,2*sizeof(Placed));
    printf("EXPECT Placed %p %zu\n",(void*)p,3*sizeof(Placed));
    printf("EXPECT Placed %p %zu\n",(void*)q,4*sizeof(Placed));
    printf("EXPECT PlacedAligned %p %zu\n",(void*)a,2*sizeof(PlacedAligned));
    bool threw=false;
    try { new(storage) Placed[negative()]; } catch (const std::bad_array_new_length&) { threw=true; }
    if (!threw) return 3;
    try { new(storage) PlacedThrow[2]; return 4; } catch(int n) { if(n!=7) return 5; }
    for(int i=0;i<3;++i) p[i].~Placed();
    for(int i=0;i<4;++i) q[i].~Placed();
    for(int i=0;i<2;++i) { global_placed[i].~Placed(); a[i].~PlacedAligned(); }
}
