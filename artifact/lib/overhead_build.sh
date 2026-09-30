#!/usr/bin/env bash
# Reproduce the retained logging-overhead build in a fresh result directory.
set -euo pipefail
cd "${HEAPLENS_ROOT:?}"
CAMPAIGN="${HEAPLENS_OVERHEAD_DIR:?}"
test ! -e "${CAMPAIGN}/build"
mkdir "${CAMPAIGN}/build"
source artifact/lib/prepare_ascylib.sh
cp -r memhook "${CAMPAIGN}/build/stock-memhook"
make -C "${CAMPAIGN}/build/stock-memhook" clean
make -C "${CAMPAIGN}/build/stock-memhook" MEMHOOK_ASCYLIB=1 -j"${JOBS:-4}"

mkdir "${CAMPAIGN}/build/ssmem"
gcc -shared -fPIC -O3 -D_GNU_SOURCE -Iartifact/vendor/ssmem/include \
  artifact/vendor/ssmem/src/ssmem.c -o "${CAMPAIGN}/build/ssmem/libssmem_x86_64.so" -lpthread -lrt
export LD_LIBRARY_PATH=${CAMPAIGN}/build/ssmem
for spec in 'efrb bst-ellen lf-bst_ellen STM=LOCKFREE' 'dvy bst-drachsler lb-bst-drachsler' 'bcco bst-bronson lb-bst_bronson'; do
  read -r slug tree binary extra <<< "$spec"
  [[ " ${OVERHEAD_TREES:-efrb dvy bcco} " == *" $slug "* ]] || continue
  base=${CAMPAIGN}/build/$slug-baseline
  inst=${CAMPAIGN}/build/$slug-logging
  cp -r artifact/vendor/ascylib "$base"
  prepare_ascylib "${HEAPLENS_ROOT}" "$base"
  patch --batch --directory "$base" -p1 -i "${HEAPLENS_ROOT}/artifact/patches/ascylib-clang14.patch"
  args=(INIT=all SET_CPU=0 VERSION=O3)
  if [[ -n "$extra" ]]; then args+=("$extra"); fi
  # Dynamic SSMEM comes before the bundled static-library search directory.
  env CFLAGS=-fno-pie LDFLAGS="-no-pie -L${CAMPAIGN}/build/ssmem -Wl,-rpath=${CAMPAIGN}/build/ssmem" \
    make -C "$base/src/$tree" "${args[@]}"
  ./sifter.sh "$base" "$inst" -s "src/$tree" --skip-refactor \
    --build "env CFLAGS=-fno-pie LDFLAGS='-no-pie -L${CAMPAIGN}/build/ssmem -Wl,-rpath=${CAMPAIGN}/build/ssmem' bear -- make ${args[*]}"
  (cd "$inst" && clang-apply-replacements-14 ./)
  test -s "$inst/src/$tree/typeset_dump.txt"
  test -s "$inst/src/$tree/fileset_dump.txt"
  ./sifter.sh "$inst" --includes-only
  env CFLAGS="-fno-pie -DMEMHOOK_ASCYLIB -I${CAMPAIGN}/build/stock-memhook" \
    LDFLAGS="-no-pie -L${CAMPAIGN}/build/stock-memhook -Wl,-rpath=${CAMPAIGN}/build/stock-memhook -lmemhook -ldl -L${CAMPAIGN}/build/ssmem -Wl,-rpath=${CAMPAIGN}/build/ssmem" \
    make -C "$inst/src/$tree" "${args[@]}"
  ldd "$base/bin/$binary"
  ldd "$inst/bin/$binary"
  readelf -Ws "$inst/bin/$binary" | grep 'UND.*ssmem_free'
  ldd "$inst/bin/$binary" | grep -F "${CAMPAIGN}/build/ssmem/libssmem_x86_64.so"
  sha256sum "$base/bin/$binary" "$inst/bin/$binary"
done
gcc --version
ldd --version
sha256sum "${CAMPAIGN}/build/stock-memhook/libmemhook.so" "${CAMPAIGN}/build/ssmem/libssmem_x86_64.so"
