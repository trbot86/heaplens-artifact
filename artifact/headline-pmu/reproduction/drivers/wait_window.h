// Author-side interval arithmetic only; not yet wired into the Valkey logger.
#ifndef HEAPLENS_WAIT_WINDOW_H
#define HEAPLENS_WAIT_WINDOW_H
#include <stdint.h>
#include <assert.h>
struct hl_window_overlap {
    uint64_t ns;
    bool starts_in_window, crosses_begin, crosses_end;
};
static inline hl_window_overlap hl_classify_wait(uint64_t begin, uint64_t end,
                                                uint64_t lo, uint64_t hi) {
    assert(begin <= end && lo <= hi);
    uint64_t left = begin > lo ? begin : lo;
    uint64_t right = end < hi ? end : hi;
    return {right > left ? right - left : 0,
            lo <= begin && begin < hi, begin < lo && lo < end,
            begin < hi && hi < end};
}
#endif
