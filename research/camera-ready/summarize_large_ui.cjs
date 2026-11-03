const fs=require('fs'),path=require('path');
const [input,output]=process.argv.slice(2);
const rows=fs.readFileSync(input,'utf8').trim().split('\n').map(JSON.parse)
  .filter(x=>x.checkpoint==='final'&&x.rep>=0);
const median=a=>{const s=[...a].sort((a,b)=>a-b);return s.length?s.length%2?s[(s.length-1)/2]:(s[s.length/2-1]+s[s.length/2])/2:null};
const quantile=(a,q)=>{const s=[...a].sort((a,b)=>a-b);return s.length?s[Math.min(s.length-1,Math.ceil(q*s.length)-1)]:null};
const tests={slider:[/^slider-/, 'pointermove'],page_visibility:[/^page-visibility-/,'click'],
 cache_visibility:[/^cache-visibility-/,'click'],filter:[/^(filter|clear-filter)$/,'input'],
 scroll:[/^scroll$/,'wheel'],brush:[/^brush-64k$/,'pointerup'],zoom_in:[/^zoom-in$/,'click'],zoom_out:[/^zoom-out$/,'click']};
const result={metric:'Input-handler entry to second animation-frame callback; not compositor-present latency',
 aggregation:'Median of within-trial medians; trial counts are recorded per case. P95 is the median of within-trial nearest-rank p95 values.',cases:[]};
for(const name of [...new Set(rows.map(x=>x.name))]){
 const rr=rows.filter(x=>x.name===name), complete=rr.filter(x=>x.status==='complete');
 const entry={name,trials:rr.length,complete:complete.length,failures:rr.filter(x=>x.failure).map(x=>x.failure),
  uncaught_errors:rr.flatMap(x=>x.errors),ready_ms:median(complete.map(x=>x.ready.ms)),
  initial_heap_mib:median(complete.map(x=>x.initial.heap_used/2**20)),
  initial_elements:median(complete.map(x=>x.initial.ui.elements)),actions:{}};
 for(const [label,[re,eventType]] of Object.entries(tests)){
  const per=complete.map(r=>{
   const actions=r.actions.filter(x=>re.test(x.label));
   const events=actions.flatMap(a=>a.events).filter(e=>e.kind==='response'&&e.type===eventType).map(e=>e.ms);
   return {rep:r.rep,event_count:events.length,median_ms:median(events),p95_ms:quantile(events,.95),
    max_ms:events.length?Math.max(...events):null,controller_ms:median(actions.map(a=>a.controller_ms)),
    max_sampled_heap_mib:Math.max(...actions.map(a=>a.state.heap_used/2**20)),
    max_elements:Math.max(...actions.map(a=>a.state.ui.elements)),
    max_detail_rects:Math.max(...actions.map(a=>a.state.ui.detailRects))};
  });
  entry.actions[label]={median_ms:median(per.map(p=>p.median_ms)),p95_ms:median(per.map(p=>p.p95_ms)),
   max_ms:per.length?Math.max(...per.map(p=>p.max_ms)):null,controller_ms:median(per.map(p=>p.controller_ms)),
   max_sampled_heap_mib:per.length?Math.max(...per.map(p=>p.max_sampled_heap_mib)):null,
   max_elements:per.length?Math.max(...per.map(p=>p.max_elements)):null,per_trial:per};
 }
 result.cases.push(entry);
}
fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result.cases.map(c=>({name:c.name,trials:c.trials,complete:c.complete,ready_ms:c.ready_ms,
 heap_mib:c.initial_heap_mib,actions:Object.fromEntries(Object.entries(c.actions).map(([k,v])=>[k,{ms:v.median_ms,p95:v.p95_ms,heap:v.max_sampled_heap_mib}]))})),null,2));
