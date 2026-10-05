"""Add and validate HSL endpoint reports without changing native Stats methods."""
import hashlib
import json
from pathlib import Path
import re
import shutil

# Pinned historical source after the artifact's existing historical patch.
SOURCE_SHA256 = '075dbe3f437837c14855759d9e421b4bf51db9d00f190743255a6aa3d3d663e1'
NATIVE_METRIC = 'reader operations per native mixed-workload completion interval'


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected db_bench timing anchor: ' + old[:80])
    return text.replace(old, new, 1)


def patch(text):
    if hashlib.sha256(text.encode()).hexdigest() != SOURCE_SHA256:
        raise ValueError('Unexpected or already patched db_bench source')
    text = once(text, '#include <cinttypes>',
                '#include <cinttypes>\n#include <sys/syscall.h>\n#include "hsl_timing.h"')
    text = once(text, '  void SetId(int id) { id_ = id; }',
                '  HlHslSample HlTimingSnapshot() const {\n'
                '    return {start_, finish_, done_, exclude_from_merge_};\n  }\n\n'
                '  void SetId(int id) { id_ = id; }')
    text = once(text, '    Benchmark* bm;\n    SharedState* shared;',
                '    Benchmark* bm;\n    long hl_os_tid;\n    SharedState* shared;')
    text = once(text, '    ThreadArg* arg = static_cast<ThreadArg*>(v);',
                '    ThreadArg* arg = static_cast<ThreadArg*>(v);\n'
                '    arg->hl_os_tid = syscall(SYS_gettid);  // before the start barrier')
    return once(text, '    merge_stats.Report(name);\n', '''    merge_stats.Report(name);
    // Additive reporting after native accounting; no new hot-path clocks.
    if (name.ToString() == "readwhilewriting") {
      HlHslTiming timing;
      for (int i = 0; i < n; ++i) {
        const auto sample = arg[i].thread->stats.HlTimingSnapshot();
        timing.Add(sample);
        printf("HL_HSL_WORKER {\\"logical_id\\":%d,\\"os_tid\\":%ld,"
               "\\"excluded\\":%s,\\"start_us\\":%llu,\\"finish_us\\":%llu,"
               "\\"operations\\":%llu}\\n",
               arg[i].thread->tid, arg[i].hl_os_tid, sample.excluded ? "true" : "false",
               (unsigned long long)sample.start_us, (unsigned long long)sample.finish_us,
               (unsigned long long)sample.operations);
      }
      timing.Report(merge_stats.HlTimingSnapshot());
    }
''')


def apply(work):
    source = Path(work) / 'tools/db_bench_tool.cc'
    patched = patch(source.read_text())
    header = Path(__file__).with_name('hsl_timing.h')
    shutil.copyfile(header, source.with_name(header.name))
    source.write_text(patched)
    return {'db_bench_tool_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'hsl_timing_header_sha256': hashlib.sha256(header.read_bytes()).hexdigest()}


def require(condition, message):
    if not condition:
        raise ValueError('Invalid HSL timing: ' + message)


def parse(text, workers):
    native = re.findall(r'^readwhilewriting\s*:\s*[\d.]+\s+micros/op\s+(\d+)\s+'
                        r'ops/sec\s+([\d.]+)\s+seconds\s+(\d+)\s+operations;', text, re.M)
    require(len(native) == 1, 'expected one native result with count and elapsed time')
    rate, rounded_seconds, operations = int(native[0][0]), float(native[0][1]), int(native[0][2])
    rows = [json.loads(line[14:]) for line in text.splitlines() if line.startswith('HL_HSL_WORKER ')]
    reports = [json.loads(line[14:]) for line in text.splitlines() if line.startswith('HL_HSL_TIMING ')]
    require(len(rows) == workers and len(reports) == 1, 'missing or duplicate workers/report')
    require({r['logical_id'] for r in rows} == set(range(workers)), 'logical identities')
    require(len({r['os_tid'] for r in rows}) == workers, 'OS identities')
    require(all(type(r['excluded']) is bool and
                all(type(r[k]) is int and r[k] >= 0 for k in ('start_us', 'finish_us', 'operations')) and
                r['finish_us'] >= r['start_us'] and r['os_tid'] > 0 for r in rows), 'worker fields')
    readers = [r for r in rows if not r['excluded']]
    writers = [r for r in rows if r['excluded']]
    require(len(writers) == 1 and writers[0]['logical_id'] == 0 and len(readers) == workers - 1,
            'expected one excluded writer and included readers')
    s = reports[0]
    require(s['schema'] == 1, 'schema')
    for role, group in (('reader', readers), ('writer', writers)):
        expected = dict(start_us=min(r['start_us'] for r in group),
                        finish_us=max(r['finish_us'] for r in group),
                        operations=sum(r['operations'] for r in group), workers=len(group))
        require(all(s[role + '_' + k] == v for k, v in expected.items()), role + ' aggregate')
    require(s['reader_operations'] == operations > 0, 'native/reader count')
    require(s['native_start_us'] == s['reader_start_us'], 'native start')
    require(s['native_finish_us'] >= max(r['finish_us'] for r in rows), 'native finish')
    native_seconds = (s['native_finish_us'] - s['native_start_us']) / 1e6
    seconds = (s['reader_finish_us'] - s['reader_start_us']) / 1e6
    require(native_seconds > 0 and seconds > 0, 'nonpositive interval')
    require(abs(native_seconds - rounded_seconds) <= .000501, 'native elapsed rounding')
    require(rate <= operations / native_seconds < rate + 1.000001, 'native rate arithmetic')
    return dict(schema=1, native_metric=NATIVE_METRIC, native_throughput=rate,
                operation_count=operations, native_exact_elapsed_seconds=native_seconds,
                reader_only_elapsed_seconds=seconds, reader_only_throughput=operations / seconds,
                writer_elapsed_seconds=(s['writer_finish_us'] - s['writer_start_us']) / 1e6,
                writer_completion_from_reader_start_seconds=(s['writer_finish_us'] - s['reader_start_us']) / 1e6,
                writer_tail_after_readers_seconds=max(0, s['writer_finish_us'] - s['reader_finish_us']) / 1e6,
                native_post_worker_gap_seconds=(s['native_finish_us'] - max(r['finish_us'] for r in rows)) / 1e6,
                endpoints=s, workers=rows)
