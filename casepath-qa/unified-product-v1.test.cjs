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
 const html=ui.collectionMarkup(rows);assert.match(html,/150/);assert.match(html,/Defects &amp; repairs/);assert.match(html,/Lease termination/);assert.match(html,/Rent changes/);assert.match(html,/Rare original passage/);
 const unclassified=ui.collectionMarkup([{...original(),title:'Mold termination rent increase'}]);assert.doesNotMatch(unclassified,/data-au-domain="defect_mold_heating"[^>]*><span>[^<]*<\/span><strong>1/);
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
 const html=ui.collectionMarkup(rows);assert.match(html,/data-au-claim="clm_original"/);assert.doesNotMatch(html,/data-au-claim="added"/);assert.match(html,/data-au-collection-count[^>]*>1 of 1/);
 const added=ui.collectionMarkup(rows,{scope:'added'});assert.match(added,/data-au-claim="added"/);assert.doesNotMatch(added,/data-au-claim="clm_original"/);assert.match(added,/Added intake/);
 assert.deepEqual(ui.matchingClaims(rows,{scope:'originals'}).map(row=>row.claim_id),['clm_original']);assert.deepEqual(ui.matchingClaims(rows,{scope:'added'}).map(row=>row.claim_id),['added']);
});
test('handling completion labels do not rewrite lifecycle codes or recorded legal outcomes',()=>{
 const rows=['completed','complete','resolved'].map((status,index)=>({...original(),origin:'canonical_original',claim_id:`done_${index}`,status,revision:1,mode:'saved',outcome:{summary:'No settlement has been recorded.'}}));const before=JSON.stringify(rows);
 const html=ui.collectionMarkup(rows);assert.match(html,/Investigation complete/);assert.doesNotMatch(html,/>Resolved</);assert.equal(ui.matchingClaims(rows,{filter:'investigation_complete'}).length,3);assert.equal(ui.matchingClaims(rows,{search:'investigation complete'}).length,3);
 assert.match(ui.workMarkup(rows[2],{},null,[]),/No settlement has been recorded\./);assert.equal(JSON.stringify(rows),before);
});
test('completed steps and actions remain local to a running investigation',()=>{
 const s={...original(),revision:1,mode:'saved',status:'running',graph:{claim_id:'clm_original',nodes:[{node_id:'first',title:'Check original source'}],edges:[]},evaluation:{nodes:[{node_id:'first',execution_state:'completed'}]},actions:[{action_id:'source-check',title:'Source checked',status:'completed'}]};
 const html=ui.workMarkup(s,{},'first',[]);assert.match(html,/class="au-status"[^>]*>Working</);assert.match(html,/class="au-node-state">Completed</);assert.match(html,/au-action-heading[^]*?<span>Completed<\/span>/);assert.doesNotMatch(html,/Investigation complete/);
 assert.match(ui.collectionMarkup([{...s,origin:'canonical_original',status:'completed'}]),/Investigation complete/);assert.equal(s.status,'running');assert.equal(s.actions[0].status,'completed');
});
