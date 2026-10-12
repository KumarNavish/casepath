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

function formingUnitStates() {
 const use={knowledge_id:'procedure.unit',version:2,definition_sha256:hash('2'),rule_pack_sha256:hash('3'),applicability:'same_verified_family_and_rule_version'},packet=state({claim_id:'unit-forming-case',revision:10,state_sha256:hash('1'),last_event_sha256:hash('a'),graph:{claim_id:'unit-forming-case',family:'incoming_packet',nodes:[{node_id:'incoming',label:'Read the original unit packet',entry:true}],edges:[]},evaluation:{nodes:[{node_id:'incoming',execution_state:'ready',activation:'true'}],edges:[],documents:[]},facts:[],obligations:[],actions:[],knowledge_uses:[use],knowledge_published:[]});
 packet.source_descriptors[0].claim_id=packet.claim_id;const body='Exact original unit source sentence.';packet.acquired_sources=[{claim_id:packet.claim_id,artifact_id:'original',sha256:hash('d'),text:body,text_sha256:sha(body),complete:true}];
 const interpreted=structuredClone(packet);interpreted.revision=11;interpreted.state_sha256=hash('4');interpreted.last_event_sha256=hash('b');
 interpreted.graph={claim_id:packet.claim_id,family:'unit_process',graph_sha256:hash('5'),nodes:Array.from({length:11},(_,index)=>({node_id:index===0?'intake':`question-${index}`,label:index===0?'Read the original unit packet':`Recorded question ${index}`,entry:index===0,condition:{flag:index===0?'intake':`question-${index}`}})),edges:Array.from({length:10},(_,index)=>({edge_id:`edge-${index}`,source_node_id:index===0?'intake':`question-${index}`,target_node_id:`question-${index+1}`}))};
 interpreted.facts=interpreted.graph.nodes.map((node,index)=>({fact_id:`condition:${node.node_id}`,status:index===0?'true':'unresolved',summary:index===0?'The original unit packet is recorded.':`Recorded question ${index} remains unestablished.`,citations:index===0?[{artifact_id:'original',sha256:hash('d'),text_sha256:sha(body),start_char:0,end_char:Array.from(body).length,quote:body}]:[]}));
 interpreted.obligations=interpreted.graph.nodes.map((node,index)=>({obligation_id:`unit-requirement-${index}`,document_type:`unit_document_${index}`,label:`Recorded document ${index}`,node_id:node.node_id,required_fact_ids:[`condition:${node.node_id}`]}));
 interpreted.evaluation={nodes:interpreted.graph.nodes.map((node,index)=>({node_id:node.node_id,activation:index===0?'true':'unresolved',execution_state:index===0?'ready':'unresolved'})),edges:interpreted.graph.edges.map(edge=>({edge_id:edge.edge_id,activation:'unresolved'})),documents:interpreted.obligations.map(obligation=>({document_type:obligation.document_type,route_state:'held_behind_question',review_state:'unreviewed'}))};
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
  assert.deepEqual(new Set([...html.matchAll(/data-au-node="([^"]+)"/g)].map(match=>match[1])),new Set(state.graph.nodes.map(node=>node.node_id)));assert.deepEqual(new Set([...html.matchAll(/data-au-obligation="([^"]+)"/g)].map(match=>match[1])),new Set(state.obligations.map(obligation=>obligation.obligation_id)));
  for(const obligation of state.obligations){assert.ok(html.includes(`data-au-select-obligation="${obligation.obligation_id}"`));assert.ok(html.includes(`data-au-select="${obligation.node_id}"`));}
  assert.match(html,/data-au-version="2"[^>]*data-au-definition-sha="2{64}"/);assert.deepEqual(ui.contextualRecord(state,{},[],'claim'),{state,projection:{}});
 }
 assert.equal(ui.formingWork(interpreted,{mode:'saved'}),true);assert.equal(ui.formingWork(settled,{mode:'saved'}),false);assert.equal(ui.formingWork(reviewed,{mode:'replay',replay:formingUnitReplay(reviewed),paused:true}),true);assert.equal(ui.formingWork(settled,{mode:'replay',replay:formingUnitReplay(settled)}),false);assert.equal(ui.formingWork(settled,{mode:'replay',replay:formingUnitReplay(settled),playing:true}),true,'the actual final publication remains visible during its accepted presentation before settling');assert.equal(ui.formingWork(reviewed,{mode:'replay',replay:{...formingUnitReplay(reviewed),state:{...reviewed,state_sha256:hash('0')}},playing:true}),false,'playing cannot bypass replay identity');assert.equal(JSON.stringify({packet,interpreted,reviewed,settled}),before);
});

test('a sufficient source review in forming work leaves unresolved decisions and conditional requirement applicability exact',()=>{
 const {interpreted,reviewed}=formingUnitStates(),before=JSON.stringify(reviewed),html=ui.workMarkup(reviewed,{},'question-4',[],'step',{}, {mode:'replay',replay:formingUnitReplay(reviewed)});
 assert.match(html,/data-au-forming/);assert.doesNotMatch(html,/May be needed\s*·\s*Sufficient/);assert.match(html,/Supplied evidence is sufficient\./);assert.match(html,/May be needed/);assert.match(html,/data-au-review="sufficient"/);assert.deepEqual(reviewed.evaluation.nodes,interpreted.evaluation.nodes);assert.deepEqual(reviewed.evaluation.edges,interpreted.evaluation.edges);
 assert.equal(reviewed.evaluation.nodes[0].execution_state,'ready');assert.ok(reviewed.evaluation.nodes.slice(1).every(node=>node.execution_state==='unresolved'));assert.ok(reviewed.evaluation.edges.every(edge=>edge.activation==='unresolved'));assert.ok(reviewed.evaluation.documents.every(document=>document.route_state==='held_behind_question'));assert.equal(ui.contextualRecord(reviewed,{},[],'requirement','unit-requirement-4').evaluation[0].review_state,'sufficient');assert.equal(ui.contextualRecord(reviewed,{},[],'fact','document:unit_document_4').status,'sufficient');assert.equal(JSON.stringify(reviewed),before);
 const checkmark=/<span aria-hidden="true">✓<\/span>/,reviewedRow=html.match(/<li[^>]*data-au-obligation="unit-requirement-4"[\s\S]*?<\/li>/)[0];assert.match(reviewedRow,checkmark);assert.match(ui.documentReviewMarkup('sufficient'),checkmark);
 for(const review of [undefined,'received','unreviewed','missing','unresolved','insufficient','satisfied']){assert.doesNotMatch(ui.documentReviewMarkup(review),checkmark);const copy=structuredClone(reviewed);copy.evaluation.documents[4].review_state=review;copy.evaluation.nodes[4].execution_state='completed';const copyBefore=JSON.stringify(copy),rendered=ui.workMarkup(copy,{},'question-4',[],'step',{}, {mode:'saved'}),row=rendered.match(/<li[^>]*data-au-obligation="unit-requirement-4"[\s\S]*?<\/li>/)[0];assert.doesNotMatch(row,checkmark,`review ${review} cannot inherit sufficiency from a completed node or sufficient document fact`);assert.equal(copy.facts.at(-1).status,'sufficient');assert.equal(copy.evaluation.documents[4].route_state,'held_behind_question');assert.deepEqual(copy.acquired_sources,reviewed.acquired_sources);assert.equal(JSON.stringify(copy),copyBefore);}
});

test('forming documents use one collective conditional label while keeping an assessed source separate from unresolved routing',()=>{
 const {reviewed}=formingUnitStates(),before=JSON.stringify(reviewed),html=ui.workMarkup(reviewed,{},'question-4',[],'step',{}, {mode:'replay',replay:formingUnitReplay(reviewed)});
 assert.equal((html.match(/May be needed/g)||[]).length,1);assert.match(html,/au-forming-document-scope/);assert.doesNotMatch(html,/Source evidence is not yet established\.|au-reading-decision|au-reading-relations/);assert.match(html,/data-au-review="sufficient"[^>]*>Supplied evidence is sufficient\./);assert.doesNotMatch(html,/May be needed\s*·\s*Sufficient/);
 for(const obligation of reviewed.obligations)assert.ok(html.includes(`data-au-obligation="${obligation.obligation_id}"`));assert.equal(ui.contextualRecord(reviewed,{},[],'requirement','unit-requirement-4').evaluation[0].route_state,'held_behind_question');assert.equal(ui.contextualRecord(reviewed,{},[],'requirement','unit-requirement-5').evaluation[0].review_state,'unreviewed');assert.match(ui.inspectorMarkup(reviewed,'question-4'),/au-reading-decision/);assert.deepEqual(ui.contextualRecord(reviewed,{},[],'step','question-4').edges,reviewed.graph.edges.filter(edge=>edge.source_node_id==='question-4'||edge.target_node_id==='question-4'));assert.equal(JSON.stringify(reviewed),before);
});

test('forming mixed routes expose a recorded requirement needed now without promoting sufficient source review or repeating held statuses',()=>{
 const {reviewed}=formingUnitStates();reviewed.evaluation.documents[2].route_state='needed_now';const before=JSON.stringify(reviewed),html=ui.workMarkup(reviewed,{},'question-4',[],'step',{}, {mode:'saved'}),row=index=>html.match(new RegExp(`<li[^>]*data-au-obligation="unit-requirement-${index}"[\\s\\S]*?<\\/li>`))[0];
 assert.equal((html.match(/May be needed/g)||[]).length,1);assert.match(row(2),/data-status="needed_now"/);assert.match(row(2),/>Needed now</);assert.doesNotMatch(row(2),/data-au-review="unreviewed"|Source evidence is not yet established/);
 assert.match(row(4),/data-status="held_behind_question"/);assert.match(row(4),/Supplied evidence is sufficient\./);assert.doesNotMatch(row(4),/Needed now|May be needed/);assert.doesNotMatch(row(5),/May be needed|Source evidence is not yet established|data-au-review="unreviewed"/);
 assert.equal(ui.contextualRecord(reviewed,{},[],'requirement','unit-requirement-2').evaluation[0].route_state,'needed_now');assert.equal(ui.contextualRecord(reviewed,{},[],'requirement','unit-requirement-4').evaluation[0].route_state,'held_behind_question');assert.equal(ui.contextualRecord(reviewed,{},[],'requirement','unit-requirement-4').evaluation[0].review_state,'sufficient');assert.equal(JSON.stringify(reviewed),before);
});

test('forming assessed requirements list a source file once while all three exact cited passages remain inspectable',()=>{
 const {reviewed}=formingUnitStates(),context={fact:'document:unit_document_4',document:'unit_document_4',obligation:'unit-requirement-4'},fact=reviewed.facts.find(item=>item.fact_id===context.fact),body=reviewed.acquired_sources[0].text;
 fact.citations=['Exact','original','unit'].map(quote=>({...fact.citations[0],quote,start_char:Array.from(body.slice(0,body.indexOf(quote))).length,end_char:Array.from(body.slice(0,body.indexOf(quote)+quote.length)).length}));reviewed.obligations[4].required_fact_ids.push(context.fact);
 const before=JSON.stringify(reviewed),html=ui.workMarkup(reviewed,{},'question-4',[],'step',context,{mode:'saved'}),row=html.match(/<li[^>]*data-au-obligation="unit-requirement-4"[\s\S]*?<\/li>/)[0],passages=html.match(/<section class="au-reading-passages">[\s\S]*?<\/section>/)[0];
 assert.equal((row.match(/class="au-link au-document-source"/g)||[]).length,1);assert.equal((row.match(/data-au-source="original"/g)||[]).length,1);assert.match(row,/data-au-source-origin="requirement:unit-requirement-4"/);assert.match(row,/Supplied evidence is sufficient\./);
 assert.equal((passages.match(/data-au-source="original"/g)||[]).length,3);assert.deepEqual([...passages.matchAll(/<q>([^<]*)<\/q>/g)].map(match=>match[1]),fact.citations.map(citation=>citation.quote));
 for(const citation of fact.citations)assert.equal(Array.from(body).slice(citation.start_char,citation.end_char).join(''),citation.quote);assert.deepEqual(ui.contextualRecord(reviewed,{},[],'fact',context.fact).citations,fact.citations);assert.deepEqual(ui.contextualRecord(reviewed,{},[],'claim').state,reviewed);assert.equal(JSON.stringify(reviewed),before,'file-link deduplication must not collapse passage or full-history provenance');
});

test('forming connections join only the selected accepted fact exact source span and its requiring node and obligation',()=>{
 const {reviewed}=formingUnitStates(),context={fact:'document:unit_document_4',document:'unit_document_4',obligation:'unit-requirement-4'};
 reviewed.obligations[4].required_fact_ids.push(context.fact);
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
 assert.deepEqual([...live.matchAll(/data-au-node="([^"]+)"/g)].map(match=>match[1]),head.graph.nodes.map(node=>node.node_id));assert.deepEqual([...live.matchAll(/data-au-edge="([^"]+)"/g)].map(match=>match[1]),head.graph.edges.map(edge=>edge.edge_id));assert.deepEqual(new Set([...live.matchAll(/data-au-obligation="([^"]+)"/g)].map(match=>match[1])),new Set(head.obligations.map(item=>item.obligation_id)));assert.deepEqual(ui.contextualRecord(head,{},history,'claim'),{state:head,projection:{}});assert.deepEqual(ui.contextualRecord(head,{},history,'use','0'),head.knowledge_uses[0]);
 assert.match(ui.workMarkup(reviewed,{},'question-4',[],'step',{}, {mode:'saved'}),/data-au-inspector-heading="question-4"/,'ordinary prepublication prefixes retain the selected-question heading');
 const replay={state:head,mode:'replay',replay_only:true,through_seq:16,current_revision:16,current_state_sha256:head.state_sha256,current_event_sha256:head.last_event_sha256};assert.match(ui.workMarkup(head,{},'question-4',history,'step',{}, {mode:'replay',replay,attention}),/data-au-publication-focus="e{64}"/);
 for(const invalid of [{},{...attention,previousRevision:15},{...attention,knowledgePublications:[]},{...attention,knowledgePublications:[{id:hash('0')}]},{...attention,acceptedEvents:[{...published,event_sha256:hash('0')},phase]}]){assert.equal(ui.formingPublication(head,history,invalid),null);assert.doesNotMatch(ui.workMarkup(head,{},'question-4',history,'step',{}, {mode:'saved',attention:invalid}),/data-au-forming="true"|data-au-publication-focus=/);}
 const foreign={...published,claim_id:'another-claim'};assert.equal(ui.formingPublication(head,[foreign,phase],{...attention,acceptedEvents:[foreign,phase]}),null);const withheld=structuredClone(head);withheld.knowledge_published[0].qualification.status='quarantined';assert.equal(ui.formingPublication(withheld,history,attention),null);
 assert.doesNotMatch(ui.workMarkup(head,{},'question-4',history,'step',{}, {mode:'saved',knowledge:{versions:[{...publication,version:99}]}}),/data-au-publication-focus=|data-au-version="99"/,'a lifetime publication or global latest lookup cannot create current attention');
 assert.doesNotMatch(ui.workMarkup(head,{},'question-4',history,'step',{}, {mode:'saved',attention,inspectionHold:true}),/data-au-forming="true"|data-au-publication-focus=/,'new attention cannot restructure a manually inspected saved view');assert.match(ui.workMarkup(head,{},'question-4',history,'step',{}, {mode:'saved',attention:{...attention,retained:true},inspectionHold:true}),/data-au-forming-revision="16"[\s\S]*data-au-publication-focus="e{64}"/,'already visible accepted attention stays in place during inspection');
 assert.equal(JSON.stringify({prior,head,history,attention}),before,'live and replay presentation must retain the actual revision and raw publication unchanged');
});

test('forming requirements retire only on recorded route exclusion while History and Documents retain exact earlier obligations',()=>{
 const {interpreted}=formingUnitStates();interpreted.evaluation.documents[2].route_state='not_needed';interpreted.evaluation.documents[3].route_state='excluded';interpreted.evaluation.nodes[4].activation='false';const before=JSON.stringify(interpreted),html=ui.workMarkup(interpreted,{},'question-4',[],'step',{}, {mode:'saved'}),documents=ui.workMarkup(interpreted,{},'question-4',[],'documents');
 assert.match(html,/data-au-forming/);assert.doesNotMatch(html,/data-au-obligation="unit-requirement-(?:2|3)"/);assert.match(html,/data-au-obligation="unit-requirement-4"/,'a node activation alone cannot fabricate document retirement');
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
 const container={ownerDocument:doc,classList:{add(){}},innerHTML:'',querySelector(s){return {'[data-au-view]':host,'.au-global-status':status,dialog,'.au-source-dialog':dialog,'.au-record-dialog':recordDialog}[s];},querySelectorAll:()=>[],addEventListener(type,fn){listeners.set(type,fn);},removeEventListener(type){listeners.delete(type);},contains:()=>true};
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
 assert.match(f.host.innerHTML,/public workspace is read-only/i);
 const presentation={mode:'saved',readOnly:true,availability:{ready:true}};
 for(const saved of [state(),state({status:'deferred',deferral:{code:'paused'}}),state({revision:0})]) {
  const before=JSON.stringify(saved),html=ui.workMarkup(saved,{},'branch',[],'sources',{},presentation)+ui.workMarkup(saved,{},'branch',[],'documents',{},presentation);
  assert.doesNotMatch(html,/data-au-start(?:[ >])|data-au-pause(?:[ >])|data-au-resume(?:[ >])|data-au-arrival(?:[ >])|data-au-add-files(?:[ >])/);
  assert.match(html,/Original sources|History/);assert.equal(JSON.stringify(saved),before);
 }
 assert.equal(ui.liveAvailability({enabled:true,provider_ready:true,read_only:true,writable:false}).ready,false);
 assert.match(ui.liveAvailability({enabled:true,provider_ready:true,read_only:true,writable:false}).reason,/read-only/i);
 assert.doesNotMatch(ui.demonstrationMarkup([],{enabled:true,provider_ready:true,read_only:true,writable:false}),/data-au-demo-mode="live"/);
});

test('public entry capability prevents work before a status response arrives',async t=>{
 const before=globalThis.CASEPATH_PUBLIC_READ_ONLY;globalThis.CASEPATH_PUBLIC_READ_ONLY=true;
 const f=dom(),held=[],api=fakeApi({handle:async path=>path.endsWith('/status')?new Promise(resolve=>held.push(resolve)):null});
 const controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{for(const resolve of held)resolve(response({enabled:true,provider_ready:true,writable:true}));controller.destroy();if(before===undefined)delete globalThis.CASEPATH_PUBLIC_READ_ONLY;else globalThis.CASEPATH_PUBLIC_READ_ONLY=before;});
 assert.match(f.container.innerHTML,/data-au-nav="intake" disabled/);await settle();await newClaim(f);
 assert.match(f.host.innerHTML,/public workspace is read-only/i);
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
 globalThis.location=new URL(entries[0]);
 globalThis.addEventListener=(type,fn)=>listeners.set(type,fn);globalThis.removeEventListener=(type,fn)=>{if(listeners.get(type)===fn)listeners.delete(type);};
 globalThis.history={pushState(_state,_unused,url){entries.splice(++index);entries.push(new URL(url,globalThis.location).href);globalThis.location=new URL(entries[index]);pushes++;},replaceState(_state,_unused,url){entries[index]=new URL(url,globalThis.location).href;globalThis.location=new URL(entries[index]);}};
 const fire=()=>{listeners.get('popstate')?.();listeners.get('hashchange')?.();};
 t.after(()=>Object.assign(globalThis,old));
 return {listeners,get pushes(){return pushes;},get hash(){return globalThis.location.hash;},external(fragment){globalThis.location.hash=fragment;fire();},back(){if(index>0){globalThis.location=new URL(entries[--index]);fire();}},forward(){if(index+1<entries.length){globalThis.location=new URL(entries[++index]);fire();}}};
}
function navClick(f,value) {
 const target={dataset:{auNav:value},closest(){return this;},hasAttribute:attr=>attr==='data-au-nav'};f.listeners.get('click')({target});
}

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
 const priorReads=api.calls.filter(call=>call.path.includes(`/claims/${id}/replay?`)).length;
 await controller.showDemonstration();
 assert.match(f.host.innerHTML,/data-au-revision="0"/,'Demonstration opens the actual first canonical packet before playback');await settle();
 for(let seq=1;seq<=head;seq++){
  t.mock.timers.tick(4100);await settle();const prefix=saved(seq),html=f.host.innerHTML;assert.match(html,new RegExp(`data-au-revision="${seq}" data-au-state-sha="${prefix.state_sha256}"`));assert.match(html,/data-au-context="step"/);assert.match(html,/<section class="au-(?:forming-process|process-hero) au-evidence-process" aria-label="(?:Complete recorded process|Decision neighborhood)">/);
  assert.deepEqual([...html.matchAll(/data-au-node="([^"]+)"/g)].map(match=>match[1]),prefix.graph.nodes.map(node=>node.node_id),'forming and settled layouts preserve every actual prefix node');assert.deepEqual([...html.matchAll(/data-au-edge="([^"]+)"/g)].map(match=>match[1]),prefix.graph.edges.map(edge=>edge.edge_id),'presentation preserves the exact accepted edge identities');assert.match(html,/data-au-node="branch"[^>]*aria-pressed="true"/);assert.match(html,/data-au-selected-step="branch"/);if(html.includes('data-au-forming="true"'))assert.match(html,new RegExp(`data-au-forming-revision="${seq}" data-au-forming-sha="${prefix.state_sha256}"`));
  assert.deepEqual(JSON.parse(f.recordPre.textContent).state,JSON.parse(JSON.stringify(saved(seq))),'the loaded record retains every exact prefix field despite quiet presentation');if(scenario==='failed-then-reconciled'&&seq>=12){assert.equal(JSON.parse(f.recordPre.textContent).state.reconciliations[0].status,seq===15?'completed':'started');assert.equal(JSON.parse(f.recordPre.textContent).state.reconciliations[0].original_deferral.reason,stopped.reason);}
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
 assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
});
async function newClaim(f) { navClick(f,'intake');await settle(); }
test('initial deep links and duplicate browser history events read saved state once without adding entries',async t=>{
 const routing=routingFixture(t,'#autonomous/claim/claim-a'),f=dom(),api=fakeApi(),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>controller.destroy());await settle();
 assert.match(f.host.innerHTML,/data-au-graph/);assert.equal(routing.pushes,0);assert.equal(api.calls.filter(call=>call.path.endsWith('/claims/claim-a')).length,1);
 routing.external('#autonomous/knowledge');await settle();assert.match(f.host.innerHTML,/au-quiet-knowledge/);assert.equal(api.calls.filter(call=>call.path.endsWith('/knowledge')).length,1);assert.equal(routing.pushes,0);
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

test('an unresolved service status keeps the default intake action until authoritative readiness arrives',async t=>{
 const f=nativeFixture(),held=[];const api=fakeApi({handle:async path=>path.endsWith('/status')?new Promise(resolve=>held.push(resolve)):null}),controller=ui.mount(f.container,{fetch:api.fetch});t.after(()=>{for(const resolve of held)resolve(response({enabled:true,provider_ready:true,limits:{}}));controller.destroy();});await settle();await newClaim(f);
 assert.equal(held.length,1,'navigation shares the exact unresolved status GET');assert.equal(api.calls.filter(call=>call.path.endsWith('/status')).length,1);assert.match(f.intake.querySelector('button[type="submit"]').textContent,/^Start autonomous work/);assert.equal(f.intake.querySelector('button[type="submit"]').disabled,false);assert.equal(api.calls.filter(call=>call.init.method==='POST').length,0);
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
