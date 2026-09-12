(() => {
  'use strict';

  const API = location.origin.replace(/\/$/, '');
  const state = {
    demo: null,
    claim: null,
    run: null,
    runId: null,
    activeArtifact: null,
    activeArtifactExtraction: null,
    activeFactId: null,
    imageZoom: 1,
    pdfPage: 1,
    selectedNode: 'cause',
  };

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
  const escapeHtml = (value = '') => String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const fmtDate = value => new Intl.DateTimeFormat('en-GB', { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' }).format(new Date(value));
  const icon = name => {
    const paths = {
      chevron:'<path d="M9 6l6 6-6 6"/>',
      check:'<path d="M5 12.5l4 4L19 7"/>',
      dot:'<circle cx="12" cy="12" r="3"/>',
      file:'<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v5h5"/>',
      external:'<path d="M14 5h5v5M13 11l6-6M19 13v6H5V5h6"/>',
      zoomIn:'<circle cx="11" cy="11" r="6"/><path d="M15.5 15.5L20 20M11 8v6M8 11h6"/>',
      zoomOut:'<circle cx="11" cy="11" r="6"/><path d="M15.5 15.5L20 20M8 11h6"/>',
      reset:'<path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.6M4 4v4.6h4.6"/>',
    };
    return `<svg aria-hidden="true" viewBox="0 0 24 24">${paths[name] || paths.dot}</svg>`;
  };

  async function api(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
    if (!response.ok) {
      let message = `${response.status} ${response.statusText}`;
      try { const body = await response.json(); message = body.detail || message; } catch (_) {}
      throw new Error(message);
    }
    return response.json();
  }

  function toast(message) {
    const el = $('#toast');
    el.textContent = message;
    el.classList.add('show');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => el.classList.remove('show'), 2600);
  }

  function formatMessage(claim) {
    return `
      <dl class="email-chrome">
        <dt>From</dt><dd>${escapeHtml(claim.customer.name)} &lt;generated.customer@example.test&gt;</dd>
        <dt>To</dt><dd>claims@protekta.example</dd>
        <dt>Received</dt><dd>${escapeHtml(fmtDate(claim.received_at))}</dd>
        <dt>Subject</dt><dd>${escapeHtml(claim.subject)}</dd>
      </dl>
      <div class="email-body">${escapeHtml(claim.message)}</div>`;
  }

  function fileLabel(a) {
    if (a.media_type === 'application/pdf') return `PDF · ${a.page_count} page${a.page_count === 1 ? '' : 's'}`;
    if (a.media_type === 'message/rfc822') return 'EMAIL · original RFC 822 file';
    if (a.media_type.startsWith('image/')) return 'IMAGE · original file';
    return a.media_type;
  }

  function renderClaim(claim) {
    state.claim = claim;
    $('#claimMeta').innerHTML = [
      `<span>${escapeHtml(claim.claim_id)}</span>`,
      `<span>${escapeHtml(claim.customer.policy)}</span>`,
      `<span>${escapeHtml(claim.canton)}</span>`,
      `<span>${escapeHtml(claim.artifacts.length)} attachments</span>`,
      `<span>Generated research claim</span>`,
    ].join('');
    $('#customerMessage').innerHTML = formatMessage(claim);
    $('#attachmentCount').textContent = `${claim.artifacts.length} source files`;
    $('#attachmentList').innerHTML = claim.artifacts.map(a => `
      <button class="attachment-row" type="button" data-artifact-id="${escapeHtml(a.artifact_id)}">
        <span class="file-icon">${a.media_type === 'application/pdf' ? 'PDF' : a.media_type.startsWith('image/') ? 'IMG' : 'EML'}</span>
        <span><strong>${escapeHtml(a.title)}</strong><small>${escapeHtml(a.filename)} · ${escapeHtml(fileLabel(a))}</small></span>
        ${icon('chevron')}
      </button>`).join('');
    $$('.attachment-row').forEach(btn => btn.addEventListener('click', () => openArtifact(btn.dataset.artifactId)));
  }

  function stageSkeleton() {
    const stages = [
      ['read','Read the submission'],
      ['understand','Understand the claim'],
      ['research','Research Swiss tenant law'],
      ['process','Build the handling process'],
      ['evidence','Determine evidence needs'],
      ['experience','Find relevant experience'],
    ];
    $('#stageList').innerHTML = stages.map((s, i) => `
      <li class="stage-item" data-stage="${s[0]}" data-status="pending">
        <span class="stage-index">${i + 1}</span>
        <div><strong>${s[1]}</strong><p>Waiting</p></div>
        <span class="stage-state">Pending</span>
      </li>`).join('');
  }

  function renderEvents(run) {
    const latestByStage = {};
    for (const event of run.events || []) latestByStage[event.stage] = event;
    for (const [stage, event] of Object.entries(latestByStage)) {
      const row = $(`.stage-item[data-stage="${stage}"]`);
      if (!row) continue;
      row.dataset.status = event.status;
      $('p', row).textContent = event.headline || event.detail || '';
      $('.stage-state', row).textContent = event.status === 'completed' ? 'Done' : event.status === 'started' ? 'Working' : event.status;
      $('.stage-index', row).innerHTML = event.status === 'completed' ? icon('check') : $('.stage-index', row).textContent;
    }
    const active = [...(run.events || [])].reverse().find(e => e.status === 'started') || [...(run.events || [])].reverse().find(e => e.status === 'completed');
    if (active) {
      $('#analysisLive').innerHTML = `<div class="live-mark"><span></span></div><div><strong>${escapeHtml(active.headline || active.label)}</strong><p>${escapeHtml(active.detail || '')}</p></div>`;
    }
  }

  async function analyseClaim() {
    if (state.runId && state.run?.status === 'running') return;
    $('#analysis').hidden = false;
    $('#result').hidden = true;
    $('#review').hidden = true;
    $('#learning').hidden = true;
    $('#laterClaim').hidden = true;
    stageSkeleton();
    $('#analysis').scrollIntoView({ behavior:'smooth', block:'start' });
    $('#analyseBtn').disabled = true;
    $('#analyseBtn span').textContent = 'Analysis running';
    try {
      const created = await api('/api/runs', { method:'POST', body:JSON.stringify({ claim_id: state.claim.claim_id }) });
      state.runId = created.run_id;
      await pollRun();
    } catch (error) {
      $('#analysisLive').innerHTML = `<div><strong>Analysis could not start</strong><p>${escapeHtml(error.message)}</p></div>`;
      $('#analyseBtn').disabled = false;
      $('#analyseBtn span').textContent = 'Analyse claim';
    }
  }

  async function pollRun() {
    for (let i = 0; i < 160; i += 1) {
      const run = await api(`/api/runs/${state.runId}`);
      state.run = run;
      renderEvents(run);
      renderAudit();
      if (run.status === 'complete') {
        $('#analyseBtn').disabled = false;
        $('#analyseBtn span').textContent = 'Run again';
        renderResult(run.result);
        return;
      }
      if (run.status === 'failed') throw new Error(run.error || 'The run stopped safely');
      await new Promise(resolve => setTimeout(resolve, 250));
    }
    throw new Error('The analysis did not finish in time');
  }

  function renderDecisionSummary(result) {
    $('#decisionSummary').innerHTML = `
      <div class="decision-cell"><small>Where are we?</small><strong>${escapeHtml(result.process.nodes.find(n => n.node_id === result.process.current_node)?.title || 'Current process step')}</strong></div>
      <div class="decision-cell current"><small>Why are we here?</small><strong>${escapeHtml(result.current_blocker)}</strong></div>
      <div class="decision-cell"><small>What is still needed?</small><strong>${result.checklist.required.filter(x => x.status === 'still_needed').length} immediate evidence request${result.checklist.required.filter(x => x.status === 'still_needed').length === 1 ? '' : 's'}</strong></div>
      <div class="decision-cell"><small>What happens next?</small><strong>${escapeHtml(result.next_action.title)}</strong></div>`;
  }

  function markerFor(node) {
    if (node.state === 'complete' || node.state === 'supported') return icon('check');
    return node.state === 'current' ? '●' : node.state === 'next' ? String.fromCharCode(8594) : '·';
  }

  function renderProcess(result) {
    $('#processPath').innerHTML = result.process.nodes.map(node => `
      <div class="process-node ${escapeHtml(node.state)}" data-node-id="${escapeHtml(node.node_id)}">
        <span class="node-marker">${markerFor(node)}</span>
        <div>
          <button type="button" data-select-node="${escapeHtml(node.node_id)}"><h4>${escapeHtml(node.title)}</h4><p>${escapeHtml(node.answer)}</p><span class="node-state">${escapeHtml(node.state)}</span></button>
          ${node.branches ? `<div class="branch-box">${node.branches.map(b => `<div class="branch"><strong>${escapeHtml(b.label)}</strong><small>${escapeHtml(b.state)}</small></div>`).join('')}</div>` : ''}
        </div>
      </div>`).join('');
    $$('[data-select-node]').forEach(btn => btn.addEventListener('click', () => {
      state.selectedNode = btn.dataset.selectNode;
      renderEvidence(result, state.selectedNode);
      $$('.process-node').forEach(row => row.classList.toggle('selected', row.dataset.nodeId === state.selectedNode));
    }));
  }

  function evidenceItem(item) {
    const status = item.status || 'available';
    return `<div class="evidence-item ${escapeHtml(status)}"><span class="evidence-status"></span><div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.why)}</p>${item.artifact_id ? `<button type="button" data-artifact-id="${escapeHtml(item.artifact_id)}">Open source</button>` : ''}</div></div>`;
  }

  function renderEvidence(result, nodeId = 'cause') {
    const node = result.process.nodes.find(n => n.node_id === nodeId) || result.process.nodes.find(n => n.node_id === 'cause');
    const available = result.checklist.present.filter(x => x.node_id === node.node_id);
    const required = result.checklist.required.filter(x => x.node_id === node.node_id);
    $('#evidenceColumn').innerHTML = `
      <p class="context-label">Selected process question</p>
      <h3 class="evidence-question">${escapeHtml(node.question)}</h3>
      <p>${escapeHtml(node.answer)}</p>
      <div class="why-matters"><small>Why it matters</small><strong>${escapeHtml(node.why)}</strong></div>
      <div class="evidence-group"><div class="evidence-group-title"><h4>Already available</h4><span>${available.length}</span></div>${available.length ? available.map(evidenceItem).join('') : '<p class="fact-state">No source evidence is linked to this step yet.</p>'}</div>
      <div class="evidence-group"><div class="evidence-group-title"><h4>Evidence needed to answer this</h4><span>${required.length}</span></div>${required.length ? required.map(evidenceItem).join('') : '<p class="fact-state">No additional evidence is currently required for this step.</p>'}</div>`;
    $$('[data-artifact-id]', $('#evidenceColumn')).forEach(btn => btn.addEventListener('click', () => openArtifact(btn.dataset.artifactId)));
  }

  function sourceButtonForFact(fact) {
    const ref = (fact.source_refs || [])[0];
    if (!ref) return '';
    return `<button class="fact-source-button" type="button" data-fact-id="${escapeHtml(fact.fact_id)}" data-artifact-id="${escapeHtml(ref.artifact_id)}" data-page="${escapeHtml(ref.page || 1)}">View source</button>`;
  }

  function renderFacts(result) {
    $('#factsList').innerHTML = result.facts.map(f => `
      <div class="fact-row ${escapeHtml(f.state)}">
        <h4>${escapeHtml(f.label)}</h4>
        <div><div class="fact-value">${escapeHtml(f.value)}</div><div class="fact-state">${escapeHtml(f.explanation)}</div></div>
        ${sourceButtonForFact(f)}
      </div>`).join('');
    $$('.fact-source-button').forEach(btn => btn.addEventListener('click', () => openArtifact(btn.dataset.artifactId, Number(btn.dataset.page || 1), btn.dataset.factId)));
  }

  function renderLaw(result) {
    $('#lawList').innerHTML = result.legal_research.sources.map(s => `<div class="law-row"><a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">${escapeHtml(s.title)}</a><p>${escapeHtml(s.role)}</p></div>`).join('') + `<p class="law-note">${escapeHtml(result.legal_research.review_status)}</p>`;
  }

  function renderPrecedents(result) {
    $('#precedentList').innerHTML = result.precedents.map((p, idx) => `
      <article class="precedent-row">
        <div><div class="precedent-id">${escapeHtml(p.claim_id)}</div>${p.review_status === 'expert_reviewed_memory' ? '<span class="memory-label">Expert-reviewed precedent</span>' : ''}</div>
        <div><h4>${escapeHtml(p.title)}</h4><p><strong>Why this case helps:</strong> ${escapeHtml(p.why_useful)}</p></div>
        <button type="button" data-precedent-index="${idx}">Open claim</button>
      </article>`).join('');
    $$('[data-precedent-index]').forEach(btn => btn.addEventListener('click', () => openPrecedent(result.precedents[Number(btn.dataset.precedentIndex)])));
  }

  function renderResult(result) {
    $('#result').hidden = false;
    renderDecisionSummary(result);
    renderProcess(result);
    renderEvidence(result, 'cause');
    renderFacts(result);
    renderLaw(result);
    renderPrecedents(result);
    $('#review').hidden = false;
    $('#result').scrollIntoView({ behavior:'smooth', block:'start' });
  }

  async function submitReview(event) {
    event.preventDefault();
    const mode = $('input[name="envelopeMode"]:checked').value;
    const payload = {
      decision: 'approve_with_edit',
      building_envelope_mode: mode,
      confidence: Number($('#reviewConfidence').value) / 100,
      justification: $('#reviewReason').value.trim(),
    };
    const button = $('button[type="submit"]', $('#reviewForm'));
    button.disabled = true;
    button.textContent = 'Saving review';
    try {
      const saved = await api(`/api/runs/${state.runId}/review`, { method:'POST', body:JSON.stringify(payload) });
      state.run = await api(`/api/runs/${state.runId}`);
      renderResult(saved.result);
      renderAudit();
      renderLearning(saved);
      $('#learning').hidden = false;
      $('#review').hidden = true;
      $('#learning').scrollIntoView({ behavior:'smooth', block:'start' });
      toast('Review saved. The claim is now reusable case memory.');
    } catch (error) {
      toast(`Review not saved: ${error.message}`);
    } finally {
      button.disabled = false;
      button.textContent = 'Approve reviewed claim';
    }
  }

  function renderLearning(saved) {
    $('#learningNow').innerHTML = `
      <article class="learning-panel"><small>Available immediately</small><h3>Saved as a reviewed precedent</h3><p>Recurring mould, disputed causation and a ventilation allegation. Start with one neutral inspection; make broader building-envelope testing conditional.</p><p><strong>Memory:</strong> ${escapeHtml(saved.memory_id)}</p></article>
      <article class="learning-panel quarantined"><small>Not yet shared</small><h3>Reusable process change remains quarantined</h3><p>${escapeHtml(saved.candidate.proposed_change)}</p><div class="support-meter"><span></span></div><p><strong>1 of 3</strong> reviewed claims support the pattern. Target and protected regression tests have not run.</p></article>`;
  }

  async function showLearningProof() {
    const proof = await api('/api/learning-proof');
    if (!proof.ready) { toast(proof.message); return; }
    const later = await api(`/api/claims/${proof.later_claim_id}`);
    $('#laterClaim').hidden = false;
    $('#laterSource').innerHTML = `<div><p class="context-label">Unseen later claim</p><h3>${escapeHtml(later.subject)}</h3><small>${escapeHtml(later.claim_id)} · ${escapeHtml(later.artifacts.length)} source files</small></div><p>${escapeHtml(later.message)}</p>`;
    const list = items => `<ul class="compare-list">${items.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul>`;
    $('#beforeAfter').innerHTML = `
      <article class="compare-panel"><p class="context-label">Before reviewed memory</p><h3>Generic causation path</h3><p><strong>Evidence requested now</strong></p>${list(proof.before.evidence_now)}<p><strong>Precedents</strong></p>${list(proof.before.precedents)}<p>${proof.before.unnecessary_immediate_requests} unnecessary immediate technical request.</p></article>
      <article class="compare-panel after"><p class="context-label">After reviewed memory</p><h3>Expert-reviewed precedent used</h3><p><strong>Evidence requested now</strong></p>${list(proof.after.evidence_now)}<p><strong>Conditional evidence</strong></p>${list(proof.after.evidence_conditional)}<p><strong>Precedents</strong></p>${list(proof.after.precedents)}<div class="change-list"><strong>What improved</strong><ul>${proof.changes.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul></div></article>`;
    $('#laterClaim').scrollIntoView({ behavior:'smooth', block:'start' });
  }

  async function openArtifact(artifactId, page = 1, factId = null) {
    if (artifactId === 'message') {
      state.activeArtifact = { artifact_id:'message', title:'Original customer message', filename:'claim-message.eml', media_type:'message/rfc822', page_count:1, fact_ids:[] };
      state.activeArtifactExtraction = { email:{ from:`${state.claim.customer.name} <generated.customer@example.test>`, to:'claims@protekta.example', date:fmtDate(state.claim.received_at), subject:state.claim.subject, body:state.claim.message }, facts:[] };
      renderViewer(page, factId);
      return;
    }
    const artifact = state.claim?.artifacts.find(a => a.artifact_id === artifactId)
      || state.demo?.claim?.artifacts.find(a => a.artifact_id === artifactId)
      || state.demo?.later_claim?.artifacts?.find(a => a.artifact_id === artifactId);
    if (!artifact) { toast('Source file not found'); return; }
    state.activeArtifact = artifact;
    state.activeArtifactExtraction = await api(`/api/artifacts/${artifactId}/extraction`);
    renderViewer(page, factId);
  }

  function factsForArtifact(artifactId) {
    const result = state.run?.result;
    if (!result) return [];
    return (result.facts || []).filter(f => (f.source_refs || []).some(r => r.artifact_id === artifactId));
  }

  function renderViewer(page = 1, factId = null) {
    const a = state.activeArtifact;
    const extraction = state.activeArtifactExtraction || {};
    $('#viewerTitle').textContent = a.title;
    $('#viewerMeta').textContent = `${a.filename} · ${a.media_type} · ${a.page_count || 1} page${(a.page_count || 1) === 1 ? '' : 's'}`;
    $('#viewerKind').textContent = a.artifact_id === 'message' ? 'Original customer message' : 'Original source artifact';
    $('#downloadArtifact').href = a.artifact_id === 'message' ? '#' : `${API}/api/artifacts/${a.artifact_id}`;
    $('#downloadArtifact').style.visibility = a.artifact_id === 'message' ? 'hidden' : 'visible';
    const original = $('#originalView');
    if (a.media_type === 'application/pdf') {
      state.pdfPage = Math.max(1, Math.min(Number(page || 1), Number(a.page_count || 1)));
      state.imageZoom = 1;
      original.innerHTML = `<div class="pdf-toolbar"><button type="button" data-pdf-page="prev" aria-label="Previous PDF page">${icon('chevron')}</button><span><strong id="pdfCurrentPage">${state.pdfPage}</strong> / ${a.page_count}</span><button type="button" data-pdf-page="next" aria-label="Next PDF page">${icon('chevron')}</button><span class="toolbar-divider"></span><button type="button" data-pdf-zoom="out" aria-label="Zoom PDF out">${icon('zoomOut')}</button><button type="button" data-pdf-zoom="reset" aria-label="Reset PDF zoom">${icon('reset')}</button><button type="button" data-pdf-zoom="in" aria-label="Zoom PDF in">${icon('zoomIn')}</button></div><div class="pdf-page-wrap"><img id="pdfPageImage" alt="${escapeHtml(a.title)}, page ${state.pdfPage}" src="${API}/api/artifacts/${a.artifact_id}/pages/${state.pdfPage}"></div>`;
      $('[data-pdf-page="prev"]', original).style.transform='rotate(180deg)';
      $$('[data-pdf-page]', original).forEach(btn => btn.addEventListener('click', () => changePdfPage(btn.dataset.pdfPage)));
      $$('[data-pdf-zoom]', original).forEach(btn => btn.addEventListener('click', () => zoomPdf(btn.dataset.pdfZoom)));
    } else if (a.media_type.startsWith('image/')) {
      state.imageZoom = 1;
      original.innerHTML = `<div class="image-toolbar"><button type="button" data-image-zoom="out" aria-label="Zoom out">${icon('zoomOut')}</button><button type="button" data-image-zoom="reset" aria-label="Reset zoom">${icon('reset')}</button><button type="button" data-image-zoom="in" aria-label="Zoom in">${icon('zoomIn')}</button></div><img id="sourceImage" alt="${escapeHtml(a.title)}" src="${API}/api/artifacts/${a.artifact_id}">`;
      $$('[data-image-zoom]', original).forEach(btn => btn.addEventListener('click', () => zoomImage(btn.dataset.imageZoom)));
    } else if (a.media_type === 'message/rfc822') {
      const email = extraction.email || {};
      original.innerHTML = `<article class="email-source"><dl><dt>From</dt><dd>${escapeHtml(email.from)}</dd><dt>To</dt><dd>${escapeHtml(email.to)}</dd><dt>Date</dt><dd>${escapeHtml(email.date)}</dd><dt>Subject</dt><dd>${escapeHtml(email.subject)}</dd></dl><pre>${escapeHtml(email.body)}</pre></article>`;
    } else {
      original.innerHTML = `<p>Open the source file in a new tab.</p>`;
    }
    const extract = $('#extractionView');
    if (extraction.pages) {
      extract.innerHTML = extraction.pages.map((text, idx) => `<section class="extract-page"><h3>Page ${idx + 1}</h3><pre>${escapeHtml(text || 'No extractable text')}</pre></section>`).join('');
    } else if (extraction.email) {
      extract.innerHTML = `<section class="extract-page"><h3>Parsed email fields</h3><pre>${escapeHtml(JSON.stringify(extraction.email, null, 2))}</pre></section>`;
    } else {
      extract.innerHTML = `<section class="extract-page"><h3>Machine representation</h3><p>${escapeHtml(extraction.image_note || 'No derived representation is substituted for the source artifact.')}</p></section>`;
    }
    const linkedFacts = factsForArtifact(a.artifact_id);
    $('#sourceFacts').innerHTML = `<h3>Facts extracted from this source</h3>${linkedFacts.length ? linkedFacts.map(f => `<div class="source-fact"><strong>${escapeHtml(f.label)}</strong><p>${escapeHtml(f.value)} · ${escapeHtml(f.state)}</p></div>`).join('') : '<p class="fact-state">No accepted facts from the current run are linked to this source.</p>'}`;
    if (factId) {
      const target = linkedFacts.find(f => f.fact_id === factId);
      if (target) $('#sourceFacts').insertAdjacentHTML('afterbegin', `<div class="source-fact"><strong>Opened from: ${escapeHtml(target.label)}</strong><p>${escapeHtml(target.explanation)}</p></div>`);
    }
    setViewerTab('original');
    $('#artifactViewer').showModal();
  }

  function updatePdfImage() {
    const img=$('#pdfPageImage');
    if (!img || !state.activeArtifact) return;
    img.src=`${API}/api/artifacts/${state.activeArtifact.artifact_id}/pages/${state.pdfPage}`;
    img.alt=`${state.activeArtifact.title}, page ${state.pdfPage}`;
    img.style.transform=`scale(${state.imageZoom})`;
    const current=$('#pdfCurrentPage'); if(current) current.textContent=String(state.pdfPage);
  }

  function changePdfPage(direction) {
    const count=Number(state.activeArtifact?.page_count || 1);
    if(direction==='prev') state.pdfPage=Math.max(1,state.pdfPage-1);
    if(direction==='next') state.pdfPage=Math.min(count,state.pdfPage+1);
    updatePdfImage();
  }

  function zoomPdf(direction) {
    if(direction==='in') state.imageZoom=Math.min(2.5,state.imageZoom+.2);
    if(direction==='out') state.imageZoom=Math.max(.55,state.imageZoom-.2);
    if(direction==='reset') state.imageZoom=1;
    updatePdfImage();
  }

  function zoomImage(direction) {
    if (direction === 'in') state.imageZoom = Math.min(3, state.imageZoom + .25);
    if (direction === 'out') state.imageZoom = Math.max(.5, state.imageZoom - .25);
    if (direction === 'reset') state.imageZoom = 1;
    const img = $('#sourceImage'); if (img) img.style.transform = `scale(${state.imageZoom})`;
  }

  function setViewerTab(tab) {
    $$('.viewer-tabs [role="tab"]').forEach(btn => btn.setAttribute('aria-selected', String(btn.dataset.viewerTab === tab)));
    $('#originalView').hidden = tab !== 'original';
    $('#extractionView').hidden = tab !== 'extraction';
  }

  function renderAudit() {
    const events = state.run?.events || [];
    $('#auditContent').innerHTML = events.length ? events.map(e => `
      <details class="audit-event" ${e.status === 'started' ? 'open' : ''}>
        <summary><span></span><div><strong>${escapeHtml(e.label)}</strong><span>${escapeHtml(e.headline || '')}</span></div><span>${escapeHtml(e.status)}</span></summary>
        <div class="audit-event-body">
          <dl class="audit-grid"><dt>Specialist</dt><dd>${escapeHtml(e.agent || '')}</dd><dt>Implementation</dt><dd>${escapeHtml(e.implementation || '')}</dd><dt>Model</dt><dd>${escapeHtml(e.model || 'None - deterministic')}</dd><dt>Prompt</dt><dd>${escapeHtml(e.prompt_version || 'None')}</dd><dt>Validator</dt><dd>${escapeHtml(e.validator || '')}</dd><dt>Input hash</dt><dd>${escapeHtml(e.input_hash || 'Recorded in run root')}</dd><dt>Output hash</dt><dd>${escapeHtml(e.output_hash || '')}</dd></dl>
          ${e.detail ? `<p>${escapeHtml(e.detail)}</p>` : ''}
          ${e.items ? `<ul class="audit-items">${e.items.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul>` : ''}
        </div>
      </details>`).join('') : '<p>No run has started yet.</p>';
  }

  function openPrecedent(p) {
    $('#precedentTitle').textContent = p.title;
    $('#precedentContent').innerHTML = `
      <p><strong>Why this case helps:</strong> ${escapeHtml(p.why_useful)}</p>
      <section class="precedent-section"><h3>Original handling pattern</h3><ul>${(p.shared_features || []).map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul></section>
      <section class="precedent-section"><h3>Reviewed process</h3><ol>${(p.final_process || []).map(x => `<li>${escapeHtml(typeof x === 'string' ? x : x.title || JSON.stringify(x))}</li>`).join('')}</ol></section>
      <section class="precedent-section"><h3>Evidence used</h3><ul>${(p.evidence || []).map(x => `<li>${escapeHtml(typeof x === 'string' ? x : x.title || JSON.stringify(x))}</li>`).join('')}</ul></section>
      <section class="precedent-section"><h3>Expert correction</h3><p>${escapeHtml(p.expert_correction || 'No correction recorded.')}</p></section>
      <section class="precedent-section"><h3>Outcome</h3><p>${escapeHtml(p.outcome || 'Not recorded.')}</p></section>`;
    $('#precedentDialog').showModal();
  }

  function renderClaimsDrawer(items) {
    $('#claimDrawerList').innerHTML = items.map(c => `<button class="drawer-claim" type="button" data-claim-id="${escapeHtml(c.claim_id)}"><strong>${escapeHtml(c.subject)}</strong><p>${escapeHtml(c.message.slice(0, 170))}${c.message.length > 170 ? '…' : ''}</p><small>${escapeHtml(c.claim_id)} · ${c.artifacts.length} source files</small></button>`).join('') + `<button class="drawer-claim" id="resetDemoBtn" type="button"><strong>Reset the learning demo</strong><p>Remove public demo reviews and case memory.</p></button>`;
    $$('[data-claim-id]').forEach(btn => btn.addEventListener('click', () => {
      if (btn.dataset.claimId === state.demo.demo_claim_id) { $('#claimsDrawer').close(); document.querySelector('#submission').scrollIntoView({behavior:'smooth'}); }
      else { $('#claimsDrawer').close(); toast('The later claim opens after the first claim is reviewed.'); }
    }));
    $('#resetDemoBtn').addEventListener('click', async () => { await api('/api/demo/reset',{method:'POST'}); location.reload(); });
  }

  function wireDialogs() {
    $('#closeViewer').addEventListener('click', () => $('#artifactViewer').close());
    $('#closeAudit').addEventListener('click', () => $('#auditDrawer').close());
    $('#closeClaims').addEventListener('click', () => $('#claimsDrawer').close());
    $('#closePrecedent').addEventListener('click', () => $('#precedentDialog').close());
    $$('.viewer-tabs [role="tab"]').forEach(btn => btn.addEventListener('click', () => setViewerTab(btn.dataset.viewerTab)));
    $('#openAuditTop').addEventListener('click', () => { renderAudit(); $('#auditDrawer').showModal(); });
    $('#openAuditResult').addEventListener('click', () => { renderAudit(); $('#auditDrawer').showModal(); });
    $('#browseClaimsBtn').addEventListener('click', async () => { const data = await api('/api/claims'); renderClaimsDrawer(data.items); $('#claimsDrawer').showModal(); });
    [$('#artifactViewer'),$('#auditDrawer'),$('#claimsDrawer'),$('#precedentDialog')].forEach(dialog => dialog.addEventListener('click', e => { if (e.target === dialog) dialog.close(); }));
  }

  async function init() {
    wireDialogs();
    $('#analyseBtn').addEventListener('click', analyseClaim);
    $('#reviewForm').addEventListener('submit', submitReview);
    $('#reviewConfidence').addEventListener('input', e => $('#confidenceOutput').textContent = `${e.target.value}%`);
    $('#tryLearningBtn').addEventListener('click', showLearningProof);
    stageSkeleton();
    try {
      state.demo = await api('/api/demo');
      renderClaim(state.demo.claim);
      const knowledge = state.demo.knowledge;
      if ((knowledge.memories || []).length) {
        toast('A previous demo review exists. Reset from Claims to replay the learning loop.');
      }
    } catch (error) {
      document.querySelector('main').innerHTML = `<section class="intro"><div><p class="context-label">Connection problem</p><h1>CasePath could not load the demo.</h1><p class="intro-lede">${escapeHtml(error.message)}</p></div></section>`;
    }
  }

  init();
})();
