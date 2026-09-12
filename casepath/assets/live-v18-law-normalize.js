(() => {
  'use strict';

  function keepOne(nodes, preferred = null) {
    const retained = preferred || nodes[0] || null;
    for (const node of nodes) {
      if (node !== retained) node.remove();
    }
    return retained;
  }

  function normalizeChecklist(canvas) {
    const checklists = [...canvas.querySelectorAll('.v17-derived-checklist')];
    const checklist = keepOne(checklists, checklists.find(item => item.querySelectorAll('.v17-checklist-group').length === 4) || checklists[0] || null);
    if (!checklist) return;

    for (const group of checklist.querySelectorAll('.v17-checklist-group')) {
      const uniqueItems = [];
      const seen = new Set();
      for (const item of group.querySelectorAll('.v17-checklist-item')) {
        const key = (item.textContent || '').replace(/\s+/g, ' ').trim();
        if (key && !seen.has(key)) {
          seen.add(key);
          uniqueItems.push(item);
        }
      }
      if (!uniqueItems.length) continue;

      for (const item of group.querySelectorAll('.v17-checklist-item')) item.remove();
      for (const details of group.querySelectorAll(':scope > details')) details.remove();

      const first = uniqueItems.shift();
      group.append(first);
      if (uniqueItems.length) {
        const details = document.createElement('details');
        details.className = 'v18-checklist-details';
        details.innerHTML = `<summary>Show ${uniqueItems.length} more</summary>`;
        for (const item of uniqueItems) details.append(item);
        details.removeAttribute('open');
        group.append(details);
      }
      group.dataset.v18Normalized = 'true';
    }
    checklist.dataset.v18Condensed = 'true';
    checklist.dataset.v18Normalized = 'true';
  }

  function normalize() {
    const canvas = document.querySelector('#stageCanvas');
    if (!canvas) return;

    const maps = [...canvas.querySelectorAll('.v17-law-map')];
    const retainedMap = keepOne(maps);
    if (retainedMap) {
      retainedMap.dataset.v18Backed = 'true';
      retainedMap.setAttribute('aria-label', 'Swiss-law sources connected to the process decisions they shape');
    }

    const details = [...canvas.querySelectorAll('.v17-law-details')];
    const retainedDetails = keepOne(details, details.find(item => item.querySelector('.law-flow')) || details.at(-1) || null);
    if (retainedDetails) {
      retainedDetails.removeAttribute('open');
      retainedDetails.dataset.v18Normalized = 'true';
    }

    const readyArtifacts = [...canvas.querySelectorAll('.v18-ready-artifacts')];
    const retainedReady = keepOne(readyArtifacts);
    if (retainedReady) retainedReady.dataset.v18Normalized = 'true';

    normalizeChecklist(canvas);

    const memoryBoundaries = [...canvas.querySelectorAll('.v18-memory-boundary')];
    const retainedMemory = keepOne(memoryBoundaries);
    if (retainedMemory) retainedMemory.dataset.v18Normalized = 'true';

    const reuseProofs = [...canvas.querySelectorAll('.v18-reuse-proof')];
    const retainedReuse = keepOne(reuseProofs, reuseProofs.find(item => item.querySelector('.v17-reuse-thread')) || reuseProofs.at(-1) || null);
    if (retainedReuse) retainedReuse.dataset.v18Normalized = 'true';
  }

  function boot() {
    const canvas = document.querySelector('#stageCanvas');
    if (!canvas) return;
    new MutationObserver(() => requestAnimationFrame(normalize)).observe(canvas, { childList: true, subtree: true });
    window.addEventListener('casepath:render', () => requestAnimationFrame(normalize));
    normalize();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
