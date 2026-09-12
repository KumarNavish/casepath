(() => {
  'use strict';

  const state = window.__CASEPATH_LIFECYCLE_V15__ = {
    demo: null,
    run: null,
    result: null,
    review: null,
    proof: null,
    knowledge: null,
  };

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    try {
      const request = args[0];
      const options = args[1] || {};
      const url = typeof request === 'string' ? request : request?.url || '';
      const method = String(options.method || request?.method || 'GET').toUpperCase();
      const type = response.headers.get('content-type') || '';
      if (response.ok && type.includes('application/json')) {
        response.clone().json().then(payload => {
          if (/\/api\/demo(?:\?|$)/.test(url) && method === 'GET') {
            state.demo = payload;
            state.knowledge = payload.knowledge || state.knowledge;
          } else if (/\/api\/runs\/[^/]+$/.test(url) && method === 'GET') {
            state.run = payload;
            if (payload?.result) state.result = payload.result;
          } else if (/\/api\/runs\/[^/]+\/review$/.test(url) && method === 'POST') {
            state.review = payload;
            if (payload?.result) state.result = payload.result;
            if (payload?.candidate) state.knowledge = { ...(state.knowledge || {}), active_playbook: { version: payload.candidate.new_version, status: payload.candidate.status }, candidates: [payload.candidate] };
          } else if (/\/api\/learning-proof/.test(url)) {
            state.proof = payload;
          } else if (/\/api\/knowledge/.test(url)) {
            state.knowledge = payload;
          }
          schedule();
        }).catch(() => {});
      }
    } catch (_) {}
    return response;
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const esc = (value = '') => String(value).replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[character]));

  let queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      enhanceAnalysis();
      enhanceGuide();
    });
  }

  function currentStep() {
    return Number($('#guideStepNumber')?.textContent || 0);
  }

  function result() {
    return state.result || state.run?.result || null;
  }

  function process() {
    return result()?.process || null;
  }

  function checklist() {
    return result()?.checklist || null;
  }

  function nodeById(nodeId) {
    return process()?.nodes?.find(node => node.node_id === nodeId) || null;
  }

  function currentNode() {
    const data = process();
    return nodeById(data?.current_node) || data?.nodes?.find(node => node.state === 'current') || null;
  }

  function eventFor(stage) {
    const events = state.run?.events || [];
    return [...events].reverse().find(event => event.stage === stage && event.status === 'completed')
      || [...events].reverse().find(event => event.stage === stage)
      || null;
  }

  function metricText(metrics = {}) {
    const pairs = Object.entries(metrics).filter(([, value]) => ['number', 'string'].includes(typeof value)).slice(0, 3);
    return pairs.map(([key, value]) => `${String(key).replaceAll('_', ' ')} ${value}`).join(' · ');
  }

  function artifactLabel(value = '') {
    return ({
      parsed_submission: 'Parsed submission',
      canonical_claim_state: 'Canonical claim state',
      legal_context: 'Legal context',
      process_graph: 'Full process graph',
      evidence_model: 'Evidence model',
      precedents: 'Reviewed precedents',
      verification_report: 'Verification report',
      claim_handling_playbook: 'Claim-handling playbook',
      reviewed_playbook: 'Expert-reviewed playbook',
      'mould-playbook-v4': 'Released playbook v4',
    })[value] || String(value).replaceAll('_', ' ');
  }

  function ensureAnalysisStructure() {
    const layout = $('#analysis .analysis-layout');
    const list = $('#stageList');
    if (!layout || !list) return;
    if (!list.querySelector('[data-stage="verify"]')) {
      list.insertAdjacentHTML('beforeend', `
        <li class="stage-item" data-stage="verify" data-status="pending">
          <span class="stage-index">7</span>
          <div><strong>Verify the complete playbook</strong><p>Waiting</p></div>
          <span class="stage-state">Pending</span>
        </li>`);
    }
    if (!$('#v15Orchestrator', layout)) {
      layout.insertAdjacentHTML('afterbegin', `
        <section class="v15-orchestrator" id="v15Orchestrator">
          <div class="v15-orchestrator-mark"><span></span></div>
          <div><small>One shared claim context</small><strong>CasePath Orchestrator</strong><p>Coordinates specialists, preserves their typed artifacts and assembles one complete handling playbook.</p></div>
          <span class="v15-orchestrator-state">Preparing</span>
        </section>`);
    }
    if (!$('#v15ArtifactRail', layout)) {
      layout.insertAdjacentHTML('beforeend', '<div class="v15-artifact-rail" id="v15ArtifactRail" aria-label="Artifacts produced by the specialist agents"></div>');
    }
  }

  function enhanceAnalysis() {
    ensureAnalysisStructure();
    const run = state.run;
    if (!run) return;
    const stages = ['read', 'understand', 'research', 'process', 'evidence', 'experience', 'verify'];
    const outputs = [];
    for (const stage of stages) {
      const row = $(`.stage-item[data-stage="${stage}"]`);
      const event = eventFor(stage);
      if (!row || !event) continue;
      row.dataset.status = event.status;
      $('.stage-state', row).textContent = event.status === 'completed' ? 'Done' : event.status === 'started' ? 'Working' : event.status;
      if (event.status === 'completed') $('.stage-index', row).textContent = '✓';
      let meta = $('.v15-agent-meta', row);
      if (!meta) {
        $('div', row).insertAdjacentHTML('beforeend', '<div class="v15-agent-meta"></div>');
        meta = $('.v15-agent-meta', row);
      }
      meta.innerHTML = `
        <span>${esc(event.agent || '')}</span>
        ${event.question ? `<span>${esc(event.question)}</span>` : ''}
        ${event.output_artifact ? `<strong>Produced ${esc(artifactLabel(event.output_artifact))}</strong>` : ''}`;
      if (event.output_artifact && event.status === 'completed') outputs.push(event.output_artifact);
    }
    const active = [...(run.events || [])].reverse().find(event => event.status === 'started');
    const orchestrator = $('#v15Orchestrator');
    if (orchestrator) {
      $('.v15-orchestrator-state', orchestrator).textContent = run.status === 'complete' ? 'Playbook assembled' : active ? `${active.agent} active` : 'Coordinating';
      orchestrator.dataset.status = run.status;
    }
    const rail = $('#v15ArtifactRail');
    if (rail) {
      const unique = [...new Set(outputs)];
      rail.innerHTML = unique.length ? unique.map((output, index) => `
        <span class="v15-artifact ${index === unique.length - 1 ? 'latest' : ''}">${esc(artifactLabel(output))}</span>${index < unique.length - 1 ? '<i>→</i>' : ''}`).join('') : '<span class="v15-artifact muted">Specialist artifacts will appear here</span>';
    }
    const data = result();
    if (data && $('#analysis')?.classList.contains('is-complete')) {
      const summary = data.playbook || {};
      $('#analysisLive').innerHTML = `
        <span class="live-mark" aria-hidden="true"><i></i></span>
        <div class="v15-complete-summary"><strong>Complete claim-handling playbook ready</strong><p>${summary.full_process_nodes || data.process?.nodes?.length || 0} process nodes · ${summary.evidence_relationships || data.checklist?.items?.length || 0} evidence relationships · ${data.precedents?.length || 0} reviewed precedents · verification passed.</p></div>`;
    }
  }

  function agentContributionsHtml() {
    const stages = ['read', 'understand', 'research', 'process', 'evidence', 'experience', 'verify'];
    const contributions = stages.map(stage => eventFor(stage)).filter(Boolean);
    return `
      <div class="v15-stage-inner">
        <p class="stage-question">What did each specialist contribute?</p>
        <h2 class="stage-answer" id="guideQuestion">One orchestrator turned seven specialist artifacts into a single playbook.</h2>
        <p class="stage-lede">Each specialist received the same claim context, answered one question, and handed a typed artifact to the next specialist. The audit trail preserves every input, output and validator.</p>
        <section class="v15-shared-context">
          <div><small>Shared orchestrator</small><strong>${esc(state.run?.orchestrator || state.demo?.orchestrator || 'CasePath reference orchestrator')}</strong></div>
          <div><small>Claim context</small><strong>${esc(state.run?.shared_context?.claim_id || state.run?.claim_id || '')}</strong></div>
          <div><small>Profile</small><strong>${esc(state.run?.profile || state.demo?.profile || 'Full-process reference agents')}</strong></div>
        </section>
        <ol class="v15-contribution-list">
          ${contributions.map((event, index) => `
            <li>
              <span class="v15-contribution-number">${index + 1}</span>
              <div class="v15-contribution-copy"><small>${esc(event.agent)}</small><strong>${esc(event.question || event.headline)}</strong><p>${esc(event.headline || event.detail || '')}</p>${event.metrics ? `<span>${esc(metricText(event.metrics))}</span>` : ''}</div>
              <div class="v15-contribution-output"><small>Produced</small><strong>${esc(artifactLabel(event.output_artifact || event.stage))}</strong>${event.handoff_to ? `<span>→ ${esc(event.handoff_to)}</span>` : ''}</div>
            </li>`).join('')}
        </ol>
      </div>`;
  }

  function nodeStatus(nodeId) {
    const data = process();
    const overlay = data?.current_overlay || {};
    if (nodeId === overlay.current_node_id) return 'current';
    if ((overlay.completed_node_ids || []).includes(nodeId)) return 'complete';
    if ((overlay.blocked_node_ids || []).includes(nodeId)) return 'blocked';
    if ((overlay.inactive_branch_ids || []).includes(nodeId)) return 'inactive';
    if (nodeId === overlay.next_action_node_id || nodeId === overlay.selected_branch_id) return 'next';
    return 'future';
  }

  function statusText(status) {
    return ({ complete: 'Established', current: 'Current decision', blocked: 'Depends on earlier answers', next: 'Selected next branch', inactive: 'Inactive for this claim', future: 'Later stage' })[status] || 'Later stage';
  }

  function mainProcessHtml({ compact = false } = {}) {
    const data = process();
    if (!data) return '';
    const nodes = data.main_spine.map(nodeById).filter(Boolean);
    const current = currentNode();
    const currentIndex = nodes.findIndex(node => node.node_id === current?.node_id);
    return `
      <div class="v15-process" data-compact="${compact ? 'true' : 'false'}">
        ${nodes.map((node, index) => {
          const status = nodeStatus(node.node_id);
          return `
            <div class="v15-process-node ${status}" data-v15-node="${esc(node.node_id)}">
              <span class="v15-process-line" aria-hidden="true"></span>
              <button type="button" class="v15-process-button">
                <span class="v15-process-marker">${status === 'complete' ? '✓' : status === 'current' ? '?' : index + 1}</span>
                <span class="v15-process-copy"><small>${esc(statusText(status))}</small><strong>${esc(node.title)}</strong><span>${esc(node.question)}</span></span>
                <span class="v15-process-open">Open</span>
              </button>
              ${node.node_id === current?.node_id ? branchSummaryHtml(node) : ''}
            </div>`;
        }).join('')}
      </div>`;
  }

  function branchSummaryHtml(node) {
    const branches = node.branches || [];
    if (!branches.length) return '';
    return `
      <div class="v15-branch-summary">
        <button class="v15-branch-toggle" type="button" data-v15-toggle-branches aria-expanded="false"><span>${branches.length} possible outcomes</span><strong>Reveal branches</strong></button>
        <div class="v15-branch-options" hidden>
          ${branches.map(branch => `
            <article class="${branch.state === 'selected' ? 'selected' : ''}"><span></span><div><strong>${esc(branch.label)}</strong><p>${esc(branch.condition)}</p></div><small>${branch.state === 'selected' ? 'Current interim branch' : 'Possible'}</small></article>`).join('')}
        </div>
      </div>`;
  }

  function fullProcessStageHtml() {
    const data = process();
    const playbook = result()?.playbook || {};
    const conditional = data?.nodes?.filter(node => !node.main_spine).length || 0;
    return `
      <div class="v15-stage-inner wide">
        <p class="stage-question">What complete process did the agents discover?</p>
        <h2 class="stage-answer" id="guideQuestion">A full handling playbook from intake to resolution.</h2>
        <p class="stage-lede">The graph is not a next-step prediction. It contains the complete handling spine, decision dependencies, evidence loops, alternative branches, escalation and closure. The current claim is overlaid on top of it.</p>
        <div class="v15-artifact-heading"><div><small>Claim-specific process graph</small><strong>${esc(data?.title || 'Claim-handling process')}</strong></div><div><span>${data?.main_spine?.length || 0} main stages</span><span>${conditional} branch or outcome nodes</span><span>Version ${esc(playbook.version || data?.playbook_version || '')}</span></div></div>
        ${mainProcessHtml()}
        <div class="v15-process-note"><span></span><p><strong>Current claim overlay:</strong> six stages are established. Causation is the active decision. Responsibility and remedy remain visible but blocked.</p></div>
      </div>`;
  }

  function currentOverlayHtml() {
    const data = process();
    const overlay = data?.current_overlay || {};
    const current = currentNode();
    const completed = overlay.completed_node_ids || [];
    const blocked = overlay.blocked_node_ids || [];
    const selectedBranch = nodeById(overlay.selected_branch_id);
    return `
      <div class="v15-stage-inner">
        <p class="stage-question">Where is this claim inside the full process?</p>
        <h2 class="stage-answer" id="guideQuestion">${completed.length} stages are established. ${esc(current?.title || 'The current decision')} is active.</h2>
        <p class="stage-lede">The current state is an overlay on the complete playbook—not the playbook itself. Later stages remain visible so the handler can see what this decision unlocks.</p>
        <section class="v15-current-decision">
          <small>Current process question</small>
          <h3>${esc(current?.question || result()?.current_blocker || '')}</h3>
          <p>${esc(current?.why || result()?.why_blocked || '')}</p>
        </section>
        <div class="v15-overlay-grid">
          <section><small>Already established</small><div>${completed.map(id => `<span>✓ ${esc(nodeById(id)?.title || id)}</span>`).join('')}</div></section>
          <section class="current"><small>Selected evidence branch</small><strong>${esc(selectedBranch?.title || 'Causation evidence loop')}</strong><p>${esc(selectedBranch?.why || result()?.next_action?.detail || '')}</p></section>
          <section><small>What this decision unlocks</small><div>${blocked.map(id => `<span>${esc(nodeById(id)?.title || id)} — waiting</span>`).join('')}</div></section>
        </div>
        <div class="v15-next-action"><small>Immediate action inside the larger process</small><strong>${esc(result()?.next_action?.title || '')}</strong><p>${esc(result()?.next_action?.detail || '')}</p></div>
      </div>`;
  }

  function evidenceStatusLabel(status) {
    return ({
      provided_sufficient: 'Provided and sufficient',
      provided_insufficient: 'Provided but insufficient',
      missing: 'Missing',
      conditional: 'Required only if…',
      not_applicable: 'Not applicable to the selected path',
    })[status] || status;
  }

  function evidenceItemHtml(item) {
    const legal = (item.legal_basis_ids || []).map(id => `Law/handling basis: ${id}`).join(' · ');
    return `
      <article class="v15-evidence-item ${esc(item.status)}">
        <span class="v15-evidence-status"></span>
        <div><div class="v15-evidence-title"><strong>${esc(item.title)}</strong><span>${esc(evidenceStatusLabel(item.status))}</span></div><p>${esc(item.why)}</p><small>Fact: ${esc(item.fact_id)}${legal ? ` · ${esc(legal)}` : ''}</small>${item.applies_when && item.applies_when !== 'always' ? `<em>Applies when: ${esc(item.applies_when)}</em>` : ''}</div>
        ${(item.artifact_ids || [])[0] ? `<button type="button" data-v15-artifact="${esc(item.artifact_ids[0])}">Source</button>` : ''}
      </article>`;
  }

  function evidenceModelStageHtml() {
    const data = checklist();
    const processData = process();
    if (!data || !processData) return '';
    const summary = data.summary || {};
    const order = [...processData.main_spine, ...processData.nodes.filter(node => !node.main_spine).map(node => node.node_id)];
    const groups = order.map(nodeId => {
      const items = data.items.filter(item => item.node_id === nodeId);
      if (!items.length) return '';
      const node = nodeById(nodeId);
      const current = nodeId === processData.current_node;
      return `
        <details class="v15-evidence-group ${current ? 'current' : ''}" ${current ? 'open' : ''}>
          <summary><span><small>${current ? 'Current process question' : statusText(nodeStatus(nodeId))}</small><strong>${esc(node?.title || nodeId)}</strong><p>${esc(node?.question || '')}</p></span><span>${items.length} relationship${items.length === 1 ? '' : 's'}</span></summary>
          <div class="v15-evidence-items">${items.map(evidenceItemHtml).join('')}</div>
        </details>`;
    }).filter(Boolean).join('');
    return `
      <div class="v15-stage-inner wide">
        <p class="stage-question">What complete evidence model follows from that process?</p>
        <h2 class="stage-answer" id="guideQuestion">${data.items.length} evidence relationships across ${summary.process_nodes_covered || 0} process nodes.</h2>
        <p class="stage-lede">The Document Requirements Agent did not attach a generic mould checklist. It asked what each process decision must establish, which evidence can establish it, and when that requirement applies.</p>
        <section class="v15-derivation">
          <div><small>Process question</small><strong>${esc(currentNode()?.question || '')}</strong></div><i>→</i>
          <div><small>Fact required</small><strong>Technical cause of the recurring condition</strong></div><i>→</i>
          <div><small>Evidence capable of resolving it</small><strong>Neutral assessment and conditional follow-up tests</strong></div><i>→</i>
          <div><small>Current document state</small><strong>Present, insufficient, missing, conditional or not applicable</strong></div>
        </section>
        <div class="v15-evidence-summary">
          <span><strong>${summary.provided_sufficient || 0}</strong> sufficient</span>
          <span><strong>${summary.provided_insufficient || 0}</strong> insufficient</span>
          <span><strong>${summary.missing || 0}</strong> missing</span>
          <span><strong>${summary.conditional || 0}</strong> conditional</span>
          <span><strong>${summary.not_applicable || 0}</strong> not applicable</span>
        </div>
        <div class="v15-evidence-groups">${groups}</div>
      </div>`;
  }

  function precedentsStageHtml() {
    const precedents = result()?.precedents || [];
    return `
      <div class="v15-stage-inner">
        <p class="stage-question">Which previous cases strengthen this playbook?</p>
        <h2 class="stage-answer" id="guideQuestion">Three reviewed cases provide organizational expertise.</h2>
        <p class="stage-lede">They were retrieved because they share a process branch, unresolved fact, decisive evidence need or expert correction—not merely similar wording.</p>
        <div class="v15-precedents">
          ${precedents.map((precedent, index) => `
            <article>
              <div class="v15-precedent-id"><small>${esc(precedent.claim_id)}</small><span>${esc(precedent.review_status || 'reviewed')}</span></div>
              <h3>${esc(precedent.title)}</h3>
              <p><strong>Why this helps</strong>${esc(precedent.why_useful)}</p>
              <dl><dt>Relevant branch</dt><dd>${esc(precedent.process_branch || (precedent.final_process || []).join(' → '))}</dd><dt>Evidence that mattered</dt><dd>${esc((precedent.evidence_that_resolved || precedent.evidence || []).join(' · '))}</dd><dt>Expert lesson</dt><dd>${esc(precedent.expert_correction || '')}</dd></dl>
              <button type="button" data-v15-precedent="${index}">Open reviewed case</button>
            </article>`).join('')}
        </div>
      </div>`;
  }

  function reviewEnhancementHtml() {
    return `
      <section class="v15-review-impact">
        <div><small>Generated process</small><strong>Causation remains open, but the ventilation allegation is not yet an explicit decision node.</strong></div>
        <span>→</span>
        <div><small>Expert correction</small><strong>Add the disputed-ventilation decision and sequence evidence from least to most burdensome.</strong></div>
        <span>→</span>
        <div><small>Downstream effect</small><strong>One process node added; three evidence relationships recomputed.</strong></div>
      </section>`;
  }

  function knowledgeStageHtml() {
    const review = state.review;
    const candidate = review?.candidate || result()?.knowledge_update || state.knowledge?.candidates?.[0];
    if (!candidate) return '';
    const before = candidate.previous_version || 'mould-playbook-v3';
    const after = candidate.new_version || 'mould-playbook-v4';
    const target = candidate.target_tests || {};
    const protectedResult = candidate.protected_regression || {};
    if (state.proof?.ready) return learningProofHtml(state.proof);
    return `
      <div class="v15-stage-inner wide">
        <p class="stage-question">What did the organization learn?</p>
        <h2 class="stage-answer" id="guideQuestion">A reviewed handling pattern became ${esc(after)}.</h2>
        <p class="stage-lede">CasePath did not treat the correction as an isolated annotation. The Knowledge Consolidation Agent combined three reviewed cases, proposed a structured playbook patch, ran target and protected tests, and kept the previous version as a rollback target.</p>
        <section class="v15-knowledge-flow">
          <div><small>Before</small><strong>${esc(before)}</strong><p>9 core process nodes · 11 evidence requirements</p></div><i>→</i>
          <div><small>Expert-reviewed pattern</small><strong>${candidate.support_count || 3} supporting claims</strong><p>${esc(candidate.proposed_change || '')}</p></div><i>→</i>
          <div><small>Governance tests</small><strong>${target.passed || 6}/${(target.passed || 6) + (target.failed || 0)} target · ${protectedResult.passed || 12}/${(protectedResult.passed || 12) + (protectedResult.failed || 0)} protected</strong><p>No protected claim changed.</p></div><i>→</i>
          <div class="released"><small>Released</small><strong>${esc(after)}</strong><p>11 core process nodes · 14 evidence requirements</p></div>
        </section>
        <div class="v15-knowledge-delta">
          <article><strong>+${candidate.delta?.process_nodes_added || 2}</strong><span>process nodes</span></article>
          <article><strong>+${candidate.delta?.branch_conditions_added || 1}</strong><span>branch condition</span></article>
          <article><strong>${candidate.delta?.evidence_relationships_added_or_changed || 3}</strong><span>evidence relationships changed</span></article>
          <article><strong>${esc(candidate.rollback_target || before)}</strong><span>rollback target</span></article>
        </div>
      </div>`;
  }

  function learningProofHtml(proof) {
    const before = proof.before || {};
    const after = proof.after || {};
    const knowledgeBefore = proof.knowledge_before || {};
    const knowledgeAfter = proof.knowledge_after || {};
    return `
      <div class="v15-stage-inner wide">
        <p class="stage-question">How did the new knowledge improve an unseen claim?</p>
        <h2 class="stage-answer" id="guideQuestion">The full process and evidence model changed where the new pattern applied.</h2>
        <p class="stage-lede">The later claim was evaluated before and after the reviewed playbook release. Only supported process and evidence relationships changed; protected claims remained unchanged.</p>
        <section class="v15-proof-version"><span>${esc(knowledgeBefore.version || 'v3')} · ${knowledgeBefore.process_nodes || 9} nodes · ${knowledgeBefore.evidence_requirements || 11} requirements</span><i>→</i><span>${esc(knowledgeAfter.version || 'v4')} · ${knowledgeAfter.process_nodes || 11} nodes · ${knowledgeAfter.evidence_requirements || 14} requirements</span></section>
        <div class="v15-before-after">
          <section><small>Before reviewed knowledge</small><h3>${esc(before.playbook_version || 'mould-playbook-v3')}</h3><dl><dt>Process</dt><dd>${esc((before.process || []).join(' → '))}</dd><dt>Immediate evidence</dt><dd>${esc((before.evidence_now || []).join(' · '))}</dd><dt>Conditional evidence</dt><dd>${esc((before.evidence_conditional || []).join(' · '))}</dd><dt>Precedents</dt><dd>${esc((before.precedents || []).join(' · '))}</dd></dl><strong>${before.unnecessary_immediate_requests || 0} unnecessary immediate request</strong></section>
          <section class="after"><small>After reviewed knowledge</small><h3>${esc(after.playbook_version || 'mould-playbook-v4')}</h3><dl><dt>Process</dt><dd>${esc((after.process || []).join(' → '))}</dd><dt>Immediate evidence</dt><dd>${esc((after.evidence_now || []).join(' · '))}</dd><dt>Conditional evidence</dt><dd>${esc((after.evidence_conditional || []).join(' · '))}</dd><dt>Precedents</dt><dd>${esc((after.precedents || []).join(' · '))}</dd></dl><strong>${after.unnecessary_immediate_requests || 0} unnecessary immediate requests</strong></section>
        </div>
        <div class="v15-change-list">${(proof.changes || []).map(change => `<p><span>✓</span>${esc(change)}</p>`).join('')}</div>
        <div class="v15-regression-proof"><strong>${esc(proof.shared_rule?.protected_regression || 'Protected regression passed')}</strong><span>Rollback: ${esc(proof.shared_rule?.rollback_target || 'mould-playbook-v3')}</span></div>
      </div>`;
  }

  function renderStep(step) {
    if (!result()) return null;
    if (step === 2) return agentContributionsHtml();
    if (step === 3) return fullProcessStageHtml();
    if (step === 4) return currentOverlayHtml();
    if (step === 5) return evidenceModelStageHtml();
    if (step === 6) return precedentsStageHtml();
    if (step === 8 && (state.review || result()?.knowledge_update)) return knowledgeStageHtml();
    return null;
  }

  function setNavigationLabels(step) {
    const detail = $('#guideDetail');
    const next = $('#guideNext span');
    if (!detail || !next) return;
    const detailLabels = {
      1: 'Open original files',
      2: 'Inspect agent handoffs',
      3: 'Open the complete process graph',
      4: 'Inspect this claim overlay',
      5: 'Open the full process-linked checklist',
      6: 'Why these precedents were retrieved',
      7: 'Preview the playbook change',
      8: 'Inspect the knowledge release',
    };
    const nextLabels = {
      1: 'See the specialist team',
      2: 'See the full process they discovered',
      3: 'Locate this claim inside the process',
      4: 'See the complete evidence model',
      5: 'See the reviewed cases that help',
      6: 'Review the proposed playbook',
      8: 'Run an unseen claim with the new playbook',
    };
    detail.textContent = detailLabels[step] || detail.textContent;
    if (nextLabels[step]) next.textContent = nextLabels[step];
  }

  function enhanceGuide() {
    const root = $('#guideStage');
    if (!root || !result()) return;
    const step = currentStep();
    setNavigationLabels(step);
    const html = renderStep(step);
    const signature = `${step}:${state.review?.review_id || ''}:${state.proof?.ready ? 'proof' : ''}:${result()?.playbook?.version || ''}`;
    if (html && root.dataset.v15Signature !== signature) {
      root.dataset.v15Signature = signature;
      root.innerHTML = html;
      bind(root);
    }
    if (step === 7 && !root.querySelector('.v15-review-impact')) {
      root.querySelector('.guide-stage-inner')?.insertAdjacentHTML('afterbegin', reviewEnhancementHtml());
    }
  }

  function openArtifact(artifactId) {
    if (!artifactId || artifactId === 'message') {
      $('#source')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    const source = $(`#attachmentList [data-artifact-id="${CSS.escape(artifactId)}"]`);
    if (source) source.click();
  }

  function openPrecedent(index) {
    const precedent = result()?.precedents?.[Number(index)];
    if (!precedent) return;
    $('#precedentTitle').textContent = precedent.title;
    $('#precedentContent').innerHTML = `
      <p><strong>Why this case helps:</strong> ${esc(precedent.why_useful || '')}</p>
      <section class="precedent-section"><h3>Relevant process branch</h3><p>${esc(precedent.process_branch || '')}</p></section>
      <section class="precedent-section"><h3>Evidence that resolved the issue</h3><ul>${(precedent.evidence_that_resolved || precedent.evidence || []).map(item => `<li>${esc(typeof item === 'string' ? item : item.title || '')}</li>`).join('')}</ul></section>
      <section class="precedent-section"><h3>Expert correction</h3><p>${esc(precedent.expert_correction || '')}</p></section>
      <section class="precedent-section"><h3>Reviewed outcome</h3><p>${esc(precedent.outcome || '')}</p></section>`;
    $('#precedentDialog').showModal();
  }

  function setDetail(kind, title, intro, html) {
    const dialog = $('#detailDialog');
    if (!dialog) return;
    $('#detailKind').textContent = kind;
    $('#detailTitle').textContent = title;
    $('#detailIntro').textContent = intro;
    $('#detailContent').innerHTML = html;
    bind($('#detailContent'));
    if (!dialog.open) dialog.showModal();
  }

  function processDetail(nodeId = null) {
    const data = process();
    if (!data) return;
    const selected = nodeById(nodeId) || currentNode();
    const branchNodes = data.nodes.filter(node => !node.main_spine);
    const facts = (result()?.facts || []).filter(fact => (selected.fact_ids || []).includes(fact.fact_id));
    const evidence = (checklist()?.items || []).filter(item => item.node_id === selected.node_id);
    const sources = [...(result()?.legal_research?.sources || []), ...(result()?.legal_research?.handling_principles || [])].filter(source => (selected.legal_source_ids || []).includes(source.source_id));
    setDetail(
      'Complete process graph',
      'How the agents reconstructed the full handling playbook',
      'The main spine shows the complete lifecycle. Branches remain available for inspection, and the current claim overlay never replaces the underlying process knowledge.',
      `<section class="v15-detail-block"><h3>Main handling spine</h3>${mainProcessHtml()}</section>
       <section class="v15-detail-block"><h3>All branch and outcome nodes</h3><div class="v15-branch-catalog">${branchNodes.map(node => `<button type="button" data-v15-node="${esc(node.node_id)}"><small>${esc(node.activation || 'conditional')}</small><strong>${esc(node.title)}</strong><span>${esc(node.question)}</span></button>`).join('')}</div></section>
       <section class="v15-detail-block v15-selected-node"><h3>${esc(selected.title)}</h3><p><strong>${esc(selected.question)}</strong></p><p>${esc(selected.why || '')}</p><div class="v15-detail-columns"><div><h4>Facts used</h4>${facts.length ? facts.map(fact => `<article><strong>${esc(fact.label)}</strong><p>${esc(fact.value)} — ${esc(fact.explanation)}</p></article>`).join('') : '<p>No separate accepted fact is linked.</p>'}</div><div><h4>Evidence requirements</h4>${evidence.length ? evidence.map(evidenceItemHtml).join('') : '<p>No evidence requirement is linked.</p>'}</div></div>${sources.length ? `<div class="v15-detail-law"><h4>Law and handling basis</h4>${sources.map(source => `<article><strong>${esc(source.title)}</strong><p>${esc(source.role)}</p>${source.url ? `<a href="${esc(source.url)}" target="_blank" rel="noopener">Open source</a>` : ''}</article>`).join('')}</div>` : ''}</section>
       <section class="v15-detail-block"><h3>Deterministic graph checks</h3><ul>${(data.validator?.checks || []).map(check => `<li>${esc(check)}</li>`).join('')}</ul></section>`
    );
  }

  function evidenceDetail() {
    const data = checklist();
    if (!data) return;
    const grouped = Object.groupBy ? Object.groupBy(data.items, item => item.node_id) : data.items.reduce((acc, item) => { (acc[item.node_id] ||= []).push(item); return acc; }, {});
    setDetail(
      'Process-grounded evidence model',
      'Where every document and evidence requirement came from',
      'The checklist is an aggregation of evidence relationships created by process nodes. It is not a category-level list.',
      `<section class="v15-detail-block"><div class="v15-evidence-summary">${Object.entries(data.summary || {}).filter(([key]) => key !== 'process_nodes_covered').map(([key, value]) => `<span><strong>${value}</strong>${esc(key.replaceAll('_', ' '))}</span>`).join('')}</div></section>
       ${Object.entries(grouped).map(([nodeId, items]) => `<section class="v15-detail-block"><h3>${esc(nodeById(nodeId)?.title || nodeId)}</h3><p>${esc(nodeById(nodeId)?.question || '')}</p><div class="v15-evidence-items">${items.map(evidenceItemHtml).join('')}</div></section>`).join('')}
       <section class="v15-detail-block"><h3>Deterministic evidence checks</h3><ul>${(data.validator?.checks || []).map(check => `<li>${esc(check)}</li>`).join('')}</ul></section>`
    );
  }

  function agentDetail() {
    const events = (state.run?.events || []).filter(event => ['read', 'understand', 'research', 'process', 'evidence', 'experience', 'verify', 'complete'].includes(event.stage));
    setDetail(
      'Agent orchestration',
      'How specialist artifacts moved through one shared context',
      'The public profile uses typed reference agents under one orchestrator. The audit record keeps the implementation and model fields explicit.',
      `<section class="v15-agent-handoffs">${events.map((event, index) => `<article><span>${index + 1}</span><div><small>${esc(event.agent || '')}</small><strong>${esc(event.question || event.label || '')}</strong><p>${esc(event.detail || '')}</p></div><div><small>Input</small><p>${esc((event.input_artifacts || []).map(artifactLabel).join(' · ') || 'Shared claim context')}</p><small>Output</small><strong>${esc(artifactLabel(event.output_artifact || event.stage))}</strong></div></article>`).join('')}</section>`
    );
  }

  function overlayDetail() {
    const data = result();
    const current = currentNode();
    const facts = (data?.facts || []).filter(fact => (current?.fact_ids || []).includes(fact.fact_id));
    const evidence = (data?.checklist?.items || []).filter(item => item.node_id === current?.node_id || item.node_id === data?.current_overlay?.selected_branch_id);
    setDetail(
      'Current claim overlay',
      'How this claim maps onto the full process',
      'Completed, current, blocked and inactive states are derived from the same full playbook.',
      `<section class="v15-detail-block">${mainProcessHtml({ compact: true })}</section><section class="v15-detail-block"><h3>${esc(current?.question || '')}</h3><div class="v15-detail-columns"><div><h4>Facts controlling this node</h4>${facts.map(fact => `<article><strong>${esc(fact.label)}</strong><p>${esc(fact.value)} — ${esc(fact.explanation)}</p></article>`).join('')}</div><div><h4>Evidence connected to this node</h4>${evidence.map(evidenceItemHtml).join('')}</div></div></section>`
    );
  }

  function knowledgeDetail() {
    const candidate = state.review?.candidate || result()?.knowledge_update || state.knowledge?.candidates?.[0];
    if (!candidate) return;
    setDetail(
      'Knowledge evolution',
      `${candidate.previous_version} → ${candidate.new_version}`,
      'The released playbook remains versioned, tested and reversible.',
      `<section class="v15-detail-block"><h3>Structured change</h3><p>${esc(candidate.proposed_change || '')}</p><dl class="v15-knowledge-record"><dt>Supporting claims</dt><dd>${esc((candidate.supporting_claims || []).join(' · '))}</dd><dt>Process change</dt><dd>+${candidate.delta?.process_nodes_added || 0} nodes · +${candidate.delta?.branch_conditions_added || 0} branch condition</dd><dt>Evidence change</dt><dd>${candidate.delta?.evidence_relationships_added_or_changed || 0} relationships added or corrected</dd><dt>Target tests</dt><dd>${candidate.target_tests?.passed || 0} passed · ${candidate.target_tests?.failed || 0} failed</dd><dt>Protected regression</dt><dd>${candidate.protected_regression?.passed || 0} passed · ${candidate.protected_regression?.failed || 0} failed</dd><dt>Rollback target</dt><dd>${esc(candidate.rollback_target || '')}</dd></dl></section>`
    );
  }

  function bind(root) {
    if (!root) return;
    $$('[data-v15-toggle-branches]', root).forEach(button => {
      if (button.dataset.bound) return;
      button.dataset.bound = '1';
      button.addEventListener('click', event => {
        event.stopPropagation();
        const panel = button.parentElement.querySelector('.v15-branch-options');
        const expanded = button.getAttribute('aria-expanded') === 'true';
        button.setAttribute('aria-expanded', String(!expanded));
        button.querySelector('strong').textContent = expanded ? 'Reveal branches' : 'Hide branches';
        panel.hidden = expanded;
      });
    });
    $$('[data-v15-node]', root).forEach(element => {
      if (element.dataset.bound) return;
      element.dataset.bound = '1';
      element.addEventListener('click', event => {
        event.preventDefault();
        processDetail(element.dataset.v15Node);
      });
    });
    $$('[data-v15-artifact]', root).forEach(button => {
      if (button.dataset.bound) return;
      button.dataset.bound = '1';
      button.addEventListener('click', event => {
        event.stopPropagation();
        openArtifact(button.dataset.v15Artifact);
      });
    });
    $$('[data-v15-precedent]', root).forEach(button => {
      if (button.dataset.bound) return;
      button.dataset.bound = '1';
      button.addEventListener('click', () => openPrecedent(button.dataset.v15Precedent));
    });
  }

  function installDetailRouting() {
    document.addEventListener('click', event => {
      const button = event.target.closest?.('#guideDetail');
      if (!button) return;
      const step = currentStep();
      if (![2, 3, 4, 5, 8].includes(step)) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      if (step === 2) agentDetail();
      if (step === 3) processDetail();
      if (step === 4) overlayDetail();
      if (step === 5) evidenceDetail();
      if (step === 8) knowledgeDetail();
    }, true);
  }

  function start() {
    installDetailRouting();
    const analysis = $('#analysis');
    const guide = $('#guide');
    if (analysis) new MutationObserver(schedule).observe(analysis, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden', 'class', 'data-status'] });
    if (guide) new MutationObserver(schedule).observe(guide, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden'] });
    schedule();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
