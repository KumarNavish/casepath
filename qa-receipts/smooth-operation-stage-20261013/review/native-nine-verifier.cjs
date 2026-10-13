const {createHash,webcrypto}=require('node:crypto'),assert=require('node:assert/strict');
globalThis.crypto ||= webcrypto;
const ui=require('/workspace/casepath-operations-coordinator-20261013/casepath/assets/autonomous-workspace-v1.js');
const sha=value=>createHash('sha256').update(value).digest('hex');
(async()=>{

 const fs=require('node:fs'),path=require('node:path'),native=JSON.parse(fs.readFileSync(process.env.CASEPATH_OPERATION_NATIVE_FIXTURE,'utf8'));
 let operations=0,maxHistory=0,workingGraphs=0,checkpoints=0; const receipts=[]; const index=JSON.parse(fs.readFileSync(path.join(process.env.CASEPATH_OPERATION_NATIVE_SIDECARS,'index.json'),'utf8'));
 for(const row of ui.REFERENCE_DEMO_CASES){
  const sidecar=JSON.parse(fs.readFileSync(path.join(process.env.CASEPATH_OPERATION_NATIVE_SIDECARS,row.claim_id+'.json'),'utf8')),frames=sidecar.frames,head=native.snapshots[row.claim_id],binding=frames[0],start=ui.checkedReferenceReplayStart(head.replay_start,{state:head.state,accepted:{events:head.events}});
  ui.checkedOperationBinding(binding,{claimId:row.claim_id,revision:head.state.revision,state_sha256:head.state.state_sha256,event_sha256:head.state.last_event_sha256},start);
  const trace={binding,rows:[],bytes:0,sources:new Map(),journal:[],pinnedJournal:head.events,transportState:null};let saved=native.unprocessed[row.claim_id].state;const hashes=[];
  for(const frame of frames.slice(0,-1)){
   hashes.push(sha(ui.canonicalJSON(frame)));
   if(frame.type==='operation'){await ui.checkedOperation(frame,trace,saved);ui.applyWorkingOperation(frame,trace,saved);if(frame.kind==='process.inspect'){workingGraphs++;assert.equal(ui.workingProcessState(trace).graph,frame.result.graph);}if(frame.result?.phase==='provisional'&&frame.result.graph_sha256)assert.equal(trace.working.inspect.result.evaluation_sha256,frame.result.evaluation_sha256);}
   else if(frame.type==='checkpoint'){saved=(await ui.checkedOperationCheckpoint(frame,trace)).state;trace.working=null;}
  }
  const material={...sidecar};delete material.sidecar_sha256;assert.equal(sha(ui.canonicalJSON(material)),sidecar.sidecar_sha256);assert.equal(index.find(item=>item.claim_id===row.claim_id).sidecar_sha256,sidecar.sidecar_sha256);checkpoints+=frames.filter(frame=>frame.type==='checkpoint').length;receipts.push({claim_id:row.claim_id,sidecar_material_sha256:sidecar.sidecar_sha256,file_sha256:sha(fs.readFileSync(path.join(process.env.CASEPATH_OPERATION_NATIVE_SIDECARS,row.claim_id+'.json'))),operations:trace.rows.length,checkpoints:frames.filter(frame=>frame.type==='checkpoint').length,head:{revision:head.state.revision,state_sha256:head.state.state_sha256,event_sha256:head.state.last_event_sha256}});const result=frames.at(-1);assert.equal(result.exact_output_verified,true);assert.equal(result.operation_count,trace.rows.length);assert.equal(result.operation_chain_sha256,trace.rows.at(-1).operation_sha256);assert.equal(result.trace_sha256,sha(ui.canonicalJSON(hashes)));assert.deepEqual(saved,head.state,row.claim_id+' exact native output');
  assert.ok(trace.rows.some(op=>op.kind==='source.open'));assert.ok(trace.rows.some(op=>op.kind==='phrase.match'));assert.ok(trace.rows.some(op=>op.kind==='fact.extract'));assert.ok(trace.rows.some(op=>op.kind==='decision'));operations+=trace.rows.length;maxHistory=Math.max(maxHistory,trace.bytes);
 }
 assert.equal(operations,4653);assert.equal(checkpoints,162);assert.equal(receipts.length,9);assert.ok(maxHistory<8*1024*1024);
assert.equal(workingGraphs,87);fs.writeFileSync('/workspace/casepath-smooth-layout-20261013-evidence/review/native-nine-verifier.json',JSON.stringify({disclosure:'Independent verifier over unchanged local native1.1 fixtures; no provider or production calls.',candidate:require('node:child_process').execFileSync('git',['rev-parse','HEAD'],{cwd:'/workspace/casepath-operations-coordinator-20261013',encoding:'utf8'}).trim(),javascript_sha256:sha(fs.readFileSync('/workspace/casepath-operations-coordinator-20261013/casepath/assets/autonomous-workspace-v1.js')),native_fixture_file_sha256:sha(fs.readFileSync(process.env.CASEPATH_OPERATION_NATIVE_FIXTURE)),operations,checkpoints,workingGraphs,maxHistory,rows:receipts},null,2)+'\n');console.log('PASS nine exact native heads/checkpoints/chains/source spans',operations,maxHistory,workingGraphs);
})().catch(error=>{console.error(error);process.exitCode=1;});
