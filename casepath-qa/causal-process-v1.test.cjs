'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const ui=require('../casepath/assets/causal-process-v1.js');
const node=(id,extra={})=>({node_id:id,label:id==='a'?'Review notice':'Check separate service',meaning:'Check the original notice.',condition:{const:'true'},document_types:[],completed:false,validation:{status:'unvalidated'},...extra});
const view=(id,execution='ready',extra={})=>({claim_id:id,workspace_revision:2,graph:{revision:1,conditions:{family_home:{verdict:'true'}},nodes:[node('a'),node('b')],edges:[],document_catalog:[]},evaluation:{nodes:[{...node('a'),execution_state:execution,activation:'true',...extra},{...node('b'),execution_state:'blocked',activation:'true',blocked_by:['a']}],steps:[{node_id:'a',state:'active',activation:'true'},{node_id:'b',state:'not_reached',activation:'true'}],documents:[]},history:[],fragments:[]});
test('blocked execution is shown even when compatibility steps say not reached',()=>{
 const v=view('blocked');ui.session(v.claim_id).selected='b';const html=ui.render(v);
 assert.match(html,/Blocked by prerequisite/);assert.match(html,/Waiting for Review notice/);
 assert.doesNotMatch(html,/>Not active ·/);
});
test('an inconsistent completed step shows review rather than a success checkmark',()=>{
 const v=view('inconsistent','ready',{inconsistent_completion:true});v.graph.nodes[0].completed=true;
 const html=ui.render(v);assert.match(html,/Completion needs review/);assert.match(html,/completed step conflicts/);
 assert.match(html,/cp-node-number">!</);assert.doesNotMatch(html,/cp-node-number">✓/);
});
test('impact explains ready to blocked and explicitly retains unchanged requirements',()=>{
 const html=ui.impactMarkup({node_changes:[{node_id:'b',label:'Separate service',before:{execution_state:'ready',activation:'true'},after:{execution_state:'blocked',activation:'true'}}],unchanged_document_types:['lease_contract'],unchanged_node_ids:['a'],unchanged_edge_ids:[],next_action:{before:'Continue',after:'Check prerequisite'}});
 assert.match(html,/Ready/);assert.match(html,/Blocked/);assert.match(html,/Lease contract/);assert.match(html,/Check prerequisite/);assert.doesNotMatch(html,/True.*→.*True/);
});
test('an empty graph can be rebuilt with a root step',()=>{
 const v=view('empty');v.graph.nodes=[];v.evaluation.nodes=[];v.evaluation.steps=[];ui.session(v.claim_id).mode='add';
 const html=ui.render(v);assert.match(html,/data-causal-form="node"/);assert.match(html,/Add a process step/);assert.doesNotMatch(html,/name="follows"/);
});
test('untrusted node text is escaped in graph and inspector',()=>{
 const v=view('escape');v.graph.nodes[0].label='<img src=x onerror=alert(1)>';
 const html=ui.render(v);assert.doesNotMatch(html,/<img/);assert.match(html,/&lt;img/);
});
test('validation is counted per node, not inherited by the entire process',()=>{
 const v=view('granular');v.graph.nodes[0].validation.status='validated';ui.session(v.claim_id).expanded=true;
 const html=ui.render(v);assert.match(html,/1<span> \/ 2 steps validated/);assert.match(html,/Unvalidated/);
});
test('condition descriptions preserve compound logic',()=>{
 assert.equal(ui.conditionText({all:[{flag:'family_home'},{not:{flag:'arrears'}}]}),'Family home and Not (Arrears)');
});

test('semantic changes remain explicit even when execution state is unchanged',()=>{
 const html=ui.impactMarkup({node_changes:[{node_id:'b',label:'Service',before:{execution_state:'ready',condition:{const:'true'},validation:{status:'validated'}},after:{execution_state:'ready',condition:{flag:'family_home'},validation:{status:'revised'}}}],edge_changes:[{edge_id:'link',label:'Connection',before:{activation:'true',relation:'enables'},after:{activation:'true',relation:'requires'}}]});
 assert.match(html,/Applies when.*Always → Family home/);assert.match(html,/Validation.*Validated → Revised/);assert.match(html,/Relationship.*Enables → Requires/);
});
test('library distinguishes current claim version from newest definition',()=>{
 const v=view('versions');v.graph.fragment_instances=[{fragment_id:'fragment',version:1,fragment_sha256:'old'}];v.fragments=[{fragment_id:'fragment',version:1,fragment_sha256:'old',name:'Service review',source_claim_id:'other'},{fragment_id:'fragment',version:2,fragment_sha256:'new',name:'Service review',source_claim_id:'other',latest:true}];
 const html=ui.render(v);assert.match(html,/This claim uses version 1 · applied here/);assert.match(html,/Latest available · This claim uses version 1 · update available/);assert.doesNotMatch(html,/New version of Service review/);
});

test('prerequisites follow dependency order even when evaluation preserves insertion order',()=>{
 const v=view('dependency-order');v.graph.nodes[1].label='Confirm handling authority';
 v.evaluation.nodes[1].execution_state='ready';v.evaluation.nodes[0].execution_state='blocked';
 v.graph.edges=[{edge_id:'prerequisite',source_node_id:'b',target_node_id:'a',relation:'requires',condition:{const:'true'},validation:{status:'unvalidated'}}];
 const html=ui.render(v);assert.ok(html.indexOf('data-causal-node="b"')<html.indexOf('data-causal-node="a"'));
 assert.match(html,/Confirm handling authority → Requires/);
});

test('current context includes connected steps rather than unrelated list neighbours',()=>{
 const v=view('connected-context');v.graph.nodes.push(node('c',{label:'Unrelated outcome'}),node('d',{label:'Independent prerequisite'}));v.evaluation.nodes=v.graph.nodes.map(n=>({...n,execution_state:'ready'}));
 v.graph.edges=[{edge_id:'prerequisite',source_node_id:'d',target_node_id:'a',relation:'requires',condition:{const:'true'},validation:{status:'unvalidated'}}];ui.session(v.claim_id).selected='d';
 const html=ui.render(v);assert.match(html,/data-causal-node="a"/);assert.match(html,/data-causal-node="d"/);assert.doesNotMatch(html,/data-causal-node="c"/);
});
