// Fresh isolated browser per trial; prepared data over normal HTTP, no routes.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {execFileSync}=require('child_process');
const {chromium}=require(process.env.HEAPLENS_PLAYWRIGHT);
const out=process.env.HEAPLENS_EVIDENCE;
const cases=JSON.parse(process.env.HEAPLENS_CASES||'["live100k","live250k","live1m","churn1m","dense1m"]');
fs.mkdirSync(out,{recursive:true});
const save=x=>fs.appendFileSync(path.join(out,'browser.jsonl'),JSON.stringify(x)+'\n');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function trial(name,rep){
 const heapLimit=process.env.HEAPLENS_JS_HEAP_MB||'2048';
 const server=await chromium.launchServer({headless:true,executablePath:process.env.HEAPLENS_BROWSER,
   args:heapLimit==='default'?[]:[`--js-flags=--max-old-space-size=${Number(heapLimit)}`]});
 let stage='connect',browser,timer;
 const row={name,rep,heap_limit_mib:heapLimit,started:new Date().toISOString(),actions:[],errors:[]};
 const work=(async()=>{
  browser=await chromium.connect(server.wsEndpoint());row.browser=browser.version();
  const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:false});
  const p=await context.newPage();p.setDefaultTimeout(20000);
  p.on('pageerror',e=>row.errors.push(String(e)));p.on('crash',()=>row.errors.push('renderer crash'));
  p.on('download',()=>row.errors.push('unexpected automatic download'));
  await p.addInitScript({path:path.join(__dirname,'optimization_ui_probe.js')});
  const cdp=await context.newCDPSession(p);await cdp.send('Performance.enable');
  async function state(){
   const perf=Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(x=>[x.name,x.value]));
   return {heap_used:perf.JSHeapUsedSize,heap_total:perf.JSHeapTotalSize,
     dom:await cdp.send('Memory.getDOMCounters'),ui:await p.evaluate(()=>({
       rows:document.querySelectorAll('.pageRow').length,
       elements:document.querySelectorAll('*').length,
       detailRects:document.querySelectorAll('#objectSVG rect').length,
       selected_region_bytes:Math.max(0,document.querySelectorAll('#objectYAxisGridGroup .tick').length-1)*64,
       thumb:document.querySelector('#timeThumb')?.getAttribute('cx'),
       brush:[...document.querySelectorAll('.brushGroup .selection')].filter(x=>x.getAttribute('width')>0).map(x=>x.getAttribute('width')),
       zoomed:document.querySelectorAll('.zoomedHugePageCard').length}))};
  }
  stage='load';await p.goto(`http://localhost:${process.env.HEAPLENS_UI_PORT||3001}/vispanels?fname=tpcc-bcco-2m--${name}.sqlite`,{waitUntil:'domcontentloaded',timeout:60000});
  await p.waitForFunction(()=>window.__heaplensBench?.ready,null,{timeout:60000});
  await p.waitForTimeout(200);row.initial=await state();
  assert.equal(row.initial.ui.rows,name==='dense64k'?1:name==='dense1m'?16:128);
  row.ready=await p.evaluate(()=>window.__heaplensBench.ready);save({...row,checkpoint:'load'});
  async function action(label,fn){
   stage=label;await p.evaluate(s=>window.__heaplensBench.action=s,label);
   const start=performance.now();let actionTimer;
   try{await Promise.race([(async()=>{await fn();await p.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))))})(),
    new Promise((_,reject)=>{actionTimer=setTimeout(()=>reject(new Error(`interaction ${label} exceeded 30 seconds`)),30000)})]);}
   finally{clearTimeout(actionTimer)}
   const controller_ms=performance.now()-start;
   await p.waitForTimeout(150);
   const metrics=await p.evaluate(()=>{const b=window.__heaplensBench;b.action='idle';return b.events});
   row.actions.push({label,controller_ms,state:await state(),events:metrics.filter(e=>e.action===label)});
   save({name,rep,checkpoint:label,action:row.actions.at(-1)});
  }
  for(const [i,fraction] of [.25,.5,.75].entries())await action(`slider-${i}`,async()=>{
   const geo=await p.locator('#timeGraphSVG').evaluate(svg=>({left:svg.querySelector('#xAxisGroup').getScreenCTM().e,
     width:+svg.querySelector('#timeGraphClipRect').getAttribute('width')*svg.getScreenCTM().a}));
   const box=await p.locator('#timeThumb').boundingBox();
   await p.mouse.move(box.x+box.width/2,box.y+box.height/2);await p.mouse.down();
   await p.mouse.move(geo.left+geo.width*fraction,box.y+box.height/2,{steps:10});await p.mouse.up();
  });
  assert.notEqual(row.initial.ui.thumb,row.actions.at(-1).state.ui.thumb);
  await p.locator('thead button.centerTableCell').click();await p.waitForTimeout(200);
  for(const family of ['page','cache'])for(let i=0;i<2;i++)await action(`${family}-visibility-${i}`,()=>p.locator(`[id="${family}-vis-char"]`).click());
  await action('filter',()=>p.locator('#typeFilter').fill('char'));
  await action('clear-filter',()=>p.locator('#typeFilter').fill(''));
  await action('scroll',async()=>{await p.locator('.pageRow').first().hover();await p.mouse.wheel(0,450)});
  await p.locator('.pageRow').first().scrollIntoViewIfNeeded();await p.waitForTimeout(200);
  await action('brush-64k',async()=>{
   if(process.env.HEAPLENS_EXACT_REGION_BYTES){
    const wanted=Number(process.env.HEAPLENS_EXACT_REGION_BYTES);
    const g=await p.locator('.hugePageCard').first().evaluate((svg,wanted)=>{
     const slots=[...svg.querySelectorAll('.slotObject')];
     const slot=slots[0],m=slot.getScreenCTM(),inverse=m.inverse();
     const x0=+slot.getAttribute('x'),width=+slot.getAttribute('width')*slots.length;
     const left=new DOMPoint(x0,25).matrixTransform(m),right=new DOMPoint(x0+width,25).matrixTransform(m);
     const y=Math.round(left.y),snap=4096,pageBytes=2097152;
     // Use integer screen coordinates and model the actual SVG transform plus
     // 4-KiB snapping. The old overlay width included extra SVG margin.
     const points=[];
     for(let x=Math.ceil(left.x);x<right.x;x++){
      const local=new DOMPoint(x,y).matrixTransform(inverse);
      points.push({x,offset:Math.round((local.x-x0)/width*pageBytes/snap)*snap});
     }
     for(const start of points.filter(x=>x.offset>=65536)){
      const end=points.find(x=>x.x>start.x&&x.offset-start.offset===wanted);
      if(end)return {start:start.x,end:end.x,y,startOffset:start.offset,endOffset:end.offset};
     }
     throw new Error('No integer-pixel gesture matches requested byte range');
    },wanted);
    row.selectionGesture={...g,requestedBytes:wanted};
    await p.mouse.move(g.start,g.y);await p.mouse.down();
    await p.mouse.move(g.end,g.y,{steps:4});await p.mouse.up();
    return;
   }
   const b=await p.locator('.brushGroup .overlay').first().boundingBox();
   // Start inside the SVG clip region, not its clipped left margin.
   await p.mouse.move(b.x+b.width*.05,b.y+b.height/2);await p.mouse.down();
   await p.mouse.move(b.x+b.width*(.05+1/32),b.y+b.height/2,{steps:4});await p.mouse.up();
  });
  assert(row.actions.at(-1).state.ui.brush.length>0,'brush must select a region');
  if(process.env.HEAPLENS_EXACT_REGION_BYTES)
   assert.equal(row.actions.at(-1).state.ui.selected_region_bytes,Number(process.env.HEAPLENS_EXACT_REGION_BYTES),'actual selected byte range');
  if(process.env.HEAPLENS_EXPECT_DETAIL_RECTS)
   assert.equal(row.actions.at(-1).state.ui.detailRects,Number(process.env.HEAPLENS_EXPECT_DETAIL_RECTS),'expected object and clip rectangle count');
  if(['dense64k','dense1m','live1m'].includes(name))
   assert(row.actions.at(-1).state.ui.detailRects>2,'populated region must render objects');
  await action('zoom-in',()=>p.locator('[data-testid="ZoomInMapIcon"]').click());
  assert.equal(row.actions.at(-1).state.ui.zoomed,1);
  await action('zoom-out',()=>p.locator('[data-testid="ZoomOutMapIcon"]').click());
  assert.equal(row.actions.at(-1).state.ui.zoomed,0);
  await p.screenshot({path:path.join(out,`${name}-${rep}.png`)});
  row.metrics=await p.evaluate(()=>window.__heaplensBench);row.status='complete';
 })();
 try{await Promise.race([work,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('trial exceeded 180 seconds')),180000)})])}
 catch(e){row.status='failed';row.failure={stage,message:String(e)}}
 finally{clearTimeout(timer);save({...row,checkpoint:'final'});console.log(JSON.stringify({name,rep,status:row.status,ready:row.ready,failure:row.failure,errors:row.errors}));
  if(browser)await Promise.race([browser.close(),delay(3000)]);
  if(process.platform==='win32'){
   // BrowserServer.kill() left private browser trees alive on this host.
   // Kill only the PID returned by this trial's launchServer, never a name.
   const pid=server.process().pid;
   execFileSync('C:/Windows/System32/taskkill.exe',['/PID',String(pid),'/T','/F'],{stdio:'pipe',timeout:15000});
   save({name,rep,checkpoint:'cleanup',browser_pid:pid,killed:true});
  }else await server.kill();
 }
}
(async()=>{
 // One discarded browser trial warms the development route and fixture.
 if(process.env.HEAPLENS_WARMUP!=='0')await trial('live100k',-1);
 for(let rep=0;rep<Number(process.env.HEAPLENS_REPS||3);rep++)for(const name of (rep%2?[...cases].reverse():cases))await trial(name,rep+Number(process.env.HEAPLENS_REP_OFFSET||0));
})().then(()=>process.exit(0)).catch(e=>{console.error(e);process.exit(1)});
