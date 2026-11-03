"""Install the accepted BCCO diagnostic's allocator/backing probes in a fresh copy."""
from pathlib import Path
import shutil
import sys


def apply(macrobench, variant):
    if variant not in ('baseline','segregation-only'):
        raise ValueError('Figure comparison isolates segregation only')
    main = macrobench/'system/main.cpp'
    text = main.read_text()
    if 'hl_fig9_identity(' in text:
        raise ValueError('Figure hooks are already installed')
    edits = {
        'parser(argc, argv);': 'parser(argc, argv);\n    hl_fig9_identity('+('true' if variant=='segregation-only' else 'false')+');',
        'int64_t starttime = get_server_clock();': 'hl_fig9_snapshot("measurement_start");\n    int64_t starttime = get_server_clock();',
        'int64_t endtime = get_server_clock();': 'int64_t endtime = get_server_clock();\n    hl_fig9_snapshot("measurement_end");',
    }
    for old,new in edits.items():
        if text.count(old) != 1:
            raise ValueError('TPC-C phase marker changed: '+old)
        text = text.replace(old,new)
    header = Path(__file__).with_name('bcco_figure_probe.h')
    shutil.copy2(header,macrobench/'system/bcco_figure_probe.h')
    main.write_text('#include "bcco_figure_probe.h"\n'+text)


if __name__=='__main__': apply(Path(sys.argv[1]),sys.argv[2])
