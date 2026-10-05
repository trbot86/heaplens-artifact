"""Private headline Python/binding phase overlay; does not change workload sizes."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
from valkey_terminal_overlay import replace_once

def benchmark(text):
    text=replace_once(text,'def run_query(index, qdata, query_ids, k, threads, np):',
        'def run_query(index, qdata, query_ids, k, threads, np, measured_iteration=None):')
    text=replace_once(text,'    t0 = time.perf_counter()\n    labels, _ = index.knn_query(qdata, k=k, num_threads=threads)\n    elapsed = time.perf_counter() - t0', '''    import hnswlib
    gate = None
    if measured_iteration is not None:
        from valkey_protocol import PerfGate
        gate = PerfGate(os.environ['HL_PERF_CONTROL'], os.environ['HL_PERF_ACK'])
        hnswlib._heaplens_phase(1, measured_iteration)
        enabled = gate.transition(True)
    try:
        t0 = time.perf_counter()
        labels, _ = index.knn_query(qdata, k=k, num_threads=threads)
        elapsed = time.perf_counter() - t0
    finally:
        if gate is not None:
            try:
                disabled = gate.transition(False)
                print('HL_HNSW_WINDOW ' + json.dumps(dict(iteration=measured_iteration,
                    enable=enabled, disable=disabled)), file=sys.stderr, flush=True)
            finally:
                gate.close()
                hnswlib._heaplens_phase(2, measured_iteration)''')
    text=replace_once(text,'    for _ in range(args.iterations):\n        elapsed, recall = run_query(index, qdata, query_ids, args.k, args.threads, np)',
        '    for iteration in range(1, args.iterations + 1):\n        elapsed, recall = run_query(index, qdata, query_ids, args.k, args.threads, np, measured_iteration=iteration)')
    return text

def bindings(text):
    if 'hnsw_phase.h' in text: raise ValueError('phase overlay already applied')
    text=replace_once(text,'#include <atomic>','#include <atomic>\n#include "hnsw_phase.h"')
    text=replace_once(text,'    if (numThreads <= 0) {','    const auto hl_context = hl_hnsw_context();\n    if (numThreads <= 0) {')
    text=replace_once(text,'    if (numThreads == 1) {','    if (numThreads == 1) {\n        hl_hnsw_worker hl_worker(hl_context, 0);')
    text=replace_once(text,'            threads.push_back(std::thread([&, threadId] {',
        '            threads.push_back(std::thread([&, threadId] {\n                hl_hnsw_worker hl_worker(hl_context, threadId);')
    # This module name is fixed by the frozen Python binding.
    text=replace_once(text,'        py::module m("hnswlib");',
        '        py::module m("hnswlib");\n    m.def("_heaplens_phase", &hl_hnsw_set_phase);')
    return text
