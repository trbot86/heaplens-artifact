(() => {
  const bench=window.__heaplensBench={events:[],ready:null,action:'load'};
  const add=(kind,data)=>bench.events.push({kind,action:bench.action,t:performance.now(),...data});
  addEventListener('error',e=>add('error',{message:e.message}));
  addEventListener('unhandledrejection',e=>add('rejection',{message:String(e.reason)}));
  try{new PerformanceObserver(list=>list.getEntries().forEach(e=>add('longtask',{start:e.startTime,ms:e.duration}))).observe({type:'longtask',buffered:true})}catch{}
  for(const type of ['pointerdown','pointerup','pointermove','click','input','change','wheel','scroll']){
    addEventListener(type,e=>{
      if(!bench.ready||bench.action==='idle')return;
      const start=performance.now(),action=bench.action;
      const id=e.target instanceof Element?e.target.id:'';
      requestAnimationFrame(()=>requestAnimationFrame(()=>bench.events.push({kind:'response',action,type,id,start,ms:performance.now()-start})));
    },{capture:true,passive:true});
  }
  const json=Response.prototype.json;
  Response.prototype.json=async function(...args){const start=performance.now();const value=await json.apply(this,args);add('body-and-json',{url:this.url,ms:performance.now()-start});return value};
  function frame(){
    if(document.querySelector('#timeThumb')&&!document.querySelector('#loadingBox')){
      requestAnimationFrame(()=>requestAnimationFrame(()=>{bench.ready={ms:performance.now(),pages:document.querySelectorAll('.pageRow').length,elements:document.querySelectorAll('*').length};bench.action='idle'}));
    }else requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
