// Pure selection tests, strict typecheck, and an independently expressed oracle.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
let ts;try{ts=require('typescript')}catch{ts=require('/opt/heaplens-ui/node_modules/typescript')}
const root=path.resolve(__dirname,'../..'),file=path.join(root,'sifter_vis_d3/sifter/src/app/ui/detailEvents.ts');
const options={noEmit:true,strict:true,skipLibCheck:true,types:[],target:ts.ScriptTarget.ES2020};
const diagnostics=ts.getPreEmitDiagnostics(ts.createProgram([file],options));
assert.equal(diagnostics.length,0,ts.formatDiagnosticsWithColorAndContext(diagnostics,
 {getCurrentDirectory:()=>root,getCanonicalFileName:x=>x,getNewLine:()=>"\n"}));
const exportsObject={};new Function('exports',ts.transpileModule(fs.readFileSync(file,'utf8'),
 {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText)(exportsObject);
const select=exportsObject.selectDetailEvents;
const event=(id,addr,size,allocTs=0,freeTs=null,type='Node',actualAddr=undefined)=>
 ({id,addr,size,allocTs,freeTs,type,actualAddr});
const visible={Node:true,Parent:true,'Field Parent':true,Hidden:false};
const fields={FieldParent:[{offset:64,size:16}]};
const expanded={FieldParent:true};
const events=[event('right',120,8),event('left',90,10),event('inside',104,4),
 event('cross-left',96,8),event('cross-right',116,8),event('enclosing',0,1000,0,null,'Parent'),
 event('future',104,4,11),event('freed',104,4,0,9),event('alloc-boundary',104,4,10),
 event('free-boundary',104,4,0,10),event('hidden',104,4,0,null,'Hidden'),
 event('unknown',104,4,0,null,null),event('zero',104,0),event('zero-out',120,0),
 event('field-crossing',64,8,0,null,'Field Parent',40)];
const before=JSON.stringify(events);
assert.deepEqual(select(events,100,20,10,visible,fields,expanded).map(e=>e.id),
 ['inside','cross-left','cross-right','enclosing','free-boundary','zero','field-crossing','alloc-boundary']);
assert.equal(JSON.stringify(events),before,'never sort or mutate the source history');
assert(!select(events,100,20,10,visible,fields,{}).some(e=>e.id==='field-crossing'));
assert.deepEqual(select(events,100,0,10,visible,fields,expanded),[]);
assert.deepEqual(select(events,100,-1,10,visible,fields,expanded),[]);
const reused=[event('old',104,8,1,5),event('new',104,8,5,9)];
assert.deepEqual(select(reused,100,20,5,visible,{},{}).map(e=>e.id),['old','new']);
assert.deepEqual(select(reused,100,20,6,visible,{},{}).map(e=>e.id),['new']);
assert.deepEqual(select([event('second',104,8,2),event('first',104,8,1),event('tie',108,8,2)],100,20,2,visible,{},{}).map(e=>e.id),['first','second','tie']);

// Oracle models existing parent/expanded-field primitive intervals, then clips
// them. Point markers from zero-sized allocations are retained in the region.
function reference(input,start,size,time,mask,fs,ex){
 if(size<=0)return [];
 return [...input].sort((a,b)=>a.allocTs-b.allocTs).filter(e=>{
  if(e.allocTs>time||!(e.freeTs===null||e.freeTs>=time)||!e.type||!mask[e.type])return false;
  const spans=[[e.addr,e.size]],tp=e.type.replace(/\s+/g,'');
  if(ex[tp])for(const f of fs[tp]||[])spans.push([(e.actualAddr?e.actualAddr:e.addr)+f.offset,f.size]);
  return spans.some(([a,n])=>n===0?a>=start&&a<start+size:
    n>0&&Math.max(a,start)<Math.min(a+n,start+size));
 });
}
let seed=61;const random=n=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed%n};
let checks=0;
for(const pageSize of [4096,2097152])for(let trial=0;trial<300;trial++){
 const page=2**46+pageSize*7,start=page+random(30)*64,size=random(12)*64,time=random(16);
 const input=Array.from({length:80},(_,id)=>event(id,page+random(70)*32,random(80)*32,
  random(16),random(3)?random(16):null,['Node','Parent','Field Parent','Hidden',null][random(5)],random(2)?page-128:undefined));
 input.push(event('outer',page-4096,2097152,0,null,'Parent'),event('inner',page+128,512,1,null,'Parent'));
 const mask={...visible,Node:!!random(2)},ex={FieldParent:!!random(2)};
 const frozen=JSON.stringify(input);
 assert.deepEqual(select(input,start,size,time,mask,fields,ex),reference(input,start,size,time,mask,fields,ex));
 assert.equal(JSON.stringify(input),frozen);checks++;
}
const dense=Array.from({length:65536},(_,i)=>event(i,2**46+i*32,32));
assert.equal(select(dense,2**46+65536,65536,0,visible,{},{}).length,2048);
assert.equal(select(dense,2**46,2097152,0,visible,{},{}).length,65536);
console.log(JSON.stringify({strict_typecheck:true,randomized_oracle_checks:checks,
 boundary_lifetime_nested_field_tests:true,source_not_mutated:true,dense_small_region:2048,dense_full_page:65536}));
