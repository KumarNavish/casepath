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
    evaluation:{nodes:[{node_id:'start',execution_state:'completed'},{node_id:'branch',execution_state:'ready'}],documents:[{document_type:'notice',route_state:'needed_now',review_state:'unreviewed'}]},
    facts:[{fact_id:'condition:family_home',label:'Family home',status:'true',summary:'The customer reports a family home.',citations:[]},{fact_id:'fact:notice',label:'Separate notice',status:'unresolved',summary:'A separate notice is required.'}],
    obligations:[{obligation_id:'obligation:branch:notice',node_id:'branch',decision_node_id:'branch',required_fact_ids:['fact:notice'],document_type:'notice',label:'Separate notice',reason:'Service depends on the family-home condition.',rule_refs:['tenancy.v1'],capability_id:'local_inbox.read'}],
    actions:[{result:{action_id:'review:notice:original',type:'document_review',node_ids:['branch'],status:'completed',summary:'Original notice inspected.'},receipt:{receipt_sha256:hash('c')}}],
    source_descriptors:[{claim_id:'claim-a',artifact_id:'original',file_name:'message.txt',sha256:hash('d')}],acquired_sources:[],knowledge_uses:[],...extra};
}
const events = (s,after=0) => ({current_revision:s.revision,events:Array.from({length:s.revision-after},(_,i)=>({seq:after+i+1,kind:i?'work.phase':'intake',revision:after+i+1,state_sha256:after+i+1===s.revision?s.state_sha256:hash('e'),payload:{summary:'Recorded activity'}}))});

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

test('motion targets describe actual persisted node/document changes only',()=>{
 const before=state(),after=structuredClone(before);
 assert.deepEqual(ui.changedTargets(before,after),{nodes:[],documents:[]});
 after.evaluation.nodes[1].execution_state='completed';after.evaluation.documents[0].review_state='sufficient';
 assert.deepEqual(ui.changedTargets(before,after),{nodes:['branch'],documents:['notice']});
 assert.deepEqual(before.evaluation.nodes.map(n=>n.execution_state),['completed','ready']);
});

test('selected step joins condition facts, obligations, rule and nested recorded action from one state',()=>{
 const s=state(),before=JSON.stringify(s),html=ui.inspectorMarkup(s,'branch');
 for(const phrase of ['Family home','Applies','Separate notice','tenancy.v1','Local inbox read','Original notice inspected.']) assert.ok(html.includes(phrase),phrase);
 assert.ok(!ui.inspectorMarkup(s,'start').includes('Original notice inspected.'));
 assert.equal(JSON.stringify(s),before);
 const docs=ui.obligationMarkup(s,'branch');assert.match(docs,/data-au-select="branch"/);assert.match(docs,/Needed now/);
});

test('deferral and prepared request retain missing evidence and external authority boundary',()=>{
 const s=state({status:'deferred',outcome:{status:'deferred',title:'Evidence assessed',summary:'Service is not yet established.',missing_evidence:[{label:'Separate notice'}],authority_limits:['External filing is not configured.'],request_draft:{status:'prepared_not_sent',subject:'Evidence request',body:'Please provide the notice.'}}});
 const html=ui.workMarkup(s,{},'branch',[]);
 for(const phrase of ['Evidence still needed','Separate notice','External filing is not configured.','Prepared · not sent','Please provide the notice.']) assert.ok(html.includes(phrase),phrase);
 assert.doesNotMatch(html,/>Approve|>Apply|>Send request/);
 assert.match(ui.workMarkup(state({status:'deferred',deferral:{code:'unsupported_format',reason:'The image has no supported extraction.'}}),{},'start',[]),/The image has no supported extraction/);
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
 const html=ui.knowledgeMarkup({versions:[{knowledge_id:'k1',version:1,title:'Service process',source_claim_id:'claim-a',knowledge_sha256:hash('a'),qualification:{status:'qualified',regression_cases:243,checks:['no_case_values_or_files']}}],uses:[],quarantined:[{knowledge_id:'q1',qualification:{reason:'Changed rule identity'}}]});
 assert.match(html,/243 branch assignments checked/);assert.match(html,/No case values or files/);assert.match(html,/Changed rule identity/);assert.doesNotMatch(html,/more accurate|improved accuracy|human approved/i);
});

// A minimal DOM boundary exercises the production mount/request/submit lifecycle.
// It does not stand in for browser layout or native keyboard acceptance.
function dom() {
 const listeners=new Map(),doc={activeElement:null,hidden:false,addEventListener(){},removeEventListener(){}};
 const status={textContent:'',classList:{toggle(){}}},message={textContent:''};
 const submit={disabled:false,textContent:''},fields={title:{value:'New title'},message:{value:'Original source message'},files:{files:[]}};
 const form={elements:fields,matches:s=>s.includes('data-au-intake'),querySelector:s=>s==='.au-form-status'?message:submit,querySelectorAll:()=>[...Object.values(fields),submit]};
 const claimList={innerHTML:''},service={textContent:''},heading={focus(){doc.activeElement=this;}};
 const host={innerHTML:'',contains:()=>false,querySelector(s){return {'[data-au-intake]':form,'[data-au-claims]':claimList,'[data-au-service]':service,'button[type="submit"]':submit,h1:heading}[s]||null;},querySelectorAll:()=>[]};
 const dialog={open:false,addEventListener(){},removeEventListener(){},close(){this.open=false;}};
 const container={ownerDocument:doc,classList:{add(){}},innerHTML:'',querySelector(s){return {'[data-au-view]':host,'.au-global-status':status,dialog}[s];},querySelectorAll:()=>[],addEventListener(type,fn){listeners.set(type,fn);},removeEventListener(type){listeners.delete(type);},contains:()=>true};
 return {container,host,form,fields,message,submit,status,listeners};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const response=(data,code=200)=>({ok:code<400,status:code,json:async()=>data});
function fakeApi(overrides={}) {
 const calls=[];
 const fetch=async(path,init)=>{calls.push({path,init});if(overrides.handle){const result=await overrides.handle(path,init,calls);if(result)return result;}
  if(path.endsWith('/status'))return response({enabled:true,provider_ready:true,limits:{}});
  if(path.endsWith('/claims')&&init.method!=='POST')return response({claims:[]});
  if(path.includes('/events?'))return response(events(state()));
  return response(state());};
 return {fetch,calls};
}

test('uncertain intake retries the identical payload/key with required mutation header and never auto-retries',async t=>{
 const f=dom();let posts=0;const api=fakeApi({handle:async(path,init)=>{if(init.method==='POST'){posts++;if(posts===1)throw new Error('Connection lost');return response(state());}}});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
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

test('local file validation sends nothing and leaves the intake editable',async t=>{
 const f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 f.fields.files.files=Array.from({length:21},()=>({name:'one.txt'}));
 await f.listeners.get('submit')({target:f.form,preventDefault(){}});
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);assert.equal(f.fields.title.disabled,false);assert.match(f.message.textContent,/at most 20/);assert.doesNotMatch(f.message.textContent,/unconfirmed/);
});

test('pause is an explicit guarded action and an uncertain response retains its exact key',async t=>{
 const f=dom(),api=fakeApi({handle:async(path,init)=>{if(path.endsWith('/pause'))throw new Error('Pause response lost');}}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 const target={dataset:{},disabled:false,isConnected:true,textContent:'Pause work',closest(){return this;},hasAttribute:attr=>attr==='data-au-pause'};
 f.listeners.get('click')({target});await settle();f.listeners.get('click')({target});await settle();
 const pauses=api.calls.filter(call=>call.path.endsWith('/pause'));assert.equal(pauses.length,2);assert.equal(pauses[0].init.body,pauses[1].init.body);assert.deepEqual({...JSON.parse(pauses[0].init.body),idempotency_key:undefined},{expected_revision:3,expected_state_sha256:hash('a'),idempotency_key:undefined});assert.equal(target.textContent,'Retry pause');
 assert.match(ui.workMarkup(state(),{},'branch',[]),/data-au-pause/);assert.doesNotMatch(ui.workMarkup(state({status:'deferred'}),{},'branch',[]),/data-au-pause/);
});

test('module destroy without a container supports the pagehide integration contract',async()=>{
 const f=dom(),api=fakeApi();ui.mount(f.container,{fetch:api.fetch});await settle();ui.destroy();assert.equal(f.container.innerHTML,'');assert.equal(f.listeners.size,0);
});

test('ready execution limits come only from the backend capability projection without changing sealed state',()=>{
 const s=state(),before=JSON.stringify(s),projection={node_capabilities:{branch:{id:null,authorized:false,reason:'This step requires an unconfigured filing capability.'}}};
 assert.match(ui.graphMarkup(s,'branch',projection),/Ready · execution unavailable/);
 assert.match(ui.inspectorMarkup(s,'branch',projection),/This step requires an unconfigured filing capability\./);
 assert.equal(JSON.stringify(s),before);
 const allowed={node_capabilities:{branch:{id:'local_assessment.record',authorized:true,reason:'Record the verified internal assessment.'}}};
 assert.match(ui.inspectorMarkup(s,'branch',allowed),/Record the verified internal assessment/);
 assert.doesNotMatch(ui.graphMarkup(s,'branch',allowed),/execution unavailable/);
 // No hardcoded policy: an arbitrary future step gets exactly its projected authority.
 s.graph.nodes[1].node_id='future';s.evaluation.nodes[1].node_id='future';s.graph.edges[0].target_node_id='future';
 assert.match(ui.graphMarkup(s,'future',{node_capabilities:{future:projection.node_capabilities.branch}}),/execution unavailable/);
});

test('reuse exposes recorded applicability and avoided mechanical work without estimating savings',()=>{
 const use={knowledge_id:'procedure.one',version:2,applicability:'same_verified_family_and_rule_version',avoided_rule_compilations:1,avoided_qualification_cases:243};
 const html=ui.knowledgeMarkup({versions:[],uses:[use],quarantined:[]})+ui.workMarkup(state({knowledge_uses:[use]}),{},'branch',[]);
 assert.match(html,/Same verified family and rule version/);assert.match(html,/1 rule compilation avoided/);assert.match(html,/243 qualification cases reused/);assert.doesNotMatch(html,/saved.*seconds|more accurate|improved accuracy/);
 assert.doesNotMatch(ui.knowledgeMarkup({versions:[],uses:[{knowledge_id:'k',version:1}],quarantined:[]}),/compilation avoided|cases reused/);
});

test('knowledge inspection connects reusable steps, required facts, obligations and recipe rules to immutable lineage',()=>{
 const base={knowledge_id:'procedure.one',version:1,title:'Service process',knowledge_sha256:hash('a'),graph:state().graph,facts:state().facts,obligations:state().obligations,qualification:{status:'qualified'}};
 const next={...base,version:2,knowledge_sha256:hash('b'),parent_knowledge_sha256:hash('a'),parent_definition_sha256:hash('d'),change_reason:'Added a qualified service-evidence recipe.',evidence_recipes:[{document_type:'notice',required_fields:['Addressee','Delivery date'],summary:'Original notice must establish service.',rule_refs:['tenancy.v1']}]};
 const html=ui.knowledgeMarkup({versions:[base,next],uses:[],quarantined:[]});
 for(const expected of ['Reusable definition','Inspect message','Check separate service','Family home','Separate notice','Addressee','Delivery date','tenancy.v1','Added a qualified service-evidence recipe.','Parent knowledge','Version history'])assert.ok(html.includes(expected),expected);
 assert.ok(html.includes(hash('a')));assert.ok(html.includes(hash('d')));
});

test('MIME fallbacks affect only blank types and never rewrite submitted bytes',async t=>{
 for(const [file,expected]of [[{name:'source.EML',type:''},'message/rfc822'],[{name:'a.txt',type:''},'text/plain'],[{name:'a.md',type:''},'text/markdown'],[{name:'a.csv',type:''},'text/csv'],[{name:'a.json',type:''},'application/json'],[{name:'a.txt',type:'application/custom'},'application/custom'],[{name:'a.unknown',type:''},'application/octet-stream']])assert.equal(ui.mediaType(file),expected);
 const f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 const bytes=Buffer.from('Subject: Exact\r\n\r\nOriginal =3D MIME bytes.\r\n','utf8');
 f.fields.files.files=[{name:'source.eml',type:'',size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}];
 await f.listeners.get('submit')({target:f.form,preventDefault(){}});
 const file=JSON.parse(api.calls.find(call=>call.init.method==='POST').init.body).files[0];assert.equal(file.media_type,'message/rfc822');assert.equal(file.content_base64,bytes.toString('base64'));
});

test('the claim envelope renders capability projection separately from the preserved state',async t=>{
 const f=dom(),saved=state(),original=JSON.stringify(saved),projection={node_capabilities:{branch:{id:null,authorized:false,reason:'Execution requires an unavailable external action.'}}};
 const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response({state:saved,projection}):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 assert.match(f.host.innerHTML,/Ready · execution unavailable/);assert.match(f.host.innerHTML,/Execution requires an unavailable external action\./);assert.equal(JSON.stringify(saved),original);
});

test('the real graph is the hero and the detailed outcome defaults closed without hiding its reason or gap count',()=>{
 const s=state({status:'deferred',outcome:{title:'Deferred',summary:'A termination dispute.',authority_limits:['Filing capability is not configured.'],missing_evidence:[{label:'Notice'},{label:'Receipt'}]}});
 const html=ui.workMarkup(s,{},'branch',[]);
 assert.match(html,/<details class="au-outcome"[^>]*data-au-disclosure="outcome"[^>]*><summary>/);
 assert.doesNotMatch(html,/<details class="au-outcome"[^>]* open/);
 const summary=html.match(/<details class="au-outcome"[^>]*><summary>(.*?)<\/summary>/s)[1];
 assert.match(summary,/2 evidence gaps/);assert.match(summary,/Filing capability is not configured/);
 assert.ok(html.indexOf('class="au-process-hero"')<html.indexOf('class="au-work-layout"'));
 assert.match(html,/class="au-graph-viewport"/);assert.match(html,/--au-ranks:2/);
});

test('compact graph labels preserve complete node names and rule text remains inspectable',()=>{
 const s=state();s.graph.nodes[1].label='Preserve challenge or extension deadline';s.graph.nodes[1].meaning='The process includes a step owned by claim_handler.';s.graph.nodes[1].authority={title:'Admitted tenancy workflow',quote:'Exact recorded operational rule.'};
 const html=ui.graphMarkup(s,'branch');assert.match(html,/Preserve deadline/);assert.match(html,/aria-label="Preserve challenge or extension deadline/);
 const inspector=ui.inspectorMarkup(s,'branch');assert.match(inspector,/<summary>Admitted rules<\/summary>/);assert.match(inspector,/Admitted tenancy workflow/);assert.match(inspector,/Exact recorded operational rule/);
 assert.ok(inspector.indexOf('The process includes')>inspector.indexOf('<summary>Admitted rules'));
});

test('only an explicitly paused deferral offers guarded resume with one retained request identity',async t=>{
 const paused=state({status:'deferred',deferral:{code:'paused',reason:'Work paused.'}}),f=dom();
 const api=fakeApi({handle:async(path,init)=>{if(path.endsWith('/resume'))throw new Error('Resume response lost');if(path.endsWith('/claims/claim-a'))return response(paused);}});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 assert.match(f.host.innerHTML,/data-au-resume/);assert.doesNotMatch(ui.workMarkup(state({status:'deferred',deferral:{code:'missing_evidence'}}),{},'branch',[]),/data-au-resume/);
 const target={dataset:{},disabled:false,isConnected:true,textContent:'Resume work',closest(){return this;},hasAttribute:attr=>attr==='data-au-resume'};
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
 const before=state(),after=structuredClone(before);after.revision=4;after.state_sha256=hash('f');after.evaluation.nodes[1].execution_state='completed';after.evaluation.documents[0].review_state='sufficient';after.facts[1].status='established';
 const accepted=ui.acceptEvents(3,events(after,3),after),plan=ui.transitionPlan(before,after,accepted,[]);
 assert.deepEqual(plan.nodes.map(row=>row.id),['branch']);assert.deepEqual(plan.edges.map(row=>row.id),['next']);assert.deepEqual(plan.documents.map(row=>row.id),['notice']);assert.deepEqual(plan.facts.map(row=>row.id),['fact:notice']);
 assert.ok(Math.max(...plan.edges.map(row=>row.delay+row.duration))<=Math.min(...plan.nodes.map(row=>row.delay)));
 assert.ok(Math.max(...plan.nodes.map(row=>row.delay+row.duration))<=Math.min(...plan.documents.map(row=>row.delay)));
 assert.ok(plan.duration<=800);
 assert.equal(ui.transitionPlan(before,after,ui.acceptEvents(null,events(after),after),[]),null);
 assert.equal(ui.transitionPlan(before,after,ui.acceptEvents(3,events(after,3),after,true),[]),null);
 assert.equal(ui.transitionPlan(after,after,ui.acceptEvents(4,{current_revision:4,events:[]},after),[]),null);
});

function motionFixture(){
 const calls=[],clones=[],cancelled=[];
 const element=(kind,id)=>({dataset:{[kind]:id},isConnected:true,contains:()=>false,animate(frames,options){calls.push({kind,id,frames,options});return{finished:new Promise(()=>{}),cancel(){cancelled.push(id);}};},getTotalLength:()=>120,cloneNode(){const clone=element('clone',id);clone.setAttribute=()=>{};clone.remove=()=>{clone.removed=true;};clones.push(clone);return clone;},parentNode:{appendChild(){}}});
 const all=[element('auNode','branch'),element('auEdge','next'),element('auDocument','notice'),element('auFact','fact:notice'),element('auStage','process')];
 const host={querySelectorAll:selector=>all.filter(el=>({'[data-au-node]':'auNode','[data-au-edge]':'auEdge','[data-au-document]':'auDocument','[data-au-fact]':'auFact','[data-au-stage]':'auStage'})[selector] in el.dataset)};
 return{host,calls,clones,cancelled};
}
test('reduced motion, hidden views, modal inspection and keyboard mode consume changes without running animations',()=>{
 const plan={nodes:[{id:'branch',delay:160,duration:220}],edges:[{id:'next',delay:0,duration:160}],documents:[{id:'notice',delay:580,duration:180}],facts:[],stages:[],duration:760};
 for(const blocked of [{reducedMotion:true},{hidden:true},{dialogOpen:true},{keyboard:true}]){const f=motionFixture();const run=ui.animateTransition(f.host,plan,blocked);assert.equal(f.calls.length,0);assert.equal(f.clones.length,0);run.cancel();}
 const f=motionFixture(),run=ui.animateTransition(f.host,plan,{});assert.equal(f.clones.length,1);assert.ok(f.calls.some(row=>row.kind==='clone'));assert.ok(f.calls.some(row=>row.kind==='auDocument'));assert.ok(f.calls.every(row=>row.options.delay+row.options.duration<=800));run.cancel();assert.ok(f.clones.every(clone=>clone.removed));assert.equal(f.cancelled.length,f.calls.length);
});


test('knowledge reuse and quarantine cannot be presented as newly learned qualified knowledge',()=>{
 const s=state({status:'deferred',run_id:'run.one',knowledge_published:[{qualification:{status:'quarantined'}}],knowledge_uses:[{knowledge_id:'k',version:1}]}),start={kind:'work.started',payload:{run_id:'run.one'}};
 const reuse={kind:'knowledge.used',payload:{knowledge:{knowledge_id:'k',version:1}}};
 const rejected={kind:'knowledge.published',payload:{knowledge:{qualification:{status:'quarantined'}}}};
 assert.equal(ui.progressModel(s,[start,reuse]).stages.at(-1).state,'recorded');
 const quarantine=ui.progressModel(s,[start,reuse,rejected]).stages.at(-1);assert.equal(quarantine.state,'blocked');assert.equal(quarantine.complete,false);assert.match(quarantine.detail,/0 published · 1 reused · 1 quarantined/);
 const html=ui.workMarkup(s,{},'branch',[rejected]);assert.match(html,/Knowledge candidate withheld/);assert.doesNotMatch(html,/Qualified knowledge version published/);
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
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());
 for(let i=0;i<20&&wrapper.hidden;i++)await settle();assert.equal(wrapper.hidden,false);assert.equal(f.fields.title.value,'New title');
 f.listeners.get('change')({target:select});assert.equal(f.fields.title.value,packet.title);assert.equal(f.fields.message.value,packet.message);assert.deepEqual(Buffer.from(await f.fields.files.files[0].arrayBuffer()),source);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
 await f.listeners.get('submit')({target:f.form,preventDefault(){}});assert.equal(select.disabled,true);const originalTitle=f.fields.title.value;select.disabled=false;select.value='0';f.fields.title.value='Retained pending title';f.listeners.get('change')({target:select});assert.equal(f.fields.title.value,'Retained pending title');assert.equal(api.calls.filter(call=>call.init.method==='POST').length,1);assert.equal(originalTitle,packet.title);
});


function routingFixture(t,fragment='') {
 const old=Object.fromEntries(['location','history','addEventListener','removeEventListener'].map(key=>[key,globalThis[key]])),listeners=new Map(),entries=['http://localhost:8123/?journey=autonomous'+fragment];let index=0,pushes=0;
 globalThis.location=new URL(entries[0]);
 globalThis.addEventListener=(type,fn)=>listeners.set(type,fn);globalThis.removeEventListener=(type,fn)=>{if(listeners.get(type)===fn)listeners.delete(type);};
 globalThis.history={pushState(_state,_unused,url){entries.splice(++index);entries.push(new URL(url,globalThis.location).href);globalThis.location=new URL(entries[index]);pushes++;}};
 const fire=()=>{listeners.get('popstate')?.();listeners.get('hashchange')?.();};
 t.after(()=>Object.assign(globalThis,old));
 return {listeners,get pushes(){return pushes;},get hash(){return globalThis.location.hash;},external(fragment){globalThis.location.hash=fragment;fire();},back(){if(index>0){globalThis.location=new URL(entries[--index]);fire();}},forward(){if(index+1<entries.length){globalThis.location=new URL(entries[++index]);fire();}}};
}
function navClick(f,value) {
 const target={dataset:{auNav:value},closest(){return this;},hasAttribute:attr=>attr==='data-au-nav'};f.listeners.get('click')({target});
}
test('initial deep links and duplicate browser history events read saved state once without adding entries',async t=>{
 const routing=routingFixture(t,'#autonomous/claim/claim-a'),f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 assert.match(f.host.innerHTML,/Working process/);assert.equal(routing.pushes,0);assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a')).length,1);
 routing.external('#autonomous/knowledge');await settle();assert.match(f.host.innerHTML,/>Knowledge</);assert.equal(api.calls.filter(call=>call.path.endsWith('/knowledge')).length,1);assert.equal(routing.pushes,0);
 routing.external('#autonomous/claim/claim-a');await settle();assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a')).length,2);assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a/events?after=0')).length,2);
 routing.external('#autonomous/claim/claim-a');await settle();assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a')).length,2);assert.equal(routing.pushes,0);
 controller.destroy();assert.equal(routing.listeners.size,0);
});

test('internal Claims, Knowledge and claim navigation adds only changed fragments and supports Back/Forward',async t=>{
 const routing=routingFixture(t),f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();assert.equal(routing.pushes,0);
 navClick(f,'knowledge');await settle();assert.equal(routing.hash,'#autonomous/knowledge');assert.equal(routing.pushes,1);
 navClick(f,'knowledge');await settle();assert.equal(routing.pushes,1);
 await controller.openClaim('claim-a');assert.equal(routing.pushes,2);assert.match(f.host.innerHTML,/Working process/);
 routing.back();await settle();assert.match(f.host.innerHTML,/>Knowledge</);routing.back();await settle();assert.match(f.host.innerHTML,/Bring the claim/);
 routing.forward();await settle();assert.match(f.host.innerHTML,/>Knowledge</);routing.forward();await settle();assert.match(f.host.innerHTML,/Working process/);assert.equal(routing.pushes,2);
 navClick(f,'intake');await settle();assert.equal(routing.hash,'');assert.equal(routing.pushes,3);assert.equal(globalThis.location.search,'?journey=autonomous');
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('a browser route change during an uncertain intake waits for its result and preserves the exact retry request',async t=>{
 const routing=routingFixture(t),f=dom();let rejectPost;
 const api=fakeApi({handle:async(path,init)=>{if(init.method==='POST')return new Promise((resolve,reject)=>{rejectPost=reject;});}}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 const submission=f.listeners.get('submit')({target:f.form,preventDefault(){}});await settle();routing.external('#autonomous/knowledge');assert.equal(api.calls.filter(call=>call.path.endsWith('/knowledge')).length,0);
 rejectPost(new Error('Intake response unconfirmed'));await submission;await settle();assert.match(f.host.innerHTML,/>Knowledge</);assert.equal(routing.pushes,0);
 routing.external('');await settle();assert.match(f.message.textContent,/same saved intake request/);assert.equal(f.fields.title.disabled,true);assert.equal(f.submit.disabled,false);
 const retry=f.listeners.get('submit')({target:f.form,preventDefault(){}});await settle();const writes=api.calls.filter(call=>call.init.method==='POST');assert.equal(writes.length,2);assert.equal(writes[0].init.body,writes[1].init.body);rejectPost(new Error('Still unconfirmed'));await retry;
});


test('mobile graph selection reveals the selected inspector and Back returns to its node; polling and desktop stay settled',async t=>{
 const originalMatch=globalThis.matchMedia;let mobile=true;globalThis.matchMedia=query=>({matches:query==='(max-width: 800px)'&&mobile,addEventListener(){},removeEventListener(){}});t.after(()=>{globalThis.matchMedia=originalMatch;});
 const f=dom(),doc=f.container.ownerDocument,scrolls=[];
 function element(attr,value){return{dataset:{[attr.replace(/^data-/, '').replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]:value},hasAttribute:name=>name===attr,getAttribute:name=>name===attr?value:null,matches:()=>false,closest(){return this;},focus(options){doc.activeElement=this;this.focusOptions=options;},scrollIntoView(options){scrolls.push({attr,value,options});}};}
 const node=element('data-au-node','branch'),heading=element('data-au-inspector-heading','branch'),back=element('data-au-back-process','branch'),relation=element('data-au-select','branch'),inspector={scrollIntoView(options){scrolls.push({attr:'inspector',options});}};
 const all=[node,heading,back,relation],originalQuery=f.host.querySelector;
 f.host.contains=element=>all.includes(element);f.host.querySelector=selector=>selector==='[data-au-inspector-heading]'?heading:selector==='.au-inspector'?inspector:originalQuery(selector);
 f.host.querySelectorAll=selector=>all.filter(el=>el.hasAttribute(selector.slice(1,-1)));
 let saved=state();const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');assert.equal(scrolls.length,0);
 node.focus();f.listeners.get('click')({target:node});assert.equal(doc.activeElement,heading);assert.deepEqual(heading.focusOptions,{preventScroll:true});assert.deepEqual(scrolls.at(-1),{attr:'inspector',options:{block:'start',behavior:'instant'}});
 saved=state({revision:4,state_sha256:hash('f')});const beforePoll=scrolls.length;await controller.refresh();assert.equal(doc.activeElement,heading);assert.equal(scrolls.length,beforePoll);
 f.listeners.get('click')({target:back});assert.equal(doc.activeElement,node);assert.deepEqual(scrolls.at(-1),{attr:'data-au-node',value:'branch',options:{block:'center',behavior:'instant'}});
 f.listeners.get('click')({target:relation});assert.equal(doc.activeElement,node);assert.equal(scrolls.at(-1).attr,'data-au-node');assert.equal(scrolls.at(-1).options.block,'nearest');
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
 assert.match(f.host.innerHTML,/revision 4/);assert.match(f.host.innerHTML,/Reading the original agreement/);assert.doesNotMatch(f.status.textContent,/Updates paused/);
});

test('a failed render is retried from saved state even if the next poll has the same revision',async t=>{
 const f=dom();let saved=state();const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 let html=f.host.innerHTML,fail=true;Object.defineProperty(f.host,'innerHTML',{get:()=>html,set:value=>{if(fail){fail=false;throw new Error('Transient render failure');}html=value;}});
 saved=state({revision:4,state_sha256:hash('f')});await controller.refresh();
 assert.match(f.status.textContent,/Updates paused/);assert.match(html,/revision 3/);
 await controller.refresh();assert.match(html,/revision 4/);assert.match(f.status.textContent,/Connection restored/);
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});
