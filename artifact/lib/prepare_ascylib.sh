#!/usr/bin/env bash
# Apply recovered experimental source changes to a fresh scratch copy only.
prepare_ascylib() {
    local root="$1" copy="$2"
    patch --batch --directory "$copy" -p1 -i "$root/artifact/patches/ascylib-historical.patch"
    grep -q -- '-DSEG_OBJS' "$copy/common/Makefile.common"
    grep -q 'info_t_alloc' "$copy/src/bst-ellen/bst_ellen.c"
    mkdir "$copy/ssmem-source"
    cp -r "$root/artifact/vendor/ssmem/." "$copy/ssmem-source/"
    make -C "$copy/ssmem-source" libssmem.a CFLAGS='-O3 -Wall -fPIC'
    cp "$copy/ssmem-source/libssmem.a" "$copy/external/lib/libssmem_x86_64.a"
}

# Diagnostic traces need interposable retirement calls. With static SSMEM,
# ssmem_free in the executable bypasses memhook's LD_PRELOAD hook. Performance
# builds continue to use the archive produced by prepare_ascylib above.
prepare_ascylib_trace_ssmem() {
    local root="$1" output="$2"
    mkdir "$output"
    gcc -shared -fPIC -O3 -D_GNU_SOURCE \
        -I"$root/artifact/vendor/ssmem/include" \
        "$root/artifact/vendor/ssmem/src/ssmem.c" \
        -o "$output/libssmem_x86_64.so" -lpthread -lrt
}
