(() => {
  'use strict';

  const store = window.__CASEPATH_PROCESS_EXPLAINER__ = {
    run: null,
    result: null,
    review: null,
  };

  const originalFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const response = await originalFetch(...args);
    try {
      const request = args[0];
      const options = args[1] || {};
      const url = typeof request === 'string' ? request : request?.url || '';
      const method = String(options.method || request?.method || 'GET').toUpperCase();
      const contentType = response.headers.get('content-type') || '';
      if (response.ok && contentType.includes('application/json')) {
        if (/\/api\/runs\/[^/]+$/.test(url) && method === 'GET') {
          response.clone().json().then(payload => {
            store.run = payload;
            if (payload?.result) store.result = payload.result;
            scheduleEnhancement();
          }).catch(() => {});
        } else if (/\/api\/runs\/[^/]+\/review$/.test(url) && method === 'POST') {
          response.clone().json().then(payload => {
            store.review = payload;
            if (payload?.result) store.result = payload.result;
            scheduleEnhancement();
          }).catch(() => {});
        }
      }
    } catch (_) {}
    return response;
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = (value = '') => String(value).replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[character]));

  let enhancementScheduled = false;
  function scheduleEnhancement() {
    if (enhancementScheduled) return;
    enhancementScheduled = true;
    requestAnimationFrame(() => {
      enhancementScheduled = false;
      enhanceCurrentView();
    });
  }

  function result() {
    return store.result || store.run?.result || null;
  }

  function currentNode(data = result()) {
    if (!data?.process?.nodes?.length) return null;
    return data.process.nodes.find(node => node.node_id === data.process.current_node)
      || data.process.nodes.find(node => node.state === 'current')
      || data.process.nodes[0];
  }

  function currentStep() {
    return Number($('#guideStepNumber')?.textContent || 0);
  }

  function completedNode(node, index, currentIndex) {
    return ['complete', 'supported'].includes(node.state) || index < currentIndex;
  }

  function statusLabel(node, index, currentIndex) {
    if (node.node_id === currentNode()?.node_id || node.state === 'current') return 'Current question';
    if (completedNode(node, index, currentIndex)) return 'Established';
    if (node.state === 'blocked') return 'Waits for the current answer';
    if (node.state === 'next') return 'Next if relevant';
    return 'Not reached yet';
  }

  function statusClass(node, index, currentIndex) {
    if (node.node_id === currentNode()?.node_id || node.state === 'current') return 'current';
    if (completedNode(node, index, currentIndex)) return 'complete';
    if (node.state === 'blocked') return 'blocked';
    if (node.state === 'next') return 'next';
    return 'pending';
  }

  function processEvent(stage) {
    const events = store.run?.events || [];
    return [...events].reverse().find(event => event.stage === stage && event.status === 'completed')
      || [...events].reverse().find(event => event.stage === stage)
      || null;
  }

  function processMetrics(data) {
    const facts = data?.facts || [];
    const legalSources = data?.legal_research?.sources || [];
    const legalQuestions = data?.legal_research?.questions || [];
    const nodes = data?.process?.nodes || [];
    const present = data?.checklist?.present || [];
    const required = data?.checklist?.required || [];
    return {
      facts: facts.length,
      legalSources: legalSources.length,
      legalQuestions: legalQuestions.length,
      nodes: nodes.length,
      present: present.length,
      required: required.length,
      open: required.filter(item => ['still_needed', 'conditional', 'insufficient'].includes(item.status)).length,
    };
  }

  function processOriginHtml(data) {
    const metrics = processMetrics(data);
    const process = processEvent('process');
    const validationLabel = process?.validator || data?.process?.validator?.valid === true ? 'Validated graph' : 'Graph proposal';
    return `
      <section class="mvp-origin" aria-labelledby="mvpOriginTitle">
        <div class="mvp-section-heading">
          <div><p>How the process was built</p><h3 id="mvpOriginTitle">Evidence and law become decision questions.</h3></div>
          <span>${escapeHtml(validationLabel)}</span>
        </div>
        <div class="mvp-origin-chain">
          <div class="mvp-origin-step">
            <small>1 · Sources</small>
            <strong>${metrics.facts} source-grounded facts</strong>
            <span>Accepted from the message and attachments</span>
          </div>
          <span class="mvp-origin-arrow" aria-hidden="true">→</span>
          <div class="mvp-origin-step">
            <small>2 · Law</small>
            <strong>${metrics.legalQuestions || metrics.legalSources} handling questions</strong>
            <span>Shaped by ${metrics.legalSources} retrieved source records</span>
          </div>
          <span class="mvp-origin-arrow" aria-hidden="true">→</span>
          <div class="mvp-origin-step">
            <small>3 · Process</small>
            <strong>${metrics.nodes} claim-specific decisions</strong>
            <span>Proposed from the accepted claim state</span>
          </div>
          <span class="mvp-origin-arrow" aria-hidden="true">→</span>
          <div class="mvp-origin-step emphasis">
            <small>4 · Current</small>
            <strong>${escapeHtml(currentNode(data)?.title || 'Current process question')}</strong>
            <span>The first unresolved decision on the selected path</span>
          </div>
        </div>
      </section>`;
  }

  function branchesHtml(node, expanded = false) {
    const branches = node?.branches || [];
    if (!branches.length) return '';
    return `
      <div class="mvp-branch-fork" data-expanded="${expanded ? 'true' : 'false'}">
        <button type="button" class="mvp-branch-toggle" aria-expanded="${expanded ? 'true' : 'false'}">
          <span>${branches.length} possible outcomes from this question</span>
          <strong>${expanded ? 'Hide outcomes' : 'Show outcomes'}</strong>
        </button>
        <div class="mvp-branch-grid" ${expanded ? '' : 'hidden'}>
          ${branches.map(branch => `
            <div class="mvp-branch-card">
              <span class="mvp-branch-dot"></span>
              <div><strong>${escapeHtml(branch.label)}</strong><p>${escapeHtml(branch.detail || branch.next || branch.state || 'Possible branch')}</p></div>
            </div>`).join('')}
        </div>
      </div>`;
  }

  function processGraphHtml(data, options = {}) {
    const nodes = data?.process?.nodes || [];
    const current = currentNode(data);
    const currentIndex = Math.max(0, nodes.findIndex(node => node.node_id === current?.node_id));
    const selectedId = options.selectedId || current?.node_id;
    const allNodes = options.allNodes !== false;
    const visibleNodes = allNodes ? nodes : nodes.filter((node, index) => index <= currentIndex + 1);
    return `
      <section class="mvp-graph-section" aria-labelledby="mvpGraphTitle">
        <div class="mvp-section-heading graph-heading">
          <div><p>Claim-specific process graph</p><h3 id="mvpGraphTitle">The selected path, current decision, and what depends on it.</h3></div>
          <span>${nodes.filter((node, index) => completedNode(node, index, currentIndex)).length} of ${nodes.length} established</span>
        </div>
        <div class="mvp-process-graph" role="list">
          ${visibleNodes.map((node, index) => {
            const originalIndex = nodes.indexOf(node);
            const status = statusClass(node, originalIndex, currentIndex);
            const isCurrent = node.node_id === current?.node_id;
            return `
              <div class="mvp-graph-step ${status}${node.node_id === selectedId ? ' selected' : ''}" role="listitem" data-mvp-node-row="${escapeHtml(node.node_id)}">
                <span class="mvp-connector" aria-hidden="true"></span>
                <button type="button" class="mvp-node" data-mvp-node="${escapeHtml(node.node_id)}" aria-current="${isCurrent ? 'step' : 'false'}">
                  <span class="mvp-node-marker">${status === 'complete' ? '✓' : isCurrent ? '?' : originalIndex + 1}</span>
                  <span class="mvp-node-copy">
                    <small>${escapeHtml(statusLabel(node, originalIndex, currentIndex))}</small>
                    <strong>${escapeHtml(node.title)}</strong>
                    <span>${escapeHtml(node.question || node.answer || '')}</span>
                  </span>
                  <span class="mvp-node-open">Why?</span>
                </button>
                ${isCurrent ? branchesHtml(node, options.expandBranches === true) : ''}
              </div>`;
          }).join('')}
        </div>
      </section>`;
  }

  function factsForNode(data, node) {
    const ids = new Set(node?.fact_ids || []);
    return (data?.facts || []).filter(fact => ids.has(fact.fact_id));
  }

  function checklistForNode(data, node) {
    const present = (data?.checklist?.present || []).filter(item => item.node_id === node?.node_id);
    const required = (data?.checklist?.required || []).filter(item => item.node_id === node?.node_id);
    return { present, required, all: [...present, ...required] };
  }

  function readableStatus(item, present = false) {
    if (present) return 'Already provided';
    const status = item?.status || 'still_needed';
    if (status === 'conditional') return 'Required only if…';
    if (status === 'insufficient') return 'Provided but insufficient';
    if (status === 'present') return 'Already provided';
    return 'Still needed';
  }

  function checklistStatusClass(item, present = false) {
    if (present || item?.status === 'present') return 'provided';
    if (item?.status === 'conditional') return 'conditional';
    if (item?.status === 'insufficient') return 'insufficient';
    return 'needed';
  }

  function factSummaryHtml(facts) {
    if (!facts.length) return '<p class="mvp-empty">No separate fact record is linked to this node.</p>';
    return `<div class="mvp-fact-list">${facts.map(fact => `
      <div class="mvp-fact ${escapeHtml(fact.state || 'known')}">
        <span></span>
        <div><strong>${escapeHtml(fact.label)}</strong><p>${escapeHtml(fact.value)} — ${escapeHtml(fact.explanation)}</p></div>
        ${(fact.source_refs || [])[0] ? `<button type="button" data-mvp-artifact="${escapeHtml(fact.source_refs[0].artifact_id)}" data-page="${escapeHtml(fact.source_refs[0].page || 1)}">Source</button>` : ''}
      </div>`).join('')}</div>`;
  }

  function checklistRowsHtml(items, presentIds = new Set()) {
    if (!items.length) return '<p class="mvp-empty">No evidence item is linked to this process question.</p>';
    return `<div class="mvp-checklist-rows">${items.map(item => {
      const isPresent = presentIds.has(item);
      const status = checklistStatusClass(item, isPresent);
      const nodeTitle = (result()?.process?.nodes || []).find(node => node.node_id === item.node_id)?.title || item.node_id || 'Current question';
      return `
        <div class="mvp-checklist-row ${status}">
          <span class="mvp-status-mark"></span>
          <div class="mvp-checklist-copy">
            <div class="mvp-checklist-title"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(readableStatus(item, isPresent))}</span></div>
            <p>${escapeHtml(item.why || 'This evidence is linked to the selected process question.')}</p>
            <small>Process node: ${escapeHtml(nodeTitle)}</small>
          </div>
          ${item.artifact_id ? `<button type="button" data-mvp-artifact="${escapeHtml(item.artifact_id)}">Open</button>` : ''}
        </div>`;
    }).join('')}</div>`;
  }

  function checklistDerivationHtml(data) {
    const node = currentNode(data);
    const facts = factsForNode(data, node);
    const checklist = checklistForNode(data, node);
    const presentSet = new Set(checklist.present);
    const metrics = processMetrics(data);
    return `
      <section class="mvp-checklist-derivation" aria-labelledby="mvpChecklistTitle">
        <div class="mvp-section-heading">
          <div><p>How the checklist was derived</p><h3 id="mvpChecklistTitle">The open process question creates the evidence request.</h3></div>
          <span>${checklist.present.length} present · ${checklist.required.length} open</span>
        </div>
        <div class="mvp-derivation-flow">
          <div class="mvp-derivation-step process">
            <small>1 · Process question</small>
            <strong>${escapeHtml(node?.question || data?.current_blocker || 'Current question')}</strong>
            <span>${escapeHtml(node?.why || 'The next action depends on this answer.')}</span>
          </div>
          <span class="mvp-derivation-arrow" aria-hidden="true">↓</span>
          <div class="mvp-derivation-step fact">
            <small>2 · Facts the process needs</small>
            ${factSummaryHtml(facts)}
          </div>
          <span class="mvp-derivation-arrow" aria-hidden="true">↓</span>
          <div class="mvp-derivation-step evidence">
            <small>3 · Evidence capable of resolving those facts</small>
            ${checklistRowsHtml(checklist.all, presentSet)}
          </div>
          <span class="mvp-derivation-arrow" aria-hidden="true">↓</span>
          <div class="mvp-derivation-step output">
            <small>4 · Aggregated document checklist</small>
            <strong>${metrics.present} available · ${metrics.open} still needed or conditional</strong>
            <span>Each item keeps its process node, reason, and current evidence state.</span>
          </div>
        </div>
      </section>`;
  }

  function enhanceProcessStage(root, data) {
    const inner = $('.guide-stage-inner', root);
    if (!inner || inner.querySelector('.mvp-origin')) return;
    $('.path-preview', inner)?.remove();
    const lede = $('.stage-lede', inner);
    if (lede) lede.textContent = 'CasePath did not select a generic mould workflow. It combined source-grounded facts with retrieved legal questions, proposed a claim-specific graph, and passed that graph through deterministic validation.';
    inner.insertAdjacentHTML('beforeend', processOriginHtml(data) + processGraphHtml(data, { allNodes: true }));
    const detail = $('#guideDetail');
    if (detail) detail.textContent = 'Open the full process graph';
    bindEnhancedInteractions(inner);
  }

  function enhanceChecklistStage(root, data) {
    const inner = $('.guide-stage-inner', root);
    if (!inner || inner.querySelector('.mvp-checklist-derivation')) return;
    $('.reason-chain', inner)?.remove();
    $('.evidence-focus', inner)?.remove();
    const lede = $('.stage-lede', inner);
    if (lede) lede.textContent = 'The checklist is compiled from the open process node. CasePath asks for evidence only when it can establish a fact that the process still needs.';
    inner.insertAdjacentHTML('beforeend', checklistDerivationHtml(data));
    const detail = $('#guideDetail');
    if (detail) detail.textContent = 'Open the process-linked checklist';
    bindEnhancedInteractions(inner);
  }

  function enhanceAnalysisSummary(data) {
    const analysis = $('#analysis');
    const live = $('#analysisLive');
    if (!analysis?.classList.contains('is-complete') || !live || live.dataset.mvpSummary === 'true') return;
    const metrics = processMetrics(data);
    live.dataset.mvpSummary = 'true';
    live.innerHTML = `
      <span class="live-mark" aria-hidden="true"><i></i></span>
      <div class="mvp-complete-copy">
        <strong>Process graph and evidence model ready</strong>
        <p>${metrics.nodes} decision nodes validated · ${metrics.present + metrics.required} evidence items linked to the process · ${metrics.open} still open.</p>
      </div>`;
  }

  function nodeContextHtml(data, node) {
    const facts = factsForNode(data, node);
    const checklist = checklistForNode(data, node);
    const presentSet = new Set(checklist.present);
    const lawSources = data?.legal_research?.sources || [];
    return `
      <section class="mvp-node-context">
        <div class="mvp-context-question">
          <p>Selected process node</p>
          <h3>${escapeHtml(node.title)}</h3>
          <strong>${escapeHtml(node.question || '')}</strong>
          <span>${escapeHtml(node.why || '')}</span>
        </div>
        <div class="mvp-context-grid">
          <section><h4>Facts used by this node</h4>${factSummaryHtml(facts)}</section>
          <section><h4>Evidence linked to this node</h4>${checklistRowsHtml(checklist.all, presentSet)}</section>
        </div>
        ${node.node_id === currentNode(data)?.node_id ? `<section class="mvp-law-context"><h4>Legal sources shaping the current handling question</h4><div>${lawSources.map(source => `<article><strong>${escapeHtml(source.title)}</strong><p>${escapeHtml(source.role)}</p><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener">Open source</a></article>`).join('')}</div></section>` : ''}
      </section>`;
  }

  function setDetail(kind, title, intro, html) {
    const dialog = $('#detailDialog');
    if (!dialog) return;
    $('#detailKind').textContent = kind;
    $('#detailTitle').textContent = title;
    $('#detailIntro').textContent = intro;
    $('#detailContent').innerHTML = html;
    bindEnhancedInteractions($('#detailContent'));
    if (!dialog.open) dialog.showModal();
  }

  function openProcessDetail(nodeId = null) {
    const data = result();
    if (!data) return;
    const node = data.process.nodes.find(item => item.node_id === nodeId) || currentNode(data);
    setDetail(
      'Process graph',
      'How CasePath built this claim-specific path',
      'Source-grounded facts and retrieved legal questions become process nodes. The validator then checks that the selected path is connected and that unknown facts are not treated as resolved.',
      processOriginHtml(data) + processGraphHtml(data, { allNodes: true, expandBranches: true, selectedId: node.node_id }) + nodeContextHtml(data, node) + validatorHtml(data)
    );
  }

  function validatorHtml(data) {
    const processChecks = data?.process?.validator?.checks || [];
    const processEventRecord = processEvent('process');
    const evidenceEventRecord = processEvent('evidence');
    return `
      <section class="mvp-validation">
        <div class="mvp-section-heading"><div><p>Acceptance boundary</p><h3>What was checked before the graph and checklist became canonical.</h3></div><span>Deterministic</span></div>
        <div class="mvp-validation-grid">
          <article><small>Process proposal</small><strong>${escapeHtml(processEventRecord?.agent || 'Process Graph Agent')}</strong><p>${escapeHtml(processEventRecord?.headline || 'Claim-specific path proposed')}</p></article>
          <article><small>Graph validator</small><strong>${escapeHtml(processEventRecord?.validator || 'Process validator')}</strong><ul>${processChecks.map(check => `<li>${escapeHtml(check)}</li>`).join('')}</ul></article>
          <article><small>Checklist proposal</small><strong>${escapeHtml(evidenceEventRecord?.agent || 'Document Checklist Agent')}</strong><p>${escapeHtml(evidenceEventRecord?.headline || 'Evidence requirements derived')}</p></article>
          <article><small>Checklist validator</small><strong>${escapeHtml(evidenceEventRecord?.validator || 'Checklist validator')}</strong><p>Every request retains its process node, reason, and evidence state.</p></article>
        </div>
      </section>`;
  }

  function openChecklistDetail() {
    const data = result();
    if (!data) return;
    const nodes = data.process?.nodes || [];
    const currentIndex = nodes.findIndex(item => item.node_id === currentNode(data)?.node_id);
    const sections = nodes.map(node => {
      const linked = checklistForNode(data, node);
      if (!linked.all.length) return '';
      return `
        <section class="mvp-node-checklist">
          <div class="mvp-node-checklist-head"><span>${escapeHtml(statusLabel(node, nodes.indexOf(node), currentIndex))}</span><h3>${escapeHtml(node.title)}</h3><p>${escapeHtml(node.question || '')}</p></div>
          ${checklistRowsHtml(linked.all, new Set(linked.present))}
        </section>`;
    }).filter(Boolean).join('');
    const metrics = processMetrics(data);
    setDetail(
      'Process → evidence → documents',
      'The complete process-linked checklist',
      'This is an aggregation of evidence requirements created by process nodes—not a category-level list attached to a mould claim.',
      checklistDerivationHtml(data) + `<section class="mvp-all-checklist"><div class="mvp-section-heading"><div><p>All process nodes</p><h3>Where every document requirement came from.</h3></div><span>${metrics.present + metrics.required} items</span></div>${sections}</section>` + validatorHtml(data)
    );
  }

  function bindEnhancedInteractions(root) {
    if (!root) return;
    $$('[data-mvp-node]', root).forEach(button => {
      if (button.dataset.mvpBound === 'true') return;
      button.dataset.mvpBound = 'true';
      button.addEventListener('click', () => openProcessDetail(button.dataset.mvpNode));
    });
    $$('.mvp-branch-toggle', root).forEach(button => {
      if (button.dataset.mvpBound === 'true') return;
      button.dataset.mvpBound = 'true';
      button.addEventListener('click', event => {
        event.stopPropagation();
        const fork = button.closest('.mvp-branch-fork');
        const grid = $('.mvp-branch-grid', fork);
        const expanded = button.getAttribute('aria-expanded') === 'true';
        button.setAttribute('aria-expanded', String(!expanded));
        $('strong', button).textContent = expanded ? 'Show outcomes' : 'Hide outcomes';
        grid.hidden = expanded;
        fork.dataset.expanded = String(!expanded);
      });
    });
    $$('[data-mvp-artifact]', root).forEach(button => {
      if (button.dataset.mvpBound === 'true') return;
      button.dataset.mvpBound = 'true';
      button.addEventListener('click', event => {
        event.stopPropagation();
        const artifactId = button.dataset.mvpArtifact;
        const sourceButton = $(`#attachmentList [data-artifact-id="${CSS.escape(artifactId)}"]`);
        if (sourceButton) sourceButton.click();
      });
    });
  }

  function enhanceCurrentView() {
    const data = result();
    if (!data) return;
    enhanceAnalysisSummary(data);
    const root = $('#guideStage');
    if (!root) return;
    const step = currentStep();
    if (step === 3) enhanceProcessStage(root, data);
    if (step === 5) enhanceChecklistStage(root, data);
  }

  function installDetailInterceptor() {
    document.addEventListener('click', event => {
      const detailButton = event.target.closest?.('#guideDetail');
      if (!detailButton) return;
      const step = currentStep();
      if (step === 3 || step === 5) {
        event.preventDefault();
        event.stopImmediatePropagation();
        if (step === 3) openProcessDetail();
        else openChecklistDetail();
      }
    }, true);
  }

  function start() {
    installDetailInterceptor();
    const guide = $('#guide');
    const analysis = $('#analysis');
    if (guide) new MutationObserver(scheduleEnhancement).observe(guide, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['hidden'] });
    if (analysis) new MutationObserver(scheduleEnhancement).observe(analysis, { childList: true, subtree: true, attributes: true, attributeFilter: ['class', 'hidden'] });
    scheduleEnhancement();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
