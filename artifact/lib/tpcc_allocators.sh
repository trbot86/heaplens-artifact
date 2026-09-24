#!/usr/bin/env bash
# Stage the retained, separately loaded allocator without replacing LD_PRELOAD's library.
tpcc_stage_allocators() {
    local root="$1" source_copy="$2"
    local retained="$root/artifact/vendor/heaplens-allocators/libjemalloc-heaplens.so"
    local expected="c516606efbdb708f503bc0f249061e492df04010a7292056281a0e9df6cbb3da"
    if [[ ! -f "$retained" ]] || [[ "$(sha256sum "$retained" | cut -d ' ' -f 1)" != "$expected" ]]; then
        echo "ERROR: retained TPC-C segregation allocator is missing or has an unexpected checksum: $retained" >&2
        return 1
    fi
    mkdir -p "$source_copy/lib"
    cp "$retained" "$source_copy/lib/libjemalloc-heaplens.so"
}
