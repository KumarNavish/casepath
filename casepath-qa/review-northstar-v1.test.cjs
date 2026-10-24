'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const northstar = require('../casepath/assets/review-northstar-v1.js');
const causal = require('../casepath/assets/causal-process-v1.js');
const hash = 'a'.repeat(64);
function fixture() {
  const nodes = [
    {node_id:'compare',label:'Compare the complete notices',meaning:'Resolve their different end dates.',condition:{flag:'family_home'},document_types:['notice'],validation:{status:'validated',actor:'Test handler'},completed:false},
    {node_id:'resolution',label:'Prepare joint resolution',meaning:'Review the available options.',condition:{const:'true'},document_types:[],validation:{status:'unvalidated'},completed:false}
  ];
  const graph = {nodes,edges:[{edge_id:'compare_first',source_node_id:'compare',target_node_id:'resolution',relation:'requires',condition:{const:'true'},validation:{status:'unvalidated'}}],conditions:{family_home:{verdict:'true',quote:'This is our family home.',source_id:'target-message'}},document_catalog:[{document_type:'notice',label:'Complete notices',held_files:[]}],revision:3,family:'lease_termination_dispute',fragment_instances:[]};
  return {contract:'casepath.causal-process-view/1.0.0',claim_id:'target',workspace_revision:7,workspace_state_sha256:hash,graph,evaluation:{nodes:[{node_id:'compare',execution_state:'ready',activation:'true'},{node_id:'resolution',execution_state:'blocked',activation:'true',blocked_by:['compare']}],steps:[],documents:[],process_status:'blocked'},effective_assessment:{next_step:'Compare the complete notices'},history:[],fragments:[],sources:[]};
}
const delta = {node_changes:[{node_id:'resolution',label:'Prepare joint resolution',before:{execution_state:'ready',blocked_by:[]},after:{execution_state:'blocked',blocked_by:['compare']}}],document_changes:[],edge_changes:[],next_action_changed:false,next_action:{before:'Ask for copies',after:'Ask for copies'},unchanged_node_ids:['compare'],changed_requirement_document_types:[]};
test('graph and direct edit remain present beside a read-only consequence preview', () => {
  globalThis.CasePathReviewNorthStar = northstar;
  const view=fixture(),s=causal.session(view.claim_id);
  Object.assign(s,{selected:'resolution',preview:{impact:delta,reason:'Test-only review proposal.'},mode:null});
  const html=causal.render(view,{presentation:'northstar'});
  assert.match(html,/data-review-process-map/);
  assert.match(html,/data-causal-node="resolution"/);
  assert.match(html,/id="cpProcessImpact"/);
  assert.match(html,/data-causal-apply/);
  assert.match(html,/data-causal-cancel/);
  assert.match(html,/Current/);
  assert.match(html,/Proposed/);
  assert.match(html,/Ask for copies/);
  assert.doesNotMatch(html,/expert.reviewed|decision authorised|claim approved/i);
  delete globalThis.CasePathReviewNorthStar;
});
test('graph stays available while an actual step form is being edited', () => {
  globalThis.CasePathReviewNorthStar=northstar;
  const view=fixture(),s=causal.session(view.claim_id);
  Object.assign(s,{selected:'compare',preview:null,mode:'edit'});
  const html=causal.render(view,{presentation:'northstar'});
  assert.match(html,/data-review-process-map/);
  assert.match(html,/data-causal-form="node"/);
  assert.match(html,/name="actor"/);
  assert.match(html,/name="reason"/);
  delete globalThis.CasePathReviewNorthStar;
});
test('reuse payoff needs an exact pinned version and an accepted matching history event', () => {
  const view=fixture();
  const fragment={fragment_id:'f1',version:2,fragment_sha256:hash,source_claim_id:'earlier',source_revision:9,name:'Paired-notice review',actor:'Test handler'};
  view.fragments=[fragment];
  assert.equal(northstar.reuseModel(view),null);
  view.graph.fragment_instances=[{...fragment}];
  assert.equal(northstar.reuseModel(view),null);
  view.history=[{event_sha256:'b'.repeat(64),operation:{type:'fragment.apply',fragment_sha256:'c'.repeat(64)},impact:delta}];
  assert.equal(northstar.reuseModel(view),null);
  view.history.push({event_sha256:'d'.repeat(64),actor:'Test handler',reason:'Test-only application',operation:{type:'fragment.apply',fragment_sha256:hash},impact:delta});
  const model=northstar.reuseModel(view);
  assert.equal(model.fragment.source_claim_id,'earlier');
  assert.equal(model.fragment.version,2);
  assert.equal(model.event.event_sha256,'d'.repeat(64));
  assert.equal(model.facts[0].source_id,'target-message');
  assert.equal(model.facts[0].quote,'This is our family home.');
});
test('a wording-only edit cannot be presented as a changed process decision', () => {
  const model=northstar.consequenceModel({node_changes:[{node_id:'compare',before:{label:'Compare notices',execution_state:'ready'},after:{label:'Compare complete notices',execution_state:'ready'}}],next_action_changed:false,next_action:{before:'Ask for copies',after:'Ask for copies'}},fixture().graph);
  assert.equal(model.material,false);
  assert.match(model.summary,/No process or document requirement changes/);
});
test('new prerequisites are named even when the next action is unchanged', () => {
  const model=northstar.consequenceModel(delta,fixture().graph);
  assert.equal(model.material,true);
  assert.match(model.rows[0].after,/Compare the complete notices/);
  assert.equal(model.nextChanged,false);
});
test('source and reviewer text is escaped; only data-backed lineage is shown', () => {
  const view=fixture();
  view.graph.nodes[0].label='<img src=x onerror=alert(1)>';
  const html=northstar.renderProcess(view,{selected:'compare',mode:null,busy:false,error:'',notice:''},{graph:view.graph,node:view.graph.nodes[0],inspector:'<p>Real editor slot</p>',tools:'',impact:'',processState:'Waiting for prerequisites'});
  assert.doesNotMatch(html,/<img src=x/);
  assert.match(html,/&lt;img/);
  assert.doesNotMatch(html,/Reviewed memory was applied/);
});

test('a proposed process stays labelled proposed and can gain its first prerequisite', () => {
  globalThis.CasePathReviewNorthStar=northstar;
  const view=fixture();view.claim_id='proposed';view.process_adopted=false;
  const html=causal.render(view,{presentation:'northstar'});
  assert.match(html,/data-causal-add/);
  assert.match(html,/proposed process/i);
  assert.match(html,/recorded assessment/i);
  delete globalThis.CasePathReviewNorthStar;
});
test('a later edit cannot make historical reuse consequences appear current', () => {
  const view=fixture();
  const fragment={fragment_id:'f1',version:2,fragment_sha256:hash,source_claim_id:'earlier',source_revision:9,name:'Paired-notice review',actor:'Test handler'};
  view.fragments=[fragment];view.graph.fragment_instances=[{...fragment}];
  view.history=[{event_sha256:'d'.repeat(64),revision:6,actor:'Test handler',reason:'Test-only application',operation:{type:'fragment.apply',fragment_sha256:hash},impact:delta}];
  view.evaluation.nodes.find(n=>n.node_id==='resolution').execution_state='ready';
  view.evaluation.nodes.find(n=>n.node_id==='resolution').blocked_by=[];
  const html=northstar.reuseMarkup(view);
  assert.match(html,/When applied/);
  assert.match(html,/Current process/);
  assert.match(html,/data-review-current-result[^>]*>[^<]*Prepare joint resolution: Ready to work/);
});

test('renaming the focused action is a wording change even when next_step text changes',()=>{
 const model=northstar.consequenceModel({node_changes:[{node_id:'compare',before:{label:'Compare notices',execution_state:'ready'},after:{label:'Compare complete notices',execution_state:'ready'}}],next_action_changed:true,next_action:{before:'Compare notices',after:'Compare complete notices'}},fixture().graph);
 assert.equal(model.material,false);assert.equal(model.nextChanged,false);
});

test('an unassessed northstar claim exposes its single existing review action in Process',()=>{
 const presentation=require('../casepath/assets/claims-workspace-presentation-v1.js');
 const html=presentation.workbench(null,{claim_id:'fresh',workflow_state:'received',intake_assessment:null},{northstar:true,detail:{message:{subject:'New claim',body:'Original message'},artifacts:[],state:{binding:{}}}});
 assert.equal((html.match(/id="cwStart"/g)||[]).length,1);
 const processPane=html.slice(html.indexOf('id="cpPane-process"'),html.indexOf('id="cpPane-overview"'));
 const overview=html.slice(html.indexOf('id="cpPane-overview"'),html.indexOf('id="cpPane-documents"'));
 assert.match(processPane,/id="cwStart"/);assert.doesNotMatch(overview,/id="cwStart"/);
});
test('reuse emphasizes the changed receiving decision before an added step',()=>{
 const view=fixture();
 const impact={...delta,node_changes:[{node_id:'compare',label:'Compare the complete notices',before:null,after:{execution_state:'blocked',blocked_by:['earlier']}},...delta.node_changes]};
 const rows=northstar.consequenceModel(impact,view.graph).rows;
 assert.equal(rows[0].id,'resolution');
});

test('a proposed prerequisite is named from its impact before it exists in the current graph',()=>{
 const graph=fixture().graph;graph.nodes=graph.nodes.filter(n=>n.node_id!=='compare');
 const impact={...delta,node_changes:[...delta.node_changes,{node_id:'compare',label:'Compare the complete notices',before:null,after:{node_id:'compare',label:'Compare the complete notices',execution_state:'blocked'}}]};
 const model=northstar.consequenceModel(impact,graph);
 assert.match(model.rows[0].after,/Compare the complete notices/);
});

test('an applied blocking connection is never described as a required prerequisite',()=>{
 const v=fixture(),fragment={fragment_id:'blocking',version:1,fragment_sha256:hash,source_claim_id:'earlier',name:'Test blocker',actor:'Test handler'};
 v.fragments=[fragment];v.graph.fragment_instances=[{...fragment}];v.graph.edges[0].relation='blocks';
 v.history=[{event_sha256:'f'.repeat(64),revision:3,operation:{type:'fragment.apply',fragment_sha256:hash},impact:delta}];
 const html=northstar.reuseMarkup(v);assert.doesNotMatch(html,/now also requires/);assert.match(html,/is now blocked by/);
});

test('current reuse wording respects evaluated edge activation and relation',()=>{
 for(const mode of ['requires','blocks','inactive-requires-with-blocks','missing-evaluation']){
  const v=fixture(),fragment={fragment_id:mode,version:1,fragment_sha256:hash,source_claim_id:'earlier',name:'Test version',actor:'Test handler'};
  v.fragments=[fragment];v.graph.fragment_instances=[{...fragment}];v.history=[{event_sha256:'f'.repeat(64),revision:3,operation:{type:'fragment.apply',fragment_sha256:hash},impact:delta}];
  if(mode==='blocks')v.graph.edges[0].relation='blocks';
  v.evaluation.edges=mode==='missing-evaluation'?[]:v.graph.edges.map(edge=>({...edge,activation:mode==='inactive-requires-with-blocks'?'false':'true'}));
  if(mode==='inactive-requires-with-blocks'){
   const block={...v.graph.edges[0],edge_id:'separate-block',relation:'blocks'};
   v.graph.edges.push(block);v.evaluation.edges.push({...block,activation:'true'});
  }
  const html=northstar.reuseMarkup(v);
  if(mode==='requires'){assert.match(html,/now also requires/);assert.match(html,/still needs review in this case/);}
  else{assert.doesNotMatch(html,/now also requires/);assert.match(html,/is now blocked by/);}
 }
});
test('reuse document passages must belong to the receiving claim sources',()=>{
 const v=fixture(),fragment={fragment_id:'sources',version:1,fragment_sha256:hash,source_claim_id:'earlier',name:'Test version',actor:'Test handler'};
 v.fragments=[fragment];v.graph.fragment_instances=[{...fragment}];v.history=[{event_sha256:'f'.repeat(64),operation:{type:'fragment.apply',fragment_sha256:hash},impact:delta}];
 v.sources=[{artifact_id:'target-a',file_name:'Tenant_notice.pdf'},{artifact_id:'target-b',file_name:'Spouse_notice.pdf'}];
 v.effective_assessment={conflicts:[{sources:[{artifact_id:'target-a',quote:'30. Juni'},{artifact_id:'target-b',quote:'31. Juli'},{artifact_id:'earlier-file',quote:'Another case'}]}]};
 assert.deepEqual(northstar.reuseModel(v).facts.map(f=>f.source_id),['target-a','target-b']);
 const html=northstar.reuseMarkup(v);assert.match(html,/30. Juni/);assert.match(html,/31. Juli/);assert.doesNotMatch(html,/Another case/);
});
