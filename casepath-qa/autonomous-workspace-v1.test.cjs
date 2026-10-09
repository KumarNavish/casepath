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
 const form={elements:fields,matches:s=>s.includes('data-au-intake'),querySelector:s=>s==='.au-form-status'?message:submit,querySelectorAll:()=>[...Object.values(fields),submit],contains:element=>Object.values(fields).includes(element),remove(){},replaceWith(){}};
 const claimList={innerHTML:''},service={textContent:''},heading={focus(){doc.activeElement=this;}};
 const host={innerHTML:'',contains:()=>false,querySelector(s){return {'[data-au-intake]':form,'[data-au-claims]':claimList,'[data-au-service]':service,'button[type="submit"]':submit,h1:heading}[s]||null;},querySelectorAll:()=>[]};
 const dialog={open:false,addEventListener(){},removeEventListener(){},close(){this.open=false;}};
 const container={ownerDocument:doc,classList:{add(){}},innerHTML:'',querySelector(s){return {'[data-au-view]':host,'.au-global-status':status,dialog}[s];},querySelectorAll:()=>[],addEventListener(type,fn){listeners.set(type,fn);},removeEventListener(type){listeners.delete(type);},contains:()=>true};
 return {container,host,form,fields,message,submit,status,listeners,dialog};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
const response=(data,code=200)=>({ok:code<400,status:code,json:async()=>data});
function fakeApi(overrides={}) {
 const calls=[];
 const fetch=async(path,init)=>{calls.push({path,init});if(overrides.handle){const result=await overrides.handle(path,init,calls);if(result)return result;}
  if(path.includes('/snapshot?'))return response({detail:'Snapshot capability unavailable'},404);
  if(path.endsWith('/preview'))return response({detail:'Preview capability unavailable'},404);
  if(path.endsWith('/status'))return response({enabled:true,provider_ready:true,limits:{}});
  if(path.endsWith('/claims')&&init.method!=='POST')return response({claims:[]});
  if(path.includes('/events?'))return response(events(state()));
  return response(state());};
 return {fetch,calls};
}

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

test('local file validation sends nothing and leaves the intake editable',async t=>{
 const f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await newClaim(f);
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
 const f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await newClaim(f);
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
 assert.match(html,/data-au-canvas/);
 assert.ok(html.indexOf('class="au-process-hero')<html.indexOf('data-au-panel="step"'));
 assert.match(html,/class="au-graph-viewport(?:\s[^"]*)?"/);assert.match(html,/--au-ranks:2/);
 assert.doesNotMatch(html,/data-au-stage="(?:sources|interpretation|verification|process|knowledge)"/);
});

test('complete graph labels and operational rule text remain inspectable',()=>{
 const s=state();s.graph.nodes[1].label='Preserve challenge or extension deadline';s.graph.nodes[1].meaning='The process includes a step owned by claim_handler.';s.graph.nodes[1].authority={title:'Admitted tenancy workflow',quote:'Exact recorded operational rule.'};
 const html=ui.graphMarkup(s,'branch');assert.match(html,/<strong class="au-node-title">Preserve challenge or extension deadline<\/strong>/);assert.match(html,/aria-label="Preserve challenge or extension deadline/);
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
 const before=state();before.evaluation.edges=[{edge_id:'next',activation:'unresolved'}];const after=structuredClone(before);after.revision=4;after.state_sha256=hash('f');after.evaluation.nodes[1].execution_state='completed';after.evaluation.documents[0].review_state='sufficient';after.facts[1].status='established';
 const accepted=ui.acceptEvents(3,events(after,3),after),plan=ui.transitionPlan(before,after,accepted,[]);
 assert.deepEqual(plan.nodes.map(row=>row.id),['branch']);assert.deepEqual(plan.edges,[]);assert.deepEqual(plan.documents.map(row=>row.id),['notice']);assert.deepEqual(plan.facts.map(row=>row.id),['fact:notice']);
 after.evaluation.edges[0].activation='true';const changedEdgePlan=ui.transitionPlan(before,after,accepted,[]);assert.deepEqual(changedEdgePlan.edges.map(row=>row.id),['next']);
 assert.ok(Math.max(...changedEdgePlan.edges.map(row=>row.delay+row.duration))<=Math.min(...changedEdgePlan.nodes.map(row=>row.delay)));
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
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await newClaim(f);
 await waitFor(()=>!wrapper.hidden);assert.equal(f.fields.title.value,'New title');
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
async function newClaim(f) { navClick(f,'intake');await settle(); }
test('initial deep links and duplicate browser history events read saved state once without adding entries',async t=>{
 const routing=routingFixture(t,'#autonomous/claim/claim-a'),f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 assert.match(f.host.innerHTML,/data-au-graph/);assert.equal(routing.pushes,0);assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a')).length,1);
 routing.external('#autonomous/knowledge');await settle();assert.match(f.host.innerHTML,/>Knowledge in context\.</);assert.equal(api.calls.filter(call=>call.path.endsWith('/knowledge')).length,1);assert.equal(routing.pushes,0);
 routing.external('#autonomous/claim/claim-a');await settle();assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a')).length,2);assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a/events?after=0')).length,2);
 routing.external('#autonomous/claim/claim-a');await settle();assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a')).length,2);assert.equal(routing.pushes,0);
 controller.destroy();assert.equal(routing.listeners.size,0);
});

test('internal Work, Knowledge and claim navigation adds only changed fragments and supports Back/Forward',async t=>{
 const routing=routingFixture(t),f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();assert.equal(routing.pushes,0);
 navClick(f,'knowledge');await settle();assert.equal(routing.hash,'#autonomous/knowledge');assert.equal(routing.pushes,1);
 navClick(f,'knowledge');await settle();assert.equal(routing.pushes,1);
 await controller.openClaim('claim-a');assert.equal(routing.pushes,2);assert.match(f.host.innerHTML,/data-au-graph/);
 routing.back();await settle();assert.match(f.host.innerHTML,/>Knowledge in context\.</);routing.back();await settle();assert.match(f.host.innerHTML,/>Every case has a source\.</);
 routing.forward();await settle();assert.match(f.host.innerHTML,/>Knowledge in context\.</);routing.forward();await settle();assert.match(f.host.innerHTML,/data-au-graph/);assert.equal(routing.pushes,2);
 navClick(f,'intake');await settle();assert.equal(routing.hash,'#autonomous/new');assert.equal(routing.pushes,3);assert.equal(globalThis.location.search,'?journey=autonomous');
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('a browser route change during an uncertain intake waits for its result and preserves the exact retry request',async t=>{
 const routing=routingFixture(t),f=dom();let rejectPost;
 const api=fakeApi({handle:async(path,init)=>{if(init.method==='POST')return new Promise((resolve,reject)=>{rejectPost=reject;});}}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await newClaim(f);
 const submission=f.listeners.get('submit')({target:f.form,preventDefault(){}});await settle();routing.external('#autonomous/knowledge');assert.equal(api.calls.filter(call=>call.path.endsWith('/knowledge')).length,0);
 rejectPost(new Error('Intake response unconfirmed'));await submission;await settle();assert.match(f.host.innerHTML,/>Knowledge in context\.</);assert.equal(routing.pushes,1,'only the explicit New claim navigation added an entry');
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
 assert.match(f.host.innerHTML,/Verified new revision/);assert.match(f.host.innerHTML,/revision 4/);
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
 return {dataset,isConnected:true,disabled:false,hasAttribute:attr=>attr===attribute,getAttribute:attr=>attr===attribute?value:null,matches:()=>false,closest(){return this;},focus(options){f.container.ownerDocument.activeElement=this;this.focusOptions=options;}};
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
 {claim_id:'claim-a',title:'Notice needs a receipt',status:'deferred',phase_summary:'Waiting for the original receipt'},
 {claim_id:'claim-b',title:'Policy investigation',status:'running',phase_summary:'Checking the cited policy'},
 {claim_id:'claim-c',title:'Completed assessment',status:'resolved',outcome:{summary:'Internal assessment recorded.'}},
 {claim_id:'claim-d',title:'Unsupported original format',status:'failed'},
 {claim_id:'claim-e',title:'Queued acquisition',status:'queued'}
];
test('the default Work collection uses saved statuses and explicit New claim navigation',async t=>{
 const f=dom(),api=fakeApi({handle:async(path,init)=>path.endsWith('/claims')&&init.method!=='POST'?response({claims:claimRows}):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 assert.match(f.container.innerHTML,/<header class="au-identity-header"/);assert.doesNotMatch(f.container.innerHTML,/class="au-rail"/);assert.match(f.container.innerHTML,/data-au-nav="work"/);assert.match(f.container.innerHTML,/data-au-nav="intake"[^>]*>New claim/);
 assert.match(f.host.innerHTML,/class="au-collection(?:\s[^"]*)?"/);assert.doesNotMatch(f.host.innerHTML,/<form[^>]*data-au-intake/);
 const html=ui.claimsMarkup(claimRows);assert.equal([...html.matchAll(/data-au-claim="/g)].length,5);assert.match(html,/Deferred/);assert.match(html,/Working/);assert.match(html,/Resolved/);assert.match(html,/Stopped/);assert.match(html,/Queued/);
 await newClaim(f);assert.match(f.host.innerHTML,/<form[^>]*data-au-intake/);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('search and filters select only matching saved claims and preserve original statuses',()=>{
 const before=JSON.stringify(claimRows),ids=options=>[...ui.claimsMarkup(claimRows,options).matchAll(/data-au-claim="([^"]+)"/g)].map(match=>match[1]);
 assert.deepEqual(ids({filter:'working'}),['claim-b','claim-e']);assert.deepEqual(ids({filter:'deferred'}),['claim-a']);assert.deepEqual(ids({filter:'resolved'}),['claim-c']);assert.deepEqual(ids({filter:'failed'}),['claim-d']);
 assert.deepEqual(ids({search:'RECEIPT'}),['claim-a']);assert.deepEqual(ids({filter:'working',search:'policy'}),['claim-b']);assert.deepEqual(ids({filter:'deferred',search:'policy'}),[]);
 const collection=ui.collectionMarkup(claimRows,{filter:'working',search:'policy'});assert.match(collection,/data-au-collection-count[^>]*>1 of 5/);assert.match(collection,/<strong>2<\/strong> In progress/);assert.match(collection,/<strong>1<\/strong> Deferred/);assert.match(collection,/<strong>1<\/strong> Resolved/);assert.match(collection,/<option value="failed"/);
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

test('each context view keeps the same selected real process and only one visible details body',()=>{
 const s=state(),before=JSON.stringify(s);
 for(const detail of ['step','documents','sources','activity']) {
  const html=ui.workMarkup(s,{},'branch',events(s).events,detail),panels=[...html.matchAll(/<section[^>]*data-au-panel="([^"]+)"[^>]*>/g)];
  assert.equal(panels.length,4);assert.deepEqual(panels.filter(match=>!match[0].includes(' hidden')).map(match=>match[1]),[detail]);
  assert.match(html,new RegExp(`data-au-detail="${detail}" aria-pressed="true"`));assert.match(html,/data-orientation="horizontal"/);assert.match(html,/data-au-node="branch"[^>]*aria-pressed="true"/);assert.match(html,/data-au-selected-step="branch"/);
  assert.match(html,/data-au-panel="sources"[\s\S]*data-au-arrival/);assert.ok(html.indexOf('class="au-process-hero')<html.indexOf('data-au-panel="step"'));
 }
 assert.equal(JSON.stringify(s),before);
});

test('supported document routes stay distinct and evidence intake is reachable from current needs',()=>{
 const statuses=['needed_now','needed_later','held_behind_question','held_not_reviewed','not_needed','optional'],labels=['Needed now','Needed later','Depends on unresolved evidence','Acquired · not established','Not required','Optional'];
 const s=state();s.obligations=statuses.map((status,index)=>({obligation_id:`obligation:${index}`,node_id:'branch',document_type:`document-${index}`,label:`Evidence ${index}`}));s.evaluation.documents=statuses.map((route_state,index)=>({document_type:`document-${index}`,route_state,review_state:'unreviewed'}));
 const markup=ui.obligationMarkup(s,'branch');for(let i=0;i<statuses.length;i++){assert.match(markup,new RegExp(`data-status="${statuses[i]}"`));assert.ok(markup.includes(labels[i]),labels[i]);}
 assert.match(ui.inspectorMarkup(state(),'branch'),/data-au-add-files/);assert.match(ui.workMarkup(state(),{},'branch',[],'sources'),/<form data-au-arrival/);
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

test('claim refresh preserves context, vertical graph scroll, open disclosures and native arrival files',async t=>{
 const f=nativeFixture();let saved=state();const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 f.listeners.get('click')({target:control(f,'data-au-detail','sources')});const form=f.arrival,list=[fileFixture()];form.elements.files.files=list;form.elements.files.focus();f.viewport.scrollTop=184;f.viewport.scrollLeft=27;const rules=f.disclosures.find(node=>node.dataset.auDisclosure==='rules:branch');rules.open=true;
 saved=state({revision:4,state_sha256:hash('f'),phase:'acquiring'});await controller.refresh();
 assert.equal(f.arrival,form);assert.equal(f.arrival.elements.files.files,list);assert.equal(f.container.ownerDocument.activeElement,form.elements.files);assert.equal(f.viewport.scrollTop,184);assert.equal(f.viewport.scrollLeft,27);assert.equal(f.disclosures.find(node=>node.dataset.auDisclosure==='rules:branch').open,true);
 assert.match(f.host.innerHTML,/data-au-context="sources"/);assert.match(f.host.innerHTML,/data-au-node="branch"[^>]*aria-pressed="true"/);
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
 const s=state({run_id:'run.new',actions:[
  {result:{action_id:'old',node_ids:['branch'],status:'completed',summary:'Earlier receipt assessed.'},receipt:{parent_revision:2,receipt_sha256:hash('1'),operation:'document_review'}},
  {result:{action_id:'new',node_ids:['branch'],status:'completed',summary:'Current receipt assessed.'},receipt:{parent_revision:6,receipt_sha256:hash('2'),operation:'document_review'}},
  {result:{action_id:'unknown',node_ids:['branch'],status:'completed',summary:'Legacy assessment without run association.'},receipt:{receipt_sha256:hash('3')}}
 ]}),history=[{seq:1,kind:'work.started',payload:{run_id:'run.old'}},{seq:5,kind:'work.started',payload:{run_id:'run.new'}}];
 assert.deepEqual(ui.actionRows(s,history).map(row=>row.scope),['historical','current','unassociated']);
 const html=ui.inspectorMarkup(s,'branch',{},history);assert.match(html,/data-au-action-scope="historical"[\s\S]*?Recorded in an earlier run[\s\S]*?Earlier receipt assessed/);assert.match(html,/data-au-action-scope="current"[\s\S]*?Recorded in this run[\s\S]*?Current receipt assessed/);assert.match(html,/run association not recorded/);
 assert.ok(html.includes(hash('1')));assert.ok(html.includes(hash('2')));assert.ok(html.includes(hash('3')));assert.deepEqual(ui.actionRows(s,[]).map(row=>row.scope),['unassociated','unassociated','unassociated']);
});

test('a branch inspector joins its own condition, evidence need, document and capability without borrowing sibling facts',()=>{
 const s=state();s.graph.nodes.push({node_id:'excluded',label:'Other conditional path',condition:{flag:'commercial_use'}});s.graph.edges.push({edge_id:'other',source_node_id:'start',target_node_id:'excluded'});s.evaluation.nodes.push({node_id:'excluded',execution_state:'inactive'});s.facts.push({fact_id:'condition:commercial_use',label:'Commercial-only condition',status:'false',summary:'Commercial condition does not apply.'});
 s.facts[0].citations=[{artifact_id:'original',sha256:hash('d'),text_sha256:hash('e'),start_char:0,end_char:11,quote:'Family home'}];
 const projection={node_capabilities:{branch:{authorized:false,id:null,reason:'External dispatch is not configured.'}}},html=ui.inspectorMarkup(s,'branch',projection);
 for(const phrase of ['Check separate service','Family home','Applies','A separate notice is required.','Separate notice','Needed now','tenancy.v1','Local inbox read','External dispatch is not configured.','Family home'])assert.ok(html.includes(phrase),phrase);
 assert.match(html,/data-au-source="original"[^>]*data-au-citation=/);assert.match(html,/data-authorized="false"/);assert.doesNotMatch(html,/Commercial-only condition|Commercial condition does not apply/);
 const graph=ui.graphMarkup(s,'branch',projection);assert.match(graph,/Other conditional path\. Does not apply/);assert.match(graph,/data-au-node="excluded"[^>]*data-status="inactive"/);assert.equal(s.facts[0].status,'true');
});

test('knowledge reuse retains the exact historical version, originating claim and applicability without proving current facts',()=>{
 const old={knowledge_id:'procedure.one',version:1,title:'Service process',source_claim_id:'origin-one',knowledge_sha256:hash('1'),summary:'Original service procedure.',qualification:{status:'qualified',regression_cases:243,checks:['no_case_values_or_files']},graph:state().graph,facts:state().facts,obligations:state().obligations};
 const latest={...old,version:2,source_claim_id:'origin-two',knowledge_sha256:hash('2'),parent_knowledge_sha256:hash('1'),change_reason:'Verified new receipt field.'};
 const use={knowledge_id:'procedure.one',version:1,knowledge_sha256:hash('1'),claim_id:'receiving-claim',applicability:'same_verified_family_and_rule_version',avoided_rule_compilations:1,avoided_qualification_cases:243};
 const html=ui.knowledgeMarkup({versions:[old,latest],uses:[use],quarantined:[]});
 assert.match(html,/data-au-version="2"[^>]*data-current="true"/);assert.match(html,/data-au-version="1"[^>]*data-current="false"/);assert.match(html,/procedure.one · version 1/);assert.match(html,/data-au-claim="origin-one"/);assert.match(html,/data-au-claim="origin-two"/);assert.match(html,/data-au-claim="receiving-claim"/);assert.ok(html.includes(hash('1')));assert.ok(html.includes(hash('2')));assert.match(html,/Same verified family and rule version/);assert.match(html,/243 qualification cases reused/);
 const saved=state({knowledge_uses:[use]}),before=JSON.stringify(saved),claim=ui.workMarkup(saved,{},'branch',[],'activity');assert.match(claim,/procedure.one · version 1/);assert.match(claim,/Evidence needed/);assert.equal(JSON.stringify(saved),before);
 assert.doesNotMatch(claim,/notice.*proven by.*reuse|fact.*established by.*knowledge|human approved|improved accuracy/i);
});

test('full public provenance, receipt checks and quarantine reasons remain inspectable and escaped',()=>{
 const attack='<svg onload="alert(1)">',version={knowledge_id:'k',version:1,title:'Procedure',source_claim_id:'claim-a',knowledge_sha256:hash('a'),qualification:{status:'qualified',regression_cases:243,checks:['no_case_values_or_files'],additional_check:{reason:'Version-specific public check',accepted:true}},source_evidence:{notice:{artifact_id:'original',source_verification:'recorded independent check'}},custom_lineage:{reason:'Public ancestry marker'}};
 const quarantine={knowledge_id:'withheld',qualification:{status:'quarantined',reason:'Exact rule identity changed',details:{failed_check:'public discrepancy marker'}},candidate:{summary:attack}};
 const html=ui.knowledgeMarkup({versions:[version],uses:[],quarantined:[quarantine]});
 for(const value of ['Version-specific public check','recorded independent check','Public ancestry marker','Exact rule identity changed','public discrepancy marker'])assert.ok(html.includes(value),value);
 assert.match(html,/&lt;svg/);assert.doesNotMatch(html,/<svg[^>]*onload=|onload="alert/);assert.match(html,/<details[\s\S]*Provenance/);
 const s=state();s.actions[0].receipt.checks=[{accepted:true,reason:'Public action check',payload:{summary:attack}}];const action=ui.inspectorMarkup(s,'branch');assert.match(action,/Public action check/);assert.match(action,/&lt;svg/);assert.doesNotMatch(action,/<svg[^>]*onload=|onload="alert/);
});

function knowledgeFixture() {
 const f=dom();let html='',rows=[],history=null;
 Object.defineProperty(f.host,'innerHTML',{get:()=>html,set:value=>{
  html=value;history={tagName:'DETAILS',open:false,parentElement:f.host};rows=[...value.matchAll(/data-au-knowledge-identity="([^"]+)"/g)].map(match=>{
   const row=control(f,'data-au-knowledge-identity',match[1]);row.parentElement=match[1].endsWith(':1')?history:f.host;row.attributes={};row.setAttribute=(name,value)=>{row.attributes[name]=value;};row.scrollIntoView=options=>{row.scrollOptions=options;};return row;
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
 const trigger=control(f,'data-au-knowledge','procedure.one');trigger.dataset.auVersion='1';trigger.dataset.auKnowledgeSha=hash('1');f.listeners.get('click')({target:trigger});await waitFor(()=>f.versions.length===2);
 const historical=f.versions.find(row=>row.dataset.auKnowledgeIdentity==='procedure.one:1'),current=f.versions.find(row=>row.dataset.auKnowledgeIdentity==='procedure.one:2');
 assert.equal(routing.hash,`#autonomous/knowledge?knowledge=procedure.one&version=1&sha256=${hash('1')}`);assert.equal(historical.attributes['data-pinned'],'true');assert.equal(current.attributes['data-pinned'],undefined);assert.equal(f.historyDisclosure.open,true);assert.equal(f.container.ownerDocument.activeElement,historical);assert.deepEqual(historical.scrollOptions,{block:'nearest',behavior:'instant'});assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('an unavailable pinned knowledge version or hash never selects the latest version as its replacement',async t=>{
 const routing=routingFixture(t,`#autonomous/knowledge?knowledge=procedure.one&version=1&sha256=${hash('9')}`),f=knowledgeFixture(),latest={knowledge_id:'procedure.one',version:2,title:'Latest procedure',knowledge_sha256:hash('2'),source_claim_id:'origin-two',qualification:{status:'qualified'}};
 const api=fakeApi({handle:async path=>path.endsWith('/knowledge')?response({versions:[latest],uses:[],quarantined:[]}):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await waitFor(()=>f.status.textContent.includes('not available'));
 assert.match(f.status.textContent,/exact reused knowledge version is not available/);assert.equal(f.versions[0].attributes['data-pinned'],undefined);assert.notEqual(f.container.ownerDocument.activeElement,f.versions[0]);assert.equal(routing.pushes,0);assert.ok(routing.hash.includes('version=1'));
 routing.external(`#autonomous/knowledge?knowledge=procedure.one&version=2&sha256=${hash('9')}`);await waitFor(()=>api.calls.filter(call=>call.path.endsWith('/knowledge')).length===2&&f.status.textContent.includes('not available'));
 assert.equal(f.versions[0].attributes['data-pinned'],undefined);assert.notEqual(f.container.ownerDocument.activeElement,f.versions[0]);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('Cancel returns to the same Work search, status filter and scroll position without writing intake',async t=>{
 const f=dom(),search=control(f,'data-au-claim-search'),filter=control(f,'data-au-claim-filter'),rows={innerHTML:''},count={textContent:''},main={scrollTop:0,scrollLeft:0},scrollCalls=[];
 search.matches=selector=>selector==='[data-au-claim-search]';filter.matches=selector=>selector==='[data-au-claim-filter]';
 const prior=Object.fromEntries(['scrollX','scrollY','scrollTo'].map(name=>[name,globalThis[name]]));Object.assign(globalThis,{scrollX:0,scrollY:0,scrollTo(options){scrollCalls.push(options);globalThis.scrollX=options.left;globalThis.scrollY=options.top;}});t.after(()=>Object.assign(globalThis,prior));
 const containerQuery=f.container.querySelector;f.container.querySelector=selector=>selector==='.au-main'?main:containerQuery(selector);
 let html='';Object.defineProperty(f.host,'innerHTML',{get:()=>html,set:value=>{html=value;f.host.scrollTop=0;main.scrollTop=0;main.scrollLeft=0;search.value=value.match(/data-au-claim-search value="([^"]*)"/)?.[1]||'';filter.value=value.match(/<option value="([^"]+)" selected/)?.[1]||'all';}});
 const query=f.host.querySelector;f.host.querySelector=selector=>({'[data-au-claim-search]':search,'[data-au-claim-filter]':filter,'[data-au-claims]':rows,'[data-au-collection-count]':count})[selector]||query(selector);
 const api=fakeApi({handle:async(path,init)=>path.endsWith('/claims')&&init.method!=='POST'?response({claims:claimRows}):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 search.value='receipt';f.listeners.get('input')({target:search});filter.value='deferred';f.listeners.get('change')({target:filter});f.host.scrollTop=127;main.scrollTop=246;main.scrollLeft=6;globalThis.scrollX=12;globalThis.scrollY=418;
 await newClaim(f);globalThis.scrollX=0;globalThis.scrollY=0;navClick(f,'work');await settle();
 assert.equal(search.value,'receipt');assert.equal(filter.value,'deferred');assert.match(rows.innerHTML,/Notice needs a receipt/);assert.doesNotMatch(rows.innerHTML,/Policy investigation/);assert.equal(count.textContent,'1 of 5');assert.equal(f.host.scrollTop,127);assert.equal(main.scrollTop,246);assert.equal(main.scrollLeft,6);assert.deepEqual(scrollCalls.at(-1),{left:12,top:418,behavior:'instant'});assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('a mismatched polling event cursor never advances the displayed state or consumes the pending event',async t=>{
 const f=dom();let saved=state(),ahead=false;
 const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(ahead?state({revision:5,state_sha256:hash('5')}):saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');const verified=f.host.innerHTML;
 saved=state({revision:4,state_sha256:hash('f'),title:'Fourth saved revision'});ahead=true;await controller.refresh();assert.equal(f.host.innerHTML,verified);
 ahead=false;await controller.refresh();assert.match(f.host.innerHTML,/Fourth saved revision/);assert.match(f.host.innerHTML,/revision 4/);const reads=api.calls.filter(call=>call.path.includes('/claim-a/events?'));assert.equal(reads.at(-2).path,reads.at(-1).path);assert.ok(reads.at(-1).path.endsWith('after=3'));assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
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

test('actual reuse provenance stays available in closed escaped disclosures in Knowledge and claim Activity',()=>{
 const attack='<img src=x onerror="alert(1)">',use={knowledge_id:'procedure.one',version:1,definition_sha256:hash('d'),rule_pack_sha256:hash('e'),applicability:'same_verified_family_and_rule_version',avoided_rule_compilations:1,reused_evidence_recipes:2,workflow_id:'workflow.recorded',public_extension:{reason:attack}};
 for(const html of [ui.knowledgeMarkup({versions:[],uses:[{...use,claim_id:'receiving-claim'}],quarantined:[]}),ui.workMarkup(state({knowledge_uses:[use]}),{},'branch',[],'activity')]) {
  for(const value of [hash('d'),hash('e'),'workflow.recorded','reused_evidence_recipes','2','Same verified family and rule version'])assert.ok(html.includes(value),value);
  const disclosure=html.match(/<details[^>]*data-au-disclosure="reuse:[^"]*"[^>]*>/);assert.ok(disclosure,'the saved reuse provenance has a stable disclosure');assert.doesNotMatch(disclosure[0],/\sopen(?:\s|>)/);assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<img|onerror="alert/);
 }
});

test('outcome verifier issues and deferral details retain complete escaped public records without opening by default',()=>{
 const attack='<svg onload="alert(1)">',outcome={status:'deferred',title:'Evidence assessment complete; claim deferred',summary:'Recorded source assessment.',missing_evidence:[],unresolved_facts:[],issues:[{code:'source_discrepancy',reason:'Recorded verifier discrepancy',details:{original_quote:attack}}],authority_limits:[],next_action:'Await named evidence.'};
 const deferred={code:'unsupported_format',reason:'No supported extraction.',details:{file_name:'recorded-file.bin',limitation:attack,public_check:'Original receipt retained'}};
 for(const [saved,values]of [[state({status:'deferred',outcome}),['Recorded verifier discrepancy','source_discrepancy']],[state({status:'deferred',deferral:deferred}),['recorded-file.bin','Original receipt retained']]]) {
  const html=ui.workMarkup(saved,{},'branch',[]);for(const value of values)assert.ok(html.includes(value),value);
  const disclosure=html.match(/<details[^>]*data-au-disclosure="outcome-record"[^>]*>/);assert.ok(disclosure,'the full public operational record is inspectable');assert.doesNotMatch(disclosure[0],/\sopen(?:\s|>)/);assert.match(html,/&lt;svg/);assert.doesNotMatch(html,/<svg\s+onload|onload="alert/);
 }
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
 const api=fakeApi({handle:async path=>path.endsWith('/status')?response(savedStatus):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();assert.match(f.host.innerHTML,/>Every case has a source\.</);await newClaim(f);
 const message=f.host.querySelector('[data-au-service]').textContent;assert.match(message,/allowance does not permit more autonomous work/i);assert.match(message,/still save a new claim.*named deferral/i);assert.doesNotMatch(message,/Local evidence acquisition and document preparation are available/);
 assert.equal(f.submit.disabled,false);assert.notEqual(f.fields.title.disabled,true);assert.doesNotMatch(f.submit.textContent,/retry|saving/i);assert.equal(f.message.textContent,'');assert.equal(JSON.stringify(savedStatus),before);
 assert.ok(api.calls.every(call=>call.path.endsWith('/status')||call.path.endsWith('/claims')));assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
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
  try { await settle();await newClaim(f);const message=f.host.querySelector('[data-au-service]').textContent;for(const pattern of example.matches||[])assert.match(message,pattern,JSON.stringify(savedStatus));if(example.excludes)assert.doesNotMatch(message,example.excludes,JSON.stringify(savedStatus));assert.equal(f.submit.disabled,false);assert.notEqual(f.fields.title.disabled,true);assert.equal(f.message.textContent,'');assert.ok(api.calls.every(call=>call.path.endsWith('/status')||call.path.endsWith('/claims')));assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0); }
  finally { controller.destroy(); }
 }
});

test('disabled service and unavailable provider keep precedence over allowance messages',async()=>{
 for(const [savedStatus,pattern,disabled]of [
  [{enabled:false,provider_ready:true,limits:{autonomous_can_start:false,autonomous_reason:'call_limit_reached'}},/^Autonomous work is disabled\.$/,true],
  [{enabled:true,provider_ready:false,limits:{autonomous_can_start:false,autonomous_reason:'call_limit_reached'}},/^Inference is unavailable\. New packets are saved with a named deferral\.$/,false]
 ]) {
  const f=dom(),api=fakeApi({handle:async path=>path.endsWith('/status')?response(savedStatus):null}),controller=ui.mount(f.container,{fetch:api.fetch});
  try { await settle();await newClaim(f);assert.match(f.host.querySelector('[data-au-service]').textContent,pattern);assert.equal(f.submit.disabled,disabled);assert.ok(api.calls.every(call=>call.path.endsWith('/status')||call.path.endsWith('/claims')));assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0); }
  finally { controller.destroy(); }
 }
});

test('accepted refresh preserves an open document-rules disclosure and focuses its replacement summary',async t=>{
 const f=nativeFixture(),original=Object.getOwnPropertyDescriptor(f.host,'innerHTML');let summary=null;
 Object.defineProperty(f.host,'innerHTML',{get:original.get,set:value=>{
  if(summary)summary.isConnected=false;original.set(value);summary=null;
  for(const detail of f.disclosures) {
   const panel=f.panels.find(node=>node.dataset.auPanel==='step');detail.closest=selector=>selector==='[data-au-panel]'?panel:null;detail.hasAttribute=name=>name==='data-au-disclosure';
   if(detail.dataset.auDisclosure==='document-rules:branch') { summary=control(f,'data-unused');summary.hasAttribute=()=>false;summary.matches=selector=>selector==='summary';summary.parentElement=detail;summary.closest=selector=>selector==='[data-au-panel]'?panel:null;summary.focus=options=>{summary.focusOptions=options;if(!panel?.hidden)f.container.ownerDocument.activeElement=summary;};detail.querySelector=selector=>selector==='summary'?summary:null; }
  }
 }});f.host.contains=element=>element===summary;
 let saved=state();const api=fakeApi({handle:async path=>path.endsWith('/claims/claim-a')?response(saved):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();await controller.openClaim('claim-a');
 assert.match(f.host.innerHTML,/<details class="au-document-rules"[^>]*data-au-disclosure="document-rules:branch"/);const detail=f.disclosures.find(node=>node.dataset.auDisclosure==='document-rules:branch');detail.open=true;summary.focus();const oldSummary=summary;
 saved=state({revision:4,state_sha256:hash('f')});await controller.refresh();assert.notEqual(summary,oldSummary);assert.equal(f.disclosures.find(node=>node.dataset.auDisclosure==='document-rules:branch').open,true);assert.equal(f.container.ownerDocument.activeElement,summary);assert.deepEqual(summary.focusOptions,{preventScroll:true});assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});

test('delayed claim collections preserve verified revisions without rejecting genuinely newer rows',async t=>{
 const other={claim_id:'claim-b',title:'Other saved claim',status:'resolved',revision:2,state_sha256:hash('b')};
 for(const example of [
  {name:'a delayed older current row',row:{claim_id:'claim-a',title:'Old collection title',status:'running',revision:3,state_sha256:hash('a')},expectedStatus:'Deferred'},
  {name:'a missing current row',row:null,expectedStatus:'Deferred'},
  {name:'a conflicting identity at the verified revision',row:{claim_id:'claim-a',title:'Conflicting collection title',status:'running',revision:4,state_sha256:hash('9')},expectedStatus:'Deferred'},
  {name:'a genuinely newer collection row',row:{claim_id:'claim-a',title:'Newer collection title',status:'queued',revision:5,state_sha256:hash('5')},expectedStatus:'Queued'}
 ])await t.test(example.name,async child=>{
  routingFixture(child,'#autonomous/claim/claim-a');const f=dom(),queue={innerHTML:''},query=f.container.querySelector;f.container.querySelector=selector=>selector==='[data-au-recent-claims]'?queue:query(selector);
  let saved=state(),projection={},finishList;const api=fakeApi({handle:async(path,init)=>path.endsWith('/claims')&&init.method!=='POST'?new Promise(resolve=>{finishList=resolve;}):path.endsWith('/claims/claim-a')?response({state:saved,projection:{claim_id:saved.claim_id,revision:saved.revision,state_sha256:saved.state_sha256,...projection}}):path.includes('/claim-a/events?')?response(events(saved,Number(path.split('after=')[1]))):null}),controller=ui.mount(f.container,{fetch:api.fetch});child.after(()=>controller.destroy());await waitFor(()=>f.host.innerHTML.includes('revision 3')&&Boolean(finishList));
  saved=state({revision:4,state_sha256:hash('f'),status:'deferred',deferral:{code:'missing_evidence',reason:'Recorded evidence needed.'}});await controller.refresh();assert.match(queue.innerHTML,/Deferred/);assert.match(f.host.innerHTML,/revision 4/);
  finishList(response({claims:[other,...(example.row?[example.row]:[])]}));await waitFor(()=>queue.innerHTML.includes('Other saved claim'));
  const row=queue.innerHTML.match(/<button[^>]*data-au-claim="claim-a"[\s\S]*?<\/button>/)?.[0];assert.ok(row,'the current verified claim remains reachable');assert.ok(row.includes(example.expectedStatus),row);assert.match(f.host.innerHTML,/revision 4/);assert.match(f.host.innerHTML,/Recorded evidence needed/);assert.doesNotMatch(queue.innerHTML,/Old collection title|Conflicting collection title/);
  if(example.row)assert.ok(queue.innerHTML.indexOf('Other saved claim')<queue.innerHTML.indexOf('data-au-claim="claim-a"'),'the API collection order is retained');
  if(example.row?.revision===5)projection={node_capabilities:{branch:{authorized:false,id:null,reason:'Projection changed after newer collection row.'}}};
  await controller.refresh();assert.ok(queue.innerHTML.includes(example.expectedStatus));
  if(example.row?.revision===5){assert.match(f.host.innerHTML,/Projection changed after newer collection row/);assert.match(f.host.innerHTML,/revision 4/);assert.match(queue.innerHTML,/Newer collection title/);}
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

test('an unresolved service status keeps the default intake action until authoritative readiness arrives',async t=>{
 const f=nativeFixture(),held=[];const api=fakeApi({handle:async path=>path.endsWith('/status')?new Promise(resolve=>held.push(resolve)):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{for(const resolve of held)resolve(response({enabled:true,provider_ready:true,limits:{}}));controller.destroy();});await settle();await newClaim(f);
 assert.equal(held.length,2);assert.match(f.intake.querySelector('button[type="submit"]').textContent,/^Start autonomous work/);assert.equal(f.intake.querySelector('button[type="submit"]').disabled,false);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
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
 const f=nativeFixture();let savedStatus={enabled:true,provider_ready:true,limits:{}},finishStatus,statusReads=0,holdNext=false;
 const api=fakeApi({handle:async path=>{if(!path.endsWith('/status'))return null;statusReads++;if(holdNext){holdNext=false;return new Promise(resolve=>{finishStatus=resolve;});}return response(savedStatus);}}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{finishStatus?.(response(savedStatus));controller.destroy();});await settle();await newClaim(f);
 const form=f.intake,list=Array.from({length:21},()=>fileFixture()),submit=form.querySelector('button[type="submit"]');form.elements.title.value='Typed original draft';form.elements.message.value='Retained original message';form.elements.files.files=list;
 await f.listeners.get('submit')({target:form,preventDefault(){}});assert.match(form.querySelector('.au-form-status').textContent,/at most 20/);assert.match(submit.textContent,/^Start autonomous work/);assert.equal(form.elements.title.disabled,false);
 savedStatus={enabled:true,provider_ready:false,limits:{}};navClick(f,'work');await settle();holdNext=true;await newClaim(f);assert.equal(f.intake,form);assert.equal(submit.textContent,'Save claim','the cached unavailable status applies before the fresh status response');assert.equal(form.elements.files.files,list);assert.equal(form.elements.title.value,'Typed original draft');assert.equal(form.elements.message.value,'Retained original message');
 finishStatus(response(savedStatus));await settle();await f.listeners.get('submit')({target:form,preventDefault(){}});assert.equal(submit.textContent,'Save claim');assert.equal(submit.disabled,false);assert.equal(form.elements.title.disabled,false);assert.equal(form.elements.files.files,list);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
 savedStatus={enabled:true,provider_ready:true,limits:{}};navClick(f,'work');await settle();await newClaim(f);assert.equal(f.intake,form);assert.match(submit.textContent,/^Start autonomous work/);assert.equal(form.elements.files.files,list);assert.equal(statusReads,6);
});
