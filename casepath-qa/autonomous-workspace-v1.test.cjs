'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const {webcrypto,createHash} = require('node:crypto');
if (!globalThis.crypto) globalThis.crypto = webcrypto;
const ui = require('../casepath/assets/autonomous-workspace-v1.js');
const sha = value => createHash('sha256').update(value).digest('hex');
const hash = char => char.repeat(64);
function state(extra={}) {
  return {claim_id:'claim-a',title:'Original incoming claim',revision:3,state_sha256:hash('a'),status:'running',
    graph:{claim_id:'claim-a',graph_sha256:hash('b'),nodes:[{node_id:'start',label:'Inspect message',entry:true},{node_id:'branch',label:'Check separate service',condition:{flag:'family_home'}}],edges:[{edge_id:'next',source_node_id:'start',target_node_id:'branch'}]},
    evaluation:{nodes:[{node_id:'start',activation:'true',execution_state:'completed'},{node_id:'branch',activation:'true',execution_state:'ready'}],documents:[{document_type:'notice',activation:'true',route_state:'needed_now',review_state:'unreviewed'}]},
    facts:[{fact_id:'condition:family_home',label:'Family home',status:'true',summary:'The customer reports a family home.',citations:[]},{fact_id:'fact:notice',label:'Separate notice',status:'unresolved',summary:'A separate notice is required.'}],
    obligations:[{obligation_id:'obligation:branch:notice',node_id:'branch',decision_node_id:'branch',required_fact_ids:['fact:notice'],document_type:'notice',label:'Separate notice',reason:'Service depends on the family-home condition.',rule_refs:['tenancy.v1'],capability_id:'local_inbox.read'}],
    actions:[{result:{action_id:'review:notice:original',type:'document_review',node_ids:['branch'],status:'completed',summary:'Original notice inspected.'},receipt:{receipt_sha256:hash('c')}}],
    source_descriptors:[{claim_id:'claim-a',artifact_id:'original',file_name:'message.txt',sha256:hash('d')}],acquired_sources:[],knowledge_uses:[],...extra};
}
const events = (s,after=0) => ({current_revision:s.revision,events:Array.from({length:s.revision-after},(_,i)=>({seq:after+i+1,kind:i?'work.phase':'intake',revision:after+i+1,state_sha256:after+i+1===s.revision?s.state_sha256:hash('e'),payload:{summary:'Recorded activity'}}))});

test('reference intake stays a source inspection and completed assessment retains external deferral',()=>{
 const provenance={mode:'deterministic_reference',synthetic:true,as_of:'2025-02-21',profile_sha256:hash('1')};
 const s=state({policy_id:'casepath.bounded-reference-assessment/1.0.0',status:'deferred',outcome:{status:'deferred',assessment_status:'complete',assessment_scope:'heating_notice',reference_provenance:provenance},semantic_contexts:{workflow:{claim_id:'claim-a',execution_mode:'deterministic_reference',reference_provenance:provenance}},receipts:[{kind:'interpretation.accepted',receipt:{workflow_id:'workflow',receipt_sha256:hash('2'),reference_execution:{provenance}}}]});
 assert.equal(ui.claimStatusLabel(s.status,s),'Assessment complete');
 assert.equal(ui.referenceExecution(s).as_of,'2025-02-21');
 assert.equal(ui.referenceExecution(state({semantic_contexts:{future:s.semantic_contexts.workflow}})).as_of,'2025-02-21','accepted work.context identifies the execution before outcome');
 assert.equal(ui.referenceExecution(state()),null,'a roster label does not imply reference execution');
 const gate={contract:'casepath.source-backed-intake/1.0.0',status:'incomplete',eligible:false,gate_sha256:hash('3'),checklist:[{document_type:'notice',label:'Notice record',node_ids:['branch'],status:'insufficient',artifact_ids:['original']}],missing_documents:[{document_type:'notice',label:'Notice record',status:'insufficient'}],legal_predicates:[{predicate_id:'landlord_validity',status:'false',citations:[],rule_refs:[]}],provenance};
 const before=JSON.stringify({s,gate}),html=ui.intakeMarkup(s,{intake:gate});
 assert.doesNotMatch(html,/accepted evidence and findings are separate/);assert.match(html,/Needs more support/);assert.match(html,/data-au-source="original"/);assert.doesNotMatch(html,/landlord_validity|Established|data-au-node=/);
 assert.equal(JSON.stringify({s,gate}),before);
 const early=state({revision:0,graph:null,evaluation:null,facts:[],obligations:[],actions:[],acquired_sources:[],mode:'unprocessed',status:'not_started',phase:'not_run'});
 const view=ui.workMarkup(early,{intake:gate},null,[],'step',{}, {availability:{ready:true}});
 assert.match(view,/data-au-start disabled/);assert.match(view,/Notice record/);assert.doesNotMatch(view,/data-au-node=/);
 const completed=ui.workMarkup(s,{},'branch',[]);
 assert.equal((completed.match(/Historical synthetic recording · as of 2025-02-21 · rules-based/g)||[]).length,1);assert.match(completed,/Assessment only; no external action taken/);
});

test('reference demonstration has the exact new nine and legacy history remains separate',()=>{
 const ids=['clm_314f2d309fea25e6','clm_4a07dbbbd859a3ce','clm_95d08975bc575592','clm_0f4f13b1e3e1328c','clm_393285577dcb12c4','clm_4a53299cfe619303','clm_2c55cdd816b1d0e8','clm_543f08f2415b2a33','clm_7dbd7c7d1c4ddf90'];
 assert.deepEqual(ui.REFERENCE_DEMO_CASES.map(row=>row.claim_id),ids);
 for(const domain of ui.DOMAINS)assert.equal(ui.REFERENCE_DEMO_CASES.filter(row=>row.domain===domain.id).length,3);
 assert.equal(ui.DEMO_CASES.length,9);assert.notDeepEqual(ui.DEMO_CASES.map(row=>row.claim_id),ids);
 const html=ui.demonstrationMarkup([],null,'reference');assert.deepEqual([...html.matchAll(/data-au-demo-case="([^"]+)"/g)].map(row=>row[1]),ids);assert.doesNotMatch(html,/Live execution|Start live/);
});

test('reference policy identifies the accepted execution before context supplies its historical date',()=>{
 const before=state(),started=state({policy_id:'casepath.bounded-reference-assessment/1.0.0'});
 assert.equal(ui.referenceExecution(before),null);assert.deepEqual(ui.referenceExecution(started),{mode:'deterministic_reference',synthetic:true});
 const html=ui.workMarkup(started,{},'branch',[]);assert.match(html,/data-au-reference-mode>Historical synthetic recording · rules-based<\/p>/);assert.doesNotMatch(html,/as of/);
 const legacy=state({policy_id:'casepath.autonomous/1',run_id:'old-model',semantic_contexts:{'old-model':{execution_mode:'provider'}},outcome:{reference_provenance:{mode:'deterministic_reference',synthetic:true,as_of:'2025-02-21'}}});
 assert.equal(ui.referenceExecution(legacy),null,'the current accepted model context wins over a retained reference outcome');
});

test('reference source labels require the exact recorded pin and later uploads retain prior assessment freshness',()=>{
 const supplement={artifact_id:'synthetic-source',sha256:hash('5'),file_name:'01-clarification.txt',role:'supporting_document'},original={artifact_id:'original',sha256:hash('d'),role:'customer_message'};
 const provenance={mode:'deterministic_reference',synthetic:true,as_of:'2025-02-21',source_roster_sha256:hash('6')};
 const s=state({run_id:'reference-run',source_roster_sha256:hash('6'),source_descriptors:[original,supplement],original_binding:{source_map:[original]},semantic_contexts:{'reference-run':{claim_id:'claim-a',execution_mode:'deterministic_reference',reference_provenance:provenance,sources:[original,supplement]}},receipts:[{kind:'interpretation.accepted',receipt:{workflow_id:'reference-run',receipt_sha256:hash('7'),reference_execution:{provenance}}}]});
 assert.equal(ui.sourceKind(s,original),'Original source');assert.equal(ui.sourceKind(s,supplement),'Synthetic demonstration document');
 const arrived=structuredClone(s),late={artifact_id:'unrelated-later-jpeg',sha256:hash('8'),file_name:supplement.file_name,media_type:'image/jpeg',role:'supporting_document'};
 arrived.source_descriptors.push(late);arrived.source_roster_sha256=hash('9');
 assert.equal(ui.sourceKind(arrived,late),'Supporting source');assert.equal(ui.sourceKind(arrived,{...late,media_type:'text/csv'}),'Supporting source');assert.equal(ui.sourceKind(arrived,{...supplement,sha256:hash('8')}),'Supporting source','filename and an old artifact ID cannot classify changed bytes');
 const projection={intake:{contract:'casepath.source-backed-intake/1.0.0',gate_sha256:hash('3'),status:'complete',eligible:true,provenance}};
 assert.equal(ui.sourceKind(arrived,late,projection),'Supporting source','a prior preflight roster cannot classify a later upload');
 assert.equal(ui.referenceExecution(arrived).as_of,'2025-02-21');assert.equal(ui.assessmentFreshness(arrived).status,'prior');assert.deepEqual(ui.assessmentFreshness(arrived).sources,[late]);
 const html=ui.workMarkup(arrived,{},'branch',[],'sources');assert.match(html,/Synthetic demonstration document/);assert.doesNotMatch(html,/unrelated-later-jpeg[^<]*Synthetic demonstration/);
 assert.equal(JSON.stringify(s.source_descriptors),JSON.stringify([original,supplement]));
});

test('completed reference assessments filter with completed assessments while external and ordinary deferred states stay exact',()=>{
 const reference=ui.REFERENCE_DEMO_CASES.map(row=>({...row,origin:'canonical_original',status:'deferred',policy_id:'casepath.bounded-reference-assessment/1.0.0',outcome:{status:'deferred',assessment_status:'complete',reference_provenance:{mode:'deterministic_reference',synthetic:true}}}));
 const ordinary={claim_id:'ordinary',origin:'canonical_original',status:'deferred',policy_id:'casepath.autonomous/1',outcome:{status:'deferred'}},wrongPolicy={...ordinary,claim_id:'old-policy',outcome:reference[0].outcome};
 const rows=[...reference,ordinary,wrongPolicy],before=JSON.stringify(rows);
 assert.deepEqual(ui.matchingClaims(rows,{filter:'investigation_complete'}).map(row=>row.claim_id),ui.REFERENCE_DEMO_CASES.map(row=>row.claim_id));
 assert.deepEqual(ui.matchingClaims(rows,{filter:'deferred'}).map(row=>row.claim_id),['ordinary','old-policy']);
 assert.match(ui.collectionMarkup(rows,{filter:'investigation_complete'}),/>Assessment complete<\/button>/);assert.equal(JSON.stringify(rows),before);
});

test('pinned synthetic source excerpts show the actual body while the full acquired bytes remain exact',()=>{
 for (const header of ['SYNTHETIC SUPPLEMENT — FICTIONAL DEMONSTRATION SOURCE\nFixture header and hash declarations.','Synthetic demonstration document (fictional)']) {
 const body=header+'\n\nThe service observation records a continuing heating fault.',source={artifact_id:'source',sha256:hash('5'),media_type:'text/plain',role:'supporting_document',text:body};
 const s=state({source_descriptors:[source],semantic_contexts:{recorded:{execution_mode:'deterministic_reference',reference_provenance:{synthetic:true},sources:[{artifact_id:source.artifact_id,sha256:source.sha256}]}}}),before=JSON.stringify(s);
 assert.equal(ui.sourceExcerpt(s,source),'The service observation records a continuing heating fault.');assert.equal(ui.sourceExcerpt(state(),source),body,'a declared synthetic header alone cannot authorize hiding an unpinned source header');
 assert.equal(ui.sourceExcerpt(s,{...source,sha256:hash('6')}),body);assert.equal(JSON.stringify(s),before);
 }
});

test('current regenerated documents stay in Sources and exact earlier documents remain in History',()=>{
 const sources=['original','earlier','cleaned'].map((artifact_id,index)=>({artifact_id,sha256:hash(String(index+1)),file_name:artifact_id+'.txt',role:index?'supporting_document':'customer_message'}));
 const provenance={mode:'deterministic_reference',synthetic:true,profile_id:'synthetic-nine-v2',source_roster_sha256:hash('4'),source_artifact_ids:['original','cleaned']};
 const s=state({run_id:'current',source_roster_sha256:hash('4'),source_descriptors:sources,original_binding:{source_map:[sources[0]]},semantic_contexts:{current:{reference_provenance:provenance}}}),before=JSON.stringify(s);
 assert.deepEqual(ui.currentSourceSelection(s).map(row=>row.artifact_id),['original','cleaned']);
 const files=ui.workMarkup(s,{},'branch',[],'sources');assert.match(files,/data-au-source="cleaned"/);assert.doesNotMatch(files,/data-au-source="earlier"/);
 const history=ui.workMarkup(s,{},'branch',[],'activity');assert.match(history,/Earlier documents/);assert.match(history,/data-au-source="earlier"/);
 assert.deepEqual(ui.currentSourceSelection({...s,source_roster_sha256:hash('5')}),sources,'a later or unreviewed source roster cannot be hidden by an older selection');
 for(const ids of [['cleaned'],['original','unknown'],['original','cleaned','cleaned']])assert.deepEqual(ui.currentSourceSelection({...s,semantic_contexts:{current:{reference_provenance:{...provenance,source_artifact_ids:ids}}}}),sources);
 assert.equal(JSON.stringify(s),before);
});

test('a current reassessment does not treat its superseded documents as new evidence',()=>{
 const sources=['original','earlier','cleaned'].map((artifact_id,index)=>({artifact_id,sha256:hash(String(index+1)),file_name:artifact_id+'.txt',role:index?'supporting_document':'customer_message'}));
 const provenance={mode:'deterministic_reference',synthetic:true,profile_id:'synthetic-nine-v2',source_roster_sha256:hash('4'),source_artifact_ids:['original','cleaned']};
 const s=state({run_id:'current',source_roster_sha256:hash('4'),source_descriptors:sources,original_binding:{source_map:[sources[0]]},semantic_contexts:{current:{claim_id:'claim-a',reference_provenance:provenance,sources:[sources[0],sources[2]]}},receipts:[{kind:'interpretation.accepted',receipt:{workflow_id:'current',receipt_sha256:hash('5')}}]}),before=JSON.stringify(s);
 assert.equal(ui.assessmentFreshness(s).status,'current');assert.deepEqual(ui.assessmentFreshness(s).sources,[]);
 assert.doesNotMatch(ui.workMarkup(s,{},'branch',[]),/new sources await review/);
 const late={artifact_id:'later',sha256:hash('6'),file_name:'later.txt'},arrived={...s,source_descriptors:[...sources,late],source_roster_sha256:hash('7')};
 assert.equal(ui.assessmentFreshness(arrived).status,'prior');assert.ok(ui.assessmentFreshness(arrived).sources.some(row=>row.artifact_id==='later'));
 const unknown=structuredClone(s);unknown.semantic_contexts.current.reference_provenance.profile_id='unknown';assert.equal(ui.assessmentFreshness(unknown).status,'prior');
 assert.equal(JSON.stringify(s),before);
});

test('a reassessment replay start must bind to the accepted run, source selection and prepared prefix',()=>{
 const start={contract:'casepath.reference-replay-start/1.0.0',claim_id:'claim-a',from_seq:4,state_sha256:hash('4'),event_sha256:hash('5'),run_id:'current-run',profile_id:'synthetic-nine-v2',profile_sha256:hash('6'),source_artifact_ids:['original','cleaned']};
 const provenance={mode:'deterministic_reference',synthetic:true,as_of:'2025-02-21',profile_id:start.profile_id,profile_sha256:start.profile_sha256};
 const head={state:state({revision:20,run_id:start.run_id,outcome:{assessment_status:'complete'},semantic_contexts:{'current-run':{execution_mode:'deterministic_reference',reference_provenance:provenance,sources:[{artifact_id:'cleaned'},{artifact_id:'original'}]}}}),accepted:{events:[{seq:4,kind:'process.prepared',state_sha256:start.state_sha256,event_sha256:start.event_sha256}]}};
 const before=JSON.stringify({start,head});assert.equal(ui.checkedReferenceReplayStart(null,head),null);assert.equal(ui.checkedReferenceReplayStart(start,head),start);
 for(const changed of [{contract:'unknown'},{claim_id:'another-claim'},{from_seq:0},{from_seq:20},{run_id:'old-run'},{profile_id:'synthetic-nine-v1'},{profile_sha256:hash('7')},{state_sha256:hash('7')},{event_sha256:hash('7')},{source_artifact_ids:['original','unreviewed']},{source_artifact_ids:['original','original','cleaned']}])assert.throws(()=>ui.checkedReferenceReplayStart({...start,...changed},head),/recording start/);
 assert.throws(()=>ui.checkedReferenceReplayStart(start,{...head,accepted:{events:[{...head.accepted.events[0],kind:'outcome.recorded'}]}}),/recording start/);
 const prepared=state({revision:4,state_sha256:start.state_sha256,last_event_sha256:start.event_sha256,run_id:start.run_id,outcome:null});
 const envelope={state:prepared,projection:{revision:prepared.revision,state_sha256:prepared.state_sha256},events:events(prepared).events.map((event,index)=>({...event,event_sha256:index===3?start.event_sha256:hash('8'),kind:index===3?'process.prepared':event.kind})),cursor_sha256:start.event_sha256,mode:'replay',replay_only:true,through_seq:4,current_revision:20,current_state_sha256:hash('9'),current_event_sha256:hash('a'),provenance:{run_id:start.run_id,event_sha256:start.event_sha256}};
 assert.equal(ui.checkedReferenceReplayOpening(envelope,start,prepared.claim_id).state,prepared);
 assert.throws(()=>ui.checkedReferenceReplayOpening({...envelope,state:{...prepared,outcome:{summary:'Old completed finding'}}},start,prepared.claim_id),/recording opening/);
 assert.equal(JSON.stringify({start,head}),before);
});

test('actual DAG topology determines rank and branches independently of input order',()=>{
 const graph={nodes:[{node_id:'join'},{node_id:'right'},{node_id:'start'},{node_id:'left'}],edges:[{source_node_id:'start',target_node_id:'left'},{source_node_id:'start',target_node_id:'right'},{source_node_id:'left',target_node_id:'join'},{source_node_id:'right',target_node_id:'join'}]};
 const layout=ui.layoutGraph(graph);
 assert.deepEqual(layout.rows.map(row=>row.map(n=>n.node_id)),[['start'],['left','right'],['join']]);
 assert.deepEqual(layout.parents.get('join'),['left','right']);
 assert.throws(()=>ui.layoutGraph({...graph,edges:[...graph.edges,{source_node_id:'join',target_node_id:'start'}]}),/cycle/);
 assert.throws(()=>ui.layoutGraph({...graph,edges:[{source_node_id:'absent',target_node_id:'start'}]}),/no step/);
 assert.throws(()=>ui.layoutGraph({nodes:[{node_id:'a'},{node_id:'a'}]}),/duplicate/);
});

test('claim identity fails closed across claims, invalid revision and graph ownership',()=>{
 assert.equal(ui.readState(state(),'claim-a').state.claim_id,'claim-a');
 assert.equal(ui.readState({state:state(),projection:{current_action:'Read message'}}).projection.current_action,'Read message');
 for(const bad of [state({revision:0}),state({state_sha256:'not a seal'}),state({graph:{claim_id:'another'}})]) assert.throws(()=>ui.readState(bad),/identity|process/);
 assert.throws(()=>ui.readState(state(),'claim-b'),/another claim/);
});

test('initial and reconnect history settle without animation; a fresh matching saved event can animate',()=>{
 const s=state();
 const first=ui.acceptEvents(null,events(s),s);assert.equal(first.cursor,3);assert.deepEqual(first.animate,[]);
 const next=state({revision:4,state_sha256:hash('f')});
 const fresh=ui.acceptEvents(3,events(next,3),next);assert.equal(fresh.animate.length,1);
 assert.deepEqual(ui.acceptEvents(3,events(next,3),next,true).animate,[]);
 assert.deepEqual(ui.acceptEvents(4,{current_revision:4,events:[]},next).animate,[]);
 const ahead=ui.acceptEvents(3,{...events(next,3),current_revision:5},next);assert.equal(ahead.ready,false);assert.equal(ahead.cursor,3);
});

test('event cursors cannot hide missing/duplicate sequences or a different resulting saved state',()=>{
 const s=state(),full=events(s);
 for(const batch of [{...full,events:full.events.slice(1)},{...full,events:[full.events[0],full.events[0],...full.events.slice(1)]},{...full,events:full.events.slice(0,2)},{...full,events:full.events.map((event,i)=>i===2?{...event,state_sha256:hash('9')}:event)},{...full,events:full.events.map((event,i)=>i===1?{...event,claim_id:'other'}:event)}]) assert.throws(()=>ui.acceptEvents(null,batch,s),/sequence|cursor|identity|claim/);
});

function savedReadTuple() {
 const body='Original lease 🏠. The notice names Alex.',saved=state({contract:'casepath.autonomous-claim/1.0.0',last_event_sha256:hash('3')}),rejection={item_id:'proposed-fact',reason:'The proposed quote was not in an original source.',item:{fact_id:'proposed-fact',citations:[{artifact_id:'outside-claim',quote:'UNACCEPTED_PROVIDER_QUOTE',start_char:0,end_char:24}]}};
 saved.source_descriptors[0].descriptor_sha256=hash('6');saved.acquired_sources=[{claim_id:saved.claim_id,artifact_id:'original',sha256:hash('d'),descriptor_sha256:hash('6'),text:body,text_sha256:sha(body),extraction:'utf8',complete:true,receipt_sha256:hash('7')}];
 saved.facts[0].citations=[{artifact_id:'original',sha256:hash('d'),text_sha256:sha(body),start_char:0,end_char:Array.from(body).length,quote:body}];saved.receipts=[{kind:'interpretation.accepted',receipt:{receipt_sha256:hash('4'),item_rejections:[rejection]}}];saved.actions[0].receipt.item_rejections=[rejection];
 saved.original_binding={claim_id:saved.claim_id,source_map:[{artifact_id:'original',original_artifact_id:'raw-original',sha256:hash('d')}]};
 const history=[{claim_id:saved.claim_id,seq:1,revision:1,state_sha256:hash('1'),event_sha256:hash('1'),previous_event_sha256:null,kind:'intake'},
  {claim_id:saved.claim_id,seq:2,revision:2,state_sha256:hash('2'),event_sha256:hash('2'),previous_event_sha256:hash('1'),kind:'interpretation.accepted',payload:{proposal:{facts:[rejection.item]},receipt:saved.receipts[0].receipt}},
  {claim_id:saved.claim_id,seq:3,revision:3,state_sha256:saved.state_sha256,event_sha256:hash('3'),previous_event_sha256:hash('2'),kind:'action.completed',payload:saved.actions[0]}];
 return {state:saved,projection:{claim_id:saved.claim_id,revision:saved.revision,state_sha256:saved.state_sha256,node_capabilities:{branch:{authorized:true,id:'local_assessment.record'}}},cursor:saved.revision,history};
}
// Authored cryptographic/control-flow fixture, not a native reducer or timing receipt.
function savedSnapshotAssetFixture(change=()=>{}) {
 const tuple=savedReadTuple(),body={mode:'saved',state:tuple.state,projection:tuple.projection,events:[]};let previous=null,previousState=null;
 for(let index=0;index<tuple.history.length;index++){
  const command={kind:tuple.history[index].kind,payload:tuple.history[index].payload||{},expected_revision:index,expected_state_sha256:previousState};
  const material={contract:'casepath.autonomous-event/1.0.0',session_id:'saved-asset-test',claim_id:tuple.state.claim_id,...command,sequence:index+1,previous_event_sha256:previous,created_at:`2026-10-15T00:00:0${index}+00:00`,idempotency_key:`saved-test-${index}`,command_sha256:sha(ui.canonicalJSON(command))};
  const event_sha256=sha(ui.canonicalJSON(material)),resulting_state_sha256=sha(`saved-result-${index}`);
  body.events.push({...material,event_sha256,resulting_state_sha256,seq:index+1,revision:index+1,timestamp:material.created_at,state_sha256:resulting_state_sha256});previous=event_sha256;previousState=resulting_state_sha256;
 }
 body.state.last_event_sha256=previous;change(body);
 const material={...body.state};delete material.state_sha256;body.state.state_sha256=sha(ui.canonicalJSON(material));body.projection.state_sha256=body.state.state_sha256;
 const last=body.events.at(-1);last.state_sha256=last.resulting_state_sha256=body.state.state_sha256;
 body.current_revision=body.state.revision;body.current_state_sha256=body.state.state_sha256;body.current_event_sha256=body.cursor_sha256=body.state.last_event_sha256;
 const bytes=Buffer.from(JSON.stringify(body)),descriptor={url:'/saved-history-test.json',bytes:bytes.length,sha256:sha(bytes),claim_id:body.state.claim_id,revision:body.state.revision,state_sha256:body.state.state_sha256,event_sha256:body.state.last_event_sha256,deployment_commit:null,history_kind:'native_fixture'};
 return {body,bytes,descriptor};
}

test('saved snapshot assets pin exact bytes publication identity native commands full history and state',async()=>{
 const asset=savedSnapshotAssetFixture(),before=JSON.stringify(asset.body),checked=await ui.checkedSavedSnapshotAsset(asset.bytes,asset.descriptor,true);
 assert.deepEqual(checked,{state:asset.body.state,projection:asset.body.projection,cursor:3,history:asset.body.events});assert.equal(JSON.stringify(asset.body),before);
 await assert.rejects(ui.checkedSavedSnapshotAsset(asset.bytes,asset.descriptor),/identity/,'native inputs require explicit opt-in');
 const published={...asset.descriptor,history_kind:'published_public_synthetic',deployment_commit:'f'.repeat(40)};await ui.checkedSavedSnapshotAsset(asset.bytes,published);
 for(const patch of [{bytes:asset.bytes.length-1},{sha256:hash('0')},{claim_id:'another-claim'},{revision:2},{state_sha256:hash('0')},{event_sha256:hash('0')},{deployment_commit:'not-a-commit'},{history_kind:'native_fixture'}])await assert.rejects(ui.checkedSavedSnapshotAsset(asset.bytes,{...published,...patch}),undefined,JSON.stringify(patch));
 const changed=Buffer.from(asset.bytes);changed[changed.length-2]^=1;await assert.rejects(ui.checkedSavedSnapshotAsset(changed,asset.descriptor,true),/identity/);
});

test('saved snapshot assets reject resealed partial forked aliased commands source text and citation bodies',async()=>{
 const changes=[body=>body.events.shift(),body=>body.events.reverse(),body=>delete body.events[1].previous_event_sha256,body=>body.events[1].previous_event_sha256=hash('0'),body=>body.events[1].expected_state_sha256=hash('0'),body=>body.events[1].payload.changed=true,body=>body.events[1].seq=7,body=>body.events[1].timestamp='changed',body=>body.events[1].state_sha256=hash('0'),body=>body.events[1].event_sha256=hash('0'),body=>body.state.acquired_sources[0].text+=' changed',body=>body.state.facts[0].citations[0].quote='changed',body=>body.mode='replay',body=>body.provenance={}];
 for(const change of changes){const asset=savedSnapshotAssetFixture(change);await assert.rejects(ui.checkedSavedSnapshotAsset(asset.bytes,asset.descriptor,true));}
 const asset=savedSnapshotAssetFixture();asset.body.state.title='changed without state hash';const bytes=Buffer.from(JSON.stringify(asset.body));await assert.rejects(ui.checkedSavedSnapshotAsset(bytes,{...asset.descriptor,bytes:bytes.length,sha256:sha(bytes)},true),/state hash/);
});

test('saved read copies retain exact accepted source spans receipts and rejected historical provider quotes without admitting them as facts',async()=>{
 const tuple=savedReadTuple(),before=JSON.stringify(tuple),checked=await ui.checkedSavedSnapshot(tuple,tuple.state.claim_id);assert.equal(checked,tuple);assert.equal(JSON.stringify(tuple),before);
 assert.deepEqual(checked.state.receipts,tuple.state.receipts);assert.deepEqual(checked.history,tuple.history);assert.deepEqual(checked.state.acquired_sources,tuple.state.acquired_sources);assert.equal(checked.state.facts[0].citations[0].quote,checked.state.acquired_sources[0].text);
 assert.equal(checked.history[1].payload.proposal.facts[0].citations[0].quote,'UNACCEPTED_PROVIDER_QUOTE');assert.equal(checked.state.actions[0].receipt.item_rejections[0].item.citations[0].artifact_id,'outside-claim');assert.ok(!checked.state.facts.some(fact=>fact.fact_id==='proposed-fact'));
 const html=ui.inspectorMarkup(checked.state,'branch');assert.doesNotMatch(html,/UNACCEPTED_PROVIDER_QUOTE|data-au-source="outside-claim"/);assert.equal(JSON.stringify(tuple),before);
});

test('saved read validation rejects unbound cursors projections sources text and accepted citations even with otherwise intact records',async()=>{
 const tuple=savedReadTuple(),before=JSON.stringify(tuple);
 const cases=[
  ['missing claim contract',copy=>{delete copy.state.contract;}],['wrong claim contract',copy=>{copy.state.contract='casepath.autonomous-claim/0';}],['wrong event contract',copy=>{copy.history[0].contract='casepath.autonomous-event/0';}],
  ['cursor',copy=>{copy.cursor=2;}],['projection claim',copy=>{copy.projection.claim_id='another-claim';}],['projection revision',copy=>{copy.projection.revision=2;}],['projection hash',copy=>{copy.projection.state_sha256=hash('0');}],['missing projection identity',copy=>{copy.projection={};}],
  ['latest cursor hash',copy=>{copy.state.last_event_sha256=hash('0');}],['event gap',copy=>{copy.history.splice(1,1);}],['duplicate event',copy=>{copy.history[1]=structuredClone(copy.history[0]);}],['event claim',copy=>{copy.history[1].claim_id='another-claim';}],['event hash',copy=>{copy.history[1].event_sha256='bad';}],['historical state hash',copy=>{copy.history[1].state_sha256='bad';}],['event chain',copy=>{copy.history[2].previous_event_sha256=hash('0');}],
  ['graph ownership',copy=>{copy.state.graph.claim_id='another-claim';}],['graph cycle',copy=>{copy.state.graph.edges.push({source_node_id:'branch',target_node_id:'start'});}],['missing graph node',copy=>{copy.state.graph.edges[0].target_node_id='missing-step';}],
  ['source roster claim',copy=>{copy.state.source_descriptors[0].claim_id='another-claim';}],['source roster hash',copy=>{copy.state.source_descriptors[0].sha256=hash('0');}],['duplicate source',copy=>{copy.state.source_descriptors.push(structuredClone(copy.state.source_descriptors[0]));}],['original binding claim',copy=>{copy.state.original_binding.claim_id='another-claim';}],['original mapping hash',copy=>{copy.state.original_binding.source_map[0].sha256=hash('0');}],
  ['acquired source claim',copy=>{copy.state.acquired_sources[0].claim_id='another-claim';}],['acquired source hash',copy=>{copy.state.acquired_sources[0].sha256=hash('0');}],['acquired descriptor hash',copy=>{copy.state.acquired_sources[0].descriptor_sha256=hash('0');}],['changed acquired text',copy=>{copy.state.acquired_sources[0].text+=' Altered text.';}],['acquired text hash',copy=>{copy.state.acquired_sources[0].text_sha256=hash('0');}],
  ['citation source',copy=>{copy.state.facts[0].citations[0].artifact_id='outside-claim';}],['citation source hash',copy=>{copy.state.facts[0].citations[0].sha256=hash('0');}],['citation text hash',copy=>{copy.state.facts[0].citations[0].text_sha256=hash('0');}],['citation quote',copy=>{copy.state.facts[0].citations[0].quote='UNACCEPTED_PROVIDER_QUOTE';}],['citation codepoint offset',copy=>{copy.state.facts[0].citations[0].end_char=copy.state.acquired_sources[0].text.length;}],['citation negative offset',copy=>{copy.state.facts[0].citations[0].start_char=-1;}]
 ];
 await assert.rejects(ui.checkedSavedSnapshot(tuple,'another-claim'),/claim/i);
 for(const [label,change] of cases){const copy=structuredClone(tuple);change(copy);await assert.rejects(ui.checkedSavedSnapshot(copy,tuple.state.claim_id),undefined,label);}
 assert.equal(JSON.stringify(tuple),before,'validation failures cannot rewrite the retained accepted copy');
});

test('motion targets describe actual persisted node/document changes only',()=>{
 const before=state(),after=structuredClone(before);
 assert.deepEqual(ui.changedTargets(before,after),{nodes:[],documents:[]});
 after.evaluation.nodes[1].execution_state='completed';after.evaluation.documents[0].review_state='sufficient';
 assert.deepEqual(ui.changedTargets(before,after),{nodes:['branch'],documents:['notice']});
 assert.deepEqual(before.evaluation.nodes.map(n=>n.execution_state),['completed','ready']);
});

function interpretationFocusFixture() {
 const saved=state({last_event_sha256:hash('9')}),body='The reported dwelling is a family home.';
 saved.evaluation.focus_node_id='start';
 const citation={artifact_id:'original',sha256:hash('d'),text_sha256:sha(body),start_char:0,end_char:body.length,quote:body};
 saved.facts[0].citations=[citation];saved.acquired_sources=[{artifact_id:'original',sha256:hash('d'),text_sha256:sha(body),text:body,complete:true}];
 const event={claim_id:saved.claim_id,seq:saved.revision,revision:saved.revision,state_sha256:saved.state_sha256,event_sha256:saved.last_event_sha256,kind:'interpretation.accepted',payload:{graph:saved.graph,facts:saved.facts,obligations:saved.obligations,receipt:{parent_revision:saved.revision-1,parent_state_sha256:hash('8'),receipt_sha256:hash('7')}}};
 return {saved,event};
}

test('a matching accepted atomic interpretation may focus its cited process while remembered inspection wins',()=>{
 const {saved,event}=interpretationFocusFixture(),before=JSON.stringify({saved,event});
 assert.equal(ui.preferredNode(saved,null,[]),'start','the evaluated focus is the independent fallback');
 assert.equal(ui.acceptedEventNode(saved,event),'branch');assert.equal(ui.preferredNode(saved,null,[event]),'branch');
 assert.equal(ui.preferredNode(saved,'start',[event]),'start','accepted playback does not override remembered manual inspection');
 const advanced=structuredClone(saved);advanced.revision=4;advanced.state_sha256=hash('f');advanced.last_event_sha256=hash('5');
 const result={action_id:'record:intake',node_id:'start',status:'completed',summary:'The original account is recorded.'},receipt={parent_revision:3,parent_state_sha256:saved.state_sha256,receipt_sha256:hash('6')};advanced.actions=[{result,receipt}];
 const action={claim_id:advanced.claim_id,seq:4,revision:4,state_sha256:advanced.state_sha256,event_sha256:advanced.last_event_sha256,kind:'action.completed',payload:{result,receipt}};
 assert.equal(ui.acceptedEventNode(advanced,action),'start');
 assert.equal(ui.preferredNode(advanced,ui.acceptedEventNode(advanced,action),[event,action]),'start','active playback can follow the newest valid action explicitly');
 assert.equal(ui.preferredNode(advanced,'branch',[event,action]),'branch','manual selection remains primary during later accepted work');
 assert.equal(ui.preferredNode(advanced,null,[event,action]),'branch','opening defaults retain the cited decision rather than an uncited intake action');
 assert.equal(ui.preferredNode(advanced,null,[event,{...action,claim_id:'another-claim'}]),'branch','a malformed newest event cannot displace an earlier valid cited interpretation');
 assert.equal(JSON.stringify({saved,event}),before,'event attention cannot alter accepted facts or identity');
});

test('unbound interpretation events cannot direct accepted-event or preferred process focus',()=>{
 const {saved,event}=interpretationFocusFixture(),before=JSON.stringify({saved,event});
 const invalid=[null,{kind:'interpretation.accepted'},
  {...event,claim_id:'another-claim'},{...event,claim_id:undefined},
  ...[undefined,0,-1,1.5,'3',Number.NaN].map(seq=>({...event,seq,revision:seq})),
  {...event,seq:saved.revision+1,revision:saved.revision+1},
  {...event,revision:saved.revision-1},
  ...[undefined,'not-a-hash',hash('0')].map(state_sha256=>({...event,state_sha256})),
  ...[undefined,'not-a-hash',hash('0')].map(event_sha256=>({...event,event_sha256})),
  {...event,after:{revision:event.seq,state_sha256:hash('0')}},
  {...event,after:{revision:event.seq-1,state_sha256:saved.state_sha256}}];
 for(const candidate of invalid) {
  const label=JSON.stringify(candidate);
  assert.equal(ui.acceptedEventNode(saved,candidate),null,label);
  assert.equal(ui.preferredNode(saved,null,[candidate]),'start',`an unbound event must retain evaluated focus: ${label}`);
  assert.equal(ui.preferredNode(saved,'start',[event,candidate]),'start','manual focus also remains stable beside a malformed newest event');
 }
 assert.equal(JSON.stringify({saved,event}),before);
});

test('consequential focus requires a same-claim accepted event and an actual changed fact or requirement',()=>{
 const {saved,event}=interpretationFocusFixture(),before=structuredClone(saved);before.revision=2;before.state_sha256=hash('2');before.facts[0].status='unresolved';before.facts[0].citations=[];
 const immutable=JSON.stringify({before,saved,event});assert.equal(ui.consequentialEventNode(before,saved,event),'branch');
 assert.equal(ui.consequentialEventNode({...before,claim_id:'another-claim'},saved,event),null,'a foreign prior snapshot cannot supply the diff that moves this case focus');
 for(const invalid of [{...event,claim_id:'another-claim'},{...event,seq:0,revision:0},{...event,seq:4,revision:4},{...event,state_sha256:hash('0')},{...event,event_sha256:hash('0')},{kind:event.kind}])assert.equal(ui.consequentialEventNode(before,saved,invalid),null);
 const unchanged=structuredClone(saved);unchanged.revision=2;unchanged.state_sha256=hash('2');assert.equal(ui.consequentialEventNode(unchanged,saved,event),null,'a revision or event alone cannot manufacture a content consequence');
 const executionOnly=structuredClone(unchanged);executionOnly.evaluation.nodes[1].execution_state='blocked';assert.equal(ui.consequentialEventNode(executionOnly,saved,event),null,'execution status alone does not resolve a fact or document requirement');
 const documentChanged=structuredClone(unchanged);documentChanged.evaluation.documents[0].route_state='held_behind_question';assert.equal(ui.consequentialEventNode(documentChanged,saved,event),'branch');
 assert.equal(JSON.stringify({before,saved,event}),immutable);
});

test('replay gives readable dwell to accepted content changes while routine prefixes remain brief',()=>{
 const routine={kind:'work.phase'},empty={facts:[],documents:[],nodes:[],edges:[],sources:[],knowledgeUses:[],knowledgePublications:[]};
 assert.equal(ui.replayContentPacing(null,empty),300);assert.equal(ui.replayContentPacing(routine,empty),300);
 for(const kind of ['sources.acquired','sources.arrived','interpretation.accepted','knowledge.used','knowledge.published','outcome.recorded','work.completed','work.deferred'])assert.equal(ui.replayContentPacing({kind},empty),4000,kind);
 for(const field of Object.keys(empty)){const changes={...empty,[field]:[{id:'accepted-object'}]},before=JSON.stringify(changes),duration=ui.replayContentPacing(routine,changes);assert.equal(duration,3500,field);assert.ok(duration>=3000&&duration<=5000);assert.equal(JSON.stringify(changes),before);}
 assert.equal(ui.replayContentPacing({kind:'action.completed'},empty),300,'an action receipt without any visible content difference does not receive a fake milestone pause');
});

test('selected decision joins its own facts and exact contextual authority and action records',()=>{
 const s=state(),before=JSON.stringify(s),html=ui.inspectorMarkup(s,'branch');
 for(const phrase of [s.facts[0].summary,'Separate notice'])assert.ok(html.includes(phrase),phrase);
 assert.match(html,/Ready to check/);assert.match(html,/Document for this decision/);assert.equal(ui.contextualRecord(s,{},[],'step','branch').evaluation.execution_state,'ready');
 assert.deepEqual(ui.contextualRecord(s,{},[],'step','branch').node,s.graph.nodes[1]);
 assert.deepEqual(ui.contextualRecord(s,{},[],'requirement',s.obligations[0].obligation_id).obligations,[s.obligations[0]]);
 assert.deepEqual(ui.contextualRecord(s,{},[],'action','0'),ui.actionRows(s)[0]);
 assert.doesNotMatch(html,/data-au-inspect="(?:fact|step|requirement)"/);
 assert.ok(!ui.inspectorMarkup(s,'start').includes('Separate notice'));assert.equal(JSON.stringify(s),before);
});

test('case facts show the accepted account and unique reason once while keeping raw verdicts and unknown step states exact',()=>{
 const s=state(),fact=s.facts[0];fact.label='INTERNAL_FACT_FIELD';fact.verdict='insufficient';fact.summary='The notice names only Alex.';fact.reason=fact.summary;
 s.evaluation.nodes[1].execution_state='unknown_recorded_step_state';s.evaluation.documents[0].review_state='insufficient';
 const render=()=>ui.inspectorMarkup(s,'branch'),factSection=html=>html.match(/<section class="au-reading-fact"[\s\S]*?<\/section>/)[0];
 let before=JSON.stringify(s),html=render(),reading=factSection(html);
 assert.equal(reading.split(fact.summary).length-1,1);assert.doesNotMatch(reading,/INTERNAL_FACT_FIELD|Insufficient|Not yet supported|data-au-inspect=/);
 assert.equal(ui.contextualRecord(s,{},[],'fact',fact.fact_id).verdict,'insufficient');assert.equal(ui.contextualRecord(s,{},[],'step','branch').evaluation.execution_state,'unknown_recorded_step_state');assert.equal(JSON.stringify(s),before);
 const graph=ui.graphMarkup(s,'branch'),node=graph.match(/<button[^>]*data-au-node="branch"[\s\S]*?<\/button>/)[0];assert.doesNotMatch(node.replace(/<[^>]*>/g,''),/Unknown recorded step state|Not recorded/);
 fact.reason='The recorded envelope has one addressee.';before=JSON.stringify(s);reading=factSection(render());assert.equal(reading.split(fact.summary).length-1,1);assert.equal(reading.split(fact.reason).length-1,1);
 const header=ui.workMarkup(s,{},'branch',[]).match(/<header[\s\S]*?<\/header>/)[0];assert.ok(!header.includes(fact.summary));assert.ok(!header.includes(fact.reason));assert.equal(JSON.stringify(s),before);
 fact.reason=`${fact.summary} The recorded envelope has one addressee.`;before=JSON.stringify(s);reading=factSection(render());assert.equal(reading.split(fact.summary).length-1,1);assert.ok(reading.includes('The recorded envelope has one addressee.'),'a repeated summary cannot hide the unique part of the accepted reason');assert.equal(JSON.stringify(s),before);
 fact.summary='';fact.reason='';before=JSON.stringify(s);reading=factSection(render());assert.match(reading,/question is not (?:yet )?established/i);assert.doesNotMatch(reading,/INTERNAL_FACT_FIELD|Insufficient|Not yet supported/);assert.equal(JSON.stringify(s),before);
});

test('alternate facts expose their recorded states as Other questions beside an established main fact without borrowing its verdict',()=>{
 const s=state(),main=s.facts[0];main.status='established';main.summary='The supplied source establishes the recorded main question.';
 const alternatives=[{fact_id:'fact:unresolved-arrears',node_id:'branch',label:'Whether the allocation is rent arrears',status:'unresolved',summary:'The allocation remains unresolved.'},{fact_id:'fact:false-question',node_id:'branch',label:'Another lease applies',status:'false',summary:'The recorded condition does not apply.'},{fact_id:'fact:known-question',node_id:'branch',label:'Recorded sender',status:'established',summary:'The source establishes this sender.'},{fact_id:'fact:applicable-question',node_id:'branch',label:'Recorded period applies',status:'true',summary:'The recorded period applies.'},{fact_id:'fact:insufficient-question',node_id:'branch',label:'Notice addresses both tenants',status:'insufficient',summary:'The source does not establish both recipients.'}];s.facts.push(...alternatives);const before=JSON.stringify(s),labels={'fact:unresolved-arrears':'Not established','fact:false-question':'Does not apply','fact:known-question':'Established','fact:applicable-question':'Applies','fact:insufficient-question':'Not established'};
 for(const forming of [false,true]){const html=ui.evidencePathMarkup(s,'branch',{}, {fact:main.fact_id},forming),mainSection=html.match(/<section class="au-reading-fact"[\s\S]*?<\/section>/)[0];assert.match(mainSection,/<h3 class="au-reading-label">Other questions<\/h3>/);assert.match(mainSection,/aria-label="Other questions for this decision"/);assert.equal((mainSection.match(new RegExp(main.summary,'g'))||[]).length,1);assert.match(mainSection,new RegExp(`data-au-fact="${main.fact_id}"`));
  for(const fact of alternatives){const control=html.match(new RegExp(`<button[^>]*data-au-fact-select="${fact.fact_id}"[^>]*>([\\s\\S]*?)<\\/button>`));assert.match(control[0],new RegExp(`data-au-fact-state="${fact.status}"`));assert.equal(control[1].replace(/<[^>]*>/g,''),`${labels[fact.fact_id]}: ${fact.label}`);assert.deepEqual(ui.contextualRecord(s,{},[],'fact',fact.fact_id),fact);}
  assert.doesNotMatch(html,/>Established: Whether the allocation is rent arrears</);const selected=ui.evidencePathMarkup(s,'branch',{}, {fact:alternatives[0].fact_id},forming);assert.match(selected,/data-au-fact="fact:unresolved-arrears"/);assert.ok(selected.includes(alternatives[0].summary));assert.deepEqual(ui.evidenceRelationships(s,'branch',{fact:alternatives[0].fact_id}).fact,alternatives[0]);
 }
 assert.equal(JSON.stringify(s),before,'alternative-question wording must not establish an unresolved fact or rewrite false/known/insufficient records');
});

test('document focus follows its exact obligation and required fact when a node has multiple requirements',()=>{
 const s=state(),first=s.obligations[0];
 s.facts.push({fact_id:'fact:receipt',label:'Delivery date',status:'established'}, {fact_id:'fact:other-notice',label:'Second notice fact',status:'unresolved'});
 s.obligations.push({...first,obligation_id:'obligation:branch:receipt',document_type:'receipt',required_fact_ids:['fact:receipt']},
  {...first,obligation_id:'obligation:branch:other-notice',required_fact_ids:['fact:other-notice']});
 s.evaluation.documents.push({document_type:'receipt',route_state:'needed_now',review_state:'unreviewed'});
 const before=JSON.stringify(s),checklist=ui.obligationMarkup(s,'branch');
 for(const obligation of s.obligations) {
  const item=checklist.match(new RegExp(`<li[^>]*data-au-obligation="${obligation.obligation_id}"[\\s\\S]*?<\\/li>`))[0];
  assert.ok(item.includes(`data-au-select-document="${obligation.document_type}"`));
  assert.ok(item.includes(`data-au-select-obligation="${obligation.obligation_id}"`));
  assert.ok(item.includes(`data-au-select-fact="${obligation.required_fact_ids[0]}"`));
  const html=ui.evidencePathMarkup(s,'branch',{}, {document:obligation.document_type,obligation:obligation.obligation_id,trace:true});
  assert.match(html,new RegExp(`data-au-fact="${obligation.required_fact_ids[0]}"`),'a focused requirement defaults to its own required fact');
  assert.match(html,new RegExp(`data-au-document="${obligation.document_type}"[^>]*data-au-obligation="${obligation.obligation_id}"`));
 }
 assert.equal(JSON.stringify(s),before,'document focus is a read-only join over accepted state');
});

test('forming requirements wait for their actual requiring step, preserve own missing evidence and retire false routes',()=>{
 const saved=state();saved.evaluation.nodes.forEach(node=>node.activation='true');saved.evaluation.documents[0].activation='true';
 const ids=copy=>[...ui.formingMarkup(copy,{},'branch').matchAll(/<li[^>]*data-au-obligation="([^"]+)"/g)].map(match=>match[1]);
 assert.deepEqual(ids(saved),['obligation:branch:notice']);
 const future=structuredClone(saved);future.evaluation.nodes[1]={node_id:'branch',activation:'true',execution_state:'blocked',blocked_by:['start'],missing_document_types:['notice']};future.evaluation.documents[0].route_state='established';future.evaluation.documents[0].review_state='sufficient';
 assert.deepEqual(ids(future),[],'early sufficient source review cannot expose an unreached requiring step');
 const ownMissing=structuredClone(saved);ownMissing.evaluation.nodes[1]={node_id:'branch',activation:'true',execution_state:'blocked',blocked_by:[],unresolved_dependencies:[],missing_document_types:['notice']};
 assert.deepEqual(ids(ownMissing),['obligation:branch:notice'],'missing evidence at the active step cannot hide its own requirement');
 const ownLater=structuredClone(ownMissing);ownLater.evaluation.documents[0].route_state='needed_later';assert.deepEqual(ids(ownLater),['obligation:branch:notice']);
 for(const route of ['needed_later','held_behind_question','not_needed','optional']){const copy=structuredClone(saved);copy.evaluation.documents[0].route_state=route;assert.deepEqual(ids(copy),[],route);}
 for(const activation of ['false','unresolved',undefined]){const copy=structuredClone(future);copy.evaluation.nodes[1]={node_id:'branch',activation,execution_state:'completed'};assert.deepEqual(ids(copy),[],String(activation));}
 const retired=structuredClone(saved);retired.evaluation.nodes[1].activation='false';retired.evaluation.documents[0]={document_type:'notice',activation:'false',route_state:'not_needed',review_state:'sufficient'};assert.deepEqual(ids(retired),[]);assert.match(ui.obligationMarkup(retired,'branch'),/obligation:branch:notice/,'settled checklist retains the exact retired obligation');
 const incoming=structuredClone(saved);incoming.graph.family='incoming_packet';assert.deepEqual(ids(incoming),[],'acquisition requirements are not a final handling checklist');
});

function formingUnitStates() {
 const use={knowledge_id:'procedure.unit',version:2,definition_sha256:hash('2'),rule_pack_sha256:hash('3'),applicability:'same_verified_family_and_rule_version'},packet=state({claim_id:'unit-forming-case',revision:10,state_sha256:hash('1'),last_event_sha256:hash('a'),graph:{claim_id:'unit-forming-case',family:'incoming_packet',nodes:[{node_id:'incoming',label:'Read the original unit packet',entry:true}],edges:[]},evaluation:{nodes:[{node_id:'incoming',execution_state:'ready',activation:'true'}],edges:[],documents:[]},facts:[],obligations:[],actions:[],knowledge_uses:[use],knowledge_published:[]});
 packet.source_descriptors[0].claim_id=packet.claim_id;const body='Exact original unit source sentence.';packet.acquired_sources=[{claim_id:packet.claim_id,artifact_id:'original',sha256:hash('d'),text:body,text_sha256:sha(body),complete:true}];
 const interpreted=structuredClone(packet);interpreted.revision=11;interpreted.state_sha256=hash('4');interpreted.last_event_sha256=hash('b');
 interpreted.graph={claim_id:packet.claim_id,family:'unit_process',graph_sha256:hash('5'),nodes:Array.from({length:11},(_,index)=>({node_id:index===0?'intake':`question-${index}`,label:index===0?'Read the original unit packet':`Recorded question ${index}`,entry:index===0,condition:{flag:index===0?'intake':`question-${index}`}})),edges:Array.from({length:10},(_,index)=>({edge_id:`edge-${index}`,source_node_id:index===0?'intake':`question-${index}`,target_node_id:`question-${index+1}`}))};
 interpreted.facts=interpreted.graph.nodes.map((node,index)=>({fact_id:`condition:${node.node_id}`,status:index===0?'true':'unresolved',summary:index===0?'The original unit packet is recorded.':`Recorded question ${index} remains unestablished.`,citations:index===0?[{artifact_id:'original',sha256:hash('d'),text_sha256:sha(body),start_char:0,end_char:Array.from(body).length,quote:body}]:[]}));
 interpreted.obligations=interpreted.graph.nodes.map((node,index)=>({obligation_id:`unit-requirement-${index}`,document_type:`unit_document_${index}`,label:`Recorded document ${index}`,node_id:node.node_id,required_fact_ids:[`condition:${node.node_id}`]}));
 interpreted.evaluation={nodes:interpreted.graph.nodes.map((node,index)=>({node_id:node.node_id,activation:index===0?'true':'unresolved',execution_state:index===0?'ready':'unresolved'})),edges:interpreted.graph.edges.map(edge=>({edge_id:edge.edge_id,activation:'unresolved'})),documents:interpreted.obligations.map((obligation,index)=>({document_type:obligation.document_type,activation:index===0?'true':'unresolved',route_state:index===0?'needed_now':'held_behind_question',review_state:'unreviewed'}))};
 const reviewed=structuredClone(interpreted);reviewed.revision=13;reviewed.state_sha256=hash('6');reviewed.last_event_sha256=hash('c');reviewed.evaluation.documents[4].review_state='sufficient';reviewed.facts.push({fact_id:'document:unit_document_4',document_type:'unit_document_4',status:'sufficient',summary:'The source supports this particular unit document review.',citations:interpreted.facts[0].citations});
 const settled=structuredClone(reviewed);settled.revision=15;settled.state_sha256=hash('7');settled.last_event_sha256=hash('e');settled.status='deferred';settled.outcome={status:'deferred',summary:'The recorded questions remain unresolved.',unresolved_facts:interpreted.facts.slice(1)};settled.knowledge_published=[{knowledge_id:'procedure.unit',version:3,source_claim_id:settled.claim_id,knowledge_sha256:hash('8'),qualification:{status:'qualified',definition_sha256:hash('9')},added_document_types:['unit_document_4'],evidence_recipes:[{document_type:'unit_document_4',required_fields:['recorded_sender','recorded_date']}],obligations:[reviewed.obligations[4]]}];
 return {packet,interpreted,reviewed,settled};
}
function formingUnitReplay(state) {return{state,mode:'replay',replay_only:true,through_seq:state.revision,current_revision:15,current_state_sha256:hash('7'),current_event_sha256:hash('e')};}

test('forming work keeps the whole accepted graph obligations and pinned knowledge together without an intermediate process',()=>{
 const {packet,interpreted,reviewed,settled}=formingUnitStates(),before=JSON.stringify({packet,interpreted,reviewed,settled});
 const early=ui.workMarkup(packet,{},'incoming',[],'step',{}, {mode:'replay',replay:formingUnitReplay(packet)});assert.match(early,/data-au-forming/);assert.deepEqual([...early.matchAll(/data-au-node="([^"]+)"/g)].map(match=>match[1]),['incoming']);assert.doesNotMatch(early,/data-au-obligation="unit-requirement-|data-au-node="question-/);assert.match(early,/data-au-version="2"[^>]*data-au-definition-sha="2{64}"/);assert.deepEqual(ui.contextualRecord(packet,{},[],'claim').state.facts,[],'reuse cannot establish a current-case fact');
 for(const state of [interpreted,reviewed]) {
  const html=ui.workMarkup(state,{},'question-4',[],'step',{}, {mode:'replay',replay:formingUnitReplay(state),paused:true});assert.match(html,/data-au-forming/);assert.match(html,/au-forming-process/);assert.match(html,/au-forming-documents/);assert.match(html,/au-forming-knowledge/);
  assert.deepEqual(new Set([...html.matchAll(/data-au-node="([^"]+)"/g)].map(match=>match[1])),new Set(state.graph.nodes.map(node=>node.node_id)));assert.deepEqual(new Set([...html.matchAll(/data-au-obligation="([^"]+)"/g)].map(match=>match[1])),new Set(['unit-requirement-0']));
  for(const obligation of state.obligations.slice(0,1)){assert.ok(html.includes(`data-au-select-obligation="${obligation.obligation_id}"`));assert.ok(html.includes(`data-au-select="${obligation.node_id}"`));}
  assert.match(html,/data-au-version="2"[^>]*data-au-definition-sha="2{64}"/);assert.deepEqual(ui.contextualRecord(state,{},[],'claim'),{state,projection:{}});
 }
 assert.equal(ui.formingWork(interpreted,{mode:'saved'}),true);assert.equal(ui.formingWork(settled,{mode:'saved'}),false);assert.equal(ui.formingWork(reviewed,{mode:'replay',replay:formingUnitReplay(reviewed),paused:true}),true);assert.equal(ui.formingWork(settled,{mode:'replay',replay:formingUnitReplay(settled)}),false);assert.equal(ui.formingWork(settled,{mode:'replay',replay:formingUnitReplay(settled),playing:true}),true,'the actual final publication remains visible during its accepted presentation before settling');assert.equal(ui.formingWork(reviewed,{mode:'replay',replay:{...formingUnitReplay(reviewed),state:{...reviewed,state_sha256:hash('0')}},playing:true}),false,'playing cannot bypass replay identity');assert.equal(JSON.stringify({packet,interpreted,reviewed,settled}),before);
});

test('sufficient future source review stays inspectable without appearing as an active requirement',()=>{
 const {reviewed}=formingUnitStates(),before=JSON.stringify(reviewed),html=ui.formingMarkup(reviewed,{},'question-4');
 assert.doesNotMatch(html,/data-au-obligation="unit-requirement-4"|data-au-review="sufficient"|May be needed/);
 assert.equal(ui.contextualRecord(reviewed,{},[],'requirement','unit-requirement-4').evaluation[0].review_state,'sufficient');
 assert.match(ui.obligationMarkup(reviewed,'question-4'),/data-au-review="sufficient"/,'the complete checklist preserves early review separately from activation');
 assert.equal(JSON.stringify(reviewed),before);
});

test('forming mixed routes expose only reached requirements and never inherit checks from received sources or completed nodes',()=>{
 const {reviewed}=formingUnitStates();reachFormingRequirement(reviewed,2);reviewed.evaluation.documents[2].route_state='needed_now';
 const before=JSON.stringify(reviewed),html=ui.formingMarkup(reviewed,{},'question-4');
 assert.match(html,/data-au-obligation="unit-requirement-2"/);assert.doesNotMatch(html,/data-au-obligation="unit-requirement-(?:4|5)"|May be needed/);
 for(const review of [undefined,'received','unreviewed','missing','unresolved','insufficient','satisfied']){
  const copy=structuredClone(reviewed);reachFormingRequirement(copy,4);copy.evaluation.nodes[4].execution_state='completed';copy.evaluation.documents[4].review_state=review;
  const row=ui.formingMarkup(copy,{},'question-4').match(/<li[^>]*data-au-obligation="unit-requirement-4"[\s\S]*?<\/li>/)[0];
  assert.doesNotMatch(row,/<span aria-hidden="true">✓<\/span>/,String(review));
 }
 assert.match(ui.documentReviewMarkup('sufficient'),/<span aria-hidden="true">✓<\/span>/);assert.equal(JSON.stringify(reviewed),before);
});

function reachFormingRequirement(saved,index){Object.assign(saved.evaluation.nodes[index],{activation:'true',execution_state:'ready',blocked_by:[],unresolved_dependencies:[]});Object.assign(saved.evaluation.documents[index],{activation:'true',route_state:saved.evaluation.documents[index].review_state==='sufficient'?'established':'needed_now'});}

test('forming assessed requirements list a source file once while all three exact cited passages remain inspectable',()=>{
 const {reviewed}=formingUnitStates(),context={fact:'document:unit_document_4',document:'unit_document_4',obligation:'unit-requirement-4'},fact=reviewed.facts.find(item=>item.fact_id===context.fact),body=reviewed.acquired_sources[0].text;
 reachFormingRequirement(reviewed,4);
 fact.citations=['Exact','original','unit'].map(quote=>({...fact.citations[0],quote,start_char:Array.from(body.slice(0,body.indexOf(quote))).length,end_char:Array.from(body.slice(0,body.indexOf(quote)+quote.length)).length}));reviewed.obligations[4].required_fact_ids.push(context.fact);
 const before=JSON.stringify(reviewed),html=ui.workMarkup(reviewed,{},'question-4',[],'step',context,{mode:'saved'}),row=html.match(/<li[^>]*data-au-obligation="unit-requirement-4"[\s\S]*?<\/li>/)[0],passages=html.match(/<section class="au-reading-passages">[\s\S]*?<\/section>/)[0];
 assert.equal((row.match(/class="au-link au-document-source"/g)||[]).length,1);assert.equal((row.match(/data-au-source="original"/g)||[]).length,1);assert.match(row,/data-au-source-origin="requirement:unit-requirement-4"/);assert.match(row,/Supplied evidence is sufficient\./);
 assert.equal((passages.match(/data-au-source="original"/g)||[]).length,3);assert.deepEqual([...passages.matchAll(/<q>([^<]*)<\/q>/g)].map(match=>match[1]),fact.citations.map(citation=>citation.quote));
 for(const citation of fact.citations)assert.equal(Array.from(body).slice(citation.start_char,citation.end_char).join(''),citation.quote);assert.deepEqual(ui.contextualRecord(reviewed,{},[],'fact',context.fact).citations,fact.citations);assert.deepEqual(ui.contextualRecord(reviewed,{},[],'claim').state,reviewed);assert.equal(JSON.stringify(reviewed),before,'file-link deduplication must not collapse passage or full-history provenance');
});

test('forming connections join only the selected accepted fact exact source span and its requiring node and obligation',()=>{
 const {reviewed}=formingUnitStates(),context={fact:'document:unit_document_4',document:'unit_document_4',obligation:'unit-requirement-4'};
 reachFormingRequirement(reviewed,4);reviewed.obligations[4].required_fact_ids.push(context.fact);
 const fact=reviewed.facts.find(item=>item.fact_id===context.fact),before=JSON.stringify(reviewed),relation=ui.formingRelations(reviewed,'question-4',context);
 assert.deepEqual(relation,{fact:context.fact,source:'original',node:'question-4',obligation:context.obligation,citation:fact.citations[0]});
 const html=ui.workMarkup(reviewed,{},'question-4',[],'step',context,{mode:'saved'}),paths=[...html.matchAll(/<path data-au-forming-wire="([^"]+)"([^>]*)>/g)];
 assert.deepEqual(paths.map(match=>match[1]),['source-process','process-document']);
 for(const [, ,attributes] of paths)for(const [key,value] of Object.entries({fact:context.fact,source:'original',node:'question-4',obligation:context.obligation}))assert.ok(attributes.includes(`data-au-wire-${key}="${value}"`));
 assert.ok(html.indexOf('class="au-forming-reading"')<html.indexOf('class="au-forming-process '));assert.ok(html.indexOf('class="au-forming-process ')<html.indexOf('class="au-forming-documents"'));
 assert.match(html,/data-au-node="question-4"[^>]*aria-pressed="true"/);assert.match(html,/data-au-select-obligation="unit-requirement-4"/);assert.deepEqual(ui.contextualRecord(reviewed,{},[],'fact',context.fact),fact);
 const cases=[['descriptor hash',copy=>{copy.source_descriptors[0].sha256=hash('0');}],['acquired hash',copy=>{copy.acquired_sources[0].sha256=hash('0');}],['citation source hash',copy=>{copy.facts.at(-1).citations[0].sha256=hash('0');}],['citation text hash',copy=>{copy.facts.at(-1).citations[0].text_sha256=hash('0');}],['wrong quote',copy=>{copy.facts.at(-1).citations[0].quote='Unaccepted source quote';}],['wrong span',copy=>{copy.facts.at(-1).citations[0].start_char=1;}],['out of bounds span',copy=>{copy.facts.at(-1).citations[0].end_char=1000;}],['unacquired source',copy=>{copy.acquired_sources=[];}]];
 for(const [label,change] of cases){const copy=structuredClone(reviewed);change(copy);assert.equal(ui.formingRelations(copy,'question-4',context),null,label);assert.doesNotMatch(ui.formingMarkup(copy,{},'question-4',[],context),/data-au-forming-wire=/,label);}
 assert.equal(ui.formingRelations(reviewed,'question-5',{...context,document:'unit_document_5',obligation:'unit-requirement-5'}),null,'an unrelated sufficient document cannot light up another decision');
 const withoutRequirement=structuredClone(reviewed);withoutRequirement.obligations[4].required_fact_ids=[context.fact];withoutRequirement.obligations[4].node_id='question-5';assert.equal(ui.formingRelations(withoutRequirement,'question-4',context),null,'an obligation cannot supply a fact to a different requiring node');
 assert.equal(JSON.stringify(reviewed),before,'connection selection must preserve every accepted record');
});

test('forming publication remains central for a deferred live accepted publication followed by a phase without inventing an intermediate revision',()=>{
 const {reviewed,settled}=formingUnitStates(),prior={...structuredClone(reviewed),revision:14,state_sha256:hash('f'),last_event_sha256:hash('f'),status:'deferred'},head={...structuredClone(settled),revision:16,state_sha256:hash('a'),last_event_sha256:hash('b')},publication=head.knowledge_published[0];
 const published={claim_id:head.claim_id,seq:15,revision:15,state_sha256:settled.state_sha256,event_sha256:settled.last_event_sha256,previous_event_sha256:prior.last_event_sha256,kind:'knowledge.published',payload:{knowledge:publication}},phase={claim_id:head.claim_id,seq:16,revision:16,state_sha256:head.state_sha256,event_sha256:head.last_event_sha256,previous_event_sha256:published.event_sha256,kind:'work.phase'},history=[published,phase],accepted=ui.acceptEvents(14,{current_revision:16,current_state_sha256:head.state_sha256,events:history},head),changes=ui.transitionPlan(prior,head,accepted,history),attention={previousRevision:14,revision:16,acceptedEvents:accepted.events,knowledgePublications:changes.knowledgePublications},before=JSON.stringify({prior,head,history,attention});
 assert.deepEqual(attention.knowledgePublications.map(row=>row.id),[publication.knowledge_sha256]);assert.equal(ui.formingWork(head,{mode:'saved'}),false);
 const focused=ui.formingPublication(head,history,attention);assert.equal(focused.seq,15);assert.equal(focused.id,published.event_sha256);assert.deepEqual(focused.knowledge,publication);
 const live=ui.workMarkup(head,{},'question-4',history,'step',{}, {mode:'saved',attention});assert.match(live,/data-au-forming-revision="16"/);assert.doesNotMatch(live,/data-au-forming-revision="15"/);assert.match(live,/data-au-publication-focus="e{64}"/);assert.match(live,/data-au-knowledge-publication="8{64}"/);assert.match(live,/Added for reuse · Version 3/);assert.match(live,/data-au-version="3"[^>]*data-au-knowledge-sha="8{64}"[^>]*data-au-definition-sha="9{64}"/);assert.match(live,/recorded sender, recorded date/);
 const compact=live.match(/<div class="au-forming-publication-focus"[^>]*>([\s\S]*?)<\/div>/)[1];assert.match(compact,/class="au-forming-used-version" data-au-knowledge-use="procedure\.unit"/);assert.match(compact,/data-au-knowledge="procedure\.unit" data-au-version="2" data-au-knowledge-sha="" data-au-definition-sha="2{64}"[^>]*>Used version 2<\/button>/);assert.equal((live.match(/data-au-knowledge="procedure\.unit" data-au-version="2"/g)||[]).length,1,'compact publication focus keeps one exact link to the actually used version');assert.doesNotMatch(live,/data-au-inspector-heading="question-4"|class="au-knowledge-use"/,'the selected question and reused procedure are not repeated as extra headings during accepted publication focus');assert.match(live,/data-au-node="question-4"[^>]*aria-pressed="true"/);
 assert.deepEqual([...live.matchAll(/data-au-node="([^"]+)"/g)].map(match=>match[1]),head.graph.nodes.map(node=>node.node_id));assert.deepEqual([...live.matchAll(/data-au-edge="([^"]+)"/g)].map(match=>match[1]),head.graph.edges.map(edge=>edge.edge_id));assert.deepEqual(new Set([...live.matchAll(/data-au-obligation="([^"]+)"/g)].map(match=>match[1])),new Set(['unit-requirement-0']));assert.deepEqual(ui.contextualRecord(head,{},history,'claim'),{state:head,projection:{}});assert.deepEqual(ui.contextualRecord(head,{},history,'use','0'),head.knowledge_uses[0]);
 assert.match(ui.workMarkup(reviewed,{},'question-4',[],'step',{}, {mode:'saved'}),/data-au-inspector-heading="question-4"/,'ordinary prepublication prefixes retain the selected-question heading');
 const replay={state:head,mode:'replay',replay_only:true,through_seq:16,current_revision:16,current_state_sha256:head.state_sha256,current_event_sha256:head.last_event_sha256};assert.match(ui.workMarkup(head,{},'question-4',history,'step',{}, {mode:'replay',replay,attention}),/data-au-publication-focus="e{64}"/);
 for(const invalid of [{},{...attention,previousRevision:15},{...attention,knowledgePublications:[]},{...attention,knowledgePublications:[{id:hash('0')}]},{...attention,acceptedEvents:[{...published,event_sha256:hash('0')},phase]}]){assert.equal(ui.formingPublication(head,history,invalid),null);assert.doesNotMatch(ui.workMarkup(head,{},'question-4',history,'step',{}, {mode:'saved',attention:invalid}),/data-au-forming="true"|data-au-publication-focus=/);}
 const foreign={...published,claim_id:'another-claim'};assert.equal(ui.formingPublication(head,[foreign,phase],{...attention,acceptedEvents:[foreign,phase]}),null);const withheld=structuredClone(head);withheld.knowledge_published[0].qualification.status='quarantined';assert.equal(ui.formingPublication(withheld,history,attention),null);
 assert.doesNotMatch(ui.workMarkup(head,{},'question-4',history,'step',{}, {mode:'saved',knowledge:{versions:[{...publication,version:99}]}}),/data-au-publication-focus=|data-au-version="99"/,'a lifetime publication or global latest lookup cannot create current attention');
 assert.doesNotMatch(ui.workMarkup(head,{},'question-4',history,'step',{}, {mode:'saved',attention,inspectionHold:true}),/data-au-forming="true"|data-au-publication-focus=/,'new attention cannot restructure a manually inspected saved view');assert.match(ui.workMarkup(head,{},'question-4',history,'step',{}, {mode:'saved',attention:{...attention,retained:true},inspectionHold:true}),/data-au-forming-revision="16"[\s\S]*data-au-publication-focus="e{64}"/,'already visible accepted attention stays in place during inspection');
 assert.equal(JSON.stringify({prior,head,history,attention}),before,'live and replay presentation must retain the actual revision and raw publication unchanged');
});

test('a multi-node requirement selects its genuinely reached node after an upstream-blocked sibling',()=>{
 const after=state();after.graph.nodes.unshift({node_id:'future',label:'A later prerequisite'});after.evaluation.nodes.unshift({node_id:'future',activation:'true',execution_state:'blocked',blocked_by:['start']});after.obligations[0].node_id='future';after.obligations[0].decision_node_id='future';after.obligations[0].node_ids=['branch'];
 const before=structuredClone(after);before.evaluation.nodes.find(row=>row.node_id==='branch').execution_state='blocked';before.evaluation.nodes.find(row=>row.node_id==='branch').blocked_by=['start'];
 assert.deepEqual(ui.enteredRequirementContext(before,after),{node:'branch',document:'notice',obligation:'obligation:branch:notice',fact:'fact:notice'});
 assert.match(ui.obligationMarkup(after,'branch',ui.formingRequirements(after),{},true),/data-au-select="branch"/);assert.doesNotMatch(ui.obligationMarkup(after,'branch',ui.formingRequirements(after),{},true),/data-au-select="future"/);
 const reached=after.evaluation.nodes.find(row=>row.node_id==='branch');Object.assign(reached,{execution_state:'blocked',blocked_by:[],unresolved_dependencies:[],missing_document_types:['notice']});assert.equal(ui.enteredRequirementContext(before,after).node,'branch','own missing evidence stays a reached requiring node');
});

test('shared document types keep each obligation attached to its own reached requiring node',()=>{
 const saved=state();saved.graph.nodes.push({node_id:'future',label:'Later service'});saved.evaluation.nodes.push({node_id:'future',activation:'true',execution_state:'blocked',blocked_by:['branch']});saved.obligations.push({...saved.obligations[0],obligation_id:'obligation:future:notice',node_id:'future',decision_node_id:'future'});saved.evaluation.documents[0].required_at_node_ids=['branch','future'];
 assert.deepEqual(ui.formingRequirements(saved).map(ui.requirementIdentity),['obligation:branch:notice']);
 const before=structuredClone(saved);saved.revision=4;saved.state_sha256=hash('f');saved.evaluation.nodes[2].execution_state='ready';saved.evaluation.nodes[2].blocked_by=[];
 const event={claim_id:saved.claim_id,seq:4,revision:4,state_sha256:saved.state_sha256,event_sha256:hash('9'),kind:'graph.advanced'},plan=ui.transitionPlan(before,saved,{ready:true,cursor:4,animate:[event]});
 assert.ok(plan.documents.some(row=>row.id==='notice'),'the accepted readiness change introduces an already-reviewed document');
});

test('a reached obligation entrance animates only its exact identity when another visible obligation shares the document type',()=>{
 const before=state();before.graph.nodes.push({node_id:'future',label:'Next requiring step'});before.evaluation.nodes.push({node_id:'future',activation:'true',execution_state:'blocked',blocked_by:['branch']});before.obligations.push({...before.obligations[0],node_id:'future',decision_node_id:'future',obligation_id:'obligation:future:notice'});
 const after=structuredClone(before);after.revision=4;after.state_sha256=hash('f');after.evaluation.nodes[2].execution_state='ready';after.evaluation.nodes[2].blocked_by=[];after.evaluation.documents[0].active_node_ids=['branch','future'];const event={claim_id:after.claim_id,seq:4,revision:4,state_sha256:after.state_sha256,event_sha256:hash('9'),kind:'graph.advanced'},plan=ui.transitionPlan(before,after,{ready:true,cursor:4,animate:[event]});
 assert.deepEqual(plan.documents[0].obligationIds,['obligation:future:notice']);const calls=[],path={};const rows=['obligation:branch:notice','obligation:future:notice'].map(id=>({dataset:{auDocument:'notice',auObligation:id},closest:selector=>selector==='[data-au-evidence-path]'?path:null,animate:(frames,options)=>{calls.push(id);return {cancel(){}};}}));const host={querySelector(){return null;},querySelectorAll:selector=>selector==='[data-au-document]'?rows:[]};ui.animateTransition(host,plan,{selected:'future'});assert.deepEqual(calls,['obligation:future:notice']);
});

test('case-language conditions retain nested all any and not scope and the recorded three-valued route truth',()=>{
 const saved=state(),expression={all:[{not:{flag:'arrears'}},{any:[{flag:'family_home'},{not:{flag:'extension_relevant'}}]}]},before=JSON.stringify(expression);
 assert.equal(ui.conditionLabel(saved,{flag:'arrears'}),'Rent arrears');assert.equal(ui.conditionLabel(saved,{flag:'extension_relevant'}),'Tenancy extension');assert.equal(ui.conditionLabel(saved,{not:{flag:'extension_relevant'}}),'No tenancy extension');assert.equal(ui.conditionLabel(saved,{all:[{not:{flag:'arrears'}},{not:{flag:'family_home'}}]}),'No rent arrears and not a family home');
 assert.equal(ui.conditionLabel(saved,expression),'No rent arrears and (Family home or no tenancy extension)');assert.equal(ui.conditionLabel(saved,{not:{any:[{flag:'family_home'},{all:[{flag:'arrears'},{not:{flag:'extension_relevant'}}]}]}}),'Not (Family home or (Rent arrears and no tenancy extension))');assert.equal(ui.conditionLabel(saved,{not:{not:{flag:'family_home'}}}),'Family home');assert.equal(ui.conditionLabel(saved,{any:[{const:'true'},{flag:'arrears'}]}),'Always or Rent arrears');
 const evaluate=(value,flags)=>value.flag?flags[value.flag]:value.not?{true:'false',false:'true',unresolved:'unresolved'}[evaluate(value.not,flags)]:value.all?value.all.map(child=>evaluate(child,flags)).includes('false')?'false':value.all.every(child=>evaluate(child,flags)==='true')?'true':'unresolved':value.any.map(child=>evaluate(child,flags)).includes('true')?'true':value.any.every(child=>evaluate(child,flags)==='false')?'false':'unresolved';
 for(const [flags,verdict,label]of [[{arrears:'false',family_home:'true',extension_relevant:'true'},'true','Applies'],[{arrears:'true',family_home:'true',extension_relevant:'false'},'false','Excluded'],[{arrears:'unresolved',family_home:'false',extension_relevant:'false'},'unresolved','Unresolved']]){
  assert.equal(evaluate(expression,flags),verdict);saved.graph.edges[0].condition=expression;saved.evaluation.edges=[{edge_id:'next',activation:verdict}];const html=ui.graphMarkup(saved,'branch',{}, {overview:true});assert.ok(html.includes(`No rent arrears and (Family home or no tenancy extension)<span>${label}</span>`));assert.equal(ui.contextualRecord(saved,{},[],'step','branch').edges[0].condition,expression);
 }
 assert.equal(JSON.stringify(expression),before,'label formatting never changes the accepted expression');
});

test('real conditional split and join labels preserve applied excluded and unresolved edge states without labelling a linear unconditional dependency',()=>{
 const saved=state();saved.graph.nodes.push({node_id:'other',label:'Other route'},{node_id:'join',label:'Join the recorded routes'});saved.graph.edges=[{edge_id:'selected',source_node_id:'start',target_node_id:'branch',condition:{flag:'family_home'}},{edge_id:'other',source_node_id:'start',target_node_id:'other',condition:{not:{flag:'family_home'}}},{edge_id:'join-left',source_node_id:'branch',target_node_id:'join',condition:{const:true}},{edge_id:'join-right',source_node_id:'other',target_node_id:'join',condition:{flag:'unresolved_guard'}}];saved.evaluation.edges=[{edge_id:'selected',activation:'true'},{edge_id:'other',activation:'false'},{edge_id:'join-left',activation:'true'},{edge_id:'join-right',activation:'unresolved'}];
 const before=JSON.stringify(saved),html=ui.graphMarkup(saved,'branch',{}, {overview:true});assert.deepEqual(ui.layoutGraph(saved.graph).rows.map(row=>row.map(node=>node.node_id)),[['start'],['branch','other'],['join']]);
 for(const [id,label,status]of [['selected','Family home','Applies'],['other','Not a family home','Excluded'],['join-right','Unresolved guard','Unresolved']])assert.match(html,new RegExp(`data-au-edge-label="${id}"[^>]*>${label.replace(/[()]/g,'\\$&')}<span>${status}</span>`));
 assert.doesNotMatch(html,/data-au-edge-label="join-left"/);assert.equal((html.match(/marker-end="url/g)||[]).length,4);assert.equal(JSON.stringify(saved),before);
});

test('forming requirements retire only on recorded route exclusion while History and Documents retain exact earlier obligations',()=>{
 const {interpreted}=formingUnitStates();interpreted.evaluation.documents[2].route_state='not_needed';interpreted.evaluation.documents[3].route_state='excluded';interpreted.evaluation.nodes[4].activation='false';const before=JSON.stringify(interpreted),html=ui.workMarkup(interpreted,{},'question-4',[],'step',{}, {mode:'saved'}),documents=ui.workMarkup(interpreted,{},'question-4',[],'documents');
 assert.match(html,/data-au-forming/);assert.doesNotMatch(html,/data-au-obligation="unit-requirement-(?:2|3)"/);assert.doesNotMatch(html,/data-au-obligation="unit-requirement-4"/,'an inapplicable requiring node removes its row without rewriting the checklist');
 for(const obligation of interpreted.obligations)assert.ok(documents.includes(`data-au-obligation="${obligation.obligation_id}"`));assert.deepEqual(ui.contextualRecord(interpreted,{},[],'claim').state.obligations,interpreted.obligations);assert.equal(ui.contextualRecord(interpreted,{},[],'requirement','unit-requirement-2').evaluation[0].route_state,'not_needed');assert.equal(ui.contextualRecord(interpreted,{},[],'requirement','unit-requirement-3').evaluation[0].route_state,'excluded');assert.equal(JSON.stringify(interpreted),before);
});

test('forming motion maps atomic interpretation and source review to exact changed objects without completing an unresolved decision',()=>{
 const {packet,interpreted,reviewed,settled}=formingUnitStates(),event=state=>({claim_id:state.claim_id,seq:state.revision,revision:state.revision,state_sha256:state.state_sha256,event_sha256:state.last_event_sha256,kind:'interpretation.accepted'}),interpretation=event(interpreted),batch={current_revision:11,current_state_sha256:interpreted.state_sha256,events:[interpretation]},accepted=ui.acceptEvents(10,batch,interpreted),before=JSON.stringify({packet,interpreted,reviewed,settled});
 const formed=ui.transitionPlan(packet,interpreted,accepted,[interpretation]);assert.ok(formed);assert.deepEqual(new Set(formed.nodes.map(row=>row.id)),new Set(interpreted.graph.nodes.map(node=>node.node_id)));assert.deepEqual(new Set(formed.documents.map(row=>row.id)),new Set(interpreted.obligations.map(obligation=>obligation.document_type)));assert.deepEqual(formed.knowledgeUses,[],'a retained version use cannot become a new reuse event');
 const phase={claim_id:reviewed.claim_id,seq:12,revision:12,state_sha256:hash('f'),event_sha256:hash('f'),kind:'work.phase'},review={...event(reviewed),kind:'action.completed',payload:{result:{action_id:'unit-source-review',node_ids:['question-4'],document_type:'unit_document_4',status:'completed',verdict:'sufficient'},receipt:{receipt_sha256:hash('d')}}};
 const reviewPlan=ui.transitionPlan(interpreted,reviewed,ui.acceptEvents(11,{current_revision:13,current_state_sha256:reviewed.state_sha256,events:[phase,review]},reviewed),[interpretation,phase,review]);assert.ok(reviewPlan);assert.deepEqual(reviewPlan.nodes,[]);assert.deepEqual(reviewPlan.edges,[]);assert.deepEqual(reviewPlan.documents.map(row=>row.id),['unit_document_4']);assert.deepEqual(reviewPlan.facts.map(row=>row.id),['document:unit_document_4']);
 for(const plan of [formed,reviewPlan]){assert.ok(plan.duration<=800);for(const row of [...plan.sources,...plan.facts,...plan.nodes,...plan.edges,...plan.documents,...plan.knowledgeUses,...plan.knowledgePublications])assert.ok(row.delay+row.duration<=800);if(plan.facts.length&&plan.documents.length)assert.ok(Math.max(...plan.facts.map(row=>row.delay+row.duration))<=Math.min(...plan.documents.map(row=>row.delay)));}
 assert.equal(ui.transitionPlan(packet,interpreted,{...accepted,animate:[]},[]),null);assert.equal(ui.transitionPlan(packet,interpreted,ui.acceptEvents(10,batch,interpreted,true),[]),null);assert.equal(ui.transitionPlan(interpreted,interpreted,{...accepted,animate:[interpretation]},[]),null);assert.throws(()=>ui.acceptEvents(10,{...batch,events:[{...interpretation,claim_id:'another-claim'}]},interpreted),/claim/);assert.throws(()=>ui.acceptEvents(10,{...batch,events:[{...interpretation,state_sha256:hash('0')}]},interpreted),/identity/);assert.equal(JSON.stringify({packet,interpreted,reviewed,settled}),before);
});

function assessedState(extra={}) {
 const s=state({run_id:'accepted-run',source_roster_sha256:hash('1'),...extra});
 s.semantic_contexts={'accepted-run':{claim_id:s.claim_id,workflow_id:'accepted-run',sources:s.source_descriptors.map(source=>({artifact_id:source.artifact_id,sha256:source.sha256}))}};
 s.receipts=[{kind:'interpretation.accepted',receipt:{operation:'interpretation.accept',workflow_id:'accepted-run',receipt_sha256:hash('2'),parent_revision:1,parent_state_sha256:hash('3'),checks:[{item_id:'condition:family_home',accepted:true}]}}];
 return s;
}

test('prior assessment labels survive new source acquisition and failed rereading without rewriting valid evidence',()=>{
 const accepted=assessedState(),sameRosterRetry={...structuredClone(accepted),run_id:'retry-run',status:'deferred',deferral:{code:'model_unavailable'}};
 assert.doesNotMatch(ui.workMarkup(sameRosterRetry,{},'branch',[]),/data-au-assessment-freshness="prior"/,'a changed run alone does not make a same-input assessment stale');
 const fresh={claim_id:accepted.claim_id,artifact_id:'later-source',file_name:'later-statement.txt',sha256:hash('4'),role:'supporting_document',media_type:'text/plain'};
 for(const acquired of [false,true]) for(const code of ['model_unavailable','call_limit_reached','verification_deferred']) {
  const s=structuredClone(accepted);s.source_descriptors.push(fresh);s.source_roster_sha256=hash('5');s.run_id='retry-run';s.status='deferred';s.deferral={code,reason:'The new evidence has no accepted reassessment.'};
  if(acquired)s.acquired_sources.push({artifact_id:fresh.artifact_id,complete:true,extraction:'utf8'});
  const before=JSON.stringify(s),html=ui.workMarkup(s,{},'branch',[],'sources');
  assert.equal(ui.assessmentFreshness(s).status,'prior');assert.deepEqual(ui.assessmentFreshness(s).sources,[fresh]);assert.match(html,/Earlier findings · new sources await review\./);assert.match(html,/Awaiting assessment/);
  assert.match(html,/data-au-source-freshness="unassessed"/);assert.ok(html.includes(fresh.file_name));
  assert.deepEqual(ui.contextualRecord(s,{},[],'fact','condition:family_home'),accepted.facts[0]);assert.deepEqual(ui.contextualRecord(s,{},[],'action','0').receipt,s.actions[0].receipt);
  assert.doesNotMatch(html,/New evidence contradicts|Contradiction established|Earlier assessment invalid/);
  assert.equal(JSON.stringify(s),before,'presentation must preserve the complete accepted state byte for byte');
 }
 assert.equal(JSON.stringify(accepted),JSON.stringify(assessedState()));
});

test('an accepted reassessment clears freshness only when its bound roster matches; historical prefixes use their own sources',()=>{
 const prior=assessedState(),next=structuredClone(prior),fresh={claim_id:prior.claim_id,artifact_id:'later-source',file_name:'later-statement.txt',sha256:hash('4'),role:'supporting_document'};
 next.source_descriptors.push(fresh);next.run_id='reassessed-run';next.semantic_contexts[next.run_id]={claim_id:next.claim_id,sources:next.source_descriptors.map(source=>({artifact_id:source.artifact_id,sha256:source.sha256}))};
 next.receipts.push({kind:'interpretation.accepted',receipt:{...prior.receipts[0].receipt,workflow_id:next.run_id,receipt_sha256:hash('6'),parent_revision:3}});
 next.facts[0].status='false';next.facts[0].summary='The accepted reassessment records a different family-home condition.';
 for(const s of [prior,next]) {
  const before=JSON.stringify(s),html=ui.workMarkup(s,{},'branch',[]);
  assert.doesNotMatch(html,/data-au-assessment-freshness="prior"|data-au-source-freshness="unassessed"/);
  assert.equal(JSON.stringify(s),before);
 }
 // A latest receipt without its accepted input context cannot borrow another
 // run's roster and claim that its sources were assessed.
 delete next.semantic_contexts[next.run_id];
 assert.doesNotMatch(ui.workMarkup(next,{},'branch',[]),/Prior assessment/);
 const unbound=state({source_descriptors:[...prior.source_descriptors,fresh]});
 assert.doesNotMatch(ui.workMarkup(unbound,{},'branch',[]),/Prior assessment/,'no accepted binding means unknown assessment coverage, not an invented prior assessment');
});

test('deferral and prepared request retain missing evidence and external authority boundary',()=>{
 const s=state({status:'deferred',outcome:{status:'deferred',title:'Evidence assessed',summary:'Service is not yet established.',missing_evidence:[{label:'Separate notice'}],authority_limits:['External filing is not configured.'],request_draft:{status:'prepared_not_sent',subject:'Evidence request',body:'Please provide the notice.'}}});
 const before=JSON.stringify(s),record=ui.contextualRecord(s,{},[],'outcome');assert.deepEqual(record.outcome,s.outcome);
 assert.equal(record.outcome.request_draft.status,'prepared_not_sent');assert.deepEqual(record.outcome.missing_evidence,[{label:'Separate notice'}]);assert.deepEqual(record.outcome.authority_limits,['External filing is not configured.']);
 assert.doesNotMatch(ui.workMarkup(s,{},'branch',[]),/>Approve|>Apply|>Send request/);
 assert.match(ui.workMarkup(state({status:'deferred',deferral:{code:'unsupported_format',reason:'The image has no supported extraction.'}}),{},'start',[]),/The image has no supported extraction/);assert.equal(JSON.stringify(s),before);
});

test('missing reviews do not hide received unassigned originals or infer their document type',()=>{
 const s=state(),descriptor=(id,file_name,media_type='text/plain')=>({claim_id:s.claim_id,artifact_id:id,file_name,media_type,role:'supporting_document',sha256:hash('d')});
 s.source_descriptors=[{...s.source_descriptors[0],role:'customer_message'},descriptor('photo','notice.jpg','image/jpeg'),descriptor('partial','partial.txt'),descriptor('complete','complete.txt'),descriptor('received','received.txt'),descriptor('assigned','assigned.txt')];
 s.acquired_sources=[{artifact_id:'photo',extraction:'unsupported_metadata',complete:false},{artifact_id:'partial',extraction:'utf8',complete:false},{artifact_id:'complete',extraction:'utf8',complete:true}];
 s.graph.document_catalog=[{document_type:'notice',held_files:[{artifact_id:'assigned',review:'insufficient'}]}];
 s.evaluation.documents[0].review_state='missing';
 const before=JSON.stringify(s),html=ui.workMarkup(s,{},'branch',[],'documents');
 const docs=html.match(/<section class="au-supporting"><h3>Files awaiting a document assignment<\/h3>([\s\S]*?)<\/section>/)[1];
 for(const id of ['photo','partial','complete','received'])assert.ok(docs.includes(`data-au-source="${id}"`),id);
 assert.doesNotMatch(docs,/data-au-source="(?:original|assigned)"|data-au-document=/);
 for(const phrase of ['notice.jpg','Interpretation unsupported','Only part of the source is readable'])assert.ok(docs.includes(phrase),phrase);
 assert.doesNotMatch(docs,/Original file received|Text available for assessment/);assert.deepEqual(ui.contextualRecord(s,{},[],'claim').state.source_descriptors,s.source_descriptors);assert.deepEqual(ui.contextualRecord(s,{},[],'claim').state.acquired_sources,s.acquired_sources);
 assert.match(ui.obligationMarkup(s,'branch'),/Needed now/);assert.doesNotMatch(ui.obligationMarkup(s,'branch'),/No reviewed source matched|Insufficient|Not yet supported/);
 assert.doesNotMatch(ui.evidencePathMarkup(s,'branch'),/Not yet supported/);assert.equal(ui.contextualRecord(s,{},[],'requirement',s.obligations[0].obligation_id).evaluation[0].review_state,'missing');
 assert.equal(JSON.stringify(s),before);
});

test('source extraction labels do not contradict a sufficient review for one document requirement',()=>{
 const s=state(),source={claim_id:s.claim_id,artifact_id:'supplied-form',file_name:'supplied-form.pdf',media_type:'application/pdf',role:'supporting_document',sha256:hash('f')};
 s.source_descriptors.push(source);s.acquired_sources=[{artifact_id:source.artifact_id,extraction:'pdf_text',complete:true}];
 s.graph.document_catalog=[{document_type:'notice',held_files:[{artifact_id:source.artifact_id,review:'sufficient'}]}];
 s.evaluation.documents[0].review_state='satisfied';
 s.actions=[{result:{action_id:'review:notice:supplied-form',type:'document_review',node_ids:['branch'],document_type:'notice',status:'completed',verdict:'sufficient',summary:'The supplied form establishes this requirement.'},receipt:{receipt_sha256:hash('c')}}];
 const before=JSON.stringify(s),html=ui.workMarkup(s,{},'branch',[],'sources');
 assert.match(html,/data-au-source="supplied-form"/);assert.doesNotMatch(html,/Text available for assessment|sufficiency not established/);assert.deepEqual(ui.contextualRecord(s,{},[],'claim').state.acquired_sources,s.acquired_sources);assert.equal(ui.contextualRecord(s,{},[],'requirement',s.obligations[0].obligation_id).evaluation[0].review_state,'satisfied');
 const requirement=ui.obligationMarkup(s,'branch');assert.match(requirement,/Needed now/);assert.match(requirement,/data-au-review="satisfied"[^>]*>Source review: Satisfied\./);assert.doesNotMatch(requirement,/Needed now\s*·\s*Satisfied/);
 assert.match(ui.workMarkup(s,{},'branch',[],'activity'),/The supplied form establishes this requirement\./);
 assert.equal(JSON.stringify(s),before);
});

test('zero active gaps can leave requirements held by unresolved questions without rewriting the outcome or draft',()=>{
 const s=state({status:'deferred',outcome:{title:'Saved provider outcome',summary:'The received evidence leaves the branch unresolved.',missing_evidence:[],unresolved_facts:[{fact_id:'condition:family_home',summary:'The family-home condition remains unresolved.'}],request_draft:{status:'prepared_not_sent',subject:'Saved request subject',body:'No active document request is recorded.'}}});
 s.evaluation.documents[0]={...s.evaluation.documents[0],route_state:'held_behind_question',review_state:'missing',required_at_node_ids:['branch']};s.evaluation.nodes[1]={...s.evaluation.nodes[1],activation:'unresolved',execution_state:'unresolved'};
 const before=JSON.stringify(s),html=ui.inspectorMarkup(s,'branch');assert.match(html,/May be needed/);assert.doesNotMatch(html,/Not yet supported/);assert.equal(ui.contextualRecord(s,{},[],'step','branch').evaluation.activation,'unresolved');assert.equal(ui.contextualRecord(s,{},[],'requirement',s.obligations[0].obligation_id).evaluation[0].review_state,'missing');assert.doesNotMatch(html,/All evidence satisfied|All documents received|Missing file|No attachment received/);
 assert.deepEqual(ui.contextualRecord(s,{},[],'outcome').outcome,s.outcome);assert.equal(JSON.stringify(s),before);
 s.evaluation.documents[0].route_state='not_needed';assert.match(ui.inspectorMarkup(s,'branch'),/not required on the recorded route/);
});

test('all displayed untrusted title, fact, source, outcome and knowledge text is escaped',()=>{
 const attack='<img src=x onerror="alert(1)">',s=state({title:attack,outcome:{summary:attack}});
 s.graph.nodes[0].label=attack;s.facts[0].summary=attack;s.facts[0].citations=[{artifact_id:'original',quote:attack}];
 const html=ui.workMarkup(s,{},'branch',[{seq:1,kind:attack,payload:{summary:attack}}])+ui.knowledgeMarkup({versions:[{title:attack,qualification:{status:'qualified'}}],quarantined:[{reason:attack}]});
 assert.doesNotMatch(html,/<img|onerror="alert/);assert.match(html,/&lt;img/);
});

test('exact citations use Python Unicode codepoint offsets, source hash and entire text hash',async()=>{
 const body='😀\nOriginal exact passage.\nAfter',s=state(),source={claim_id:s.claim_id,artifact_id:'original',sha256:hash('d'),text:body,text_sha256:sha(body),complete:true};
 const quote='Original exact passage.',citation={artifact_id:'original',sha256:source.sha256,text_sha256:source.text_sha256,start_char:2,end_char:2+quote.length,quote};
 const checked=await ui.checkedSource(s,s.source_descriptors[0],source,citation);assert.equal(checked.span.before,'😀\n');assert.equal(checked.span.quote,quote);
 for(const changed of [{...citation,start_char:3},{...citation,sha256:hash('a')},{...citation,text_sha256:hash('a')},{...citation,artifact_id:'other'}]) await assert.rejects(ui.checkedSource(s,s.source_descriptors[0],source,changed),/source|passage/);
 await assert.rejects(ui.checkedSource(s,s.source_descriptors[0],{...source,text:body+'changed'},citation),/identity/);
 await assert.rejects(ui.checkedSource(s,s.source_descriptors[0],{...source,claim_id:'other'},citation),/another claim/);
});

test('knowledge qualification and quarantine render recorded proofs rather than inferred learning quality',()=>{
 const version={knowledge_id:'k1',version:1,title:'Service process',source_claim_id:'claim-a',knowledge_sha256:hash('a'),qualification:{status:'qualified',regression_cases:243,checks:['no_case_values_or_files']}};
 const quarantine={knowledge_id:'q1',qualification:{status:'quarantined',reason:'Changed rule identity'}},data={versions:[version],uses:[],quarantined:[quarantine]};
 const html=ui.knowledgeMarkup(data);assert.match(html,/data-au-inspect="knowledge-index"[^>]*>History/);assert.doesNotMatch(html,/data-au-inspect="withheld-index"/);assert.deepEqual(ui.contextualRecord(null,{},[],'knowledge-index','',data),data);assert.deepEqual(ui.contextualRecord(null,{},[],'withheld-index','',data),[quarantine]);assert.doesNotMatch(html,/more accurate|improved accuracy|human approved/i);
 assert.deepEqual(ui.contextualRecord(null,{},[],'knowledge','k1:1',data),version);assert.deepEqual(ui.contextualRecord(null,{},[],'quarantine','0',data),quarantine);assert.equal(version.qualification.regression_cases,243);
});

function reconciliation(claim_id,status='completed') {
 const admission={contract:'casepath.saved-result-admission/1.0.0',identity:{claim_id,workflow_id:'saved-workflow'}};
 for(const field of ['workflow_sha256','config_sha256','terminal_sha256','context_sha256','proposal_sha256','verifier_sha256','proposal_receipt_sha256','verifier_receipt_sha256','interpret_request_sha256','interpret_schema_sha256','verify_request_sha256','verify_schema_sha256','admission_sha256'])admission[field]=sha(field);
 return {reconciliation_id:'saved-reconciliation',request:{claim_id,expected_revision:11,expected_state_sha256:sha(`${claim_id}:11`),idempotency_key:'saved-reconciliation-key',actor:'Local operator',reason:'Review the saved failure.'},original_deferral:{code:'verification_deferred',reason:'interpretation citation is not an exact claim source span'},failure_event_sha256:sha('original-failure'),admission,status,started_event_sha256:sha('reconciliation-started'),...(status==='completed'?{completed_event_sha256:sha('reconciliation-completed')}:status==='failed'?{failure_reason:'Saved-result admission remains unresolved.'}:{})};
}
test('reconciliation and item rejection history preserve rejected provenance without presenting proposed quotes as accepted evidence',()=>{
 const attack='<img src=x onerror="alert(1)">',rejection={item_id:'step:lt_type',reason:'citation is not exact: '+attack,item:{node_id:'lt_type',citations:[{artifact_id:'original',quote:'die Familie',claimed_extension:attack},{artifact_id:'outside-claim',quote:'Unbound text'}]}};
 const receipt={receipt_sha256:hash('f'),item_rejections:[rejection,{item_id:'document:notice:original',reason:'No sufficient review accepted.',item:{artifact_id:'original',verdict:'sufficient'}}]};
 for(const status of ['started','failed','completed']) {
  const record=reconciliation('claim-a',status),saved=state({status:'deferred',deferral:status==='completed'?null:record.original_deferral,outcome:status==='completed'?{status:'deferred',summary:'Evidence remains unresolved.'}:null,reconciliations:[record],receipts:[{receipt}],actions:[{result:{action_id:'rejected-item-review',status:'completed',citations:[]},receipt}]});
  const before=JSON.stringify(saved),journal=[{seq:11,kind:'work.deferred',payload:record.original_deferral},{seq:12,kind:`reconciliation.${status}`,payload:{reconciliation_id:record.reconciliation_id}}],html=ui.workMarkup(saved,{},'branch',journal,'activity');
  assert.ok(html.includes(({started:'Saved result review started',completed:'Saved result review finished',failed:'Saved result review failed'})[status]));assert.ok(html.includes(record.original_deferral.reason));
  assert.deepEqual(ui.contextualRecord(saved,{},journal,'reconciliation',record.reconciliation_id),record);
  assert.deepEqual(ui.contextualRecord(saved,{},journal,'claim').state.receipts,[{receipt}]);
  assert.deepEqual(ui.contextualRecord(saved,{},journal,'action','0').receipt.item_rejections,receipt.item_rejections);
  assert.match(html,/data-au-inspect="reconciliation"/);assert.match(html,/data-au-inspect="claim"/);
  assert.doesNotMatch(html,/data-au-source="outside-claim"|data-au-citation=|<q>|<mark|<img|onerror="alert/);
  assert.equal(ui.replayCanAdvance(saved),status==='completed');assert.equal(JSON.stringify(saved),before);
 }
 const saved=state({status:'deferred',deferral:{code:'execution_deferred',reason:'Current execution stopped.'},outcome:{status:'deferred',summary:'Older accepted assessment.'}}),html=ui.workMarkup(saved,{},'branch',[]);
 assert.match(html,/data-au-claim-status>Execution failed\.<\/span> Current execution stopped\./);
 assert.deepEqual(ui.contextualRecord(saved,{},[],'outcome'),{outcome:saved.outcome,deferral:saved.deferral});
});

test('activity keeps one record entry while preserving repeated rejection provenance and distinct runs in exact receipts',()=>{
 const rejection={item_id:'step:lt_type',reason:'Quote is not exact.',item:{node_id:'lt_type',citations:[{artifact_id:'original',quote:'die Familie'}]}};
 const interpretation={workflow_id:'run-a',receipt_sha256:sha('interpretation'),item_rejections:[rejection]},outcome={...interpretation,receipt_sha256:sha('outcome')};
 const distinct={...interpretation,receipt_sha256:sha('distinct'),item_rejections:[{...rejection,reason:'A separate rejection.'}]},later={...interpretation,workflow_id:'run-b',receipt_sha256:sha('later')};
 const saved=state({receipts:[{receipt:interpretation},{receipt:outcome},{receipt:distinct},{receipt:later}],actions:[{result:{action_id:'document-review',status:'completed'},receipt:interpretation}]}),before=JSON.stringify(saved);
 const html=ui.workMarkup(saved,{},'branch',[],'activity');assert.doesNotMatch(html,/<details|<summary>Rejected proposal items/);
 assert.match(html,/data-au-inspect="claim"/);assert.ok(html.includes(`data-au-inspect="action" data-au-record-id="${ui.actionRows(saved)[0].instanceId}"`));
 const claim=ui.contextualRecord(saved,{},[],'claim');assert.deepEqual(claim.state.receipts,[{receipt:interpretation},{receipt:outcome},{receipt:distinct},{receipt:later}]);
 assert.equal(new Set(claim.state.receipts.map(row=>row.receipt.receipt_sha256)).size,4);
 assert.deepEqual(ui.contextualRecord(saved,{},[],'action','0').receipt,interpretation);assert.equal(JSON.stringify(saved),before);
});

// A minimal DOM boundary exercises the production mount/request/submit lifecycle.
// It does not stand in for browser layout or native keyboard acceptance.
function dom() {
 const listeners=new Map(),doc={activeElement:null,hidden:false,addEventListener(){},removeEventListener(){}};
 const status={textContent:'',classList:{toggle(){}}},message={textContent:''};
 const submit={disabled:false,textContent:''},fields={title:{value:'New title'},message:{value:'Original source message'},files:{files:[]}};
 const form={elements:fields,matches:s=>s.includes('data-au-intake'),querySelector:s=>s==='.au-form-status'?message:submit,querySelectorAll:()=>[...Object.values(fields),submit],contains:element=>Object.values(fields).includes(element),remove(){},replaceWith(){}};
 const claimList={innerHTML:''},service={textContent:''},heading={focus(){doc.activeElement=this;}};
 const host={innerHTML:'',contains:()=>false,querySelector(s){return {'[data-au-intake]':form,'[data-au-claims]':claimList,'[data-au-service]':service,'button[type="submit"]':submit,h1:heading}[s]||null;},querySelectorAll:()=>[]};
 const dialog={open:false,addEventListener(){},removeEventListener(){},close(){this.open=false;}};
 const recordCallbacks=new Map(),recordTitle={textContent:''},recordPre={dataset:{},textContent:''};let recordHTML='';
 const recordBody={get innerHTML(){return recordHTML;},set innerHTML(value){recordHTML=value;},querySelector:selector=>selector==='pre'&&recordHTML.includes('<pre')?recordPre:null};
 const recordDialog={open:false,addEventListener(type,fn){recordCallbacks.set(type,fn);},removeEventListener(type){recordCallbacks.delete(type);},showModal(){this.open=true;},close(){this.open=false;recordCallbacks.get('close')?.();},querySelector:selector=>selector==='[data-au-record-content]'?recordBody:selector==='#auRecordTitle'?recordTitle:null};
 const containerAttributes=new Map();
 const container={ownerDocument:doc,classList:{add(){}},setAttribute(name,value){containerAttributes.set(name,value);},removeAttribute(name){containerAttributes.delete(name);},innerHTML:'',querySelector(s){return {'[data-au-view]':host,'.au-global-status':status,dialog,'.au-source-dialog':dialog,'.au-record-dialog':recordDialog}[s];},querySelectorAll:()=>[],addEventListener(type,fn){listeners.set(type,fn);},removeEventListener(type){listeners.delete(type);},contains:()=>true};
 return {container,host,form,fields,message,submit,status,listeners,dialog,recordDialog,recordBody,recordPre};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const response=(data,code=200)=>({ok:code<400,status:code,json:async()=>data});
function fakeApi(overrides={}) {
 const calls=[];
 const fetch=async(path,init)=>{calls.push({path,init});if(overrides.handle){const result=await overrides.handle(path,init,calls);if(result)return result;}
  if(path.includes('/snapshot?'))return response({detail:'Snapshot capability unavailable'},404);
  if(path.endsWith('/preview'))return response({detail:'Preview capability unavailable'},404);
  if(path.endsWith('/knowledge'))return response({versions:[],uses:[],quarantined:[]});
  if(path.endsWith('/status'))return response({enabled:true,provider_ready:true,limits:{}});
  if(path.endsWith('/claims')&&init.method!=='POST')return response({claims:[]});
  if(path.includes('/events?'))return response(events(state()));
  return response(state());};
 return {fetch,calls};
}

test('public read-only capability blocks forged forms and removes work controls while preserving inspection',async t=>{
 const f=dom(),api=fakeApi({handle:async(path)=>path.endsWith('/status')?response({enabled:true,provider_ready:true,read_only:true,writable:false,limits:{}}):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await newClaim(f);
 await f.listeners.get('submit')({target:f.form,preventDefault(){}});
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
 assert.doesNotMatch(f.host.innerHTML,/data-au-intake|data-au-arrival/);
 const presentation={mode:'saved',readOnly:true,availability:{ready:true}};
 for(const saved of [state(),state({status:'deferred',deferral:{code:'paused'}}),state({revision:0})]) {
  const before=JSON.stringify(saved),html=ui.workMarkup(saved,{},'branch',[],'sources',{},presentation)+ui.workMarkup(saved,{},'branch',[],'documents',{},presentation);
  assert.doesNotMatch(html,/data-au-start(?:[ >])|data-au-pause(?:[ >])|data-au-resume(?:[ >])|data-au-arrival(?:[ >])|data-au-add-files(?:[ >])/);
  assert.match(html,/Sources|History/);assert.equal(JSON.stringify(saved),before);
 }
 assert.equal(ui.liveAvailability({enabled:true,provider_ready:true,read_only:true,writable:false}).ready,false);
 assert.match(ui.liveAvailability({enabled:true,provider_ready:true,read_only:true,writable:false}).reason,/read-only/i);
 assert.doesNotMatch(ui.demonstrationMarkup([],{enabled:true,provider_ready:true,read_only:true,writable:false}),/data-au-demo-mode="live"/);
});

test('public entry capability prevents work before a status response arrives',async t=>{
 const before=globalThis.CASEPATH_PUBLIC_READ_ONLY;globalThis.CASEPATH_PUBLIC_READ_ONLY=true;
 const f=dom(),held=[],api=fakeApi({handle:async path=>path.endsWith('/status')?new Promise(resolve=>held.push(resolve)):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{for(const resolve of held)resolve(response({enabled:true,provider_ready:true,writable:true}));controller.destroy();if(before===undefined)delete globalThis.CASEPATH_PUBLIC_READ_ONLY;else globalThis.CASEPATH_PUBLIC_READ_ONLY=before;});
 assert.doesNotMatch(f.container.innerHTML,/data-au-nav="intake"/);assert.match(f.container.innerHTML,/data-au-public-access>Read-only/);await settle();await newClaim(f);
 assert.doesNotMatch(f.host.innerHTML,/data-au-intake|data-au-arrival/);
 await f.listeners.get('submit')({target:f.form,preventDefault(){}});
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('a read-only status arriving during file preparation is denied centrally without an uncertain write retry',async t=>{
 const f=nativeFixture(),publicStatus={enabled:true,provider_ready:false,read_only:true,writable:false,limits:{}},bytes=Buffer.from('Original fixture bytes');let reads=0,finishStatus,finishBytes;
 const api=fakeApi({handle:async(path)=>path.endsWith('/status')?++reads===2?new Promise(resolve=>{finishStatus=resolve;}):response({enabled:true,provider_ready:true,limits:{}}):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{finishStatus?.(response(publicStatus));finishBytes?.(bytes);controller.destroy();});await settle();await newClaim(f);
 const form=f.intake;form.elements.title.value='Original fixture';form.elements.message.value='Supplied message';form.elements.files.files=[{...fileFixture(),arrayBuffer:()=>new Promise(resolve=>{finishBytes=resolve;})}];
 const submission=f.listeners.get('submit')({target:form,preventDefault(){}});await waitFor(()=>Boolean(finishBytes));
 finishStatus(response(publicStatus));await settle();finishBytes(bytes);await submission;
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
 assert.match(form.querySelector('.au-form-status').textContent,/public workspace is read-only/i);
 assert.doesNotMatch(form.querySelector('.au-form-status').textContent,/unconfirmed|Retry/i);
 assert.equal(form.querySelector('button[type="submit"]').disabled,true);
});

test('uncertain intake retries the identical payload/key with required mutation header and never auto-retries',async t=>{
 const f=dom();let posts=0;const api=fakeApi({handle:async(path,init)=>{if(init.method==='POST'){posts++;if(posts===1)throw new Error('Connection lost');return response(state());}}});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await newClaim(f);
 await f.listeners.get('submit')({target:f.form,preventDefault(){}});
 assert.equal(posts,1);assert.match(f.message.textContent,/same request key/);assert.equal(f.fields.title.disabled,true);assert.equal(f.submit.disabled,false);
 f.fields.title.value='Must not silently create a second intake';
 await f.listeners.get('submit')({target:f.form,preventDefault(){}});
 const writes=api.calls.filter(call=>call.init.method==='POST');assert.equal(writes.length,2);assert.equal(writes[0].init.body,writes[1].init.body);assert.equal(writes[0].init.headers['X-CasePath-Agent-Work'],'1');assert.equal(writes[0].init.headers['Content-Type'],'application/json');
 assert.equal(JSON.parse(writes[0].init.body).title,'New title');
});

test('destroy aborts outstanding reads and stale responses cannot resurrect the view',async()=>{
 const f=dom(),pending=[];const controller=ui.mount(f.container,{fetch:async(path,init)=>new Promise(resolve=>pending.push({path,init,resolve}))});
 assert.equal(pending.length,2);controller.destroy();assert.ok(pending.every(call=>call.init.signal.aborted));assert.equal(f.container.innerHTML,'');
 pending.forEach(call=>call.resolve(response(call.path.endsWith('/status')?{enabled:true}:{claims:[]})));await settle();assert.equal(f.container.innerHTML,'');assert.equal(f.listeners.size,0);
});

test('a late claim response cannot replace a more recently selected claim',async t=>{
 const f=dom();let finish;const b=state({claim_id:'claim-b',graph:null});
 const api=fakeApi({handle:async(path)=>{if(path.endsWith('/claims/claim-a'))return new Promise(resolve=>finish=resolve);if(path.endsWith('/claims/claim-b'))return response(b);if(path.includes('/claim-b/events'))return response(events(b));}});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 const first=controller.openClaim('claim-a');await controller.openClaim('claim-b');const saved=f.host.innerHTML;finish(response(state()));await first;
 assert.equal(f.host.innerHTML,saved);assert.match(saved,/Original incoming claim/);
});

test('a known catalog claim paints its original preview immediately while its authoritative snapshot is held',async t=>{
 const f=dom(),catalog={claim_id:'claim-a',origin:'canonical_original',title:'Known original catalog claim',source_preview:{text:'The exact original intake excerpt.'},revision:27,status:'resolved',state_sha256:hash('0')},before=JSON.stringify(catalog);let release;
 const saved=state({title:catalog.title,origin:'canonical_original',message:catalog.source_preview.text}),api=fakeApi({handle:async(path,init)=>{
  if(path.endsWith('/claims')&&init.method!=='POST')return response({claims:[catalog]});
  if(path.includes('/claims/claim-a/snapshot?'))return new Promise(resolve=>{release=resolve;});
 }}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();release?.(response({detail:'Disposed isolated read'},410));});await settle();
 const opening=controller.openClaim('claim-a');assert.equal(typeof release,'function');
 assert.match(f.host.innerHTML,/Known original catalog claim/);assert.match(f.host.innerHTML,/The exact original intake excerpt\./);assert.match(f.host.innerHTML,/claim-a/);
 assert.doesNotMatch(f.host.innerHTML,/data-au-revision=|data-au-state-sha=|data-au-node=|data-au-start|data-au-pause|data-au-resume|data-au-arrival|Investigation complete|Opening|Verifying/,'catalog content is read-only and cannot supply accepted lifecycle state');
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);assert.equal(JSON.stringify(catalog),before);
 release(response({state:saved,projection:{claim_id:saved.claim_id,revision:saved.revision,state_sha256:saved.state_sha256},...events(saved),current_state_sha256:saved.state_sha256,cursor_sha256:hash('9')}));await opening;
 assert.match(f.host.innerHTML,/data-au-revision="3" data-au-state-sha="a{64}"/);assert.doesNotMatch(f.host.innerHTML,/data-au-revision="27"/);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);assert.equal(JSON.stringify(catalog),before);
});

test('local file validation sends nothing and leaves the intake editable',async t=>{
 const f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await newClaim(f);
 f.fields.files.files=Array.from({length:21},()=>({name:'one.txt'}));
 await f.listeners.get('submit')({target:f.form,preventDefault(){}});
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);assert.equal(f.fields.title.disabled,false);assert.match(f.message.textContent,/at most 20/);assert.doesNotMatch(f.message.textContent,/unconfirmed/);
});

test('pause is an explicit guarded action and an uncertain response retains its exact key',async t=>{
 const f=dom(),api=fakeApi({handle:async(path,init)=>{if(path.endsWith('/pause'))throw new Error('Pause response lost');}}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 const target={dataset:{},disabled:false,isConnected:true,textContent:'Pause work',closest(){return this;},hasAttribute:attr=>attr==='data-au-pause'};
 f.host.querySelectorAll=selector=>selector==='[data-au-start],[data-au-pause],[data-au-resume]'?[target]:[];
 f.listeners.get('click')({target});await settle();f.listeners.get('click')({target});await settle();
 const pauses=api.calls.filter(call=>call.path.endsWith('/pause'));assert.equal(pauses.length,2);assert.equal(pauses[0].init.body,pauses[1].init.body);assert.deepEqual({...JSON.parse(pauses[0].init.body),idempotency_key:undefined},{expected_revision:3,expected_state_sha256:hash('a'),idempotency_key:undefined});assert.equal(target.textContent,'Retry pause');
 assert.match(ui.workMarkup(state(),{},'branch',[]),/data-au-pause/);assert.doesNotMatch(ui.workMarkup(state({status:'deferred'}),{},'branch',[]),/data-au-pause/);
});

test('module destroy without a container supports the pagehide integration contract',async()=>{
 const f=dom(),api=fakeApi();ui.mount(f.container,{fetch:api.fetch});await settle();ui.destroy();assert.equal(f.container.innerHTML,'');assert.equal(f.listeners.size,0);
});

test('ready execution limits come only from the backend capability projection without changing sealed state',()=>{
 const s=state(),before=JSON.stringify(s),projection={node_capabilities:{branch:{id:null,authorized:false,reason:'This step requires an unconfigured filing capability.'}}};
 assert.match(ui.graphMarkup(s,'branch',projection),/data-au-node="branch"[^>]*data-status="ready"/);assert.deepEqual(ui.contextualRecord(s,projection,[],'step','branch').capability,projection.node_capabilities.branch);
 assert.match(ui.inspectorMarkup(s,'branch',projection),/This step requires an unconfigured filing capability\./);
 assert.equal(JSON.stringify(s),before);
 const allowed={node_capabilities:{branch:{id:'local_assessment.record',authorized:true,reason:'Record the verified internal assessment.'}}};
 assert.deepEqual(ui.contextualRecord(s,allowed,[],'step','branch').capability,allowed.node_capabilities.branch);assert.doesNotMatch(ui.inspectorMarkup(s,'branch',allowed),/unconfigured filing capability/);
 assert.doesNotMatch(ui.graphMarkup(s,'branch',allowed),/execution unavailable/);
 // No hardcoded policy: an arbitrary future step gets exactly its projected authority.
 s.graph.nodes[1].node_id='future';s.evaluation.nodes[1].node_id='future';s.graph.edges[0].target_node_id='future';
 assert.match(ui.inspectorMarkup(s,'future',{node_capabilities:{future:projection.node_capabilities.branch}}),/unconfigured filing capability/);assert.deepEqual(ui.contextualRecord(s,{node_capabilities:{future:projection.node_capabilities.branch}},[],'step','future').capability,projection.node_capabilities.branch);
});

test('reuse exposes recorded applicability and avoided mechanical work without estimating savings',()=>{
 const use={knowledge_id:'procedure.one',version:2,applicability:'same_verified_family_and_rule_version',avoided_rule_compilations:1,avoided_qualification_cases:243},s=state({knowledge_uses:[use]});
 const record=ui.contextualRecord(s,{},[],'use','0');assert.deepEqual(record,use);assert.equal(record.avoided_rule_compilations,1);assert.equal(record.avoided_qualification_cases,243);
 const html=ui.workMarkup(s,{},'branch',[],'knowledge');assert.match(html,/Used for this case · Version 2/);assert.match(html,/Used for this current case/);assert.match(html,/own source evidence/);assert.doesNotMatch(html,/saved.*seconds|more accurate|improved accuracy/);
});

test('knowledge inspection connects reusable steps, required facts, obligations and recipe rules to immutable lineage',()=>{
 const first={knowledge_id:'procedure.one',version:1,title:'Service process',knowledge_sha256:hash('a'),graph:state().graph,facts:state().facts,obligations:state().obligations,qualification:{status:'qualified'}};
 const next={...first,version:2,knowledge_sha256:hash('b'),parent_knowledge_sha256:hash('a'),parent_definition_sha256:hash('d'),change_reason:'Added a qualified service-evidence recipe.',evidence_recipes:[{document_type:'notice',required_fields:['Addressee','Delivery date'],summary:'Original notice must establish service.',rule_refs:['tenancy.v1']}]},data={versions:[first,next],uses:[],quarantined:[]};
 assert.deepEqual(ui.contextualRecord(null,{},[],'knowledge','procedure.one:1',data),first);assert.deepEqual(ui.contextualRecord(null,{},[],'knowledge','procedure.one:2',data),next);
 assert.deepEqual(next.evidence_recipes[0].rule_refs,['tenancy.v1']);assert.equal(next.parent_knowledge_sha256,first.knowledge_sha256);assert.match(ui.knowledgeMarkup(data),/data-au-inspect="knowledge-index"[^>]*>History/);assert.doesNotMatch(ui.knowledgeMarkup(data),/data-au-inspect="knowledge"/);
});

test('MIME fallbacks affect only blank types and never rewrite submitted bytes',async t=>{
 for(const [file,expected]of [[{name:'source.EML',type:''},'message/rfc822'],[{name:'a.txt',type:''},'text/plain'],[{name:'a.md',type:''},'text/markdown'],[{name:'a.csv',type:''},'text/csv'],[{name:'a.json',type:''},'application/json'],[{name:'a.txt',type:'application/custom'},'application/custom'],[{name:'a.unknown',type:''},'application/octet-stream']])assert.equal(ui.mediaType(file),expected);
 const f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await newClaim(f);
 const bytes=Buffer.from('Subject: Exact\r\n\r\nOriginal =3D MIME bytes.\r\n','utf8');
 f.fields.files.files=[{name:'source.eml',type:'',size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}];
 await f.listeners.get('submit')({target:f.form,preventDefault(){}});
 const file=JSON.parse(api.calls.find(call=>call.init.method==='POST').init.body).files[0];assert.equal(file.media_type,'message/rfc822');assert.equal(file.content_base64,bytes.toString('base64'));
});

test('readable MIME previews use the body of the same bound original while preserving wire bytes and PDF extraction',()=>{
 const body='Exact original customer message. The notice date is unknown.',encoded=Buffer.from(body).toString('base64'),wire=`From: sender@example.invalid\r\nMIME-Version: 1.0\r\nContent-Transfer-Encoding: base64\r\n\r\n${encoded}`,digest=sha(wire),saved=state({message:body});
 saved.source_descriptors=[{claim_id:saved.claim_id,artifact_id:'original',file_name:'original-message.eml',role:'customer_message',sha256:digest,media_type:'message/rfc822'}];
 const source={claim_id:saved.claim_id,artifact_id:'original',file_name:'original-message.eml',media_type:'message/rfc822',sha256:digest,text:wire,text_sha256:sha(wire),receipt_sha256:hash('1'),complete:true,extraction:'email_mime'};saved.acquired_sources=[source];
 saved.original_binding={claim_id:saved.claim_id,intake:{customer_message:{body,raw_file:{artifact_id:'raw-original',sha256:digest}}},source_map:[{artifact_id:'original',original_artifact_id:'raw-original',sha256:digest}]};
 const before=JSON.stringify(saved);assert.equal(ui.readableSourceText(saved,source),body);assert.equal(ui.readableSourceText(saved,{...source,media_type:'Message/RFC822; charset=UTF-8'}),body);
 const plainWire={...source,file_name:'original-message.txt',media_type:'text/plain; charset=utf-8',extraction:'utf8'};
 const plainSaved={...saved,source_descriptors:[{...saved.source_descriptors[0],file_name:plainWire.file_name,media_type:plainWire.media_type}],acquired_sources:[plainWire]};
 assert.equal(ui.readableSourceText(plainSaved,plainWire),body,'the canonical text/plain original message retains its bound readable body');
 assert.doesNotMatch(ui.acquiredContentMarkup(plainSaved),/MIME-Version|Content-Transfer-Encoding/);
 assert.equal(ui.readableSourceText({...plainSaved,original_binding:undefined},plainWire),null,'encoded text/plain content cannot escape binding checks');
 const html=ui.acquiredContentMarkup(saved);assert.ok(html.includes(body));assert.doesNotMatch(html,/MIME-Version|Content-Transfer-Encoding|From: sender/);assert.ok(!html.includes(encoded));assert.ok(html.includes(`data-au-source-identity="${saved.claim_id}:original:${digest}:${source.text_sha256}"`));
 const invalidStates=[
  {...saved,original_binding:{...saved.original_binding,claim_id:'another-claim'}},
  {...saved,source_descriptors:[{...saved.source_descriptors[0],role:'supporting_document'}]},
  {...saved,source_descriptors:[{...saved.source_descriptors[0],sha256:hash('0')}]},
  {...saved,original_binding:{...saved.original_binding,source_map:[]}},
  ...['artifact_id','original_artifact_id','sha256'].map(field=>({...saved,original_binding:{...saved.original_binding,source_map:[{...saved.original_binding.source_map[0],[field]:'wrong-original'}]}})),
  {...saved,message:'A different customer message'},
  {...saved,original_binding:{...saved.original_binding,intake:{customer_message:{...saved.original_binding.intake.customer_message,body:'Different parsed body'}}}},
  {...saved,original_binding:{...saved.original_binding,intake:{customer_message:{body,raw_file:{artifact_id:'raw-original',sha256:hash('0')}}}}}
 ];
 for(const invalid of invalidStates)assert.equal(ui.readableSourceText(invalid,source),null,'an unbound MIME source cannot borrow the catalog or another message body');
 for(const invalid of [{...source,artifact_id:'other-artifact'},{...source,sha256:hash('0')},{...source,extraction:'unsupported_metadata'}])assert.equal(ui.readableSourceText(saved,invalid),null);
 const pdf={artifact_id:'pdf-original',media_type:'application/pdf',extraction:'pdf_text',text:'Exact extracted PDF text.',text_sha256:sha('Exact extracted PDF text.'),complete:false};assert.equal(ui.readableSourceText(saved,pdf),pdf.text);assert.equal(ui.readableSourceText(saved,{...pdf,extraction:'unsupported_metadata'}),null);
 assert.equal(JSON.stringify(saved),before);assert.equal(source.text,wire);assert.equal(source.sha256,digest);assert.equal(source.receipt_sha256,hash('1'));
});

test('published procedure changes and an exact reused version remain distinct with stable ordinary names',()=>{
 for(const [family,label]of [['lease_termination_dispute','Lease termination'],['defect_mold_heating','Defects and repairs'],['rent_increase_dispute','Rent increases']])assert.equal(ui.procedureLabel({family,knowledge_id:`procedure.${family}`,title:`Generic ${family} workflow`}),label);
 const published={knowledge_id:'procedure.lease_termination_dispute',family:'lease_termination_dispute',title:'Generic workflow',version:3,knowledge_sha256:hash('1'),qualification:{status:'qualified',definition_sha256:hash('2')},added_document_types:['proof_of_receipt'],evidence_recipes:[{document_type:'proof_of_receipt',required_fields:['recipient','delivery_evidence','delivery_date']}],obligations:[{document_type:'proof_of_receipt',label:'Proof of receipt'}]},use={knowledge_id:published.knowledge_id,version:2,knowledge_sha256:hash('3'),definition_sha256:hash('4'),applicability:'same_verified_family_and_rule_version'},saved=state({knowledge_published:[published],knowledge_uses:[use]}),before=JSON.stringify(saved),html=ui.claimKnowledgeMarkup(saved);
 assert.match(html,/<h3>Lease termination<\/h3>/);assert.match(html,/>Added for reuse · Version 3<\/p>/);assert.match(html,/Added proof of receipt requirements: recipient, delivery evidence, delivery date\./);
 const publicationLink=html.match(/<button[^>]*data-au-knowledge="procedure\.lease_termination_dispute"[^>]*data-au-version="3"[^>]*>Open procedure<\/button>/)?.[0],reuseLink=html.match(/<button[^>]*data-au-knowledge="procedure\.lease_termination_dispute"[^>]*data-au-version="2"[^>]*>Open procedure<\/button>/)?.[0];assert.ok(publicationLink);assert.ok(reuseLink);assert.match(html,/Used for this case · Lease termination · Version 2/);
 assert.ok(publicationLink.includes(`data-au-knowledge-sha="${hash('1')}"`));assert.ok(publicationLink.includes(`data-au-definition-sha="${hash('2')}"`));assert.ok(reuseLink.includes(`data-au-knowledge-sha="${hash('3')}"`));assert.ok(reuseLink.includes(`data-au-definition-sha="${hash('4')}"`));
 assert.deepEqual(ui.contextualRecord(saved,{},[],'publication','0'),published);assert.deepEqual(ui.contextualRecord(saved,{},[],'use','0'),use);assert.doesNotMatch(html,/facts? (?:proved|established) by (?:reuse|knowledge)|improved accuracy/i);
 assert.doesNotMatch(ui.claimKnowledgeMarkup(state({knowledge_published:[{...published,added_document_types:[]}]})),/Added [^<]* requirements/,'unchanged support cannot fabricate added document requirements');
 const reused={...use,reason:'INTERNAL_WORKFLOW_MATCH_REASON'},reuseState=state({knowledge_uses:[reused]}),reuseHTML=ui.claimKnowledgeMarkup(reuseState);assert.match(reuseHTML,/Used for this lease-termination case\./);assert.doesNotMatch(reuseHTML,/INTERNAL_WORKFLOW_MATCH_REASON/);assert.deepEqual(ui.contextualRecord(reuseState,{},[],'use','0'),reused,'ordinary enum copy must preserve the exact recorded internal reason');
 const withheld={...published,qualification:{status:'quarantined',reason:'The source support remains unresolved.'}};assert.doesNotMatch(ui.claimKnowledgeMarkup(state({knowledge_published:[withheld]})),/>Open procedure<|Qualified for reuse/);assert.equal(JSON.stringify(saved),before);
});

test('the claim envelope renders capability projection separately from the preserved state',async t=>{
 const f=dom(),saved=state(),original=JSON.stringify(saved),projection={node_capabilities:{branch:{id:null,authorized:false,reason:'Execution requires an unavailable external action.'}}};
 const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response({state:saved,projection}):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 assert.match(f.host.innerHTML,/data-au-node="branch"[^>]*data-status="ready"/);assert.deepEqual(ui.contextualRecord(saved,projection,[],'step','branch').capability,projection.node_capabilities.branch);assert.match(f.host.innerHTML,/data-au-forming="true"/);assert.doesNotMatch(f.host.innerHTML,/Execution requires an unavailable external action\./);assert.match(ui.inspectorMarkup(saved,'branch',projection),/Execution requires an unavailable external action\./,'the exact capability limit remains accessible in the settled inspector');assert.doesNotMatch(f.host.innerHTML,/data-au-inspect="claim"/);f.listeners.get('click')({target:control(f,'data-au-detail','activity')});assert.match(f.host.innerHTML,/data-au-inspect="claim"[^>]*>Case details/);f.listeners.get('click')({target:control(f,'data-au-inspect','claim')});assert.deepEqual(JSON.parse(f.recordPre.textContent),{state:saved,projection});assert.match(f.host.innerHTML,new RegExp(`data-au-revision="${saved.revision}" data-au-state-sha="${saved.state_sha256}"`));assert.equal(JSON.stringify(saved),original);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('a claim renders one selected real process and keeps exact outcome authority in one contextual record',()=>{
 const s=state({status:'deferred',outcome:{title:'Deferred',summary:'A termination dispute.',authority_limits:['Filing capability is not configured.'],missing_evidence:[{label:'Notice'},{label:'Receipt'}]}}),before=JSON.stringify(s),html=ui.workMarkup(s,{},'branch',[]);
 assert.match(html,/data-au-canvas/);assert.match(html,/data-au-selected-step="branch"/);assert.match(html,/data-au-detail="activity"[^>]*>History/);assert.doesNotMatch(html,/data-au-inspect="claim"|<details/);assert.match(ui.workMarkup(s,{},'branch',[],'activity'),/data-au-inspect="claim"[^>]*>Case details/);
 assert.equal([...html.matchAll(/data-au-panel="/g)].length,1);assert.deepEqual(ui.contextualRecord(s,{},[],'outcome').outcome,s.outcome);assert.equal(JSON.stringify(s),before);
});

test('complete graph labels and operational rule text remain inspectable',()=>{
 const s=state();s.graph.nodes[1].label='Preserve challenge or extension deadline';s.graph.nodes[1].meaning='The process includes a step owned by claim_handler.';s.graph.nodes[1].authority={title:'Admitted tenancy workflow',quote:'Exact recorded operational rule.'};
 assert.match(ui.graphMarkup(s,'branch'),/Preserve challenge or extension deadline/);
 const record=ui.contextualRecord(s,{},[],'step','branch');assert.deepEqual(record.node,s.graph.nodes[1]);assert.equal(record.node.authority.quote,'Exact recorded operational rule.');assert.doesNotMatch(ui.inspectorMarkup(s,'branch'),/data-au-inspect="step"/);assert.deepEqual(ui.contextualRecord(s,{},[],'claim').state.graph.nodes[1],record.node);
});

test('only an explicitly paused deferral offers guarded resume with one retained request identity',async t=>{
 const paused=state({status:'deferred',deferral:{code:'paused',reason:'Work paused.'}}),f=dom();
 const api=fakeApi({handle:async(path,init)=>{if(path.endsWith('/resume'))throw new Error('Resume response lost');if(path.endsWith('/claims/claim-a'))return response(paused);}});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 assert.match(f.host.innerHTML,/data-au-resume/);assert.doesNotMatch(ui.workMarkup(state({status:'deferred',deferral:{code:'missing_evidence'}}),{},'branch',[]),/data-au-resume/);
 const target={dataset:{},disabled:false,isConnected:true,textContent:'Resume work',closest(){return this;},hasAttribute:attr=>attr==='data-au-resume'};
 f.host.querySelectorAll=selector=>selector==='[data-au-start],[data-au-pause],[data-au-resume]'?[target]:[];
 f.listeners.get('click')({target});await settle();f.listeners.get('click')({target});await settle();
 const writes=api.calls.filter(call=>call.path.endsWith('/resume'));assert.equal(writes.length,2);assert.equal(writes[0].init.body,writes[1].init.body);assert.equal(JSON.parse(writes[0].init.body).expected_revision,3);assert.equal(writes[0].init.headers['X-CasePath-Agent-Work'],'1');assert.equal(target.textContent,'Retry resume');
});

test('work progress uses persisted phases, admitted interpretation and actual action/knowledge counts',()=>{
 const s=state({phase:'verifying',phase_summary:'Independently checking the cited facts.',acquired_sources:[{artifact_id:'original'}],receipts:[],knowledge_published:[]});
 const history=[{seq:1,kind:'work.started',payload:{run_id:'run.one'}},{seq:2,kind:'work.phase',payload:{phase:'interpreting'}},{seq:3,kind:'work.phase',payload:{phase:'verifying'}}];s.run_id='run.one';
 const model=ui.progressModel(s,history);
 assert.equal(model.stages.find(stage=>stage.id==='sources').state,'complete');assert.equal(model.stages.find(stage=>stage.id==='interpretation').state,'complete');assert.equal(model.stages.find(stage=>stage.id==='verification').state,'active');assert.equal(model.stages.find(stage=>stage.id==='process').state,'pending');assert.equal(model.explanation,s.phase_summary);
 s.status='deferred';s.phase='deferred';s.outcome={summary:'Evidence is missing.'};s.knowledge_published=[{qualification:{status:'qualified'}},{qualification:{status:'quarantined'}}];s.knowledge_uses=[{knowledge_id:'k',version:1}];
 history.push({seq:4,kind:'interpretation.accepted',payload:{receipt:{checks:[{accepted:true},{accepted:false}]}}},{seq:5,kind:'action.completed',payload:{}},{seq:6,kind:'outcome.recorded',payload:{}},{seq:7,kind:'knowledge.published',payload:{}});
 const finished=ui.progressModel(s,history);assert.ok(finished.stages.every(stage=>stage.state!=='active'));assert.match(finished.stages.find(stage=>stage.id==='verification').detail,/2 checks/);assert.match(finished.stages.find(stage=>stage.id==='process').detail,/1 action/);assert.match(finished.stages.find(stage=>stage.id==='knowledge').detail,/1 published/);assert.match(finished.stages.find(stage=>stage.id==='knowledge').detail,/1 reused/);
 const html=ui.progressMarkup(s,history);assert.match(html,/1 quarantined/);assert.doesNotMatch(html,/progressbar|setTimeout|spinner|animation/);
});

test('a new evidence workflow does not inherit the earlier pass completed interpretation',()=>{
 const s=state({run_id:'run.new',phase:'acquiring',knowledge_published:[]});
 const history=[{seq:1,kind:'work.started',payload:{run_id:'run.old'}},{seq:2,kind:'interpretation.accepted',payload:{}},{seq:3,kind:'outcome.recorded',payload:{}},{seq:4,kind:'work.started',payload:{run_id:'run.new'}},{seq:5,kind:'work.phase',payload:{phase:'acquiring'}}];
 const progress=ui.progressModel(s,history);assert.equal(progress.stages.find(stage=>stage.id==='sources').state,'active');assert.equal(progress.stages.find(stage=>stage.id==='interpretation').state,'pending');assert.equal(progress.stages.find(stage=>stage.id==='verification').state,'pending');
});

test('causal choreography requires a fresh matching accepted event and targets only actual changed dependencies',()=>{
 const before=state();before.evaluation.edges=[{edge_id:'next',activation:'unresolved'}];const after=structuredClone(before);after.revision=4;after.state_sha256=hash('f');after.evaluation.nodes[1].execution_state='completed';after.evaluation.documents[0].review_state='sufficient';after.facts[1].status='established';
 const accepted=ui.acceptEvents(3,events(after,3),after),plan=ui.transitionPlan(before,after,accepted,[]);
 assert.deepEqual(plan.nodes.map(row=>row.id),['branch']);assert.deepEqual(plan.edges,[]);assert.deepEqual(plan.documents.map(row=>row.id),['notice']);assert.deepEqual(plan.facts.map(row=>row.id),['fact:notice']);
 after.evaluation.edges[0].activation='true';const changedEdgePlan=ui.transitionPlan(before,after,accepted,[]);assert.deepEqual(changedEdgePlan.edges.map(row=>row.id),['next']);
 assert.ok(Math.max(...changedEdgePlan.edges.map(row=>row.delay))<=Math.min(...changedEdgePlan.nodes.map(row=>row.delay)),'the actual dependency route belongs to its changed process group');
 assert.ok(Math.max(...plan.facts.map(row=>row.delay+row.duration))<=Math.min(...plan.nodes.map(row=>row.delay)),'the accepted fact settles before the process group starts');
 assert.ok(Math.max(...plan.nodes.map(row=>row.delay+row.duration))<=Math.min(...plan.documents.map(row=>row.delay)),'the selected process settles before its derived requirement starts');
 for(const row of [...plan.nodes,...plan.documents,...plan.facts,...changedEdgePlan.edges])assert.ok(row.duration>=180&&row.duration<=320&&row.delay+row.duration<=800,'accepted change motion stays within the bounded causal wave');
 assert.ok(plan.duration<=800);
 assert.equal(ui.transitionPlan(before,after,ui.acceptEvents(null,events(after),after),[]),null);
 assert.equal(ui.transitionPlan(before,after,ui.acceptEvents(3,events(after,3),after,true),[]),null);
 assert.equal(ui.transitionPlan(after,after,ui.acceptEvents(4,{current_revision:4,events:[]},after),[]),null);
});

function motionFixture(){
 const calls=[],clones=[],cancelled=[];
 const element=(kind,id)=>({dataset:{[kind]:id},isConnected:true,contains:()=>false,animate(frames,options){calls.push({kind,id,frames,options});return{finished:new Promise(()=>{}),cancel(){cancelled.push(id);}};},getTotalLength:()=>120,cloneNode(){const clone=element('clone',id);clone.setAttribute=()=>{};clone.remove=()=>{clone.removed=true;};clones.push(clone);return clone;},parentNode:{appendChild(){}}});
 const all=[element('auNode','branch'),element('auEdge','next'),element('auDocument','notice'),element('auFact','fact:notice'),element('auStage','process'),element('auSemanticEvent',hash('9'))];
 const host={querySelectorAll:selector=>all.filter(el=>({'[data-au-node]':'auNode','[data-au-edge]':'auEdge','[data-au-document]':'auDocument','[data-au-fact]':'auFact','[data-au-stage]':'auStage','[data-au-semantic-event]':'auSemanticEvent','[data-au-knowledge-use]':'auKnowledgeUse','[data-au-knowledge-publication]':'auKnowledgePublication'})[selector] in el.dataset)};
 return{host,calls,clones,cancelled,all,element};
}
function formingMotionFixture(state) {
 const f=motionFixture();f.all.length=0;
 const forming={dataset:{auForming:'true'}},viewport=f.element('formingGraph','visible-graph-frame'),innerGraph=f.element('formingInnerGraph','oversized-graph-content'),documents=f.element('formingDocuments','requirements'),source=f.element('auSource','original'),fact=f.element('auFact','document:unit_document_4'),publication=f.element('auKnowledgePublication',hash('8'));
 const nodes=state.graph.nodes.map(node=>f.element('auNode',node.node_id)),rows=state.obligations.map(obligation=>f.element('auDocument',obligation.document_type));f.all.push(...nodes,...rows,source,fact,publication);
 viewport.getBoundingClientRect=()=>({left:0,top:0,right:450,bottom:260,width:450,height:260});viewport.closest=selector=>selector==='.au-graph-viewport'?viewport:null;innerGraph.getBoundingClientRect=()=>({left:0,top:0,right:450,bottom:660,width:450,height:660});innerGraph.closest=selector=>selector==='.au-graph-viewport'?viewport:null;
 const read={dataset:{auEvidencePath:''}};for(const element of f.all)element.closest=selector=>selector==='[data-au-evidence-path]'?read:selector==='[data-au-forming]'?forming:selector==='.au-forming-documents'&&rows.includes(element)?documents:null;
 const query=selector=>selector==='[data-au-forming="true"]'||selector==='[data-au-forming]'?forming:selector==='[data-au-graph-pan]'||selector==='.au-graph-viewport'?viewport:selector==='[data-au-graph]'?innerGraph:selector==='.au-forming-documents .au-obligations'?documents:null;f.host.querySelector=query;forming.querySelector=query;
 const fields={'[data-au-node]':'auNode','[data-au-document]':'auDocument','[data-au-source]':'auSource','[data-au-fact]':'auFact','[data-au-knowledge-publication]':'auKnowledgePublication'};f.host.querySelectorAll=selector=>f.all.filter(element=>fields[selector] in element.dataset);
 return {...f,forming,viewport,innerGraph,documents,nodes,rows,source,fact,publication};
}

test('forming attention transfers from one accepted whole graph frame to its document list without competing node entrances',()=>{
 const {packet,interpreted}=formingUnitStates(),event={claim_id:interpreted.claim_id,seq:11,revision:11,state_sha256:interpreted.state_sha256,event_sha256:interpreted.last_event_sha256,kind:'interpretation.accepted'},plan=ui.transitionPlan(packet,interpreted,ui.acceptEvents(10,{current_revision:11,events:[event]},interpreted),[event]),before=JSON.stringify(interpreted),f=formingMotionFixture(interpreted),run=ui.animateTransition(f.host,plan,{selected:'question-4'});
 assert.equal(f.calls.filter(call=>call.kind==='formingGraph').length,1);assert.equal(f.calls.filter(call=>call.kind==='formingDocuments').length,1);assert.equal(f.calls.filter(call=>call.kind==='formingInnerGraph'||call.kind==='auNode'||call.kind==='auDocument').length,0,'the atomic eleven-object state has one visible graph-frame-to-list transfer');
 const graph=f.calls.find(call=>call.kind==='formingGraph'),documents=f.calls.find(call=>call.kind==='formingDocuments');assert.ok(graph.options.delay+graph.options.duration<=documents.options.delay);assert.ok(f.calls.every(call=>call.options.delay+call.options.duration<=800&&call.options.fill==='none'));assert.ok(run.duration<=800);run.cancel();assert.equal(f.cancelled.length,f.calls.length);assert.equal(JSON.stringify(interpreted),before);
 const {settled}=formingUnitStates(),publication={claim_id:settled.claim_id,seq:15,revision:15,state_sha256:settled.state_sha256,event_sha256:settled.last_event_sha256,kind:'knowledge.published',payload:{knowledge:settled.knowledge_published[0]}},fullPlan=ui.transitionPlan(packet,settled,{ready:true,cursor:15,animate:[publication]},[publication]),full=formingMotionFixture(settled);ui.animateTransition(full.host,fullPlan,{selected:'question-4'});const stages=['auSource','auFact','formingGraph','formingDocuments','auKnowledgePublication'].map(kind=>full.calls.find(call=>call.kind===kind));assert.ok(stages.every(Boolean),'one captured accepted state can carry every real changed stage');for(let index=1;index<stages.length;index++)assert.ok(stages[index-1].options.delay+stages[index-1].options.duration<=stages[index].options.delay,'each meaningful stage ends before the next takes attention');assert.ok(stages.at(-1).options.delay+stages.at(-1).options.duration<=800);
 for(const environment of [{reducedMotion:true},{hidden:true},{dialogOpen:true},{keyboard:true}]){const blocked=formingMotionFixture(interpreted);ui.animateTransition(blocked.host,plan,environment);assert.equal(blocked.calls.length,0);}
});

test('forming source review and qualification move only their exact new content and preserve active inspection',()=>{
 const {interpreted,reviewed,settled}=formingUnitStates(),review={claim_id:reviewed.claim_id,seq:13,revision:13,state_sha256:reviewed.state_sha256,event_sha256:reviewed.last_event_sha256,kind:'action.completed'},plan=ui.transitionPlan(interpreted,reviewed,{ready:true,cursor:13,animate:[review]},[review]),f=formingMotionFixture(reviewed);const run=ui.animateTransition(f.host,plan,{selected:'question-4'});
 assert.ok(f.calls.some(call=>call.kind==='auSource'&&call.id==='original'));assert.ok(f.calls.some(call=>call.kind==='auFact'&&call.id==='document:unit_document_4'));assert.ok(f.calls.some(call=>call.kind==='auDocument'&&call.id==='unit_document_4'));assert.ok(!f.calls.some(call=>call.kind==='formingGraph'||call.kind==='auNode'));assert.ok(f.calls.every(call=>call.kind!=='auDocument'||call.id==='unit_document_4'));
 const source=f.calls.find(call=>call.kind==='auSource'),fact=f.calls.find(call=>call.kind==='auFact'),document=f.calls.find(call=>call.kind==='auDocument');assert.ok(source.options.delay+source.options.duration<=fact.options.delay);assert.ok(fact.options.delay+fact.options.duration<=document.options.delay);assert.ok(run.duration<=800);run.cancel();
 const focused=formingMotionFixture(reviewed);ui.animateTransition(focused.host,plan,{activeElement:focused.fact,selected:'question-4'});assert.ok(!focused.calls.some(call=>call.kind==='auFact'),'the inspected fact remains still while accepted fields render');
 const prior=structuredClone(settled);prior.revision=14;prior.state_sha256=hash('f');prior.knowledge_published=[];const published={claim_id:settled.claim_id,seq:15,revision:15,state_sha256:settled.state_sha256,event_sha256:settled.last_event_sha256,kind:'knowledge.published',payload:{knowledge:settled.knowledge_published[0]}},publicationPlan=ui.transitionPlan(prior,settled,ui.acceptEvents(14,{current_revision:15,events:[published]},settled),[published]),knowledge=formingMotionFixture(settled);ui.animateTransition(knowledge.host,publicationPlan,{selected:'question-4'});assert.deepEqual(knowledge.calls.map(call=>[call.kind,call.id]),[['auKnowledgePublication',hash('8')]]);assert.ok(knowledge.calls[0].options.delay+knowledge.calls[0].options.duration<=800);
});

test('accepted action context selects its exact shared-step requirement and fact while explicit inspection retains authority',()=>{
 const notice=state().obligations[0], alternate={...notice,obligation_id:'obligation:branch:lease',document_type:'lease',required_fact_ids:['fact:lease']};
 const result={action_id:'inspect:notice',type:'document_review',status:'completed',node_ids:['branch'],document_type:'notice',obligation_id:notice.obligation_id,fact_id:'fact:notice',summary:'Authored source-inspection context fixture.'},receipt={receipt_sha256:hash('8'),parent_revision:3,parent_state_sha256:hash('a')};
 const s=state({revision:4,state_sha256:hash('f'),last_event_sha256:hash('9'),obligations:[alternate,notice],facts:[...state().facts,{fact_id:'fact:lease',label:'Lease',status:'unresolved'}],actions:[{result,receipt}]});
 const event={seq:4,revision:4,claim_id:s.claim_id,state_sha256:s.state_sha256,event_sha256:s.last_event_sha256,kind:'action.completed',payload:{result,receipt}};
 const saved=JSON.stringify(s),expected={document:'notice',obligation:notice.obligation_id,fact:'fact:notice'};
 assert.equal(ui.acceptedEventNode(s,event),'branch');
 assert.deepEqual(ui.preferredEvidenceContext(s,'branch',[event]),expected,'the latest accepted action cannot borrow the first different document at its node');
 const explicit={document:'lease',obligation:alternate.obligation_id,fact:'fact:lease'};
 assert.deepEqual(ui.preferredEvidenceContext(s,'branch',[event],explicit),{...explicit,trace:undefined});
 assert.deepEqual(ui.preferredEvidenceContext(s,'branch',[event],{},{selected:'branch',evidenceContext:explicit}),explicit);
 for(const forged of [{...event,claim_id:'unrelated'},{...event,event_sha256:hash('0')},{...event,payload:{}}])assert.deepEqual(ui.acceptedEventContext(s,forged,'branch'),{});
 const duplicate={...notice,obligation_id:'obligation:branch:second-notice',required_fact_ids:['fact:lease']};
 s.obligations.push(duplicate);result.obligation_id=duplicate.obligation_id;result.fact_id='fact:lease';
 assert.deepEqual(ui.acceptedEventContext(s,event,'branch'),{document:'notice',obligation:duplicate.obligation_id,fact:'fact:lease'},'equal document types must keep the recorded obligation identity');
 result.obligation_id=notice.obligation_id;result.fact_id='fact:notice';s.obligations.pop();
 assert.equal(JSON.stringify(s),saved,'inspection context may not mutate an accepted saved record');
});
test('reduced motion, hidden views, modal inspection and keyboard mode consume changes without running animations',()=>{
 const plan={nodes:[{id:'branch',delay:160,duration:220}],edges:[{id:'next',delay:0,duration:160}],documents:[{id:'notice',delay:580,duration:180}],facts:[],stages:[],duration:760};
 for(const blocked of [{reducedMotion:true},{hidden:true},{dialogOpen:true},{keyboard:true}]){const f=motionFixture();const run=ui.animateTransition(f.host,plan,blocked);assert.equal(f.calls.length,0);assert.equal(f.clones.length,0);run.cancel();}
 const f=motionFixture(),run=ui.animateTransition(f.host,plan,{});assert.equal(f.clones.length,0,'a visible selected node keeps its parallel graph edge static');assert.equal(f.calls.filter(row=>row.kind==='auNode').length,1);assert.ok(f.calls.some(row=>row.kind==='auDocument'));assert.ok(f.calls.every(row=>row.options.delay+row.options.duration<=800));run.cancel();assert.equal(f.cancelled.length,f.calls.length);
 const edgeOnly=motionFixture();edgeOnly.all.splice(0,1);const edgeRun=ui.animateTransition(edgeOnly.host,plan,{});assert.equal(edgeOnly.clones.length,1,'an edge-only process representation uses one temporary overlay');assert.equal(edgeOnly.calls.filter(row=>row.kind==='clone').length,1);assert.equal(edgeOnly.calls.filter(row=>row.kind==='auNode').length,0);edgeRun.cancel();assert.ok(edgeOnly.clones.every(clone=>clone.removed));assert.equal(edgeOnly.cancelled.length,edgeOnly.calls.length);
});

test('action and knowledge motion uses exact accepted event objects, settles after consumption, and retains qualification distinctions',()=>{
 const before=state({knowledge_published:[]}),eventHash=hash('9');
 for(const kind of ['action.completed','knowledge.used','knowledge.published','withheld']) {
  const after=structuredClone(before);after.revision=4;after.state_sha256=hash('f');after.last_event_sha256=eventHash;
  const event={seq:4,revision:4,claim_id:after.claim_id,state_sha256:after.state_sha256,event_sha256:eventHash,kind:kind==='withheld'?'knowledge.published':kind};
  if(kind==='action.completed') {
   const result={action_id:'assess:notice',status:'completed',node_ids:['branch'],summary:'The accepted notice assessment.'};
   const receipt={receipt_sha256:hash('6'),parent_revision:3,parent_state_sha256:before.state_sha256};
   event.payload={result,receipt};after.actions.push({result,receipt});after.facts[1].status='established';after.evaluation.documents[0].review_state='sufficient';after.evaluation.nodes[1].execution_state='completed';
  } else {
   const knowledge={knowledge_id:'procedure.notice',version:1,...kind==='knowledge.used'?{definition_sha256:hash('7'),applicability:'same_verified_rule_version'}:{knowledge_sha256:hash('8'),source_claim_id:after.claim_id,qualification:{status:kind==='withheld'?'quarantined':'qualified',reason:kind==='withheld'?'The candidate lacks supported applicability.':'Recorded qualification checks.'}}};
   event.payload={knowledge};after[kind==='knowledge.used'?'knowledge_uses':'knowledge_published'].push(knowledge);
  }
  const batch={current_revision:4,current_state_sha256:after.state_sha256,cursor_sha256:eventHash,events:[event]},accepted=ui.acceptEvents(3,batch,after);
  const saved=JSON.stringify(after),plan=ui.transitionPlan(before,after,accepted,[event]),html=ui.workMarkup(after,{},'branch',[event]);
  assert.deepEqual(plan.semantic.map(row=>row.id),[eventHash]);assert.deepEqual(plan.stages,[]);
  const semantic=ui.semanticEventRecord(after,event);assert.equal(semantic.id,eventHash);assert.equal(semantic.type,kind==='action.completed'?'action':kind==='knowledge.used'?'reused':kind==='withheld'?'withheld':'qualified');assert.deepEqual(ui.contextualRecord(after,{},[event],'event','4'),event);
  assert.match(ui.workMarkup(after,{},'branch',[event],'activity'),/data-au-inspect="event"[^>]*data-au-record-id="4"/);
  if(kind==='knowledge.used')assert.match(ui.workMarkup(after,{},'branch',[event],'knowledge'),/data-au-definition-sha="777777/);
  if(kind==='withheld')assert.doesNotMatch(ui.semanticEventMarkup(after,[event]),/Inspect exact version|Knowledge qualified/);
  for(const changed of [{...event,claim_id:'another-claim'},{...event,event_sha256:hash('0')},{...event,state_sha256:hash('0')},{...event,payload:{}}]) {
   assert.equal(ui.semanticEventRecord(after,changed),null,'an unrelated event cannot borrow a matching saved object');
  }
  const initialBatch={...batch,events:[...events(after).events.slice(0,-1),event]};
  assert.equal(ui.transitionPlan(before,after,ui.acceptEvents(null,initialBatch,after),[event]),null);
  assert.equal(ui.transitionPlan(before,after,ui.acceptEvents(3,batch,after,true),[event]),null);
  assert.equal(ui.transitionPlan(after,after,ui.acceptEvents(4,{...batch,events:[]},after),[event]),null);
  for(const environment of [{reducedMotion:true},{hidden:true},{dialogOpen:true},{keyboard:true}]) {
   const f=motionFixture();ui.animateTransition(f.host,plan,environment);assert.equal(f.calls.length,0);
  }
  const f=motionFixture();for(const row of plan.knowledgeUses)f.all.push(f.element('auKnowledgeUse',row.id));for(const row of plan.knowledgePublications)f.all.push(f.element('auKnowledgePublication',row.id));const animation=ui.animateTransition(f.host,plan,{});
  assert.equal(f.calls.filter(row=>row.kind==='auSemanticEvent').length,0,'quiet playback moves the actual changed object rather than a second event badge');assert.ok(f.calls.some(row=>row.kind===(kind==='action.completed'?'auFact':kind==='knowledge.used'?'auKnowledgeUse':'auKnowledgePublication')),'the corresponding accepted content object carries motion');assert.ok(f.calls.every(row=>row.options.iterations===undefined&&row.options.fill==='none'));
  animation.cancel();assert.equal(JSON.stringify(after),saved);
 }
});


test('knowledge reuse and quarantine cannot be presented as newly learned qualified knowledge',()=>{
 const s=state({status:'deferred',run_id:'run.one',knowledge_published:[{qualification:{status:'quarantined'}}],knowledge_uses:[{knowledge_id:'k',version:1}]}),start={kind:'work.started',payload:{run_id:'run.one'}};
 const reuse={kind:'knowledge.used',payload:{knowledge:{knowledge_id:'k',version:1}}};
 const rejected={kind:'knowledge.published',payload:{knowledge:{qualification:{status:'quarantined'}}}};
 assert.equal(ui.progressModel(s,[start,reuse]).stages.at(-1).state,'recorded');
 const quarantine=ui.progressModel(s,[start,reuse,rejected]).stages.at(-1);assert.equal(quarantine.state,'blocked');assert.equal(quarantine.complete,false);assert.match(quarantine.detail,/0 published · 1 reused · 1 quarantined/);
 const html=ui.workMarkup(s,{},'branch',[rejected],'knowledge');assert.match(html,/Withheld from reuse/);assert.doesNotMatch(html,/Qualified knowledge version published/);
 assert.equal(ui.progressModel(s,[{kind:'interpretation.accepted',payload:{}}]).stages.find(stage=>stage.id==='verification').state,'pending');
});

test('recorded knowledge reuse has a readable marker without implying new qualification',()=>{
 const s=state({status:'deferred',run_id:'run.one',knowledge_published:[],knowledge_uses:[{knowledge_id:'k',version:1}]}),start={kind:'work.started',payload:{run_id:'run.one'}};
 const reuse={kind:'knowledge.used',payload:{knowledge:{knowledge_id:'k',version:1}}};
 const knowledgeMarkup=history=>ui.progressMarkup(s,history).match(/<li data-au-stage="knowledge"[\s\S]*?<\/li>/)[0];
 const pending=knowledgeMarkup([start]);assert.match(pending,/data-state="pending"/);assert.doesNotMatch(pending,/Reuse recorded|↺|✓/);
 const recorded=knowledgeMarkup([start,reuse]);assert.match(recorded,/data-state="recorded"/);assert.match(recorded,/aria-hidden="true">↺<\/span>/);assert.match(recorded,/<span>Reuse recorded · 0 published · 1 reused<\/span>/);assert.doesNotMatch(recorded,/✓|data-state="complete"/);
 assert.equal(ui.progressModel(s,[start,reuse]).stages.at(-1).complete,false);
 const qualified={kind:'knowledge.published',payload:{knowledge:{qualification:{status:'qualified'}}}};
 s.knowledge_published=[qualified.payload.knowledge];const published=knowledgeMarkup([start,reuse,qualified]);assert.match(published,/data-state="complete"/);assert.match(published,/✓/);assert.match(published,/1 published · 1 reused/);assert.doesNotMatch(published,/Reuse recorded|↺/);
 const quarantined={kind:'knowledge.published',payload:{knowledge:{qualification:{status:'quarantined'}}}};
 s.knowledge_published=[quarantined.payload.knowledge];const withheld=knowledgeMarkup([start,reuse,quarantined]);assert.match(withheld,/data-state="blocked"/);assert.match(withheld,/0 published · 1 reused · 1 quarantined/);assert.doesNotMatch(withheld,/Reuse recorded|↺|✓/);
});

test('fictional assets require a same-origin hash-bound URL and exact bytes before use',async()=>{
 const location=new URL('http://localhost:8123/'),packet={title:'Fictional claim',message:'All people are invented.',files:[{file_name:'original.txt',media_type:'text/plain',content_base64:Buffer.from('Exact \r\nbytes').toString('base64')}]};
 const bytes=Buffer.from(JSON.stringify({packets:[packet]})),url=ui.demoAssetURL('/assets/examples.json?sha256='+sha(bytes),location);
 assert.equal(url.origin,location.origin);assert.deepEqual(await ui.checkedExamples(bytes,sha(bytes)),[packet]);
 for(const invalid of ['https://elsewhere.example/packet.json?sha256='+sha(bytes),'/assets/examples.json','http://user:password@localhost:8123/x?sha256='+sha(bytes)])assert.throws(()=>ui.demoAssetURL(invalid,location),/identity/);
 await assert.rejects(ui.checkedExamples(Buffer.concat([bytes,Buffer.from(' ')]),sha(bytes)),/identity/);
 const bad=Buffer.from(JSON.stringify({packets:[{...packet,files:[{...packet.files[0],content_base64:'not base64'}]}]}));await assert.rejects(ui.checkedExamples(bad,sha(bad)),/source file/);
});

test('explicit fictional selection fills native files without submitting and cannot change uncertain intake',async t=>{
 const f=dom(),oldLocation=globalThis.location,oldTransfer=globalThis.DataTransfer;
 globalThis.location=new URL('http://localhost:8123/');globalThis.DataTransfer=class{constructor(){this.files=[];this.items={add:file=>this.files.push(file)};}};
 t.after(()=>{globalThis.location=oldLocation;globalThis.DataTransfer=oldTransfer;});
 const source=Buffer.from('Exact original \r\nUnicode: ü.'),packet={title:'Fictional example',message:'Fictional source message.',files:[{file_name:'original.txt',media_type:'text/plain',content_base64:source.toString('base64')}]};
 const bytes=Buffer.from(JSON.stringify({packets:[packet]})),asset='/assets/examples.json?sha256='+sha(bytes);
 f.container.ownerDocument.querySelector=()=>({content:asset});
 const select={value:'0',disabled:false,innerHTML:'',matches:s=>s==='[data-au-example]'},wrapper={hidden:true};
 const originalQuery=f.host.querySelector;f.host.querySelector=s=>s==='[data-au-example]'?select:s==='[data-au-examples]'?wrapper:originalQuery(s);
 f.form.querySelectorAll=()=>[...Object.values(f.fields),select,f.submit];
 const api=fakeApi({handle:async(path,init)=>{if(path.includes('/assets/examples.json'))return{ok:true,arrayBuffer:async()=>bytes};if(init.method==='POST')throw new Error('Intake response lost');}});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await newClaim(f);
 await waitFor(()=>!wrapper.hidden);assert.equal(f.fields.title.value,'New title');
 f.listeners.get('change')({target:select});assert.equal(f.fields.title.value,packet.title);assert.equal(f.fields.message.value,packet.message);assert.deepEqual(Buffer.from(await f.fields.files.files[0].arrayBuffer()),source);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
 await f.listeners.get('submit')({target:f.form,preventDefault(){}});assert.equal(select.disabled,true);const originalTitle=f.fields.title.value;select.disabled=false;select.value='0';f.fields.title.value='Retained pending title';f.listeners.get('change')({target:select});assert.equal(f.fields.title.value,'Retained pending title');assert.equal(api.calls.filter(call=>call.init.method==='POST').length,1);assert.equal(originalTitle,packet.title);
});


function routingFixture(t,fragment='') {
 const old=Object.fromEntries(['location','history','addEventListener','removeEventListener'].map(key=>[key,globalThis[key]])),listeners=new Map(),entries=['http://localhost:8123/?journey=autonomous'+fragment];let index=0,pushes=0;
 const oldStorage=Object.getOwnPropertyDescriptor(globalThis,'sessionStorage'),storage=new Map();
 Object.defineProperty(globalThis,'sessionStorage',{configurable:true,value:{getItem:key=>storage.get(String(key))??null,setItem(key,value){storage.set(String(key),String(value));},removeItem(key){storage.delete(String(key));}}});
 globalThis.location=new URL(entries[0]);
 globalThis.addEventListener=(type,fn)=>listeners.set(type,fn);globalThis.removeEventListener=(type,fn)=>{if(listeners.get(type)===fn)listeners.delete(type);};
 globalThis.history={pushState(_state,_unused,url){entries.splice(++index);entries.push(new URL(url,globalThis.location).href);globalThis.location=new URL(entries[index]);pushes++;},replaceState(_state,_unused,url){entries[index]=new URL(url,globalThis.location).href;globalThis.location=new URL(entries[index]);}};
 const fire=()=>{listeners.get('popstate')?.();listeners.get('hashchange')?.();};
 t.after(()=>{Object.assign(globalThis,old);if(oldStorage)Object.defineProperty(globalThis,'sessionStorage',oldStorage);else delete globalThis.sessionStorage;});
 return {listeners,get pushes(){return pushes;},get hash(){return globalThis.location.hash;},external(fragment){globalThis.location.hash=fragment;fire();},back(){if(index>0){globalThis.location=new URL(entries[--index]);fire();}},forward(){if(index+1<entries.length){globalThis.location=new URL(entries[++index]);fire();}}};
}
function navClick(f,value) {
 const target={dataset:{auNav:value},closest(){return this;},hasAttribute:attr=>attr==='data-au-nav'};f.listeners.get('click')({target});
}

test('ready saved snapshot assets paint derivative work immediately while fresh GET stays independent',async t=>{
 routingFixture(t);const f=operationOpeningDOM(),asset=savedSnapshotAssetFixture(),fresh=deferredRead();
 const api=fakeApi({handle:async path=>path.endsWith('/saved-history-test.json')?new Response(asset.bytes):path.endsWith('/claims/claim-a/snapshot?after=0')?fresh.promise:null});
 const controller=ui.mount(f.container,{fetch:api.fetch,savedSnapshot:asset.descriptor,allowNativeSavedSnapshot:true});t.after(()=>controller.destroy());assert.equal(await controller.savedSnapshotReady,true);
 const opening=controller.openClaim('claim-a');assert.match(f.host.innerHTML,new RegExp(`data-au-revision="3" data-au-state-sha="${asset.body.state.state_sha256}"`));assert.equal(f.attributes.get('data-au-read-state'),'refreshing');assert.doesNotMatch(f.host.innerHTML,/data-au-operation-stage|data-au-current-operation/);
 assert.equal(api.calls.filter(row=>row.path.endsWith('/snapshot?after=0')).length,1);assert.equal(api.calls.filter(row=>row.path.includes('/operations?')||row.init.method==='POST').length,0);
 const live=structuredClone(asset.body);live.projection.node_capabilities.branch.authorized=false;fresh.resolve(response(live));await opening;
 f.listeners.get('click')({target:control(f,'data-au-detail','activity')});f.listeners.get('click')({target:control(f,'data-au-inspect','claim')});assert.equal(JSON.parse(f.recordPre.textContent).projection.node_capabilities.branch.authorized,false);
});

test('an immediate saved selection retains pending asset admission without waiting or moving focus',async t=>{
 routingFixture(t);const f=dom(),asset=savedSnapshotAssetFixture(),pending=deferredRead(),fresh=deferredRead();let assetSignal;
 const api=fakeApi({handle:async(path,init)=>path.endsWith('/saved-history-test.json')?(assetSignal=init.signal,pending.promise):path.endsWith('/claims/claim-a/snapshot?after=0')?fresh.promise:null});
 const controller=ui.mount(f.container,{fetch:api.fetch,savedSnapshot:asset.descriptor,allowNativeSavedSnapshot:true});t.after(()=>{controller.destroy();fresh.resolve(response(asset.body));});await waitFor(()=>Boolean(assetSignal));controller.openClaim('claim-a');const focus={};f.container.ownerDocument.activeElement=focus;
 assert.equal(assetSignal.aborted,false);assert.equal(api.calls.filter(row=>row.path.endsWith('/snapshot?after=0')).length,1);assert.doesNotMatch(f.host.innerHTML,/data-au-state-sha=/);
 pending.resolve(new Response(asset.bytes));assert.equal(await controller.savedSnapshotReady,true);await settle();assert.match(f.host.innerHTML,new RegExp(asset.body.state.state_sha256));assert.equal(f.container.ownerDocument.activeElement,focus);
});

test('saved snapshot preload is public-only and an unavailable asset leaves ordinary GET opening intact',async t=>{
 routingFixture(t);const f=dom(),asset=savedSnapshotAssetFixture(),api=fakeApi({handle:async path=>path.endsWith('/saved-history-test.json')?new Response(asset.bytes):null});
 const descriptor={...asset.descriptor,history_kind:'published_public_synthetic',deployment_commit:'f'.repeat(40)},controller=ui.mount(f.container,{fetch:api.fetch,savedSnapshot:descriptor});t.after(()=>controller.destroy());assert.equal(await controller.savedSnapshotReady,false);assert.equal(api.calls.filter(row=>row.path.endsWith('/saved-history-test.json')).length,0);
 await controller.openClaim('claim-a');assert.match(f.host.innerHTML,/data-au-revision="3"/);assert.equal(api.calls.filter(row=>row.path.endsWith('/claims/claim-a')).length,1);
});

test('saved snapshot acquisition stops a stalled body after its owned fifteen second deadline',async t=>{
 t.mock.timers.enable({apis:['setTimeout']});routingFixture(t);const f=dom(),asset=savedSnapshotAssetFixture();let signal,cancelled=false;
 const api=fakeApi({handle:async(path,init)=>path.endsWith('/saved-history-test.json')?(signal=init.signal,new Response(new ReadableStream({cancel(){cancelled=true;}}))):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,savedSnapshot:asset.descriptor,allowNativeSavedSnapshot:true});t.after(()=>controller.destroy());await settle();assert.ok(signal);t.mock.timers.tick(14999);assert.equal(signal.aborted,false);t.mock.timers.tick(1);assert.equal(await controller.savedSnapshotReady,false);assert.equal(signal.aborted,true);assert.equal(cancelled,true);
});

for(const scenario of ['navigation','replay','inspection','hidden','fresh-first'])test(`late saved snapshot admission cannot replace ${scenario} work`,async t=>{
 routingFixture(t);const f=dom(),asset=savedSnapshotAssetFixture(),pending=deferredRead(),fresh=deferredRead();let assetSignal;
 const api=fakeApi({handle:async(path,init)=>path.endsWith('/saved-history-test.json')?(assetSignal=init.signal,pending.promise):path.endsWith('/claims/claim-a/snapshot?after=0')?fresh.promise:path.includes('/replay?')?new Promise(()=>{}):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,savedSnapshot:asset.descriptor,allowNativeSavedSnapshot:true});t.after(()=>{controller.destroy();fresh.resolve(response(asset.body));});await waitFor(()=>Boolean(assetSignal));const opening=controller.openClaim('claim-a');
 if(scenario==='navigation')await controller.showKnowledge();
 if(scenario==='replay')controller.openClaim('claim-a',true,{mode:'replay',through:1});
 if(scenario==='inspection')f.listeners.get('click')({target:control(f,'data-au-detail','activity')});
 if(scenario==='hidden')f.container.ownerDocument.hidden=true;
 if(scenario==='fresh-first'){const live=structuredClone(asset.body);live.state.title='Fresh current wins';live.projection.node_capabilities.branch.authorized=false;fresh.resolve(response(live));await opening;}
 const before=f.host.innerHTML,focus={};f.container.ownerDocument.activeElement=focus;pending.resolve(new Response(asset.bytes));await controller.savedSnapshotReady;await settle();assert.equal(f.host.innerHTML,before);assert.equal(f.container.ownerDocument.activeElement,focus);
 if(['navigation','replay'].includes(scenario))assert.equal(assetSignal.aborted,true);
 assert.equal(api.calls.filter(row=>row.path.includes('/operations?')||row.init.method==='POST').length,0);
});

test('Cases page, domain and search navigation retains URL state and Back while resetting changed refinements',async t=>{
 const routing=routingFixture(t,'#autonomous/cases?page=4'),f=dom(),rows=Array.from({length:150},(_,index)=>({claim_id:`original-${index}`,origin:'canonical_original',title:`Original case ${index}`,source_preview:{text:index===149?'Rare original intake passage':'Original intake'},status:'not_started',browse_metadata:{domain:index<50?'defect_mold_heating':index<100?'lease_termination_dispute':'rent_increase_dispute'}})),before=JSON.stringify(rows);
 const api=fakeApi({handle:async(path,init)=>path.endsWith('/claims')&&init.method!=='POST'?response({claims:rows}):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 const ids=()=>[...f.host.querySelector('[data-au-claims]').innerHTML.matchAll(/data-au-claim="([^"]+)"/g)].map(match=>match[1]);
 assert.deepEqual(ids(),rows.slice(60,80).map(row=>row.claim_id));assert.equal(new URLSearchParams(routing.hash.split('?')[1]).get('page'),'4');
 f.listeners.get('click')({target:control(f,'data-au-page','5')});assert.deepEqual(ids(),rows.slice(80,100).map(row=>row.claim_id));assert.equal(new URLSearchParams(routing.hash.split('?')[1]).get('page'),'5');
 routing.back();await settle();assert.deepEqual(ids(),rows.slice(60,80).map(row=>row.claim_id));assert.equal(new URLSearchParams(routing.hash.split('?')[1]).get('page'),'4');
 f.listeners.get('click')({target:control(f,'data-au-domain','rent_increase_dispute')});assert.deepEqual(ids(),rows.slice(100,120).map(row=>row.claim_id));let params=new URLSearchParams(routing.hash.split('?')[1]);assert.equal(params.get('domain'),'rent_increase_dispute');assert.equal(params.get('page'),null);
 f.listeners.get('click')({target:control(f,'data-au-page','3')});assert.deepEqual(ids(),rows.slice(140).map(row=>row.claim_id));
 const search=control(f,'data-au-claim-search');search.value='Rare original';search.matches=selector=>selector==='[data-au-claim-search]';f.listeners.get('input')({target:search});assert.deepEqual(ids(),['original-149']);params=new URLSearchParams(routing.hash.split('?')[1]);assert.equal(params.get('q'),'Rare original');assert.equal(params.get('page'),null);assert.equal(params.get('domain'),'rent_increase_dispute');
 assert.equal(JSON.stringify(rows),before);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);assert.doesNotMatch(f.host.innerHTML,/au-collection-summary|data-au-claim-filter|data-au-refresh-claims/);
});
for(const scenario of ['failed-only','partial-outcome-with-failure','failed-reconciliation','evidence-deferred','failed-then-reconciled']) test(`recorded presentation retains ${scenario} history and advances only after an accepted outcome`,async t=>{
 t.mock.timers.enable({apis:['setTimeout']});
 const f=dom(),id=ui.DEMO_CASES[0].claim_id,next=ui.DEMO_CASES[1].claim_id;
 const stopped={code:'verification_deferred',reason:'interpretation citation is not an exact claim source span',details:{error_type:'ValueError',workflow_id:'saved-workflow'}};
 const outcome={status:'deferred',title:'Recorded evidence assessment',summary:'The supplied source leaves a question unresolved.',missing_evidence:[],unresolved_facts:[]};
 const blocked=['failed-only','partial-outcome-with-failure','failed-reconciliation'].includes(scenario),head=scenario==='failed-then-reconciled'?15:scenario==='failed-reconciliation'?13:11;
 const zero=claim_id=>({claim_id,title:'Original source packet',message:'Original customer message.',revision:0,state_sha256:sha(`${claim_id}:0`),status:'not_started',mode:'unprocessed',phase:'not_run',graph:null,evaluation:null,outcome:null,deferral:null,facts:[],obligations:[],actions:[],acquired_sources:[],source_descriptors:[]});
 const saved=seq=>seq===0?zero(id):state({claim_id:id,title:'Original source packet',revision:seq,state_sha256:sha(`${id}:${seq}`),last_event_sha256:sha(`event:${seq}`),graph:{...state().graph,claim_id:id},status:seq>=11?'deferred':'running',phase:seq>=11?'deferred':'verifying',outcome:seq>=11&&['partial-outcome-with-failure','failed-reconciliation','evidence-deferred'].includes(scenario)||seq>=14?outcome:null,deferral:seq>=11&&scenario!=='evidence-deferred'&&seq<15?stopped:null,reconciliations:seq>=12?[reconciliation(id,seq===15?'completed':scenario==='failed-reconciliation'&&seq===13?'failed':'started')]:[],actions:[]});
 const envelope=(claim_id,seq)=>{
  const current_revision=claim_id===id?head:0,s=claim_id===id?saved(seq):zero(claim_id);
  const events=Array.from({length:seq},(_,i)=>({seq:i+1,kind:({11:scenario==='evidence-deferred'?'outcome.recorded':'work.deferred',12:'reconciliation.started',13:scenario==='failed-reconciliation'?'reconciliation.failed':'interpretation.accepted',14:'outcome.recorded',15:'reconciliation.completed'})[i+1] || (i===0?'intake':'work.phase'),revision:i+1,state_sha256:sha(`${id}:${i+1}`),event_sha256:sha(`event:${i+1}`),payload:i+1===11?scenario==='evidence-deferred'?{outcome}:stopped:i+1===12?reconciliation(id,'started'):i+1===13&&scenario==='failed-reconciliation'?{reconciliation_id:'saved-reconciliation',admission_sha256:sha('admission_sha256'),reason:'Saved-result admission remains unresolved.'}:i+1===15?{reconciliation_id:'saved-reconciliation',admission_sha256:sha('admission_sha256')}:{phase:'verifying'}}));
  return {state:s,projection:{revision:seq,state_sha256:s.state_sha256},events,cursor_sha256:seq?sha(`event:${seq}`):null,mode:'replay',replay_only:true,through_seq:seq,current_revision,current_state_sha256:sha(`${claim_id}:${current_revision}`),current_event_sha256:current_revision?sha(`event:${current_revision}`):null,provenance:seq?{event_sha256:s.last_event_sha256}:{} };
 };
 const api=fakeApi({handle:async(path)=>{
  if(path.endsWith('/claims'))return response({claims:[{...saved(head),origin:'canonical_original'}]});
  const replay=path.match(/\/claims\/([^/]+)\/replay\?through_seq=(\d+)$/);if(replay)return response(envelope(replay[1],Number(replay[2])));
 }});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 await controller.openClaim(id,true,{mode:'replay',through:head,detail:'activity'});assert.match(f.host.innerHTML,/data-au-context="activity"/);f.listeners.get('click')({target:control(f,'data-au-inspect','claim')});assert.deepEqual(JSON.parse(f.recordPre.textContent).state,JSON.parse(JSON.stringify(saved(head))));f.recordDialog.close();
 const closedRecord=f.recordPre.textContent;
 const priorReads=api.calls.filter(call=>call.path.includes(`/claims/${id}/replay?`)).length;
 await controller.showDemonstration(true,'legacy');
 assert.match(f.host.innerHTML,/data-au-revision="0"/,'Demonstration opens the actual first canonical packet before playback');await settle();
 for(let seq=1;seq<=head;seq++){
  t.mock.timers.tick(4100);await settle();const prefix=saved(seq),html=f.host.innerHTML;assert.match(html,new RegExp(`data-au-revision="${seq}" data-au-state-sha="${prefix.state_sha256}"`));assert.match(html,/data-au-context="step"/);assert.match(html,/<section class="au-(?:forming-process|process-hero) au-evidence-process" aria-label="(?:Complete recorded process|Decision neighborhood)">/);
  assert.deepEqual([...html.matchAll(/data-au-node="([^"]+)"/g)].map(match=>match[1]),prefix.graph.nodes.map(node=>node.node_id),'forming and settled layouts preserve every actual prefix node');assert.deepEqual([...html.matchAll(/data-au-edge="([^"]+)"/g)].map(match=>match[1]),prefix.graph.edges.map(edge=>edge.edge_id),'presentation preserves the exact accepted edge identities');assert.match(html,/data-au-node="branch"[^>]*aria-pressed="true"/);assert.match(html,/data-au-selected-step="branch"/);if(html.includes('data-au-forming="true"'))assert.match(html,new RegExp(`data-au-forming-revision="${seq}" data-au-forming-sha="${prefix.state_sha256}"`));
  assert.equal(f.recordPre.textContent,closedRecord,'quiet replay does not serialize into a closed History dialog');
 }
 assert.equal(api.calls.filter(call=>call.path.includes(`/claims/${id}/replay?`)).length-priorReads,head+1,'every saved prefix, including failure, remains inspectable');
 if(blocked)assert.match(f.host.innerHTML,/data-au-claim-status>Execution failed\.<\/span>/);
 t.mock.timers.tick(4100);await settle();
 const nextReads=api.calls.filter(call=>call.path.includes(`/claims/${next}/replay?`));
 assert.equal(nextReads.length,blocked?0:1);
 if(blocked){
  assert.match(f.status.textContent,/no settled operational outcome.*stopped at its saved head/i);
  assert.ok(f.host.innerHTML.includes(stopped.reason));assert.doesNotMatch(f.host.innerHTML,/data-au-demo-stop/);
  t.mock.timers.tick(20000);await settle();assert.equal(api.calls.filter(call=>call.path.includes(`/claims/${next}/replay?`)).length,0);
 }
 for(let seq=1;seq<=head;seq++){
  await controller.openClaim(id,false,{mode:'replay',through:seq,detail:'activity'});f.listeners.get('click')({target:control(f,'data-au-inspect','claim')});
  assert.deepEqual(JSON.parse(f.recordPre.textContent).state,JSON.parse(JSON.stringify(saved(seq))),'opening History retains every exact prefix field despite quiet presentation');if(scenario==='failed-then-reconciled'&&seq>=12){assert.equal(JSON.parse(f.recordPre.textContent).state.reconciliations[0].status,seq===15?'completed':'started');assert.equal(JSON.parse(f.recordPre.textContent).state.reconciliations[0].original_deferral.reason,stopped.reason);}
  f.recordDialog.close();
 }
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});
async function newClaim(f) { navClick(f,'intake');await settle(); }
test('initial deep links and duplicate browser history events read saved state once without adding entries',async t=>{
 const routing=routingFixture(t,'#autonomous/claim/claim-a'),f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 assert.match(f.host.innerHTML,/data-au-graph/);assert.equal(routing.pushes,0);assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a')).length,1);
 assert.equal(api.calls.filter(call=>call.path.endsWith('/knowledge')).length,1,'direct entry quietly warms Knowledge even without an idle callback');
 routing.external('#autonomous/knowledge');await settle();assert.match(f.host.innerHTML,/au-quiet-knowledge/);assert.equal(api.calls.filter(call=>call.path.endsWith('/knowledge')).length,2,'explicit Knowledge navigation revalidates the warmed read');assert.equal(routing.pushes,0);
 routing.external('#autonomous/claim/claim-a');await settle();assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a')).length,2);assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a/events?after=0')).length,2);
 routing.external('#autonomous/claim/claim-a');await settle();assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a')).length,2);assert.equal(routing.pushes,0);
 controller.destroy();assert.equal(routing.listeners.size,0);
});

test('internal Work, Knowledge and claim navigation adds only changed fragments and supports Back/Forward',async t=>{
 const routing=routingFixture(t),f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();assert.equal(routing.pushes,0);
 navClick(f,'knowledge');await settle();assert.equal(routing.hash,'#autonomous/knowledge');assert.equal(routing.pushes,1);
 navClick(f,'knowledge');await settle();assert.equal(routing.pushes,1);
 await controller.openClaim('claim-a');assert.equal(routing.pushes,2);assert.match(f.host.innerHTML,/data-au-graph/);
 routing.back();await settle();assert.match(f.host.innerHTML,/au-quiet-knowledge/);routing.back();await settle();assert.match(f.host.innerHTML,/<h1[^>]*>Cases<\/h1>/);
 routing.forward();await settle();assert.match(f.host.innerHTML,/au-quiet-knowledge/);routing.forward();await settle();assert.match(f.host.innerHTML,/data-au-graph/);assert.equal(routing.pushes,2);
 navClick(f,'intake');await settle();assert.equal(routing.hash,'#autonomous/new');assert.equal(routing.pushes,3);assert.equal(globalThis.location.search,'?journey=autonomous');
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('a browser route change during an uncertain intake waits for its result and preserves the exact retry request',async t=>{
 const routing=routingFixture(t),f=dom();let rejectPost;
 const api=fakeApi({handle:async(path,init)=>{if(init.method==='POST')return new Promise((resolve,reject)=>{rejectPost=reject;});}}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await newClaim(f);
 const priorKnowledgeReads=api.calls.filter(call=>call.path.endsWith('/knowledge')).length;
 const submission=f.listeners.get('submit')({target:f.form,preventDefault(){}});await settle();routing.external('#autonomous/knowledge');assert.equal(api.calls.filter(call=>call.path.endsWith('/knowledge')).length,priorKnowledgeReads,'busy intake navigation must not start a new Knowledge read');
 rejectPost(new Error('Intake response unconfirmed'));await submission;await settle();assert.match(f.host.innerHTML,/au-quiet-knowledge/);assert.equal(routing.pushes,1,'only the explicit New claim navigation added an entry');
 assert.equal(api.calls.filter(call=>call.path.endsWith('/knowledge')).length,priorKnowledgeReads+1,'the deferred Knowledge route reads once after the intake result settles');
 routing.external('#autonomous/new');await settle();assert.match(f.message.textContent,/same saved intake request/);assert.equal(f.fields.title.disabled,true);assert.equal(f.submit.disabled,false);
 const retry=f.listeners.get('submit')({target:f.form,preventDefault(){}});await settle();const writes=api.calls.filter(call=>call.init.method==='POST');assert.equal(writes.length,2);assert.equal(writes[0].init.body,writes[1].init.body);rejectPost(new Error('Still unconfirmed'));await retry;
});


test('graph selection and return keep focus on its junction without moving the page at either width',async t=>{
 const originalMatch=globalThis.matchMedia;let mobile=true;globalThis.matchMedia=query=>({matches:query==='(max-width: 800px)'&&mobile,addEventListener(){},removeEventListener(){}});t.after(()=>{globalThis.matchMedia=originalMatch;});
 const f=dom(),doc=f.container.ownerDocument,scrolls=[];
 function element(attr,value){return{dataset:{[attr.replace(/^data-/, '').replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]:value},hasAttribute:name=>name===attr,getAttribute:name=>name===attr?value:null,matches:()=>false,closest(){return this;},focus(options){doc.activeElement=this;this.focusOptions=options;},scrollIntoView(options){scrolls.push({attr,value,options});}};}
 const node=element('data-au-node','branch'),heading=element('data-au-inspector-heading','branch'),back=element('data-au-back-process','branch'),relation=element('data-au-select','branch'),inspector={scrollIntoView(options){scrolls.push({attr:'inspector',options});}};
 const all=[node,heading,back,relation],originalQuery=f.host.querySelector;
 f.host.contains=element=>all.includes(element);f.host.querySelector=selector=>selector==='[data-au-inspector-heading]'?heading:selector==='.au-inspector'?inspector:originalQuery(selector);
 f.host.querySelectorAll=selector=>all.filter(el=>el.hasAttribute(selector.slice(1,-1)));
 let saved=state();const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');assert.equal(scrolls.length,0);
 node.focus();f.listeners.get('click')({target:node});assert.equal(doc.activeElement,node);assert.deepEqual(node.focusOptions,{preventScroll:true});assert.equal(scrolls.length,0);
 saved=state({revision:4,state_sha256:hash('f')});const beforePoll=scrolls.length;await controller.refresh();assert.equal(doc.activeElement,node);assert.equal(scrolls.length,beforePoll);
 f.listeners.get('click')({target:back});assert.equal(doc.activeElement,node);assert.equal(scrolls.length,0);
 f.listeners.get('click')({target:relation});assert.equal(doc.activeElement,node);assert.equal(scrolls.length,0);
 mobile=false;node.focus();const beforeDesktop=scrolls.length;f.listeners.get('click')({target:node});assert.equal(doc.activeElement,node);assert.equal(scrolls.length,beforeDesktop);
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('a focused claim title allows saved revisions to render during polling',async t=>{
 const f=dom(),heading=f.host.querySelector('h1');
 heading.hasAttribute=()=>false;heading.matches=()=>false;f.host.contains=element=>element===heading;
 let saved=state();const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 assert.equal(f.container.ownerDocument.activeElement,heading);
 saved=state({revision:4,state_sha256:hash('f'),phase:'interpreting',phase_summary:'Reading the original agreement.'});
 await controller.refresh();
 assert.match(f.host.innerHTML,/data-au-revision="4"/);assert.deepEqual(ui.contextualRecord(saved,{},[],'claim').state.phase_summary,'Reading the original agreement.');assert.doesNotMatch(f.status.textContent,/Updates paused/);
});

test('direct panel inspection retains Sources Documents Knowledge and History through an accepted requiring-step advance',async t=>{
 for(const panel of ['sources','documents','knowledge','activity'])await t.test(panel,async t=>{
  const f=dom(),before=state();before.evaluation.nodes[1].execution_state='blocked';before.evaluation.nodes[1].blocked_by=['start'];let saved=before;
  const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response({state:saved,projection:{claim_id:saved.claim_id,revision:saved.revision,state_sha256:saved.state_sha256}}):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a',true,{detail:panel});
  assert.match(f.host.innerHTML,new RegExp(`data-au-context="${panel}"`));saved=structuredClone(before);saved.revision=4;saved.state_sha256=hash('f');saved.evaluation.nodes[1].execution_state='ready';saved.evaluation.nodes[1].blocked_by=[];await controller.refresh();await settle();
  assert.match(f.host.innerHTML,new RegExp(`data-au-context="${panel}"`));assert.equal(api.calls.some(call=>call.init.method==='POST'),false);
 });
});

test('an accepted live requiring-step advance focuses its actual new requirement while manual inspection keeps its focus',async t=>{
 for(const held of [false,true])await t.test(String(held),async t=>{
  const f=dom(),before=state();before.evaluation.nodes[1].execution_state='blocked';before.evaluation.nodes[1].blocked_by=['start'];before.evaluation.documents[0].route_state='established';before.evaluation.documents[0].review_state='sufficient';let saved=before;
  const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response({state:saved,projection:{claim_id:saved.claim_id,revision:saved.revision,state_sha256:saved.state_sha256}}):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
  if(held)f.listeners.get('click')({target:control(f,'data-au-node','start')});
  saved=structuredClone(before);saved.revision=4;saved.state_sha256=hash('f');saved.evaluation.nodes[1].execution_state='ready';saved.evaluation.nodes[1].blocked_by=[];await controller.refresh();await settle();
  assert.match(f.host.innerHTML,/data-au-obligation="obligation:branch:notice"/);assert.match(f.host.innerHTML,new RegExp(`data-au-selected-step="${held?'start':'branch'}"`));
  assert.equal(api.calls.some(call=>call.init.method==='POST'),false);
 });
});

test('unchanged verified polling and reconnect keep existing claim nodes while changed capabilities and revisions still render',async t=>{
 const f=dom(),visibility=new Map(),viewport={scrollLeft:0,scrollTop:0},query=f.host.querySelector;
 f.container.ownerDocument.addEventListener=(type,fn)=>visibility.set(type,fn);f.container.ownerDocument.removeEventListener=type=>visibility.delete(type);
 f.host.querySelector=selector=>selector==='.au-graph-viewport'?viewport:query(selector);
 let saved=state({status:'deferred',outcome:{status:'deferred',summary:'A question remains unresolved.'}}),capabilities={},failRead=false;
 const api=fakeApi({handle:async path=>{
  if(path.endsWith('/claims/claim-a')){if(failRead){failRead=false;throw new Error('Read unavailable');}return response({state:saved,projection:{revision:saved.revision,state_sha256:saved.state_sha256,node_capabilities:capabilities}});}
  if(path.includes('/claim-a/events?'))return response(events(saved,Number(path.split('after=')[1])));
 }}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 viewport.scrollLeft=37;viewport.scrollTop=69;
 const target={dataset:{auSelect:'start'},closest(){return this;},hasAttribute:attr=>attr==='data-au-select'};f.listeners.get('click')({target});
 let html=f.host.innerHTML,replacements=0;Object.defineProperty(f.host,'innerHTML',{get:()=>html,set:value=>{replacements++;html=value;}});
 const focused={isConnected:true};f.container.ownerDocument.activeElement=focused;
 await controller.refresh();await controller.refresh();visibility.get('visibilitychange')();await settle();
 failRead=true;await controller.refresh();assert.match(f.status.textContent,/Updates paused/);await controller.refresh();
 assert.equal(replacements,0,'same verified state, cursor and capability projection preserve connected controls even after reconnect');
 assert.match(html,/data-au-selected-step="start"/);assert.equal(f.container.ownerDocument.activeElement,focused);assert.equal(viewport.scrollLeft,37);assert.equal(viewport.scrollTop,69);
 capabilities={start:{authorized:false,reason:'Changed execution limit.'}};await controller.refresh();assert.equal(replacements,1);assert.match(html,/Changed execution limit/);
 saved=state({revision:4,state_sha256:hash('f')});await controller.refresh();assert.equal(replacements,2);assert.match(html,/data-au-revision="4"/);
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('a failed render is retried from saved state even if the next poll has the same revision',async t=>{
 const f=dom();let saved=state();const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 let html=f.host.innerHTML,fail=true;Object.defineProperty(f.host,'innerHTML',{get:()=>html,set:value=>{if(fail){fail=false;throw new Error('Transient render failure');}html=value;}});
 saved=state({revision:4,state_sha256:hash('f')});await controller.refresh();
 assert.match(f.status.textContent,/Updates paused/);assert.match(html,/data-au-revision="3"/);
 await controller.refresh();assert.match(html,/data-au-revision="4"/);assert.match(f.status.textContent,/Connection restored/);
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('present projection identities must bind to the same claim, revision and saved state',()=>{
 const saved=state(),matching={claim_id:saved.claim_id,revision:saved.revision,state_sha256:saved.state_sha256,node_capabilities:{branch:{authorized:false,reason:'Not configured.'}}};
 assert.equal(ui.readState({state:saved,projection:matching},saved.claim_id).projection,matching);
 for(const projection of [{...matching,claim_id:'claim-b'},{...matching,revision:4},{...matching,state_sha256:hash('9')},{...matching,revision:0},{...matching,state_sha256:null}]) {
  assert.throws(()=>ui.readState({state:saved,projection},saved.claim_id),/projection|identity|revision|claim/i);
 }
 // Older envelopes omit identity fields; they still cannot alter the saved state.
 const before=JSON.stringify(saved),legacy={node_capabilities:{branch:{authorized:true}}};
 assert.equal(ui.readState({state:saved,projection:legacy}).projection,legacy);assert.equal(JSON.stringify(saved),before);
});

test('an initial event/state revision mismatch keeps the claim private until a matching read arrives',{timeout:1000},async t=>{
 const f=dom();let reads=0,finishRead;
 const next=state({revision:4,state_sha256:hash('f'),title:'Verified new revision'});
 const api=fakeApi({handle:async path=>{
  if(path.endsWith('/claims/claim-a')){reads++;return reads===1?response(state()):new Promise(resolve=>{finishRead=resolve;});}
  if(path.includes('/claim-a/events?'))return response(events(next));
 }}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 const opening=controller.openClaim('claim-a');await settle();
 assert.doesNotMatch(f.host.innerHTML,/Original incoming claim|Inspect message|Check separate service|data-au-node/);
 assert.equal(reads,2,'the first mismatch should trigger a bounded fresh snapshot read');
 finishRead(response(next));await opening;
 assert.match(f.host.innerHTML,/Verified new revision/);assert.match(f.host.innerHTML,/data-au-revision="4"/);
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('initial revision mismatch bounds immediate reads and retains automatic recovery plus explicit retry',{timeout:1000},async t=>{
 const f=dom(),api=fakeApi({handle:async path=>path.includes('/claim-a/events?')?response(events(state({revision:4,state_sha256:hash('f')}))):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 const reads=api.calls.filter(call=>call.path.endsWith('/claims/claim-a')).length;
 assert.ok(reads>=2&&reads<=3,`mismatched initial load made ${reads} snapshot reads`);
 assert.doesNotMatch(f.host.innerHTML,/Original incoming claim|data-au-node/);assert.match(f.host.innerHTML,/Retry opening claim/);
 for(let i=0;i<4;i++)await settle();assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a')).length,reads,'an unmatched initial claim must not start background polling');
});

test('a mismatched refresh projection and a stale saved revision retain the last verified claim',async t=>{
 const f=dom();let saved=state(),projection={claim_id:'claim-a',revision:3,state_sha256:hash('a')};
 const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response({state:saved,projection}):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 await controller.openClaim('claim-a');
 const verified=f.host.innerHTML;
 saved=state({revision:4,state_sha256:hash('f'),title:'Unverified capability snapshot'});projection={claim_id:'claim-a',revision:3,state_sha256:hash('a')};await controller.refresh();
 assert.equal(f.host.innerHTML,verified);assert.match(f.status.textContent,/Updates paused/);assert.doesNotMatch(f.host.innerHTML,/Unverified capability snapshot/);
 saved=state({revision:2,state_sha256:hash('2'),title:'Stale claim title'});projection={claim_id:'claim-a',revision:2,state_sha256:hash('2')};await controller.refresh();
 assert.equal(f.host.innerHTML,verified);assert.doesNotMatch(f.host.innerHTML,/Stale claim title/);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

function control(f,attribute,value='') {
 const dataset={[attribute.replace(/^data-/,'').replace(/-([a-z])/g,(_,char)=>char.toUpperCase())]:value};
 return {dataset,textContent:value||attribute,isConnected:true,disabled:false,hasAttribute:attr=>attr===attribute,getAttribute:attr=>attr===attribute?value:null,matches:()=>false,closest(){return this;},focus(options){f.container.ownerDocument.activeElement=this;this.focusOptions=options;}};
}
function sourceFixture() {
 const f=dom(),callbacks=new Map(),body={innerHTML:'',querySelector:()=>null},title={textContent:''},close=control(f,'data-au-close');
 f.dialog.addEventListener=(type,callback)=>callbacks.set(type,callback);f.dialog.removeEventListener=type=>callbacks.delete(type);
 f.dialog.showModal=()=>{f.dialog.open=true;close.focus();};f.dialog.close=()=>{f.dialog.open=false;callbacks.get('close')?.();};
 const query=f.container.querySelector;f.container.querySelector=selector=>selector==='[data-au-source-content]'?body:selector==='#auSourceTitle'?title:query(selector);
 return {...f,body,sourceTitle:title,close};
}
async function waitFor(predicate) { const deadline=Date.now()+1000;while(!predicate()&&Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,1));assert.ok(predicate(),'the expected asynchronous operation did not complete'); }

test('source inspection verifies exact identity, preserves claim context and returns focus after close',async t=>{
 const f=sourceFixture(),body='😀\nExact source passage.\nAfter',source={claim_id:'claim-a',artifact_id:'original',sha256:hash('d'),text:body,text_sha256:sha(body),complete:true};
 const citation={artifact_id:'original',sha256:hash('d'),text_sha256:sha(body),start_char:2,end_char:23,quote:'Exact source passage.'};
 const api=fakeApi({handle:async path=>path.endsWith('/sources/claim-a/original/text')?response(source):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 const trigger=control(f,'data-au-source','original');trigger.dataset.auCitation=JSON.stringify(citation);trigger.focus();const verified=f.host.innerHTML;
 f.listeners.get('click')({target:trigger});await waitFor(()=>f.body.innerHTML.includes('<mark'));
 assert.equal(f.sourceTitle.textContent,'message.txt');assert.match(f.body.innerHTML,/<mark tabindex="-1">Exact source passage\.<\/mark>/);assert.match(f.body.innerHTML,/Download original/);assert.ok(f.body.innerHTML.includes(source.text_sha256));
 assert.equal(f.host.innerHTML,verified);assert.equal(f.dialog.open,true);assert.equal(f.container.ownerDocument.activeElement,f.close);
 f.listeners.get('click')({target:f.close});assert.equal(f.dialog.open,false);assert.equal(f.container.ownerDocument.activeElement,trigger);assert.deepEqual(trigger.focusOptions,{preventScroll:true});
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('a rejected citation opens its verified original without highlighting the invalid proposed quote',async t=>{
 const f=sourceFixture(),body='Die Familie is the exact original text.',source={claim_id:'claim-a',artifact_id:'original',sha256:hash('d'),text:body,text_sha256:sha(body),complete:true};
 const saved=state({receipts:[{receipt:{receipt_sha256:hash('f'),item_rejections:[{item_id:'step:lt_type',reason:'Quote is not an exact source span.',item:{citations:[{artifact_id:'original',quote:'die Familie'}]}}]}}]});
 const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.endsWith('/sources/claim-a/original/text')?response(source):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 assert.deepEqual(ui.contextualRecord(saved,{},[],'claim').state.receipts[0].receipt.item_rejections[0].item.citations,[{artifact_id:'original',quote:'die Familie'}]);f.listeners.get('click')({target:control(f,'data-au-detail','sources')});const markup=f.host.innerHTML.match(/<button[^>]*data-au-source="original"[^>]*data-au-source-origin="originals:[^"]*"[^>]*>/)?.[0];assert.ok(markup);assert.doesNotMatch(markup,/data-au-citation/);
 const trigger=control(f,'data-au-source','original');trigger.dataset.auSourceOrigin=markup.match(/data-au-source-origin="([^"]*)"/)[1];
 f.listeners.get('click')({target:trigger});await waitFor(()=>f.body.innerHTML.includes('Die Familie'));
 assert.doesNotMatch(f.body.innerHTML,/<mark|die Familie/);assert.ok(f.body.innerHTML.includes(source.text_sha256));assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('an invalid source text never becomes cited evidence and a late source response cannot reopen another claim',async t=>{
 const f=sourceFixture();let finish;
 const source={claim_id:'claim-a',artifact_id:'original',sha256:hash('d'),text:'Unexpected bytes',text_sha256:sha('Different bytes'),complete:true};
 const b=state({claim_id:'claim-b',title:'Second claim',graph:null});let deferred=false;
 const api=fakeApi({handle:async path=>{
  if(path.endsWith('/sources/claim-a/original/text'))return deferred?new Promise(resolve=>{finish=resolve;}):response(source);
  if(path.endsWith('/claims/claim-b'))return response(b);if(path.includes('/claim-b/events?'))return response(events(b));
 }}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 const trigger=control(f,'data-au-source','original');f.listeners.get('click')({target:trigger});await waitFor(()=>f.body.innerHTML.includes('role="alert"'));
 assert.match(f.body.innerHTML,/identity check/);assert.doesNotMatch(f.body.innerHTML,/<mark|<pre|Unexpected bytes/);
 f.dialog.close();deferred=true;f.listeners.get('click')({target:trigger});await settle();await controller.openClaim('claim-b');const settled=f.body.innerHTML;
 finish(response({...source,text_sha256:sha(source.text)}));await settle();await settle();
 assert.equal(f.dialog.open,false);assert.equal(f.body.innerHTML,settled);assert.match(f.host.innerHTML,/Second claim/);
});

const claimRows=[
 {origin:'canonical_original',claim_id:'claim-a',title:'Notice needs a receipt',status:'deferred',phase_summary:'Waiting for the original receipt'},
 {origin:'canonical_original',claim_id:'claim-b',title:'Policy investigation',status:'running',phase_summary:'Checking the cited policy'},
 {origin:'canonical_original',claim_id:'claim-c',title:'Completed assessment',status:'resolved',outcome:{summary:'Internal assessment recorded.'}},
 {origin:'canonical_original',claim_id:'claim-d',title:'Unsupported original format',status:'failed'},
 {origin:'canonical_original',claim_id:'claim-e',title:'Queued acquisition',status:'queued'}
];
test('the default Work collection uses saved statuses and explicit New claim navigation',async t=>{
 const f=dom(),api=fakeApi({handle:async(path,init)=>path.endsWith('/claims')&&init.method!=='POST'?response({claims:claimRows}):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 assert.match(f.container.innerHTML,/<header class="au-identity-header"/);assert.doesNotMatch(f.container.innerHTML,/class="au-rail"/);assert.match(f.container.innerHTML,/data-au-nav="work"/);assert.match(f.container.innerHTML,/data-au-nav="intake"[^>]*>New claim/);
 assert.match(f.host.innerHTML,/class="au-collection(?:\s[^"]*)?"/);assert.doesNotMatch(f.host.innerHTML,/<form[^>]*data-au-intake/);
 const html=ui.claimsMarkup(claimRows);assert.equal([...html.matchAll(/data-au-claim="/g)].length,5);assert.match(html,/Execution stopped/);assert.match(html,/Working/);assert.match(html,/Investigation complete/);assert.match(html,/Execution failed/);assert.match(html,/Queued/);
 await newClaim(f);assert.match(f.host.innerHTML,/<form[^>]*data-au-intake/);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('search and filters select only matching saved claims and preserve original statuses',()=>{
 const before=JSON.stringify(claimRows),ids=options=>[...ui.claimsMarkup(claimRows,options).matchAll(/data-au-claim="([^"]+)"/g)].map(match=>match[1]);
 assert.deepEqual(ids({filter:'working'}),['claim-b','claim-e']);assert.deepEqual(ids({filter:'deferred'}),['claim-a']);assert.deepEqual(ids({filter:'resolved'}),['claim-c']);assert.deepEqual(ids({filter:'failed'}),['claim-d']);
 assert.deepEqual(ids({search:'RECEIPT'}),['claim-a']);assert.deepEqual(ids({filter:'working',search:'policy'}),['claim-b']);assert.deepEqual(ids({filter:'deferred',search:'policy'}),[]);
 const collection=ui.collectionMarkup(claimRows,{filter:'working',search:'policy'});assert.equal([...collection.matchAll(/data-au-claim="/g)].length,1);assert.match(collection,/data-au-filter="working" aria-pressed="true"/);assert.deepEqual(ui.matchingClaims(claimRows,{filter:'failed'}).map(row=>row.claim_id),['claim-d']);
 assert.equal(JSON.stringify(claimRows),before);assert.doesNotMatch(ui.claimsMarkup([]),/data-au-claim="/);
});

test('typing a collection search updates results without replacing the focused native search input',async t=>{
 const f=dom(),search=control(f,'data-au-claim-search'),filter=control(f,'data-au-claim-filter'),count={textContent:''},rows={innerHTML:''};search.value='';filter.value='all';
 search.matches=selector=>selector==='[data-au-claim-search]';filter.matches=selector=>selector==='[data-au-claim-filter]';
 const query=f.host.querySelector;f.host.querySelector=selector=>({'[data-au-claim-search]':search,'[data-au-claim-filter]':filter,'[data-au-collection-count]':count,'[data-au-claims]':rows})[selector]||query(selector);
 const api=fakeApi({handle:async(path,init)=>path.endsWith('/claims')&&init.method!=='POST'?response({claims:claimRows}):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 const shell=f.host.innerHTML;search.focus();search.value='receipt';f.listeners.get('input')({target:search});assert.equal(f.host.innerHTML,shell);assert.equal(f.container.ownerDocument.activeElement,search);assert.match(rows.innerHTML,/Notice needs a receipt/);assert.doesNotMatch(rows.innerHTML,/Policy investigation/);assert.equal(count.textContent,'1 of 5');
 filter.value='working';f.listeners.get('change')({target:filter});assert.equal(f.host.innerHTML,shell);assert.doesNotMatch(rows.innerHTML,/data-au-claim="/);assert.equal(count.textContent,'0 of 5');assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('each local view renders only its current purpose while retaining the same immutable selected claim',()=>{
 const s=state(),before=JSON.stringify(s);
 for(const detail of ['step','documents','knowledge','sources','activity']) {
  const html=ui.workMarkup(s,{},'branch',events(s).events,detail),panels=[...html.matchAll(/<section[^>]*data-au-panel="([^"]+)"[^>]*>/g)];
  assert.deepEqual(panels.map(match=>match[1]),[detail]);assert.doesNotMatch(html,/<details|data-au-panel="[^"]+"[^>]* hidden/);
  assert.match(html,new RegExp(`data-au-detail="${detail}" aria-pressed="true"`));
  if(detail==='step'){assert.match(html,/data-au-node="branch"[^>]*aria-pressed="true"/);assert.match(html,/data-au-selected-step="branch"/);}
  if(detail==='sources')assert.match(html,/<form data-au-arrival/);
 }
 assert.equal(JSON.stringify(s),before);
});

test('supported document routes stay distinct and evidence intake is reachable from current needs',()=>{
 const statuses=['needed_now','needed_later','held_behind_question','held_not_reviewed','not_needed','optional'],labels=['Needed now','Needed later','May be needed','Needs checking','Not required','Optional'];
 const s=state();s.obligations=statuses.map((status,index)=>({obligation_id:`obligation:${index}`,node_id:'branch',document_type:`document-${index}`,label:`Evidence ${index}`}));s.evaluation.documents=statuses.map((route_state,index)=>({document_type:`document-${index}`,route_state,review_state:'unreviewed'}));
 const markup=ui.obligationMarkup(s,'branch');for(let i=0;i<statuses.length;i++){assert.match(markup,new RegExp(`data-status="${statuses[i]}"`));assert.ok(markup.includes(labels[i]),labels[i]);}
 assert.match(ui.workMarkup(state(),{},'branch',[],'documents'),/data-au-add-files/);assert.match(ui.workMarkup(state(),{},'branch',[],'sources'),/<form data-au-arrival/);
});

// This fixture models the relevant native-node lifetime: assigning innerHTML
// creates new form, panel and scroll nodes unless production moves the old form.
// It deliberately does not emulate rendering, layout, or browser accessibility.
function nativeFixture() {
 const f=dom(),query=f.host.querySelector;let html='',intake=null,arrival=null,viewport=null,details=[],panels=[],tabs=[];
 function form(kind) {
  const message={textContent:''},submit={disabled:false,textContent:'',isConnected:true},files=control(f,'data-files');files.files=[];files.name='files';
  const fields={files};if(kind==='intake'){fields.title=control(f,'data-title');fields.title.value='';fields.message=control(f,'data-message');fields.message.value='';}
  const node={elements:fields,isConnected:true,matches:selector=>selector.includes(`data-au-${kind}`),contains:element=>Object.values(fields).includes(element)||element===submit,querySelector:selector=>selector==='.au-form-status'?message:selector==='button[type="submit"]'?submit:null,querySelectorAll:()=>[...Object.values(fields),submit],remove(){this.isConnected=false;if(kind==='intake'&&intake===this)intake=null;if(kind==='arrival'&&arrival===this)arrival=null;},replaceWith(other){this.isConnected=false;other.isConnected=true;if(kind==='intake')intake=other;else arrival=other;}};
  for(const field of Object.values(fields)){field.closest=selector=>selector==='form'?node:null;field.matches=selector=>/input|textarea/.test(selector);}
  return node;
 }
 Object.defineProperty(f.host,'innerHTML',{configurable:true,get:()=>html,set:value=>{
  if(intake)intake.isConnected=false;if(arrival)arrival.isConnected=false;html=value;intake=/<form[^>]*data-au-intake/.test(html)?form('intake'):null;arrival=/<form[^>]*data-au-arrival/.test(html)?form('arrival'):null;viewport=html.includes('au-graph-viewport')?{scrollLeft:0,scrollTop:0}:null;
  const submitLabel=html.match(/<button[^>]*type="submit"[^>]*>([\s\S]*?)<\/button>/)?.[1]?.replace(/<[^>]*>/g,'').replace(/\s+/g,' ').trim();if(intake&&submitLabel)intake.querySelector('button[type="submit"]').textContent=submitLabel;
  details=[...html.matchAll(/<details[^>]*data-au-disclosure="([^"]+)"[^>]*>/g)].map(match=>({dataset:{auDisclosure:match[1]},open:match[0].includes(' open'),querySelector:()=>null}));
  panels=[...html.matchAll(/<section[^>]*data-au-panel="([^"]+)"[^>]*>/g)].map(match=>({dataset:{auPanel:match[1]},hidden:match[0].includes(' hidden')}));
  tabs=[...html.matchAll(/<button[^>]*data-au-detail="([^"]+)"[^>]*aria-pressed="(true|false)"[^>]*>/g)].map(match=>{const node=control(f,'data-au-detail',match[1]);node.pressed=match[2];node.setAttribute=(attr,value)=>{if(attr==='aria-pressed')node.pressed=value;};return node;});
 }});
 f.host.querySelector=selector=>selector==='[data-au-intake]'?intake:selector==='[data-au-arrival]'?arrival:selector==='.au-graph-viewport'?viewport:selector==='button[type="submit"]'?intake?.querySelector(selector)||arrival?.querySelector(selector):query(selector);
 f.host.querySelectorAll=selector=>selector==='[data-au-panel]'?panels:selector==='[data-au-detail]'||selector==='.au-context-nav [data-au-detail]'?tabs:selector==='details[open][data-au-disclosure]'?details.filter(node=>node.open):selector==='[data-au-disclosure]'?details:[];
 f.host.contains=element=>intake?.contains(element)||arrival?.contains(element)||tabs.includes(element)||false;
 return {...f,get intake(){return intake;},get arrival(){return arrival;},get viewport(){return viewport;},get disclosures(){return details;},get panels(){return panels;}};
}
function fileFixture() { const bytes=Buffer.from('Exact original \r\nUnicode: ü.');return{name:'evidence.txt',type:'text/plain',size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}; }

test('an editable New claim draft retains the native form, FileList and typed values through Work and Knowledge',async t=>{
 const f=nativeFixture(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await newClaim(f);
 const form=f.intake,list=[fileFixture()];form.elements.title.value='Unsubmitted draft';form.elements.message.value='Typing the original incoming message.';form.elements.files.files=list;
 navClick(f,'work');await settle();assert.equal(f.intake,null);navClick(f,'knowledge');await settle();await newClaim(f);
 assert.equal(f.intake,form);assert.equal(f.intake.elements.files.files,list);assert.equal(f.intake.elements.title.value,'Unsubmitted draft');assert.equal(f.intake.elements.message.value,'Typing the original incoming message.');assert.equal(f.intake.elements.title.disabled,false);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('an uncertain New claim keeps its native files and exact retry payload through Work navigation',async t=>{
 const f=nativeFixture(),api=fakeApi({handle:async(_path,init)=>{if(init.method==='POST')throw new Error('Intake response lost');}}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await newClaim(f);
 const form=f.intake,list=[fileFixture()];form.elements.title.value='Retained original claim';form.elements.message.value='Original source text';form.elements.files.files=list;await f.listeners.get('submit')({target:form,preventDefault(){}});
 navClick(f,'work');await settle();await newClaim(f);assert.equal(f.intake,form);assert.equal(f.intake.elements.files.files,list);assert.equal(f.intake.elements.title.disabled,true);assert.equal(f.intake.querySelector('button[type="submit"]').disabled,false);
 await f.listeners.get('submit')({target:f.intake,preventDefault(){}});const writes=api.calls.filter(call=>call.init.method==='POST');assert.equal(writes.length,2);assert.equal(writes[0].init.body,writes[1].init.body);assert.ok(JSON.parse(writes[0].init.body).files[0].content_base64);assert.equal(JSON.parse(writes[0].init.body).title,'Retained original claim');
});

test('claim refresh preserves the selected Process scroll and native Sources FileList through separate focused views',async t=>{
 const f=nativeFixture();let saved=state();const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 f.viewport.scrollTop=184;f.viewport.scrollLeft=27;saved=state({revision:4,state_sha256:hash('f')});await controller.refresh();
 assert.equal(f.viewport.scrollTop,184);assert.equal(f.viewport.scrollLeft,27);assert.match(f.host.innerHTML,/data-au-selected-step="branch"/);
 f.listeners.get('click')({target:control(f,'data-au-detail','sources')});assert.equal(f.viewport,null,'Sources has its own focus and does not keep a hidden graph');
 const form=f.arrival,list=[fileFixture()];form.elements.files.files=list;form.elements.files.focus();saved=state({revision:5,state_sha256:hash('5'),phase:'acquiring'});await controller.refresh();
 assert.equal(f.arrival,form);assert.equal(f.arrival.elements.files.files,list);assert.equal(f.container.ownerDocument.activeElement,form.elements.files);assert.match(f.host.innerHTML,/data-au-context="sources"/);
 f.listeners.get('click')({target:control(f,'data-au-detail','step')});assert.match(f.host.innerHTML,/data-au-selected-step="branch"/);assert.equal(f.arrival,null);
 f.listeners.get('click')({target:control(f,'data-au-detail','sources')});assert.equal(f.arrival,form);assert.equal(form.elements.files.files,list);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('uncertain file arrivals retain their claim guard and retry key across details and other claims',async t=>{
 const f=nativeFixture(),b=state({claim_id:'claim-b',title:'Other claim',graph:null});const api=fakeApi({handle:async(path,init)=>{
  if(path.endsWith('/sources')&&init.method==='POST')throw new Error('File arrival response lost');if(path.endsWith('/claims/claim-b'))return response(b);if(path.includes('/claim-b/events?'))return response(events(b));
 }}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 f.listeners.get('click')({target:control(f,'data-au-add-files')});const form=f.arrival,list=[fileFixture()];form.elements.files.files=list;await f.listeners.get('submit')({target:form,preventDefault(){}});
 f.listeners.get('click')({target:control(f,'data-au-detail','step')});f.listeners.get('click')({target:control(f,'data-au-detail','sources')});assert.equal(f.arrival,form);assert.equal(f.arrival.elements.files.files,list);
 await controller.openClaim('claim-b');await controller.openClaim('claim-a');f.listeners.get('click')({target:control(f,'data-au-detail','sources')});assert.equal(f.arrival,form);assert.equal(f.arrival.elements.files.disabled,true);assert.equal(f.arrival.querySelector('button[type="submit"]').disabled,false);
 await f.listeners.get('submit')({target:f.arrival,preventDefault(){}});const writes=api.calls.filter(call=>call.path.endsWith('/sources')&&call.init.method==='POST');assert.equal(writes.length,2);assert.equal(writes[0].path,writes[1].path);assert.equal(writes[0].init.body,writes[1].init.body);assert.equal(JSON.parse(writes[0].init.body).expected_revision,3);assert.equal(JSON.parse(writes[0].init.body).expected_state_sha256,hash('a'));assert.ok(JSON.parse(writes[0].init.body).idempotency_key);
});

test('recorded actions distinguish the current accepted run from historical and unassociated results',()=>{
 const saved=state({run_id:'run.new',actions:[
  {result:{action_id:'old',node_ids:['branch'],status:'completed',summary:'Earlier receipt assessed.'},receipt:{parent_revision:2,receipt_sha256:hash('1'),operation:'document_review'}},
  {result:{action_id:'new',node_ids:['branch'],status:'completed',summary:'Current receipt assessed.'},receipt:{parent_revision:6,receipt_sha256:hash('2'),operation:'document_review'}},
  {result:{action_id:'unknown',node_ids:['branch'],status:'completed',summary:'Legacy assessment without run association.'},receipt:{receipt_sha256:hash('3')}}
 ]}),history=[{seq:1,kind:'work.started',payload:{run_id:'run.old'}},{seq:5,kind:'work.started',payload:{run_id:'run.new'}}],before=JSON.stringify(saved);
 const rows=ui.actionRows(saved,history);assert.deepEqual(rows.map(row=>row.scope),['historical','current','unassociated']);
 const html=ui.workMarkup(saved,{},'branch',history,'activity');
 for(let index=0;index<rows.length;index++){assert.ok(html.includes(`data-au-inspect="action" data-au-record-id="${rows[index].instanceId}"`));assert.deepEqual(ui.contextualRecord(saved,{},history,'action',rows[index].instanceId),rows[index]);assert.equal(rows[index].receipt.receipt_sha256,hash(String(index+1)));}
 assert.deepEqual(ui.actionRows(saved,[]).map(row=>row.scope),['unassociated','unassociated','unassociated']);assert.equal(JSON.stringify(saved),before);
});

test('a branch inspector joins its own condition, evidence need, document and capability without borrowing sibling facts',()=>{
 const saved=state();saved.graph.nodes.push({node_id:'excluded',label:'Other conditional path',condition:{flag:'commercial_use'}});saved.graph.edges.push({edge_id:'other',source_node_id:'start',target_node_id:'excluded'});saved.evaluation.nodes.push({node_id:'excluded',execution_state:'inactive'});saved.facts.push({fact_id:'condition:commercial_use',label:'Commercial-only condition',status:'false',summary:'Commercial condition does not apply.'});
 saved.facts[0].citations=[{artifact_id:'original',sha256:hash('d'),text_sha256:hash('e'),start_char:0,end_char:11,quote:'Family home'}];
 const projection={node_capabilities:{branch:{authorized:false,id:null,reason:'External dispatch is not configured.'}}},before=JSON.stringify(saved),html=ui.inspectorMarkup(saved,'branch',projection);
 assert.match(ui.workMarkup(saved,projection,'branch',[]),/class="au-process-question au-reading-question"[^>]*data-au-inspector-heading="branch"[^>]*>Check separate service/);
 assert.match(html,/data-au-selected-step="branch"/);assert.deepEqual(ui.contextualRecord(saved,projection,[],'step','branch').node,saved.graph.nodes[1]);
 for(const phrase of ['Family home',saved.facts[0].summary,'Separate notice','Required now in the recorded process.','External dispatch is not configured.'])assert.ok(html.includes(phrase),phrase);
 assert.match(html,/data-au-source="original"[^>]*data-au-citation=/);assert.doesNotMatch(html,/Commercial-only condition|Commercial condition does not apply/);
 assert.equal(ui.contextualRecord(saved,projection,[],'fact','fact:notice').summary,'A separate notice is required.');
 assert.deepEqual(ui.contextualRecord(saved,projection,[],'requirement',saved.obligations[0].obligation_id).obligations,[saved.obligations[0]]);assert.deepEqual(ui.contextualRecord(saved,projection,[],'step','branch').capability,projection.node_capabilities.branch);
 const graph=ui.graphMarkup(saved,'branch',projection);assert.match(graph,/Other conditional path\. Does not apply/);assert.match(graph,/data-au-node="excluded"[^>]*data-status="inactive"/);assert.equal(JSON.stringify(saved),before);
});

test('knowledge reuse retains the exact historical version, originating claim and applicability without proving current facts',()=>{
 const old={knowledge_id:'procedure.one',version:1,title:'Service process',source_claim_id:'origin-one',knowledge_sha256:hash('1'),summary:'Original service procedure.',qualification:{status:'qualified',regression_cases:243,checks:['no_case_values_or_files']},graph:state().graph,facts:state().facts,obligations:state().obligations};
 const latest={...old,version:2,source_claim_id:'origin-two',knowledge_sha256:hash('2'),parent_knowledge_sha256:hash('1'),change_reason:'Verified new receipt field.'};
 const use={knowledge_id:'procedure.one',version:1,knowledge_sha256:hash('1'),claim_id:'receiving-claim',applicability:'same_verified_family_and_rule_version',avoided_rule_compilations:1,avoided_qualification_cases:243},data={versions:[old,latest],uses:[use],quarantined:[]};
 const newest=ui.knowledgeMarkup(data),historical=ui.knowledgeMarkup(data,[],{knowledge_id:old.knowledge_id,version:1,knowledge_sha256:hash('1')});
 assert.match(newest,/data-au-knowledge-identity="procedure.one:2"/);assert.doesNotMatch(newest,/data-au-knowledge-identity="procedure.one:1"/);assert.match(newest,/data-au-claim="origin-two"/);assert.doesNotMatch(newest,/data-au-claim="receiving-claim"/);
 assert.match(historical,/data-au-knowledge-identity="procedure.one:1"/);assert.match(historical,/data-au-claim="origin-one"/);assert.match(historical,/data-au-claim="receiving-claim"/);
 for(const version of [old,latest]){assert.deepEqual(ui.contextualRecord(null,{},[],'knowledge',`${version.knowledge_id}:${version.version}`,data),version);assert.ok(historical.includes(`data-au-knowledge-sha="${version.knowledge_sha256}"`));}
 assert.deepEqual(ui.contextualRecord(null,{},[],'use','0',data),use);old.qualification.definition_sha256=hash('3');latest.qualification={...latest.qualification,definition_sha256:hash('4')};
 assert.deepEqual(ui.knowledgeUses(old,[{...use,definition_sha256:hash('3')}]),[{...use,definition_sha256:hash('3')}]);assert.deepEqual(ui.knowledgeUses(old,[{...use,definition_sha256:hash('9')}]),[],'a matching knowledge hash cannot override a mismatched definition hash');assert.deepEqual(ui.knowledgeUses(old,[{...use,knowledge_sha256:hash('9'),definition_sha256:hash('3')}]),[],'a matching definition hash cannot override a mismatched knowledge hash');
 const saved=state({knowledge_uses:[use]}),before=JSON.stringify(saved),claim=ui.workMarkup(saved,{},'branch',[],'knowledge');assert.match(claim,/Version 1/);assert.match(claim,/case still requires its own source evidence/);assert.deepEqual(ui.contextualRecord(saved,{},[],'use','0'),use);assert.equal(JSON.stringify(saved),before);
 assert.doesNotMatch(claim,/notice.*proven by.*reuse|fact.*established by.*knowledge|human approved|improved accuracy/i);
});

test('full public provenance, receipt checks and quarantine reasons remain inspectable and escaped',()=>{
 const attack='<svg onload="alert(1)">',version={knowledge_id:'k',version:1,title:'Procedure',source_claim_id:'claim-a',knowledge_sha256:hash('a'),qualification:{status:'qualified',regression_cases:243,checks:['no_case_values_or_files'],additional_check:{reason:'Version-specific public check',accepted:true}},source_evidence:{notice:{artifact_id:'original',source_verification:'recorded independent check'}},custom_lineage:{reason:'Public ancestry marker'}};
 const quarantine={knowledge_id:'withheld',qualification:{status:'quarantined',reason:'Exact rule identity changed',details:{failed_check:'public discrepancy marker'}},candidate:{summary:attack}},data={versions:[version],uses:[],quarantined:[quarantine]};
 assert.deepEqual(ui.contextualRecord(null,{},[],'knowledge','k:1',data),version);assert.deepEqual(ui.contextualRecord(null,{},[],'quarantine','0',data),quarantine);
 assert.doesNotMatch(ui.knowledgeMarkup(data),/<svg[^>]*onload=|onload="alert/);
 const saved=state();saved.actions[0].receipt.checks=[{accepted:true,reason:'Public action check',payload:{summary:attack}}];assert.deepEqual(ui.contextualRecord(saved,{},[],'action','0'),ui.actionRows(saved)[0]);
});

function knowledgeFixture() {
 const f=dom();let html='',rows=[],history=null;
 Object.defineProperty(f.host,'innerHTML',{get:()=>html,set:value=>{
  html=value;history={tagName:'DETAILS',open:false,parentElement:f.host};rows=[...value.matchAll(/data-au-knowledge-identity="([^"]+)"/g)].map(match=>{
   const row=control(f,'data-au-knowledge-identity',match[1]);row.parentElement=f.host;row.attributes={};row.setAttribute=(name,value)=>{row.attributes[name]=value;};row.scrollIntoView=options=>{row.scrollOptions=options;};return row;
  });
 }});
 f.host.querySelectorAll=selector=>selector==='[data-au-knowledge-identity]'?rows:[];
 return {...f,get versions(){return rows;},get historyDisclosure(){return history;}};
}

test('Inspect reused knowledge navigates to and reveals the exact historical version and hash',async t=>{
 const routing=routingFixture(t),f=knowledgeFixture(),old={knowledge_id:'procedure.one',version:1,title:'Original procedure',knowledge_sha256:hash('1'),source_claim_id:'origin-one',qualification:{status:'qualified'}},latest={...old,version:2,title:'Latest procedure',knowledge_sha256:hash('2'),source_claim_id:'origin-two'};
 const saved=state({knowledge_uses:[{knowledge_id:old.knowledge_id,version:1,knowledge_sha256:hash('1'),applicability:'same_verified_family_and_rule_version'}]});
 const api=fakeApi({handle:async path=>path.endsWith('/knowledge')?response({versions:[old,latest],uses:[],quarantined:[]}):path.endsWith('/claims/claim-a')?response(saved):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 assert.match(f.host.innerHTML,/data-au-knowledge="procedure.one"[^>]*data-au-version="1"[^>]*data-au-knowledge-sha="1{64}"/);
 const trigger=control(f,'data-au-knowledge','procedure.one');trigger.dataset.auVersion='1';trigger.dataset.auKnowledgeSha=hash('1');f.listeners.get('click')({target:trigger});await waitFor(()=>f.versions.length===1);assert.match(f.host.innerHTML,/data-au-knowledge="procedure.one"[^>]*data-au-version="2"/,'the other version remains reachable in the procedure list');
 const historical=f.versions.find(row=>row.dataset.auKnowledgeIdentity==='procedure.one:1'),current=f.versions.find(row=>row.dataset.auKnowledgeIdentity==='procedure.one:2');
 assert.equal(routing.hash,`#autonomous/knowledge?knowledge=procedure.one&version=1&sha256=${hash('1')}`);assert.equal(historical.attributes['data-pinned'],'true');assert.equal(current,undefined,'a second version is not rendered as another competing record');assert.equal(f.historyDisclosure.open,false,'the exact historical version is the primary record, not a hidden history disclosure');assert.equal(f.container.ownerDocument.activeElement,historical);assert.deepEqual(historical.scrollOptions,{block:'nearest',behavior:'instant'});assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('an unavailable pinned knowledge version or hash never selects the latest version as its replacement',async t=>{
 const routing=routingFixture(t,`#autonomous/knowledge?knowledge=procedure.one&version=1&sha256=${hash('9')}`),f=knowledgeFixture(),latest={knowledge_id:'procedure.one',version:2,title:'Latest procedure',knowledge_sha256:hash('2'),source_claim_id:'origin-two',qualification:{status:'qualified'}};
 const api=fakeApi({handle:async path=>path.endsWith('/knowledge')?response({versions:[latest],uses:[],quarantined:[]}):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await waitFor(()=>f.status.textContent.includes('not available'));
 assert.match(f.status.textContent,/exact reused knowledge version is not available/);assert.equal(f.versions.length,0,'an unavailable exact pin cannot borrow the latest primary version');assert.match(f.host.innerHTML,/data-au-knowledge="procedure.one"[^>]*data-au-version="2"/,'the actual available version remains a deliberate list navigation');assert.equal(routing.pushes,0);assert.ok(routing.hash.includes('version=1'));
 routing.external(`#autonomous/knowledge?knowledge=procedure.one&version=2&sha256=${hash('9')}`);await waitFor(()=>api.calls.filter(call=>call.path.endsWith('/knowledge')).length===2&&f.status.textContent.includes('not available'));
 assert.equal(f.versions.length,0,'an unavailable exact pin cannot borrow the latest primary version');assert.match(f.host.innerHTML,/data-au-knowledge="procedure.one"[^>]*data-au-version="2"/,'the actual available version remains a deliberate list navigation');assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('Cancel returns to the same Work search, status filter and scroll position without writing intake',async t=>{
 const f=dom(),search=control(f,'data-au-claim-search'),filter=control(f,'data-au-claim-filter'),rows={innerHTML:''},count={textContent:''},main={scrollTop:0,scrollLeft:0},scrollCalls=[];
 search.matches=selector=>selector==='[data-au-claim-search]';filter.matches=selector=>selector==='[data-au-claim-filter]';
 const prior=Object.fromEntries(['scrollX','scrollY','scrollTo'].map(name=>[name,globalThis[name]]));Object.assign(globalThis,{scrollX:0,scrollY:0,scrollTo(options){scrollCalls.push(options);globalThis.scrollX=options.left;globalThis.scrollY=options.top;}});t.after(()=>Object.assign(globalThis,prior));
 const containerQuery=f.container.querySelector;f.container.querySelector=selector=>selector==='.au-main'?main:containerQuery(selector);
 let html='';Object.defineProperty(f.host,'innerHTML',{get:()=>html,set:value=>{html=value;f.host.scrollTop=0;main.scrollTop=0;main.scrollLeft=0;search.value=value.match(/data-au-claim-search value="([^"]*)"/)?.[1]||'';filter.value=value.match(/data-au-filter="([^"]+)" aria-pressed="true"/)?.[1]||'all';}});
 const query=f.host.querySelector;f.host.querySelector=selector=>({'[data-au-claim-search]':search,'[data-au-claim-filter]':filter,'[data-au-claims]':rows,'[data-au-collection-count]':count})[selector]||query(selector);
 const api=fakeApi({handle:async(path,init)=>path.endsWith('/claims')&&init.method!=='POST'?response({claims:claimRows}):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 search.value='receipt';f.listeners.get('input')({target:search});filter.value='deferred';f.listeners.get('click')({target:control(f,'data-au-filter','deferred')});f.host.scrollTop=127;main.scrollTop=246;main.scrollLeft=6;globalThis.scrollX=12;globalThis.scrollY=418;
 await newClaim(f);globalThis.scrollX=0;globalThis.scrollY=0;navClick(f,'work');await settle();
 assert.equal(search.value,'receipt');assert.equal(filter.value,'deferred');assert.match(rows.innerHTML,/Notice needs a receipt/);assert.doesNotMatch(rows.innerHTML,/Policy investigation/);assert.equal(count.textContent,'1 of 5');assert.equal(f.host.scrollTop,127);assert.equal(main.scrollTop,246);assert.equal(main.scrollLeft,6);assert.deepEqual(scrollCalls.at(-1),{left:12,top:418,behavior:'instant'});assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('a mismatched polling event cursor never advances the displayed state or consumes the pending event',async t=>{
 const f=dom();let saved=state(),ahead=false;
 const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(ahead?state({revision:5,state_sha256:hash('5')}):saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');const verified=f.host.innerHTML;
 saved=state({revision:4,state_sha256:hash('f'),title:'Fourth saved revision'});ahead=true;await controller.refresh();assert.equal(f.host.innerHTML,verified);
 ahead=false;await controller.refresh();assert.match(f.host.innerHTML,/Fourth saved revision/);assert.match(f.host.innerHTML,/data-au-revision="4"/);const reads=api.calls.filter(call=>call.path.includes('/claim-a/events?'));assert.equal(reads.at(-2).path,reads.at(-1).path);assert.ok(reads.at(-1).path.endsWith('after=3'));assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('closing a source after a saved refresh focuses the replacement citation control in the same claim',async t=>{
 const f=sourceFixture(),body='Verified original text',source={claim_id:'claim-a',artifact_id:'original',sha256:hash('d'),text:body,text_sha256:sha(body),complete:true};let saved=state(),trigger=control(f,'data-au-source','original');
 f.host.contains=element=>element===trigger;f.host.querySelectorAll=selector=>selector==='[data-au-source]'?[trigger]:[];
 const api=fakeApi({handle:async path=>path.endsWith('/sources/claim-a/original/text')?response(source):path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');trigger.focus();f.listeners.get('click')({target:trigger});await waitFor(()=>f.body.innerHTML.includes('Verified original text'));
 const oldTrigger=trigger;oldTrigger.isConnected=false;trigger=control(f,'data-au-source','original');saved=state({revision:4,state_sha256:hash('f')});await controller.refresh();assert.equal(f.dialog.open,true);assert.equal(f.container.ownerDocument.activeElement,f.close);f.dialog.close();assert.equal(f.container.ownerDocument.activeElement,trigger);assert.deepEqual(trigger.focusOptions,{preventScroll:true});
});

test('missing or empty run identities never associate recorded actions with a current run',()=>{
 const actions=[{result:{action_id:'old',status:'completed'},receipt:{parent_revision:2}}];
 for(const run_id of [undefined,null,'','  '])for(const eventRun of [undefined,null,'','  ']) {
  const saved={actions,...(run_id===undefined?{}:{run_id})},event={seq:1,kind:'work.started',payload:{...(eventRun===undefined?{}:{run_id:eventRun})}};
  assert.deepEqual(ui.actionRows(saved,[event]).map(row=>row.scope),['unassociated'],`state run ${String(run_id)} / event run ${String(eventRun)}`);
 }
});

function duplicatePanelFixture() {
 const f=sourceFixture(),query=f.host.querySelector;let html='',panels=[],sources=[],disclosures=[],summaries=[];
 function attach(node,panel) {
  node.parentElement=panel;node.closest=selector=>selector==='[data-au-panel]'?panel:/hidden|inert/.test(selector)?panel.hidden?panel:null:selector==='button,[data-au-nav]'?node:null;
  node.getClientRects=()=>panel.hidden?[]:[{}];Object.defineProperty(node,'offsetParent',{get:()=>panel.hidden?null:f.host});
  node.focus=options=>{node.focusOptions=options;if(!panel.hidden)f.container.ownerDocument.activeElement=node;};return node;
 }
 Object.defineProperty(f.host,'innerHTML',{get:()=>html,set:value=>{
  for(const node of [...sources,...summaries])node.isConnected=false;html=value;panels=['step','documents'].map(id=>({dataset:{auPanel:id},hidden:id!==(value.match(/data-au-context="([^"]+)"/)?.[1]||'step'),parentElement:f.host,getAttribute:name=>name==='data-au-panel'?id:null}));
  const citation=JSON.stringify({artifact_id:'original',sha256:hash('d'),text_sha256:sha('Text'),start_char:0,end_char:4,quote:'Text'});
  sources=panels.map(panel=>{const node=attach(control(f,'data-au-source','original'),panel),get=node.getAttribute;node.dataset.auCitation=citation;node.getAttribute=name=>name==='data-au-citation'?citation:get(name);return node;});
  disclosures=panels.map(panel=>({dataset:{auDisclosure:'obligation:obligation:branch:notice'},open:false,parentElement:panel,closest:selector=>selector==='[data-au-panel]'?panel:null,hasAttribute:name=>name==='data-au-disclosure',getAttribute:name=>name==='data-au-disclosure'?'obligation:obligation:branch:notice':null}));
  summaries=disclosures.map((disclosure,index)=>{const node=attach(control(f,'data-unused'),panels[index]);node.hasAttribute=()=>false;node.matches=selector=>selector==='summary';node.parentElement=disclosure;disclosure.querySelector=selector=>selector==='summary'?node:null;return node;});
 }});
 f.host.contains=node=>sources.includes(node)||summaries.includes(node);
 f.host.querySelector=selector=>selector==='[data-au-context]'?{setAttribute(){}}:query(selector);
 f.host.querySelectorAll=selector=>selector==='[data-au-source]'?sources:selector==='[data-au-panel]'?panels:selector==='[data-au-disclosure]'?disclosures:selector==='details[open][data-au-disclosure]'?disclosures.filter(node=>node.open):[];
 return {...f,get documentSource(){return sources[1];},get hiddenSource(){return sources[0];},get documentSummary(){return summaries[1];},get hiddenSummary(){return summaries[0];}};
}

test('a source dialog returns to its visible All documents origin after polling duplicates its citation in hidden This step',async t=>{
 const f=duplicatePanelFixture(),source={claim_id:'claim-a',artifact_id:'original',sha256:hash('d'),text:'Text',text_sha256:sha('Text'),complete:true};let saved=state();
 const api=fakeApi({handle:async path=>path.endsWith('/sources/claim-a/original/text')?response(source):path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');f.listeners.get('click')({target:control(f,'data-au-detail','documents')});
 f.documentSource.focus();f.listeners.get('click')({target:f.documentSource});await waitFor(()=>f.body.innerHTML.includes('<mark'));saved=state({revision:4,state_sha256:hash('f')});await controller.refresh();assert.equal(f.container.ownerDocument.activeElement,f.close);f.dialog.close();
 assert.equal(f.container.ownerDocument.activeElement,f.documentSource);assert.notEqual(f.container.ownerDocument.activeElement,f.hiddenSource);assert.deepEqual(f.documentSource.focusOptions,{preventScroll:true});
});

test('a refreshed Why required summary retains its visible All documents focus despite a duplicated hidden disclosure',async t=>{
 const f=duplicatePanelFixture();let saved=state();const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');f.listeners.get('click')({target:control(f,'data-au-detail','documents')});f.documentSummary.focus();
 saved=state({revision:4,state_sha256:hash('f')});await controller.refresh();assert.equal(f.container.ownerDocument.activeElement,f.documentSummary);assert.notEqual(f.container.ownerDocument.activeElement,f.hiddenSummary);assert.deepEqual(f.documentSummary.focusOptions,{preventScroll:true});
});

test('actual reuse provenance remains exact in one contextual record without asserting current facts',()=>{
 const attack='<img src=x onerror="alert(1)">',use={knowledge_id:'procedure.one',version:1,definition_sha256:hash('d'),rule_pack_sha256:hash('e'),applicability:'same_verified_family_and_rule_version',avoided_rule_compilations:1,reused_evidence_recipes:2,workflow_id:'workflow.recorded',public_extension:{reason:attack}},s=state({knowledge_uses:[use]}),before=JSON.stringify(s);
 assert.deepEqual(ui.contextualRecord(s,{},[],'use','0'),use);assert.deepEqual(ui.contextualRecord(null,{},[],'use','0',{uses:[use]}),use);
 const data={versions:[{knowledge_id:use.knowledge_id,version:1,definition_sha256:use.definition_sha256}],uses:[{...use,claim_id:'receiving-claim'}],quarantined:[]};
 for(const html of [ui.knowledgeMarkup(data),ui.workMarkup(s,{},'branch',[],'knowledge')]){assert.doesNotMatch(html,/data-au-inspect="(?:use|knowledge|publication)"|<img|onerror="alert/);}
 assert.deepEqual(ui.contextualRecord(null,{},[],'knowledge-index','',data).uses,data.uses);assert.deepEqual(ui.contextualRecord(s,{},[],'claim').state.knowledge_uses,[use]);
 assert.equal(JSON.stringify(s),before);
});

test('one outcome record preserves all verifier issues and deferral details without accepting their text as markup',()=>{
 const attack='<svg onload="alert(1)">',outcome={status:'deferred',title:'Evidence assessment complete; claim deferred',summary:'Recorded source assessment.',missing_evidence:[],unresolved_facts:[],issues:[{code:'source_discrepancy',reason:'Recorded verifier discrepancy',details:{original_quote:attack}}],authority_limits:[],next_action:'Await named evidence.'};
 const deferred={code:'unsupported_format',reason:'No supported extraction.',details:{file_name:'recorded-file.bin',limitation:attack,public_check:'Original receipt retained'}};
 for(const saved of [state({status:'deferred',outcome}),state({status:'deferred',deferral:deferred})]) {const before=JSON.stringify(saved),record=ui.contextualRecord(saved,{},[],'outcome');assert.deepEqual(record,{outcome:saved.outcome,deferral:saved.deferral});assert.doesNotMatch(ui.workMarkup(saved,{},'branch',[]),/<svg\s+onload|onload="alert/);assert.equal(JSON.stringify(saved),before);}

});

test('accepted changes leave hidden document contexts still',()=>{
 const f=motionFixture(),doc=f.host.querySelectorAll('[data-au-document]')[0];
 doc.closest=selector=>selector==='[hidden]'?{hidden:true}:null;
 const run=ui.animateTransition(f.host,{nodes:[],edges:[],facts:[],documents:[{id:'notice',delay:580,duration:180}],stages:[]},{});
 assert.equal(f.calls.length,0);run.cancel();
});
test('paused interpretation describes an unaccepted result instead of active reading',()=>{
 const s=state({status:'deferred',phase:'deferred',run_id:'paused-run',deferral:{code:'paused',reason:'Paused'}});
 const html=ui.progressMarkup(s,[{kind:'work.started',payload:{run_id:'paused-run'}},{kind:'work.phase',payload:{phase:'interpreting'}}]);
 assert.match(html,/Interpretation not accepted/);assert.doesNotMatch(html,/Reading the evidence|aria-current="step"/);
});

test('an exhausted authoritative call allowance is visible before intake while packet saving remains available',async t=>{
 const savedStatus={enabled:true,provider_ready:true,limits:{autonomous_can_start:false,autonomous_reason:'call_limit_reached',effective_autonomous_max_provider_calls:24,provider_calls_used:24}},before=JSON.stringify(savedStatus),f=dom();
 const api=fakeApi({handle:async path=>path.endsWith('/status')?response(savedStatus):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();assert.match(f.host.innerHTML,/<h1[^>]*>Cases<\/h1>/);await newClaim(f);
 const message=f.host.querySelector('[data-au-service]').textContent;assert.match(message,/allowance does not permit more autonomous work/i);assert.match(message,/still save a new claim.*named deferral/i);assert.doesNotMatch(message,/Local evidence acquisition and document preparation are available/);
 assert.equal(f.submit.disabled,false);assert.notEqual(f.fields.title.disabled,true);assert.doesNotMatch(f.submit.textContent,/retry|saving/i);assert.equal(f.message.textContent,'');assert.equal(JSON.stringify(savedStatus),before);
 assert.ok(api.calls.every(call=>['/status','/claims','/knowledge'].some(path=>call.path.endsWith(path)) && (!call.init.method || call.init.method==='GET')));assert.ok(api.calls.filter(call=>call.path.endsWith('/knowledge')).length<=1);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('cost, pending and unknown allowance statuses keep distinct honest intake messages without disabling saving',async()=>{
 const cases=[
  {limits:{autonomous_can_start:false,autonomous_reason:'cost_limit_reached'},matches:[/cost allowance does not permit more autonomous work/i,/still save a new claim.*named deferral/i]},
  {limits:{autonomous_can_start:false,autonomous_reason:'provider_outcome_pending'},matches:[/pending|unconfirmed/i,/cannot start yet/i,/still save a new claim.*named deferral/i],excludes:/allowance does not permit|exhausted|spent/i},
  {limits:{autonomous_can_start:false,autonomous_reason:'provider_cost_bound_exceeded'},matches:[/provider cost.*bound/i,/still save a new claim.*named deferral/i],excludes:/allowance.*spent|call limit reached|cost limit reached/i},
  {limits:{autonomous_can_start:false,autonomous_reason:'unknown_future_condition',effective_autonomous_max_provider_calls:24,provider_calls_used:24},excludes:/allowance does not permit|exhausted|spent|call limit reached/i},
  {limits:{autonomous_can_start:false,autonomous_reason:'constructor'},matches:[/Autonomous inference is unavailable for new work/],excludes:/allowance does not permit|exhausted|spent|function|object Object/i},
  {limits:{autonomous_can_start:false,autonomous_reason:'__proto__'},matches:[/Autonomous inference is unavailable for new work/],excludes:/allowance does not permit|exhausted|spent|function|object Object/i},
  {limits:{autonomous_can_start:true,autonomous_reason:'call_limit_reached',effective_autonomous_max_provider_calls:24,provider_calls_used:24},matches:[/Local evidence acquisition and document preparation are available/],excludes:/allowance does not permit|exhausted|spent/i},
  {limits:{autonomous_reason:'call_limit_reached',effective_autonomous_max_provider_calls:24,provider_calls_used:24},matches:[/Local evidence acquisition and document preparation are available/],excludes:/allowance does not permit|exhausted|spent/i},
  {limits:{autonomous_can_start:'false',autonomous_reason:'cost_limit_reached'},matches:[/Local evidence acquisition and document preparation are available/],excludes:/allowance does not permit|exhausted|spent/i},
  {matches:[/Local evidence acquisition and document preparation are available/],excludes:/allowance does not permit|exhausted|spent/i}
 ];
 for(const example of cases) {
  const f=dom(),savedStatus={enabled:true,provider_ready:true,...('limits' in example?{limits:example.limits}:{})},api=fakeApi({handle:async path=>path.endsWith('/status')?response(savedStatus):null}),controller=ui.mount(f.container,{fetch:api.fetch});
  try { await settle();await newClaim(f);const message=f.host.querySelector('[data-au-service]').textContent;for(const pattern of example.matches||[])assert.match(message,pattern,JSON.stringify(savedStatus));if(example.excludes)assert.doesNotMatch(message,example.excludes,JSON.stringify(savedStatus));assert.equal(f.submit.disabled,false);assert.notEqual(f.fields.title.disabled,true);assert.equal(f.message.textContent,'');assert.ok(api.calls.every(call=>['/status','/claims','/knowledge'].some(path=>call.path.endsWith(path)) && (!call.init.method || call.init.method==='GET')));assert.ok(api.calls.filter(call=>call.path.endsWith('/knowledge')).length<=1);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0); }
  finally { controller.destroy(); }
 }
});

test('disabled service and unavailable provider keep precedence over allowance messages',async()=>{
 for(const [savedStatus,pattern,disabled]of [
  [{enabled:false,provider_ready:true,limits:{autonomous_can_start:false,autonomous_reason:'call_limit_reached'}},/^Autonomous work is disabled\.$/,true],
  [{enabled:true,provider_ready:false,limits:{autonomous_can_start:false,autonomous_reason:'call_limit_reached'}},/^Inference is unavailable\. New packets are saved with a named deferral\.$/,false]
 ]) {
  const f=dom(),api=fakeApi({handle:async path=>path.endsWith('/status')?response(savedStatus):null}),controller=ui.mount(f.container,{fetch:api.fetch});
  try { await settle();await newClaim(f);assert.match(f.host.querySelector('[data-au-service]').textContent,pattern);assert.equal(f.submit.disabled,disabled);assert.ok(api.calls.every(call=>['/status','/claims','/knowledge'].some(path=>call.path.endsWith(path)) && (!call.init.method || call.init.method==='GET')));assert.ok(api.calls.filter(call=>call.path.endsWith('/knowledge')).length<=1);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0); }
  finally { controller.destroy(); }
 }
});

test('accepted refresh keeps History Case details exact and closing its drawer returns to the replacement inspection control',async t=>{
 const f=dom();let saved=state(),trigger=control(f,'data-au-inspect','claim');trigger.textContent='Case details';
 f.host.contains=element=>element===trigger;f.host.querySelectorAll=selector=>selector==='[data-au-inspect]'?[trigger]:[];
 const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 assert.doesNotMatch(f.host.innerHTML,/data-au-inspect="claim"/);f.listeners.get('click')({target:control(f,'data-au-detail','activity')});assert.match(f.host.innerHTML,/data-au-inspect="claim"[^>]*>Case details/);
 trigger.focus();f.listeners.get('click')({target:trigger});assert.equal(f.recordDialog.open,true);assert.deepEqual(JSON.parse(f.recordPre.textContent),JSON.parse(JSON.stringify(ui.contextualRecord(saved,{},events(saved).events,'claim'))));
 const old=trigger;old.isConnected=false;trigger=control(f,'data-au-inspect','claim');trigger.textContent='Case details';
 saved=state({revision:4,state_sha256:hash('f')});await controller.refresh();assert.equal(f.recordDialog.open,true);const record=JSON.parse(f.recordPre.textContent);assert.deepEqual(record,JSON.parse(JSON.stringify(ui.contextualRecord(saved,{},events(saved).events,'claim'))));assert.deepEqual(record.state.graph.nodes[1],ui.contextualRecord(saved,{},[],'step','branch').node);
 f.recordDialog.close();assert.equal(f.container.ownerDocument.activeElement,trigger);assert.deepEqual(trigger.focusOptions,{preventScroll:true});assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('closed History keeps its snapshot quiet and reopening reads the newest exact case record',async t=>{
 const f=dom();let saved=state();
 const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 const trigger=control(f,'data-au-inspect','claim');trigger.textContent='Case details';
 f.listeners.get('click')({target:trigger});assert.equal(f.recordDialog.open,true);const original=f.recordPre.textContent;
 f.recordDialog.close();saved=state({revision:4,state_sha256:hash('f')});await controller.refresh();
 assert.equal(f.recordPre.textContent,original,'closed inspectors must not serialize new accepted state during presentation');
 f.listeners.get('click')({target:trigger});assert.equal(f.recordDialog.open,true);
 assert.deepEqual(JSON.parse(f.recordPre.textContent),JSON.parse(JSON.stringify(ui.contextualRecord(saved,{},events(saved).events,'claim'))));
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('global Knowledge History opens the full exact DTO including versions uses quarantine and public extensions',async t=>{
 const attack='<svg onload="alert(1)">',data={versions:[{knowledge_id:'procedure.one',version:2,knowledge_sha256:hash('a'),definition_sha256:hash('b'),qualification:{status:'qualified',checks:['no_case_values_or_files']},public_extension:{text:attack}}],uses:[{knowledge_id:'procedure.one',version:2,knowledge_sha256:hash('a'),definition_sha256:hash('b'),claim_id:'receiving-case',reason:'Exact recorded reuse reason.'}],quarantined:[{knowledge_id:'withheld',qualification:{status:'quarantined',reason:'Exact withheld reason.'}}],public_extension:{source:'Exact public catalog extension.'}},before=JSON.stringify(data),f=dom(),api=fakeApi({handle:async path=>path.endsWith('/knowledge')?response(data):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();navClick(f,'knowledge');await settle();
 assert.equal([...f.host.innerHTML.matchAll(/data-au-inspect="knowledge-index"/g)].length,1);assert.match(f.host.innerHTML,/data-au-inspect="knowledge-index"[^>]*>History/);assert.doesNotMatch(f.host.innerHTML,/data-au-inspect="(?:knowledge|use|quarantine|withheld-index)"/);
 f.listeners.get('click')({target:control(f,'data-au-inspect','knowledge-index')});assert.equal(f.recordDialog.open,true);assert.deepEqual(JSON.parse(f.recordPre.textContent),data);assert.doesNotMatch(f.recordBody.innerHTML,/<svg|onload=/);assert.equal(JSON.stringify(data),before);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('delayed claim collections preserve verified revisions without rejecting genuinely newer rows',async t=>{
 const other={claim_id:'claim-b',title:'Other saved claim',status:'resolved',revision:2,state_sha256:hash('b')};
 for(const example of [
  {name:'a delayed older current row',row:{claim_id:'claim-a',title:'Old collection title',status:'running',revision:3,state_sha256:hash('a')},expectedStatus:'More evidence needed'},
  {name:'a missing current row',row:null,expectedStatus:'More evidence needed'},
  {name:'a conflicting identity at the verified revision',row:{claim_id:'claim-a',title:'Conflicting collection title',status:'running',revision:4,state_sha256:hash('9')},expectedStatus:'More evidence needed'},
  {name:'a genuinely newer collection row',row:{claim_id:'claim-a',title:'Newer collection title',status:'queued',revision:5,state_sha256:hash('5')},expectedStatus:'Queued'}
 ])await t.test(example.name,async child=>{
  routingFixture(child,'#autonomous/claim/claim-a?detail=activity');const f=dom(),queue={innerHTML:''},query=f.container.querySelector;f.container.querySelector=selector=>selector==='[data-au-recent-claims]'?queue:query(selector);
  let saved=state(),projection={},finishList;const api=fakeApi({handle:async(path,init)=>path.endsWith('/claims')&&init.method!=='POST'?new Promise(resolve=>{finishList=resolve;}):path.endsWith('/claims/claim-a')?response({state:saved,projection:{claim_id:saved.claim_id,revision:saved.revision,state_sha256:saved.state_sha256,...projection}}):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});child.after(()=>controller.destroy());await waitFor(()=>f.host.innerHTML.includes('data-au-revision="3"')&&Boolean(finishList));
  saved=state({revision:4,state_sha256:hash('f'),status:'deferred',outcome:{status:'deferred',reason:'Recorded evidence needed.',missing_evidence:[{document_type:'notice',label:'Notice receipt'}]}});await controller.refresh();assert.match(queue.innerHTML,/More evidence needed/);assert.match(f.host.innerHTML,/data-au-revision="4"/);
  finishList(response({claims:[other,...(example.row?[example.row]:[])]}));await waitFor(()=>queue.innerHTML.includes('Other saved claim'));
  const row=queue.innerHTML.match(/<button[^>]*data-au-claim="claim-a"[\s\S]*?<\/button>/)?.[0];assert.ok(row,'the current verified claim remains reachable');assert.ok(row.includes(example.expectedStatus),row);assert.match(row,/data-au-claim="claim-a"/);assert.match(f.host.innerHTML,/data-au-revision="4"/);assert.match(f.host.innerHTML,/Recorded evidence needed/);assert.doesNotMatch(queue.innerHTML,/Old collection title|Conflicting collection title/);
  if(example.row)assert.ok(queue.innerHTML.indexOf('Other saved claim')<queue.innerHTML.indexOf('data-au-claim="claim-a"'),'the API collection order is retained');
  if(example.row?.revision===5)projection={node_capabilities:{branch:{authorized:false,id:null,reason:'Projection changed after newer collection row.'}}};
  await controller.refresh();assert.ok(queue.innerHTML.includes(example.expectedStatus));
  if(example.row?.revision===5){f.listeners.get('click')({target:control(f,'data-au-inspect','claim')});const inspected=JSON.parse(f.recordPre.textContent);assert.equal(inspected.projection.node_capabilities.branch.reason,'Projection changed after newer collection row.');assert.deepEqual(inspected.state,saved);assert.match(f.host.innerHTML,/data-au-revision="4"/);assert.match(queue.innerHTML,/Newer collection title/);}
  assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
 });
});

test('idle intake labels distinguish saving a claim from available or unknown autonomous work',async()=>{
 const exhausted={enabled:true,provider_ready:true,limits:{autonomous_can_start:false,autonomous_reason:'call_limit_reached',effective_autonomous_max_provider_calls:24,provider_calls_used:24}};
 for(const [savedStatus,label,disabled]of [
  [exhausted,/^Save claim$/,false],
  [{enabled:true,provider_ready:false,limits:{}},/^Save claim$/,false],
  [{enabled:true,provider_ready:true,limits:{autonomous_can_start:false,autonomous_reason:'provider_outcome_pending'}},/^Save claim$/,false],
  [{enabled:true,provider_ready:true,limits:{autonomous_can_start:false,autonomous_reason:'unknown_future_condition'}},/^Save claim$/,false],
  [{enabled:true,provider_ready:true,limits:{autonomous_can_start:true}},/^Start autonomous work/,false],
  [{enabled:true,provider_ready:true},/^Start autonomous work/,false],
  [{enabled:true,provider_ready:true,limits:{autonomous_reason:'call_limit_reached'}},/^Start autonomous work/,false],
  [{enabled:true,limits:{}},/^Start autonomous work/,false],
  [{enabled:false,provider_ready:true,limits:{autonomous_can_start:false,autonomous_reason:'call_limit_reached'}},/^Start autonomous work/,true]
 ]) {
  const f=nativeFixture(),api=fakeApi({handle:async path=>path.endsWith('/status')?response(savedStatus):null}),controller=ui.mount(f.container,{fetch:api.fetch});
  try { await settle();await newClaim(f);const submit=f.intake.querySelector('button[type="submit"]');assert.match(submit.textContent,label,JSON.stringify(savedStatus));assert.equal(submit.disabled,disabled);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0); }
  finally { controller.destroy(); }
 }
});

test('an unresolved service status keeps intake disabled until authoritative readiness arrives',async t=>{
 const f=nativeFixture(),held=[];const api=fakeApi({handle:async path=>path.endsWith('/status')?new Promise(resolve=>held.push(resolve)):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{for(const resolve of held)resolve(response({enabled:true,provider_ready:true,limits:{}}));controller.destroy();});await settle();await newClaim(f);
 assert.equal(held.length,1,'navigation shares the exact unresolved status GET');assert.equal(api.calls.filter(call=>call.path.endsWith('/status')).length,1);assert.match(f.intake.querySelector('button[type="submit"]').textContent,/^Start autonomous work/);assert.equal(f.intake.querySelector('button[type="submit"]').disabled,true);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
 for(const resolve of held)resolve(response({enabled:true,provider_ready:true,limits:{}}));await settle();assert.match(f.intake.querySelector('button[type="submit"]').textContent,/^Start autonomous work/);
});

test('late status reads preserve Saving and exact Retry labels while retaining the same intake files and draft',async t=>{
 const f=nativeFixture(),available={enabled:true,provider_ready:true,limits:{}},unavailable={enabled:true,provider_ready:true,limits:{autonomous_can_start:false,autonomous_reason:'call_limit_reached',effective_autonomous_max_provider_calls:24,provider_calls_used:24}};let statusReads=0,finishStatus,rejectPost;
 const api=fakeApi({handle:async(path,init)=>{if(path.endsWith('/status')){statusReads++;return statusReads===2||statusReads===4?new Promise(resolve=>{finishStatus=resolve;}):response(available);}if(init.method==='POST')return new Promise((_resolve,reject)=>{rejectPost=reject;});}}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{finishStatus?.(response(unavailable));rejectPost?.(new Error('Unconfirmed intake'));controller.destroy();});await settle();await newClaim(f);
 const form=f.intake,list=[fileFixture()],submit=form.querySelector('button[type="submit"]');form.elements.title.value='Retained original draft';form.elements.message.value='Original source message';form.elements.files.files=list;
 const submission=f.listeners.get('submit')({target:form,preventDefault(){}});await waitFor(()=>Boolean(rejectPost));assert.equal(submit.textContent,'Saving…');finishStatus(response(unavailable));await settle();assert.equal(submit.textContent,'Saving…');assert.equal(submit.disabled,true);
 rejectPost(new Error('Intake response lost'));await submission;assert.equal(submit.textContent,'Retry same request');assert.equal(submit.disabled,false);assert.equal(form.elements.title.disabled,true);
 navClick(f,'work');await settle();await newClaim(f);assert.equal(statusReads,4);assert.equal(f.intake,form);assert.equal(submit.textContent,'Retry same request');finishStatus(response(unavailable));await settle();
 assert.equal(submit.textContent,'Retry same request');assert.equal(submit.disabled,false);assert.equal(form.elements.files.files,list);assert.equal(form.elements.title.value,'Retained original draft');assert.equal(form.elements.message.value,'Original source message');assert.equal(api.calls.filter(call=>call.init.method==='POST').length,1);
});

test('a late unavailable status cannot replace Saving while native source bytes are still being prepared',async t=>{
 const f=nativeFixture(),available={enabled:true,provider_ready:true,limits:{}},unavailable={enabled:true,provider_ready:false,limits:{}},bytes=Buffer.from('Original retained bytes');let statusReads=0,finishStatus,finishBytes;
 const api=fakeApi({handle:async(path,init)=>{if(path.endsWith('/status'))return ++statusReads===2?new Promise(resolve=>{finishStatus=resolve;}):response(available);if(init.method==='POST')throw new Error('Unconfirmed packet response');}}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{finishStatus?.(response(unavailable));finishBytes?.(bytes);controller.destroy();});await settle();await newClaim(f);
 const form=f.intake,submit=form.querySelector('button[type="submit"]'),list=[{...fileFixture(),arrayBuffer:()=>new Promise(resolve=>{finishBytes=resolve;})}];form.elements.title.value='Original claim';form.elements.message.value='Original source';form.elements.files.files=list;
 const submission=f.listeners.get('submit')({target:form,preventDefault(){}});await waitFor(()=>Boolean(finishBytes));assert.equal(submit.textContent,'Saving…');assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
 finishStatus(response(unavailable));await settle();assert.match(f.host.querySelector('[data-au-service]').textContent,/Inference is unavailable/);assert.equal(submit.textContent,'Saving…');assert.equal(submit.disabled,true);
 finishBytes(bytes);await submission;assert.equal(submit.textContent,'Retry same request');assert.equal(form.elements.files.files,list);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,1);
});

test('returning to intake updates its idle label and local validation restores that label without replacing draft files',async t=>{
 let now=Date.now();t.mock.method(Date,'now',()=>now);
 const f=nativeFixture();let savedStatus={enabled:true,provider_ready:true,limits:{}},finishStatus,statusReads=0,holdNext=false;
 const api=fakeApi({handle:async path=>{if(!path.endsWith('/status'))return null;statusReads++;if(holdNext){holdNext=false;return new Promise(resolve=>{finishStatus=resolve;});}return response(savedStatus);}}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{finishStatus?.(response(savedStatus));controller.destroy();});await settle();await newClaim(f);
 const form=f.intake,list=Array.from({length:21},()=>fileFixture()),submit=form.querySelector('button[type="submit"]');form.elements.title.value='Typed original draft';form.elements.message.value='Retained original message';form.elements.files.files=list;
 await f.listeners.get('submit')({target:form,preventDefault(){}});assert.match(form.querySelector('.au-form-status').textContent,/at most 20/);assert.match(submit.textContent,/^Start autonomous work/);assert.equal(form.elements.title.disabled,false);
 savedStatus={enabled:true,provider_ready:false,limits:{}};now+=10001;navClick(f,'work');await settle();holdNext=true;await newClaim(f);assert.equal(f.intake,form);assert.equal(submit.textContent,'Save claim','the cached unavailable status applies before the fresh status response');assert.equal(form.elements.files.files,list);assert.equal(form.elements.title.value,'Typed original draft');assert.equal(form.elements.message.value,'Retained original message');
 finishStatus(response(savedStatus));await settle();await f.listeners.get('submit')({target:form,preventDefault(){}});assert.equal(submit.textContent,'Save claim');assert.equal(submit.disabled,false);assert.equal(form.elements.title.disabled,false);assert.equal(form.elements.files.files,list);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
 savedStatus={enabled:true,provider_ready:true,limits:{}};now+=10001;navClick(f,'work');await settle();await newClaim(f);assert.equal(f.intake,form);assert.match(submit.textContent,/^Start autonomous work/);assert.equal(form.elements.files.files,list);assert.equal(statusReads,6);
});

const operationContract='casepath.operations-stream/1.0.0';
function operationFixture() {
 const sourceText='Before 😀\r\nA tenant reports a cold home. Zürich.',descriptor={artifact_id:'source',sha256:sha('original immutable bytes'),file_name:'source.txt'};
 const baseline=state({source_descriptors:[descriptor],run_id:'reference-run',revision:3,last_event_sha256:sha('event-3')});delete baseline.state_sha256;baseline.state_sha256=sha(ui.canonicalJSON(baseline));
 const head={...baseline,revision:4,last_event_sha256:sha('event-4'),status:'deferred',outcome:{assessment_status:'complete'}};delete head.state_sha256;head.state_sha256=sha(ui.canonicalJSON(head));
 const start={claim_id:baseline.claim_id,from_seq:3,run_id:baseline.run_id,profile_id:'synthetic-nine-v2',profile_sha256:sha('profile')},binding={contract:operationContract,type:'binding',instrumentation_id:'casepath.reference-operations/1.1.0',...start,mode:'historical_recomputed',newly_recomputed:true,source_roster_sha256:sha('roster'),rule_set_sha256:sha('rules'),input_sha256:sha('input'),current_revision:4,current_state_sha256:head.state_sha256,current_event_sha256:head.last_event_sha256};
 const journal=Array.from({length:4},(_,index)=>({claim_id:baseline.claim_id,seq:index+1,revision:index+1,kind:index===2?'process.prepared':'work.phase',event_sha256:sha(`event-${index+1}`),previous_event_sha256:index?sha(`event-${index}`):null,state_sha256:index===2?baseline.state_sha256:index===3?head.state_sha256:sha(`state-${index+1}`)}));
 const trace={binding,rows:[],sources:new Map(),bytes:0,pinnedJournal:journal,journal:[],transportState:null};
 const seal=(kind,object,result,source)=>{const input={source_artifact_id:descriptor.artifact_id},frame={contract:operationContract,type:'operation',seq:trace.rows.length+1,id:`real-${trace.rows.length+1}`,kind,object,input,result,cause_ids:trace.rows.length?[trace.rows.at(-1).id]:[],previous_operation_sha256:trace.rows.at(-1)?.operation_sha256||null,input_sha256:sha(ui.canonicalJSON(input)),result_sha256:sha(ui.canonicalJSON(result)),...source?{source}:{}};const material={...frame};delete material.contract;delete material.type;return {...frame,operation_sha256:sha(ui.canonicalJSON(material))};};
 return {sourceText,descriptor,baseline,head,start,binding,journal,trace,seal};
}
function operationOpeningFixture(id=ui.REFERENCE_DEMO_CASES[0].claim_id) {
 const run='opening-reference-run',profile=sha('opening-profile'),roster=sha('opening-roster');
 const catalog={nodes:[{node_id:'start',label:'Read the received message'},{node_id:'branch',label:'Assess the received notice'}],transitions:[{edge_id:'next',source_node_id:'start',target_node_id:'branch'}],documents:[{document_type:'notice',label:'Received notice',required_at_node_ids:['branch']}]};
 const provenance={mode:'deterministic_reference',synthetic:true,as_of:'2025-02-21',profile_id:'synthetic-nine-v2',profile_sha256:profile,rule_set_sha256:sha('opening-rules')};
 const opening=state({claim_id:id,title:'Actual original opening',revision:0,state_sha256:sha('opening-state'),last_event_sha256:null,mode:'unprocessed',phase:'not_run',graph:null,evaluation:null,facts:[],obligations:[],actions:[],status:'not_started'});
 const head=state({claim_id:id,title:opening.title,revision:4,state_sha256:sha('opening-head'),last_event_sha256:sha('opening-event-4'),run_id:run,source_roster_sha256:roster,policy_id:'casepath.bounded-reference-assessment/1.0.0',status:'deferred',outcome:{assessment_status:'complete',summary:'The later accepted outcome must stay hidden.',reference_provenance:provenance},graph:{claim_id:id,family:'opening_family',graph_sha256:sha('opening-graph'),nodes:catalog.nodes.map(node=>({...node,document_types:node.node_id==='branch'?['notice']:[]})),edges:catalog.transitions,document_catalog:catalog.documents},semantic_contexts:{[run]:{claim_id:id,execution_mode:'deterministic_reference',reference_provenance:provenance,sources:[{artifact_id:'original'}],rule_packs:[{family:'opening_family',template_sha256:sha('opening-pack'),process_catalog:catalog}],compatible_knowledge:[]}},knowledge_uses:[]});
 opening.original_binding={claim_id:id,source_map:opening.source_descriptors.map(row=>({artifact_id:row.artifact_id,sha256:row.sha256}))};
 opening.source_descriptors=opening.source_descriptors.map(row=>({...row,claim_id:id}));head.source_descriptors=structuredClone(opening.source_descriptors);head.original_binding=structuredClone(opening.original_binding);head.contract='casepath.autonomous-claim/1.0.0';delete head.state_sha256;head.state_sha256=sha(ui.canonicalJSON(head));
 const journal=Array.from({length:4},(_,index)=>({contract:'casepath.autonomous-event/1.0.0',claim_id:id,seq:index+1,sequence:index+1,revision:index+1,kind:index===2?'process.prepared':'work.phase',event_sha256:sha(`opening-event-${index+1}`),previous_event_sha256:index?sha(`opening-event-${index}`):null,state_sha256:index===3?head.state_sha256:sha(`opening-state-${index+1}`)}));
 for(const event of journal)event.resulting_state_sha256=event.state_sha256;
 const start={contract:'casepath.reference-replay-start/1.0.0',claim_id:id,from_seq:3,state_sha256:journal[2].state_sha256,event_sha256:journal[2].event_sha256,run_id:run,profile_id:'synthetic-nine-v2',profile_sha256:profile,source_artifact_ids:['original']};
 const envelope=(saved,through)=>({state:saved,projection:{claim_id:id,revision:through,state_sha256:saved.state_sha256},events:journal.slice(0,through),cursor_sha256:saved.last_event_sha256,mode:'replay',replay_only:true,through_seq:through,current_revision:4,current_state_sha256:head.state_sha256,current_event_sha256:head.last_event_sha256,replay_start:start,provenance:{source_roster_sha256:saved.source_roster_sha256,policy_id:saved.policy_id,run_id:saved.run_id,event_sha256:saved.last_event_sha256}});
 const zero=envelope(opening,0),replay=envelope(head,4),snapshot={state:head,projection:replay.projection,events:journal,cursor_sha256:head.last_event_sha256,mode:'saved',current_revision:4,current_state_sha256:head.state_sha256,current_event_sha256:head.last_event_sha256,replay_start:start};
 const binding={...start,contract:operationContract,type:'binding',instrumentation_id:'casepath.reference-operations/1.1.0',mode:'historical_recomputed',newly_recomputed:true,source_roster_sha256:roster,rule_set_sha256:provenance.rule_set_sha256,input_sha256:sha('opening-input'),current_revision:4,current_state_sha256:head.state_sha256,current_event_sha256:head.last_event_sha256};
 return {id,head,zero,replay,snapshot,binding};
}
const deferredRead=()=>{let resolve;const promise=new Promise(done=>{resolve=done;});return {promise,resolve};};
function operationOpeningDOM() {
 const f=dom(),attributes=new Map(),query=f.host.querySelector;
 const transport={textContent:'Pause',hasAttribute:key=>['data-au-demo-stop','data-au-demo-resume'].includes(key)&&f.host.innerHTML.includes(' '+key),closest(){return this;},removeAttribute(key){f.host.innerHTML=f.host.innerHTML.replace(' '+key,'');},setAttribute(key){f.host.innerHTML=f.host.innerHTML.replace('<div class="au-stage-transport"><button','<div class="au-stage-transport"><button '+key);}};
 f.host.querySelector=key=>key==='[data-au-release-opening]'&&f.host.innerHTML.includes('data-au-release-opening=')?{}:key==='[data-au-release-plan]'&&f.host.innerHTML.includes('data-au-release-plan=')?{remove(){f.host.innerHTML=f.host.innerHTML.replace(/<section[^>]*data-au-release-plan=[\s\S]*?<\/section>/,'');}}:['[data-au-demo-stop]','[data-au-demo-resume]'].includes(key)&&transport.hasAttribute(key.slice(1,-1))?transport:query(key);
 f.host.setAttribute=(key,value)=>attributes.set(key,String(value));f.host.getAttribute=key=>attributes.get(key);f.host.removeAttribute=key=>attributes.delete(key);return {...f,attributes};
}
function pendingOperationResponse(binding) {
 return {ok:true,status:200,body:new ReadableStream({start(controller){controller.enqueue(new TextEncoder().encode(JSON.stringify(binding)+'\n'));},cancel(){}})};
}

function recordedPacketFixture(native=operationOpeningFixture(),bodies=null) {
 const raw=bodies||[JSON.stringify(native.zero),JSON.stringify(native.snapshot),JSON.stringify(native.binding)+'\n'];
 const claim={claim_id:native.id,head:{revision:native.head.revision,state_sha256:native.head.state_sha256,event_sha256:native.head.last_event_sha256}};
 for(const [index,kind]of ['opening','head_snapshot','operations'].entries())claim[kind]={bytes:Buffer.byteLength(raw[index]),sha256:sha(raw[index]),root:index};
 const packet={contract:'casepath.recorded-session-packet/1.0.0',deployment_commit:null,history_kind:'native_fixture',claims:[claim],fragments:raw};
 const seal=value=>{const bytes=Buffer.from(JSON.stringify(value));return{bytes,descriptor:{url:'/recorded-prototype.json',bytes:bytes.length,sha256:sha(bytes),deployment_commit:value.deployment_commit,history_kind:value.history_kind}};};
 return{native,packet,raw,seal,...seal(packet)};
}

function delayedPacketHash(t,bytes) {
 const subtle=globalThis.crypto.subtle,original=subtle.digest,started=deferredRead(),release=deferredRead();
 subtle.digest=function(algorithm,input){if(Buffer.from(input).equals(bytes)){started.resolve();return release.promise.then(()=>original.call(subtle,algorithm,input));}return original.call(subtle,algorithm,input);};
 let restored=false;const restore=()=>{if(!restored){restored=true;subtle.digest=original;release.resolve();}};t.after(restore);return{started:started.promise,release:()=>release.resolve(),restore};
}

test('complete acquired packet may finish local SHA inside the original300ms immediate-click choice',async t=>{
 const f=operationOpeningDOM(),packet=recordedPacketFixture(),hash=delayedPacketHash(t,packet.bytes),opening=deferredRead(),snapshot=deferredRead(),timers=[];let assetSignal,liveSignal;
 const originalTimeout=globalThis.setTimeout;globalThis.setTimeout=(fn,ms,...args)=>{if(ms===300)timers.push(Date.now());return originalTimeout(fn,ms,...args);};t.after(()=>{globalThis.setTimeout=originalTimeout;});
 const api=fakeApi({handle:async(path,init)=>path.endsWith('/recorded-prototype.json')?(assetSignal=init.signal,new Response(packet.bytes)):path.endsWith('/replay?through_seq=0')?opening.promise:path.endsWith('/snapshot?after=0')?snapshot.promise:path.includes('/operations?')?(liveSignal=init.signal,pendingOperationResponse(packet.native.binding)):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});t.after(()=>{controller.destroy();opening.resolve(response(packet.native.zero));snapshot.resolve(response(packet.native.snapshot));});await hash.started;assert.match(f.host.innerHTML,/Cases|No .*claims|All cases/i,'Cases renders while acquired bytes await local verification');
 const started=Date.now(),selecting=controller.showDemonstration();await settle();assert.equal(assetSignal.aborted,false,'exact acquired bytes remain eligible; no network is being awaited');assert.equal(timers.length,1,'the choice deadline starts before the pending asset SHA finishes');assert.ok(api.calls.some(row=>row.path.includes('/operations?mode=live')),'Live reads run concurrently with local packet verification');
 const pause=f.host.querySelector('[data-au-demo-stop]');f.listeners.get('click')({target:pause});const focus={};f.container.ownerDocument.activeElement=focus;
 await new Promise(resolve=>originalTimeout(resolve,150));hash.release();await selecting;assert.equal(timers.length,1,'verification cannot restart another300ms window');assert.ok(Date.now()-started<700);assert.equal(await controller.recordedPacketReady,true);assert.equal(liveSignal.aborted,true);assert.ok(f.host.querySelector('[data-au-demo-resume]'));assert.equal(f.container.ownerDocument.activeElement,focus);assert.doesNotMatch(f.host.innerHTML,/data-au-revision=|data-au-stage-fact=|Live rules-based check/);
});

test('complete acquired packet missing the300ms choice cannot paint or splice into later verified Live',async t=>{
 const f=operationOpeningDOM(),packet=recordedPacketFixture(),hash=delayedPacketHash(t,packet.bytes),opening=deferredRead();
 const api=fakeApi({handle:async path=>path.endsWith('/recorded-prototype.json')?new Response(packet.bytes):path.endsWith('/replay?through_seq=0')?opening.promise:path.endsWith('/snapshot?after=0')?response(packet.native.snapshot):path.includes('/operations?')?pendingOperationResponse(packet.native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});t.after(()=>{controller.destroy();opening.resolve(response(packet.native.zero));});await hash.started;const selecting=controller.showDemonstration();await new Promise(resolve=>setTimeout(resolve,350));opening.resolve(response(packet.native.zero));await selecting;await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='historical_recomputed');const before=f.host.innerHTML;
 hash.release();await controller.recordedPacketReady;await settle();await settle();assert.equal(f.host.innerHTML,before,'late local verification cannot join the completed choice');assert.match(f.host.innerHTML,/Live rules-based check/);assert.doesNotMatch(f.host.innerHTML,/Recorded replay/);assert.equal(api.calls.filter(row=>row.path.includes(`/claims/${packet.native.id}/operations?`)).length,1);
});

test('ready verified Live wins while a completely acquired packet still awaits local SHA',async t=>{
 const f=operationOpeningDOM(),packet=recordedPacketFixture(),hash=delayedPacketHash(t,packet.bytes);
 const api=fakeApi({handle:async path=>path.endsWith('/recorded-prototype.json')?new Response(packet.bytes):path.endsWith('/replay?through_seq=0')?response(packet.native.zero):path.endsWith('/snapshot?after=0')?response(packet.native.snapshot):path.includes('/operations?')?pendingOperationResponse(packet.native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});t.after(()=>controller.destroy());await hash.started;await controller.showDemonstration();await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='historical_recomputed');const before=f.host.innerHTML;hash.release();await controller.recordedPacketReady;await settle();assert.equal(f.host.innerHTML,before);assert.match(f.host.innerHTML,/Live rules-based check/);assert.doesNotMatch(f.host.innerHTML,/Recorded replay/);
});

test('navigation and hidden ownership cancel acquired packet verification without late Recorded paint',async t=>{
 for(const hide of [false,true]){
  const f=operationOpeningDOM(),packet=recordedPacketFixture(),hash=delayedPacketHash(t,packet.bytes),opening=deferredRead(),listeners=new Map();let assetSignal;f.container.ownerDocument.addEventListener=(name,fn)=>listeners.set(name,fn);
  const api=fakeApi({handle:async(path,init)=>path.endsWith('/recorded-prototype.json')?(assetSignal=init.signal,new Response(packet.bytes)):path.endsWith('/replay?through_seq=0')?opening.promise:path.endsWith('/snapshot?after=0')?response(packet.native.snapshot):path.includes('/operations?')?pendingOperationResponse(packet.native.binding):null});
  const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});await hash.started;const selecting=controller.showDemonstration();
  if(hide){f.container.ownerDocument.hidden=true;listeners.get('visibilitychange')();}else await controller.showKnowledge();const before=f.host.innerHTML;assert.equal(assetSignal.aborted,true);hash.release();assert.equal(await controller.recordedPacketReady,false);if(hide)await new Promise(resolve=>setTimeout(resolve,350));else{opening.resolve(response(packet.native.zero));await selecting;}await settle();assert.equal(f.host.innerHTML,before,'packet verification cannot repaint while cancelled; unrelated Live opening remains held');assert.doesNotMatch(f.host.innerHTML,/Recorded replay/);controller.destroy();opening.resolve(response(packet.native.zero));await selecting;hash.restore();
 }
});

test('recorded packet selected codec preserves exact UTF8 numeric spellings escapes and CRLF without expanding other claims',async()=>{
 const fixture=recordedPacketFixture(undefined,['{"value":-0,"other":0.0,"name":"\\u00e9"} \r\n','{"x":1.00e+3,"n":0e0}','{"v":"😀"}\r\n{"q":"\\\\u00e9"}\n']);
 let root=fixture.packet.fragments.push('x')-1;for(let i=0;i<40;i++)root=fixture.packet.fragments.push([root,root])-1;
 const other=structuredClone(fixture.packet.claims[0]);other.claim_id=ui.REFERENCE_DEMO_CASES[1].claim_id;for(const kind of ['opening','head_snapshot','operations'])other[kind]={bytes:1,sha256:sha('x'),root};fixture.packet.claims.push(other);
 const asset=fixture.seal(fixture.packet),packet=await ui.checkedRecordedPacket(asset.bytes,asset.descriptor,true),decoded=await ui.decodeRecordedSession(packet,fixture.native.id);
 assert.equal(Object.is(decoded.opening.value,-0),true);assert.equal(decoded.opening.name,'é');
 for(const [index,kind]of ['opening','head_snapshot','operations'].entries())assert.equal(Buffer.from(decoded.raw[kind]).toString(),fixture.raw[index]);
 await assert.rejects(ui.decodeRecordedSession(packet,other.claim_id),/bound/);assert.equal(Object.isFrozen(packet.fragments),true);
});

test('recorded packet codec rejects unbound assets invalid publication DAG roots expansion and raw hashes',async()=>{
 const f=recordedPacketFixture();await assert.rejects(ui.checkedRecordedPacket(f.bytes,f.descriptor),/contract|publication/);await assert.rejects(ui.checkedRecordedPacket(f.bytes,{...f.descriptor,sha256:sha('other')},true),/asset identity/);await assert.rejects(ui.decodeRecordedSession(f.packet,f.native.id),/not verified/);
 for(const change of [copy=>copy.fragments[0]=[0],copy=>copy.fragments[0]=[1],copy=>copy.claims[0].opening.root=999,copy=>copy.claims.push(structuredClone(copy.claims[0])),copy=>copy.claims[0].operations.bytes=25*1024*1024]){const copy=structuredClone(f.packet);change(copy);const asset=f.seal(copy);await assert.rejects(ui.checkedRecordedPacket(asset.bytes,asset.descriptor,true));}
 const copy=structuredClone(f.packet);copy.claims[0].operations.sha256=sha('different trace');const asset=f.seal(copy),packet=await ui.checkedRecordedPacket(asset.bytes,asset.descriptor,true);await assert.rejects(ui.decodeRecordedSession(packet,f.native.id),/exact byte/);
 const signal=new AbortController();signal.abort();await assert.rejects(ui.decodeRecordedSession(await ui.checkedRecordedPacket(f.bytes,f.descriptor,true),f.native.id,signal.signal),/cancelled/);
});

test('ready recorded packet wins the bounded opening choice and late live replies cannot replace the whole Recorded session',async t=>{
 const routing=routingFixture(t),f=operationOpeningDOM(),packet=recordedPacketFixture(),opening=deferredRead(),snapshot=deferredRead(),incompleteFallback=deferredRead();let liveSignal;
 const api=fakeApi({handle:async(path,init)=>path.endsWith('/recorded-prototype.json')?new Response(packet.bytes):path.endsWith('/replay?through_seq=0')?opening.promise:path.endsWith('/snapshot?after=0')?snapshot.promise:path.endsWith('/replay?through_seq=4')?incompleteFallback.promise:path.includes('/operations?')?(liveSignal=init.signal,pendingOperationResponse(packet.native.binding)):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});t.after(()=>{controller.destroy();incompleteFallback.resolve(response(packet.native.replay));opening.resolve(response(packet.native.zero));snapshot.resolve(response(packet.native.snapshot));});assert.equal(await controller.recordedPacketReady,true);const writes=[];let markup=f.host.innerHTML;Object.defineProperty(f.host,'innerHTML',{get:()=>markup,set:value=>{markup=value;writes.push(value);},configurable:true});const selecting=controller.showDemonstration();
 assert.match(f.host.innerHTML,/Opening investigation/);assert.doesNotMatch(f.host.innerHTML,/Live rules-based check|data-au-revision=/);await selecting;await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='recorded_operations');
 assert.ok(writes.every(html=>!html.includes('Live rules-based check')),'every opening/playback render retains whole-session Recorded identity');assert.match(f.host.innerHTML,/Recorded replay/);assert.doesNotMatch(f.host.innerHTML,/Live rules-based check|The later accepted outcome|data-au-stage-fact=/);assert.match(routing.hash,/operations=recorded/);assert.equal(liveSignal.aborted,true);
 await waitFor(()=>api.calls.some(row=>row.path.endsWith('/replay?through_seq=4')));const before=f.host.innerHTML;opening.resolve(response(packet.native.zero));snapshot.resolve(response(packet.native.snapshot));await settle();await settle();assert.equal(f.host.innerHTML,before,'late live responses cannot take over an admitted Recorded session');assert.equal(api.calls.filter(row=>row.path.includes(`/claims/${packet.native.id}/operations?`)).length,1,'recorded body uses packet bytes without another API trace');
});

test('independently verified live opening wins before300ms and never consumes available recorded packet frames',async t=>{
 const f=operationOpeningDOM(),packet=recordedPacketFixture();
 const api=fakeApi({handle:async path=>path.endsWith('/recorded-prototype.json')?new Response(packet.bytes):path.endsWith('/replay?through_seq=0')?response(packet.native.zero):path.endsWith('/snapshot?after=0')?response(packet.native.snapshot):path.includes('/operations?')?pendingOperationResponse(packet.native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});t.after(()=>controller.destroy());assert.equal(await controller.recordedPacketReady,true);const started=Date.now();await controller.showDemonstration();await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='historical_recomputed');assert.ok(Date.now()-started<300);assert.match(f.host.innerHTML,/Live rules-based check/);assert.doesNotMatch(f.host.innerHTML,/Recorded replay/);
});

test('unfinished recorded asset never delays Cases or selected live work and cannot join a later opening',async t=>{
 const f=operationOpeningDOM(),packet=recordedPacketFixture(),asset=deferredRead(),opening=deferredRead();let assetSignal;
 const api=fakeApi({handle:async(path,init)=>path.endsWith('/recorded-prototype.json')?(assetSignal=init.signal,asset.promise):path.endsWith('/replay?through_seq=0')?opening.promise:path.endsWith('/snapshot?after=0')?response(packet.native.snapshot):path.includes('/operations?')?pendingOperationResponse(packet.native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});t.after(()=>{controller.destroy();asset.resolve(new Response(packet.bytes));opening.resolve(response(packet.native.zero));});await settle();await new Promise(resolve=>setTimeout(resolve,5));assert.match(f.host.innerHTML,/Cases|No .*claims|All cases/i);const selecting=controller.showDemonstration();await settle();assert.equal(assetSignal.aborted,false);assert.match(f.host.innerHTML,/Opening investigation/);
 await new Promise(resolve=>setTimeout(resolve,350));asset.resolve(new Response(packet.bytes));assert.equal(await controller.recordedPacketReady,true);opening.resolve(response(packet.native.zero));await selecting;await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='historical_recomputed');assert.doesNotMatch(f.host.innerHTML,/Recorded replay/);
});

test('unusable recorded packet retains the existing live503 to recorded endpoint fallback',async t=>{
 const f=operationOpeningDOM(),packet=recordedPacketFixture();packet.packet.claims[0].head.state_sha256=sha('different recorded head');const asset=packet.seal(packet.packet);
 const api=fakeApi({handle:async path=>path.endsWith('/recorded-prototype.json')?new Response(asset.bytes):path.endsWith('/replay?through_seq=0')?response(packet.native.zero):path.endsWith('/snapshot?after=0')?response(packet.native.snapshot):path.includes('/operations?mode=live')?response({detail:'Live not available'},503):path.includes('/operations?mode=recorded')?pendingOperationResponse(packet.native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:asset.descriptor,allowNativeRecordedPacket:true});t.after(()=>controller.destroy());assert.equal(await controller.recordedPacketReady,true);await controller.showDemonstration();await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='recorded_operations');
 assert.equal(api.calls.filter(row=>row.path.includes(`/claims/${packet.native.id}/operations?mode=live`)).length,1);assert.equal(api.calls.filter(row=>row.path.includes(`/claims/${packet.native.id}/operations?mode=recorded`)).length,1);assert.match(f.host.innerHTML,/Recorded replay/);assert.doesNotMatch(f.host.innerHTML,/The later accepted outcome|data-au-stage-fact=/);
});

test('explicit Recorded route uses whole packet identity and retires release provenance before accepted opening paint',async t=>{
 const routing=routingFixture(t),f=operationOpeningDOM(),packet=recordedPacketFixture(),opening=deferredRead(),snapshot=deferredRead();
 const api=fakeApi({handle:async path=>path.endsWith('/recorded-prototype.json')?new Response(packet.bytes):path.endsWith('/replay?through_seq=0')?opening.promise:path.endsWith('/snapshot?after=0')?snapshot.promise:path.includes('/operations?')?pendingOperationResponse(packet.native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});t.after(()=>{controller.destroy();opening.resolve(response(packet.native.zero));snapshot.resolve(response(packet.native.snapshot));});assert.equal(await controller.recordedPacketReady,true);const before=api.calls.length;await controller.showDemonstration(true,'reference','recorded');
 assert.equal(api.calls.slice(before).length,0,'explicit Recorded admission uses no selected API reads; this authored binding-only fixture later takes its expected incomplete-stream fallback');await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='recorded_operations');assert.equal(api.calls.filter(row=>row.path.includes('/operations?mode=live')).length,0);assert.match(routing.hash,/operations=recorded/);assert.match(f.host.innerHTML,/Recorded replay/);assert.doesNotMatch(f.host.innerHTML,/data-au-release-plan=/);assert.match(f.host.innerHTML,/data-au-planned-process=/);
});

test('idle recorded packet owner cancels on hidden or leaving Cases while an available asset remains reusable',async t=>{
 for(const hide of [false,true]){
  const f=operationOpeningDOM(),packet=recordedPacketFixture(),asset=deferredRead();let signal;const documentListeners=new Map();f.container.ownerDocument.addEventListener=(kind,fn)=>documentListeners.set(kind,fn);
  const api=fakeApi({handle:async(path,init)=>path.endsWith('/recorded-prototype.json')?(signal=init.signal,asset.promise):null});const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});await settle();await new Promise(resolve=>setTimeout(resolve,5));assert.equal(signal.aborted,false);
  if(hide){f.container.ownerDocument.hidden=true;documentListeners.get('visibilitychange')();}else await controller.showKnowledge();assert.equal(signal.aborted,true);asset.resolve(new Response(packet.bytes));assert.equal(await controller.recordedPacketReady,false);controller.destroy();
 }
});

test('held recorded opening retires a mismatched release catalog without replacing the focused Pause context',async t=>{
 const f=operationOpeningDOM(),native=operationOpeningFixture(),plan=ui.releaseOperationProcess(native.id),opening=deferredRead(),snapshot=deferredRead();
 for(const saved of [native.zero.state,native.head])Object.assign(saved.original_binding,{claim_binding_sha256:plan.release.claim_binding_sha256,corpus_manifest_sha256:plan.release.corpus_manifest_sha256});
 delete native.head.state_sha256;native.head.state_sha256=sha(ui.canonicalJSON(native.head));for(const envelope of [native.zero,native.snapshot,native.replay])envelope.current_state_sha256=native.head.state_sha256;native.snapshot.projection.state_sha256=native.head.state_sha256;native.snapshot.events.at(-1).state_sha256=native.head.state_sha256;native.snapshot.events.at(-1).resulting_state_sha256=native.head.state_sha256;native.binding.current_state_sha256=native.head.state_sha256;
 assert.equal(ui.releaseOpeningMatches(plan,native.zero.state),true);const packet=recordedPacketFixture(native);
 const api=fakeApi({handle:async path=>path.endsWith('/recorded-prototype.json')?new Response(packet.bytes):path.endsWith('/replay?through_seq=0')?opening.promise:path.endsWith('/snapshot?after=0')?snapshot.promise:path.includes('/operations?')?pendingOperationResponse(native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});t.after(()=>{controller.destroy();opening.resolve(response(native.zero));snapshot.resolve(response(native.snapshot));});assert.equal(await controller.recordedPacketReady,true);const selecting=controller.showDemonstration();f.listeners.get('click')({target:f.host.querySelector('[data-au-demo-stop]')});const focus={};f.container.ownerDocument.activeElement=focus;await selecting;
 assert.doesNotMatch(f.host.innerHTML,/data-au-release-plan=/,'known mismatched release topology retires even while held');assert.ok(f.host.querySelector('[data-au-demo-resume]'));assert.equal(f.container.ownerDocument.activeElement,focus);assert.doesNotMatch(f.host.innerHTML,/data-au-revision=|data-au-stage-fact=/);
});

test('recorded opening decision preserves trusted pending Pause and route cancellation without repainting late work',async t=>{
 const f=operationOpeningDOM(),packet=recordedPacketFixture(),opening=deferredRead(),snapshot=deferredRead();
 const api=fakeApi({handle:async path=>path.endsWith('/recorded-prototype.json')?new Response(packet.bytes):path.endsWith('/replay?through_seq=0')?opening.promise:path.endsWith('/snapshot?after=0')?snapshot.promise:path.includes('/operations?')?pendingOperationResponse(packet.native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});t.after(()=>{controller.destroy();opening.resolve(response(packet.native.zero));snapshot.resolve(response(packet.native.snapshot));});assert.equal(await controller.recordedPacketReady,true);const selecting=controller.showDemonstration();f.listeners.get('click')({target:f.host.querySelector('[data-au-demo-stop]')});await selecting;assert.ok(f.host.querySelector('[data-au-demo-resume]'));assert.doesNotMatch(f.host.innerHTML,/data-au-revision=|data-au-stage-fact=/);
 await controller.showKnowledge();const before=f.host.innerHTML;opening.resolve(response(packet.native.zero));snapshot.resolve(response(packet.native.snapshot));await settle();assert.equal(f.host.innerHTML,before);
});

test('complete atomic operation heads retain real saved envelopes and pinned source history without replay provenance',async()=>{
 const native=operationOpeningFixture(),head={claimId:native.id,revision:4,state_sha256:native.head.state_sha256,event_sha256:native.head.last_event_sha256},before=JSON.stringify(native.snapshot);
 for(const key of ['replay_only','through_seq','provenance','current_head'])assert.equal(Object.hasOwn(native.snapshot,key),false);
 const incoming=await ui.checkedAtomicOperationHead(native.snapshot,head,native.zero.replay_start,native.zero.state);
 assert.equal(incoming.state,native.head);assert.equal(incoming.accepted.events.length,4);assert.equal(incoming.replay,undefined);assert.equal(JSON.stringify(native.snapshot),before,'validation cannot manufacture replay provenance or mutate the atomic response');
});

test('complete atomic operation heads reject partial forks stale identities and changed source or start bindings',async()=>{
 const native=operationOpeningFixture(),head={claimId:native.id,revision:4,state_sha256:native.head.state_sha256,event_sha256:native.head.last_event_sha256};
 const cases=[['missing prefix',copy=>copy.events.shift()],['missing tail',copy=>copy.events.pop()],['duplicate sequence',copy=>copy.events.splice(1,0,copy.events[0])],['fork',copy=>copy.events[1].previous_event_sha256=sha('fork')],['missing link',copy=>delete copy.events[1].previous_event_sha256],['native sequence alias',copy=>copy.events[1].sequence=9],['native state alias',copy=>copy.events[1].resulting_state_sha256=sha('other state')],['stale state',copy=>copy.current_state_sha256=sha('stale')],['different current event',copy=>copy.current_event_sha256=sha('other head')],['missing current event',copy=>delete copy.current_event_sha256],['missing start',copy=>delete copy.replay_start],['changed start',copy=>copy.replay_start.profile_sha256=sha('other profile')],['changed original binding',copy=>copy.state.original_binding.claim_id='other'],['changed original source',copy=>copy.state.source_descriptors[0].sha256=sha('other bytes')],['unhashed accepted fact',copy=>copy.state.facts[0].summary='Changed fact'],['replay provenance stand-in',copy=>copy.provenance={}]];
 for(const [label,change]of cases){const copy=structuredClone(native.snapshot);change(copy);await assert.rejects(ui.checkedAtomicOperationHead(copy,head,native.zero.replay_start,native.zero.state),undefined,label);}
 // Even a self-consistent supplied head cannot borrow another opening's source packet.
 const changed=structuredClone(native.snapshot);changed.state.original_binding.claim_id='different';delete changed.state.state_sha256;changed.state.state_sha256=sha(ui.canonicalJSON(changed.state));changed.current_state_sha256=changed.state.state_sha256;changed.projection.state_sha256=changed.state.state_sha256;changed.events.at(-1).state_sha256=changed.state.state_sha256;changed.events.at(-1).resulting_state_sha256=changed.state.state_sha256;
 await assert.rejects(ui.checkedAtomicOperationHead(changed,{...head,state_sha256:changed.state.state_sha256},native.zero.replay_start,native.zero.state),/opening/);
});

test('cold operation selection starts the pinned head hint and live transport before its opening read finishes',async t=>{
 const f=operationOpeningDOM(),native=operationOpeningFixture(),opening=deferredRead(),head=deferredRead();
 const api=fakeApi({handle:async path=>path.endsWith('/claims')?response({claims:[{...native.head}]}):path.includes('/snapshot?')?response(native.snapshot):path.endsWith('/replay?through_seq=0')?opening.promise:path.endsWith('/replay?through_seq=4')?head.promise:path.includes('/operations?')?pendingOperationResponse(native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();opening.resolve(response(native.zero));head.resolve(response(native.replay));});await settle();
 const selecting=controller.showDemonstration();await settle();
 assert.ok(api.calls.some(row=>row.path.endsWith('/replay?through_seq=4')),'the catalog revision starts an independent verified replay read');
 assert.ok(api.calls.some(row=>row.path.endsWith('/operations?mode=live')),'default selection starts the live read without waiting for replay');
 head.resolve(response(native.replay));await settle();assert.doesNotMatch(f.host.innerHTML,/data-au-planned-process=/,'a hinted head alone cannot bind an earlier opening');
 opening.resolve(response(native.zero));await selecting;await waitFor(()=>f.host.innerHTML.includes('data-au-planned-process='));
 assert.match(f.host.innerHTML,new RegExp(`data-au-planned-process="${native.head.state_sha256}"`));assert.match(f.host.innerHTML,/data-au-planned-authority="none"/);assert.match(f.host.innerHTML,/data-au-revision="0"/);assert.doesNotMatch(f.host.innerHTML,/The later accepted outcome|data-au-stage-fact=|data-status="completed"/);
 assert.equal(api.calls.filter(row=>row.path.endsWith('/replay?through_seq=4')).length,1,'the verified hint reuses the normal head validation without another payload');assert.equal(api.calls.filter(row=>row.init.method==='POST').length,0);
});

test('cold operation selection reuses one complete atomic head while showing only a release outline before any response',async t=>{
 const f=operationOpeningDOM(),native=operationOpeningFixture(),opening=deferredRead(),snapshot=deferredRead();
 const api=fakeApi({handle:async path=>path.endsWith('/snapshot?after=0')?snapshot.promise:path.endsWith('/replay?through_seq=0')?opening.promise:path.includes('/operations?')?pendingOperationResponse(native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();opening.resolve(response(native.zero));snapshot.resolve(response(native.snapshot));});await settle();const before=api.calls.length,selecting=controller.showDemonstration();await settle();
 assert.match(f.host.innerHTML,/data-au-release-plan=/);assert.match(f.host.innerHTML,/>Procedure outline</);assert.doesNotMatch(f.host.innerHTML,/data-au-(?:revision|state-sha|forming-revision|forming-sha|planned-process)=|data-au-stage-fact=|data-status="completed"/);
 assert.deepEqual(api.calls.slice(before).map(row=>row.path.split('/').at(-1)).sort(),['operations?mode=live','replay?through_seq=0','snapshot?after=0'],'all three selected reads start before opening resolves');
 snapshot.resolve(response(native.snapshot));await settle();assert.doesNotMatch(f.host.innerHTML,/data-au-planned-process=/,'a complete atomic head alone cannot bind its opening');
 opening.resolve(response(native.zero));await selecting;await waitFor(()=>f.host.innerHTML.includes('data-au-planned-process='));
 assert.doesNotMatch(f.host.innerHTML,/data-au-release-plan=/);assert.match(f.host.innerHTML,/data-au-revision="0"/);assert.doesNotMatch(f.host.innerHTML,/The later accepted outcome|data-au-stage-fact=|data-status="completed"/);
 assert.equal(api.calls.filter(row=>row.path.endsWith(`/claims/${native.id}/snapshot?after=0`)).length,1);assert.equal(api.calls.filter(row=>row.path.endsWith('/replay?through_seq=4')).length,0,'valid atomic history replaces the full replay payload');assert.equal(api.calls.filter(row=>row.path.includes('/operations?mode=recorded')).length,0);await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='historical_recomputed');
});

test('cold operation selection falls back once for a partial atomic head without admitting its state',async t=>{
 const f=operationOpeningDOM(),native=operationOpeningFixture(),head=deferredRead(),partial=structuredClone(native.snapshot);partial.events.shift();
 const api=fakeApi({handle:async path=>path.endsWith('/snapshot?after=0')?response(partial):path.endsWith('/replay?through_seq=0')?response(native.zero):path.endsWith('/replay?through_seq=4')?head.promise:path.includes('/operations?')?pendingOperationResponse(native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();head.resolve(response(native.replay));});await settle();const before=api.calls.length;await controller.showDemonstration();await waitFor(()=>api.calls.some(row=>row.path.endsWith('/replay?through_seq=4')));
 assert.doesNotMatch(f.host.innerHTML,/data-au-planned-process=|data-au-stage-fact=/);assert.equal(f.attributes.get('data-au-operation-run-mode'),'opening');assert.equal(api.calls.slice(before).length,4,'invalid atomic history adds exactly one verified replay fallback');
 head.resolve(response(native.replay));await waitFor(()=>f.host.innerHTML.includes('data-au-planned-process='));assert.equal(api.calls.filter(row=>row.path.endsWith('/replay?through_seq=4')).length,1);assert.equal(api.calls.filter(row=>row.path.includes(`/claims/${native.id}/operations?`)).length,1);
});

test('cold operation selection never starts a fallback head read from an invalid atomic response after navigation',async t=>{
 const f=operationOpeningDOM(),native=operationOpeningFixture(),snapshot=deferredRead(),partial=structuredClone(native.snapshot);partial.events.pop();
 const api=fakeApi({handle:async path=>path.endsWith('/snapshot?after=0')?snapshot.promise:path.endsWith('/replay?through_seq=0')?response(native.zero):path.includes('/operations?')?pendingOperationResponse(native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();snapshot.resolve(response(partial));});await settle();await controller.showDemonstration();await settle();await controller.showKnowledge();const after=f.host.innerHTML;
 snapshot.resolve(response(partial));await settle();await settle();assert.equal(api.calls.filter(row=>row.path.endsWith('/replay?through_seq=4')).length,0,'an abandoned verifier cannot create a new owned request');assert.equal(f.host.innerHTML,after);assert.equal(api.calls.filter(row=>row.path.includes(`/claims/${native.id}/operations?`)).length,1);
});

test('cold operation selection refetches a stale catalog revision without consuming its hinted state',async t=>{
 const f=operationOpeningDOM(),native=operationOpeningFixture(),head=deferredRead();
 const api=fakeApi({handle:async path=>path.endsWith('/claims')?response({claims:[{...native.head,revision:3}]}):path.endsWith('/replay?through_seq=0')?response(native.zero):path.endsWith('/replay?through_seq=3')?response({detail:'Old hint unavailable'},409):path.endsWith('/replay?through_seq=4')?head.promise:path.includes('/operations?')?pendingOperationResponse(native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();head.resolve(response(native.replay));});await settle();await controller.showDemonstration();await settle();
 assert.ok(api.calls.some(row=>row.path.endsWith('/replay?through_seq=3')));assert.ok(api.calls.some(row=>row.path.endsWith('/replay?through_seq=4')));assert.doesNotMatch(f.host.innerHTML,/data-au-planned-process=/);
 head.resolve(response(native.replay));await waitFor(()=>f.host.innerHTML.includes('data-au-planned-process='));assert.match(f.host.innerHTML,/data-au-revision="0"/);assert.equal(api.calls.filter(row=>row.path.includes('/operations?mode=recorded')).length,0,'a stale speculative hint does not force a recorded fallback');
});

test('cold operation selection aborts its early reader and ignores late opening and outline responses after navigation',async t=>{
 const f=operationOpeningDOM(),native=operationOpeningFixture(),opening=deferredRead(),snapshot=deferredRead();let cancelled=0,signal;
 const api=fakeApi({handle:async(path,init)=>path.includes('/snapshot?')?snapshot.promise:path.endsWith('/replay?through_seq=0')?opening.promise:path.includes('/operations?')?(signal=init.signal,{ok:true,status:200,body:new ReadableStream({cancel(){cancelled++;}})}):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();opening.resolve(response(native.zero));snapshot.resolve(response(native.snapshot));});await settle();const selecting=controller.showDemonstration();await settle();assert.equal(signal.aborted,false);
 await controller.showWork();const after=f.host.innerHTML;assert.equal(signal.aborted,true);await settle();assert.equal(cancelled,1,'even a transport that ignores AbortSignal releases its owned body reader');
 snapshot.resolve(response(native.snapshot));opening.resolve(response(native.zero));await selecting;await settle();assert.equal(f.host.innerHTML,after);assert.equal(api.calls.filter(row=>row.path.includes('/operations?')).length,1,'stale work cannot trigger a fallback trace');
});

test('cold operation selection retains explicit recorded delivery and never starts live reads for legacy playback',async t=>{
 const f=operationOpeningDOM(),native=operationOpeningFixture();
 const api=fakeApi({handle:async path=>path.endsWith('/claims')?response({claims:[native.head]}):path.endsWith('/replay?through_seq=0')?response(native.zero):path.endsWith('/replay?through_seq=4')?response(native.replay):path.includes('/operations?')?pendingOperationResponse(native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.showDemonstration(true,'reference','recorded');await settle();
 assert.equal(api.calls.filter(row=>row.path.includes('/operations?mode=recorded')).length,1);assert.equal(api.calls.filter(row=>row.path.includes('/operations?mode=live')).length,0);
 const count=api.calls.filter(row=>row.path.includes('/operations?')).length;await controller.showDemonstration(true,'legacy');await settle();assert.equal(api.calls.filter(row=>row.path.includes('/operations?')).length,count,'only the selected allowed reference operation session can start a stream');
});

test('selected operation priority cancels only idle reads and suppresses new warming until foreground navigation',async t=>{
 const f=operationOpeningDOM(),native=operationOpeningFixture(),head=deferredRead(),pending=[],idle=[];const previousIdle=globalThis.requestIdleCallback,previousCancel=globalThis.cancelIdleCallback;
 globalThis.requestIdleCallback=callback=>(idle.push(callback),idle.length);globalThis.cancelIdleCallback=()=>{};
 const api=fakeApi({handle:async(path,init)=>{
  if(path.endsWith('/claims'))return response({claims:[native.head]});
  if(path.endsWith('/knowledge')||path.includes('/snapshot?')){const read=deferredRead();pending.push({...read,path,signal:init.signal});return read.promise;}
  if(path.endsWith('/replay?through_seq=0'))return response(native.zero);if(path.endsWith('/replay?through_seq=4'))return head.promise;if(path.includes('/operations?'))return pendingOperationResponse(native.binding);
 }});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();head.resolve(response(native.replay));for(const row of pending)row.resolve(row.path.endsWith('/knowledge')?response({versions:[],uses:[],quarantined:[]}):response(native.snapshot));globalThis.requestIdleCallback=previousIdle;globalThis.cancelIdleCallback=previousCancel;});
 await settle();assert.ok(idle.length);idle.shift()();await settle();assert.equal(pending.filter(row=>row.path.includes('/snapshot?')).length,2,'the existing bounded idle queue was actually running');
 const warming=pending.slice();await controller.showDemonstration();await settle();assert.ok(warming.every(row=>row.signal.aborted),'selection aborts active idle Knowledge and snapshots rather than only ignoring their results');
 const afterSelection=api.calls.length;for(const callback of idle.splice(0))callback();await settle();assert.equal(api.calls.length,afterSelection,'selected startup cannot refill the idle queue');
 assert.ok(api.calls.filter(row=>row.path.includes('/replay?')||row.path.includes('/operations?')).every(row=>!row.init.signal.aborted),'selected head, opening and operation reads retain ownership');
 const knowledge=controller.showKnowledge();await settle();assert.ok(pending.length>warming.length,'explicit Knowledge starts its foreground read despite suspended warming');assert.equal(pending.at(-1).signal.aborted,false);pending.at(-1).resolve(response({versions:[],uses:[],quarantined:[]}));await knowledge;
});

test('selected operation priority leaves an explicit foreground Cases read intact and defers direct-entry collection warming',async t=>{
 const native=operationOpeningFixture(),f=operationOpeningDOM(),collection=deferredRead(),head=deferredRead();let collectionSignal;
 const api=fakeApi({handle:async(path,init)=>{if(path.endsWith('/claims')){collectionSignal=init.signal;return collection.promise;}if(path.includes('/snapshot?'))return response(native.snapshot);if(path.endsWith('/replay?through_seq=0'))return response(native.zero);if(path.endsWith('/replay?through_seq=4'))return head.promise;if(path.includes('/operations?'))return pendingOperationResponse(native.binding);}});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();collection.resolve(response({claims:[native.head]}));head.resolve(response(native.replay));});await settle();assert.ok(collectionSignal);
 await controller.showDemonstration();await settle();assert.equal(collectionSignal.aborted,false,'selection cannot cancel the explicitly requested Cases collection');assert.equal(api.calls.filter(row=>row.path.endsWith('/claims')).length,1,'an unfinished selected run cannot add a quiet collection read');
 assert.equal(api.calls.filter(row=>row.path.endsWith('/knowledge')).length,0,'direct-entry warm Knowledge waits for selected work');
});

test('selected operation priority defers the direct-route idle catalog and Knowledge until the selected run ends',async t=>{
 routingFixture(t,'#autonomous/demonstration');const native=operationOpeningFixture(),f=operationOpeningDOM(),head=deferredRead();
 const api=fakeApi({handle:async path=>path.includes('/snapshot?')?response(native.snapshot):path.endsWith('/replay?through_seq=0')?response(native.zero):path.endsWith('/replay?through_seq=4')?head.promise:path.includes('/operations?')?pendingOperationResponse(native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();head.resolve(response(native.replay));});await settle();await settle();
 assert.equal(api.calls.filter(row=>row.path.endsWith('/claims')||row.path.endsWith('/knowledge')).length,0,'a cold operation route cannot start background catalog or Knowledge traffic while its head is pending');
 await controller.showWork();await settle();assert.equal(api.calls.filter(row=>row.path.endsWith('/claims')).length,1,'explicit Cases navigation still loads its collection');assert.equal(api.calls.filter(row=>row.path.endsWith('/knowledge')).length,1,'ordinary idle Knowledge warming resumes after leaving the selected run');
});

test('release procedure outlines carry only the exact nine release catalogs and no accepted state identity',()=>{
 for(const row of ui.REFERENCE_DEMO_CASES){const plan=ui.releaseOperationProcess(row.claim_id),html=ui.releaseProcedurePreview(plan,'recorded');assert.ok(plan);assert.equal(plan.release.profile_id,'synthetic-nine-v2');assert.ok(plan.release.request_source_pin.quote);assert.match(html,/Recorded replay/);assert.match(html,/data-au-release-authority="none"/);assert.match(html,/>Procedure outline</);assert.equal((html.match(/data-au-planned-node disabled/g)||[]).length,plan.graph.nodes.length);assert.doesNotMatch(html,/data-au-(?:revision|state-sha|forming-revision|forming-sha|planned-process|planned-head-revision|planned-graph-sha)=|data-au-stage-fact=|data-au-document-checked="true"|data-status="completed"|Procedure reused|Version [0-9]|undefined/);assert.equal(plan.head_revision,undefined);assert.equal(plan.graph.graph_sha256,undefined);}
 for(const id of ['clm_2a9c260c26afaa34','auto_a489b283495e7b03b5aab860','unknown'])assert.equal(ui.releaseOperationProcess(id),null,'historical and unknown cases have no release outline or operation permission');
});

test('release procedure reconciliation requires original binding profile catalog and exact active request source pins',async()=>{
 const fs=require('node:fs'),path=require('node:path'),plan=ui.releaseOperationProcess(ui.REFERENCE_DEMO_CASES[0].claim_id),release=plan.release;
 const sources=release.source_sha256s.map((hash,index)=>{const directory=path.join(__dirname,'../casepath-api/casepath_api/reference_profiles/synthetic-nine-v2',plan.claim_id),file=fs.readdirSync(directory).find(file=>sha(fs.readFileSync(path.join(directory,file)))===hash),text=fs.readFileSync(path.join(directory,file),'utf8');return{artifact_id:'release-source-'+index,file_name:file,sha256:hash,text_sha256:sha(text),text};});
 const state={claim_id:plan.claim_id,run_id:'current',revision:4,original_binding:{claim_binding_sha256:release.claim_binding_sha256,corpus_manifest_sha256:release.corpus_manifest_sha256},semantic_contexts:{current:{execution_mode:'deterministic_reference',reference_provenance:{mode:'deterministic_reference',synthetic:true,as_of:'2025-02-21',profile_id:release.profile_id,profile_sha256:release.profile_sha256},sources}},acquired_sources:sources};
 const admitted={graph:structuredClone(plan.graph),rule_pack_sha256:release.rule_pack_sha256};assert.equal(await ui.releaseHeadMatches(plan,state,admitted),true);
 for(const change of [copy=>copy.original_binding.claim_binding_sha256=sha('different original'),copy=>copy.original_binding.corpus_manifest_sha256=sha('other corpus'),copy=>copy.semantic_contexts.current.reference_provenance.profile_sha256=sha('other profile'),copy=>copy.semantic_contexts.current.sources=[],copy=>copy.acquired_sources=copy.acquired_sources.map(row=>({...row,text:row.text+'changed'}))]){const copy=structuredClone(state);change(copy);assert.equal(await ui.releaseHeadMatches(plan,copy,admitted),false);}
 const changed=structuredClone(admitted);changed.graph.nodes.pop();assert.equal(await ui.releaseHeadMatches(plan,state,changed),false);assert.equal(await ui.releaseHeadMatches(plan,state,{...admitted,rule_pack_sha256:sha('other pack')}),false);
});

test('release procedure opening retains trusted History detail and focus while a valid late opening arrives',async t=>{
 const native=operationOpeningFixture(),f=operationOpeningDOM(),opening=deferredRead(),head=deferredRead(),plan=ui.releaseOperationProcess(native.id),zero=structuredClone(native.zero);
 zero.state.original_binding={claim_binding_sha256:plan.release.claim_binding_sha256,corpus_manifest_sha256:plan.release.corpus_manifest_sha256};zero.provenance.claim_binding_sha256=plan.release.claim_binding_sha256;
 const api=fakeApi({handle:async path=>path.endsWith('/replay?through_seq=0')?opening.promise:path.endsWith('/replay?through_seq=4')?head.promise:path.includes('/operations?')?pendingOperationResponse(native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();opening.resolve(response(zero));head.resolve(response(native.replay));});await settle();const selecting=controller.showDemonstration();const target=control(f,'data-au-detail','activity');target.focus();f.listeners.get('click')({target});const before=f.host.innerHTML;
 opening.resolve(response(zero));await selecting;await settle();assert.equal(f.host.innerHTML,before,'late accepted revision zero cannot replace the held release map');assert.equal(f.container.ownerDocument.activeElement,target,'late opening cannot steal trusted focus');assert.doesNotMatch(f.host.innerHTML,/data-au-revision=/);
 f.listeners.get('click')({target:control(f,'data-au-demo-resume')});assert.match(f.host.innerHTML,/data-au-context="activity"/,'Resume retains the actual pending History choice');assert.match(f.host.innerHTML,/data-au-revision="0"/);assert.equal(api.calls.filter(row=>row.path.includes('/snapshot?')).length,1);
});

test('release procedure pending Pause can Resume before any response and retires a mismatched outline while held',async t=>{
 const native=operationOpeningFixture(),f=operationOpeningDOM(),opening=deferredRead(),head=deferredRead();
 const api=fakeApi({handle:async path=>path.endsWith('/replay?through_seq=0')?opening.promise:path.endsWith('/replay?through_seq=4')?head.promise:path.includes('/operations?')?pendingOperationResponse(native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();opening.resolve(response(native.zero));head.resolve(response(native.replay));});await settle();const selecting=controller.showDemonstration();
 f.listeners.get('click')({target:f.host.querySelector('[data-au-demo-stop]')});assert.ok(f.host.querySelector('[data-au-demo-resume]'),'pre-response Pause immediately exposes Resume');assert.equal(f.host.querySelector('[data-au-demo-stop]'),null);
 f.listeners.get('click')({target:f.host.querySelector('[data-au-demo-resume]')});assert.ok(f.host.querySelector('[data-au-demo-stop]'),'Resume works while current is still unknown');
 f.listeners.get('click')({target:f.host.querySelector('[data-au-demo-stop]')});const focus={};f.container.ownerDocument.activeElement=focus;
 opening.resolve(response(native.zero));await selecting;await settle();assert.doesNotMatch(f.host.innerHTML,/data-au-release-plan=/,'an actually mismatched original retires the outline despite the pause');assert.ok(f.host.querySelector('[data-au-demo-resume]'));assert.equal(f.container.ownerDocument.activeElement,focus,'retirement preserves the focused control rather than repainting the claim');assert.doesNotMatch(f.host.innerHTML,/data-au-revision=/);
});
test('operation source spans preserve Python codepoints, exact original/text hashes and provisional authority',async()=>{
 const f=operationFixture(),prior=JSON.stringify(f.baseline);f.sourceText += '\n' + 'Deep original line.\n'.repeat(200);
 const open=f.seal('source.open',{type:'source',id:'source'},{...f.descriptor,text:f.sourceText,text_sha256:sha(f.sourceText)});
 await ui.checkedOperation(open,f.trace,f.baseline);
 const chars=Array.from(f.sourceText),quote='A tenant reports a cold home.',start_char=chars.join('').indexOf('A tenant')-1,pin={artifact_id:'source',sha256:f.descriptor.sha256,text_sha256:sha(f.sourceText),offset_unit:'unicode_code_point',start_char,end_char:start_char+Array.from(quote).length,quote};
 const span=f.seal('span.read',{type:'source',id:'source'},{read:true},pin);await ui.checkedOperation(span,f.trace,f.baseline);
 f.trace.current=span;const reading=ui.operationReadingMarkup(f.trace);assert.match(reading,/<mark[^>]*>A tenant reports a cold home\.<\/mark>/);assert.ok(reading.includes('Before 😀&#13;\n'));assert.equal((reading.match(/Deep original line\./g)||[]).length,200,'the source pane retains the complete immutable text');
 const extract=f.seal('fact.extract',{type:'fact',id:'condition:cold',node_id:'branch'},{status:'provisional'},pin);await ui.checkedOperation(extract,f.trace,f.baseline);f.trace.current=extract;assert.match(ui.operationReadingMarkup(f.trace),/Provisional finding/);
 assert.equal(JSON.stringify(f.baseline),prior,'an operation cannot mutate accepted facts, nodes or document state');
 const bad=f.seal('phrase.match',{type:'source',id:'source'},{matched:true},{...pin,start_char:pin.start_char+1,end_char:pin.end_char+1});await assert.rejects(ui.checkedOperation(bad,f.trace,f.baseline),/exact Unicode/);
 const tampered={...f.seal('phrase.match',{type:'source',id:'source'},{matched:true},pin),result:{matched:false}};await assert.rejects(ui.checkedOperation(tampered,f.trace,f.baseline),/identity/);
 assert.equal(f.trace.rows.length,3);assert.match(ui.operationHistoryMarkup(f.trace),/real-1/);assert.match(ui.operationHistoryMarkup(f.trace),/real-3/);
});
test('compact operation checkpoints reconstruct only the exact pinned native journal and head',async()=>{
 const f=operationFixture(),head={claimId:f.binding.claim_id,revision:4,state_sha256:f.head.state_sha256,event_sha256:f.head.last_event_sha256};
 assert.equal(ui.checkedOperationBinding(f.binding,head,f.start),f.binding);
 for(const change of [{run_id:'older-run'},{profile_sha256:sha('wrong-profile')},{current_state_sha256:sha('wrong-head')},{mode:'invented-live'},{instrumentation_id:'unsupported-revision'}])assert.throws(()=>ui.checkedOperationBinding({...f.binding,...change},head,f.start),/binding/);
 const frame=(s)=>({contract:operationContract,type:'checkpoint',verified:true,journal_seq:s.revision,event_sha256:s.last_event_sha256,state_sha256:s.state_sha256,events:[f.journal[s.revision-1]],mode:'replay',through_seq:s.revision,current_revision:4,current_state_sha256:f.head.state_sha256,current_event_sha256:f.head.last_event_sha256,cursor_sha256:s.last_event_sha256,provenance:{run_id:s.run_id,event_sha256:s.last_event_sha256}});
 const first={...frame(f.baseline),state:f.baseline};assert.equal((await ui.checkedOperationCheckpoint(first,f.trace)).state,f.baseline);
 const delta={...frame(f.head),base_state_sha256:f.baseline.state_sha256,state_delta:{set:{revision:4,last_event_sha256:f.head.last_event_sha256,state_sha256:f.head.state_sha256,status:f.head.status,outcome:f.head.outcome},remove:[]}};
 await assert.rejects(ui.checkedOperationCheckpoint({...delta,state_delta:{...delta.state_delta,set:{...delta.state_delta.set,status:'completed'}}},f.trace),/exact state hash/);
 const incoming=await ui.checkedOperationCheckpoint(delta,f.trace);assert.deepEqual(incoming.state,f.head);assert.deepEqual(incoming.accepted.events,f.journal);
 await assert.rejects(ui.checkedOperationCheckpoint(delta,f.trace),/sequence/);
});
test('NDJSON operations decode fragmented Unicode and cancel without consuming another frame',async()=>{
 const frames=[{contract:operationContract,type:'binding',label:'😀 Zürich'},{contract:operationContract,type:'error',message:'Exact stop'}],bytes=new TextEncoder().encode(frames.map(JSON.stringify).join('\n')+'\n');let cancelled=0,offset=0;
 const response={body:{getReader(){return{async read(){if(offset===bytes.length)return{done:true};const value=bytes.slice(offset,offset+3);offset+=value.length;return{value,done:false};},async cancel(){cancelled++;},releaseLock(){}};}}};
 const iterator=ui.operationFrames(response);assert.deepEqual((await iterator.next()).value,frames[0]);await iterator.return();assert.equal(cancelled,1);assert.ok(offset<bytes.length);
 const huge={body:new ReadableStream({start(controller){controller.enqueue(new TextEncoder().encode('x'.repeat(2*1024*1024)));controller.close();}})};
 await assert.rejects(async()=>{for await(const frame of ui.operationFrames(huge))void frame;},/bound/);
});

test('wire draining completes before paused application consumption and abort prevents the next frame',async()=>{
 const frames=Array.from({length:12},(_,seq)=>({contract:operationContract,type:'operation',seq,label:'😀'})),controller=new AbortController();let pulls=0;
 const body=new ReadableStream({pull(stream){pulls++;if(pulls<=frames.length)stream.enqueue(new TextEncoder().encode(JSON.stringify(frames[pulls-1])+'\n'));else stream.close();}}),buffer=ui.bufferedOperations({body},controller.signal);
 await buffer.producer;assert.equal(pulls,frames.length+1,'the wire finishes independently of presentation');
 assert.deepEqual((await buffer.next()).value,frames[0]);controller.abort();assert.deepEqual(await buffer.next(),{done:true});
});

test('recorded delivery retains the captured binding while each visible mode keeps its historical as-of qualifier',()=>{
 const f=operationFixture(),bindingBefore=JSON.stringify(f.binding),replay={state:f.baseline,mode:'replay',replay_only:true,through_seq:3,current_revision:4,current_state_sha256:f.head.state_sha256,current_event_sha256:f.head.last_event_sha256};
 const render=delivery=>ui.workMarkup(f.baseline,{},'branch',f.journal.slice(0,3),'step',{}, {mode:'replay',replay,operations:{binding:f.binding,rows:[],sources:new Map(),asOf:'2025-02-21',...delivery}});
 const recorded=render({recorded:true});assert.match(recorded,/Recorded replay · Synthetic sources · No external action · as of 2025-02-21/);assert.doesNotMatch(recorded,/Live check from saved sources/);
 const live=render({});assert.match(live,/Live rules-based check · Synthetic sources · No external action · as of 2025-02-21/);assert.equal((live.match(/as of 2025-02-21/g)||[]).length,1);assert.doesNotMatch(live,/Recorded investigation/);assert.doesNotMatch(live,/data-au-operation-skip/);assert.match(render({buffer:{result:{exact_output_verified:true,state_sha256:f.binding.current_state_sha256,current_event_sha256:f.binding.current_event_sha256}}}),/data-au-operation-skip/);assert.doesNotMatch(render({finished:true}),/data-au-operation-skip/);
 const saved=render({savedFallback:true});assert.match(saved,/Saved result · Synthetic sources · No external action/);assert.doesNotMatch(saved,/Live check from saved sources/);assert.equal(JSON.stringify(f.binding),bindingBefore);
 assert.equal(ui.operationLabel({kind:'node.evaluate'}),'Evaluate step');assert.equal(ui.operationLabel({kind:'dependency.evaluate'}),'Check dependency');assert.equal(ui.operationLabel({kind:'branch.activate',result:{activation:'unresolved'}}),'Evaluate unresolved branch');assert.equal(ui.operationLabel({kind:'fact.extract',result:{verification_required:false,status:'established'}}),'Inspect verified finding');
});

test('operation delivery names existing procedure reuse and its recorded origin without changing saved knowledge',()=>{
 const use={knowledge_id:'procedure.defect_mold_heating',version:2,knowledge_sha256:sha('recorded procedure'),source_claim_id:'claim-a'},saved=state({knowledge_uses:[use]}),before=JSON.stringify(saved);
 const ordinary=ui.formingKnowledgeMarkup(saved),delivered=ui.formingKnowledgeMarkup(saved,{},false,false,null,[],true);
 assert.match(ordinary,/Procedure used for this case · Version 2/);assert.match(ordinary,/From this case’s source evidence/);
 assert.match(delivered,/Procedure reused · Version 2/);assert.match(delivered,/Recorded origin: this case’s source evidence/);assert.match(delivered,/data-au-knowledge="procedure.defect_mold_heating"/);assert.equal(ui.operationLabel({kind:'knowledge.reuse'}),'Procedure reused');assert.equal(JSON.stringify(saved),before);
 saved.knowledge_uses=[{...use,source_claim_id:'earlier-source-case'}];assert.match(ui.formingKnowledgeMarkup(saved,{},false,false,null,[],true),/Origin source case/);assert.match(ui.formingKnowledgeMarkup(saved,{},false,false,null,[],true),/data-au-claim="earlier-source-case"/);
});

test('failed live operation records remain inspectable while recorded delivery opens and preserves same-ID attempts',async()=>{
 const f=operationFixture(),operation=f.seal('source.open',{type:'source',id:'source'},{...f.descriptor,text:f.sourceText,text_sha256:sha(f.sourceText)});await ui.checkedOperation(operation,f.trace,f.baseline);
 const pending={binding:null,rows:[],previousAttempts:[{rows:f.trace.rows,bytes:f.trace.bytes,recorded:false,reason:'The stream ended before its verified result.'}]};
 assert.equal(ui.operationRecord(pending,'operation',operation.id),operation);assert.match(ui.operationHistoryMarkup(pending),/Earlier live assessment stopped/);assert.match(ui.operationHistoryMarkup(pending),/Waiting for the stored operation trace/);
 const delivered={...operation,operation_sha256:sha('same semantic object in another captured chain')};pending.rows=[delivered];
 assert.equal(ui.operationRecord(pending,'operation',operation.id),delivered);assert.equal(ui.operationRecord(pending,'operation-attempt','0:'+operation.id),operation);assert.match(ui.operationHistoryMarkup(pending),new RegExp(`data-au-record-id="0:${operation.id}"`));
});

test('operation reading uses current case labels and source summaries without exposing raw routing or Boolean scalars',()=>{
 const f=operationFixture(),raw={contract:operationContract,type:'operation',id:'observed-node',kind:'node.evaluate',object:{type:'node',id:'branch'},result:{verdict:true,activation:'true',route_state:'needed_later'}},trace={state:f.baseline,current:raw,rows:[raw],sources:new Map()};
 const html=ui.operationReadingMarkup(trace);assert.match(html,/Check separate service/);assert.doesNotMatch(html,/needed_later|· true|· false|>true</);assert.deepEqual(ui.operationRecord(trace,'operation',raw.id),raw,'History retains exact machine fields');
 trace.current={...raw,kind:'document.require',object:{type:'document',id:'notice'},result:{route_state:'needed_now'}};assert.match(ui.operationReadingMarkup(trace),/Separate notice/);assert.doesNotMatch(ui.operationReadingMarkup(trace),/needed_now/);
 trace.current={...raw,result:{summary:'The actual source describes an uncertain service date.',verdict:'unresolved'}};assert.match(ui.operationReadingMarkup(trace),/The actual source describes an uncertain service date/);
});

test('restarting Demonstration opens its own first case after inspection of another case',async t=>{
 const f=dom(),first=ui.DEMO_CASES[0].claim_id,second=ui.DEMO_CASES[1].claim_id;
 const envelope=id=>{const saved=state({claim_id:id,title:id===first?'First original packet':'Earlier inspected packet',revision:0,state_sha256:sha(id),last_event_sha256:null,graph:null,evaluation:null,facts:[],obligations:[],actions:[],status:'not_started',mode:'unprocessed',phase:'not_run'});return {state:saved,projection:{revision:0,state_sha256:saved.state_sha256},events:[],cursor_sha256:null,mode:'replay',replay_only:true,through_seq:0,current_revision:0,current_state_sha256:saved.state_sha256,current_event_sha256:null,provenance:{event_sha256:null}};};
 const api=fakeApi({handle:async path=>{const match=path.match(/\/claims\/([^/]+)\/replay\?through_seq=0$/);return match?response(envelope(match[1])):null;}}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 await controller.openClaim(second,true,{mode:'replay',collection:'legacy',through:0,detail:'activity'});assert.ok(f.host.innerHTML.includes(sha(second)));
 await controller.showDemonstration(true,'legacy');assert.ok(f.host.innerHTML.includes(sha(first)));assert.ok(!f.host.innerHTML.includes(sha(second)));assert.equal(api.calls.filter(row=>row.init.method==='POST').length,0);
});

function workingFixture(){
 const f=operationFixture(),graph={...f.baseline.graph,conditions:{family_home:{verdict:'true'}},document_catalog:[{document_type:'notice',label:'Separate notice'}],nodes:f.baseline.graph.nodes.map(node=>({...node,completed:true,document_types:node.node_id==='branch'?['notice']:[]}))};
 const seal=(kind,object,input,result,causes=[],stage='interpretation')=>{const frame={...f.seal(kind,object,result),stage,input,cause_ids:causes,input_sha256:sha(ui.canonicalJSON(input))};const material={...frame};delete material.contract;delete material.type;delete material.operation_sha256;return {...frame,operation_sha256:sha(ui.canonicalJSON(material))};};
 const inspect=(effective_conditions,conditions_override=null,stage='interpretation')=>{const evaluation_sha256=sha(ui.canonicalJSON({graph_sha256:graph.graph_sha256,conditions_override,effective_conditions}));return seal('process.inspect',{type:'process',id:f.baseline.claim_id},{graph_sha256:graph.graph_sha256,evaluation_sha256,conditions_override},{phase:'provisional',graph_sha256:graph.graph_sha256,evaluation_sha256,graph,effective_conditions},[],stage);};
 return {...f,graph,seal,inspect};
}
test('actual working graphs and applicability stay separately inspectable without advancing accepted execution',async()=>{
 const f=workingFixture(),original=structuredClone(f.baseline),inspect=f.inspect({family_home:{verdict:'false'}});await ui.checkedOperation(inspect,f.trace,f.baseline);ui.applyWorkingOperation(inspect,f.trace,f.baseline);
 const scope={graph_sha256:f.graph.graph_sha256,evaluation_sha256:inspect.result.evaluation_sha256},node=f.seal('node.evaluate',{type:'node',id:'branch'},scope,{...scope,phase:'provisional',activation:'true',execution_state:'completed',effective_completed:true},[inspect.id]);await ui.checkedOperation(node,f.trace,f.baseline);ui.applyWorkingOperation(node,f.trace,f.baseline);f.trace.current=node;
 const working=ui.workingProcessState(f.trace),markup=ui.formingMarkup(f.baseline,{},'start',[],{}, {},{},false,f.trace);
 assert.equal(working.graph,f.graph);assert.deepEqual(working.conditions,inspect.result.effective_conditions);assert.deepEqual(f.baseline,original);assert.equal(f.trace.transportState,null);
 assert.match(markup,/au-operation-stage/);assert.doesNotMatch(markup,/Working model · provisional|Applicability · Applies/);assert.match(markup,/<button[^>]*data-au-node="start"[^>]*data-status="completed"/);assert.match(markup,/<button[^>]*data-au-node="branch"[^>]*data-status="provisional"/);assert.equal((markup.match(/data-status="completed"/g)||[]).length,1,"only the already accepted parent stays complete");assert.match(markup,new RegExp(`data-au-working-scope="${inspect.id}"`));assert.match(markup,new RegExp(`data-au-record-id="${node.id}"`));assert.deepEqual(ui.operationRecord(f.trace,'operation',node.id),node,'raw actual execution result is inspectable');
 f.trace.finished=true;assert.equal(ui.workingProcessState(f.trace),null);assert.match(ui.graphMarkup(f.baseline,'start'),/>✓</,'the accepted graph retains its existing recorded completion');
});
test('working evaluations cannot borrow a different graph, override condition scope, stage or target',async()=>{
 const f=workingFixture(),inspect=f.inspect({family_home:{verdict:'false'}});await ui.checkedOperation(inspect,f.trace,f.baseline);ui.applyWorkingOperation(inspect,f.trace,f.baseline);
 const scope={graph_sha256:f.graph.graph_sha256,evaluation_sha256:inspect.result.evaluation_sha256};
 for(const change of [{graph_sha256:sha('other graph')},{evaluation_sha256:sha('other override')}]){const op=f.seal('node.evaluate',{type:'node',id:'branch'},{...scope,...change},{...scope,...change,phase:'provisional',activation:'false'},[inspect.id]);await assert.rejects(ui.checkedOperation(op,f.trace,f.baseline),/exact inspected process scope/);}
 await assert.rejects(ui.checkedOperation(f.seal('node.evaluate',{type:'node',id:'future-step'},scope,{...scope,phase:'provisional',activation:'true'},[inspect.id]),f.trace,f.baseline),/different process object/);
 await assert.rejects(ui.checkedOperation(f.seal('node.evaluate',{type:'node',id:'branch'},scope,{...scope,phase:'provisional',activation:'true'},[inspect.id],'verification'),f.trace,f.baseline),/exact inspected process scope/);
 const wrong=f.inspect({family_home:{verdict:'true'}});wrong.result.evaluation_sha256=inspect.result.evaluation_sha256;wrong.input.evaluation_sha256=inspect.result.evaluation_sha256;wrong.result_sha256=sha(ui.canonicalJSON(wrong.result));wrong.input_sha256=sha(ui.canonicalJSON(wrong.input));const material={...wrong};delete material.type;delete material.contract;delete material.operation_sha256;wrong.operation_sha256=sha(ui.canonicalJSON(material));await assert.rejects(ui.checkedOperation(wrong,f.trace,f.baseline),/condition scope.*identity/);assert.equal(f.trace.rows.length,1);
});
test('same working graph with a different actual override retains independent scope and provisional document targets',async()=>{
 const f=workingFixture(),first=f.inspect({family_home:{verdict:'false'}});await ui.checkedOperation(first,f.trace,f.baseline);ui.applyWorkingOperation(first,f.trace,f.baseline);
 const second=f.inspect({family_home:{verdict:'true'}},{family_home:'true'});await ui.checkedOperation(second,f.trace,f.baseline);ui.applyWorkingOperation(second,f.trace,f.baseline);assert.notEqual(first.result.evaluation_sha256,second.result.evaluation_sha256);assert.equal(f.trace.workingScopes.size,2);
 const scope={graph_sha256:f.graph.graph_sha256,evaluation_sha256:second.result.evaluation_sha256},document=f.seal('document.require',{type:'document',id:'notice'},{...scope,required_at_node_ids:['branch']},{...scope,phase:'provisional',activation:'true',route_state:'needed_later',review_state:'sufficient',required_at_node_ids:['branch']},[second.id]);await ui.checkedOperation(document,f.trace,f.baseline);ui.applyWorkingOperation(document,f.trace,f.baseline);f.trace.current=document;f.trace.state=f.baseline;
 const markup=ui.formingMarkup(f.baseline,{},'start',[],{}, {},{},false,f.trace);assert.doesNotMatch(markup,/Requirement calculation|data-au-working-document="notice"/);assert.equal(ui.operationRecord(f.trace,'operation',document.id),document,'inactive future requirements stay in exact History rather than appearing on the stage');assert.equal(ui.operationNodeId(document,f.graph,f.baseline),'branch');assert.doesNotMatch(ui.operationReadingMarkup(f.trace),/needed_later|sufficient/);assert.equal(f.trace.workingScopes.get(first.id).documents.size,0);assert.equal(f.baseline.evaluation.documents[0].review_state,'unreviewed');
});
test('source-to-working-step relationships use exact observed fact/document pins rather than retained reading state',async()=>{
 const f=workingFixture(),inspect=f.inspect({});await ui.checkedOperation(inspect,f.trace,f.baseline);ui.applyWorkingOperation(inspect,f.trace,f.baseline);
 const pin={artifact_id:'source',quote:'A tenant reports a cold home.',start_char:10,end_char:39},fact={id:'actual-fact',kind:'fact.extract',object:{type:'fact',id:'fact:notice'},input:{document_type:'notice'},result:{verification_required:true},source:pin};f.trace.current=fact;
 assert.deepEqual(ui.operationRelationship(f.trace,f.baseline),{node:'branch',source:'source',pin,operation_id:'actual-fact',graph_sha256:f.graph.graph_sha256});
 f.trace.displaySource={artifact_id:'source',pin};f.trace.current={...fact,source:undefined};assert.equal(ui.operationRelationship(f.trace,f.baseline),null,'retained source reading cannot invent an operation dependency');
});

test('selected provisional readiness explains the actual blocker independently of applicability',async()=>{
 const f=workingFixture(),inspect=f.inspect({});await ui.checkedOperation(inspect,f.trace,f.baseline);ui.applyWorkingOperation(inspect,f.trace,f.baseline);
 const scope={graph_sha256:f.graph.graph_sha256,evaluation_sha256:inspect.result.evaluation_sha256},result={...scope,phase:'provisional',activation:'true',execution_state:'blocked',blocked_by:['start'],unresolved_dependencies:[],missing_document_types:['notice']},op=f.seal('node.evaluate',{type:'node',id:'branch'},scope,result,[inspect.id]);await ui.checkedOperation(op,f.trace,f.baseline);ui.applyWorkingOperation(op,f.trace,f.baseline);f.trace.current=op;
 const working=ui.workingProcessState(f.trace),html=ui.graphMarkup(working,'branch',{}, {overview:true,working:f.trace.working});assert.deepEqual(working.evaluation.nodes[0].blocked_by,['start']);assert.equal(working.evaluation.nodes[0].execution_state,'blocked');assert.match(html,/Applicability · Applies/);assert.match(html,/Execution · Waiting for Inspect message/);assert.doesNotMatch(html,/>✓<|data-status="completed"|>Ready to check</);assert.equal(f.baseline.evaluation.nodes[1].execution_state,'ready');
 assert.match(ui.workingReadiness({...result,blocked_by:[],unresolved_dependencies:['start']},f.graph),/Unresolved prerequisite: Inspect message/);assert.match(ui.workingReadiness({...result,blocked_by:[]},f.graph),/Source support needed: Separate notice/);
});

test('stage source context retires active ink on an unrelated operation while preserving exact historical span identity',async()=>{
 const f=operationFixture(),open=f.seal('source.open',{type:'source',id:'source'},{...f.descriptor,text:f.sourceText,text_sha256:sha(f.sourceText)});await ui.checkedOperation(open,f.trace,f.baseline);
 const quote='A tenant reports a cold home.',chars=Array.from(f.sourceText),start_char=chars.join('').indexOf('A tenant')-1,pin={artifact_id:'source',sha256:f.descriptor.sha256,text_sha256:sha(f.sourceText),offset_unit:'unicode_code_point',start_char,end_char:start_char+Array.from(quote).length,quote};
 const read=f.seal('phrase.match',{type:'source',id:'source'},{matched:true},pin);await ui.checkedOperation(read,f.trace,f.baseline);f.trace.current=read;f.trace.displaySource={artifact_id:'source',pin,id:read.id};assert.match(ui.operationReadingMarkup(f.trace,true),/data-au-operation-span/);
 f.trace.current={id:'current-condition',kind:'condition.evaluate',object:{type:'condition',id:'cold'},cause_ids:[],result:{verdict:true}};const html=ui.operationReadingMarkup(f.trace,true);assert.doesNotMatch(html,/<mark|data-au-operation-span=/);assert.match(html,new RegExp(`data-au-operation-read-context="${read.id}"`));assert.match(html,/A tenant reports a cold home/);assert.match(html,new RegExp(`data-au-source-origin="operation:${read.id}"`));
});
test('stage clauses retain Unicode offsets and match their factual meaning rather than a nearby convenient number',()=>{
 const quote='On the recorded morning a calibrated instrument measured the living room at15.8C. The fixed pump is outside ordinary small tenant maintenance. No tenant alteration or misuse explains the failure.',pin={artifact_id:'source',start_char:2,end_char:2+Array.from(quote).length,quote};
 const op=id=>({kind:'fact.extract',object:{id},result:{},source:pin});const bounded=ui.stageFactSpan(op('outside_small_tenant_maintenance_and_no_tenant_cause'));assert.match(bounded.quote,/outside ordinary small tenant maintenance/);assert.match(bounded.quote,/No tenant alteration or misuse/);assert.doesNotMatch(bounded.quote,/15\.8C/);
 assert.equal(Array.from('😀 '+quote).slice(bounded.start_char,bounded.end_char).join(''),bounded.quote);
 const unknown=ui.stageFactSpan(op('issuer_authority_and_received_packet'));assert.equal(unknown,pin,'an unknown compound meaning retains the full native citation');
 const tenancy={...pin,quote:'I rent this dwelling under an indefinite residential lease. Current monthly net rent is CHF1800; the landlord maintains the fixed heating.'};const scope=ui.stageFactSpan({...op('residential_tenancy_scope'),source:tenancy});assert.match(scope.quote,/residential lease/);assert.doesNotMatch(scope.quote,/CHF1800/);
 assert.match(ui.stageFactSpan({...op('fact:tenancy_terms_evidence'),source:tenancy}).quote,/CHF1800/);
});
test('stage attention coalesces calculation churn and identical cited reads without dropping or reordering History',()=>{
 const trace={visibleResults:new Map(),sources:new Map(),rows:[]};for(const kind of ['condition.evaluate','node.evaluate','dependency.evaluate','verification.check','span.read'])assert.equal(ui.operationAttention({kind},trace),false);
 const operation={id:'observed-match',kind:'phrase.match',object:{type:'source',id:'source'},result:{matched:true},source:{start_char:5,end_char:30,quote:'the actual cited phrase'}};trace.rows.push(operation);assert.equal(ui.operationAttention(operation,trace),false,'the exact matched phrase is checked without a separate visible dwell');const repeat={...operation,id:'later-observed-match'};trace.rows.push(repeat);assert.equal(ui.operationAttention(repeat,trace),false);assert.deepEqual(trace.rows.map(row=>row.id),['observed-match','later-observed-match']);
});
test('operation scrubbing uses only the preceding verified checkpoint and exact prior evaluation scope',async()=>{
 const f=workingFixture(),original=structuredClone(f.baseline),inspect=f.inspect({family_home:{verdict:'true'}});await ui.checkedOperation(inspect,f.trace,f.baseline);ui.applyWorkingOperation(inspect,f.trace,f.baseline);
 const scope={graph_sha256:f.graph.graph_sha256,evaluation_sha256:inspect.result.evaluation_sha256},node=f.seal('node.evaluate',{type:'node',id:'branch'},scope,{...scope,phase:'provisional',activation:'true',execution_state:'blocked',blocked_by:['start']},[inspect.id]);await ui.checkedOperation(node,f.trace,f.baseline);ui.applyWorkingOperation(node,f.trace,f.baseline);
 f.trace.checkpoints=[{after_operation:0,state:f.baseline,projection:{},events:f.journal.slice(0,3),revision:3,state_sha256:f.baseline.state_sha256},{after_operation:2,state:f.head,projection:{},events:f.journal,revision:4,state_sha256:f.head.state_sha256}];f.trace.current=node;
 const view=ui.operationInspection(f.trace,0);assert.equal(view.state,f.baseline);assert.equal(view.trace.current,inspect);assert.equal(view.trace.rows.length,1);assert.equal(view.trace.working.nodes.size,0,'later native results cannot color an earlier scope');assert.equal(view.checkpoint.revision,3);assert.equal(f.trace.current,node);assert.equal(f.trace.transportState,null);assert.deepEqual(f.baseline,original);
 assert.equal(ui.operationInspection(f.trace,-1),null);assert.equal(ui.operationInspection(f.trace,2),null);
});
test('stage opening keeps a known original quiet and its complete map preserves accepted completion only on exact graph identity',async()=>{
 const f=workingFixture(),state={...f.baseline,message:'The original incoming message.'},inspect=f.inspect({});await ui.checkedOperation(inspect,f.trace,state);ui.applyWorkingOperation(inspect,f.trace,state);f.trace.current=inspect;
 const matching={...state,graph:f.graph};const html=ui.operationStageMarkup(matching,{},'start',f.trace);assert.match(html,/>✓</);assert.doesNotMatch(html,/Provisional applicability|Provisional working step|Working model|Inspect calculation/);
 const different=ui.operationStageMarkup({...state,graph:{...state.graph,graph_sha256:sha('different exact graph')}},{},'start',f.trace);assert.doesNotMatch(different,/data-status="completed"|>✓</);
 f.trace.current={id:'before-source',kind:'document.require',object:{type:'document',id:'notice'},result:{},cause_ids:[]};assert.doesNotMatch(ui.operationStageMarkup(state,{},'start',f.trace),/The original incoming message/,'the map starts without a whole-message reading panel');
 const source={text:'Synthetic demonstration document (fictional)\nSource date: 2025-02-21\nReview as-of: 2025-02-21\n\nActual substantive body with a Unicode 😀 character.'};const body=ui.sourceBodySpan(source);assert.equal(Array.from(source.text).slice(body.start_char,body.end_char).join(''),body.quote);assert.equal(body.quote,'Actual substantive body with a Unicode 😀 character.');
});

test('stage transport uses a bound total without granting access to future unverified operations',()=>{
 const f=operationFixture(),trace={binding:f.binding,rows:Array.from({length:3},(_,i)=>({id:`real-${i}`})),sources:new Map(),current:{id:'real-1',kind:'condition.evaluate',object:{type:'condition',id:'cold'},cause_ids:[],result:{}},buffer:{result:{contract:operationContract,exact_output_verified:true,state_sha256:f.binding.current_state_sha256,current_event_sha256:f.binding.current_event_sha256,operation_count:824}}};
 assert.equal(ui.bufferedOperationCount(trace),824);const html=ui.workMarkup(f.baseline,{},'branch',[],'step',{}, {mode:'replay',operations:trace,playing:true});assert.match(html,/max="823"/);assert.match(html,/>2 \/ 824</);assert.doesNotMatch(html,/ \/ Synthetic claim/);assert.equal(ui.operationInspection(trace,823),null);
 for(const invalid of [{operation_count:4097},{operation_count:2.5},{exact_output_verified:false},{state_sha256:sha('different head')},{current_event_sha256:sha('different event')}]) assert.equal(ui.bufferedOperationCount({...trace,buffer:{result:{...trace.buffer.result,...invalid}}}),null);
});
test('stage excerpts stay compact while full source inspection retains every original Unicode character and exact document labels',async()=>{
 const f=operationFixture(),open=f.seal('source.open',{type:'source',id:'source'},{...f.descriptor,text:f.sourceText,text_sha256:sha(f.sourceText)});await ui.checkedOperation(open,f.trace,f.baseline);f.trace.current=open;const markup=ui.operationReadingMarkup(f.trace);assert.match(markup,/A tenant reports a cold home/);const compact=ui.operationReadingMarkup(f.trace,true);assert.match(compact,/data-au-compact-excerpt/);assert.doesNotMatch(compact,/data-au-source-body-anchor/);
 const state={...f.baseline,facts:[{fact_id:'relevant_tenancy_terms',label:'Relevant residential tenancy terms, parties and dwelling; this is not a complete lease contract'}],obligations:[{document_type:'tenancy_terms',required_fact_ids:['relevant_tenancy_terms']}],graph:{...f.baseline.graph,document_catalog:[{document_type:'tenancy_terms',label:'Relevant tenancy terms'}]}};f.trace.current={id:'actual-accepted-fact',kind:'fact.extract',object:{id:'relevant_tenancy_terms'},result:{verification_required:false},source:{artifact_id:'source',start_char:0,end_char:30,quote:'Monthly net rent is CHF1800.'}};f.trace.dockedFacts=new Map([[f.trace.current.object.id,{operation:f.trace.current,node:'branch',observed:true}]]);const html=ui.operationStageMarkup(state,{},'branch',f.trace);assert.match(html,/aria-label="Relevant tenancy terms:/);assert.doesNotMatch(html,/<strong>Relevant residential tenancy terms/);
});

test('compact unknown findings use a short literal Unicode subspan while inspection preserves the complete native pin',()=>{
 const text='😀 The complete recorded delivery packet includes the letter, envelope and sender attestation. The source remains available in full.',pin={artifact_id:'packet',start_char:12,end_char:12+Array.from(text).length,quote:text},op={kind:'fact.extract',object:{id:'issuer_authority_and_received_packet'},source:pin};const compact=ui.stageFactSpan(op,true);assert.equal(ui.stageFactSpan(op),pin);assert.equal(compact.quote,'😀 The complete recorded delivery packet includes the letter, envelope and sender attestation.');assert.equal(Array.from(pin.quote).slice(compact.start_char-pin.start_char,compact.end_char-pin.start_char).join(''),compact.quote);assert.ok(compact.end_char<pin.end_char);assert.match(compact.quote,/attestation\.$/,'an unknown legal predicate keeps a complete actual clause rather than an arbitrary word count');
});
test('an actually checked stage document receives a named source card inside its existing requirement landing',()=>{
 const f=operationFixture(),source={...f.descriptor,file_name:'01-delivery-attestation.txt',text:f.sourceText,text_sha256:sha(f.sourceText)},pin={artifact_id:source.artifact_id,start_char:0,end_char:20,quote:Array.from(source.text).slice(0,20).join('')},required={id:'actual-require',kind:'document.require',object:{id:'notice'},result:{activation:'true',active_node_ids:['branch']}},check={id:'actual-check',kind:'document.check',object:{id:'notice'},source:pin,result:{assessment:'sufficient'}};
 const state={...f.baseline,evaluation:{...f.baseline.evaluation,documents:[{document_type:'notice',review_state:'sufficient'}]},obligations:[{document_type:'notice',required_fact_ids:[]}]},node={node_id:'branch',document_types:['notice']},trace={rows:[required,check],current:check,sources:new Map([[source.artifact_id,source]])};const html=ui.stageNodeContents(node,state,trace,null,false);assert.match(html,/au-stage-landing/);assert.match(html,/au-stage-source-name">Delivery attestation/);assert.match(html,/data-au-check-operation="actual-check"/);assert.match(html,/data-au-document-checked="true"/);assert.match(html,/Source checked/);
 assert.doesNotMatch(ui.stageNodeContents(node,state,{...trace,rows:[required]},null,false),/au-stage-source-name|data-au-check-operation/,'accepted sufficiency cannot replace an absent observed check in operation delivery');const planned=ui.stageNodeContents(node,state,{...trace,rows:[check]},null,false);assert.match(planned,/data-au-document-planned="true"/);assert.doesNotMatch(planned,/data-au-check-operation|data-au-document-checked="true"/,'a check cannot activate an unobserved requirement or fill its planned slot');
});

test('a stage fact lifts the same exact compact Unicode subspan that carries its source ink',()=>{
 const quote='I, Riley Foster, am the tenant under an indefinite ordinary residential lease. Current monthly net rent is CHF1800; the landlord maintains the fixed central heating and circulation pump.',source={artifact_id:'checked-source',file_name:'01-tenancy-clarification.txt',text:'😀 '+quote},pin={artifact_id:source.artifact_id,start_char:2,end_char:2+Array.from(quote).length,quote},op={id:'native-tenancy-fact',kind:'fact.extract',object:{type:'fact',id:'fact:tenancy_terms_evidence'},source:pin,result:{verification_required:false},cause_ids:[]},trace={current:op,rows:[op],sources:new Map([[source.artifact_id,source]])},compact=ui.stageFactSpan(op,true),html=ui.operationReadingMarkup(trace,true);assert.equal(compact.quote,'CHF1800');assert.match(html,new RegExp(`data-au-operation-start-char="${compact.start_char}" data-au-operation-end-char="${compact.end_char}"`));assert.match(html,/>CHF1800<\/mark>/);assert.equal(Array.from(source.text).slice(compact.start_char,compact.end_char).join(''),compact.quote);assert.equal(ui.operationReading(trace).pin,pin,'the full native inspection citation remains unchanged');
 trace.current={...op,id:'native-matched-phrase',kind:'phrase.match',result:{matched:true}};assert.match(ui.operationReadingMarkup(trace,true),/>monthly net rent is CHF1800; the landlord maintains the fixed central heating and circulation pump.<\/mark>/,'ordinary cited reading retains its longer native meaning clause');
});

test('an early planned rail comes only from the complete current-run pinned catalog and carries no accepted prefix state',async()=>{
 const catalog={nodes:[{node_id:'start',label:'Read the supplied packet'},{node_id:'review',label:'Assess the source'},{node_id:'alternative',label:'Assess the alternative route'}],documents:[{document_type:'notice',label:'Received notice',required_at_node_ids:['review']}],transitions:[{edge_id:'main',source_node_id:'start',target_node_id:'review'},{edge_id:'alternative-route',source_node_id:'start',target_node_id:'alternative'}]},pack={family:'test_family',template_sha256:sha('exact full template'),process_catalog:catalog};
 const graph={claim_id:'planned-case',family:pack.family,graph_sha256:sha('exact head graph'),nodes:catalog.nodes.map(node=>({...node,completed:true,document_types:node.node_id==='review'?['notice']:[]})),edges:catalog.transitions.map(edge=>({...edge,condition:{const:'false'},validation:{status:'validated'}})),document_catalog:[{document_type:'notice',label:'Received notice',held_files:['future-source']}]};
 const head={claim_id:graph.claim_id,run_id:'current-workflow',revision:12,state_sha256:sha('head state'),last_event_sha256:sha('head event'),graph,semantic_contexts:{'current-workflow':{claim_id:graph.claim_id,rule_packs:[pack],compatible_knowledge:[]}},knowledge_uses:[],facts:[{fact_id:'future-fact'}],obligations:[{document_type:'notice'}],outcome:{summary:'Future accepted outcome'},evaluation:{nodes:graph.nodes.map(node=>({node_id:node.node_id,execution_state:'completed'}))}};
 const before=JSON.stringify(head),plan=await ui.plannedOperationProcess(head);assert.equal(plan.graph.nodes.length,3);assert.equal(plan.graph.edges.length,2);assert.equal(plan.procedure,null);assert.deepEqual(plan.evaluation,{nodes:[],edges:[],documents:[]});assert.deepEqual(plan.facts,[]);assert.deepEqual(plan.obligations,[]);assert.doesNotMatch(JSON.stringify(plan),/completed|future-source|future-fact|Future accepted outcome|validated|"condition"/);
 const prefix={...head,revision:0,state_sha256:sha('opening'),graph:{family:'incoming_packet',nodes:[],edges:[]},facts:[],obligations:[],evaluation:{nodes:[],documents:[]},outcome:null,message:'The actual original message.'},trace={plannedProcess:plan,rows:[],sources:new Map(),current:null};
 const html=ui.operationStageMarkup(prefix,{},'start',trace);assert.equal((html.match(/data-au-planned-node disabled/g)||[]).length,3);assert.match(html,/data-au-planned-authority="none"/);assert.match(html,/Recorded procedure · planned steps/);assert.match(html,/data-au-stage-document="notice"[^>]*data-au-document-active="false"[^>]*data-au-document-checked="false"/);assert.doesNotMatch(html,/data-au-stage-fact=|data-status="completed"|>✓<|Future accepted outcome/);assert.equal(ui.operationStageGraph(trace,prefix),plan.graph);
 for(const change of [copy=>copy.graph.nodes.pop(),copy=>copy.graph.edges.pop(),copy=>copy.graph.nodes[1].document_types=[],copy=>copy.graph.nodes[0].label='Pruned or changed meaning',copy=>copy.semantic_contexts['current-workflow'].claim_id='another-case']){const copy=structuredClone(head);change(copy);assert.equal(await ui.plannedOperationProcess(copy),null);}
 const use={workflow_id:head.run_id,knowledge_id:'procedure.test_family',version:2,rule_pack_sha256:pack.template_sha256,definition_sha256:sha('exact reused definition'),knowledge_sha256:sha('exact reused publication')};
 const reused=structuredClone(head);reused.knowledge_uses=[{...use,workflow_id:'old-workflow',version:99},use];reused.semantic_contexts[head.run_id].compatible_knowledge=[{...use}];const reusedPlan=await ui.plannedOperationProcess(reused);assert.equal(reusedPlan.procedure.version,2);const linked=ui.operationStageMarkup(prefix,{},null,{...trace,plannedProcess:reusedPlan});assert.match(linked,/data-au-knowledge="procedure.test_family" data-au-version="2"/);assert.ok(linked.includes(`data-au-knowledge-sha="${use.knowledge_sha256}" data-au-definition-sha="${use.definition_sha256}"`));assert.match(linked,/>Procedure test family · Version 2<\/button>/);assert.doesNotMatch(linked,/Recorded procedure · planned steps/);
 for(const field of ['rule_pack_sha256','knowledge_sha256','version']){const copy=structuredClone(reused);copy.semantic_contexts[head.run_id].compatible_knowledge[0][field]=field==='version'?3:sha('other version');assert.equal(await ui.plannedOperationProcess(copy),null);}
 assert.equal(JSON.stringify(head),before);
});

test('native cited reads stay inspectable without separate dwell before an actual consequence',()=>{
 const source={text:'😀 A literal cited passage and remaining source.'},pin={artifact_id:'source',start_char:4,end_char:24,quote:Array.from(source.text).slice(4,24).join('')},trace={sources:new Map([['source',source]]),visibleResults:new Map(),rows:[]};
 const read={id:'actual-span-read',kind:'span.read',object:{type:'source',id:'source'},result:{},source:pin};assert.equal(ui.operationAttention(read,trace),false);assert.equal(ui.operationAttention({...read,id:'same-passage-later'},trace),false);assert.equal(ui.operationAttention({...read,source:{...pin,start_char:0,end_char:Array.from(source.text).length,quote:source.text}},trace),false);assert.equal(ui.operationAttention({...read,source:{...pin,artifact_id:'unopened-source'}},trace),false);assert.equal(ui.operationReadDuration(read),700);
});

test('a cited decision retires source ink when the visible stage pulls back to its map and outcome',()=>{
 const f=operationFixture(),source={artifact_id:'source',text:f.sourceText},pin={artifact_id:'source',start_char:0,end_char:6,quote:'Before'},fact={id:'actual-cited-fact',kind:'fact.extract',object:{type:'fact',id:'fact:notice'},source:pin,result:{verification_required:true},cause_ids:[]},trace={rows:[fact],current:fact,sources:new Map([['source',source]])};
 assert.equal(ui.operationReading(trace).active,true);assert.match(ui.operationReadingMarkup(trace,true),/data-au-operation-span="actual-cited-fact"/);
 const decision={...fact,id:'actual-cited-decision',kind:'decision',result:{summary:'The actual recorded decision.'}},before=JSON.stringify(f.baseline);trace.rows.push(decision);trace.current=decision;
 assert.equal(ui.operationReading(trace).active,false);assert.equal(ui.operationReading(trace).pin,pin,'decision inspection retains the exact native citation');const html=ui.operationStageMarkup(f.baseline,{},'branch',trace);assert.match(html,/data-au-stage-phase="map"/);assert.match(html,/The actual recorded decision\./);assert.doesNotMatch(html,/<mark(?:\s|>)|data-au-operation-span=/);assert.doesNotMatch(html,/au-stage-source-title|data-au-operation-read-context="actual-cited-decision"/,'the actual map and outcome take the full stage while the native decision citation remains inspectable');assert.equal(JSON.stringify(f.baseline),before);
});

test('a real provisional document fact can dock as an observed quote on a planned node without accepted facts or requirements',()=>{
 const f=operationFixture(),pin={artifact_id:'source',start_char:0,end_char:6,quote:'Before'},operation={id:'observed-real-operation',seq:1,kind:'fact.extract',object:{type:'fact',id:'fact:notice'},input:{document_type:'notice'},result:{verification_required:true,status:'provisional'},source:pin,cause_ids:[]};
 const graph={...f.baseline.graph,family:'actual-recorded-family',nodes:[{node_id:'branch',label:'Assess the received notice',document_types:['notice']}],edges:[],document_catalog:[{document_type:'notice',label:'Received notice'}]},state={...f.baseline,graph:{family:'incoming_packet',nodes:[],edges:[]},facts:[],obligations:[],evaluation:{nodes:[],documents:[]}},trace={plannedProcess:{claim_id:state.claim_id,graph,head_state_sha256:sha('verified head'),head_revision:9,rule_pack_sha256:sha('pinned rulepack'),procedure:null},rows:[operation],current:operation,sources:new Map(),dockedFacts:new Map([['fact:notice',{operation,node:'branch',observed:true}]])};
 const before=JSON.stringify(state);assert.equal(ui.operationNodeId(operation,graph,state),'branch');assert.equal(ui.operationNodeId({...operation,object:{type:'fact',id:'unmapped-legal-predicate'},input:{rule_refs:['CO:259']}},graph,state),null,'a rule citation cannot invent a predicate-to-node association');
 const html=ui.operationStageMarkup(state,{},null,trace);assert.match(html,/data-au-fact-state="observed"/);assert.match(html,/data-au-fact-operation="observed-real-operation"/);assert.match(html,/data-status="planned"/);assert.match(html,/>Before<\/span>/);assert.match(html,/data-au-document-planned="true"[^>]*data-au-document-checked="false"/);assert.doesNotMatch(html,/au-stage-finding|data-status="completed"|data-au-fact-state="accepted"|>✓</);assert.equal(ui.operationRecord(trace,'operation',operation.id),operation);assert.equal(JSON.stringify(state),before);
 trace.checkpoints=[{after_operation:0,state,projection:{},events:[]}];assert.equal(ui.operationInspection(trace,0).trace.dockedFacts.get('fact:notice').observed,true);assert.equal(ui.operationInspection(trace,-1),null);
});

test('stage document history follows the latest observed requirement and never borrows a future checked source',()=>{
 const f=operationFixture(),source={...f.descriptor,text:f.sourceText,text_sha256:sha(f.sourceText)},pin={artifact_id:source.artifact_id,start_char:0,end_char:6,quote:'Before'},node={node_id:'branch',document_types:['notice']};
 const state={...f.baseline,evaluation:{...f.baseline.evaluation,documents:[{document_type:'notice',review_state:'sufficient'}]}};
 const requirement={id:'required-first',seq:1,kind:'document.require',object:{id:'notice'},result:{activation:'true',active_node_ids:['branch']},cause_ids:[]},check={id:'checked-first',seq:2,kind:'document.check',object:{id:'notice'},source:pin,result:{assessment:'sufficient'},cause_ids:['required-first']};
 const trace={rows:[requirement],sources:new Map([[source.artifact_id,source]]),current:requirement,checkpoints:[{after_operation:0,state,projection:{},events:[]}]};
 assert.doesNotMatch(ui.stageNodeContents(node,state,trace,null),/data-au-check-operation|data-au-document-checked="true"/);
 trace.rows.push(check);assert.match(ui.stageNodeContents(node,state,trace,null),/data-au-check-operation="checked-first"/);
 trace.rows.push({...requirement,id:'requirement-excluded',result:{activation:'false',active_node_ids:[]}});
 const excluded=ui.stageNodeContents(node,state,trace,null);assert.match(excluded,/data-au-document-active="false"/);assert.doesNotMatch(excluded,/data-au-check-operation|data-au-document-checked="true"/,'a later excluded requirement returns to a quiet empty planned slot');
 const earlier=ui.operationInspection(trace,0);
 assert.match(ui.stageNodeContents(node,state,earlier.trace,null),/data-au-stage-document="notice"/);
 assert.doesNotMatch(ui.stageNodeContents(node,state,earlier.trace,null),/data-au-check-operation|data-au-document-checked="true"/,'scrubbing cannot borrow a later observed check');
 trace.rows.push({...requirement,id:'required-again'});assert.match(ui.stageNodeContents(node,state,trace,null),/data-au-operation-id="required-again"/);
 assert.deepEqual([...ui.operationHistoryMarkup({...trace,binding:f.binding}).matchAll(/data-au-record-id="([^"]+)"/g)].map(row=>row[1]),['required-again','requirement-excluded','checked-first','required-first']);
 assert.deepEqual(trace.rows.map(row=>row.id),['required-first','checked-first','requirement-excluded','required-again']);
});

test('observed source-context docking requires preceding native causal ancestry and one exact document destination',()=>{
 const source={artifact_id:'original',sha256:sha('original bytes'),text_sha256:sha('original text')},pin={...source,start_char:4,end_char:16,quote:'actual words'},graph={nodes:[{node_id:'notice-step',document_types:['notice']},{node_id:'other-step',document_types:['other']}],edges:[]},accepted={facts:[],obligations:[],graph:{family:'incoming_packet'}};
 const open={id:'native-open',kind:'source.open',object:{type:'source',id:source.artifact_id},result:source,cause_ids:[]},match={id:'native-match',kind:'phrase.match',object:{type:'source',id:source.artifact_id},source:pin,result:{matched:true},cause_ids:[open.id]},document={id:'native-document-fact',kind:'fact.extract',object:{type:'fact',id:'fact:notice'},input:{document_type:'notice'},source:pin,cause_ids:[match.id]},semantic={id:'native-observation',kind:'fact.extract',object:{type:'fact',id:'a-predicate-with-no-node-name'},input:{rule_refs:['actual-rule']},source:pin,cause_ids:[match.id]};
 const before=JSON.stringify(accepted),trace={rows:[open,match,document,semantic]};
 assert.equal(ui.operationNodeId(semantic,graph,accepted,trace),'notice-step','shared native phrase cause locates observed source context without guessing a predicate meaning');
 assert.equal(ui.operationNodeId(semantic,graph,accepted),null,'legal references alone cannot invent a node');
 const anotherMatch={...match,id:'native-different-span',source:{...pin,start_char:20,end_char:32},cause_ids:[open.id]},anotherObservation={...semantic,id:'native-adjacent-observation',source:anotherMatch.source,cause_ids:[anotherMatch.id]};
 trace.rows.push(anotherMatch,anotherObservation);assert.equal(ui.operationNodeId(anotherObservation,graph,accepted,trace),'notice-step','a different native match may share the unique already observed acquisition destination');
 const otherDocument={...document,id:'native-other-document',object:{type:'fact',id:'fact:other'},input:{document_type:'other'},cause_ids:[anotherMatch.id]};
 trace.rows.push(otherDocument,{...anotherObservation,id:'after-two-destinations'});
 assert.equal(ui.operationNodeId(trace.rows.at(-1),graph,accepted,trace),'other-step','the exact shared match takes precedence over a broader acquisition root');
 const thirdMatch={...anotherMatch,id:'third-native-match'},ambiguous={...semantic,id:'ambiguous-native-observation',cause_ids:[thirdMatch.id]};trace.rows.push(thirdMatch,ambiguous);
 assert.equal(ui.operationNodeId(ambiguous,graph,accepted,trace),null,'an acquisition with two distinct destinations cannot choose a consumer');
 const future={rows:[open,match,semantic,document]};assert.equal(ui.operationNodeId(semantic,graph,accepted,future),null,'even an available later fact cannot bind an earlier operation');
 for(const change of [{source:{...pin,artifact_id:'unrelated-source'}},{source:{...pin,sha256:sha('different bytes')}},{source:{...pin,text_sha256:sha('different text')}},{source:{...pin,sha256:undefined}},{cause_ids:['no-recorded-cause']}]){const unknown={...semantic,id:'unknown-'+JSON.stringify(change),...change},isolated={rows:[open,match,document,unknown]};assert.equal(ui.operationNodeId(unknown,graph,accepted,isolated),null);}
 assert.equal(JSON.stringify(accepted),before,'a source-context association changes no accepted fact or node');
});

test('only distinct actual consequences own visible dwell and every source operation retains its exact history identity',()=>{
 const trace={rows:[],sources:new Map(),visibleResults:new Map()},pin={artifact_id:'original',sha256:sha('source'),start_char:0,end_char:12,quote:'actual words'},sourceOps=['source.open','span.read','phrase.match','condition.evaluate','node.evaluate','dependency.evaluate','document.require','verification.check'].map((kind,index)=>({id:'native-source-'+index,kind,object:{type:'source',id:'original'},result:{matched:true,activation:'true',active_node_ids:['step']},source:pin,cause_ids:[]}));
 for(const operation of sourceOps){trace.rows.push(operation);assert.equal(ui.operationAttention(operation,trace),false,operation.kind);}
 const fact={id:'native-first-fact',kind:'fact.extract',object:{type:'fact',id:'actual-fact'},source:pin,result:{verification_required:true},cause_ids:[sourceOps[2].id]};trace.rows.push(fact);assert.equal(ui.operationAttention(fact,trace),true);
 const repeat={...fact,id:'native-verified-repeat',result:{verification_required:false,status:'established'}};trace.rows.push(repeat);assert.equal(ui.operationAttention(repeat,trace),false,'verification updates state without replaying the same handoff');
 const check={id:'native-sufficient-check',kind:'document.check',object:{type:'document',id:'notice'},source:pin,result:{assessment:'sufficient'},cause_ids:[]};trace.rows.push(check);assert.equal(ui.operationAttention(check,trace),true);assert.equal(ui.operationAttention({...check,id:'native-repeat-check'},trace),false);
 assert.deepEqual(trace.rows.map(row=>row.id),[...sourceOps.map(row=>row.id),fact.id,repeat.id,check.id]);assert.equal(ui.operationRecord(trace,'operation',sourceOps[2].id),sourceOps[2]);
});

test('compact stage excerpts preserve exact Unicode display bounds inside the unchanged full native citation',()=>{
 const text='Before 😀\r\nThe landlord records three reports. After unchanged original text.',chars=Array.from(text),start=chars.indexOf('T'),quote=chars.slice(start,start+42).join(''),source={artifact_id:'original',file_name:'03-original-notification.txt',text,text_sha256:sha(text)},pin={artifact_id:source.artifact_id,sha256:sha(text),text_sha256:sha(text),start_char:start,end_char:start+42,quote},operation={id:'native-bounded-fact',kind:'fact.extract',object:{type:'fact',id:'unknown-predicate'},source:pin,result:{verification_required:true},cause_ids:[]},trace={rows:[operation],current:operation,sources:new Map([[source.artifact_id,source]])};
 const html=ui.operationReadingMarkup(trace,true),display=ui.stageFactSpan(operation,true);assert.equal(chars.slice(display.start_char,display.end_char).join(''),display.quote);assert.ok(display.start_char>=pin.start_char&&display.end_char<=pin.end_char);assert.match(html,/03-original-notification\.txt/);assert.match(html,new RegExp(`data-au-citation-start-char="${pin.start_char}" data-au-citation-end-char="${pin.end_char}"`));assert.match(html,/data-au-compact-excerpt/);assert.doesNotMatch(html,/>Before 😀&#13;/);assert.equal(ui.operationReading(trace).pin,pin);assert.match(ui.operationReadingMarkup(trace),/Before 😀&#13;\n/);
});

test('recorded operation delivery is an explicit retained URL preference and legacy through links keep their revision',()=>{
 assert.equal(ui.operationRoutePreference('#autonomous/demonstration'),'live');assert.equal(ui.operationRoutePreference('#autonomous/demonstration?operations=recorded'),'recorded');assert.equal(ui.operationRoutePreference('#autonomous/demonstration','?journey=autonomous&operations=recorded'),'recorded');assert.equal(ui.operationRoutePreference('#autonomous/demonstration?operations=unknown'),'live');
 const fragment=ui.claimFragment('native-case',{mode:'replay',collection:'reference',operations:'recorded',through:28,detail:'step'}),params=new URLSearchParams(fragment.split('?')[1]);assert.equal(params.get('operations'),'recorded');assert.equal(params.get('through'),'28');assert.equal(params.get('mode'),'replay');assert.equal(params.get('collection'),'reference');assert.equal(ui.operationRoutePreference(fragment),'recorded');
 assert.equal(new URLSearchParams(ui.claimFragment('legacy-case',{mode:'replay',collection:'legacy',through:11}).split('?')[1]).get('through'),'11');assert.equal(ui.claimFragment('native-case',{mode:'replay',through:0}).includes('operations='),false,'default live delivery adds no override');
});

test('shared-source observations stay neutral when the one recorded document has multiple structural consumers',()=>{
 const source={artifact_id:'source',sha256:sha('source bytes'),text_sha256:sha('source text')},pin={...source,start_char:0,end_char:12,quote:'actual words'},open={id:'open',kind:'source.open',object:{id:'source'},result:source,cause_ids:[]},match={id:'match',kind:'phrase.match',cause_ids:['open']},document={id:'document-fact',kind:'fact.extract',object:{type:'fact',id:'fact:shared'},input:{document_type:'shared'},source:pin,cause_ids:['match']},observation={id:'observation',kind:'fact.extract',object:{type:'fact',id:'predicate'},source:pin,cause_ids:['match']},graph={nodes:[{node_id:'first',document_types:['shared']},{node_id:'second',document_types:['shared']}]};
 assert.equal(ui.operationNodeId(observation,graph,{facts:[],obligations:[]},{rows:[open,match,document,observation]}),null);
});

test('a pending observed handoff retains its phase through inspection and only actual accepted document support may fill a slot',()=>{
 const f=operationFixture(),pin={artifact_id:'source',start_char:0,end_char:6,quote:'Before'},operation={id:'pending-native-fact',kind:'fact.extract',object:{type:'fact',id:'fact:notice'},input:{document_type:'notice'},source:pin,result:{verification_required:true},cause_ids:[]},graph={...f.baseline.graph,nodes:[{node_id:'branch',document_types:['notice']}]},state={...f.baseline,graph},trace={rows:[operation],current:operation,sources:new Map(),dockPhases:new Map([[operation.id,'transfer']]),dockedFacts:new Map([[operation.object.id,{operation,node:'branch',observed:true}]]),checkpoints:[{after_operation:0,state,projection:{},events:[]}]};
 assert.match(ui.stageNodeContents(graph.nodes[0],state,trace,null),/data-au-fact-operation="pending-native-fact" data-au-dock-phase="transfer"/);
 assert.equal(ui.operationInspection(trace,0).trace.dockPhases.get(operation.id),'transfer','opening History cannot prematurely complete a pending transfer');
 assert.match(ui.stageNodeContents(graph.nodes[0],state,{...trace,finished:true},null),/data-au-dock-phase="landed"/,'a verified settled result presents its genuine observed and accepted support without animation');
 const required={id:'required',kind:'document.require',object:{id:'notice'},result:{activation:'true',active_node_ids:['branch']}},check={id:'checked',kind:'document.check',object:{id:'notice'},source:pin,result:{assessment:'sufficient'}},source={artifact_id:'source',file_name:'actual-original.txt',text:f.sourceText};
 const documents={rows:[required,check],current:check,sources:new Map([['source',source]]),dockPhases:new Map([[check.id,'read']])},accepted={...state,evaluation:{...state.evaluation,documents:[{document_type:'notice',review_state:'sufficient'}]}};
 const reading=ui.stageNodeContents(graph.nodes[0],accepted,documents,null);assert.match(reading,/data-au-document-supported="true" data-au-document-checked="false"/);assert.match(reading,/class="au-stage-thumbnail" data-au-dock-phase="read"/);
 assert.doesNotMatch(ui.stageNodeContents(graph.nodes[0],state,documents,null),/data-au-check-operation="checked"/,'a sufficient operation cannot borrow accepted document state from a later checkpoint');
 documents.dockPhases.set(check.id,'landed');assert.match(ui.stageNodeContents(graph.nodes[0],accepted,documents,null),/data-au-document-checked="true"/);
});

test('stage chips keep complete source phrases and bounded context starts at actual word and sentence boundaries',()=>{
 const text='The landlord is Synthetische Wohnraum AG. Current monthly net rent is CHF1800; the landlord maintains the fixed heating.',pin={artifact_id:'original',start_char:0,end_char:Array.from(text).length,quote:text},operation={id:'terms-fact',kind:'fact.extract',object:{type:'fact',id:'fact:tenancy_terms_evidence'},source:pin,result:{},cause_ids:[]},trace={current:operation,rows:[operation],sources:new Map([['original',{artifact_id:'original',file_name:'01-terms.txt',text}]])};
 const html=ui.operationReadingMarkup(trace,true);assert.match(html,/class="au-stage-excerpt-context">Current monthly net rent is CHF1800;/);assert.doesNotMatch(html,/class="au-stage-excerpt-context">(?:tische|che|Wohnraum)/);
 for(const [id,quote,expected] of [['residential_tenancy_scope','I am the tenant under an indefinite ordinary residential lease.','ordinary residential lease'],['landlord_first_knowledge',"We received the first report on2025-02-01; this is the landlord’s first documented knowledge.",'received the first report on2025-02-01'],['continuing_defect_without_remedy','We remain responsible; no lasting repair has yet occurred as of this acknowledgment.','no lasting repair has yet occurred'],['objective_use_impairment','Heating is inadequate for the contracted winter residential use of the principal living rooms.','Heating is inadequate']]){
  const full={...pin,start_char:2,end_char:2+Array.from(quote).length,quote},actual={...operation,object:{type:'fact',id},source:full},span=ui.stageFactSpan(actual,true);assert.equal(span.quote,expected);assert.equal(Array.from('😀 '+quote).slice(span.start_char,span.end_char).join(''),expected);assert.equal(actual.source,full);
 }
});

test('the same fact rereads changed source or meaning while verification-only repeats stay quiet',()=>{
 const pin={artifact_id:'source',sha256:sha('source'),text_sha256:sha('text'),start_char:0,end_char:12,quote:'actual words'},fact={id:'first',kind:'fact.extract',object:{type:'fact',id:'same-fact'},input:{document_type:'notice'},source:pin,result:{status:'provisional',verification_required:true,summary:'The actual observed meaning.'}},trace={visibleResults:new Map()};
 assert.equal(ui.operationAttention(fact,trace),true);assert.equal(ui.operationAttention({...fact,id:'verified',result:{...fact.result,status:'established',verification_required:false}},trace),false);
 for(const change of [{source:{...pin,artifact_id:'another-original'}},{source:{...pin,sha256:sha('changed bytes')}},{source:{...pin,text_sha256:sha('changed text')}},{source:{...pin,start_char:20,end_char:32}},{result:{...fact.result,summary:'The actual observed meaning has changed.'}},{result:{...fact.result,value:'another actual value'}}]){const independent={visibleResults:new Map()};ui.operationAttention(fact,independent);assert.equal(ui.operationAttention({...fact,id:'changed',...change},independent),true,JSON.stringify(change));}
});

test('an excerpt context remains inside the actual cited body and excludes source metadata headers',()=>{
 const header='Synthetic demonstration document (fictional)\nSource date: 2026-10-15\nReview as-of: 2026-10-15\n\n',quote='Current monthly net rent is CHF1800; the landlord maintains the fixed heating.',text=header+quote,start=Array.from(header).length,pin={artifact_id:'original',start_char:start,end_char:start+Array.from(quote).length,quote},operation={id:'actual-body-fact',kind:'fact.extract',object:{type:'fact',id:'fact:tenancy_terms_evidence'},source:pin,result:{},cause_ids:[]},trace={current:operation,rows:[operation],sources:new Map([['original',{artifact_id:'original',file_name:'01-original.txt',text}]])};
 const html=ui.operationReadingMarkup(trace,true),context=html.match(/class="au-stage-excerpt-context">([^<]*)<\/p>/)[1];assert.match(context,/^Current monthly net rent is CHF1800;/);assert.doesNotMatch(context,/Synthetic|Source date|Review as-of|2026-10-15/);assert.equal(ui.operationReading(trace).pin,pin);
});

test('a settled filled document slot has one source card while active delivery keeps its source preview and complete native inspection pin',()=>{
 const f=operationFixture(),source={...f.descriptor,file_name:'01-delivery-attestation.txt',text:f.sourceText,text_sha256:sha(f.sourceText)},pin={artifact_id:source.artifact_id,sha256:source.sha256,text_sha256:source.text_sha256,start_char:0,end_char:20,quote:Array.from(source.text).slice(0,20).join('')},required={id:'actual-require',kind:'document.require',object:{id:'notice'},result:{activation:'true',active_node_ids:['branch']}},check={id:'actual-check',kind:'document.check',object:{id:'notice'},source:pin,result:{assessment:'sufficient'}},fact={id:'actual-fact',kind:'fact.extract',object:{type:'fact',id:'fact:notice'},source:pin,result:{verification_required:false}},node={node_id:'branch',document_types:['notice']},state={...f.baseline,graph:{...f.baseline.graph,document_catalog:[{document_type:'notice',label:'Separate notice'}]},evaluation:{...f.baseline.evaluation,documents:[{document_type:'notice',review_state:'sufficient'}]},obligations:[{document_type:'notice',required_fact_ids:[]}]},trace={rows:[required,check,fact],current:check,finished:true,sources:new Map([[source.artifact_id,source]]),dockedFacts:new Map([[fact.object.id,{operation:fact,node:node.node_id,observed:true}]])};
 const settled=ui.stageNodeContents(node,state,trace,null,true),active=ui.stageNodeContents(node,state,{...trace,finished:false},null,false),slot=settled.slice(settled.indexOf('<div class="au-stage-slot"'));
 assert.equal((slot.match(/class="au-stage-thumbnail"/g)||[]).length,1);assert.equal((slot.match(/class="au-stage-source-name"/g)||[]).length,1);assert.match(slot,/data-au-document-checked="true"/);assert.match(slot,/data-au-check-operation="actual-check"/);assert.ok(slot.includes('data-au-citation="'+JSON.stringify(pin).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;').replaceAll('>','&gt;')+'"'));assert.match(slot,/Source checked/);assert.doesNotMatch(slot,/au-stage-paper|<span>Separate notice<\/span>/);assert.match(settled,/data-au-stage-fact="fact:notice"/);
 assert.match(active,/<span>Separate notice<\/span>/);assert.match(active,/au-stage-paper/);assert.equal(ui.operationRecord(trace,'operation',check.id).source,pin);
});

test('an uncited knowledge consequence cannot bring retained source context above the map while exact History and cited inspection remain available',()=>{
 const f=operationFixture(),pin={artifact_id:'source',sha256:f.descriptor.sha256,text_sha256:sha(f.sourceText),start_char:0,end_char:6,quote:'Before'},source={...f.descriptor,text:f.sourceText,text_sha256:pin.text_sha256},fact={id:'actual-cited-fact',kind:'fact.extract',object:{type:'fact',id:'fact:notice'},source:pin,result:{verification_required:true},cause_ids:[]},reuse={id:'actual-uncited-reuse',kind:'knowledge.reuse',object:{type:'knowledge',id:'procedure.actual'},input:{},result:{version:1},cause_ids:[]},trace={state:f.baseline,rows:[fact,reuse],current:reuse,sources:new Map([['source',source]]),displaySource:{artifact_id:'source',pin,id:fact.id}};
 const stage=ui.operationStageMarkup(f.baseline,{},'branch',trace);assert.match(stage,/data-au-graph/);assert.doesNotMatch(stage,/au-stage-source-title|au-stage-unbound-source|data-au-compact-excerpt/,'an uncited current step has no stale excerpt before its map');
 const history=ui.operationReadingMarkup(trace);assert.match(history,/data-au-operation-read-context="actual-cited-fact"/);assert.match(history,/>Before<\/span> 😀&#13;\nA tenant reports a cold home\. Zürich\./);assert.equal(ui.operationRecord(trace,'operation',fact.id).source,pin);
 const inspection={...trace,current:fact,inspection:true};assert.match(ui.operationStageMarkup(f.baseline,{},'branch',inspection),/data-au-operation-span="actual-cited-fact"/,'an intentionally inspected actual citation keeps its exact stage excerpt');assert.equal(ui.operationReading(inspection).pin,pin);
});

test('verified operation batches yield to a browser task at the time budget without changing native checks or order',async()=>{
 const f=operationFixture(),before=JSON.stringify(f.baseline),budget={started:0};let clock=0,yields=0,gates=0;
 const runtime={performance:{now:()=>clock},scheduler:{async yield(){yields++;assert.equal(f.trace.rows.length,3,'the third native operation has already passed its hash and chain checks');}},setTimeout(){assert.fail('native scheduler takes precedence');}};
 for(let index=0;index<5;index++){const operation=f.seal('condition.evaluate',{type:'node',id:'branch'},{verdict:'unresolved'});await ui.checkedOperation(operation,f.trace,f.baseline);clock+=4;assert.equal(await ui.operationFrameYield(budget,runtime,()=>true,async()=>{gates++;return true;}),true);}
 assert.equal(yields,1);assert.equal(gates,1);assert.deepEqual(f.trace.rows.map(row=>row.seq),[1,2,3,4,5]);assert.equal(JSON.stringify(f.baseline),before);
 const invalid=f.seal('condition.evaluate',{type:'node',id:'branch'},{verdict:'unresolved'});invalid.result.verdict='false';clock+=4;
 await assert.rejects(async()=>{await ui.checkedOperation(invalid,f.trace,f.baseline);await ui.operationFrameYield(budget,runtime,()=>true,async()=>true);},/identity check/);assert.equal(yields,1,'a rejected frame never reaches the between-frame yield');assert.equal(f.trace.rows.length,5);
});

test('the browser-task fallback waits for pause inspection and visibility gates before resuming verified frames',async()=>{
 let releaseTask,releaseGate,paused=true,hidden=true,settled=false,tasks=0;const budget={started:0},runtime={performance:{now:()=>12},setTimeout(resolve,delay){tasks++;assert.equal(delay,0);releaseTask=resolve;}};
 const pending=ui.operationFrameYield(budget,runtime,()=>true,async()=>{while(paused||hidden)await new Promise(resolve=>{releaseGate=resolve;});return true;}).then(value=>{settled=true;return value;});
 assert.equal(tasks,1);assert.equal(settled,false);releaseTask();await settle();assert.equal(settled,false,'input can hold the continuation while its browser task is yielded');assert.equal(typeof releaseGate,'function');paused=false;hidden=false;releaseGate();assert.equal(await pending,true);assert.equal(budget.started,12);
});

test('a yielded operation batch cannot continue after abort stale route or inspection-gate cancellation',async()=>{
 for(const cancelAt of ['before-task','during-task','during-gate']){
  let active=cancelAt!=='before-task',tasks=0,gates=0;const budget={started:0},runtime={performance:{now:()=>12},scheduler:{async yield(){tasks++;if(cancelAt==='during-task')active=false;}}};
  assert.equal(await ui.operationFrameYield(budget,runtime,()=>active,async()=>{gates++;if(cancelAt==='during-gate')active=false;return active;}),false,cancelAt);assert.equal(tasks,cancelAt==='before-task'?0:1);assert.equal(gates,cancelAt==='during-gate'?1:0);
 }
});

test('release procedure embedded data regenerates exactly from policy profile and immutable source bytes',()=>{
 const path=require('node:path'),{execFileSync}=require('node:child_process'),root=path.resolve(__dirname,'..'),python=process.env.CASEPATH_PYTHON||path.join(root,'.runtime/casepath-dev-v2/venv/bin/python');
 const script="#!/usr/bin/env python3\n\"\"\"Read-only canonical release DTO derivation; stdout only, no journal or head.\"\"\"\nimport hashlib\nimport json\nfrom pathlib import Path\nimport sys\n\n\ndef generate(root):\n    root = Path(root).resolve()\n    sys.path.insert(0, str(root / 'casepath-api'))\n    from casepath_api.autonomous_reference_policy_v1 import bounded_reference_policy, SCOPES\n    from casepath_api.workspace_corpus import canonical_json_bytes, digest_value\n\n    sha = lambda raw: hashlib.sha256(raw).hexdigest()\n    profile_root = root / 'casepath-api/casepath_api/reference_profiles/synthetic-nine-v2'\n    profile_raw = (profile_root / 'profile.json').read_bytes()\n    profile = json.loads(profile_raw)\n    base_path = root / 'casepath-api/casepath_api/corpora/synthetic-150/policy/static-rule-templates-v3.json'\n    base = json.loads(base_path.read_bytes())\n    policy = bounded_reference_policy(base)\n    catalogs = []\n    for template in policy['templates']:\n        catalog = template['process_catalog']\n        catalogs.append({\n            'family': template['domain'],\n            'rule_pack_sha256': digest_value(template),\n            'nodes': [{\n                'node_id': node['node_id'], 'label': node['label'],\n                'document_types': [doc['document_type'] for doc in catalog['documents']\n                                   if node['node_id'] in doc['required_at_node_ids']],\n            } for node in catalog['nodes']],\n            'transitions': [{\n                'edge_id': edge['edge_id'], 'source_node_id': edge['source_node_id'],\n                'target_node_id': edge['target_node_id'],\n            } for edge in catalog['transitions']],\n            'documents': [{\n                'document_type': doc['document_type'], 'label': doc['label'],\n                'required_at_node_ids': doc['required_at_node_ids'],\n            } for doc in catalog['documents']],\n        })\n    claims = []\n    for claim_id, entry in profile['claims'].items():\n        matches = []\n        for source in entry['sources']:\n            raw = (profile_root / claim_id / source['file_name']).read_bytes()\n            if sha(raw) != source['sha256'] or len(raw) != source['size_bytes']:\n                raise ValueError('release source bytes differ: ' + claim_id)\n            text = raw.decode('utf-8')\n            for family, scope in SCOPES.items():\n                start = text.find(scope['request'])\n                if start >= 0:\n                    matches.append({\n                        'family': family, 'file_name': source['file_name'],\n                        'source_sha256': source['sha256'], 'text_sha256': sha(text.encode('utf-8')),\n                        'offset_unit': 'unicode_code_point', 'start_char': start,\n                        'end_char': start + len(scope['request']), 'quote': scope['request'],\n                    })\n        if len(matches) != 1:\n            raise ValueError('release request must have one exact source match: ' + claim_id)\n        claims.append({\n            'claim_id': claim_id, 'family': matches[0]['family'],\n            # The legacy profile key names the corpus claim binding, not the\n            # derived autonomous original-binding wrapper. Match the native\n            # ReferenceProfile.match contract explicitly.\n            'claim_binding_sha256': entry['original_binding_sha256'],\n            'corpus_manifest_sha256': entry['corpus_manifest_sha256'],\n            # These are release-profile supplement hashes. They do not assert\n            # the selected run's full/current source roster or active sources.\n            'source_sha256s': sorted(source['sha256'] for source in entry['sources']),\n            'request_source_pin': matches[0],\n        })\n    value = {\n        'contract': 'casepath.release-procedure-outline/1',\n        'profile_id': profile['profile_id'], 'profile_raw_sha256': sha(profile_raw),\n        'base_policy_sha256': digest_value(base), 'bounded_policy_sha256': digest_value(policy),\n        'source_files_sha256': {name: sha((root / name).read_bytes()) for name in [\n            'casepath-api/casepath_api/autonomous_reference_policy_v1.py',\n            'casepath-api/casepath_api/corpora/synthetic-150/policy/static-rule-templates-v3.json',\n            'casepath-api/casepath_api/reference_profiles/synthetic-nine-v1/normative_sources.json',\n        ]},\n        'catalogs': catalogs, 'claims': claims,\n    }\n    for catalog in value['catalogs']:\n        catalog['catalog_sha256'] = digest_value(catalog)\n    value['artifact_material_sha256'] = digest_value(value)\n    return value\n\n\nif __name__ == '__main__':\n    result = generate(sys.argv[1] if len(sys.argv) > 1 else '/workspace/casepath-cold-start-20261015')\n    print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')))\n";
 const expected=JSON.parse(execFileSync(python,['-c',script,root],{cwd:root,encoding:'utf8',env:{...process.env,PYTHONDONTWRITEBYTECODE:'1'},maxBuffer:1024*1024}));assert.deepEqual(ui.RELEASE_PROCEDURE_OUTLINE,expected,'policy/profile/source drift requires regenerating the release asset; no journal or head participates');assert.ok(Object.isFrozen(ui.RELEASE_PROCEDURE_OUTLINE.catalogs[0].nodes));
});


// These exercise the selected route and the production ownership handoff.
test('direct autonomous routes acquire a same-origin packet behind the immediate map and retain the original300ms choice',async t=>{
 for(const fragment of ['#autonomous/demonstration']) {
  routingFixture(t,fragment);const f=operationOpeningDOM(),packet=recordedPacketFixture(),opening=deferredRead(),snapshot=deferredRead();
  const api=fakeApi({handle:async path=>path.endsWith('/recorded-prototype.json')?new Response(packet.bytes):path.endsWith('/replay?through_seq=0')?opening.promise:path.endsWith('/snapshot?after=0')?snapshot.promise:path.includes('/operations?')?pendingOperationResponse(packet.native.binding):null});
  const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});
  try {
   assert.match(f.host.innerHTML,/data-au-release-plan=/);assert.doesNotMatch(f.host.innerHTML,/data-au-stage-fact=|data-au-revision=/);
   assert.equal(await controller.recordedPacketReady,true,'direct selection must acquire the bounded asset');
   await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='recorded_operations');assert.match(f.host.innerHTML,/Recorded replay/);assert.ok(api.calls.every(row=>!row.init.method||row.init.method==='GET'));
  } finally { controller.destroy();opening.resolve(response(packet.native.zero));snapshot.resolve(response(packet.native.snapshot));await settle(); }
 }
});

test('current verified binding prefetches exactly one next opening snapshot and trace without painting its facts and cancels all owned reads on exit',async t=>{
 const f=operationOpeningDOM(),first=operationOpeningFixture(),next=operationOpeningFixture(ui.REFERENCE_DEMO_CASES[1].claim_id),held=deferredRead();let nextSignal,cancelled=0;
 const api=fakeApi({handle:async(path,init)=>{
  if(path.includes(next.id)) { if(path.includes('/operations?')) {nextSignal=init.signal;return {ok:true,status:200,body:new ReadableStream({cancel(){cancelled++;}})};}return held.promise; }
  if(path.endsWith('/replay?through_seq=0'))return response(first.zero);if(path.endsWith('/snapshot?after=0'))return response(first.snapshot);if(path.includes('/operations?'))return pendingOperationResponse(first.binding);
 }});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();held.resolve(response(next.zero));});await settle();await controller.showDemonstration();await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='historical_recomputed');await settle();
 const requests=api.calls.filter(row=>row.path.includes(next.id));assert.deepEqual(requests.map(row=>row.path.split('/').at(-1)).sort(),['operations?mode=live','replay?through_seq=0','snapshot?after=0']);assert.doesNotMatch(f.host.innerHTML,/data-au-stage-fact=|The later accepted outcome/);assert.ok(!api.calls.some(row=>row.path.includes(ui.REFERENCE_DEMO_CASES[2].claim_id)),'only one future case is owned');
 await controller.showWork();const after=f.host.innerHTML;assert.equal(nextSignal.aborted,true);assert.ok(requests.every(row=>row.init.signal.aborted));held.resolve(response(next.zero));await settle();await settle();assert.equal(cancelled,1);assert.equal(f.host.innerHTML,after);assert.equal(api.calls.filter(row=>row.path.includes(next.id)).length,3,'late snapshots cannot create a fallback read');
});


test('a valid observed newer live opening prevents the300ms packet fallback from rolling the selected head back',async t=>{
 const f=operationOpeningDOM(),packet=recordedPacketFixture(),head=deferredRead(),zero=structuredClone(packet.native.zero);
 zero.current_revision=5;zero.current_state_sha256=sha('newer-observed-head');zero.current_event_sha256=sha('newer-observed-event');
 const api=fakeApi({handle:async path=>path.endsWith('/recorded-prototype.json')?new Response(packet.bytes):path.endsWith('/replay?through_seq=0')?response(zero):path.includes('/snapshot?')||path.endsWith('/replay?through_seq=5')?head.promise:path.includes('/operations?')?pendingOperationResponse(packet.native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});t.after(()=>{controller.destroy();head.resolve(response(packet.native.snapshot));});assert.equal(await controller.recordedPacketReady,true);await controller.showDemonstration();await settle();
 assert.doesNotMatch(f.host.innerHTML,/Recorded replay|The later accepted outcome/);assert.equal(api.calls.filter(row=>row.path.includes('mode=recorded')).length,0,'mismatched cached packet cannot replace observed live identity');assert.notEqual(f.attributes.get('data-au-operation-run-mode'),'recorded_operations');
});


function completedItineraryFixture(id,count) {
 const native=operationOpeningFixture(id),journal=native.snapshot.events,start=native.zero.replay_start;native.zero.state.state_sha256=sha('opening-'+id);native.zero.projection.state_sha256=native.zero.state.state_sha256;
 const baseline={...native.zero.state,revision:3,run_id:native.head.run_id,last_event_sha256:journal[2].event_sha256,graph:native.head.graph,source_roster_sha256:native.head.source_roster_sha256};delete baseline.state_sha256;baseline.state_sha256=sha(ui.canonicalJSON(baseline));
 journal[2].state_sha256=baseline.state_sha256;journal[2].resulting_state_sha256=baseline.state_sha256;start.state_sha256=baseline.state_sha256;native.binding.state_sha256=baseline.state_sha256;
 const frames=[native.binding];let previous=null;
 for(let seq=1;seq<=count;seq++) {
  const input={},result={activation:'true',execution_state:'ready'},operation={contract:operationContract,type:'operation',seq,id:`native-${seq}`,kind:'node.evaluate',object:{type:'node',id:'branch'},input,result,cause_ids:previous?[previous.id]:[],previous_operation_sha256:previous?.operation_sha256||null,input_sha256:sha(ui.canonicalJSON(input)),result_sha256:sha(ui.canonicalJSON(result))};const material={...operation};delete material.contract;delete material.type;operation.operation_sha256=sha(ui.canonicalJSON(material));frames.push(operation);previous=operation;
 }
 const checkpoint=saved=>({contract:operationContract,type:'checkpoint',verified:true,journal_seq:saved.revision,event_sha256:saved.last_event_sha256,state_sha256:saved.state_sha256,events:[journal[saved.revision-1]],mode:'replay',through_seq:saved.revision,current_revision:4,current_state_sha256:native.head.state_sha256,current_event_sha256:native.head.last_event_sha256,cursor_sha256:saved.last_event_sha256,provenance:{run_id:saved.run_id,event_sha256:saved.last_event_sha256,source_roster_sha256:saved.source_roster_sha256,policy_id:saved.policy_id}});
 frames.push({...checkpoint(baseline),state:baseline});frames.push({...checkpoint(native.head),base_state_sha256:baseline.state_sha256,state_delta:{set:native.head,remove:Object.keys(baseline).filter(key=>!(key in native.head))}});
 const hashes=JSON.parse(JSON.stringify(frames)).map(frame=>sha(ui.canonicalJSON(frame)));
 frames.push({contract:operationContract,type:'result',state_sha256:native.head.state_sha256,current_event_sha256:native.head.last_event_sha256,operation_count:count,operation_chain_sha256:previous.operation_sha256,exact_output_verified:true,trace_sha256:sha(ui.canonicalJSON(hashes))});
 return {...native,frames,body:frames.map(JSON.stringify).join('\n')+'\n'};
}

test('completed outcome holds8000ms independently of a ready next case and reuses its824 to299 operation transport without a zero or stale count',async t=>{
 const first=completedItineraryFixture(ui.REFERENCE_DEMO_CASES[0].claim_id,824),next=completedItineraryFixture(ui.REFERENCE_DEMO_CASES[1].claim_id,299),f=operationOpeningDOM(),future=deferredRead(),timers=[],writes=[];
 let markup=f.host.innerHTML,elapsed=0;Object.defineProperty(f.host,'innerHTML',{get:()=>markup,set:value=>{markup=value;writes.push(value);},configurable:true});const now=Date.now.bind(Date);t.mock.method(Date,'now',()=>now()+elapsed);
 const timeout=globalThis.setTimeout;globalThis.setTimeout=(fn,ms,...args)=>{if(ms===8000){const handle=timeout(()=>{},60000);timers.push({fn,handle});return handle;}return timeout(fn,ms,...args);};t.after(()=>{globalThis.setTimeout=timeout;for(const timer of timers)clearTimeout(timer.handle);});
 const api=fakeApi({handle:async path=>{const native=path.includes(first.id)?first:path.includes(next.id)?next:null;if(!native){if(path.includes('/replay?')||path.includes('/snapshot?')||path.includes('/operations?'))return future.promise;return null;}if(path.endsWith('/replay?through_seq=0'))return response(native.zero);if(path.endsWith('/snapshot?after=0'))return response(native.snapshot);if(path.includes('/operations?'))return new Response(native.body);}});
 const checkedTrace={binding:first.binding,rows:[],sources:new Map(),pinnedJournal:first.snapshot.events,journal:[],transportState:null};await ui.checkedOperationCheckpoint(first.frames.at(-3),checkedTrace);await ui.checkedOperationCheckpoint(first.frames.at(-2),checkedTrace);
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{controller.destroy();future.resolve(response({}));});await settle();await controller.showDemonstration();await waitFor(()=>timers.length===1);
 assert.match(f.host.innerHTML,/data-au-revision="4"/);assert.match(f.host.innerHTML,/max="823"/);assert.match(f.host.innerHTML,/The later accepted outcome/);assert.equal(f.attributes.get('data-au-operation-result-verified'),'true');
 assert.equal(api.calls.filter(row=>row.path.includes(next.id)).length,3,'one opening, one atomic head, one stream prepare during the current case');await settle();assert.ok(f.host.innerHTML.includes(`data-au-state-sha="${first.head.state_sha256}"`));assert.doesNotMatch(f.host.innerHTML,new RegExp(`data-au-claim-id="${next.id}"`));
 const boundary=writes.length;elapsed+=8000;clearTimeout(timers[0].handle);timers[0].fn();await waitFor(()=>timers.length===2);
 const nextWrites=writes.slice(boundary).filter(html=>html.includes(`data-au-state-sha="${next.zero.state.state_sha256}"`)||html.includes(`data-au-state-sha="${next.head.state_sha256}"`));
 assert.ok(nextWrites.length);assert.ok(nextWrites.every(html=>html.includes('max="298"')),'every second-case render uses its own admitted299-operation total');assert.ok(nextWrites.every(html=>!html.includes('max="823"')&&!html.includes('0 received')));assert.match(nextWrites[0],/value="0"/);assert.doesNotMatch(nextWrites[0],/The later accepted outcome|data-au-stage-fact=/,'a prefetched head never donates facts or its outcome to revision zero');assert.equal(api.calls.filter(row=>row.path.includes(next.id)).length,3,'handoff does not refetch the prepared native stream');
});

test('first genuine consequence retains a real sweep and transfer while subsequent reads keep their full pacing',()=>{
 const first={id:'first',kind:'fact.extract',source:{quote:'The actual bounded source statement.'}},later={...first,id:'later'},trace={openingConsequenceId:'first'};
 assert.deepEqual(ui.operationChoreographyTiming(first,trace),{read:360,transfer:300});assert.deepEqual(ui.operationChoreographyTiming(later,trace),{read:ui.operationReadDuration(later),transfer:600});assert.equal(ui.operationChoreographyTiming(first,{openingConsequenceId:'another-case'}).transfer,600);
});


test('pause and hide after the8000ms outcome hold preserve the finished case and resume the delayed next opening',async t=>{
 for(const action of ['pause','hide']) {
  const f=operationOpeningDOM(),first=completedItineraryFixture(ui.REFERENCE_DEMO_CASES[0].claim_id,1),next=operationOpeningFixture(ui.REFERENCE_DEMO_CASES[1].claim_id),opening=deferredRead(),future=deferredRead(),visibility=new Map(),timers=[];let elapsed=0,allowNext=false;
  f.container.ownerDocument.addEventListener=(name,fn)=>visibility.set(name,fn);const realNow=Date.now.bind(Date),restoreDate=Date.now;Date.now=()=>realNow()+elapsed;
  const timeout=globalThis.setTimeout;globalThis.setTimeout=(fn,ms,...args)=>{if(ms===8000){const handle=timeout(()=>{},60000);timers.push({fn,handle});return handle;}return timeout(fn,ms,...args);};
  const api=fakeApi({handle:async path=>{if(path.includes(first.id)){if(path.includes('/snapshot?'))return response(first.snapshot);if(path.endsWith('/replay?through_seq=0'))return response(first.zero);if(path.includes('/operations?'))return new Response(first.body);}if(path.includes(next.id)){if(path.includes('/snapshot?'))return response(next.snapshot);if(path.includes('/operations?'))return pendingOperationResponse(next.binding);if(path.endsWith('/replay?through_seq=0'))return allowNext?response(next.zero):opening.promise;}if(path.includes('/replay?')||path.includes('/snapshot?')||path.includes('/operations?'))return future.promise;}});
  const controller=ui.mount(f.container,{fetch:api.fetch});
  try {
   await settle();await controller.showDemonstration();await waitFor(()=>timers.length===1);elapsed+=8000;clearTimeout(timers[0].handle);timers[0].fn();await settle();
   if(action==='pause') {f.listeners.get('click')({target:control(f,'data-au-demo-stop')});allowNext=true;opening.resolve(response(next.zero));await settle();await settle();assert.ok(f.host.innerHTML.includes(first.head.state_sha256));f.listeners.get('click')({target:control(f,'data-au-demo-resume')});}
   else {f.container.ownerDocument.hidden=true;visibility.get('visibilitychange')();await settle();allowNext=true;opening.resolve(response(next.zero));await settle();assert.ok(f.host.innerHTML.includes(first.head.state_sha256));f.container.ownerDocument.hidden=false;visibility.get('visibilitychange')();}
   await waitFor(()=>f.host.innerHTML.includes(`data-au-planned-process="${next.head.state_sha256}"`));assert.equal(timers.length,1,'the completed visible hold is not repeated after resuming');assert.doesNotMatch(f.status.textContent,/unavailable|stopped|cancelled/);assert.equal(f.attributes.get('data-au-operation-result-verified'),'false');
  } finally {controller.destroy();opening.resolve(response(next.zero));future.resolve(response({}));for(const timer of timers)clearTimeout(timer.handle);globalThis.setTimeout=timeout;Date.now=restoreDate;await settle();}
 }
});

test('Cases cold click can finish packet acquisition inside its original300ms choice',async t=>{
 const f=operationOpeningDOM(),packet=recordedPacketFixture(),asset=deferredRead(),opening=deferredRead(),head=deferredRead();let assetSignal;
 const api=fakeApi({handle:async(path,init)=>path.endsWith('/recorded-prototype.json')?(assetSignal=init.signal,asset.promise):path.endsWith('/replay?through_seq=0')?opening.promise:path.includes('/snapshot?')||path.endsWith('/replay?through_seq=4')?head.promise:path.includes('/operations?')?pendingOperationResponse(packet.native.binding):null});
 const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});t.after(()=>{controller.destroy();opening.resolve(response(packet.native.zero));head.resolve(response(packet.native.snapshot));});await settle();await new Promise(resolve=>setTimeout(resolve,5));const selecting=controller.showDemonstration();assert.match(f.host.innerHTML,/data-au-release-plan=/);assert.equal(assetSignal.aborted,false);asset.resolve(new Response(packet.bytes));assert.equal(await controller.recordedPacketReady,true);await selecting;await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='recorded_operations');assert.match(f.host.innerHTML,/Recorded replay/);
});


test('late binding and result hashes cannot mutate a newly selected operation session',async t=>{
 for(const phase of ['binding','result']) {
  const first=completedItineraryFixture(ui.REFERENCE_DEMO_CASES[0].claim_id,1),f=operationOpeningDOM(),future=deferredRead();
  const bytes=Buffer.from(phase==='binding'?ui.canonicalJSON(first.binding):ui.canonicalJSON(JSON.parse(JSON.stringify(first.frames.slice(0,-1))).map(frame=>sha(ui.canonicalJSON(frame))))),hash=delayedPacketHash(t,bytes);
  const api=fakeApi({handle:async path=>{if(!path.includes(first.id)){if(path.includes('/replay?')||path.includes('/snapshot?')||path.includes('/operations?'))return future.promise;return null;}if(path.includes('/snapshot?'))return response(first.snapshot);if(path.endsWith('/replay?through_seq=0'))return response(first.zero);if(path.includes('/operations?mode=recorded'))return pendingOperationResponse({...first.binding,mode:'recorded_operations'});if(path.includes('/operations?'))return phase==='binding'?pendingOperationResponse(first.binding):new Response(first.body);}});
  const controller=ui.mount(f.container,{fetch:api.fetch});
  try {await settle();await controller.showDemonstration();await hash.started;await controller.showDemonstration(true,'reference','recorded');await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='recorded_operations');const before=f.host.innerHTML;hash.release();await settle();await settle();assert.equal(f.host.innerHTML,before,`${phase} completion keeps the replacement session unchanged`);assert.equal(f.attributes.get('data-au-operation-result-verified'),'false');assert.doesNotMatch(f.status.textContent,/stopped|differs/);}
  finally {controller.destroy();future.resolve(response({}));hash.restore();await settle();}
 }
});


test('next-case prefetch retains the live503 to recorded trace fallback and cancels its bounded owner on exit',async t=>{
 const f=operationOpeningDOM(),first=operationOpeningFixture(),next=operationOpeningFixture(ui.REFERENCE_DEMO_CASES[1].claim_id);let recordedSignal,cancelled=0;
 const api=fakeApi({handle:async(path,init)=>{const native=path.includes(next.id)?next:first;if(path.endsWith('/replay?through_seq=0'))return response(native.zero);if(path.includes('/snapshot?'))return response(native.snapshot);if(path.includes(next.id)&&path.includes('/operations?mode=live'))return response({detail:'Live unavailable'},503);if(path.includes(next.id)&&path.includes('/operations?mode=recorded')){recordedSignal=init.signal;return {ok:true,status:200,body:new ReadableStream({start(controller){controller.enqueue(new TextEncoder().encode(JSON.stringify({...next.binding,mode:'recorded_operations'})+'\n'));},cancel(){cancelled++;}})};}if(path.includes('/operations?'))return pendingOperationResponse(first.binding);}});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.showDemonstration();await waitFor(()=>Boolean(recordedSignal));assert.equal(api.calls.filter(row=>row.path.includes(next.id)&&row.path.includes('/operations?')).length,2);assert.match(f.host.innerHTML,/Live rules-based check/);assert.doesNotMatch(f.host.innerHTML,/The later accepted outcome|data-au-stage-fact=/);await controller.showWork();await settle();assert.equal(recordedSignal.aborted,true);assert.equal(cancelled,1);
});


test('the300ms choice accepts verified Live before the cutoff and commits Recorded at the cutoff without a late splice',async t=>{
 for(const liveFirst of [true,false]) {
  const f=operationOpeningDOM(),packet=recordedPacketFixture(),opening=deferredRead(),head=deferredRead(),fallback=deferredRead(),deadlines=[];
  const timeout=globalThis.setTimeout;globalThis.setTimeout=(fn,ms,...args)=>{if(ms===300){const handle=timeout(()=>{},60000);deadlines.push({fn,handle});return handle;}return timeout(fn,ms,...args);};
  const api=fakeApi({handle:async path=>path.endsWith('/recorded-prototype.json')?new Response(packet.bytes):path.endsWith('/replay?through_seq=0')?opening.promise:path.includes('/snapshot?')?head.promise:path.endsWith('/replay?through_seq=4')?fallback.promise:path.includes('/operations?')?pendingOperationResponse(packet.native.binding):null});
  const controller=ui.mount(f.container,{fetch:api.fetch,recordedPacket:packet.descriptor,allowNativeRecordedPacket:true});
  try {assert.equal(await controller.recordedPacketReady,true);const selecting=controller.showDemonstration();await settle();assert.equal(deadlines.length,1,'one300ms timer owns the entire choice');
   if(liveFirst){opening.resolve(response(packet.native.zero));head.resolve(response(packet.native.snapshot));await selecting;await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='historical_recomputed');assert.match(f.host.innerHTML,/Live rules-based check/);assert.doesNotMatch(f.host.innerHTML,/Recorded replay/);}
   else {await new Promise(resolve=>timeout(resolve,50));clearTimeout(deadlines[0].handle);deadlines[0].fn();await selecting;await waitFor(()=>f.attributes.get('data-au-operation-run-mode')==='recorded_operations');await waitFor(()=>api.calls.some(row=>row.path.includes(packet.native.id)&&row.path.endsWith('/replay?through_seq=4')));const before=f.host.innerHTML;opening.resolve(response(packet.native.zero));head.resolve(response(packet.native.snapshot));await settle();await settle();assert.equal(f.host.innerHTML,before);assert.match(f.host.innerHTML,/Recorded replay/);}
  } finally {controller.destroy();opening.resolve(response(packet.native.zero));head.resolve(response(packet.native.snapshot));fallback.resolve(response(packet.native.replay));for(const timer of deadlines)clearTimeout(timer.handle);globalThis.setTimeout=timeout;await settle();}
 }
});
