"""Author-side trace retention; call only between trials after the writer exits.

Raw files are measured on NFS. Archives live on local scratch; per-trial receipts
and the inventory live on NFS and should also be copied to the author's machine.
This module never deletes archives, modifies a benchmark, or starts a process.
"""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from datetime import datetime, timezone

GIB = 1024**3
CHUNK = 40 * 65536


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as src:
        for block in iter(lambda: src.read(CHUNK), b''):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    """Replace only this store's metadata, never experiment data."""
    path = Path(path)
    part = path.with_suffix('.json.tmp')
    with part.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    os.replace(part, path)
    sync_directory(path.parent)


def sync_directory(path):
    """Make published filenames durable before releasing the raw trace (Linux)."""
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class TraceStore:
    def __init__(self, *, raw_root, archive_root, manifest_root, campaign, host,
                 raw_floor=50*GIB, archive_floor=50*GIB, expected_traces=200):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', campaign):
            raise ValueError('Unsafe campaign identifier')
        roots = [Path(x).absolute() for x in (raw_root, archive_root, manifest_root)]
        for root in roots:
            if len(root.parts) < 3 or root.resolve() != root:
                raise ValueError('Explicit non-symlink, non-root storage directories required')
        if any(a == b or a in b.parents or b in a.parents
               for i,a in enumerate(roots) for b in roots[i+1:]):
            raise ValueError('Storage directories must be separate, not nested')
        self.raw_root, self.archive_root, self.manifest_root = roots
        self.campaign, self.host = campaign, host
        self.raw_floor, self.archive_floor = raw_floor, archive_floor
        self.expected_traces = expected_traces
        for root in roots:
            root.mkdir(parents=True, exist_ok=True)
        marker = self.manifest_root/'store.json'
        settings = dict(campaign=campaign, host=host, raw_root=str(self.raw_root),
                        archive_root=str(self.archive_root), manifest_root=str(self.manifest_root),
                        expected_traces=expected_traces, raw_floor=raw_floor, archive_floor=archive_floor,
                        retention='pending_author_review_no_automatic_deletion',
                        storage_kind='scratch_only_not_independent_backup')
        if marker.exists():
            if json.loads(marker.read_text()) != settings:
                raise ValueError('Existing store settings differ; do not change destinations silently')
        else:
            write_json(marker, settings)

    def before_trial(self, raw_cap=20*GIB):
        # Require headroom for the next raw file and even incompressible output.
        # The controller must separately impose raw_cap and monitor free space
        # while the benchmark is writing; this check alone cannot guarantee it.
        if shutil.disk_usage(self.raw_root).free < self.raw_floor + raw_cap:
            raise RuntimeError('NFS lacks next-trial reserve; stop before measurements')
        if shutil.disk_usage(self.archive_root).free < self.archive_floor + raw_cap + GIB:
            raise RuntimeError('Scratch lacks next-trial archive reserve; stop before measurements')

    def archive(self, trial_id, identity):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', trial_id):
            raise ValueError('Unsafe trial identifier')
        required = {'trial_id', 'measurement_status', 'application', 'variant', 'repetition',
                    'source_revision', 'binary_sha256', 'command_sha256'}
        if not required <= identity.keys() or identity['trial_id'] != trial_id or identity['measurement_status'] != 'completed':
            raise ValueError('Require completed measurement metadata and exact trial identity')
        if any(not re.fullmatch(r'[0-9a-f]{64}', identity[k]) for k in ('binary_sha256','command_sha256')):
            raise ValueError('Require actual SHA-256 identities')
        raw = self.raw_root/trial_id/'events.bin'
        receipt = self.manifest_root/(trial_id+'.json')
        dest = self.archive_root/trial_id/'events.bin.gz'
        if raw.is_symlink() or raw.resolve() != raw or not raw.is_file():
            raise ValueError('Raw trace must be a regular owned file without symlinks')
        if receipt.exists() or dest.parent.exists():
            raise FileExistsError('Trial already has outputs; retain them and recover explicitly')
        st = raw.stat()
        if st.st_size == 0 or st.st_size % 40:
            raise ValueError('Trace is empty or has partial 40-byte records')
        # Deflate can grow incompressible input; do not budget only its expected ratio.
        reserve = st.st_size + st.st_size//1000 + GIB
        if shutil.disk_usage(self.archive_root).free < self.archive_floor + reserve:
            raise RuntimeError('Insufficient scratch reserve; raw trace retained')
        dest.parent.mkdir()
        part = dest.with_suffix('.gz.part')
        record = dict(campaign=self.campaign, host=self.host, identity=identity,
                      original_raw_path=str(raw), archive_path=str(dest),
                      raw_bytes=st.st_size, started_utc=now(), status='archiving_raw_retained',
                      retention='pending_author_review_no_automatic_deletion',
                      storage_kind='scratch_only_not_independent_backup')
        write_json(receipt, record)
        try:
            h = hashlib.sha256(); allocations = frees = 0
            with raw.open('rb') as source, part.open('xb') as target:
                with gzip.GzipFile(filename='', mode='wb', fileobj=target, compresslevel=1, mtime=0) as zipped:
                    for block in iter(lambda: source.read(CHUNK), b''):
                        if len(block) % 40:
                            raise ValueError('Partial event record; raw retained')
                        kinds = block[36::40]
                        a, f = kinds.count(1), kinds.count(0)
                        if a+f != len(kinds):
                            raise ValueError('Invalid event kind; raw retained')
                        allocations += a; frees += f
                        h.update(block); zipped.write(block)
                target.flush(); os.fsync(target.fileno())
            check = hashlib.sha256(); size = 0
            with gzip.open(part, 'rb') as stream:
                for block in iter(lambda: stream.read(CHUNK), b''):
                    check.update(block); size += len(block)
            after = raw.stat()
            if (size != st.st_size or check.digest() != h.digest() or
                (after.st_ino, after.st_size, after.st_mtime_ns) != (st.st_ino, st.st_size, st.st_mtime_ns)):
                raise RuntimeError('Trace changed or independent decompression failed; raw retained')
            part.rename(dest)
            sync_directory(dest.parent)
            sync_directory(self.archive_root)
            record.update(status='verified_raw_retained', verified_utc=now(),
                          raw_sha256=h.hexdigest(), archive_sha256=sha(dest),
                          archive_bytes=dest.stat().st_size, records=size//40,
                          allocations=allocations, frees=frees)
            # Record the independently verified recovery location before deletion.
            write_json(receipt, record)
            self.inventory()
            raw.unlink()  # The one exact validated raw file; never a recursive delete.
            record.update(status='archived_raw_removed', raw_removed_utc=now())
            write_json(receipt, record)
            self.inventory()
            return record
        except BaseException as exc:
            record.update(status='interrupted_reconcile_before_resuming', error=repr(exc),
                          raw_present=raw.exists(), archive_present=dest.exists(), partial_present=part.exists())
            # Keep every file remaining; no automatic retry or archive cleanup.
            write_json(receipt, record)
            self.inventory()
            raise

    def inventory(self):
        entries = []
        for p in sorted(self.manifest_root.glob('*.json')):
            if p.name in ('store.json', 'inventory.json'):
                continue
            row = json.loads(p.read_text())
            if row.get('campaign') != self.campaign:
                raise ValueError('Unexpected manifest in store')
            archive = Path(row['archive_path'])
            present = archive.is_file()
            entries.append(dict(trial_id=row['identity']['trial_id'], manifest=str(p),
                                archive_path=str(archive), archive_present=present,
                                archive_bytes=row.get('archive_bytes'), status=row['status'],
                                retention=row['retention']))
        retained = sum(r.get('archive_bytes') or 0 for r in entries if r['archive_present'])
        completed = sum(r['status']=='archived_raw_removed' and r['archive_present'] for r in entries)
        report = dict(campaign=self.campaign, host=self.host, updated_utc=now(),
                      archive_root=str(self.archive_root), expected_traces=self.expected_traces,
                      archived_trials=completed, remaining_trials=max(0,self.expected_traces-completed),
                      retained_bytes=retained, raw_free_bytes=shutil.disk_usage(self.raw_root).free,
                      scratch_free_bytes=shutil.disk_usage(self.archive_root).free,
                      author_action='Review retained archives at campaign completion; no automatic deletion',
                      entries=entries)
        write_json(self.manifest_root/'inventory.json', report)
        return report
