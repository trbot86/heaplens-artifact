const fs=require('fs'),path=require('path'),assert=require('assert/strict');
let ts;try{ts=require('typescript')}catch{ts=require('/opt/heaplens-ui/node_modules/typescript')}
const file=path.resolve(__dirname,'../../sifter_vis_d3/sifter/src/app/ui/timestampClock.ts');
const api={};new Function('exports',ts.transpileModule(fs.readFileSync(file,'utf8'),
 {compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText)(api);
assert.equal(api.formatElapsedTimestamp(2200000000,2200000000),'1.00 s');
assert.equal(api.formatElapsedTimestamp(2200000000,null),'2200000000 ticks');
for(const value of ['0','-1','NaN','Infinity'])assert.throws(()=>api.parseTimestampHz(value));
assert.equal(api.parseTimestampHz(undefined),null);
assert.equal(api.parseTimestampHz(''),null);
console.log('Trace clock tests passed');
