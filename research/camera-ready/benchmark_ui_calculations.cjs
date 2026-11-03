// Offline numerical benchmark, not a browser/UI speedup claim. No UI edits.
const fs=require('fs'), assert=require('assert/strict');
const ts=require('/opt/heaplens-ui/node_modules/typescript');
const {performance}=require('perf_hooks');
const root='/baseline/sifter_vis_d3/sifter/src/app/ui/';
const source=fs.readFileSync(root+'pagesComponent.tsx','utf8');
const start=source.indexOf('function getSlotDataPerBucket(');
const end=source.indexOf('\nconst SplitBlock',start);
assert(start>=0&&end>start);
// Same JS realm for both implementations: a sandboxed VM gives the baseline
// different global lookup costs and would confound the timing comparison.
const legacySlots=new Function(ts.transpileModule(source.slice(start,end),
  {compilerOptions:{target:ts.ScriptTarget.ES2020}}).outputText+'\nreturn getSlotDataPerBucket;')();
function currentSlots(events,pageAddr,pageSize,numSlots,numBuckets,getBucketIdx,pageVis,bucketIdx){
  const ret=Array(numSlots).fill(0),slotSize=Math.floor(pageSize/numSlots);
  for(const event of events){
    if(!event.type||!pageVis[event.type])continue;
    const addr=event.actualAddr?event.actualAddr:event.addr;
    if(Math.floor(addr/pageSize)!==Math.floor(pageAddr/pageSize))continue;
    if(getBucketIdx(event.allocTs)>bucketIdx)continue;
    if(event.freeTs&&getBucketIdx(event.freeTs)<=bucketIdx)continue;
    ret[Math.floor((addr%pageSize)/slotSize)]+=event.size;
  }
  return ret;
}
function currentCache(cache,visible,bucketIdx){
  const out=new Array(cache.numSets).fill(0),cols=cache.idxToTpAndSt.length;
  cache.occ[bucketIdx].forEach((v,i)=>{out[Math.floor(i/cols)]+=(visible[i%cols]?v:0)});
  return out;
}
// Exact reduction expression from CacheBoxArray's totalData useMemo.
const cacheSource=fs.readFileSync(root+'cacheSetComponent.tsx','utf8');
const cacheExpr=cacheSource.slice(cacheSource.indexOf('return  cacheData.occ.map('),cacheSource.indexOf('}, [cacheData, visibleTypes]);'));
assert(cacheExpr.startsWith('return  cacheData.occ.map('));
const legacyCache=new Function('cacheData','visibleTypes',cacheExpr);
const evidence='/evidence';const rows=[];
function timed(fn){const start=performance.now();const value=fn();return {ms:performance.now()-start,value};}
function median(v){v=[...v].sort((a,b)=>a-b);const mid=Math.floor(v.length/2);return v.length%2?v[mid]:(v[mid-1]+v[mid])/2;}
for(const name of ['tpcc-bcco-2m','valkey-full']){
  const common=JSON.parse(fs.readFileSync('/prior/'+name+'/common.json'));
  const min=common.linesAndStats.minTs,max=common.linesAndStats.maxTs,numBuckets=2000;
  const getBucketIdx=ts=>Math.ceil((ts-min)/Math.max(Math.floor((max-min)/numBuckets),1));
  const allTypes=Object.fromEntries(common.types.map(t=>[t,true]));
  if(name==='tpcc-bcco-2m')for(const budget of [17,256]){
    const pages=JSON.parse(fs.readFileSync('/prior/'+name+`/pages-${budget}.json`)).page_num_events;
    const inputs=Object.entries(pages);
    let equalCells=0;
    for(const mask of [allTypes,{...allTypes,itemid_t:false}]){
      for(const [addr,p] of inputs){
        const full=legacySlots(p.events,+addr,2097152,128,2000,getBucketIdx,mask);
        for(let bucket=0;bucket<2002;bucket++){
          const point=currentSlots(p.events,+addr,2097152,128,2000,getBucketIdx,mask,bucket);
          for(let slot=0;slot<128;slot++){
            assert.equal(point[slot],full[bucket][slot]);equalCells++;
          }
        }
      }
    }
    let old=[],fast=[];
    for(let rep=0;rep<7;rep++){
      const mask=rep%2?allTypes:{...allTypes,itemid_t:false};
      const slow=()=>inputs.reduce((sum,[addr,p])=>sum+legacySlots(p.events,+addr,2097152,128,2000,getBucketIdx,mask)[500][0],0);
      const quick=()=>inputs.reduce((sum,[addr,p])=>sum+currentSlots(p.events,+addr,2097152,128,2000,getBucketIdx,mask,500)[0],0);
      let s,q;
      if(rep%2){q=timed(quick);s=timed(slow)}else{s=timed(slow);q=timed(quick)}
      assert.equal(s.value,q.value);
      if(rep){old.push(s.ms);fast.push(q.ms)}
    }
    rows.push({kind:'huge-page-slots',case:name,budget,pages:inputs.length,checked_cells:equalCells,
      old_ms:old,current_bucket_ms:fast,old_median_ms:median(old),current_bucket_median_ms:median(fast)});
  }
  const cache=common.cacheData,visible=cache.idxToTpAndSt.map(()=>true);
  for(const mask of [visible,visible.map((_,i)=>i%3!==0)]){
    const full=legacyCache(cache,mask);
    for(let bucket=0;bucket<cache.occ.length;bucket++){
      const point=currentCache(cache,mask,bucket);
      for(let set=0;set<cache.numSets;set++)assert.equal(point[set],full[bucket][set]);
    }
  }
  let old=[],fast=[];
  for(let rep=0;rep<7;rep++){
    let s,q;
    const slow=()=>legacyCache(cache,visible)[500],quick=()=>currentCache(cache,visible,500);
    if(rep%2){q=timed(quick);s=timed(slow)}else{s=timed(slow);q=timed(quick)}
    assert.deepEqual(Array.from(s.value),q.value);
    if(rep){old.push(s.ms);fast.push(q.ms)}
  }
  rows.push({kind:'cache-visible-type-totals',case:name,checked_cells:2*cache.occ.length*cache.numSets,
    old_ms:old,current_bucket_ms:fast,old_median_ms:median(old),current_bucket_median_ms:median(fast)});
}
fs.writeFileSync(evidence+'/ui-computation-same-realm.json',JSON.stringify({node:process.version,
  methodology:'Same JS realm for both implementations. Original TypeScript helper/reduction extracted from main; current-bucket candidates are offline only. Two masks, every bucket, every slot/set checked.',rows},null,2));
console.log(JSON.stringify(rows,null,2));
