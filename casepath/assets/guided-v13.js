(() => {
  'use strict';

  const API = location.origin.replace(/\/$/, '');
  const GUIDE_TOTAL = 8;
  const state = {
    demo: null,
    claim: null,
    laterClaim: null,
    run: null,
    runId: null,
    result: null,
    guideStep: 0,
    reviewSaved: null,
    learningProof: null,
    activeArtifact: null,
    activeArtifactExtraction: null,
    imageZoom: 1,
    pdfPage: 1,
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const escapeHtml = (value = '') => String(value).replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[character]));
  const fmtDate = value => new Intl.DateTimeFormat('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
  }).format(new Date(value));
  const icon = name => {
    const paths = {
      chevron: '<path d="M9 6l6 6-6 6"/>',
      check: '<path d="M5 12.5l4 4L19 7"/>',
      external: '<path d="M14 5h5v5M13 11l6-6M19 13v6H5V5h6"/>',
      zoomIn: '<circle cx="11" cy="11" r="6"/><path d="M15.5 15.5L20 20M11 8v6M8 11h6"/>',
      zoomOut: '<circle cx="11" cy="11" r="6"/><path d="M15.5 15.5L20 20M8 11h6"/>',
      reset: '<path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.6M4 4v4.6h4.6"/>',
    };
    return `<svg aria-hidden="true" viewBox="0 0 24 24">${paths[name] || paths.check}</svg>`;
  };

  async function api(path, options = {}) {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
    if (!response.ok) {
      let message = `${response.status} ${response.statusText}`;
      try {
        const body = await response.json();
        message = body.detail || message;
      } catch (_) {}
      throw new Error(message);
    }
    return response.json();
  }

  function toast(message) {
    const element = $('#toast');
    element.textContent = message;
    element.classList.add('show');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => element.classList.remove('show'), 2600);
  }

  function formatMessage(claim) {
    return `
      <dl class="email-chrome">
        <dt>From</dt><dd>${escapeHtml(claim.customer.name)} &lt;customer@example.test&gt;</dd>
        <dt>To</dt><dd>claims@protekta.example</dd>
        <dt>Received</dt><dd>${escapeHtml(fmtDate(claim.received_at))}</dd>
        <dt>Subject</dt><dd>${escapeHtml(claim.subject)}</dd>
      </dl>
      <div class="email-body">${escapeHtml(claim.message)}</div>`;
  }

  function fileLabel(artifact) {
    if (artifact.media_type === 'application/pdf') return `PDF · ${artifact.page_count} page${artifact.page_count === 1 ? '' : 's'}`;
    if (artifact.media_type === 'message/rfc822') return 'Email · original message file';
    if (artifact.media_type?.startsWith('image/')) return 'Image · original file';
    return artifact.media_type || 'Source file';
  }

  function renderClaim(claim) {
    state.claim = claim;
    $('#claimMeta').innerHTML = [
      claim.claim_id,
      claim.customer?.policy,
      claim.canton,
      `${claim.artifacts.length} attachments`,
    ].filter(Boolean).map(item => `<span>${escapeHtml(item)}</span>`).join('');
    $('#customerMessage').innerHTML = formatMessage(claim);
    $('#attachmentCount').textContent = `${claim.artifacts.length} source files`;
    $('#attachmentList').innerHTML = claim.artifacts.map(artifact => `
      <button class="attachment-row" type="button" data-artifact-id="${escapeHtml(artifact.artifact_id)}">
        <span class="file-icon">${artifact.media_type === 'application/pdf' ? 'PDF' : artifact.media_type?.startsWith('image/') ? 'IMG' : 'EML'}</span>
        <span><strong>${escapeHtml(artifact.title)}</strong><small>${escapeHtml(artifact.filename)} · ${escapeHtml(fileLabel(artifact))}</small></span>
        ${icon('chevron')}
      </button>`).join('');
    $$('[data-artifact-id]', $('#attachmentList')).forEach(button => {
      button.addEventListener('click', () => openArtifact(button.dataset.artifactId));
    });
  }

  function stageSkeleton() {
    const stages = [
      ['read', 'Read the submission'],
      ['understand', 'Understand the claim'],
      ['research', 'Research Swiss tenant law'],
      ['process', 'Build the handling process'],
      ['evidence', 'Determine evidence needs'],
      ['experience', 'Find relevant experience'],
    ];
    $('#stageList').innerHTML = stages.map((stage, index) => `
      <li class="stage-item" data-stage="${stage[0]}" data-status="pending">
        <span class="stage-index">${index + 1}</span>
        <div><strong>${stage[1]}</strong><p>Waiting</p></div>
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
      if (event.status === 'completed') $('.stage-index', row).innerHTML = icon('check');
    }
    const events = run.events || [];
    const active = [...events].reverse().find(event => event.status === 'started') || [...events].reverse().find(event => event.status === 'completed');
    if (active) {
      $('#analysisLive').innerHTML = `<span class="live-mark" aria-hidden="true"><i></i></span><div><strong>${escapeHtml(active.headline || active.label)}</strong><p>${escapeHtml(active.detail || '')}</p></div>`;
    }
  }

  async function analyseClaim() {
    if (!state.claim || (state.runId && state.run?.status === 'running')) return;
    $('#analysis').hidden = false;
    $('#analysis').classList.remove('is-complete');
    $('#guide').hidden = true;
    state.result = null;
    state.reviewSaved = null;
    state.learningProof = null;
    state.guideStep = 0;
    stageSkeleton();
    $('#analysis').scrollIntoView({ behavior: 'smooth', block: 'start' });
    $('#analyseBtn').disabled = true;
    $('#analyseBtn span').textContent = 'Analysis running';
    try {
      const created = await api('/api/runs', {
        method: 'POST',
        body: JSON.stringify({ claim_id: state.claim.claim_id }),
      });
      state.runId = created.run_id;
      await pollRun();
    } catch (error) {
      $('#analysisLive').innerHTML = `<div><strong>Analysis could not start</strong><p>${escapeHtml(error.message)}</p></div>`;
      $('#analyseBtn').disabled = false;
      $('#analyseBtn span').textContent = 'Analyse claim';
    }
  }

  async function pollRun() {
    for (let attempt = 0; attempt < 180; attempt += 1) {
      const run = await api(`/api/runs/${state.runId}`);
      state.run = run;
      renderEvents(run);
      renderAudit();
      if (run.status === 'complete') {
        state.result = run.result;
        $('#analyseBtn').disabled = false;
        $('#analyseBtn span').textContent = 'Run again';
        $('#analysis').classList.add('is-complete');
        $('#analysisLive').innerHTML = `<span class="live-mark" aria-hidden="true"><i></i></span><div><strong>Analysis complete</strong><p>CasePath found one unresolved question that determines the next action.</p></div>`;
        $('#guide').hidden = false;
        state.guideStep = 0;
        renderGuide();
        $('#guide').scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
      }
      if (run.status === 'failed') throw new Error(run.error || 'The run stopped safely');
      await new Promise(resolve => setTimeout(resolve, 260));
    }
    throw new Error('The analysis did not finish in time');
  }

  function currentNode(result = state.result) {
    if (!result?.process?.nodes?.length) return null;
    return result.process.nodes.find(node => node.node_id === result.process.current_node)
      || result.process.nodes.find(node => node.state === 'current')
      || result.process.nodes[0];
  }

  function factStateClass(fact) {
    if (fact.state === 'unknown') return 'unknown';
    if (fact.state === 'conflicting') return 'conflicting';
    return 'known';
  }

  function knownFacts() {
    return (state.result?.facts || []).filter(fact => !['unknown', 'conflicting'].includes(fact.state));
  }

  function uncertainFacts() {
    return (state.result?.facts || []).filter(fact => ['unknown', 'conflicting'].includes(fact.state));
  }

  function sourceButtonForFact(fact, label = 'View source') {
    const ref = (fact.source_refs || [])[0];
    if (!ref) return '';
    return `<button type="button" data-open-fact="${escapeHtml(fact.fact_id)}" data-artifact-id="${escapeHtml(ref.artifact_id)}" data-page="${escapeHtml(ref.page || 1)}">${escapeHtml(label)}</button>`;
  }

  function bindSourceButtons(root = document) {
    $$('[data-open-fact]', root).forEach(button => {
      button.addEventListener('click', () => openArtifact(button.dataset.artifactId, Number(button.dataset.page || 1), button.dataset.openFact));
    });
    $$('[data-open-artifact]', root).forEach(button => {
      button.addEventListener('click', () => openArtifact(button.dataset.openArtifact, Number(button.dataset.page || 1)));
    });
    $$('[data-open-precedent]', root).forEach(button => {
      button.addEventListener('click', () => openPrecedent(state.result.precedents[Number(button.dataset.openPrecedent)]));
    });
  }

  function renderGuideDots() {
    $('#guideDots').innerHTML = Array.from({ length: GUIDE_TOTAL }, (_, index) => `
      <button class="guide-dot ${index < state.guideStep ? 'complete' : index === state.guideStep ? 'current' : ''}" type="button" disabled aria-label="Step ${index + 1}${index === state.guideStep ? ', current' : ''}"></button>`).join('');
    $('#guideStepNumber').textContent = String(state.guideStep + 1);
    $('#guideStepTotal').textContent = String(GUIDE_TOTAL);
  }

  function stageSubmission() {
    const claim = state.claim;
    const pdfs = claim.artifacts.filter(item => item.media_type === 'application/pdf').length;
    const images = claim.artifacts.filter(item => item.media_type?.startsWith('image/')).length;
    const correspondence = claim.artifacts.filter(item => item.media_type === 'message/rfc822').length;
    return `
      <div class="guide-stage-inner">
        <p class="stage-question">What did the customer send?</p>
        <h2 class="stage-answer" id="guideQuestion">One message and ${claim.artifacts.length} original files.</h2>
        <p class="stage-lede">CasePath read the exact sources as submitted. The original documents remain separate from anything the system extracted.</p>
        <div class="source-summary">
          <div class="source-summary-item"><small>Customer account</small><strong>1 original message</strong></div>
          <div class="source-summary-item"><small>Documents</small><strong>${pdfs + correspondence} formal source${pdfs + correspondence === 1 ? '' : 's'}</strong></div>
          <div class="source-summary-item"><small>Visual evidence</small><strong>${images} image${images === 1 ? '' : 's'}</strong></div>
        </div>
      </div>`;
  }

  function stageUnderstanding() {
    const facts = knownFacts().slice(0, 3);
    const unresolved = uncertainFacts()[0];
    const summary = state.result?.summary || state.result?.claim_summary || state.run?.understanding?.summary
      || 'A recurring rental-defect dispute in which notification is supported but responsibility is not yet established.';
    return `
      <div class="guide-stage-inner">
        <p class="stage-question">What does CasePath understand?</p>
        <h2 class="stage-answer" id="guideQuestion">${escapeHtml(summary)}</h2>
        <p class="stage-lede">CasePath keeps established facts separate from allegations, conflicts, and information that is still unknown.</p>
        <div class="fact-summary">
          ${facts.map(fact => `<div class="fact-summary-row ${factStateClass(fact)}"><span class="state-dot"></span><div><strong>${escapeHtml(fact.label)}: ${escapeHtml(fact.value)}</strong><p>${escapeHtml(fact.explanation)}</p></div>${sourceButtonForFact(fact)}</div>`).join('')}
          ${unresolved ? `<div class="fact-summary-row ${factStateClass(unresolved)}"><span class="state-dot"></span><div><strong>${escapeHtml(unresolved.label)}: ${escapeHtml(unresolved.value)}</strong><p>${escapeHtml(unresolved.explanation)}</p></div>${sourceButtonForFact(unresolved)}</div>` : ''}
        </div>
      </div>`;
  }

  function stageQuestion() {
    const node = currentNode();
    const nodes = state.result.process.nodes || [];
    const currentIndex = Math.max(0, nodes.findIndex(item => item.node_id === node.node_id));
    const preview = nodes.slice(Math.max(0, currentIndex - 2), currentIndex + 1);
    return `
      <div class="guide-stage-inner">
        <p class="stage-question">What legal or process question matters now?</p>
        <h2 class="stage-answer" id="guideQuestion">${escapeHtml(node.question || state.result.current_blocker)}</h2>
        <p class="stage-lede">${escapeHtml(node.why || 'The next handling step depends on the answer to this question.')}</p>
        <div class="path-preview">
          ${preview.map(item => `<div class="path-step ${item.node_id === node.node_id ? 'current' : ''}"><span class="path-mark">${item.node_id === node.node_id ? '•' : '✓'}</span><div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.node_id === node.node_id ? 'Current question' : item.answer)}</p></div></div>`).join('')}
        </div>
      </div>`;
  }

  function stageBlocker() {
    const node = currentNode();
    const branches = node.branches || [];
    return `
      <div class="guide-stage-inner">
        <p class="stage-question">What is blocking the claim?</p>
        <h2 class="stage-answer" id="guideQuestion">${escapeHtml(state.result.current_blocker || node.answer)}</h2>
        <p class="stage-lede">The available sources show that the condition exists, but they do not yet establish which explanation is more likely. Responsibility therefore remains open.</p>
        ${branches.length ? `<div class="branch-preview">${branches.map(branch => `<div class="branch-option"><strong>${escapeHtml(branch.label)}</strong><p>${escapeHtml(branch.detail || branch.next || 'Still possible')}</p></div>`).join('')}</div>` : ''}
      </div>`;
  }

  function stageEvidence() {
    const node = currentNode();
    const present = (state.result.checklist?.present || []).filter(item => item.node_id === node.node_id);
    const required = (state.result.checklist?.required || []).filter(item => item.node_id === node.node_id);
    const immediate = required.find(item => item.status === 'still_needed') || required[0];
    const conditional = required.find(item => item.status === 'conditional');
    return `
      <div class="guide-stage-inner">
        <p class="stage-question">What evidence would resolve the blocker?</p>
        <h2 class="stage-answer" id="guideQuestion">${escapeHtml(immediate?.title || 'Independent technical assessment')}</h2>
        <p class="stage-lede">${escapeHtml(immediate?.why || 'A neutral assessment can distinguish a building defect from other possible causes.')}</p>
        <div class="reason-chain">
          <div class="chain-step"><small>Current question</small><strong>${escapeHtml(node.question)}</strong></div>
          <div class="chain-step"><small>Fact still needed</small><strong>${escapeHtml(node.answer || 'Likely cause of the condition')}</strong></div>
          <div class="chain-step"><small>Evidence that can establish it</small><strong>${escapeHtml(immediate?.title || 'Independent technical assessment')}</strong></div>
        </div>
        <div class="evidence-focus">
          <small>Already available</small>
          <h3>${present.length} source item${present.length === 1 ? '' : 's'} support this question</h3>
          <p>${present.length ? escapeHtml(present.map(item => item.title).join(' · ')) : 'The current submission contains no evidence that resolves this question.'}${conditional ? ` Broader testing remains conditional: ${escapeHtml(conditional.title)}.` : ''}</p>
        </div>
      </div>`;
  }

  function stagePrecedents() {
    const precedents = state.result.precedents || [];
    return `
      <div class="guide-stage-inner">
        <p class="stage-question">Which previous cases are useful here?</p>
        <h2 class="stage-answer" id="guideQuestion">Three previous cases may help.</h2>
        <p class="stage-lede">They were retrieved because they reached the same process question, evidence gap, or expert-corrected branch—not merely because their wording was similar.</p>
        <div class="precedent-guide-list">
          ${precedents.map((precedent, index) => `<div class="precedent-guide-row"><small>${escapeHtml(precedent.claim_id)}</small><div><h3>${escapeHtml(precedent.title)}</h3><p>${escapeHtml(precedent.why_useful)}</p>${precedent.review_status === 'expert_reviewed_memory' ? '<span class="memory-tag">Expert-reviewed precedent</span>' : ''}</div><button type="button" data-open-precedent="${index}">Open case</button></div>`).join('')}
        </div>
      </div>`;
  }

  function stageReview() {
    return `
      <div class="guide-stage-inner">
        <p class="stage-question">What should the expert review or do next?</p>
        <h2 class="stage-answer" id="guideQuestion">Should broader building-envelope testing happen now?</h2>
        <p class="stage-lede">The consequential choice is the order of technical evidence. CasePath recommends one neutral inspection first, then broader testing only if the first assessment is inconclusive.</p>
        <form class="review-prompt" id="guidedReviewForm">
          <label class="review-choice recommended">
            <input type="radio" name="envelopeMode" value="conditional" checked>
            <span><strong>Make broader testing conditional</strong><small>Start with one neutral technical inspection. Request building-envelope testing only if the first assessment cannot establish the cause.</small></span>
          </label>
          <label class="review-choice">
            <input type="radio" name="envelopeMode" value="required_now">
            <span><strong>Request both assessments now</strong><small>Use this only when the current evidence already justifies both technical steps.</small></span>
          </label>
          <details class="review-note"><summary>Add a review note</summary><textarea id="reviewReason">Start with one neutral technical inspection. Keep broader building-envelope testing conditional on an inconclusive first assessment.</textarea></details>
          <button class="primary-action review-submit" type="submit">Approve reviewed plan</button>
          <p class="review-status" id="reviewStatus">This changes the evidence sequence, not the underlying claim facts.</p>
        </form>
      </div>`;
  }

  function stageLearning() {
    if (state.learningProof?.ready) return stageLearningProof();
    const saved = state.reviewSaved;
    return `
      <div class="guide-stage-inner">
        <p class="stage-question">What does CasePath learn after approval?</p>
        <h2 class="stage-answer" id="guideQuestion">The reviewed claim is now useful to future handlers.</h2>
        <p class="stage-lede">CasePath separates immediate case memory from changes to shared process knowledge.</p>
        <div class="learning-lines">
          <div class="learning-line available"><small>Available immediately</small><div><h3>Reviewed precedent</h3><p>The final process, evidence order, expert explanation, and next action can now be retrieved for similar claims.${saved?.memory_id ? ` Memory ${escapeHtml(saved.memory_id)}.` : ''}</p></div></div>
          <div class="learning-line quarantined"><small>Not yet shared</small><div><h3>Candidate reusable rule</h3><p>${escapeHtml(saved?.candidate?.proposed_change || 'A broader process rule remains quarantined until more reviewed cases support it and protected claims pass regression tests.')}</p></div></div>
        </div>
      </div>`;
  }

  function stageLearningProof() {
    const proof = state.learningProof;
    const before = proof.before || {};
    const after = proof.after || {};
    return `
      <div class="guide-stage-inner">
        <p class="stage-question">See this knowledge help with the next claim</p>
        <h2 class="stage-answer" id="guideQuestion">A later claim now avoids an unnecessary immediate request.</h2>
        <p class="stage-lede">The reviewed precedent changes the order of evidence without pretending that causation is already known.</p>
        <div class="before-after">
          <div class="before-after-panel"><small>Before reviewed memory</small><h3>Broad technical requests at once</h3><ul>${(before.evidence_now || []).map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>
          <div class="before-after-panel after"><small>After reviewed memory</small><h3>One neutral inspection first</h3><ul>${(after.evidence_now || []).map(item => `<li>${escapeHtml(item)}</li>`).join('')}${(after.evidence_conditional || []).map(item => `<li>${escapeHtml(item)} — conditional</li>`).join('')}</ul></div>
        </div>
        <div class="proof-change"><strong>What improved</strong><p>${escapeHtml((proof.changes || [])[0] || 'The reviewed precedent keeps the cause unresolved and removes an unnecessary immediate request.')}</p></div>
      </div>`;
  }

  const stageRenderers = [stageSubmission, stageUnderstanding, stageQuestion, stageBlocker, stageEvidence, stagePrecedents, stageReview, stageLearning];
  const nextLabels = [
    'See what CasePath understood',
    'See what matters now',
    'See what is blocking the claim',
    'See what evidence would resolve it',
    'See previous cases that may help',
    'Review the consequential decision',
    '',
    'See this knowledge help the next claim',
  ];
  const detailLabels = [
    'Open original files',
    'Review all facts',
    'See the full decision path',
    'Inspect competing evidence',
    'See all evidence needs',
    'Why these cases were retrieved',
    'See downstream effect',
    'See what was saved',
  ];

  function renderGuide() {
    if (!state.result) return;
    renderGuideDots();
    $('#guideStage').innerHTML = stageRenderers[state.guideStep]();
    bindSourceButtons($('#guideStage'));
    const back = $('#guideBack');
    const detail = $('#guideDetail');
    const next = $('#guideNext');
    back.disabled = state.guideStep === 0;
    detail.textContent = detailLabels[state.guideStep];
    next.hidden = state.guideStep === 6 || (state.guideStep === 7 && state.learningProof?.ready);
    next.querySelector('span').textContent = nextLabels[state.guideStep] || 'Continue';
    if (state.guideStep === 6) $('#guidedReviewForm').addEventListener('submit', submitGuidedReview);
  }

  function nextGuide() {
    if (state.guideStep === 7) {
      showLearningProof();
      return;
    }
    if (state.guideStep < GUIDE_TOTAL - 1) {
      state.guideStep += 1;
      renderGuide();
      $('#guide').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function backGuide() {
    if (state.guideStep > 0) {
      state.guideStep -= 1;
      renderGuide();
      $('#guide').scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  async function submitGuidedReview(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const button = $('button[type="submit"]', form);
    const mode = $('input[name="envelopeMode"]:checked', form).value;
    const reason = $('#reviewReason')?.value.trim() || 'Start with one neutral technical inspection. Keep broader building-envelope testing conditional on an inconclusive first assessment.';
    button.disabled = true;
    button.textContent = 'Saving review';
    $('#reviewStatus').textContent = 'Saving the corrected evidence sequence…';
    try {
      const saved = await api(`/api/runs/${state.runId}/review`, {
        method: 'POST',
        body: JSON.stringify({ decision: 'approve_with_edit', building_envelope_mode: mode, confidence: 0.92, justification: reason }),
      });
      state.reviewSaved = saved;
      state.result = saved.result;
      state.run = await api(`/api/runs/${state.runId}`);
      renderAudit();
      state.guideStep = 7;
      renderGuide();
      $('#guide').scrollIntoView({ behavior: 'smooth', block: 'start' });
      toast('Review saved. The claim is now reusable case memory.');
    } catch (error) {
      button.disabled = false;
      button.textContent = 'Approve reviewed plan';
      $('#reviewStatus').textContent = `Review not saved: ${error.message}`;
    }
  }

  async function showLearningProof() {
    const next = $('#guideNext');
    next.disabled = true;
    next.querySelector('span').textContent = 'Loading the later claim';
    try {
      const proof = await api('/api/learning-proof');
      if (!proof.ready) {
        toast(proof.message || 'The learning proof is not ready.');
        next.disabled = false;
        next.querySelector('span').textContent = nextLabels[7];
        return;
      }
      state.learningProof = proof;
      state.laterClaim = await api(`/api/claims/${proof.later_claim_id}`);
      renderGuide();
      $('#guide').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (error) {
      toast(`The later claim could not load: ${error.message}`);
      next.disabled = false;
      next.querySelector('span').textContent = nextLabels[7];
    }
  }

  function openDetailForStep() {
    if (state.guideStep === 0) {
      $('#source').scrollIntoView({ behavior: 'smooth', block: 'start' });
      return;
    }
    const renderers = [null, detailFacts, detailProcess, detailBlocker, detailChecklist, detailPrecedents, detailReview, detailLearning];
    renderers[state.guideStep]();
    bindSourceButtons($('#detailContent'));
    $('#detailDialog').showModal();
  }

  function setDetail(kind, title, intro, content) {
    $('#detailKind').textContent = kind;
    $('#detailTitle').textContent = title;
    $('#detailIntro').textContent = intro;
    $('#detailContent').innerHTML = content;
  }

  function detailFacts() {
    const facts = state.result.facts || [];
    setDetail('Evidence and facts', 'Everything CasePath accepted', 'Each conclusion remains linked to the original source that supports it.', `<section class="detail-section"><div class="detail-list">${facts.map(fact => `<div class="detail-row"><strong>${escapeHtml(fact.label)}</strong><div><p><b>${escapeHtml(fact.value)}</b></p><p>${escapeHtml(fact.explanation)}</p></div>${sourceButtonForFact(fact)}</div>`).join('')}</div></section>`);
  }

  function detailProcess() {
    const nodes = state.result.process.nodes || [];
    const current = currentNode();
    setDetail('Decision path', 'The full handling path', 'Completed steps stay quiet. The current question is dominant. Alternative branches remain collapsed until requested.', `
      <section class="detail-section"><div class="detail-path">${nodes.map((node, index) => `<div class="detail-path-node ${node.node_id === current.node_id ? 'current' : ['complete', 'supported'].includes(node.state) ? 'complete' : ''}"><span>${node.node_id === current.node_id ? '•' : ['complete', 'supported'].includes(node.state) ? '✓' : index + 1}</span><div><strong>${escapeHtml(node.title)}</strong><p>${escapeHtml(node.question || node.answer)}</p></div></div>`).join('')}</div></section>
      ${current.branches?.length ? `<section class="detail-section branch-details"><details><summary>Show ${current.branches.length} alternative outcomes</summary><div class="branch-detail-grid">${current.branches.map(branch => `<div class="branch-detail"><strong>${escapeHtml(branch.label)}</strong><p>${escapeHtml(branch.detail || branch.next || 'Alternative branch')}</p></div>`).join('')}</div></details></section>` : ''}
      <section class="detail-section"><h3>Legal sources that shape this question</h3><div class="detail-list">${(state.result.legal_research?.sources || []).map(source => `<div class="detail-row"><strong>${escapeHtml(source.title)}</strong><p>${escapeHtml(source.role)}</p><a href="${escapeHtml(source.url)}" target="_blank" rel="noopener">Open source</a></div>`).join('')}</div></section>`);
  }

  function detailBlocker() {
    const current = currentNode();
    const related = (state.result.facts || []).filter(fact => (current.fact_ids || []).includes(fact.fact_id) || ['unknown', 'conflicting'].includes(fact.state));
    setDetail('Competing evidence', 'Why the current question remains open', 'The system preserves allegations and contradictions instead of converting them into conclusions.', `<section class="detail-section"><div class="detail-list">${related.map(fact => `<div class="detail-row"><strong>${escapeHtml(fact.label)}</strong><div><p><b>${escapeHtml(fact.value)}</b></p><p>${escapeHtml(fact.explanation)}</p></div>${sourceButtonForFact(fact)}</div>`).join('')}</div></section>`);
  }

  function detailChecklist() {
    const present = state.result.checklist?.present || [];
    const required = state.result.checklist?.required || [];
    const group = (title, items) => `<section class="detail-section"><h3>${escapeHtml(title)}</h3><div class="detail-list">${items.length ? items.map(item => `<div class="detail-row"><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.why)}</p>${item.artifact_id ? `<button type="button" data-open-artifact="${escapeHtml(item.artifact_id)}">Open source</button>` : `<small>${escapeHtml((item.status || '').replace('_', ' '))}</small>`}</div>`).join('') : '<p>No items in this group.</p>'}</div></section>`;
    setDetail('Process-linked evidence', 'All evidence needs', 'Every item answers a process question. This is the aggregated checklist view, not the starting point.', group('Already available', present) + group('Still needed or conditional', required));
  }

  function detailPrecedents() {
    const precedents = state.result.precedents || [];
    setDetail('Organizational memory', 'Why these cases were retrieved', 'The ranking uses the same legal question, process branch, unresolved fact, evidence need, and expert correction.', `<section class="detail-section"><div class="detail-list">${precedents.map((precedent, index) => `<div class="detail-row"><strong>${escapeHtml(precedent.claim_id)}</strong><div><p><b>${escapeHtml(precedent.title)}</b></p><p>${escapeHtml(precedent.why_useful)}</p></div><button type="button" data-open-precedent="${index}">Open case</button></div>`).join('')}</div></section>`);
  }

  function detailReview() {
    setDetail('Expert correction', 'What this choice changes', 'The correction updates the evidence sequence. It does not rewrite supported facts or release a shared rule.', `<section class="detail-section"><div class="reason-chain"><div class="chain-step"><small>Before</small><strong>Neutral inspection and building-envelope assessment requested immediately</strong></div><div class="chain-step"><small>Expert correction</small><strong>Keep broader testing conditional</strong></div><div class="chain-step"><small>After</small><strong>One targeted request now; broader assessment only if needed</strong></div></div></section>`);
  }

  function detailLearning() {
    const saved = state.reviewSaved;
    setDetail('Knowledge impact', 'What was saved', 'Immediate case memory and shared process knowledge follow different safety rules.', `<section class="detail-section"><div class="detail-list"><div class="detail-row"><strong>Reviewed precedent</strong><p>Available to future historical-claim retrieval immediately.</p><small>${escapeHtml(saved?.memory_id || 'Saved')}</small></div><div class="detail-row"><strong>Candidate reusable rule</strong><p>${escapeHtml(saved?.candidate?.proposed_change || 'Still requires repeated expert support and regression testing.')}</p><small>Quarantined</small></div></div></section>`);
  }

  async function openArtifact(artifactId, page = 1, factId = null) {
    if (artifactId === 'message') {
      state.activeArtifact = { artifact_id: 'message', title: 'Original customer message', filename: 'claim-message.eml', media_type: 'message/rfc822', page_count: 1 };
      state.activeArtifactExtraction = { email: { from: `${state.claim.customer.name} <customer@example.test>`, to: 'claims@protekta.example', date: fmtDate(state.claim.received_at), subject: state.claim.subject, body: state.claim.message } };
      renderViewer(page, factId);
      return;
    }
    const allArtifacts = [...(state.claim?.artifacts || []), ...(state.laterClaim?.artifacts || [])];
    const artifact = allArtifacts.find(item => item.artifact_id === artifactId);
    if (!artifact) {
      toast('Source file not found');
      return;
    }
    state.activeArtifact = artifact;
    state.activeArtifactExtraction = await api(`/api/artifacts/${artifactId}/extraction`);
    renderViewer(page, factId);
  }

  function factsForArtifact(artifactId) {
    return (state.result?.facts || []).filter(fact => (fact.source_refs || []).some(ref => ref.artifact_id === artifactId));
  }

  function renderViewer(page = 1, factId = null) {
    const artifact = state.activeArtifact;
    const extraction = state.activeArtifactExtraction || {};
    $('#viewerTitle').textContent = artifact.title;
    $('#viewerMeta').textContent = `${artifact.filename} · ${artifact.media_type} · ${artifact.page_count || 1} page${(artifact.page_count || 1) === 1 ? '' : 's'}`;
    $('#viewerKind').textContent = artifact.artifact_id === 'message' ? 'Original customer message' : 'Original source artifact';
    $('#downloadArtifact').href = artifact.artifact_id === 'message' ? '#' : `${API}/api/artifacts/${artifact.artifact_id}`;
    $('#downloadArtifact').style.visibility = artifact.artifact_id === 'message' ? 'hidden' : 'visible';
    const original = $('#originalView');
    if (artifact.media_type === 'application/pdf') {
      state.pdfPage = Math.max(1, Math.min(Number(page || 1), Number(artifact.page_count || 1)));
      state.imageZoom = 1;
      original.innerHTML = `<div class="pdf-toolbar"><button type="button" data-pdf-page="prev" aria-label="Previous PDF page">${icon('chevron')}</button><span><strong id="pdfCurrentPage">${state.pdfPage}</strong> / ${artifact.page_count}</span><button type="button" data-pdf-page="next" aria-label="Next PDF page">${icon('chevron')}</button><span class="toolbar-divider"></span><button type="button" data-pdf-zoom="out" aria-label="Zoom PDF out">${icon('zoomOut')}</button><button type="button" data-pdf-zoom="reset" aria-label="Reset PDF zoom">${icon('reset')}</button><button type="button" data-pdf-zoom="in" aria-label="Zoom PDF in">${icon('zoomIn')}</button></div><div class="pdf-page-wrap"><img id="pdfPageImage" alt="${escapeHtml(artifact.title)}, page ${state.pdfPage}" src="${API}/api/artifacts/${artifact.artifact_id}/pages/${state.pdfPage}"></div>`;
      $('[data-pdf-page="prev"]', original).style.transform = 'rotate(180deg)';
      $$('[data-pdf-page]', original).forEach(button => button.addEventListener('click', () => changePdfPage(button.dataset.pdfPage)));
      $$('[data-pdf-zoom]', original).forEach(button => button.addEventListener('click', () => zoomPdf(button.dataset.pdfZoom)));
    } else if (artifact.media_type?.startsWith('image/')) {
      state.imageZoom = 1;
      original.innerHTML = `<div class="image-toolbar"><button type="button" data-image-zoom="out" aria-label="Zoom out">${icon('zoomOut')}</button><button type="button" data-image-zoom="reset" aria-label="Reset zoom">${icon('reset')}</button><button type="button" data-image-zoom="in" aria-label="Zoom in">${icon('zoomIn')}</button></div><img id="sourceImage" alt="${escapeHtml(artifact.title)}" src="${API}/api/artifacts/${artifact.artifact_id}">`;
      $$('[data-image-zoom]', original).forEach(button => button.addEventListener('click', () => zoomImage(button.dataset.imageZoom)));
    } else if (artifact.media_type === 'message/rfc822') {
      const email = extraction.email || {};
      original.innerHTML = `<article class="email-source"><dl><dt>From</dt><dd>${escapeHtml(email.from)}</dd><dt>To</dt><dd>${escapeHtml(email.to)}</dd><dt>Date</dt><dd>${escapeHtml(email.date)}</dd><dt>Subject</dt><dd>${escapeHtml(email.subject)}</dd></dl><pre>${escapeHtml(email.body)}</pre></article>`;
    } else {
      original.innerHTML = '<p>Open the source file in a new tab.</p>';
    }

    if (extraction.pages) {
      $('#extractionView').innerHTML = extraction.pages.map((text, index) => `<section class="extract-page"><h3>Page ${index + 1}</h3><pre>${escapeHtml(text || 'No extractable text')}</pre></section>`).join('');
    } else if (extraction.email) {
      $('#extractionView').innerHTML = `<section class="extract-page"><h3>Parsed email fields</h3><pre>${escapeHtml(JSON.stringify(extraction.email, null, 2))}</pre></section>`;
    } else {
      $('#extractionView').innerHTML = `<section class="extract-page"><h3>Machine representation</h3><p>${escapeHtml(extraction.image_note || 'No derived representation is substituted for the source artifact.')}</p></section>`;
    }

    const linkedFacts = factsForArtifact(artifact.artifact_id);
    const opened = factId ? linkedFacts.find(fact => fact.fact_id === factId) : null;
    $('#sourceFacts').innerHTML = `${opened ? `<div class="source-fact opened"><strong>Opened from: ${escapeHtml(opened.label)}</strong><p>${escapeHtml(opened.explanation)}</p></div>` : ''}<h3>Facts extracted from this source</h3>${linkedFacts.length ? linkedFacts.map(fact => `<div class="source-fact"><strong>${escapeHtml(fact.label)}</strong><p>${escapeHtml(fact.value)} · ${escapeHtml(fact.state)}</p></div>`).join('') : '<p>No accepted facts from the current run are linked to this source.</p>'}`;
    setViewerTab('original');
    $('#artifactViewer').showModal();
  }

  function updatePdfImage() {
    const image = $('#pdfPageImage');
    if (!image || !state.activeArtifact) return;
    image.src = `${API}/api/artifacts/${state.activeArtifact.artifact_id}/pages/${state.pdfPage}`;
    image.alt = `${state.activeArtifact.title}, page ${state.pdfPage}`;
    image.style.transform = `scale(${state.imageZoom})`;
    if ($('#pdfCurrentPage')) $('#pdfCurrentPage').textContent = String(state.pdfPage);
  }

  function changePdfPage(direction) {
    const count = Number(state.activeArtifact?.page_count || 1);
    if (direction === 'prev') state.pdfPage = Math.max(1, state.pdfPage - 1);
    if (direction === 'next') state.pdfPage = Math.min(count, state.pdfPage + 1);
    updatePdfImage();
  }

  function zoomPdf(direction) {
    if (direction === 'in') state.imageZoom = Math.min(2.5, state.imageZoom + .2);
    if (direction === 'out') state.imageZoom = Math.max(.55, state.imageZoom - .2);
    if (direction === 'reset') state.imageZoom = 1;
    updatePdfImage();
  }

  function zoomImage(direction) {
    if (direction === 'in') state.imageZoom = Math.min(3, state.imageZoom + .25);
    if (direction === 'out') state.imageZoom = Math.max(.5, state.imageZoom - .25);
    if (direction === 'reset') state.imageZoom = 1;
    const image = $('#sourceImage');
    if (image) image.style.transform = `scale(${state.imageZoom})`;
  }

  function setViewerTab(tab) {
    $$('.viewer-tabs [role="tab"]').forEach(button => button.setAttribute('aria-selected', String(button.dataset.viewerTab === tab)));
    $('#originalView').hidden = tab !== 'original';
    $('#extractionView').hidden = tab !== 'extraction';
  }

  function renderAudit() {
    const events = state.run?.events || [];
    $('#auditContent').innerHTML = events.length ? events.map(event => `
      <details class="audit-event" ${event.status === 'started' ? 'open' : ''}>
        <summary><span></span><div><strong>${escapeHtml(event.label)}</strong><span>${escapeHtml(event.headline || '')}</span></div><span>${escapeHtml(event.status)}</span></summary>
        <div class="audit-event-body">
          <dl class="audit-grid"><dt>Specialist</dt><dd>${escapeHtml(event.agent || '')}</dd><dt>Implementation</dt><dd>${escapeHtml(event.implementation || '')}</dd><dt>Model</dt><dd>${escapeHtml(event.model || 'None — deterministic')}</dd><dt>Prompt</dt><dd>${escapeHtml(event.prompt_version || 'None')}</dd><dt>Validator</dt><dd>${escapeHtml(event.validator || '')}</dd><dt>Input hash</dt><dd>${escapeHtml(event.input_hash || 'Recorded in run root')}</dd><dt>Output hash</dt><dd>${escapeHtml(event.output_hash || '')}</dd></dl>
          ${event.detail ? `<p>${escapeHtml(event.detail)}</p>` : ''}
          ${event.items ? `<ul class="audit-items">${event.items.map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul>` : ''}
        </div>
      </details>`).join('') : '<p>No run has started yet.</p>';
  }

  function openPrecedent(precedent) {
    $('#precedentTitle').textContent = precedent.title;
    $('#precedentContent').innerHTML = `
      <p><strong>Why this case helps:</strong> ${escapeHtml(precedent.why_useful)}</p>
      <section class="precedent-section"><h3>What was similar</h3><ul>${(precedent.shared_features || []).map(item => `<li>${escapeHtml(item)}</li>`).join('')}</ul></section>
      <section class="precedent-section"><h3>Reviewed process</h3><ol>${(precedent.final_process || []).map(item => `<li>${escapeHtml(typeof item === 'string' ? item : item.title || JSON.stringify(item))}</li>`).join('')}</ol></section>
      <section class="precedent-section"><h3>Evidence that resolved it</h3><ul>${(precedent.evidence || []).map(item => `<li>${escapeHtml(typeof item === 'string' ? item : item.title || JSON.stringify(item))}</li>`).join('')}</ul></section>
      <section class="precedent-section"><h3>Expert correction</h3><p>${escapeHtml(precedent.expert_correction || 'No correction recorded.')}</p></section>
      <section class="precedent-section"><h3>Outcome</h3><p>${escapeHtml(precedent.outcome || 'Not recorded.')}</p></section>`;
    $('#precedentDialog').showModal();
  }

  function renderClaimsDrawer(items) {
    $('#claimDrawerList').innerHTML = items.map(claim => `<button class="drawer-claim" type="button" data-claim-id="${escapeHtml(claim.claim_id)}"><strong>${escapeHtml(claim.subject)}</strong><p>${escapeHtml(claim.message.slice(0, 170))}${claim.message.length > 170 ? '…' : ''}</p><small>${escapeHtml(claim.claim_id)} · ${claim.artifacts.length} source files</small></button>`).join('') + `<button class="drawer-claim" id="resetDemoBtn" type="button"><strong>Reset the learning demo</strong><p>Remove public demo reviews and case memory.</p></button>`;
    $$('[data-claim-id]', $('#claimDrawerList')).forEach(button => button.addEventListener('click', () => {
      $('#claimsDrawer').close();
      if (button.dataset.claimId === state.demo.demo_claim_id) $('#submission').scrollIntoView({ behavior: 'smooth' });
      else toast('The later claim appears after the first claim is reviewed.');
    }));
    $('#resetDemoBtn').addEventListener('click', async () => {
      await api('/api/demo/reset', { method: 'POST' });
      location.reload();
    });
  }

  function wireDialogs() {
    $('#closeViewer').addEventListener('click', () => $('#artifactViewer').close());
    $('#closeDetail').addEventListener('click', () => $('#detailDialog').close());
    $('#closeAudit').addEventListener('click', () => $('#auditDrawer').close());
    $('#closeClaims').addEventListener('click', () => $('#claimsDrawer').close());
    $('#closePrecedent').addEventListener('click', () => $('#precedentDialog').close());
    $$('.viewer-tabs [role="tab"]').forEach(button => button.addEventListener('click', () => setViewerTab(button.dataset.viewerTab)));
    const openAudit = () => { renderAudit(); $('#auditDrawer').showModal(); };
    $('#openAuditTop').addEventListener('click', openAudit);
    $('#openAuditGuide').addEventListener('click', openAudit);
    $('#browseClaimsBtn').addEventListener('click', async () => {
      const data = await api('/api/claims');
      renderClaimsDrawer(data.items);
      $('#claimsDrawer').showModal();
    });
    [$('#artifactViewer'), $('#detailDialog'), $('#auditDrawer'), $('#claimsDrawer'), $('#precedentDialog')].forEach(dialog => {
      dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
    });
  }

  async function init() {
    wireDialogs();
    $('#analyseBtn').addEventListener('click', analyseClaim);
    $('#guideNext').addEventListener('click', nextGuide);
    $('#guideBack').addEventListener('click', backGuide);
    $('#guideDetail').addEventListener('click', openDetailForStep);
    stageSkeleton();
    try {
      state.demo = await api('/api/demo');
      renderClaim(state.demo.claim);
      if ((state.demo.knowledge?.memories || []).length) toast('A previous demo review exists. Reset from Claims to replay the learning loop.');
    } catch (error) {
      $('#main').innerHTML = `<section class="intro"><div><p class="eyebrow">Connection problem</p><h1>CasePath could not load the demo.</h1><p class="intro-lede">${escapeHtml(error.message)}</p></div></section>`;
    }
  }

  init();
})();
