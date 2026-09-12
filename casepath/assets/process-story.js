(() => {
  'use strict';

  if (document.documentElement.dataset.claimsWorkspace === 'true') return;

  if (new URLSearchParams(location.search).get('foundation') === 'live-v1') return;

  const PROCESS_NODE_INTERVAL_MS = 2500;
  const PROCESS_BRANCH_HOLD_MS = 2500;
  const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  const completedStories = new Set();
  const timers = new Set();
  let activeLayout = null;
  let queued = false;

  function later(callback, delay) {
    const timer = window.setTimeout(() => {
      timers.delete(timer);
      callback();
    }, delay);
    timers.add(timer);
  }

  function clearTimeline() {
    for (const timer of timers) window.clearTimeout(timer);
    timers.clear();
    activeLayout = null;
  }

  function storyKey(layout) {
    const runId = document.body.dataset.casepathActiveRunId || 'unbound-run';
    const processId = layout.dataset.processId || 'unbound-process';
    return `${runId}:${processId}:${layout.dataset.processNodeCount || '0'}`;
  }

  function buildControls(layout) {
    return {
      focus: layout.querySelector('[data-process-build-focus]'),
      count: layout.querySelector('[data-process-build-count]'),
      basis: layout.querySelector('[data-process-build-basis]'),
      title: layout.querySelector('[data-process-build-title]'),
      detail: layout.querySelector('[data-process-build-detail]'),
      announcement: layout.querySelector('[data-process-build-announcement]'),
    };
  }

  function ensureExploreControl(layout) {
    let control = layout.querySelector('[data-process-story-explore]');
    if (control) return control;
    control = document.createElement('button');
    control.type = 'button';
    control.className = 'process-story-explore';
    control.dataset.processStoryExplore = 'true';
    control.setAttribute('aria-expanded', 'false');
    control.innerHTML = '<span>Explore full path</span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';
    const map = layout.querySelector('.process-map');
    map?.append(control);
    return control;
  }

  function setNarration(layout, { count, basis, title, detail, announcement }) {
    const controls = buildControls(layout);
    if (controls.count) controls.count.textContent = count;
    if (controls.basis) controls.basis.textContent = basis;
    if (controls.title) controls.title.textContent = title;
    if (controls.detail) controls.detail.textContent = detail;
    if (controls.announcement && announcement) controls.announcement.textContent = announcement;
  }

  function emitStep(layout, target, detail) {
    layout.querySelectorAll('[data-agent-cursor-target="true"]').forEach(node => node.removeAttribute('data-agent-cursor-target'));
    target?.setAttribute('data-agent-cursor-target', 'true');
    window.dispatchEvent(new CustomEvent('casepath:graph-step', {
      detail: {
        processId: layout.dataset.processId || '',
        parentId: target?.closest?.('[data-process-parent-id]')?.dataset.processParentId || '',
        edge: target?.closest?.('[data-process-edge-condition]')?.dataset.processEdgeCondition || '',
        evidenceRequirementIds: (target?.closest?.('[data-basis-evidence-requirement-ids]')?.dataset.basisEvidenceRequirementIds || '').split(',').filter(Boolean),
        ...detail,
      },
    }));
  }

  function enableGraph(layout) {
    for (const button of layout.querySelectorAll('.process-node-button')) {
      button.removeAttribute('aria-disabled');
      button.removeAttribute('tabindex');
    }
  }

  function finalNarration(layout, branch) {
    const currentId = layout.dataset.processCurrentNode || '';
    const current = layout.querySelector(`.process-node-button[data-node-id="${CSS.escape(currentId)}"]`);
    const currentTitle = current?.querySelector('strong')?.textContent?.trim() || 'the current decision';
    const branchTitle = branch?.querySelector('strong')?.textContent?.trim() || 'the returned next branch';
    setNarration(layout, {
      count: `${layout.dataset.processNodeCount || 'All'} decisions connected`,
      basis: 'Returned process graph',
      title: currentTitle,
      detail: `Current decision. The full returned path is ready to explore; its next selected branch is ${branchTitle}.`,
      announcement: `Process graph complete. ${currentTitle} is the current decision.`,
    });
  }

  function finishStory(layout, key, branch, { emit = true } = {}) {
    if (!layout.isConnected) return;
    for (const node of layout.querySelectorAll('.process-spine > .process-node')) {
      node.dataset.processBuildState = 'built';
    }
    if (branch) branch.dataset.processBuildState = 'built';
    layout.dataset.processConstructionState = 'complete';
    if (!layout.dataset.processStoryExpanded) layout.dataset.processStoryExpanded = 'false';
    const explore = ensureExploreControl(layout);
    if (explore) explore.hidden = false;
    finalNarration(layout, branch);
    enableGraph(layout);
    completedStories.add(key);
    if (emit) emitStep(layout, branch || layout, {
      kind: 'complete',
      nodeId: branch?.dataset.nodeId || layout.dataset.processCurrentNode || '',
      index: Number(layout.dataset.processNodeCount || 0),
      total: Number(layout.dataset.processNodeCount || 0),
      basisKinds: (branch?.dataset.basisKinds || '').split(',').filter(Boolean),
      parentId: branch?.dataset.processParentId || '',
      edge: branch?.dataset.processEdgeCondition || '',
      factIds: (branch?.dataset.basisFactIds || '').split(',').filter(Boolean),
      lawIds: (branch?.dataset.basisLawIds || '').split(',').filter(Boolean),
      evidenceRequirementIds: (branch?.dataset.basisEvidenceRequirementIds || '').split(',').filter(Boolean),
    });
  }

  function activateNode(layout, node, index, total) {
    if (!layout.isConnected || activeLayout !== layout) return;
    layout.querySelectorAll('[data-process-build-state="building"]').forEach(previous => {
      previous.dataset.processBuildState = 'built';
    });
    node.dataset.processBuildState = 'building';
    const nodes = [...layout.querySelectorAll('.process-spine > .process-node')];
    nodes.forEach((candidate, candidateIndex) => {
      if (candidateIndex > index) candidate.dataset.processBuildState = 'pending';
      else if (candidateIndex < index - 3) candidate.dataset.processBuildState = 'receded';
    });
    const button = node.querySelector('.process-node-button');
    const title = button?.querySelector('strong')?.textContent?.trim() || button?.dataset.nodeId || 'Process decision';
    setNarration(layout, {
      count: `Building decision ${index + 1} of ${total}`,
      basis: node.dataset.basisLabel || 'Process rationale',
      title,
      detail: node.dataset.basisDetail || 'Required by the returned process topology.',
      announcement: `Decision ${index + 1} of ${total}: ${title}.`,
    });
    emitStep(layout, button || node, {
      kind: 'node',
      nodeId: button?.dataset.nodeId || '',
      index,
      total,
      basisKinds: (node.dataset.basisKinds || '').split(',').filter(Boolean),
      parentId: node.dataset.processParentId || '',
      edge: node.dataset.processEdgeCondition || '',
      factIds: (node.dataset.basisFactIds || '').split(',').filter(Boolean),
      lawIds: (node.dataset.basisLawIds || '').split(',').filter(Boolean),
      evidenceRequirementIds: (node.dataset.basisEvidenceRequirementIds || '').split(',').filter(Boolean),
    });
  }

  function activateBranch(layout, branch, total) {
    if (!layout.isConnected || activeLayout !== layout || !branch) return;
    layout.querySelectorAll('[data-process-build-state="building"]').forEach(previous => {
      previous.dataset.processBuildState = 'built';
    });
    branch.dataset.processBuildState = 'building';
    const title = branch.querySelector('strong')?.textContent?.trim() || 'Selected branch';
    setNarration(layout, {
      count: 'Selecting the evidence loop',
      basis: branch.dataset.basisLabel || 'Branch condition + process rationale',
      title,
      detail: branch.dataset.basisDetail || branch.querySelector('p')?.textContent?.trim() || 'Selected by the returned graph.',
      announcement: `Selected next step: ${title}.`,
    });
    emitStep(layout, branch, {
      kind: 'branch',
      nodeId: branch.dataset.nodeId || '',
      index: total,
      total,
      basisKinds: (branch.dataset.basisKinds || '').split(',').filter(Boolean),
      parentId: branch.dataset.processParentId || '',
      edge: branch.dataset.processEdgeCondition || '',
      factIds: (branch.dataset.basisFactIds || '').split(',').filter(Boolean),
      lawIds: (branch.dataset.basisLawIds || '').split(',').filter(Boolean),
      evidenceRequirementIds: (branch.dataset.basisEvidenceRequirementIds || '').split(',').filter(Boolean),
    });
  }

  function startStory(layout) {
    if (layout.dataset.processStoryRuntime === 'bound') return;
    layout.dataset.processStoryRuntime = 'bound';
    layout.dataset.laterExpanded = 'true';
    layout.dataset.processStoryExpanded = 'false';
    const explore = ensureExploreControl(layout);
    if (explore) explore.hidden = true;
    const nodes = [...layout.querySelectorAll('.process-spine > .process-node')];
    const branch = layout.querySelector('[data-process-selected-branch]');
    if (!nodes.length) return;
    const key = storyKey(layout);
    if (completedStories.has(key)) {
      finishStory(layout, key, branch, { emit: false });
      return;
    }

    clearTimeline();
    activeLayout = layout;
    layout.dataset.processConstructionState = 'building';
    for (const node of nodes) node.dataset.processBuildState = 'pending';
    if (branch) branch.dataset.processBuildState = 'pending';
    for (const button of layout.querySelectorAll('.process-node-button')) {
      button.setAttribute('aria-disabled', 'true');
      button.setAttribute('tabindex', '-1');
    }

    nodes.forEach((node, index) => later(
      () => activateNode(layout, node, index, nodes.length),
      (reduceMotion ? 0 : 180) + (PROCESS_NODE_INTERVAL_MS * index),
    ));
    const branchAt = (reduceMotion ? 0 : 180) + (PROCESS_NODE_INTERVAL_MS * nodes.length);
    later(() => activateBranch(layout, branch, nodes.length), branchAt);
    later(() => finishStory(layout, key, branch), branchAt + PROCESS_BRANCH_HOLD_MS);
  }

  function synchronize() {
    queued = false;
    const canvas = document.querySelector('#stageCanvas');
    const processMoment = canvas?.dataset.casepathMoment === 'process';
    const layout = processMoment ? canvas.querySelector('.process-layout[data-process-story="grounded-node-sequence/1.0.0"]') : null;
    if (!layout) {
      if (activeLayout) clearTimeline();
      return;
    }
    startStory(layout);
  }

  function queue() {
    if (queued) return;
    queued = true;
    window.requestAnimationFrame(synchronize);
  }

  function toggleFullPath(event) {
    const control = event.target.closest?.('[data-process-story-explore]');
    if (!control) return;
    const layout = control.closest('.process-layout[data-process-story="grounded-node-sequence/1.0.0"]');
    if (!layout) return;
    const expanded = layout.dataset.processStoryExpanded === 'true';
    layout.dataset.processStoryExpanded = String(!expanded);
    control.setAttribute('aria-expanded', String(!expanded));
    const label = control.querySelector('span');
    if (label) label.textContent = expanded ? 'Explore full path' : 'Hide full path';
  }

  function boot() {
    const canvas = document.querySelector('#stageCanvas');
    if (!canvas) return;
    new MutationObserver(queue).observe(canvas, { childList: true, subtree: true });
    canvas.addEventListener('click', toggleFullPath);
    window.addEventListener('casepath:render', queue);
    queue();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
