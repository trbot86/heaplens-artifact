"""Mechanical test-copy preparation; never edits either source checkout."""
from pathlib import Path
for variant in ('baseline','optimized'):
    root=Path('/study')/variant/'sifter_vis_d3/sifter'
    page=root/'src/app/vispanels/page.tsx'
    text=page.read_text()
    assert 'const INIT_PAGE_SIZE = 4096;' in text
    page.write_text(text.replace('const INIT_PAGE_SIZE = 4096;',
        "const INIT_PAGE_SIZE = typeof window !== 'undefined' && window.location.search.includes('tpcc-bcco-2m') ? 2097152 : 4096;"))
    (root/'node_modules').symlink_to('/opt/heaplens-ui/node_modules')
