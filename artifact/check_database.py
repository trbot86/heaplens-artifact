#!/usr/bin/env python3
"""Reject an empty database even if the older pipeline exited successfully."""
import sqlite3
import sys
from pathlib import Path
path = Path(sys.argv[1]).resolve()
with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
    assert db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    counts = {name: db.execute('SELECT COUNT(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] for name in tables}
    print("Database row counts:", counts)
    if counts.get("SUPERTABLE", 0) == 0:
        raise SystemExit("FAIL: no allocation records in database")
    usable = db.execute("SELECT COUNT(*) FROM SUPERTABLE WHERE isNew=1 AND TYPE != 'NULL' AND FILE != 'NULL'").fetchone()[0]
    print("Typed allocations with source-file metadata:", usable)
    if not usable:
        raise SystemExit("FAIL: no typed allocations with source-file metadata for the GUI")
