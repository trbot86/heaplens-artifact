// Run in the pinned UI environment. Optional HEAPLENS_BASELINE supplies an
// unchanged checkout for comparisons with the actual previous UI helper.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
let ts;try{ts=require('typescript')}catch{ts=require('/opt/heaplens-ui/node_modules/typescript')}
const root=path.resolve(__dirname,'../..'),file=path.join(root,'sifter_vis_d3/sifter/src/app/ui/currentBucket.ts');
const program=ts.createProgram([file],{noEmit:true,strict:true,skipLibCheck:true,types:[],target:ts.ScriptTarget.ES2020});
const diagnostics=ts.getPreEmitDiagnostics(program);
assert.equal(diagnostics.length,0,ts.formatDiagnosticsWithColorAndContext(diagnostics,{getCurrentDirectory:()=>root,getCanonicalFileName:x=>x,getNewLine:()=>"\n"}));
const exportsObject={};new Function('exports',ts.transpileModule(fs.readFileSync(file,'utf8'),
 {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText)(exportsObject);
const {getSlotDataAtBucket,getCacheTotalsAtBucket}=exportsObject;
function reference(events,addr,size,slots,buckets,getBucket,visible){
 const out=Array.from({length:buckets+2},()=>Array(slots).fill(0));
 for(const e of events){
  if(!e.type||!visible[e.type])continue;const a=e.actualAddr?e.actualAddr:e.addr;
  if(Math.floor(a/size)!==Math.floor(addr/size))continue;
  const slot=Math.floor((a%size)/Math.floor(size/slots));
  out[getBucket(e.allocTs)][slot]+=e.size;
  if(e.freeTs)out[getBucket(e.freeTs)][slot]-=e.size;
 }
 for(let b=1;b<out.length;b++)for(let s=0;s<slots;s++)out[b][s]+=out[b-1][s];
 return out;
}
let old=reference;
if(process.env.HEAPLENS_BASELINE){
 const source=fs.readFileSync(path.join(process.env.HEAPLENS_BASELINE,'sifter_vis_d3/sifter/src/app/ui/pagesComponent.tsx'),'utf8');
 const start=source.indexOf('function getSlotDataPerBucket('),end=source.indexOf('\nconst SplitBlock',start);
 assert(start>=0&&end>start);
 old=new Function(ts.transpileModule(source.slice(start,end),{compilerOptions:{target:ts.ScriptTarget.ES2020}}).outputText+'\nreturn getSlotDataPerBucket;')();
}
let seed=47;const rnd=n=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed%n};
let checks=0;
for(const size of [4096,2097152])for(let trial=0;trial<60;trial++){
 const buckets=20,page=7*size,getBucket=t=>Math.ceil(t/5),mask={A:true,B:trial%2===0};
 const events=Array.from({length:80},()=>({addr:page+rnd(size*2),actualAddr:rnd(3)?undefined:page+rnd(size),
  size:rnd(size+64),type:[null,'A','B'][rnd(3)],allocTs:rnd(106),freeTs:rnd(4)?rnd(106):null}));
 const all=old(events,page,size,128,buckets,getBucket,mask);
 for(let bucket=0;bucket<buckets+2;bucket++){
  assert.deepEqual(getSlotDataAtBucket(events,page,size,128,getBucket,mask,bucket),all[bucket]);checks++;
 }
}
for(const sets of [1,8,64])for(const types of [0,1,7]){
 const values=Array.from({length:sets*types},()=>rnd(100)-20),visible=Array.from({length:types},()=>!!rnd(2));
 const expected=values.reduce((out,v,i)=>{out[Math.floor(i/types)]+=visible[i%types]?v:0;return out},Array(sets).fill(0));
 assert.deepEqual(getCacheTotalsAtBucket(values,sets,types,visible),expected);checks++;
}
let fixtureCells=0;
if(process.env.HEAPLENS_FIXTURES){
 assert(process.env.HEAPLENS_BASELINE,'Fixture comparison requires the frozen baseline');
 const fixtures=process.env.HEAPLENS_FIXTURES;
 const cacheSource=fs.readFileSync(path.join(process.env.HEAPLENS_BASELINE,'sifter_vis_d3/sifter/src/app/ui/cacheSetComponent.tsx'),'utf8');
 const expr=cacheSource.slice(cacheSource.indexOf('return  cacheData.occ.map('),cacheSource.indexOf('}, [cacheData, visibleTypes]);'));
 const oldCache=new Function('cacheData','visibleTypes',expr);
 for(const name of ['valkey-full','tpcc-bcco-2m']){
  const common=JSON.parse(fs.readFileSync(path.join(fixtures,'budget-latency-20260928',name,'common.json')));
  const cache=common.cacheData,visible=cache.idxToTpAndSt.map(()=>true);
  for(const mask of [visible,visible.map((_,i)=>i%3!==0)]){
   const all=oldCache(cache,mask);
   for(let b=0;b<all.length;b++){
    assert.deepEqual(getCacheTotalsAtBucket(cache.occ[b],cache.numSets,cache.idxToTpAndSt.length,mask),all[b]);
    fixtureCells+=cache.numSets;
   }
  }
  if(name==='tpcc-bcco-2m')for(const budget of [17,128]){
   const pages=JSON.parse(fs.readFileSync(path.join(fixtures,'cluster-first-20260928',name,`pages-${budget}.json`))).page_num_events;
   const mask=Object.fromEntries(common.types.map(t=>[t,true]));
   const getBucket=t=>Math.ceil((t-common.linesAndStats.minTs)/Math.max(Math.floor((common.linesAndStats.maxTs-common.linesAndStats.minTs)/2000),1));
   for(const visible of [mask,{...mask,itemid_t:false}])for(const [addr,p] of Object.entries(pages)){
    const all=old(p.events,+addr,2097152,128,2000,getBucket,visible);
    for(let b=0;b<2002;b++){
     assert.deepEqual(getSlotDataAtBucket(p.events,+addr,2097152,128,getBucket,visible,b),all[b]);
     fixtureCells+=128;
    }
   }
  }
 }
}
console.log(JSON.stringify({strict_typecheck:true,equal_output_cases:checks,fixture_cells_checked:fixtureCells}));
