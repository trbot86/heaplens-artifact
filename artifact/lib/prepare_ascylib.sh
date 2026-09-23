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
