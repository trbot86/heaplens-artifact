const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert/strict');
const {chromium}=require(process.env.HEAPLENS_PLAYWRIGHT);
const out=process.env.HEAPLENS_EVIDENCE||path.join(__dirname,'integrated-optimization-20260928');
const hash=x=>crypto.createHash('sha256').update(JSON.stringify(x)).digest('hex');
const pause=p=>p.waitForTimeout(300);
async function main(){
 const browser=await chromium.launch({headless:true,executablePath:process.env.HEAPLENS_BROWSER});const results=[];
 try{for(const [name,budget,tp] of [['valkey-full',52,'raxNode'],['tpcc-bcco-2m',128,'itemid_t']]){
  const states=[];
  for(const policy of ['baseline','optimized']){
   const context=await browser.newContext({viewport:{width:1280,height:720}}),p=await context.newPage();const errors=[];
   p.on('pageerror',e=>errors.push(String(e)));
   await p.goto(`http://localhost:${policy==='baseline'?3000:3001}/vispanels?fname=${name}--${budget}.sqlite`);
   await p.locator('#timeThumb').waitFor();await pause(p);
   const box=await p.locator('#timeThumb').boundingBox();
   const x=await p.locator('#timeGraphSVG').evaluate(svg=>svg.querySelector('#xAxisGroup').getScreenCTM().e + +svg.querySelector('#timeGraphClipRect').getAttribute('width')*svg.getScreenCTM().a*.3);
   await p.mouse.move(box.x+box.width/2,box.y+box.height/2);await p.mouse.down();await p.mouse.move(x,box.y+box.height/2,{steps:10});await p.mouse.up();await pause(p);
   const rendered=async()=>p.evaluate(()=>({cache:[...document.querySelectorAll('#cacheBoxesSVG rect')].map(e=>[e.getAttribute('fill'),e.getAttribute('data-total-max')]),
      selected:document.querySelector('.pageCardSelected')?.outerHTML||null,
      selectedPageLabel:document.querySelector('.pageCardSelected')?.closest('.pageRow')?.textContent||null,
      focus:[...document.querySelectorAll('#objectSVG rect')].map(e=>['x','y','width','height','fill'].map(k=>e.getAttribute(k))),
      brush:[...document.querySelectorAll('.brushGroup .selection')].map(e=>[e.getAttribute('x'),e.getAttribute('width')])}));
   const row=p.locator('tr').filter({has:p.locator('.legendText').filter({hasText:new RegExp('^'+tp+'$')})});
   assert.equal(await row.count(),1);await row.locator('.legendColumnLabel').click();await pause(p);
   const expanded=await rendered();
   const hovered=p.locator('#cacheBoxesSVG rect').first();await hovered.hover();
   await p.locator('.cacheOccTable').waitFor();const tooltip=await p.locator('.cacheOccTable').innerText();
   assert(tooltip.length>0);assert(!tooltip.includes('NaN'));await p.mouse.move(10,10);await pause(p);
   if(name==='valkey-full'){
    await p.locator('.pageCardBack').nth(1).click();await pause(p);assert.equal(await p.locator('.pageCardSelected').count(),1);
   }else{
    const overlay=await p.locator('.brushGroup .overlay').first().boundingBox();
    await p.mouse.move(overlay.x+overlay.width*.05,overlay.y+overlay.height/2);await p.mouse.down();
    await p.mouse.move(overlay.x+overlay.width*.15,overlay.y+overlay.height/2,{steps:8});await p.mouse.up();await pause(p);
    assert(await p.locator('.brushGroup .selection').first().getAttribute('width'));
   }
   const selected=await rendered();
   if(name==='valkey-full')assert.notEqual(selected.selectedPageLabel,expanded.selectedPageLabel,'Page click did not change selected page');
   await row.locator('.legendColumnLabel').click();await pause(p);
   states.push({policy,expanded:hash(expanded),tooltip,selected:hash(selected),errors});
   await p.screenshot({path:path.join(out,`features-${name}-${policy}.png`)});await context.close();
  }
  assert.deepEqual({...states[0],policy:null},{...states[1],policy:null});assert.equal(states[0].errors.length,0);
  results.push({name,budget,states,equal:true});
 }}finally{await browser.close()}
 fs.writeFileSync(path.join(out,'feature-checks.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
}
main().catch(e=>{console.error(e);process.exitCode=1});
