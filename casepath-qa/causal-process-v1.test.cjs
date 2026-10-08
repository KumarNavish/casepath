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
 const change=id=>html.match(new RegExp(`<tr data-impact-id="${id}"[^>]*>[\\s\\S]*?</tr>`))?.[0]||'';
 const side=(row,key)=>row.match(new RegExp(`<td data-impact-side="${key}">[\\s\\S]*?</td>`))?.[0]||'';
 assert.match(side(change('b'),'before'),/Always/);assert.match(side(change('b'),'after'),/Family home/);
 assert.match(side(change('b'),'before'),/Validated/);assert.match(side(change('b'),'after'),/Revised/);
 assert.match(side(change('link'),'before'),/Enables/);assert.match(side(change('link'),'after'),/Requires/);
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

test('selected step relationships use evaluated activation and explicit direction',()=>{
 const v=view('evaluated-relationships');v.graph.nodes.push(node('c',{label:'Prepare response'}),node('d',{label:'Review conflict'}));
 v.graph.edges=[
  {edge_id:'needs',source_node_id:'b',target_node_id:'a',relation:'requires',condition:{const:'true'}},
  {edge_id:'next',source_node_id:'a',target_node_id:'c',relation:'enables',condition:{const:'true'}},
  {edge_id:'stop',source_node_id:'d',target_node_id:'a',relation:'blocks',condition:{const:'true'}}
 ];
 v.evaluation.edges=v.graph.edges.map((e,i)=>({...e,activation:['true','false','unresolved'][i]}));
 v.evaluation.nodes.push({...v.graph.nodes[2],execution_state:'inactive'},{...v.graph.nodes[3],execution_state:'unresolved'});
 const html=ui.render(v),row=id=>html.match(new RegExp(`<li[^>]*data-relationship-id="${id}"[^>]*>[\\s\\S]*?</li>`))?.[0]||'';
 assert.match(row('needs'),/Required before/);assert.match(row('needs'),/Active connection/);assert.ok(row('needs').indexOf('Check separate service')<row('needs').indexOf('Review notice'));
 assert.match(row('next'),/Enables/);assert.match(row('next'),/Inactive connection/);
 assert.match(row('stop'),/Blocks/);assert.match(row('stop'),/Needs clarification/);
 assert.doesNotMatch(html,/Source supports|Evidence proves/);
});

test('a local graph renders one selected step between incoming prerequisites and outgoing branches',()=>{
 const v=view('single-connected-graph');
 v.graph.nodes=[node('a',{label:'Current review'}),node('before',{label:'Check source'}),node('yes',{label:'Request service copy'}),node('no',{label:'Continue notice review'}),node('unrelated',{label:'Unrelated archive'})];
 v.graph.edges=[
  {edge_id:'prerequisite',source_node_id:'before',target_node_id:'a',relation:'requires',condition:{const:'true'}},
  {edge_id:'confirmed',source_node_id:'a',target_node_id:'yes',relation:'branches_to',condition:{flag:'family_home'}},
  {edge_id:'alternative',source_node_id:'a',target_node_id:'no',relation:'branches_to',condition:{not:{flag:'family_home'}}},
  {edge_id:'not-local',source_node_id:'no',target_node_id:'unrelated',relation:'enables',condition:{const:'true'}}
 ];
 v.evaluation.nodes=v.graph.nodes.map(n=>({...n,execution_state:n.node_id==='no'?'inactive':'ready'}));
 v.evaluation.edges=v.graph.edges.map((e,i)=>({...e,activation:['true','true','false','false'][i]}));
 const original=JSON.stringify(v),html=ui.contextMarkup(v,'a',{scope:'overview'});
 assert.equal((html.match(/data-causal-node="a"/g)||[]).length,1);
 assert.equal((html.match(/<strong>Current review<\/strong>/g)||[]).length,1);
 assert.ok(html.indexOf('data-causal-node="before"')<html.indexOf('data-causal-node="a"'));
 assert.ok(html.indexOf('data-causal-node="a"')<html.indexOf('data-causal-node="yes"'));
 assert.ok(html.indexOf('data-causal-node="a"')<html.indexOf('data-causal-node="no"'));
 assert.match(html,/class="cp-context-neighbors cp-context-incoming" aria-label="Incoming connections"/);
 assert.match(html,/class="cp-context-neighbors cp-context-outgoing" aria-label="Outgoing connections"/);
 assert.match(html,/data-relationship-id="alternative" data-activation="false"[\s\S]*?Not \(Family home\)[\s\S]*?Inactive connection/);
 assert.match(html,/data-relationship-id="confirmed" data-activation="true"[\s\S]*?Family home[\s\S]*?Active connection/);
 assert.doesNotMatch(html,/Unrelated archive|not-local/);
 assert.equal(JSON.stringify(v),original);
});

test('parallel relationships share their actual neighbor and preserve every connection state',()=>{
 const v=view('parallel-connections');v.graph.nodes.push(node('c',{label:'Later review'}));
 v.graph.edges=[
  {edge_id:'flow',source_node_id:'b',target_node_id:'a',relation:'enables',condition:{const:'true'}},
  {edge_id:'dependency',source_node_id:'b',target_node_id:'a',relation:'requires',condition:{flag:'family_home'}},
  {edge_id:'unknown',source_node_id:'a',target_node_id:'c',relation:'blocks',condition:{const:'true'}}
 ];
 // The helper presents the supplied projection; it does not reevaluate or hide a relationship.
 v.evaluation.edges=[{edge_id:'flow',activation:'true'},{edge_id:'dependency',activation:'unresolved'}];
 const html=ui.contextMarkup(v,'a'),incoming=html.slice(html.indexOf('class="cp-context-neighbors cp-context-incoming"'),html.indexOf('<div class="cp-context-selected">'));
 assert.equal((incoming.match(/data-causal-node="b"/g)||[]).length,1);
 for(const edge of ['flow','dependency','unknown'])assert.equal((html.match(new RegExp('data-causal-edge="'+edge+'"','g'))||[]).length,1);
 assert.match(html,/data-relationship-id="dependency" data-activation="unresolved"[\s\S]*?Needs clarification/);
 assert.match(html,/data-relationship-id="unknown" data-activation="unknown"[\s\S]*?Not evaluated/);
});

test('reusable context markup escapes source text and keeps element identities scoped',()=>{
 const v=view('context-escaping');v.graph.nodes[0].label='<img src=x onerror=alert(1)>';
 v.graph.nodes[1].label='Review "source" & condition';
 v.graph.edges=[{edge_id:'unsafe"edge',source_node_id:'b',target_node_id:'a',relation:'requires',condition:{flag:'<svg onload=alert(1)>'}}];
 const first=ui.contextMarkup(v,'a',{scope:'overview"<'}),second=ui.contextMarkup(v,'a',{scope:'process'});
 assert.doesNotMatch(first,/<img|<svg|scope="overview"</);
 assert.match(first,/&lt;img/);assert.match(first,/&lt;svg/);assert.match(first,/Review &quot;source&quot; &amp; condition/);
 assert.match(first,/data-causal-edge="unsafe&quot;edge"/);
 const ids=[...`${first}${second}`.matchAll(/\sid="([^"]+)"/g)].map(match=>match[1]);
 assert.equal(ids.length,new Set(ids).size);
 assert.match(ui.contextMarkup(view('isolated-context'),'a'),/No recorded connections for this step/);
 assert.equal(ui.contextMarkup(null,'a'),'');assert.equal(ui.contextMarkup(v,'missing'),'');
});

test('connected documents show their evaluated requirement and review state',()=>{
 const v=view('relationship-documents');v.graph.nodes[0].document_types=['notice','optional_note'];
 v.evaluation.documents=[{document_type:'notice',label:'Notice',required_at_node_ids:['a'],route_state:'held_not_reviewed',requirement_class:'mandatory'},{document_type:'optional_note',label:'Background note',required_at_node_ids:['a'],route_state:'optional',requirement_class:'optional'}];
 const html=ui.render(v);
 assert.match(html,/data-context-document="notice"[\s\S]*?On file · needs review/);
 assert.match(html,/data-context-document="optional_note"[\s\S]*?Optional/);
 assert.match(html,/data-causal-document-open="notice"/);
});

test('impact compares actual requirement changes separately from definition changes',()=>{
 const html=ui.impactMarkup({
  changed_requirement_document_types:['notice'],unchanged_requirement_document_types:['lease'],
  document_changes:[{document_type:'notice',label:'Notice',before:{route_state:'not_needed',request:false},after:{route_state:'needed_now',request:true}},{document_type:'lease',label:'Tenancy agreement',before:{label:'Lease',route_state:'needed_now'},after:{label:'Tenancy agreement',route_state:'needed_now'}}],
  document_definition_changes:[{document_type:'lease',fields:['label'],before:{label:'Lease'},after:{label:'Tenancy agreement'}}],
  next_action_changed:true,next_action:{before:'Review notice',after:'Request notice'}
 });
 assert.match(html,/Current/);assert.match(html,/Proposed/);
 assert.match(html,/1 document requirement changes/);
 const row=id=>html.match(new RegExp(`<tr[^>]*data-impact-id="${id}"[^>]*>[\\s\\S]*?</tr>`))?.[0]||'';
 assert.match(row('notice'),/data-requirement-changed="true"/);assert.match(row('notice'),/Not required/);assert.match(row('notice'),/Needed now/);
 assert.match(row('lease'),/data-requirement-changed="false"/);assert.match(row('lease'),/Requirement unchanged/);assert.match(row('lease'),/Lease/);assert.match(row('lease'),/Tenancy agreement/);
 assert.match(html,/<details[^>]*><summary>What stays unchanged/);assert.match(html,/Review notice/);assert.match(html,/Request notice/);
});

test('a missing edge evaluation is labelled unknown rather than active',()=>{
 const v=view('missing-edge-evaluation');v.graph.edges=[{edge_id:'missing',source_node_id:'b',target_node_id:'a',relation:'requires',condition:{const:'true'}}];
 const html=ui.render(v),row=html.match(/<li[^>]*data-relationship-id="missing"[^>]*>[\s\S]*?<\/li>/)?.[0]||'';
 assert.match(row,/Not evaluated/);assert.doesNotMatch(row,/Active connection/);
});


test('large previews disclose connection details and keep one action pair before changes',()=>{
 const v=view('compact-preview');ui.session(v.claim_id).preview={reason:'Review dependencies',impact:{node_changes:[{node_id:'a',label:'Review notice',before:{label:'Old name',meaning:'Old meaning',condition:{const:'true'},document_types:[]},after:{label:'New name',meaning:'New meaning',condition:{flag:'family_home'},document_types:['notice']}}],edge_changes:[{edge_id:'link',label:'Connection',before:{relation:'enables'},after:{relation:'requires'}}]}};
 const html=ui.render(v);
 assert.equal((html.match(/data-causal-apply/g)||[]).length,1);assert.ok(html.indexOf('data-causal-apply')<html.indexOf('cp-impact-list'));
 assert.match(html,/<details class="cp-impact-connections"><summary>Connections/);assert.match(html,/<summary>2 more changes to Review notice/);
 assert.match(html,/Old name/);assert.match(html,/New name/);assert.match(html,/Old meaning/);assert.match(html,/New meaning/);assert.match(html,/Family home/);assert.match(html,/Requires/);
});


test('document review insufficiency remains visible beside requirement timing',()=>{
 const v=view('insufficient-review');v.evaluation.documents=[{document_type:'notice',label:'Notice',required_at_node_ids:['a'],route_state:'needed_later',review_state:'insufficient'},{document_type:'lease',label:'Lease',required_at_node_ids:['a'],route_state:'held_not_reviewed',review_state:'review_needed'}];
 const html=ui.render(v);
 assert.match(html,/Needed later · Received · insufficient/);assert.match(html,/On file · Review needed/);
 const impact=ui.impactMarkup({changed_requirement_document_types:['notice'],document_changes:[{document_type:'notice',label:'Notice',before:{route_state:'established',review_state:'sufficient'},after:{route_state:'needed_later',review_state:'insufficient'}}]});
 assert.match(impact,/Established/);assert.match(impact,/Needed later · Received · insufficient/);
});

test('a document dependency recalculation does not invent a new source review',()=>{
 const html=ui.impactMarkup({document_changes:[{document_type:'notice',before:{route_state:'held_behind_question',condition_flags:['family_home','arrears']},after:{route_state:'held_behind_question',condition_flags:['arrears']}}],changed_requirement_document_types:[]});
 assert.match(html,/Relevant conditions/);assert.match(html,/Family home, Arrears/);assert.doesNotMatch(html,/Review record updated/);
});
test('the selected step shows its actual blocking prerequisite before other relationships',()=>{
 const v=view('blocking-priority');v.graph.nodes.push(node('c',{label:'Downstream'}));
 v.graph.edges=[{edge_id:'next',source_node_id:'b',target_node_id:'c',relation:'enables'},{edge_id:'required',source_node_id:'a',target_node_id:'b',relation:'requires'}];v.evaluation.edges=v.graph.edges.map(e=>({...e,activation:'true'}));ui.session(v.claim_id).selected='b';
 const html=ui.render(v);assert.ok(html.indexOf('data-relationship-id="required"')<html.indexOf('data-relationship-id="next"'));assert.match(html,/Required before/);
});

test('unchanged impact includes named relationships and distinguishes requirement from document state',()=>{
 const html=ui.impactMarkup({unchanged_node_ids:['a'],unchanged_edge_ids:['e1'],unchanged_requirement_document_types:['notice'],unchanged_document_types:['lease']},{nodes:[node('a'),node('b')],edges:[{edge_id:'e1',source_node_id:'a',target_node_id:'b'}],document_catalog:[{document_type:'notice',label:'Notice'},{document_type:'lease',label:'Lease'}]});
 assert.match(html,/<strong>Connections<\/strong> · Review notice → Check separate service/);
 assert.match(html,/<strong>Document requirements<\/strong> · Notice/);
 assert.match(html,/<strong>Document states<\/strong> · Lease/);
});

test('preview and saved impact disclosures preserve independent entity scopes',()=>{
 const impact={node_changes:[{node_id:'a',before:{label:'Old',meaning:'Before',kind:'review',completed:false},after:{label:'New',meaning:'After',kind:'request',completed:true}}],edge_changes:[{edge_id:'e',before:{relation:'enables'},after:{relation:'requires'}}],unchanged_node_ids:['b']};
 const open=new Set(['preview:Step:a','preview:connections','preview:unchanged','saved:unchanged']);
 const preview=ui.impactMarkup(impact,{}, {scope:'preview',open});
 const saved=ui.impactMarkup(impact,{}, {scope:'saved',open});
 for(const key of ['Step:a','connections','unchanged'])assert.ok(preview.includes(`data-av-disclosure="preview:${key}" open`));
 assert.ok(saved.includes('data-av-disclosure="saved:unchanged" open'));
 assert.ok(!saved.includes('data-av-disclosure="saved:Step:a" open'));
 const ids=[...`${preview}${saved}`.matchAll(/\sid="([^"]+)"/g)].map(m=>m[1]);assert.equal(ids.length,new Set(ids).size);
 assert.ok(!ui.impactMarkup(impact).includes('data-av-disclosure'));
});


test('an unresolved branch stays possible until its signed evaluation activates it',()=>{
 const v=view('possible-branch');v.graph.edges=[{edge_id:'branch',source_node_id:'b',target_node_id:'a',relation:'branches_to',condition:{flag:'family_home'}}];
 v.evaluation.edges=[{edge_id:'branch',activation:'unresolved'}];
 const pending=ui.contextMarkup(v,'a');assert.match(pending,/>Possible branch</);assert.match(pending,/Needs clarification/);assert.doesNotMatch(pending,/>Branches to</);
 v.evaluation.edges[0].activation='true';const active=ui.contextMarkup(v,'a');assert.match(active,/>Branches to</);assert.match(active,/Active connection/);assert.doesNotMatch(active,/Possible branch/);
});
