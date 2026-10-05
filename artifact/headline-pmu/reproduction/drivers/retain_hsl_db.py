"""Verified HSL database retention. Caller holds campaign lock between trials."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import fcntl, hashlib, json, os, re, shutil, subprocess, tarfile
from pathlib import Path
from trace_store import sha, write_json, sync_directory, now
B=Path('/campaign/archive')
H=Path('/campaign/data')

def archive_db(name, *, archive_root=None, receipt_root=None):
    assert re.fullmatch(r'paper-rocks-hsl-(before|after)-(plain|logging)-r(0[1-9]|10)',name)
    trial=H/'rocks-paper'/name; db=trial/'db'
    assert db.resolve()==db
    assert json.loads((trial/'result.json').read_text())['measurement_status']=='completed'
    assert json.loads((trial/'persistence.json').read_text())['status']=='passed'
    root=Path(archive_root) if archive_root is not None else B/'database-archives'
    receipts=Path(receipt_root) if receipt_root is not None else H/'database-retention'
    assert root.is_absolute() and receipts.is_absolute()
    assert root.resolve()==root and receipts.resolve()==receipts
    assert root!=receipts and root not in receipts.parents and receipts not in root.parents
    assert db not in root.parents and db not in receipts.parents
    root.mkdir(exist_ok=True); receipts.mkdir(exist_ok=True)
    target=root/(name+'.tar.gz'); receipt=receipts/(name+'.json')
    if receipt.exists():
        record=json.loads(receipt.read_text())
        assert record['source']==str(db) and record['archive']==str(target)
        assert sha(target)==record['archive_sha256']
        if record['status']=='archived_source_removed':
            assert not db.exists(); return
        assert record['status']=='verified_before_source_removal'
        remove_verified(db,record,receipt); return
    assert db.is_dir() and not target.exists()
    files={}
    for p in sorted(db.rglob('*')):
        assert not p.is_symlink()
        if p.is_file(): files[str(p.relative_to(db))]={'bytes':p.stat().st_size,'sha256':sha(p)}
        else: assert p.is_dir()
    total=sum(v['bytes'] for v in files.values()); assert total>0
    assert shutil.disk_usage(root).free>50*1024**3+total+1024**3
    part=target.with_suffix('.partial'); assert not part.exists()
    with tarfile.open(part,'w:gz',compresslevel=1) as t:
        for rel in files:t.add(db/rel,arcname=rel,recursive=False)
    with part.open('rb') as f:os.fsync(f.fileno())
    verified={}
    with tarfile.open(part,'r:gz') as t:
        for m in t:
            assert m.isfile() and m.name in files and m.name not in verified
            h=hashlib.sha256(); size=0
            with t.extractfile(m) as f:
                for block in iter(lambda:f.read(1048576),b''):h.update(block);size+=len(block)
            verified[m.name]={'bytes':size,'sha256':h.hexdigest()}
    assert verified==files
    for rel,meta in files.items():assert sha(db/rel)==meta['sha256']
    os.rename(part,target); sync_directory(root)
    record=dict(trial_id=name,source=str(db),archive=str(target),source_file_bytes=total,
        archive_bytes=target.stat().st_size,archive_sha256=sha(target),files=files,
        status='verified_before_source_removal',time=now(),retention='pending_author_review_no_automatic_deletion',
        storage_kind='scratch_only_not_independent_backup')
    write_json(receipt,record)
    remove_verified(db,record,receipt)

def remove_verified(db,record,receipt):
    # Container-created DB directories require their creating uid; mount only this
    # exact trial directory. Reverify every file inside that mount before unlink.
    assert db.resolve()==db and db.parent.parent==H/'rocks-paper'
    assert sha(record['archive'])==record['archive_sha256']
    paths=list(db.rglob('*'))
    assert not any(p.is_symlink() for p in paths)
    assert {str(p.relative_to(db)) for p in paths if p.is_file()}==set(record['files'])
    for rel, meta in record['files'].items():
        assert sha(db/rel)==meta['sha256']
    for rel in record['files']:(db/rel).unlink()
    for p in sorted(paths,key=lambda p:len(p.parts),reverse=True):
        if p.is_dir():p.rmdir()
    db.rmdir()
    assert not db.exists();sync_directory(db.parent)
    record['status']='archived_source_removed';write_json(receipt,record)
    receipts=receipt.parent
    rows=[json.loads(p.read_text()) for p in sorted(receipts.glob('paper-rocks-*.json'))]
    write_json(receipts/'inventory.json',dict(databases=rows,total_source_file_bytes=sum(r['source_file_bytes'] for r in rows),
        total_archive_bytes=sum(r['archive_bytes'] for r in rows),updated=now()))
    print(json.dumps({k:record[k] for k in ['trial_id','source_file_bytes','archive_bytes','status']}),flush=True)
