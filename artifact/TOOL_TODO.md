# HeapLENS tool TODO

## Consistent type names for allocation and field metadata

Status: planned follow-up, agreed October 7, 2026. The current Figure 8 repair
uses a narrow alias for the pinned RocksDB HashSkipList bucket.

Runtime allocation records and compiler-extracted field metadata can spell
the same C++ type differently. For example, the bucket's runtime name uses
`char const*` and `KeyComparator const&`, while its field metadata uses
`const char*` and `const KeyComparator&`. Removing whitespace does not make
these names match, so the GUI previously omitted fields already in the database.

- Define a common type representation and make both data sources consistently
  produce it for matching. Prefer compiler-derived type identity where
  available; do not accumulate workload-specific aliases as the general fix.
- Preserve the original names for display and diagnosis. Normalize before
  discarding token boundaries, and use the common representation throughout
  conversion and GUI field association.
- Preserve `const`/`volatile` qualification and what each qualifier applies to,
  pointer/reference structure, namespaces and template arguments. Do not
  simply remove qualifiers: distinct template specializations can have
  different fields and layouts.
- Support existing databases through a compatible read-time path. Keep
  original traces unchanged, and leave ambiguous or unsupported matches
  unresolved with a useful diagnostic rather than attaching a guessed layout.
- Validate the complete path from allocation and field extraction to GUI
  association. Cover equivalent qualifier spellings, nested templates,
  namespace distinctions, pointer versus pointee qualification, references,
  typedef/alias handling, and specializations with different layouts. Check
  field names, sizes and offsets, including baseline and reordered layouts.
- Replace the narrow bucket alias only after those checks pass and retained
  traces continue to resolve correctly without merging distinct types.

This work concerns type identity and field association. The current narrow
repair reads existing field offsets; it does not change benchmark layouts or
performance results. See the [Figure 8 notes](REPRODUCTION_CONFIGURATIONS.md#figure-8-field-metadata-and-memory)
for the released repair's validation scope.
