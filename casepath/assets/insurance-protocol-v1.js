(() => {
  'use strict';

  if (document.documentElement.dataset.claimsWorkspace === 'true') return;

  const params = new URLSearchParams(location.search);
  const LEGACY_MODE = params.get('journey') === 'legacy-v20';
  // The product is one same-origin application. A URL parameter, global, or
  // stale hosted default must never move evidence or authority to another API.
  const API = location.origin.replace(/\/$/, '');
  const SESSION_KEY = 'casepath:demo-session';
  const LOOP_KEY = 'casepath:insurance-loop-id';
  const PENDING_KEY = 'casepath:insurance-pending-key';
  const DRAFT_KEY = 'casepath:insurance-evidence-draft';
  const CORRECTION_KEY = 'casepath:insurance-correction-key';
  const CORRECTION_PREVIEW_KEY = 'casepath:insurance-correction-preview';
  const ACTION_COUNT_KEY = 'casepath:insurance-deliberate-actions';
  const ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/;
  const PARTIAL_STATUSES = new Set(['intent_journaled', 'execution_started', 'receipt_recorded', 'source_observed', 'assertion_normalized', 'interpreted', 'replan_receipt_pending']);
  const restoredActionCount = Number(sessionStorage.getItem(ACTION_COUNT_KEY));
  const view = { active: false, busy: false, step: 'proposal', loopId: null, proposal: null, protocol: null, state: null, correctionOptions: null, correctionSelection: null, correctionPreview: null, deliberateActions: Number.isInteger(restoredActionCount) && restoredActionCount >= 0 ? restoredActionCount : 0 };

  const byId = id => document.getElementById(id);
  const escapeHtml = value => String(value ?? '').replace(/[&<>"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[character]));
  const key = prefix => `${prefix}-${crypto.randomUUID?.() || Date.now().toString(36)}`;

  function storedJson(name) {
    try { return JSON.parse(sessionStorage.getItem(name) || 'null'); } catch (_) { return null; }
  }

  async function sha256Text(value) {
    const bytes = new TextEncoder().encode(value);
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('');
  }

  function sessionId() {
    const existing = sessionStorage.getItem(SESSION_KEY);
    if (existing && ID_PATTERN.test(existing)) return existing;
    const created = key('ui');
    sessionStorage.setItem(SESSION_KEY, created);
    return created;
  }

  async function request(path, { method = 'GET', body, idempotencyKey } = {}) {
    const headers = { Accept: 'application/json', 'X-CasePath-Session': sessionId() };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (idempotencyKey) headers['X-CasePath-Idempotency-Key'] = idempotencyKey;
    const response = await fetch(`${API}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    const value = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
    if (!response.ok) {
      const error = new Error(typeof value.detail === 'string' ? value.detail : JSON.stringify(value.detail));
      error.status = response.status;
      error.payload = value;
      throw error;
    }
    return value;
  }

  function recordAction() {
    view.deliberateActions += 1;
    sessionStorage.setItem(ACTION_COUNT_KEY, String(view.deliberateActions));
    document.body.dataset.insuranceActionCount = String(view.deliberateActions);
  }

  function focusCanvas() {
    requestAnimationFrame(() => byId('artifactCanvas')?.focus({ preventScroll: true }));
  }

  function canvas() {
    let root = byId('artifactCanvas');
    if (!root) {
      root = document.createElement('section');
      root.id = 'artifactCanvas';
      root.className = 'insurance-protocol-panel';
      byId('liveWorkspace').append(root);
    }
    root.classList.add('insurance-protocol-panel');
    root.setAttribute('tabindex', '-1');
    return root;
  }

  function hashes(values) {
    return `<dl class="insurance-protocol-hashes">${values.filter(([, value]) => value).map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`).join('')}</dl>`;
  }

  function setAction(label, disabled = false) {
    const button = byId('journeyNext');
    byId('journeyActions').hidden = false;
    button.hidden = false;
    button.disabled = disabled;
    button.setAttribute('aria-disabled', String(disabled));
    button.querySelector('span').textContent = label;
  }

  function renderProposal() {
    const proposal = view.proposal;
    const scope = proposal.pace_scope || {};
    const earlier = Array.isArray(scope.earlier_mandatory_obligation_ids) ? scope.earlier_mandatory_obligation_ids.join(', ') : '';
    canvas().innerHTML = `<header><span class="insurance-protocol-kicker">Verified evidence request</span><h2>Add a neutral technical assessment</h2><p>CasePath has certified that this source can resolve the current causation slice. ClaimLoop remains the claim-wide authority and may surface an earlier mandatory item after replanning.</p></header><article class="insurance-protocol-card"><span class="insurance-protocol-status">Deterministic reference worker · zero model calls</span><h3>What the source may do</h3><ul><li>Address only the active technical-assessment obligation.</li><li>Enter server-owned quarantine before it can affect the claim.</li><li>Register through <code>source.register@1</code>; the browser cannot declare it sufficient.</li>${earlier ? `<li>Earlier unresolved mandatory item remains: <code>${escapeHtml(earlier)}</code>.</li>` : ''}</ul><details class="insurance-protocol-proof"><summary>Show proposal proof</summary>${hashes([['State', proposal.state_sha256], ['PACE proposal', proposal.proposal_sha256], ['PACE certificate', proposal.proposal?.pace_result?.certificate?.certificate_sha256], ['PACE scope', scope.scope_sha256]])}</details></article>`;
    setAction('Provide assessment');
    focusCanvas();
  }

  function renderSelected() {
    const storedDraft = storedJson(DRAFT_KEY) || {};
    const draft = storedDraft.proposal_sha256 === view.proposal.proposal_sha256 ? storedDraft : {};
    if (storedDraft.proposal_sha256 && draft !== storedDraft) sessionStorage.removeItem(DRAFT_KEY);
    const inputContract = view.proposal.evidence_input_contract || {};
    const allowedFindings = Array.isArray(inputContract.finding_values) ? inputContract.finding_values.join(', ') : 'server-bound catalog only';
    const skeleton = JSON.stringify({ schema: inputContract.schema || 'casepath.synthetic-neutral-assessment/1.0.0', document_kind: inputContract.document_kind || 'neutral_assessment', evidence_item_id: inputContract.evidence_item_id || 'technical_assessment', finding: '<allowed finding>', basis: '<source-grounded basis>' });
    canvas().innerHTML = `<header><span class="insurance-protocol-kicker">Source intake</span><h2>Provide synthetic assessment evidence</h2><p>Choose a UTF-8 text file or paste its text. The server—not this form—owns the artifact hash, admission decision, observation, and interpretation.</p></header><article class="insurance-protocol-card"><div class="insurance-protocol-inputs"><label><span>Text file</span><input id="protocolEvidenceFile" type="file" accept=".txt,text/plain"></label><span class="insurance-protocol-or">or paste text</span><label><span>Source filename</span><input id="protocolEvidenceFilename" type="text" maxlength="200" autocomplete="off" value="${escapeHtml(draft.filename || '')}" placeholder="assessment.txt" required></label><label><span>Assessment document</span><textarea id="protocolEvidenceContent" maxlength="100000" rows="9" placeholder="${escapeHtml(skeleton)}" required>${escapeHtml(draft.content || '')}</textarea></label><p class="insurance-protocol-note"><strong>Allowed findings:</strong> ${escapeHtml(allowedFindings)}. The server decides what each admitted finding means for sufficiency.</p><p class="insurance-protocol-note" id="protocolEvidenceStatus" role="status">Only the closed typed JSON document admitted as <code>text/plain; charset=utf-8</code> is accepted. Empty, oversized, stale, or hash-mismatched input fails closed.</p></div><details class="insurance-protocol-proof"><summary>Show bound proposal and input contract</summary>${hashes([['Proposal', view.proposal.proposal_sha256], ['Case state', view.proposal.state_sha256], ['Input contract', inputContract.input_contract_sha256], ['Template', inputContract.template_sha256]])}</details></article>`;
    const filename = byId('protocolEvidenceFilename');
    const content = byId('protocolEvidenceContent');
    const persist = () => sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ proposal_sha256: view.proposal.proposal_sha256, filename: filename.value, content: content.value }));
    filename.addEventListener('input', persist);
    content.addEventListener('input', persist);
    byId('protocolEvidenceFile').addEventListener('change', async event => {
      const file = event.target.files?.[0];
      if (!file) return;
      if (file.size > 100000) {
        byId('protocolEvidenceStatus').textContent = 'The selected file exceeds the 100,000-byte limit.';
        return;
      }
      let decoded;
      try {
        decoded = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
      } catch (_) {
        filename.value = '';
        content.value = '';
        persist();
        refresh();
        byId('protocolEvidenceStatus').textContent = 'The selected file is not valid UTF-8 and was not admitted.';
        return;
      }
      filename.value = file.name;
      content.value = decoded;
      persist();
      refresh();
      byId('protocolEvidenceStatus').textContent = `${file.name} loaded locally; no bytes have been admitted yet.`;
    });
    view.step = 'selected';
    setAction('Register and replan', !(draft.filename && draft.content));
    const refresh = () => setAction('Register and replan', !(filename.value.trim() && content.value.trim()));
    filename.addEventListener('input', refresh);
    content.addEventListener('input', refresh);
    refresh();
    focusCanvas();
  }

  function correctionRequestBody(candidate) {
    return {
      candidate_sha256: candidate.candidate_sha256,
      target_assertion_sha256: candidate.target_assertion_sha256,
      target_interpretation_sha256: candidate.target_interpretation_sha256,
      semantic_delta_id: candidate.semantic_delta_id,
      expected_revision: candidate.revision,
    };
  }

  function semanticSummary(value) {
    if (!value) return 'Unavailable';
    const normalized = value.normalized_value == null ? 'none' : value.normalized_value;
    return `${value.fact_state} · ${normalized} · ${value.evidence_status}`;
  }

  function renderCorrectionSelection(options) {
    const candidates = Array.isArray(options?.candidates) ? options.candidates : [];
    if (candidates.length !== 1 || options.state_sha256 !== view.protocol?.base_state_sha256) {
      throw new Error('No exact case-local correction choice is available for this journal state.');
    }
    const candidate = candidates[0];
    view.correctionOptions = options;
    view.correctionSelection = null;
    view.step = 'correction-select';
    const operation = candidate.operation === 'rollback_scoped_correction' ? 'Rollback correction' : 'Correct admitted interpretation';
    canvas().innerHTML = `<header><span class="insurance-protocol-kicker">${escapeHtml(operation)} · choose before preview</span><h2>Select the exact assertion and semantic change</h2><p>The server enumerated this option from the admitted source and current journal. You choose the target and intended delta; the browser still cannot invent a fact, scope, or authority.</p></header><article class="insurance-protocol-card"><fieldset class="insurance-protocol-correction-choice"><legend>Admitted assertion / interpretation</legend><label><input id="protocolCorrectionChoice" type="radio" name="protocolCorrectionChoice" value="${escapeHtml(candidate.candidate_sha256)}"><span><strong>${escapeHtml(candidate.target_fact_id)} · ${escapeHtml(candidate.target_evidence_item_id)}</strong><br>${escapeHtml(candidate.semantic_delta_label)}</span></label></fieldset><dl class="insurance-protocol-diff"><dt>Current semantics</dt><dd>${escapeHtml(semanticSummary(candidate.current_semantics))}</dd><dt>Proposed semantics</dt><dd>${escapeHtml(semanticSummary(candidate.proposed_semantics))}</dd><dt>Current value</dt><dd>${escapeHtml(candidate.current_semantics?.value)}</dd><dt>Proposed value</dt><dd>${escapeHtml(candidate.proposed_semantics?.value)}</dd></dl><details class="insurance-protocol-proof"><summary>Show selected authority lineage</summary>${hashes([['Candidate', candidate.candidate_sha256], ['Assertion', candidate.target_assertion_sha256], ['Interpretation', candidate.target_interpretation_sha256], ['Source observation', candidate.source_observation_sha256], ['Journal state', candidate.state_sha256]])}</details><div class="insurance-protocol-secondary-actions"><button class="secondary-button" id="protocolCorrectionCancel" type="button">Cancel</button></div></article>`;
    const choice = byId('protocolCorrectionChoice');
    choice.addEventListener('change', () => {
      view.correctionSelection = candidate;
      setAction(candidate.operation === 'rollback_scoped_correction' ? 'Preview rollback' : 'Preview semantic correction');
    });
    setAction('Select a correction first', true);
    focusCanvas();
  }

  function renderCorrectionPreview(prepared) {
    const preview = prepared?.preview || {};
    if (!view.protocol
      || preview.parent_state_sha256 !== view.protocol.base_state_sha256
      || preview.unrelated_facts_before_sha256 !== preview.unrelated_facts_after_sha256
      || !/^[0-9a-f]{64}$/.test(prepared?.correction_sha256 || '')) {
      throw new Error('The correction preview is stale or fails its locality commitment.');
    }
    view.correctionPreview = prepared;
    view.step = 'correction-preview';
    const effect = prepared.effect || {};
    const scope = prepared.scope || {};
    const isRollback = preview.operation === 'rollback_scoped_correction';
    canvas().innerHTML = `<header><span class="insurance-protocol-kicker">${isRollback ? 'Rollback' : 'Correction'} preview · not yet applied</span><h2>Review the exact case-local change</h2><p>Confirming changes only the named fact and evidence item. The unrelated-fact commitment must remain identical.</p></header><article class="insurance-protocol-card"><span class="insurance-protocol-status">Awaiting explicit confirmation</span><h3>${escapeHtml(effect.fact_id)} · ${escapeHtml(effect.evidence_item_id)}</h3><dl class="insurance-protocol-diff"><dt>Before semantics</dt><dd>${escapeHtml(semanticSummary(preview.before_semantics))}</dd><dt>After semantics</dt><dd>${escapeHtml(semanticSummary(preview.expected_after_semantics))}</dd><dt>Before value</dt><dd>${escapeHtml(preview.before_semantics?.value)}</dd><dt>After value</dt><dd>${escapeHtml(preview.expected_after_semantics?.value)}</dd><dt>Claim scope</dt><dd>${escapeHtml((scope.claim_ids || []).join(', '))}</dd><dt>Fact scope</dt><dd>${escapeHtml((scope.fact_ids || []).join(', '))}</dd><dt>Evidence scope</dt><dd>${escapeHtml((scope.evidence_item_ids || []).join(', '))}</dd></dl><p class="insurance-protocol-note">Unrelated objects: ${preview.unrelated_facts_before_sha256 === preview.unrelated_facts_after_sha256 ? 'unchanged' : 'INVALID'}. The rollback identity binds the exact prior fact and evidence objects.</p><details class="insurance-protocol-proof"><summary>Show before, after, and rollback hashes</summary>${hashes([['Correction', prepared.correction_sha256], ['Authority receipt', preview.correction_artifact_receipt_sha256], ['Parent state', preview.parent_state_sha256], ['Before fact', preview.before_fact_sha256], ['Expected fact', preview.expected_after_fact_sha256], ['Before evidence', preview.before_evidence_sha256], ['Expected evidence', preview.expected_after_evidence_sha256], ['Unrelated before', preview.unrelated_facts_before_sha256], ['Unrelated after', preview.unrelated_facts_after_sha256], ['Rollback fact', preview.rollback_fact_sha256], ['Rollback evidence', preview.rollback_evidence_sha256]])}</details><div class="insurance-protocol-secondary-actions"><button class="secondary-button" id="protocolCorrectionCancel" type="button">Cancel preview</button></div></article>`;
    setAction(isRollback ? 'Confirm rollback' : 'Confirm scoped correction');
    focusCanvas();
  }

  function evidencePassages(state, factId, thin) {
    const fact = Array.isArray(state?.facts) ? state.facts.find(value => value.fact_id === factId) : null;
    const factPassages = Array.isArray(fact?.source_refs)
      ? fact.source_refs.filter(value => typeof value?.excerpt === 'string' && value.excerpt.trim()).slice(0, 3).map(value => ({ label: fact.label || fact.fact_id, text: value.excerpt, source: value }))
      : [];
    if (factPassages.length >= 2) return factPassages;
    const observation = thin?.normalized_assertion?.claim_observation;
    const raw = observation?.value;
    const source = observation?.source_refs?.[0];
    if (!raw || !source || observation.fact_id !== factId) return factPassages;
    let parsed;
    try { parsed = JSON.parse(raw); } catch (_) { return [{ label: 'Admitted source', text: raw, source }]; }
    const admitted = [
      ['Finding', parsed.finding],
      ['Technical basis', parsed.basis],
      ['Document type', parsed.document_kind],
    ].filter(([, text]) => typeof text === 'string' && text.trim()).map(([label, text]) => ({ label, text, source }));
    return [...factPassages, ...admitted].slice(0, 3);
  }

  function workEventMarkup(state) {
    const graph = state?.six_agent_graph_audit || {};
    const agents = Array.isArray(graph.agents) ? graph.agents : [];
    const gates = Array.isArray(graph.deterministic_gates) ? graph.deterministic_gates : [];
    if (agents.length !== 6 || gates.length !== 3) return '';
    const artifacts = graph.specialist_artifacts || {};
    const unique = values => [...new Set(values.filter(value => typeof value === 'string' && value))].sort();
    const nestedRefs = values => unique(values.flatMap(value => Array.isArray(value?.source_ref_ids) ? value.source_ref_ids : []));
    const roleRefs = agentId => {
      if (agentId === 'canonical_facts') return [];
      if (agentId === 'orchestrator_plan') return unique(artifacts.orchestrator_plan?.focus_source_ref_ids || []);
      if (agentId === 'document_source_integrity') return nestedRefs(artifacts.document_source_integrity?.artifacts || []);
      if (agentId === 'process_decision_mapping') return nestedRefs(artifacts.process_decision_mapping?.decisions || []);
      if (agentId === 'evidence_checklist') return nestedRefs(artifacts.evidence_checklist?.items || []);
      if (agentId === 'final_claim_brief_audit') return unique(artifacts.final_claim_brief_audit?.source_ref_ids || graph.final_claim_brief?.source_ref_ids || []);
      return [];
    };
    const roleNames = {
      canonical_facts: 'Canonical facts',
      orchestrator_plan: 'Bounded work plan',
      document_source_integrity: 'Document and source integrity',
      process_decision_mapping: 'Process decision mapping',
      evidence_checklist: 'Evidence checklist',
      final_claim_brief_audit: 'Final claim brief audit',
    };
    const rows = agents.map(agent => {
      const sourceRefs = roleRefs(agent.agent_id);
      const terminal = agent.outcome || agent.finish_reason || 'completed';
      return `<li class="insurance-protocol-work-event"><h4>${escapeHtml(roleNames[agent.agent_id] || agent.agent_id)}</h4><p><strong>Worker:</strong> Deterministic reference worker — no model call</p><dl><dt>Actual input artifact</dt><dd>${escapeHtml(agent.input_artifact_hash)}</dd><dt>Actual typed output</dt><dd>${escapeHtml(agent.output_artifact || agent.agent_id)} · ${escapeHtml(agent.output_artifact_hash)}</dd><dt>Source references</dt><dd>${escapeHtml(sourceRefs.length ? sourceRefs.join(', ') : 'None accepted by this role')}</dd><dt>Gate result</dt><dd>Role-local gate not separately emitted · exact cycle acceptance 3/3 passed below</dd><dt>Duration</dt><dd>Not separately measured in the persisted receipt</dd><dt>Terminal status</dt><dd>${escapeHtml(terminal)}</dd></dl></li>`;
    }).join('');
    const gateRows = gates.map(gate => `<li><strong>${escapeHtml(gate.role || gate.agent_id)}:</strong> ${escapeHtml(gate.outcome)} · ${escapeHtml(gate.input_artifact_hash)} → ${escapeHtml(gate.output_artifact_hash)}</li>`).join('');
    return `<section class="insurance-protocol-work"><h3>Recorded work</h3><p>These are persisted work receipts from this exact replan, not animated agents.</p><ol>${rows}</ol><h4>Deterministic acceptance gates</h4><ul>${gateRows}</ul></section>`;
  }

  function assertProtocolState(protocol, state) {
    if (!state
      || protocol.loop_id !== state.loop_id
      || protocol.base_revision !== state.revision
      || protocol.base_state_sha256 !== state.state_sha256
      || protocol.last_event_sha256 !== state.last_event_sha256) {
      throw new Error('Protocol and claim state do not name one authoritative journal prefix. Reload before rendering.');
    }
  }

  function renderProtocol(protocol, state = view.state) {
    assertProtocolState(protocol, state);
    view.protocol = protocol;
    view.state = state || view.state;
    const records = protocol.record_set || {};
    const receipt = records.action_receipt || {};
    const thin = protocol.thin_waist_record_set || {};
    const next = protocol.next_action;
    const status = protocol.protocol_status;
    const unknown = status === 'dispatch_unknown';
    const partial = PARTIAL_STATUSES.has(status);
    const cancelled = status === 'cancelled';
    const terminal = Boolean(protocol.terminal_mode);
    const correction = protocol.latest_correction;
    const copy = unknown
      ? ['Reconciliation required', 'The effect is unknown—CasePath will not retry it', 'Reconciliation inspects the same persisted intent and effect key before any transition.']
      : partial
        ? ['Durable registration in progress', 'Resume the exact journaled lineage', 'The next request reuses the original idempotency key; it does not create a second action or effect.']
        : cancelled
          ? ['No-effect terminal', 'The registration intent was cancelled safely', 'No evidence was accepted and no replanning claim is made.']
          : terminal
            ? ['Decision packet ready', protocol.terminal_mode === 'abstain' ? 'CasePath abstained safely' : 'CasePath reached a decision-ready state', 'The terminal disposition is bound to the current journal and provenance state.']
            : ['Registration accepted and replanned', next?.title || 'No further bounded action is currently exposed', 'The admitted observation passed source, process, evidence, and readiness checks before this state was accepted.'];
    const correctionControls = status === 'replanned' && protocol.correction_count < 2
      ? `<div class="insurance-protocol-secondary-actions"><button class="secondary-button" id="protocolCorrection" type="button">${protocol.correction_count === 0 ? 'Correct an assertion' : 'Roll back this correction'}</button>${protocol.decision_ready_packet_sha256 ? '<button class="secondary-button" id="protocolPacket" type="button">View decision packet</button>' : '<span class="insurance-protocol-note">The displayed evidence action remains authoritative; no terminal packet exists yet.</span>'}</div>`
      : protocol.decision_ready_packet_sha256
        ? '<div class="insurance-protocol-secondary-actions"><button class="secondary-button" id="protocolPacket" type="button">View decision packet</button></div>'
        : '';
    const correctionEffect = Array.isArray(state?.corrections) ? state.corrections.at(-1)?.effect : null;
    const correctionCard = correction ? `<article class="insurance-protocol-card" data-correction-receipt="${escapeHtml(correction.delta_sha256)}"><span class="insurance-protocol-status">${protocol.correction_count === 1 ? 'Scoped correction applied' : 'Correction rolled back'}</span><h3>${escapeHtml(correction.fact_id)} · ${escapeHtml(correction.evidence_item_id)}</h3><dl class="insurance-protocol-diff"><dt>Resulting fact state</dt><dd>${escapeHtml(correctionEffect?.fact_state)}</dd><dt>Resulting value</dt><dd>${escapeHtml(correctionEffect?.normalized_value ?? 'unresolved')}</dd><dt>Resulting evidence status</dt><dd>${escapeHtml(correctionEffect?.evidence_status)}</dd><dt>Affected objects</dt><dd>${escapeHtml(correction.fact_id)}, ${escapeHtml(correction.evidence_item_id)}</dd><dt>Unaffected objects</dt><dd>All other facts · digest unchanged</dd></dl><p>Reload reconstructs this semantic delta from the journal. The rollback identity is the exact before-fact and before-evidence pair below.</p><details class="insurance-protocol-proof"><summary>Technical receipt</summary>${hashes([['Correction', correction.correction_sha256], ['Application event', correction.event_sha256], ['Before fact / rollback', correction.before_fact_sha256], ['After fact', correction.after_fact_sha256], ['Before evidence / rollback', correction.before_evidence_sha256], ['After evidence', correction.after_evidence_sha256], ['Unrelated before', correction.unrelated_facts_before_sha256], ['Unrelated after', correction.unrelated_facts_after_sha256], ['Delta receipt', correction.delta_sha256]])}</details></article>` : '';
    const unresolved = Array.isArray(state?.obligations)
      ? state.obligations.filter(item => ['active', 'conditional', 'contradicted', 'blocked'].includes(item.status) && item.mandatory_now === true)
      : [];
    const controlling = unresolved.find(item => item.obligation_id === next?.evidence_item_id) || unresolved[0];
    const why = unresolved.length
      ? `${controlling?.obligation_id || 'A current obligation'} remains ${controlling?.status || 'open'} because ${controlling?.fact_id || next?.fact_id || 'a controlling fact'} is not decision-ready. ${unresolved.length} current mandatory obligation${unresolved.length === 1 ? '' : 's'} remain, so CasePath exposes one bounded evidence action instead of claiming readiness.`
      : terminal
        ? 'All terminal conditions and deterministic provenance gates passed.'
        : 'The accepted graph produced a bounded continued state; no terminal disposition is inferred by the browser.';
    const evidenceItems = Array.isArray(state?.checklist?.items) ? state.checklist.items : [];
    const statusOrder = ['provided_sufficient', 'provided_insufficient', 'missing', 'conditional', 'not_applicable', 'unknown'];
    const evidenceGroups = statusOrder.map(value => {
      const items = evidenceItems.filter(item => item.status === value);
      return items.length ? `<li><strong>${escapeHtml(value.replaceAll('_', ' '))}:</strong> ${items.map(item => escapeHtml(item.title || item.item_id)).join('; ')}</li>` : '';
    }).join('');
    const passages = evidencePassages(state, controlling?.fact_id || next?.fact_id, thin);
    const passageMarkup = passages.length
      ? `<blockquote class="insurance-protocol-passages">${passages.map(item => `<p><strong>${escapeHtml(item.label)}:</strong> “${escapeHtml(item.text)}” <span>page ${escapeHtml(item.source.page)} · exact admitted source</span></p>`).join('')}</blockquote>`
      : '<p>No admitted source passage is available for this state.</p>';
    const currentStateLabel = unknown
      ? 'Reconciliation required'
      : partial
        ? 'Registration in progress'
        : cancelled
          ? 'Cancelled · no evidence effect'
          : terminal
            ? protocol.terminal_mode
            : status === 'replanned'
              ? 'Certified continued state'
              : 'Fail-closed state';
    const overlay = state?.process?.current_overlay || {};
    const observed = thin.normalized_assertion;
    const changedFact = correctionEffect
      ? `${correctionEffect.fact_id} is now ${correctionEffect.fact_state}${correctionEffect.normalized_value ? ` (${correctionEffect.normalized_value})` : ''}.`
      : observed
        ? `${observed.fact_id} changed from unresolved to ${observed.fact_state} (${observed.normalized_value || 'no normalized value'}).`
        : 'No accepted fact changed.';
    const affectedEvidenceId = correctionEffect?.evidence_item_id || observed?.evidence_item_id;
    const affectedObligation = Array.isArray(state?.obligations)
      ? state.obligations.find(item => item.obligation_id === affectedEvidenceId)
      : null;
    const changedObligation = affectedObligation
      ? `${affectedObligation.obligation_id} is now ${affectedObligation.status} with evidence ${affectedObligation.evidence_status}.`
      : 'No admitted observation changed an obligation.';
    const affectedNodes = Array.isArray(state?.process?.nodes) && Array.isArray(affectedObligation?.process_node_ids)
      ? state.process.nodes.filter(node => affectedObligation.process_node_ids.includes(node.node_id)).map(node => `${node.title} (${node.state})`)
      : [];
    const changedBranch = affectedNodes.length
      ? `Affected process objects: ${affectedNodes.join('; ')}.`
      : 'No process branch change is claimed.';
    const actionTitle = next?.title || (terminal ? 'No further evidence action is required.' : 'No safe bounded action is currently available.');
    const controllingNodes = Array.isArray(state?.process?.nodes) && Array.isArray(controlling?.process_node_ids)
      ? state.process.nodes.filter(node => controlling.process_node_ids.includes(node.node_id))
      : [];
    const impacted = controllingNodes.flatMap(node => [node.title, ...(Array.isArray(node.branches) ? node.branches.map(branch => branch.label) : [])]);
    const nextDetail = next
      ? `<p><strong>${escapeHtml(actionTitle)}</strong></p><ul><li>Resolves: ${escapeHtml(next.fact_id)} through ${escapeHtml(next.evidence_item_id)}.</li><li>Affected decisions and branches: ${escapeHtml(impacted.length ? impacted.join('; ') : 'the named controlling obligation only')}.</li><li>Burden: one bounded evidence submission. Delay: external evidence time only; CasePath performs no hidden wait.</li><li>Safety: no claim state changes unless server-owned admission and all deterministic checks pass.</li></ul>`
      : `<p>${escapeHtml(actionTitle)}</p>`;
    const requestOutcome = terminal ? `Terminal packet ${protocol.terminal_mode}` : next ? `Selected one bounded request: ${actionTitle}` : 'No request selected; safe stop retained';
    canvas().innerHTML = `<header><span class="insurance-protocol-kicker">${escapeHtml(copy[0])}</span><h2>${escapeHtml(copy[1])}</h2><p>${escapeHtml(copy[2])}</p></header><article class="insurance-protocol-card ${(unknown || cancelled) ? 'insurance-protocol-error' : ''}"><span class="insurance-protocol-status">${escapeHtml(status)}</span><section class="insurance-protocol-outcome"><h3>Current state</h3><p><strong>${escapeHtml(currentStateLabel)}</strong> · unresolved decision: ${escapeHtml(overlay.current_node_id || controlling?.fact_id || 'none')}</p><h3>Why</h3><p>${escapeHtml(why)}</p>${passageMarkup}<h3>Next action</h3>${nextDetail}<h3>Evidence</h3><ul class="insurance-protocol-evidence-roster">${evidenceGroups || '<li>No evidence roster is available.</li>'}</ul><h3>What changed</h3><ul><li>${escapeHtml(changedFact)}</li><li>${escapeHtml(changedObligation)}</li><li>${escapeHtml(changedBranch)}</li><li>New blocker: ${escapeHtml(controlling ? `${controlling.obligation_id} · ${controlling.status}` : 'none')}.</li><li>Request outcome: ${escapeHtml(requestOutcome)}.</li></ul></section><details class="insurance-protocol-proof"><summary>Technical receipt</summary>${hashes([['Versioned state', protocol.projection_sha256], ['Journal state', protocol.base_state_sha256], ['V1 intent', records.intent?.intent_sha256], ['Registry receipt', receipt.receipt_sha256], ['Source observation', records.source_observation?.observation_sha256], ['V2 assertion', thin.normalized_assertion?.assertion_sha256], ['V2 interpretation', thin.interpretation?.interpretation_sha256], ['V2 proposal', thin.decision_proposal?.proposal_sha256], ['V2 decision', thin.decision_record?.decision_sha256], ['V2 replan intent', thin.action_intent?.intent_sha256], ['V2 replan receipt', thin.action_receipt?.receipt_sha256], ['Decision packet', protocol.decision_ready_packet_sha256]])}</details>${correctionControls}</article>${correctionCard}${workEventMarkup(state)}`;
    view.step = unknown ? 'unknown' : partial ? 'resume' : terminal ? 'packet' : 'result';
    setAction(
      unknown ? 'Reconcile same intent'
        : partial ? 'Resume exact registration'
          : terminal ? 'View decision packet'
            : next ? `Next action certified: ${next.title}`
              : 'Safe stop — no bounded action available',
      !unknown && !partial && !terminal,
    );
    focusCanvas();
  }

  function renderError(error) {
    const transportUnconfirmed = !Number.isInteger(error?.status);
    const title = transportUnconfirmed
      ? 'Outcome unconfirmed—reconcile from the journal'
      : 'The action was rejected safely';
    const detail = transportUnconfirmed
      ? 'The response was interrupted. CasePath will reuse the exact idempotency key and inspect the durable journal before taking another action.'
      : error.message;
    canvas().innerHTML = `<article class="insurance-protocol-card insurance-protocol-error" role="alert"><span class="insurance-protocol-status">Stopped safely</span><h2>${escapeHtml(title)}</h2><p>${escapeHtml(detail)}</p></article>`;
    view.step = view.loopId ? 'hydrate' : 'bootstrap';
    setAction(view.loopId ? 'Resume from journal' : 'Retry exact start');
    focusCanvas();
  }

  async function hydrate() {
    if (!view.loopId) return start();
    const [protocol, state] = await Promise.all([
      request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/protocol-state`),
      request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}`),
    ]);
    assertProtocolState(protocol, state);
    view.state = state;
    view.protocol = protocol;
    if (protocol.protocol_status === 'not_started') {
      view.proposal = await request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/protocol/proposal`);
      if (storedJson(DRAFT_KEY)?.proposal_sha256 === view.proposal.proposal_sha256 && storedJson(DRAFT_KEY)?.content) renderSelected();
      else {
        view.step = 'proposal';
        renderProposal();
      }
    } else if (protocol.protocol_status === 'replanned' && storedJson(CORRECTION_PREVIEW_KEY)) {
      const stored = storedJson(CORRECTION_PREVIEW_KEY);
      const pending = sessionStorage.getItem(CORRECTION_KEY);
      const alreadyApplied = protocol.latest_correction?.correction_id === stored?.correction_id;
      const previewStale = stored?.preview?.parent_state_sha256 !== protocol.base_state_sha256;
      if (!pending || !stored?.selection || alreadyApplied || previewStale) {
        sessionStorage.removeItem(CORRECTION_KEY);
        sessionStorage.removeItem(CORRECTION_PREVIEW_KEY);
        renderProtocol(protocol, state);
      } else {
        const rebound = await request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/protocol/corrections/proposal`, {
          method: 'POST',
          idempotencyKey: `${pending}.prepare`,
          body: correctionRequestBody(stored.selection),
        });
        if (JSON.stringify(rebound) !== JSON.stringify(stored)) {
          sessionStorage.removeItem(CORRECTION_PREVIEW_KEY);
          renderProtocol(protocol, state);
        } else renderCorrectionPreview(rebound);
      }
    } else {
      if (protocol.correction_count > 0) sessionStorage.removeItem(CORRECTION_PREVIEW_KEY);
      renderProtocol(protocol, state);
    }
  }

  async function start() {
    view.active = true;
    document.documentElement.dataset.insuranceProtocol = 'active';
    byId('startState').hidden = true;
    byId('liveWorkspace').hidden = false;
    byId('openAudit').disabled = false;
    byId('orchestratorStatus').textContent = 'Loading the replay-derived claim state';
    byId('liveChip').textContent = 'Working';
    let loopId = sessionStorage.getItem(LOOP_KEY);
    if (!loopId) {
      const pending = sessionStorage.getItem(PENDING_KEY) || key('bootstrap');
      sessionStorage.setItem(PENDING_KEY, pending);
      const created = await request('/api/claim-loops/v1/bootstrap/generated-mould', { method: 'POST', idempotencyKey: pending });
      loopId = created.loop_id;
      sessionStorage.setItem(LOOP_KEY, loopId);
      sessionStorage.removeItem(PENDING_KEY);
    }
    view.loopId = loopId;
    document.body.dataset.casepathActiveLoopId = loopId;
    await hydrate();
    byId('orchestratorStatus').textContent = 'Replay-derived insurance protocol state';
    byId('liveChip').textContent = 'Ready';
  }

  async function register() {
    const filename = byId('protocolEvidenceFilename')?.value.trim() || '';
    const content = byId('protocolEvidenceContent')?.value || '';
    const contentBytes = new TextEncoder().encode(content).byteLength;
    if (!filename || !content.trim()) throw new Error('Choose a text file or enter assessment text.');
    if (!filename.toLowerCase().endsWith('.txt')) throw new Error('The assessment filename must end in .txt.');
    if (contentBytes > 100000) throw new Error('The assessment exceeds the 100,000-byte limit.');
    const pending = sessionStorage.getItem(PENDING_KEY) || key('registration');
    sessionStorage.setItem(PENDING_KEY, pending);
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ proposal_sha256: view.proposal.proposal_sha256, filename, content }));
    const claimedContentSha256 = await sha256Text(content);
    const stage = await request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/protocol/sources/stage`, {
      method: 'POST', idempotencyKey: `${pending}.stage`, body: { filename, media_type: 'text/plain; charset=utf-8', content, claimed_content_sha256: claimedContentSha256, expected_revision: view.proposal.revision },
    });
    const result = await request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/protocol/registrations`, {
      method: 'POST', idempotencyKey: `${pending}.register`, body: { proposal_sha256: view.proposal.proposal_sha256, staged_artifact_receipt_sha256: stage.staged_artifact_receipt_sha256, expected_revision: view.proposal.revision },
    });
    if (result.protocol_state.protocol_status !== 'dispatch_unknown' && !PARTIAL_STATUSES.has(result.protocol_state.protocol_status)) {
      sessionStorage.removeItem(PENDING_KEY);
      sessionStorage.removeItem(DRAFT_KEY);
    }
    // Registration responses intentionally carry only the protocol projection and
    // the canonical state identity. Re-read the exact state/protocol pair before
    // rendering instead of treating an absent, oversized `state` field as trusted.
    await hydrate();
  }

  async function resumeRegistration() {
    const pending = sessionStorage.getItem(PENDING_KEY);
    const records = view.protocol?.record_set;
    if (!pending || !records?.proposal?.proposal_sha256 || !records?.staged_artifact?.receipt_sha256) {
      throw new Error('The exact registration lineage is unavailable.');
    }
    const result = await request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/protocol/registrations`, {
      method: 'POST',
      idempotencyKey: `${pending}.register`,
      body: {
        proposal_sha256: records.proposal.proposal_sha256,
        staged_artifact_receipt_sha256: records.staged_artifact.receipt_sha256,
        expected_revision: records.proposal.source_revision,
      },
    });
    if (!['dispatch_unknown', 'intent_journaled', 'execution_started', 'receipt_recorded', 'source_observed', 'assertion_normalized', 'interpreted', 'replan_receipt_pending'].includes(result.protocol_state.protocol_status)) sessionStorage.removeItem(PENDING_KEY);
    await hydrate();
  }

  async function reconcile() {
    const pending = sessionStorage.getItem(PENDING_KEY);
    const intent = view.protocol?.record_set?.intent?.intent_sha256;
    if (!pending || !intent) throw new Error('The persisted intent locator is unavailable.');
    const result = await request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/protocol/intents/${intent}/reconcile`, { method: 'POST', idempotencyKey: `${pending}.register` });
    if (result.protocol_state.protocol_status !== 'dispatch_unknown') sessionStorage.removeItem(PENDING_KEY);
    await hydrate();
  }

  async function beginCorrectionSelection() {
    if (view.busy) return;
    view.busy = true;
    recordAction();
    const button = byId('protocolCorrection');
    if (button) button.disabled = true;
    try {
      const options = await request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/protocol/corrections/options`);
      renderCorrectionSelection(options);
    } catch (error) {
      renderError(error);
    } finally {
      view.busy = false;
    }
  }

  async function prepareCorrection() {
    const candidate = view.correctionSelection;
    if (!candidate) throw new Error('Select the exact correction before requesting a preview.');
    const pending = sessionStorage.getItem(CORRECTION_KEY) || key('correction');
    sessionStorage.setItem(CORRECTION_KEY, pending);
    const prepared = await request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/protocol/corrections/proposal`, {
      method: 'POST',
      idempotencyKey: `${pending}.prepare`,
      body: correctionRequestBody(candidate),
    });
    sessionStorage.setItem(CORRECTION_PREVIEW_KEY, JSON.stringify(prepared));
    renderCorrectionPreview(prepared);
  }

  async function confirmCorrection() {
    const prepared = view.correctionPreview || storedJson(CORRECTION_PREVIEW_KEY);
    const pending = sessionStorage.getItem(CORRECTION_KEY);
    if (!prepared?.correction_id || !pending) throw new Error('The correction preview lineage is unavailable.');
    await request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/corrections`, { method: 'POST', idempotencyKey: `${pending}.apply`, body: { correction_id: prepared.correction_id } });
    sessionStorage.removeItem(CORRECTION_KEY);
    sessionStorage.removeItem(CORRECTION_PREVIEW_KEY);
    view.correctionOptions = null;
    view.correctionSelection = null;
    view.correctionPreview = null;
    await hydrate();
  }

  function cancelCorrectionPreview() {
    sessionStorage.removeItem(CORRECTION_KEY);
    sessionStorage.removeItem(CORRECTION_PREVIEW_KEY);
    view.correctionOptions = null;
    view.correctionSelection = null;
    view.correctionPreview = null;
    renderProtocol(view.protocol, view.state);
  }

  async function showDecisionPacket(managedByPrimaryAction = false) {
    if (view.busy && !managedByPrimaryAction) return;
    if (!managedByPrimaryAction) {
      view.busy = true;
      recordAction();
    }
    try {
      const packet = await request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/decision-ready`);
      const mode = packet.terminal_mode === 'abstain' ? 'Safe abstention' : 'Decision ready';
      canvas().innerHTML = `<header><span class="insurance-protocol-kicker">Authoritative terminal packet</span><h2>${escapeHtml(mode)}</h2><p>This is the server-validated terminal disposition, not a UI inference.</p></header><article class="insurance-protocol-card"><span class="insurance-protocol-status">${escapeHtml(packet.terminal_mode)}</span>${hashes([['Packet', packet.packet_sha256], ['Source state', packet.source_state_sha256], ['Cycle', packet.six_agent_cycle_receipt_sha256], ['Gate receipt', packet.deterministic_gate_receipt_sha256], ['Accepted artifacts', packet.accepted_cycle_artifacts_sha256]])}</article>`;
      view.step = 'audit';
      setAction('Inspect authoritative audit');
      focusCanvas();
    } catch (error) {
      renderError(error);
    } finally {
      if (!managedByPrimaryAction) view.busy = false;
    }
  }

  async function openAudit(event) {
    if (!view.active) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const [audit, protocol, state] = await Promise.all([
      request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/audit`),
      request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}/protocol-state`),
      request(`/api/claim-loops/v1/${encodeURIComponent(view.loopId)}`),
    ]);
    const thin = protocol.thin_waist_record_set || {};
    const correction = protocol.latest_correction || {};
    const cycle = state.six_agent_cycle_receipt || {};
    if (protocol.loop_id !== state.loop_id
      || protocol.base_revision !== state.revision
      || protocol.base_state_sha256 !== state.state_sha256
      || protocol.last_event_sha256 !== state.last_event_sha256
      || audit.loop_id !== state.loop_id
      || audit.event_count !== state.revision
      || !Array.isArray(audit.event_sha256s)
      || audit.event_sha256s.length !== state.revision
      || audit.event_sha256s.at(-1) !== state.last_event_sha256
      || audit.state_sha256 !== state.state_sha256
      || audit.last_event_sha256 !== state.last_event_sha256) {
      throw new Error('Audit views do not name one authoritative journal prefix. Reload before inspecting receipts.');
    }
    byId('auditContent').innerHTML = `<section class="insurance-protocol-panel"><header><span class="insurance-protocol-kicker">Authoritative replay audit</span><h2>Six roles, three gates, zero provider activity</h2><p>${escapeHtml((cycle.agent_ids || []).join(' → '))}</p><p>${escapeHtml((cycle.deterministic_gate_ids || []).join(' → '))}</p></header><article class="insurance-protocol-card">${hashes([['Loop state', audit.state_sha256], ['Last event', audit.last_event_sha256], ['Cycle receipt', cycle.receipt_sha256], ['Graph audit', cycle.graph_audit_sha256], ['Protocol projection', protocol.projection_sha256], ['V1 intent', protocol.record_set?.intent?.intent_sha256], ['Registry receipt', protocol.record_set?.action_receipt?.receipt_sha256], ['V2 assertion', thin.normalized_assertion?.assertion_sha256], ['V2 interpretation', thin.interpretation?.interpretation_sha256], ['V2 proposal', thin.decision_proposal?.proposal_sha256], ['V2 decision', thin.decision_record?.decision_sha256], ['V2 intent', thin.action_intent?.intent_sha256], ['V2 receipt', thin.action_receipt?.receipt_sha256], ['Correction event', correction.event_sha256], ['Correction delta', correction.delta_sha256], ['Decision packet', protocol.decision_ready_packet_sha256]])}<p>Transport: ${escapeHtml(cycle.transport_mode)} · Correction count: ${escapeHtml(protocol.correction_count)} · Model calls: ${escapeHtml(audit.incremental_loop_activity.model_calls)} · Provider calls: ${escapeHtml(audit.incremental_loop_activity.provider_calls)} · Cost: ${escapeHtml(audit.incremental_loop_activity.cost_usd ?? 'unknown')}</p></article></section>`;
    byId('auditDrawer').showModal();
    setAction('Inspect authoritative audit');
  }

  async function next(event) {
    if (!view.active) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (view.busy) return;
    view.busy = true;
    setAction('Working…', true);
    try {
      recordAction();
      if (view.step === 'proposal') { view.step = 'selected'; renderSelected(); }
      else if (view.step === 'selected') await register();
      else if (view.step === 'correction-select') await prepareCorrection();
      else if (view.step === 'correction-preview') await confirmCorrection();
      else if (view.step === 'resume') await resumeRegistration();
      else if (view.step === 'unknown') await reconcile();
      else if (view.step === 'packet') await showDecisionPacket(true);
      else if (view.step === 'hydrate') await hydrate();
      else if (view.step === 'bootstrap') await start();
      else await openAudit(event);
    } catch (error) {
      renderError(error);
    } finally {
      view.busy = false;
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.body.dataset.insuranceActionCount = String(view.deliberateActions);
    const run = byId('runCasePath');
    if (LEGACY_MODE) byId('insuranceProtocolMode').checked = false;
    run.addEventListener('click', event => {
      if (LEGACY_MODE) return;
      const resume = Boolean(sessionStorage.getItem(LOOP_KEY));
      if (!byId('insuranceProtocolMode').checked && !resume) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (view.busy) return;
      view.busy = true;
      recordAction();
      start().catch(renderError).finally(() => { view.busy = false; });
    }, true);
    byId('journeyNext').addEventListener('click', next, true);
    byId('liveWorkspace').addEventListener('click', event => {
      if (event.target.closest('#protocolCorrection')) beginCorrectionSelection();
      if (event.target.closest('#protocolCorrectionCancel')) cancelCorrectionPreview();
      if (event.target.closest('#protocolPacket')) showDecisionPacket();
    });
    byId('openAudit').addEventListener('click', openAudit, true);
    byId('journeyBack').hidden = true;
    if (!LEGACY_MODE && (sessionStorage.getItem(LOOP_KEY) || sessionStorage.getItem(PENDING_KEY))) {
      byId('insuranceProtocolMode').checked = true;
      run.querySelector('span').textContent = 'Resume evidence journey';
      view.busy = true;
      start().catch(renderError).finally(() => { view.busy = false; });
    }
  });
})();
