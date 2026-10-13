const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{createHash,webcrypto}=require('node:crypto');globalThis.crypto ||=webcrypto;
const ui=require(process.env.REVIEW_JS),sha=x=>createHash('sha256').update(x).digest('hex');
(async()=>{
const np='/workspace/casepath-reference-polish-evidence-20261013/native-v1-v2-reference.json',native=JSON.parse(fs.readFileSync(np)),dir='/workspace/operation-runtime-evidence/native-sidecars';
const receipt={source_sha256:sha(fs.readFileSync(process.env.REVIEW_JS)),native_sha256:sha(fs.readFileSync(np)),cases:[],fact_meaning_table:[],uninspectable:[],totals:{operations:0,checkpoints:0,shown:0,reading_subspans:0,accepted_fills_retained:0,peek_checked:0}};const meanings=new Set();
for(const row of ui.REFERENCE_DEMO_CASES){
 const bytes=fs.readFileSync(path.join(dir,row.claim_id+'.json')),side=JSON.parse(bytes),head=native.snapshots[row.claim_id],binding=side.frames[0],start=ui.checkedReferenceReplayStart(head.replay_start,{state:head.state,accepted:{events:head.events}});ui.checkedOperationBinding(binding,{claimId:row.claim_id,revision:head.state.revision,state_sha256:head.state.state_sha256,event_sha256:head.state.last_event_sha256},start);
 const trace={binding,rows:[],bytes:0,sources:new Map(),journal:[],pinnedJournal:head.events,transportState:null,visibleResults:new Map(),dockedFacts:new Map(),checkpoints:[]};let saved=native.unprocessed[row.claim_id].state, hashes=[];
 for(const frame of side.frames.slice(0,-1)){
  hashes.push(sha(ui.canonicalJSON(frame)));
  if(frame.type==='operation'){
   const op=await ui.checkedOperation(frame,trace,saved);ui.applyWorkingOperation(op,trace,saved);const graph=ui.workingProcessState(trace)?.graph||saved.graph,node=ui.operationNodeId(op,graph,saved);
   if(op.kind==='fact.extract'&&op.source){const full=ui.stageFactSpan(op),compact=ui.stageFactSpan(op,true);assert.equal(Array.from(op.source.quote).slice(full.start_char-op.source.start_char,full.end_char-op.source.start_char).join(''),full.quote);assert.equal(Array.from(op.source.quote).slice(compact.start_char-op.source.start_char,compact.end_char-op.source.start_char).join(''),compact.quote);const id=op.object.id;
    if(id==='outside_small_tenant_maintenance_and_no_tenant_cause'){assert.match(full.quote,/outside ordinary small tenant maintenance/);assert.match(full.quote,/no tenant alteration or misuse/i);assert.doesNotMatch(full.quote,/15\.[89]C|16\.1C/);}
    if(id==='residential_tenancy_scope'){assert.match(full.quote,/residential lease|residential tenancy/);assert.doesNotMatch(full.quote,/CHF/);}
    if(id==='objective_use_impairment')assert.match(full.quote,/inadequate.*contracted.*use/i);
    if(id==='landlord_first_knowledge')assert.match(full.quote,/first.*documented knowledge/i);
    if(id==='continuing_defect_without_remedy')assert.match(full.quote,/no lasting repair|did not remove the continuing defect/i);
    if(['issuer_authority_and_received_packet','issuer_authority_and_complete_packet','fact:original_notification_context','fact:received_termination_packet','fact:received_rent_increase_packet','complete_channel_archive','canton_approved_form','ordinary_non269c_tenancy','contemporaneous_substantive_reasons','later_email_is_not_original_reasons'].includes(id))assert.equal(full,op.source,'unknown or compound meaning returns complete native pin');
    const k=id+'|'+op.source.quote;if(!meanings.has(k)){meanings.add(k);receipt.fact_meaning_table.push({claim_id:row.claim_id,operation_id:op.id,id,full:full.quote,compact:compact.quote,original_pin_returned:full===op.source,source:op.source});}
   }
   if(op.kind==='fact.extract'&&op.source&&node&&op.result.verification_required===false&&saved.facts.some(x=>x.fact_id===op.object.id))trace.dockedFacts.set(op.object.id,{operation:op,node});
   const show=ui.operationAttention(op,trace);trace.consumed=op;
   if(!show){const prior=ui.operationReading(trace)?.pin,cause=trace.rows.find(x=>x.id===op.cause_ids.at(-1)),pin=op.source||(op.kind==='phrase.match'?cause?.source:null);if(!pin||!prior||pin.artifact_id!==prior.artifact_id||pin.start_char!==prior.start_char||pin.end_char!==prior.end_char)trace.inkRetired=true;}
   if(show){trace.current=op;trace.inkRetired=false;const cause=trace.rows.find(x=>x.id===op.cause_ids.at(-1)),pin=op.source||(op.kind==='phrase.match'?cause?.source:null);if(pin)trace.displaySource={artifact_id:pin.artifact_id,pin,id:op.id};else if(op.kind==='source.open')trace.displaySource={artifact_id:op.object.id,id:op.id};trace.state=saved;
    const markup=ui.operationStageMarkup(saved,{},node,trace),aria=[...markup.matchAll(/aria-label="([^"]*)"/g)].map(x=>x[1]);for(const a of aria)assert.doesNotMatch(a,/provisional|Applicability|Execution|Working model|Not established|Intake incomplete/i);
    const reading=ui.operationReading(trace);if(reading?.active){const span=ui.stageFactSpan({...op,source:reading.pin});assert.equal(reading.chars.slice(span.start_char,span.end_char).join(''),span.quote);receipt.totals.reading_subspans++;}
    for(const m of markup.matchAll(/<button[^>]*data-au-node="([^"]+)"[^>]*data-status="completed"/g))assert.ok(saved.evaluation.nodes.some(x=>x.node_id===m[1]&&x.execution_state==='completed'),'completion only from actual accepted checkpoint');
    if(trace.working&&graph.graph_sha256===saved.graph?.graph_sha256){for(const n of saved.evaluation.nodes.filter(x=>x.execution_state==='completed')){assert.ok(markup.includes('data-au-node="'+n.node_id+'"'),'accepted node mounted');assert.ok(new RegExp('<button[^>]*data-au-node="'+n.node_id+'"[^>]*data-status="completed"').test(markup),'accepted fill retained');receipt.totals.accepted_fills_retained++;}}
    receipt.totals.shown++;
   }receipt.totals.operations++;
  }else if(frame.type==='checkpoint'){const incoming=await ui.checkedOperationCheckpoint(frame,trace);saved=incoming.state;trace.working=null;trace.checkpoints.push({after_operation:trace.rows.length,revision:saved.revision,state_sha256:saved.state_sha256,event_sha256:frame.event_sha256,state:saved,projection:incoming.projection,events:incoming.accepted.events});receipt.totals.checkpoints++;}
 }
 const result=side.frames.at(-1);assert.equal(result.operation_count,trace.rows.length);assert.equal(result.operation_chain_sha256,trace.rows.at(-1).operation_sha256);assert.equal(result.trace_sha256,sha(ui.canonicalJSON(hashes)));assert.deepEqual(saved,head.state);
 const before={rows:trace.rows.length,head:trace.transportState.state_sha256};for(let i=0;i<trace.rows.length;i++){const view=ui.operationInspection(trace,i);if(!view){receipt.uninspectable.push({claim_id:row.claim_id,index:i,operation_id:trace.rows[i].id,kind:trace.rows[i].kind,first_checkpoint_after_operation:trace.checkpoints[0]?.after_operation});continue;}assert.ok(view.checkpoint.after_operation<=i);assert.equal(view.trace.rows.length,i+1);assert.equal(view.trace.current,trace.rows[i]);assert.equal(view.state,view.checkpoint.state);for(const scope of view.trace.workingScopes.values())assert.ok(scope.inspect.seq<=i+1);receipt.totals.peek_checked++;}assert.equal(trace.rows.length,before.rows);assert.equal(trace.transportState.state_sha256,before.head);
 receipt.cases.push({claim_id:row.claim_id,source_sha256:sha(bytes),operations:trace.rows.length,state_sha256:saved.state_sha256,first_checkpoint_after_operation:trace.checkpoints[0]?.after_operation});
}
console.log(JSON.stringify(receipt,null,2));if(receipt.uninspectable.length){console.error('FAIL actual composition lacks a preceding verified checkpoint for '+receipt.uninspectable.length+' first operations');process.exitCode=1;}
})().catch(e=>{console.error(e);process.exitCode=1;});
