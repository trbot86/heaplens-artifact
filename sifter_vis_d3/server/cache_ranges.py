"""Cache-set delta updates without allocating per-object index arrays."""


def add_cache_range(data, bucket, start_set, type_idx, count, num_sets, delta):
    """Add one delta per touched line, including repeated sets on wraparound."""
    if count < 0:
        raise ValueError('negative cache-line count')
    if count == 1:
        data[bucket, start_set, type_idx] += delta
        return
    cycles, remainder = divmod(count, num_sets)
    if cycles:
        data[bucket, :, type_idx] += cycles * delta
    first = min(remainder, num_sets - start_set)
    if first:
        data[bucket, start_set:start_set + first, type_idx] += delta
    if remainder > first:
        data[bucket, :remainder - first, type_idx] += delta
