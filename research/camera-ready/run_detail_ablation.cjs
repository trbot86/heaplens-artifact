const path=require('path'),fs=require('fs'),{spawnSync}=require('child_process');
const script=path.join(__dirname,'benchmark_large_ui.cjs'),root=process.env.HEAPLENS_EVIDENCE;
const campaignDeadline=Date.now()+15*60*1000;
function run(policy,name,rep,warm=false){
 if(Date.now()>campaignDeadline)throw new Error('15-minute UI campaign budget reached; no further trials launched');
 const directory=path.join(root,warm?'warmup':policy);fs.mkdirSync(directory,{recursive:true});
 const result=spawnSync(process.execPath,[script],{stdio:'inherit',env:{...process.env,
  HEAPLENS_EVIDENCE:directory,HEAPLENS_UI_PORT:policy==='baseline'?'3002':'3003',
  HEAPLENS_CASES:JSON.stringify([name]),HEAPLENS_REPS:'1',HEAPLENS_REP_OFFSET:String(rep),
  HEAPLENS_WARMUP:'0',HEAPLENS_JS_HEAP_MB:'default',
  HEAPLENS_EXPECT_DETAIL_RECTS:process.env.HEAPLENS_EXACT_REGION_BYTES&&!warm?
    String(policy==='optimized'?Number(process.env.HEAPLENS_EXACT_REGION_BYTES)/32+2:name==='live1m'?7815:65538):''}});
 if(result.status!==0)throw new Error(`Benchmark failed: ${policy}/${name}/${rep}`);
 const last=fs.readFileSync(path.join(directory,'browser.jsonl'),'utf8').trim().split('\n').map(JSON.parse).filter(r=>r.checkpoint==='final').at(-1);
 if(last.status!=='complete'||last.errors.length)throw new Error(JSON.stringify(last.failure||last.errors));
}
for(const policy of ['baseline','optimized'])run(policy,'live100k',-1,true);
for(let rep=0;rep<3;rep++)for(const name of ['dense64k','dense1m','live1m'])
 for(const policy of (rep%2?['optimized','baseline']:['baseline','optimized']))run(policy,name,rep);
