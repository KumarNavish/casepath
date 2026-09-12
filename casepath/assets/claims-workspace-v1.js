(() => {
  'use strict';

  const SAFE_REJECTION_COPY = 'Evidence was safely rejected; no observation was added. CasePath kept the bounded action open.';
  const ADMITTED_ADVANCE_COPY = Object.freeze({
    next_action: 'Observation committed once. CasePath verified the next bounded action.',
    decision_ready: 'Observation committed once. Three deterministic gates certified the decision packet.',
    abstain: 'Observation committed once. CasePath abstained safely rather than infer unsupported facts.',
  });
  const NATIVE_INQUIRY_MODE_HEADER = 'X-CasePath-Native-Research-Mode';
  const NATIVE_INQUIRY_MODE = 'current-public-corpus-provisional-v1';
  const NATIVE_NEED_STATES = Object.freeze({
    missing:'Missing',
    partial:'Partly answered',
    pending:'Expected',
    received:'Received',
    contested:'Conflicting records',
    conditional:'Depends on another fact',
    withdrawn:'Withdrawn',
    uncertain:'Uncertain',
  });
  const NATIVE_EVIDENCE_ROLES = new Set(['support','contrary','correction','context']);
  const inquiryRecord = value => Boolean(value && typeof value === 'object' && !Array.isArray(value));
  const inquiryText = value => typeof value === 'string' && value.trim() ? value : null;
  const inquiryEsc = value => String(value ?? '').replace(/[&<>'"]/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));
  const inquiryCanonical = value => {
    if (value === null || typeof value !== 'object') return JSON.stringify(value);
    if (Array.isArray(value)) return `[${value.map(inquiryCanonical).join(',')}]`;
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${inquiryCanonical(value[key])}`).join(',')}}`;
  };
  const inquiryStamp = value => {
    try {
      const instant = new Date(value);
      if (!Number.isFinite(instant.valueOf())) return null;
      return new Intl.DateTimeFormat(undefined, {dateStyle:'medium',timeStyle:'short'}).format(instant);
    } catch (_) { return null; }
  };

  function nativePointer(value, {role = null} = {}) {
    if (
      !inquiryRecord(value)
      || !/^[tp][0-9]+$/.test(value.ref || '')
      || !['text','native_image'].includes(value.kind)
      || !inquiryText(value.source_id)
      || !inquiryText(value.view_id)
      || !inquiryStamp(value.first_observed_at)
      || (role !== null && value.role !== role)
    ) return null;
    return {
      ref:value.ref,
      kind:value.kind,
      sourceId:value.source_id,
      viewId:value.view_id,
      firstObservedAt:value.first_observed_at,
      text:value.kind === 'text' && typeof value.text === 'string' ? value.text : null,
      ...(value.page_index === null || Number.isSafeInteger(value.page_index) ? {pageIndex:value.page_index} : {}),
      ...(role === null ? {} : {role}),
    };
  }

  function nativeNeed(proposalNeed, actorNeed) {
    if (
      !inquiryRecord(proposalNeed)
      || !inquiryRecord(actorNeed)
      || !inquiryText(proposalNeed.need_id)
      || proposalNeed.need_id !== actorNeed.need_id
      || !inquiryText(proposalNeed.description)
      || proposalNeed.description !== actorNeed.description
      || !Object.hasOwn(NATIVE_NEED_STATES, proposalNeed.state)
      || proposalNeed.state !== actorNeed.state
      || (proposalNeed.answer !== null && typeof proposalNeed.answer !== 'string')
      || proposalNeed.answer !== actorNeed.answer
      || (proposalNeed.until !== null && (!inquiryText(proposalNeed.until) || !inquiryStamp(proposalNeed.until)))
      || proposalNeed.until !== actorNeed.until
      || !Array.isArray(proposalNeed.warrants)
      || !proposalNeed.warrants.length
      || !Array.isArray(proposalNeed.evidence)
      || !Array.isArray(actorNeed.warrant_refs)
      || !Array.isArray(actorNeed.evidence)
    ) return null;
    const warrants = proposalNeed.warrants.map(value => nativePointer(value));
    const evidence = proposalNeed.evidence.map(value => NATIVE_EVIDENCE_ROLES.has(value?.role) ? nativePointer(value, {role:value.role}) : null);
    if (warrants.includes(null) || evidence.includes(null)) return null;
    if (inquiryCanonical(actorNeed.warrant_refs) !== inquiryCanonical(warrants.map(value => value.ref))) return null;
    if (inquiryCanonical(actorNeed.evidence) !== inquiryCanonical(evidence.map(value => ({ref:value.ref,role:value.role})))) return null;
    return {
      needId:proposalNeed.need_id,
      description:proposalNeed.description,
      answer:proposalNeed.answer,
      state:proposalNeed.state,
      until:proposalNeed.until,
      warrants,
      evidence,
    };
  }

  function unavailableInvestigation(message = 'No usable investigation result is available.') {
    return {kind:'unavailable', message};
  }

  function buildEvidenceInvestigationView(value, claimId) {
    if (
      !inquiryRecord(value)
      || value.contract !== 'casepath.native-live-workspace-state/1.0.0'
      || value.claim_id !== claimId
      || !Number.isSafeInteger(value.completed_cycle_count)
      || value.completed_cycle_count < 0
      || !Array.isArray(value.unresolved_cycle_keys)
      || !inquiryRecord(value.canonical_facts)
      || Object.keys(value.canonical_facts).length
      || value.certified_readiness !== null
      || value.customer_send !== false
    ) return unavailableInvestigation();
    if (value.latest_cycle === null) {
      return {kind:'empty', message:'No evidence investigation has been recorded for this claim.'};
    }
    const latest = value.latest_cycle;
    const proposal = latest?.provisional_proposal;
    const actorOutput = latest?.actor_output;
    const observedLabel = inquiryStamp(latest?.observed_at);
    if (
      !inquiryRecord(latest)
      || latest.contract !== 'casepath.native-live-workspace-cycle/1.0.0'
      || latest.claim_id !== claimId
      || !inquiryText(latest.cycle_id)
      || latest.qualified !== true
      || latest.status !== 'completed_qualified'
      || latest.transport_receipt?.qualified !== true
      || !inquiryRecord(latest.canonical_facts)
      || Object.keys(latest.canonical_facts).length
      || latest.certified_readiness !== null
      || latest.customer_send !== false
      || !observedLabel
      || !inquiryRecord(actorOutput)
      || !Array.isArray(actorOutput.needs)
      || !inquiryRecord(proposal)
      || proposal.contract !== 'casepath.native-live-provisional-proposal/1.0.0'
      || proposal.observed_at !== latest.observed_at
      || proposal.input_identity !== latest.input_identity
      || proposal.source_prefix_sha256 !== latest.source_prefix_sha256
      || !/^[0-9a-f]{64}$/.test(latest.input_identity || '')
      || !/^[0-9a-f]{64}$/.test(latest.source_prefix_sha256 || '')
      || proposal.authority !== 'FALLIBLE_MODEL_PROPOSAL_OVER_ADMITTED_SOURCE_BYTES'
      || proposal.canonical_fact_effect !== null
      || proposal.readiness_effect !== null
      || proposal.customer_send !== false
      || !/^[0-9a-f]{64}$/.test(proposal.proposal_sha256 || '')
      || !Array.isArray(proposal.needs)
      || proposal.needs.length !== actorOutput.needs.length
    ) return unavailableInvestigation('The latest investigation did not produce a usable result.');
    const needs = proposal.needs.map((row, index) => nativeNeed(row, actorOutput.needs[index]));
    if (needs.includes(null) || new Set(needs.map(row => row.needId)).size !== needs.length) return unavailableInvestigation();
    const transport = latest.transport_receipt;
    const cost = latest.cost_receipt;
    if (!inquiryRecord(transport) || !inquiryRecord(cost) || transport.qualified !== true) {
      return unavailableInvestigation('The latest investigation has no qualified provider receipt.');
    }
    let providerQualification;
    if (transport.transport_kind === 'openrouter_http_once') {
      if (
        transport.provider_identity?.model !== 'openai/gpt-5.4-mini'
        || transport.provider_identity?.provider !== 'OpenAI'
        || transport.provider_identity?.finish_reason !== 'stop'
        || transport.trace?.request_count !== 1
        || transport.trace?.cost_known !== true
        || transport.trace?.cost_within_call_bound !== true
        || transport.usage_complete !== true
        || !Number.isFinite(transport.actual_cost_usd)
        || transport.actual_cost_usd < 0
        || cost.model !== 'openai/gpt-5.4-mini'
        || cost.reasoning_effort !== 'low'
        || cost.billable_cost_usd !== transport.actual_cost_usd
        || cost.cost_status !== 'PROVIDER_REPORTED'
      ) return unavailableInvestigation('The latest provider receipt failed validation.');
      providerQualification = {
        kind:'openrouter',
        model:transport.provider_identity.model,
        provider:transport.provider_identity.provider,
        inputTokens:transport.usage.input_tokens,
        cachedInputTokens:transport.usage.cached_input_tokens,
        outputTokens:transport.usage.output_tokens,
        reasoningTokens:transport.usage.reasoning_output_tokens,
        costUsd:transport.actual_cost_usd,
      };
    } else {
      providerQualification = {
        kind:'legacy-recorded',
        model:cost.model || 'Recorded reader',
        provider:'Recorded transport',
        inputTokens:transport.usage?.input_tokens ?? null,
        cachedInputTokens:transport.usage?.cached_input_tokens ?? null,
        outputTokens:transport.usage?.output_tokens ?? null,
        reasoningTokens:transport.usage?.reasoning_output_tokens ?? null,
        costUsd:cost.billable_cost_usd ?? null,
      };
    }

    const rawRequests = actorOutput.requests === undefined ? [] : actorOutput.requests;
    if (!Array.isArray(rawRequests)) return unavailableInvestigation();
    const exportState = value.export_state;
    if (exportState !== null && (
      !inquiryRecord(exportState)
      || exportState.contract !== 'casepath.native-live-export-state/1.0.0'
      || exportState.configured !== true
      || !Array.isArray(exportState.available_channels)
      || !Array.isArray(exportState.actions)
      || !Array.isArray(exportState.source_admissions)
      || inquiryCanonical(exportState.current_output) !== inquiryCanonical(actorOutput)
    )) return unavailableInvestigation();
    if (exportState === null && rawRequests.length) return unavailableInvestigation();
    if (exportState !== null && actorOutput.requests === undefined) return unavailableInvestigation();
    const channels = new Map();
    for (const row of exportState?.available_channels || []) {
      if (!inquiryRecord(row) || !inquiryText(row.channel_id) || !inquiryText(row.description) || channels.has(row.channel_id)) return unavailableInvestigation();
      channels.set(row.channel_id, row.description);
    }
    const needIds = new Set(needs.map(row => row.needId));
    const requests = [];
    for (const row of rawRequests) {
      if (
        !inquiryRecord(row)
        || !channels.has(row.channel_id)
        || !Array.isArray(row.need_ids)
        || !row.need_ids.length
        || row.need_ids.some(id => !needIds.has(id))
        || !inquiryText(row.purpose)
      ) return unavailableInvestigation();
      requests.push({
        channelId:row.channel_id,
        channel:channels.get(row.channel_id),
        needIds:[...row.need_ids],
        needLabels:row.need_ids.map(id => needs.find(need => need.needId === id).description),
        purpose:row.purpose,
      });
    }

    const exportReceipts = (exportState?.source_admissions || []).filter(row => row?.kind === 'export');
    const outcomes = [];
    for (const [index, row] of (exportState?.actions || []).entries()) {
      const receipt = exportReceipts[index];
      if (
        !inquiryRecord(row)
        || !['exported','unavailable'].includes(row.status)
        || !channels.has(row.channel_id)
        || !Array.isArray(row.need_ids)
        || row.need_ids.some(id => !inquiryText(id))
        || !inquiryText(row.purpose)
        || !inquiryText(row.source_id)
        || !/^[0-9a-f]{64}$/.test(row.sha256 || '')
        || !inquiryRecord(receipt)
        || receipt.status !== row.status
        || receipt.source_id !== row.source_id
        || receipt.sha256 !== row.sha256
        || !inquiryStamp(receipt.observed_at)
      ) return unavailableInvestigation();
      outcomes.push({
        status:row.status,
        channelId:row.channel_id,
        channel:channels.get(row.channel_id),
        needIds:[...row.need_ids],
        purpose:row.purpose,
        sourceId:row.source_id,
        sha256:row.sha256,
        observedAt:receipt.observed_at,
      });
    }
    return {
      kind:'qualified',
      cycleId:latest.cycle_id,
      observedAt:latest.observed_at,
      observedLabel,
      providerQualification,
      needs,
      requests,
      outcomes,
      hasNewerPendingAttempt:value.unresolved_cycle_keys.length > 0,
    };
  }

  function pointerMarkup(pointer, prefix) {
    const page = Number.isSafeInteger(pointer.pageIndex) ? ` · page ${pointer.pageIndex + 1}` : '';
    const sourceText = pointer.text === null ? '' : `<blockquote class="cw-investigation-source-text">${inquiryEsc(pointer.text)}</blockquote>`;
    return `<li><strong>${inquiryEsc(prefix)} ${inquiryEsc(pointer.ref)}</strong><span>${inquiryEsc(pointer.sourceId)} · ${inquiryEsc(pointer.viewId)}${inquiryEsc(page)}</span>${sourceText}</li>`;
  }

  function evidenceInvestigationMarkup(view, loop = null) {
    if (!view) return '';
    if (view.kind !== 'qualified') return `<section class="cw-section cw-investigation cw-investigation-empty" id="cwEvidenceInvestigation"><p class="cw-eyebrow">Evidence investigation</p><h2>Source review</h2><p class="cw-status">${inquiryEsc(view.message)}</p>${view.kind === 'empty' ? '<div class="cw-actions"><button class="cw-button cw-button-primary" id="cwNativeInvestigate" type="button">Investigate admitted sources</button></div>' : ''}</section>`;
    const nativeRoster = loop?.loop_state?.accepted_artifacts?.observable_package?.native_need_roster;
    const rosterRows = Array.isArray(nativeRoster) ? nativeRoster : [];
    const rosterByNeed = new Map(rosterRows.map(row => [row.need_id, row]));
    const activeFactId = loop?.loop_state?.selected_action?.fact_id || null;
    const observedFactIds = new Set((loop?.loop_state?.observations || []).map(row => row.fact_id));
    const correctedFactIds = new Set(loop?.latest_correction?.fact_id ? [loop.latest_correction.fact_id] : []);
    const admittedNeedIds = new Set(rosterRows.filter(row => observedFactIds.has(row.fact_id)).map(row => row.need_id));
    const outsidePlanCount = view.needs.filter(row => !rosterByNeed.has(row.needId)).length;
    const journalSummary = loop
      ? `<p class="cw-investigation-note" data-native-admission-summary="${inquiryEsc(`${admittedNeedIds.size}/${rosterRows.length}/${outsidePlanCount}`)}"><strong>Shared journal:</strong> ${inquiryEsc(admittedNeedIds.size)} of ${inquiryEsc(rosterRows.length)} initial proposed inquiries admitted.${outsidePlanCount ? ` ${inquiryEsc(outsidePlanCount)} newer proposed ${outsidePlanCount === 1 ? 'inquiry remains' : 'inquiries remain'} outside that fixed plan.` : ''}</p>`
      : '<p class="cw-investigation-note">No reader proposal has entered the shared evidence journal.</p>';
    const needs = view.needs.length ? view.needs.map(row => {
      const references = [
        ...row.warrants.map(pointer => pointerMarkup(pointer, 'Need basis')),
        ...row.evidence.map(pointer => pointerMarkup(pointer, `Record ${pointer.role}`)),
      ].join('');
      const answer = row.answer === null ? 'No supported answer yet.' : row.answer;
      const until = row.until ? `<small>Expected by ${inquiryEsc(inquiryStamp(row.until) || row.until)}</small>` : '';
      const roster = rosterByNeed.get(row.needId);
      const correctionApplied = Boolean(roster && correctedFactIds.has(roster.fact_id));
      const canObserve = Boolean(roster && roster.fact_id === activeFactId && row.answer && row.evidence.length);
      const canCorrect = Boolean(roster && !correctionApplied && observedFactIds.has(roster.fact_id) && row.evidence.some(ref => ref.role === 'correction'));
      const journalState = !roster
        ? 'New reader proposal · outside the current journal plan'
        : admittedNeedIds.has(row.needId)
          ? correctionApplied ? 'Admitted source-relative answer · later source extension applied' : 'Admitted source-relative answer'
          : roster.fact_id === activeFactId
            ? 'Current inquiry · not yet admitted'
            : 'Initial plan inquiry · not yet admitted';
      const correctionBoundary = row.evidence.some(ref => ref.role === 'correction')
        ? correctionApplied
          ? '<small>The journal bound this later source extension to one earlier admitted assertion; sibling observations remain unchanged.</small>'
          : '<small>A correction remains provisional until the server binds it to an earlier admitted assertion.</small>'
        : '';
      const actions = [
        canObserve ? `<button class="cw-button cw-button-primary" type="button" data-native-operation="observe" data-native-need-id="${inquiryEsc(row.needId)}">Admit source answer</button>` : '',
        canCorrect ? `<button class="cw-button" type="button" data-native-operation="correct" data-native-need-id="${inquiryEsc(row.needId)}">Validate scoped correction</button>` : '',
      ].filter(Boolean).join('');
      return `<article class="cw-investigation-need"><header><h3>${inquiryEsc(row.description)}</h3><span data-native-need-state="${inquiryEsc(row.state)}">Reader: ${inquiryEsc(NATIVE_NEED_STATES[row.state])}</span></header><p class="cw-investigation-note"><strong>Journal:</strong> ${inquiryEsc(journalState)}</p><p>${inquiryEsc(answer)}</p>${until}${correctionBoundary}<details><summary>Source references</summary><ul>${references}</ul></details>${actions ? `<div class="cw-actions">${actions}</div>` : ''}</article>`;
    }).join('') : '<p class="cw-muted">The review found no current information needs.</p>';
    const requests = view.requests.length ? `<div class="cw-investigation-subsection"><h3>Suggested follow-ups</h3><ul>${view.requests.map(row => `<li><strong>${inquiryEsc(row.channel)}</strong><span>${inquiryEsc(row.purpose)}</span><small>For ${inquiryEsc(row.needLabels.join('; '))}</small></li>`).join('')}</ul></div>` : '';
    const outcomes = view.outcomes.length ? `<div class="cw-investigation-subsection"><h3>Returns and availability</h3><ul>${view.outcomes.map(row => `<li><strong>${row.status === 'exported' ? 'Record returned' : 'Unavailable'} · ${inquiryEsc(row.channel)}</strong><span>${inquiryEsc(row.purpose)}</span><small>${inquiryEsc(inquiryStamp(row.observedAt) || row.observedAt)}</small><details><summary>Return provenance</summary><dl><div><dt>Source</dt><dd>${inquiryEsc(row.sourceId)}</dd></div><div><dt>SHA-256</dt><dd><code>${inquiryEsc(row.sha256)}</code></dd></div><div><dt>Channel ID</dt><dd>${inquiryEsc(row.channelId)}</dd></div></dl></details></li>`).join('')}</ul></div>` : '';
    const pending = view.hasNewerPendingAttempt ? '<p class="cw-investigation-note">A newer review is still being reconciled. This is the latest completed result.</p>' : '';
    const qualification = view.providerQualification;
    const qualificationCopy = qualification.kind === 'openrouter'
      ? `${inquiryEsc(qualification.model)} via ${inquiryEsc(qualification.provider)} · ${inquiryEsc(qualification.inputTokens)} input / ${inquiryEsc(qualification.outputTokens)} output tokens · $${inquiryEsc(Number(qualification.costUsd).toFixed(4))}`
      : `${inquiryEsc(qualification.model)} · recorded transport metrics`;
    const planAction = loop ? '<button class="cw-button" id="cwNativeInvestigate" type="button">Re-read admitted sources</button>' : '<button class="cw-button cw-button-primary" id="cwNativeEnsure" type="button">Open provisional plan in evidence journal</button>';
    return `<section class="cw-section cw-investigation" id="cwEvidenceInvestigation"><p class="cw-eyebrow">Evidence investigation</p><div class="cw-investigation-heading"><h2>Latest source review</h2><time>${inquiryEsc(view.observedLabel)}</time></div><p class="cw-status">This source review is a fallible proposal. Answers enter the claim journal only through the source admission controls below.</p><p class="cw-verified-line" data-native-provider-kind="${inquiryEsc(qualification.kind)}">Qualified provider call: ${qualificationCopy}</p>${journalSummary}${pending}<div class="cw-investigation-needs">${needs}</div>${requests}${outcomes}<div class="cw-actions">${planAction}</div></section>`;
  }

  function claimLoopAdvanceStatus({
    beforeRevision,
    afterRevision,
    beforeObservationCount,
    afterObservationCount,
    outcome,
  }) {
    if (
      !Number.isSafeInteger(beforeRevision)
      || !Number.isSafeInteger(afterRevision)
      || !Number.isSafeInteger(beforeObservationCount)
      || !Number.isSafeInteger(afterObservationCount)
      || beforeRevision < 0
      || beforeObservationCount < 0
      || afterObservationCount < 0
      || afterRevision !== beforeRevision + 2
    ) throw new Error('The authoritative replan did not advance by exactly two journal revisions');
    const observationDelta = afterObservationCount - beforeObservationCount;
    if (observationDelta === 0) {
      if (outcome !== 'next_action') throw new Error('A rejected proposal did not preserve the bounded next action');
      return Object.freeze({kind:'safely_rejected', observationDelta, copy:SAFE_REJECTION_COPY});
    }
    if (observationDelta !== 1 || !Object.hasOwn(ADMITTED_ADVANCE_COPY, outcome)) {
      throw new Error('The authoritative observation delta is outside the closed advance contract');
    }
    return Object.freeze({kind:'observation_admitted', observationDelta, copy:ADMITTED_ADVANCE_COPY[outcome]});
  }

  function claimLoopStateHashMaterials(value) {
    if (!inquiryRecord(value) || !Array.isArray(value.native_proposal_revisions)) return [];
    const material = Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'state_sha256'));
    const revisions = material.native_proposal_revisions;
    if (revisions.length === 0) {
      delete material.native_proposal_revisions;
      return [material];
    }
    const candidates = [material];
    if (revisions.every(revision => inquiryRecord(revision)
      && Array.isArray(revision.readings)
      && revision.readings.every(inquiryRecord))) {
      candidates.push({
        ...material,
        native_proposal_revisions: revisions.map(revision => ({
          ...revision,
          readings: revision.readings.map(reading => Object.fromEntries(
            Object.entries(reading).filter(([key, item]) => key !== 'until' || item !== null),
          )),
        })),
      });
    }
    return candidates;
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      claimLoopAdvanceStatus,
      claimLoopStateHashMaterials,
      SAFE_REJECTION_COPY,
      ADMITTED_ADVANCE_COPY,
      NATIVE_INQUIRY_MODE_HEADER,
      NATIVE_INQUIRY_MODE,
      buildEvidenceInvestigationView,
      evidenceInvestigationMarkup,
    };
    return;
  }

  if (location.protocol === 'file:') return;

  const params = new URLSearchParams(location.search);
  if (
    params.get('foundation') === 'live-v1'
    || ['legacy-v20', 'insurance-v1'].includes(params.get('journey'))
  ) return;

  document.documentElement.dataset.claimsWorkspace = 'true';

  const api = location.origin;
  const state = {
    cursor: null,
    items: [],
    total: 0,
    detail: null,
    detailPriority: null,
    loading: false,
    queuedLoad: null,
    filterTimer: null,
    returnFocus: null,
    returnClaimId: null,
    loop: null,
    detailEpoch: 0,
    detailController: null,
    mutationBusy: null,
    correctionPreview: null,
    nativeInvestigation: null,
  };
  const EXPECTED_AGENT_IDS = ['canonical_facts','orchestrator_plan','document_source_integrity','process_decision_mapping','evidence_checklist','final_claim_brief_audit'];
  const EXPECTED_GATE_IDS = ['deterministic_process_gate','deterministic_evidence_gate','whole_playbook_gate'];
  const REGISTRATION_BODY_FIELDS = ['schema','action_id','expected_revision','idempotency_key','acquisition_intent_id','acquisition_receipt_id','content_b64'];
  const REGISTRATION_RECEIPT_FIELDS = ['action_id','action_sha256','acquisition_intent_id','acquisition_receipt_id','adapter_artifact_sha256','adapter_id','byte_end','byte_start','channel','claim_id','content_length','content_sha256','contract','evidence_item_id','freshness_nonce','idempotency_key','intent_receipt_sha256','loop_id','media_sniffer_id','media_sniffer_sha256','parent_revision','parent_state_sha256','receipt_sha256','record_version','registered_at','server_sniffed_media_type','session_id','source_acquisition_receipt_sha256','source_entry_sha256'];

  const root = document.createElement('div');
  root.id = 'claimsWorkspace';
  root.innerHTML = `
    <div class="cw-shell">
      <header class="cw-topbar">
        <div class="cw-brand"><span class="cw-mark">CP</span><span>CasePath</span></div>
        <div class="cw-topbar-title"><strong>Claims workspace</strong><span>Journal-backed readiness and the safest next action</span></div>
        <button class="cw-button" id="cwRefresh" type="button">Refresh</button>
      </header>
      <main class="cw-main">
        <section class="cw-hero">
          <div><p class="cw-eyebrow">Active work</p><h1>Know what blocks every claim.</h1><p>Open the source record, see the honest readiness state, and take only a bounded, replayable action. Unknown values stay unknown until evidence supports them.</p></div>
          <div class="cw-summary"><strong id="cwTotal">—</strong><span>claims in view</span></div>
        </section>
        <section class="cw-filter-card" aria-label="Claims filters">
          <form class="cw-filters" id="cwFilters">
            <div class="cw-field"><label for="cwSearch">Search</label><input id="cwSearch" type="search" placeholder="Claim ID, subject, or owner" autocomplete="off"></div>
            <div class="cw-field"><label for="cwState">State</label><select id="cwState"><option value="">All states</option><option value="received">Received</option><option value="in_review">In review</option><option value="waiting">Waiting</option><option value="waiting_for_evidence">Waiting for evidence</option><option value="dispatching">Dispatching</option><option value="decision_ready">Decision ready</option><option value="safe_abstention">Safe abstention</option><option value="failed">Failed</option></select></div>
            <div class="cw-field"><label for="cwReadiness">Readiness</label><select id="cwReadiness"><option value="">All readiness</option><option value="not_assessed">Not assessed</option><option value="blocked">Blocked</option><option value="decision_ready">Decision ready</option><option value="safe_abstention">Safe abstention</option></select></div>
            <div class="cw-field"><label for="cwSort">Sort</label><select id="cwSort"><option value="priority">Explainable priority</option><option value="urgency">Urgency</option><option value="oldest_waiting">Oldest waiting</option><option value="nearest_deadline">Nearest deadline</option><option value="most_decision_ready">Most decision-ready</option><option value="latest_update">Latest update</option></select></div>
            <details class="cw-advanced-filters"><summary>More filters</summary><div class="cw-advanced-filter-grid">
              <div class="cw-field"><label for="cwClaimType">Claim type</label><select id="cwClaimType"><option value="">All claim types</option><option value="unclassified_intake">Unclassified intake</option></select></div>
              <div class="cw-field"><label for="cwOwner">Owner</label><select id="cwOwner"><option value="">All owners</option><option value="unassigned">Unassigned</option></select></div>
              <div class="cw-field"><label for="cwUrgency">Urgency</label><select id="cwUrgency"><option value="">All urgency</option><option value="high">High</option><option value="elevated">Elevated</option><option value="normal">Normal</option></select></div>
              <div class="cw-field"><label for="cwFailure">Effects</label><select id="cwFailure"><option value="">All effect states</option><option value="true">Failed or unknown</option><option value="false">No unknown effect</option></select></div>
              <div class="cw-field"><label for="cwPendingEvidence">Pending evidence</label><select id="cwPendingEvidence"><option value="">All evidence states</option><option value="unknown">Not assessed</option><option value="none">None pending</option><option value="some">Evidence pending</option></select></div>
            </div></details>
          </form>
        </section>
        <section class="cw-table-card" aria-live="polite">
          <div id="cwTable"></div>
          <div class="cw-table-foot"><span id="cwPageStatus">Loading claims…</span><button class="cw-button" id="cwMore" type="button" hidden>Load more</button></div>
        </section>
      </main>
    </div>
    <section class="cw-detail" id="cwDetail" hidden aria-label="Claim workbench" aria-modal="true" role="dialog">
      <div class="cw-detail-scrim" data-close-detail></div><article class="cw-detail-panel" id="cwDetailPanel" tabindex="-1"></article>
    </section>`;
  document.body.appendChild(root);

  const $ = selector => root.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[character]));
  const label = value => String(value ?? 'unknown').replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase());
  const bytes = value => value < 1024 ? `${value} B` : `${(value / 1024).toFixed(1)} KB`;
  const stamp = value => {
    try { return new Intl.DateTimeFormat(undefined, {dateStyle:'medium',timeStyle:'short'}).format(new Date(value)); }
    catch (_) { return value; }
  };
  const commandKey = prefix => `${prefix}-${crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`}`;
  const commandSlot = (kind, claimId) => `casepath:workspace-command:${claimId}:${kind}`;

  function storedCommandIdentity(kind, claimId) {
    const raw = sessionStorage.getItem(commandSlot(kind, claimId));
    if (!raw) return null;
    try {
      const value = JSON.parse(raw);
      const body = JSON.parse(value.body);
      if (!value || typeof value !== 'object' || typeof value.key !== 'string' || value.key.length < 8 || typeof value.body !== 'string' || !body || typeof body !== 'object' || Array.isArray(body)) throw new Error('invalid');
      return {...value, parsedBody: body};
    } catch (_) {
      return {invalid: true};
    }
  }

  const canonicalJson = value => {
    if (value === null || typeof value !== 'object') return JSON.stringify(value);
    if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`;
  };
  const CLAIM_LOOP_FLOAT_FIELDS = new Set(['confidence', 'cost_usd']);
  const claimLoopCanonicalJson = (value, field = null) => {
    if (value === null || typeof value !== 'object') {
      if (typeof value === 'number' && Number.isInteger(value) && CLAIM_LOOP_FLOAT_FIELDS.has(field)) return value.toFixed(1);
      return JSON.stringify(value);
    }
    if (Array.isArray(value)) return `[${value.map(item => claimLoopCanonicalJson(item)).join(',')}]`;
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${claimLoopCanonicalJson(value[key], key)}`).join(',')}}`;
  };
  const sha256 = async value => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonicalJson(value))))].map(byte => byte.toString(16).padStart(2, '0')).join('');
  const claimLoopSha256 = async value => [...new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(claimLoopCanonicalJson(value))))].map(byte => byte.toString(16).padStart(2, '0')).join('');
  const validClaimLoopStateHash = async value => {
    if (!value || !/^[0-9a-f]{64}$/.test(value.state_sha256 || '')) return false;
    for (const material of claimLoopStateHashMaterials(value)) {
      if (value.state_sha256 === await claimLoopSha256(material)) return true;
    }
    return false;
  };

  function commandIdentity(kind, claimId, body, fixedKey = null, metadata = null) {
    const slot = commandSlot(kind, claimId);
    const bodyJson = JSON.stringify(body);
    const stored = storedCommandIdentity(kind, claimId);
    if (stored) {
      if (stored.invalid) throw new Error('The pending command identity is corrupt. Reload the authoritative claim state before taking another action.');
      if (canonicalJson(stored.parsedBody) !== canonicalJson(body)) throw new Error(`Resolve the pending ${kind} command before submitting different input.`);
      const {parsedBody: _parsedBody, ...identity} = stored;
      return {...identity, resumed: true};
    }
    if (metadata !== null && (!metadata || typeof metadata !== 'object' || Array.isArray(metadata) || 'key' in metadata || 'body' in metadata)) {
      throw new Error('Pending command metadata is invalid');
    }
    const value = {key: fixedKey || commandKey(kind), body: bodyJson, ...(metadata || {})};
    sessionStorage.setItem(slot, JSON.stringify(value));
    return value;
  }

  function clearCommandIdentity(kind, claimId) {
    sessionStorage.removeItem(commandSlot(kind, claimId));
  }

  function activeDetailContext() {
    return state.detail ? { epoch: state.detailEpoch, claimId: state.detail.state.claim_id } : null;
  }

  function isActiveDetail(context) {
    return Boolean(context && context.epoch === state.detailEpoch && state.detail?.state?.claim_id === context.claimId && !$('#cwDetail').hidden);
  }

  const base64Bytes = value => {
    if (typeof value !== 'string' || !value) throw new Error('Acquired source base64 is empty');
    let binary;
    try { binary = atob(value); }
    catch (_) { throw new Error('Acquired source base64 is invalid'); }
    const decoded = Uint8Array.from(binary, character => character.charCodeAt(0));
    if (btoa(binary) !== value) throw new Error('Acquired source base64 is not canonical');
    return decoded;
  };
  const sha256Bytes = async value => [...new Uint8Array(await crypto.subtle.digest('SHA-256', value))].map(byte => byte.toString(16).padStart(2, '0')).join('');

  async function validateState(value, claimId) {
    if (!value || typeof value !== 'object' || Array.isArray(value) || value.contract !== 'casepath.claim-workspace-state/1.0.0' || value.claim_id !== claimId || !/^[0-9a-f]{64}$/.test(value.state_sha256 || '') || !/^[0-9a-f]{64}$/.test(value.last_event_sha256 || '') || value.state_sha256 !== await sha256(Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'state_sha256')))) {
      throw new Error('The authoritative claim state failed validation');
    }
    return value;
  }

  async function validateDetailResponse(value, claimId) {
    const expectedKeys = ['artifacts','authority','contract','detail_sha256','message','state'];
    if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).sort().join('|') !== expectedKeys.join('|') || value.contract !== 'casepath.claim-workspace-detail/1.0.0' || value.authority !== 'claim_loop_events' || !/^[0-9a-f]{64}$/.test(value.detail_sha256 || '')) {
      throw new Error('The server returned an invalid authoritative claim detail');
    }
    await validateState(value.state, claimId);
    const material = Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'detail_sha256'));
    if (value.detail_sha256 !== await sha256(material)) throw new Error('The authoritative claim detail failed hash verification');
    return value;
  }

  async function validateMutationResponse(value, claimId, expectedEventType, priorState) {
    const expectedKeys = ['contract','event_sha256','event_type','idempotency_scope','response_sha256','state'];
    if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).sort().join('|') !== expectedKeys.join('|') || value.contract !== 'casepath.claim-workspace-command-response/1.0.0' || value.event_type !== expectedEventType || value.idempotency_scope !== 'workspace_event' || value.state?.claim_id !== claimId || !/^[0-9a-f]{64}$/.test(value.event_sha256 || '') || !/^[0-9a-f]{64}$/.test(value.response_sha256 || '')) {
      const error = new Error('The server returned an invalid command receipt');
      error.ambiguousResponse = true;
      throw error;
    }
    try { await validateState(value.state, claimId); }
    catch (cause) {
      const error = new Error(cause.message);
      error.ambiguousResponse = true;
      throw error;
    }
    const responseMaterial = Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'response_sha256'));
    if (value.response_sha256 !== await sha256(responseMaterial) || value.state.last_event_sha256 !== value.event_sha256 || value.state.revision !== priorState.revision + 1 || value.state.binding?.binding_sha256 !== priorState.binding?.binding_sha256) {
      const error = new Error('The server command receipt failed hash verification');
      error.ambiguousResponse = true;
      throw error;
    }
    return value;
  }

  async function validateOperationalProjection(value, claimId, workspaceState = null, loopState = null) {
    const keys = ['claim_id','claim_loop_prefix','contract','controlling_decision','current_process','evidence_class_counts','evidence_items','failure_or_unknown_effect','last_authoritative_update','next_state','pending_evidence_count','principal_blocker','projection_sha256','provisional_next_action','readiness_scope','readiness_state','workflow_state','workspace_prefix'];
    const prefixKeys = ['last_event_at','last_event_sha256','loop_id','revision','state_sha256'];
    const loopPrefixKeys = ['last_event_at','last_event_sha256','loop_id','phase','revision','state_sha256'];
    const processKeys = ['next_action_node_id','node_id','node_title','overlay_sha256','selected_branch_id'];
    const nextKeys = ['action_id','action_sha256','kind','terminal_mode','title'];
    const evidenceKeys = ['current_path','evidence_class','evidence_item_id','fact_id','fact_state','mandatory_now','obligation_status','provenance_edge_sha256s','raw_status','source_ref_ids','title'];
    const classes = ['received','missing','insufficient','conditional','irrelevant','unknown'];
    if (
      !value || typeof value !== 'object' || Array.isArray(value)
      || Object.keys(value).sort().join('|') !== keys.sort().join('|')
      || value.contract !== 'casepath.workspace-operational-projection/1.0.0'
      || value.claim_id !== claimId
      || !/^[0-9a-f]{64}$/.test(value.projection_sha256 || '')
      || value.projection_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'projection_sha256')))
      || !value.workspace_prefix || Object.keys(value.workspace_prefix).sort().join('|') !== prefixKeys.sort().join('|')
      || !value.next_state || Object.keys(value.next_state).sort().join('|') !== nextKeys.sort().join('|')
      || !['start_processing','evidence_action','processing','decision_ready','safe_abstention','typed_failure'].includes(value.next_state.kind)
      || !['not_assessed','blocked','decision_ready','safe_abstention'].includes(value.readiness_state)
      || !['claim_process','provisional_plan'].includes(value.readiness_scope)
      || (value.provisional_next_action !== null && (
        !inquiryRecord(value.provisional_next_action)
        || Object.keys(value.provisional_next_action).sort().join('|') !== 'audience|enabled|requested_contents'
        || !['internal','provider','claimant','authority'].includes(value.provisional_next_action.audience)
        || typeof value.provisional_next_action.enabled !== 'boolean'
        || !Array.isArray(value.provisional_next_action.requested_contents)
        || value.provisional_next_action.requested_contents.length > 8
        || (value.provisional_next_action.enabled && !value.provisional_next_action.requested_contents.length)
        || value.provisional_next_action.requested_contents.some(item => typeof item !== 'string' || !item.trim() || item !== item.trim() || item.length > 240)
        || new Set(value.provisional_next_action.requested_contents).size !== value.provisional_next_action.requested_contents.length
      ))
      || (value.readiness_scope !== 'provisional_plan' && value.provisional_next_action !== null)
      || typeof value.failure_or_unknown_effect !== 'boolean'
      || !Array.isArray(value.evidence_items)
      || !value.evidence_class_counts || Object.keys(value.evidence_class_counts).sort().join('|') !== classes.slice().sort().join('|')
      || classes.some(name => !Number.isInteger(value.evidence_class_counts[name]) || value.evidence_class_counts[name] < 0)
      || classes.reduce((total, name) => total + value.evidence_class_counts[name], 0) !== value.evidence_items.length
    ) throw new Error('The operational claim projection failed validation');
    if (loopState) {
      const expectedScope = inquiryRecord(loopState.accepted_artifacts?.observable_package?.native_proposal_receipt)
        ? 'provisional_plan'
        : 'claim_process';
      if (value.readiness_scope !== expectedScope) throw new Error('The operational readiness scope differs from its persisted authority');
    }
    if (workspaceState && (
      value.workspace_prefix.loop_id !== workspaceState.loop_id
      || value.workspace_prefix.revision !== workspaceState.revision
      || value.workspace_prefix.state_sha256 !== workspaceState.state_sha256
      || value.workspace_prefix.last_event_sha256 !== workspaceState.last_event_sha256
    )) throw new Error('The operational projection differs from the workspace journal');
    if (value.claim_loop_prefix === null) {
      if (loopState || value.evidence_items.length || value.current_process && value.current_process.overlay_sha256 !== null) throw new Error('A pre-loop projection contains longitudinal authority');
    } else {
      const loopPrefix = value.claim_loop_prefix;
      if (
        Object.keys(loopPrefix).sort().join('|') !== loopPrefixKeys.sort().join('|')
        || typeof loopPrefix.loop_id !== 'string'
        || !Number.isInteger(loopPrefix.revision) || loopPrefix.revision < 1
        || !/^[0-9a-f]{64}$/.test(loopPrefix.state_sha256 || '')
        || !/^[0-9a-f]{64}$/.test(loopPrefix.last_event_sha256 || '')
        || typeof loopPrefix.last_event_at !== 'string'
        || typeof loopPrefix.phase !== 'string'
      ) throw new Error('The operational claim-loop prefix is invalid');
      // Queue rows intentionally carry only the minimal hash-bound loop prefix.
      // A workbench response also supplies the complete loop state, and only in
      // that context can the browser perform the deeper field-for-field join.
      if (loopState && (
        loopPrefix.loop_id !== loopState.loop_id
        || loopPrefix.revision !== loopState.revision
        || loopPrefix.state_sha256 !== loopState.state_sha256
        || loopPrefix.last_event_sha256 !== loopState.last_event_sha256
        || loopPrefix.phase !== loopState.phase
      )) throw new Error('The operational projection differs from the claim-loop journal');
    }
    if (value.current_process !== null && Object.keys(value.current_process).sort().join('|') !== processKeys.sort().join('|')) throw new Error('The current process projection is not closed');
    const seen = new Set();
    const counted = Object.fromEntries(classes.map(name => [name, 0]));
    for (const item of value.evidence_items) {
      if (
        !item || Object.keys(item).sort().join('|') !== evidenceKeys.sort().join('|')
        || seen.has(item.evidence_item_id) || !classes.includes(item.evidence_class)
        || !Array.isArray(item.source_ref_ids) || !Array.isArray(item.provenance_edge_sha256s)
        || !item.provenance_edge_sha256s.every(hash => /^[0-9a-f]{64}$/.test(hash))
      ) throw new Error('The evidence-class projection is invalid');
      seen.add(item.evidence_item_id);
      counted[item.evidence_class] += 1;
    }
    if (classes.some(name => counted[name] !== value.evidence_class_counts[name])) throw new Error('The evidence-class counts differ from the roster');
    return value;
  }

  async function validateQueueResponse(value) {
    const keys = ['authority','contract','corpus_identity','facets','generated_at','items','next_cursor','page_count','projection_sha256','request_sha256','state_roster_sha256','total_count'];
    const rowKeys = ['claim_id','claim_type','deadline_at','failure_or_unknown_effect','language','last_authoritative_update','next_safe_action','operational_projection','owner','pending_evidence_count','principal_blocker','priority_tuple','readiness_state','received_age_days','received_at','revision','row_sha256','state_sha256','subject','urgency','workflow_state'];
    const priorityDimensions = ['safety','deadline','failed_or_unknown_effect','unresolved_critical_obligation','waiting_age_days','customer_burden','closeness_to_readiness'];
    if (
      !value || typeof value !== 'object' || Array.isArray(value)
      || Object.keys(value).sort().join('|') !== keys.sort().join('|')
      || value.contract !== 'casepath.claim-queue-projection/2.0.0'
      || value.authority !== 'claim_loop_events'
      || !Array.isArray(value.items) || value.page_count !== value.items.length
      || !Number.isInteger(value.total_count) || value.total_count < value.page_count
      || !/^[0-9a-f]{64}$/.test(value.projection_sha256 || '')
      || value.projection_sha256 !== await sha256(Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'projection_sha256')))
    ) throw new Error('The server returned an invalid queue projection');
    for (const item of value.items) {
      if (
        !item || Object.keys(item).sort().join('|') !== rowKeys.sort().join('|')
        || !Array.isArray(item.priority_tuple) || item.priority_tuple.length !== priorityDimensions.length
        || item.priority_tuple.some((row, index) => !row || Object.keys(row).sort().join('|') !== 'dimension|value'
          || row.dimension !== priorityDimensions[index]
          || !(typeof row.value === 'string' && row.value.length > 0 || Number.isInteger(row.value)))
        || ![0,1].includes(item.priority_tuple[0].value)
        || typeof item.priority_tuple[1].value !== 'string'
        || ![0,1].includes(item.priority_tuple[2].value)
        || ![0,1].includes(item.priority_tuple[3].value)
        || !Number.isInteger(item.priority_tuple[4].value) || item.priority_tuple[4].value < 0
        || item.priority_tuple[5].value !== 'unknown'
        || ![0,1,2,3].includes(item.priority_tuple[6].value)
        || !/^[0-9a-f]{64}$/.test(item.row_sha256 || '')
        || item.row_sha256 !== await sha256(Object.fromEntries(Object.entries(item).filter(([key]) => key !== 'row_sha256')))
      ) throw new Error('A queue row failed hash verification');
      const expectedReadinessRank = {decision_ready:3, safe_abstention:2, blocked:1, not_assessed:0}[item.readiness_state];
      if (
        expectedReadinessRank === undefined
        || !Number.isSafeInteger(item.received_age_days) || item.received_age_days < 0
        || item.priority_tuple[0].value !== (['failed','typed_failure'].includes(item.workflow_state) ? 0 : 1)
        || item.priority_tuple[1].value !== (item.deadline_at || 'unknown')
        || item.priority_tuple[2].value !== (item.failure_or_unknown_effect ? 0 : 1)
        || item.priority_tuple[3].value !== (item.readiness_state === 'decision_ready' ? 1 : 0)
        || item.priority_tuple[4].value !== item.received_age_days
        || item.priority_tuple[6].value !== expectedReadinessRank
      ) throw new Error('A queue priority tuple differs from its deterministic row projection');
      await validateOperationalProjection(item.operational_projection, item.claim_id, {
        loop_id:`workspace.${item.claim_id}`,
        revision:item.revision,
        state_sha256:item.state_sha256,
        last_event_sha256:item.operational_projection.workspace_prefix.last_event_sha256,
      });
      if (
        item.workflow_state !== item.operational_projection.workflow_state
        || item.readiness_state !== item.operational_projection.readiness_state
        || item.principal_blocker !== item.operational_projection.principal_blocker
        || item.pending_evidence_count !== item.operational_projection.pending_evidence_count
        || item.next_safe_action !== item.operational_projection.next_state.title
        || item.failure_or_unknown_effect !== item.operational_projection.failure_or_unknown_effect
        || item.last_authoritative_update !== item.operational_projection.last_authoritative_update
      ) throw new Error('A queue row differs from its operational authority');
    }
    return value;
  }

  async function validateLoopView(value, claimId) {
    const loop = value?.loop_state;
    const cycle = loop?.six_agent_cycle_receipt;
    const audit = value?.audit;
    if (
      !value || typeof value !== 'object' || Array.isArray(value)
      || value.contract !== 'casepath.workspace-claim-loop-view/2.0.0'
      || value.claim_id !== claimId
      || value.authority !== 'claim_loop_events'
      || !/^[0-9a-f]{64}$/.test(value.view_sha256 || '')
      || !loop || loop.claim_id !== claimId
      || value.revision !== loop.revision
      || value.state_sha256 !== loop.state_sha256
      || !/^[0-9a-f]{64}$/.test(loop.state_sha256 || '')
      || !/^[0-9a-f]{64}$/.test(loop.last_event_sha256 || '')
      || !cycle || cycle.transport_mode !== 'deterministic_test_double'
      || canonicalJson(cycle.agent_ids) !== canonicalJson(EXPECTED_AGENT_IDS)
      || canonicalJson(cycle.deterministic_gate_ids) !== canonicalJson(EXPECTED_GATE_IDS)
      || cycle.agent_receipt_sha256s?.length !== EXPECTED_AGENT_IDS.length
      || cycle.gate_receipt_sha256s?.length !== EXPECTED_GATE_IDS.length
      || cycle.model_calls !== 0 || cycle.provider_calls !== 0 || cycle.cost_usd !== 0
      || !audit || audit.state_sha256 !== loop.state_sha256
      || audit.model_calls !== 0 || audit.provider_calls !== 0 || audit.cost_usd !== 0
    ) throw new Error('The server returned an invalid authoritative claim loop');
    const provisionalBinding = value.provisional_source_binding;
    const acceptedNativeBinding = loop.accepted_artifacts?.observable_package?.native_proposal_receipt;
    const isNativePlan = provisionalBinding !== null && provisionalBinding !== undefined;
    if (isNativePlan) {
      if (
        !inquiryRecord(provisionalBinding)
        || provisionalBinding.authority !== 'fallible_proposal_only'
        || !inquiryText(provisionalBinding.cycle_id)
        || !/^[0-9a-f]{64}$/.test(provisionalBinding.proposal_sha256 || '')
        || !/^[0-9a-f]{64}$/.test(provisionalBinding.source_prefix_sha256 || '')
        || canonicalJson(provisionalBinding) !== canonicalJson(acceptedNativeBinding)
      ) throw new Error('The provisional source-plan binding failed validation');
    } else if (acceptedNativeBinding !== undefined) {
      throw new Error('The native proposal provenance was not projected');
    }
    if (
      value.view_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'view_sha256')))
      || !await validClaimLoopStateHash(loop)
      || cycle.receipt_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(cycle).filter(([key]) => key !== 'receipt_sha256')))
      || audit.receipt_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(audit).filter(([key]) => key !== 'receipt_sha256')))
    ) throw new Error('The authoritative loop or cycle receipt failed hash verification');
    await validateOperationalProjection(value.operational_projection, claimId, {
      loop_id:`workspace.${claimId}`,
      revision:value.workspace_revision,
      state_sha256:value.workspace_state_sha256,
      last_event_sha256:value.operational_projection.workspace_prefix.last_event_sha256,
    }, loop);
    if (value.outcome === 'next_action' && !isNativePlan) {
      const contract = value.input_contract;
      const contractKeys = ['acquisition_intent_contract','acquisition_receipt_contract','action_id','adapter_id','authority_id','catalog_sha256','contract','evidence_item_id','expected_revision','fact_id','input_contract_sha256','intent_ttl_seconds','interpreter_id','interpreter_source_sha256','max_content_bytes','registration_body_fields','registration_receipt_contract','registration_schema','server_interpretation_only','source_policy_sha256'];
      if (
        !contract || Object.keys(contract).sort().join('|') !== contractKeys.sort().join('|')
        || contract.contract !== 'casepath.server-interpreted-evidence-input/1.0.0'
        || contract.input_contract_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(contract).filter(([key]) => key !== 'input_contract_sha256')))
        || contract.evidence_item_id !== loop.selected_action?.evidence_item_id
        || contract.fact_id !== loop.selected_action?.fact_id
        || contract.action_id !== loop.selected_action?.action_id
        || contract.expected_revision !== loop.revision
        || contract.adapter_id !== 'loopback-source-byte-acquisition-v1'
        || contract.acquisition_intent_contract !== 'casepath.workspace-acquisition-intent/1.0.0'
        || contract.acquisition_receipt_contract !== 'casepath.workspace-source-acquisition/1.0.0'
        || contract.registration_receipt_contract !== 'casepath.workspace-evidence-registration-receipt/1.0.0'
        || contract.registration_schema !== 'casepath.workspace-evidence-registration/3.0.0'
        || canonicalJson(contract.registration_body_fields) !== canonicalJson(REGISTRATION_BODY_FIELDS)
        || contract.server_interpretation_only !== true
        || !Number.isInteger(contract.intent_ttl_seconds) || contract.intent_ttl_seconds !== 300
        || !Number.isInteger(contract.max_content_bytes) || contract.max_content_bytes !== 100000
        || ![contract.interpreter_source_sha256,contract.source_policy_sha256,contract.catalog_sha256].every(value => /^[0-9a-f]{64}$/.test(value || ''))
        || contract.interpreter_id !== 'casepath.fixed-source-span-interpreter/1.0.0'
        || contract.authority_id !== 'casepath.independent-evidence-authority/1.0.0'
      ) throw new Error('The evidence input contract failed authority validation');
    } else if (value.input_contract !== null || value.stage_receipt !== null) {
      throw new Error('A non-interactive loop exposed an evidence input contract');
    }
    const terminal = ['decision_ready', 'abstained'].includes(loop.phase);
    const expectedOutcome = loop.phase === 'decision_ready' ? 'decision_ready' : loop.phase === 'abstained' ? 'abstain' : loop.phase === 'awaiting_observation' && loop.selected_action ? 'next_action' : 'processing';
    const expectedMode = loop.phase === 'decision_ready' ? 'finalize' : loop.phase === 'abstained' ? 'abstain' : null;
    if (value.outcome !== expectedOutcome || loop.terminal_mode !== expectedMode || terminal !== Boolean(value.decision_packet)) throw new Error('The loop outcome and terminal authority differ');
    if (value.decision_packet) {
      const packet = value.decision_packet;
      const packetHash = packet.packet_sha256;
      if (
        !/^[0-9a-f]{64}$/.test(packetHash || '')
        || packetHash !== await claimLoopSha256(Object.fromEntries(Object.entries(packet).filter(([key]) => key !== 'packet_sha256')))
        || packet.contract !== 'casepath.decision-ready-packet/1.0.0'
        || packet.claim_id !== claimId || packet.loop_id !== loop.loop_id
        || packet.source_state_sha256 !== loop.state_sha256
        || packet.phase !== loop.phase || packet.terminal_mode !== loop.terminal_mode
        || packet.selected_action !== null
        || packet.six_agent_cycle_receipt_sha256 !== cycle.receipt_sha256
        || packet.deterministic_gate_receipt_sha256 !== loop.deterministic_gate_receipt?.receipt_sha256
        || packet.accepted_cycle_artifacts_sha256 !== packet.accepted_cycle_artifacts?.receipt_sha256
        || packet.accepted_cycle_artifacts_sha256 !== loop.accepted_cycle_artifacts?.receipt_sha256
        || canonicalJson(packet.current_overlay) !== canonicalJson(loop.process?.current_overlay)
        || canonicalJson(packet.obligations) !== canonicalJson(loop.obligations)
        || canonicalJson(packet.provenance_edges) !== canonicalJson(loop.provenance_edges)
        || canonicalJson(packet.sufficiency) !== canonicalJson(loop.sufficiency)
      ) throw new Error('The terminal packet failed authority validation');
    }
    if (value.stage_receipt) {
      const stage = value.stage_receipt;
      if (
        Object.keys(stage).sort().join('|') !== REGISTRATION_RECEIPT_FIELDS.slice().sort().join('|')
        || stage.contract !== 'casepath.workspace-evidence-registration-receipt/1.0.0'
        || stage.claim_id !== claimId || stage.loop_id !== loop.loop_id
        || stage.session_id !== loop.session_id || stage.record_version !== loop.record_version
        || stage.adapter_id !== 'loopback-source-byte-acquisition-v1'
        || stage.channel !== 'public-corpus-source-span-loopback-v1'
        || stage.server_sniffed_media_type !== 'text/plain; charset=utf-8'
        || stage.media_sniffer_id !== 'casepath.strict-utf8-text-sniffer/1.0.0'
        || stage.receipt_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(stage).filter(([key]) => key !== 'receipt_sha256')))
        || !Number.isInteger(stage.content_length) || stage.content_length < 1
        || !Number.isInteger(stage.byte_start) || !Number.isInteger(stage.byte_end)
        || stage.byte_start < 0 || stage.byte_end <= stage.byte_start
        || stage.byte_end - stage.byte_start !== stage.content_length
        || stage.parent_state_sha256 !== loop.state_sha256
        || stage.parent_revision !== loop.revision
        || stage.action_sha256 !== loop.selected_action?.action_sha256
        || stage.action_id !== loop.selected_action?.action_id
        || stage.evidence_item_id !== loop.selected_action?.evidence_item_id
        || !/^intent\.[0-9a-f]{64}$/.test(stage.acquisition_intent_id || '')
        || !/^acquisition\.[0-9a-f]{64}$/.test(stage.acquisition_receipt_id || '')
        || !Number.isFinite(Date.parse(stage.registered_at || ''))
        || ![stage.parent_state_sha256,stage.action_sha256,stage.intent_receipt_sha256,stage.source_acquisition_receipt_sha256,stage.content_sha256,stage.media_sniffer_sha256,stage.freshness_nonce,stage.adapter_artifact_sha256,stage.source_entry_sha256,stage.receipt_sha256].every(value => /^[0-9a-f]{64}$/.test(value || ''))
      ) throw new Error('The staged evidence receipt failed validation');
    }
    if (
      !Number.isInteger(value.correction_count) || value.correction_count < 0
      || value.correction_count !== (Array.isArray(loop.corrections) ? loop.corrections.length : -1)
      || !Array.isArray(value.correction_candidates) || value.correction_candidates.length > 1
    ) throw new Error('The correction authority roster failed validation');
    for (const candidate of value.correction_candidates) await validateCorrectionCandidate(candidate, value);
    if (value.latest_correction) await validateCorrectionDelta(value.latest_correction, value);
    if ((value.correction_count === 0) !== (value.latest_correction === null)) throw new Error('The correction journal summary differs from the loop state');
    return value;
  }

  async function validateCorrectionCandidate(candidate, loop) {
    const keys = ['authority_adapter_id','candidate_sha256','claim_id','contract','current_semantics','loop_id','operation','proposed_semantics','revision','source_artifact_receipt_sha256','source_observation_sha256','state_sha256','target_action_id','target_evidence_item_id','target_fact_id'];
    const proposedKeys = ['evidence_item_id','evidence_status','explanation','fact_id','fact_state','normalized_value','value'];
    const currentKeys = ['evidence_status','explanation','fact_state','normalized_value','value'];
    if (
      !candidate || Object.keys(candidate).sort().join('|') !== keys.join('|')
      || candidate.contract !== 'casepath.workspace-correction-candidate/1.0.0'
      || candidate.claim_id !== loop.claim_id || candidate.loop_id !== loop.loop_state.loop_id
      || candidate.revision !== loop.loop_state.revision || candidate.state_sha256 !== loop.loop_state.state_sha256
      || candidate.authority_adapter_id !== 'casepath.correction.workspace-evidence-withdrawal/1.0.0'
      || candidate.operation !== 'withdraw_decision_sufficiency'
      || Object.keys(candidate.current_semantics || {}).sort().join('|') !== currentKeys.join('|')
      || Object.keys(candidate.proposed_semantics || {}).sort().join('|') !== proposedKeys.join('|')
      || candidate.proposed_semantics.fact_id !== candidate.target_fact_id
      || candidate.proposed_semantics.evidence_item_id !== candidate.target_evidence_item_id
      || candidate.proposed_semantics.fact_state !== 'unknown'
      || candidate.proposed_semantics.normalized_value !== null
      || candidate.proposed_semantics.evidence_status !== 'provided_insufficient'
      || ![candidate.candidate_sha256,candidate.source_artifact_receipt_sha256,candidate.source_observation_sha256,candidate.state_sha256].every(value => /^[0-9a-f]{64}$/.test(value || ''))
      || candidate.candidate_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(candidate).filter(([key]) => key !== 'candidate_sha256')))
    ) throw new Error('The scoped correction candidate failed authority validation');
    return candidate;
  }

  async function validateCorrectionDelta(delta, loop) {
    const keys = ['after_evidence_sha256','after_fact_sha256','after_semantics','before_evidence_sha256','before_fact_sha256','before_semantics','contract','correction_artifact_receipt_sha256','correction_id','correction_sha256','cycle_receipt_sha256','delta_sha256','effect','event_sha256','event_type','evidence_item_id','fact_id','rollback_evidence_sha256','rollback_fact_sha256','unrelated_facts_after_sha256','unrelated_facts_before_sha256'];
    const effectKeys = ['evidence_item_id','evidence_status','explanation','fact_id','fact_state','normalized_value','value'];
    const semanticKeys = ['evidence_status','explanation','fact_state','normalized_value','value'];
    const hashes = ['after_evidence_sha256','after_fact_sha256','before_evidence_sha256','before_fact_sha256','correction_artifact_receipt_sha256','correction_sha256','cycle_receipt_sha256','delta_sha256','event_sha256','rollback_evidence_sha256','rollback_fact_sha256','unrelated_facts_after_sha256','unrelated_facts_before_sha256'];
    const provisionalNativePlan = Boolean(loop.loop_state?.accepted_artifacts?.observable_package?.native_proposal_receipt);
    const expectedWithdrawalEffect = (
      delta.effect?.fact_state === 'unknown'
      && delta.effect?.normalized_value === null
      && delta.effect?.evidence_status === 'provided_insufficient'
    );
    const journaledNativeEffect = (
      provisionalNativePlan
      && canonicalJson(delta.effect) === canonicalJson({
        fact_id:delta.fact_id,
        evidence_item_id:delta.evidence_item_id,
        value:delta.after_semantics?.value,
        fact_state:delta.after_semantics?.fact_state,
        normalized_value:delta.after_semantics?.normalized_value,
        explanation:delta.after_semantics?.explanation,
        evidence_status:delta.after_semantics?.evidence_status,
      })
      && canonicalJson(delta.before_semantics) !== canonicalJson(delta.after_semantics)
    );
    if (
      !delta || Object.keys(delta).sort().join('|') !== keys.join('|')
      || delta.contract !== 'casepath.workspace-correction-delta/1.0.0'
      || delta.event_type !== 'CORRECTION_APPLIED'
      || Object.keys(delta.effect || {}).sort().join('|') !== effectKeys.join('|')
      || Object.keys(delta.before_semantics || {}).sort().join('|') !== semanticKeys.join('|')
      || Object.keys(delta.after_semantics || {}).sort().join('|') !== semanticKeys.join('|')
      || !hashes.every(key => /^[0-9a-f]{64}$/.test(delta[key] || ''))
      || delta.correction_id !== `correction.${delta.correction_sha256}`
      || delta.fact_id !== delta.effect?.fact_id
      || delta.evidence_item_id !== delta.effect?.evidence_item_id
      || (!expectedWithdrawalEffect && !journaledNativeEffect)
      || canonicalJson(delta.after_semantics) !== canonicalJson((() => {
        const fact = loop.loop_state.facts.find(item => item.fact_id === delta.fact_id);
        const evidence = loop.loop_state.checklist.items.find(item => item.item_id === delta.evidence_item_id);
        return fact && evidence ? {
          fact_state: fact.state,
          normalized_value: fact.normalized_value,
          value: fact.value,
          explanation: fact.explanation,
          evidence_status: evidence.status,
        } : null;
      })())
      || delta.unrelated_facts_before_sha256 !== delta.unrelated_facts_after_sha256
      || delta.delta_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(delta).filter(([key]) => key !== 'delta_sha256')))
      || !loop.loop_state.corrections.some(correction => correction.correction_id === delta.correction_id)
    ) throw new Error('The journal-derived correction delta failed authority validation');
    return delta;
  }

  async function validateCorrectionPreview(value, loop, candidate) {
    const keys = ['candidate_sha256','claim_id','contract','correction_id','correction_sha256','effect','loop_id','preview','response_sha256','revision','scope','state_sha256'];
    const scopeKeys = ['claim_ids','evidence_item_ids','fact_ids'];
    const previewKeys = ['before_evidence_sha256','before_fact_sha256','before_semantics','correction_artifact_receipt_sha256','expected_after_evidence_sha256','expected_after_fact_sha256','expected_after_semantics','operation','rollback_evidence_sha256','rollback_fact_sha256','unrelated_facts_after_sha256','unrelated_facts_before_sha256'];
    const previewHashes = ['before_evidence_sha256','before_fact_sha256','correction_artifact_receipt_sha256','expected_after_evidence_sha256','expected_after_fact_sha256','rollback_evidence_sha256','rollback_fact_sha256','unrelated_facts_after_sha256','unrelated_facts_before_sha256'];
    if (
      !value || Object.keys(value).sort().join('|') !== keys.join('|')
      || value.contract !== 'casepath.workspace-correction-preview/1.0.0'
      || value.claim_id !== loop.claim_id || value.loop_id !== loop.loop_state.loop_id
      || value.revision !== loop.loop_state.revision || value.state_sha256 !== loop.loop_state.state_sha256
      || value.candidate_sha256 !== candidate.candidate_sha256
      || value.correction_id !== `correction.${value.correction_sha256}`
      || canonicalJson(value.effect) !== canonicalJson(candidate.proposed_semantics)
      || Object.keys(value.scope || {}).sort().join('|') !== scopeKeys.join('|')
      || Object.keys(value.preview || {}).sort().join('|') !== previewKeys.join('|')
      || canonicalJson(value.scope?.claim_ids) !== canonicalJson([loop.claim_id])
      || canonicalJson(value.scope?.fact_ids) !== canonicalJson([candidate.target_fact_id])
      || canonicalJson(value.scope?.evidence_item_ids) !== canonicalJson([candidate.target_evidence_item_id])
      || !previewHashes.every(key => /^[0-9a-f]{64}$/.test(value.preview?.[key] || ''))
      || value.preview.operation !== candidate.operation
      || value.preview.unrelated_facts_before_sha256 !== value.preview.unrelated_facts_after_sha256
      || canonicalJson(value.preview.before_semantics) !== canonicalJson(candidate.current_semantics)
      || Object.keys(value.preview.expected_after_semantics || {}).sort().join('|') !== ['evidence_status','explanation','fact_state','normalized_value','value'].join('|')
      || value.preview.expected_after_semantics.fact_state !== candidate.proposed_semantics.fact_state
      || value.preview.expected_after_semantics.value !== candidate.proposed_semantics.value
      || value.preview.expected_after_semantics.explanation !== candidate.proposed_semantics.explanation
      || value.preview.expected_after_semantics.evidence_status !== candidate.proposed_semantics.evidence_status
      || value.response_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'response_sha256')))
    ) throw new Error('The scoped correction preview failed authority validation');
    return value;
  }

  async function validateCorrectionApplyResponse(value, loop, correctionId, expectedIdempotencyKey) {
    const keys = ['command_receipt','contract','cost_status','cost_usd','credential_access_status','incremental_loop_activity','loop_id','model_calls','phase','provider_calls','provider_credentials_read','revision','selected_action','source_acceptance_activity','state_sha256','sufficiency','terminal_mode','total_bound_activity','upstream_source_run_activity'];
    const receiptKeys = ['contract','event_sha256','idempotency_key','loop_id','receipt_sha256','revision','state_sha256'];
    const receipt = value?.command_receipt;
    if (
      !value || Object.keys(value).sort().join('|') !== keys.join('|')
      || value.contract !== 'casepath.claim-loop-response/1.0.0'
      || value.loop_id !== loop.loop_state.loop_id
      || !receipt || Object.keys(receipt).sort().join('|') !== receiptKeys.join('|')
      || receipt.contract !== 'casepath.claim-loop-command-receipt/1.0.0'
      || receipt.loop_id !== value.loop_id || receipt.revision !== value.revision
      || receipt.state_sha256 !== value.state_sha256
      || receipt.idempotency_key !== expectedIdempotencyKey
      || !/^[0-9a-f]{64}$/.test(receipt.event_sha256 || '')
      || receipt.receipt_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(receipt).filter(([key]) => key !== 'receipt_sha256')))
      || value.model_calls !== 0 || value.provider_calls !== 0 || value.provider_credentials_read !== false || value.cost_usd !== 0
      || !/^correction\.[0-9a-f]{64}$/.test(correctionId)
    ) throw new Error('The scoped correction commit receipt failed authority validation');
    return value;
  }

  async function validateEvidenceIntentResponse(value, loop, expectedBody, expectedIdempotencyKey) {
    const intent = value?.intent;
    const responseKeys = ['claim_id','contract','intent','loop_id','recovered_durable_acquisition','response_sha256'];
    const intentKeys = ['action_id','action_sha256','adapter_id','claim_id','claim_registry_watermark_sha256','contract','evidence_item_id','expected_revision','expected_state_sha256','expires_at','idempotency_key','intent_id','issued_at','loop_id','receipt_sha256','record_version','session_id'];
    const issuedAt = Date.parse(intent?.issued_at || '');
    const expiresAt = Date.parse(intent?.expires_at || '');
    if (
      !value || Object.keys(value).sort().join('|') !== responseKeys.join('|')
      || value.contract !== 'casepath.workspace-acquisition-intent-response/1.0.0'
      || value.claim_id !== loop.claim_id || value.loop_id !== loop.loop_state.loop_id
      || !intent || Object.keys(intent).sort().join('|') !== intentKeys.sort().join('|')
      || intent.contract !== 'casepath.workspace-acquisition-intent/1.0.0'
      || !/^intent\.[0-9a-f]{64}$/.test(intent.intent_id || '')
      || intent.claim_id !== loop.claim_id || intent.loop_id !== loop.loop_state.loop_id
      || intent.session_id !== loop.loop_state.session_id
      || intent.record_version !== loop.loop_state.record_version
      || intent.expected_revision !== expectedBody.expected_revision
      || intent.expected_state_sha256 !== loop.loop_state.state_sha256
      || intent.action_id !== expectedBody.action_id
      || intent.action_sha256 !== loop.loop_state.selected_action?.action_sha256
      || intent.evidence_item_id !== loop.loop_state.selected_action?.evidence_item_id
      || typeof value.recovered_durable_acquisition !== 'boolean'
      || (!value.recovered_durable_acquisition && intent.idempotency_key !== expectedIdempotencyKey)
      || (value.recovered_durable_acquisition && intent.idempotency_key === expectedIdempotencyKey)
      || typeof intent.idempotency_key !== 'string' || intent.idempotency_key.length < 8 || intent.idempotency_key.length > 128
      || intent.adapter_id !== 'loopback-source-byte-acquisition-v1'
      || !Number.isFinite(issuedAt) || !Number.isFinite(expiresAt)
      || expiresAt - issuedAt !== 300000
      || ![intent.expected_state_sha256,intent.action_sha256,intent.claim_registry_watermark_sha256,intent.receipt_sha256].every(item => /^[0-9a-f]{64}$/.test(item || ''))
      || !/^[0-9a-f]{64}$/.test(value.response_sha256 || '')
      || intent.receipt_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(intent).filter(([key]) => key !== 'receipt_sha256')))
      || value.response_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'response_sha256')))
    ) throw new Error('The server returned an invalid source-acquisition intent');
    return value;
  }

  async function validateEvidenceAcquisitionResponse(value, loop, intent) {
    const receipt = value?.acquisition_receipt;
    const responseKeys = ['acquisition_receipt','claim_id','content_b64','contract','loop_id','response_sha256'];
    const receiptKeys = ['acquired_at','acquisition_intent_id','acquisition_receipt_id','action_id','action_sha256','adapter_artifact_sha256','adapter_id','byte_end','byte_start','channel','claim_first_seen_receipt_sha256','claim_id','claim_registry_watermark_sha256','content_length','content_sha256','contract','evidence_item_id','expected_revision','expected_state_sha256','expires_at','freshness','freshness_nonce','idempotency_key','intent_receipt_sha256','loop_id','media_sniffer_id','media_sniffer_sha256','receipt_sha256','record_version','server_sniffed_media_type','session_id','source_artifact_id','source_artifact_sha256','source_entry_sha256','source_version','text_end','text_start'];
    const raw = base64Bytes(value?.content_b64);
    const acquiredAt = Date.parse(receipt?.acquired_at || '');
    const expiresAt = Date.parse(receipt?.expires_at || '');
    if (
      !value || Object.keys(value).sort().join('|') !== responseKeys.join('|')
      || value.contract !== 'casepath.workspace-source-acquisition-response/1.0.0'
      || value.claim_id !== loop.claim_id || value.loop_id !== loop.loop_state.loop_id
      || !receipt || Object.keys(receipt).sort().join('|') !== receiptKeys.sort().join('|')
      || receipt.contract !== 'casepath.workspace-source-acquisition/1.0.0'
      || !/^acquisition\.[0-9a-f]{64}$/.test(receipt.acquisition_receipt_id || '')
      || receipt.acquisition_intent_id !== intent.intent_id
      || receipt.claim_id !== intent.claim_id || receipt.loop_id !== intent.loop_id
      || receipt.session_id !== intent.session_id || receipt.record_version !== intent.record_version
      || receipt.expected_revision !== intent.expected_revision
      || receipt.expected_state_sha256 !== intent.expected_state_sha256
      || receipt.action_id !== intent.action_id || receipt.action_sha256 !== intent.action_sha256
      || receipt.evidence_item_id !== intent.evidence_item_id
      || receipt.idempotency_key !== intent.idempotency_key
      || receipt.intent_receipt_sha256 !== intent.receipt_sha256
      || receipt.claim_registry_watermark_sha256 !== intent.claim_registry_watermark_sha256
      || receipt.adapter_id !== 'loopback-source-byte-acquisition-v1'
      || receipt.channel !== 'public-corpus-source-span-loopback-v1'
      || receipt.server_sniffed_media_type !== 'text/plain; charset=utf-8'
      || receipt.media_sniffer_id !== 'casepath.strict-utf8-text-sniffer/1.0.0'
      || receipt.freshness !== 'fresh_until_expires_at'
      || receipt.expires_at !== intent.expires_at
      || !Number.isFinite(acquiredAt) || !Number.isFinite(expiresAt) || acquiredAt > expiresAt
      || !Number.isInteger(receipt.text_start) || !Number.isInteger(receipt.text_end)
      || receipt.text_start < 0 || receipt.text_end <= receipt.text_start
      || !Number.isInteger(receipt.byte_start) || !Number.isInteger(receipt.byte_end)
      || receipt.byte_start < 0 || receipt.byte_end <= receipt.byte_start
      || !Number.isInteger(receipt.content_length) || receipt.content_length !== raw.byteLength
      || receipt.byte_end - receipt.byte_start !== receipt.content_length
      || receipt.content_length > loop.input_contract.max_content_bytes
      || receipt.content_sha256 !== await sha256Bytes(raw)
      || ![receipt.expected_state_sha256,receipt.action_sha256,receipt.intent_receipt_sha256,receipt.adapter_artifact_sha256,receipt.claim_registry_watermark_sha256,receipt.claim_first_seen_receipt_sha256,receipt.source_entry_sha256,receipt.source_artifact_sha256,receipt.content_sha256,receipt.media_sniffer_sha256,receipt.freshness_nonce,receipt.receipt_sha256,value.response_sha256].every(item => /^[0-9a-f]{64}$/.test(item || ''))
      || receipt.receipt_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(receipt).filter(([key]) => key !== 'receipt_sha256')))
      || value.response_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'response_sha256')))
    ) throw new Error('The server returned an invalid source-acquisition receipt');
    return value;
  }

  async function validateStageResponse(value, loop, expectedBody) {
    const receipt = value?.stage_receipt;
    const responseKeys = ['claim_id','contract','loop_id','parent_revision','parent_state_sha256','response_sha256','stage_receipt'];
    const raw = base64Bytes(expectedBody.content_b64);
    if (
      !value || Object.keys(value).sort().join('|') !== responseKeys.join('|')
      || Object.keys(expectedBody).sort().join('|') !== REGISTRATION_BODY_FIELDS.slice().sort().join('|')
      || value.contract !== 'casepath.workspace-evidence-registration-response/1.0.0'
      || value.claim_id !== loop.claim_id
      || value.loop_id !== loop.loop_state.loop_id
      || value.parent_revision !== loop.loop_state.revision
      || value.parent_state_sha256 !== loop.loop_state.state_sha256
      || !receipt || Object.keys(receipt).sort().join('|') !== REGISTRATION_RECEIPT_FIELDS.slice().sort().join('|')
      || receipt.contract !== 'casepath.workspace-evidence-registration-receipt/1.0.0'
      || receipt.claim_id !== loop.claim_id || receipt.loop_id !== loop.loop_state.loop_id
      || receipt.session_id !== loop.loop_state.session_id
      || receipt.record_version !== loop.loop_state.record_version
      || receipt.parent_revision !== expectedBody.expected_revision
      || receipt.parent_state_sha256 !== loop.loop_state.state_sha256
      || receipt.action_id !== expectedBody.action_id
      || receipt.action_sha256 !== loop.loop_state.selected_action?.action_sha256
      || receipt.evidence_item_id !== loop.loop_state.selected_action?.evidence_item_id
      || receipt.idempotency_key !== expectedBody.idempotency_key
      || receipt.acquisition_intent_id !== expectedBody.acquisition_intent_id
      || receipt.acquisition_receipt_id !== expectedBody.acquisition_receipt_id
      || receipt.adapter_id !== 'loopback-source-byte-acquisition-v1'
      || receipt.channel !== 'public-corpus-source-span-loopback-v1'
      || receipt.server_sniffed_media_type !== 'text/plain; charset=utf-8'
      || receipt.media_sniffer_id !== 'casepath.strict-utf8-text-sniffer/1.0.0'
      || !Number.isInteger(receipt.content_length) || receipt.content_length !== raw.byteLength
      || !Number.isInteger(receipt.byte_start) || !Number.isInteger(receipt.byte_end)
      || receipt.byte_start < 0 || receipt.byte_end <= receipt.byte_start
      || receipt.byte_end - receipt.byte_start !== receipt.content_length
      || receipt.content_sha256 !== await sha256Bytes(raw)
      || !Number.isFinite(Date.parse(receipt.registered_at || ''))
      || ![receipt.parent_state_sha256,receipt.action_sha256,receipt.intent_receipt_sha256,receipt.source_acquisition_receipt_sha256,receipt.content_sha256,receipt.media_sniffer_sha256,receipt.freshness_nonce,receipt.adapter_artifact_sha256,receipt.source_entry_sha256,receipt.receipt_sha256,value.response_sha256].every(item => /^[0-9a-f]{64}$/.test(item || ''))
    ) throw new Error('The server returned an invalid evidence-stage receipt');
    if (
      receipt.receipt_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(receipt).filter(([key]) => key !== 'receipt_sha256')))
      || value.response_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'response_sha256')))
    ) throw new Error('The evidence-stage receipt failed hash verification');
    return value;
  }

  async function validateAdvanceResponse(value, loop, expectedBody) {
    const admission = value?.admission;
    const response = value?.claim_loop_response;
    if (
      value?.contract !== 'casepath.workspace-claim-loop-advance-response/1.0.0'
      || value.claim_id !== loop.claim_id
      || value.loop_id !== loop.loop_state.loop_id
      || !admission || admission.contract !== 'casepath.workspace-advance-admission/1.0.0'
      || admission.expected_revision !== expectedBody.expected_revision
      || admission.expected_state_sha256 !== expectedBody.expected_state_sha256
      || admission.action_sha256 !== expectedBody.action_sha256
      || admission.stage_receipt_sha256 !== expectedBody.stage_receipt_sha256
      || typeof admission.action_id !== 'string' || !admission.action_id
      || admission.adapter_id !== 'loopback-source-byte-acquisition-v1'
      || !/^[0-9a-f]{64}$/.test(admission.adapter_implementation_sha256 || '')
      || value.request_context_sha256 !== await sha256(admission)
      || !response || response.loop_id !== loop.loop_state.loop_id
      || response.contract !== 'casepath.claim-loop-response/1.0.0'
      || !/^[0-9a-f]{64}$/.test(response.state_sha256 || '')
      || value.response_sha256 !== await claimLoopSha256(Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'response_sha256')))
    ) throw new Error('The verified replan response failed authority validation');
    return value;
  }

  async function request(path, options = {}) {
    let response;
    try {
      response = await fetch(`${api}${path}`, {cache: 'no-store', ...options});
    } catch (cause) {
      const error = new Error(cause?.message || 'No response was received');
      error.transportFailure = true;
      throw error;
    }
    const body = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = body?.detail;
      const message = typeof detail === 'string' ? detail : detail?.reason || `Request failed (${response.status})`;
      const error = new Error(message);
      error.responseReceived = true;
      error.status = response.status;
      error.code = typeof detail === 'object' && detail ? detail.code : null;
      error.ambiguousResponse = response.status >= 500 || (response.status === 409 && error.code === 'request_in_progress');
      throw error;
    }
    return body;
  }

  async function requireVerifiedResponse(validation) {
    try {
      return await validation;
    } catch (error) {
      if (!error.responseReceived && !error.transportFailure) error.ambiguousResponse = true;
      throw error;
    }
  }

  function queryString(cursor = null) {
    const query = new URLSearchParams({limit:'25',sort:$('#cwSort').value});
    const fields = [
      ['q','#cwSearch'],['state','#cwState'],['readiness','#cwReadiness'],
      ['claim_type','#cwClaimType'],['owner','#cwOwner'],['urgency','#cwUrgency'],
      ['failure','#cwFailure'],['pending_evidence','#cwPendingEvidence'],
    ];
    fields.forEach(([key, selector]) => { const value = $(selector).value.trim(); if (value) query.set(key, value); });
    if (cursor) query.set('cursor', cursor);
    return query.toString();
  }

  function tone(item) {
    if (item.failure_or_unknown_effect) return 'failure';
    if (item.readiness_state === 'decision_ready') return 'ready';
    if (item.readiness_state === 'blocked') return 'blocked';
    return 'unknown';
  }

  function evidenceProgressMarkup(projection, {compact = false} = {}) {
    const counts = projection?.evidence_class_counts;
    if (!counts) return '<span class="cw-progress-empty">Not assessed</span>';
    const total = ['received','missing','insufficient','conditional','irrelevant','unknown']
      .reduce((sum, name) => sum + counts[name], 0);
    if (!total) return '<span class="cw-progress-empty">Not assessed</span>';
    const resolved = counts.received + counts.irrelevant;
    const percent = Math.round((resolved / total) * 100);
    const detail = compact
      ? `${resolved} of ${total} resolved`
      : `${resolved} of ${total} resolved · ${counts.received} received · ${counts.irrelevant} irrelevant · ${counts.missing} missing · ${counts.insufficient} insufficient · ${counts.conditional} conditional · ${counts.unknown} unknown`;
    return `<div class="cw-progress" data-progress-percent="${percent}" role="progressbar" aria-label="Evidence readiness" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}"><span style="width:${percent}%"></span></div><small class="cw-progress-copy">${esc(detail)}</small>`;
  }

  function renderRows() {
    $('#cwTotal').textContent = state.total.toLocaleString();
    $('#cwPageStatus').textContent = state.items.length ? `Showing ${state.items.length} of ${state.total}` : 'No claims match these filters';
    $('#cwMore').hidden = !state.cursor;
    if (!state.items.length) {
      $('#cwTable').innerHTML = `<div class="cw-empty"><h2>${state.total === 0 ? 'Seed the local workspace' : 'No matching claims'}</h2><p>${state.total === 0 ? 'The authoritative journal is empty. Import the bundled public-safe synthetic claims once, then refresh.' : 'Adjust a filter or search term. No authoritative state was changed.'}</p>${state.total === 0 ? '<code>./bin/casepath seed --corpus synthetic-dev-60</code>' : ''}</div>`;
      return;
    }
    $('#cwTable').innerHTML = `<div class="cw-table-scroll"><table class="cw-table"><thead><tr><th>Claim</th><th>Handler</th><th>Time</th><th>State</th><th>Evidence and blocker</th><th>Next safe action</th><th>Updated</th></tr></thead><tbody>${state.items.map(item => `
      <tr tabindex="0" data-claim-id="${esc(item.claim_id)}" aria-label="Open ${esc(item.claim_id)}">
        <td class="cw-claim-cell"><strong>${esc(item.subject)}</strong><span>${esc(item.claim_id)}</span></td>
        <td data-label="Handler"><strong>${esc(item.owner || 'Unassigned')}</strong><small>${esc(item.received_age_days)} days open</small></td>
        <td data-label="Time"><strong>${esc(item.deadline_at ? stamp(item.deadline_at) : 'No declared deadline')}</strong><small>${esc(label(item.urgency))} urgency</small></td>
        <td data-label="State"><span class="cw-pill" data-tone="${tone(item)}">${esc(item.operational_projection.readiness_scope === 'provisional_plan' && item.readiness_state === 'decision_ready' ? 'Provisional plan covered' : label(item.readiness_state))}</span><small>${esc(item.operational_projection.readiness_scope === 'provisional_plan' && item.workflow_state === 'decision_ready' ? 'Inner cycle complete' : label(item.workflow_state))}</small>${item.failure_or_unknown_effect ? '<span class="cw-effect-warning">Unknown effect</span>' : item.operational_projection.readiness_scope === 'provisional_plan' ? '' : '<span class="cw-effect-clear">Effect known</span>'}</td>
        <td data-label="Evidence"><strong>${item.pending_evidence_count == null ? 'Not assessed' : `${esc(item.pending_evidence_count)} current mandatory`}</strong>${evidenceProgressMarkup(item.operational_projection, {compact:true})}<small>${esc(item.principal_blocker)}</small></td>
        <td data-label="Next action"><strong>${esc(item.next_safe_action)}</strong></td>
        <td data-label="Updated">${esc(stamp(item.last_authoritative_update))}</td>
      </tr>`).join('')}</tbody></table></div>`;
    root.querySelectorAll('[data-claim-id]').forEach(row => {
      const open = () => openClaim(row.dataset.claimId);
      row.addEventListener('click', open);
      row.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open(); } });
    });
  }

  async function loadQueue({append = false} = {}) {
    if (state.loading) { state.queuedLoad = {append}; return; }
    state.loading = true;
    $('#cwPageStatus').textContent = 'Loading authoritative journal projection…';
    try {
      const page = await requireVerifiedResponse(validateQueueResponse(await request(`/api/claim-loops/v1/workspace/claims?${queryString(append ? state.cursor : null)}`)));
      state.items = append ? state.items.concat(page.items) : page.items;
      state.total = page.total_count;
      state.cursor = page.next_cursor;
      renderRows();
      hydrateOpenPriority();
      const ownerSelect = $('#cwOwner');
      const selected = ownerSelect.value;
      const owners = Array.isArray(page.facets?.owners) ? page.facets.owners : [];
      ownerSelect.innerHTML = '<option value="">All owners</option><option value="unassigned">Unassigned</option>' + owners.map(owner => `<option value="${esc(owner)}">${esc(owner)}</option>`).join('');
      ownerSelect.value = selected;
      const typeSelect = $('#cwClaimType');
      const selectedType = typeSelect.value;
      const claimTypes = Array.isArray(page.facets?.claim_types) ? page.facets.claim_types : [];
      typeSelect.innerHTML = '<option value="">All claim types</option>' + claimTypes.map(value => `<option value="${esc(value)}">${esc(label(value))}</option>`).join('');
      typeSelect.value = selectedType;
    } catch (error) {
      $('#cwTable').innerHTML = `<div class="cw-error"><h2>Workspace unavailable</h2><p>${esc(error.message)}</p></div>`;
      $('#cwPageStatus').textContent = 'Failed closed; no claim state changed';
    } finally {
      state.loading = false;
      if (state.queuedLoad) {
        const queued = state.queuedLoad;
        state.queuedLoad = null;
        void loadQueue(queued);
      }
    }
  }

  function priorityList(item) {
    return item.priority_tuple.map(row => `<li data-priority-dimension="${esc(row.dimension)}" data-priority-value-json="${esc(JSON.stringify(row.value))}"><strong>${esc(label(row.dimension))}:</strong> ${esc(row.value)}</li>`).join('');
  }

  function hydrateOpenPriority() {
    const claimId = state.detail?.state?.claim_id;
    const section = $('#cwExplainablePriority');
    if (!claimId || !section) return;
    const list = section.querySelector('ol');
    const stateSha = state.detail.state.state_sha256;
    const priority = state.items.find(item => item.claim_id === claimId && item.state_sha256 === stateSha)
      || (state.detailPriority?.claim_id === claimId && state.detailPriority.state_sha256 === stateSha ? state.detailPriority : null);
    if (!priority) {
      list.innerHTML = '';
      section.querySelector('[data-priority-status]').hidden = false;
      return;
    }
    list.innerHTML = priorityList(priority);
    section.querySelector('[data-priority-status]').hidden = true;
  }

  async function loadOpenPriority(claimId, detailStateSha, context, signal) {
    const query = new URLSearchParams({q:claimId, sort:'priority', limit:'1'});
    try {
      const page = await requireVerifiedResponse(validateQueueResponse(await request(`/api/claim-loops/v1/workspace/claims?${query}`, {signal})));
      if (!isActiveDetail(context) || state.detail.state.state_sha256 !== detailStateSha) return;
      if (page.total_count !== 1 || page.items.length !== 1 || page.items[0].claim_id !== claimId || page.items[0].state_sha256 !== detailStateSha) {
        throw new Error('The exact priority row does not bind the open claim state');
      }
      state.detailPriority = page.items[0];
      hydrateOpenPriority();
    } catch (error) {
      if (error.name === 'AbortError' || !isActiveDetail(context) || state.detail.state.state_sha256 !== detailStateSha) return;
      const status = $('#cwExplainablePriority [data-priority-status]');
      if (status) {
        status.hidden = false;
        status.textContent = 'Explainable priority is unavailable because its authoritative queue receipt could not be verified.';
      }
    }
  }

  async function loadClaimLoop(claimId, {allowMissing = false, signal = null} = {}) {
    try {
      return await requireVerifiedResponse(validateLoopView(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}/loop`, {signal}), claimId));
    } catch (error) {
      if (allowMissing && error.status === 404) return null;
      throw error;
    }
  }

  async function loadEvidenceInvestigation(claimId, context, signal) {
    try {
      const response = await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}/native-inquiry/live`, {
        headers:{[NATIVE_INQUIRY_MODE_HEADER]:NATIVE_INQUIRY_MODE},
        signal,
      });
      if (!isActiveDetail(context)) return;
      state.nativeInvestigation = buildEvidenceInvestigationView(response, claimId);
      const mount = $('#cwEvidenceInvestigationMount');
      if (mount) {
        mount.innerHTML = evidenceInvestigationMarkup(state.nativeInvestigation, state.loop);
        bindNativeInvestigationActions();
      }
    } catch (error) {
      if (error.name === 'AbortError' || !isActiveDetail(context)) return;
      if (error.status === 404) return;
      state.nativeInvestigation = unavailableInvestigation('Evidence investigation is temporarily unavailable.');
      const mount = $('#cwEvidenceInvestigationMount');
      if (mount) mount.innerHTML = evidenceInvestigationMarkup(state.nativeInvestigation, state.loop);
    }
  }

  async function runNativeInvestigation() {
    if (state.mutationBusy || !state.detail) return;
    const claimId = state.detail.state.claim_id;
    const context = activeDetailContext();
    const marker = {operation:'cycle', claim_id:claimId};
    const pending = commandIdentity('native-cycle', claimId, marker);
    setLoopMutationBusy(true, 'Inspecting the currently admitted source bytes…', context);
    try {
      await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}/native-inquiry/live`, {
        method:'POST',
        headers:{[NATIVE_INQUIRY_MODE_HEADER]:NATIVE_INQUIRY_MODE,'X-CasePath-Idempotency-Key':pending.key},
      });
      const authoritative = buildEvidenceInvestigationView(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}/native-inquiry/live`, {headers:{[NATIVE_INQUIRY_MODE_HEADER]:NATIVE_INQUIRY_MODE}}), claimId);
      if (!isActiveDetail(context)) return;
      if (authoritative.kind !== 'qualified') throw new Error('The provider result was not qualified for source review');
      clearCommandIdentity('native-cycle', claimId);
      state.nativeInvestigation = authoritative;
      renderDetail(state.detail);
      $('#cwCommandStatus').textContent = 'Source review recorded. Proposed answers remain provisional until separately admitted.';
    } catch (error) {
      if (!isActiveDetail(context)) return;
      if (error.responseReceived && !error.ambiguousResponse) clearCommandIdentity('native-cycle', claimId);
      $('#cwCommandStatus').textContent = `Source review failed closed: ${error.message}`;
    } finally {
      setLoopMutationBusy(false, '', context);
    }
  }

  async function mutateNativeClaimLoop(operation, needId = null) {
    if (state.mutationBusy || !state.detail || state.nativeInvestigation?.kind !== 'qualified') return;
    const claimId = state.detail.state.claim_id;
    const context = activeDetailContext();
    const cycleId = state.nativeInvestigation.cycleId;
    const body = operation === 'ensure'
      ? {operation,cycle_id:cycleId}
      : {operation,cycle_id:cycleId,loop_id:state.loop?.loop_state?.loop_id,need_id:needId};
    if ((operation !== 'ensure' && (!body.loop_id || !inquiryText(needId)))) return;
    const pending = commandIdentity(`native-${operation}`, claimId, body);
    setLoopMutationBusy(true, operation === 'ensure' ? 'Opening the provisional plan in the claim journal…' : operation === 'observe' ? 'Validating cited source bytes before admission…' : 'Applying one source-scoped correction…', context);
    try {
      const result = await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}/native-inquiry/live/claim-loop`, {
        method:'POST',
        headers:{'Content-Type':'application/json',[NATIVE_INQUIRY_MODE_HEADER]:NATIVE_INQUIRY_MODE,'X-CasePath-Idempotency-Key':pending.key},
        body:JSON.stringify(body),
      });
      if (
        result?.contract !== 'casepath.native-claim-loop-bridge-result/1.0.0'
        || result.operation !== operation
        || result.claim_id !== claimId
        || result.cycle_id !== cycleId
        || result.provisional !== true
        || result.canonical_fact_certification !== false
        || result.legal_readiness_certification !== false
      ) throw new Error('The native journal bridge returned an invalid boundary receipt');
      if (
        operation === 'correct'
        && (
          result.source_change_kind !== 'answer_extension'
          || result.prior_source_fact_replacement_established !== false
        )
      ) throw new Error('The native correction receipt did not preserve its provisional extension boundary');
      const loop = await loadClaimLoop(claimId);
      if (!isActiveDetail(context)) return;
      if (
        loop.loop_state.loop_id !== result.loop_id
        || !inquiryRecord(loop.provisional_source_binding)
      ) throw new Error('The shared claim journal did not confirm the native transition');
      clearCommandIdentity(`native-${operation}`, claimId);
      state.loop = loop;
      await loadQueue();
      if (!isActiveDetail(context)) return;
      renderDetail(state.detail);
      $('#cwCommandStatus').textContent = operation === 'ensure'
        ? 'The provisional source plan is now in the shared evidence journal.'
        : operation === 'observe'
          ? 'One server-verified source answer was admitted and the plan was re-evaluated.'
          : 'A later source extended one provisional answer; it did not certify replacement of an earlier source fact, and neighboring observations were retained.';
    } catch (error) {
      if (!isActiveDetail(context)) return;
      if (error.responseReceived && !error.ambiguousResponse) clearCommandIdentity(`native-${operation}`, claimId);
      $('#cwCommandStatus').textContent = `Native journal transition failed closed: ${error.message}`;
    } finally {
      setLoopMutationBusy(false, '', context);
    }
  }

  function bindNativeInvestigationActions() {
    $('#cwNativeInvestigate')?.addEventListener('click', runNativeInvestigation);
    $('#cwNativeEnsure')?.addEventListener('click', () => mutateNativeClaimLoop('ensure'));
    root.querySelectorAll('[data-native-operation][data-native-need-id]').forEach(button => button.addEventListener('click', () => mutateNativeClaimLoop(button.dataset.nativeOperation, button.dataset.nativeNeedId)));
  }

  function proposalRevisionMarkup(revision) {
    if (!inquiryRecord(revision)
      || revision.contract !== 'casepath.native-proposal-revision/1.0.0'
      || revision.provisional !== true
      || !Array.isArray(revision.readings)
      || !Array.isArray(revision.actions)
      || !Array.isArray(revision.action_dispositions)) return '';
    const retired = revision.action_dispositions.filter(item => item.disposition === 'retired');
    return `<section class="cw-section" id="cwUpdatedSourceReview" data-cycle-id="${esc(revision.cycle_id)}" data-revision-sha256="${esc(revision.revision_sha256)}">
      <h3>Updated source review</h3>
      <p>These are the model's latest readings of the available records. They can be corrected and do not establish that a service is complete or the claim is ready.</p>
      <ul class="cw-evidence-list">${revision.readings.map(item => `<li data-reading-id="${esc(item.reading_id)}" data-reading-state="${esc(item.state)}"><strong>${esc(item.description)}</strong><p>${esc(item.answer || 'No answer established')}</p><small>Model assessment: ${esc(label(item.state))}</small><details><summary>Cited sources (${(item.evidence || []).length})</summary>${(item.evidence || []).map(evidence => `<div data-reading-source-id="${esc(evidence.source_ref?.source_id || '')}"><small>${esc(label(evidence.role))}</small><blockquote>${esc(evidence.source_ref?.sanitized_excerpt || 'No excerpt available')}</blockquote></div>`).join('')}</details></li>`).join('')}</ul>
      ${retired.length ? `<h4>No longer requested (${retired.length})</h4><ul>${retired.map(item => `<li data-retired-action-index="${esc(item.prior_action_index)}">${esc(item.reason)}</li>`).join('')}</ul>` : ''}
      ${revision.actions.length === 0 ? '<p>No follow-up request is proposed in this revision. The claim remains subject to review.</p>' : ''}
    </section>`;
  }

  function loopWorkbenchMarkup(loop, workspaceState) {
    if (!loop) {
      return workspaceState.workflow_state === 'in_review' ? `
        <section class="cw-section cw-loop cw-decision-card" id="cwLoopWorkbench">
          <p class="cw-eyebrow">Current decision</p>
          <h2>Evidence review has not started</h2>
          <p class="cw-status">Choose how to review the admitted sources, then keep every accepted observation in the same claim journal.</p>
          <div class="cw-actions"><button class="cw-button cw-button-primary" id="cwEnsureLoop" type="button">Open evidence workbench</button></div>
        </section>` : '';
    }
    const value = loop.loop_state;
    const provisionalPlan = inquiryRecord(loop.provisional_source_binding);
    const action = value.selected_action;
    const staged = loop.stage_receipt;
    const pendingIntent = storedCommandIdentity('evidence-intent', loop.claim_id);
    const pendingStage = storedCommandIdentity('evidence', loop.claim_id);
    const pendingAdvance = storedCommandIdentity('advance', loop.claim_id);
    const pendingInvalid = Boolean(pendingIntent?.invalid || pendingStage?.invalid || pendingAdvance?.invalid);
    const operational = loop.operational_projection;
    const evidenceClasses = ['received','missing','insufficient','conditional','irrelevant','unknown'];
    const evidenceClassMarkup = evidenceClasses.map(name => {
      const items = operational.evidence_items.filter(item => item.evidence_class === name);
      return `<section class="cw-evidence-class" data-evidence-class="${esc(name)}"><header><h3>${esc(label(name))}</h3><span>${items.length}</span></header><ul>${items.length ? items.map(item => `<li data-evidence-item-id="${esc(item.evidence_item_id)}" data-fact-id="${esc(item.fact_id)}" data-fact-state="${esc(item.fact_state)}" data-raw-status="${esc(item.raw_status)}" data-obligation-status="${esc(item.obligation_status)}" data-mandatory-now="${esc(String(item.mandatory_now))}" data-current-path="${esc(String(item.current_path))}" data-source-ref-ids="${esc(canonicalJson(item.source_ref_ids))}" data-provenance-edge-sha256s="${esc(canonicalJson(item.provenance_edge_sha256s))}"><strong>${esc(item.title)}</strong><small>${esc(label(item.fact_state))} fact · ${esc(label(item.obligation_status))}${item.mandatory_now ? ' · mandatory now' : ''}</small></li>`).join('') : '<li class="cw-muted">None</li>'}</ul></section>`;
    }).join('');
    const observations = Array.isArray(value.observations) ? value.observations : [];
    const observationEvidence = observations.length
      ? observations.map(observation => {
        const ref = observation.source_refs?.[0];
        const evidenceCopy = ref?.sanitized_excerpt || observation.value;
        return `<li data-observation-sha256="${esc(observation.observation_sha256)}" data-fact-id="${esc(observation.fact_id)}" data-evidence-item-id="${esc(observation.evidence_item_id)}" data-fact-state="${esc(observation.fact_state)}" data-normalized-value="${esc(observation.normalized_value ?? '')}" data-evidence-status="${esc(observation.evidence_status)}" data-source-ref="${esc(canonicalJson(ref || null))}"><strong>${esc(observation.explanation || 'Accepted source observation')}</strong><blockquote>${esc(evidenceCopy)}</blockquote><span>Immutable source SHA ${esc((ref?.source_sha256 || '').slice(0, 16))}…</span></li>`;
      }).join('')
      : '<li class="cw-muted">No decision-bearing observation has been committed yet.</li>';
    const correctionCandidate = loop.correction_candidates?.[0] || null;
    const correctionPreview = state.correctionPreview?.claimId === loop.claim_id ? state.correctionPreview.value : null;
    const latestCorrection = loop.latest_correction;
    const nativeCorrection = Boolean(provisionalPlan && latestCorrection);
    const correctionMarkup = latestCorrection ? `
      <section class="cw-correction" id="cwCorrectionResult">
        <p class="cw-eyebrow">Scoped correction applied</p>
        <h3>${nativeCorrection ? 'One provisional source-backed answer was extended' : 'One evidence assertion was withdrawn'}</h3>
        <p>${nativeCorrection ? 'A later record changed only the selected provisional answer. This does not certify claim truth or completeness, and unrelated facts stayed byte-identical.' : 'The target returned to <strong>unknown / insufficient</strong>. No replacement truth was supplied and unrelated facts stayed byte-identical.'}</p>
        <div class="cw-correction-semantics" data-before-semantics="${esc(canonicalJson(latestCorrection.before_semantics))}" data-after-semantics="${esc(canonicalJson(latestCorrection.after_semantics))}"><p><strong>Before</strong> <code>${esc(canonicalJson(latestCorrection.before_semantics))}</code></p><p><strong>After</strong> <code>${esc(canonicalJson(latestCorrection.after_semantics))}</code></p></div>
        <dl class="cw-hash-delta"><div><dt>Fact</dt><dd><code>${esc(latestCorrection.before_fact_sha256.slice(0,12))}… → ${esc(latestCorrection.after_fact_sha256.slice(0,12))}…</code></dd></div><div><dt>Evidence</dt><dd><code>${esc(latestCorrection.before_evidence_sha256.slice(0,12))}… → ${esc(latestCorrection.after_evidence_sha256.slice(0,12))}…</code></dd></div><div><dt>Unrelated facts</dt><dd><code>${esc(latestCorrection.unrelated_facts_after_sha256.slice(0,16))}… unchanged</code></dd></div></dl>
        <p class="cw-stage-receipt" data-delta-sha256="${esc(latestCorrection.delta_sha256)}">Correction receipt <code>${esc(latestCorrection.delta_sha256.slice(0,16))}…</code></p>
      </section>` : correctionPreview ? `
      <section class="cw-correction" id="cwCorrectionPreview">
        <p class="cw-eyebrow">Preview only · journal unchanged</p>
        <h3>Withdraw this evidence assertion?</h3>
        <p>This changes only <strong>${esc(label(correctionPreview.effect.fact_id))}</strong> and <strong>${esc(label(correctionPreview.effect.evidence_item_id))}</strong> to unknown / insufficient. It does not create a new fact.</p>
        <dl class="cw-hash-delta"><div><dt>Fact</dt><dd><code>${esc(correctionPreview.preview.before_fact_sha256.slice(0,12))}… → ${esc(correctionPreview.preview.expected_after_fact_sha256.slice(0,12))}…</code></dd></div><div><dt>Evidence</dt><dd><code>${esc(correctionPreview.preview.before_evidence_sha256.slice(0,12))}… → ${esc(correctionPreview.preview.expected_after_evidence_sha256.slice(0,12))}…</code></dd></div><div><dt>Unrelated facts</dt><dd><code>${esc(correctionPreview.preview.unrelated_facts_after_sha256.slice(0,16))}… unchanged</code></dd></div></dl>
        <div class="cw-actions"><button class="cw-button cw-button-primary" id="cwCorrectionConfirm" type="button">Confirm scoped correction</button><button class="cw-button" id="cwCorrectionCancel" type="button">Cancel</button></div>
      </section>` : correctionCandidate ? `
      <section class="cw-correction" id="cwCorrectionOption">
        <p class="cw-eyebrow">Case-local correction</p>
        <h3>Evidence no longer supports this finding?</h3>
        <p>Preview an exact, reversible withdrawal. Scope, source, and effect are server-owned; the browser cannot change them.</p>
        <div class="cw-actions"><button class="cw-button" id="cwCorrectionReview" type="button">${storedCommandIdentity('correction-preview', loop.claim_id) ? 'Recover correction preview' : 'Review scoped correction'}</button></div>
      </section>` : '';
    const outcomeCopy = loop.outcome === 'decision_ready'
      ? provisionalPlan
        ? 'The inner cycle covers every inquiry in this fallible source plan. Claim completeness remains unverified.'
        : 'The six-role traversal and three deterministic gates certify a decision-ready packet.'
      : loop.outcome === 'abstain'
        ? `The system abstained safely: ${esc(value.abstain_reason || 'the required evidence is unresolved')}`
        : action
          ? provisionalPlan
            ? 'This source-relative inquiry remains provisional. Accepted source spans record what was observed without certifying the customer goal.'
            : 'CasePath selected one bounded evidence obligation. Request one source span; the server alone decides whether its meaning is admissible.'
          : 'The journal is processing the accepted transition.';
    const proposedAction = provisionalPlan ? operational.provisional_next_action : null;
    const visibleNextStateTitle = proposedAction?.enabled
      ? `${({provider: 'Provider', claimant: 'Claimant', authority: 'Authority', internal: 'Internal review'})[proposedAction.audience]} — ${proposedAction.requested_contents[0]}${proposedAction.requested_contents.length > 1 ? ` (+${proposedAction.requested_contents.length - 1} more)` : ''}`
      : provisionalPlan && operational.next_state.kind === 'decision_ready'
        ? 'Review provisional-plan coverage'
        : operational.next_state.title;
    const proposedActionMarkup = proposedAction?.enabled ? `
      <section class="cw-correction" id="cwProvisionalNextAction" data-audience="${esc(proposedAction.audience)}">
        <p class="cw-eyebrow">Fallible proposed follow-up · no dispatch</p>
        <h3>${esc(({provider: 'Request from the provider', claimant: 'Request from the claimant', authority: 'Request from the authority', internal: 'Internal review'})[proposedAction.audience])}</h3>
        <ul>${proposedAction.requested_contents.map(item => `<li>${esc(item)}</li>`).join('')}</ul>
        <p>This proposal comes from the saved model plan. It has not been sent and does not certify that the customer goal is fulfilled.</p>
      </section>` : '';
    const evidenceForm = action && !provisionalPlan ? `
      <form class="cw-evidence-form" id="cwEvidenceForm">
        <p class="cw-authority-badge">Server-acquired bytes · independent semantic authority · no approve, deny, pay, or close authority</p>
        <p class="cw-muted">The browser submits only the current action, revision, acquisition receipts, and exact acquired bytes. It cannot choose a source, parser, finding, normalized value, sufficiency state, or branch.</p>
        <div class="cw-actions">
          <button class="cw-button cw-button-primary" id="cwLoopCommit" type="submit" ${pendingInvalid ? 'disabled' : ''}>${pendingAdvance ? 'Check journal and finish replan' : staged ? 'Complete verified replan' : pendingStage || pendingIntent ? 'Check journal and retry safely' : 'Acquire source and replan'}</button>
        </div>
      </form>` : '';
    const roles = value.six_agent_cycle_receipt.agent_ids.map((agent, index) => `<li data-agent-id="${esc(agent)}" data-receipt-sha256="${esc(value.six_agent_cycle_receipt.agent_receipt_sha256s[index])}"><strong>${esc(label(agent))}</strong><span>receipt ${esc(value.six_agent_cycle_receipt.agent_receipt_sha256s[index].slice(0, 12))}…</span></li>`).join('');
    const gates = value.six_agent_cycle_receipt.deterministic_gate_ids.map((gate, index) => `<li data-gate-id="${esc(gate)}" data-receipt-sha256="${esc(value.six_agent_cycle_receipt.gate_receipt_sha256s[index])}"><strong>${esc(label(gate))}</strong><span>receipt ${esc(value.six_agent_cycle_receipt.gate_receipt_sha256s[index].slice(0, 12))}…</span></li>`).join('');
    return `
      <section class="cw-section cw-loop cw-decision-card" id="cwLoopWorkbench" data-outcome="${esc(loop.outcome)}">
        <p class="cw-eyebrow">Current decision</p>
        <h2 id="cwLoopProposal" data-action-sha256="${esc(action?.action_sha256 || '')}">${esc(action?.title || label(loop.outcome))}</h2>
        <p class="cw-status">${outcomeCopy}</p>
        <div class="cw-state-grid cw-current-process" id="cwCurrentProcess" data-operational-projection-sha256="${esc(operational.projection_sha256)}"><div class="cw-state-item"><span>Current process</span><strong>${esc(operational.current_process?.node_title || operational.current_process?.node_id || 'Not started')}</strong><small>${esc(operational.current_process?.node_id || 'No current node')}</small></div><div class="cw-state-item"><span>Controlling uncertainty</span><strong>${esc(operational.controlling_decision?.title || 'No controlling uncertainty')}</strong><small>${operational.controlling_decision ? `${esc(label(operational.controlling_decision.fact_state))} fact · ${esc(label(operational.controlling_decision.evidence_class))} evidence` : provisionalPlan ? 'All provisional-plan inquiries have been handled' : 'Current mandatory obligations are resolved'}</small></div><div class="cw-state-item"><span>Journal state</span><strong>${esc(label(operational.workflow_state))}</strong><small>revision ${esc(operational.claim_loop_prefix?.revision || '—')}</small></div></div>
        <section class="cw-progress-panel" id="cwEvidenceProgress"><header><strong>${provisionalPlan ? 'Provisional-plan coverage' : 'Evidence readiness'}</strong><span>${esc(operational.pending_evidence_count)} ${provisionalPlan ? 'proposed inquiries' : 'current mandatory'} unresolved</span></header>${evidenceProgressMarkup(operational)}</section>
        <p class="cw-status" id="cwPrincipalBlocker" data-principal-blocker="${esc(operational.principal_blocker)}">Controlling blocker: ${esc(operational.principal_blocker)}</p>
        <p class="cw-status" id="cwNextState" data-next-state="${esc(canonicalJson(operational.next_state))}">${proposedAction?.enabled ? 'Proposed next step' : 'Next safe state'}: ${esc(visibleNextStateTitle)}</p>
        ${proposedActionMarkup}
        ${proposalRevisionMarkup(loop.latest_proposal_revision)}
        ${loop.latest_proposal_revision ? '<details id="cwSavedEvidenceAssessment"><summary>Saved evidence assessment</summary><p>These admitted states are retained for reference. The updated review above records the latest proposed readings and request changes.</p>' : ''}
        <div class="cw-evidence-classes" id="cwEvidenceClasses">${evidenceClassMarkup}</div>
        ${loop.latest_proposal_revision ? '</details>' : ''}
        <details class="cw-source-observations"><summary>Accepted source observations (${observations.length})</summary><ul class="cw-evidence-list" id="cwEvidencePresent">${observationEvidence}</ul></details>
        <div class="cw-safety-boundary"><strong>Safety boundary</strong><span>${loop.outcome === 'decision_ready' ? provisionalPlan ? 'Coverage applies only to the model-proposed inquiries. It does not certify the claim, legal sufficiency, or completeness.' : 'The packet is evidence-ready, but CasePath still cannot approve, deny, pay, or close the claim.' : loop.outcome === 'abstain' ? 'Mandatory evidence remains unresolved. CasePath stopped rather than infer an unsupported fact.' : loop.outcome === 'processing' ? 'One journaled transition is in flight. No second action is available until its receipt is reconciled.' : provisionalPlan ? 'Only an answer whose cited source bytes match this active inquiry can enter the journal.' : 'This action submits one exact evidence object for independent admission or safe rejection. It cannot approve, deny, pay, or close the claim.'}</span></div>
        ${evidenceForm}
        ${correctionMarkup}
        ${staged ? `<p class="cw-stage-receipt" id="cwEvidenceStageReceipt" data-receipt-sha256="${esc(staged.receipt_sha256)}">Registration receipt <code>${esc(staged.receipt_sha256.slice(0, 16))}…</code></p>` : ''}
        ${loop.decision_packet ? `<p class="cw-terminal-receipt">${provisionalPlan ? 'Provisional-plan coverage receipt' : 'Certified packet'} <code>${esc(loop.decision_packet.packet_sha256.slice(0, 16))}…</code></p>` : ''}
        <p class="cw-verified-line">Inner journal cycle: 6 deterministic roles · 3 gates · zero additional provider calls.</p>
        <details class="cw-receipt" id="cwDiagnostics"><summary>Verification and receipts</summary><div class="cw-cycle-grid"><div><h4>Six deterministic roles</h4><ul class="cw-receipt-list" id="cwAgentReceipts">${roles}</ul></div><div><h4>Three authority gates</h4><ul class="cw-receipt-list" id="cwGateReceipts">${gates}</ul></div></div><pre data-receipt-json="${esc(canonicalJson({loop_id:value.loop_id,revision:value.revision,state_sha256:value.state_sha256,last_event_sha256:value.last_event_sha256,cycle_receipt_sha256:value.six_agent_cycle_receipt.receipt_sha256,audit_sha256:loop.audit.receipt_sha256,model_calls:loop.audit.model_calls,provider_calls:loop.audit.provider_calls,cost_usd:loop.audit.cost_usd}))}">${esc(JSON.stringify({loop_id:value.loop_id,revision:value.revision,state_sha256:value.state_sha256,last_event_sha256:value.last_event_sha256,cycle_receipt_sha256:value.six_agent_cycle_receipt.receipt_sha256,audit_sha256:loop.audit.receipt_sha256,model_calls:loop.audit.model_calls,provider_calls:loop.audit.provider_calls,cost_usd:loop.audit.cost_usd}, null, 2))}</pre></details>
      </section>`;
  }

  async function openClaim(claimId) {
    const epoch = ++state.detailEpoch;
    state.mutationBusy = null;
    state.correctionPreview = null;
    state.nativeInvestigation = null;
    state.detailController?.abort();
    const controller = new AbortController();
    state.detailController = controller;
    const detailRoot = $('#cwDetail');
    const panel = $('#cwDetailPanel');
    state.returnFocus = document.activeElement;
    state.returnClaimId = claimId;
    $('.cw-shell').inert = true;
    detailRoot.hidden = false;
    document.body.style.overflow = 'hidden';
    panel.innerHTML = '<div class="cw-empty"><h2>Opening source-linked claim…</h2></div>';
    try {
      const detail = await validateDetailResponse(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}`, {signal:controller.signal}), claimId);
      if (epoch !== state.detailEpoch) return;
      const loop = detail.state.workflow_state === 'in_review'
        ? await loadClaimLoop(claimId, {allowMissing:true, signal:controller.signal})
        : null;
      if (epoch !== state.detailEpoch) return;
      state.loop = loop;
      const pendingLoop = storedCommandIdentity('loop', claimId);
      if (loop && pendingLoop && !pendingLoop.invalid) {
        const expected = pendingLoop.parsedBody;
        if (
          expected.expected_workspace_revision === loop.workspace_revision
          && expected.expected_workspace_state_sha256 === loop.workspace_state_sha256
        ) clearCommandIdentity('loop', claimId);
      }
      state.detail = detail;
      state.detailPriority = null;
      renderDetail(detail);
      void loadEvidenceInvestigation(claimId, activeDetailContext(), controller.signal);
      history.replaceState(null, '', `#claim=${encodeURIComponent(claimId)}`);
      const pendingIntent = storedCommandIdentity('evidence-intent', claimId);
      const pendingEvidence = storedCommandIdentity('evidence', claimId);
      const pendingAdvance = storedCommandIdentity('advance', claimId);
      if (state.loop && (pendingIntent && !pendingIntent.invalid || pendingEvidence && !pendingEvidence.invalid || pendingAdvance && !pendingAdvance.invalid)) {
        void commitLoopObservation();
      }
    } catch (error) {
      if (error.name === 'AbortError' || epoch !== state.detailEpoch) return;
      panel.innerHTML = `<div class="cw-error"><h2>Claim unavailable</h2><p>${esc(error.message)}</p><div class="cw-actions"><button class="cw-button" data-close-detail>Close</button></div></div>`;
      panel.querySelector('[data-close-detail]')?.addEventListener('click', closeDetail);
      panel.focus();
    }
  }

  function renderDetail(detail) {
    const value = detail.state;
    let recoveredCommand = '';
    const pendingStart = storedCommandIdentity('start', value.claim_id);
    if (pendingStart && !pendingStart.invalid && value.intake_assessment && value.workflow_state === 'in_review') {
      clearCommandIdentity('start', value.claim_id);
      recoveredCommand = 'Recovered the committed assessment from the authoritative journal after a lost response.';
    }
    const pendingStartUnresolved = Boolean(pendingStart && !pendingStart.invalid && !(value.intake_assessment && value.workflow_state === 'in_review'));
    let invalidPendingCommand = Boolean(pendingStart?.invalid);
    const pendingAssign = storedCommandIdentity('assign', value.claim_id);
    let pendingAssignBody = null;
    if (pendingAssign) {
      if (pendingAssign.invalid) {
        invalidPendingCommand = true;
      } else {
        pendingAssignBody = pendingAssign.parsedBody;
      }
      if (pendingAssignBody && value.owner === pendingAssignBody.owner) {
        clearCommandIdentity('assign', value.claim_id);
        recoveredCommand = 'Recovered the committed assignment from the authoritative journal after a lost response.';
        pendingAssignBody = null;
      }
    }
    const pendingIntent = storedCommandIdentity('evidence-intent', value.claim_id);
    const pendingEvidence = storedCommandIdentity('evidence', value.claim_id);
    const pendingAdvance = storedCommandIdentity('advance', value.claim_id);
    const pendingCorrectionPreview = storedCommandIdentity('correction-preview', value.claim_id);
    const pendingCorrectionApply = storedCommandIdentity('correction-apply', value.claim_id);
    if (state.loop?.latest_correction && pendingCorrectionApply?.parsedBody?.correction_id === state.loop.latest_correction.correction_id) {
      // The authoritative correction event proves that its server-enumerated
      // preview was consumed, even when the browser lost the apply response.
      // Clear both halves of that one lineage on reload; retaining the preview
      // would falsely present a completed correction as still pending.
      clearCommandIdentity('correction-preview', value.claim_id);
      clearCommandIdentity('correction-apply', value.claim_id);
      state.correctionPreview = null;
    }
    const loopCommandPending = Boolean(pendingIntent || pendingEvidence || pendingAdvance || pendingCorrectionPreview || pendingCorrectionApply);
    invalidPendingCommand = invalidPendingCommand || Boolean(pendingIntent?.invalid || pendingEvidence?.invalid || pendingAdvance?.invalid || pendingCorrectionPreview?.invalid || pendingCorrectionApply?.invalid);
    const priority = state.items.find(item => item.claim_id === value.claim_id && item.state_sha256 === value.state_sha256)
      || (state.detailPriority?.claim_id === value.claim_id && state.detailPriority.state_sha256 === value.state_sha256 ? state.detailPriority : null);
    const assessment = value.intake_assessment;
    const winningScore = assessment?.domain_scores?.find(row => row.claim_type === assessment.claim_type);
    const assessmentMarkup = assessment ? `
        <details class="cw-section cw-secondary" data-workbench-assessment>
          <summary>Accepted intake and policy</summary>
          <div class="cw-secondary-body">
          <p class="cw-eyebrow">Source-bound workbench</p>
          <h3>${esc(assessment.policy_template.title)}</h3>
          <div class="cw-state-grid"><div class="cw-state-item"><span>Public intake family</span><strong>${esc(label(assessment.claim_type))}</strong></div><div class="cw-state-item"><span>Accepted intake node</span><strong>${esc(assessment.current_node.label)}</strong></div><div class="cw-state-item"><span>Responsibility</span><strong>${esc(label(assessment.current_node.responsibility))}</strong></div><div class="cw-state-item"><span>Classifier evidence</span><strong>${esc((winningScore?.matched_terms || []).join(', '))}</strong></div></div>
          <p class="cw-status">This deterministic compiler uses only the admitted customer-message subject to choose among the three equally visible public playbooks. It does not inspect benchmark labels, expected actions, or outcomes.</p>
          <h4>Possible next branches</h4>
          <ul class="cw-priority">${assessment.outgoing_branches.map(branch => `<li><strong>${esc(branch.target_label)}</strong><span>${esc(branch.condition)}${branch.optional_path ? ' · conditional' : ''}</span></li>`).join('')}</ul>
          <h4>Policy guardrails</h4>
          <ul class="cw-priority">${assessment.policy_clause_refs.map(clause => `<li><span>${esc(clause.content)}</span><small>${esc(clause.clause_id)} · SHA ${esc(clause.content_sha256.slice(0,12))}…</small></li>`).join('')}</ul>
          <details class="cw-receipt"><summary>Compiler proof</summary><pre>${esc(JSON.stringify({compiler_id:assessment.compiler_id,assessment_sha256:assessment.assessment_sha256,message_sha256:assessment.message_sha256,policy_template_sha256:assessment.policy_template.template_sha256,static_policy_file_sha256:assessment.static_policy_file_sha256,classifier_catalog_sha256:assessment.classifier_catalog_sha256,activity:assessment.activity}, null, 2))}</pre></details>
          </div>
        </details>` : '';
    const primaryWorkspaceAction = !state.loop && value.workflow_state !== 'in_review' ? `
      <section class="cw-section cw-decision-card">
        <p class="cw-eyebrow">Current decision</p>
        <h2>${esc(value.next_safe_action)}</h2>
        <p class="cw-status">${esc(value.principal_blocker)}</p>
        <div class="cw-safety-boundary"><strong>Safety boundary</strong><span>This action records or reconciles state only. It cannot approve, deny, pay, or close the claim.</span></div>
        <div class="cw-actions">${value.failure_or_unknown_effect ? '<button class="cw-button cw-button-primary" id="cwReconcile">Reconcile unknown effect</button>' : `<button class="cw-button cw-button-primary" id="cwStart" ${invalidPendingCommand ? 'disabled' : ''}>${pendingStartUnresolved ? 'Retry pending assessment' : value.workflow_state === 'waiting' ? 'Resume deterministic assessment' : 'Start deterministic assessment'}</button>`}</div>
      </section>` : '';
    const operational = state.loop?.operational_projection;
    const provisionalPlan = inquiryRecord(state.loop?.provisional_source_binding);
    const visibleReadiness = operational
      ? provisionalPlan && operational.readiness_state === 'decision_ready' ? 'Provisional plan covered' : label(operational.readiness_state)
      : label(value.readiness_state);
    const visibleGaps = operational
      ? operational.pending_evidence_count
      : value.pending_evidence_count == null ? 'Not assessed' : value.pending_evidence_count;
    $('#cwDetailPanel').innerHTML = `
      <header class="cw-detail-head"><div class="cw-detail-title"><small>${esc(value.claim_id)}</small><h2>${esc(detail.message.subject)}</h2><p>${esc(value.binding.language)} · received ${esc(stamp(value.binding.received_at))}</p></div><button class="cw-button cw-close" data-close-detail aria-label="Close claim">×</button></header>
      <div class="cw-detail-body">
        <section class="cw-state-strip" aria-label="Authoritative claim state"><span><small>Workflow</small><strong>${esc(operational ? label(operational.workflow_state) : label(value.workflow_state))}</strong></span><span><small>Readiness</small><strong>${esc(visibleReadiness)}</strong></span><span><small>Owner</small><strong>${esc(value.owner || 'Unassigned')}</strong></span><span><small>Evidence gaps</small><strong>${esc(visibleGaps)}</strong></span></section>
        ${primaryWorkspaceAction}
        ${loopWorkbenchMarkup(state.loop, value)}
        <div id="cwEvidenceInvestigationMount">${evidenceInvestigationMarkup(state.nativeInvestigation, state.loop)}</div>
        <p class="cw-command-status" id="cwCommandStatus" role="status" aria-live="polite">${invalidPendingCommand ? 'A local pending-command receipt is corrupt. The claim remains read-only until authoritative state is reloaded.' : loopCommandPending ? 'A source or replan outcome is unresolved. Evidence inputs are locked; the single action above checks the journal with the exact command.' : pendingAssignBody ? `The assignment outcome is unknown. Retry uses the exact original command.` : pendingStartUnresolved ? 'The assessment outcome is unknown. Retry uses the exact original command.' : ''}</p>
        ${assessmentMarkup}
        <details class="cw-section cw-secondary" id="cwSourceRecord"><summary>Accepted source record</summary><div class="cw-secondary-body"><p class="cw-body-copy" lang="${esc(value.binding.language)}">${esc(detail.message.body)}</p><div class="cw-artifacts">${detail.artifacts.map(artifact => `<a class="cw-artifact" href="${esc(artifact.download_url)}" target="_blank" rel="noopener"><span class="cw-artifact-icon">${esc(artifact.role === 'customer_message' ? 'MSG' : 'FILE')}</span><span class="cw-artifact-copy"><strong>${esc(artifact.file_name)}</strong><span>${esc(artifact.media_type)} · ${bytes(artifact.size_bytes)} · SHA ${esc(artifact.sha256.slice(0,12))}…</span></span></a>`).join('')}</div></div></details>
        <details class="cw-section cw-secondary" id="cwAssignment" ${!value.owner || pendingAssignBody ? 'open' : ''}><summary>Assignment</summary><div class="cw-secondary-body"><form class="cw-owner-form" id="cwOwnerForm"><input id="cwOwnerInput" maxlength="80" value="${esc(pendingAssignBody?.owner || value.owner || '')}" placeholder="Handler name" aria-label="Assigned handler" ${pendingAssignBody || invalidPendingCommand || loopCommandPending ? 'readonly' : ''}><button class="cw-button" type="submit" ${invalidPendingCommand || loopCommandPending ? 'disabled' : ''}>${pendingAssignBody ? 'Retry pending assignment' : 'Assign'}</button></form></div></details>
        <details class="cw-section cw-secondary" id="cwExplainablePriority"><summary>Explainable priority</summary><p class="cw-status" data-priority-status ${priority ? 'hidden' : ''}>Loading the verified priority tuple…</p><ol class="cw-priority">${priority ? priorityList(priority) : ''}</ol></details>
        <details class="cw-section cw-secondary"><summary>Workspace receipt and export</summary><div class="cw-secondary-body"><pre class="cw-technical-receipt">${esc(JSON.stringify({detail_sha256:detail.detail_sha256 || null,state_sha256:value.state_sha256,binding_sha256:value.binding.binding_sha256,last_event_sha256:value.last_event_sha256,revision:value.revision,authority:detail.authority}, null, 2))}</pre><button class="cw-button" id="cwExport" type="button">Export verified status</button></div></details>
      </div>`;
    root.querySelectorAll('[data-close-detail]').forEach(button => button.addEventListener('click', closeDetail));
    $('#cwOwnerForm').addEventListener('submit', event => { event.preventDefault(); assignOwner(); });
    $('#cwStart')?.addEventListener('click', startClaim);
    $('#cwReconcile')?.addEventListener('click', reconcileClaim);
    $('#cwEnsureLoop')?.addEventListener('click', ensureClaimLoop);
    bindNativeInvestigationActions();
    $('#cwEvidenceForm')?.addEventListener('submit', event => { event.preventDefault(); commitLoopObservation(); });
    $('#cwCorrectionReview')?.addEventListener('click', previewWorkspaceCorrection);
    $('#cwCorrectionConfirm')?.addEventListener('click', applyWorkspaceCorrection);
    $('#cwCorrectionCancel')?.addEventListener('click', cancelWorkspaceCorrection);
    $('#cwExport').addEventListener('click', exportClaim);
    if (recoveredCommand) $('#cwCommandStatus').textContent = recoveredCommand;
    $('#cwDetailPanel').focus?.();
    if (!priority) void loadOpenPriority(value.claim_id, value.state_sha256, activeDetailContext(), state.detailController?.signal);
  }

  async function assignOwner() {
    const detail = state.detail;
    const context = activeDetailContext();
    const owner = $('#cwOwnerInput').value.trim();
    if (!owner) { $('#cwCommandStatus').textContent = 'Enter a handler name.'; return; }
    $('#cwCommandStatus').textContent = 'Journaling assignment…';
    try {
      const body = {owner,expected_revision:detail.state.revision};
      const pending = commandIdentity('assign', detail.state.claim_id, body);
      const response = await validateMutationResponse(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(detail.state.claim_id)}/owner`, {method:'POST',headers:{'Content-Type':'application/json','X-CasePath-Idempotency-Key':pending.key},body:pending.body}), detail.state.claim_id, 'WORKSPACE_OWNER_ASSIGNED', detail.state);
      if (!isActiveDetail(context)) return;
      await reflectAcceptedMutation(response, 'Assignment journaled and replayable.', 'assign', context);
    } catch (error) {
      if (!isActiveDetail(context)) return;
      if (error.responseReceived && !error.ambiguousResponse) {
        clearCommandIdentity('assign', detail.state.claim_id);
        await reloadDetailAfterDefinitiveRejection(error.message);
        return;
      }
      $('#cwCommandStatus').textContent = error.transportFailure || error.ambiguousResponse ? `No valid response received: ${error.message}. Outcome is unknown; retry will use the exact same command.` : `Assignment rejected without a state change: ${error.message}`;
    }
  }

  async function startClaim() {
    const detail = state.detail;
    const context = activeDetailContext();
    $('#cwCommandStatus').textContent = 'Starting deterministic assessment…';
    try {
      const body = {expected_revision:detail.state.revision};
      const pending = commandIdentity('start', detail.state.claim_id, body);
      const response = await validateMutationResponse(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(detail.state.claim_id)}/start`, {method:'POST',headers:{'Content-Type':'application/json','X-CasePath-Idempotency-Key':pending.key},body:pending.body}), detail.state.claim_id, 'WORKSPACE_PROCESSING_STARTED', detail.state);
      if (!isActiveDetail(context)) return;
      await reflectAcceptedMutation(response, 'Source-bound assessment compiled and durably journaled.', 'start', context);
    } catch (error) {
      if (!isActiveDetail(context)) return;
      if (error.responseReceived && !error.ambiguousResponse) {
        clearCommandIdentity('start', detail.state.claim_id);
        await reloadDetailAfterDefinitiveRejection(error.message);
        return;
      }
      $('#cwCommandStatus').textContent = error.transportFailure || error.ambiguousResponse ? `No valid response received: ${error.message}. Outcome is unknown; retry will use the exact same command.` : `Assessment rejected without a state change: ${error.message}`;
    }
  }

  function setLoopMutationBusy(value, message = '', context = null) {
    if (value) {
      state.mutationBusy = context ? {...context} : activeDetailContext();
    } else if (
      !context
      || (state.mutationBusy?.epoch === context.epoch && state.mutationBusy?.claimId === context.claimId)
    ) {
      state.mutationBusy = null;
    } else {
      return;
    }
    const active = Boolean(state.mutationBusy);
    root.querySelectorAll('#cwDetailPanel button:not([data-close-detail]), #cwDetailPanel input, #cwDetailPanel select, #cwDetailPanel textarea').forEach(control => { control.disabled = active; });
    if (message && $('#cwCommandStatus')) $('#cwCommandStatus').textContent = message;
  }

  async function ensureClaimLoop() {
    if (state.mutationBusy || !state.detail) return;
    const detail = state.detail;
    const context = activeDetailContext();
    setLoopMutationBusy(true, 'Opening the journal-backed evidence workbench…', context);
    try {
      const body = {expected_workspace_revision:detail.state.revision,expected_workspace_state_sha256:detail.state.state_sha256};
      const pending = commandIdentity('loop', detail.state.claim_id, body);
      const posted = await requireVerifiedResponse(validateLoopView(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(detail.state.claim_id)}/loop`, {method:'POST',headers:{'Content-Type':'application/json','X-CasePath-Idempotency-Key':pending.key},body:pending.body}), detail.state.claim_id));
      if (!isActiveDetail(context)) return;
      const value = await loadClaimLoop(detail.state.claim_id);
      if (!isActiveDetail(context)) return;
      if (
        value.loop_state.state_sha256 !== posted.loop_state.state_sha256
        || value.workspace_revision !== posted.workspace_revision
        || value.workspace_state_sha256 !== posted.workspace_state_sha256
        || value.compilation_receipt.receipt_sha256 !== posted.compilation_receipt.receipt_sha256
      ) {
        const error = new Error('The authoritative journal did not confirm the exact evidence workbench');
        error.ambiguousResponse = true;
        throw error;
      }
      clearCommandIdentity('loop', detail.state.claim_id);
      state.loop = value;
      await loadQueue();
      if (!isActiveDetail(context)) return;
      renderDetail(detail);
      $('#cwCommandStatus').textContent = 'Evidence workbench is bound to the accepted claim journal.';
    } catch (error) {
      if (!isActiveDetail(context)) return;
      if (error.responseReceived && !error.ambiguousResponse) {
        clearCommandIdentity('loop', detail.state.claim_id);
        try {
          const recovered = await loadClaimLoop(detail.state.claim_id, {allowMissing:true});
          if (isActiveDetail(context)) state.loop = recovered;
        } catch (_) { /* Keep the evidence workbench closed when refresh fails. */ }
      }
      $('#cwCommandStatus').textContent = `Evidence workbench failed closed: ${error.message}. No claim evidence was accepted.`;
      root.querySelectorAll('#cwDetailPanel button, #cwDetailPanel input, #cwDetailPanel select, #cwDetailPanel textarea').forEach(control => { control.disabled = false; });
    } finally {
      setLoopMutationBusy(false, '', context);
    }
  }

  async function exactStageBody(loop) {
    const pending = storedCommandIdentity('evidence', loop.claim_id);
    if (pending?.invalid) throw new Error('The pending evidence command is corrupt');
    if (pending) {
      if (
        Object.keys(pending.parsedBody).sort().join('|') !== REGISTRATION_BODY_FIELDS.slice().sort().join('|')
        || pending.parsedBody.idempotency_key !== pending.key
      ) throw new Error('The pending evidence command differs from the closed registration contract');
      return pending.parsedBody;
    }
    const contract = loop.input_contract;
    const action = loop.loop_state.selected_action;
    if (!contract || !action || contract.action_id !== action.action_id || contract.expected_revision !== loop.loop_state.revision) {
      throw new Error('The current source-acquisition authority is unavailable');
    }
    const intentBody = {action_id:action.action_id, expected_revision:loop.loop_state.revision};
    const intentCommand = commandIdentity('evidence-intent', loop.claim_id, intentBody);
    const intentRequest = {...intentBody, idempotency_key:intentCommand.key};
    const intentResponse = await requireVerifiedResponse(validateEvidenceIntentResponse(
      await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(loop.claim_id)}/loop/evidence/intents`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(intentRequest),
      }),
      loop,
      intentBody,
      intentCommand.key,
    ));
    const intentKey = intentResponse.intent.idempotency_key;
    if (intentResponse.recovered_durable_acquisition) {
      clearCommandIdentity('evidence-intent', loop.claim_id);
      commandIdentity('evidence-intent', loop.claim_id, intentBody, intentKey);
    }
    const acquisitionResponse = await requireVerifiedResponse(validateEvidenceAcquisitionResponse(
      await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(loop.claim_id)}/loop/evidence/intents/${encodeURIComponent(intentResponse.intent.intent_id)}/acquire`, {method:'POST'}),
      loop,
      intentResponse.intent,
    ));
    const body = {
      schema: contract.registration_schema,
      action_id: action.action_id,
      expected_revision: loop.loop_state.revision,
      idempotency_key: intentKey,
      acquisition_intent_id: intentResponse.intent.intent_id,
      acquisition_receipt_id: acquisitionResponse.acquisition_receipt.acquisition_receipt_id,
      content_b64: acquisitionResponse.content_b64,
    };
    if (canonicalJson(Object.keys(body)) !== canonicalJson(contract.registration_body_fields)) {
      throw new Error('The browser registration envelope differs from the closed server contract');
    }
    commandIdentity('evidence', loop.claim_id, body, intentKey);
    return body;
  }

  function exactAdvanceBody(loop) {
    const pending = storedCommandIdentity('advance', loop.claim_id);
    if (pending?.invalid) throw new Error('The pending replan command is corrupt');
    if (pending) return pending.parsedBody;
    const staged = loop.stage_receipt;
    const action = loop.loop_state.selected_action;
    if (!staged || !action) throw new Error('An exact staged observation is required before replanning');
    return {
      expected_revision: loop.loop_state.revision,
      expected_state_sha256: loop.loop_state.state_sha256,
      action_sha256: action.action_sha256,
      stage_receipt_sha256: staged.receipt_sha256,
    };
  }

  async function verifiedAdvanceBaseline(loop, pending, body) {
    const before = pending?.before_loop_state;
    const observations = before?.observations;
    if (
      !before
      || !Array.isArray(observations)
      || !Number.isSafeInteger(before.revision)
      || before.revision !== body.expected_revision
      || before.state_sha256 !== body.expected_state_sha256
      || before.loop_id !== loop.loop_state.loop_id
      || before.claim_id !== loop.claim_id
      || before.selected_action?.action_sha256 !== body.action_sha256
      || !await validClaimLoopStateHash(before)
    ) throw new Error('The pending replan lacks its exact hash-verified pre-advance state');
    return Object.freeze({revision:before.revision, observationCount:observations.length});
  }

  async function stageLoopEvidence(context, loop) {
    const existingStage = loop.stage_receipt;
    const pendingIntent = storedCommandIdentity('evidence-intent', loop.claim_id);
    const pendingExisting = storedCommandIdentity('evidence', loop.claim_id);
    if (existingStage) {
      if (pendingExisting && !pendingExisting.invalid) {
        const expected = pendingExisting.parsedBody;
        const raw = base64Bytes(expected.content_b64);
        if (
          existingStage.idempotency_key !== expected.idempotency_key
          || existingStage.parent_revision !== expected.expected_revision
          || existingStage.parent_state_sha256 !== loop.loop_state.state_sha256
          || existingStage.action_id !== loop.loop_state.selected_action?.action_id
          || existingStage.action_id !== expected.action_id
          || existingStage.action_sha256 !== loop.loop_state.selected_action?.action_sha256
          || existingStage.evidence_item_id !== loop.loop_state.selected_action?.evidence_item_id
          || existingStage.acquisition_intent_id !== expected.acquisition_intent_id
          || existingStage.acquisition_receipt_id !== expected.acquisition_receipt_id
          || existingStage.content_length !== raw.byteLength
          || existingStage.content_sha256 !== await sha256Bytes(raw)
        ) throw new Error('The journaled stage differs from the pending browser command');
        clearCommandIdentity('evidence', loop.claim_id);
      }
      if (pendingIntent && !pendingIntent.invalid) {
        if (
          existingStage.idempotency_key !== pendingIntent.key
          || pendingIntent.parsedBody.action_id !== existingStage.action_id
          || pendingIntent.parsedBody.expected_revision !== existingStage.parent_revision
        ) throw new Error('The journaled stage differs from the pending source intent');
        clearCommandIdentity('evidence-intent', loop.claim_id);
      }
      return loop;
    }
    const body = await exactStageBody(loop);
    const pending = commandIdentity('evidence', loop.claim_id, body);
    if (pending.key !== body.idempotency_key) throw new Error('The registration key differs from its acquisition intent');
    const response = await requireVerifiedResponse(validateStageResponse(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(loop.claim_id)}/loop/evidence`, {method:'POST',headers:{'Content-Type':'application/json','X-CasePath-Idempotency-Key':pending.key},body:pending.body}), loop, body));
    if (!isActiveDetail(context)) return null;
    const fresh = await loadClaimLoop(loop.claim_id);
    if (!isActiveDetail(context)) return null;
    if (fresh.stage_receipt?.receipt_sha256 !== response.stage_receipt.receipt_sha256) throw new Error('The authoritative journal did not confirm the staged receipt');
    clearCommandIdentity('evidence', loop.claim_id);
    clearCommandIdentity('evidence-intent', loop.claim_id);
    return fresh;
  }

  async function advanceClaimLoop(context, loop) {
    const body = exactAdvanceBody(loop);
    const existingPending = storedCommandIdentity('advance', loop.claim_id);
    const pending = commandIdentity(
      'advance',
      loop.claim_id,
      body,
      null,
      existingPending ? null : {before_loop_state:loop.loop_state},
    );
    const baseline = await verifiedAdvanceBaseline(loop, pending, body);
    const response = await requireVerifiedResponse(validateAdvanceResponse(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(loop.claim_id)}/loop/advance`, {method:'POST',headers:{'Content-Type':'application/json','X-CasePath-Idempotency-Key':pending.key},body:pending.body}), loop, body));
    if (!isActiveDetail(context)) return null;
    const fresh = await loadClaimLoop(loop.claim_id);
    if (!isActiveDetail(context)) return null;
    if (fresh.loop_state.state_sha256 !== response.claim_loop_response.state_sha256) {
      const error = new Error('The authoritative journal did not confirm the exact replan state');
      error.ambiguousResponse = true;
      throw error;
    }
    const status = claimLoopAdvanceStatus({
      beforeRevision:baseline.revision,
      afterRevision:fresh.loop_state.revision,
      beforeObservationCount:baseline.observationCount,
      afterObservationCount:fresh.loop_state.observations.length,
      outcome:fresh.outcome,
    });
    clearCommandIdentity('advance', loop.claim_id);
    return {loop:fresh, status};
  }

  async function commitLoopObservation() {
    if (state.mutationBusy || !state.detail || !state.loop) return;
    const context = activeDetailContext();
    let loop = state.loop;
    setLoopMutationBusy(true, 'Validating the source, applying independent admission policy, and rerunning six roles and three gates…', context);
    try {
      if (!storedCommandIdentity('advance', loop.claim_id)) {
        loop = await stageLoopEvidence(context, loop);
        if (!loop || !isActiveDetail(context)) return;
      }
      const advance = await advanceClaimLoop(context, loop);
      if (!advance || !isActiveDetail(context)) return;
      ({loop} = advance);
      state.loop = loop;
      await loadQueue();
      if (!isActiveDetail(context)) return;
      renderDetail(state.detail);
      $('#cwCommandStatus').textContent = advance.status.copy;
    } catch (error) {
      if (!isActiveDetail(context)) return;
      if (error.responseReceived && !error.ambiguousResponse) {
        clearCommandIdentity('evidence-intent', context.claimId);
        clearCommandIdentity('evidence', context.claimId);
        clearCommandIdentity('advance', context.claimId);
        try {
          const recovered = await loadClaimLoop(context.claimId);
          if (isActiveDetail(context)) state.loop = recovered;
        } catch (_) { /* Preserve the fail-closed message when refresh also fails. */ }
      }
      if (!isActiveDetail(context)) return;
      renderDetail(state.detail);
      $('#cwCommandStatus').textContent = error.transportFailure || error.ambiguousResponse
        ? `No valid completion receipt was received: ${error.message}. Inputs are locked; use the same action to check the journal and retry safely.`
        : `Observation was rejected without being applied: ${error.message}. Authoritative state was reloaded.`;
    } finally {
      setLoopMutationBusy(false, '', context);
    }
  }

  async function previewWorkspaceCorrection() {
    if (state.mutationBusy || !state.detail || !state.loop) return;
    const context = activeDetailContext();
    const loop = state.loop;
    const candidate = loop.correction_candidates?.[0];
    if (!candidate) return;
    setLoopMutationBusy(true, 'Verifying the exact source, scope, rollback, and unchanged unrelated facts…', context);
    try {
      const body = {
        candidate_sha256: candidate.candidate_sha256,
        expected_revision: loop.loop_state.revision,
        expected_state_sha256: loop.loop_state.state_sha256,
      };
      const pending = commandIdentity('correction-preview', loop.claim_id, body);
      const response = await requireVerifiedResponse(validateCorrectionPreview(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(loop.claim_id)}/loop/corrections/preview`, {method:'POST',headers:{'Content-Type':'application/json','X-CasePath-Idempotency-Key':pending.key},body:pending.body}), loop, candidate));
      if (!isActiveDetail(context)) return;
      state.correctionPreview = {claimId:loop.claim_id,value:response};
      renderDetail(state.detail);
      $('#cwCommandStatus').textContent = 'Correction preview verified. The claim journal is unchanged until explicit confirmation.';
    } catch (error) {
      if (!isActiveDetail(context)) return;
      if (error.responseReceived && !error.ambiguousResponse) {
        clearCommandIdentity('correction-preview', loop.claim_id);
        state.correctionPreview = null;
      }
      $('#cwCommandStatus').textContent = `Correction preview failed closed: ${error.message}`;
    } finally {
      setLoopMutationBusy(false, '', context);
    }
  }

  function cancelWorkspaceCorrection() {
    if (!state.detail || !state.loop) return;
    clearCommandIdentity('correction-preview', state.loop.claim_id);
    state.correctionPreview = null;
    renderDetail(state.detail);
    $('#cwCommandStatus').textContent = 'Correction cancelled. The authoritative claim journal was not changed.';
  }

  async function applyWorkspaceCorrection() {
    if (state.mutationBusy || !state.detail || !state.loop || !state.correctionPreview) return;
    const context = activeDetailContext();
    const loop = state.loop;
    const preview = state.correctionPreview.value;
    setLoopMutationBusy(true, 'Applying one scoped correction and rerunning six roles and three gates…', context);
    try {
      const body = {correction_id:preview.correction_id};
      const pending = commandIdentity('correction-apply', loop.claim_id, body);
      const response = await requireVerifiedResponse(validateCorrectionApplyResponse(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(loop.claim_id)}/loop/corrections`, {method:'POST',headers:{'Content-Type':'application/json','X-CasePath-Idempotency-Key':pending.key},body:pending.body}), loop, preview.correction_id, pending.key));
      if (!isActiveDetail(context)) return;
      const fresh = await loadClaimLoop(loop.claim_id);
      if (!isActiveDetail(context)) return;
      if (
        fresh.loop_state.state_sha256 !== response.state_sha256
        || fresh.loop_state.revision !== response.revision
        || fresh.latest_correction?.correction_id !== preview.correction_id
        || fresh.latest_correction?.event_sha256 !== response.command_receipt.event_sha256
        || fresh.outcome === 'processing'
      ) {
        const error = new Error('The authoritative journal did not confirm the scoped correction');
        error.ambiguousResponse = true;
        throw error;
      }
      clearCommandIdentity('correction-preview', loop.claim_id);
      clearCommandIdentity('correction-apply', loop.claim_id);
      state.correctionPreview = null;
      state.loop = fresh;
      await loadQueue();
      if (!isActiveDetail(context)) return;
      renderDetail(state.detail);
      $('#cwCommandStatus').textContent = 'Scoped correction committed once. The affected obligation was replanned; unrelated facts stayed unchanged.';
    } catch (error) {
      if (!isActiveDetail(context)) return;
      if (error.responseReceived && !error.ambiguousResponse) {
        clearCommandIdentity('correction-apply', loop.claim_id);
        try {
          const fresh = await loadClaimLoop(loop.claim_id);
          if (isActiveDetail(context)) state.loop = fresh;
        } catch (_) { /* Retain the verified preview when refresh is unavailable. */ }
      }
      if (!isActiveDetail(context)) return;
      renderDetail(state.detail);
      $('#cwCommandStatus').textContent = error.transportFailure || error.ambiguousResponse
        ? `No valid correction completion receipt was received: ${error.message}. Retry uses the exact same correction.`
        : `Correction was rejected without a journal change: ${error.message}`;
    } finally {
      setLoopMutationBusy(false, '', context);
    }
  }

  async function reconcileClaim() {
    const detail = state.detail;
    const context = activeDetailContext();
    $('#cwCommandStatus').textContent = 'Reconciling the durable unknown effect…';
    try {
      const body = {expected_revision:detail.state.revision};
      const pending = commandIdentity('reconcile', detail.state.claim_id, body);
      const response = await validateMutationResponse(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(detail.state.claim_id)}/reconcile`, {method:'POST',headers:{'Content-Type':'application/json','X-CasePath-Idempotency-Key':pending.key},body:pending.body}), detail.state.claim_id, 'WORKSPACE_UNKNOWN_RECONCILED', detail.state);
      if (!isActiveDetail(context)) return;
      await reflectAcceptedMutation(response, 'Unknown effect reconciled from the journal.', 'reconcile', context);
    } catch (error) {
      if (!isActiveDetail(context)) return;
      if (error.responseReceived && !error.ambiguousResponse) {
        clearCommandIdentity('reconcile', detail.state.claim_id);
        await reloadDetailAfterDefinitiveRejection(error.message);
        return;
      }
      $('#cwCommandStatus').textContent = error.transportFailure || error.ambiguousResponse ? `No valid response received: ${error.message}. Outcome is unknown; retry will use the exact same command.` : `Reconciliation rejected without a state change: ${error.message}`;
    }
  }

  async function reloadDetailAfterDefinitiveRejection(message) {
    const claimId = state.detail.state.claim_id;
    const context = activeDetailContext();
    root.querySelectorAll('#cwDetailPanel button, #cwDetailPanel input').forEach(control => { control.disabled = true; });
    $('#cwCommandStatus').textContent = `Command rejected: ${message}. Reloading authoritative state before another action is allowed.`;
    try {
      const fresh = await validateDetailResponse(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}`), claimId);
      if (!isActiveDetail(context)) return;
      state.detail = fresh;
      renderDetail(fresh);
      $('#cwCommandStatus').textContent = `Command rejected without a state change: ${message}. Authoritative state reloaded.`;
    } catch (refreshError) {
      if (!isActiveDetail(context)) return;
      $('#cwCommandStatus').textContent = `Command rejected: ${message}. Authoritative state could not be reloaded: ${refreshError.message}`;
    }
  }

  async function exportClaim() {
    const claimId = state.detail.state.claim_id;
    const context = activeDetailContext();
    try {
      const loop = state.loop;
      const value = await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}${loop ? '/loop/export' : '/export'}`);
      if (!isActiveDetail(context)) return;
      const selfHash = value?.export_sha256;
      if (
        !/^[0-9a-f]{64}$/.test(selfHash || '')
        || selfHash !== await sha256(Object.fromEntries(Object.entries(value).filter(([key]) => key !== 'export_sha256')))
        || value.claim_id !== claimId
        || (loop
          ? value.contract !== 'casepath.workspace-claim-loop-export/1.0.0'
            || value.loop_state_sha256 !== loop.loop_state.state_sha256
            || value.loop_audit_sha256 !== loop.audit.receipt_sha256
            || value.outcome !== loop.outcome
          : value.contract !== 'casepath.claim-status-export/1.0.0'
            || value.state_sha256 !== state.detail.state.state_sha256)
      ) throw new Error('The exported status failed authority validation');
      const blob = new Blob([JSON.stringify(value, null, 2) + '\n'], {type:'application/json'});
      const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = `${claimId}-status.json`; link.click(); URL.revokeObjectURL(link.href);
    } catch (error) { $('#cwCommandStatus').textContent = `Export failed: ${error.message}`; }
  }

  async function refreshOpen(claimId) {
    const detail = await validateDetailResponse(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(claimId)}`), claimId);
    state.loop = detail.state.workflow_state === 'in_review' ? await loadClaimLoop(claimId, {allowMissing:true}) : null;
    state.detail = detail;
    renderDetail(detail);
    await loadQueue();
  }

  async function reflectAcceptedMutation(response, message, commandKind, context) {
    try {
      const fresh = await validateDetailResponse(await request(`/api/claim-loops/v1/workspace/claims/${encodeURIComponent(response.state.claim_id)}`), response.state.claim_id);
      if (!isActiveDetail(context)) return;
      if (fresh.state.state_sha256 !== response.state.state_sha256 || fresh.state.last_event_sha256 !== response.event_sha256 || fresh.state.revision !== response.state.revision) throw new Error('the journal snapshot does not confirm the command receipt');
      clearCommandIdentity(commandKind, response.state.claim_id);
      state.detail = fresh;
      renderDetail(fresh);
      await loadQueue();
      if (!isActiveDetail(context)) return;
      $('#cwCommandStatus').textContent = message;
    } catch (error) {
      root.querySelectorAll('#cwDetailPanel button, #cwDetailPanel input').forEach(control => { control.disabled = true; });
      const failure = new Error(`Command receipt is not yet confirmed by the authoritative journal: ${error.message}`);
      failure.ambiguousResponse = true;
      throw failure;
    }
  }

  function closeDetail() {
    state.detailEpoch += 1;
    state.mutationBusy = null;
    state.detailController?.abort();
    state.detailController = null;
    $('#cwDetail').hidden = true;
    $('.cw-shell').inert = false;
    document.body.style.overflow = '';
    state.detail = null;
    state.detailPriority = null;
    state.loop = null;
    state.correctionPreview = null;
    state.nativeInvestigation = null;
    history.replaceState(null, '', `${location.pathname}${location.search}`);
    const currentRow = state.returnClaimId ? root.querySelector(`[data-claim-id="${CSS.escape(state.returnClaimId)}"]`) : null;
    (currentRow || (state.returnFocus?.isConnected ? state.returnFocus : null))?.focus?.();
    state.returnFocus = null;
    state.returnClaimId = null;
    void loadQueue();
  }

  function claimIdFromLocation() {
    const match = location.hash.match(/^#claim=([^&]+)$/);
    if (!match) return null;
    try { return decodeURIComponent(match[1]); }
    catch (_) { return null; }
  }

  function syncClaimFromLocation() {
    const claimId = claimIdFromLocation();
    if (claimId) {
      if (!$('#cwDetail').hidden && state.returnClaimId === claimId) return;
      void openClaim(claimId);
      return;
    }
    if (!$('#cwDetail').hidden) closeDetail();
  }

  $('#cwFilters').addEventListener('submit', event => event.preventDefault());
  $('#cwFilters').addEventListener('input', () => { clearTimeout(state.filterTimer); state.filterTimer = setTimeout(() => loadQueue(), 180); });
  $('#cwFilters').addEventListener('change', () => loadQueue());
  $('#cwRefresh').addEventListener('click', () => loadQueue());
  $('#cwMore').addEventListener('click', () => loadQueue({append:true}));
  root.querySelector('[data-close-detail]').addEventListener('click', closeDetail);
  document.addEventListener('keydown', event => {
    if ($('#cwDetail').hidden || event.defaultPrevented) return;
    if (event.key === 'Escape') { closeDetail(); return; }
    if (event.key !== 'Tab') return;
    const panel = $('#cwDetailPanel');
    // Collapsed evidence sections and hidden controls must not become trap endpoints.
    const focusable = [...panel.querySelectorAll('button,input,select,textarea,a[href],summary,[tabindex],[contenteditable="true"]')].filter(control => {
      // Chromium may report rectangles for content inside closed details.
      for (let parent = control.parentElement; parent && parent !== panel; parent = parent.parentElement) {
        if (parent.tagName === 'DETAILS' && !parent.open) {
          const summary = [...parent.children].find(child => child.tagName === 'SUMMARY');
          if (!summary?.contains(control)) return false;
        }
      }
      const style = getComputedStyle(control);
      return control.tabIndex >= 0
        && !control.matches(':disabled')
        && !control.closest('[inert]')
        && control.getClientRects().length > 0
        && style.visibility !== 'hidden'
        && style.visibility !== 'collapse';
    });
    if (!focusable.length) { event.preventDefault(); panel.focus(); return; }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (!focusable.includes(document.activeElement)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    } else if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first.focus();
    }
  });

  window.addEventListener('hashchange', syncClaimFromLocation);
  void loadQueue();
  syncClaimFromLocation();
})();
