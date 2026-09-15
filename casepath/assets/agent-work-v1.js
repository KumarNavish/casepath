/* Agent-work projections for the existing CasePath workspace.
   No provider code, claim truth, artificial timing or invented work lives here. */
(function () {
  'use strict';
  const ROOT='/api/agent-work/v1', CONTRACT='casepath.agent-work/1.0.0';
  const h=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const icon=(name)=>`<svg class="aw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${({work:'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',close:'m6 6 12 12M6 18 18 6',arrow:'M4 12h15m-5-5 5 5-5 5',source:'M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 12h8M8 16h6',check:'m5 12 4 4L19 6',link:'m9 15 6-6M7 17l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M17 7l1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0'})[name]||'M5 12h14'}"/></svg>`;
  const state={cap:null,claim:null,run:null,events:[],summary:null,busy:false,visible:true,timer:null,fetching:false,workforce:false,forceRefresh:null,renderKey:null,workforceKey:null,messages:new Map()};
  const time=t=>t?new Intl.DateTimeFormat(undefined,{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(t)):'—';
  const label=s=>({not_started:'Not started',working:'Working',completed:'Completed',blocked:'Needs review',unconfirmed:'Outcome unconfirmed',queued:'Queued',running:'Processing',interrupted:'Interrupted',failed:'Needs review'})[s]||s;
  const roleName=r=>state.cap?.roles.find(x=>x.id===r)?.label||'CasePath';
  const currentLabel=r=>r.currentness==='historical'?'Previous review':r.currentness==='unconfirmed'?'Check saved state':label(r.status);
  const currentTone=r=>['historical','unconfirmed'].includes(r.currentness)?'unconfirmed':statusClass(r.status);
  const statusClass=s=>['completed','working','blocked','unconfirmed'].includes(s)?s:'quiet';
  function objectTitle(o){
    const value=o?.value||{};
    if(o?.kind==='role_completion')return roleName(value.role)+' · completed work';
    if(o?.kind==='branch')return value.condition||value.label||'Conditional handling path';
    return value.title||value.text||value.filename||value.name||({source_integrity:'Source integrity check',execution_plan:'Execution plan',authority_snapshot:'Verified handling state',readiness:'Current readiness',next_action:'Next action'})[o?.id]||({span:'Source passage',source_link:'Process–evidence link',plan:'Execution plan'})[o?.kind]||'Recorded work';
  }
  async function request(path,options={}) {
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
    try {
      const response=await fetch(ROOT+path,{credentials:'same-origin',cache:'no-store',redirect:'error',...options,signal:controller.signal});
      const value=await response.json();
      if(!response.ok)throw new Error(typeof value.detail==='string'?value.detail:'Work record unavailable');
      if(value.contract!==CONTRACT)throw new Error('The work record uses an unsupported contract.');
      return value;
    } finally {clearTimeout(timer);}
  }
  function getClaim() {
    const panel=document.getElementById('cwDetailPanel'),detail=document.getElementById('cwDetail');
    if(!panel||!detail||detail.hidden)return null;
    return panel.dataset.openClaimId||panel.dataset.claimId||null;
  }
  function mount() {
    const root=document.getElementById('claimsWorkspace');if(!root||!state.cap)return;
    const nav=root.querySelector('.cp-navigation');
    if(nav&&!document.getElementById('awWorkforceButton')){
      const button=document.createElement('button');button.id='awWorkforceButton';button.type='button';button.innerHTML=icon('work')+'<span>AI workforce</span>';button.setAttribute('aria-label','AI workforce');button.setAttribute('aria-pressed','false');button.addEventListener('click',()=>showWorkforce());nav.append(button);
    }
    const claim=getClaim();
    if(claim!==state.claim){document.getElementById('awInspector')?.close();state.inspection=null;state.claim=claim;state.run=null;state.events=[];state.summary=null;state.renderKey=null;}
    if(!claim)return;
    const work=root.querySelector('.cp-work-column');if(!work)return;
    if(!document.getElementById('awClaimWork')){
      const section=document.createElement('section');section.id='awClaimWork';section.className='aw-work-strip';section.setAttribute('aria-label','Agent work');work.prepend(section);state.renderKey=null;
    }
    const start=document.getElementById('cwStart');
    if(start&&!start.dataset.agentWorkEntry){start.dataset.agentWorkEntry='true';start.textContent='Start team review';}
    renderClaim();
  }
  function compactSummary(summary){
    if(!summary)return '<span class="aw-kicker">Agent work</span><p class="aw-muted">No agent run is recorded for this claim.</p>';
    const active=summary.current_role,complete=summary.status==='completed';
    return `<span class="aw-kicker">${summary.facts_worker==='external_facts'?'Mixed workers · same authority':'Reference workers · same authority'}</span><div class="aw-run-heading"><strong>${complete?'Six roles completed':active?`${h(active.label)} · ${h(label(active.status))}`:h(label(summary.status))}</strong><span>${summary.completed_roles} of 6 stages</span></div>${summary.currentness==='historical'?'<p class="aw-stale">The claim has changed since this run. Its work remains inspectable as history.</p>':''}${summary.currentness==='unconfirmed'?'<p class="aw-stale">The current claim state could not be confirmed. Saved work is available, but it must not replace the current process.</p>':''}${summary.status==='blocked'||summary.status==='unconfirmed'?`<p class="aw-stale">${h(summary.last_message)}</p>`:''}`;
  }
  function roleTrack(summary){return summary?`<ol class="aw-role-track" aria-label="Recorded stages">${summary.roles.map(r=>`<li data-status="${statusClass(r.status)}"><button type="button" data-aw-role="${h(r.id)}" ${r.status==='not_started'?'disabled':''}><span class="aw-role-dot">${r.status==='completed'?icon('check'):''}</span><strong>${h(r.label)}</strong><small>${h(label(r.status))}${r.limited_source_extractions?.length?' · limited source coverage':''}</small></button></li>`).join('')}</ol>`:'';}
  function renderClaim(){
    const host=document.getElementById('awClaimWork');if(!host)return;
    const summary=state.summary,hasStart=Boolean(document.getElementById('cwStart'));
    const key=JSON.stringify([summary?.run_id,summary?.last_sequence,summary?.status,summary?.currentness,state.busy,hasStart,summary?.recovery]);
    if(state.renderKey===key)return;
    state.renderKey=key;
    if(summary?.run_id)host.dataset.awRunId=summary.run_id;else delete host.dataset.awRunId;
    const actions=summary?.recovery?.can_resume?`<button type="button" class="aw-text-button" data-aw-resume ${state.busy?'disabled':''}>Resume saved work ${icon('arrow')}</button>`:(!hasStart&&!['queued','running','unconfirmed','interrupted'].includes(summary?.status))?`<button type="button" class="aw-text-button" data-aw-start ${state.busy?'disabled':''}>${summary?'Review current state':'Inspect with agents'} ${icon('arrow')}</button>`:'';
    const start=document.getElementById('cwStart');
    if(start){
      const waiting=['queued','running','unconfirmed','interrupted'].includes(summary?.status);
      if(waiting){start.dataset.awLocked='true';start.disabled=true;start.textContent=summary.recovery?.can_resume?'Resume using the saved work above':summary.status==='running'?'Team review in progress':'Saved work needs checking';}
      else if(start.dataset.awLocked){delete start.dataset.awLocked;start.disabled=state.busy;start.textContent='Start team review';}
    }
    const focusedRole=host.contains(document.activeElement)?document.activeElement?.dataset?.awRole:null;
    host.innerHTML=compactSummary(summary)+roleTrack(summary)+`<div class="aw-strip-actions">${summary?'<button class="aw-text-button" type="button" data-aw-timeline>View recorded work</button>':''}${actions}${state.cap?.facts_workers?.includes('external_facts')?'<label class="aw-worker-select">Facts worker <select id="awFactsWorker"><option value="reference">Reference</option><option value="external_facts">External model · bounded</option></select></label>':''}</div><p class="aw-message" id="awRequestStatus" role="status" aria-live="polite"></p>`;
    const pending=pendingRequest();if(pending)document.getElementById('awRequestStatus').innerHTML='A submitted work request is unconfirmed. <button type="button" class="aw-text-button" data-aw-retry>Check the same request</button>';
    if(focusedRole)host.querySelector(`[data-aw-role="${CSS.escape(focusedRole)}"]`)?.focus({preventScroll:true});
    if(state.messages.has(state.claim)&&!pending)document.getElementById('awRequestStatus').textContent=state.messages.get(state.claim);
    renderTimeline();renderProcess();
  }
  function pendingRequest(){try{return JSON.parse(sessionStorage.getItem('casepath.agent-work.pending.'+state.claim)||'null');}catch(_){return null;}}
  function report(message){if(state.claim)state.messages.set(state.claim,message);const target=document.getElementById('awRequestStatus');if(target)target.textContent=message;}
  async function startWork(retry=false){
    if(state.busy||!state.claim)return;
    const selectedWorker=document.getElementById('awFactsWorker')?.value||'reference';
    state.busy=true;state.renderKey=null;renderClaim();
    const claim=state.claim;
    try{
      let body=retry?pendingRequest():null;
      if(!body){
        if(pendingRequest())throw new Error('Check the existing unconfirmed request before starting another.');
        const context=await request(`/claims/${encodeURIComponent(claim)}/context`);
        body={idempotency_key:'work-ui-'+crypto.randomUUID(),expected_context_sha256:context.context_sha256,facts_worker:selectedWorker};
        sessionStorage.setItem('casepath.agent-work.pending.'+claim,JSON.stringify(body));
      }
      report('Submitting the work request…');
      const result=await request(`/claims/${encodeURIComponent(claim)}/runs`,{method:'POST',headers:{'Content-Type':'application/json','X-CasePath-Agent-Work':'1'},body:JSON.stringify(body)});
      sessionStorage.removeItem('casepath.agent-work.pending.'+claim);state.messages.delete(claim);
      if(state.claim===claim){state.run=result;state.summary=result.summary;state.events=[];state.renderKey=null;renderClaim();}
    }catch(error){if(state.claim===claim)report(error.name==='AbortError'?'No completion response was received. The same request can be checked; do not create a new one.':error.message);}
    finally{state.busy=false;state.renderKey=null;renderClaim();void poll();}
  }
  async function resumeWork(){
    if(state.busy||!state.claim||!state.summary?.recovery?.can_resume)return;
    const claim=state.claim,run=state.summary.run_id;
    state.busy=true;state.renderKey=null;renderClaim();
    try{
      const response=await request(`/claims/${encodeURIComponent(claim)}/runs/${encodeURIComponent(run)}/resume`,{method:'POST',headers:{'X-CasePath-Agent-Work':'1'}});
      if(state.claim===claim&&state.summary?.run_id===run){state.run=response;state.summary=response.summary;state.messages.delete(claim);}
    }catch(error){if(state.claim===claim)report(error.name==='AbortError'?'The resume response was not confirmed. Check the saved work before trying again.':error.message);}
    finally{state.busy=false;state.renderKey=null;renderClaim();void poll();}
  }
  const HIDDEN_OPERATIONS=new Set(['WORK_PRODUCT_RECORDED','RUN_QUEUED','PROCESS_INSPECTED']);
  function renderTimeline(){
    const panel=document.getElementById('cpPanel-activity');if(!panel||!state.run)return;
    let host=document.getElementById('awTimeline');
    if(!host){host=document.createElement('section');host.id='awTimeline';host.className='aw-timeline';panel.prepend(host);}
    const events=state.events.filter(e=>!HIDDEN_OPERATIONS.has(e.operation));
    const version=state.summary.run_id+':'+state.events.length+':'+state.events.at(-1)?.event_sha256;
    const previous=host.dataset.eventCount;if(previous===version)return;
    host.dataset.eventCount=version;
    host.innerHTML=`<header class="aw-section-heading"><div><h3>Agent execution</h3><p>Source reads, checked products and handoffs—recorded as they happened.</p></div><span>${events.length} events</span></header><ol>${events.map(e=>`<li data-role="${h(e.role||'kernel')}" data-operation="${h(e.operation)}"><time datetime="${h(e.timestamp)}">${h(time(e.timestamp))}</time><button type="button" data-aw-event="${e.sequence}"><span class="aw-event-role">${h(roleName(e.role))}${e.worker_kind==='external'?' <small>External</small>':''}</span><strong>${h(e.message)}</strong>${e.sources?.length?`<blockquote>“${h(e.sources[0].quote.slice(0,170))}${e.sources[0].quote.length>170?'…':''}”</blockquote>`:''}<span class="aw-event-state" data-status="${e.status==='rejected'?'blocked':'quiet'}">${h(e.status)}${e.gate?' · gate recorded':''}</span></button></li>`).join('')}</ol>`;
  }
  function renderProcess(){
    const panel=document.getElementById('cpPanel-process');if(!panel||!state.run)return;
    const objects=state.run.objects,nodes=objects.filter(o=>o.kind==='process_node');
    if(!nodes.length){document.getElementById('awProcessCanvas')?.remove();panel.classList.remove('aw-has-process');return;}
    let host=document.getElementById('awProcessCanvas');if(!host){host=document.createElement('section');host.id='awProcessCanvas';host.className='aw-process';panel.prepend(host);}
    if(state.summary.currentness!=='current'||!state.summary.roles.some(r=>r.id==='process_decision_mapping'&&r.status==='completed')){host.hidden=true;panel.classList.remove('aw-has-process');return;}
    host.hidden=false;
    const key=state.summary.run_id+':'+nodes.length+':'+state.summary.last_sequence+':'+state.summary.currentness;if(host.dataset.version===key){panel.classList.add('aw-has-process');return;}host.dataset.version=key;
    const snap=objects.find(o=>o.kind==='authority_snapshot')?.value;
    const current=snap?.process?.current_overlay?.current_node_id,done=snap?.process?.current_overlay?.completed_node_ids||[];
    const branches=objects.filter(o=>o.kind==='branch'),obligations=objects.filter(o=>o.kind==='obligation');
    host.innerHTML=`<header class="aw-section-heading"><div><h3>The mapped handling path</h3><p>Every step below matches the existing gated claim state.</p></div></header><ol class="aw-graph">${nodes.map(o=>`<li data-node-state="${done.includes(o.value.node_id)?'complete':current===o.value.node_id?'current':'future'}"><span class="aw-graph-point">${done.includes(o.value.node_id)?icon('check'):''}</span><div class="aw-node"><button type="button" data-aw-object="${h(o.id)}"><span>${current===o.value.node_id?'Current decision':done.includes(o.value.node_id)?'Completed step':'Process step'}</span><strong>${h(o.value.title)}</strong>${icon('link')}</button>${obligations.filter(e=>e.value.process_node_ids.includes(o.value.node_id)).map(e=>`<button type="button" class="aw-linked-requirement" data-aw-object="${h(e.id)}">${icon('source')}<span>${h(e.value.title)}</span><small>${h(e.value.evidence_class==='conditional'?'Only if needed':e.value.evidence_class==='received'?'Received':e.value.mandatory_now?'Needed now':e.value.evidence_class)}</small></button>`).join('')}${branches.filter(b=>b.value.from_node_id===o.value.node_id).map(b=>`<button type="button" class="aw-branch" data-branch="${h(b.value.state)}" data-aw-object="${h(b.id)}">${icon('arrow')}<span>${h(b.value.condition||b.value.label||'Conditional path')}</span><small>${b.value.state==='selected'?'Active path':'Alternative'}</small></button>`).join('')}</div></li>`).join('')}</ol><p class="aw-muted">Mapped work is not a new claim approval. Open a decision to inspect its recorded rule and evidence links.</p>`;
    panel.classList.add('aw-has-process');
  }
  function openTimeline(role=null){
    document.querySelector('#cpTab-activity')?.click();
    const host=document.getElementById('awTimeline');
    const target=role?host?.querySelector(`[data-role="${CSS.escape(role)}"]`):host;
    target?.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth'});
    target?.querySelector('button')?.focus({preventScroll:true});
  }
  function detailDialog(){
    let dialog=document.getElementById('awInspector');if(dialog)return dialog;
    dialog=document.createElement('dialog');dialog.id='awInspector';dialog.className='aw-inspector';document.getElementById('claimsWorkspace').append(dialog);return dialog;
  }
  function refreshInspectionContext(unavailable=false){
    const dialog=document.getElementById('awInspector'),host=dialog?.querySelector('.aw-inspection-state');
    if(!dialog?.open||!host||!state.inspection)return;
    const saved=state.inspection.run.summary,latest=state.summary;
    const classification=unavailable?'unconfirmed':latest?.run_id===saved.run_id?latest.currentness:saved.currentness;
    const message=classification==='historical'?'This is historical work from a previous claim state.':classification==='unconfirmed'?'The current claim state is unconfirmed. This saved work is not a current decision.':latest?.run_id!==saved.run_id?'A later review is available. This inspector keeps the earlier recorded work.':'';
    if(host.textContent!==message)host.innerHTML=message?`<p class="aw-stale">${h(message)}</p>`:'';
  }
  function inspect(event=null,objectId=null){
    if(!state.run)return;
    const alreadyOpen=document.getElementById('awInspector')?.open;
    if(!alreadyOpen||event||!state.inspection)state.inspection={run:state.run,events:state.events.slice()};
    const inspected=state.inspection;
    const objects=inspected.run.objects,lookupId=objectId||(event?.operation==='SOURCE_OPENED'?'source:'+event.object_id:event?.operation==='AGENT_COMPLETED'?'complete:'+event.role:event?.object_id);
    let obj=objects.find(o=>o.id===lookupId);
    if(event&&lookupId){const anchored=inspected.events.find(e=>e.sequence>event.sequence&&e.operation==='WORK_PRODUCT_RECORDED'&&e.object_id===lookupId);if(anchored)obj={id:lookupId,kind:anchored.object_kind,value:anchored.after.value,sha256:anchored.after.value_sha256,event_sequence:anchored.sequence};}
    const value=event&&event.after&&!['SOURCE_OPENED','AGENT_COMPLETED'].includes(event.operation)?event.after:obj?.value||event?.after||{};
    const spans=event?.sources?.length?event.sources:value.source?[value.source]:obj?.kind==='span'?[value]:[];
    const links=new Set(event?.links||[]);
    const handoff=event?.operation==='HANDOFF_COMPLETED'?inspected.events.find(e=>e.sequence===event.parent_event):event;
    if(handoff?.operation==='HANDOFF_STARTED')(handoff.after?.products||[]).forEach(p=>links.add(p.object_id));
    if(obj?.kind==='role_completion'){const owned=new Set(inspected.events.filter(e=>e.role===value.role&&e.operation==='WORK_PRODUCT_RECORDED'&&e.sequence<=obj.event_sequence).map(e=>e.object_id));objects.filter(o=>owned.has(o.id)&&o.kind!=='opened_source'&&o.kind!=='role_completion').forEach(o=>links.add(o.id));}
    if(value.span_id)links.add(value.span_id);
    (value.process_node_ids||[]).forEach(id=>links.add('node:'+id));
    if(value.requirement_id)links.add('obligation:'+value.requirement_id);
    if(value.process_node_id)links.add('node:'+value.process_node_id);
    if(obj?.kind==='branch'){if(value.from_node_id)links.add('node:'+value.from_node_id);if(value.target)links.add('node:'+value.target);}
    const available=[...links].map(id=>objects.find(o=>o.id===id)).filter(Boolean);
    const title=event?.operation==='GATE_REJECTED'?'Work needs review':event?.after?.text||event?.after?.title||event?.after?.filename||(obj?objectTitle(obj):event?.message||'Recorded work');
    const dialog=detailDialog();
    dialog.innerHTML=`<header><span class="aw-kicker">${event?h(roleName(event.role)):'Linked work product'}</span><button type="button" class="aw-close" data-aw-close aria-label="Close work detail">${icon('close')}</button></header><h2>${h(title)}</h2><div class="aw-inspection-state" role="status" aria-live="polite"></div>${event?`<p class="aw-detail-meta">${h(time(event.timestamp))} · ${h(event.status)} · ${event.worker_kind==='external'?'External worker':event.worker_kind==='kernel'?'Deterministic check':'Reference worker'}</p>`:''}${spans.map(span=>`<section class="aw-source-proof"><h3>Exact supporting passage</h3><blockquote><mark>${h(span.quote)}</mark></blockquote><p>Original source · characters ${span.start}–${span.end}</p><small>A reported source statement, not an established fact.</small></section>`).join('')}${value.why||value.rule_explanation?`<section><h3>Why this exists</h3><p>${h(value.why||value.rule_explanation)}</p></section>`:''}${obj?.kind==='branch'?`<section><h3>Condition and path</h3><p>${h(value.condition||value.label||'No additional condition recorded')}</p><p>${h(({selected:'Active path',inactive:'Inactive alternative',rejected:'Rejected by the recorded authority',unresolved:'Unresolved path'})[value.state]||'Path state not established')}</p></section>`:''}${value.evidence_class?`<section><h3>Evidence state</h3><p>${h(value.evidence_class)}${value.mandatory_now?' · needed before proceeding':' · not requested at this step'}</p></section>`:''}${event?.gate?`<section class="aw-gate-proof"><h3>${event.gate.accepted?'Gate accepted':'Gate rejected'}</h3><p>${h(event.gate.reason)}</p></section>`:''}${value.coverage_contract&&value.coverage&&Object.keys(value.coverage).length?`<section class="aw-completion-coverage"><h3>Completed work checked</h3><dl>${Object.entries(value.coverage).map(([key,count])=>`<div><dt>${h(({process_nodes:'Process steps',branches:'Branches',obligations:'Evidence requirements',document_requirements:'Document requirements',process_requirement_links:'Process links',source_assertions:'Source statements'})[key]||'Checked items')}</dt><dd>${h(count)}</dd></div>`).join('')}</dl><p>The complete roster matches the saved claim. This does not certify the truth of a source statement.</p></section>`:''}${available.length?`<section><h3>Connected work</h3>${available.map(o=>`<button type="button" class="aw-related" data-aw-object="${h(o.id)}"><span>${h(objectTitle(o))}</span>${icon('arrow')}</button>`).join('')}</section>`:''}${obj?.kind==='opened_source'?`<section><h3>Read scope</h3><p>${h(value.extraction)} · ${value.complete?'complete bounded extraction':'limited extraction; no visual interpretation claimed'}</p><blockquote>${h(value.text?.slice(0,3000)||'No readable text was extracted from this source.')}</blockquote></section>`:''}<details class="aw-technical"><summary>Technical details</summary><pre>${h(JSON.stringify({event,object:obj||null},null,2))}</pre></details>`;
    if(!dialog.open)dialog.showModal();refreshInspectionContext();
  }
  async function showWorkforce(){
    state.workforce=true;state.workforceKey=null;document.getElementById('awWorkforceButton')?.setAttribute('aria-pressed','true');
    let view=document.getElementById('awWorkforce');if(!view){view=document.createElement('section');view.id='awWorkforce';view.className='aw-workforce';view.setAttribute('aria-label','AI workforce');document.getElementById('claimsWorkspace').append(view);}
    view.hidden=false;view.innerHTML='<p class="aw-muted" role="status">Loading recorded work…</p>';
    await refreshWorkforce();
  }
  function closeWorkforce(){state.workforce=false;const view=document.getElementById('awWorkforce');if(view)view.hidden=true;document.getElementById('awWorkforceButton')?.setAttribute('aria-pressed','false');}
  async function refreshWorkforce(){
    const view=document.getElementById('awWorkforce');if(!state.workforce||!view)return;
    try{
      const data=await request('/workforce');
      const active=data.runs.filter(r=>['queued','running'].includes(r.status)),blocked=data.runs.filter(r=>['blocked','unconfirmed','interrupted'].includes(r.status)||r.currentness==='unconfirmed');
      const key=JSON.stringify(data);if(state.workforceKey===key)return;state.workforceKey=key;
      const focusedClaim=view.contains(document.activeElement)?document.activeElement?.dataset?.awClaim:null;const scroll=view.scrollTop;
      view.innerHTML=`<header class="aw-workforce-heading"><div><span class="aw-kicker">CasePath</span><h1>AI workforce</h1><p>Six roles. One source-grounded record of the work.</p></div><button class="aw-text-button" type="button" data-aw-back>Back to claims</button></header><div class="aw-workforce-stats"><span><strong>${active.length}</strong> active or queued</span><span><strong>${blocked.length}</strong> need review</span><span><strong>${data.runs.filter(r=>r.status==='completed').length}</strong> latest completed reviews</span></div><div class="aw-team">${data.roles.map(role=>{const relevant=data.runs.filter(r=>r.roles.find(x=>x.id===role.id)?.status==='working'),complete=data.runs.filter(r=>r.roles.find(x=>x.id===role.id)?.status==='completed');return `<section><h2>${h(role.label)}</h2><p>${relevant.length?`${relevant.length} claim in progress`:'No work running'}</p><span>${complete.length} latest recorded completions</span></section>`;}).join('')}</div>${data.coverage?.has_more?'<p class="aw-stale">This is a partial work roster. Open a claim for its complete current work record.</p>':''}<h2 class="aw-runs-heading">Latest work per claim</h2>${data.runs.length?`<div class="aw-runs">${data.runs.map(r=>`<button type="button" data-aw-claim="${h(r.claim_id)}"><span><strong>${h(r.subject)}</strong><small>${h(r.current_role?.label||'Six-role review')} · ${r.completed_roles} of 6 stages completed</small></span><span data-status="${currentTone(r)}">${h(currentLabel(r))}</span>${icon('arrow')}</button>`).join('')}</div>`:'<div class="aw-empty"><h3>No work has been run yet</h3><p>Open a claim and start a team review. This view will show only the work that actually executes.</p></div>'}`;
      view.scrollTop=scroll;if(focusedClaim)view.querySelector(`[data-aw-claim="${CSS.escape(focusedClaim)}"]`)?.focus({preventScroll:true});
    }catch(e){view.innerHTML=`<p class="aw-stale">${h(e.message)}</p><button type="button" class="aw-text-button" data-aw-back>Return to claims</button>`;}
  }
  function updateQueue(runs){
    const latest=new Map();for(const run of runs)if(!latest.has(run.claim_id))latest.set(run.claim_id,run);
    document.querySelectorAll('tr[data-claim-id]').forEach(row=>{
      const run=latest.get(row.dataset.claimId);if(!run)return;
      const cell=row.querySelector('.cp-state-cell')||row.querySelector('td:nth-child(2)');if(!cell)return;
      let el=cell.querySelector('.aw-row-work');if(!el){el=document.createElement('small');el.className='aw-row-work';cell.append(el);}
      const text=run.currentness==='historical'?`Previous review · ${run.completed_roles} of 6 roles completed`:run.currentness==='unconfirmed'?'Saved review · current state unconfirmed':run.current_role?`${run.current_role.label} · ${label(run.current_role.status)}`:run.status==='completed'?`Review complete · ${run.completed_roles} of 6 roles`:`${label(run.status)} · ${run.completed_roles} of 6 stages completed`;
      if(el.textContent!==text)el.textContent=text;
    });
  }
  async function poll(){
    if(state.fetching||document.hidden)return;
    state.fetching=true;
    try{
      mount();
      if(state.workforce)await refreshWorkforce();
      const all=await request('/workforce');updateQueue(all.runs);
      const claim=state.claim;if(!claim)return;
      let latest=all.runs.find(r=>r.claim_id===claim);
      if(!latest&&all.coverage?.has_more){const scoped=await request(`/claims/${encodeURIComponent(claim)}/runs`);latest=scoped.runs[0];}
      if(!latest){state.summary=null;state.run=null;state.renderKey=null;renderClaim();return;}
      const run=await request(`/claims/${encodeURIComponent(claim)}/runs/${encodeURIComponent(latest.run_id)}`);
      if(claim!==state.claim)return;
      if(state.summary?.run_id!==latest.run_id)state.events=[];
      state.run=run;state.summary=run.summary;refreshInspectionContext();
      let after=state.events.at(-1)?.sequence||0;
      for(let i=0;i<10&&after<run.summary.last_sequence;i++){
        const batch=await request(`/claims/${encodeURIComponent(claim)}/runs/${encodeURIComponent(latest.run_id)}/events?after=${after}&limit=500`);
        if(claim!==state.claim||batch.claim_id!==claim||batch.run_id!==latest.run_id)return;
        for(const event of batch.events.filter(e=>e.sequence<=run.summary.last_sequence)){if(event.sequence!==after+1)throw new Error('The work timeline is incomplete.');state.events.push(event);after=event.sequence;}
        if(!batch.events.length)break;
      }
      renderClaim();
      if(run.summary.status==='completed'&&run.summary.currentness==='current'&&state.forceRefresh!==run.summary.run_id){state.forceRefresh=run.summary.run_id;document.querySelector('[data-refresh-claim]')?.click();}
    }catch(e){refreshInspectionContext(true);report(e.name==='AbortError'?'Work status is temporarily unavailable. Saved work has not been replaced.':e.message);}
    finally{state.fetching=false;}
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest('button');if(!button)return;
    if(button.id==='cwStart'&&state.cap){event.preventDefault();event.stopImmediatePropagation();void startWork();return;}
    if(button.hasAttribute('data-aw-resume'))void resumeWork();
    if(button.hasAttribute('data-aw-start'))void startWork();
    if(button.hasAttribute('data-aw-retry'))void startWork(true);
    if(button.hasAttribute('data-aw-timeline'))openTimeline();
    if(button.dataset.awRole)openTimeline(button.dataset.awRole);
    if(button.dataset.awEvent)inspect(state.events.find(e=>e.sequence===Number(button.dataset.awEvent)));
    if(button.dataset.awObject)inspect(null,button.dataset.awObject);
    if(button.hasAttribute('data-aw-close'))button.closest('dialog')?.close();
    if(button.hasAttribute('data-aw-back'))closeWorkforce();
    if(button.dataset.awClaim){closeWorkforce();location.hash=new URLSearchParams({claim:button.dataset.awClaim,view:'activity'});}
  },true);
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&state.workforce){closeWorkforce();e.preventDefault();e.stopImmediatePropagation();}},true);
  async function boot(){
    try{state.cap=await request('/capabilities');}catch(_){return;}
    const observer=new MutationObserver(()=>{if(state.visible){state.visible=false;requestAnimationFrame(()=>{state.visible=true;mount();});}});
    observer.observe(document.body,{childList:true,subtree:true});
    mount();void poll();state.timer=setInterval(poll,1500);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)void poll();});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else void boot();
})();
