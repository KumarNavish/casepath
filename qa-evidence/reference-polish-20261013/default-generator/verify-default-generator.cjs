'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {createHash}=require('node:crypto'),cp=require('node:child_process');
const root='/workspace/casepath-polish-gate-inventory-20261013';
const output='/workspace/casepath-reference-polish-default-generator-20261013';
const source=fs.readFileSync(path.join(root,'casepath-qa/unified-product-browser-v1.test.cjs'),'utf8');
const sha=value=>createHash('sha256').update(value).digest('hex');
const fn=source.slice(source.indexOf('function referenceFixture('),source.indexOf('function pdfDrawerFixture('));
const ids=JSON.parse(source.match(/const referenceIds = (\[[\s\S]*?\]);/)[1].replace(/'/g,'"').replace(/,\s*\]/,']'));
const context={fs,root,process,referenceIds:ids,nativeMigrationReferenceFixture:undefined,nativeReferenceFixture:undefined,execFileSync:(command,args,options)=>{
  assert.equal(options.maxBuffer,256*1024*1024);
  assert.equal(args.at(-1),'migration');
  fs.writeFileSync(path.join(output,'generator-command.json'),JSON.stringify({command,args,cwd:options.cwd,maxBuffer:options.maxBuffer,externalFixtureInput:false},null,2)+'\n');
  return cp.execFileSync(command,args,options);
}};
assert.equal(process.env.CASEPATH_REFERENCE_MIGRATION_FIXTURE,undefined);
assert.equal(process.env.CASEPATH_REFERENCE_FIXTURE,undefined);
const started=Date.now();vm.createContext(context);vm.runInContext(fn,context);
const actual=context.referenceFixture(true);
const previous=JSON.parse(fs.readFileSync('/workspace/casepath-reference-polish-evidence-20261013/native-v1-v2-reference.json','utf8'));
let prefixes=0;
const rows=[];
for(const id of ids){
  const saved=actual.snapshots[id],start=saved.replay_start;
  assert.equal(saved.state.outcome.assessment_status,'complete');
  assert.equal(start.contract,'casepath.reference-replay-start/1.0.0');
  assert.equal(start.profile_id,'synthetic-nine-v2');
  assert.equal(start.profile_sha256,'18c2ff55eb39324fee225b2b44330079715d1de11234d2367a2ed172b59c0869');
  assert.deepEqual(start,previous.snapshots[id].replay_start);
  const states=actual.prefixes[id];
  for(let seq=0;seq<=saved.state.revision;seq++){
    const dto=states[seq],expected=previous.prefixes[id][seq];
    assert.equal(dto.state_sha256,expected.state_sha256);
    assert.deepEqual(dto.events,expected.events);
    assert.deepEqual(dto.replay_start,start);
    prefixes++;
  }
  const first=states[start.from_seq],event=first.events.at(-1);
  assert.equal(event.kind,'process.prepared');
  assert.equal(event.event_sha256,start.event_sha256);
  assert.equal(first.state_sha256,start.state_sha256);
  assert.equal(actual.before_v1_snapshots[id].state_sha256,previous.before_v1_snapshots[id].state_sha256);
  rows.push({claim_id:id,revision:saved.state.revision,state_sha256:saved.state_sha256,replay_start:start});
}
assert.equal(prefixes,393);assert.equal(Object.keys(actual.raw_sources).length,57);
for(const [id,bytes] of Object.entries(actual.raw_sources))assert.equal(bytes,previous.raw_sources[id]);
const fixture=fs.readFileSync(process.env.CASEPATH_REFERENCE_MIGRATION_FIXTURE_OUTPUT);
const result={sourceCommit:cp.execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),qaSha256:sha(source),functionSha256:sha(fn),inputOverrideAbsent:true,maxBuffer:256*1024*1024,outputBytes:fixture.length,outputSha256:sha(fixture),claims:ids.length,prefixes,physicalSources:Object.keys(actual.raw_sources).length,everyStateAndEventMatchesPreviousExport:true,metadataMatchesActualPreparedPrefixes:true,oldV1StatesPreserved:true,rows,duration_seconds:(Date.now()-started)/1000};
fs.writeFileSync(path.join(output,'receipt.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({claims:ids.length,prefixes,physicalSources:57,outputBytes:fixture.length,duration_seconds:result.duration_seconds,exit_code:0}));
