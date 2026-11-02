// Compare existing source diagnostics without undertaking the deferred cleanup.
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const ts=require('/opt/heaplens-ui/node_modules/typescript');
function diagnostics(root){
 const config=ts.readConfigFile(path.join(root,'tsconfig.json'),ts.sys.readFile);
 const parsed=ts.parseJsonConfigFileContent(config.config,ts.sys,root);
 const program=ts.createProgram(parsed.fileNames,{...parsed.options,noEmit:true,incremental:false});
 return ts.getPreEmitDiagnostics(program).filter(d=>d.file&&d.file.fileName.includes('/src/'))
  // MUI's abbreviated union strings can reorder when unrelated props change.
  // Compare code + exact offending expression, not line numbers or truncation.
  .map(d=>path.relative(root,d.file.fileName)+':'+d.code+':'+
    d.file.text.slice(d.start,d.start+d.length).trim());
}
const before=diagnostics(process.argv[2]),after=diagnostics(process.argv[3]);
const extra=[...after];for(const d of before){const i=extra.indexOf(d);if(i>=0)extra.splice(i,1)}
console.log(JSON.stringify({baseline_source_diagnostics:before.length,candidate_source_diagnostics:after.length,added:extra},null,2));
assert.equal(extra.length,0,'New source TypeScript diagnostics');
