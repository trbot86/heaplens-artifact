const fs=require('fs'),path=require('path'),assert=require('assert/strict'),{spawnSync}=require('child_process');
const [root,output]=process.argv.slice(2),policies={},regionSizes={};
for(const policy of ['baseline','optimized']){
 const raw=path.join(root,policy,'browser.jsonl'),summary=path.join(root,policy,'summary.json');
 const parsed=fs.readFileSync(raw,'utf8').trim().split('\n').map(JSON.parse);
 const finals=parsed.filter(r=>r.checkpoint==='final');
 assert.equal(finals.length,9);assert(finals.every(r=>r.status==='complete'&&!r.errors.length));
 regionSizes[policy]=[...new Set(finals.map(r=>r.actions.find(a=>a.label==='brush-64k').state.ui.selected_region_bytes))];
 assert.equal(parsed.filter(r=>r.checkpoint==='cleanup'&&r.killed).length,9);
 const r=spawnSync(process.execPath,[path.join(__dirname,'summarize_large_ui.cjs'),raw,summary],{encoding:'utf8'});
 assert.equal(r.status,0,r.stderr);policies[policy]=JSON.parse(fs.readFileSync(summary));
}
const comparisons=policies.baseline.cases.map(before=>{
 const after=policies.optimized.cases.find(r=>r.name===before.name);
 assert.equal(before.trials,3);assert.equal(after.trials,3);
 return {name:before.name,before_load_ms:before.ready_ms,after_load_ms:after.ready_ms,
  before_brush_ms:before.actions.brush.median_ms,after_brush_ms:after.actions.brush.median_ms,
  brush_speedup:before.actions.brush.median_ms/after.actions.brush.median_ms,
  before_brush_max_sampled_heap_mib:before.actions.brush.max_sampled_heap_mib,
  after_brush_max_sampled_heap_mib:after.actions.brush.max_sampled_heap_mib,
  before_detail_rects:before.actions.brush.per_trial.map(r=>r.max_detail_rects),
  after_detail_rects:after.actions.brush.per_trial.map(r=>r.max_detail_rects)};
});
assert.deepEqual(regionSizes.baseline,regionSizes.optimized,'Selected widths differ across policies');
fs.writeFileSync(output,JSON.stringify({protocol:'Three interleaved fresh-browser pairs per fixture; default browser heap policy',
 baseline_revision:'0cdccc03f8b7b6c7419e803a9ac8c14f5a82391a',selected_region_bytes:regionSizes.baseline,comparisons,policies},null,2)+'\n');
console.log(JSON.stringify(comparisons,null,2));
