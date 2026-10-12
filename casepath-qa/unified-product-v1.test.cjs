'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {webcrypto,createHash}=require('node:crypto');
if(!globalThis.crypto)globalThis.crypto=webcrypto;
const ui=require('../casepath/assets/autonomous-workspace-v1.js');
const hash=c=>c.repeat(64),sha=v=>createHash('sha256').update(v).digest('hex');
const original=()=>({claim_id:'clm_original',origin:'canonical_original',title:'Original intake',mode:'unprocessed',status:'not_started',phase:'not_run',revision:0,state_sha256:hash('a'),graph:null,evaluation:null,source_preview:{text:'The original customer message.'},source_descriptors:[{claim_id:'clm_original',artifact_id:'message',file_name:'message.eml',media_type:'message/rfc822',sha256:hash('b')}],acquired_sources:[],facts:[],obligations:[],actions:[]});
const snapshot=s=>({state:s,projection:{claim_id:s.claim_id,revision:s.revision,state_sha256:s.state_sha256},events:[],current_revision:s.revision,current_state_sha256:s.state_sha256,cursor_sha256:null});
test('revision zero requires an explicit source-bound unprocessed state and has no invented process',()=>{
 const s=original();assert.equal(ui.readState({state:s},s.claim_id).state,s);
 const html=ui.workMarkup(s,{},null,[]);
 assert.match(html,/The original customer message\./);assert.match(html,/Not started/);assert.doesNotMatch(html,/data-au-node=|Recorded outcome|No original source recorded/);
 for(const extra of [{mode:undefined},{status:'running'},{graph:{nodes:[]}},{evaluation:{nodes:[]}},{outcome:{summary:'Pretend outcome'}}])assert.throws(()=>ui.readState({...s,...extra}),/identity|unprocessed/);
});
test('atomic snapshots bind state, projection, events and journal cursor before display',()=>{
 const s=original(),value=snapshot(s);assert.equal(ui.readSnapshot(value,s.claim_id,null).accepted.cursor,0);
 for(const extra of [{current_revision:1},{current_state_sha256:hash('d')},{cursor_sha256:'bad'},{projection:{...value.projection,revision:1}}])assert.throws(()=>ui.readSnapshot({...value,...extra},s.claim_id,null),/snapshot|cursor|projection|revision|identity/);
 assert.throws(()=>ui.readSnapshot(value,'other',null),/another claim/);
});
test('full collection search and domain browsing use supplied presentation metadata only',()=>{
 const rows=Array.from({length:150},(_,i)=>({...original(),claim_id:`clm_${i}`,title:`Claim ${i}`,browse_metadata:{domain:i<50?'defect_mold_heating':i<100?'lease_termination_dispute':'rent_increase_dispute'},source_preview:{text:i===149?'Rare original passage':'Original message'}}));
 assert.equal(ui.matchingClaims(rows,{domain:'defect_mold_heating'}).length,50);
 assert.equal(ui.matchingClaims(rows,{search:'rare original'}).at(0).claim_id,'clm_149');
 const html=ui.collectionMarkup(rows);assert.deepEqual([...html.matchAll(/data-au-claim="([^"]+)"/g)].map(match=>match[1]),rows.slice(0,20).map(row=>row.claim_id));assert.match(html,/Defects &amp; repairs/);assert.match(html,/Lease termination/);assert.match(html,/Rent changes/);assert.match(ui.collectionMarkup(rows,{search:'rare original'}),/Rare original passage/);assert.equal(ui.matchingClaims(rows).length,150);
 const unclassified=ui.collectionMarkup([{...original(),title:'Mold termination rent increase'}]);assert.equal(ui.matchingClaims([{...original(),title:'Mold termination rent increase'}],{domain:'defect_mold_heating'}).length,0,'subject words do not supply browsing classification');assert.match(unclassified,/data-au-claim="clm_original"/);
});

test('collection pagination bounds each reading view while searching every original and resetting changed scopes',()=>{
 const rows=Array.from({length:150},(_,index)=>({...original(),claim_id:`clm_${index}`,title:`Case ${index}`,browse_metadata:{domain:index<50?'defect_mold_heating':index<100?'lease_termination_dispute':'rent_increase_dispute'},source_preview:{text:index===149?'Rare original source passage':'Original source message'}})),before=JSON.stringify(rows);
 const first=ui.collectionPage(rows,{scope:'originals'});assert.deepEqual(first.rows,rows.slice(0,20));assert.equal(first.page,1);assert.equal(first.pages,8);assert.equal(first.total,150);assert.equal(first.pageSize,20);
 const last=ui.collectionPage(rows,{scope:'originals',page:8});assert.deepEqual(last.rows,rows.slice(140));assert.equal(last.page,8);assert.equal(last.total,150);
 assert.deepEqual(ui.collectionPage(rows,{page:999}).rows,last.rows);assert.equal(ui.collectionPage(rows,{page:0}).page,1);
 const search=ui.collectionPage(rows,{page:8,search:'rare original'});assert.deepEqual(search.rows,[rows[149]]);assert.equal(search.total,1);assert.equal(search.page,1);assert.equal(search.pages,1);
 const domain=ui.collectionPage(rows,{page:8,domain:'lease_termination_dispute'});assert.equal(domain.total,50);assert.equal(domain.pages,3);assert.equal(domain.page,3);assert.deepEqual(domain.rows,rows.slice(90,100));
 assert.equal(ui.collectionPage(rows,{page:1,domain:'lease_termination_dispute'}).rows[0].claim_id,'clm_50','a reset domain view starts with its own first record');
 const empty=ui.collectionPage(rows,{search:'No matching source'});assert.deepEqual(empty.rows,[]);assert.equal(empty.total,0);assert.equal(empty.page,1);assert.equal(empty.pages,1);
 assert.equal(JSON.stringify(rows),before,'page selection cannot rewrite original identity, source text, or accepted state');
});

test('catalog previews expose only the exact known original message before accepted state is available',()=>{
 const attack='<img src=x onerror="alert(1)">',row={...original(),title:attack,source_preview:{text:'Exact original intake excerpt.'},revision:27,status:'resolved',facts:[{fact_id:'invented',summary:'UNACCEPTED FACT'}],outcome:{summary:'UNACCEPTED OUTCOME'},graph:{nodes:[{node_id:'invented-branch'}]}},before=JSON.stringify(row);
 const html=ui.catalogPreviewMarkup(row,row.claim_id);assert.equal(typeof html,'string');assert.match(html,/Exact original intake excerpt\./);assert.match(html,/&lt;img/);assert.ok(html.includes(row.claim_id));
 assert.doesNotMatch(html,/<img|onerror="alert|data-au-revision=|data-au-state-sha=|data-au-node=|data-au-start|data-au-pause|data-au-resume|data-au-arrival|UNACCEPTED FACT|UNACCEPTED OUTCOME|Investigation complete|Opening|Verifying/);
 assert.equal(ui.catalogPreviewMarkup(row,'another-claim'),null);assert.equal(ui.catalogPreviewMarkup(null,row.claim_id),null);assert.equal(ui.catalogPreviewMarkup({...row,claim_id:undefined},row.claim_id),null);
 const native={claim_id:'native-original',title:'Exact native catalog title'};assert.match(ui.catalogPreviewMarkup(native,native.claim_id),/Exact native catalog title/);assert.doesNotMatch(ui.catalogPreviewMarkup(native,native.claim_id),/Exact original intake excerpt/,'another record cannot supply a missing message');
 assert.equal(JSON.stringify(row),before,'catalog display cannot admit facts or promote its unverified status');
});
test('demonstration selection is exactly nine canonical identities with three per domain',()=>{
 assert.equal(ui.DEMO_CASES.length,9);assert.equal(new Set(ui.DEMO_CASES.map(x=>x.claim_id)).size,9);
 assert.deepEqual(Object.values(ui.DEMO_CASES.reduce((counts,x)=>(counts[x.domain]=(counts[x.domain]||0)+1,counts),{})),[3,3,3]);
 const html=ui.demonstrationMarkup([],{enabled:true,provider_ready:true,limits:{autonomous_can_start:false,autonomous_reason:'call_limit_reached'}},'live');
 for(const row of ui.DEMO_CASES)assert.match(html,new RegExp(row.claim_id));
 assert.match(html,/Verified replay/);assert.match(html,/Live execution/);assert.match(html,/allowance/);assert.doesNotMatch(html,/9 completed/);
});
test('read-only previews check original and derived hashes without admitting evidence',async()=>{
 const s=original(),descriptor=s.source_descriptors[0],body='Original derived preview';
 const material={...descriptor,preview_only:true,evidence_admitted:false,text:body,text_sha256:sha(body),complete:true};const response={...material,preview_sha256:sha(ui.canonicalJSON(material))};
 const checked=await ui.checkedPreview(s,descriptor,response);assert.equal(checked.text,body);
 for(const extra of [{preview_only:false},{evidence_admitted:true},{preview_sha256:hash('a')},{receipt_sha256:hash('d')},{sha256:hash('d')}])await assert.rejects(ui.checkedPreview(s,descriptor,{...response,...extra}),/preview|source|identity|receipt/);
});
test('later supporting files do not inherit the canonical original binding, while original previews must match it',async()=>{
 const s=original();s.original_binding={original_binding_sha256:hash('c'),source_map:[{artifact_id:'message'}]};
 const descriptor={claim_id:s.claim_id,artifact_id:'later',file_name:'later.txt',media_type:'text/plain',sha256:hash('d')};
 const material={...descriptor,text:'A later original file',text_sha256:sha('A later original file'),complete:true,preview_only:true,evidence_admitted:false};
 const sealed=value=>({...value,preview_sha256:sha(ui.canonicalJSON(value))});
 assert.equal((await ui.checkedPreview(s,descriptor,sealed(material))).artifact_id,'later');
 const originalMaterial={...material,...s.source_descriptors[0]};
 await assert.rejects(ui.checkedPreview(s,s.source_descriptors[0],sealed(originalMaterial)),/original binding/);
 assert.equal((await ui.checkedPreview(s,s.source_descriptors[0],sealed({...originalMaterial,original_binding_sha256:hash('c')}))).artifact_id,'message');
});
test('replay binds prefix provenance and same-revision heads without confusing a legitimate later head',()=>{
 const state={...original(),revision:1,mode:'saved',status:'received',phase:'received',last_event_sha256:hash('b'),source_roster_sha256:hash('c'),policy_id:'policy.one',run_id:'run.one',receipts:[{receipt:{rule_pack_sha256:hash('d')}}],original_binding:{original_binding_sha256:hash('e'),claim_binding_sha256:hash('f'),source_map:[{artifact_id:'message',original_artifact_id:'original-message',sha256:hash('b')}]}};
 const provenance={source_roster_sha256:state.source_roster_sha256,sources:state.source_descriptors,source_map:state.original_binding.source_map,original_binding_sha256:hash('e'),claim_binding_sha256:hash('f'),policy_id:state.policy_id,run_id:state.run_id,event_sha256:hash('b'),rule_pack_sha256:[hash('d')]};
 const value={state,projection:{revision:1,state_sha256:state.state_sha256},mode:'replay',replay_only:true,through_seq:1,events:[{seq:1,revision:1,state_sha256:state.state_sha256,event_sha256:hash('b')}],cursor_sha256:hash('b'),current_revision:2,current_state_sha256:hash('8'),current_event_sha256:hash('9'),current_head:{revision:2,state_sha256:hash('8'),event_sha256:hash('9')},provenance};
 assert.equal(ui.readReplay(value,state.claim_id,1).state.revision,1);
 for(const field of ['source_roster_sha256','original_binding_sha256','claim_binding_sha256','policy_id','run_id','event_sha256'])assert.throws(()=>ui.readReplay({...value,provenance:{...provenance,[field]:'another'}},state.claim_id,1),/provenance|binding/);
 for(const extra of [{provenance:{}},{current_revision:1},{current_event_sha256:null},{current_head:{...value.current_head,revision:3}},{current_head:{...value.current_head,state_sha256:hash('a')}},{current_head:{...value.current_head,event_sha256:hash('a')}},{provenance:{...provenance,sources:[{...state.source_descriptors[0],sha256:hash('9')}]}},{provenance:{...provenance,sources:[{...state.source_descriptors[0],size_bytes:999}]}},{provenance:{...provenance,source_map:[]}},{provenance:{...provenance,rule_pack_sha256:[]}}])assert.throws(()=>ui.readReplay({...value,...extra},state.claim_id,1),/replay|prefix|provenance|identity|head|binding/);
 const same={...value,current_revision:1,current_state_sha256:state.state_sha256,current_event_sha256:state.last_event_sha256,current_head:{revision:1,state_sha256:state.state_sha256,event_sha256:state.last_event_sha256}};
 assert.equal(ui.readReplay(same,state.claim_id,1).state,state);
});
test('original collection and added intakes retain separate explicit identities',()=>{
 const rows=[{...original(),origin:'canonical_original'},{...original(),claim_id:'added',origin:'native_intake',title:'A native intake',mode:'saved',revision:1,status:'completed'}];
 const html=ui.collectionMarkup(rows);assert.match(html,/data-au-claim="clm_original"/);assert.doesNotMatch(html,/data-au-claim="added"/);assert.equal([...html.matchAll(/data-au-claim="/g)].length,1);assert.match(html,/data-au-collection-scope="originals" aria-pressed="true"/);
 const added=ui.collectionMarkup(rows,{scope:'added'});assert.match(added,/data-au-claim="added"/);assert.doesNotMatch(added,/data-au-claim="clm_original"/);assert.match(added,/data-au-collection-scope="added" aria-pressed="true"/);assert.equal([...added.matchAll(/data-au-claim="/g)].length,1);
 assert.deepEqual(ui.matchingClaims(rows,{scope:'originals'}).map(row=>row.claim_id),['clm_original']);assert.deepEqual(ui.matchingClaims(rows,{scope:'added'}).map(row=>row.claim_id),['added']);
});
test('handling completion labels do not rewrite lifecycle codes or recorded legal outcomes',()=>{
 const rows=['completed','complete','resolved'].map((status,index)=>({...original(),origin:'canonical_original',claim_id:`done_${index}`,status,revision:1,mode:'saved',outcome:{summary:'No settlement has been recorded.'}}));const before=JSON.stringify(rows);
 const html=ui.collectionMarkup(rows);assert.match(html,/Investigation complete/);assert.doesNotMatch(html,/>Resolved</);assert.equal(ui.matchingClaims(rows,{filter:'investigation_complete'}).length,3);assert.equal(ui.matchingClaims(rows,{search:'investigation complete'}).length,3);
 assert.match(ui.workMarkup(rows[2],{},null,[]),/No settlement has been recorded\./);assert.equal(JSON.stringify(rows),before);
});
test('execution failure remains separate from an accepted evidence deferral in claim and itinerary labels',()=>{
 const failed={...original(),claim_id:ui.DEMO_CASES[4].claim_id,revision:11,mode:'saved',status:'deferred',phase:'deferred',outcome:null,deferral:{code:'verification_deferred',reason:'interpretation citation is not an exact claim source span',details:{error_type:'ValueError',workflow_id:'saved-workflow'}}};
 const evidence={...failed,deferral:null,outcome:{status:'deferred',summary:'A received source leaves the question unresolved.',missing_evidence:[],unresolved_facts:[{fact_id:'condition:notice_authority',summary:'Which notice governs remains unresolved.'}]}};
 const before=JSON.stringify([failed,evidence]);
 for(const [claim,label]of [[failed,'Execution failed'],[evidence,'More evidence needed']]) {
  assert.match(ui.workMarkup(claim,{},null,[]),new RegExp(`data-au-claim-status>${label}\\.<\\/span>`));
  assert.match(ui.claimsMarkup([claim]),new RegExp(`>${label}</span>`));
  assert.match(ui.demoItineraryMarkup([claim]),new RegExp(`>${label}</span>`));
 }
 assert.match(ui.workMarkup(failed,{},null,[]),/interpretation citation is not an exact claim source span/);
 assert.match(ui.claimsMarkup([{...failed,deferral:undefined}]),/>Execution stopped<\/span>/,'queue summaries do not infer the failure code they omit');
 assert.equal(ui.replayCanAdvance(failed),false);
 assert.equal(ui.replayCanAdvance({...failed,status:'completed'}),false,'a completed code without an accepted outcome cannot finish the replay');
 assert.equal(ui.replayCanAdvance(evidence),true);
 assert.equal(ui.replayCanAdvance({...evidence,status:'running'}),false);
 for(const code of ['verification_deferred','provider_deferred','execution_deferred','model_unavailable','paused']) {
  const partial={...evidence,deferral:{code,reason:'Execution remains unresolved.'}};
  assert.equal(ui.replayCanAdvance(partial),false,'an existing outcome cannot clear a current execution deferral');
  assert.doesNotMatch(ui.workMarkup(partial,{},null,[]),/data-au-claim-status>More evidence needed\.<\/span>/);
 }
 assert.equal(ui.replayCanAdvance({...evidence,reconciliations:[{status:'failed'}]}),false);
 assert.equal(ui.replayCanAdvance({...evidence,reconciliations:[{status:'started'}]}),false);
 assert.equal(ui.replayCanAdvance({...evidence,reconciliations:[{status:'failed'},{status:'completed'}]}),true);
 assert.equal(JSON.stringify([failed,evidence]),before);
 const demo=ui.demonstrationMarkup([failed,evidence],null);
 assert.match(demo,/sources and recorded histories/);assert.match(demo,/Playback stops if no operational outcome was accepted/);assert.doesNotMatch(demo,/accepted histories/);
});
test('completed steps and actions remain local to a running investigation',()=>{
 const s={...original(),revision:1,mode:'saved',status:'running',graph:{claim_id:'clm_original',nodes:[{node_id:'first',title:'Check original source'}],edges:[]},evaluation:{nodes:[{node_id:'first',execution_state:'completed'}]},actions:[{action_id:'source-check',title:'Source checked',status:'completed'}]};
 const html=ui.workMarkup(s,{},'first',[]);assert.match(html,/data-au-claim-status>Working\.<\/span>/);assert.match(html,/class="au-node-state">Completed</);assert.deepEqual(ui.contextualRecord(s,{},[],'action','0').result,s.actions[0]);assert.ok(ui.workMarkup(s,{},'first',[],'activity').includes(`data-au-inspect="action" data-au-record-id="${ui.actionRows(s)[0].instanceId}"`));assert.doesNotMatch(html,/Investigation complete/);
 assert.match(ui.collectionMarkup([{...s,origin:'canonical_original',status:'completed'}]),/Investigation complete/);assert.equal(s.status,'running');assert.equal(s.actions[0].status,'completed');
});

test('one contextual record resolves exact accepted objects without expanding a competing copy into every view',()=>{
 const s={...original(),revision:3,mode:'saved',status:'running',
  graph:{claim_id:'clm_original',nodes:[{node_id:'decision',label:'Check recorded notice'}],edges:[]},
  evaluation:{nodes:[{node_id:'decision',execution_state:'blocked'}],documents:[{document_type:'notice',route_state:'held_behind_question',review_state:'unreviewed'}]},
  facts:[{fact_id:'fact:notice',status:'unresolved',summary:'The recorded notice date remains unknown.'}],
  obligations:[{obligation_id:'need:notice',node_id:'decision',document_type:'notice',required_fact_ids:['fact:notice'],reason:'The recorded question must be decided first.'}],
  actions:[{result:{action_id:'review',node_ids:['decision'],document_type:'notice',status:'completed'},receipt:{receipt_sha256:hash('c'),checks:[{accepted:true,reason:'Original receipt retained.'}]}}],
  knowledge_uses:[{knowledge_id:'knowledge.notice',version:1,definition_sha256:hash('d'),applicability:'same_verified_family_and_rule_version'}]};
 const projection={claim_id:s.claim_id,revision:s.revision,state_sha256:s.state_sha256,node_capabilities:{decision:{authorized:false,reason:'No filing capability recorded.'}}};
 const event={seq:3,claim_id:s.claim_id,revision:3,state_sha256:s.state_sha256,event_sha256:hash('e'),kind:'action.completed',payload:s.actions[0]};
 const version={knowledge_id:'knowledge.notice',version:1,knowledge_sha256:hash('f'),source_claim_id:'origin',qualification:{status:'qualified',checks:['no_case_values_or_files']}};
 const data={versions:[version],uses:[],quarantined:[]}, before=JSON.stringify({s,projection,event,data});
 assert.deepEqual(ui.contextualRecord(s,projection,[event],'claim'),{state:s,projection});
 const replay={state:s,projection,mode:'replay',replay_only:true,through_seq:s.revision,current_revision:7,current_state_sha256:hash('7'),current_event_sha256:hash('8'),provenance:{source_roster_sha256:hash('9')},events:[event]};assert.equal(ui.contextualRecord(s,projection,[event],'replay','',data,replay),replay,'replay inspection retains both exact prefix and separate saved-head identities');
 assert.deepEqual(ui.contextualRecord(s,projection,[event],'fact','fact:notice'),s.facts[0]);
 assert.deepEqual(ui.contextualRecord(s,projection,[event],'requirement','need:notice'),{obligations:s.obligations,evaluation:s.evaluation.documents});
 assert.deepEqual(ui.contextualRecord(s,projection,[event],'event','3'),event);
 const step=ui.contextualRecord(s,projection,[event],'step','decision');
 assert.deepEqual(step.node,s.graph.nodes[0]);assert.deepEqual(step.evaluation,s.evaluation.nodes[0]);assert.deepEqual(step.capability,projection.node_capabilities.decision);
 assert.deepEqual(ui.contextualRecord(s,projection,[event],'knowledge','knowledge.notice:1',data),version);
 assert.deepEqual(ui.contextualRecord(s,projection,[event],'use','0',data),s.knowledge_uses[0]);
 assert.equal(JSON.stringify({s,projection,event,data}),before,'inspection cannot change source authority or invent facts from reuse');
 const html=ui.workMarkup(s,projection,'decision',[event]);
 assert.match(html,/data-au-inspect="claim"/);assert.match(html,new RegExp(`data-au-revision="${s.revision}" data-au-state-sha="${s.state_sha256}"`));assert.match(html,/data-au-inspect="fact"/);assert.match(html,/data-au-inspect="requirement"/);
 assert.doesNotMatch(html,/<details[\s\S]*<details/,'primary reading does not replicate nested technical records');
 assert.ok(html.includes(s.facts[0].summary));assert.equal(ui.contextualRecord(s,projection,[event],'requirement','need:notice').obligations[0].reason,s.obligations[0].reason);assert.match(html,/May be needed/);assert.match(html,/Not yet supported/);assert.equal(ui.contextualRecord(s,projection,[event],'requirement','need:notice').evaluation[0].route_state,'held_behind_question');
});
