/* Agent-work projections for the existing CasePath workspace.
   No provider code, claim truth, artificial timing or invented work lives here. */
(function () {
  'use strict';
  const ROOT='/api/agent-work/v1', CONTRACT='casepath.agent-work/1.0.0';
  const h=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const icon=(name)=>`<svg class="aw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${({work:'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z',close:'m6 6 12 12M6 18 18 6',arrow:'M4 12h15m-5-5 5 5-5 5',source:'M14 3H5v18h14V8l-5-5Zm0 0v5h5M8 12h8M8 16h6',check:'m5 12 4 4L19 6',link:'m9 15 6-6M7 17l-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M17 7l1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0',plan:'M4 6h5m6 0h5M9 6a3 3 0 0 1 3 3v6a3 3 0 0 0 3 3h5M4 18h5',process:'M5 3v5m0 0h14v8m-14-8v13m11-5h6M3 3h4M3 21h4',evidence:'M5 3h14v18H5zM8 8l2 2 4-4M8 14h8M8 18h6',audit:'M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6zM9 12l2 2 4-4',pulse:'M3 12h4l2-5 4 10 2-5h6'})[name]||'M5 12h14'}"/></svg>`;
  const state={cap:null,claim:null,run:null,events:[],summary:null,assessment:null,assessmentLoading:false,busy:false,visible:true,timer:null,fetching:false,workforce:false,forceRefresh:null,renderKey:null,workforceKey:null,messages:new Map(),timelineExpanded:false,timelineOpen:false,repoll:false,stream:null,streamRun:null,streamFailed:null,lastRosterAt:0,spotlit:null,revealCount:0,revealTimer:null};
  const time=t=>t?new Intl.DateTimeFormat(undefined,{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date(t)):'—';
  const label=s=>({not_started:'Not started',working:'Working',completed:'Completed',blocked:'Needs review',unconfirmed:'Outcome unconfirmed',queued:'Queued',running:'Processing',interrupted:'Interrupted',failed:'Needs review'})[s]||s;
  const roleName=r=>state.cap?.roles.find(x=>x.id===r)?.label||'CasePath';
  const currentLabel=r=>r.currentness==='historical'?'Previous review':r.currentness==='unconfirmed'?'Check saved state':label(r.status);
  const currentTone=r=>['historical','unconfirmed'].includes(r.currentness)?'unconfirmed':statusClass(r.status);
  const statusClass=s=>['completed','working','blocked','unconfirmed'].includes(s)?s:'quiet';
  const ROLE_ICON={canonical_facts:'source',orchestrator_plan:'plan',document_source_integrity:'link',process_decision_mapping:'process',evidence_checklist:'evidence',final_claim_brief_audit:'audit'};
  const MILESTONE_OPERATIONS=new Set(['RUN_STARTED','AGENT_STARTED','AGENT_COMPLETED','AGENT_BLOCKED','SOURCE_SPAN_SELECTED','ASSERTION_PROPOSED','HANDOFF_COMPLETED','AUTHORITY_CONFIRMED','CLAIM_REPLANNED','ACTION_PROPOSED','GATE_REJECTED','RUN_COMPLETED','RUN_BLOCKED']);
  const roleIcon=id=>icon(ROLE_ICON[id]||'work');
  const eventsFor=operation=>state.events.filter(e=>e.operation===operation);
  const latestVisibleEvent=()=>[...state.events].reverse().find(e=>!HIDDEN_OPERATIONS.has(e.operation));
  const modelLabel=()=>{const row=[...state.events].reverse().find(e=>e.operation==='PROVIDER_RESPONSE_RECEIVED'&&e.after?.response_model);if(!row)return null;const raw=row.after.response_model.split('/').at(-1).replace(':free','').replaceAll('-',' ');return raw.replace(/\b\w/g,c=>c.toUpperCase());};
  function roleOutcome(role){
    if(!role)return 'Waiting';
    if(role.status==='working')return role.last_operation||'Working through recorded tools';
    if(role.status==='blocked')return role.last_operation||'Needs review';
    if(role.status==='not_started')return 'Waiting for checked handoff';
    const c=role.coverage||{},objects=state.run?.objects||[];
    if(role.id==='canonical_facts')return `${objects.filter(o=>o.kind==='assertion').length} exact source statement${objects.filter(o=>o.kind==='assertion').length===1?'':'s'}`;
    if(role.id==='orchestrator_plan')return eventsFor('HANDOFF_COMPLETED').length?`${eventsFor('HANDOFF_COMPLETED').length} checked handoffs`:'Review sequence set';
    if(role.id==='document_source_integrity')return `${c.source_assertions||0} statement${c.source_assertions===1?'':'s'} rechecked`;
    if(role.id==='process_decision_mapping')return `${c.process_nodes||0} steps · ${c.branches||0} paths`;
    if(role.id==='evidence_checklist')return `${c.obligations||0} needs · ${c.process_requirement_links||0} links`;
    return role.status==='completed'?'Readiness and next action checked':label(role.status);
  }

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
    const nav=root.querySelector('.cp-top-links');
    if(nav){
      let button=document.getElementById('awWorkforceButton');
      if(!button){button=document.createElement('button');button.id='awWorkforceButton';button.type='button';button.innerHTML=icon('work')+'<span>Saved reviews</span>';button.setAttribute('aria-label','Saved reviews');button.setAttribute('aria-pressed','false');nav.append(button);}
      if(!button.dataset.agentWorkEntry){button.dataset.agentWorkEntry='true';button.addEventListener('click',event=>{event.preventDefault();showWorkforce();});}
    }
    const claim=getClaim();
    if(claim!==state.claim){closeStream();clearTimeout(state.revealTimer);state.revealTimer=null;document.getElementById('awInspector')?.close();state.inspection=null;state.claim=claim;state.run=null;state.events=[];state.summary=null;state.assessment=null;state.assessmentLoading=false;state.renderKey=null;state.timelineExpanded=false;state.timelineOpen=false;state.repoll=Boolean(claim);state.spotlit=null;state.revealCount=0;}
    if(!claim)return;
    const activity=root.querySelector('#cpReviewCard');if(!activity)return;
    let section=document.getElementById('awClaimWork');
    if(!section){
      section=document.createElement('section');section.id='awClaimWork';section.className='aw-work-strip';section.setAttribute('aria-label','Agent review');
      state.renderKey=null;
    }
    if(section.parentElement!==activity)activity.querySelector('h2')?.after(section);
    if(!state.assessment&&activity.dataset.assessment){try{state.assessment=JSON.parse(activity.dataset.assessment);state.assessmentLoading=false;}catch(_){}}
    const start=document.getElementById('cwStart');
    if(start&&!start.dataset.agentWorkEntry){start.dataset.agentWorkEntry='true';start.textContent='Review claim';}
    renderClaim();
  }
  function compactSummary(summary){
    const roles=summary?.roles||state.cap?.roles.map(r=>({...r,status:'not_started'}))||[];
    if(!summary)return `<header class="aw-console-head"><div><span class="aw-kicker">Agent review</span><h2>Ready to review the source packet</h2><p>The review will check the source statements, handling path, evidence needs and next step.</p></div><span class="aw-console-state" data-status="quiet">Ready</span></header>`;
    const active=summary.current_role,complete=summary.status==='completed',blocked=summary.status==='blocked'||summary.status==='unconfirmed';
    const stages={canonical_facts:'Reading source statements',orchestrator_plan:'Checking the review plan',document_source_integrity:'Checking source links',process_decision_mapping:'Mapping the handling path',evidence_checklist:'Checking evidence needs',final_claim_brief_audit:'Checking the next step'};
    const heading=complete?'Review execution recorded':blocked?`Review paused while ${h((stages[active?.id]||active?.label||'a checked gate').toLowerCase())}`:active?h(stages[active.id]||`${active.label} is working on the claim`):summary.status==='queued'?'Review is queued':h(label(summary.status));
    const latest=latestVisibleEvent();
    const description=complete?'The recorded execution can be inspected below. The claim may still need evidence before a decision.':blocked?h(summary.last_message):latest?h(latest.message):'The review is moving through the saved checks.';
    return `<header class="aw-console-head"><div><span class="aw-kicker">Review execution</span><h2>${heading}</h2><p>${description}</p></div><span class="aw-console-state" data-status="${currentTone(summary)}"><strong>${complete?'Saved':`${summary.completed_roles}/6`}</strong>${complete?'Recorded':blocked?'Needs review':'In progress'}</span></header>`;
  }
  function roleTrack(summary){
    if(summary&&!summary.roles)return '<div class="aw-agent-flow aw-agent-flow-loading" aria-live="polite"><span>Loading recorded specialist outputs…</span></div>';
    const roles=summary?.roles||state.cap?.roles.map(r=>({...r,status:'not_started',coverage:{}}))||[];
    const handoffs=eventsFor('HANDOFF_COMPLETED');
    return `<div class="aw-agent-flow" role="group" aria-label="Review team and checked handoffs">${roles.map((role,index)=>{
      const next=roles[index+1],handoff=next?handoffs.find(e=>e.role===next.id):null;
      const external=role.id==='canonical_facts'&&summary?.facts_worker==='external_facts';
      const agent=`<button type="button" class="aw-agent" data-aw-role="${h(role.id)}" data-status="${statusClass(role.status)}" ${role.status==='not_started'?'disabled':''}><span class="aw-agent-mark">${role.status==='completed'?icon('check'):roleIcon(role.id)}</span><span class="aw-agent-copy"><strong>${h(role.label)}</strong><small>${h(roleOutcome(role))}</small>${external?`<em>${h(modelLabel()||'External model')}</em>`:''}</span></button>`;
      const bridge=next?handoff?`<button type="button" class="aw-handoff" data-aw-event="${handoff.sequence}" aria-label="Inspect checked handoff from ${h(role.label)} to ${h(next.label)}">${icon('arrow')}<span>Handoff</span></button>`:`<span class="aw-handoff aw-handoff-pending" aria-hidden="true">${icon('arrow')}</span>`:'';
      return agent+bridge;
    }).join('')}</div>`;
  }
  function liveSignal(summary){
    if(!summary)return '<div class="aw-live-signal aw-live-ready"><span class="aw-live-mark">'+icon('work')+'</span><div><small>Review team</small><strong>Source-grounded collaboration, on demand</strong><p>No work is shown until it actually executes.</p></div></div>';
    const latest=latestVisibleEvent(),complete=summary.status==='completed';
    if(complete)return '';
    const role=summary.current_role;
    return `<div class="aw-live-signal" data-live="${summary.status==='running'}"><span class="aw-live-mark">${icon('pulse')}</span><div><small>${summary.status==='running'?'Working now':h(label(summary.status))}</small><strong>${h(role?.label||'Review team')}</strong><p>${h(latest?.message||summary.last_message||'Waiting for the next persisted event')}</p></div><span class="aw-live-time">${latest?h(time(latest.timestamp)):''}</span></div>`;
  }
  function narrativeEvent(event){
    const span=event.sources?.[0];
    if(event.operation==='RUN_QUEUED'){
      const body=document.querySelector('#cwSourceContent .cw-message')?.textContent||'';
      const paragraph=body.split(/\n\s*\n/).find((part,index)=>index>0&&part.trim().length>20)||body;
      const clause=paragraph.split(/[;\n]/).map(part=>part.trim()).find(part=>part.length>20)||'';
      const quote=(clause.includes(':')?clause.split(':').slice(1).join(':').trim():clause).slice(0,150);
      return quote?{text:`Customer: “${quote}”`,quote,message:true}:null;
    }
    if(event.operation==='SOURCE_SPAN_SELECTED'&&span?.extraction==='message_body'&&span.quote){
      const quote=span.quote.includes(':')?span.quote.split(':').slice(1).join(':').trim():span.quote.trim();
      const shown=quote.replace(/[;.!?]+$/,'');
      return {text:`Customer: “${shown.slice(0,150)}${shown.length>150?'…':''}”`,quote,message:true};
    }
    return null;
  }
  function assessmentStages(assessment){
    if(!assessment)return [];
    const stages=[],opened=new Set(state.events.filter(event=>event.operation==='SOURCE_OPENED').map(event=>event.object_id));
    const labels={health_effects:'Health effects',mold:'Mould',family_home:'Separate service',extension_relevant:'Extension',reference_rate:'Reference-rate reason',specialist_needed:'Technical inspection',arrears:'Arrears',retaliation_screen:'Good-faith concern',heating:'Heating',deposit_considered:'Rent deposit',renovation:'Renovation',termination_received:'Termination received',claim_received:'Increase received'};
    for(const item of assessment.noticed||[]){
      if(item.source_kind!=='pdf_text'||!item.text.includes(': ')||!opened.has(item.source_id))continue;
      const quote=item.text.split(': ').at(-1),file=assessment.attachment_pages?.find(page=>page.artifact_id===item.source_id)?.file_name||'';
      const name=/spouse|wife|husband/i.test(file)?'Spouse notice':'Tenant notice';
      stages.push({text:`${name}, page ${item.page||1}: end date ${quote.replace(/^(\d{1,2})\.\s*Juni$/i,'$1 June').replace(/^(\d{1,2})\.\s*Juli$/i,'$1 July')}`,sourceId:item.source_id,quote});
    }
    for(const conflict of assessment.conflicts||[]){
      if(!conflict.sources.every(source=>opened.has(source.artifact_id)))continue;
      stages.push({text:`The notices give different end dates: ${conflict.sources.map(source=>source.quote).join(' and ')}`,sourceId:conflict.sources[0].artifact_id,quote:conflict.sources[0].quote});
    }
    const order=['termination_received','claim_received','health_effects','mold','family_home','reference_rate','extension_relevant','arrears','retaliation_screen','heating','specialist_needed','deposit_considered','renovation'];
    for(const [flag,value] of Object.entries(assessment.conditions||{}).sort(([left],[right])=>order.indexOf(left)-order.indexOf(right))){
      const quote=value.quote||value.candidate_quote;
      stages.push({flag,...(quote?{text:`${labels[flag]||flag.replaceAll('_',' ')}: ${value.verdict} — “${quote}”`,quote,message:true}:{})});
    }
    return stages;
  }
  function narrativeLines(events){
    const lines=[],seen=new Set();
    const add=(event,line)=>{if(line&&!seen.has(line.text)){seen.add(line.text);lines.push({event,line});}};
    for(const event of events){
      if(event.operation==='RUN_QUEUED'||event.operation==='SOURCE_SPAN_SELECTED')add(event,narrativeEvent(event));
      if(event.operation==='AUTHORITY_CONFIRMED')for(const stage of assessmentStages(state.assessment).slice(0,state.revealCount))if(stage.text)add(event,stage);
    }
    return lines;
  }
  function lineButton(event,line){
    const target=line.message?'data-aw-message':line.sourceId?`data-aw-source-id="${h(line.sourceId)}"`:`data-aw-source="${event.sequence}"`;
    const anchor=line.quote?` data-aw-quote="${h(line.quote)}"`:'';
    const quoted=state.assessment?.language?.startsWith('de')&&line.text.match(/^(.*?)“([^”]+)”(.*)$/);
    const words=quoted?`${h(quoted[1])}“<span lang="de">${h(quoted[2])}</span>”${h(quoted[3])}`:h(line.text);
    return `<a href="#" ${target}${anchor}>${words}</a>`;
  }
  function syncLivePath(){
    const working=['queued','running'].includes(state.summary?.status);
    const path=document.querySelector('.cp-a-path');if(!path)return;
    path.classList.toggle('aw-path-settling',working);
    if(!working){path.querySelectorAll('[data-aw-settled]').forEach(node=>delete node.dataset.awSettled);return;}
    const nodes=new Set(state.events.filter(event=>event.operation==='PROCESS_NODE_PROPOSED').map(event=>String(event.object_id||'').replace(/^node:/,'')));
    const flags=new Set(assessmentStages(state.assessment).slice(0,state.revealCount).map(stage=>stage.flag).filter(Boolean));
    path.querySelectorAll('ol>li[data-path-state]').forEach(row=>row.dataset.awSettled=String(nodes.has(row.querySelector('[data-canvas-node]')?.dataset.canvasNode)));
    path.querySelectorAll('[data-condition-flag]').forEach(row=>row.dataset.awSettled=String(flags.has(row.dataset.conditionFlag)));
    path.querySelectorAll('.cp-a-condition[data-condition-flag]').forEach(row=>row.dataset.awSettled=String(flags.has(row.dataset.conditionFlag)));
  }
  function renderClaim(){
    const host=document.getElementById('awClaimWork');if(!host)return;
    const summary=state.summary,hasStart=Boolean(document.getElementById('cwStart'));
    const stages=assessmentStages(state.assessment),working=['queued','running'].includes(summary?.status);
    if(!working&&state.revealTimer){clearTimeout(state.revealTimer);state.revealTimer=null;}
    if(summary?.status==='completed')state.revealCount=stages.length;
    if(working&&state.assessment&&state.events.some(event=>event.operation==='AUTHORITY_CONFIRMED')&&state.revealCount<stages.length&&!state.revealTimer){
      state.revealTimer=setTimeout(()=>{state.revealTimer=null;state.revealCount++;state.renderKey=null;renderClaim();},160);
    }
    syncLivePath();
    host.hidden=Boolean(state.assessment&&summary?.status==='completed')||!summary&&!state.busy&&!pendingRequest();
    const key=JSON.stringify([summary?.run_id,summary?.last_sequence,summary?.status,state.busy,hasStart,state.events.length,state.messages.get(state.claim),state.assessment?.assessment_sha256,state.revealCount]);
    if(state.renderKey===key)return;state.renderKey=key;
    const start=document.getElementById('cwStart');
    if(start){const waiting=['queued','running','interrupted'].includes(summary?.status);start.disabled=state.busy||waiting&&!summary?.run_id;start.textContent=waiting?'Stop':'Review claim';}
    if(host.hidden){host.innerHTML='';renderTimeline();return;}
    const pending=pendingRequest(),stopping=state.events.some(event=>event.operation==='RUN_CANCEL_REQUESTED')&&working;
    const cancelled=summary?.status==='cancelled';
    const lines=narrativeLines(state.events);
    const detail=cancelled?'Review stopped. Saved findings remain in Timeline.':stopping?'Stopping after the current source check…':state.messages.get(state.claim)||(!lines.length?'Reading the claim…':'');
    host.innerHTML=`<div class="aw-review-progress" data-status="${h(summary?.status||'opening')}">${detail?`<p role="status">${h(detail)}</p>`:''}<ol class="aw-narrative-lines">${lines.slice(-8).map(({event,line})=>`<li>${lineButton(event,line)}</li>`).join('')}</ol>${summary?.recovery?.can_resume?'<a href="#" data-aw-resume>Resume saved review</a>':''}${pending&&!state.busy?'<a href="#" data-aw-retry>Check the same request</a>':''}<p class="aw-message" id="awRequestStatus" role="status" aria-live="polite"></p></div>`;
    if(working&&lines.length){const latest=lines.at(-1),spotlightKey=latest.event.sequence+':'+latest.line.text;if(state.spotlit!==spotlightKey){state.spotlit=spotlightKey;spotlight(latest.line,false);}}
    renderTimeline();
  }
  function renderTimeline(){
    const panel=document.getElementById('cpPanel-activity');if(!panel||!state.run)return;
    let host=document.getElementById('awTimeline');if(!host){host=document.createElement('div');host.id='awTimeline';panel.append(host);}
    const lines=narrativeLines(state.events);
    const key=state.summary?.run_id+':'+state.events.length+':'+(state.assessment?.assessment_sha256||'')+':'+state.revealCount;if(host.dataset.version===key)return;host.dataset.version=key;
    host.innerHTML=`<ol class="aw-narrative-lines">${lines.map(({event,line})=>`<li><time datetime="${h(event.timestamp)}">${h(time(event.timestamp))}</time>${lineButton(event,line)}</li>`).join('')}</ol>${!lines.length?'<p>Source reads will appear here as they are saved.</p>':''}`;
  }
  function renderProcess(){}
  function openTimeline(){const panel=document.getElementById('cpPanel-activity');if(!panel)return;panel.open=true;panel.scrollIntoView({block:'start'});panel.querySelector('summary')?.focus({preventScroll:true});}
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
      if(state.claim===claim){clearTimeout(state.revealTimer);state.revealTimer=null;state.revealCount=0;state.spotlit=null;state.run=result;state.summary=result.summary;state.events=[];state.renderKey=null;renderClaim();openStream(claim,result.summary.run_id);}
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
  async function cancelWork(){
    if(state.busy||!state.claim||!state.summary?.run_id)return;
    const claim=state.claim,run=state.summary.run_id;
    state.busy=true;report('Stopping after the current source check…');state.renderKey=null;renderClaim();
    try{
      const response=await request(`/claims/${encodeURIComponent(claim)}/runs/${encodeURIComponent(run)}/cancel`,{method:'POST',headers:{'X-CasePath-Agent-Work':'1'}});
      if(state.claim===claim&&state.summary?.run_id===run){state.run=response;state.summary=response.summary;state.messages.delete(claim);}
    }catch(error){if(state.claim===claim)report(error.message);}
    finally{state.busy=false;state.renderKey=null;renderClaim();void poll();}
  }
  function spotlight(line,open){
    const rail=document.querySelector('.cp-source-rail');if(!rail)return;
    const target=line.message||!line.sourceId?rail.querySelector('[data-packet-message]'):rail.querySelector(`[data-artifact-id="${CSS.escape(line.sourceId)}"]`);
    if(!target)return;
    rail.querySelectorAll('.aw-source-focused').forEach(button=>button.classList.remove('aw-source-focused'));
    target.classList.add('aw-source-focused');target.scrollIntoView({block:'center',behavior:'instant'});
    if(target.hasAttribute('data-packet-message')){
      if(open)target.click();
      const message=document.querySelector('#cwSourceContent .cw-message'),text=message?.textContent||'',quote=line.quote||'';
      const start=quote?text.indexOf(quote):-1;
      if(start>=0){message.replaceChildren(document.createTextNode(text.slice(0,start)),Object.assign(document.createElement('mark'),{textContent:quote}),document.createTextNode(text.slice(start+quote.length)));if(open)message.querySelector('mark')?.scrollIntoView({block:'center',behavior:'instant'});}
      return;
    }
    target.classList.remove('aw-source-flash');void target.offsetWidth;target.classList.add('aw-source-flash');
    if(open){if(line.quote)target.dataset.sourceQuote=line.quote;target.click();if(line.quote)delete target.dataset.sourceQuote;}
  }
  function focusSource(sequence){
    const event=state.events.find(row=>row.sequence===sequence);if(!event)return;
    const sourceId=event.sources?.[0]?.source_id||event.after?.source_id||event.object_id;
    spotlight({sourceId,quote:event.sources?.[0]?.quote,message:event.sources?.[0]?.extraction==='message_body'},true);
  }
  function focusSourceId(sourceId,quote){spotlight({sourceId,quote},true);}
  const HIDDEN_OPERATIONS=new Set(['WORK_PRODUCT_RECORDED','RUN_QUEUED','PROCESS_INSPECTED']);
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
    let view=document.getElementById('awWorkforce');if(!view){view=document.createElement('section');view.id='awWorkforce';view.className='aw-workforce';view.setAttribute('aria-label','Review operations');document.getElementById('claimsWorkspace').append(view);}
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
      const focusedClaim=view.contains(document.activeElement)?document.activeElement?.dataset?.awClaim:null,scroll=view.scrollTop;
      const runs=data.runs.map(r=>`<button type="button" class="aw-run-row" data-aw-claim="${h(r.claim_id)}"><span class="aw-run-main"><strong>${h(r.subject)}</strong><small>${h(r.facts_worker==='external_facts'?'External review':'Deterministic review')}</small></span><span class="aw-run-state" data-status="${statusClass(r.status)}">${h(label(r.status))}</span>${icon('arrow')}</button>`).join('');
      view.innerHTML=`<header class="aw-workforce-heading"><div><span class="aw-kicker">Saved reviews</span><h1>Review operations</h1></div><button class="aw-text-button" type="button" data-aw-back>Back to claims</button></header><div class="aw-workforce-stats"><span><strong>${active.length}</strong> active</span><span><strong>${blocked.length}</strong> need review</span><span><strong>${data.runs.filter(r=>r.status==='completed').length}</strong> completed</span><span><strong>${data.coverage?.total_claims||data.runs.length}</strong> claims with recorded work</span></div>${data.coverage?.has_more?'<p class="aw-stale">Open a claim to inspect its full work history.</p>':''}<div class="aw-runs-header"><h2>Latest review per claim</h2></div>${data.runs.length?`<div class="aw-runs">${runs}</div>`:'<div class="aw-empty"><h3>No review has run yet</h3><p>Open a claim to start a review.</p></div>'}`;
      view.scrollTop=scroll;if(focusedClaim)view.querySelector(`[data-aw-claim="${CSS.escape(focusedClaim)}"]`)?.focus({preventScroll:true});
    }catch(e){view.innerHTML=`<p class="aw-stale">${h(e.message)}</p><button type="button" class="aw-text-button" data-aw-back>Return to claims</button>`;}
  }
  function updateQueue(){}
  function closeStream(){state.stream?.close();state.stream=null;state.streamRun=null;}
  function openStream(claim,runId){
    if(state.streamRun===runId||state.streamFailed===runId||!window.EventSource)return;
    closeStream();
    const after=state.events.at(-1)?.sequence||0;
    const stream=new EventSource(`${ROOT}/claims/${encodeURIComponent(claim)}/runs/${encodeURIComponent(runId)}/stream?after=${after}`);
    state.stream=stream;state.streamRun=runId;
    stream.addEventListener('work',message=>{
      if(state.claim!==claim||state.streamRun!==runId)return;
      const event=JSON.parse(message.data),previous=state.events.at(-1)?.sequence||0;
      if(event.sequence<=previous)return;
      if(event.sequence!==previous+1){closeStream();state.streamFailed=runId;void poll();return;}
      state.events.push(event);
      if(state.summary){state.summary.last_sequence=event.sequence;state.summary.last_message=event.message;}
      renderClaim();
      if(event.operation==='AUTHORITY_CONFIRMED'&&!state.assessment&&!state.assessmentLoading){state.assessmentLoading=true;window.dispatchEvent(new Event('casepath:refresh-claim'));}
      if(['AGENT_STARTED','AGENT_COMPLETED','AGENT_BLOCKED','RUN_COMPLETED','RUN_BLOCKED','RUN_FAILED'].includes(event.operation))void poll();
    });
    stream.addEventListener('done',()=>{closeStream();void poll();});
    stream.onerror=()=>{closeStream();state.streamFailed=runId;void poll();};
  }
  async function poll(){
    if(state.fetching||document.hidden)return;
    state.fetching=true;
    try{
      mount();
      if(state.workforce)await refreshWorkforce();
      const claim=state.claim;
      if(!claim){
        if(!state.workforce&&Date.now()-state.lastRosterAt>30000){const all=await request('/workforce');updateQueue(all.runs);state.lastRosterAt=Date.now();}
        return;
      }
      const scoped=await request(`/claims/${encodeURIComponent(claim)}/runs`);
      if(claim!==state.claim)return;
      const latest=scoped.runs[0];
      if(!latest){state.summary=null;state.run=null;state.renderKey=null;renderClaim();return;}
      if(state.streamFailed!==latest.run_id)state.streamFailed=null;
      const run=await request(`/claims/${encodeURIComponent(claim)}/runs/${encodeURIComponent(latest.run_id)}`);
      if(claim!==state.claim)return;
      if(state.summary?.run_id!==latest.run_id){state.events=[];state.revealCount=0;state.spotlit=null;}
      state.run=run;state.summary=run.summary;refreshInspectionContext();
      let after=state.events.at(-1)?.sequence||0;
      for(let i=0;i<10&&after<run.summary.last_sequence;i++){
        const batch=await request(`/claims/${encodeURIComponent(claim)}/runs/${encodeURIComponent(latest.run_id)}/events?after=${after}&limit=500`);
        if(claim!==state.claim||batch.claim_id!==claim||batch.run_id!==latest.run_id)return;
        for(const event of batch.events.filter(e=>e.sequence<=run.summary.last_sequence)){if(event.sequence!==after+1)throw new Error('The work timeline is incomplete.');state.events.push(event);after=event.sequence;}
        if(!batch.events.length)break;
      }
      renderClaim();
      if(state.events.some(event=>event.operation==='AUTHORITY_CONFIRMED')&&!state.assessment&&!state.assessmentLoading){state.assessmentLoading=true;window.dispatchEvent(new Event('casepath:refresh-claim'));}
      if(['queued','running'].includes(run.summary.status))openStream(claim,latest.run_id);
      else closeStream();
      if(run.summary.status==='completed'&&run.summary.currentness==='current'&&state.forceRefresh!==run.summary.run_id){state.forceRefresh=run.summary.run_id;window.dispatchEvent(new Event('casepath:refresh-claim'));}
    }catch(e){refreshInspectionContext(true);report(e.name==='AbortError'?'Work status is temporarily unavailable. Saved work has not been replaced.':e.message);}
    finally{state.fetching=false;if(state.repoll){state.repoll=false;queueMicrotask(()=>void poll());}}
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest('button,a[data-aw-source],a[data-aw-source-id],a[data-aw-message],a[data-aw-resume],a[data-aw-retry]');if(!button)return;
    if(button.tagName==='A')event.preventDefault();
    if(button.id==='cwStart'&&state.cap){event.preventDefault();event.stopImmediatePropagation();if(['queued','running'].includes(state.summary?.status))void cancelWork();else void startWork();return;}
    if(button.hasAttribute('data-aw-resume'))void resumeWork();
    if(button.hasAttribute('data-aw-start'))void startWork();
    if(button.hasAttribute('data-aw-retry'))void startWork(true);
    if(button.hasAttribute('data-aw-timeline'))openTimeline();
    if(button.hasAttribute('data-aw-cancel'))void cancelWork();
    if(button.hasAttribute('data-aw-source'))focusSource(Number(button.dataset.awSource));
    if(button.hasAttribute('data-aw-source-id'))focusSourceId(button.dataset.awSourceId,button.dataset.awQuote);
    if(button.hasAttribute('data-aw-message'))spotlight({message:true,quote:button.dataset.awQuote},true);
    if(button.hasAttribute('data-aw-need'))document.querySelector('.cp-a-needs')?.scrollIntoView({block:'start'});
    if(button.hasAttribute('data-aw-trace-toggle')){state.timelineExpanded=!state.timelineExpanded;const trace=document.getElementById('awTimeline');if(trace)delete trace.dataset.eventCount;renderTimeline();}
    if(button.dataset.awRole)openTimeline();
    if(button.dataset.awEvent)inspect(state.events.find(e=>e.sequence===Number(button.dataset.awEvent)));
    if(button.dataset.awObject)inspect(null,button.dataset.awObject);
    if(button.hasAttribute('data-aw-close'))button.closest('dialog')?.close();
    if(button.hasAttribute('data-aw-back'))closeWorkforce();
    if(button.dataset.awClaim){closeWorkforce();location.hash=new URLSearchParams({claim:button.dataset.awClaim});}
  },true);
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&state.workforce){closeWorkforce();e.preventDefault();e.stopImmediatePropagation();}},true);
  async function boot(){
    try{state.cap=await request('/capabilities');}catch(_){window.dispatchEvent(new Event('casepath:agent-work-unavailable'));return;}
    const observer=new MutationObserver(()=>{if(state.visible){state.visible=false;requestAnimationFrame(()=>{state.visible=true;mount();});}});
    observer.observe(document.body,{childList:true,subtree:true});
    mount();void poll();state.timer=setInterval(()=>{if(!state.stream)void poll();},1500);
    document.addEventListener('visibilitychange',()=>{if(!document.hidden)void poll();});
    window.dispatchEvent(new Event('casepath:agent-work-ready'));
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else void boot();
})();
