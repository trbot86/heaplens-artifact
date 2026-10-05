"""Check separate October 5 validation rows without launching measurements."""
from pathlib import Path
import hashlib,json,sys,tarfile
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
import metrics
for name,expected in metrics.read(HERE/'manifest.json').items():
    if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=expected:raise ValueError('Changed validation evidence: '+name)
for stage in ('backend','backend-current','ui-toggle','ui-toggle-current','ui-detail','ui-detail-current'):
    expected=metrics.read(HERE/(stage+'-source-snapshot.json'))['files']
    seen=set()
    with tarfile.open(HERE/(stage+'-source-snapshot.tar.gz')) as archive:
        for member in archive:
            if not member.isfile() or member.name not in expected or member.name in seen:raise ValueError('Unexpected source snapshot member')
            if hashlib.sha256(archive.extractfile(member).read()).hexdigest()!=expected[member.name]:raise ValueError('Source snapshot mismatch')
            seen.add(member.name)
    if seen!=set(expected):raise ValueError('Incomplete source snapshot')
actual={
 'backend':metrics.backend(metrics.read(HERE/'backend.json')),
 'backend-current':metrics.backend_current(metrics.read(HERE/'backend-current.json')),
 'ui-toggle':metrics.toggle(metrics.jsonlines(HERE/'ui-toggle.jsonl')),
 'ui-toggle-current':metrics.toggle(metrics.jsonlines(HERE/'ui-toggle-current.jsonl'),('optimized',)),
 'ui-detail':metrics.detail(metrics.jsonlines(HERE/'ui-detail-baseline.jsonl'),metrics.jsonlines(HERE/'ui-detail-optimized.jsonl')),
 'ui-detail-current':metrics.detail(None,metrics.jsonlines(HERE/'ui-detail-current-optimized.jsonl'))}
if actual!=metrics.read(HERE/'summary.json'):raise ValueError('Validation summary differs from individual rows')
for case in ('valkey','bcco'):
    fresh=[r for r in metrics.read(HERE/'backend.json') if r['case']==case]
    old=[r for r in metrics.read(HERE.parent/'saved/backend.json') if r['case']==case]
    current=[r for r in metrics.read(HERE/'backend-current.json') if r['case']==case]
    if {r['payload_sha256'] for r in fresh}!={r['payload_sha256'] for r in old}:raise ValueError('Frozen backend differs from historical output')
    if {r['cache_sha256'] for r in fresh}!={r['cache_sha256'] for r in current}:raise ValueError('Current cache output differs')
historical=metrics.jsonlines(HERE.parent/'saved/toggle.jsonl')
for row in metrics.jsonlines(HERE/'ui-toggle.jsonl'):
    old=next(r for r in historical if all(r[k]==row[k] for k in ('name','budget','rep','policy')))
    if row['states']!=old['states'] or row['exports']!=old['exports']:raise ValueError('Frozen UI differs from historical states/exports')
print(json.dumps(dict(status='passed',results=actual),indent=2))
