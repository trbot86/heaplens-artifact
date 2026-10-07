"""Known equivalent Clang field-owner and runtime allocation type spellings.

The converter removes whitespace from field-owner names. RTTI can put const
after its base type instead of before it. Do not erase const or use substring
matching: that would attach layouts to distinct C++ types. These exact aliases
repair the pinned HashSkipList bucket; offsets always come from the database.
"""

FIELD_TYPE_ALIASES = {
    'rocksdb::SkipList<charconst*,rocksdb::MemTableRep::KeyComparatorconst&>':
        'rocksdb::SkipList<constchar*,constrocksdb::MemTableRep::KeyComparator&>',
}


def match_field_types(fields_by_type, requested_types):
    """Return layouts under the requested keys, preferring an exact match."""
    matched = {}
    for name in requested_types:
        source = name if name in fields_by_type else FIELD_TYPE_ALIASES.get(name)
        if source in fields_by_type:
            matched[name] = fields_by_type[source]
    return matched
