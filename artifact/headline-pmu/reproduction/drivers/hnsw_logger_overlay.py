"""Checked two-buffer AIO plus phase reports at natural producer TLS exit."""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
from valkey_aio_overlay import transform as aio
from valkey_terminal_overlay import replace_once

def transform(text):
    text=aio(text)
    # Natural TLS teardown hands this buffer to a process-lifetime pool.
    # Pool vector growth must not append records after the captured tail length.
    text=replace_once(text,'int global_fd;',
                      'int global_fd;\nstatic thread_local bool hl_hnsw_sealed = false;')
    text=replace_once(text,'    ~ThreadExiter()\n    {',
                      '    ~ThreadExiter()\n    {\n      hl_hnsw_sealed = true;')
    text=replace_once(text,'void MemStampCollector::copy(memhook_info_t &unit_log){',
                      'void MemStampCollector::copy(memhook_info_t &unit_log){\n  if (hl_hnsw_sealed) return;')
    text=replace_once(text,'#include "aio_completion.h"',
                      '#include "aio_completion.h"\n#include "overhead-wait-probe.h"')
    text=replace_once(text,'hl_finish_aio(int index)', 'hl_finish_aio(int index, int kind=0)')
    text=replace_once(text,'return aio_suspend(list, 1, NULL);','return hl_wait(list, 1, NULL, kind);')
    text=replace_once(text,'hl_finish_aio(0);\n        hl_finish_aio(1);',
                      'hl_finish_aio(0, 1);\n        hl_finish_aio(1, 1);')
    text=replace_once(text,'hl_submitted[buffer_index] = true;',
                      'hl_submitted[buffer_index] = true;\n    ++hl_full[hl_phase];')
    text=replace_once(text,'      //close(fd);','      hl_report();\n      //close(fd);')
    return text
