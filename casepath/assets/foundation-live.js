(() => {
  'use strict';

  if (document.documentElement.dataset.claimsWorkspace === 'true') return;

  const params = new URLSearchParams(location.search);
  if (params.get('foundation') !== 'live-v1') return;

  const API = location.origin.replace(/\/$/, '');
  const sessionPattern = /^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$/;
  let sessionId = params.get('foundation_session') || sessionStorage.getItem('casepath:foundation-session');
  if (!sessionPattern.test(sessionId || '')) sessionId = `foundation-${crypto.randomUUID()}`;
  sessionStorage.setItem('casepath:foundation-session', sessionId);

  const trace = {
    contract: 'casepath.foundation-ui-api-trace/1.0.0',
    session_id: sessionId,
    api_base: API,
    calls: [],
    lifecycle_id: null,
    candidate_version_id: null,
    state: 'ready',
    restart_verified: false,
    audit_export: null,
    model_calls: 0,
    provider_calls: 0,
    provider_credentials_read: false,
    cost_usd: 0.0,
    central_hypothesis: 'UNTESTED',
  };
  window.__CASEPATH_FOUNDATION_TRACE = trace;

  document.body.innerHTML = `
    <div class="foundation-shell" data-foundation-state="ready">
      <header class="foundation-topbar">
        <a class="foundation-brand" href="#foundationMain"><span>CP</span>CasePath</a>
        <div><strong>Open-source foundation</strong><small>Live deterministic integration · public synthetic fixtures</small></div>
        <span class="foundation-zero">0 model calls · USD 0.00</span>
      </header>
      <main id="foundationMain" class="foundation-main">
        <section class="foundation-hero">
          <div>
            <p class="foundation-eyebrow">Provider-free system proof</p>
            <h1>One traceable claim lifecycle, through the actual API, UI, and store.</h1>
            <p>Every output keeps the chain <b>source → process decision → required fact → evidence need → document requirement</b>. This run verifies integration, not model quality or the process-first hypothesis.</p>
          </div>
          <aside class="foundation-boundary">
            <strong>Evidence boundary</strong>
            <p>The reviewer identity is a signed <code>non_human_test_fixture</code>. It is not human or expert validation.</p>
            <p>General anonymization safety and scientific advantage remain untested.</p>
          </aside>
        </section>

        <section class="foundation-control" aria-labelledby="foundationControlTitle">
          <div><p class="foundation-eyebrow">Trusted intake</p><h2 id="foundationControlTitle">Run the frozen public-development case</h2><p id="foundationRegistryStatus">Checking the signed server registry…</p></div>
          <button id="foundationStart" type="button" disabled>Start trusted lifecycle</button>
        </section>

        <ol class="foundation-steps" id="foundationSteps" aria-label="Persistent lifecycle states">
          ${['trusted intake','canonical case','source-linked process','document plan','quarantined','reviewed','regression passed','promoted','later-case retrieval','restart recovery','rolled back','benchmark + audit'].map((label, index) => `<li data-step="${index}"><span>${String(index + 1).padStart(2, '0')}</span><strong>${label}</strong><small>pending</small></li>`).join('')}
        </ol>

        <section class="foundation-artifacts" id="foundationArtifacts" hidden>
          <article class="foundation-process">
            <header><p class="foundation-eyebrow">Process model</p><h2>Decisions and branches</h2><small id="foundationProcessHash"></small></header>
            <div id="foundationProcessNodes"></div>
          </article>
          <article class="foundation-documents">
            <header><p class="foundation-eyebrow">Process-derived plan</p><h2>Evidence and documents</h2><small id="foundationDocumentHash"></small></header>
            <div id="foundationDocumentItems"></div>
          </article>
        </section>

        <section class="foundation-review" id="foundationReviewPanel" hidden>
          <div><p class="foundation-eyebrow">Authenticated review boundary</p><h2>Apply a signed non-human test fixture review</h2><p>The server binds the principal, role, artifact version, corrections, timestamp, nonce, and signature before any state can change.</p></div>
          <label>Fixture correction note<textarea id="foundationCorrection">No semantic correction; exercise governance only.</textarea></label>
          <button id="foundationReview" type="button">Sign and submit test review</button>
        </section>

        <section class="foundation-actions" id="foundationActions" hidden>
          <button id="foundationRegression" type="button">Run regression gate</button>
          <button id="foundationPromote" type="button" disabled>Promote test knowledge</button>
          <button id="foundationRetrieve" type="button" disabled>Retrieve on later case</button>
          <button id="foundationRestart" type="button" disabled>Verify service restart</button>
          <button id="foundationRollback" type="button" disabled>Rollback exactly</button>
          <button id="foundationExport" type="button" disabled>Project benchmark + export audit</button>
        </section>

        <section class="foundation-receipts" id="foundationReceipts" aria-live="polite">
          <header><p class="foundation-eyebrow">Hash-bound receipts</p><h2 id="foundationStateTitle">Ready</h2><p id="foundationStateCopy">No lifecycle mutation has occurred.</p></header>
          <pre id="foundationReceiptLog">Waiting for trusted registry…</pre>
        </section>
      </main>
    </div>`;

  const $ = selector => document.querySelector(selector);
  const shell = $('.foundation-shell');
  const requestHeaders = key => ({
    'Content-Type': 'application/json',
    'X-CasePath-Session': sessionId,
    'X-CasePath-Idempotency-Key': `${sessionId}:${key}`,
  });
  const idKey = action => `${action}-${trace.lifecycle_id || 'registry'}`.replace(/[^A-Za-z0-9._:-]/g, '-').slice(0, 120);

  function record(path, method, request, response) {
    trace.calls.push({ path, method, request, response });
    window.dispatchEvent(new CustomEvent('casepath:foundation-trace', { detail: { path, method } }));
  }

  async function api(path, { method = 'GET', body = null, key = null } = {}) {
    const options = { method, cache: 'no-store', headers: { 'X-CasePath-Session': sessionId } };
    if (body !== null) {
      options.headers = requestHeaders(key || idKey(path));
      options.body = JSON.stringify(body);
    }
    const response = await fetch(`${API}${path}`, options);
    const payload = await response.json().catch(() => ({ detail: 'non-JSON response' }));
    record(path, method, body, { status: response.status, payload });
    if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
    return payload;
  }

  function step(index, status, receipt = '') {
    const row = $(`[data-step="${index}"]`);
    row.dataset.status = status;
    row.querySelector('small').textContent = receipt ? `${status} · ${receipt.slice(0, 12)}…` : status;
  }

  function setState(state, title, copy, receipt) {
    trace.state = state;
    shell.dataset.foundationState = state;
    $('#foundationStateTitle').textContent = title;
    $('#foundationStateCopy').textContent = copy;
    $('#foundationReceiptLog').textContent = JSON.stringify(receipt, null, 2);
  }

  function provenanceLabel(item) {
    const locators = item.provenance || [];
    const first = locators[0] || {};
    return `${first.artifact_id || 'source'} · ${first.locator_kind || 'locator'}${first.page ? ` · p.${first.page}` : ''}`;
  }

  function renderArtifacts(canonical) {
    const process = canonical.process_artifact || {};
    const concepts = process.concepts || [];
    $('#foundationProcessNodes').innerHTML = concepts.map((item, index) => `
      <button type="button" class="foundation-node" data-kind="${item.kind || 'node'}">
        <span>${String(index + 1).padStart(2, '0')}</span><div><small>${item.kind || 'process node'}</small><strong>${item.label || item.concept_id}</strong><code>${provenanceLabel(item)}</code></div>
      </button>`).join('');
    $('#foundationDocumentItems').innerHTML = (canonical.evidence_document_plan || []).map(item => `
      <article class="foundation-document"><span>${item.state || 'unknown'}</span><div><strong>${item.label || item.document_id}</strong><small>${item.request_mode || 'conditional'}</small><code>${provenanceLabel(item)}</code></div></article>`).join('');
    $('#foundationProcessHash').textContent = `canonical ${canonical.canonical_sha256.slice(0, 16)}…`;
    $('#foundationDocumentHash').textContent = `${canonical.evidence_document_plan.length} process-linked requirements`;
    $('#foundationArtifacts').hidden = false;
  }

  async function boot() {
    try {
      const [status, registry] = await Promise.all([
        api('/api/foundation/v1/status'),
        api('/api/foundation/v1/registry'),
      ]);
      trace.status_receipt = status.receipt_sha256;
      trace.registry_receipt = registry.receipt_sha256;
      trace.case_ids = registry.case_ids;
      $('#foundationRegistryStatus').textContent = `${registry.dataset_id} · ${registry.dataset_version} · ${registry.case_count} signed cases`;
      $('#foundationStart').disabled = false;
      $('#foundationReceiptLog').textContent = JSON.stringify({ status, registry }, null, 2);
    } catch (error) {
      setState('blocked', 'Foundation unavailable', error.message, { error: error.message });
    }
  }

  $('#foundationStart').addEventListener('click', async () => {
    try {
      const caseId = trace.case_ids[0];
      const result = await api('/api/foundation/v1/intake', {
        method: 'POST', body: { case_id: caseId }, key: 'trusted-intake-0001',
      });
      trace.lifecycle_id = result.lifecycle_id;
      trace.candidate_version_id = result.candidate_version_id;
      trace.intake = result;
      [0, 1, 2, 3, 4].forEach(index => step(index, 'passed', index === 0 ? result.trusted_privacy_receipt.receipt_sha256 : result.transaction_receipt.receipt_sha256));
      renderArtifacts(result.canonical);
      $('#foundationReviewPanel').hidden = false;
      setState('quarantined', 'Candidate quarantined', 'Trusted intake, canonicalization, reference boundary, validation, and provenance checks passed.', result);
      $('#foundationStart').disabled = true;
    } catch (error) {
      setState('blocked', 'Intake blocked', error.message, { error: error.message });
    }
  });

  $('#foundationReview').addEventListener('click', async () => {
    try {
      const corrections = [{
        fixture_id: 'iteration11.non-human-review',
        authority_type: 'non_human_test_fixture',
        semantic_change: false,
        note: $('#foundationCorrection').value,
      }];
      const issued = await api('/api/foundation/v1/review/authorize-test-fixture', {
        method: 'POST',
        body: { lifecycle_id: trace.lifecycle_id, artifact_version: trace.candidate_version_id, accepted_corrections: corrections },
        key: idKey('review-authorize'),
      });
      const reviewed = await api('/api/foundation/v1/review', {
        method: 'POST', body: { authorization: issued.authorization }, key: idKey('review-submit'),
      });
      trace.review = reviewed;
      step(5, 'passed', reviewed.review_receipt.receipt_sha256);
      $('#foundationReview').disabled = true;
      $('#foundationActions').hidden = false;
      setState('reviewed', 'Authenticated fixture review recorded', 'Signature, principal, role, artifact version, nonce, revocation, replay, and provenance checks passed.', reviewed);
    } catch (error) {
      setState('blocked', 'Review rejected', error.message, { error: error.message });
    }
  });

  $('#foundationRegression').addEventListener('click', async () => {
    try {
      const result = await api('/api/foundation/v1/regression', {
        method: 'POST', body: { lifecycle_id: trace.lifecycle_id }, key: idKey('regression'),
      });
      trace.regression = result;
      step(6, 'passed', result.regression_receipt.receipt_sha256);
      $('#foundationRegression').disabled = true;
      $('#foundationPromote').disabled = false;
      setState('regression_passed', 'Regression gate passed', 'Canonical validation, content address, provenance, and review signature remain intact.', result);
    } catch (error) { setState('blocked', 'Regression denied', error.message, { error: error.message }); }
  });

  $('#foundationPromote').addEventListener('click', async () => {
    try {
      const result = await api('/api/foundation/v1/promote', {
        method: 'POST', body: { lifecycle_id: trace.lifecycle_id }, key: idKey('promote'),
      });
      trace.promotion = result;
      step(7, 'passed', result.promotion_receipt.receipt_sha256);
      $('#foundationPromote').disabled = true;
      $('#foundationRetrieve').disabled = false;
      setState('promoted', 'Test knowledge promoted atomically', 'The exact prior active version is retained as the rollback target.', result);
    } catch (error) { setState('blocked', 'Promotion denied', error.message, { error: error.message }); }
  });

  $('#foundationRetrieve').addEventListener('click', async () => {
    try {
      const laterCase = trace.case_ids.find(value => value !== trace.intake.case_id);
      const result = await api('/api/foundation/v1/retrieve', {
        method: 'POST', body: { later_case_id: laterCase }, key: idKey('retrieve'),
      });
      trace.retrieval = result;
      step(8, 'passed', result.retrieval_receipt.receipt_sha256);
      $('#foundationRetrieve').disabled = true;
      $('#foundationRestart').disabled = false;
      setState('retrieved', 'Later-case retrieval received', 'The active content, provenance, version, and index are bound in one receipt.', result);
    } catch (error) { setState('blocked', 'Retrieval denied', error.message, { error: error.message }); }
  });

  $('#foundationRestart').addEventListener('click', async () => {
    try {
      const result = await api(`/api/foundation/v1/lifecycle/${encodeURIComponent(trace.lifecycle_id)}`);
      trace.restart_verified = result.restart_recovered === true && result.session.active_version_id === trace.promotion.active_version_id;
      if (!trace.restart_verified) throw new Error('restart recovery identity mismatch');
      trace.restart = result;
      step(9, 'passed', result.receipt_sha256);
      $('#foundationRestart').disabled = true;
      $('#foundationRollback').disabled = false;
      setState('restart_recovered', 'Service restart recovered', 'The persistent store returned the exact promoted version after process restart.', result);
    } catch (error) { setState('blocked', 'Restart recovery failed', error.message, { error: error.message }); }
  });

  $('#foundationRollback').addEventListener('click', async () => {
    try {
      const result = await api('/api/foundation/v1/rollback', {
        method: 'POST', body: { lifecycle_id: trace.lifecycle_id }, key: idKey('rollback'),
      });
      if (result.exact_prior_version_restored !== true) throw new Error('rollback was not exact');
      trace.rollback = result;
      step(10, 'passed', result.rollback_receipt.receipt_sha256);
      $('#foundationRollback').disabled = true;
      $('#foundationExport').disabled = false;
      setState('rolled_back', 'Exact rollback complete', 'Prior version, content, provenance, and retrieval index were restored byte-for-byte.', result);
    } catch (error) { setState('blocked', 'Rollback failed', error.message, { error: error.message }); }
  });

  $('#foundationExport').addEventListener('click', async () => {
    try {
      const traceSnapshot = JSON.parse(JSON.stringify(trace));
      const traceReceipt = await api('/api/foundation/v1/ui-trace', {
        method: 'POST',
        body: { lifecycle_id: trace.lifecycle_id, trace: traceSnapshot },
        key: idKey('ui-trace'),
      });
      const [benchmark, audit] = await Promise.all([
        api(`/api/foundation/v1/lifecycle/${encodeURIComponent(trace.lifecycle_id)}/benchmark`),
        api('/api/foundation/v1/audit-export'),
      ]);
      trace.benchmark = benchmark;
      trace.audit_export = audit;
      trace.ui_trace_receipt = traceReceipt.trace_receipt;
      step(11, 'passed', audit.receipt_sha256);
      const blob = new Blob([JSON.stringify(audit, null, 2)], { type: 'application/json' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `casepath-foundation-audit-${sessionId}.json`;
      link.dataset.foundationDownload = 'audit';
      document.body.append(link);
      trace.audit_download_name = link.download;
      $('#foundationExport').disabled = true;
      setState('complete', 'Live foundation proof complete', 'Benchmark projection and immutable audit export are ready. The scientific hypothesis remains UNTESTED.', { benchmark, audit });
    } catch (error) { setState('blocked', 'Export failed', error.message, { error: error.message }); }
  });

  boot();
})();
