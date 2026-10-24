/* A presentation of the journal-backed review workspace. No mutation authority lives here. */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.CasePathReviewNorthStar=api;
})(typeof globalThis==='object'?globalThis:this,function(){
'use strict';
const h=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const words=value=>String(value??'').replaceAll('_',' ').replace(/^./,c=>c.toUpperCase());
const list=value=>Array.isArray(value)?value:[];
const same=(a,b)=>JSON.stringify(a??null)===JSON.stringify(b??null);
const stateName=value=>({ready:'Ready to work',active:'Ready to work',blocked:'Waiting for prerequisites',completed:'Completed',done:'Completed',unresolved:'Needs clarification',review_required:'Review needed',not_reached:'Not active',inactive:'Not active',inconsistent:'Completion needs review',needed_now:'Needed now',needed_later:'Needed later',not_needed:'Not required',held_not_reviewed:'On file · needs review',established:'Established',held_behind_question:'Depends on an answer'})[value]||words(value||'Not evaluated');
const reviewRoles=[['reader','Claim reader','overview'],['checker','Source checker','process'],['builder','Process builder','process'],['finder','Document finder','documents'],['result','Result checker','overview']];
const icon=kind=>{
  const path={
    reader:'M5 3h9l4 4v14H5z M14 3v5h4 M8 12h7 M8 16h7',
    checker:'M5 3h14v18H5z M8 8l1 1 2-3 M13 8h3 M8 15l1 1 2-3 M13 15h3',
    builder:'M9 3h6v5H9z M3 16h6v5H3z M15 16h6v5h-6z M12 8v4 M6 16v-4h12v4',
    finder:'M5 3h9l4 4v14H5z M14 3v5h4 M8 13h7 M8 17h5',
    result:'M12 3l8 3v6c0 5-4 8-8 10-4-2-8-5-8-10V6z M8 12l3 3 5-6'
  }[kind]||'M5 3h14v18H5z';
  return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.35" aria-hidden="true"><path d="'+path+'"/></svg>';
};
function header(detail){
  return '<header class="cw-detail-head cp-claim-header nr-header"><div class="cp-claim-title"><a class="nr-wordmark" href="?journey=review&amp;view=northstar" data-close-detail>CasePath</a><h1 class="cp-sr-only">'+h(detail.message?.subject||'Claim review')+'</h1></div><nav class="nr-role-tabs" role="tablist" aria-label="Claim review views">'+reviewRoles.map(([id,name,pane])=>'<button type="button" role="tab" id="nr-role-'+id+'" data-review-role="'+id+'" aria-controls="cpPane-'+pane+'" aria-selected="'+(id==='builder')+'" tabindex="'+(id==='builder'?0:-1)+'">'+icon(id)+'<span>'+name+'</span></button>').join('')+'</nav></header>';
}
function consequenceModel(impact={},graph={}){
  const names=new Map(list(graph.nodes).map(n=>[n.node_id,n.label]));
  for(const row of list(impact.node_changes))names.set(row.node_id,row.label||row.after?.label||row.before?.label||names.get(row.node_id)||words(row.node_id));
  const name=id=>names.get(id)||words(id);
  const state=row=>{
    if(!row)return 'Not present';
    const status=stateName(row.inconsistent_completion?'inconsistent':row.execution_state||row.state||row.route_state);
    const blockers=list(row.blocked_by).map(name);
    return status+(blockers.length?' · '+blockers.join(', '):'');
  };
  const materialFields=['execution_state','state','activation','blocked_by','unresolved_dependencies','inconsistent_completion','completed','document_types','condition','entry'];
  const nodes=list(impact.node_changes).filter(row=>!row.before||!row.after||materialFields.some(key=>!same(row.before?.[key],row.after?.[key]))).sort((a,b)=>Number(Boolean(b.before&&b.after))-Number(Boolean(a.before&&a.after)));
  const documents=list(impact.document_changes).filter(row=>!row.before||!row.after||['route_state','request','required_at_node_ids','review_state','requirement_class'].some(key=>!same(row.before?.[key],row.after?.[key])));
  const relationships=list(impact.edge_changes).filter(row=>!row.before||!row.after||['source_node_id','target_node_id','relation','condition','activation'].some(key=>!same(row.before?.[key],row.after?.[key])));
  const rows=[
    ...nodes.map(row=>({kind:'Step',id:row.node_id,label:row.label||name(row.node_id),before:row.before?state(row.before):'Not present',after:row.after?state(row.after):'Removed'})),
    ...documents.map(row=>({kind:'Document',id:row.document_type,label:row.label||words(row.document_type),before:row.before?stateName(row.before.route_state)+(list(row.before.required_at_node_ids).length?' · required by '+row.before.required_at_node_ids.map(name).join(', '):''):'Not required',after:row.after?stateName(row.after.route_state)+(list(row.after.required_at_node_ids).length?' · required by '+row.after.required_at_node_ids.map(name).join(', '):''):'Not required'})),
    ...relationships.map(row=>({kind:'Dependency',id:row.edge_id,label:row.label||'Process connection',before:row.before?name(row.before.source_node_id)+' → '+words(row.before.relation)+' → '+name(row.before.target_node_id):'Not present',after:row.after?name(row.after.source_node_id)+' → '+words(row.after.relation)+' → '+name(row.after.target_node_id):'Removed'}))
  ];
  const material=rows.length>0;
  return {material,rows,nextChanged:material&&impact.next_action_changed===true,next:impact.next_action||{},summary:material?rows.length+' process '+(rows.length===1?'change':'changes')+(impact.next_action_changed?' · next action changes':' · next action unchanged'):'No process or document requirement changes. The wording or review record changes only.'};
}
function reuseModel(view){
  const pins=list(view.graph?.fragment_instances),fragments=Array.isArray(view.fragments)?view.fragments:list(view.fragments?.items);
  for(const pin of pins.slice().reverse()){
    const fragment=fragments.find(f=>f.fragment_sha256===pin.fragment_sha256&&f.fragment_id===pin.fragment_id&&f.version===pin.version&&f.source_claim_id===pin.source_claim_id);
    const event=list(view.history).slice().reverse().find(row=>row.event_sha256&&row.operation?.type==='fragment.apply'&&row.operation.fragment_sha256===pin.fragment_sha256&&row.impact);
    if(!fragment||!event||fragment.source_claim_id===view.claim_id)continue;
    const conditionFacts=Object.entries(view.graph.conditions||{}).map(([flag,value])=>({flag,...(typeof value==='object'?value:{verdict:value})})).filter(f=>typeof f.quote==='string'&&f.quote.trim()).sort((a,b)=>(a.flag==='family_home'?-1:0)-(b.flag==='family_home'?-1:0));
    const sources=new Map(list(view.sources).map(a=>[a.artifact_id,a]));
    const documentFacts=list(view.effective_assessment?.conflicts).flatMap(conflict=>list(conflict.sources)).filter(row=>sources.has(row.artifact_id)&&typeof row.quote==='string'&&row.quote.trim()).map(row=>({source_id:row.artifact_id,quote:row.quote,label:String(sources.get(row.artifact_id).file_name||'Original notice').replaceAll('_',' ')}));
    const facts=documentFacts.length?documentFacts:conditionFacts;
    return {fragment,event,facts,consequence:consequenceModel(event.impact,view.graph)};
  }
  return null;
}
function comparison(impact,graph,{proposed=false}={}){
  const model=consequenceModel(impact,graph);
  const current=proposed?'Current':'Before',next=proposed?'Proposed':'Now';
  const rows=model.rows.slice(0,3);
  return '<section class="nr-consequence" aria-label="Process consequences"><div class="nr-consequence-heading"><h3>'+h(proposed?'What this correction changes':'What changed')+'</h3><p>'+h(model.summary)+'</p></div>'+
    (rows.length?'<table><thead><tr><th scope="col">Affected process</th><th scope="col">'+current+'</th><th scope="col">'+next+'</th></tr></thead><tbody>'+rows.map(row=>'<tr data-review-change="'+h(row.id)+'"><th scope="row">'+h(row.label)+'</th><td>'+h(row.before)+'</td><td>'+h(row.after)+'</td></tr>').join('')+'</tbody></table>':'')+
    '<p class="nr-next-action"><strong>'+(model.nextChanged?'Next action':'Next action unchanged')+'</strong> '+h(model.next.after||'No different next action recorded.')+'</p></section>';
}
function reuseMarkup(view){
  const model=reuseModel(view);
  if(!model)return '';
  const f=model.fragment;
  const sourceFacts=model.facts.slice(0,2).map(fact=>fact.source_id?'<button type="button" class="nr-source-fact" data-noticed-source="'+h(fact.source_id)+'" data-noticed-quote="'+h(fact.quote)+'"><small>'+h(fact.label||'This case’s source passage')+'</small><strong>'+h(fact.quote)+'</strong><span aria-hidden="true">↗</span></button>':'<blockquote>'+h(fact.quote)+'</blockquote>').join('');
  const effect=model.consequence.rows[0];
  const currentNode=effect?.kind==='Step'?list(view.evaluation?.nodes).find(n=>n.node_id===effect.id):null;
  const currentDocument=effect?.kind==='Document'?list(view.evaluation?.documents).find(d=>d.document_type===effect.id):null;
  const names=new Map(list(view.graph.nodes).map(n=>[n.node_id,n.label]));
  const historicalNode=list(model.event.impact.node_changes).find(n=>n.node_id===effect?.id);
  const addedPending=list(historicalNode?.after?.blocked_by).filter(id=>!list(historicalNode?.before?.blocked_by).includes(id)&&list(currentNode?.blocked_by).includes(id));
  const evaluatedEdges=new Map(list(view.evaluation?.edges).map(edge=>[edge.edge_id,edge]));
  const activeRequirements=addedPending.filter(id=>list(view.graph.edges).some(edge=>edge.source_node_id===id&&edge.target_node_id===effect?.id&&edge.relation==='requires'&&evaluatedEdges.get(edge.edge_id)?.activation==='true'));
  const otherBlockers=addedPending.filter(id=>!activeRequirements.includes(id));
  const named=ids=>ids.map(id=>'“'+(names.get(id)||words(id))+'”').join(', ');
  const pendingStatement=[activeRequirements.length?'Still requires '+named(activeRequirements)+'.':'',otherBlockers.length?'Still blocked by '+named(otherBlockers)+'.':''].filter(Boolean).join(' ');
  const preservedConnections=list(historicalNode?.before?.blocked_by).filter(id=>list(view.graph.edges).some(edge=>edge.source_node_id===id&&edge.target_node_id===effect?.id));
  const preservedNote=preservedConnections.length?'Earlier process connection retained: '+preservedConnections.map(id=>names.get(id)||words(id)).join(', ')+'.':'';
  const pendingEdges=list(view.graph.edges).filter(edge=>edge.target_node_id===effect?.id&&activeRequirements.includes(edge.source_node_id)&&edge.relation==='requires'&&evaluatedEdges.get(edge.edge_id)?.activation==='true');
  const boundaryReview=pendingEdges.some(edge=>edge.validation?.status!=='validated')?'The imported dependency still needs review in this case.':pendingEdges.length?'The dependency has a recorded review in this case.':'';
  const alreadyWaiting=historicalNode?.before?.execution_state==='blocked'&&historicalNode?.after?.execution_state==='blocked'?'This step was already waiting before application.':'';
  const currentResult=currentNode?stateName(currentNode.inconsistent_completion?'inconsistent':currentNode.execution_state||currentNode.state):currentDocument?stateName(currentDocument.route_state):effect?.kind==='Step'||effect?.kind==='Document'?'This item is no longer in the current process.':'Open the graph to review the current dependency.';
  const currentBlockers=list(currentNode?.blocked_by).filter(id=>!addedPending.includes(id));
  const next=view.effective_assessment?.next_step;
  const nextUnchanged=typeof next==='string'&&next===model.consequence.next.after&&model.event.impact.next_action_changed===false;
  const nextHistory=model.event.impact.next_action_changed===true?'Next action changed on application.':model.event.impact.next_action_changed===false?'Next action unchanged by this application.':'No next-action comparison recorded.';
  const history=effect?'<section class="nr-application-change" aria-label="Historical application change" data-review-application-history><div class="nr-application-heading"><p>When applied · revision '+h(model.event.revision??'recorded')+'</p><p>'+h([alreadyWaiting,nextHistory].filter(Boolean).join(' '))+(preservedConnections.length?' <span data-review-retained-context>Earlier process connections retained.</span>':'')+'</p></div><div class="nr-before-after"><div class="nr-affected-step" data-review-affected-step="'+h(effect.id)+'">'+(effect.kind==='Step'?'<span class="nr-affected-number" data-review-ordinal-for="'+h(effect.id)+'" hidden></span>':'')+'<div><small>Affected '+h(effect.kind.toLowerCase())+'</small><strong>'+h(effect.label)+'</strong></div></div><div class="nr-before" data-review-before><small>Before application</small><p>'+h(effect.before)+'</p></div><span class="nr-change-arrow" aria-hidden="true">→</span><div class="nr-after" data-review-after><small>After application</small><p>'+h(effect.after)+'</p></div></div></section>':'<p class="nr-no-effect">The saved process version produced no different process or document requirement.</p>';
  return '<section class="nr-reuse" aria-label="Reviewed process reuse" data-review-reuse="'+h(f.fragment_sha256)+'"><header><h3>Earlier review → this case</h3><p>Exact saved version '+h(f.version)+' · applied in this claim</p></header>'+history+'<div class="nr-reuse-cards">'+
    '<article data-review-reuse-card="sources"><h4>'+icon('reader')+'This case’s sources</h4>'+ (sourceFacts||'<p>No quoted condition is available in this process view. Open the original sources to inspect this case.</p>')+'</article>'+
    '<article data-review-reuse-card="version"><h4>'+icon('builder')+'Reviewed process version</h4><strong>'+h(f.name)+'</strong><p>Saved by '+h(f.actor||f.handler||'the recorded reviewer')+'</p><a href="?journey=review&amp;view=northstar#claim='+encodeURIComponent(f.source_claim_id)+'">Open the source case ↗</a><details><summary>Version provenance</summary><dl><dt>Version</dt><dd>'+h(f.version)+'</dd><dt>Source revision</dt><dd>'+h(f.source_revision??f.source_workspace_revision??'See source record')+'</dd><dt>Version identity</dt><dd><code>'+h(f.fragment_sha256)+'</code></dd><dt>Accepted application</dt><dd><code>'+h(model.event.event_sha256)+'</code></dd></dl><p>'+h(model.event.reason||'Saved application of the selected process version.')+'</p></details>'+(preservedNote?'<details class="nr-application-record"><summary>Earlier process connections</summary><p data-review-preserved-connection>'+h(preservedNote)+'</p></details>':'')+'</article>'+
    '<article data-review-reuse-card="result"><h4>'+icon('result')+'Result in this case</h4><p class="nr-current-state">Current process · <strong data-review-current-result>'+h(currentResult)+'</strong></p>'+(pendingStatement?'<p data-review-current-dependency>'+h(pendingStatement)+'</p>':'')+(currentBlockers.length?'<p>Also waiting for '+h(named(currentBlockers))+'.</p>':'')+(boundaryReview?'<p class="nr-boundary-review">'+h(boundaryReview)+'</p>':'')+'<p class="nr-current-next" data-review-current-next><small>'+h(nextUnchanged?'Next action · unchanged by this application':'Current next action')+'</small>'+h(next||'No current next action recorded.')+'</p></article></div>'+'<p class="nr-review-limit nr-reuse-notice">This case keeps its own facts, source files and evidence reviews. A recorded process review does not authorise the claim outcome. Qualified review is still required.</p></section>';
}
function renderProcess(view,s,ui){
  const graph=ui.graph||view.graph,nodes=list(graph.nodes),selected=ui.node||nodes.find(n=>n.node_id===s.selected)||nodes[0];
  const evaluations=new Map(list(view.evaluation?.nodes||view.evaluation?.steps).map(row=>[row.node_id,row]));
  const last=list(view.history).slice().reverse().find(row=>row.impact&&row.event_sha256);
  const payoff=!s.preview&&!s.mode&&reuseModel(view);
  const map='<nav class="nr-process-map" aria-label="Working process graph" data-review-process-map><svg class="nr-process-links" aria-hidden="true"></svg><ol>'+nodes.map((node,i)=>{
    const row=evaluations.get(node.node_id)||{},status=stateName(row.inconsistent_completion?'inconsistent':row.execution_state||row.state);
    return '<li><button type="button" class="nr-process-node" data-causal-node="'+h(node.node_id)+'" aria-pressed="'+(node.node_id===selected?.node_id)+'"><span class="nr-step-number">'+(row.execution_state==='completed'?'✓':i+1)+'</span><strong>'+h(node.label)+'</strong><small>'+h(status)+'</small></button></li>';
  }).join('')+'</ol></nav>';
  const preview=s.preview?'<section class="cp-impact nr-impact" tabindex="-1" id="cpProcessImpact"><p class="nr-eyebrow">Preview · nothing saved yet</p>'+comparison(s.preview.impact,graph,{proposed:true})+'<p>'+h(s.preview.reason||'')+'</p><div class="cp-actions cp-impact-actions"><button type="button" class="cw-button cw-button-primary" data-causal-apply>Apply to this claim</button><button type="button" class="cw-button" data-causal-cancel>Keep current process</button></div><details class="nr-impact-details"><summary>All changed and unchanged requirements</summary>'+ui.impact+'</details></section>':'';
  const recent=!s.preview&&!s.mode&&last?'<details class="nr-last-change"><summary>Last saved consequence · '+h(last.actor||'Recorded reviewer')+'</summary>'+comparison(last.impact,graph)+'</details>':'';
  return '<section class="cp-causal nr-causal" id="cpCausalProcess" data-claim-id="'+h(view.claim_id)+'" data-workspace-revision="'+h(view.workspace_revision)+'"'+(payoff?' data-review-payoff="true"':'')+' aria-labelledby="cpCausalTitle" '+(s.busy?'aria-busy="true"':'')+'>'+
    '<header class="nr-process-heading"><div><h2 id="cpCausalTitle">'+(view.process_adopted===false?'Proposed process':'Working process')+'</h2><p>'+h(ui.processState||'Review the process and its evidence')+'</p></div><div><span>Revision '+h(graph.revision)+'</span>'+(view.undo?'<button type="button" class="cw-text-button" data-causal-undo>Undo last change</button>':'')+'<button type="button" class="cw-text-button" data-causal-add>Add step</button>'+(reuseModel(view)?'<button type="button" class="cw-text-button" data-review-result>Review reuse result →</button>':'')+'</div></header>'+
    (view.process_adopted===false?'<p class="cp-process-warning">This claim still uses its recorded assessment. Preview and apply a correction to adopt this proposed process.</p>':'')+
    '<div class="cp-process-status" data-state="'+(s.busy?'working':s.notice?'saved':'idle')+'" role="status" aria-live="polite">'+h(s.busy?'Calculating consequences…':s.notice||'')+'</div>'+
    (s.error?'<div class="cp-process-warning" role="alert">'+h(s.error)+' <button type="button" class="cw-button" data-causal-reload>Reload saved process</button></div>':'')+
    (payoff?'<details class="nr-full-process" data-review-full-process open><summary>Full process · '+nodes.length+' steps <span>Revision '+h(graph.revision)+'</span></summary>'+map+'</details>':map)+'<div class="nr-review-context"><div class="nr-selected-heading"><h3>'+h(selected?.label||'Process review')+'</h3>'+(!s.mode&&!s.preview&&selected?'<button type="button" class="cw-text-button nr-edit-decision" data-causal-edit>Edit decision</button>':'')+'</div><aside class="cp-process-inspector" aria-label="Selected process step">'+(preview||ui.inspector)+'</aside></div>'+recent+ui.tools+
    '<p class="nr-review-limit">Original evidence remains unchanged. Process completion and the claim decision are separate.</p></section>';
}
const observers=new WeakMap();
function bindGraph(container,view){
  const map=container.querySelector('[data-review-process-map]');
  if(!map)return;
  const previous=observers.get(container),state=previous?.claimId===view.claim_id?previous.state:{resultExpanded:false};
  previous?.disconnect();
  const disclosure=map.closest('[data-review-full-process]'),panel=container.closest('#cwDetailPanel')||container.querySelector('#cwDetailPanel');
  let role;
  function draw(){
    if(!map.isConnected)return;
    const svg=map.querySelector('svg'),bounds=map.getBoundingClientRect(),buttons=new Map([...map.querySelectorAll('[data-causal-node]')].map(el=>[el.dataset.causalNode,el]));
    // The map already has the shared presentation order. Never number this
    // second view from the journal's raw node-array order.
    for(const marker of container.querySelectorAll('[data-review-ordinal-for]')){
      const label=buttons.get(marker.dataset.reviewOrdinalFor)?.querySelector('.nr-step-number')?.textContent.trim()||'';
      marker.textContent=label;marker.hidden=!label;
    }
    if(!bounds.width||!bounds.height)return;
    container.style?.setProperty('--nr-map-height',Math.ceil(bounds.height+12)+'px');
    const selected=map.querySelector('[aria-pressed="true"]')?.dataset.causalNode;
    const paths=list(view.graph.edges).map(edge=>{
      const a=buttons.get(edge.source_node_id)?.getBoundingClientRect(),b=buttons.get(edge.target_node_id)?.getBoundingClientRect();
      if(!a||!b)return '';
      const horizontal=Math.abs(a.top-b.top)<4;
      const x1=(horizontal?a.right:a.left+a.width/2)-bounds.left,y1=(horizontal?a.top+a.height/2:a.bottom)-bounds.top;
      const x2=(horizontal?b.left:b.left+b.width/2)-bounds.left,y2=(horizontal?b.top+b.height/2:b.top)-bounds.top;
      const d=horizontal?'M '+x1+' '+y1+' L '+x2+' '+y2:'M '+x1+' '+y1+' V '+((y1+y2)/2)+' H '+x2+' V '+y2;
      return '<path d="'+d+'" marker-end="url(#nr-process-arrow)" class="'+([edge.source_node_id,edge.target_node_id].includes(selected)?'selected':'')+'"/>';
    }).join('');
    svg.setAttribute('viewBox','0 0 '+bounds.width+' '+bounds.height);svg.innerHTML='<defs><marker id="nr-process-arrow" viewBox="0 0 6 6" refX="5" refY="3" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 6 3 L 0 6 z" fill="#b5b1b5"/></marker></defs>'+paths;
  }
  function syncRole(){
    const next=panel?.dataset.reviewActiveRole||'builder';
    if(role!==next){role=next;if(disclosure)disclosure.open=role==='result'?state.resultExpanded:true;}
    draw();
  }
  const toggle=()=>{if(role==='result')state.resultExpanded=disclosure.open;draw();};
  disclosure?.addEventListener('toggle',toggle);
  syncRole();
  let resize,roles;
  if(typeof ResizeObserver!=='undefined'){resize=new ResizeObserver(draw);resize.observe(map);}
  if(disclosure&&panel&&typeof MutationObserver!=='undefined'){roles=new MutationObserver(syncRole);roles.observe(panel,{attributes:true,attributeFilter:['data-review-active-role']});}
  observers.set(container,{claimId:view.claim_id,state,disconnect(){resize?.disconnect();roles?.disconnect();disclosure?.removeEventListener('toggle',toggle);}});
}
return Object.freeze({header,renderProcess,consequenceModel,reuseModel,reuseMarkup,comparison,bindGraph});
});
