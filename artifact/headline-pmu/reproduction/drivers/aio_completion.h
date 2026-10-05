// Author-only completion primitive. Caller supplies ONLY a successfully
// submitted, not-yet-reaped request. Never call aio_error on uninitialized AIO.
#ifndef HEAPLENS_AIO_COMPLETION_H
#define HEAPLENS_AIO_COMPLETION_H
#include <errno.h>
#include <stdint.h>

enum hl_aio_completion { hl_aio_ok, hl_aio_wait_error,
                         hl_aio_request_error, hl_aio_short_write };

// Dependency injection permits deterministic checks of EINTR/spurious wakeups
// without involving the evaluator logger. The real wrapper must retain errno,
// report failures, and reject the trial rather than recycling a failed buffer.
template <class Error, class Wait, class Return>
hl_aio_completion hl_complete_submitted(uint64_t expected,
                                       Error error, Wait wait, Return reap) {
    int status;
    while ((status = error()) == EINPROGRESS) {
        if (wait() != 0 && errno != EINTR) return hl_aio_wait_error;
    }
    // Reap exactly once even when a completed request reports an error.
    auto bytes = reap();
    if (status != 0 || bytes < 0) return hl_aio_request_error;
    if (uint64_t(bytes) != expected) return hl_aio_short_write;
    return hl_aio_ok;
}
#endif
