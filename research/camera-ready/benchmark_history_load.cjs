// Full database-to-UI loading through the real, research-only HTTP prep server.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {execFileSync}=require('child_process');
const {chromium}=require(process.env.HEAPLENS_PLAYWRIGHT);
const out=process.env.HEAPLENS_EVIDENCE;
fs.mkdirSync(out,{recursive:true});
const save=row=>fs.appendFileSync(path.join(out,'browser.jsonl'),JSON.stringify(row)+'\n');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function trial(name,policy,rep){
 const server=await chromium.launchServer({headless:true,executablePath:process.env.HEAPLENS_BROWSER});
 let browser,timer;
 const row={name,policy,rep,errors:[],started:new Date().toISOString()};
 const work=(async()=>{
  browser=await chromium.connect(server.wsEndpoint());row.browser=browser.version();
  const page=await browser.newPage({viewport:{width:1440,height:1000},acceptDownloads:false});
  page.on('pageerror',e=>row.errors.push(String(e)));page.on('download',()=>row.errors.push('unexpected export'));
  await page.addInitScript({path:path.join(__dirname,'optimization_ui_probe.js')});
  const cdp=await page.context().newCDPSession(page);await cdp.send('Performance.enable');
  const responses=[];
  page.on('response',response=>{if(response.url().includes('/init-app/'))responses.push(response)});
  await page.goto(`http://localhost:3003/vispanels?fname=${name}--${policy}.sqlite`,{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>window.__heaplensBench?.ready,null,{timeout:120000});
  row.ready=await page.evaluate(()=>window.__heaplensBench.ready);
  row.metrics=await page.evaluate(()=>window.__heaplensBench);
  const metrics=Object.fromEntries((await cdp.send('Performance.getMetrics')).metrics.map(x=>[x.name,x.value]));
  row.post_ready_heap_bytes=metrics.JSHeapUsedSize;
  row.dom=await cdp.send('Memory.getDOMCounters');
  assert.equal(responses.length,1,'exactly one actual database-preparation request');
  row.serverTiming=await responses[0].headerValue('server-timing');
  row.responseStatus=responses[0].status();assert.equal(row.responseStatus,200);
  row.selectionText=await page.getByText(/Showing.*history records/).textContent();
  assert(row.ready.pages>0);assert.equal(row.errors.length,0);
  if(rep===0)await page.screenshot({path:path.join(out,`${name}-${policy}.png`)});
  row.status='complete';
 })();
 try{await Promise.race([work,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('whole load trial exceeded 120 seconds')),120000)})])}
 catch(error){row.status='failed';row.error=String(error)}
 finally{
  clearTimeout(timer);
  if(browser)await Promise.race([browser.close(),delay(3000)]);
  if(process.platform==='win32'){
   execFileSync('C:/Windows/System32/taskkill.exe',['/PID',String(server.process().pid),'/T','/F'],{stdio:'pipe',timeout:15000});
  }else await server.kill();
  row.cleanup=true;save(row);
 }
 console.log(JSON.stringify({name,policy,rep,status:row.status,ready:row.ready?.ms,error:row.error}));
 assert.equal(row.status,'complete',row.error);
}
(async()=>{
 for(const name of ['valkey','tpcc-bcco-2m'])await trial(name,'reduced',-1);
 for(let rep=0;rep<3;rep++)for(const name of ['valkey','tpcc-bcco-2m'])
  for(const policy of (rep%2?['full','reduced']:['reduced','full']))await trial(name,policy,rep);
})().catch(error=>{console.error(error);process.exitCode=1});
