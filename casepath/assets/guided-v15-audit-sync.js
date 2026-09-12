(() => {
  'use strict';

  const API = location.origin.replace(/\/$/, '');
  const esc = (value = '') => String(value).replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[character]));

  async function syncReviewEvents() {
    const lifecycle = window.__CASEPATH_LIFECYCLE_V15__;
    const runId = lifecycle?.run?.run_id;
    const content = document.querySelector('#auditContent');
    if (!runId || !content || content.querySelector('[data-v15-review-audit]')) return;
    try {
      const response = await fetch(`${API}/api/runs/${encodeURIComponent(runId)}`);
      if (!response.ok) return;
      const run = await response.json();
      lifecycle.run = run;
      const events = (run.events || []).filter(event => ['review', 'consolidate'].includes(event.stage));
      if (!events.length) return;
      const section = document.createElement('section');
      section.dataset.v15ReviewAudit = 'true';
      section.className = 'v15-audit-review-events';
      section.innerHTML = `
        <p class="eyebrow">Expert-to-knowledge handoff</p>
        ${events.map(event => `
          <details class="audit-event" open>
            <summary><span></span><div><strong>${esc(event.label)}</strong><span>${esc(event.headline || '')}</span></div><span>${esc(event.status || '')}</span></summary>
            <div class="audit-event-body">
              <dl class="audit-grid"><dt>Specialist</dt><dd>${esc(event.agent || '')}</dd><dt>Implementation</dt><dd>${esc(event.implementation || '')}</dd><dt>Model</dt><dd>${esc(event.model || 'None — human or deterministic')}</dd><dt>Prompt</dt><dd>${esc(event.prompt_version || 'None')}</dd><dt>Validator</dt><dd>${esc(event.validator || '')}</dd><dt>Output</dt><dd>${esc(event.output_artifact || '')}</dd></dl>
              ${event.detail ? `<p>${esc(event.detail)}</p>` : ''}
            </div>
          </details>`).join('')}`;
      content.append(section);
    } catch (_) {}
  }

  document.addEventListener('click', event => {
    const opener = event.target.closest?.('#openAuditGuide, #openAuditTop');
    if (!opener) return;
    const lifecycle = window.__CASEPATH_LIFECYCLE_V15__;
    if (!lifecycle?.review) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    (async () => {
      await syncReviewEvents();
      const audit = document.querySelector('#auditDrawer');
      if (audit && !audit.open) audit.showModal();
    })();
  }, true);

  const audit = document.querySelector('#auditDrawer');
  if (audit) new MutationObserver(syncReviewEvents).observe(audit, { attributes: true, attributeFilter: ['open'] });
})();
