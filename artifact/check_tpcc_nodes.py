#!/usr/bin/env python3
"""Require Figure 6's typed tree allocations, beyond generic database validity."""
import argparse
import json
from pathlib import Path
import sqlite3


def check(path):
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        rows = db.execute('SELECT TYPE, SIZE, FILE, COUNT(*) FROM SUPERTABLE '
                          'WHERE isNew=1 GROUP BY TYPE, SIZE, FILE').fetchall()
    nodes = [(tp, size, source, count) for tp, size, source, count in rows
             if isinstance(tp, str) and ''.join(tp.split()).startswith('node_t<')]
    if not nodes:
        raise ValueError('no typed BCCO node allocations; generic typed rows are insufficient for Figure 6')
    if any(size != 56 or not isinstance(source, str) or
           not source.replace('\\', '/').endswith('/allocator_new.h')
           for tp, size, source, count in nodes):
        raise ValueError('BCCO nodes lack the expected 56-byte layout or record-manager source')
    return {'status': 'passed', 'scope': 'Figure 6 BCCO node presence, requested size and source',
            'typed_node_allocations': sum(r[3] for r in nodes),
            'types': sorted({r[0] for r in nodes}), 'requested_bytes': 56}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = check(args.database)
    except (ValueError, sqlite3.Error) as error:
        parser.exit(1, 'FAIL: ' + str(error) + '\n')
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
