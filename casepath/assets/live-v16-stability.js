(() => {
  'use strict';

  if (document.documentElement.dataset.claimsWorkspace === 'true') return;

  if (new URLSearchParams(location.search).get('foundation') === 'live-v1') return;

  const viewerFixHref = 'assets/live-v16-viewer-fix.css?sha256=c635aebf3089123fcde188d55263b973d9f71d5788ea871aca7d0586aefdb8d7';
  if (![...document.querySelectorAll('link[rel="stylesheet"]')].some(link => link.href === new URL(viewerFixHref, document.baseURI).href)) {
    const stylesheet = document.createElement('link');
    stylesheet.rel = 'stylesheet';
    stylesheet.href = viewerFixHref;
    document.head.append(stylesheet);
  }

  const viewer = document.querySelector('#sourceViewer');
  const stage = document.querySelector('#sourceStage');

  if (viewer && stage) {
    function keepActiveRepresentationVisible() {
      if (!viewer.open) return;
      stage.hidden = false;
      stage.removeAttribute('aria-hidden');
      stage.style.display = 'flex';
      stage.style.visibility = 'visible';
      stage.style.opacity = '1';
      for (const child of stage.children) {
        child.hidden = false;
        child.removeAttribute('aria-hidden');
        child.style.visibility = 'visible';
        child.style.opacity = '1';
        if (child.classList.contains('extraction-pages')) child.style.display = 'block';
      }
    }

    new MutationObserver(keepActiveRepresentationVisible).observe(stage, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ['hidden', 'style', 'aria-hidden'],
    });

    document.addEventListener('click', event => {
      if (!event.target.closest?.('[data-source-tab]')) return;
      requestAnimationFrame(keepActiveRepresentationVisible);
      setTimeout(keepActiveRepresentationVisible, 100);
      setTimeout(keepActiveRepresentationVisible, 600);
    });

    viewer.addEventListener('close', () => {
      stage.style.removeProperty('display');
      stage.style.removeProperty('visibility');
      stage.style.removeProperty('opacity');
    });
  }

  const escapeHtml = (value = '') => String(value).replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[character]));
  const query = new URLSearchParams(location.search);
  const loopback = ['127.0.0.1', 'localhost', '::1'].includes(location.hostname);
  const apiBase = location.origin.replace(/\/$/, '');

  const auditHeader = document.querySelector('#auditDrawer .audit-shell > header');
  const auditClose = document.querySelector('#closeAudit');
  if (auditHeader && auditClose && !document.querySelector('#browserEvidenceLink')) {
    const evidenceStatus = document.createElement('span');
    evidenceStatus.id = 'browserEvidenceLink';
    evidenceStatus.className = 'release-evidence-status';
    evidenceStatus.setAttribute('role', 'status');
    evidenceStatus.setAttribute('aria-live', 'polite');
    evidenceStatus.dataset.evidenceState = 'pending';
    evidenceStatus.textContent = 'Current release evidence pending';
    auditHeader.insertBefore(evidenceStatus, auditClose);
  }

  const evidenceControl = document.querySelector('#browserEvidenceLink');
  const qaEvidenceBase = 'https://casepath-guided-canonical-qa.onrender.com';
  const exactCommit = /^[0-9a-f]{40}$/;

  const sha256Pattern = /^[0-9a-f]{64}$/;

  function retainedEvidenceComplete(report, manifest) {
    const files = manifest?.files;
    const reportFiles = report?.evidence?.files;
    const retained = manifest?.retained_media_contract;
    if (!Array.isArray(files) || files.length === 0 || !Array.isArray(reportFiles)) return false;
    if (JSON.stringify(files) !== JSON.stringify(reportFiles)) return false;
    const paths = new Set();
    for (const file of files) {
      if (!file || typeof file.path !== 'string' || file.path.length === 0
        || paths.has(file.path) || !sha256Pattern.test(file.sha256 || '')
        || !Number.isInteger(file.bytes) || file.bytes <= 0) return false;
      paths.add(file.path);
    }
    const required = [
      ...(Array.isArray(retained?.json) ? retained.json : []),
      ...(Array.isArray(retained?.screenshots) ? retained.screenshots : []),
      ...(typeof retained?.video === 'string' ? [retained.video] : []),
    ];
    return Array.isArray(retained?.json)
      && retained.json.length > 0
      && Array.isArray(retained?.screenshots)
      && retained.screenshots.length > 0
      && typeof retained?.video === 'string'
      && retained.video.length > 0
      && required.every(path => paths.has(path))
      && Array.isArray(retained?.missing)
      && retained.missing.length === 0
      && Array.isArray(retained?.empty)
      && retained.empty.length === 0;
  }

  function releaseEvidenceAttested(frontend, api, report, manifest, manifestBinding) {
    const commit = frontend?.source_commit;
    const reportIdentities = [
      report?.deployment?.frontend?.source_commit,
      report?.deployment?.api?.source_commit,
      report?.deployment?.qa?.source_commit,
    ];
    return exactCommit.test(commit || '')
      && frontend?.alignment_eligible === true
      && api?.status === 'ok'
      && api?.release_id === frontend?.release_id
      && api?.source_commit === commit
      && api?.source_commit_aligned === true
      && api?.source_commit_conflict === false
      && report?.status === 'passed'
      && report?.failed === 0
      && report?.release_id === frontend?.release_id
      && reportIdentities.every(value => value === commit)
      && report?.evidence?.retained_before_session_reset === true
      && Array.isArray(report?.evidence?.missing)
      && report.evidence.missing.length === 0
      && manifest?.contract === 'casepath.qa-evidence-manifest/1.0.0'
      && manifest?.release_id === frontend?.release_id
      && manifest?.source_commit === commit
      && manifest?.gate?.sha256 === report?.evidence?.gate?.sha256
      && manifest?.retained_before_session_reset === true
      && report?.evidence?.manifest?.path === 'evidence-manifest.json'
      && sha256Pattern.test(manifestBinding?.sha256 || '')
      && report.evidence.manifest.sha256 === manifestBinding.sha256
      && report.evidence.manifest.bytes === manifestBinding.bytes
      && retainedEvidenceComplete(report, manifest);
  }

  async function sha256Hex(bytes) {
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return [...new Uint8Array(digest)]
      .map(value => value.toString(16).padStart(2, '0'))
      .join('');
  }

  window.__casepathEvidenceAttestation = Object.freeze({
    isAttested: releaseEvidenceAttested,
  });

  async function attestCurrentReleaseEvidence() {
    if (!evidenceControl) return;
    try {
      const [frontendResponse, apiResponse, reportResponse, manifestResponse] = await Promise.all([
        fetch('deployment.json', { cache: 'no-store' }),
        fetch(`${apiBase}/healthz`, { cache: 'no-store', mode: 'cors' }),
        fetch(`${qaEvidenceBase}/report.json`, { cache: 'no-store', mode: 'cors' }),
        fetch(`${qaEvidenceBase}/evidence-manifest.json`, { cache: 'no-store', mode: 'cors' }),
      ]);
      if (![frontendResponse, apiResponse, reportResponse, manifestResponse].every(response => response.ok)) return;
      const manifestText = await manifestResponse.text();
      const manifestBytes = new TextEncoder().encode(manifestText);
      const [frontend, api, report, manifestHash] = await Promise.all([
        frontendResponse.json(),
        apiResponse.json(),
        reportResponse.json(),
        sha256Hex(manifestBytes),
      ]);
      const manifest = JSON.parse(manifestText);
      const commit = frontend.source_commit;
      const attested = releaseEvidenceAttested(frontend, api, report, manifest, {
        sha256: manifestHash,
        bytes: manifestBytes.byteLength,
      });
      if (!attested) return;
      const link = document.createElement('a');
      link.id = evidenceControl.id;
      link.className = evidenceControl.className;
      link.dataset.evidenceState = 'attested';
      link.href = `${qaEvidenceBase}/report.json`;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = `Current release evidence · ${commit.slice(0, 8)}`;
      evidenceControl.replaceWith(link);
    } catch (_) {
      // Network, CORS, parsing, identity, or evidence failures keep the control
      // in its intentionally non-clickable pending state.
    }
  }

  // A localhost product run is a closed, zero-hosted-dependency process. Its
  // browser evidence is produced locally after the journey, never fetched
  // from a release QA service while the handler is working.
  if (!loopback && !query.has('qa')) attestCurrentReleaseEvidence();

  function discoveredRunIds() {
    const ids = [];
    for (const entry of performance.getEntriesByType('resource')) {
      try {
        const url = new URL(entry.name);
        const match = url.pathname.match(/^\/api\/runs\/([^/]+)$/);
        if (match && !ids.includes(match[1])) ids.push(match[1]);
      } catch (_) {}
    }
    return ids;
  }

  function auditEvent(event) {
    const inputs = (event.input_artifacts || []).join(', ') || event.input_hash || '';
    const output = event.output_artifact || event.output_hash || '';
    const specialist = event.agent || event.label || event.stage || 'Run event';
    const eventLabel = [event.label, event.headline].filter(Boolean).join(' · ');
    return `<details class="audit-event">
      <summary><span></span><div><strong>${escapeHtml(specialist)}</strong><span>${escapeHtml(eventLabel)}</span></div><span>${escapeHtml(event.status || '')}</span></summary>
      <div class="audit-event-body">
        ${event.detail ? `<p>${escapeHtml(event.detail)}</p>` : ''}
        <dl class="audit-grid">
          <dt>Specialist</dt><dd>${escapeHtml(specialist)}</dd>
          <dt>Implementation</dt><dd>${escapeHtml(event.implementation || '')}</dd>
          <dt>Model</dt><dd>${escapeHtml(event.model || 'None — deterministic or human')}</dd>
          <dt>Prompt</dt><dd>${escapeHtml(event.prompt_version || 'None')}</dd>
          <dt>Validator</dt><dd>${escapeHtml(event.validator || '')}</dd>
          <dt>Input</dt><dd>${escapeHtml(inputs)}</dd>
          <dt>Output</dt><dd>${escapeHtml(output)}</dd>
        </dl>
      </div>
    </details>`;
  }

  async function openUnifiedAudit(event) {
    const trigger = event.target.closest?.('#openAudit');
    if (!trigger || trigger.disabled) return;
    if (document.documentElement.dataset.insuranceProtocol === 'active') return;
    event.preventDefault();
    event.stopImmediatePropagation();

    const drawer = document.querySelector('#auditDrawer');
    const content = document.querySelector('#auditContent');
    const shell = drawer?.querySelector('.audit-shell');
    const proof = document.querySelector('#orchestrationProof');
    if (!drawer || !content || !shell) return;

    trigger.disabled = true;
    const originalLabel = trigger.textContent;
    trigger.textContent = 'Loading audit…';

    try {
      // The capture-phase handler owns this click. Move the renderer-owned
      // proof beside the replaceable event list so later content refreshes
      // cannot delete the six-agent/three-gate evidence.
      if (proof) {
        proof.hidden = false;
        proof.classList.add('v21-audit-proof');
        shell.insertBefore(proof, content);
      }
      const ids = discoveredRunIds();
      const runs = await Promise.all(ids.map(async runId => {
        const retained = window.CasePathRunStore?.get?.(runId);
        if (retained?.run_id === runId && Array.isArray(retained.events)) return retained;
        const sessionId = sessionStorage.getItem('casepath:demo-session') || '';
        const response = await fetch(`${apiBase}/api/runs/${encodeURIComponent(runId)}`, {
          headers: sessionId ? { 'X-CasePath-Session': sessionId } : {},
        });
        if (!response.ok) throw new Error(`Run ${runId} could not be read.`);
        return response.json();
      }));
      runs.sort((a, b) => String(a.created_at || '').localeCompare(String(b.created_at || '')));
      content.innerHTML = `<div style="padding:17px 0;border-bottom:1px solid #e5e8ec;color:#626a75;font-size:10px;line-height:1.5">Open any event to inspect its <strong style="color:#101318">Implementation</strong>, model, <strong style="color:#101318">Prompt</strong>, tools, <strong style="color:#101318">Validator</strong>, inputs, outputs, and provenance.</div>` + runs.map((run, index) => {
        const label = index === 0 ? 'Flagship claim and review memory' : 'Held-out later demo claim under the unchanged shared playbook';
        return `<section class="audit-run-section" style="padding-top:${index ? 26 : 0}px">
          <header style="padding:18px 0 10px;border-bottom:1px solid #e5e8ec">
            <span class="quiet-label">${escapeHtml(label)}</span>
            <strong style="display:block;margin-top:4px;font-size:13px">${escapeHtml(run.claim_id || run.run_id || '')}</strong>
          </header>
          ${(run.events || []).map(auditEvent).join('')}
        </section>`;
      }).join('');
      if (!drawer.open) drawer.showModal();
    } catch (error) {
      content.innerHTML = `<p style="padding:18px 0;color:#626a75">${escapeHtml(error.message)}</p>`;
      if (!drawer.open) drawer.showModal();
    } finally {
      trigger.disabled = false;
      trigger.textContent = originalLabel;
    }
  }

  document.addEventListener('click', openUnifiedAudit, true);
})();
