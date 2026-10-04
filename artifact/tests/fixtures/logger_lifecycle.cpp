// Exercise the actual logger header with tiny buffers, without workload code.
#include "memhook.h"
#include <cassert>

static int fault, forced_waits, submissions, reaps;
extern "C" int __real_aio_write(struct aiocb *);
extern "C" int __real_aio_error(const struct aiocb *);
extern "C" int __real_aio_suspend(const struct aiocb *const[], int, const struct timespec *);
extern "C" ssize_t __real_aio_return(struct aiocb *);
extern "C" int __wrap_aio_write(struct aiocb *p) {
  if (fault == 4) { errno = EIO; return -1; }
  ++submissions;
  return __real_aio_write(p);
}
extern "C" int __wrap_aio_error(const struct aiocb *p) {
  assert(submissions > reaps); // No querying unsubmitted slots.
  if ((fault == 1 && forced_waits < 2) || fault == 5) return EINPROGRESS;
  int result = __real_aio_error(p);
  return result == 0 && fault == 3 ? EIO : result;
}
extern "C" int __wrap_aio_suspend(const struct aiocb *const p[], int n, const struct timespec *t) {
  if (fault == 5) { errno = EINVAL; return -1; }
  if (fault == 1 && forced_waits++ == 0) { errno = EINTR; return -1; }
  return __real_aio_suspend(p, n, t);
}
extern "C" ssize_t __wrap_aio_return(struct aiocb *p) {
  ++reaps;
  ssize_t result = __real_aio_return(p);
  return fault == 2 && result > 0 ? result - 1 : result;
}

memhook_memory_pool::memhook_memory_pool() {}
memhook_memory_pool::~memhook_memory_pool() {}
void memhook_memory_pool::add(memhook_info_t *p, int bytes) {
  int saved = log_index;
  memhook_info_t bookkeeping;
  memhookCollector.copy(bookkeeping); // Simulate pool vector allocation hooks.
  assert(log_index == saved);
  assert(write(global_fd, p, bytes) == bytes);
}

int main(int argc, char **argv) {
  assert(argc == 4);
  int count = atoi(argv[1]);
  fault = atoi(argv[2]);
  global_fd = open(argv[3], O_CREAT | O_EXCL | O_APPEND | O_RDWR, 0600);
  assert(global_fd >= 0);
  {
    ThreadExiter terminal;
    for (int i = 0; i < count; ++i) {
      memhook_info_t record;
      record.timestamp = i;
      record.typeofop = true;
      memhookCollector.copy(record);
    }
    terminal.finish();
    terminal.finish(); // Explicit flush followed by TLS teardown is idempotent.
  }
  assert(submissions == reaps);
  assert(lseek(global_fd, 0, SEEK_END) == off_t(count * sizeof(memhook_info_t)));
  close(global_fd);
}
