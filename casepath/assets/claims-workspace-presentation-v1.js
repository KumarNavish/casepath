/* Read-only presentation of validated CasePath projections. No workflow authority. */
(function (root, factory) {
  const view = factory();
  if (typeof module === 'object' && module.exports) module.exports = view;
  else root.CasePathPresentation = view;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const names = Object.freeze({not_assessed:'Not assessed',blocked:'Waiting for evidence',decision_ready:'Ready to proceed',safe_abstention:'Review required',in_review:'In review',waiting_for_evidence:'Waiting for evidence',dispatching:'Checking an action',received:'Received',missing:'Missing',insufficient:'Insufficient',conditional:'Conditional',irrelevant:'Not needed',unknown:'Not verified',failed:'Needs attention',claim_handler:'Claim handler',external_specialist:'Specialist',provided_sufficient:'Sufficient',provided_insufficient:'Insufficient',known:'Established',contradicted:'Conflicting information',conflicting:'Conflicting information',unclassified_intake:'Not classified',lease_termination_dispute:'Lease termination',defect_mold_heating:'Defects and heating',rent_increase_dispute:'Rent changes'});
  const label = value => names[value] || String(value ?? 'Not recorded').replaceAll('_',' ').replace(/^./, c=>c.toUpperCase());
  const copy = value => ({'Start deterministic assessment':'Start assessment','Deterministic assessment has not started':'Assessment has not started','Resume deterministic assessment':'Resume assessment','Review certified decision-ready packet':'Review the evidence-ready packet','No current mandatory evidence obligation remains':'No required evidence is outstanding on the current path','Review safe abstention and unresolved evidence':'Review unresolved evidence'})[value] || String(value ?? 'Not recorded');
  const iconPaths = {back:'m15 18-6-6 6-6M9 12h12',next:'m9 6 6 6-6 6',check:'m5 12 4 4L19 6',file:'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h6',refresh:'M20 7v5h-5M4 17v-5h5M5 8a8 8 0 0 1 13-3l2 7M4 12l2 7a8 8 0 0 0 13-3',search:'m21 21-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',close:'m6 6 12 12M6 18 18 6',arrow:'M4 12h16m-5-5 5 5-5 5'};
  const icon = name => `<svg class="cw-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${iconPaths[name] || iconPaths.file}"/></svg>`;
  const date = (value, time=false) => {
    if (!value || !Number.isFinite(new Date(value).valueOf())) return 'Not recorded';
    return new Intl.DateTimeFormat(undefined,{dateStyle:'medium',...(time?{timeStyle:'short'}:{})}).format(new Date(value));
  };
  const conflict = item => item?.raw_status === 'conflicting' || item?.obligation_status === 'contradicted';
  const evidenceStatus = item => conflict(item) ? 'Conflicting information' : label(item?.evidence_class || 'unknown');
  const readiness = p => {
    if (p?.failure_or_unknown_effect) return 'Action needs checking';
    if (p?.readiness_scope === 'provisional_plan' && p?.provisional_next_action?.enabled) return 'Follow-up proposed';
    if (p?.readiness_scope === 'provisional_plan' && p?.readiness_state === 'decision_ready') return 'Plan covered · review needed';
    if (p?.evidence_items?.some(conflict)) return 'Conflicting information';
    return label(p?.readiness_state || 'not_assessed');
  };
  const tone = p => p?.failure_or_unknown_effect || p?.evidence_items?.some(conflict) ? 'failure' : p?.readiness_state === 'decision_ready' && p?.readiness_scope !== 'provisional_plan' ? 'ready' : p?.readiness_state === 'blocked' ? 'blocked' : 'unknown';
  const status = p => `<span class="cw-pill" data-tone="${tone(p)}">${h(readiness(p))}</span>`;
  const options = (pairs, first) => `<option value="">${h(first)}</option>${pairs.map(v=>`<option value="${h(v)}">${h(label(v))}</option>`).join('')}`;

  function shell() {
    return `<div class="cw-shell">
      <header class="cw-topbar"><a class="cw-brand" href="#" aria-label="CasePath claims"><span class="cw-mark">CP</span><span>CasePath</span></a><span class="cw-environment">Local development · synthetic claims</span><button class="cw-button cw-button-quiet" id="cwRefresh" type="button">${icon('refresh')}Refresh</button></header>
      <main class="cw-main" id="cwQueue"><section class="cw-hero"><div><h1>Claims</h1><p>Find the next claim that needs your attention.</p></div><div class="cw-summary"><strong id="cwTotal">—</strong><span>claims in this view</span></div></section>
      <nav class="cw-views" aria-label="Queue views"><button type="button" data-queue-view="all" aria-pressed="true">All claims</button><button type="button" data-queue-view="evidence" aria-pressed="false">Needs evidence</button><button type="button" data-queue-view="ready" aria-pressed="false">Ready to proceed</button><button type="button" data-queue-view="attention" aria-pressed="false">Needs attention</button><button type="button" data-queue-view="unassigned" aria-pressed="false">Unassigned</button></nav>
      <section class="cw-filter-card" aria-label="Claims filters"><form class="cw-filters" id="cwFilters">
        <div class="cw-field cw-search-field"><label for="cwSearch">Search claims</label><input id="cwSearch" type="search" placeholder="Claim, subject or handler" autocomplete="off"></div>
        <div class="cw-field"><label for="cwState">Status</label><select id="cwState">${options(['received','in_review','waiting','waiting_for_evidence','dispatching','decision_ready','safe_abstention','failed'],'All statuses')}</select></div>
        <div class="cw-field"><label for="cwSort">Sort by</label><select id="cwSort"><option value="priority">Priority</option><option value="oldest_waiting">Waiting longest</option><option value="urgency">Urgency</option><option value="nearest_deadline">Nearest deadline</option><option value="most_decision_ready">Closest to readiness</option><option value="latest_update">Latest update</option></select></div>
        <details class="cw-advanced-filters"><summary>More filters</summary><div class="cw-advanced-filter-grid">
          <div class="cw-field"><label for="cwReadiness">Readiness</label><select id="cwReadiness">${options(['not_assessed','blocked','decision_ready','safe_abstention'],'All readiness')}</select></div>
          <div class="cw-field"><label for="cwClaimType">Claim type</label><select id="cwClaimType">${options(['unclassified_intake'],'All types')}</select></div>
          <div class="cw-field"><label for="cwOwner">Handler</label><select id="cwOwner"><option value="">All handlers</option><option value="unassigned">Unassigned</option></select></div>
          <div class="cw-field"><label for="cwUrgency">Urgency</label><select id="cwUrgency">${options(['high','elevated','normal'],'All urgencies')}</select></div>
          <div class="cw-field"><label for="cwFailure">Action outcome</label><select id="cwFailure"><option value="">All outcomes</option><option value="true">Failed or uncertain</option><option value="false">No uncertain outcome</option></select></div>
          <div class="cw-field"><label for="cwPendingEvidence">Evidence</label><select id="cwPendingEvidence"><option value="">All evidence</option><option value="unknown">Not assessed</option><option value="none">None outstanding</option><option value="some">Evidence outstanding</option></select></div>
        </div></details><button type="button" class="cw-text-button cw-clear-filters" id="cwClearFilters" hidden>Clear filters</button>
      </form></section>
      <div id="cwQueueNotice" class="cw-inline-notice" role="status" hidden></div>
      <section class="cw-table-card" aria-label="Claims queue"><div id="cwTable"></div><div class="cw-table-foot"><span id="cwPageStatus" role="status" aria-live="polite">Loading claims…</span><button class="cw-button" id="cwMore" type="button" hidden>Load more claims</button></div></section>
      <p class="cw-queue-footnote">Priority and readiness come from saved claim records. An unrecorded deadline stays unknown.</p></main></div>
      <section class="cw-detail" id="cwDetail" hidden aria-label="Claim workbench" aria-modal="true" role="dialog"><div class="cw-detail-scrim" data-close-detail></div><article class="cw-detail-panel" id="cwDetailPanel" tabindex="-1"></article></section>`;
  }

  function queueRows(items) {
    return `<div class="cw-table-scroll"><table class="cw-table"><thead><tr><th scope="col">Claim</th><th scope="col">Status</th><th scope="col">Current blocker</th><th scope="col">Next action</th><th scope="col">Handler</th></tr></thead><tbody>${items.map(item=>{
      const p=item.operational_projection;
      return `<tr tabindex="0" data-claim-id="${h(item.claim_id)}" aria-label="Open ${h(item.claim_id)}: ${h(item.subject)}">
        <td class="cw-claim-cell"><strong title="${h(item.subject)}">${h(item.subject)}</strong><span>${h(item.claim_id)} <span class="cw-inline-dot">·</span> ${h(item.received_age_days)} days open</span>${item.urgency==='high'||item.urgency==='elevated'?`<small class="cw-urgency">${h(label(item.urgency))} urgency${item.deadline_at?` · Due ${h(date(item.deadline_at))}`:''}</small>`:item.deadline_at?`<small>Due ${h(date(item.deadline_at))}</small>`:''}</td>
        <td data-label="Status">${status(p)}<small>${item.pending_evidence_count==null?'Evidence not assessed':`${h(item.pending_evidence_count)} required now`}</small></td>
        <td data-label="Blocker" class="cw-blocker-cell">${h(copy(item.principal_blocker))}</td>
        <td data-label="Next action" class="cw-next-cell"><strong>${h(copy(item.next_safe_action))}</strong>${icon('next')}</td>
        <td data-label="Handler" class="cw-handler-cell">${h(item.owner||'Unassigned')}</td></tr>`;
    }).join('')}</tbody></table></div>`;
  }
  function skeleton() {
    return `<div class="cw-skeleton" role="status" aria-label="Loading claims">${Array.from({length:6},()=>'<div><span></span><span></span><span></span></div>').join('')}<span class="cw-sr-only">Loading claims…</span></div>`;
  }

  function evidenceRow(item, loop) {
    const raw=loop.loop_state.checklist.items.find(row=>row.item_id===item.evidence_item_id);
    const nodes=loop.loop_state.process.nodes.filter(n=>(raw?.node_ids||[raw?.node_id]).includes(n.node_id));
    const timing=item.mandatory_now?'Needed now':item.evidence_class==='conditional'?`Only if the process reaches “${nodes[0]?.title || item.title}”`:item.evidence_class==='received'?'Accepted for this step':item.evidence_class==='irrelevant'?'No longer needed on this path':'Requires review';
    return `<li class="cw-evidence-row" data-evidence-item-id="${h(item.evidence_item_id)}" data-fact-id="${h(item.fact_id)}" data-fact-state="${h(item.fact_state)}" data-raw-status="${h(item.raw_status)}" data-obligation-status="${h(item.obligation_status)}" data-mandatory-now="${h(String(item.mandatory_now))}" data-current-path="${h(String(item.current_path))}" data-source-ref-ids="${h(JSON.stringify(item.source_ref_ids))}" data-provenance-edge-sha256s="${h(JSON.stringify(item.provenance_edge_sha256s))}"><button type="button" class="cw-evidence-link" data-evidence-source="${h(item.evidence_item_id)}"><span><strong>${h(item.title)}</strong><small>${h(timing)}</small></span><span class="cw-evidence-status" data-class="${conflict(item)?'conflict':h(item.evidence_class)}">${h(evidenceStatus(item))}</span>${icon('next')}</button></li>`;
  }
  function evidenceList(loop) {
    const p=loop.operational_projection;
    const classes=['missing','insufficient','unknown','received','conditional','irrelevant'];
    return `<section class="cw-section cw-evidence-section" id="cwEvidenceClasses"><div class="cw-section-heading"><h3>Evidence</h3><span>${p.pending_evidence_count} required now</span></div><p class="cw-section-intro">Open an item to see why it is needed and its supporting sources.</p>${classes.map(name=>{
      const items=p.evidence_items.filter(i=>i.evidence_class===name); if(!items.length) return '';
      const list=`<ul class="cw-evidence-items">${items.map(i=>evidenceRow(i,loop)).join('')}</ul>`;
      return ['conditional','irrelevant'].includes(name)?`<details class="cw-evidence-group" data-evidence-class="${name}" id="cwEvidenceGroup-${name}"><summary>${label(name)} <span>${items.length}</span></summary>${list}</details>`:`<div class="cw-evidence-group" data-evidence-class="${name}">${list}</div>`;
    }).join('')}</section>`;
  }
  function processNode(node, loop) {
    const overlay=loop.loop_state.process.current_overlay;
    const completed=overlay.completed_node_ids.includes(node.node_id);
    const current=overlay.current_node_id===node.node_id;
    const blocked=overlay.blocked_node_ids.includes(node.node_id);
    const state=completed?'complete':current?'current':blocked?'blocked':node.state==='inactive'?'inactive':'future';
    return `<li data-process-state="${state}"><span class="cw-step-mark">${completed?icon('check'):''}</span><button type="button" class="cw-process-link" data-process-node="${h(node.node_id)}" ${current?'aria-current="step"':''}><strong>${h(node.title)}</strong><span>${completed?'Completed':current?'Current decision':blocked?'Blocked':state==='inactive'?'Inactive branch':'Not reached'}</span></button></li>`;
  }
  function process(loop) {
    const p=loop.loop_state.process, overlay=p.current_overlay;
    const nodes=p.main_spine.map(id=>p.nodes.find(n=>n.node_id===id)).filter(Boolean);
    const at=Math.max(0,nodes.findIndex(n=>n.node_id===overlay.current_node_id));
    const context=nodes.slice(Math.max(0,at-1),Math.min(nodes.length,at+2));
    const current=p.nodes.find(n=>n.node_id===overlay.current_node_id);
    const branches=(current?.branches||[]).map(b=>({...b,node:p.nodes.find(n=>n.node_id===b.target)}));
    return `<section class="cw-section cw-process-section" id="cwCurrentProcess" data-operational-projection-sha256="${h(loop.operational_projection.projection_sha256)}"><div class="cw-section-heading"><h3>Handling process</h3><span>${overlay.completed_node_ids.filter(id=>p.main_spine.includes(id)).length} of ${nodes.length} steps completed</span></div><ol class="cw-process-path">${context.map(n=>processNode(n,loop)).join('')}</ol>${branches.length?`<details class="cw-branches" id="cwProcessBranches"><summary>Paths from the current decision</summary><ul>${branches.map(b=>`<li data-branch-state="${h(b.state)}"><span>${h(b.node?.title||'Unlabelled process step')}</span><small>${b.state==='selected'?'Active path':'Possible alternative'}</small></li>`).join('')}</ul></details>`:''}<details class="cw-full-process" id="cwFullProcess"><summary>Show all ${nodes.length} process steps</summary><ol class="cw-process-path">${nodes.map(n=>processNode(n,loop)).join('')}</ol></details></section>`;
  }

  function compareLoops(before, after, kind='evidence') {
    if(!before || !after || before.claim_id!==after.claim_id) return null;
    const old=before.operational_projection, next=after.operational_projection;
    const changes=next.evidence_items.flatMap(item=>{
      const previous=old.evidence_items.find(i=>i.evidence_item_id===item.evidence_item_id);
      if(!previous || ['evidence_class','fact_state','mandatory_now','current_path','raw_status'].every(k=>previous[k]===item[k])) return [];
      return [{id:item.evidence_item_id,title:item.title,before:evidenceStatus(previous),after:evidenceStatus(item),wasRequired:previous.mandatory_now,isRequired:item.mandatory_now}];
    });
    const added=after.loop_state.observations.length-before.loop_state.observations.length;
    return {kind,claimId:after.claim_id,beforeRevision:before.revision,afterRevision:after.revision,accepted:added>0,changes,beforeState:readiness(old),afterState:readiness(next),beforeStep:old.current_process?.node_title,afterStep:next.current_process?.node_title,remaining:next.pending_evidence_count};
  }
  function changeMarkup(change) {
    if(!change) return '';
    const title=change.kind==='correction'?'Correction applied':change.accepted?'Evidence received · process updated':'Evidence not accepted';
    return `<section class="cw-change" id="cwReplanDelta" tabindex="-1" data-accepted="${change.accepted || change.kind==='correction'}" data-change-kind="${h(change.kind)}" data-before-revision="${h(change.beforeRevision)}" data-after-revision="${h(change.afterRevision)}"><div class="cw-section-heading"><h3>${title}</h3><button type="button" class="cw-text-button" data-dismiss-change aria-label="Dismiss change summary">${icon('close')}</button></div>${change.changes.length?`<ul>${change.changes.map(c=>`<li><button type="button" data-evidence-source="${h(c.id)}">${h(c.title)}</button><span>${h(c.before)} ${icon('arrow')} <strong>${h(c.after)}</strong>${c.wasRequired&&!c.isRequired?' · Removed from current requests':!c.wasRequired&&c.isRequired?' · Needed next':''}</span></li>`).join('')}</ul>`:'<p>No finding was added. The evidence gap remains open; no claim decision changed.</p>'}${change.beforeStep!==change.afterStep?`<p class="cw-change-path"><span>${h(change.beforeStep)}</span>${icon('arrow')}<strong>${h(change.afterStep)}</strong></p>`:''}<p class="cw-change-readiness">${h(change.afterState)} · ${h(change.remaining)} required now</p></section>`;
  }
  function semanticText(value) {
    if(!value || typeof value!=='object') return 'Not recorded';
    const fact={known:'Established',unknown:'Unknown',conflicting:'Conflicting information'}[value.fact_state] || label(value.fact_state);
    const evidence={provided_sufficient:'Sufficient evidence',provided_insufficient:'Insufficient evidence',missing:'Missing evidence',conditional:'Conditional evidence'}[value.evidence_status] || label(value.evidence_status);
    return `${fact} · ${evidence}`;
  }
  function correction(loop, opts) {
    const latest=loop.latest_correction, preview=opts.correctionPreview, candidate=loop.correction_candidates?.[0];
    const item=loop.operational_projection.evidence_items.find(i=>i.fact_id===(preview?.effect.fact_id||candidate?.target_fact_id));
    if(preview) return `<section class="cw-correction" id="cwCorrectionPreview" tabindex="-1"><h3>Review this correction</h3><p>Withdraw support for <strong>${h(item?.title||label(preview.effect.fact_id))}</strong>. No replacement finding is created.</p><div class="cw-before-after"><div><small>Before</small><strong>${h(item?evidenceStatus(item):'Existing accepted finding')}</strong></div><div><small>After</small><strong>Unknown · insufficient evidence</strong></div></div><p class="cw-stable">Unrelated facts will stay unchanged.</p><div class="cw-actions"><button class="cw-button cw-button-primary" id="cwCorrectionConfirm" type="button">Apply correction</button><button class="cw-button" id="cwCorrectionCancel" type="button">Keep current finding</button></div><p class="cw-note">Preview only. Nothing changes until you confirm.</p></section>`;
    if(latest) return `<section class="cw-correction" id="cwCorrectionResult"><h3>Correction recorded</h3><div class="cw-before-after cw-correction-semantics" data-before-semantics="${h(JSON.stringify(latest.before_semantics))}" data-after-semantics="${h(JSON.stringify(latest.after_semantics))}"><div><small>Before</small><p>${h(semanticText(latest.before_semantics))}</p></div><div><small>After</small><p>${h(semanticText(latest.after_semantics))}</p></div></div><p class="cw-stable">Unrelated facts stayed unchanged.</p><details><summary>Restoring a finding</summary><p>There is no automatic undo. A finding can be established again only through an accepted evidence action; the correction remains in the history.</p></details><details class="cw-receipt"><summary>Correction receipt</summary><pre>${h(JSON.stringify(latest,null,2))}</pre></details></section>`;
    if(candidate) return `<section class="cw-correction" id="cwCorrectionOption"><h3>Something changed?</h3><p>Preview the withdrawal of an accepted finding before changing this claim.</p><button class="cw-button" id="cwCorrectionReview" type="button">${opts.pendingCorrection?'Recover correction preview':'Review correction'}</button></section>`;
    return '';
  }

  function provisionalFollowupMarkup(projection) {
    const action=projection?.provisional_next_action;
    const audiences={provider:'Request from the provider',claimant:'Request from the claimant',authority:'Request from the authority',internal:'Internal review'};
    if(projection?.readiness_scope!=='provisional_plan' || action?.enabled!==true || !Object.hasOwn(audiences,action.audience) || !Array.isArray(action.requested_contents) || !action.requested_contents.length) return '';
    return `<section class="cw-section" id="cwProvisionalNextAction" data-audience="${h(action.audience)}"><div class="cw-section-heading"><h3>${h(audiences[action.audience])}</h3><span>Proposed follow-up</span></div><ul class="cw-priority">${action.requested_contents.map(text=>`<li>${h(text)}</li>`).join('')}</ul><p class="cw-note">This fallible proposal has not been sent and does not certify that the customer goal is fulfilled.</p></section>`;
  }

  function workbench(loop, workspace, opts={}) {
    if(!loop) {
      const reviewing=workspace.workflow_state==='in_review', failed=workspace.failure_or_unknown_effect;
      return `<section class="cw-section cw-focus" id="cwLoopWorkbench"><span class="cw-focus-label">Next action</span><h2>${failed?'Check the previous action':reviewing?'Identify the evidence gap':'Review the claim'}</h2><p>${failed?'The previous action has an uncertain outcome. Check the saved record before trying anything else.':reviewing?'The initial assessment is saved. Open the evidence review to see the active process and what is missing.':'The claim has been received but not assessed. Check the original message and begin the assessment.'}</p><div class="cw-actions"><button class="cw-button cw-button-primary" id="${failed?'cwReconcile':reviewing?'cwEnsureLoop':'cwStart'}" type="button" ${opts.invalid?'disabled':''}>${failed?'Check saved action':reviewing?'Open evidence review':opts.pendingStart?'Recover assessment':'Start assessment'}${icon('arrow')}</button></div><p class="cw-note">This records the assessment. It does not approve, pay or close the claim.</p></section>`;
    }
    const p=loop.operational_projection, s=loop.loop_state, action=s.selected_action, provisional=p.readiness_scope==='provisional_plan';
    const heading=provisional && p.provisional_next_action?.enabled ? 'Review the proposed follow-up' : action?.title || (loop.outcome==='decision_ready'?(provisional?'Review the covered plan':'Evidence is ready for review'):loop.outcome==='abstain'?'A review is needed before proceeding':'Checking the saved action');
    const primary=provisional && (action || p.provisional_next_action?.enabled)?'<button class="cw-button cw-button-primary" type="button" data-show-investigation>Review saved investigation</button>':action&&!provisional?`<form class="cw-evidence-form" id="cwEvidenceForm"><button class="cw-button cw-button-primary" id="cwLoopCommit" type="submit" ${opts.pendingInvalid||opts.correctionPreview?'disabled':''}>${opts.pendingAdvance?'Check saved action and replan':loop.stage_receipt?'Complete evidence review':opts.pendingIntent||opts.pendingStage?'Recover evidence action':'Check available evidence'}${icon('arrow')}</button></form>`:loop.outcome==='decision_ready'?'<button class="cw-button cw-button-primary" id="cwExport" type="button">Export status for review</button>':loop.outcome==='abstain'?'<button class="cw-button cw-button-primary" type="button" data-show-evidence>Review unresolved evidence</button>':loop.outcome==='processing'?'<button class="cw-button cw-button-primary" type="button" data-refresh-claim>Check saved state</button>':'';
    const scopedNote=provisional?'This is a proposed plan, not a certified claim decision.':loop.outcome==='decision_ready'?'Readiness applies to this evidence review. Approval, payment and closure still require a separate decision.':loop.outcome==='abstain'?'The system stopped rather than infer an unsupported finding. No approval, payment or closure occurred.':'Checks the next available source and updates this process only if the evidence is accepted. Nothing is sent to the customer.';
    const counts=p.evidence_class_counts, total=p.evidence_items.length, resolved=counts.received+counts.irrelevant, percent=total?Math.round(resolved/total*100):0;
    const roles=s.six_agent_cycle_receipt.agent_ids.map((id,i)=>`<li data-agent-id="${h(id)}" data-receipt-sha256="${h(s.six_agent_cycle_receipt.agent_receipt_sha256s[i])}"><strong>${h(label(id))}</strong><span>${h(s.six_agent_cycle_receipt.agent_receipt_sha256s[i])}</span></li>`).join('');
    const gates=s.six_agent_cycle_receipt.deterministic_gate_ids.map((id,i)=>`<li data-gate-id="${h(id)}" data-receipt-sha256="${h(s.six_agent_cycle_receipt.gate_receipt_sha256s[i])}"><strong>${h(label(id))}</strong><span>${h(s.six_agent_cycle_receipt.gate_receipt_sha256s[i])}</span></li>`).join('');
    return `${changeMarkup(opts.change)}<section class="cw-section cw-focus" id="cwLoopWorkbench" data-outcome="${h(loop.outcome)}"><span class="cw-focus-label">${action?'Next action':'Current position'}</span><h2 id="cwLoopProposal" data-action-sha256="${h(action?.action_sha256||'')}">${h(heading)}</h2><p id="cwPrincipalBlocker" data-principal-blocker="${h(p.principal_blocker)}">${h(copy(p.principal_blocker))}</p><div class="cw-actions">${primary}${p.controlling_decision?`<button class="cw-text-button" type="button" data-evidence-source="${h(p.controlling_decision.evidence_item_id)}">Why this is needed</button>`:''}</div><p class="cw-note cw-safety-boundary">${h(scopedNote)}</p><p id="cwNextState" class="cw-sr-only" data-next-state="${h(JSON.stringify(p.next_state))}">${h(copy(p.next_state.title))}</p>${loop.stage_receipt?'<p class="cw-inline-notice" id="cwEvidenceStageReceipt">Evidence registered. The process update has not yet completed.</p>':''}</section>
      ${provisionalFollowupMarkup(p)}${opts.provisionalMarkup || ''}${correction(loop,{...opts,correctionPreview:opts.correctionPreview})}
      ${process(loop)}
      <section class="cw-progress-panel" id="cwEvidenceProgress"><header><strong>${provisional?'Proposed plan coverage':'Evidence coverage'}</strong><span>${resolved} of ${total} resolved</span></header><div class="cw-progress" role="progressbar" aria-label="Evidence items resolved" aria-valuemin="0" aria-valuemax="${total||1}" aria-valuenow="${resolved}" data-progress-percent="${percent}"><span style="width:${percent}%"></span></div></section>
      ${evidenceList(loop)}
      <details class="cw-section cw-secondary" id="cwRecordedActivity"><summary>Recorded activity</summary><ol class="cw-activity"><li><strong>Initial assessment saved</strong><span>Assigned process: ${h(workspace.intake_assessment?.policy_template?.title||'Recorded process')}</span></li><li><strong>Evidence review opened</strong><span>Source-bound process and evidence requirements recorded.</span></li>${s.observations.map((o,i)=>`<li><button type="button" class="cw-text-button" data-evidence-source="${h(o.evidence_item_id)}">Evidence recorded: ${h(p.evidence_items.find(e=>e.evidence_item_id===o.evidence_item_id)?.title||o.explanation)}</button><span>${h(label(o.evidence_status))} at admission. Current status is shown in the evidence list.</span></li>`).join('')}${loop.latest_correction?'<li><strong>Correction applied</strong><span>Scoped finding updated; unrelated facts preserved.</span></li>':''}<li><strong>Process and evidence checks completed</strong><span>This journal cycle recorded six deterministic checks and three gates, with no additional model call.</span></li></ol></details>
      <details class="cw-section cw-receipt" id="cwDiagnostics"><summary>Verification and receipts</summary><div class="cw-cycle-grid"><div><h4>Deterministic checks</h4><ul class="cw-receipt-list" id="cwAgentReceipts">${roles}</ul></div><div><h4>Authority gates</h4><ul class="cw-receipt-list" id="cwGateReceipts">${gates}</ul></div></div><pre>${h(JSON.stringify({loop_id:s.loop_id,revision:s.revision,state_sha256:s.state_sha256,last_event_sha256:s.last_event_sha256,audit:loop.audit},null,2))}</pre></details>`;
  }

  function sourceRecord(detail) {
    return `<aside class="cw-source-rail" aria-label="Claim sources"><section class="cw-section cw-source-inspector" id="cwSourceInspector" tabindex="-1"><div class="cw-section-heading"><h3 id="cwSourceHeading">Original customer message</h3><button type="button" class="cw-text-button" data-source-reset hidden>Show message</button></div><div id="cwSourceContent"><p class="cw-source-label">Customer account · not an established finding</p><div class="cw-message" tabindex="0" role="region" aria-label="Original customer message text" lang="${h(detail.state.binding.language)}">${h(detail.message.body)}</div></div></section><section class="cw-section" id="cwSourceRecord"><div class="cw-section-heading"><h3>Source files</h3><span>${detail.artifacts.length}</span></div><ul class="cw-file-list">${detail.artifacts.map((a,index)=>`<li><button type="button" class="cw-artifact" data-source-artifact="${index}">${icon('file')}<span class="cw-artifact-copy"><strong>${h(a.file_name)}</strong><small>${h(a.media_type)} · ${a.size_bytes<1024?a.size_bytes+' B':(a.size_bytes/1024).toFixed(1)+' KB'}</small></span>${icon('next')}</button></li>`).join('')}</ul><p class="cw-note">Source files are preserved as received. A file's presence does not establish its sufficiency.</p></section></aside>`;
  }
  function sourceArtifactIndex(ref, detail) {
    if(!ref || !detail || !/^[a-f0-9]{64}$/.test(ref.source_sha256 || '')) return -1;
    const artifacts=detail.artifacts || [];
    const direct=artifacts.findIndex(a=>a.sha256===ref.source_sha256);
    if(direct>=0) return direct;
    const messageId=detail.message?.message_id;
    const isMessageProjection=messageId
      && ref.source_id===`${messageId}.message-body-projection`
      && ref.source_version==='casepath.message-body-projection/1.0.0'
      && detail.state?.binding?.source_documents?.some(d=>d.sha256===ref.source_sha256);
    return isMessageProjection ? artifacts.findIndex(a=>a.artifact_id===messageId && a.role==='customer_message') : -1;
  }
  function evidenceSource(item, loop, detail) {
    const raw=loop.loop_state.checklist.items.find(row=>row.item_id===item.evidence_item_id);
    const linked=loop.loop_state.process.nodes.filter(n=>(raw?.node_ids||[raw?.node_id]).includes(n.node_id));
    const observations=loop.loop_state.observations.filter(o=>o.evidence_item_id===item.evidence_item_id);
    const clauses=(detail.state.intake_assessment?.policy_clause_refs||[]).filter(c=>(raw?.legal_basis_ids||[]).includes(c.clause_id));
    return `<div class="cw-source-selection"><span class="cw-evidence-status" data-class="${conflict(item)?'conflict':h(item.evidence_class)}">${h(evidenceStatus(item))}</span><h4>${h(item.title)}</h4><p><strong>Why this is needed</strong><br>${h(raw?.why === 'A bounded source observation is required for this policy step.' ? 'This step needs supporting information before it can proceed.' : raw?.why || 'No more specific reason is recorded.')}</p><p><strong>Process consequence</strong><br>${item.mandatory_now?'This is required before the current process step can proceed.':item.evidence_class==='conditional'?'Do not request it now. It becomes relevant only if its linked process step is reached.':item.evidence_class==='received'?'This evidence has been accepted for the linked step.':item.evidence_class==='irrelevant'?'This item is not needed on the current path.':'This item has not established a sufficient finding.'}</p>${linked.length?`<p class="cw-source-label">Linked step: ${h(linked.map(n=>n.title).join(' · '))}</p>`:''}
      ${observations.length?`<h4>Recorded evidence</h4>${observations.map(o=>(o.source_refs||[]).map(ref=>{
        const index=sourceArtifactIndex(ref,detail);
        return `<figure class="cw-source-passage"><blockquote><mark>${h(ref.sanitized_excerpt||o.value)}</mark></blockquote><figcaption>Recorded ${h(date(o.observed_at,true))} · current status: ${h(evidenceStatus(item))}</figcaption>${index>=0?`<button type="button" class="cw-text-button" data-source-artifact="${index}">Open original source ${icon('next')}</button>`:''}<details><summary>Exact source locator</summary><pre>${h(JSON.stringify(ref,null,2))}</pre></details></figure>`;
      }).join('')).join('')}`:'<p class="cw-no-source">No evidence has been accepted for this item. The customer message is context, not proof of this step.</p>'}
      ${clauses.length?`<h4>Supporting process rules</h4>${clauses.map(c=>`<figure class="cw-source-passage"><blockquote>${h(c.content)}</blockquote><figcaption>${h(c.clause_id)}</figcaption></figure>`).join('')}`:'<p class="cw-note">No specific rule passage is linked in this record.</p>'}</div>`;
  }
  function detail(detail, loop, opts) {
    const s=detail.state, p=loop?.operational_projection||s;
    const terminal=loop?.outcome==='decision_ready' && !loop?.operational_projection?.provisional_next_action?.enabled;
    return `<header class="cw-detail-head"><div class="cw-detail-navigation"><button class="cw-text-button" type="button" data-close-detail>${icon('back')}Claims</button><span>${h(s.claim_id)}</span><div class="cw-detail-tools"><button type="button" class="cw-text-button" data-refresh-claim aria-label="Refresh claim">${icon('refresh')}</button>${!terminal?'<button class="cw-button" id="cwExport" type="button">Export status</button>':''}</div></div><div class="cw-detail-title"><h2>${h(detail.message.subject)}</h2><p>Received ${h(date(s.binding.received_at))} · ${h(s.binding.language)} · ${h(s.owner||'Unassigned')}</p></div><section class="cw-state-strip" aria-label="Current claim state"><span>${status(p)}</span><span><small>Evidence</small><strong>${p.pending_evidence_count==null?'Not assessed':`${h(p.pending_evidence_count)} required now`}</strong></span><span><small>Last saved</small><strong>${h(date(loop?.operational_projection.last_authoritative_update||s.last_authoritative_update,true))}</strong></span><span><small>Deadline</small><strong>${s.deadline_at?h(date(s.deadline_at)):'Not recorded'}</strong></span></section></header>
      <div class="cw-detail-body"><div class="cw-work-column"><p class="cw-command-status" id="cwCommandStatus" role="status" aria-live="polite">${h(opts.commandStatus||'')}</p>${opts.workbench}
      <details class="cw-section cw-secondary" id="cwAssignment"><summary>Handler assignment${s.owner?` · ${h(s.owner)}`:''}</summary><form class="cw-owner-form" id="cwOwnerForm"><input id="cwOwnerInput" maxlength="80" value="${h(opts.ownerValue)}" placeholder="Handler name" aria-label="Assigned handler" ${opts.ownerReadonly?'readonly':''}><button class="cw-button" type="submit" ${opts.ownerDisabled?'disabled':''}>${opts.pendingAssign?'Recover assignment':'Save assignment'}</button></form></details>
      <details class="cw-section cw-secondary" id="cwExplainablePriority"><summary>Why this queue position?</summary><p class="cw-status" data-priority-status ${opts.priority?'hidden':''}>Loading saved priority…</p><ol class="cw-priority">${opts.priorityMarkup||''}</ol></details>
      <details class="cw-section cw-secondary" id="cwSavedInvestigation"><summary>Saved source investigation</summary><div id="cwEvidenceInvestigationMount"><p class="cw-note">An optional saved investigation is separate from this evidence review.</p><button type="button" class="cw-button" data-load-investigation>Load saved investigation</button></div></details>
      <details class="cw-section cw-receipt" id="cwWorkspaceReceipt"><summary>Workspace provenance</summary><pre>${h(JSON.stringify({detail_sha256:detail.detail_sha256,state_sha256:s.state_sha256,revision:s.revision,last_event_sha256:s.last_event_sha256},null,2))}</pre></details></div>${sourceRecord(detail)}</div>`;
  }
  return Object.freeze({h,label,copy,icon,date,readiness,evidenceStatus,tone,status,shell,queueRows,skeleton,workbench,detail,sourceRecord,evidenceSource,compareLoops,changeMarkup,semanticText,sourceArtifactIndex,provisionalFollowupMarkup});
});
