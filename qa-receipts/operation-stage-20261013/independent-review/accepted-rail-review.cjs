const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{createHash,webcrypto}=require('node:crypto'); globalThis.crypto ||=webcrypto;
const ui=require(process.env.REVIEW_JS), sha=x=>createHash('sha256').update(x).digest('hex');
(async()=>{
const nativePath='/workspace/casepath-reference-polish-evidence-20261013/native-v1-v2-reference.json', dir='/workspace/operation-runtime-evidence/native-sidecars',native=JSON.parse(fs.readFileSync(nativePath,'utf8'));
const receipt={source_sha256:sha(fs.readFileSync(process.env.REVIEW_JS)),native_fixture_sha256:sha(fs.readFileSync(nativePath)),cases:[],totals:{operations:0,checkpoints:0,shown:0,subspans:0,retainedInkQuiet:0,forbiddenAria:0},examples:{retainedInkQuiet:[],forbiddenAria:[]}};
for(const row of ui.REFERENCE_DEMO_CASES.filter(row=>row.claim_id==='clm_314f2d309fea25e6')){
 const bytes=fs.readFileSync(path.join(dir,row.claim_id+'.json')),sidecar=JSON.parse(bytes),frames=sidecar.frames,head=native.snapshots[row.claim_id],binding=frames[0],start=ui.checkedReferenceReplayStart(head.replay_start,{state:head.state,accepted:{events:head.events}});
 ui.checkedOperationBinding(binding,{claimId:row.claim_id,revision:head.state.revision,state_sha256:head.state.state_sha256,event_sha256:head.state.last_event_sha256},start);
 const trace={binding,rows:[],bytes:0,sources:new Map(),journal:[],pinnedJournal:head.events,transportState:null,visibleResults:new Map(),frameHashes:[],dockedFacts:new Map()}; let saved=native.unprocessed[row.claim_id].state; const hashes=[]; let shown=0,checkpoints=0;
 for(const frame of frames.slice(0,-1)){
  hashes.push(sha(ui.canonicalJSON(frame)));
  if(frame.type==='operation'){
   const op=await ui.checkedOperation(frame,trace,saved);ui.applyWorkingOperation(op,trace,saved);
   const graph=ui.workingProcessState(trace)?.graph||saved.graph,node=ui.operationNodeId(op,graph,saved);
   if(op.kind==='fact.extract'&&op.source&&node&&op.result.verification_required===false&&saved.facts.some(x=>x.fact_id===op.object.id))trace.dockedFacts.set(op.object.id,{operation:op,node});
   const show=ui.operationAttention(op,trace);
   if(show){
    trace.current=op; const cause=trace.rows.find(x=>x.id===op.cause_ids.at(-1)),pin=op.source||(op.kind==='phrase.match'?cause?.source:null);
    if(pin)trace.displaySource={artifact_id:pin.artifact_id,pin,id:op.id}; else if(op.kind==='source.open')trace.displaySource={artifact_id:op.object.id,id:op.id};
    trace.state=saved; const markup=ui.operationStageMarkup(saved,{},node,trace); const completed=saved.evaluation?.nodes?.filter(x=>x.execution_state==='completed'&&graph?.nodes?.some(n=>n.node_id===x.node_id)).map(x=>x.node_id)||[]; if(trace.working&&completed.length){receipt.regressions ||= []; receipt.regressions.push({operation_id:op.id,kind:op.kind,operation_seq:op.seq,accepted_revision:saved.revision,accepted_graph_sha256:saved.graph.graph_sha256,display_graph_sha256:graph.graph_sha256,completed_node_ids:completed,rendered_completed_count:(markup.match(/data-status="completed"/g)||[]).length,working_inspect_id:trace.working.inspect.id});}
    const aria=[...markup.matchAll(/aria-label="([^"]*)"/g)].map(x=>x[1]).filter(x=>/provisional|Applicability|Execution|Working model|Not established|Intake incomplete/i.test(x));
    if(aria.length){receipt.totals.forbiddenAria+=aria.length;if(receipt.examples.forbiddenAria.length<4)receipt.examples.forbiddenAria.push({claim:row.claim_id,id:op.id,kind:op.kind,aria});}
    const reading=ui.operationReading(trace);if(reading?.active){const span=ui.stageFactSpan({...op,source:reading.pin});assert.equal(reading.chars.slice(span.start_char,span.end_char).join(''),span.quote,op.id+' exact stage subspan');assert.ok(span.start_char>=reading.pin.start_char&&span.end_char<=reading.pin.end_char);receipt.totals.subspans++;}
    for(const m of markup.matchAll(/data-au-stage-fact="([^"]+)"/g))assert.ok(saved.facts.some(x=>x.fact_id===m[1]),'only accepted fact dock');
    shown++;
   } else if(ui.operationReading(trace)?.active&&!['phrase.match','span.read'].includes(op.kind)){
    receipt.totals.retainedInkQuiet++;if(receipt.examples.retainedInkQuiet.length<6)receipt.examples.retainedInkQuiet.push({claim:row.claim_id,shown:trace.current.id,shownKind:trace.current.kind,consumed:op.id,consumedKind:op.kind,consumedStage:op.stage});
   }
   receipt.totals.operations++;
  } else if(frame.type==='checkpoint'){saved=(await ui.checkedOperationCheckpoint(frame,trace)).state;trace.working=null;checkpoints++;}
 }
 const result=frames.at(-1);assert.equal(result.exact_output_verified,true);assert.equal(result.operation_count,trace.rows.length);assert.equal(result.operation_chain_sha256,trace.rows.at(-1).operation_sha256);assert.equal(result.trace_sha256,sha(ui.canonicalJSON(hashes)));assert.deepEqual(saved,head.state);
 receipt.cases.push({claim_id:row.claim_id,sidecar_sha256:sha(bytes),operations:trace.rows.length,checkpoints,shown,state_sha256:saved.state_sha256});receipt.totals.shown+=shown;receipt.totals.checkpoints+=checkpoints;
}
console.log(JSON.stringify(receipt,null,2));
})().catch(e=>{console.error(e);process.exitCode=1});
