"""Author-only terminal TLS flush transformation; not a complete Valkey overlay.

Call memhook_terminal_flush on each logging thread only after the measured
window closes and application work is quiescent. The caller must separately
verify acknowledgements from every producer before allowing process exit.
"""
from portable_runtime import cpus, node, rocks_cpus, rocks_nodes, host_name


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"expected one frozen-source anchor: {old!r}")
    return text.replace(old, new, 1)


def transform(header):
    header = replace_once(
        header, "int global_fd;",
        "int global_fd;\nthread_local bool hl_terminal_sealed = false;")
    header = replace_once(
        header, "    ~ThreadExiter()\n    {",
        "    ~ThreadExiter() { finish(); }\n"
        "    void finish()\n    {\n"
        "      if (hl_terminal_sealed) return;\n"
        "      hl_terminal_sealed = true;")
    # The memory pool retains the buffer pointer until process destruction.
    # A sealed producer must never mutate that buffer or register it twice.
    header = replace_once(
        header, "void MemStampCollector::copy(memhook_info_t &unit_log){",
        "void MemStampCollector::copy(memhook_info_t &unit_log){\n"
        "  if (hl_terminal_sealed) return;")
    return replace_once(
        header, "thread_local ThreadExiter exiter;",
        "thread_local ThreadExiter exiter;\n"
        'extern "C" void memhook_terminal_flush() { exiter.finish(); }')
