/* A desk of validated saved work. No browser state establishes claim readiness. */
(function(global, factory) {
  const view = factory();
  if (typeof module === 'object' && module.exports) module.exports = view;
  else { global.CasePathDesk = view; view.start(); }
})(typeof globalThis === 'object' ? globalThis : this, function() {
  'use strict';
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const stateNames = {working:'Working',waiting_for_you:'Waiting for you',waiting_for_others:'Waiting for others',paused:'Paused',done:'Done',failed:'Failed',not_started:'Not started',waiting:'Waiting',quiet:'Quiet',unknown:'Not yet checked'};
  const groupNames = {needs_you:'Needs you',working:'Agent working',waiting:'Waiting on others',quiet:'Quiet / unreviewed',closed:'Closed'};
  const stamp = value => value && Number.isFinite(new Date(value).valueOf()) ? new Intl.DateTimeFormat('en-GB',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value)) : '';
  function row(claim) {
    const activity = claim.latest_activity;
    const activityLabel=activity?.type==='RUN_COMPLETED'&&activity.label==='All six roles completed. Claim readiness remains governed by the existing authority.'?'Six review roles finished; findings need handler review.':activity?.label;
    return `<li class="ad-row" data-state="${escape(claim.agent_state)}"><div class="ad-row-heading"><a href="#claim=${encodeURIComponent(claim.claim_id)}" data-desk-claim="${escape(claim.claim_id)}">${escape(claim.claim_id==='clm_f69b1747447bc221' ? 'Family-home termination notices' : typeof window!=='undefined' && window.CasePathPresentation ? window.CasePathPresentation.title(claim.title || claim.subject) : claim.title || claim.subject)}<small class="ad-open">Open claim</small></a><span class="ad-state">${escape(claim.recovery_required ? 'Recovery needed' : stateNames[claim.agent_state] || claim.agent_state?.replaceAll('_',' ') || 'Unknown')}</span></div><p class="ad-ask">${escape(claim.ask || 'No handler ask is recorded.')}</p><div class="ad-row-foot"><span>${escape(claim.decider || claim.accountable || claim.owner || 'Handler unassigned')}${claim.reference ? ' · '+escape(claim.reference) : ''}</span><details class="ad-peek"><summary>What was checked</summary><div class="ad-peek-content"><p>${escape(claim.why || 'No review result is recorded.')}</p><p>${escape(claim.coverage?.note || 'Source coverage is unknown.')}</p>${activity ? `<p><span class="ad-activity-type">${escape(activity.type==='RUN_COMPLETED'?'Agent review finished':activity.type?.replaceAll('_',' ').toLowerCase() || 'Recorded work')}</span> ${escape(activityLabel)}${stamp(activity.timestamp) ? ' · '+escape(stamp(activity.timestamp)) : ''}</p>` : '<p>No agent activity is recorded.</p>'}${claim.draft_status !== 'not_prepared' ? `<p>${claim.draft_status === 'approved_not_sent' ? 'Request approved, not sent.' : 'Draft, not sent.'}</p>` : ''}<div class="ad-peek-sources" data-desk-evidence="${escape(claim.claim_id)}"></div></div></details></div></li>`;
  }
  function peekEvidence(agent, claim) {
    if(agent.claim_id!==claim.claim_id || agent.workspace_revision!==claim.workspace_revision || agent.workspace_state_sha256!==claim.workspace_state_sha256)throw new Error('Saved work changed. Refresh the desk before opening its passages.');
    const sources=claim.recovery_required?[]:(agent.questions?.[0]?.sources||[]).filter(source=>source.artifact_id&&source.quote);
    const html=sources.length?sources.map((source,index)=>`<button type="button" data-desk-source="${index}" data-desk-source-claim="${escape(claim.claim_id)}"><q>${escape(source.quote)}</q><span>${escape(source.file_name||'Original source')}${source.page?` · page ${escape(source.page)}`:''}</span></button>`).join(''):'<p>No exact source passage is attached to this ask. Its process and recorded work are available in the claim.</p>';
    return {sources,html};
  }
  const unreviewed = group => group.claims.filter(claim=>claim.review_started===false).length;
  const countMarkup = group => `<strong>${escape(group.count)}</strong><span>${escape(groupNames[group.id]||group.label)}</span>${group.id==='quiet'&&unreviewed(group)?`<small>${unreviewed(group)} not yet reviewed</small>`:''}`;
  function groups(data, search = '') {
    const term = search.toLocaleLowerCase().trim();
    const filtered = group => group.claims.filter(c => !term || [c.title,c.subject,c.reference,c.owner,c.ask].join(' ').toLocaleLowerCase().includes(term));
    if (term && !data.groups.some(g => filtered(g).length)) return '<section class="ad-empty"><h2>No matching claims</h2><p>Try a claim name, reference or handler.</p><button type="button" data-desk-clear>Clear search</button></section>';
    return data.groups.map(group => {
      const items = filtered(group), title = groupNames[group.id] || group.label;
      const body = `<ol class="ad-rows">${items.map(row).join('')}</ol>`;
      if (!items.length) return '';
      if (['quiet','closed'].includes(group.id) && !term) return `<details class="ad-group ad-quiet" data-desk-group="${escape(group.id)}"><summary><h2>${escape(title)}</h2><span>${escape(group.count)}</span>${group.id==='quiet'&&unreviewed(group)?`<small class="ad-unreviewed">${unreviewed(group)} not yet reviewed</small>`:''}</summary>${body}</details>`;
      return `<section class="ad-group" aria-labelledby="ad-${escape(group.id)}"><header class="ad-group-heading"><h2 id="ad-${escape(group.id)}">${escape(title)}</h2><span>${escape(group.count)}${term ? ' · '+items.length+' shown' : ''}</span></header>${body}</section>`;
    }).join('');
  }
  function shell(data) {
    return `<header class="ad-heading"><div><p class="ad-eyebrow">Claims desk</p><h1>Your next decisions</h1></div><p class="ad-workspace-note">${escape(data.total)} synthetic claims<br>Local review · drafts stay here</p></header><nav class="ad-counts" aria-label="Who acts next">${data.groups.map(g => `<a href="#ad-${escape(g.id)}" data-desk-group-link="${escape(g.id)}">${countMarkup(g)}</a>`).join('')}</nav><div class="ad-tools"><label for="adSearch">Find a claim<input id="adSearch" type="search" placeholder="Claim, reference or handler" autocomplete="off"></label><button type="button" data-desk-refresh>Refresh saved work</button></div><p id="adStatus" class="ad-status" role="status" aria-live="polite"></p><div id="adGroups">${groups(data)}</div>`;
  }
  function start() {
    const workspace = window.CasePathWorkspace;
    if (!workspace || workspace.queueRoot().querySelector('#agentDesk')) return;
    document.documentElement.dataset.agentNative = 'true';
    document.querySelectorAll('.cp-top-links [data-close-detail]').forEach(a => a.textContent = 'Desk');
    const original = workspace.queueRoot().querySelector('#cwQueue'), desk = document.createElement('main');
    desk.id = 'agentDesk'; desk.className = 'ad-desk'; desk.tabIndex = -1;
    original.before(desk); original.hidden = true;
    desk.innerHTML = '<div class="ad-loading" role="status"><p class="ad-eyebrow">Claims desk</p><h1>Reading saved work…</h1><div class="ad-skeleton"></div><div class="ad-skeleton"></div><div class="ad-skeleton"></div></div>';
    let data = null, search = '', loading = false, poll = null, claimEpoch = 0;
    const agentReads = new Map(), agentCache = new Map(), peekSources = new Map();
    let claimRefresh = null;
    function refreshClaim() {
      if(!claimRefresh)claimRefresh=Promise.resolve(workspace.refresh()).finally(()=>{claimRefresh=null;});
      return claimRefresh;
    }
    const openedGroups = new Set(), openedPeeks = new Set();
    async function verify(value, field, contract) {
      if (!value || value.contract !== contract || typeof value[field] !== 'string') throw new Error('The saved projection could not be verified. Refresh the desk.');
      const canonical = value => value === null || typeof value !== 'object' ? JSON.stringify(value) : Array.isArray(value) ? '['+value.map(canonical).join(',')+']' : '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
      const bytes = new TextEncoder().encode(canonical(Object.fromEntries(Object.entries(value).filter(([k])=>k!==field))));
      const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(v=>v.toString(16).padStart(2,'0')).join('');
      if (hash !== value[field]) throw new Error('The saved projection identity differs. Refresh the desk.');
      return value;
    }
    function display() {
      const active=document.activeElement, focus=active?.id;
      const focusClaim=active?.closest('[data-desk-claim]')?.dataset.deskClaim;
      const focusPeek=active?.closest('.ad-peek')?.closest('.ad-row')?.querySelector('[data-desk-claim]')?.dataset.deskClaim;
      if (!desk.querySelector('#adSearch')) desk.innerHTML = shell(data);
      else {
        desk.querySelector('#adGroups').innerHTML = groups(data,search);
        desk.querySelectorAll('.ad-counts a').forEach(a => { const g=data.groups.find(g=>g.id===a.dataset.deskGroupLink); if(g)a.innerHTML=countMarkup(g); });
      }
      for (const id of openedGroups) desk.querySelector(`[data-desk-group="${id}"]`)?.setAttribute('open','');
      for(const id of openedPeeks) desk.querySelector('[data-desk-claim="'+CSS.escape(id)+'"]')?.closest('.ad-row')?.querySelector('.ad-peek')?.setAttribute('open','');
      const focusTarget=focus?document.getElementById(focus):focusClaim?desk.querySelector('[data-desk-claim="'+CSS.escape(focusClaim)+'"]'):focusPeek?desk.querySelector('[data-desk-claim="'+CSS.escape(focusPeek)+'"]')?.closest('.ad-row')?.querySelector('.ad-peek summary'):null;
      focusTarget?.focus({preventScroll:true});
      desk.querySelector('#adSearch').value = search;
    }
    async function load() {
      if (loading) return;
      loading = true; desk.setAttribute('aria-busy','true');
      try {
        const value = await workspace.request('/api/claim-loops/v1/workspace/desk');
        data = await verify(value,'projection_sha256','casepath.agent-desk/1.0.0'); display();
        if(!performance.getEntriesByName('casepath:desk-painted').length)requestAnimationFrame(()=>performance.mark('casepath:desk-painted'));
        desk.querySelector('#adStatus').textContent = ''; // Review coverage is already explicit in the Quiet count.
        clearTimeout(poll);
        if (!workspace.snapshot().claim && data.groups.some(g=>g.id==='working' && g.count)) poll=setTimeout(load,1400);
      } catch (error) {
        if (data) desk.querySelector('#adStatus').innerHTML = `${escape(error.message)} <button type="button" data-desk-refresh>Try again</button>`;
        else desk.innerHTML = `<section class="ad-empty" role="alert"><h1>The desk could not load</h1><p>${escape(error.message)}</p><button type="button" data-desk-refresh>Try again</button></section>`;
      } finally { loading=false; desk.setAttribute('aria-busy','false'); }
    }
    async function readPeek(claimId) {
      const claim=data?.groups.flatMap(group=>group.claims).find(row=>row.claim_id===claimId);
      const target=()=>desk.querySelector('[data-desk-evidence="'+CSS.escape(claimId)+'"]');
      if(!claim||!target())return;
      target().textContent='Reading cited passages…';
      try {
        const key=claimId+':'+claim.workspace_revision;
        let agent=agentCache.get(key);
        if(!agent){
          if(!agentReads.has(key))agentReads.set(key,workspace.request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}/agent`).finally(()=>agentReads.delete(key)));
          agent=await agentReads.get(key);await verify(agent,'projection_sha256','casepath.agent-desk-claim/1.0.0');agentCache.set(key,agent);
        }
        const current=data?.groups.flatMap(group=>group.claims).find(row=>row.claim_id===claimId),evidence=peekEvidence(agent,current||claim);
        if(!target())return;peekSources.set(claimId,evidence.sources);target().innerHTML=evidence.html;
      }catch(error){if(target())target().textContent=error.message;}
    }
    desk.addEventListener('input',event=>{if(event.target.id==='adSearch'){search=event.target.value;desk.querySelector('#adGroups').innerHTML=groups(data,search);}});
    desk.addEventListener('toggle',event=>{const id=event.target.dataset.deskGroup;if(id){if(event.target.open)openedGroups.add(id);else openedGroups.delete(id);}if(event.target.matches('.ad-peek')){const claim=event.target.closest('.ad-row')?.querySelector('[data-desk-claim]')?.dataset.deskClaim;if(claim){if(event.target.open){openedPeeks.add(claim);void readPeek(claim);}else openedPeeks.delete(claim);}}},true);
    desk.addEventListener('click',event=>{
      const evidence=event.target.closest('[data-desk-source]');
      if(evidence){const id=evidence.dataset.deskSourceClaim,span=peekSources.get(id)?.[Number(evidence.dataset.deskSource)];if(span)void workspace.openClaim(id).then(()=>{if(workspace.snapshot().claim?.state.claim_id===id)workspace.openSource(span);});return;}
      const claim=event.target.closest('[data-desk-claim]');
      if(claim){event.preventDefault();workspace.openClaim(claim.dataset.deskClaim);return;}
      if(event.target.closest('[data-desk-refresh]')) void load();
      if(event.target.closest('[data-desk-clear]')){search='';display();desk.querySelector('#adSearch')?.focus();}
      const link=event.target.closest('[data-desk-group-link]');
      if(link){event.preventDefault();const id=link.dataset.deskGroupLink;let target=desk.querySelector(`[data-desk-group="${id}"]`);if(target){target.open=true;openedGroups.add(id);}else target=desk.querySelector('#ad-'+id);target?.scrollIntoView({block:'start'});}
    });
    function paintClaim(snapshot,agent) {
      const id=snapshot.claim.state.claim_id,mount=document.getElementById('agentClaimMount');
      if(!mount || workspace.snapshot().claim?.state.claim_id!==id)return;
      const state=workspace.snapshot().claim.state;
      if(agent.claim_id!==id || agent.workspace_revision!==state.revision || agent.workspace_state_sha256!==state.state_sha256){void refreshClaim();return;}
      if(mount.dataset.agentSha===agent.projection_sha256 || mount.dataset.agentSha && window.CasePathAgentClaim.session(id).busy)return;
      const active=mount.contains(document.activeElement)?document.activeElement:null;
      const source=active?.hasAttribute('data-av-source')?window.CasePathAgentClaim.session(id).sources[Number(active.dataset.avSource)]:null;
      const disclosure=active?.tagName==='SUMMARY'?active.parentElement.dataset.avDisclosure:null;
      let focus=active?.id?'#'+CSS.escape(active.id):active?.hasAttribute('data-av-control')?'[data-av-control="'+CSS.escape(active.dataset.avControl)+'"]':active?.hasAttribute('data-edit-owner')?'[data-edit-owner]':disclosure?'[data-av-disclosure="'+CSS.escape(disclosure)+'"]>summary':active?.name?'[name="'+CSS.escape(active.name)+'"]'+(active.type==='radio'?'[value="'+CSS.escape(active.value)+'"]':''):active?.matches('.av-decision button[type=submit]')?'.av-decision button[type=submit]':null;
      let selection=active?.tagName==='TEXTAREA'?{start:active.selectionStart,end:active.selectionEnd}:null;
      // A core refresh replaces this mount before announcing the new claim.
      // Restore only its scoped input, while focus is still lost to that removal.
      if(!active && document.activeElement===document.body && snapshot.agentFocus?.id){
        focus='#'+CSS.escape(snapshot.agentFocus.id);selection=snapshot.agentFocus.selection;
      }
      const current=workspace.snapshot();
      mount.innerHTML=window.CasePathAgentClaim.render({claim:current.claim.state,agent,process:current.process,sources:current.claim.artifacts});
      mount.dataset.agentSha=agent.projection_sha256;
      mount.setAttribute('aria-busy','false');
      window.CasePathAgentClaim.bind({root:mount,api:{request:workspace.request,verify},refresh:async()=>{agentCache.clear();await refreshClaim();if(!workspace.snapshot().claim)void load();},onOpenSource:workspace.openSource,onOpenPane:name=>workspace.openPane(name==='trace'?'activity':name),onNotice:text=>{const status=document.querySelector('#cwCommandStatus');if(status)status.textContent=text;}});
      mount.dataset.pane=document.querySelector('[data-claim-section][aria-selected=true]')?.dataset.claimSection||'overview';
      if(focus){const target=mount.querySelector(focus);target?.focus({preventScroll:true});if(selection&&target?.setSelectionRange)target.setSelectionRange(selection.start,selection.end);}
      if(source){const index=window.CasePathAgentClaim.session(id).sources.findIndex(item=>item.artifact_id===source.artifact_id&&(item.quote||item.exact_text||item.locator?.exact_text)===(source.quote||source.exact_text||source.locator?.exact_text));if(index>=0)mount.querySelector('[data-av-source="'+index+'"]')?.focus({preventScroll:true});}
    }
    async function claimRendered(event) {
      const epoch=++claimEpoch,snapshot=event.detail,id=snapshot.claim?.state.claim_id;
      if(!id || !document.getElementById('agentClaimMount'))return;
      clearTimeout(poll);
      const key=id+':'+snapshot.claim.state.revision;
      if(agentCache.has(key))paintClaim(snapshot,agentCache.get(key));
      try {
        if(!agentReads.has(key))agentReads.set(key,workspace.request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(id)}/agent`).finally(()=>agentReads.delete(key)));
        const agent=await agentReads.get(key);
        await verify(agent,'projection_sha256','casepath.agent-desk-claim/1.0.0');
        if(workspace.snapshot().claim?.state.claim_id!==id)return;
        agentCache.set(key,agent);paintClaim(snapshot,agent);
        if(agent.state==='working')setTimeout(()=>{if(epoch===claimEpoch && workspace.snapshot().claim?.state.claim_id===id)void claimRendered({detail:workspace.snapshot()});},1400);
      }catch(error){
        const mount=document.getElementById('agentClaimMount');
        if(workspace.snapshot().claim?.state.claim_id===id && mount){mount.innerHTML=`<p class="av-notice" role="alert">${escape(error.message)} <button type="button" data-agent-retry>Read saved work again</button></p>`;mount.querySelector('button').onclick=()=>claimRendered({detail:workspace.snapshot()});mount.setAttribute('aria-busy','false');}
      }
    }
    window.addEventListener('casepath:claim-rendered',claimRendered);
    window.addEventListener('hashchange',()=>{if(!location.hash)void load();});
    window.addEventListener('casepath:desk-refresh',()=>{if(!workspace.snapshot().claim)void load();});
    document.addEventListener('click',event=>{const tab=event.target.closest('[data-claim-section]');if(tab){const mount=document.getElementById('agentClaimMount');if(mount)mount.dataset.pane=tab.dataset.claimSection;}});
    void load().then(async()=>{
      try {
        await workspace.request('/api/claim-loops/v1/workspace/desk/start',{method:'POST',headers:{'Content-Type':'application/json','X-CasePath-Agent-Work':'1','X-CasePath-Idempotency-Key':'desk-arrival-synthetic-150-v2-6'},body:JSON.stringify({limit:6})});
        await load();
        if(location.hash.includes('claim=') && workspace.snapshot().claim)void claimRendered({detail:workspace.snapshot()});
      }catch(error){const status=desk.querySelector('#adStatus');if(status)status.textContent=`The agent could not start: ${error.message}. Refresh saved work to recover.`;}
    });
    const current=workspace.snapshot(); if(current.claim) void claimRendered({detail:current});
  }
  return Object.freeze({escape,row,groups,shell,peekEvidence,start});
});
