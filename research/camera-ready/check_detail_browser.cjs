// Behavioral equivalence, separate from timings. Small page arrays are replayed
// with fixed palettes; both versions get byte-identical input. Compare visible
// detail screenshots, not off-screen DOM that is deliberately eliminated.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert/strict');
const {execFileSync}=require('child_process');
const {chromium}=require(process.env.HEAPLENS_PLAYWRIGHT);
const evidence=process.env.HEAPLENS_EVIDENCE,root=process.env.HEAPLENS_FIXTURE_ROOT;
fs.mkdirSync(evidence,{recursive:true});
const read=f=>JSON.parse(fs.readFileSync(f,'utf8'));
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
const delay=ms=>new Promise(r=>setTimeout(r,ms));
async function main(){
 const result=[];
 for(const name of ['valkey-full','tpcc-bcco-2m']){
  const common=read(path.join(root,'budget-latency-20260928',name,'common.json'));
  const data=read(path.join(root,'history-budget-20260928',name,'pages.json'));
  const lo=common.linesAndStats.minTs,hi=common.linesAndStats.maxTs;
  let targetAddress;
  if(name==='tpcc-bcco-2m'){
   targetAddress=Math.min(...Object.keys(data.page_num_events).map(Number));
   const page=data.page_num_events[targetAddress],base=targetAddress;
   const obj=(offset,size,type,alloc=lo,free=null,file='detail-fixture')=>({
    file,line:1,addr:base+offset,actualAddr:base+offset,size,type,allocTs:alloc,freeTs:free});
   page.events=[obj(0,2097152,'itemid_t'),obj(65536,131072,'Row_lock'),
     obj(98304,65536,'itemid_t'),obj(163840,65536,'itemid_t'),
     ...Array.from({length:400},(_,i)=>obj(102400+i*256,96,'char')),
     ...Array.from({length:16},(_,i)=>obj(106560+i*4096,64,'itemid_t')),
     obj(114720,32,'char',lo,lo+(hi-lo)/2,'old-lifetime'),
     obj(114720,32,'char',lo+(hi-lo)/2,null,'new-lifetime')];
   data.page_num_events={[base]:page};
   if(data.selection)Object.assign(data.selection,{selected_pages:1,selected_records:page.events.length});
  }else{
   const target=lo+(hi-lo)*.3;
   targetAddress=+Object.keys(data.page_num_events).find(a=>data.page_num_events[a].events.some(
    e=>e.type==='raxNode'&&e.allocTs<=target&&(e.freeTs===null||e.freeTs>=target)));
   assert(targetAddress,'retained Valkey fixture must include an active raxNode page');
  }
  const payload=JSON.stringify({...common,pagesData:data});
  const palette=[...new Set(common.types.concat(common.cacheData.idxToTpAndSt))]
    .map((type,i)=>({type,colour:`hsl(${i*137%360},40%,45%)`}));
  const paired=[];
  for(const policy of ['baseline','optimized']){
   const server=await chromium.launchServer({headless:true,executablePath:process.env.HEAPLENS_BROWSER});
   let browser;
   try{
    browser=await chromium.connect(server.wsEndpoint());
    const context=await browser.newContext({viewport:{width:1440,height:1000}});
    const p=await context.newPage(),errors=[],states=[];p.setDefaultTimeout(15000);
    p.on('pageerror',e=>errors.push(String(e)));
    await p.route('http://localhost:5000/**',async route=>{
     const url=new URL(route.request().url());
     const body=url.pathname.startsWith('/init-app/')?payload:
      url.pathname.startsWith('/log-data/get-colours/')?JSON.stringify(palette):'""';
     await route.fulfill({status:200,contentType:'application/json',body});
    });
    await p.goto(`http://localhost:${policy==='baseline'?3002:3003}/vispanels?fname=${name}--detailcheck.sqlite`,{timeout:60000});
    await p.locator('#timeThumb').waitFor();await p.waitForTimeout(400);
    async function capture(label){
     await p.mouse.move(5,5);await p.waitForTimeout(350);
     const svg=await p.locator('#objectSVG').screenshot({animations:'disabled'});
     fs.writeFileSync(path.join(evidence,`${name}-${policy}-${label}.png`),svg);
     const cache=await p.locator('#cacheBoxesSVG').evaluate(svg=>[...svg.querySelectorAll('rect')].map(r=>[r.getAttribute('fill'),r.getAttribute('data-total-max')]));
     states.push({label,detail_png:hash(svg),cache:hash(JSON.stringify(cache))});
    }
    async function slide(fraction){
     const geom=await p.locator('#timeGraphSVG').evaluate(svg=>({left:svg.querySelector('#xAxisGroup').getScreenCTM().e,
      width:+svg.querySelector('#timeGraphClipRect').getAttribute('width')*svg.getScreenCTM().a}));
     const b=await p.locator('#timeThumb').boundingBox();
     await p.mouse.move(b.x+b.width/2,b.y+b.height/2);await p.mouse.down();
     await p.mouse.move(geom.left+geom.width*fraction,b.y+b.height/2,{steps:8});await p.mouse.up();await p.waitForTimeout(250);
    }
    await slide(.3);
    if(name==='valkey-full'){
     await p.locator('.pageRow').filter({hasText:`0x${targetAddress.toString(16)}`}).locator('.pageCardBack').click();
    }else{
     const b=await p.locator('.brushGroup .overlay').first().boundingBox();
     await p.mouse.move(b.x+b.width*.05,b.y+b.height/2);await p.mouse.down();
     await p.mouse.move(b.x+b.width*(.05+1/32),b.y+b.height/2,{steps:4});await p.mouse.up();
    }
    await capture('selected');
    // Exercise actual detail zoom/pan, not merely creation of zero-height SVGs.
    await p.locator('#objectSVG').hover();await p.mouse.wheel(0,-180);await p.waitForTimeout(300);
    await capture('detail-zoom');
    const type=name==='valkey-full'?'raxNode':'itemid_t';
    const row=p.locator('tr').filter({has:p.locator('.legendText').filter({hasText:new RegExp('^'+type+'$')})});
    assert.equal(await row.count(),1);await row.locator('.legendColumnLabel').click();
    await capture('fields-expanded');
    await p.locator('thead button.centerTableCell').click();await p.waitForTimeout(200);
    await p.locator(`[id="page-vis-${type}"]`).click();await capture('type-hidden');
    await p.locator(`[id="page-vis-${type}"]`).click();await capture('type-restored');
    await p.locator('#objectSVG').hover();await p.mouse.wheel(0,80);await p.waitForTimeout(300);
    await capture('detail-pan');
    const hover=await p.locator('#objectSVG').evaluate(svg=>{
     // A <rect> inside <defs>/<clipPath> has no ordinary layout box. Transform
     // its declared SVG coordinates into screen coordinates explicitly.
     const cr=svg.querySelector('#objectLayoutClipRect'),m=svg.getScreenCTM();
     const a=new DOMPoint(+cr.getAttribute('x'),+cr.getAttribute('y')).matrixTransform(m);
     const z=new DOMPoint(+cr.getAttribute('x')+ +cr.getAttribute('width'),
       +cr.getAttribute('y')+ +cr.getAttribute('height')).matrixTransform(m);
     const clip={left:a.x,top:a.y,right:z.x,bottom:z.y};
     for(const r of [...svg.querySelectorAll('#objectGroup rect')].reverse()){
      if(getComputedStyle(r).visibility!=='visible')continue;
      const b=r.getBoundingClientRect(),x0=Math.max(b.left,clip.left),x1=Math.min(b.right,clip.right),
       y0=Math.max(b.top,clip.top),y1=Math.min(b.bottom,clip.bottom);
      if(x1-x0>2&&y1-y0>2)return {x:(x0+x1)/2,y:(y0+y1)/2};
     }return null;
    });
    assert(hover,'must have genuinely visible object geometry after detail zoom');
    await p.mouse.move(hover.x,hover.y);await p.getByRole('tooltip').waitFor();
    const tooltip=await p.getByRole('tooltip').innerText();assert(tooltip.includes('type:'));
    states.push({label:'object-tooltip',tooltip});await p.mouse.move(5,5);
    // The Valkey target was chosen for liveness at .3. Test its tooltip at
    // that time, then check the later (possibly empty) layout.
    await slide(.75);await capture('later-lifetime');
    if(name==='tpcc-bcco-2m'){
     await p.locator('[data-testid="ZoomInMapIcon"]').click();await capture('page-zoom-in');
     await p.locator('[data-testid="ZoomOutMapIcon"]').click();await capture('page-zoom-out');
    }
    assert.equal(errors.length,0);paired.push({policy,states,errors});
   }finally{
    if(browser)await Promise.race([browser.close(),delay(3000)]);
    execFileSync('C:/Windows/System32/taskkill.exe',['/PID',String(server.process().pid),'/T','/F'],{stdio:'pipe',timeout:15000});
   }
  }
  fs.writeFileSync(path.join(evidence,`${name}-states.json`),JSON.stringify(paired,null,2));
  assert.deepEqual(paired[0].states,paired[1].states,`${name}: visible detail/cache/tooltip must match`);
  result.push({name,states_equal:paired[0].states.length,page_errors:0});
 }
 fs.writeFileSync(path.join(evidence,'checks.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}
main().then(()=>process.exit(0)).catch(e=>{console.error(e);process.exit(1)});
