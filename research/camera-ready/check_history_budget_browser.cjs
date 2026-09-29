// Replay retained data and synthetic density/churn stresses in an isolated UI.
// Synthetic histories measure UI cost; they are not paper application results.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(process.env.HEAPLENS_PLAYWRIGHT);
const evidence=process.env.HEAPLENS_EVIDENCE,tools=path.dirname(evidence);
const read=f=>JSON.parse(fs.readFileSync(f,'utf8'));
const rows=[];
async function main(){
 const browser=await chromium.launch({headless:true,executablePath:process.env.HEAPLENS_BROWSER});
 try{
  const configurations=process.env.HEAPLENS_CASES ? JSON.parse(process.env.HEAPLENS_CASES) :
   [['valkey-full',0,'retained'],['tpcc-bcco-2m',0,'retained'],
   ...[50000,100000,250000].flatMap(n=>[['tpcc-bcco-2m',n,'live'],['tpcc-bcco-2m',n,'churn']])];
  for(const [name,n,kind] of configurations){
   const common=read(path.join(tools,'budget-latency-20260928',name,'common.json'));
   const pages=read(path.join(evidence,name,'pages.json'));
   if(kind==='empty'){
    pages.page_num_events={};pages.clusters={};
    Object.assign(pages.selection,{selected_pages:0,selected_records:0,represented_clusters:0,
      omitted_types:['example omitted type'],record_budget:1});
   }
   if(n){
    const addresses=Object.keys(pages.page_num_events).map(Number),min=common.linesAndStats.minTs,max=common.linesAndStats.maxTs;
    let left=n;
    addresses.forEach((addr,p)=>{
     const count=Math.ceil(left/(addresses.length-p));left-=count;
     const type=pages.page_num_events[addr].events.find(e=>e.type)?.type||common.types[0];
     pages.page_num_events[addr].events=Array.from({length:count},(_,j)=>({file:null,line:0,
      addr:addr+j*32%2097152,actualAddr:addr+j*32%2097152,size:32,type,
      allocTs:kind==='live'?min:min+(max-min)*(j%100)/100,
      freeTs:kind==='live'?null:min+(max-min)*((j%100)+.1)/100}));
    });
    pages.selection.selected_records=n;
   }
   const palette=[...new Set([...common.types,...common.cacheData.idxToTpAndSt])]
    .map((type,i)=>({type,colour:`hsl(${i*137%360},40%,45%)`}));
   for(let rep=0;rep<Number(process.env.HEAPLENS_REPS||(n?3:1));rep++){
    console.log(JSON.stringify({start:true,name,n,kind,rep}));
    const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
    const page=await context.newPage(),errors=[],downloads=[],requests=[];
    page.on('pageerror',e=>errors.push(String(e)));page.on('download',d=>downloads.push(d));
    page.on('crash',()=>console.log(JSON.stringify({crash:true,name,n,kind,rep})));
    await page.addInitScript(()=>{window.showSaveFilePicker=undefined});
    await page.addInitScript({path:path.join(__dirname,'optimization_ui_probe.js')});
    if(!process.env.HEAPLENS_USE_HTTP) await page.route('http://localhost:5000/**',async route=>{
     const url=new URL(route.request().url());requests.push(url.pathname+url.search);
     const json=url.pathname.startsWith('/init-app/')?{...common,pagesData:pages}:
      url.pathname.startsWith('/get-pages-and-cache-data/')?{pagesData:pages,cacheData:common.cacheData}:
      url.pathname.startsWith('/log-data/get-colours/')?palette:
      url.pathname.startsWith('/log-data/get-notes/')?'':[];
     await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(json)});
    });
    await page.goto(`http://localhost:3001/vispanels?fname=${name}--128.sqlite`,{timeout:120000});
    await page.waitForFunction(()=>window.__heaplensBench?.ready,null,{timeout:120000});
    await page.waitForTimeout(200);
    assert.equal(downloads.length,0,'no automatic export');
    assert.equal(await page.locator('.pageRow').count(),Object.keys(pages.page_num_events).length);
    for(const fraction of [.25,.5,.75]){
     await page.evaluate(()=>window.__heaplensBench.action='slider');
     const geometry=await page.locator('#timeGraphSVG').evaluate(svg=>{
      const m=svg.getScreenCTM(),axis=svg.querySelector('#xAxisGroup').getScreenCTM();
      return {left:axis.e,width:+svg.querySelector('#timeGraphClipRect').getAttribute('width')*m.a};
     });
     const b=await page.locator('#timeThumb').boundingBox();
     await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();
     await page.mouse.move(geometry.left+geometry.width*fraction,b.y+b.height/2,{steps:10});await page.mouse.up();
     await page.waitForTimeout(100);
    }
    await page.evaluate(()=>window.__heaplensBench.action='idle');
    if(kind==='empty'){
     assert(await page.getByRole('button',{name:'Export 5 snapshots',exact:true}).isDisabled());
     assert((await page.getByRole('alert').filter({hasText:'Showing'}).innerText()).includes('Increase the limits'));
    }
    if(!n&&kind==='retained'){
     const downloaded=page.waitForEvent('download');
     await page.getByRole('button',{name:'Export 5 snapshots',exact:true}).click();
     await page.waitForTimeout(1000);
     console.log(JSON.stringify({exportStatus:await page.getByRole('status').allTextContents(),name}));
     const d=await downloaded;await page.getByText('Export saved.',{exact:true}).waitFor();
     const text=fs.readFileSync(await d.path(),'utf8');
     assert.equal((text.match(/^- snapshot_index:/gm)||[]).length,5);
     assert(text.includes(`TOTAL_PAGES: ${Object.keys(pages.page_num_events).length}`));
     // Cancel a second export; do not produce another partial download.
     // Deliberately slow the sink so even the small fixture stays cancellable.
     await page.evaluate(()=>{
      window.__cancelSinkAborted=false;
      window.showSaveFilePicker=async()=>({createWritable:async()=>({
       async write(){await new Promise(r=>setTimeout(r,50))}, async close(){},
       async abort(){window.__cancelSinkAborted=true}})});
     });
     await page.getByRole('button',{name:'Export 5 snapshots',exact:true}).click();
     await page.getByRole('button',{name:'Cancel export',exact:true}).click();
     await page.getByText('Export cancelled.',{exact:true}).waitFor();
     assert.equal(downloads.length,1);
     assert(await page.evaluate(()=>window.__cancelSinkAborted));
     // Exercise the direct-streaming branch with an instrumented browser sink.
     await page.evaluate(()=>{
      window.__stream={writes:0,bytes:0,closed:false,aborted:false};
      window.showSaveFilePicker=async()=>({createWritable:async()=>({
       async write(chunk){window.__stream.writes++;window.__stream.bytes+=chunk.length},
       async close(){window.__stream.closed=true},async abort(){window.__stream.aborted=true}})});
     });
     await page.getByRole('button',{name:'Export 5 snapshots',exact:true}).click();
     await page.getByText('Export saved.',{exact:true}).waitFor();
     const stream=await page.evaluate(()=>window.__stream);
     assert(stream.closed&&!stream.aborted&&stream.writes>1);
     // Settings are user-editable and propagated on resample (HTTP validation
     // and production selector forwarding are checked by the Python tests).
     await page.locator('button').filter({has:page.locator('[data-testid="SettingsIcon"]')}).click();
     await page.getByLabel('Maximum pages',{exact:true}).fill('80');
     await page.getByLabel('Maximum history records',{exact:true}).fill('50000');
     await page.keyboard.press('Escape');
     await page.locator('button').filter({has:page.locator('[data-testid="CachedIcon"]')}).click();
     await page.waitForTimeout(400);
     assert(requests.some(r=>r.startsWith('/get-pages-and-cache-data/')&&r.includes('page_budget=80&record_budget=50000')));
    }
    await page.screenshot({path:path.join(evidence,`${name}-${kind}-${n}-${rep}.png`)});
    const metrics=await page.evaluate(()=>window.__heaplensBench);
    const row={name,kind,records:n||pages.selection.selected_records,rep,
     transport:process.env.HEAPLENS_USE_HTTP?'http':'playwright-route',browser:browser.version(),metrics,errors};
    rows.push(row);fs.appendFileSync(path.join(evidence,'browser.jsonl'),JSON.stringify(row)+'\n');
    console.log(JSON.stringify({name,kind,n,rep,ready:metrics.ready,errors}));
    assert.equal(errors.length,0);
    await context.close();
   }
  }
 }finally{await browser.close()}
 const functional=rows.some(r=>r.kind==='retained');
 fs.writeFileSync(path.join(evidence,(functional?'browser-checks':'browser-stress-checks')+'.json'),JSON.stringify({runs:rows.length,no_automatic_download:true,
  five_snapshots:functional,cancel:functional,stream_sink:functional,settings_forwarded:functional,errors:0},null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1});
