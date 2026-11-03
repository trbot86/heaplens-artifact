// Reproducible local UI interactions, using a separate headless browser profile.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert/strict');
const {chromium}=require(process.env.HEAPLENS_PLAYWRIGHT);
const out=process.env.HEAPLENS_EVIDENCE||path.join(__dirname,'integrated-optimization-20260928');
const label=process.env.HEAPLENS_STUDY_LABEL||'';
const hash=x=>crypto.createHash('sha256').update(typeof x==='string'?x:JSON.stringify(x)).digest('hex');
async function settle(page){await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));await page.waitForTimeout(120)}
async function snapshot(page){return page.evaluate(()=>({
  thumb:document.querySelector('#timeThumb')?.getAttribute('cx'),
  rows:[...document.querySelectorAll('.pageRow')].map(row=>({text:row.textContent,
    rects:[...row.querySelectorAll('svg rect')].map(r=>['x','y','width','height','fill','fill-opacity','data-total-max'].map(k=>r.getAttribute(k)))})),
  cache:[...document.querySelectorAll('#cacheBoxesSVG rect')].map(r=>['x','y','fill','data-total-max'].map(k=>r.getAttribute(k)))
}))}
async function main(){
 const browser=await chromium.launch({headless:true,executablePath:process.env.HEAPLENS_BROWSER});
 const rows=[],cases=process.env.HEAPLENS_BROWSER_CASES?JSON.parse(process.env.HEAPLENS_BROWSER_CASES):[['valkey-full',52,'robj'],['tpcc-bcco-2m',17,'itemid_t'],['tpcc-bcco-2m',128,'itemid_t']];
 const positions=JSON.parse(process.env.HEAPLENS_SLIDER_POSITIONS||'[0.9,0.5,0.9]');
 try{
  for(const policy of ['baseline','optimized']){
   const p=await browser.newPage();await p.goto(`http://localhost:${policy==='baseline'?3000:3001}/vispanels?fname=valkey-full--52.sqlite`,{timeout:120000});
   await p.locator('#timeThumb').waitFor({timeout:60000});await p.waitForTimeout(500);await p.close();
  }
  for(const [name,budget,type] of cases)for(let rep=0;rep<3;rep++)for(const policy of (rep%2?['optimized','baseline']:['baseline','optimized'])){
   const context=await browser.newContext({viewport:{width:1280,height:720},acceptDownloads:true});
   const page=await context.newPage(),errors=[],downloads=[],states=[];
   page.on('pageerror',e=>errors.push(String(e)));page.on('download',d=>downloads.push(d));
   await page.addInitScript({path:path.join(__dirname,'optimization_ui_probe.js')});
   const port=policy==='baseline'?3000:3001;
   console.log(JSON.stringify({start:true,name,budget,rep,policy}));
   await page.goto(`http://localhost:${port}/vispanels?fname=${name}--${budget}.sqlite`,{waitUntil:'domcontentloaded',timeout:60000});
   await page.waitForFunction(()=>window.__heaplensBench?.ready,{},{timeout:60000});await settle(page);
   assert.equal(await page.locator('.pageRow').count(),budget);
   async function action(label,fn){
    await page.evaluate(label=>window.__heaplensBench.action=label,label);await fn();await settle(page);
    states.push({label,hash:hash(await snapshot(page))});await page.evaluate(()=>window.__heaplensBench.action='idle');
   }
   states.push({label:'initial',hash:hash(await snapshot(page))});
   for(const [i,fraction] of positions.entries())await action(`slider-${i}`,async()=>{
    const geometry=await page.locator('#timeGraphSVG').evaluate(svg=>{
     const thumb=svg.querySelector('#timeThumb'),clip=svg.querySelector('#timeGraphClipRect');
     const m=svg.getScreenCTM();const p=new DOMPoint(+thumb.getAttribute('cx'),0).matrixTransform(m);
     // Source bounds: the y-axis strip is 50 SVG units; observed clip width
     // supplies the plotting width. Read the rendered x-axis start below.
     const axis=svg.querySelector('#xAxisGroup').getScreenCTM();
     return {left:axis.e,width:+clip.getAttribute('width')*m.a};
    });
    const start=await page.locator('#timeThumb').boundingBox();
    await page.mouse.move(start.x+start.width/2,start.y+start.height/2);await page.mouse.down();
    await page.mouse.move(geometry.left+geometry.width*fraction,start.y+start.height/2,{steps:20});await page.mouse.up();
   });
   // Expand the visibility controls via the actual header, discovered from DOM.
   await page.locator('thead button.centerTableCell').click();
   await settle(page);
   for(const family of ['page','cache'])for(let i=0;i<2;i++)await action(`${family}-visibility-${i}`,()=>page.locator(`[id="${family}-vis-${type}"]`).click());
   await action('filter',()=>page.locator('#typeFilter').fill(type));
   await action('clear-filter',()=>page.locator('#typeFilter').fill(''));
   await action('scroll',async()=>{await page.locator('.pageRow').first().hover();await page.mouse.wheel(0,450)});
   await page.screenshot({path:path.join(out,`${label}${name}-${budget}-${policy}-${rep}.png`)});
   const exported=[];for(const d of downloads){const p=await d.path();exported.push({name:d.suggestedFilename(),sha256_excluding_generated_at:hash(fs.readFileSync(p,'utf8').replace(/^GENERATED_AT:.*$/m,'GENERATED_AT: <normalized>'))})}
   const metrics=await page.evaluate(()=>window.__heaplensBench);
   const row={name,budget,rep,policy,positions,browser:browser.version(),metrics,states,exports:exported,errors};
   rows.push(row);fs.appendFileSync(path.join(out,label+'browser.jsonl'),JSON.stringify(row)+'\n');
   console.log(JSON.stringify({done:true,name,budget,rep,policy,ready:metrics.ready,errors}));
   await context.close();
  }
 }finally{await browser.close()}
 for(const [name,budget] of cases)for(let rep=0;rep<3;rep++){
  const pair=rows.filter(r=>r.name===name&&r.budget===budget&&r.rep===rep);
  assert.deepEqual(pair[0].states,pair[1].states,`Rendered state differs: ${name}/${budget}/${rep}`);
  assert.deepEqual(pair[0].exports,pair[1].exports,`Export differs: ${name}/${budget}/${rep}`);
  assert.equal(pair[0].errors.length+pair[1].errors.length,0);
 }
 fs.writeFileSync(path.join(out,label+'browser-equality.json'),JSON.stringify({paired_trials:3*cases.length,states_equal:true,exports_equal:true,page_errors:0},null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1});
