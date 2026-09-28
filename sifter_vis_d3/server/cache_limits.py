"""Preflight the dense cache-view response; this is not a peak-RSS guarantee."""
import os

DEFAULT_BUDGET_MB = 4096
# Account conservatively for arrays/copies, Python lists/integers and JSON.
# A single array's 8 bytes/cell substantially understates the full response.
ESTIMATED_BYTES_PER_CELL = 96


class CacheRequestError(ValueError):
    pass


class CacheBudgetExceeded(CacheRequestError):
    pass


def validate_cache_geometry(page_size, line_size, buckets, size, assoc):
    values = (page_size, line_size, buckets, size, assoc)
    if any(type(value) is not int or value <= 0 for value in values):
        raise CacheRequestError("Page size, cache-line size, time buckets, cache size, and associativity must be positive integers.")
    if size % (line_size * assoc) != 0:
        raise CacheRequestError("Cache size must be a positive multiple of cache-line size times associativity.")
    return size // (line_size * assoc)


def check_cache_budget(buckets, sets, columns):
    try:
        budget_mb = int(os.environ.get('HEAPLENS_CACHE_BUDGET_MB', DEFAULT_BUDGET_MB))
        if budget_mb <= 0:
            raise ValueError()
    except ValueError:
        raise CacheRequestError("HEAPLENS_CACHE_BUDGET_MB must be a positive integer.")
    budget = budget_mb * 1024 * 1024
    bytes_per_row = sets * columns * ESTIMATED_BYTES_PER_CELL
    estimate = (buckets + 2) * bytes_per_row
    if estimate > budget:
        max_buckets = budget // max(bytes_per_row, 1) - 2
        suggestion = (f"Try {max_buckets} or fewer time buckets in Settings. "
                      if max_buckets >= 1 else "This geometry exceeds the budget even at one time bucket. ")
        raise CacheBudgetExceeded(
            f"Cache view exceeds the configured memory budget: estimated {estimate / 2**30:.2f} GiB "
            f"for arrays and response data; budget {budget / 2**30:.2f} GiB. "
            + suggestion + "The previous view is unchanged. Cache geometry and bucket count were not reduced automatically.")
    return estimate
