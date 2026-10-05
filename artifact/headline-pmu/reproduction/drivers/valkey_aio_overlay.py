"""Author-only checked AIO lifecycle overlay; apply before terminal overlay.

Not deployed. Supports the frozen two-buffer configuration only. This changes
logger bookkeeping and must be recorded as part of the measurement overlay.
"""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name
from valkey_terminal_overlay import replace_once


def transform(header, with_waits=False):
    header = replace_once(header, 'int global_fd;', '''int global_fd;
#include "aio_completion.h"
static thread_local bool hl_submitted[2] = {};
static void hl_finish_aio(int index) {
    if (!hl_submitted[index]) return;
    auto *request = &async_struct_array[index];
    const struct aiocb *list[1] = {request};
    auto result = hl_complete_submitted(request->aio_nbytes,
        [&]() { return aio_error(request); },
        [&]() { return aio_suspend(list, 1, NULL); },
        [&]() { return aio_return(request); });
    if (result != hl_aio_ok) _exit(94);
    hl_submitted[index] = false;
}''')
    start = header.index('        for (int i = 1; i < number_of_buffers; i++) {')
    end = header.index('        int unfilled_buffer_size', start)
    header = replace_once(header, header[start:end],
                          '        hl_finish_aio(0);\n        hl_finish_aio(1);\n\n')
    header = replace_once(header, 'if (thread_first_call) {',
                          'if (thread_first_call) {\n    if (number_of_buffers != 2) _exit(95);')
    header = replace_once(header,
                          '(struct aiocb*) malloc(sizeof(struct aiocb)*number_of_buffers)',
                          '(struct aiocb*) calloc(number_of_buffers, sizeof(struct aiocb))')
    header = replace_once(header, '''    if (aio_write(&async_struct_array[buffer_index]) != 0) {
      cout << "aio_write FAILED" << endl;
    }''', '''    if (hl_submitted[buffer_index]) _exit(96);
    if (aio_write(&async_struct_array[buffer_index]) != 0) _exit(97);
    hl_submitted[buffer_index] = true;''')
    start = header.index('    if (aio_error(&async_struct_array[buffer_index]) == EINPROGRESS){')
    end = header.index('\n  }\n}', start)
    header = replace_once(header, header[start:end], '    hl_finish_aio(buffer_index);')
    if with_waits:
        header = replace_once(header, 'hl_submitted[buffer_index] = true;',
                              'hl_submitted[buffer_index] = true;\n    ++hl_total_full_buffers;')
        header = replace_once(header, '#include "aio_completion.h"',
                              '#include "aio_completion.h"\n#include "valkey_wait_probe.h"')
        header = replace_once(header, 'hl_finish_aio(int index)',
                              'hl_finish_aio(int index, unsigned kind=0)')
        header = replace_once(header, 'return aio_suspend(list, 1, NULL);',
                              'return hl_valkey_suspend(list, 1, NULL, kind);')
        header = replace_once(header, 'hl_finish_aio(0);\n        hl_finish_aio(1);',
                              'hl_finish_aio(0, 1);\n        hl_finish_aio(1, 1);')
    return header
