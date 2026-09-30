"""Generate a reviewed mechanical native reference only in a private snapshot."""
import argparse
import json
from pathlib import Path
import shutil
import time
from run_processing_ablations import bounded_docker, digest

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--study',type=Path,required=True)
ap.add_argument('--source',type=Path,required=True)
args=ap.parse_args()
source=args.source/'type_analysis/convert_to_db'
target=args.study/'candidate/type_analysis/convert_to_db'
shutil.copytree(source,target)
def change(path,old,new):
    text=path.read_text()
    assert text.count(old)==1,(path,old)
    path.write_text(text.replace(old,new))
p=target/'sampler.cpp'
change(p,'#include "sampler.hpp"','#include "sampler.hpp"\n#include <cstdlib>')
change(p,'    std::unordered_map<uint16_t, std::vector<int64_t>> buckets{};',
       '    const bool direct_prefix = std::string(std::getenv("HEAPLENS_DIRECT_PREFIX") ? std::getenv("HEAPLENS_DIRECT_PREFIX") : "0") == "1";\n'
       '    std::unordered_map<uint16_t, std::vector<int64_t>> buckets{};')
change(p,'            buckets[event.tindex_name][event_bucket] += event.size;',
       '            if (direct_prefix) {\n'
       '                auto& values = buckets[event.tindex_name];\n'
       '                for (size_t j = event_bucket; j < values.size(); ++j) values[j] += event.size;\n'
       '            } else buckets[event.tindex_name][event_bucket] += event.size;')
change(p,'            buckets[event.tindex_name][event_bucket] -= event.size;',
       '            if (direct_prefix) {\n'
       '                auto& values = buckets[event.tindex_name];\n'
       '                for (size_t j = event_bucket; j < values.size(); ++j) values[j] -= event.size;\n'
       '            } else buckets[event.tindex_name][event_bucket] -= event.size;')
change(p,'    for (auto& bucket : buckets) {\n        for (int i = 1;',
       '    if (!direct_prefix) for (auto& bucket : buckets) {\n        for (int i = 1;')
p=target/'main.cpp'
change(p,'#include <random>','#include <random>\n#include <chrono>')
change(p,'    Sampler s{};',
       '    const auto reconstruction_start = std::chrono::steady_clock::now();\n'
       '    Sampler s{};\n'
       '    std::cerr << "ABLATION_PHASE reconstruction " << std::chrono::duration<double>(std::chrono::steady_clock::now()-reconstruction_start).count() << "\\n";')
change(p,'    s.sample_pages_and_record_stats(page_size, num_pages_per_type,',
       '    const auto statistics_start = std::chrono::steady_clock::now();\n'
       '    s.sample_pages_and_record_stats(page_size, num_pages_per_type,')
change(p,'                                    cache_line_size, num_buckets, sample_portion);',
       '                                    cache_line_size, num_buckets, sample_portion);\n'
       '    std::cerr << "ABLATION_PHASE sampling_statistics_sql " << std::chrono::duration<double>(std::chrono::steady_clock::now()-statistics_start).count() << "\\n";')
worker='research/camera-ready/ablate_native_prefix.py'
shutil.copy2(args.source/worker,args.study/'candidate'/worker)
(args.study/'evidence/native-source.json').write_text(json.dumps({str(p.relative_to(args.study/'candidate')):digest(p)
                                    for p in target.iterdir() if p.is_file()},indent=2)+'\n')
compiler=['g++','-std=c++17','-O2']+['/candidate/type_analysis/convert_to_db/'+p.name for p in sorted(target.glob('*.cpp'))]+[
    '-lsqlite3','-lpthread','-ltbb','-o','/evidence/native-convert']
assert bounded_docker(args.study,'native-build',compiler,120)['exit_code']==0
logs=Path('/tmp/heaplens-sampling-gui-20260928-iVVPZe/work/valkey-full')
results=[]
expected=None
started=time.monotonic()
for rep in (-1,0,1,2):
    for policy in (['prefix'] if rep==-1 else (['prefix','direct'] if rep%2==0 else ['direct','prefix'])):
        if time.monotonic()-started>900:raise TimeoutError('Native campaign budget exceeded')
        label=f'native-{policy}-{rep}'
        command=['python3','/candidate/'+worker,'--policy',policy,'--output',f'/evidence/{label}.json']
        outcome=bounded_docker(args.study,label,command,300,extra_mounts=['-v',f'{logs}:/logs:ro'])
        assert outcome['exit_code']==0,label
        row=json.loads((args.study/'evidence'/(label+'.json')).read_text())
        if expected is None:expected=row['tables']
        assert row['tables']==expected,'Native logical database output changed'
        row['rep']=rep
        results.append(row)
        (args.study/'evidence/native-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'native_complete':True,'all_logical_tables_equal':True,'trials':len(results)}),flush=True)
