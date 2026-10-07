// Deterministic delayed AIO: an in-flight buffer must remain unchanged until
// it is reaped, even when producers grow, hit the process cap, and exit.
#include "memhook.h"
#include <cassert>
#include <map>
#include <mutex>
#include <algorithm>

struct Pending { std::vector<char> bytes; bool ready; };
static std::map<const aiocb*, Pending> requests;
static std::mutex io_mutex;
static int submissions=0, reaps=0, waits=0, peak_buffers=0;
static int operation_waits=0, drain_waits=0;
static size_t peak_extra=0;
static bool fail_growth=false;
static thread_local bool draining=false;
extern "C" void* __real_malloc(size_t);
extern "C" void* __wrap_malloc(size_t bytes) {
  if (fail_growth && !thread_first_call && bytes==sizeof(memhook_info_t)*MEMHOOK_MAX_BUFFER_SIZE)
    return nullptr;
  return __real_malloc(bytes);
}

extern "C" int aio_write(aiocb* p) noexcept {
  std::lock_guard<std::mutex> guard(io_mutex);
  assert(!requests.count(p));
  const char* data=(const char*)p->aio_buf;
  requests.emplace(p,Pending{std::vector<char>(data,data+p->aio_nbytes),false});
  ++submissions;
  return 0;
}
extern "C" int aio_error(const aiocb* p) noexcept {
  std::lock_guard<std::mutex> guard(io_mutex);
  assert(requests.count(p));
  return requests.at(p).ready ? 0 : EINPROGRESS;
}
extern "C" int aio_suspend(const aiocb* const p[],int n,const timespec*) {
  std::lock_guard<std::mutex> guard(io_mutex);
  assert(n==1 && requests.count(p[0]));
  requests.at(p[0]).ready=true;
  ++waits;
  if (draining) ++drain_waits; else ++operation_waits;
  return 0;
}
extern "C" ssize_t aio_return(aiocb* p) noexcept {
  std::lock_guard<std::mutex> guard(io_mutex);
  assert(requests.count(p) && requests.at(p).ready);
  const auto& expected=requests.at(p).bytes;
  assert(expected.size()==p->aio_nbytes);
  if (p->aio_nbytes) {
    assert(memcmp(expected.data(),(const void*)p->aio_buf,p->aio_nbytes)==0);
    assert(write(global_fd,(const void*)p->aio_buf,p->aio_nbytes)==(ssize_t)p->aio_nbytes);
  }
  requests.erase(p); ++reaps;
  return p->aio_nbytes;
}

memhook_memory_pool::memhook_memory_pool() {}
memhook_memory_pool::~memhook_memory_pool() {}
void memhook_memory_pool::add(memhook_info_t* p,int bytes) {
  std::lock_guard<std::mutex> guard(io_mutex);
  assert(write(global_fd,p,bytes)==bytes);
  // Match production ownership: this nonempty tail remains allocated until
  // process exit, and any extra-buffer budget it owns remains reserved.
}

static void producer(int id,int count) {
  ThreadExiter terminal;
  for(int i=0;i<count;++i) {
    memhook_info_t row;
    row.timestamp=id*100000+i;
    row.size=i+1;
    row.typeofop=true;
    memhookCollector.copy(row);
    std::lock_guard<std::mutex> guard(io_mutex);
    peak_buffers=std::max(peak_buffers,number_of_buffers);
    peak_extra=std::max(peak_extra,memhook_extra_buffer_bytes.load());
    assert(memhook_extra_buffer_bytes.load()<=MEMHOOK_EXTRA_BUFFER_BUDGET_BYTES);
    assert(number_of_buffers<=MEMHOOK_MAX_BUFFERS);
  }
  draining=true;
  terminal.finish(); terminal.finish();
}

static void completed_slot_control() {
  // Slot 0 remains busy while the most recently submitted slot 1 is ready.
  // A two-slot scan must reuse slot 1; round-robin must wait for slot 0.
  std::thread test([] {
    aiocb controls[2] = {};
    bool submitted[2] = {true,true};
    async_struct_array=controls; async_submitted=submitted;
    number_of_buffers=2;
    requests.emplace(&controls[0],Pending{{},false});
    requests.emplace(&controls[1],Pending{{},true});
    int before=waits;
    int chosen=memhook_next_buffer(1);
#if MEMHOOK_REUSE_COMPLETED_BUFFERS
    assert(chosen==1 && waits==before);
    memhook_finish_aio(0);
#else
    assert(chosen==0 && waits==before+1);
    memhook_finish_aio(1);
#endif
    assert(requests.empty());
    async_struct_array=nullptr; async_submitted=nullptr;
  });
  test.join();
  submissions=reaps=waits=operation_waits=drain_waits=0;
}

int main(int argc,char** argv) {
  assert(argc==3);
  int count=atoi(argv[1]);
  fail_growth=getenv("MEMHOOK_TEST_FAIL_GROW")!=nullptr;
  global_fd=open(argv[2],O_RDWR|O_CREAT|O_EXCL|O_APPEND,0600);
  assert(global_fd>=0);
  completed_slot_control();
  for(int wave=0;wave<3;++wave) {
    std::vector<std::thread> threads;
    for(int i=0;i<3;++i) threads.emplace_back(producer,wave*3+i,count);
    for(auto& thread:threads) thread.join();
    if(count%MEMHOOK_MAX_BUFFER_SIZE==0) assert(memhook_extra_buffer_bytes.load()==0);
  }
  assert(requests.empty() && submissions==reaps);
  assert(lseek(global_fd,0,SEEK_END)==off_t(9*count*sizeof(memhook_info_t)));
  lseek(global_fd,0,SEEK_SET);
  std::vector<memhook_info_t> rows(9*count);
  assert(read(global_fd,rows.data(),rows.size()*sizeof(memhook_info_t))==ssize_t(rows.size()*sizeof(memhook_info_t)));
  std::sort(rows.begin(),rows.end(),[](const memhook_info_t& a,const memhook_info_t& b){return a.timestamp<b.timestamp;});
  for(int id=0;id<9;++id) for(int i=0;i<count;++i) {
    const auto& row=rows[id*count+i];
    assert(row.timestamp==uint64_t(id*100000+i) && row.size==size_t(i+1) && row.typeofop);
  }
  if(!fail_growth && count>=3*MEMHOOK_MAX_BUFFER_SIZE && MEMHOOK_MAX_BUFFERS>2 &&
     MEMHOOK_EXTRA_BUFFER_BUDGET_BYTES>=sizeof(memhook_info_t)*MEMHOOK_MAX_BUFFER_SIZE)
    assert(peak_buffers>2);
  if(fail_growth) assert(peak_buffers<=2 && memhook_extra_buffer_bytes.load()==0);
  printf("{\"records\":%zu,\"peak_buffers_per_thread\":%d,\"peak_extra_bytes\":%zu,\"retained_extra_bytes\":%zu,\"waits\":%d,\"operation_waits\":%d,\"drain_waits\":%d,\"submissions\":%d,\"reaps\":%d}\n",
         rows.size(),peak_buffers,peak_extra,memhook_extra_buffer_bytes.load(),waits,operation_waits,drain_waits,submissions,reaps);
  close(global_fd);
}
