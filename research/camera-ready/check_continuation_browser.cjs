const path=require('path'),assert=require('assert/strict');
const {pathToFileURL}=require('url');
const {chromium}=require(process.env.HEAPLENS_PLAYWRIGHT);
async function main(){
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const page=await browser.newPage({viewport:{width:1000,height:1200}});
  await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);
  assert.equal(await page.locator('.pageContinuationMark').count(),8);
  const info=await page.locator('.pageContinuationMark').evaluateAll(nodes=>nodes.map(n=>({
   bounds:n.getBoundingClientRect().toJSON(),pointerEvents:getComputedStyle(n).pointerEvents})));
  assert(info.every(n=>n.pointerEvents==='none'));
  await page.screenshot({path:process.argv[3]});
  console.log(JSON.stringify({markers:info.length,hitTesting:'none',screenshot:process.argv[3]}));
 } finally {await browser.close()}
}
main().catch(e=>{console.error(e);process.exit(1)});
