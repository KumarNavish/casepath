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

const readCacheAPI='https://casepath.example.invalid/api/claim-loops/v1/autonomous',readCacheNow=1700000000000;
function readCacheHead(id='clm_original',at=readCacheNow) {const state={...original(),contract:'casepath.autonomous-claim/1.0.0',claim_id:id};state.source_descriptors=state.source_descriptors.map(source=>({...source,claim_id:id}));return{at,state,projection:{claim_id:id,revision:state.revision,state_sha256:state.state_sha256},cursor:0,history:[]};}
function readCacheMaterial() {return{contract:'casepath.read-cache/1',api:readCacheAPI,saved_at:readCacheNow,snapshots:[readCacheHead()],knowledge:null};}
function sealedReadCache(material) {return JSON.stringify({...material,sha256:sha(ui.canonicalJSON(material))});}

test('the read cache retains at most three exact saved heads and the complete Knowledge DTO without altering source authority',async()=>{
 const material=readCacheMaterial();material.snapshots=[readCacheHead('original-a'),readCacheHead('original-b'),readCacheHead('original-c')];material.knowledge={at:readCacheNow,value:{versions:[{knowledge_id:'procedure.one',version:2,knowledge_sha256:hash('b'),source_claim_id:'original-a',qualification:{status:'qualified',checks:['no_case_values_or_files']}}],uses:[{knowledge_id:'procedure.one',version:2,knowledge_sha256:hash('b'),claim_id:'original-b',applicability:'same_verified_family_and_rule_version'}],quarantined:[{knowledge_id:'withheld',qualification:{status:'quarantined',reason:'Exact original withheld reason.'}}],public_extension:{text:'Exact public DTO extension.'}}};
 const before=JSON.stringify(material),serialized=sealedReadCache(material),restored=await ui.checkedReadCache(serialized,readCacheAPI,readCacheNow);assert.deepEqual(restored,material);assert.equal(restored.snapshots.length,3);assert.deepEqual(restored.knowledge.value,material.knowledge.value);assert.equal(JSON.stringify(material),before);assert.deepEqual(restored.snapshots.map(head=>head.state.source_descriptors[0].sha256),[hash('b'),hash('b'),hash('b')]);
 const boundary=structuredClone(material);boundary.saved_at=readCacheNow-900000;for(const head of boundary.snapshots)head.at=boundary.saved_at;boundary.knowledge.at=boundary.saved_at;assert.deepEqual(await ui.checkedReadCache(sealedReadCache(boundary),readCacheAPI,readCacheNow),boundary,'a read at the exact fifteen-minute bound remains inspectable');
});

test('read cache checksums API contract age and complete entry identities fail closed independently',async()=>{
 const material=readCacheMaterial(),serialized=sealedReadCache(material),before=JSON.stringify(material);
 await assert.rejects(ui.checkedReadCache('{',readCacheAPI,readCacheNow));await assert.rejects(ui.checkedReadCache(JSON.stringify({...material,sha256:hash('0')}),readCacheAPI,readCacheNow));await assert.rejects(ui.checkedReadCache(serialized,readCacheAPI+'/another-namespace',readCacheNow));
 const cases=[['contract',copy=>{copy.contract='casepath.read-cache/0';}],['API',copy=>{copy.api='https://other.example.invalid/api/claim-loops/v1/autonomous';}],['expired envelope',copy=>{copy.saved_at=readCacheNow-900001;}],['future envelope',copy=>{copy.saved_at=readCacheNow+1;}],['expired head',copy=>{copy.snapshots[0].at=readCacheNow-900001;}],['future head',copy=>{copy.snapshots[0].at=readCacheNow+1;}],['invalid timestamp',copy=>{copy.snapshots[0].at=String(readCacheNow);}],['wrong head claim',copy=>{copy.snapshots[0].state.claim_id='another-claim';}],['head cursor',copy=>{copy.snapshots[0].cursor=1;}],['head projection',copy=>{copy.snapshots[0].projection.state_sha256=hash('0');}]];
 for(const [label,change] of cases){const copy=structuredClone(material);change(copy);await assert.rejects(ui.checkedReadCache(sealedReadCache(copy),readCacheAPI,readCacheNow),undefined,label);}
 assert.equal(JSON.stringify(material),before,'failed local validation cannot modify the saved original');
});

test('read cache rejects duplicate or excess saved heads oversized storage and stale malformed Knowledge',async()=>{
 const material=readCacheMaterial(),before=JSON.stringify(material),duplicate={...material,snapshots:[material.snapshots[0],structuredClone(material.snapshots[0])]},excess={...material,snapshots:['a','b','c','d'].map(id=>readCacheHead(id))};await assert.rejects(ui.checkedReadCache(sealedReadCache(duplicate),readCacheAPI,readCacheNow));await assert.rejects(ui.checkedReadCache(sealedReadCache(excess),readCacheAPI,readCacheNow));
 const oversized={...material,knowledge:{at:readCacheNow,value:{versions:[],uses:[],quarantined:[],public_extension:'x'.repeat(1048577)}}};assert.ok(sealedReadCache(oversized).length*2>2*1024*1024);await assert.rejects(ui.checkedReadCache(sealedReadCache(oversized),readCacheAPI,readCacheNow),/bound/i);
 for(const knowledge of [{at:readCacheNow-900001,value:{versions:[]}},{at:readCacheNow+1,value:{versions:[]}},{at:readCacheNow,value:{versions:{}}},{at:readCacheNow,value:{versions:[],uses:{}}},{at:readCacheNow,value:{versions:[],quarantined:{}}}])await assert.rejects(ui.checkedReadCache(sealedReadCache({...material,knowledge}),readCacheAPI,readCacheNow));
 assert.equal(JSON.stringify(material),before);
});
test('full collection search and domain browsing use supplied presentation metadata only',()=>{
 const rows=Array.from({length:150},(_,i)=>({...original(),claim_id:`clm_${i}`,title:`Claim ${i}`,browse_metadata:{domain:i<50?'defect_mold_heating':i<100?'lease_termination_dispute':'rent_increase_dispute'},source_preview:{text:i===149?'Rare original passage':'Original message'}}));
 assert.equal(ui.matchingClaims(rows,{domain:'defect_mold_heating'}).length,50);
 assert.equal(ui.matchingClaims(rows,{search:'rare original'}).at(0).claim_id,'clm_149');
 const html=ui.collectionMarkup(rows);assert.deepEqual([...html.matchAll(/data-au-claim="([^"]+)"/g)].map(match=>match[1]),rows.slice(0,20).map(row=>row.claim_id));assert.match(html,/Defects and repairs/);assert.match(html,/Lease termination/);assert.match(html,/Rent increases/);assert.match(ui.collectionMarkup(rows,{search:'rare original'}),/Rare original passage/);assert.equal(ui.matchingClaims(rows).length,150);
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

test('preview boundaries keep whole original words and the complete source searchable and unchanged',()=>{
 const prefix='Whole source sentence. '.repeat(10),boundaryWord='BoundaryWordMustStayWhole',message=`${prefix}${boundaryWord} The source continues beyond the preview.`,row={...original(),source_preview:{text:message}},expected=prefix.trimEnd()+'…';row.source_descriptors[0].sha256=sha(message);
 assert.ok(prefix.length<240&&prefix.length+boundaryWord.length>240,'the boundary falls inside a source word');
 const before=JSON.stringify(row),cases=ui.claimsMarkup([row]),catalog=ui.catalogPreviewMarkup(row,row.claim_id);
 assert.equal(cases.match(/<p class="au-claim-excerpt" id="ex-[^"]+">([^<]*)<\/p>/)[1],expected);assert.equal(catalog.match(/<pre class="au-original-message">([^<]*)<\/pre>/)[1],expected);assert.doesNotMatch(cases+catalog,/BoundaryWord|The source continues beyond the preview/);
 assert.deepEqual(ui.matchingClaims([row],{search:'source continues beyond'}).map(item=>item.claim_id),[row.claim_id],'clipping the reading excerpt cannot clip full-source search');assert.equal(ui.contextualRecord(row,{},[],'claim').state.source_preview.text,message);assert.equal(row.source_descriptors[0].sha256,sha(message));assert.equal(JSON.stringify(row),before);
 const short={...row,source_preview:{text:'The complete short original message.'}};assert.match(ui.claimsMarkup([short]),/>The complete short original message\.<\/p>/);assert.match(ui.catalogPreviewMarkup(short,short.claim_id),/>The complete short original message\.<\/pre>/);
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
 const html=ui.collectionMarkup(rows);assert.match(html,/data-au-claim="clm_original"/);assert.doesNotMatch(html,/data-au-claim="added"/);assert.equal([...html.matchAll(/data-au-claim="/g)].length,1);assert.match(html,/<p class="au-lead">150 fictional cases<\/p>/);assert.match(html,/data-au-collection-scope="added">Added <span data-au-scope-count>\(1\)<\/span><\/button>/);assert.doesNotMatch(html,/data-au-collection-scope="originals"/);
 const added=ui.collectionMarkup(rows,{scope:'added'});assert.match(added,/data-au-claim="added"/);assert.doesNotMatch(added,/data-au-claim="clm_original"/);assert.match(added,/<p class="au-lead">Added cases<\/p>/);assert.match(added,/data-au-collection-scope="originals">Original cases <span data-au-scope-count>\(1\)<\/span><\/button>/);assert.doesNotMatch(added,/data-au-collection-scope="added"/);assert.equal([...added.matchAll(/data-au-claim="/g)].length,1);
 assert.deepEqual(ui.matchingClaims(rows,{scope:'originals'}).map(row=>row.claim_id),['clm_original']);assert.deepEqual(ui.matchingClaims(rows,{scope:'added'}).map(row=>row.claim_id),['added']);
});
test('handling completion labels do not rewrite lifecycle codes or recorded legal outcomes',()=>{
 const rows=['completed','complete','resolved'].map((status,index)=>({...original(),origin:'canonical_original',claim_id:`done_${index}`,status,revision:1,mode:'saved',outcome:{summary:'No settlement has been recorded.'}}));const before=JSON.stringify(rows);
 const html=ui.collectionMarkup(rows);assert.equal([...html.matchAll(/<span class="au-claim-status-word">Assessment complete</g)].length,3);assert.doesNotMatch(html,/>Resolved<|Checks complete/);assert.equal(ui.matchingClaims(rows,{filter:'investigation_complete'}).length,3);assert.equal(ui.matchingClaims(rows,{search:'assessment complete'}).length,3);
 assert.match(ui.workMarkup(rows[2],{},null,[],'activity'),/No settlement has been recorded\./);assert.deepEqual(ui.contextualRecord(rows[2],{},[],'claim').state.outcome,rows[2].outcome);assert.equal(JSON.stringify(rows),before);
});
test('execution failure remains separate from an accepted evidence deferral in claim and itinerary labels',()=>{
 const failed={...original(),claim_id:ui.DEMO_CASES[4].claim_id,revision:11,mode:'saved',status:'deferred',phase:'deferred',outcome:null,deferral:{code:'verification_deferred',reason:'interpretation citation is not an exact claim source span',details:{error_type:'ValueError',workflow_id:'saved-workflow'}}};
 const evidence={...failed,deferral:null,outcome:{status:'deferred',summary:'A received source leaves the question unresolved.',missing_evidence:[],unresolved_facts:[{fact_id:'condition:notice_authority',summary:'Which notice governs remains unresolved.'}]}};
 const before=JSON.stringify([failed,evidence]);
 for(const [claim,label]of [[failed,'Stopped'],[evidence,'More evidence needed']]) {
  assert.match(ui.workMarkup(claim,{},null,[]),new RegExp(`data-au-claim-status>${label}\\.<\\/span>`));
  assert.match(ui.claimsMarkup([claim]),new RegExp(`<span class="au-claim-status-word">${label}</span>`));
  assert.match(ui.demoItineraryMarkup([claim],null,null,ui.DEMO_CASES),new RegExp(`>${label}</span>`),'the explicit legacy itinerary retains the recorded execution label');
 }
 const failedHtml=ui.workMarkup(failed,{},null,[]);assert.match(failedHtml,/data-au-claim-status>Stopped\.<\/span> Execution failed\. Open Details for the recorded reason\.<button type="button" class="au-link au-record-link" data-au-inspect="outcome" data-au-record-id="">Details<\/button>/);assert.deepEqual(ui.contextualRecord(failed,{},[],'outcome').deferral,failed.deferral,'the exact recorded failure reason stays one Details control away');
 assert.match(ui.claimsMarkup([{...failed,deferral:undefined}]),/<span class="au-claim-status-word">Stopped<\/span><\/p>/,'queue summaries do not infer the failure code they omit');
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
 const demo=ui.demonstrationMarkup([failed,evidence],null,'replay');
 assert.match(demo,/sources and recorded histories/);assert.match(demo,/Playback stops if no operational outcome was accepted/);assert.doesNotMatch(demo,/accepted histories/);
});
test('completed steps and actions remain local to a running investigation',()=>{
 const s={...original(),revision:1,mode:'saved',status:'running',graph:{claim_id:'clm_original',nodes:[{node_id:'first',title:'Check original source'}],edges:[]},evaluation:{nodes:[{node_id:'first',execution_state:'completed'}]},actions:[{action_id:'source-check',title:'Source checked',status:'completed'}]};
 const html=ui.workMarkup(s,{},'first',[]);assert.match(html,/data-au-claim-status>Working\.<\/span>/);assert.match(html,/class="au-node-state">Completed</);assert.deepEqual(ui.contextualRecord(s,{},[],'action','0').result,s.actions[0]);assert.ok(ui.workMarkup(s,{},'first',[],'activity').includes(`data-au-inspect="action" data-au-record-id="${ui.actionRows(s)[0].instanceId}"`));assert.doesNotMatch(html,/Checks complete/);
 assert.match(ui.collectionMarkup([{...s,origin:'canonical_original',status:'completed'}]),/<span class="au-claim-status-word">Assessment complete</);assert.equal(s.status,'running');assert.equal(s.actions[0].status,'completed');
});

test('one contextual record resolves exact accepted objects without expanding a competing copy into every view',()=>{
 const s={...original(),revision:3,mode:'saved',status:'running',
  graph:{claim_id:'clm_original',nodes:[{node_id:'decision',label:'Check recorded notice'}],edges:[]},
  evaluation:{nodes:[{node_id:'decision',activation:'unresolved',execution_state:'blocked'}],documents:[{document_type:'notice',activation:'true',route_state:'held_behind_question',review_state:'unreviewed'}]},
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
 assert.match(html,/data-au-detail="activity"[^>]*>History/);assert.match(html,new RegExp(`data-au-revision="${s.revision}" data-au-state-sha="${s.state_sha256}"`));assert.doesNotMatch(html,/data-au-inspect="(?:claim|fact|step|requirement|use)"/);assert.match(ui.workMarkup(s,projection,'decision',[event],'activity'),/data-au-inspect="claim"[^>]*>Case details/);
 assert.doesNotMatch(html,/<details[\s\S]*<details/,'primary reading does not replicate nested technical records');
 assert.ok(html.includes(s.facts[0].summary));assert.equal(ui.contextualRecord(s,projection,[event],'requirement','need:notice').obligations[0].reason,s.obligations[0].reason);assert.doesNotMatch(html,/Not yet supported/);assert.equal(ui.contextualRecord(s,projection,[event],'requirement','need:notice').evaluation[0].route_state,'held_behind_question');
 assert.deepEqual(ui.formingRequirements(s),[]);assert.doesNotMatch(html,/<li[^>]*data-au-obligation="need:notice"/,'an unreached held requirement remains in its exact record rather than the forming rail');
 const checklist=ui.workMarkup(s,projection,'decision',[event],'documents');assert.match(checklist,/Document checklist/);assert.match(checklist,/<li[^>]*data-au-obligation="need:notice"[^>]*data-au-document="notice"[^>]*data-status="held_behind_question"/);assert.match(checklist,/May be needed/,'the full checklist retains the recorded held route');
 const held=structuredClone(s);Object.assign(held.evaluation.nodes[0],{activation:'true',execution_state:'ready'});assert.deepEqual(ui.formingRequirements(held),[],'a ready node cannot expose a document still held behind a question');
 const unreached=structuredClone(s);unreached.evaluation.documents[0].route_state='needed_now';assert.deepEqual(ui.formingRequirements(unreached),[],'a needed document cannot expose a step whose activation remains unresolved');
 const reached=structuredClone(s),quote='The recorded notice is dated 21 February 2025.',text=`😀\n${quote}\nOriginal closing.`,source={...reached.source_descriptors[0],text,text_sha256:sha(text),complete:true},citation={artifact_id:source.artifact_id,sha256:source.sha256,text_sha256:source.text_sha256,start_char:2,end_char:2+Array.from(quote).length,quote},context={document:'notice',obligation:'need:notice',fact:'fact:notice'};
 Object.assign(reached.evaluation.nodes[0],{activation:'true',execution_state:'ready'});Object.assign(reached.evaluation.documents[0],{route_state:'needed_now',review_state:'sufficient'});Object.assign(reached.facts[0],{status:'true',summary:quote,citations:[citation]});reached.acquired_sources=[source];
 const ownMissing=structuredClone(reached);Object.assign(ownMissing.evaluation.nodes[0],{execution_state:'blocked',blocked_by:[],unresolved_dependencies:[],missing_document_types:['notice']});ownMissing.evaluation.documents[0].review_state='missing';
 const variantsBefore=JSON.stringify({held,unreached,reached,ownMissing});
 for(const variant of [reached,ownMissing]){
  assert.deepEqual(ui.formingRequirements(variant),variant.obligations,'ready and own-missing-evidence steps expose their exact recorded requirement');
  assert.deepEqual(ui.formingRelations(variant,'decision',context),{fact:context.fact,source:source.artifact_id,node:'decision',obligation:context.obligation,citation});
  const forming=ui.workMarkup(variant,projection,'decision',[event],'step',context),rows=[...forming.matchAll(/<li[^>]*data-au-obligation="([^"]+)"/g)],paths=[...forming.matchAll(/<path data-au-forming-wire="([^"]+)"([^>]*)>/g)];assert.deepEqual(rows.map(row=>row[1]),['need:notice']);assert.match(forming,/data-au-select="decision" data-au-select-document="notice" data-au-select-obligation="need:notice" data-au-select-fact="fact:notice"/);assert.deepEqual(paths.map(path=>path[1]),['source-process','process-document']);
  for(const [, ,attributes] of paths)for(const [field,value] of Object.entries({fact:context.fact,source:source.artifact_id,node:'decision',obligation:context.obligation}))assert.ok(attributes.includes(`data-au-wire-${field}="${value}"`));
  assert.deepEqual(ui.contextualRecord(variant,projection,[event],'claim'),{state:variant,projection});assert.deepEqual(ui.contextualRecord(variant,projection,[event],'requirement',context.obligation),{obligations:variant.obligations,evaluation:variant.evaluation.documents});assert.deepEqual(ui.contextualRecord(variant,projection,[event],'fact',context.fact),variant.facts[0]);
 }
 const reachedRow=ui.obligationMarkup(reached,'decision',ui.formingRequirements(reached),context,true);assert.match(reachedRow,/data-au-source="message" data-au-source-origin="requirement:need:notice"/);assert.match(reachedRow,/Supplied evidence is sufficient\./);assert.equal(Array.from(text).slice(citation.start_char,citation.end_char).join(''),quote);
 assert.equal(JSON.stringify({held,unreached,reached,ownMissing}),variantsBefore,'forming joins and full inspection cannot modify accepted fixture objects');assert.equal(JSON.stringify({s,projection,event,data}),before,'the original held state and exact records remain immutable after every view');
});

test('History owns Case details event action and playback controls while purpose views retain exact selections',()=>{
 const s={...original(),revision:3,mode:'saved',status:'running',graph:{claim_id:'clm_original',nodes:[{node_id:'decision',label:'Check the supplied notice'}],edges:[]},evaluation:{nodes:[{node_id:'decision',activation:'true',execution_state:'ready'}],documents:[{document_type:'notice',activation:'true',route_state:'needed_now',review_state:'insufficient'}]},facts:[{fact_id:'fact:notice',summary:'The supplied notice has one addressee.',reason:'Its envelope names Alex.',verdict:'insufficient'}],obligations:[{obligation_id:'need:notice',node_id:'decision',document_type:'notice',required_fact_ids:['fact:notice']}],actions:[{result:{action_id:'review:notice',node_id:'decision',status:'completed'},receipt:{receipt_sha256:hash('c')}}],knowledge_uses:[{knowledge_id:'procedure.notice',version:2,knowledge_sha256:hash('d'),definition_sha256:hash('e'),applicability:'same_verified_family_and_rule_version'}],knowledge_published:[{knowledge_id:'procedure.notice',version:3,knowledge_sha256:hash('f'),qualification:{status:'qualified',definition_sha256:hash('1')}}]},projection={claim_id:s.claim_id,revision:3,state_sha256:s.state_sha256},event={claim_id:s.claim_id,seq:3,revision:3,state_sha256:s.state_sha256,event_sha256:hash('2'),kind:'action.completed',payload:s.actions[0]},replay={state:s,projection,events:[event],through_seq:3,current_revision:8,current_state_sha256:hash('3'),current_event_sha256:hash('4'),provenance:{source_roster_sha256:hash('5')}},before=JSON.stringify({s,projection,event,replay});
 for(const detail of ['step','documents','knowledge','sources']) {
  const html=ui.workMarkup(s,projection,'decision',[event],detail,{}, {mode:'replay',replay}),header=html.match(/<header[\s\S]*?<\/header>/)[0],nav=html.match(/<nav class="au-context-nav"[\s\S]*?<\/nav>/)[0];
  assert.equal([...header.matchAll(/data-au-detail="activity"/g)].length,1);assert.match(header,/>History<\/button>/);assert.doesNotMatch(header,/data-au-refresh-claim|>Record<\/button>/);assert.doesNotMatch(nav,/data-au-detail="activity"/);
  const now=html.match(/<div class="au-now"[\s\S]*?<\/div>/)[0];assert.deepEqual([...now.matchAll(/data-au-inspect="([^"]+)" data-au-record-id="([^"]*)"/g)].map(match=>[match[1],match[2]]),[['event','3']],'the Now line offers only the current accepted event');
  assert.match(html,new RegExp(`data-au-panel="${detail}"`));assert.doesNotMatch(html.replace(now,''),/data-au-inspect="(?:claim|fact|requirement|step|use|publication|knowledge|event|action|replay)"|au-replay-record-link/);
  if(detail==='step'){assert.match(html,/data-au-selected-step="decision"/);assert.match(html,/data-au-forming/);assert.match(html,/au-forming-documents/);assert.match(html,/data-au-select="decision" data-au-select-document="notice" data-au-select-obligation="need:notice"/);}if(detail==='documents'){assert.match(html,/Document checklist/);assert.match(html,/data-au-obligation="need:notice"/);}if(detail==='knowledge'){assert.match(html,/data-au-version="2"/);assert.match(html,/data-au-knowledge-sha="d{64}"/);}
 }
 const history=ui.workMarkup(s,projection,'decision',[event],'activity',{}, {mode:'replay',replay});assert.match(history,/data-au-inspect="claim"[^>]*>Case details<\/button>/);assert.match(history,/data-au-inspect="event" data-au-record-id="3">Details<\/button>/);assert.ok(history.includes(`data-au-inspect="action" data-au-record-id="${ui.actionRows(s,[event])[0].instanceId}">Details</button>`));assert.match(history,/data-au-inspect="replay"[^>]*>Playback details<\/button>/);assert.doesNotMatch(history,/au-replay-record-link/);
 assert.deepEqual(ui.contextualRecord(s,projection,[event],'claim'),{state:s,projection});assert.equal(ui.contextualRecord(s,projection,[event],'replay','',{},replay),replay);assert.deepEqual(ui.contextualRecord(s,projection,[event],'event','3'),event);assert.deepEqual(ui.contextualRecord(s,projection,[event],'action',ui.actionRows(s,[event])[0].instanceId).receipt,s.actions[0].receipt);assert.equal(JSON.stringify({s,projection,event,replay}),before);
});

test('unstarted Cases and canonical demo rows show original identity and message without generic state badges',()=>{
 for(const roster of [ui.REFERENCE_DEMO_CASES,ui.DEMO_CASES]){
 const rows=roster.map((demo,index)=>({...original(),claim_id:demo.claim_id,title:`Exact original title ${index}`,source_preview:{text:`Exact original message ${index}`}})),before=JSON.stringify(rows),cases=ui.claimsMarkup(rows),demo=ui.demoItineraryMarkup(rows,null,null,roster);
 for(const [index,row] of rows.entries()){assert.ok(cases.includes(`data-au-claim="${row.claim_id}"`));assert.ok(cases.includes(row.source_preview.text));assert.ok(demo.includes(`data-au-claim="${row.claim_id}"`));assert.ok(demo.includes(row.title));}
 assert.equal([...cases.matchAll(/<p class="au-claim-state"><span class="au-claim-status-word">Not started<\/span><\/p>/g)].length,rows.length,'each unprocessed row says Not started as text');assert.doesNotMatch(cases,/class="au-status"|>Not run<|>Received</);assert.doesNotMatch(demo,/class="au-status"|>Not started<|>Not run<|>Status not loaded</);assert.equal(JSON.stringify(rows),before);assert.equal(ui.matchingClaims(rows,{filter:'not_started'}).length,9,'the recorded status remains available for exact filtering');
 }
});

test('forming knowledge preserves accepted version use and origin without borrowing a later version or establishing current facts',()=>{
 const use={knowledge_id:'procedure.unit',version:2,definition_sha256:hash('d'),workflow_id:'unit-current-workflow',applicability:'same_verified_family_and_rule_version'},publication={knowledge_id:'procedure.unit',version:3,knowledge_sha256:hash('f'),source_claim_id:'unit-current-case',qualification:{status:'qualified',definition_sha256:hash('1')},added_document_types:['unit_notice'],obligations:[{document_type:'unit_notice',label:'Recorded notice'}],evidence_recipes:[{document_type:'unit_notice',required_fields:['recorded_sender','recorded_date']}]},state={...original(),claim_id:'unit-current-case',revision:15,mode:'saved',status:'running',knowledge_uses:[use],knowledge_published:[publication],facts:[]},prior={knowledge_id:use.knowledge_id,version:2,knowledge_sha256:hash('e'),source_claim_id:'unit-prior-origin',qualification:{status:'qualified',definition_sha256:hash('d')}},latest={knowledge_id:use.knowledge_id,version:3,knowledge_sha256:hash('f'),source_claim_id:'unit-later-origin',qualification:{status:'qualified',definition_sha256:hash('1')}},data={versions:[latest,prior],uses:[],quarantined:[]},before=JSON.stringify({state,data});
 const html=ui.formingKnowledgeMarkup(state,data);assert.match(html,/Version 2/);assert.match(html,/Saved for reuse · Version 3/);assert.match(html,/data-au-version="2"[^>]*data-au-knowledge-sha=""[^>]*data-au-definition-sha="d{64}"/,'a use with only a definition hash cannot invent a knowledge hash');assert.match(html,/data-au-version="3"[^>]*data-au-knowledge-sha="f{64}"[^>]*data-au-definition-sha="1{64}"/);assert.match(html,/data-au-claim="unit-prior-origin"/);assert.doesNotMatch(html,/data-au-claim="unit-later-origin"/);assert.match(html,/From this case’s source evidence\./);assert.match(html,/Added recorded notice requirements: recorded sender, recorded date\./);
 assert.doesNotMatch(ui.knowledgeOriginMarkup(state,use,{versions:[latest]}),/Source case|unit-later-origin/,'a later version cannot supply the used version origin');for(const invalid of [{...use,definition_sha256:hash('0')},{...use,knowledge_sha256:hash('0')},{...use,definition_sha256:undefined}])assert.equal(ui.knowledgeOriginMarkup(state,invalid,data),'');
 assert.deepEqual(ui.contextualRecord(state,{},[],'use','0'),use);assert.deepEqual(ui.contextualRecord(state,{},[],'publication','0'),publication);assert.deepEqual(ui.contextualRecord(state,{},[],'claim').state.facts,[]);assert.equal(JSON.stringify({state,data}),before);
});
