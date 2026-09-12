(() => {
  'use strict';

  if (document.documentElement.dataset.claimsWorkspace === 'true') return;

  if (new URLSearchParams(location.search).get('foundation') === 'live-v1') return;

  const labels = {
    read: 'Read',
    understand: 'Understand',
    research: 'Law',
    process: 'Process',
    evidence: 'Evidence',
    experience: 'Experience',
    verify: 'Verify',
  };
  let scheduled = false;

  function synchronize() {
    scheduled = false;
    const rail = document.querySelector('.v19-team-history');
    const activeId = document.querySelector('.v18-progress-focus')?.dataset.activeStage;
    const label = labels[activeId];
    if (!rail || !label) return;

    const desiredText = `${label} · working now`;
    const matching = [...rail.querySelectorAll('li')].filter(item => item.textContent.trim().startsWith(`${label} ·`));
    const item = matching.at(-1) || document.createElement('li');
    for (const duplicate of matching) {
      if (duplicate !== item) duplicate.remove();
    }
    if (item.dataset.state !== 'active') item.dataset.state = 'active';
    if (item.title !== 'working now') item.title = 'working now';
    if (item.textContent !== desiredText) item.textContent = desiredText;
    if (!item.isConnected) rail.append(item);
  }

  function queue() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(synchronize);
  }

  function boot() {
    const target = document.querySelector('#agentProgress');
    if (!target) return;
    new MutationObserver(queue).observe(target, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-state', 'data-active-stage'] });
    window.addEventListener('casepath:render', queue);
    queue();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, { once: true });
  else boot();
})();
