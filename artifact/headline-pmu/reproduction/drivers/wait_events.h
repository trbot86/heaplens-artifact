// Author-side prototype: collect bounded TLS wait events, classify after the
// process-wide measurement window is closed. Not yet deployed into memhook.
#ifndef HEAPLENS_WAIT_EVENTS_H
#define HEAPLENS_WAIT_EVENTS_H
#include "wait_window.h"
#include <stddef.h>

struct hl_wait_event { uint64_t begin, end; unsigned kind; bool error; };
struct hl_window_wait_stats {
    uint64_t starts, overlap_ns, max_overlap_ns, errors_starting;
    uint64_t crosses_begin, crosses_end;
};
template <size_t Capacity> struct hl_wait_events {
    hl_wait_event events[Capacity];
    size_t used = 0;
    bool overflow = false;

    // Never overwrite or silently discard evidence. The caller must reject a
    // trial with overflow=true; it must not publish partial totals as complete.
    bool append(uint64_t begin, uint64_t end, unsigned kind, bool error) {
        assert(begin <= end && kind < 2);
        if (used == Capacity) { overflow = true; return false; }
        events[used++] = {begin, end, kind, error};
        return true;
    }
    bool summarize(uint64_t lo, uint64_t hi,
                   hl_window_wait_stats (&out)[2]) const {
        assert(lo <= hi);
        out[0] = {}; out[1] = {};
        if (overflow) return false;
        for (size_t i = 0; i < used; ++i) {
            const auto &e = events[i];
            const auto overlap = hl_classify_wait(e.begin, e.end, lo, hi);
            auto &s = out[e.kind];
            s.starts += overlap.starts_in_window;
            s.errors_starting += overlap.starts_in_window && e.error;
            s.overlap_ns += overlap.ns;
            if (overlap.ns > s.max_overlap_ns) s.max_overlap_ns = overlap.ns;
            s.crosses_begin += overlap.crosses_begin;
            s.crosses_end += overlap.crosses_end;
        }
        return true;
    }
};
#endif
