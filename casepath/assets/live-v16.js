(() => {
  'use strict';

  if (document.documentElement.dataset.claimsWorkspace === 'true') return;

  if (new URLSearchParams(location.search).get('foundation') === 'live-v1') return;

  const params = new URLSearchParams(location.search);
  const API = location.origin.replace(/\/$/, '');
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  // Provider work may finish quickly, but each user-facing chapter must remain readable.
  // These timings pace only the presentation of returned events; they never delay or
  // change the run, its provider calls, or its persisted result.
  const WORKING_FRAME_MS = 2300;
  const ARTIFACT_FRAME_MS = 5500;
  const CONCISE_WORKING_FRAME_MS = 500;
  const CONCISE_ARTIFACT_FRAME_MS = 800;
  // Source opening is part of the story, so it keeps the full readable hold.
  // These graph-native summaries can remain concise without hiding causal work.
  const CONCISE_GRAPH_STAGES = new Set(['evidence', 'experience', 'verify']);
  const RESEARCH_ARTIFACT_FRAME_MS = 9000;
  // This is an inactivity limit, not a reading-speed limit. Each accepted
  // decision-flow step rearms it while the cinematic trace is progressing.
  const PROCESS_STORY_TIMEOUT_MS = 120000;
  const OFFICIAL_LAW_TOUR_TIMEOUT_MS = 120000;
  // A real six-specialist run can return the accepted fact batch after the
  // downstream calls have finished. Wait for that exact run-bound batch rather
  // than silently advancing to a theatrical deterministic substitute.
  const FACT_SOURCE_TOUR_TIMEOUT_MS = 180000;
  const AGENT_RECEIPT_BEAT_MS = reduceMotion ? 20 : 800;
  const BACKGROUND_BEAT_MS = reduceMotion ? 20 : 120;
  const KNOWLEDGE_BEAT_MS = 1200;
  const LATER_CAUSAL_STEP_CONTRACT = 'casepath.later-causal-step/1.0.0';
  const LATER_CAUSAL_SOURCE_HOLD_MS = reduceMotion ? 2400 : 5200;
  const LATER_CAUSAL_MEMORY_HOLD_MS = reduceMotion ? 1800 : 3000;
  const LATER_CAUSAL_ELIGIBILITY_HOLD_MS = reduceMotion ? 1800 : 2800;
  const LATER_CAUSAL_STEP_TIMEOUT_MS = 10000;
  const SESSION_STORAGE_KEY = 'casepath:demo-session';
  const SESSION_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/;
  const NEMOTRON_AGENT_IDS = new Set([
    'canonical_facts',
    'orchestrator_plan',
    'document_source_integrity',
    'process_decision_mapping',
    'evidence_checklist',
    'final_claim_brief_audit',
  ]);
  const FAILURE_AGENT_LABELS = Object.freeze({
    canonical_facts: 'Claim reader',
    orchestrator_plan: 'Work planner',
    document_source_integrity: 'Source checker',
    process_decision_mapping: 'Process builder',
    evidence_checklist: 'Document finder',
    final_claim_brief_audit: 'Result checker',
  });
  const SAFE_MODEL_FAILURE_MESSAGE = 'The model provider did not return an accepted result. No fact, process, or document state was changed.';

  function createSessionId() {
    const token = crypto.randomUUID?.() || [...crypto.getRandomValues(new Uint8Array(16))].map(value => value.toString(16).padStart(2, '0')).join('');
    return `ui-${token}`;
  }

  function demoSessionId() {
    try {
      const stored = sessionStorage.getItem(SESSION_STORAGE_KEY);
      if (stored && SESSION_ID_PATTERN.test(stored)) return stored;
      const created = createSessionId();
      sessionStorage.setItem(SESSION_STORAGE_KEY, created);
      return created;
    } catch (_) {
      return createSessionId();
    }
  }

  const SESSION_ID = demoSessionId();

  const STAGES = [
    { id: 'read', label: 'Read evidence', short: 'Read', job: 'Reading the message and every original attachment.' },
    { id: 'understand', label: 'Understand claim', short: 'Understand', job: 'Separating supported facts, allegations, conflicts, and unknowns.' },
    { id: 'research', label: 'Research law', short: 'Law', job: 'Finding the Swiss-law questions that shape the handling process.' },
    { id: 'process', label: 'Build process', short: 'Process', job: 'Working out every decision needed from intake to resolution.' },
    { id: 'evidence', label: 'Map evidence', short: 'Evidence', job: 'Connecting each process decision to the facts and evidence it needs.' },
    { id: 'experience', label: 'Find experience', short: 'Experience', job: 'Looking for provenance-labelled reference precedents at difficult branches.' },
    { id: 'verify', label: 'Verify plan', short: 'Verify', job: 'Checking graph integrity, grounding, and document traceability.' },
  ];

  const state = {
    demo: null,
    claim: null,
    flagshipClaim: null,
    laterClaim: null,
    runId: null,
    run: null,
    flagshipRun: null,
    baselineLaterRun: null,
    laterRun: null,
    review: null,
    reviewBefore: null,
    proof: null,
    selectedNodeId: 'causation',
    branchesExpanded: false,
    activeStage: null,
    stageMode: null,
    eventQueue: [],
    queuedEventIds: new Set(),
    presentedEvents: [],
    presenting: false,
    polling: false,
    starting: false,
    runComplete: false,
    streamConnections: 0,
    terminalHydrations: 0,
    journey: 'start',
    viewer: { artifact: null, extraction: null, page: 1, zoom: 1, tab: 'original', context: null, searchMatches: [] },
  };

  // Reuse the page-load request if the viewer starts immediately. A cold API
  // must never create a second competing demo request or keep the UI on the
  // disabled start button while the service wakes.
  let demoRequest = null;
  let startupNoticeTimer = 0;

  function requestDemo() {
    if (!demoRequest) {
      const earlyRequest = window.__CASEPATH_DEMO_REQUEST;
      demoRequest = Promise.resolve(earlyRequest)
        .then(demo => demo || api('/api/demo'))
        .catch(error => {
          demoRequest = null;
          throw error;
        });
    }
    return demoRequest;
  }

  function beginStartupNotice() {
    clearTimeout(startupNoticeTimer);
    startupNoticeTimer = setTimeout(() => {
      if (document.body.dataset.casepathStartup !== 'waking') return;
      setOrchestrator('First visit: waking the secure analysis service · sources remain available');
    }, 2400);
  }

  function endStartupNotice() {
    clearTimeout(startupNoticeTimer);
    startupNoticeTimer = 0;
  }

  // One browser-owned run store is the shared source of truth for every
  // presentation layer.  Legacy enhancers may read it, but only this module
  // writes it from the authenticated run stream or the terminal hydration.
  const runStoreValues = new Map();
  const runStoreSubscribers = new Set();
  const runStore = Object.freeze({
    get(runId = document.body.dataset.casepathActiveRunId || '') {
      return runStoreValues.get(runId)
        || (state.run?.run_id === runId ? state.run : null)
        || (state.flagshipRun?.run_id === runId ? state.flagshipRun : null)
        || (state.baselineLaterRun?.run_id === runId ? state.baselineLaterRun : null)
        || (state.laterRun?.run_id === runId ? state.laterRun : null)
        || null;
    },
    subscribe(callback) {
      if (typeof callback !== 'function') return () => {};
      runStoreSubscribers.add(callback);
      return () => runStoreSubscribers.delete(callback);
    },
  });
  window.CasePathRunStore = runStore;

  function publishRunSnapshot(run, { later = false, terminal = false } = {}) {
    if (!run?.run_id) return;
    runStoreValues.set(run.run_id, run);
    document.body.dataset.runStoreReady = 'true';
    document.body.dataset.runStoreActiveId = run.run_id;
    document.body.dataset.runStoreStatus = run.status || '';
    document.body.dataset.runStoreEventCount = String(run.events?.length || 0);
    for (const subscriber of runStoreSubscribers) {
      try { subscriber(run, { later, terminal }); } catch (_) {}
    }
    window.dispatchEvent(new CustomEvent('casepath:run-snapshot', {
      detail: { run, runId: run.run_id, later, terminal },
    }));
  }

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const esc = (value = '') => String(value).replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[character]));
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  let processStoryWaitRunId = '';
  let processStoryWaitPromise = null;
  let processStoryAwaitedRunId = '';

  function renderCanvas(markup, moment = '') {
    const canvas = $('#stageCanvas');
    if (!canvas) return;
    canvas.innerHTML = markup;
    canvas.dataset.casepathMoment = moment;
    canvas.setAttribute('aria-busy', 'false');
    window.dispatchEvent(new CustomEvent('casepath:render', { detail: { moment } }));
  }

  function announceRender(moment = '') {
    const canvas = $('#stageCanvas');
    if (canvas && moment) canvas.dataset.casepathMoment = moment;
    window.dispatchEvent(new CustomEvent('casepath:render', { detail: { moment } }));
  }

  const EXPLICIT_ACTOR_TYPES = new Set(['nemotron_agent', 'deterministic_tool', 'deterministic_gate']);
  const SUCCESS_EVENT_STATES = new Set(['accepted', 'cache_hit', 'completed', 'passed', 'succeeded', 'succeeded_with_guarded_fallback', 'success']);
  const PRESENTABLE_STAGE_STATES = new Set([...SUCCESS_EVENT_STATES, 'candidate_prepared']);
  const PROCESS_CONTRIBUTION_ROLE = 'Process Decision Mapping Agent';
  const EVIDENCE_CONTRIBUTION_ROLE = 'Evidence and Checklist Agent';
  const FINAL_CONTRIBUTION_ROLE = 'Final Claim Brief Agent';
  const DETERMINISTIC_CONTRIBUTION_ROLE = 'deterministic_application';
  const FINAL_FIELD_CONTRACT = [
    ['current_node_id', 'final:current_node'],
    ['next_action_node_id', 'final:next_action'],
    ['supporting_fact_ids', 'final:supporting_facts'],
    ['upstream_contribution_ids', 'final:upstream_contributions'],
    ['audit_check_ids', 'final:audit_checks'],
  ];
  const FINAL_UPSTREAM_CONTRIBUTION_IDS = ['document_source_integrity', 'evidence_checklist', 'process_decision_mapping'];
  const FINAL_AUDIT_CHECK_IDS = [
    'current_node_supported_by_canonical_facts',
    'evidence_items_bound_to_process_nodes',
    'next_action_connected_in_static_topology',
    'upstream_contribution_lineage_complete',
  ];

  function returnedValue(event, ...keys) {
    for (const key of keys) {
      const value = event?.[key];
      if (value !== undefined && value !== null && String(value).trim()) return String(value);
    }
    return '';
  }

  function eventKind(event) {
    const actorType = returnedValue(event, 'actor_type');
    if (EXPLICIT_ACTOR_TYPES.has(actorType)) return actorType;
    const eventType = returnedValue(event, 'event_type', 'type');
    const implementation = returnedValue(event, 'implementation');
    if (/gate/i.test(eventType) || /gate/i.test(implementation)) return 'legacy_deterministic_gate';
    if (returnedValue(event, 'model', 'requested_model', 'response_model')) return 'legacy_model_event';
    if (/deterministic|reference/i.test(implementation)) return 'legacy_deterministic_event';
    return 'legacy_event';
  }

  function eventIsGate(event) {
    return ['deterministic_gate', 'legacy_deterministic_gate'].includes(eventKind(event));
  }

  function eventState(event) {
    return returnedValue(event, 'outcome', 'status');
  }

  function eventSucceeded(event) {
    return SUCCESS_EVENT_STATES.has(eventState(event).toLowerCase());
  }

  function eventIsCachedReplay(event) {
    return event?.cache_hit === true
      || returnedValue(event, 'cache_hit').toLowerCase() === 'true'
      || eventState(event).toLowerCase() === 'cache_hit'
      || (returnedValue(event, 'call_count') === '0'
        && returnedValue(event, 'usage_source').toLowerCase() === 'cache');
  }

  function eventArtifacts(event) {
    const returned = [];
    if (Array.isArray(event?.output_artifacts)) returned.push(...event.output_artifacts);
    const single = event?.output_artifact ?? event?.output_artifact_id;
    if (single !== undefined && single !== null && String(single).trim()) returned.push(single);
    return [...new Set(returned.map(value => String(value)))];
  }

  function returnedActorName(event, { preferLabel = false } = {}) {
    const actor = returnedValue(event, 'actor_name', 'agent_name', 'agent', 'actor_id', 'agent_id');
    const label = returnedValue(event, 'label');
    return preferLabel ? label || actor : actor || label;
  }

  function eventReceiptKey(event) {
    return returnedValue(event, 'event_id') || (event?.ordinal !== undefined ? `ordinal:${event.ordinal}` : [event?.stage, event?.status, event?.label, event?.output_artifact].map(value => String(value || '')).join(':'));
  }

  function rememberPresentedEvent(event) {
    const key = eventReceiptKey(event);
    if (!state.presentedEvents.some(item => eventReceiptKey(item) === key)) state.presentedEvents.push(event);
  }

  function actorKindLabel(kind) {
    return ({
      nemotron_agent: 'Nemotron agent',
      deterministic_tool: 'Deterministic tool',
      deterministic_gate: 'Deterministic gate',
      legacy_model_event: 'Model-assisted legacy event',
      legacy_deterministic_gate: 'Legacy deterministic gate',
      legacy_deterministic_event: 'Deterministic reference event',
      legacy_event: 'Legacy event contract',
    })[kind] || 'Returned event';
  }

  function proofMeta(label, value, key = '') {
    if (!value) return '';
    return `<span${key ? ` data-proof-field="${esc(key)}"` : ''}><small>${esc(label)}</small><code>${esc(value)}</code></span>`;
  }

  function actorInitials(value) {
    const words = String(value || '').trim().split(/\s+/).filter(Boolean);
    return words.slice(0, 2).map(word => word[0]).join('').toUpperCase() || 'N';
  }

  function returnedFramework(event) {
    const framework = event?.orchestration_framework ?? event?.framework;
    if (typeof framework === 'string') return framework;
    if (!framework || typeof framework !== 'object' || Array.isArray(framework)) return '';
    const labels = { langchain: 'LangChain', langgraph: 'LangGraph', langchain_openrouter: 'LangChain OpenRouter' };
    return Object.entries(labels).flatMap(([key, label]) => {
      const value = framework[key];
      return typeof value === 'string' && value.trim() ? [`${label} ${value}`] : [];
    }).join(' · ');
  }

  function safeEventMetrics(event) {
    const allowed = {
      accepted_count: 'Accepted',
      rejected_count: 'Rejected',
      accepted_fact_count: 'Facts accepted',
      rejected_fact_count: 'Facts rejected',
      source_reference_projection_count: 'Source bindings projected',
      facts: 'Facts',
      unknowns: 'Unknowns',
      conflicts: 'Conflicts',
      nodes: 'Process nodes',
      edges: 'Connections',
      items: 'Evidence links',
      files: 'Files',
      pages: 'Pages',
      images: 'Images',
      precedents: 'Precedents',
      checks: 'Checks',
      checks_passed: 'Checks passed',
      canonical_artifacts: 'Canonical artifacts',
    };
    const metrics = event?.metrics && typeof event.metrics === 'object' && !Array.isArray(event.metrics) ? event.metrics : {};
    return Object.entries(allowed).flatMap(([key, label]) => {
      const raw = event?.[key] ?? metrics[key];
      const value = Number(raw);
      return Number.isFinite(value) && value >= 0 ? [{ key, label, value }] : [];
    });
  }

  function renderSafeEventMetrics(event) {
    const metrics = safeEventMetrics(event);
    if (!metrics.length) return '';
    return `<div class="orchestration-result-metrics" aria-label="Returned bounded result counts">${metrics.map(metric => `<span data-result-metric="${esc(metric.key)}"><strong>${esc(metric.value)}</strong><small>${esc(metric.label)}</small></span>`).join('')}</div>`;
  }

  function renderActorCard(event) {
    if (!event) return '';
    const kind = eventKind(event);
    const isNemotron = kind === 'nemotron_agent';
    const isModelLegacy = kind === 'legacy_model_event';
    const deterministic = ['deterministic_tool', 'legacy_deterministic_event', 'legacy_event'].includes(kind);
    const actorName = returnedActorName(event, { preferLabel: deterministic });
    const detail = returnedValue(event, 'result_summary', 'safe_summary', 'headline', 'detail', 'question');
    const status = eventState(event);
    const model = returnedValue(event, 'requested_model', 'model');
    const responseModel = returnedValue(event, 'response_model');
    const callId = returnedValue(event, 'call_id');
    const delegationId = returnedValue(event, 'delegation_id');
    const artifacts = eventArtifacts(event).join(', ');
    const artifactLabel = returnedValue(event, 'output_artifact_label', 'artifact_label');
    const outputHash = returnedValue(event, 'output_artifact_hash', 'output_hash', 'artifact_hash');
    const inputArtifacts = Array.isArray(event?.input_artifacts) ? event.input_artifacts.map(value => String(value)).join(', ') : returnedValue(event, 'input_artifact', 'input_artifact_id');
    const inputHash = returnedValue(event, 'input_artifact_hash', 'input_hash');
    const cacheHit = event?.cache_hit === true || returnedValue(event, 'cache_hit').toLowerCase() === 'true';
    const originCallId = returnedValue(event, 'cache_origin_call_id', 'origin_call_id');
    const actorId = returnedValue(event, 'actor_id', 'agent_id', 'agent');
    const isCanonicalRoot = actorId === 'canonical_facts';
    const missingResponseIdentity = eventSucceeded(event) && !responseModel && !(cacheHit && originCallId);
    const missingCallProof = isNemotron && (
      !model ||
      (eventSucceeded(event) && (
        !callId ||
        (!isCanonicalRoot && !delegationId) ||
        !artifacts ||
        !outputHash ||
        missingResponseIdentity
      ))
    );
    const meta = [
      isNemotron ? proofMeta('Orchestration', returnedFramework(event), 'orchestration-framework') : '',
      (isNemotron || isModelLegacy) ? proofMeta('Requested model', model, 'model') : '',
      (isNemotron || isModelLegacy) ? proofMeta('Response model', responseModel, 'response-model') : '',
      (isNemotron || isModelLegacy) ? proofMeta('Call', callId, 'call-id') : '',
      isNemotron ? proofMeta('Delegation', delegationId, 'delegation-id') : '',
      proofMeta('Output artifact', artifactLabel ? `${artifactLabel} · ${artifacts}` : artifacts, 'artifact-id'),
      proofMeta('Output hash', outputHash, 'artifact-hash'),
      proofMeta('Input artifact', inputArtifacts, 'input-artifact-id'),
      proofMeta('Input hash', inputHash, 'input-hash'),
      cacheHit ? proofMeta('Cache origin call', originCallId, 'cache-origin-call-id') : '',
      deterministic ? proofMeta('Implementation', returnedValue(event, 'implementation'), 'implementation') : '',
    ].filter(Boolean).join('');
    return `<article class="orchestration-actor-card ${isNemotron ? 'is-nemotron' : 'is-non-agent'}" data-actor-type="${esc(kind)}" data-actor-id="${esc(actorId)}" data-call-id="${esc(callId)}" data-delegation-id="${esc(delegationId)}" data-output-artifact="${esc(artifacts)}" data-event-status="${esc(status)}">
      ${isNemotron ? `<span class="orchestration-agent-avatar" aria-hidden="true">${esc(actorInitials(actorName))}</span>` : ''}
      <div class="orchestration-actor-copy"><small>${esc(actorKindLabel(kind))}${status ? ` · ${esc(status)}` : ''}</small><strong>${esc(actorName || 'Actor identity not returned')}</strong>${detail ? `<p>${esc(detail)}</p>` : ''}${renderSafeEventMetrics(event)}${missingCallProof ? '<p class="orchestration-proof-warning">Call-bound model, call, delegation, artifact, or accepted-output hash identity was not fully returned.</p>' : ''}</div>
      ${meta ? `<div class="orchestration-actor-meta">${meta}</div>` : ''}
    </article>`;
  }

  function renderHandoffReceipt(event) {
    if (!event) return '';
    const handoffTo = returnedValue(event, 'handoff_to');
    if (!handoffTo) return '';
    const handoffFrom = returnedValue(event, 'handoff_from') || returnedActorName(event);
    const artifacts = eventArtifacts(event).join(', ');
    const outputHash = returnedValue(event, 'output_artifact_hash', 'output_hash', 'artifact_hash');
    return `<article class="orchestration-receipt handoff-receipt" data-receipt-type="handoff" data-handoff-from="${esc(handoffFrom)}" data-handoff-to="${esc(handoffTo)}" data-artifact-id="${esc(artifacts)}" data-artifact-hash="${esc(outputHash)}">
      <span class="receipt-mark" aria-hidden="true">→</span><div><small>Returned handoff${eventState(event) ? ` · ${esc(eventState(event))}` : ''}</small><strong>${esc(handoffFrom || 'Source actor not returned')} → ${esc(handoffTo)}</strong>${artifacts ? `<code>${esc(artifacts)}</code>` : ''}${outputHash ? `<code>${esc(outputHash)}</code>` : ''}</div>
    </article>`;
  }

  function renderGateReceipt(event) {
    if (!event) return '';
    const gateId = returnedValue(event, 'gate_id', 'agent_id');
    const validator = returnedValue(event, 'validator');
    const gateName = gateId || validator || returnedValue(event, 'label');
    const artifact = eventArtifacts(event).join(', ');
    const outcome = eventState(event);
    const gateMark = eventSucceeded(event) ? '✓' : /fail|reject/i.test(outcome) ? '×' : '◇';
    const gateIdentity = gateId ? ` data-gate-id="${esc(gateId)}"` : '';
    const receiptLabel = gateId ? 'Deterministic gate receipt' : validator ? 'Deterministic validator receipt' : 'Deterministic receipt';
    return `<article class="orchestration-receipt gate-receipt" data-receipt-type="gate" data-actor-type="${esc(eventKind(event))}"${gateIdentity} data-gate-outcome="${esc(outcome)}" data-artifact-id="${esc(artifact)}">
      <span class="receipt-mark" aria-hidden="true">${gateMark}</span><div><small>${receiptLabel}${outcome ? ` · ${esc(outcome)}` : ''}</small><strong>${esc(gateName || 'Deterministic identity not returned')}</strong>${artifact ? `<code>${esc(artifact)}</code>` : ''}</div>
    </article>`;
  }

  function returnedAgentAudit() {
    const run = currentRun();
    return run?.agent_orchestration || run?.result?.agent_orchestration || run?.result?.audit?.agent_orchestration || null;
  }

  function returnedTeamSummary(events) {
    const roles = new Map();
    const gates = new Map();
    for (const event of events) {
      const actorId = returnedValue(event, 'agent_id', 'actor_id');
      if (!actorId) continue;
      if (eventKind(event) === 'nemotron_agent') {
        const role = returnedActorName(event) || actorId;
        if (!roles.has(actorId) || eventSucceeded(event)) roles.set(actorId, role);
      }
      if (eventKind(event) === 'deterministic_gate') {
        const role = returnedActorName(event) || actorId;
        if (!gates.has(actorId) || eventSucceeded(event)) gates.set(actorId, role);
      }
    }
    const parallelIds = ['document_source_integrity', 'process_decision_mapping'];
    const topologyGroups = returnedAgentAudit()?.execution_topology?.parallel_groups;
    const parallelReturned = parallelIds.every(id => roles.has(id))
      && gates.has('deterministic_process_gate')
      && Array.isArray(topologyGroups)
      && topologyGroups.some(group => Array.isArray(group) && group.length === parallelIds.length && parallelIds.every(id => group.includes(id)));
    return { roles, gates, parallelIds, parallelReturned };
  }

  function renderReturnedTeamSummary(events) {
    const { roles, gates, parallelIds, parallelReturned } = returnedTeamSummary(events);
    if (!roles.size && !gates.size) return '';
    const roleIds = [...roles.keys()];
    const gateIds = [...gates.keys()];
    const parallel = parallelReturned ? `<div class="orchestration-parallel-branch" data-parallel-role-ids="${esc(parallelIds.join(','))}" data-parallel-gate-id="deterministic_process_gate"><span>${esc(roles.get(parallelIds[0]))}</span><i>fan-out</i><span>${esc(roles.get(parallelIds[1]))}</span><b aria-hidden="true">→</b><strong>${esc(gates.get('deterministic_process_gate'))}</strong></div>` : '';
    return `<section class="orchestration-run-summary" aria-label="Returned orchestration team" data-nemotron-role-count="${roles.size}" data-deterministic-gate-count="${gates.size}" data-nemotron-role-ids="${esc(roleIds.join(','))}" data-deterministic-gate-ids="${esc(gateIds.join(','))}"><div><small>Returned orchestration</small><strong>${roles.size} unique Nemotron role${roles.size === 1 ? '' : 's'} · ${gates.size} unique deterministic gate${gates.size === 1 ? '' : 's'}</strong></div>${parallel}</section>`;
  }

  function renderTeamTrace(events, open = false) {
    const team = returnedTeamSummary(events);
    const modelCalls = [...new Set(events.map(event => returnedValue(event, 'call_id')).filter(Boolean))];
    const rows = events.map(event => {
      const kind = eventKind(event);
      const name = returnedActorName(event, { preferLabel: kind !== 'nemotron_agent' && kind !== 'legacy_model_event' });
      const artifact = eventArtifacts(event).join(', ');
      const callId = returnedValue(event, 'call_id');
      const delegationId = returnedValue(event, 'delegation_id');
      const outputHash = returnedValue(event, 'output_artifact_hash', 'output_hash', 'artifact_hash');
      const identities = [artifact ? `artifact ${artifact}` : '', outputHash ? `hash ${outputHash}` : '', callId ? `call ${callId}` : '', delegationId ? `delegation ${delegationId}` : ''].filter(Boolean);
      return `<li data-event-id="${esc(returnedValue(event, 'event_id'))}" data-actor-type="${esc(kind)}" data-call-id="${esc(callId)}" data-delegation-id="${esc(delegationId)}"><span>${esc(actorKindLabel(kind))}</span><strong>${esc(name || 'Identity not returned')}</strong>${eventState(event) ? `<em>${esc(eventState(event))}</em>` : ''}${identities.length ? `<code>${identities.map(value => esc(value)).join('<br>')}</code>` : ''}</li>`;
    }).join('');
    return `<details class="orchestration-team-trace" id="teamTrace" ${open ? 'open' : ''}><summary><span>Team Trace</span><strong>${team.roles.size} Nemotron role${team.roles.size === 1 ? '' : 's'} · ${team.gates.size} deterministic gate${team.gates.size === 1 ? '' : 's'}${modelCalls.length ? ` · ${modelCalls.length} call${modelCalls.length === 1 ? '' : 's'}` : ''}</strong><i aria-hidden="true">⌄</i></summary><ol>${rows}</ol></details>`;
  }

  function renderOrchestrationProof() {
    const proof = $('#orchestrationProof');
    if (!proof || !state.presentedEvents.length) return;
    const events = state.presentedEvents;
    const traceOpen = $('#teamTrace')?.open || false;
    const reversed = [...events].reverse();
    const actorEvent = reversed.find(event => !eventIsGate(event) && event.stage !== 'complete') || null;
    const handoffEvent = reversed.find(event => returnedValue(event, 'handoff_to') && eventSucceeded(event));
    const gateEvent = reversed.find(eventIsGate);
    const graphAccepted = events.some(event => eventArtifacts(event).includes('process_graph') && eventSucceeded(event));
    const runReady = events.some(event => event.stage === 'complete' && eventSucceeded(event));
    const nemotronPlanEvent = reversed.find(event => returnedValue(event, 'agent_id') === 'orchestrator_plan' && eventKind(event) === 'nemotron_agent');
    const topologySetupEvent = reversed.find(event => event.stage === 'orchestrator' || returnedValue(event, 'actor_role') === 'orchestrator');
    const expectsNemotronPlan = currentRun()?.model_mode === 'openrouter_nemotron';
    const label = $('#orchestratorLabel');
    if (label) {
      label.textContent = nemotronPlanEvent
        ? 'Nemotron focus plan · deterministic LangGraph topology'
        : topologySetupEvent
          ? expectsNemotronPlan
            ? 'Deterministic LangGraph setup · awaiting returned focus plan'
            : 'Deterministic reference pipeline'
          : 'Orchestration status';
    }
    proof.hidden = false;
    proof.classList.toggle('is-artifact-dominant', graphAccepted);
    proof.classList.toggle('is-run-ready', runReady);
    proof.dataset.proofActorType = actorEvent ? eventKind(actorEvent) : '';
    const currentEvent = events.at(-1) || null;
    proof.dataset.currentEventId = returnedValue(currentEvent, 'event_id');
    proof.dataset.currentStage = currentEvent?.stage || '';
    proof.dataset.currentActorType = currentEvent ? eventKind(currentEvent) : '';
    proof.dataset.currentActorId = returnedValue(currentEvent, 'actor_id', 'agent_id', 'agent', 'gate_id');
    proof.dataset.currentCallId = returnedValue(currentEvent, 'call_id');
    proof.dataset.currentStatus = eventState(currentEvent);
    proof.dataset.currentOutputArtifact = eventArtifacts(currentEvent).join(', ');
    proof.dataset.currentHeadline = returnedValue(currentEvent, 'headline', 'result_summary', 'safe_summary', 'detail');
    proof.innerHTML = `<h2 class="visually-hidden" id="orchestrationProofTitle">Returned agent activity and deterministic proof</h2>${renderActorCard(actorEvent)}<div class="orchestration-receipts">${renderHandoffReceipt(handoffEvent)}${renderGateReceipt(gateEvent)}</div>${runReady ? renderReturnedTeamSummary(events) : ''}${renderTeamTrace(events, traceOpen)}<p class="orchestration-boundary">Generated fictional claim · no coverage or legal decision · legal interpretations remain unapproved · simulated review is not expert approval · candidate knowledge remains quarantined pending qualified support, tests, and approval.</p>`;
    document.body.dataset.orchestrationProof = 'true';
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', 'X-CasePath-Session': SESSION_ID, ...(options.headers || {}) },
    });
    if (!response.ok) {
      let detail = `${response.status}`;
      try { detail = (await response.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    const type = response.headers.get('content-type') || '';
    return type.includes('application/json') ? response.json() : response;
  }

  function toast(message) {
    const node = $('#toast');
    node.textContent = message;
    node.classList.add('show');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => node.classList.remove('show'), 2300);
  }

  function formatDate(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date);
  }

  function mimeLabel(artifact) {
    if (artifact.media_type === 'application/pdf') return `PDF · ${artifact.page_count || 1} page${artifact.page_count === 1 ? '' : 's'}`;
    if (artifact.media_type === 'message/rfc822') return 'Email correspondence';
    if (artifact.media_type?.startsWith('image/')) return 'Photograph';
    return artifact.document_type || artifact.kind || 'Attachment';
  }

  function formatConfidence(value) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? `${Math.round(numeric * 100)}%` : 'not returned';
  }

  function sourcePage(ref) {
    const numeric = Number(ref?.page);
    return Number.isInteger(numeric) && numeric > 0 ? numeric : null;
  }

  function normalizedRegion(ref) {
    const region = ref?.region;
    if (!Array.isArray(region) || region.length !== 4) return null;
    const values = region.map(Number);
    if (!values.every(value => Number.isFinite(value) && value >= 0 && value <= 1)) return null;
    const [x, y, width, height] = values;
    return width > 0 && height > 0 && x + width <= 1 && y + height <= 1 ? values : null;
  }

  function sourceLocatorId(ref) {
    const artifactId = String(ref?.artifact_id || 'unknown-source');
    const kind = String(ref?.locator_kind || 'unknown-locator');
    if (kind === 'visual_observation') return `source:${artifactId}:region:${(ref?.region || []).join(',')}`;
    if (kind === 'metadata_field') return `source:${artifactId}:field:${String(ref?.field || '')}`;
    return `source:${artifactId}:page:${String(ref?.page || '')}:quote:${String(ref?.excerpt || '')}`;
  }

  function validVisualAnnotation(ref) {
    return ref?.locator_kind === 'visual_observation'
      && ref?.producer === 'deterministic_reference_annotation'
      && ref?.authority === 'generated_demo_reference_only'
      && ref?.annotation_contract === 'casepath.visual-reference-annotation/1.0.0'
      && typeof ref?.annotation_version === 'string'
      && ref.annotation_version.startsWith('generated-demo-reference/')
      && /^[0-9a-f]{64}$/.test(ref?.image_sha256 || '')
      && Boolean(normalizedRegion(ref))
      && typeof ref?.observation === 'string'
      && Boolean(ref.observation.trim());
  }

  function visualAnnotationAttributes(ref) {
    return `data-source-producer="${esc(ref?.producer || '')}" data-source-authority="${esc(ref?.authority || '')}" data-annotation-contract="${esc(ref?.annotation_contract || '')}" data-annotation-version="${esc(ref?.annotation_version || '')}" data-image-sha256="${esc(ref?.image_sha256 || '')}"`;
  }

  function sourceLocatorMarkup(ref, className = 'source-locator') {
    const kind = ref?.locator_kind || '';
    const agent = esc(ref?.agent || 'Agent not returned');
    if (kind === 'text_quote') {
      const page = sourcePage(ref);
      const excerpt = String(ref?.excerpt || '').trim();
      const exactQuote = page !== null && excerpt.length > 0;
      const title = page === null ? 'Text quote · page not returned' : `Text quote · page ${page}`;
      return `<span class="${className} text-quote" data-locator-kind="text_quote" data-source-page="${page ?? ''}" data-source-excerpt="${esc(ref.excerpt || '')}" data-source-agent="${esc(ref.agent || '')}"><span>${esc(title)} · ${agent}</span>${exactQuote ? `<q>${esc(ref.excerpt)}</q>` : '<span class="locator-detail">A complete page-and-passage locator was not returned; no exact quotation is claimed.</span>'}</span>`;
    }
    if (kind === 'visual_observation') {
      const region = normalizedRegion(ref);
      const regionLabel = region ? region.map(value => Number(value).toFixed(2)).join(', ') : 'region not returned';
      const verified = validVisualAnnotation(ref);
      return `<span class="${className} visual-observation" data-locator-kind="visual_observation" data-source-region="${esc(region ? JSON.stringify(region) : '')}" data-source-observation="${esc(ref.observation || '')}" ${visualAnnotationAttributes(ref)}><span>${verified ? 'Curated generated-demo reference annotation' : 'Visual annotation provenance incomplete'} · region [${esc(regionLabel)}]</span><span class="locator-detail">${esc(ref.observation || 'Observation not returned.')} <em>${verified ? 'Hash-bound to these demo image bytes; not machine extraction, model output, or qualified review.' : 'No machine extraction or qualified observation is claimed.'}</em></span></span>`;
    }
    if (kind === 'metadata_field') {
      return `<span class="${className} metadata-field" data-locator-kind="metadata_field" data-source-field="${esc(ref.field || '')}" data-source-value="${esc(ref.value ?? '')}" data-source-agent="${esc(ref.agent || '')}"><span>Metadata field · ${agent}</span><span class="locator-detail"><strong>${esc(ref.field || 'Field not returned')}:</strong> <code>${esc(ref.value ?? 'Value not returned')}</code></span></span>`;
    }
    return `<span class="${className} unknown-locator" data-locator-kind="${esc(kind)}" data-source-agent="${esc(ref?.agent || '')}"><span>Locator type not returned · ${agent}</span><span class="locator-detail">No exact quote or visual region is claimed.</span></span>`;
  }

  function sourceTitle(artifactId) {
    if (artifactId === 'message') return 'Customer message';
    if (artifactId === 'intake') return 'Intake metadata';
    return findArtifact(artifactId)?.title || artifactId || 'Unknown source';
  }

  function sourceRefButton(fact, ref, nodeId = '') {
    const region = normalizedRegion(ref);
    return `<button class="grounding-ref source-link" type="button" data-source-ref="${esc(ref.artifact_id)}" data-source-locator-kind="${esc(ref.locator_kind || '')}" data-source-page="${sourcePage(ref) ?? ''}" data-source-excerpt="${esc(ref.excerpt || '')}" data-source-region="${esc(region ? JSON.stringify(region) : '')}" data-source-observation="${esc(ref.observation || '')}" data-source-field="${esc(ref.field || '')}" data-source-value="${esc(ref.value ?? '')}" data-source-agent="${esc(ref.agent || '')}" ${visualAnnotationAttributes(ref)} data-fact-id="${esc(fact.fact_id || '')}" data-node-id="${esc(nodeId)}" data-fact-confidence="${esc(fact.confidence ?? '')}" data-fact-state="${esc(fact.state || '')}"><strong class="grounding-source-title">${esc(sourceTitle(ref.artifact_id))}</strong>${sourceLocatorMarkup(ref, 'grounding-locator')}<small>confidence ${formatConfidence(fact.confidence)} · ${esc(fact.state || 'state not returned')}</small></button>`;
  }

  function artifactUrl(artifactId) {
    return `${API}/api/artifacts/${encodeURIComponent(artifactId)}`;
  }

  function pageUrl(artifactId, page) {
    return `${API}/api/artifacts/${encodeURIComponent(artifactId)}/pages/${page}`;
  }

  async function boot() {
    // Bind the static claim shell before the API request. Render's API may be
    // waking up, but the already-rendered desktop workspace must remain
    // immediately interactive instead of feeling like a blank/loading page.
    bindGlobalInteractions();
    $('#runCasePath').disabled = false;
    try {
      const demo = await requestDemo();
      if (state.starting || state.journey !== 'start') return;
      state.demo = demo;
      state.flagshipClaim = state.demo.claim;
      state.claim = state.flagshipClaim;
      renderClaim(state.claim);
      renderProgress();
      window.dispatchEvent(new CustomEvent('casepath:demo-ready', { detail: {
        claim: state.flagshipClaim,
        laterClaimId: state.demo?.later_claim_id || '',
        demoClaimId: state.demo?.demo_claim_id || '',
      } }));
    } catch (error) {
      if (state.starting || state.journey !== 'start') return;
      $('#startState').innerHTML = `<div class="start-copy"><span class="quiet-label">CasePath could not open</span><h2>The claim workspace is unavailable.</h2><p>${esc(error.message)}</p></div><button class="primary-button" id="retryBoot" type="button">Try again</button>`;
      $('#retryBoot')?.addEventListener('click', () => location.reload(), { once: true });
    }
  }

  function renderClaim(claim) {
    if (!claim) return;
    $('#headerClaimTitle').textContent = claim.subject;
    $('#headerClaimId').textContent = `${claim.claim_id} · ${claim.language?.toUpperCase() || 'EN'} · received ${formatDate(claim.received_at)}`;
    $('#customerEmail').innerHTML = `
      <header class="email-head">
        <h2 class="email-subject">${esc(claim.subject)}</h2>
        <div class="email-meta">
          <strong>From</strong><span>${esc(claim.customer?.name || 'Customer')}</span>
          <strong>Address</strong><span>${esc(claim.customer?.address || '')}</span>
          <strong>Policy</strong><span>${esc(claim.customer?.policy || '')}</span>
          <strong>Received</strong><span>${esc(formatDate(claim.received_at))}</span>
        </div>
      </header>
      <div class="email-body">${esc(claim.message || '')}</div>`;
    $('#customerEmail').setAttribute('aria-busy', 'false');
    const artifacts = claim.artifacts || [];
    $('#attachmentCount').textContent = `${artifacts.length} files`;
    $('#attachmentList').innerHTML = artifacts.map(artifact => {
      let thumb = `<span>${artifact.media_type === 'application/pdf' ? 'PDF' : artifact.media_type === 'message/rfc822' ? 'EML' : 'IMG'}</span>`;
      if (artifact.media_type === 'application/pdf') thumb = `<img src="${pageUrl(artifact.artifact_id, 1)}" alt="">`;
      if (artifact.media_type?.startsWith('image/')) thumb = `<img src="${artifactUrl(artifact.artifact_id)}" alt="">`;
      return `
        <button class="attachment-row" type="button" data-artifact-id="${esc(artifact.artifact_id)}" data-source-rail-item data-source-id="${esc(artifact.artifact_id)}">
          <span class="attachment-thumb">${thumb}</span>
          <span><span class="attachment-title">${esc(artifact.title)}</span><span class="attachment-meta">${esc(artifact.filename)} · ${esc(mimeLabel(artifact))}</span></span>
          <span class="attachment-open">Open</span>
        </button>`;
    }).join('');
    window.dispatchEvent(new CustomEvent('casepath:claim-rendered', { detail: {
      claim,
      journey: state.journey,
    } }));
  }

  function renderProgress(activeId = null) {
    const run = currentRun();
    const completed = new Set((run?.events || []).filter(event => event.status === 'completed').map(event => event.stage));
    $('#agentProgress').innerHTML = STAGES.map((stage, index) => {
      const isComplete = completed.has(stage.id);
      const isActive = stage.id === activeId && !isComplete;
      return `<span class="agent-step ${isComplete ? 'complete' : isActive ? 'active' : ''}" data-progress-stage="${stage.id}"><span class="agent-step-dot">${isComplete ? '✓' : index + 1}</span>${esc(stage.short)}</span>`;
    }).join('');
  }

  function currentRun() {
    return state.journey === 'later' ? state.laterRun : state.run;
  }

  function setOrchestrator(status, done = false, requestedMode = '') {
    const mode = requestedMode || (done ? 'ready' : 'working');
    const chipLabels = {
      cached: 'Cached replay',
      failed: 'Stopped',
      live: 'Live',
      ready: 'Ready',
      returned: 'Returned',
      working: 'Working',
    };
    const chip = $('#liveChip');
    $('#orchestratorStatus').textContent = status;
    chip.textContent = chipLabels[mode] || chipLabels.working;
    chip.dataset.orchestrationMode = mode;
    chip.classList.toggle('done', mode === 'ready');
    document.body.dataset.orchestrationMode = mode;
  }

  async function startFlagshipRun() {
    if (state.polling || state.starting || state.journey !== 'start') return;
    state.starting = true;
    const button = $('#runCasePath');
    button.disabled = true;
    button.querySelector('span').textContent = 'Starting analysis…';
    // The claim is already rendered. Move to the truthful opening workspace
    // immediately; network wake-up must not look like a frozen primary action.
    $('#startState').hidden = true;
    $('#liveWorkspace').hidden = false;
    $('#journeyActions').hidden = true;
    document.body.dataset.casepathStartup = 'waking';
    setOrchestrator('Preparing the source-grounded review');
    beginStartupNotice();
    renderProgress();
    announceRender('opening');
    try {
      if (!params.has('preserve')) await api('/api/demo/reset', { method: 'POST' });
      state.demo = state.demo || await requestDemo();
      state.flagshipClaim = state.demo.claim;
      state.claim = state.flagshipClaim;
      renderClaim(state.claim);
      const created = await api('/api/runs', { method: 'POST', body: JSON.stringify({ claim_id: state.demo.demo_claim_id }) });
      state.runId = created.run_id;
      document.body.dataset.casepathActiveRunId = created.run_id;
      state.journey = 'live';
      endStartupNotice();
      delete document.body.dataset.casepathStartup;
      state.starting = false;
      state.eventQueue = [];
      state.queuedEventIds.clear();
      state.presentedEvents = [];
      state.runComplete = false;
      state.run = { run_id: created.run_id, events: [], status: created.status || 'queued', ...created };
      state.flagshipRun = state.run;
      publishRunSnapshot(state.run);
      $('#openAudit').disabled = false;
      $('#journeyActions').hidden = true;
      setOrchestrator('Opening one shared claim context');
      renderProgress();
      state.polling = true;
      streamRun(state.runId, false).catch(() => {});
    } catch (error) {
      state.starting = false;
      endStartupNotice();
      delete document.body.dataset.casepathStartup;
      $('#startState').hidden = false;
      $('#liveWorkspace').hidden = true;
      button.disabled = false;
      button.querySelector('span').textContent = 'Analyse claim';
      toast(`Could not start: ${error.message}`);
    }
  }

  function parseSseFrames(buffer, onFrame) {
    const normalized = buffer.replaceAll('\r\n', '\n');
    const frames = normalized.split('\n\n');
    const remainder = frames.pop() || '';
    for (const frame of frames) {
      const data = frame.split('\n')
        .filter(line => line.startsWith('data:'))
        .map(line => line.slice(5).trimStart())
        .join('\n');
      if (!data) continue;
      try { onFrame(JSON.parse(data)); } catch (_) {}
    }
    return remainder;
  }

  function mergeStreamEnvelope(runId, envelope, later) {
    const existing = (later ? state.laterRun : state.run)
      || runStore.get(runId)
      || { run_id: runId, events: [], status: 'running' };
    const patch = envelope.run_patch && typeof envelope.run_patch === 'object'
      ? envelope.run_patch
      : {};
    const auditEvent = envelope.audit_event && typeof envelope.audit_event === 'object'
      ? envelope.audit_event
      : null;
    const events = Array.isArray(existing.events) ? [...existing.events] : [];
    if (auditEvent && !events.some(event => event.event_id === auditEvent.event_id)) events.push(auditEvent);
    const run = { ...existing, ...patch, run_id: runId, events };
    if (later) state.laterRun = run;
    else {
      state.run = run;
      state.flagshipRun = run;
    }
    publishRunSnapshot(run, { later });
    if (auditEvent) {
      enqueueNewEvents(run, later);
      window.dispatchEvent(new CustomEvent('casepath:run-event', {
        detail: { event: auditEvent, envelope, run, runId, later },
      }));
    }
    if (envelope.type && envelope.type !== 'run.activity') {
      window.dispatchEvent(new CustomEvent('casepath:semantic-event', {
        detail: { ...envelope, runId, later },
      }));
    }
    if (!state.presenting) presentQueuedEvents(later);
  }

  async function hydrateTerminalRun(runId, later) {
    state.terminalHydrations += 1;
    document.body.dataset.terminalHydrations = String(state.terminalHydrations);
    const run = await api(`/api/runs/${encodeURIComponent(runId)}`);
    if (later) state.laterRun = run;
    else {
      state.run = run;
      state.flagshipRun = run;
    }
    publishRunSnapshot(run, { later, terminal: true });
    enqueueNewEvents(run, later);
    if (run.status === 'failed') {
      showTerminalFailure(run, later);
      throw new Error(run.error || 'The run stopped safely.');
    }
    if (run.status !== 'complete') throw new Error('The live run stream closed before a terminal result was available.');
    if (later) state.laterRunComplete = true;
    else state.runComplete = true;
    state.polling = false;
    if (!state.presenting) presentQueuedEvents(later);
    return run;
  }

  async function streamRun(runId, later, { present = true } = {}) {
    let after = 0;
    let retries = 0;
    try {
      while (true) {
        state.streamConnections += 1;
        document.body.dataset.runTransport = 'fetch-sse';
        document.body.dataset.streamConnections = String(state.streamConnections);
        document.body.dataset.activeRunPolls = '0';
        const response = await fetch(`${API}/api/runs/${encodeURIComponent(runId)}/events?after=${after}`, {
          headers: {
            Accept: 'text/event-stream',
            'X-CasePath-Session': SESSION_ID,
          },
        });
        if (!response.ok || !response.body) throw new Error(`Live run stream unavailable (${response.status}).`);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let terminal = false;
        while (true) {
          const { value, done } = await reader.read();
          buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
          buffer = parseSseFrames(buffer, envelope => {
            const sequence = Number(envelope.sequence);
            if (Number.isInteger(sequence) && sequence > after) after = sequence;
            if (present) mergeStreamEnvelope(runId, envelope, later);
            if (envelope.type === 'run.completed' || envelope.type === 'run.failed' || envelope.terminal === true) terminal = true;
          });
          if (done || terminal) break;
        }
        if (terminal) {
          if (present) return hydrateTerminalRun(runId, later);
          const run = await api(`/api/runs/${encodeURIComponent(runId)}`);
          if (run.status === 'failed') throw new Error(run.error || 'Comparison run failed.');
          if (run.status !== 'complete') throw new Error('The comparison stream closed before completion.');
          return run;
        }
        retries += 1;
        if (retries > 3) throw new Error('The live run stream ended before completion.');
        await wait(Math.min(2000, 250 * (2 ** retries)));
      }
    } catch (error) {
      state.polling = false;
      if (present) {
        const run = later ? state.laterRun : state.run;
        if (run?.status === 'failed') showTerminalFailure(run, later);
        else {
          state.eventQueue = state.eventQueue.filter(entry => entry.later !== later);
          state.presenting = false;
          renderFailure(SAFE_MODEL_FAILURE_MESSAGE);
        }
      }
      throw error;
    }
  }

  function enqueueNewEvents(run, later) {
    for (const event of run.events || []) {
      const key = `${later ? 'later' : 'flagship'}:${event.event_id || event.ordinal}`;
      if (state.queuedEventIds.has(key)) continue;
      state.queuedEventIds.add(key);
      state.eventQueue.push({ event, later, key });
    }
  }

  function announcePresentation(phase, event = null, explicitMoment = '') {
    if (phase === 'background') return;
    const moment = explicitMoment || $('#stageCanvas')?.dataset.casepathMoment || '';
    window.dispatchEvent(new CustomEvent('casepath:presentation', { detail: {
      phase, moment, eventId: returnedValue(event, 'event_id'), stage: returnedValue(event, 'stage'),
      runId: state.runId,
    } }));
  }

  function processStoryComplete() {
    const canvas = document.querySelector('#artifactCanvas');
    return canvas?.dataset.processStoryRunId === processStoryRunId()
      && document.querySelectorAll('#artifactProcessGraph[data-process-construction-state="complete"] [data-process-build-state="built"]').length >= 10;
  }

  function processStoryDrawing() {
    return Boolean(document.querySelector('#artifactProcessGraph[data-process-construction-state="building"]'));
  }

  function processStoryRunId() {
    return state.runId || document.body.dataset.casepathActiveRunId || 'unbound-run';
  }

  function waitForProcessStory() {
    const runId = processStoryRunId();
    if (processStoryWaitRunId !== runId) {
      processStoryWaitRunId = runId;
      processStoryWaitPromise = null;
    }
    if (processStoryComplete()) {
      document.body.dataset.casepathProcessStoryWait = 'complete';
      return Promise.resolve('complete');
    }
    if (processStoryWaitPromise) return processStoryWaitPromise;
    document.body.dataset.casepathProcessStoryWait = 'waiting';
    processStoryWaitPromise = new Promise(resolve => {
      let settled = false;
      let timeout = 0;
      const finish = status => {
        if (settled) return;
        settled = true;
        window.removeEventListener('casepath:artifact-process-complete', onComplete);
        window.removeEventListener('casepath:artifact-process-started', onStarted);
        window.removeEventListener('casepath:decision-flow-step', onProgress);
        window.clearTimeout(timeout);
        document.body.dataset.casepathProcessStoryWait = status;
        resolve(status);
      };
      const onComplete = event => {
        if (String(event.detail?.runId || '') === runId && processStoryComplete()) finish('complete');
      };
      const noteDelay = () => {
        if (settled) return;
        document.body.dataset.casepathProcessStoryWait = 'timed-out';
        setOrchestrator('The accepted process trace did not complete for this run.');
        toast('The accepted process trace did not complete. Nothing was substituted.');
        window.dispatchEvent(new CustomEvent('casepath:artifact-process-timeout', {
          detail: { runId, timeoutMs: PROCESS_STORY_TIMEOUT_MS },
        }));
        finish('timed-out');
      };
      const armTimeout = () => {
        if (settled) return;
        window.clearTimeout(timeout);
        document.body.dataset.casepathProcessStoryWait = 'drawing';
        timeout = window.setTimeout(noteDelay, PROCESS_STORY_TIMEOUT_MS);
      };
      const onStarted = event => {
        if (String(event.detail?.runId || '') === runId) armTimeout();
      };
      const onProgress = event => {
        if (String(event.detail?.runId || '') === runId) armTimeout();
      };
      window.addEventListener('casepath:artifact-process-complete', onComplete);
      window.addEventListener('casepath:artifact-process-started', onStarted);
      window.addEventListener('casepath:decision-flow-step', onProgress);
      armTimeout();
    });
    return processStoryWaitPromise;
  }

  function waitForProcessStoryOnce() {
    const runId = processStoryRunId();
    if (processStoryAwaitedRunId === runId) return processStoryWaitPromise || Promise.resolve('already-awaited');
    processStoryAwaitedRunId = runId;
    return waitForProcessStory();
  }

  function waitForOfficialLawTour() {
    const runId = processStoryRunId();
    const complete = () => {
      const canvas = document.querySelector('#artifactCanvas[data-official-law-tour-state="complete"]');
      return canvas?.dataset.officialLawTourRunId === runId;
    };
    if (complete()) return Promise.resolve('complete');
    return new Promise(resolve => {
      let settled = false;
      const finish = status => {
        if (settled) return;
        settled = true;
        window.removeEventListener('casepath:official-source-tour-complete', onComplete);
        window.clearTimeout(timeout);
        resolve(status);
      };
      const onComplete = event => {
        if (String(event.detail?.runId || '') === runId) finish('complete');
      };
      const timeout = window.setTimeout(() => finish('timed-out'), OFFICIAL_LAW_TOUR_TIMEOUT_MS);
      window.addEventListener('casepath:official-source-tour-complete', onComplete);
    });
  }

  function waitForFactSourceTour() {
    const runId = processStoryRunId();
    const complete = () => {
      const canvas = document.querySelector('#artifactCanvas[data-fact-source-tour-state="complete"]');
      return canvas?.dataset.factSourceTourRunId === runId;
    };
    if (complete()) return Promise.resolve('complete');
    document.body.dataset.casepathFactSourceTourWait = 'waiting';
    return new Promise(resolve => {
      let settled = false;
      const finish = status => {
        if (settled) return;
        settled = true;
        window.removeEventListener('casepath:fact-source-tour-complete', onComplete);
        window.clearTimeout(timeout);
        document.body.dataset.casepathFactSourceTourWait = status;
        resolve(status);
      };
      const onComplete = event => {
        if (String(event.detail?.runId || '') === runId) finish('complete');
      };
      const timeout = window.setTimeout(() => finish('timed-out'), FACT_SOURCE_TOUR_TIMEOUT_MS);
      window.addEventListener('casepath:fact-source-tour-complete', onComplete);
    });
  }

  function waitsForCompletedProcess(event) {
    if (['evidence', 'experience', 'verify'].includes(event?.stage)) return true;
    if (event?.stage !== 'agent_orchestration') return false;
    return ['evidence_checklist', 'final_claim_brief_audit'].includes(returnedValue(event, 'agent_id', 'actor_id'));
  }

  async function presentQueuedEvents(later) {
    if (state.presenting) return;
    state.presenting = true;
    while (state.eventQueue.length) {
      const activeRun = later ? state.laterRun : state.run;
      if (activeRun?.status === 'failed') {
        showTerminalFailure(activeRun, later);
        return;
      }
      const entry = state.eventQueue.shift();
      if (entry.later !== later) {
        state.eventQueue.push(entry);
        break;
      }
      if (!later && waitsForCompletedProcess(entry.event) && processStoryAwaitedRunId !== processStoryRunId()) {
        const processStoryStatus = await waitForProcessStoryOnce();
        if (processStoryStatus !== 'complete') {
          state.eventQueue = [];
          state.presenting = false;
          renderFailure('The accepted process trace did not complete for this exact run. Nothing was substituted.');
          return;
        }
      }
      let phase = 'background';
      if (later) {
        appendLaterEvent(entry.event);
      } else {
        phase = presentFlagshipEvent(entry.event);
        announcePresentation(phase, entry.event);
      }
      const conciseGraphStage = CONCISE_GRAPH_STAGES.has(entry.event.stage);
      // The first three chapters are user-visible evidence work too.  Advancing
      // them on the background heartbeat made their working and accepted
      // artifact frames last roughly 120 ms even though the product contract
      // above promises readable 2.3 s / 5.5 s holds.  Only genuinely
      // background events use the heartbeat; returned read, understanding, and
      // research frames follow the same semantic pacing as the later chapters.
      const frameMs = phase === 'working'
        ? conciseGraphStage ? CONCISE_WORKING_FRAME_MS : WORKING_FRAME_MS
        : phase === 'receipt'
          ? AGENT_RECEIPT_BEAT_MS
        : phase === 'artifact' && entry.event.stage === 'research'
          ? RESEARCH_ARTIFACT_FRAME_MS
          : phase === 'artifact' && conciseGraphStage
            ? CONCISE_ARTIFACT_FRAME_MS
          : phase === 'artifact'
            ? ARTIFACT_FRAME_MS
            : BACKGROUND_BEAT_MS;
      const processArtifact = phase === 'artifact' && entry.event.stage === 'process';
      if (!processArtifact) await wait(frameMs);
      const updatedRun = later ? state.laterRun : state.run;
      if (updatedRun?.status === 'failed') {
        showTerminalFailure(updatedRun, later);
        return;
      }
      if (phase === 'artifact' && entry.event.stage === 'understand') {
        const factTourStatus = await waitForFactSourceTour();
        if (factTourStatus !== 'complete') {
          state.eventQueue = [];
          state.presenting = false;
          renderFailure('The accepted fact trace did not arrive for this exact run. Nothing was substituted.');
          return;
        }
      }
      if (phase === 'artifact' && entry.event.stage === 'research') {
        const lawTourStatus = await waitForOfficialLawTour();
        if (lawTourStatus !== 'complete') {
          state.eventQueue = [];
          state.presenting = false;
          renderFailure('The official-law trace did not complete for this exact run. Nothing was substituted.');
          return;
        }
      }
      if (processArtifact) {
        const processStoryStatus = await waitForProcessStoryOnce();
        if (processStoryStatus !== 'complete') {
          state.eventQueue = [];
          state.presenting = false;
          renderFailure('The accepted process trace did not complete for this exact run. Nothing was substituted.');
          return;
        }
      }
    }
    state.presenting = false;
    const run = later ? state.laterRun : state.run;
    if (run?.status === 'complete' && !state.eventQueue.some(entry => entry.later === later)) {
      if (later) finishLaterRun();
      else {
        finishFlagshipRun();
        if (state.journey === 'ready') announcePresentation('ready', null, 'ready');
      }
    }
  }

  function presentFlagshipEvent(event) {
    rememberPresentedEvent(event);
    renderOrchestrationProof();
    if (event.stage === 'orchestrator') {
      setOrchestrator(event.headline || event.label);
      renderOpeningContext(event);
      return 'working';
    }
    if (event.stage === 'complete') {
      setOrchestrator(returnedValue(event, 'headline', 'label') || 'Final run event returned', false, 'returned');
      return 'background';
    }
    const returnedAgentId = returnedValue(event, 'agent_id', 'actor_id');
    const modelAgentEvent = eventKind(event) === 'nemotron_agent'
      && NEMOTRON_AGENT_IDS.has(returnedAgentId);
    const modelAgentStarted = modelAgentEvent
      && ['started', 'running', 'in_progress'].includes(eventState(event).toLowerCase());
    if (modelAgentStarted) {
      const canvas = $('#stageCanvas');
      if (canvas) canvas.dataset.casepathActiveAgentId = returnedAgentId;
      setOrchestrator(`${returnedActorName(event)} is working`, false, 'live');
      window.dispatchEvent(new CustomEvent('casepath:agent-focus', { detail: {
        agentId: returnedAgentId,
        callId: returnedValue(event, 'call_id'),
        outputArtifact: eventArtifacts(event).join(', '),
        eventId: returnedValue(event, 'event_id'),
        runId: state.runId,
        status: 'started',
        inputArtifact: returnedValue(event, 'input_artifact'),
        inputArtifactHash: returnedValue(event, 'input_artifact_hash', 'input_hash'),
        provider: returnedValue(event, 'provider'),
        requestedModel: returnedValue(event, 'requested_model', 'model'),
        callCount: returnedValue(event, 'call_count'),
        cacheHit: false,
      } }));
      return 'working';
    }
    if (event.stage === 'agent_orchestration'
      && modelAgentEvent
      && eventSucceeded(event)) {
      const cachedReplay = eventIsCachedReplay(event);
      const canvas = $('#stageCanvas');
      if (canvas) canvas.dataset.casepathActiveAgentId = returnedAgentId;
      setOrchestrator(cachedReplay
        ? `${returnedActorName(event)} reused a verified cached contribution · no provider call`
        : `${returnedActorName(event)} returned a bounded contribution`, false, cachedReplay ? 'cached' : 'returned');
      window.dispatchEvent(new CustomEvent('casepath:agent-focus', { detail: {
        agentId: returnedAgentId,
        callId: returnedValue(event, 'call_id'),
        outputArtifact: eventArtifacts(event).join(', '),
        eventId: returnedValue(event, 'event_id'),
        runId: state.runId,
        status: cachedReplay ? 'cache_hit' : 'completed',
        cacheHit: cachedReplay,
        callCount: returnedValue(event, 'call_count'),
        usageSource: returnedValue(event, 'usage_source'),
        outcome: eventState(event),
      } }));
      return 'receipt';
    }
    if (modelAgentEvent && eventSucceeded(event)) {
      const cachedReplay = eventIsCachedReplay(event);
      setOrchestrator(cachedReplay
        ? `${returnedActorName(event)} reused a verified cached contribution · no provider call`
        : `${returnedActorName(event)} returned a bounded contribution`, false, cachedReplay ? 'cached' : 'returned');
      window.dispatchEvent(new CustomEvent('casepath:agent-focus', { detail: {
        agentId: returnedAgentId,
        callId: returnedValue(event, 'call_id'),
        outputArtifact: eventArtifacts(event).join(', '),
        eventId: returnedValue(event, 'event_id'),
        runId: state.runId,
        status: cachedReplay ? 'cache_hit' : 'completed',
        cacheHit: cachedReplay,
        callCount: returnedValue(event, 'call_count'),
        usageSource: returnedValue(event, 'usage_source'),
        outcome: eventState(event),
      } }));
    }
    const stage = STAGES.find(item => item.id === event.stage);
    if (!stage) return 'background';
    const status = eventState(event).toLowerCase();
    const started = ['started', 'running', 'in_progress'].includes(status);
    const artifactReady = PRESENTABLE_STAGE_STATES.has(status);
    if (!started && !artifactReady) return 'background';
    state.activeStage = stage.id;
    state.stageMode = stage.id;
    const actor = returnedActorName(event);
    const update = returnedValue(event, 'headline', 'detail', 'question', 'label');
    setOrchestrator(
      [actor, update].filter(Boolean).join(': ') || 'Returned run event received',
      false,
      eventIsCachedReplay(event) ? 'cached' : modelAgentEvent && eventSucceeded(event) ? 'returned' : 'working',
    );
    renderProgress(stage.id);
    if (started) renderStageStarted(stage, event);
    else renderStageCompleted(stage, event);
    return started ? 'working' : 'artifact';
  }

  function stageHeader(stage, title, intro) {
    return `<div class="stage-kicker"><span class="agent-avatar">${esc(stage.short.slice(0, 2).toUpperCase())}</span><span><strong>${esc(stage.label)}</strong> · ${esc(stage.job)}</span></div><h2 class="stage-title">${esc(title)}</h2><p class="stage-intro">${esc(intro)}</p>`;
  }

  function renderOpeningContext(event) {
    const kind = eventKind(event);
    const expectsNemotronPlan = currentRun()?.model_mode === 'openrouter_nemotron';
    const orchestrationBoundary = kind === 'nemotron_agent'
      ? 'A call-bound Nemotron orchestration event was returned for this shared context.'
      : kind === 'deterministic_tool' && expectsNemotronPlan
        ? 'Application code opened the shared context; no model call is claimed for this setup step. The call-bound Nemotron plan appears only when its returned event arrives.'
        : 'This run returned legacy deterministic reference orchestration; no Nemotron orchestrator is claimed.';
    renderCanvas(`<div class="stage-shell">${stageHeader({ label: 'Orchestrator', short: 'CP', job: 'One shared claim context' }, 'CasePath has opened the claim.', event.detail || '')}<div class="live-question"><small>Orchestration boundary</small><strong>${esc(orchestrationBoundary)}</strong></div></div>`, 'opening');
  }

  function renderStageStarted(stage, event) {
    let title = event.headline || stage.job;
    let intro = event.detail || stage.job;
    if (stage.id === 'process') title = 'CasePath is building the handling process.';
    if (stage.id === 'evidence') title = 'CasePath is attaching evidence needs to the process.';
    if (stage.id === 'experience') title = 'CasePath is asking organizational memory for help.';
    renderCanvas(`<div class="stage-shell">${stageHeader(stage, title, intro)}<div class="live-question"><small>Question being answered</small><strong>${esc(event.question || stage.job)}</strong></div></div>`, stage.id);
  }

  function renderStageCompleted(stage, event) {
    if (stage.id === 'read') return renderReadStage(stage, event);
    if (stage.id === 'understand') return renderUnderstandStage(stage, event);
    if (stage.id === 'research') return renderLawStage(stage, event);
    if (stage.id === 'process') return renderProcessStage(stage, event, { evidence: false, precedents: false });
    if (stage.id === 'evidence') return renderProcessStage(stage, event, { evidence: true, precedents: false });
    if (stage.id === 'experience') return renderProcessStage(stage, event, { evidence: true, precedents: true });
    if (stage.id === 'verify') return renderVerifyStage(stage, event);
  }

  function renderReadStage(stage, event) {
    const parsed = state.run?.parsed_submission || {};
    const rows = (parsed.files || []).map(file => `<div class="event-row"><span class="event-mark">✓</span><div><strong>${esc(file.title)}</strong><p>${esc(file.read_detail)}</p></div></div>`).join('');
    renderCanvas(`<div class="stage-shell">${stageHeader(stage, 'The original submission is in the shared claim context.', event.detail || '')}<div class="event-list"><div class="event-row"><span class="event-mark">✓</span><div><strong>Customer message</strong><p>${parsed.message_chars || 0} characters preserved as submitted.</p></div></div>${rows}</div></div>`, 'read');
  }

  function renderUnderstandStage(stage, event) {
    const understanding = state.run?.result || state.run?.understanding || {};
    const facts = understanding.facts || [];
    renderCanvas(`<div class="stage-shell">${stageHeader(stage, 'CasePath has separated what is known from what is still open.', event.detail || '')}<div class="fact-stream">${facts.map(fact => {
      const refs = fact.source_refs || [];
      return `<article class="fact-row ${esc(fact.state)}" data-fact-id="${esc(fact.fact_id)}"><span class="fact-state"></span><div><strong>${esc(fact.label)} — ${esc(fact.value)}</strong><p>${esc(fact.explanation)}</p><small>${esc(fact.state || 'unclassified')} · confidence ${formatConfidence(fact.confidence)}</small>${refs.length ? `<div class="fact-source-list">${refs.map(ref => sourceRefButton(fact, ref)).join('')}</div>` : '<p class="grounding-warning">No source reference returned.</p>'}</div></article>`;
    }).join('')}</div></div>`, 'understand');
    bindSourceLinks($('#stageCanvas'));
  }

  function officialLegalSourceMarkup(source) {
    const retrieval = source?.retrieval || {};
    return `<article class="legal-authority official" data-legal-source-id="${esc(source?.source_id || '')}" data-passage-sha256="${esc(source?.passage_sha256 || '')}" data-snapshot-sha256="${esc(retrieval.snapshot_sha256 || '')}" data-snapshot-scope="${esc(retrieval.snapshot_scope || '')}" data-registry-version="${esc(retrieval.registry_version || '')}"><small>Official registry source · qualified review pending</small><strong>${esc(source?.title || 'Official source not returned')}</strong><blockquote lang="${esc(source?.passage_language || '')}">${esc(source?.passage_text || 'Official passage not returned.')}</blockquote><p>${esc(source?.passage_summary || '')}</p><dl><dt>Version</dt><dd>${esc(source?.version_date || 'not returned')}</dd><dt>Location</dt><dd>${esc(source?.location || 'not returned')}</dd><dt>Passage SHA-256</dt><dd><code>${esc(source?.passage_sha256 || 'not returned')}</code></dd><dt>Registry record</dt><dd>${esc(retrieval.method || 'not returned')} · ${esc(retrieval.retrieved_at || 'date not returned')} · ${esc(retrieval.registry_version || 'version not returned')}</dd><dt>Snapshot scope</dt><dd>${esc(retrieval.snapshot_scope || 'not returned')}</dd><dt>Snapshot SHA-256</dt><dd><code>${esc(retrieval.snapshot_sha256 || 'not returned')}</code></dd></dl>${source?.url ? `<a href="${esc(source.url)}" target="_blank" rel="noopener">Open official source</a>` : ''}</article>`;
  }

  function handlingPrincipleMarkup(source) {
    return `<article class="legal-authority deterministic" data-legal-source-id="${esc(source?.source_id || '')}" data-producer="${esc(source?.producer || '')}"><small>Deterministic application proposal · qualified review pending</small><strong>${esc(source?.title || 'Handling proposal not returned')}</strong><p>${esc(source?.role || '')}</p><p><b>Producer:</b> ${esc(source?.producer || 'not returned')} · <b>status:</b> ${esc(source?.validation_status || 'not returned')}</p></article>`;
  }

  function officialUrlHost(value) {
    try {
      return new URL(String(value || '')).host || 'official source';
    } catch (_) {
      return 'official source';
    }
  }

  function legalQuestionMarkup(question, legal, index) {
    const officialById = new Map((legal.sources || []).map(source => [source.source_id, source]));
    const principleById = new Map((legal.handling_principles || []).map(source => [source.source_id, source]));
    const officials = (question.source_ids || []).map(id => officialById.get(id)).filter(Boolean);
    const principles = (question.interpretation_ids || []).map(id => principleById.get(id)).filter(Boolean);
    return `<article class="law-query" data-question-id="${esc(question.question_id || '')}" data-source-ids="${esc((question.source_ids || []).join(','))}" data-interpretation-ids="${esc((question.interpretation_ids || []).join(','))}" data-process-node-ids="${esc((question.process_node_ids || []).join(','))}"><span class="law-number">${index + 1}</span><div><strong>${esc(question.text || 'Legal question not returned')}</strong><p>${esc(question.consequence || 'Consequence not returned')}</p><small>${officials.length} official source${officials.length === 1 ? '' : 's'} · ${principles.length} deterministic proposal${principles.length === 1 ? '' : 's'} · process ${esc((question.process_node_ids || []).join(' → '))}</small><details><summary>Inspect joined passage and provenance</summary><div class="legal-authority-list">${officials.map(officialLegalSourceMarkup).join('')}${principles.map(handlingPrincipleMarkup).join('')}</div></details></div></article>`;
  }

  function officialSourceBrowserMarkup(legal) {
    const sources = legal.sources || [];
    if (!sources.length) return '';
    const first = sources[0];
    return `<section class="official-source-browser" data-retrieval-method="versioned_official_source_registry_lookup" data-registry-version="${esc(legal.registry_version || '')}" data-cache-purpose="reliable_same-source_reuse">
      <header class="official-browser-chrome">
        <span class="official-browser-dots" aria-hidden="true"><i></i><i></i><i></i></span>
        <span class="official-browser-address"><small>Cached exact official source</small><strong data-official-browser-host>${esc(officialUrlHost(first?.url))}</strong><code data-official-browser-url>${esc(first?.url || 'URL not returned')}</code></span>
        <span class="official-browser-cache"><b>Reusable snapshot</b><code>${esc(legal.registry_version || 'version not returned')}</code></span>
      </header>
      <nav aria-label="Exact official Swiss-law sections">${sources.map((source, index) => `<button class="official-source-tab" type="button" data-official-source-tab="${esc(source.source_id)}" data-official-source-url="${esc(source.url || '')}" data-official-source-location="${esc(source.location || source.title)}" aria-selected="${index === 0}">${esc(source.location || source.title)}</button>`).join('')}</nav>
      ${sources.map((source, index) => `<article class="official-source-passage" data-official-source-panel="${esc(source.source_id)}" data-official-source-url="${esc(source.url || '')}" ${index === 0 ? '' : 'hidden'}><div><small>${esc(source.title)}</small><strong>${esc(source.location || 'Exact section')}</strong></div><blockquote lang="${esc(source.passage_language || '')}">${esc(source.passage_text || 'Official passage not returned.')}</blockquote><footer><span>Cached for reliable reuse · ${esc(source.version_date || 'version date not returned')} · passage ${esc((source.passage_sha256 || '').slice(0, 10) || 'hash unavailable')}</span>${source.url ? `<a href="${esc(source.url)}" target="_blank" rel="noopener">Verify on official website ↗</a>` : ''}</footer></article>`).join('')}
    </section>`;
  }

  function bindOfficialSourceBrowser() {
    const browser = $('.official-source-browser', $('#stageCanvas'));
    const buttons = browser ? $$('.official-source-tab', browser) : [];
    if (!buttons.length) return;
    for (const button of buttons) button.addEventListener('click', () => {
      for (const item of buttons) item.setAttribute('aria-selected', String(item === button));
      for (const panel of $$('.official-source-passage', browser)) panel.hidden = panel.dataset.officialSourcePanel !== button.dataset.officialSourceTab;
      const url = button.dataset.officialSourceUrl || '';
      const urlNode = $('[data-official-browser-url]', browser);
      const hostNode = $('[data-official-browser-host]', browser);
      if (urlNode) urlNode.textContent = url;
      if (hostNode) hostNode.textContent = officialUrlHost(url);
      window.dispatchEvent(new CustomEvent('casepath:official-source-step', { detail: {
        sourceId: button.dataset.officialSourceTab,
        location: button.dataset.officialSourceLocation,
        url,
        retrievalMethod: browser.dataset.retrievalMethod,
        registryVersion: browser.dataset.registryVersion,
        cachePurpose: browser.dataset.cachePurpose,
      } }));
    });
  }

  function renderLawStage(stage, event) {
    const legal = state.run?.result?.legal_research || state.run?.legal_research || {};
    renderCanvas(`<div class="stage-shell">${stageHeader(stage, 'Swiss-law questions are joined to versioned official passages.', 'Each question names its official-source IDs, deterministic handling-proposal IDs, process decisions, consequence, and pending qualified-review status.')}${officialSourceBrowserMarkup(legal)}<div class="law-flow" data-legal-contract="${esc(legal.contract || '')}" data-registry-version="${esc(legal.registry_version || '')}">${(legal.questions || []).map((question, index) => legalQuestionMarkup(question, legal, index)).join('')}</div></div>`, 'research');
    bindOfficialSourceBrowser();
  }

  function processData() {
    const run = currentRun();
    return run?.result?.process || run?.process || run?.process_candidate || null;
  }

  function checklistData() {
    const run = currentRun();
    return run?.result?.checklist || run?.checklist || run?.checklist_candidate || null;
  }

  function understandingData() {
    const run = currentRun();
    return run?.result || run?.understanding || null;
  }

  function legalData() {
    const run = currentRun();
    return run?.result?.legal_research || run?.legal_research || null;
  }

  function nodeById(nodeId) {
    return processData()?.nodes?.find(node => node.node_id === nodeId) || null;
  }

  function owningNodeForFact(factId) {
    if (!factId) return null;
    const process = processData();
    const direct = (process?.nodes || []).find(node => (node.fact_ids || []).includes(factId));
    if (direct) return direct;
    const item = (checklistData()?.items || []).find(entry => entry.fact_id === factId && entry.node_id);
    return item ? nodeById(item.node_id) : null;
  }

  function edgeStateLabel(stateValue) {
    return ({ selected: 'current path', possible: 'available branch', inactive: 'inactive branch', loop: 'evidence loop', blocked: 'blocked', future: 'later path' })[stateValue] || stateValue || 'connected';
  }

  function precedentProvenance(precedent) {
    if (['qualified_expert_reviewed', 'expert_reviewed_memory'].includes(precedent?.review_status) && precedent?.memory_id) return 'Qualified expert-reviewed case memory returned by the server';
    if (precedent?.review_status === 'unverified_demo_memory' && precedent?.memory_id) return 'Unverified generated-demo review memory returned by the server';
    if (precedent?.review_status === 'generated_reference') return 'Generated reference pattern · not qualified review';
    const review = precedent?.review_status ? ` · ${precedent.review_status.replaceAll('_', ' ')}` : '';
    return `Reference pattern${review}`;
  }

  function precedentRankingSummary(precedent) {
    const ranking = precedent?.ranking || {};
    const factors = (ranking.factors || []).map(factor => `${factor.factor}: ${factor.value} (+${factor.weight})`);
    return `<span class="precedent-rank" data-ranking-contract="${esc(ranking.contract || '')}" data-corpus-version="${esc(ranking.corpus_version || '')}" data-rank="${esc(ranking.rank ?? '')}" data-score-basis-points="${esc(ranking.score_basis_points ?? '')}" data-context-hash="${esc(ranking.context_hash || '')}"><strong>Rank ${esc(ranking.rank ?? 'not returned')} · ${esc(ranking.score_basis_points ?? 'not returned')} points</strong><small>${esc(factors.join(' · ') || 'Ranking factors not returned')}</small><code>${esc(ranking.context_hash || 'Context hash not returned')}</code></span>`;
  }

  function precedentRankingReceipt(run) {
    const receipt = run?.result?.precedent_ranking || run?.precedent_ranking;
    if (!receipt) return '';
    const context = receipt.context || {};
    const candidates = (receipt.candidate_scores || []).map(item => `${item.claim_id}: ${item.score_basis_points}`).join(' · ');
    return `<aside class="precedent-ranking-receipt" data-ranking-contract="${esc(receipt.contract || '')}" data-corpus-version="${esc(receipt.corpus_version || '')}" data-context-hash="${esc(receipt.context_hash || '')}" data-result-hash="${esc(receipt.result_hash || '')}" data-selected-claim-ids="${esc((receipt.selected_claim_ids || []).join(','))}"><small>Inspectable generated-pattern ranking receipt</small><strong>${esc((receipt.selected_claim_ids || []).join(' → ') || 'Selected IDs not returned')}</strong><p>Current decision ${esc(context.current_process_node_id || 'not returned')} · next ${esc(context.next_action_node_id || 'not returned')} · unresolved ${esc((context.unresolved_fact_ids || []).join(', ') || 'none')}</p><small>${esc(candidates || 'Candidate scores not returned')}</small><code>context ${esc(receipt.context_hash || 'not returned')}</code><code>result ${esc(receipt.result_hash || 'not returned')}</code></aside>`;
  }

  function legalProvenance(source) {
    if (source?.source_type === 'official_statute' || source?.source_type === 'official_guidance') return { kind: 'official', label: 'Official registry source · passage retained' };
    return { kind: 'interpretation', label: 'Deterministic application proposal · qualified review pending' };
  }

  function nodeState(nodeId) {
    const process = processData();
    const overlay = process?.current_overlay || currentRun()?.result?.current_overlay || {};
    if (nodeId === overlay.current_node_id || nodeId === process?.current_node) return 'current';
    if ((overlay.completed_node_ids || []).includes(nodeId)) return 'complete';
    if ((overlay.blocked_node_ids || []).includes(nodeId)) return 'blocked';
    return 'future';
  }

  function evidenceForNode(nodeId) {
    return (checklistData()?.items || []).filter(item => evidenceOwnerIds(item).includes(nodeId));
  }

  function evidenceOwnerIds(item) {
    const returned = Array.isArray(item?.node_ids) ? item.node_ids.filter(value => typeof value === 'string' && value) : [];
    return returned.length ? [...new Set(returned)] : item?.node_id ? [item.node_id] : [];
  }

  function evidenceOwnershipMarkup(item, inspectedNodeId) {
    const owners = evidenceOwnerIds(item);
    const primary = owners[0] || item?.node_id || '';
    const secondary = owners.filter(nodeId => nodeId !== primary);
    const labels = owners.map(nodeId => nodeById(nodeId)?.title || nodeId.replaceAll('_', ' '));
    const inspectedIndex = owners.indexOf(inspectedNodeId);
    return `<span class="evidence-ownership" data-primary-node-id="${esc(primary)}" data-node-ids="${esc(owners.join(','))}" data-current-path="${esc(String(item?.current_path === true))}" data-inspected-owner-index="${esc(inspectedIndex)}"><strong>Primary decision: ${esc(labels[0] || 'not returned')}</strong>${secondary.length ? `<small>Also required by ${esc(labels.slice(1).join(' · '))}</small>` : '<small>Single process owner</small>'}<small>Ordered owner IDs: ${esc(owners.join(' → ') || 'not returned')} · current path ${esc(String(item?.current_path === true))}</small></span>`;
  }

  function memoryApplicationReceipt(result = currentRun()?.result || currentRun()) {
    const receipt = result?.memory_application;
    return receipt?.contract === 'casepath.memory-application-receipt/1.0.0'
      && receipt.authority === 'unverified_demo'
      && receipt.scope === 'case_specific_guidance_only'
      && receipt.eligibility?.contract === 'casepath.semantic-memory-eligibility/1.0.0'
      && receipt.eligibility?.rule_id === 'same_grounded_mould_signature_v2'
      && /^[a-f0-9]{64}$/.test(receipt.eligibility?.semantic_signature_hash || '')
      && receipt.model_acceptance_reused === false
      && receipt.shared_rule_applied === false
      && receipt.applied === true
      ? receipt
      : null;
  }

  function reviewedMemoryState(result = currentRun()?.result || currentRun()) {
    const receipt = memoryApplicationReceipt(result);
    const retrievedPrecedent = (result?.precedents || []).find(item => item.review_status === 'unverified_demo_memory' && item.memory_id);
    const retrieved = Boolean(retrievedPrecedent)
      && result?.reviewed_memory_retrieved === true
      && result?.knowledge?.reviewed_memory_retrieved === true;
    const usedFlags = result?.memory_used === true
      && result?.reviewed_memory_used === true
      && result?.knowledge?.reviewed_memory_used === true
      && result?.process?.memory_used === true
      && result?.checklist?.memory_used === true;
    const unusedFlags = result?.memory_used === false
      && result?.reviewed_memory_used === false
      && result?.knowledge?.reviewed_memory_used === false
      && result?.process?.memory_used === false
      && result?.checklist?.memory_used === false;
    const used = retrieved && usedFlags && Boolean(receipt);
    const retrievedOnly = retrieved
      && unusedFlags
      && result?.memory_application == null
      && result?.process?.case_specific_guidance_applied !== true
      && result?.checklist?.case_specific_guidance_applied !== true;
    return { receipt, retrievedPrecedent, retrieved, used, retrievedOnly };
  }

  function renderMemoryReuseProof({ result, proof, memoryUsed, retrievedOnly, memoryState }) {
    if (!memoryUsed && !retrievedOnly) return '';
    const receipt = memoryState?.receipt || null;
    const precedent = memoryState?.retrievedPrecedent || null;
    if (!precedent || (memoryUsed && !receipt)) return '';
    const authorityCopy = precedent.review_status === 'qualified_expert_reviewed'
      ? 'Qualified expert-reviewed case memory returned'
      : 'Unverified demo review memory returned';
    const playbook = result?.playbook?.version || 'Version not returned';
    const wrapperHeader = memoryUsed
      ? '<header><small>Unverified demo memory returned with a valid application receipt</small><strong>Bounded guidance was applied; this implies neither qualified review nor release of the quarantined shared-rule candidate.</strong></header>'
      : '<header><small>Unverified demo memory retrieved and ranked only</small><strong>No application receipt or memory-driven DTO change was returned; this implies neither qualified review nor shared-rule release.</strong></header>';
    const receiptAttributes = memoryUsed
      ? ` data-memory-contract="${esc(receipt.contract)}" data-application-hash="${esc(receipt.application_hash || '')}" data-memory-authority="${esc(receipt.authority)}" data-memory-scope="${esc(receipt.scope)}"`
      : '';
    const threadBody = memoryUsed
      ? `<article><small>${esc(authorityCopy)} and applied</small><strong>${esc(precedent.claim_id)} · ${esc(precedent.memory_id)}</strong></article>
        <article><small>Receipt authority and scope</small><strong>${esc(receipt.authority)} · ${esc(receipt.scope)}</strong></article>
        <article><small>Application hash</small><strong><code>${esc(receipt.application_hash || 'not returned')}</code></strong></article>
        <article><small>Shared playbook</small><strong>${esc(playbook)} unchanged · shared rule ${esc(String(receipt.shared_rule_applied === true))}</strong></article>
        <article><small>Acceptance boundary</small><strong>Model acceptance reused ${esc(String(receipt.model_acceptance_reused === true))}${proof?.causal_delta?.nonzero === true ? ' · nonzero causal delta computed' : ''}</strong></article>`
      : `<article><small>${esc(authorityCopy)} and ranked</small><strong>${esc(precedent.claim_id)} · ${esc(precedent.memory_id)}</strong></article>
        <article><small>Guidance state</small><strong>Disabled for this required-now review outcome</strong></article>
        <article><small>Application receipt</small><strong>None returned</strong></article>
        <article><small>Process effect</small><strong>Not used or applied · no memory-driven DTO change</strong></article>
        <article><small>Shared playbook</small><strong>${esc(playbook)} unchanged</strong></article>`;
    return `<section class="v18-reuse-proof">${wrapperHeader}<section class="v17-reuse-thread${retrievedOnly ? ' retrieved-only' : ''}" data-memory-retrieved="true" data-memory-used="${esc(String(memoryUsed))}" data-application-receipt="${esc(String(Boolean(receipt)))}"${receiptAttributes} aria-label="How returned review memory was ranked or applied on the held-out later demo claim">${threadBody}</section></section>`;
  }

  function factsForNode(node) {
    const ids = new Set(node?.fact_ids || []);
    for (const item of evidenceForNode(node?.node_id)) if (item.fact_id) ids.add(item.fact_id);
    return (understandingData()?.facts || []).filter(fact => ids.has(fact.fact_id));
  }

  function legalForNode(node) {
    const legal = legalData() || {};
    const all = [...(legal.sources || []), ...(legal.handling_principles || [])];
    const joined = (legal.questions || []).filter(question => (question.process_node_ids || []).includes(node?.node_id)).flatMap(question => [...(question.source_ids || []), ...(question.interpretation_ids || [])]);
    const ids = new Set([...(node?.legal_source_ids || []), ...(legal.node_links?.[node?.node_id] || []), ...joined]);
    return all.filter(source => ids.has(source.source_id));
  }

  function processConstructionBasis(node) {
    const facts = factsForNode(node);
    const laws = legalForNode(node);
    const official = laws.find(source => Boolean(source?.url));
    const handlingRule = laws.find(source => !source?.url);
    const primaryFact = facts.find(fact => !['unknown', 'conflicting'].includes(fact.state)) || facts[0];
    const items = [];
    if (primaryFact) {
      items.push({
        kind: 'evidence',
        label: 'Claim evidence',
        detail: `${primaryFact.label || primaryFact.fact_id}: ${primaryFact.value ?? 'value not returned'}`,
      });
    }
    if (official) {
      items.push({
        kind: 'law',
        label: 'Swiss law',
        detail: official.location || official.title || official.source_id,
      });
    }
    if (handlingRule) {
      items.push({
        kind: 'reasoning',
        label: 'Handling rule',
        detail: handlingRule.title || handlingRule.role || handlingRule.source_id,
      });
    }
    items.push({
      kind: 'reasoning',
      label: 'Process rationale',
      detail: node?.why || node?.activation || 'Required by the returned process topology.',
    });
    return {
      items,
      factIds: facts.map(fact => fact.fact_id).filter(Boolean),
      lawIds: laws.map(source => source.source_id).filter(Boolean),
      evidenceRequirementIds: [...new Set([...(node?.evidence_requirement_ids || []), ...evidenceForNode(node?.node_id).map(item => item.item_id).filter(Boolean)])],
    };
  }

  function processBasisAttributes(basis) {
    return `data-basis-kinds="${esc([...new Set(basis.items.map(item => item.kind))].join(','))}" data-basis-label="${esc(basis.items.map(item => item.label).join(' + '))}" data-basis-detail="${esc(basis.items.map(item => item.detail).join(' → '))}" data-basis-fact-ids="${esc(basis.factIds.join(','))}" data-basis-law-ids="${esc(basis.lawIds.join(','))}" data-basis-evidence-requirement-ids="${esc(basis.evidenceRequirementIds.join(','))}"`;
  }

  function processBasisMarkup(basis) {
    return `<span class="process-node-basis" ${processBasisAttributes(basis)}>${basis.items.map(item => `<span class="process-basis-item" data-basis-kind="${esc(item.kind)}"><small>${esc(item.label)}</small><em>${esc(item.detail)}</em></span>`).join('')}</span>`;
  }

  function statusLabel(status) {
    return ({
      provided_sufficient: 'Available',
      provided_insufficient: 'Insufficient',
      missing: 'Missing',
      conditional: 'Conditional',
      not_applicable: 'Not needed on this path',
    })[status] || status?.replaceAll('_', ' ') || '';
  }

  function validatedContributionEntries(value, expectedAttribution, expectedEntityId = '') {
    const entries = (Array.isArray(value) ? value : value && typeof value === 'object' ? [value] : [])
      .filter(item => item && typeof item === 'object');
    if (!entries.length) return [];
    const ids = entries.map(item => item.contribution_id);
    if (ids.some(id => typeof id !== 'string' || !id) || new Set(ids).size !== ids.length) return [];
    const valid = entries.every(item => {
      if (typeof item.deterministic_fallback_applied !== 'boolean'
        || !Number.isInteger(item.confidence_basis_points)
        || item.confidence_basis_points < 0
        || item.confidence_basis_points > 10000) return false;
      const expectedRole = item.deterministic_fallback_applied ? DETERMINISTIC_CONTRIBUTION_ROLE : expectedAttribution;
      if (item.attribution !== expectedRole) return false;
      if (expectedAttribution === PROCESS_CONTRIBUTION_ROLE) {
        return typeof item.fact_id === 'string'
          && Boolean(item.fact_id)
          && item.contribution_id === `fact:${item.fact_id}:decision_value`
          && Array.isArray(item.model_owned_fields)
          && item.model_owned_fields.length === 1
          && item.model_owned_fields[0] === 'decision_value';
      }
      if (expectedAttribution === EVIDENCE_CONTRIBUTION_ROLE) {
        const match = item.contribution_id.match(/^item:(.+):(status|artifacts)$/);
        return Boolean(match
          && (!expectedEntityId || match[1] === expectedEntityId)
          && item.field === (match[2] === 'status' ? 'status' : 'artifact_ids'));
      }
      if (expectedAttribution === FINAL_CONTRIBUTION_ROLE) {
        return FINAL_FIELD_CONTRACT.some(([field, id]) => field === item.field && id === item.contribution_id);
      }
      return false;
    });
    return valid ? entries : [];
  }

  function renderContributionAttribution(value, unit, expectedEntityId = '') {
    const reviewTransform = currentRun()?.result?.review_transform
      || currentRun()?.review_transform
      || currentRun()?.result?.audit?.review_transform;
    if (reviewTransform?.acceptance_scope === 'post_review_unverified_transform' || memoryApplicationReceipt()) return '';
    const expectedAttribution = unit === 'fact'
      ? PROCESS_CONTRIBUTION_ROLE
      : unit === 'final'
        ? FINAL_CONTRIBUTION_ROLE
        : EVIDENCE_CONTRIBUTION_ROLE;
    const entries = validatedContributionEntries(value, expectedAttribution, expectedEntityId);
    const accepted = entries.filter(item => item.deterministic_fallback_applied === false && returnedValue(item, 'attribution') === expectedAttribution);
    const fallback = entries.filter(item => item.deterministic_fallback_applied === true && returnedValue(item, 'attribution') === DETERMINISTIC_CONTRIBUTION_ROLE);
    if (!accepted.length && !fallback.length) return '';
    const authority = accepted.length && fallback.length ? 'mixed' : accepted.length ? 'nemotron-accepted' : 'deterministic-fallback';
    const roles = [...new Set(accepted.map(item => returnedValue(item, 'attribution')).filter(Boolean))];
    const unitLabel = unit === 'fact' ? 'decision field' : 'field';
    const countLabel = count => `${count} ${unitLabel}${count === 1 ? '' : 's'}`;
    const acceptedLabel = accepted.length ? `Nemotron accepted · ${countLabel(accepted.length)}` : '';
    const fallbackLabel = fallback.length ? `Deterministic fallback · ${countLabel(fallback.length)}` : '';
    return `<span class="model-contribution-attribution ${authority}" data-contribution-authority="${authority}" data-accepted-count="${accepted.length}" data-fallback-count="${fallback.length}" data-accepted-contribution-ids="${esc(accepted.map(item => item.contribution_id).join(','))}" data-fallback-contribution-ids="${esc(fallback.map(item => item.contribution_id).join(','))}"><i aria-hidden="true"></i><span><strong>${esc([acceptedLabel, fallbackLabel].filter(Boolean).join(' · '))}</strong>${roles.length ? `<small>${esc(roles.join(' · '))}</small>` : ''}</span></span>`;
  }

  function renderProcessStage(stage, event, options) {
    state.stageMode = options.precedents ? 'experience' : options.evidence ? 'evidence' : 'process';
    const title = options.precedents ? 'Generated reference patterns are helping with the difficult decision.' : options.evidence ? 'Evidence now follows directly from the process.' : 'The complete handling process is taking shape.';
    const intro = options.precedents ? 'CasePath ranked generated reference patterns against the same branch, unresolved fact, and evidence need. Each result carries its provenance, factors, context hash, and review state.' : options.evidence ? 'Each process node now carries the facts and evidence it needs. The checklist is only an aggregate of these links.' : 'The main handling spine is visible first. The current claim is overlaid inside it, and alternative branches stay folded until they matter.';
    renderCanvas(`<div class="stage-shell">${stageHeader(stage, title, intro)}${renderProcessWorkspace({ ...options, story: state.stageMode === 'process' })}</div>`, state.stageMode);
    bindProcessInteractions();
  }

  function renderProcessWorkspace({ evidence = false, precedents = false, story = false } = {}) {
    const process = processData();
    if (!process) return '<p>Process artifact is not ready.</p>';
    const spine = (process.main_spine || []).map(nodeById).filter(Boolean);
    const spineIds = new Set(spine.map(node => node.node_id));
    const branchNodes = (process.nodes || []).filter(node => !spineIds.has(node.node_id));
    if (!state.selectedNodeId || !nodeById(state.selectedNodeId)) state.selectedNodeId = process.current_node || 'causation';
    return `<div class="process-layout" data-evidence="${esc(String(evidence))}" data-precedents="${esc(String(precedents))}" data-process-story="${story ? 'grounded-node-sequence/1.0.0' : ''}" data-process-id="${esc(process.process_id || '')}" data-process-current-node="${esc(process.current_node || '')}" data-process-node-count="${spine.length}"><div class="process-map">${story ? `<span class="visually-hidden" aria-live="polite" aria-atomic="true" data-process-build-announcement>Preparing the process decisions.</span><section class="process-build-focus" aria-live="off" data-process-build-focus><span class="process-build-order"><i aria-hidden="true"></i><b data-process-build-count>Preparing ${spine.length} decisions</b></span><div><small data-process-build-basis>Claim evidence + Swiss law + process rationale</small><strong data-process-build-title>Connecting every decision to its reason</strong><p data-process-build-detail>The graph will be constructed in returned process order. One grounded decision is introduced at a time.</p></div></section>` : ''}<div class="process-spine">${spine.map((node, index) => {
      const status = nodeState(node.node_id);
      const count = evidenceForNode(node.node_id).length;
      const basis = processConstructionBasis(node);
      return `<div class="process-node ${status}" data-process-build-index="${index}" data-process-parent-id="${esc(index ? spine[index - 1]?.node_id || '' : '')}" data-process-edge-condition="${esc((process.edges || []).find(edge => edge.source === spine[index - 1]?.node_id && edge.target === node.node_id)?.condition || '')}" ${processBasisAttributes(basis)} style="animation-delay:${index * 55}ms"><span class="process-marker">${status === 'complete' ? '✓' : status === 'current' ? '?' : index + 1}</span><button class="process-node-button" type="button" data-node-id="${esc(node.node_id)}"><span><small>${status === 'current' ? 'Current decision' : status === 'complete' ? 'Established' : status === 'blocked' ? 'Waits for earlier answer' : 'Later stage'}</small><strong>${esc(node.title)}</strong><span class="node-answer">${esc(node.answer || node.question)}</span>${processBasisMarkup(basis)}${renderContributionAttribution(node.agent_decision_contributions, 'fact')}</span>${evidence && count ? `<span class="node-evidence-count">${count} evidence link${count === 1 ? '' : 's'}</span>` : ''}</button>${node.node_id === (process.current_node || 'causation') ? renderBranches(node) : ''}</div>`;
    }).join('')}</div>${renderBranchExplorer(branchNodes, process.edges || [], evidence)}</div>${renderInspector(state.selectedNodeId, { evidence, precedents })}</div>`;
  }

  function renderBranches(node) {
    if (!node.branches?.length) return '';
    const selected = node.branches.find(branch => branch.state === 'selected') || node.branches[0];
    const selectedNode = nodeById(selected.target);
    const selectedBasis = processConstructionBasis(selectedNode || { why: selected.condition, activation: selected.condition });
    return `<div class="branch-fork"><article class="process-selected-branch" data-process-selected-branch data-node-id="${esc(selected.target)}" data-process-parent-id="${esc(node.node_id)}" data-process-edge-condition="${esc(selected.condition)}" ${processBasisAttributes(selectedBasis)}><span class="process-selected-branch-line" aria-hidden="true"></span><div><small>Selected from the returned graph</small><strong>${esc(selected.label)}</strong><p>${esc(selected.condition)}</p><span>${esc(selectedBasis.items.map(item => item.label).join(' + '))}</span></div></article><button type="button" data-toggle-node-branches aria-expanded="false"><span>${node.branches.length - 1} alternative causation outcome${node.branches.length === 2 ? '' : 's'}</span><strong>Inspect alternatives</strong></button><div class="branch-options" hidden>${node.branches.map(branch => { const target = nodeById(branch.target); const basis = processConstructionBasis(target || { why: branch.condition, activation: branch.condition }); return `<button type="button" class="branch-option ${branch.state === 'selected' ? 'selected' : ''}" data-node-id="${esc(branch.target)}" data-process-parent-id="${esc(node.node_id)}" data-process-edge-condition="${esc(branch.condition)}" ${processBasisAttributes(basis)}><strong>${esc(branch.label)}</strong><p>${esc(branch.condition)}</p>${processBasisMarkup(basis)}<small>${esc(edgeStateLabel(branch.state))} · opens ${esc(branch.target)}</small></button>`; }).join('')}</div></div>`;
  }

  function renderBranchExplorer(nodes, edges, evidence) {
    if (!nodes.length && !edges.length) return '';
    const nodeExplorer = nodes.length ? `<button class="branch-explorer-toggle" type="button" data-toggle-all-branches aria-expanded="${state.branchesExpanded}" aria-controls="processBranchGrid"><span><small>Branches and evidence loops</small><strong id="processBranchesTitle">Explore ${nodes.length} connected decisions</strong></span><span>${state.branchesExpanded ? 'Collapse' : 'Expand'}</span></button><div class="process-branch-grid" id="processBranchGrid" ${state.branchesExpanded ? '' : 'hidden'}>${nodes.map(node => {
      const incoming = edges.filter(edge => edge.target === node.node_id);
      const outgoing = edges.filter(edge => edge.source === node.node_id);
      const count = evidenceForNode(node.node_id).length;
      return `<button type="button" class="process-branch-node ${esc(node.state || nodeState(node.node_id))}" data-node-id="${esc(node.node_id)}"><span class="branch-node-meta">${esc(node.kind || 'decision')} · ${esc(node.state || 'available')}</span><strong>${esc(node.title)}</strong><p>${esc(node.answer || node.question)}</p><small>Active when: ${esc(node.activation || 'connected path')}</small>${renderContributionAttribution(node.agent_decision_contributions, 'fact')}${evidence && count ? `<span class="node-evidence-count">${count} evidence link${count === 1 ? '' : 's'}</span>` : ''}<span class="branch-edge-summary">${incoming.map(edge => `${edge.source} → ${edgeStateLabel(edge.state)}`).concat(outgoing.map(edge => `${edgeStateLabel(edge.state)} → ${edge.target}`)).map(label => `<i>${esc(label)}</i>`).join('')}</span></button>`;
    }).join('')}</div>` : '<h3 id="processBranchesTitle" class="visually-hidden">Process connections</h3>';
    const edgeLedger = edges.length ? `<details class="process-edge-ledger"><summary>All ${edges.length} graph connections</summary><div>${edges.map(edge => `<button type="button" class="process-edge" data-node-id="${esc(edge.target)}" data-edge-source="${esc(edge.source)}" data-edge-target="${esc(edge.target)}" data-edge-state="${esc(edge.state || '')}"><strong>${esc(edge.source)} → ${esc(edge.target)}</strong><span>${esc(edge.condition || edge.label || edgeStateLabel(edge.state))}</span><small>${esc(edgeStateLabel(edge.state))} · inspect destination decision</small></button>`).join('')}</div></details>` : '';
    return `<section class="process-branches" aria-labelledby="processBranchesTitle">${nodeExplorer}${edgeLedger}</section>`;
  }

  function renderInspector(nodeId, { evidence = false, precedents = false } = {}) {
    const node = nodeById(nodeId) || nodeById(processData()?.current_node);
    if (!node) return '<aside class="decision-inspector"></aside>';
    const facts = factsForNode(node);
    const items = evidenceForNode(node.node_id);
    const laws = legalForNode(node);
    const run = currentRun();
    const previous = run?.result?.precedents || run?.precedents || [];
    return `<aside class="decision-inspector" data-inspector-node="${esc(node.node_id)}" tabindex="-1"><div class="inspector-label"><span>${esc(node.kind === 'outcome' ? 'Outcome' : node.kind === 'action' ? 'Action' : 'Process decision')} · ${esc(node.node_id)}</span><span>${esc(nodeState(node.node_id) === 'current' ? 'Current claim' : '')}</span></div><h3>${esc(node.question)}</h3><p>${esc(node.why || node.answer || '')}</p>
      ${facts.length ? `<section class="inspector-section"><h4>What this decision knows</h4>${facts.map(fact => `<article class="inspector-fact ${fact.state === 'unknown' || fact.state === 'conflicting' ? 'conditional' : ''}" data-fact-id="${esc(fact.fact_id)}" data-node-id="${esc(node.node_id)}"><header><strong>${esc(fact.label)}:</strong> ${esc(fact.value)}</header><p>${esc(fact.explanation)}</p><small>${esc(fact.fact_id)} · ${esc(fact.state || 'unclassified')} · confidence ${formatConfidence(fact.confidence)}</small>${(fact.source_refs || []).length ? `<div class="fact-source-list">${fact.source_refs.map(ref => sourceRefButton(fact, ref, node.node_id)).join('')}</div>` : '<p class="grounding-warning">No source reference returned.</p>'}</article>`).join('')}</section>` : ''}
      ${evidence ? `<section class="inspector-section"><h4>What this decision requires</h4>${items.length ? items.map(item => { const owners = evidenceOwnerIds(item); return `<article class="inspector-row ${item.status === 'missing' ? 'missing' : item.status === 'conditional' || item.status === 'provided_insufficient' ? 'conditional' : ''}" data-item-id="${esc(item.item_id)}" data-node-id="${esc(item.node_id)}" data-node-ids="${esc(owners.join(','))}" data-current-path="${esc(String(item.current_path === true))}" data-fact-id="${esc(item.fact_id)}"><i></i><span><strong>${esc(item.title)} — ${esc(statusLabel(item.status))}</strong><br>${esc(item.why)}<br><small>${esc(item.item_id)} · fact ${esc(item.fact_id)}</small>${evidenceOwnershipMarkup(item, node.node_id)}${renderContributionAttribution(item.agent_contribution, 'item', item.item_id)}${item.applies_when && item.status === 'conditional' ? `<br><em>Only if: ${esc(item.applies_when)}</em>` : ''}${(item.artifact_ids || []).map(artifactId => ` <button class="source-link evidence-artifact-link" type="button" data-source-ref="${esc(artifactId)}" data-fact-id="${esc(item.fact_id)}" data-node-id="${esc(node.node_id)}">Open ${esc(sourceTitle(artifactId))}</button>`).join('')}</span></article>`; }).join('') : '<div class="inspector-row"><i></i><span>No separate evidence requirement is linked to this decision.</span></div>'}</section>` : ''}
      ${laws.length ? `<section class="inspector-section"><h4>Why this step exists</h4>${laws.map(source => { const provenance = legalProvenance(source); return `<button class="law-marker ${provenance.kind}" type="button" data-law-id="${esc(source.source_id)}"><small>${esc(provenance.label)}</small>§ ${esc(source.title)}</button><div class="law-detail" data-law-detail="${esc(source.source_id)}" hidden>${source.url ? officialLegalSourceMarkup(source) : handlingPrincipleMarkup(source)}</div>`; }).join('')}</section>` : ''}
      ${precedents && previous.length ? `<section class="precedent-inline"><header><h4>Generated reference patterns that help</h4><span>${previous.length} returned</span></header>${precedentRankingReceipt(run)}${previous.map((item, index) => `<button class="precedent-mini" type="button" data-precedent-index="${index}"><small>${esc(precedentProvenance(item))}</small><strong>${esc(item.claim_id)} · ${esc(item.title)}</strong><p>${esc(item.why_useful)}</p>${precedentRankingSummary(item)}</button>`).join('')}</section>` : ''}
    </aside>`;
  }

  function bindProcessInteractions() {
    $$('.process-node-button[data-node-id],.process-branch-node[data-node-id],.branch-option[data-node-id],.process-edge[data-node-id]').forEach(button => button.addEventListener('click', () => {
      state.selectedNodeId = button.dataset.nodeId;
      const layout = button.closest('.process-layout');
      if (!layout) return;
      const options = {
        evidence: layout.dataset.evidence === 'true',
        precedents: layout.dataset.precedents === 'true',
        story: Boolean(layout.dataset.processStory),
      };
      layout.outerHTML = renderProcessWorkspace(options);
      bindProcessInteractions();
      announceRender($('#stageCanvas')?.dataset.casepathMoment || state.stageMode);
      requestAnimationFrame(() => $(`.decision-inspector[data-inspector-node="${CSS.escape(state.selectedNodeId)}"]`)?.focus?.());
    }));
    $$('[data-toggle-node-branches]').forEach(button => button.addEventListener('click', () => {
      const expanded = button.getAttribute('aria-expanded') === 'true';
      button.setAttribute('aria-expanded', String(!expanded));
      button.querySelector('strong').textContent = expanded ? 'Reveal outcomes' : 'Hide outcomes';
      button.nextElementSibling.hidden = expanded;
    }));
    $$('[data-toggle-all-branches]').forEach(button => button.addEventListener('click', () => {
      const expanded = button.getAttribute('aria-expanded') === 'true';
      state.branchesExpanded = !expanded;
      button.setAttribute('aria-expanded', String(!expanded));
      button.lastElementChild.textContent = expanded ? 'Expand' : 'Collapse';
      const grid = $(`#${CSS.escape(button.getAttribute('aria-controls'))}`);
      if (grid) grid.hidden = expanded;
    }));
    $$('[data-law-id]').forEach(button => button.addEventListener('click', () => {
      const detail = $(`[data-law-detail="${CSS.escape(button.dataset.lawId)}"]`);
      if (detail) detail.hidden = !detail.hidden;
    }));
    $$('[data-precedent-index]').forEach(button => button.addEventListener('click', () => openPrecedent(Number(button.dataset.precedentIndex))));
    bindSourceLinks();
  }

  function renderVerifyStage(stage, event) {
    const verification = state.run?.result?.verification || state.run?.verification || state.run?.verification_candidate || {};
    const checks = verification.checks || verification.accepted_checks || [];
    const rejected = verification.rejected_proposals || [];
    const candidate = eventState(event).toLowerCase() === 'candidate_prepared';
    const title = candidate ? 'The verification candidate passed its executable checks.' : 'The playbook passed its acceptance checks.';
    const intro = candidate
      ? 'The candidate graph and every process-to-evidence link passed deterministic verification; final acceptance still occurs at the whole-playbook gate.'
      : 'The verifier checks the complete graph and every process-to-evidence link before the result reaches a reviewer.';
    renderCanvas(`<div class="stage-shell">${stageHeader(stage, title, intro)}<div class="process-synthesis"><section class="synthesis-primary"><h3>The process remains the map of the claim.</h3><p>CasePath preserved the supported path, kept unresolved causation open, and blocked responsibility and remedy until competent evidence arrives.</p>${renderProcessWorkspace({ evidence: true, precedents: true })}</section><section><span class="quiet-label">Verification</span><div class="verification-list">${checks.map(check => `<div class="verification-row"><span>✓</span><div>${esc(typeof check === 'string' ? check : check.label || check.name || JSON.stringify(check))}</div></div>`).join('')}${rejected.map(item => `<div class="verification-row rejected"><span>×</span><div>${esc(item.reason || item.title || item)}</div></div>`).join('')}</div></section></div></div>`, 'verify');
    bindProcessInteractions();
  }

  function finishFlagshipRun() {
    if (state.journey !== 'live' || !state.runComplete || state.presenting) return;
    if (!processStoryComplete()) {
      waitForProcessStory().then(status => {
        if (status === 'complete') finishFlagshipRun();
        else renderFailure('The accepted process trace did not complete for this exact run. Nothing was substituted.');
      });
      return;
    }
    state.polling = false;
    state.journey = 'ready';
    state.flagshipRun = state.run;
    setOrchestrator('The handling playbook is ready for a simulated demo review', true);
    renderProgress();
    renderReadyMoment();
  }

  function renderFinalHandoff(result) {
    const run = currentRun();
    const reviewTransform = result?.review_transform
      || result?.audit?.review_transform
      || run?.review_transform
      || run?.result?.review_transform
      || run?.result?.audit?.review_transform;
    if (reviewTransform?.acceptance_scope === 'post_review_unverified_transform') return '';
    const finalBrief = result?.agent_orchestration?.final_claim_brief
      || result?.audit?.agent_orchestration?.final_claim_brief;
    const process = result?.process;
    const entries = validatedContributionEntries(finalBrief?.field_contributions, FINAL_CONTRIBUTION_ROLE);
    const exactFields = entries.length === FINAL_FIELD_CONTRACT.length
      && entries.every((entry, index) => entry.field === FINAL_FIELD_CONTRACT[index][0] && entry.contribution_id === FINAL_FIELD_CONTRACT[index][1]);
    if (!finalBrief || !process || !exactFields) return '';
    const overlay = process.current_overlay || {};
    if (finalBrief.current_node_id !== process.current_node
      || finalBrief.current_node_id !== overlay.current_node_id
      || finalBrief.next_action_node_id !== overlay.next_action_node_id
      || finalBrief.next_action_node_id !== result?.next_action?.process_node_id) return '';
    const nodes = new Map((process.nodes || []).map(node => [node.node_id, node]));
    const current = nodes.get(finalBrief.current_node_id);
    const next = nodes.get(finalBrief.next_action_node_id);
    if (!current || !next) return '';
    const expectedSupportingFacts = [...(current.fact_ids || [])].sort();
    if (JSON.stringify(finalBrief.supporting_fact_ids) !== JSON.stringify(expectedSupportingFacts)
      || JSON.stringify(finalBrief.upstream_contribution_ids) !== JSON.stringify(FINAL_UPSTREAM_CONTRIBUTION_IDS)
      || JSON.stringify(finalBrief.input_contribution_ids) !== JSON.stringify(FINAL_UPSTREAM_CONTRIBUTION_IDS)
      || JSON.stringify(finalBrief.audit_check_ids) !== JSON.stringify(FINAL_AUDIT_CHECK_IDS)) return '';
    const accepted = entries.filter(item => item.deterministic_fallback_applied === false);
    const fallback = entries.filter(item => item.deterministic_fallback_applied === true);
    return `<section class="v20-final-handoff" aria-label="Accepted final claim handoff" data-current-node-id="${esc(finalBrief.current_node_id)}" data-next-action-node-id="${esc(finalBrief.next_action_node_id)}" data-field-count="${entries.length}" data-field-ids="${esc(entries.map(item => item.contribution_id).join(','))}" data-accepted-count="${accepted.length}" data-fallback-count="${fallback.length}" data-accepted-contribution-ids="${esc(accepted.map(item => item.contribution_id).join(','))}" data-fallback-contribution-ids="${esc(fallback.map(item => item.contribution_id).join(','))}">
      <div class="v20-final-handoff-route"><small>Final Claim Brief Agent → Whole-Playbook Gate</small><strong><span>${esc(current.title)}</span><i aria-hidden="true">→</i><span>${esc(next.title)}</span></strong><p>The agent named the live decision and next action; application code checked five independent fields before accepting the handoff.</p></div>
      ${renderContributionAttribution(entries, 'final')}
    </section>`;
  }

  function renderReadyMoment() {
    const result = state.run.result;
    const verification = result.verification || {};
    const accepted = verification.checks || verification.accepted_checks || [];
    const process = result.process || {};
    const current = (process.nodes || []).find(node => node.node_id === process.current_overlay?.current_node_id);
    const next = (process.nodes || []).find(node => node.node_id === process.current_overlay?.next_action_node_id);
    const routeCopy = current && next
      ? `${current.title} is the current decision; ${next.title} is the next action, with the evidence for that handoff attached directly to the graph.`
      : 'The full process, current decision, next action, and supporting evidence remain visible together.';
    renderCanvas(`<div class="stage-shell"><div class="process-synthesis"><section class="synthesis-primary"><span class="quiet-label">Handling playbook ready</span><h3>CasePath has reconstructed how this claim should be handled.</h3><p>${esc(routeCopy)}</p>${renderFinalHandoff(result)}${renderProcessWorkspace({ evidence: true, precedents: true })}</section><section><span class="quiet-label">What was constructed</span><div class="artifact-summary"><div class="artifact-row"><span class="artifact-icon">P</span><div><strong>Handling process</strong><p>From claim intake through responsibility, remedy, escalation, and closure.</p></div><span>Ready</span></div><div class="artifact-row"><span class="artifact-icon">E</span><div><strong>Evidence across the process</strong><p>Every requirement retains the decision, fact, reason, and current status.</p></div><span>Ready</span></div><div class="artifact-row"><span class="artifact-icon">H</span><div><strong>Generated reference patterns that help</strong><p>Returned records retain generated, qualified-review, or unverified-demo provenance.</p></div><span>Ready</span></div></div><span class="quiet-label" style="margin-top:22px">Acceptance checks</span><div class="verification-list">${accepted.slice(0, 5).map(check => `<div class="verification-row"><span>✓</span><div>${esc(typeof check === 'string' ? check : check.label || check.name || JSON.stringify(check))}</div></div>`).join('')}</div></section></div></div>`, 'ready');
    bindProcessInteractions();
    showJourneyActions({ back: false, next: 'Review the proposed playbook' });
  }

  function showJourneyActions({ back = true, next = 'Continue' } = {}) {
    $('#journeyActions').hidden = false;
    $('#journeyBack').hidden = !back;
    $('#journeyNext span').textContent = next;
  }

  function hideJourneyActions() {
    $('#journeyActions').hidden = true;
  }

  function showReview() {
    state.journey = 'review';
    hideJourneyActions();
    setOrchestrator('Simulated demo review: testing one correction', true);
    state.selectedNodeId = 'causation';
    renderCanvas(`<div class="stage-shell"><div class="stage-kicker"><span class="agent-avatar">DR</span><span><strong>Simulated demo review</strong> · unverified reviewer workflow</span></div><h2 class="stage-title">Review the decision that controls the rest of the process.</h2><p class="stage-intro">This generated demo uses an unverified reviewer choice. It shows how one evidence-order correction propagates; it is not qualified expert approval.</p><div class="review-layout"><div class="review-graph">${renderProcessWorkspace({ evidence: true, precedents: false })}</div><form class="review-panel" id="reviewForm"><span class="quiet-label">Proposed demo correction</span><h3>How should broader building testing be sequenced?</h3><p>CasePath proposes one neutral inspection first. Broader building-envelope testing should remain conditional unless the first assessment cannot establish the cause.</p><label class="review-choice"><input type="radio" name="building_envelope_mode" value="conditional" checked><strong>Neutral assessment first</strong><p>Keep building-envelope testing conditional. Add an explicit step to test the ventilation allegation only when competent evidence makes it relevant.</p></label><label class="review-choice"><input type="radio" name="building_envelope_mode" value="required_now"><strong>Request broader testing now</strong><p>Keep the existing immediate building-envelope request.</p></label><div class="review-impact" id="reviewImpact"></div><textarea class="review-note" name="justification" placeholder="Optional simulated-review reason">Keep causation unresolved. Use one neutral inspection first, then test the ventilation allegation or building envelope only when the first assessment supports that branch.</textarea><button class="primary-button review-submit" type="submit"><span>Apply demo correction</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></button></form></div></div>`, 'review');
    bindProcessInteractions();
    renderReviewImpact('conditional');
    $$('input[name="building_envelope_mode"]').forEach(input => input.addEventListener('change', () => renderReviewImpact(input.value)));
    $('#reviewForm').addEventListener('submit', submitReview);
  }

  function renderReviewImpact(mode) {
    const recommended = mode === 'conditional';
    $('#reviewImpact').innerHTML = `<div class="review-impact-row"><small>Process</small><strong>${recommended ? 'Add “Test the ventilation allegation” after the neutral assessment.' : 'No new process decision.'}</strong></div><div class="review-impact-row"><small>Evidence</small><strong>${recommended ? 'Move use evidence to the new decision; building-envelope testing remains conditional.' : 'Broad building-envelope testing remains immediately missing.'}</strong></div><div class="review-impact-row"><small>Next action</small><strong>${recommended ? 'Arrange one competent neutral assessment first.' : 'Request neutral and broader testing together.'}</strong></div>`;
  }

  function snapshot(value) {
    return JSON.parse(JSON.stringify(value || {}));
  }

  async function awaitCompletedRun(runId) {
    return streamRun(runId, false, { present: false });
  }

  async function ensureBaselineLaterRun() {
    if (state.baselineLaterRun?.status === 'complete') return state.baselineLaterRun;
    const created = await api('/api/runs', { method: 'POST', body: JSON.stringify({ claim_id: state.demo.later_claim_id, knowledge_mode: 'baseline' }) });
    state.baselineLaterRun = await awaitCompletedRun(created.run_id);
    return state.baselineLaterRun;
  }

  function computedReviewDelta(beforeResult, afterResult) {
    const beforeNodes = new Map((beforeResult?.process?.nodes || []).map(node => [node.node_id, node]));
    const afterNodes = new Map((afterResult?.process?.nodes || []).map(node => [node.node_id, node]));
    const beforeItems = new Map((beforeResult?.checklist?.items || []).map(item => [item.item_id, item]));
    const afterItems = new Map((afterResult?.checklist?.items || []).map(item => [item.item_id, item]));
    const edgeKey = edge => `${edge.source}\u0000${edge.target}\u0000${edge.branch_id || edge.label || ''}`;
    const beforeEdges = new Map((beforeResult?.process?.edges || []).map(edge => [edgeKey(edge), edge]));
    const afterEdges = new Map((afterResult?.process?.edges || []).map(edge => [edgeKey(edge), edge]));
    const nodesAdded = [...afterNodes.keys()].filter(id => !beforeNodes.has(id));
    const nodesRemoved = [...beforeNodes.keys()].filter(id => !afterNodes.has(id));
    const nodesChanged = [...afterNodes.entries()].filter(([id, node]) => beforeNodes.has(id) && JSON.stringify(beforeNodes.get(id)) !== JSON.stringify(node)).map(([id]) => id);
    const edgesAdded = [...afterEdges.keys()].filter(key => !beforeEdges.has(key));
    const edgesRemoved = [...beforeEdges.keys()].filter(key => !afterEdges.has(key));
    const edgesChanged = [...afterEdges.entries()].filter(([key, edge]) => beforeEdges.has(key) && JSON.stringify(beforeEdges.get(key)) !== JSON.stringify(edge)).map(([key]) => key.replaceAll('\u0000', ' → '));
    const evidenceChanged = [...afterItems.values()].filter(item => {
      const prior = beforeItems.get(item.item_id);
      return !prior || JSON.stringify(prior) !== JSON.stringify(item);
    });
    return { nodesAdded, nodesRemoved, nodesChanged, edgesAdded, edgesRemoved, edgesChanged, evidenceChanged };
  }

  function renderReviewedChecklist(items) {
    return `<details class="reviewed-checklist" open><summary>Server-returned demo-corrected checklist · ${items.length} items</summary><div>${items.map(item => { const owners = evidenceOwnerIds(item); return `<article data-item-id="${esc(item.item_id)}" data-node-id="${esc(item.node_id)}" data-node-ids="${esc(owners.join(','))}" data-current-path="${esc(String(item.current_path === true))}" data-fact-id="${esc(item.fact_id)}"><header><strong>${esc(item.title)}</strong><span>${esc(statusLabel(item.status))}</span></header><p>${esc(item.why)}</p><small>${esc(item.item_id)} · ordered decisions ${esc(owners.join(' → ') || 'not returned')} · current path ${esc(String(item.current_path === true))} · fact ${esc(item.fact_id)}</small></article>`; }).join('')}</div></details>`;
  }

  function showReviewApplied() {
    state.journey = 'review-applied';
    state.stageMode = 'experience';
    const result = state.review?.result || state.run?.result || {};
    if (state.review?.result && state.run) {
      state.run = {
        ...state.run,
        result: snapshot(state.review.result),
        review_transform: snapshot(state.review.review_transform),
        candidate: snapshot(state.review.candidate),
        review_response: snapshot(state.review),
      };
      state.flagshipRun = state.run;
    }
    const delta = computedReviewDelta(state.reviewBefore, result);
    const reviewer = state.review?.reviewer || {};
    renderCanvas(`<div class="stage-shell review-applied"><header class="review-applied-heading"><span class="quiet-label">Server-confirmed simulated-review result</span><h2>The demo-corrected graph and checklist are now visible.</h2><p>This is the result returned after the simulated review—not a preview or qualified approval. The reviewer is recorded as ${esc(reviewer.type || 'type not returned')} with qualification ${esc(reviewer.qualification_status || 'not returned')}. This outcome is unverified, and the model acceptance from the pre-review result is not reused.</p></header><div class="review-applied-delta"><article><small>Process nodes added</small><strong>${delta.nodesAdded.length}</strong><p>${delta.nodesAdded.length ? delta.nodesAdded.map(id => esc(id)).join(', ') : 'None'}</p></article><article><small>Process nodes removed / changed</small><strong>${delta.nodesRemoved.length} / ${delta.nodesChanged.length}</strong><p>${delta.nodesRemoved.concat(delta.nodesChanged).length ? delta.nodesRemoved.concat(delta.nodesChanged).map(id => esc(id)).join(', ') : 'None'}</p></article><article><small>Connections added / removed / changed</small><strong>${delta.edgesAdded.length} / ${delta.edgesRemoved.length} / ${delta.edgesChanged.length}</strong><p>Computed from every returned graph edge.</p></article><article><small>Evidence relationships changed</small><strong>${delta.evidenceChanged.length}</strong><p>${delta.evidenceChanged.length ? delta.evidenceChanged.map(item => esc(item.item_id)).join(', ') : 'None'}</p></article></div><div class="review-applied-layout"><section><h3>Returned demo-corrected process graph</h3>${renderProcessWorkspace({ evidence: true, precedents: false })}</section><section>${renderReviewedChecklist(result.checklist?.items || [])}</section></div></div>`, 'review-applied');
    bindProcessInteractions();
    setOrchestrator('Simulated review saved; inspect the returned graph before demo-memory consolidation', true);
    showJourneyActions({ back: false, next: 'Inspect unverified learning outcome' });
  }

  async function submitReview(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const button = event.currentTarget.querySelector('button[type="submit"]');
    button.disabled = true;
    button.querySelector('span').textContent = 'Capturing a comparison and saving review…';
    try {
      state.reviewBefore = snapshot(state.run?.result);
      state.review = await api(`/api/runs/${encodeURIComponent(state.runId)}/review`, {
        method: 'POST',
        body: JSON.stringify({
          decision: 'approve_with_edit',
          building_envelope_mode: form.get('building_envelope_mode'),
          confidence: .94,
          justification: form.get('justification') || '',
        }),
      });
      state.run = await api(`/api/runs/${encodeURIComponent(state.runId)}`);
      state.flagshipRun = state.run;
      publishRunSnapshot(state.run, { terminal: true });
      showReviewApplied();
      window.dispatchEvent(new CustomEvent('casepath:review-saved', { detail: {
        review: state.review,
        result: state.review?.result || state.run?.result || null,
        moment: 'review-applied',
      } }));
    } catch (error) {
      button.disabled = false;
      button.querySelector('span').textContent = 'Apply demo correction';
      toast(`Could not save review: ${error.message}`);
    }
  }

  async function showKnowledgeConsolidation() {
    state.journey = 'knowledge';
    hideJourneyActions();
    setOrchestrator('Deterministic knowledge governance is deciding what can safely be reused', false);
    const events = (state.run.events || []).filter(event => ['review', 'consolidate'].includes(event.stage));
    renderCanvas(`<div class="stage-shell knowledge-agent"><div class="stage-kicker"><span class="agent-avatar">KG</span><span><strong>Deterministic knowledge governance</strong> · governed organizational learning</span></div><h2 class="stage-title">CasePath is reviewing what the organization can learn.</h2><p class="stage-intro">Unverified demo memory and shared organizational rules have separate gates. Candidate output remains quarantined until qualified support, tests, and approval exist.</p><div class="knowledge-thinking"><div class="orchestrator-mark"><span></span><i></i></div><div><strong id="knowledgeThinkingTitle">Reading the demo review result</strong><p id="knowledgeThinkingDetail">Checking what became unverified demo memory and what remains quarantined.</p></div></div><div id="knowledgeResult"></div></div>`, 'knowledge');
    for (const event of events) {
      $('#knowledgeThinkingTitle').textContent = event.headline || event.label;
      $('#knowledgeThinkingDetail').textContent = event.detail || '';
      await wait(KNOWLEDGE_BEAT_MS);
    }
    renderKnowledgeResult();
  }

  function renderKnowledgeResult() {
    const candidate = state.review?.candidate || null;
    const knowledge = state.review?.knowledge || {};
    const memoryAvailable = state.review?.accepted === true && knowledge.reviewed_memory_available === true && Boolean(state.review?.memory_id);
    const supportReturned = Number.isFinite(Number(candidate?.support_count)) && Number.isFinite(Number(candidate?.required_support));
    const support = supportReturned ? `${Number(candidate.support_count)} of ${Number(candidate.required_support)} unverified demo support records` : 'Unverified support count not returned';
    const qualifiedSupportReturned = Number.isFinite(Number(candidate?.qualified_support_count)) && Number.isFinite(Number(candidate?.required_qualified_support));
    const qualifiedSupport = qualifiedSupportReturned ? `${Number(candidate.qualified_support_count)} of ${Number(candidate.required_qualified_support)} qualified support records` : 'Qualified support count not returned';
    const sharedChanged = candidate?.shared_knowledge_changed === true && knowledge.shared_playbook_version && candidate?.status === 'released';
    const sharedVersion = knowledge.shared_playbook_version || candidate?.base_version || 'Version not returned';
    const targetStatus = candidate?.target_tests?.status || 'not returned';
    const regressionStatus = candidate?.protected_regression?.status || 'not returned';
    const approvalStatus = candidate?.approval?.status || 'not returned';
    $('#knowledgeResult').innerHTML = `<section class="v20-learning-summary" data-learning-status="${esc(candidate?.status || 'not-returned')}"><span>What CasePath learned</span><h2>${memoryAvailable ? 'One unverified demo memory is available for ranking; application eligibility remains separate.' : 'No unverified demo-review memory was confirmed.'}</h2><article class="v20-learning-row" data-outcome="reviewed-memory"><span>${memoryAvailable ? '✓' : '!'}</span><div><small>Unverified demo review memory</small><strong>${memoryAvailable ? 'Saved and available as an explicitly unverified precedent.' : 'Not confirmed by the review response.'}</strong><p>${memoryAvailable ? `Memory ${esc(state.review.memory_id)} preserves the source package, returned graph, checklist, correction, and unverified reviewer status. Saving it does not mean later guidance was used or applied.` : 'CasePath will not claim stored or retrievable memory without a server-returned memory identifier.'}</p></div></article><article class="v20-learning-row quarantined" data-outcome="candidate"><span>Q</span><div><small>Reusable-rule candidate · ${esc(candidate?.status || 'status not returned')}</small><strong>${esc(support)} · ${esc(qualifiedSupport)}.</strong><p>Deterministic target tests: ${esc(targetStatus)} · protected regression: ${esc(regressionStatus)} · qualified approval: ${esc(approvalStatus)}. Passing deterministic checks does not supply the missing qualified support or approval; proposed version ${esc(candidate?.proposed_version || 'not returned')} remains quarantined.</p></div></article><article class="v20-learning-row unchanged" data-outcome="shared-playbook"><span>${sharedChanged ? 'changed' : '—'}</span><div><small>Shared playbook ${sharedChanged ? 'changed' : 'unchanged'}</small><strong>${esc(sharedVersion)} remains the active shared version.</strong><p>${sharedChanged ? 'The server explicitly returned a released shared change.' : 'The simulated correction is case-specific unverified guidance. Even with deterministic target and protected checks passed, no qualified approval or shared-rule release occurred.'}</p></div></article></section>`;
    document.body.dataset.casepathLearningReady = 'true';
    announceRender('knowledge');
    setOrchestrator(memoryAvailable ? 'Unverified demo memory saved; shared-rule candidate quarantined' : 'No demo-review memory was confirmed', true);
    showJourneyActions({ back: false, next: memoryAvailable ? 'Test unverified memory on a new claim' : 'Restart the demo' });
  }

  function dispatchLaterCausalStep(detail) {
    window.dispatchEvent(new CustomEvent('casepath:later-causal-step', { detail: {
      contract: LATER_CAUSAL_STEP_CONTRACT,
      runId: String(state.laterRun?.run_id || ''),
      ...detail,
    } }));
  }

  function waitForLaterCausalStep(eventName, accept) {
    return new Promise((resolve, reject) => {
      let settled = false;
      const finish = (error, detail) => {
        if (settled) return;
        settled = true;
        window.removeEventListener(eventName, onEvent);
        window.clearTimeout(timeout);
        if (error) reject(error);
        else resolve(detail);
      };
      const onEvent = event => {
        const detail = event.detail || {};
        if (accept(detail)) finish(null, detail);
      };
      const timeout = window.setTimeout(() => {
        finish(new Error(`The later-claim ${eventName.replace('casepath:', '')} step did not become visible.`));
      }, LATER_CAUSAL_STEP_TIMEOUT_MS);
      window.addEventListener(eventName, onEvent);
    });
  }

  function waitForTwoPaints() {
    return new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  }

  async function presentLaterCausalStep(detail, { eventName, holdMs, minimumVisibleMs, accept }) {
    const startedAt = performance.now();
    const visible = waitForLaterCausalStep(eventName, accept);
    dispatchLaterCausalStep(detail);
    await visible;
    await waitForTwoPaints();
    await wait(Math.max(minimumVisibleMs, holdMs - (performance.now() - startedAt)));
  }

  async function presentLaterCausalBridge(result) {
    const fact = (result?.facts || []).find(item => item.semantic_role === 'management_ventilation_allegation')
      || (result?.facts || []).find(item => item.fact_id === 'fact_ventilation_allegation');
    const ref = (fact?.source_refs || [])[0];
    if (fact && ref?.artifact_id) {
      const sourceStep = {
        phase: 'source',
        factId: String(fact.fact_id || ''),
        sourceId: String(ref.artifact_id),
        locatorId: sourceLocatorId(ref),
      };
      await presentLaterCausalStep(sourceStep, {
        eventName: 'casepath:later-source-opened',
        holdMs: LATER_CAUSAL_SOURCE_HOLD_MS,
        minimumVisibleMs: reduceMotion ? 900 : 1800,
        accept: detail => detail.contract === LATER_CAUSAL_STEP_CONTRACT
          && detail.runId === String(state.laterRun?.run_id || '')
          && detail.factId === sourceStep.factId
          && detail.sourceId === sourceStep.sourceId
          && detail.locatorId === sourceStep.locatorId
          && Boolean(document.querySelector('[data-later-causal-phase="source"] mark.is-highlighted, [data-later-causal-phase="source"] .ac-visual-region-target.is-highlighted'))
          && ([...document.querySelectorAll('.attachment-row.is-active, .v21-source-summary-toggle.is-active')]
            .some(row => (row.dataset.artifactId || row.dataset.activeSourceId) === sourceStep.sourceId)),
      });
    }
    const receipt = result?.memory_application;
    const memoryOriginId = String(receipt?.source_memory?.memory_id || '');
    const memoryRetrieved = result?.reviewed_memory_retrieved === true
      || result?.knowledge?.reviewed_memory_retrieved === true;
    if (memoryRetrieved
      && receipt?.contract === 'casepath.memory-application-receipt/1.0.0'
      && memoryOriginId) {
      await presentLaterCausalStep({ phase: 'memory', memoryOriginId }, {
        eventName: 'casepath:later-causal-step-visible',
        holdMs: LATER_CAUSAL_MEMORY_HOLD_MS,
        minimumVisibleMs: reduceMotion ? 900 : 1600,
        accept: detail => detail.contract === LATER_CAUSAL_STEP_CONTRACT
          && detail.runId === String(state.laterRun?.run_id || '')
          && detail.phase === 'memory'
          && detail.memoryOriginId === memoryOriginId
          && Boolean(document.querySelector('[data-later-causal-phase="memory"]')),
      });
    }
    const eligibility = receipt?.eligibility || {};
    const eligibilityChecks = eligibility?.checks || {};
    if (memoryRetrieved
      && receipt?.applied === true
      && eligibility?.eligible === true
      && eligibility?.contract === 'casepath.semantic-memory-eligibility/1.0.0'
      && eligibility?.rule_id
      && fact?.semantic_role === 'management_ventilation_allegation'
      && Object.keys(eligibilityChecks).length
      && Object.values(eligibilityChecks).every(value => value === true)) {
      const eligibilityStep = {
        phase: 'eligibility',
        memoryOriginId,
        eligibilityContract: String(eligibility.contract),
        ruleId: String(eligibility.rule_id),
        semanticRole: String(fact?.semantic_role || ''),
      };
      await presentLaterCausalStep(eligibilityStep, {
        eventName: 'casepath:later-causal-step-visible',
        holdMs: LATER_CAUSAL_ELIGIBILITY_HOLD_MS,
        minimumVisibleMs: reduceMotion ? 900 : 1600,
        accept: detail => detail.contract === LATER_CAUSAL_STEP_CONTRACT
          && detail.runId === String(state.laterRun?.run_id || '')
          && detail.phase === 'eligibility'
          && detail.memoryOriginId === memoryOriginId
          && detail.ruleId === eligibilityStep.ruleId
          && Boolean(document.querySelector('[data-later-causal-phase="eligibility"]')),
      });
    }
  }

  async function startLaterClaim() {
    state.journey = 'later';
    hideJourneyActions();
    setOrchestrator('Opening the held-out later demo claim with unverified demo memory available', false);
    try {
      state.laterClaim = await api(`/api/claims/${encodeURIComponent(state.demo.later_claim_id)}`);
      state.claim = state.laterClaim;
      renderClaim(state.claim);
      setOrchestrator('Freezing a no-memory counterfactual for the held-out claim after learning', false);
      await ensureBaselineLaterRun();
      const created = await api('/api/runs', { method: 'POST', body: JSON.stringify({ claim_id: state.demo.later_claim_id, knowledge_mode: 'current' }) });
      state.laterRun = { run_id: created.run_id, events: [], status: 'queued' };
      document.body.dataset.casepathActiveRunId = created.run_id;
      state.laterRunComplete = false;
      state.eventQueue = [];
      state.queuedEventIds.clear();
      const flagshipAudit = state.flagshipRun?.result?.agent_orchestration || state.run?.result?.agent_orchestration || {};
      const flagshipAgents = Array.isArray(flagshipAudit.agents) ? flagshipAudit.agents : [];
      const callBoundSixAgentRun = NEMOTRON_AGENT_IDS.size === 6
        && [...NEMOTRON_AGENT_IDS].every(agentId => flagshipAgents.some(entry => (
          entry?.agent_id === agentId
          && entry?.actor_type === 'nemotron_agent'
          && entry?.call_id
        )));
      const flagshipTruth = callBoundSixAgentRun
        ? 'The earlier result came from six call-bound specialist agents.'
        : 'The earlier result was a reference replay of six specialist roles.';
      renderCanvas(`<div class="stage-shell later-run"><div class="later-source-banner"><div><span class="quiet-label">Later claim · unverified memory</span><h3>${esc(state.laterClaim.subject)}</h3><p>${esc(flagshipTruth)} This comparison makes no new model call.</p></div><span class="new-knowledge">Before → after</span></div><div class="later-agent-stream" id="laterAgentStream"></div><div id="laterResult"></div></div>`, 'later-work');
      dispatchLaterCausalStep({
        phase: 'waiting',
        memoryOriginId: String(state.review?.memory_id || ''),
      });
      renderProgress();
      streamRun(created.run_id, true).catch(() => {});
    } catch (error) {
      console.error('Later-claim comparison setup failed', error);
      renderFailure(error.message);
    }
  }

  function appendLaterEvent(event) {
    if (event.stage === 'orchestrator') {
      setOrchestrator(event.headline || event.label, false);
      return;
    }
    if (event.stage === 'complete') return;
    const stage = STAGES.find(item => item.id === event.stage);
    if (!stage || event.status !== 'completed') return;
    renderProgress(stage.id);
    setOrchestrator(`${event.agent}: ${event.headline}`, false);
    const stream = $('#laterAgentStream');
    if (!stream) return;
    stream.insertAdjacentHTML('beforeend', `<div class="later-agent-row"><span>✓</span><strong>${esc(stage.label)}</strong><p>${esc(event.headline || event.detail || '')}</p></div>`);
    stream.lastElementChild?.scrollIntoView({ block: 'nearest', behavior: reduceMotion ? 'auto' : 'smooth' });
  }

  async function finishLaterRun() {
    if (state.journey !== 'later' || !state.laterRunComplete || state.laterFinishing) return;
    state.laterFinishing = true;
    try {
      const baselineId = state.baselineLaterRun?.run_id;
      const laterId = state.laterRun?.run_id;
      if (!baselineId || !laterId) throw new Error('Both completed comparison run identifiers are required.');
      await presentLaterCausalBridge(state.laterRun.result || {});
      state.proof = await api(`/api/learning-proof?baseline_run_id=${encodeURIComponent(baselineId)}&later_run_id=${encodeURIComponent(laterId)}`);
      window.__casepathLearningProof = state.proof;
      const renderedState = renderLaterResult();
      setOrchestrator(
        renderedState.memoryUsed
          ? 'The held-out later demo claim applied case-specific unverified guidance under a valid receipt; shared playbook stayed unchanged'
          : renderedState.retrievedOnly
            ? 'The held-out later demo claim retrieved and ranked dormant unverified memory; no guidance was applied'
            : renderedState.memoryRetrieved
              ? 'Unverified demo memory was retrieved, but any application claim failed closed'
              : 'No demo memory retrieval or application was confirmed for the held-out later demo claim',
        true,
      );
      renderProgress();
      showJourneyActions({ back: false, next: 'Restart the demo' });
    } catch (error) {
      console.error('Later-claim comparison finalization failed', error);
      renderFailure(error.message);
    }
  }

  function renderLaterResult() {
    const result = state.laterRun.result || {};
    const process = result.process || state.laterRun.process || {};
    const proof = state.proof || {};
    const before = proof.before || {};
    const after = proof.after || {};
    const changes = proof.changes || {};
    const returnedMemoryState = reviewedMemoryState(result);
    const receipt = returnedMemoryState.receipt;
    const receiptProof = proof.memory_application_proof || {};
    const deterministicChecks = proof.deterministic_checks || [];
    const expectedCheckNames = ['Same observable input', 'Same canonical state', 'Exact current memory receipt', 'Pure memory replay matches learned DTOs', 'Receipt before semantic hashes match baseline DTOs', 'Receipt after hashes match learned DTOs', 'Nonzero causal DTO delta', 'Only allowed causal operations changed', 'Deterministic target and protected checks passed', 'Shared v3 remains unchanged'];
    const proofReady = proof.ready === true
      && proof.computed === true
      && proof.causal_delta?.nonzero === true
      && returnedMemoryState.used
      && receipt
      && ['receipt_present', 'receipt_valid', 'source_memory_current', 'before_hashes_match', 'after_hashes_match', 'allowed_delta_exact', 'replay_exact'].every(key => receiptProof[key] === true)
      && receiptProof.application_hash === receipt.application_hash
      && JSON.stringify(deterministicChecks.map(check => check.name)) === JSON.stringify(expectedCheckNames)
      && deterministicChecks.every(check => check.status === 'passed');
    const memoryRetrieved = returnedMemoryState.retrieved;
    const retrievedOnly = returnedMemoryState.retrievedOnly;
    const memoryUsed = returnedMemoryState.used && proof.reviewed_memory_proof?.used === true && Boolean(proofReady);
    const sharedApplied = result.shared_rule_applied === true && proof.shared_rule?.applied === true;
    const beforePrecedents = (before.precedents || []).map(item => item.claim_id);
    const addedPrecedents = changes.precedent_claim_ids_added || [];
    const causalDelta = proof.causal_delta || {};
    const processDelta = causalDelta.process || {};
    const evidenceDelta = causalDelta.evidence || {};
    const addedNodes = processDelta.added_node_ids || changes.process_node_ids_added || [];
    const addedEdges = processDelta.added_edges || [];
    const evidenceChanges = evidenceDelta.changed_item_ids || [];
    const currentNodeId = process.current_overlay?.current_node_id || process.current_node || (process.nodes || []).find(node => node.state === 'current')?.node_id || '';
    if (currentNodeId) state.selectedNodeId = currentNodeId;
    state.stageMode = 'experience';
    const processMarkup = (process.nodes || []).length
      ? `<section class="later-process-result" data-run-id="${esc(state.laterRun.run_id || '')}" data-current-node-id="${esc(currentNodeId)}"><header><small>Returned claim state</small><h3>${esc(result.category || 'Category not returned')}</h3><p>${esc(result.scope || 'Scope not returned')}</p></header>${renderProcessWorkspace({ evidence: true, precedents: true })}</section>`
      : '<section class="later-process-result"><p>Process artifact was not returned for this claim.</p></section>';
    const boundaryHashes = side => ['process_dto_hash', 'checklist_dto_hash', 'process_semantic_hash', 'checklist_semantic_hash'].map(key => `<div data-hash-key="${esc(key)}"><small>${esc(key.replaceAll('_', ' '))}</small><code>${esc(side?.[key] || 'not returned')}</code></div>`).join('');
    const operationRows = receipt ? [...(receipt.process_operations || []), ...(receipt.evidence_operations || [])].map(operation => `<li data-operation-id="${esc(operation.operation_id || '')}"><strong>${esc(operation.operation_id || 'operation not returned')}</strong><span>${esc(operation.operation || '')}${operation.node_id ? ` · node ${esc(operation.node_id)}` : ''}${operation.source ? ` · ${esc(operation.source)} → ${esc(operation.target)}` : ''}${operation.item_id ? ` · item ${esc(operation.item_id)}` : ''}</span></li>`).join('') : '';
    const semanticFact = (result.facts || []).find(fact => fact.semantic_role === 'management_ventilation_allegation');
    const eligibility = receipt?.eligibility || {};
    const receiptMarkup = receipt && memoryUsed ? `<section class="memory-application-receipt" data-memory-contract="${esc(receipt.contract)}" data-memory-authority="${esc(receipt.authority)}" data-memory-scope="${esc(receipt.scope)}" data-application-hash="${esc(receipt.application_hash || '')}" data-model-acceptance-reused="${esc(String(receipt.model_acceptance_reused))}" data-shared-rule-applied="${esc(String(receipt.shared_rule_applied))}" data-memory-application-state="receipt-returned"><header><small>Hash-bound memory application receipt</small><h3>Case-specific unverified guidance only</h3><p>Applied ${esc(String(receipt.applied))} · model acceptance reused ${esc(String(receipt.model_acceptance_reused))} · shared rule applied ${esc(String(receipt.shared_rule_applied))}</p></header><section class="memory-semantic-eligibility" data-eligibility-contract="${esc(eligibility.contract || '')}" data-eligibility-rule-id="${esc(eligibility.rule_id || '')}" data-semantic-signature-hash="${esc(eligibility.semantic_signature_hash || '')}" data-semantic-role="${esc(semanticFact?.semantic_role || '')}"><small>Semantic eligibility — not claim or artifact identity matching</small><strong>${esc(eligibility.contract || 'contract not returned')} · ${esc(eligibility.rule_id || 'rule not returned')}</strong><p>Required fact role <code>${esc(semanticFact?.semantic_role || 'not returned')}</code> is bound to canonical fact <code>${esc(semanticFact?.fact_id || 'not returned')}</code>.</p><code>semantic signature ${esc(eligibility.semantic_signature_hash || 'not returned')}</code><code> · semantic facts ${esc(eligibility.facts_hash || 'not returned')}</code></section><div class="memory-hash-boundary"><section><h4>Before</h4>${boundaryHashes(receipt.before)}</section><section><h4>After</h4>${boundaryHashes(receipt.after)}</section></div><details open><summary>Exact allowed operations</summary><ol class="memory-operation-list">${operationRows}</ol></details><code class="memory-application-hash">application ${esc(receipt.application_hash || 'not returned')}</code></section>` : retrievedOnly ? `<section class="memory-application-receipt retrieved-only" data-memory-application-state="retrieved-not-applied"><header><small>Dormant unverified memory retrieval</small><h3>Retrieved and ranked — not used or applied</h3><p>Generated reference ranking returned memory ${esc(returnedMemoryState.retrievedPrecedent?.memory_id || 'identifier not returned')}, but its guidance is disabled for this review outcome. No application receipt exists and no process or checklist transform is claimed.</p></header></section>` : '<section class="memory-application-receipt incomplete" data-memory-application-state="not-proven"><h3>Current memory application receipt not valid</h3><p>No case-specific transform is claimed.</p></section>';
    const causalMarkup = `<section class="causal-delta" data-causal-nonzero="${esc(String(causalDelta.nonzero === true))}"><header><small>Computed causal delta</small><h3>${causalDelta.nonzero === true ? 'The exact later process and checklist change is visible.' : 'No nonzero causal delta was returned.'}</h3></header><div><article data-delta-kind="nodes"><small>Added process node</small><strong>${esc(addedNodes.join(', ') || 'none')}</strong></article><article data-delta-kind="edges"><small>Added connections</small><strong>${esc(addedEdges.map(edge => `${edge.source} → ${edge.target}`).join(' · ') || 'none')}</strong></article><article data-delta-kind="evidence"><small>Changed evidence items</small><strong>${esc(evidenceChanges.join(', ') || 'none')}</strong></article></div></section>`;
    const checksMarkup = `<section class="memory-deterministic-checks"><header><small>All deterministic checks</small><strong>${deterministicChecks.filter(check => check.status === 'passed').length} of ${deterministicChecks.length} passed</strong></header><div class="verification-list">${deterministicChecks.map(check => `<div class="verification-row ${check.status === 'passed' ? '' : 'rejected'}" data-memory-check="${esc(check.name || '')}" data-check-status="${esc(check.status || '')}"><span>${check.status === 'passed' ? '✓' : '×'}</span><div><strong>${esc(check.name || 'Unnamed check')}</strong><small>${esc(check.detail || '')}</small></div></div>`).join('')}</div></section>`;
    const headerState = memoryUsed
      ? { small: 'Case-specific unverified guidance applied', title: 'The held-out later demo claim visibly changed under a hash-bound unverified memory receipt.', detail: 'The same observable input and canonical state produced a bounded causal DTO delta: one ventilation-dispute node, two edges, and three changed evidence items. This is not qualified review, model acceptance reuse, or a released shared rule.' }
      : retrievedOnly
        ? { small: 'Dormant unverified memory retrieved and ranked — not applied', title: 'The held-out later demo claim retained the unchanged process.', detail: 'The required-now review memory appeared only as an explicitly unverified generated reference pattern. Guidance was disabled, no application receipt exists, and no process or checklist change is claimed.' }
        : memoryRetrieved
          ? { small: 'Memory retrieved; application failed closed', title: 'No memory-driven process change is claimed.', detail: 'A returned unverified memory precedent was visible, but the exact usage flags, receipt, and computed proof did not all agree.' }
          : { small: 'No demo memory retrieved or applied', title: 'The held-out later demo claim stayed on the returned shared process.', detail: 'CasePath found no receipt-bound case-specific transform and claims no memory use.' };
    const afterLabel = memoryUsed ? 'After unverified demo-memory application' : retrievedOnly ? 'After dormant memory retrieval (not applied)' : 'Current held-out later demo run';
    const reuseProofMarkup = renderMemoryReuseProof({ result, proof, memoryUsed, retrievedOnly, memoryState: returnedMemoryState });
    $('#laterResult').innerHTML = `<header class="v20-later-heading" data-memory-retrieved="${memoryRetrieved}" data-memory-used="${memoryUsed}" data-memory-retrieved-only="${retrievedOnly}" data-causal-proof-ready="${Boolean(proofReady)}"><small>${headerState.small}</small><h2>${headerState.title}</h2><p>${headerState.detail}</p></header>${receiptMarkup}${causalMarkup}${processMarkup}<div class="final-proof"><span class="quiet-label">Computed comparison</span><strong>Baseline ${esc(before.result_hash || 'hash not returned')} → after ${esc(after.result_hash || 'hash not returned')}</strong><p>Both sides are completed later-claim runs. Shared rule applied: ${esc(String(sharedApplied))}.</p></div>${reuseProofMarkup}<div class="before-after"><section><h4>Baseline without governed memory application</h4><h3>${esc(before.playbook_version || 'Version not returned')}</h3><ul><li>Run ${esc(before.run_id || 'not returned')}</li><li>Precedents: ${esc(beforePrecedents.join(', ') || 'none returned')}</li><li>Process nodes: ${esc(String((before.process_node_ids || []).length))}</li></ul></section><section><h4>${afterLabel}</h4><h3>${esc(after.playbook_version || 'Version not returned')}</h3><ul><li class="${memoryUsed ? 'reused' : ''}">Run ${esc(after.run_id || 'not returned')}</li><li class="${memoryRetrieved ? 'reused' : ''}">Precedents added: ${esc(addedPrecedents.join(', ') || 'none')}</li><li>Process nodes added: ${esc(addedNodes.join(', ') || 'none')}</li><li>Evidence items changed: ${esc(evidenceChanges.join(', ') || 'none')}</li></ul></section></div>${checksMarkup}<section class="reuse-boundary"><strong>Shared playbook v3 unchanged</strong><p>${esc(proof.shared_rule?.version_after || result.playbook?.version || 'Version not returned')} remains active; candidate status ${esc(proof.shared_rule?.candidate_status || proof.candidate?.status || 'not returned')}. Retrieval or passing deterministic checks does not mean application, qualified approval, or shared v4 release.</p></section>`;
    bindProcessInteractions();
    const normalizedNodeIds = [...new Set((Array.isArray(addedNodes) ? addedNodes : []).map(value => String(value || '')).filter(Boolean))];
    const normalizedEdges = (Array.isArray(addedEdges) ? addedEdges : [])
      .map(edge => ({ source: String(edge?.source || ''), target: String(edge?.target || '') }))
      .filter(edge => edge.source && edge.target);
    const normalizedEvidenceIds = [...new Set((Array.isArray(evidenceChanges) ? evidenceChanges : []).map(value => String(value || '')).filter(Boolean))];
    const applicationHash = String(receipt?.application_hash || '');
    const memoryOriginId = String(receipt?.source_memory?.memory_id || '');
    const sharedPlaybookUnchanged = result.shared_rule_applied === false && proof.shared_rule?.applied === false;
    const validatedMemoryPresentation = Boolean(
      memoryUsed
      && proofReady
      && applicationHash
      && memoryOriginId
      && sharedPlaybookUnchanged
      && normalizedNodeIds.length === 1
      && normalizedEdges.length === 2
      && normalizedEvidenceIds.length === 3
    );
    window.dispatchEvent(new CustomEvent('casepath:later-memory-validation', { detail: {
      contract: 'casepath.later-memory-validation/1.0.0',
      runId: String(state.laterRun.run_id || ''),
      validated: validatedMemoryPresentation,
      proofReady: Boolean(proofReady),
      memoryUsed: Boolean(memoryUsed),
      memoryRetrieved: Boolean(memoryRetrieved),
      retrievedOnly: Boolean(retrievedOnly),
      applicationHash: validatedMemoryPresentation ? applicationHash : '',
      memoryOriginId: validatedMemoryPresentation ? memoryOriginId : '',
      sharedPlaybookUnchanged,
      delta: validatedMemoryPresentation
        ? { nodeIds: normalizedNodeIds, edges: normalizedEdges, evidenceIds: normalizedEvidenceIds }
        : { nodeIds: [], edges: [], evidenceIds: [] },
    } }));
    announceRender('later-result');
    return { proofReady: Boolean(proofReady), memoryRetrieved, memoryUsed, retrievedOnly };
  }

  function restartDemo() {
    const url = new URL(location.href);
    url.searchParams.delete('preserve');
    url.searchParams.set('restart', String(Date.now()));
    location.href = url.toString();
  }

  function terminalFailureReceipts(run) {
    return (run?.events || []).filter(event => (
      event?.status === 'failed'
      && (event?.receipt_type === 'agent_failed' || event?.stage === 'failed')
    ));
  }

  function showTerminalFailure(run, later = false) {
    for (const event of terminalFailureReceipts(run)) rememberPresentedEvent(event);
    state.eventQueue = state.eventQueue.filter(entry => entry.later !== later);
    state.presenting = false;
    renderOrchestrationProof();
    renderFailure(SAFE_MODEL_FAILURE_MESSAGE, run);
  }

  function renderFailure(message, run = null) {
    const failureAgent = FAILURE_AGENT_LABELS[run?.failure_stage] || '';
    const title = failureAgent ? `${failureAgent} stopped before a result was accepted.` : 'No result was accepted.';
    setOrchestrator('CasePath stopped safely', false, 'failed');
    renderCanvas(`<div class="stage-shell" data-terminal-failure="true" data-failure-stage="${esc(NEMOTRON_AGENT_IDS.has(run?.failure_stage) ? run.failure_stage : '')}">${stageHeader({ label: 'Stopped safely', short: '!', job: 'No claim state was changed' }, title, message)}<button class="primary-button" id="retryFailedRun" type="button">Try again</button></div>`, 'failure');
    $('#retryFailedRun')?.addEventListener('click', restartDemo, { once: true });
  }

  function bindSourceLinks(root = document) {
    $$('[data-source-ref]', root).forEach(button => {
      if (button.dataset.bound) return;
      button.dataset.bound = 'true';
      button.addEventListener('click', event => {
        event.stopPropagation();
        const returnedPage = Number(button.dataset.sourcePage);
        let region = null;
        try { region = button.dataset.sourceRegion ? JSON.parse(button.dataset.sourceRegion) : null; } catch (_) {}
        openSource(button.dataset.sourceRef, Number.isInteger(returnedPage) && returnedPage > 0 ? returnedPage : 1, {
          factId: button.dataset.factId || '',
          nodeId: button.dataset.nodeId || '',
          locator_kind: button.dataset.sourceLocatorKind || '',
          excerpt: button.dataset.sourceExcerpt || '',
          region,
          observation: button.dataset.sourceObservation || '',
          field: button.dataset.sourceField || '',
          value: button.dataset.sourceValue || '',
          agent: button.dataset.sourceAgent || '',
          producer: button.dataset.sourceProducer || '',
          authority: button.dataset.sourceAuthority || '',
          annotation_contract: button.dataset.annotationContract || '',
          annotation_version: button.dataset.annotationVersion || '',
          image_sha256: button.dataset.imageSha256 || '',
          confidence: button.dataset.factConfidence || '',
          state: button.dataset.factState || '',
        });
      });
    });
  }

  function findArtifact(artifactId) {
    return (state.claim?.artifacts || []).find(item => item.artifact_id === artifactId)
      || (state.flagshipClaim?.artifacts || []).find(item => item.artifact_id === artifactId)
      || (state.laterClaim?.artifacts || []).find(item => item.artifact_id === artifactId)
      || null;
  }

  async function openSource(artifactId, page = 1, context = null) {
    if (artifactId === 'message') return openMessageSource(page, context);
    if (artifactId === 'intake') return openIntakeSource(context);
    const artifact = findArtifact(artifactId);
    if (!artifact) {
      toast('That source is not in the current claim package.');
      return;
    }
    const returnFocus = $('#sourceViewer').open ? state.viewer.returnFocus : document.activeElement;
    const exactTextQuery = context?.locator_kind === 'text_quote' ? String(context.excerpt || '').trim() : '';
    state.viewer = { artifact, extraction: null, page: Math.max(1, page), zoom: 1, tab: exactTextQuery ? 'extraction' : 'original', context, searchMatches: [], query: exactTextQuery, returnFocus };
    $('#sourceViewerKind').textContent = 'Original attachment';
    $('#sourceViewerTitle').textContent = artifact.title;
    $('#sourceViewerMeta').textContent = `${artifact.filename} · ${mimeLabel(artifact)} · received ${formatDate(artifact.received_at)}`;
    $('#openOriginal').href = artifactUrl(artifact.artifact_id);
    $('#openOriginal').hidden = false;
    $('#openOriginal').removeAttribute('aria-disabled');
    $('#sourceSearch').value = exactTextQuery;
    $('#sourceSearchStatus').textContent = '';
    $('#sourceSearchResults').innerHTML = '';
    renderGalleryControls();
    if (!$('#sourceViewer').open) $('#sourceViewer').showModal();
    $('#closeSourceViewer').focus();
    setSourceTab(exactTextQuery ? 'extraction' : 'original');
    renderSourceEvidence(artifact.artifact_id);
  }

  function openMessageSource(_page = 1, context = null) {
    const claim = state.claim || state.flagshipClaim;
    if (!claim) {
      toast('Claim sources are still loading.');
      return;
    }
    const returnFocus = $('#sourceViewer').open ? state.viewer.returnFocus : document.activeElement;
    state.viewer = { artifact: { artifact_id: 'message', title: 'Customer message', filename: 'customer-message', media_type: 'message/rfc822', page_count: 1 }, extraction: null, page: 1, zoom: 1, tab: 'original', context, searchMatches: [], query: '', returnFocus };
    $('#sourceViewerKind').textContent = 'Original customer message';
    $('#sourceViewerTitle').textContent = claim.subject;
    $('#sourceViewerMeta').textContent = `${claim.customer?.name || 'Customer'} · received ${formatDate(claim.received_at)}`;
    $('#openOriginal').removeAttribute('href');
    $('#openOriginal').hidden = true;
    $('#openOriginal').setAttribute('aria-disabled', 'true');
    $('#sourceSearch').value = '';
    $('#sourceSearchStatus').textContent = '';
    $('#sourceSearchResults').innerHTML = '';
    renderGalleryControls();
    if (!$('#sourceViewer').open) $('#sourceViewer').showModal();
    $('#closeSourceViewer').focus();
    setSourceTab('original');
    renderSourceEvidence('message');
  }

  function intakePayload() {
    const claim = state.claim || state.flagshipClaim || {};
    return {
      claim_id: claim.claim_id || '',
      subject: claim.subject || '',
      received_at: claim.received_at || '',
      customer_name: claim.customer?.name || '',
      customer_address: claim.customer?.address || '',
      policy_reference: claim.customer?.policy || '',
    };
  }

  function openIntakeSource(context = null) {
    const returnFocus = $('#sourceViewer').open ? state.viewer.returnFocus : document.activeElement;
    state.viewer = { artifact: { artifact_id: 'intake', title: 'Intake metadata', filename: 'observed-intake-fields', media_type: 'application/casepath-intake+json', page_count: 1 }, extraction: null, page: 1, zoom: 1, tab: 'original', context, searchMatches: [], query: '', returnFocus };
    $('#sourceViewerKind').textContent = 'Observed intake metadata';
    $('#sourceViewerTitle').textContent = 'Intake metadata';
    $('#sourceViewerMeta').textContent = 'Fields received with the current claim submission';
    $('#openOriginal').removeAttribute('href');
    $('#openOriginal').hidden = true;
    $('#openOriginal').setAttribute('aria-disabled', 'true');
    $('#sourceSearch').value = '';
    $('#sourceSearchStatus').textContent = '';
    $('#sourceSearchResults').innerHTML = '';
    renderGalleryControls();
    if (!$('#sourceViewer').open) $('#sourceViewer').showModal();
    $('#closeSourceViewer').focus();
    setSourceTab('original');
    renderSourceEvidence('intake');
  }

  function imageArtifacts() {
    return (state.claim?.artifacts || []).filter(artifact => artifact.media_type?.startsWith('image/'));
  }

  function renderGalleryControls() {
    const gallery = imageArtifacts();
    const index = gallery.findIndex(artifact => artifact.artifact_id === state.viewer.artifact?.artifact_id);
    const nav = $('#sourceGalleryNav');
    const useful = index >= 0 && gallery.length > 1;
    nav.hidden = !useful;
    if (!useful) return;
    $('#sourcePosition').textContent = `Image ${index + 1} of ${gallery.length}`;
    $('#sourcePrevious').disabled = index === 0;
    $('#sourceNext').disabled = index === gallery.length - 1;
    nav.dataset.galleryIndex = String(index);
  }

  function moveImage(offset) {
    const gallery = imageArtifacts();
    const index = gallery.findIndex(artifact => artifact.artifact_id === state.viewer.artifact?.artifact_id);
    const target = gallery[index + offset];
    if (target) openSource(target.artifact_id, 1, null);
  }

  function renderImageSource(artifact, zoom) {
    const context = state.viewer.context || {};
    const region = context.locator_kind === 'visual_observation' ? normalizedRegion(context) : null;
    const curated = region && validVisualAnnotation(context) && context.image_sha256 === artifact.sha256;
    const highlight = region ? `<span class="visual-region-highlight" role="img" aria-label="${curated ? 'Curated generated-demo reference annotation' : 'Unverified visual annotation'} region: ${esc(context.observation || 'observation not returned')}" data-highlight-region="${esc(JSON.stringify(region))}" ${visualAnnotationAttributes(context)} data-artifact-sha256="${esc(artifact.sha256 || '')}" style="left:${region[0] * 100}%;top:${region[1] * 100}%;width:${region[2] * 100}%;height:${region[3] * 100}%"><span>${curated ? 'Curated demo annotation' : 'Unverified annotation'}</span></span>` : '';
    return `<figure class="source-image-frame" style="transform:scale(${zoom})"><img id="sourceImage" src="${artifactUrl(artifact.artifact_id)}" alt="${esc(artifact.title)}">${highlight}</figure>`;
  }

  async function renderSourceViewer() {
    const { artifact, page, zoom, tab } = state.viewer;
    if (!artifact) return;
    $('#sourceViewer').setAttribute('aria-busy', 'true');
    $('#sourceStage').setAttribute('aria-busy', 'true');
    $('#zoomValue').textContent = `${Math.round(zoom * 100)}%`;
    $('#sourceSearchForm').hidden = artifact.media_type?.startsWith('image/');
    try {
      if (tab === 'extraction') {
        await renderExtraction();
      } else {
        $('#pageThumbnails').hidden = artifact.media_type !== 'application/pdf';
        if (artifact.media_type === 'application/pdf') {
          $('#pageThumbnails').innerHTML = Array.from({ length: artifact.page_count || 1 }, (_, index) => `<button class="page-thumb" type="button" data-page="${index + 1}" aria-current="${index + 1 === page ? 'page' : 'false'}"><img src="${pageUrl(artifact.artifact_id, index + 1)}" alt="Page ${index + 1}"><span>${index + 1}</span></button>`).join('');
          $('#sourceStage').innerHTML = `<img id="documentPage" src="${pageUrl(artifact.artifact_id, page)}" alt="${esc(artifact.title)}, page ${page}" style="transform:scale(${zoom})">`;
          $$('.page-thumb', $('#sourceViewer')).forEach(button => button.addEventListener('click', () => {
            state.viewer.page = Number(button.dataset.page);
            renderSourceViewer();
          }));
        } else if (artifact.media_type?.startsWith('image/')) {
          $('#pageThumbnails').hidden = true;
          $('#sourceStage').innerHTML = renderImageSource(artifact, zoom);
        } else if (artifact.artifact_id === 'message') {
          $('#pageThumbnails').hidden = true;
          const claim = state.claim || state.flagshipClaim;
          $('#sourceStage').innerHTML = `<article class="email-document" style="transform:scale(${zoom})"><dl><dt>From</dt><dd>${esc(claim.customer?.name || 'Customer')}</dd><dt>To</dt><dd>Legal protection claims</dd><dt>Received</dt><dd>${esc(formatDate(claim.received_at))}</dd><dt>Subject</dt><dd>${esc(claim.subject)}</dd></dl><pre>${esc(claim.message)}</pre></article>`;
        } else if (artifact.artifact_id === 'intake') {
          $('#pageThumbnails').hidden = true;
          const intake = intakePayload();
          $('#sourceStage').innerHTML = `<article class="email-document intake-document" style="transform:scale(${zoom})"><dl>${Object.entries(intake).map(([key, value]) => `<dt>${esc(key.replaceAll('_', ' '))}</dt><dd>${esc(value)}</dd>`).join('')}</dl></article>`;
        } else {
          $('#pageThumbnails').hidden = true;
          if (!state.viewer.extraction) state.viewer.extraction = await api(`/api/artifacts/${encodeURIComponent(artifact.artifact_id)}/extraction`);
          const email = state.viewer.extraction.email || {};
          $('#sourceStage').innerHTML = `<article class="email-document" style="transform:scale(${zoom})"><dl><dt>From</dt><dd>${esc(email.from || '')}</dd><dt>To</dt><dd>${esc(email.to || '')}</dd><dt>Date</dt><dd>${esc(email.date || '')}</dd><dt>Subject</dt><dd>${esc(email.subject || artifact.title)}</dd></dl><pre>${esc(email.body || '')}</pre></article>`;
        }
      }
    } catch (error) {
      $('#sourceStage').innerHTML = `<p role="alert">${esc(error.message)}</p>`;
    } finally {
      $('#sourceStage').setAttribute('aria-busy', 'false');
      $('#sourceViewer').setAttribute('aria-busy', 'false');
    }
  }

  function highlightedText(value, query) {
    if (!query) return esc(value);
    const safe = String(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return String(value).split(new RegExp(`(${safe})`, 'ig')).map(part => part.toLowerCase() === query.toLowerCase() ? `<mark>${esc(part)}</mark>` : esc(part)).join('');
  }

  async function renderExtraction() {
    const artifact = state.viewer.artifact;
    $('#pageThumbnails').hidden = true;
    if (artifact.artifact_id === 'message') {
      const claim = state.claim || state.flagshipClaim;
      $('#sourceStage').innerHTML = `<div class="extraction-pages"><div class="extraction-page" data-extraction-page="1"><h3>Machine-visible customer message</h3><pre>${highlightedText(claim.message, state.viewer.query)}</pre></div></div>`;
      return;
    }
    if (artifact.artifact_id === 'intake') {
      $('#sourceStage').innerHTML = `<div class="extraction-pages"><div class="extraction-page" data-extraction-page="1"><h3>Observed intake fields</h3><pre>${highlightedText(JSON.stringify(intakePayload(), null, 2), state.viewer.query)}</pre></div></div>`;
      return;
    }
    try {
      if (!state.viewer.extraction) state.viewer.extraction = await api(`/api/artifacts/${encodeURIComponent(artifact.artifact_id)}/extraction`);
      const extraction = state.viewer.extraction;
      if (extraction.pages) {
        $('#sourceStage').innerHTML = `<div class="extraction-pages">${extraction.pages.map((text, index) => `<div class="extraction-page" data-extraction-page="${index + 1}"><h3>Page ${index + 1}</h3><pre>${highlightedText(text || 'No text extracted.', state.viewer.query)}</pre></div>`).join('')}</div>`;
      } else if (extraction.email) {
        $('#sourceStage').innerHTML = `<div class="extraction-pages"><div class="extraction-page" data-extraction-page="1"><h3>Structured email fields</h3><pre>${highlightedText(JSON.stringify(extraction.email, null, 2), state.viewer.query)}</pre></div></div>`;
      } else {
        $('#sourceStage').innerHTML = `<div class="extraction-pages"><div class="extraction-page"><h3>Curated generated-demo image reference</h3><pre>${esc(extraction.image_note || 'Original pixels and metadata preserved; no machine extraction is claimed.')}</pre></div></div>`;
      }
    } catch (error) {
      $('#sourceStage').innerHTML = `<p>${esc(error.message)}</p>`;
    }
  }

  async function searchExtractedSource(event) {
    event.preventDefault();
    const query = $('#sourceSearch').value.trim();
    state.viewer.query = query;
    state.viewer.searchMatches = [];
    $('#sourceSearchResults').innerHTML = '';
    if (!query) {
      $('#sourceSearchStatus').textContent = 'Enter text to search this source.';
      return;
    }
    const artifact = state.viewer.artifact;
    let pages = [];
    try {
      if (artifact.artifact_id === 'message') {
        pages = [(state.claim || state.flagshipClaim)?.message || ''];
      } else if (artifact.artifact_id === 'intake') {
        pages = [JSON.stringify(intakePayload(), null, 2)];
      } else {
        if (!state.viewer.extraction) state.viewer.extraction = await api(`/api/artifacts/${encodeURIComponent(artifact.artifact_id)}/extraction`);
        if (state.viewer.extraction.pages) pages = state.viewer.extraction.pages;
        else if (state.viewer.extraction.email) pages = [JSON.stringify(state.viewer.extraction.email, null, 2)];
      }
      pages.forEach((text, index) => {
        const haystack = String(text || '');
        const position = haystack.toLowerCase().indexOf(query.toLowerCase());
        if (position < 0) return;
        const start = Math.max(0, position - 65);
        const end = Math.min(haystack.length, position + query.length + 85);
        state.viewer.searchMatches.push({ page: index + 1, excerpt: haystack.slice(start, end).replace(/\s+/g, ' ').trim() });
      });
      $('#sourceSearchStatus').textContent = `${state.viewer.searchMatches.length} page${state.viewer.searchMatches.length === 1 ? '' : 's'} matched “${query}”.`;
      $('#sourceSearchResults').innerHTML = state.viewer.searchMatches.map(match => `<button type="button" data-search-page="${match.page}"><strong>Page ${match.page}</strong><span>${highlightedText(match.excerpt, query)}</span></button>`).join('');
      setSourceTab('extraction');
    } catch (error) {
      $('#sourceSearchStatus').textContent = `Search unavailable: ${error.message}`;
    }
  }

  function renderSourceEvidence(artifactId) {
    const facts = (currentRun()?.result?.facts || currentRun()?.understanding?.facts || []).filter(fact => (fact.source_refs || []).some(ref => ref.artifact_id === artifactId));
    const context = state.viewer.context;
    const openedFrom = context?.factId ? `<section class="opened-grounding" data-fact-id="${esc(context.factId)}" data-node-id="${esc(context.nodeId || '')}" data-source-agent="${esc(context.agent || '')}" data-source-producer="${esc(context.producer || '')}" data-source-authority="${esc(context.authority || '')}" data-fact-confidence="${esc(context.confidence ?? '')}" data-fact-state="${esc(context.state || '')}"><small>Opened from fact ${esc(context.factId)}</small>${sourceLocatorMarkup(context, 'opened-locator')}<p>confidence ${formatConfidence(context.confidence)} · ${esc(context.state || 'state not returned')}</p></section>` : '';
    const selectedFact = context?.factId ? facts.find(fact => fact.fact_id === context.factId) : null;
    const visibleFacts = selectedFact ? [selectedFact] : facts;
    $('#sourceEvidence').innerHTML = `${openedFrom}<h3>Used in the path</h3><p>${facts.length ? `${facts.length} linked decision${facts.length === 1 ? '' : 's'} · open one to return to the graph.` : 'No process decision uses this source yet.'}</p>${visibleFacts.length ? visibleFacts.map(fact => {
      const refs = (fact.source_refs || []).filter(ref => ref.artifact_id === artifactId);
      const node = owningNodeForFact(fact.fact_id);
      const exactRefs = selectedFact ? refs.map(ref => sourceLocatorMarkup(ref, 'source-passage')).join('') : '';
      return `<article class="source-fact${selectedFact ? ' is-selected-fact' : ' is-compact-fact'}" data-fact-id="${esc(fact.fact_id)}" data-node-id="${esc(node?.node_id || '')}"><strong>${esc(fact.label)}</strong><small>${esc(fact.value)} · ${esc(fact.state || 'unclassified')}</small>${exactRefs}${node ? `<button type="button" class="route-to-decision" data-source-fact-node="${esc(node.node_id)}">${selectedFact ? 'Return to decision' : 'Open decision'} · ${esc(node.title)}</button>` : '<p class="grounding-warning">No owning process decision returned.</p>'}</article>`;
    }).join('') : '<article class="source-fact"><p>No current claim fact points to this source yet.</p></article>'}`;
  }

  function setSourceTab(tab, focus = false) {
    state.viewer.tab = tab;
    $$('[data-source-tab]').forEach(button => {
      const selected = button.dataset.sourceTab === tab;
      button.setAttribute('aria-selected', String(selected));
      button.tabIndex = selected ? 0 : -1;
      if (selected) $('#sourceStage').setAttribute('aria-labelledby', button.id);
      if (selected && focus) button.focus();
    });
    renderSourceViewer();
  }

  function focusOwningDecision(nodeId) {
    closeSourceViewer({ restoreFocus: false });
    state.selectedNodeId = nodeId;
    const target = $(`.process-node-button[data-node-id="${CSS.escape(nodeId)}"],.process-branch-node[data-node-id="${CSS.escape(nodeId)}"]`, $('#stageCanvas'));
    if (!target) {
      toast('The owning decision will be selected when the process graph is visible.');
      return;
    }
    target.click();
    requestAnimationFrame(() => {
      const refreshed = $(`.process-node-button[data-node-id="${CSS.escape(nodeId)}"],.process-branch-node[data-node-id="${CSS.escape(nodeId)}"]`, $('#stageCanvas'));
      refreshed?.focus();
    });
  }

  function closeSourceViewer({ restoreFocus = true } = {}) {
    const returnFocus = state.viewer.returnFocus;
    if ($('#sourceViewer').open) $('#sourceViewer').close();
    if (restoreFocus) requestAnimationFrame(() => {
      if (returnFocus?.isConnected) returnFocus.focus();
    });
  }

  function openPrecedent(index) {
    const run = currentRun();
    const precedent = (run?.precedents || run?.result?.precedents || [])[index];
    if (!precedent) return;
    $('#precedentViewerKind').textContent = precedentProvenance(precedent);
    $('#precedentTitle').textContent = `${precedent.claim_id} · ${precedent.title}`;
    $('#precedentContent').innerHTML = `<p class="precedent-provenance">${esc(precedentProvenance(precedent))}</p><p class="precedent-summary">${esc(precedent.why_useful)}</p>${precedentRankingSummary(precedent)}${precedentRankingReceipt(run)}<div class="precedent-grid"><section><h3>Relevant branch</h3><p>${esc((precedent.final_process || []).join(' → '))}</p></section><section><h3>Evidence that mattered</h3><ul>${(precedent.evidence || []).map(item => `<li>${esc(typeof item === 'string' ? item : item.title || JSON.stringify(item))}</li>`).join('')}</ul></section><section><h3>Returned review state</h3><p>${esc(precedent.review_status || 'Not returned')}</p></section><section><h3>Outcome</h3><p>${esc(precedent.outcome || 'Outcome not returned')}</p></section></div>`;
    $('#precedentViewer').showModal();
  }

  async function openAuditDrawer() {
    let run = currentRun();
    if (!run?.run_id && state.runId) run = await api(`/api/runs/${encodeURIComponent(state.runId)}`);
    if (!run) return;
    if (run.run_id) {
      try {
        run = await api(`/api/runs/${encodeURIComponent(run.run_id)}`);
        if (state.journey === 'later') state.laterRun = run; else state.run = run;
      } catch (_) {}
    }
    const eventMarkup = (run.events || []).map(event => {
      const kind = eventKind(event);
      const isModelEvent = kind === 'nemotron_agent' || kind === 'legacy_model_event';
      const field = (label, value) => value ? `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>` : '';
      const actorType = returnedValue(event, 'actor_type');
      const inputs = Array.isArray(event.input_artifacts) ? event.input_artifacts.join(', ') : returnedValue(event, 'input_artifact');
      const outputs = eventArtifacts(event).join(', ');
      return `<details class="audit-event" ${event.stage === state.activeStage ? 'open' : ''} data-actor-type="${esc(kind)}" data-call-id="${esc(returnedValue(event, 'call_id'))}" data-delegation-id="${esc(returnedValue(event, 'delegation_id'))}"><summary><span></span><div><strong>${esc(event.label)}</strong><span>${esc(event.headline || '')}</span></div><span>${esc(event.status || '')}</span></summary><div class="audit-event-body"><p>${esc(event.detail || '')}</p><dl class="audit-grid">${field('Actor contract', actorType || `Not returned — ${actorKindLabel(kind)}`)}${field('Returned actor', returnedActorName(event))}${field('Implementation', returnedValue(event, 'implementation'))}${isModelEvent ? field('Requested model', returnedValue(event, 'requested_model', 'model')) : ''}${isModelEvent ? field('Response model', returnedValue(event, 'response_model')) : ''}${field('Call ID', returnedValue(event, 'call_id'))}${field('Delegation ID', returnedValue(event, 'delegation_id'))}${field('Cache origin call', returnedValue(event, 'cache_origin_call_id', 'origin_call_id'))}${field('Prompt version', returnedValue(event, 'prompt_version'))}${field('Validator', returnedValue(event, 'gate_id', 'validator'))}${field('Input artifact', inputs)}${field('Input hash', returnedValue(event, 'input_artifact_hash', 'input_hash'))}${field('Output artifact', outputs)}${field('Output hash', returnedValue(event, 'output_artifact_hash', 'output_hash', 'artifact_hash'))}${field('Handoff from', returnedValue(event, 'handoff_from'))}${field('Handoff to', returnedValue(event, 'handoff_to'))}</dl></div></details>`;
    }).join('');
    const auditContent = $('#auditContent');
    const proof = $('#orchestrationProof');
    const eventList = document.createElement('section');
    eventList.className = 'audit-event-list';
    eventList.innerHTML = eventMarkup;
    auditContent.replaceChildren();
    if (proof) {
      proof.classList.add('v21-audit-proof');
      auditContent.append(proof);
    }
    auditContent.append(eventList);
    $('#auditDrawer').showModal();
  }

  function bindGlobalInteractions() {
    $('#runCasePath').addEventListener('click', startFlagshipRun);
    $('#toggleSource').addEventListener('click', () => openSource('message', 1));
    $('#attachmentList').addEventListener('click', event => {
      const row = event.target.closest('[data-artifact-id]');
      if (row) openSource(row.dataset.artifactId, 1);
    });
    $('#journeyNext').addEventListener('click', () => {
      if (state.journey === 'ready') showReview();
      else if (state.journey === 'review-applied') showKnowledgeConsolidation();
      else if (state.journey === 'knowledge') {
        const memoryAvailable = state.review?.accepted === true && state.review?.knowledge?.reviewed_memory_available === true && Boolean(state.review?.memory_id);
        if (memoryAvailable) startLaterClaim(); else restartDemo();
      }
      else if (state.journey === 'later' && state.laterRunComplete) restartDemo();
    });
    $('#journeyBack').addEventListener('click', () => {
      if (state.journey === 'review') {
        state.journey = 'ready';
        renderReadyMoment();
      }
    });
    $('#openAudit').addEventListener('click', openAuditDrawer);
    $('#closeAudit').addEventListener('click', () => $('#auditDrawer').close());
    $('#closeSourceViewer').addEventListener('click', () => closeSourceViewer());
    $('#closePrecedent').addEventListener('click', () => $('#precedentViewer').close());
    $$('[data-source-tab]').forEach(button => button.addEventListener('click', () => setSourceTab(button.dataset.sourceTab)));
    $('.source-viewer-tabs').addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const tabs = $$('[data-source-tab]');
      const current = tabs.indexOf(document.activeElement);
      const target = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      setSourceTab(tabs[target].dataset.sourceTab, true);
    });
    $('#sourceSearchForm').addEventListener('submit', searchExtractedSource);
    $('#sourceSearchResults').addEventListener('click', event => {
      const button = event.target.closest('[data-search-page]');
      if (!button) return;
      state.viewer.page = Number(button.dataset.searchPage);
      setSourceTab('extraction');
      requestAnimationFrame(() => $(`[data-extraction-page="${state.viewer.page}"]`)?.scrollIntoView({ block: 'start' }));
    });
    $('#sourcePrevious').addEventListener('click', () => moveImage(-1));
    $('#sourceNext').addEventListener('click', () => moveImage(1));
    $('#sourceEvidence').addEventListener('click', event => {
      const button = event.target.closest('[data-source-fact-node]');
      if (button) focusOwningDecision(button.dataset.sourceFactNode);
    });
    document.addEventListener('casepath:open-source', event => {
      const detail = event.detail || {};
      if (!detail.artifactId) return;
      openSource(detail.artifactId, Number(detail.page) || 1, detail.context || null);
    });
    document.addEventListener('casepath:open-precedent', event => {
      const index = Number(event.detail?.index);
      if (Number.isInteger(index) && index >= 0) openPrecedent(index);
    });
    document.addEventListener('casepath:begin-review', () => {
      if (state.journey === 'ready') showReview();
    });
    document.addEventListener('casepath:submit-review', event => {
      if (state.journey === 'ready') showReview();
      const form = $('#reviewForm');
      if (!form) return;
      const mode = event.detail?.buildingEnvelopeMode || 'conditional';
      const input = $(`input[name="building_envelope_mode"][value="${CSS.escape(mode)}"]`, form);
      if (input) input.checked = true;
      const note = $('textarea[name="justification"]', form);
      if (note && typeof event.detail?.justification === 'string') note.value = event.detail.justification;
      form.requestSubmit();
    });
    document.addEventListener('casepath:continue-journey', () => {
      if (!$('#journeyNext').hidden && !$('#journeyNext').disabled) $('#journeyNext').click();
    });
    $('#zoomIn').addEventListener('click', () => { state.viewer.zoom = Math.min(2, state.viewer.zoom + .15); renderSourceViewer(); });
    $('#zoomOut').addEventListener('click', () => { state.viewer.zoom = Math.max(.55, state.viewer.zoom - .15); renderSourceViewer(); });
    [$('#sourceViewer'), $('#auditDrawer'), $('#precedentViewer')].forEach(dialog => dialog.addEventListener('click', event => {
      if (event.target !== dialog) return;
      if (dialog === $('#sourceViewer')) closeSourceViewer();
      else dialog.close();
    }));
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') {
        if ($('#sourceViewer').open) closeSourceViewer();
        [$('#auditDrawer'), $('#precedentViewer')].forEach(dialog => { if (dialog.open) dialog.close(); });
      }
    });
    bindSourceLinks();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
