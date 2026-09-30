"""Untimed explanation of base-object lifetime spans at the tested resolution."""
import argparse
import json
import math
from pathlib import Path
import sys
import numpy as np

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--root',default='/candidate')
ap.add_argument('--output',required=True)
args=ap.parse_args()
sys.path.insert(0,str(Path(args.root)/'sifter_vis_d3/server'))
from sampler import Sampler
results=[]
for name,page in [('valkey',4096),('bcco',2097152)]:
    s=Sampler(f'/inputs/{name}.sqlite',page,64,2000)
    objects=s.get_objects(s.all_data)
    width=max(math.floor(s.max_ts-s.min_ts)/2000,1)
    start=np.ceil((objects.allocTs.to_numpy(dtype=float)-s.min_ts)/width)
    free=objects.freeTs.to_numpy(dtype=float)
    end=np.where(np.isnan(free),2002,np.ceil((free-s.min_ts)/width))
    spans=end-start
    results.append(dict(case=name,base_objects=len(objects),buckets=2000,
        no_logged_free=int(np.isnan(free).sum()),same_bucket=int((spans==0).sum()),
        reversed_bucket_interval=int((spans<0).sum()),
        fraction_same_bucket=float(np.mean(spans==0)),
        fraction_spanning_at_least_1000_buckets=float(np.mean(spans>=1000)),
        mean_absolute_bucket_span=float(np.mean(np.abs(spans))),
        median_absolute_bucket_span=float(np.median(np.abs(spans))),
        note='Before cache field expansion; preserves current object reconstruction and bucket semantics.'))
Path(args.output).write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results),flush=True)
