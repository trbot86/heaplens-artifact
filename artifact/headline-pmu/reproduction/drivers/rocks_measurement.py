"""Author-side RocksDB measurement parsing; no execution or file mutation."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
import re

def check_isl_topology(topology,allowed):
    """Require the frozen 0-19 mask to be distinct physical cores on node 0."""
    found={}
    for line in topology.splitlines():
        if not line or line.startswith('#'):continue
        cpu,node,socket,core,online=line.split(',')
        if int(cpu) in range(20):
            if node!='0' or online!='Y' or int(cpu) not in allowed:
                raise ValueError('Frozen ISL CPU mask is unavailable or not on node 0')
            found[int(cpu)]=(socket,core)
    if len(found)!=20 or len(set(found.values()))!=20:
        raise ValueError('Frozen ISL mask does not select twenty distinct physical cores')
    return sorted(found)

def parse_reader_result(text):
    matches=re.findall(
        r'^readwhilewriting\s*:\s*([\d.]+)\s+micros/op\s+(\d+)\s+ops/sec\s+'
        r'([\d.]+)\s+seconds\s+(\d+)\s+operations;',text,re.MULTILINE)
    if len(matches)!=1:
        raise ValueError('Expected exactly one readwhilewriting result with actual operation count')
    micros,rate,seconds,operations=matches[0]
    rate=int(rate);seconds=float(seconds);operations=int(operations)
    if min(rate,seconds,operations)<=0:raise ValueError('Nonpositive reader result')
    # Elapsed time is rounded to milliseconds and throughput truncated to integer.
    low=operations/(seconds+0.000501)
    high=operations/max(seconds-0.000501,1e-9)
    if rate+1<low or rate>high:raise ValueError('Reader count/rate/time are inconsistent')
    if text.count('HL_COUNTER_GATE enable')!=1 or text.count('HL_COUNTER_GATE disable')!=1:
        raise ValueError('Expected one measured counter window')
    if text.index('HL_COUNTER_GATE enable')>text.index('HL_COUNTER_GATE disable'):
        raise ValueError('Reversed counter window')
    return dict(operation_count=operations,operation_unit='reader operations',
                throughput=rate,reported_reader_elapsed_seconds=seconds,
                counter_scope='Whole db_bench process during readwhilewriting, including writer/background activity')
