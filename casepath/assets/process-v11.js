(() => {
  'use strict';

  const ROOT_ID = 'processPath';
  let observer;
  let rebuilding = false;
  let zoom = 1;

  const q = (selector, root = document) => root.querySelector(selector);
  const qa = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = (value = '') => String(value).replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[character]));

  function statusOf(element) {
    return ['complete', 'supported', 'current', 'next', 'blocked']
      .find(status => element.classList.contains(status)) || 'pending';
  }

  function collectNodes(root) {
    return qa(':scope > .process-node', root).map((element, index) => {
      const title = q('h4', element)?.textContent?.trim() || `Process step ${index + 1}`;
      const answer = q('p', element)?.textContent?.trim() || '';
      const branches = qa('.branch', element).map((branch, branchIndex) => ({
        label: q('strong', branch)?.textContent?.trim() || `Outcome ${branchIndex + 1}`,
        detail: q('small', branch)?.textContent?.trim() || 'Requires review',
      }));
      return {
        id: element.dataset.nodeId || `step-${index + 1}`,
        title,
        answer,
        status: statusOf(element),
        index,
        branches,
        sourceElement: element,
      };
    });
  }

  function stageRail() {
    const stages = ['Intake', 'Scope', 'Dispute', 'Process', 'Evidence', 'Decision', 'Resolution'];
    const mappedCurrent = 3;
    return `
      <ol class="cp-stage-rail" aria-label="Claim handling progress">
        ${stages.map((label, index) => {
          const status = index < mappedCurrent ? 'done' : index === mappedCurrent ? 'current' : 'pending';
          return `<li class="${status}"><span>${status === 'done' ? '✓' : index + 1}</span><strong>${label}</strong>${status === 'current' ? '<small>Current</small>' : ''}</li>`;
        }).join('')}
      </ol>`;
  }

  function nodeCard(node, position, currentIndex) {
    const completed = node.status === 'complete' || node.status === 'supported' || position < currentIndex;
    const isCurrent = node.status === 'current' || position === currentIndex;
    const stateClass = completed ? 'is-complete' : isCurrent ? 'is-current' : node.status === 'blocked' ? 'is-blocked' : 'is-future';
    const stateLabel = completed ? 'Completed' : isCurrent ? 'Current question' : node.status === 'blocked' ? 'Blocked' : 'Pending';
    return `
      <div class="cp-graph-step ${stateClass}" data-node-id="${escapeHtml(node.id)}">
        <button class="cp-graph-node" type="button" data-cp-node="${escapeHtml(node.id)}" aria-label="Open ${escapeHtml(node.title)}">
          <span class="cp-node-number">${completed ? '✓' : position + 1}</span>
          <span class="cp-node-copy">
            <strong>${escapeHtml(node.title)}</strong>
            ${node.answer ? `<small>${escapeHtml(node.answer)}</small>` : ''}
          </span>
          <span class="cp-node-state">${stateLabel}</span>
        </button>
      </div>`;
  }

  function branchFork(currentNode) {
    if (!currentNode?.branches?.length) return '';
    return `
      <div class="cp-branch-fork" data-expanded="false">
        <button class="cp-branch-toggle" type="button" aria-expanded="false">
          <span>${currentNode.branches.length} possible outcomes</span>
          <strong>Show decision branches</strong>
        </button>
        <div class="cp-branch-grid" hidden>
          ${currentNode.branches.map((branch, index) => `
            <div class="cp-branch-card ${index === 0 ? 'preferred' : index === currentNode.branches.length - 1 ? 'risk' : ''}">
              <span>${index + 1}</span>
              <strong>${escapeHtml(branch.label)}</strong>
              <small>${escapeHtml(branch.detail)}</small>
            </div>`).join('')}
        </div>
      </div>`;
  }

  function buildGraph(root) {
    const nodes = collectNodes(root);
    if (!nodes.length) return;

    const previousGraph = q(':scope > .cp-process-graph', root);
    if (previousGraph) previousGraph.remove();

    const explicitCurrent = nodes.findIndex(node => node.status === 'current');
    let lastComplete = -1;
    nodes.forEach((node, index) => { if (node.status === 'complete' || node.status === 'supported') lastComplete = index; });
    const currentIndex = explicitCurrent >= 0 ? explicitCurrent : Math.min(nodes.length - 1, lastComplete + 1);
    const completedCount = nodes.filter((node, index) => node.status === 'complete' || node.status === 'supported' || index < currentIndex).length;
    const currentNode = nodes[currentIndex];

    const graph = document.createElement('section');
    graph.className = 'cp-process-graph';
    graph.innerHTML = `
      <header class="cp-process-header">
        <div>
          <h4>Claim handling process</h4>
          <p><strong>${completedCount}</strong> of <strong>${nodes.length}</strong> decisions established</p>
        </div>
        <div class="cp-process-tools" aria-label="Process graph controls">
          <button type="button" data-cp-zoom="out" aria-label="Zoom out">−</button>
          <output aria-live="polite">100%</output>
          <button type="button" data-cp-zoom="in" aria-label="Zoom in">+</button>
          <button type="button" data-cp-zoom="reset">Reset</button>
        </div>
      </header>
      ${stageRail()}
      <div class="cp-graph-viewport" tabindex="0" aria-label="Interactive claim process graph">
        <div class="cp-graph-canvas" style="--cp-graph-scale:1">
          ${nodes.slice(0, currentIndex + 1).map((node, index) => nodeCard(node, index, currentIndex)).join('')}
          ${branchFork(currentNode)}
          ${nodes.slice(currentIndex + 1).map((node, offset) => nodeCard(node, currentIndex + 1 + offset, currentIndex)).join('')}
        </div>
      </div>
      <footer class="cp-process-legend" aria-label="Process status legend">
        <span><i class="complete"></i>Completed</span>
        <span><i class="current"></i>Current</span>
        <span><i class="pending"></i>Pending</span>
        <span><i class="blocked"></i>Blocked or alternative</span>
      </footer>`;

    root.classList.add('cp-enhanced');
    root.appendChild(graph);

    qa('[data-cp-node]', graph).forEach(button => {
      button.addEventListener('click', () => {
        const id = button.dataset.cpNode;
        const original = q(`:scope > .process-node [data-select-node="${CSS.escape(id)}"]`, root);
        original?.click();
        qa('.cp-graph-step', graph).forEach(step => step.classList.toggle('is-selected', step.dataset.nodeId === id));
        const evidence = document.getElementById('evidenceColumn');
        if (evidence && window.matchMedia('(max-width: 900px)').matches) {
          evidence.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      });
    });

    const toggle = q('.cp-branch-toggle', graph);
    if (toggle) {
      toggle.addEventListener('click', () => {
        const fork = toggle.closest('.cp-branch-fork');
        const expanded = fork.dataset.expanded === 'true';
        fork.dataset.expanded = String(!expanded);
        toggle.setAttribute('aria-expanded', String(!expanded));
        q('.cp-branch-grid', fork).hidden = expanded;
        q('strong', toggle).textContent = expanded ? 'Show decision branches' : 'Hide decision branches';
      });
    }

    const viewport = q('.cp-graph-viewport', graph);
    const canvas = q('.cp-graph-canvas', graph);
    const output = q('.cp-process-tools output', graph);
    qa('[data-cp-zoom]', graph).forEach(button => {
      button.addEventListener('click', () => {
        const action = button.dataset.cpZoom;
        zoom = action === 'in' ? Math.min(1.25, zoom + 0.1) : action === 'out' ? Math.max(0.75, zoom - 0.1) : 1;
        canvas.style.setProperty('--cp-graph-scale', zoom.toFixed(2));
        output.value = `${Math.round(zoom * 100)}%`;
        output.textContent = `${Math.round(zoom * 100)}%`;
        if (action === 'reset') viewport.scrollTo({ left: 0, top: 0, behavior: 'smooth' });
      });
    });
  }

  function scheduleBuild(root) {
    if (rebuilding) return;
    rebuilding = true;
    requestAnimationFrame(() => {
      try { buildGraph(root); } finally { rebuilding = false; }
    });
  }

  function start() {
    const root = document.getElementById(ROOT_ID);
    if (!root) return;
    observer = new MutationObserver(records => {
      const externalMutation = records.some(record => !record.target.closest?.('.cp-process-graph'));
      if (externalMutation) scheduleBuild(root);
    });
    observer.observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
    scheduleBuild(root);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
