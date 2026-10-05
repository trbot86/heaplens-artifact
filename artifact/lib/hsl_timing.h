#ifndef HEAPLENS_HSL_TIMING_H
#define HEAPLENS_HSL_TIMING_H
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>

// Snapshot existing Stats only after completion. No clocks or hot-path hooks.
struct HlHslSample {
  uint64_t start_us, finish_us, operations;
  bool excluded;
};
struct HlHslInterval {
  bool present = false;
  uint64_t start_us = 0, finish_us = 0, operations = 0;
  unsigned workers = 0;
  void Add(const HlHslSample& s) {
    assert(s.finish_us >= s.start_us);
    if (!present) { start_us = s.start_us; finish_us = s.finish_us; present = true; }
    else { start_us = std::min(start_us, s.start_us); finish_us = std::max(finish_us, s.finish_us); }
    operations += s.operations;
    ++workers;
  }
};
struct HlHslTiming {
  HlHslInterval readers, writers;
  void Add(const HlHslSample& s) { (s.excluded ? writers : readers).Add(s); }
  void Report(const HlHslSample& native) const {
    assert(readers.present && writers.workers == 1);
    assert(readers.operations == native.operations);
    printf("HL_HSL_TIMING {\"schema\":1,\"native_start_us\":%llu,\"native_finish_us\":%llu,"
           "\"reader_start_us\":%llu,\"reader_finish_us\":%llu,\"reader_operations\":%llu,"
           "\"reader_workers\":%u,\"writer_start_us\":%llu,\"writer_finish_us\":%llu,"
           "\"writer_operations\":%llu,\"writer_workers\":%u}\n",
           (unsigned long long)native.start_us, (unsigned long long)native.finish_us,
           (unsigned long long)readers.start_us, (unsigned long long)readers.finish_us,
           (unsigned long long)readers.operations, readers.workers,
           (unsigned long long)writers.start_us, (unsigned long long)writers.finish_us,
           (unsigned long long)writers.operations, writers.workers);
    fflush(stdout);
  }
};
#endif
