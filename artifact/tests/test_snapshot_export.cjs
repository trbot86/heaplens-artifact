// Run with node in the pinned artifact image (no frontend server required).
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
let ts;try{ts=require('typescript')}catch{ts=require('/opt/heaplens-ui/node_modules/typescript')}
const root=path.resolve(__dirname,'../..');
const file=path.join(root,'sifter_vis_d3/sifter/src/app/ui/snapshotExport.ts');
const program=ts.createProgram([file],{noEmit:true,strict:true,skipLibCheck:true,types:[],target:ts.ScriptTarget.ES2020});
assert.equal(ts.getPreEmitDiagnostics(program).length,0,
 ts.formatDiagnosticsWithColorAndContext(ts.getPreEmitDiagnostics(program),{getCurrentDirectory:()=>root,getCanonicalFileName:x=>x,getNewLine:()=> '\n'}));
const api={};new Function('exports',ts.transpileModule(fs.readFileSync(file,'utf8'),
 {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText)(api);
const {writePageSnapshots,openSnapshotSink,DOWNLOAD_LIMIT_BYTES}=api;
function sink(){return {chunks:[],closed:false,aborted:false,async write(c){this.chunks.push(c)},
 async close(){this.closed=true},async abort(){this.aborted=true;this.chunks=[]},
 text(){return Buffer.concat(this.chunks.map(c=>Buffer.from(c))).toString()}}}
async function main(){
 const event=(allocTs,freeTs,type='A')=>({allocTs,freeTs,type,addr:4096,size:32});
 const pages={4096:{cluster:0,events:[event(0,1),event(1,null),event(4,3),event(2,2,null)]},8192:{cluster:1,events:[]}};
 const clusters={0:{size:4,pages:[8192,4096]},1:{size:1,pages:[]}};
 const fields={A:[{name:'field',offset:0,size:8,subtype:'long'}]};
 const options={generatedAt:'2026-09-28T00:00:00.000Z'};
 const output=sink(),before=JSON.stringify({pages,clusters,fields});
 await writePageSnapshots(pages,clusters,fields,4096,output,options);
 assert(output.closed&&!output.aborted);
 assert.equal((output.text().match(/^- snapshot_index:/gm)||[]).length,5);
 assert(output.text().includes('SNAPSHOT_INTERVALS: 4'));
 assert.equal(JSON.stringify({pages,clusters,fields}),before);
 const empty=sink();await writePageSnapshots({},{},{},4096,empty);
 assert.equal((empty.text().match(/^- snapshot_index:/gm)||[]).length,1);
 assert(empty.text().includes('TOTAL_PAGES: 0'));
 const constant=sink();await writePageSnapshots({0:{cluster:0,events:[event(0,0)]}},{},{},4096,constant);
 assert.equal((constant.text().match(/^  time: 0$/gm)||[]).length,5);
 assert.equal((constant.text().match(/^    object_count: 1$/gm)||[]).length,5);
 // Compare every byte with the actual prior serializer, changing only its
 // snapshot interval constant and timestamp. This also checks free==time.
 if(process.env.HEAPLENS_BASELINE){
  const old=fs.readFileSync(path.join(process.env.HEAPLENS_BASELINE,'sifter_vis_d3/sifter/src/app/ui/pagesComponent.tsx'),'utf8');
  const part=old.slice(old.indexOf('const SNAPSHOT_INTERVALS'),old.indexOf('const SplitBlock'))
    .replace('SNAPSHOT_INTERVALS = 8','SNAPSHOT_INTERVALS = 4');
  const reference=new Function(ts.transpileModule(part,{compilerOptions:{target:ts.ScriptTarget.ES2020}}).outputText+';return buildPageSnapshotText;')();
  assert.equal(output.text(),reference(pages,structuredClone(clusters),fields,4096)
    .replace(/^GENERATED_AT:.*$/m,'GENERATED_AT: '+options.generatedAt));
 }
 const nested=sink();await writePageSnapshots(pages,{0:{size:4,pages:{page_num:[8192,4096]}}},{},4096,nested);
 assert(nested.text().includes('page_count: 2\n  pages: [4096, 8192]'));
 const unicode=sink(),long='🙂'.repeat(20000);
 await writePageSnapshots({0:{cluster:0,events:[event(0,null,long)]}},{},{},4096,unicode);
 assert.equal(unicode.text().split(long).length-1,5);
 assert(unicode.chunks.every(c=>c.length<=65536));
 // A million records reproduce the former spread-argument failure. Nothing
 // is live, so this tests history traversal without a giant test output.
 const large={0:{cluster:0,events:Array(1_000_000).fill(event(0,-1))}};
 assert.throws(()=>Math.min(...large[0].events.map(e=>e.allocTs)),RangeError);
 const largeSink=sink();let ticks=0;const timer=setInterval(()=>ticks++,1);
 await writePageSnapshots(large,{},{},2097152,largeSink);clearInterval(timer);
 assert(largeSink.closed&&ticks>0);
 const cancelled=sink(),controller=new AbortController();let progress=0;
 await assert.rejects(writePageSnapshots(large,{},{},2097152,cancelled,{signal:controller.signal,
  onProgress:()=>{if(++progress===3)controller.abort()}}),{name:'AbortError'});
 assert(cancelled.aborted&&!cancelled.closed);
 const broken=sink();broken.write=async()=>{throw Error('disk full')};
 await assert.rejects(writePageSnapshots(pages,clusters,fields,4096,broken),/disk full/);
 assert(broken.aborted&&!broken.closed);
 global.window={};let clicks=0;
 global.document={createElement:()=>({style:{},click(){clicks++}}),body:{appendChild(){},removeChild(){}}};
 const fallback=await openSnapshotSink();await fallback.write(new Uint8Array([65]));await fallback.close();
 assert.equal(clicks,1);
 const capped=await openSnapshotSink();const block=new Uint8Array(1024*1024);
 for(let i=0;i<64;i++)await capped.write(block);
 await assert.rejects(capped.write(new Uint8Array(1)),/64 MiB/);await capped.abort();assert.equal(clicks,1);
 const direct=sink();window.showSaveFilePicker=async()=>({createWritable:async()=>direct});
 assert.equal(await openSnapshotSink(),direct);
 console.log(JSON.stringify({strict_typecheck:true,format_equal:true,million_record_export:true,
  cooperative_timer_ticks:ticks,cancellation:true,write_failure:true,fallback_limit:DOWNLOAD_LIMIT_BYTES,
  nested_cluster_pages:true,input_immutable:true,unicode_chunks:true}));
}
main().catch(e=>{console.error(e);process.exitCode=1});
