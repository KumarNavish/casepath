(() => {
  'use strict';

  if (document.documentElement.dataset.claimsWorkspace === 'true') return;

  if (new URLSearchParams(location.search).get('foundation') === 'live-v1') return;

  const API = location.origin.replace(/\/$/, '');
  const stageDefs = [
    { id: 'read', label: 'Read', selector: '.event-list', output: 'source package', next: 'Canonical Claim Preparation Tool' },
    { id: 'understand', label: 'Understand', selector: '.fact-stream', output: 'claim state', next: 'Swiss Legal Source Tool' },
    { id: 'research', label: 'Law', selector: '.law-flow,.v17-law-map', output: 'legal context', next: 'Process Projection Tool' },
    { id: 'process', label: 'Process', pattern: /complete handling process is taking shape|building the handling process/i, output: 'handling process', next: 'Evidence Checklist Tool' },
    { id: 'evidence', label: 'Evidence', pattern: /Evidence now follows directly from the process|attaching evidence/i, output: 'evidence model', next: 'Historical Retrieval Tool' },
    { id: 'experience', label: 'Experience', selector: '.precedent-inline', output: 'provenance-labelled generated reference patterns', next: 'Whole-Playbook Verification Gate' },
    { id: 'verify', label: 'Verify', selector: '.verification-list', output: 'verified playbook', next: 'Demo review' },
  ];
  const stageOrder = stageDefs.map(stage => stage.id);
  let scheduled = false;
  let cachedRun = null;
  let cachedRunId = '';
  let cachedAt = 0;

  function ensureAssets() {
    const lawNormalizeSrc = 'assets/live-v18-law-normalize.js?sha256=d34bdb45661aa2aecff189bdf8ca43e303aee71d9975fb9acd7e46e8e6549d97';
    if (![...document.scripts].some(script => script.src === new URL(lawNormalizeSrc, document.baseURI).href)) {
      const script = document.createElement('script');
      script.src = lawNormalizeSrc;
      script.async = false;
      document.head.append(script);
    }
    const liveV19Href = 'assets/live-v19.css?sha256=7da2e0500edc81a9c2aff735bb93d478267cda7dfe186b27ce3a061ea812d499';
    if (![...document.querySelectorAll('link[rel="stylesheet"]')].some(link => link.href === new URL(liveV19Href, document.baseURI).href)) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = liveV19Href;
      document.head.append(link);
    }
  }

  function esc(value = '') {
    return String(value).replace(/[&<>'"]/g, character => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
    }[character]));
  }

  function discoveredRunIds() {
    const ids = Array.isArray(window.CASEPATH_RUN_IDS) ? [...window.CASEPATH_RUN_IDS] : [];
    for (const entry of performance.getEntriesByType('resource')) {
      try {
        const url = new URL(entry.name);
        const match = url.pathname.match(/^\/api\/runs\/([^/]+)$/);
        if (match && !ids.includes(match[1])) ids.push(match[1]);
      } catch (_) {}
    }
    return ids;
  }

  async function currentRun({ fresh = false, first = false } = {}) {
    const ids = discoveredRunIds();
    const runId = first ? ids[0] : ids.at(-1);
    if (!runId) return null;
    const shared = window.CasePathRunStore?.get?.(runId);
    if (shared) return shared;
    if (window.CasePathRunStore) return cachedRunId === runId ? cachedRun : null;
    if (!fresh && cachedRunId === runId && cachedRun && Date.now() - cachedAt < 400) return cachedRun;
    try {
      const response = await fetch(`${API}/api/runs/${encodeURIComponent(runId)}`, { headers: { Accept: 'application/json' } });
      if (!response.ok) return cachedRunId === runId ? cachedRun : null;
      const value = await response.json();
      cachedRun = value;
      cachedRunId = runId;
      cachedAt = Date.now();
      return value;
    } catch (_) {
      return cachedRunId === runId ? cachedRun : null;
    }
  }

  function activeStage(canvas) {
    const text = canvas?.textContent || '';
    return stageDefs.find(stage => stage.selector ? canvas.querySelector(stage.selector) : stage.pattern?.test(text)) || null;
  }

  function journeyKind(canvas) {
    if (!canvas) return 'opening';
    if (canvas.querySelector('#reviewForm')) return 'review';
    if (canvas.querySelector('.knowledge-agent')) return 'knowledge';
    if (canvas.querySelector('.later-run')) return 'later';
    if (canvas.querySelector('.v17-derived-checklist,.artifact-summary') || /Handling playbook ready|reconstructed how this claim should be handled/i.test(canvas.textContent || '')) return 'ready';
    return activeStage(canvas) ? 'stage' : 'opening';
  }

  function eventFor(run, stageId) {
    return [...(run?.events || [])].reverse().find(event => event.stage === stageId && event.status === 'completed')
      || [...(run?.events || [])].reverse().find(event => event.stage === stageId)
      || null;
  }

  function missionFor(run, stage, kind) {
    if (kind === 'review') return 'Review the evidence-order decision that changes the process and next action.';
    if (kind === 'knowledge') return 'Separate immediately reusable case memory from a governed shared-rule release.';
    if (kind === 'later') return 'Check whether the held-out later demo claim retrieves unverified demo memory without changing the shared playbook.';
    if (kind === 'ready') return 'Bring the process, evidence, and provenance-labelled experience together for simulated demo review.';
    if (!stage) return 'Open one shared claim context for the specialist team.';
    const event = eventFor(run, stage.id);
    return event?.question || event?.headline || event?.detail || `Add ${stage.output} to the shared claim context.`;
  }

  function completedStageIds(run) {
    return stageDefs.filter(stage => (run?.events || []).some(event => event.stage === stage.id && event.status === 'completed')).map(stage => stage.id);
  }

  function renderTeamRail(canvas, run) {
    const nav = document.querySelector('#agentProgress');
    if (!nav || document.querySelector('#liveWorkspace')?.hidden) return;
    let rail = nav.querySelector('.v19-team-rail');
    if (!rail) {
      rail = document.createElement('section');
      rail.className = 'v19-team-rail';
      rail.setAttribute('aria-label', 'Live CasePath team activity');
      nav.append(rail);
    }
    const kind = journeyKind(canvas);
    const stage = activeStage(canvas);
    const completed = completedStageIds(run);
    const activeId = kind === 'stage' ? stage?.id : '';
    const activeIndex = stageOrder.indexOf(activeId);
    const next = activeIndex >= 0 ? stageDefs[activeIndex + 1] : null;
    const contributed = [...new Set(completed.map(id => stageDefs.find(stageDef => stageDef.id === id)?.output).filter(Boolean))];
    const history = [];
    for (const id of completed.slice(-3)) {
      const item = stageDefs.find(stageDef => stageDef.id === id);
      if (item) history.push({ label: item.label, state: 'complete', detail: item.output });
    }
    if (activeId && !completed.includes(activeId)) history.push({ label: stage.label, state: 'active', detail: 'working now' });
    if (kind === 'ready') history.push({ label: 'Team', state: 'complete', detail: 'playbook ready' });
    if (kind === 'review') history.push({ label: 'Demo reviewer', state: 'active', detail: 'simulating one correction' });
    if (kind === 'knowledge') history.push({ label: 'Knowledge', state: 'active', detail: 'testing reuse' });
    if (kind === 'later') history.push({ label: 'Reuse', state: 'active', detail: 'new claim' });
    if (next && !completed.includes(next.id)) history.push({ label: next.label, state: 'next', detail: 'next' });
    const mission = missionFor(run, stage, kind);
    rail.innerHTML = `
      <div class="v19-team-mission">
        <span class="v19-team-mark" aria-hidden="true">CP</span>
        <div><small>Orchestrator request</small><strong>${esc(mission)}</strong></div>
        <span class="v19-context-count">${contributed.length} grounded artifact${contributed.length === 1 ? '' : 's'} shared</span>
      </div>
      <ol class="v19-team-history">${history.map(item => `<li data-state="${esc(item.state)}" title="${esc(item.detail)}">${esc(item.label)} · ${esc(item.detail)}</li>`).join('')}</ol>`;
  }

  function runProcess(run) {
    return run?.result?.process || run?.process || null;
  }

  function runChecklist(run) {
    return run?.result?.checklist || run?.checklist || null;
  }

  function decorateProcessNodes(canvas, run) {
    const process = runProcess(run);
    const checklist = runChecklist(run);
    if (!process || !canvas.querySelector('.process-layout')) return;
    const evidence = checklist?.items || [];
    for (const node of process.nodes || []) {
      const button = canvas.querySelector(`.process-node-button[data-node-id="${CSS.escape(node.node_id)}"]`);
      const container = button?.closest('.process-node');
      if (!button || !container) continue;
      container.dataset.v19HasLaw = String(Boolean(node.legal_source_ids?.length));
      let signals = button.querySelector('.v19-node-signals');
      if (!signals) {
        signals = document.createElement('span');
        signals.className = 'v19-node-signals';
        signals.setAttribute('aria-hidden', 'true');
        button.append(signals);
      }
      const items = evidence.filter(item => {
        const owners = Array.isArray(item.node_ids) && item.node_ids.length ? item.node_ids : item.node_id ? [item.node_id] : [];
        return owners.includes(node.node_id);
      });
      const missing = items.filter(item => ['missing', 'provided_insufficient'].includes(item.status)).length;
      const conditional = items.filter(item => item.status === 'conditional').length;
      const available = items.filter(item => item.status === 'provided_sufficient').length;
      const evidenceState = missing ? 'missing' : conditional ? 'conditional' : available ? 'available' : '';
      const evidenceText = missing ? `${missing} needed` : conditional ? `${conditional} conditional` : available ? `${available} ready` : '';
      signals.innerHTML = `${node.legal_source_ids?.length ? `<span class="v19-node-signal" data-kind="law" title="${node.legal_source_ids.length} legal source${node.legal_source_ids.length === 1 ? '' : 's'} linked">§${node.legal_source_ids.length}</span>` : ''}${items.length ? `<span class="v19-node-signal" data-kind="evidence" data-state="${evidenceState}" title="${items.length} process-grounded evidence relationship${items.length === 1 ? '' : 's'}">${esc(evidenceText || `${items.length} evidence`)}</span>` : ''}`;
    }
  }

  function progressiveGraph(canvas) {
    const stage = activeStage(canvas);
    const layout = canvas.querySelector('.process-layout');
    if (!layout || !['process', 'evidence', 'experience'].includes(stage?.id)) return;
    for (const id of ['escalation', 'resolution']) {
      layout.querySelector(`[data-node-id="${id}"]`)?.closest('.process-node')?.classList.add('v19-deferred');
    }
    let toggle = layout.querySelector('.v19-later-toggle');
    if (!toggle) {
      const remedy = layout.querySelector('[data-node-id="remedy"]')?.closest('.process-node');
      if (!remedy) return;
      toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'v19-later-toggle';
      toggle.textContent = '2 later stages · escalation and closure';
      remedy.after(toggle);
      toggle.addEventListener('click', () => {
        const expanded = layout.dataset.laterExpanded === 'true';
        layout.dataset.laterExpanded = String(!expanded);
        toggle.textContent = expanded ? '2 later stages · escalation and closure' : 'Hide later stages';
      });
    }
  }

  function traceSource(event) {
    const trigger = event.target.closest?.('[data-source-ref]');
    if (!trigger) return;
    const artifactId = trigger.dataset.sourceRef;
    if (!artifactId) return;
    const row = document.querySelector(`.attachment-row[data-artifact-id="${CSS.escape(artifactId)}"]`);
    if (!row) return;
    document.querySelectorAll('.attachment-row.v19-source-pulse').forEach(item => item.classList.remove('v19-source-pulse'));
    document.querySelectorAll('.v19-source-origin').forEach(item => item.remove());
    row.classList.add('v19-source-pulse');
    const note = document.createElement('span');
    note.className = 'v19-source-origin';
    note.textContent = 'This conclusion opens its original customer evidence.';
    row.append(note);
    window.setTimeout(() => {
      row.classList.remove('v19-source-pulse');
      note.remove();
    }, 2300);
  }

  function reviewMode(form) {
    return form?.querySelector('input[name="building_envelope_mode"]:checked')?.value || 'conditional';
  }

  function renderReviewGraphPreview(canvas) {
    const form = canvas.querySelector('#reviewForm');
    const graph = canvas.querySelector('.review-graph');
    const node = graph?.querySelector('[data-node-id="causation"]')?.closest('.process-node');
    if (!form || !graph || !node) return;
    let preview = node.querySelector('.v19-review-branch-preview');
    if (!preview) {
      preview = document.createElement('section');
      preview.className = 'v19-review-branch-preview';
      preview.setAttribute('aria-live', 'polite');
      const button = node.querySelector('.process-node-button');
      button?.after(preview);
    }
    const mode = reviewMode(form);
    graph.dataset.v19ReviewMode = mode;
    preview.dataset.mode = mode;
    const steps = mode === 'conditional'
      ? ['Neutral assessment first', 'Test ventilation allegation only if supported', 'Broader building testing stays conditional']
      : ['Neutral assessment', 'Request broader building testing now', 'Responsibility still waits for causation'];
    preview.innerHTML = `<small>Process preview after this simulated choice</small><div class="v19-review-path">${steps.map(step => `<span>${esc(step)}</span>`).join('')}</div>`;
    if (form.dataset.v19ReviewBound !== 'true') {
      form.dataset.v19ReviewBound = 'true';
      form.addEventListener('change', event => {
        if (event.target.matches('input[name="building_envelope_mode"]')) requestAnimationFrame(() => renderReviewGraphPreview(canvas));
      });
    }
  }

  function directProductCopy(canvas) {
    const rail = canvas.querySelector('.v18-ready-artifacts:not([data-v19-product-copy="true"])');
    if (rail) {
      const articles = [...rail.querySelectorAll('article')];
      const copy = [
        ['Handling process', 'The claim is mapped from intake to closure. Causation is the current decision.'],
        ['Evidence linked to decisions', 'Every decision carries the facts and evidence needed to resolve it.'],
        ['Organizational experience', 'Generated reference patterns and governed memory records appear at the branch where they help and remain labelled by provenance.'],
      ];
      articles.forEach((article, index) => {
        if (!copy[index]) return;
        const strong = article.querySelector('strong');
        const paragraph = article.querySelector('p');
        if (strong) strong.textContent = copy[index][0];
        if (paragraph) paragraph.textContent = copy[index][1];
      });
      rail.dataset.v19ProductCopy = 'true';
    }
    const build = canvas.querySelector('.v17-build-state[data-v18-backed="true"]');
    if (build && build.dataset.v19ProductCopy !== 'true') {
      const stage = activeStage(canvas)?.id;
      const copy = {
        process: 'The complete handling spine and its causation alternatives passed the graph validator.',
        evidence: 'Every evidence requirement points back to the decision, fact, and reason that created it.',
        experience: 'Generated reference patterns or governed memory records were returned for the unresolved branch and labelled by provenance.',
        verify: 'Graph integrity, legal links, evidence traceability, and no-repeat requests passed.',
      }[stage];
      if (copy && build.querySelector('p')) build.querySelector('p').textContent = copy;
      build.dataset.v19ProductCopy = 'true';
    }
  }

  async function supportBoundary(canvas, run) {
    const boundary = canvas.querySelector('.v18-memory-boundary');
    if (!boundary || canvas.querySelector('.v19-support-meter')) return;
    const candidate = run?.candidate || run?.result?.knowledge_update || {};
    const supported = Number(candidate.support_count);
    const required = Number(candidate.required_support);
    if (!Number.isFinite(supported) || !Number.isFinite(required) || required < 1) return;
    const meter = document.createElement('section');
    meter.className = 'v19-support-meter';
    meter.innerHTML = `<div><small>Potential reusable process change</small><strong>${Math.min(supported, required)} of ${required} support records were returned for the same evidence-order rule.</strong></div><div class="v19-support-dots" aria-label="${Math.min(supported, required)} of ${required} support records">${Array.from({ length: required }, (_, index) => `<i data-supported="${index < supported}">${index < supported ? '✓' : index + 1}</i>`).join('')}</div>`;
    boundary.after(meter);
  }

  async function enhance() {
    const canvas = document.querySelector('#stageCanvas');
    if (!canvas) return;
    const run = await currentRun();
    renderTeamRail(canvas, run);
    decorateProcessNodes(canvas, run);
    progressiveGraph(canvas);
    renderReviewGraphPreview(canvas);
    directProductCopy(canvas);
    if (journeyKind(canvas) === 'knowledge') await supportBoundary(canvas, await currentRun({ first: true, fresh: true }));
  }

  function queue() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(async () => {
      scheduled = false;
      await enhance();
    });
  }

  function boot() {
    ensureAssets();
    document.addEventListener('click', traceSource, true);
    const observer = new MutationObserver(queue);
    for (const target of [document.querySelector('#agentProgress'), document.querySelector('#stageCanvas'), document.querySelector('#auditDrawer'), document.querySelector('.submission-pane')]) {
      if (target) observer.observe(target, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'hidden', 'open', 'aria-selected'] });
    }
    window.addEventListener('casepath:render', queue);
    queue();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
