// Render the actual page-card components and stylesheet, not a hand-drawn mockup.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {createRequire}=require('module');
const req=createRequire('/opt/heaplens-ui/package.json');
const ts=req('typescript'),React=req('react'),{renderToStaticMarkup}=req('react-dom/server');
const root=process.env.HEAPLENS_SOURCE_ROOT || path.resolve(__dirname,'../..');
async function main(){
 const d3=await import('/opt/heaplens-ui/node_modules/d3/src/index.js');
 const source=fs.readFileSync(path.join(root,'sifter_vis_d3/sifter/src/app/ui/pagesComponent.tsx'),'utf8');
 const ast=ts.createSourceFile('pages.tsx',source,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
 const names=['ContinuationMarks','PageObject','PageCard','HugePageCard'];
 const pieces=ast.statements.filter(n=>ts.isFunctionDeclaration(n)&&names.includes(n.name?.text));
 assert.equal(pieces.length,names.length);
 const code=pieces.map(n=>n.getText(ast)).join('\n');
 const js=ts.transpileModule(code,{compilerOptions:{jsx:ts.JsxEmit.React,module:ts.ModuleKind.CommonJS}}).outputText;
 const api={};
 new Function('exports',ts.transpileModule(fs.readFileSync(path.join(root,'sifter_vis_d3/sifter/src/app/ui/continuationEdges.ts'),'utf8'),
  {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(api);
 const cards=new Function('React','useMemo','useRef','useEffect','d3','continuationEdges',
  'PAGE_CARD_SVG_WIDTH','PAGE_CARD_SVG_HEIGHT','PAGE_CARD_BORDER_WIDTH',js+';return {PageCard,HugePageCard};')(
  React,React.useMemo,React.useRef,React.useEffect,d3,api.continuationEdges,540,50,530);
 const event=(addr,size,actualAddr,actualSize)=>({addr,size,actualAddr,actualSize,type:'Node',file:'fixture',line:1,allocTs:10,freeTs:30});
 const cases=[
  ['First fragment',0,event(4080,16,4080,4128),1],
  ['Middle fragment',4096,event(4096,4096,4080,4128),2],
  ['Last fragment',8192,event(8192,16,4080,4128),1],
  ['Exact boundaries',4096,event(4096,4096,4096,4096),0],
  ['Legacy extent unknown',4096,event(4096,4096,4080,undefined),0],
 ];
 let html='';
 const ordinary=renderToStaticMarkup(React.createElement(cards.PageCard,{addr:0,selAddr:-1,pageSize:4096,
  objectData:{events:[event(256,512,256,512),event(768,512,768,512),event(2048,1024,2048,1024)]},
  setSelPageAddr:()=>{},colourOfType:{Node:'#90c4dc'},showHot:false,pageVis:{Node:true},
  showHitm:false,perf:{},currTs:20,hitmCutoff:0}));
 html+='<section><h3>Ordinary objects (including adjacent objects of the same type)</h3>'+ordinary+'</section>';
 for(const [label,addr,ev,count] of cases){
  const markup=renderToStaticMarkup(React.createElement(cards.PageCard,{addr,selAddr:-1,pageSize:4096,
   objectData:{events:[ev]},setSelPageAddr:()=>{},colourOfType:{Node:'#90c4dc'},showHot:false,pageVis:{Node:true},
   showHitm:false,perf:{},currTs:20,hitmCutoff:0}));
  assert.equal((markup.match(/class="pageContinuationMark"/g)||[]).length,count,label);
  html+=`<section><h3>${label}</h3>${markup}</section>`;
 }
 for(const zoomedSize of [0,65536]){
  const ev=event(2097152,2097152,2097136,2097184);
  const markup=renderToStaticMarkup(React.createElement(cards.HugePageCard,{addr:2097152,selAddr:0,pageSize:2097152,
   slotSize:65536,slotData:Array(32).fill(.8),setSelPageAddr:()=>{},colourOfType:{Node:'#90c4dc'},
   zoomedSize,setZoomedSize:()=>{},selSize:0,setSelSize:()=>{},objData:{events:[ev]},zoomedAddr:2097152,
   edges:api.continuationEdges(ev,2097152,2097152)}));
  assert.equal((markup.match(/class="pageContinuationMark"/g)||[]).length,2);
  html+=`<section><h3>Huge page ${zoomedSize?'zoomed at start (far boundary outside view)':'overview'}</h3>${markup}</section>`;
 }
 const css=req('sass').compile(path.join(root,'sifter_vis_d3/sifter/src/app/ui/componentStyles.scss')).css;
 fs.writeFileSync(process.argv[2],`<!doctype html><meta charset="utf-8"><style>${css}\nbody{font:16px sans-serif;background:#fafafa;padding:20px}section{width:800px}h3{font-size:15px;margin:12px 0 0}</style>${html}`);
 console.log('Actual page-card render checks passed.');
}
main().catch(e=>{console.error(e);process.exit(1)});
