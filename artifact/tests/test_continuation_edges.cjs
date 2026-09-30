const fs=require('fs'),path=require('path'),assert=require('assert/strict');
let ts;try{ts=require('typescript')}catch{ts=require('/opt/heaplens-ui/node_modules/typescript')}
const root=path.resolve(__dirname,'../..'),file=path.join(root,'sifter_vis_d3/sifter/src/app/ui/continuationEdges.ts');
const options={noEmit:true,strict:true,skipLibCheck:true,types:[],target:ts.ScriptTarget.ES2020};
assert.equal(ts.getPreEmitDiagnostics(ts.createProgram([file],options)).length,0);
const out={};new Function('exports',ts.transpileModule(fs.readFileSync(file,'utf8'),
 {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(out);
for(const pageSize of [4096,2097152]){
 const start=pageSize-16,size=pageSize+32;
 for(const [page,addr,len,before,after] of [
  [0,start,16,false,true],[pageSize,pageSize,pageSize,true,true],
  [2*pageSize,2*pageSize,16,true,false]]){
  assert.deepEqual(out.continuationEdges({addr,size:len,actualAddr:start,actualSize:size},page,pageSize),{before,after});
 }
 assert.deepEqual(out.continuationEdges({addr:pageSize,size:pageSize,actualAddr:pageSize,actualSize:pageSize},pageSize,pageSize),{before:false,after:false});
 assert.deepEqual(out.continuationEdges({addr:pageSize,size:pageSize,actualAddr:start},pageSize,pageSize),{before:false,after:false});
 assert.deepEqual(out.continuationEdges({addr:pageSize,size:pageSize,actualAddr:start,actualSize:0},pageSize,pageSize),{before:false,after:false});
}
const live={addr:4096,size:4096,actualAddr:4080,actualSize:8192,type:'Node',allocTs:10,freeTs:20};
assert.deepEqual(out.visiblePageContinuation([live],4096,4096,15,{Node:true}),{before:true,after:true});
for(const [time,visible] of [[9,{Node:true}],[21,{Node:true}],[15,{Node:false}]])
 assert.deepEqual(out.visiblePageContinuation([live],4096,4096,time,visible),{before:false,after:false});
console.log('Continuation tests passed: first/middle/last fragments, exact ends, and legacy extents, at 4 KiB and 2 MiB.');
