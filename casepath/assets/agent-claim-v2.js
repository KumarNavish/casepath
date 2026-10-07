/* Claim-facing agent controls. Journal and run projections supply every state. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CasePathAgentClaim = api;
})(typeof globalThis === 'object' ? globalThis : this, function (global) {
  'use strict';
  const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const label = value => {const text = String(value ?? ''); return (/^[A-Z_]+$/.test(text) ? text.toLowerCase() : text).replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());};
  const states = {working:'Working', waiting_for_you:'Waiting for you', waiting_for_others:'Waiting for others', paused:'Paused', done:'Done', failed:'Failed', unknown:'Not yet checked'};
  const canClearPause = agent => agent.pause_requested === true && agent.recovery_required !== true && agent.run?.status === 'completed' && agent.run.facts_worker === 'reference' && agent.run.provider_requests === 0 && Array.isArray(agent.run.pending_calls) && agent.run.pending_calls.length === 0;
  const inspectRecovery = agent => !canClearPause(agent) && (agent.recovery_required === true || agent.pause_requested || ['paused', 'failed', 'unknown'].includes(agent.state)) && (agent.run ? agent.run.recovery?.can_resume !== true || agent.run.facts_worker !== 'reference' : agent.recovery_required === true);
  const sessions = new Map(), bindings = new WeakMap();
  const session = id => {
    if (!sessions.has(id)) sessions.set(id, {answers:{}, reasons:{}, preview:null, lessonPreview:null, error:'', notice:'', busy:false, sources:[], open:new Set()});
    return sessions.get(id);
  };
  const button = (text, attrs = '', primary = false) => `<button type="button" class="av-button${primary ? ' av-button-primary' : ''}" ${attrs}>${h(text)}</button>`;
  const sourceText = source => {
    if (source.role === 'customer_message' || source.media_type === 'message/rfc822' || source.extraction === 'message_body') return 'Customer message';
    const filename = source.file_name || source.filename || source.title;
    return global.CasePathPresentation?.fileTitle ? global.CasePathPresentation.fileTitle({...source, file_name:filename}) : String(filename || 'Original source').replaceAll('_', ' ');
  };
  function citation(source, s, text) {
    if (!source || !(source.quote || source.exact_text || source.locator?.exact_text)) return '';
    const artifacts = Array.isArray(s.input?.sources) ? s.input.sources : s.input?.sources?.artifacts || [];
    const original = artifacts.find(item => item.artifact_id === source.artifact_id) || {};
    const span = {...original, ...source}, index = s.sources.push(span) - 1;
    const filename = span.file_name || span.filename || span.title;
    return button(text || `${sourceText(span)}${span.page ? ` · page ${span.page}` : ''}`, `data-av-source="${index}"${filename ? ` title="${h(filename)}"` : ''}`, false);
  }
  function mandateMarkup(agent, s) {
    const mandate = agent.mandate || {};
    return `<details class="av-mandate" data-av-disclosure="mandate"${s.open.has('mandate') ? ' open' : ''}><summary id="avMandateSummary">Agent mandate</summary><div class="av-mandate-columns"><div><h3>Works unattended</h3><ul>${(mandate.unattended || []).map(item => `<li>${h(item)}</li>`).join('')}</ul></div><div><h3>Waits for your approval</h3><ul>${(mandate.requires_handler || []).map(item => `<li>${h(item)}</li>`).join('')}</ul></div></div></details>`;
  }
  function questionMarkup(question, s, owner) {
    const id = question.question_id, answer = s.answers[id] || question.proposal?.answer_id;
    const override = answer !== question.proposal?.answer_id, reasonId = `av-reason-${id}`, locked = s.busy || s.pending;
    const citations = (question.sources || []).map(source => `<li>${citation(source, s)}${source.quote ? `<blockquote>${h(source.quote)}</blockquote>` : ''}</li>`).join('');
    const action = question.previewable ? `<fieldset class="av-answer-list"><legend>Choose your answer</legend>${(question.answers || []).map(item => `<label class="av-answer" data-proposed="${item.answer_id === question.proposal?.answer_id}"><input type="radio" name="answer_id" value="${h(item.answer_id)}"${item.answer_id === answer ? ' checked' : ''} required${locked ? ' disabled' : ''}><span><strong>${h(item.label)}</strong>${item.answer_id === question.proposal?.answer_id ? '<small class="av-proposal-label">Agent proposal · not saved</small>' : ''}${item.description ? `<span>${h(item.description)}</span>` : ''}</span></label>`).join('')}</fieldset>
      <div class="av-decision-reason"${override ? '' : ' hidden'}><label for="${h(reasonId)}">Reason for choosing another answer</label><textarea id="${h(reasonId)}" name="reason" maxlength="2000" aria-describedby="${h(reasonId)}-help"${override ? ' required' : ''}${locked ? ' disabled' : ''}>${h(s.reasons[id] || '')}</textarea><small id="${h(reasonId)}-help">Your reason stays with this decision. Reuse is a separate approval.</small></div>
      ${owner ? `<input type="hidden" name="actor" value="${h(owner)}">` : `<label class="av-reviewing-handler">Reviewing handler<input name="actor" required maxlength="80" autocomplete="name" value="${h(s.actors?.[id] || '')}"></label>`}
      <div class="av-decision-actions"><button type="submit" class="av-button av-button-primary"${locked ? ' disabled' : ''}>Preview consequences</button><span>Preview first. Apply saves your answer and starts the next review. Drafts stay not sent.</span></div>` : `<div class="av-decision-actions">${button(question.pane === 'draft' ? 'Review draft, not sent' : question.pane === 'process' ? 'Review process' : 'Open source review', `data-av-pane="${h(question.pane === 'draft' ? 'documents' : question.pane || 'sources')}"`)}<span>The source gap stays open until reviewed.</span></div>`;
    const draft = question.kind === 'draft_approval' ? `<div class="av-draft-review">${question.draft?.body_markdown ? `<details><summary>Read draft, not sent</summary><pre>${h(question.draft.body_markdown)}</pre></details>` : '<p>The saved request is not prepared yet. Inspect its scope in Documents.</p>'}${button('Inspect request in Documents', 'data-av-pane="documents"')}</div>` : '';
    return `<section class="av-decision" data-question-kind="${h(question.kind)}" aria-labelledby="av-question-${h(id)}"><form data-av-decision="${h(id)}"><p class="av-question-kicker">${h(question.decider || 'Handler decision')} · ${h(label(question.kind))}</p><h3 class="av-question-title" id="av-question-${h(id)}">${h(question.prompt)}</h3>${question.why && question.why !== question.proposal?.reason ? `<p class="av-question-why">${h(question.why)}</p>` : ''}${question.proposal?.reason ? `<p class="av-proposal"><span>Agent reading:</span> ${h(question.proposal.reason)}</p>` : ''}${question.counter_reading ? `<p class="av-counter-reading"><span>Counter-reading:</span> ${h(question.counter_reading)}</p>` : ''}${citations ? `<ul class="av-citations" aria-label="Evidence for this question">${citations}</ul>` : '<p class="av-source-gap">No exact source passage supports this question yet.</p>'}${draft}${action}</form></section>`;
  }
  function impactMarkup(preview) {
    return global.CasePathCausal?.impactMarkup ? global.CasePathCausal.impactMarkup(preview.impact, preview.graph || {}) : `<p>Inspect the process preview before applying this decision.</p>${button('Open process', 'data-av-pane="process"')}`;
  }
  function evidenceStatesMarkup(process, agent, s) {
    const states = {needed_now:['missing', 'Missing · needed now'], needed_later:['missing-later', 'Missing · needed later'], held_not_reviewed:['held-not-reviewed', 'Held · not reviewed'], held_behind_question:['unknown', 'Unknown · depends on an answer'], not_needed:['not-applicable', 'Not applicable on this route'], established:['handler-confirmed', 'Handler confirmed'], optional:['optional', 'Optional']};
    const rank = {conflicting:0, insufficient:1, 'held-not-reviewed':2, missing:3, 'missing-later':4, unknown:5, optional:6, 'not-applicable':7, 'handler-confirmed':8};
    const documents = (process?.evaluation?.documents || []).map(doc => {const [state, text] = doc.review_state === 'insufficient' ? ['insufficient', 'Received · insufficient'] : states[doc.route_state] || ['unknown', 'State not yet checked']; return {doc, state, text};}).sort((a, b) => rank[a.state] - rank[b.state]);
    const conflicts = agent.conflicts || [];
    const rows = conflicts.map(conflict => `<li class="av-coverage-row" data-state="conflicting"><strong>${h(conflict.fact || conflict.prompt || 'Conflicting source statements')}</strong><span>${h(conflict.message || conflict.why || '')}</span>${(conflict.sources || []).map(source => citation(source, s)).join('')}${conflict.review?.reason ? `<small>Handler review: ${h(conflict.review.reason)}</small>` : ''}${conflict.truth_status === 'unresolved' ? '<small>Source conflict remains unresolved.</small>' : ''}</li>`).join('') + documents.map(({doc, state, text}) => `<li class="av-coverage-row" data-state="${state}"><strong>${h(doc.label || label(doc.document_type))}</strong><span>${text}</span>${button('Inspect document', `data-av-pane="documents" data-av-document="${h(doc.document_type)}"`)}</li>`).join('');
    return rows ? `<details class="av-document-states" data-av-disclosure="documents"${s.open.has('documents') ? ' open' : ''}><summary>Evidence gaps and confirmed documents</summary><ul>${rows}</ul></details>` : '';
  }
  function decisionsMarkup(agent, s, owner) {
    if (s.preview) {
      const question = s.preview.question || {};
      const answer = question.answers?.find(item => item.answer_id === s.preview.answer_id)?.label || label(s.preview.answer_id);
      const handlerReason = s.previewBody?.reason || (s.preview.answer_id !== question.proposal?.answer_id ? s.preview.reason : '');
      const citations = (question.sources || []).map(source => {const link = citation(source, s);return link ? `<li>${link}<blockquote>${h(source.quote || source.exact_text || source.locator?.exact_text)}</blockquote></li>` : '';}).join('');
      return `<section class="av-preview" tabindex="-1" aria-labelledby="av-preview-title"><p class="av-question-kicker">Decision preview</p><h3 id="av-preview-title">${h(question.prompt || 'Review the consequences')}</h3><p class="av-preview-answer"><span>Your answer:</span> <strong>${h(answer)}</strong></p>${handlerReason ? `<p class="av-handler-reason"><span>Your reason</span> ${h(handlerReason)}</p>` : ''}${question.proposal?.reason ? `<p class="av-proposal"><span>Agent reading:</span> ${h(question.proposal.reason)}</p>` : ''}${question.counter_reading ? `<p class="av-counter-reading"><span>Counter-reading:</span> ${h(question.counter_reading)}</p>` : ''}${citations ? `<ul class="av-citations av-preview-citations" aria-label="Evidence for your answer">${citations}</ul>` : '<p class="av-source-gap">No exact source passage supports this question yet.</p>'}<div class="av-decision-actions"><p class="av-apply-context"><span>${h(question.prompt || 'Review the consequences')}</span><strong>Your answer: ${h(answer)}</strong></p>${button('Apply decision', `data-av-apply${s.busy || s.pending ? ' disabled' : ''}`, true)}${button('Keep current state', `data-av-cancel${s.busy || s.pending ? ' disabled' : ''}`)}<span>Preview first. Apply saves your answer and starts the next review. Drafts stay not sent.</span></div>${impactMarkup(s.preview)}<p class="av-preview-authority">${s.preview.operation ? 'This changes the working process.' : 'This records your review; the source gap remains visible.'} The claim outcome remains for separate review.</p></section>`;
    }
    const questions = agent.questions || [];
    if (!questions.length) return `<section class="av-decision av-decision-empty"><h3>${agent.recovery_required === true ? 'Recovery needed' : agent.state === 'working' ? 'Review in progress' : agent.state === 'paused' ? 'The agent is paused' : agent.state === 'failed' ? 'The review needs recovery' : agent.state === 'waiting_for_others' ? 'Waiting for the next source' : agent.state === 'done' ? 'No handler decision is waiting' : 'No checked decision is available yet'}</h3><p>${h((agent.recovery_required === true && agent.recovery_ask) || agent.next_action || (agent.state === 'working' ? 'The next ask appears when a recorded check needs your decision.' : 'The saved process and sources remain available below.'))}</p></section>`;
    const current = questions.find(question => question.question_id === s.selectedQuestion) || questions[0];
    s.selectedQuestion = current.question_id;
    const picker = questions.length > 1 ? `<div class="av-decision-picker"><label for="avQuestionSelect">Choose a decision</label><small>${questions.length} decisions in this claim</small><select id="avQuestionSelect" data-av-question-select${s.busy || s.pending ? ' disabled' : ''}>${questions.map(question => `<option value="${h(question.question_id)}"${question.question_id === current.question_id ? ' selected' : ''}>${h(question.prompt)}</option>`).join('')}</select></div>` : '';
    return picker + questionMarkup(current, s, owner);
  }
  function learningPreviewMarkup(preview, s) {
    const scope = preview.scope || {};
    const names = new Map((s.input.process?.graph?.nodes || []).map(node => [node.node_id, node.label]));
    const documents = new Map((preview.fragment_preview?.document_catalog || []).map(doc => [doc.document_type, doc.label]));
    const boundary = item => typeof item === 'string' ? item : `${names.get(item.source_node_id) || label(item.source_node_id)} → ${label(item.relation)} → ${names.get(item.target_node_id) || label(item.target_node_id)}`;
    return `<section class="av-lesson-preview" tabindex="-1"><h4>Review reuse scope</h4><dl><dt>Claim family</dt><dd>${h(label(scope.family))}</dd><dt>Included steps</dt><dd>${(scope.node_ids || []).map(id => h(names.get(id) || label(id))).join(', ') || 'None'}</dd><dt>Boundary relationships</dt><dd>${(scope.boundary_relationships || []).map(item => h(boundary(item))).join(', ') || 'None'}</dd><dt>Document definitions</dt><dd>${(scope.documents || []).map(item => h(typeof item === 'string' ? documents.get(item) || label(item) : item.label || label(item.document_type))).join(', ') || 'None'}</dd></dl><h4>Conflicts</h4>${preview.conflicts?.length ? `<ul>${preview.conflicts.map(item => `<li>${h(typeof item === 'string' ? item : item.reason || item.message || item.label)}</li>`).join('')}</ul>` : '<p>No scope conflict was reported by this preview.</p>'}<p>This saves a reviewed version. Applying it to another claim requires a separate preview and approval.</p><div class="av-learning-actions">${button('Approve reusable fragment', `data-av-lesson-apply${s.busy || s.pending ? ' disabled' : ''}`, true)}${button('Keep this claim only', `data-av-lesson-cancel${s.busy || s.pending ? ' disabled' : ''}`)}</div></section>`;
  }
  function learningFormMarkup(s, owner) {
    const nodes = (s.input.process?.graph?.nodes || []).filter(node => node.validation?.status === 'validated');
    if (s.lessonPreview) return learningPreviewMarkup(s.lessonPreview, s);
    return nodes.length ? `<form class="av-lesson-form" data-av-lesson><h4>Prepare a reusable fragment</h4><label>Name<input name="name" maxlength="100" required value="${h(s.lessonDraft?.name || '')}"></label><fieldset><legend>Validated steps to include</legend>${nodes.map(node => `<label><input type="checkbox" name="node_ids" value="${h(node.node_id)}"${s.lessonDraft?.node_ids?.includes(node.node_id) ? ' checked' : ''}>${h(node.label)}</label>`).join('')}</fieldset>${owner ? `<input type="hidden" name="actor" value="${h(owner)}">` : '<label>Reviewing handler<input name="actor" maxlength="80" required></label>'}<label>Why this can be reused<textarea name="reason" maxlength="2000" required>${h(s.lessonDraft?.reason || s.lastOverride?.reason || '')}</textarea></label><button type="submit" class="av-button"${s.busy ? ' disabled' : ''}>Preview scope and conflicts</button></form>` : `<p>Validate the relevant process steps before saving a reusable fragment.</p>${button('Review process steps', 'data-av-pane="process"')}`;
  }
  function workMarkup(agent, s) {
    const activity = agent.activity || [], coverage = agent.coverage || {}, learning = agent.learning || {};
    const display = event => event.type === 'RUN_COMPLETED' && event.label === 'All six roles completed. Claim readiness remains governed by the existing authority.' ? 'Six review roles finished; findings need handler review.' : event.label || event.message || event.description || label(event.role);
    const rows = activity.slice(-3).map(event => `<li><span class="av-activity-type">${h(label(event.type))}</span><p>${h(display(event))}</p><div class="av-event-citations">${(event.sources || []).map(source => citation(source, s)).join('')}</div>${event.timestamp ? `<time datetime="${h(event.timestamp)}">${h(timeLabel(event.timestamp))}</time>` : ''}</li>`).join('');
    const trace = activity.map(event => `<li><strong>${h(event.label || label(event.type))}</strong>${event.role ? `<span>${h(label(event.role))}</span>` : ''}${event.timestamp ? `<time datetime="${h(event.timestamp)}">${h(timeLabel(event.timestamp))}</time>` : ''}<span>${h(event.message || event.description || '')}</span>${(event.sources || []).map(source => citation(source, s)).join('')}</li>`).join('');
    const gapRows = (coverage.limited_sources || []).map(source => `<li class="av-coverage-row" data-state="unreadable"><strong>${h(source.label || source.artifact_id)}</strong><span>${h(source.reason)}</span>${source.quote ? citation(source, s) : ''}</li>`).join('');
    const count = value => Number.isInteger(value) && value >= 0 ? h(value) : 'Unknown';
    const read = Number.isInteger(coverage.read_sources) && Number.isInteger(coverage.total_sources) ? `${coverage.read_sources} of ${coverage.total_sources} sources read` : 'Source coverage not yet recorded';
    const fragments = learning.fragments || [], memories = learning.memories || [], uses = learning.uses || [];
    const useRows = uses.map(use => {
      const fragment = fragments.find(item => item.fragment_sha256 === use.fragment_sha256);
      const memory = memories.find(item => item.memory_sha256 === use.memory_sha256);
      const title = use.kind === 'fragment_use' ? `${fragment?.name || 'Reviewed process fragment'}${fragment?.version ? ` · version ${fragment.version}` : ''}` : label(memory?.condition || use.target || 'Reviewed condition memory');
      return `<li><strong>${h(title)}</strong><span>Applied in this claim${use.revision != null ? ` · revision ${h(use.revision)}` : ''}</span>${use.actor || use.handler ? `<small>${h(use.actor || use.handler)}</small>` : ''}${use.reason || use.note ? `<p>${h(use.reason || use.note)}</p>` : ''}</li>`;
    }).join('');
    return `<section class="av-work" aria-labelledby="av-work-title"><div class="av-section-head"><h3 id="av-work-title">Recorded work</h3>${agent.run?.completed_roles != null ? `<span>${h(agent.run.completed_roles)} of 6 review roles complete</span>` : ''}</div>${rows ? `<ol class="av-activity">${rows}</ol>` : '<p class="av-work-empty">No agent activity has been recorded for this claim.</p>'}<details class="av-trace" data-av-disclosure="trace"${s.open.has('trace') ? ' open' : ''}><summary>Recent recorded work <span>${activity.length} ${activity.length === 1 ? 'milestone' : 'milestones'}</span></summary>${trace ? `<ol>${trace}</ol>` : '<p>No recorded events.</p>'}${agent.run?.run_id ? `<p class="av-run-id">Run ${h(agent.run.run_id)}</p>` : ''}</details>${agent.run?.run_id ? button('Inspect full review', 'data-av-pane="trace"') : ''}</section>
      <section class="av-coverage" aria-labelledby="av-coverage-title"><div class="av-section-head"><h3 id="av-coverage-title">Source coverage</h3><span>${h(read)}</span></div>${coverage.note ? `<p>${h(coverage.note)}</p>` : ''}<ul class="av-coverage-counts"><li data-state="unreadable"><strong>${count(coverage.unreadable_sources)}</strong> could not be read</li><li data-state="held-not-reviewed"><strong>${count(coverage.unread_sources)}</strong> not read</li><li data-state="arrived-since"><strong>${count(coverage.arrived_since)}</strong> arrived since this review</li></ul>${gapRows ? `<ul class="av-coverage-gaps">${gapRows}</ul>` : ''}${evidenceStatesMarkup(s.input.process, agent, s)}${button('Inspect sources', 'data-av-pane="sources"')}</section>
      <details class="av-learning" data-av-disclosure="learning"${s.open.has('learning') ? ' open' : ''}><summary>Reviewed knowledge <span>${memories.length} ${memories.length === 1 ? 'lesson' : 'lessons'} · ${fragments.length} saved process ${fragments.length === 1 ? 'version' : 'versions'}</span></summary><p>Corrections stay with the claim. A lesson or process fragment needs its own review before reuse.</p>${s.lastOverride ? `<p class="av-learning-change"><strong>Recorded in this claim</strong> ${h(s.lastOverride.reason)} ${button('Prepare reuse', 'data-av-prepare-reuse')}</p>` : ''}${memories.length ? `<ul class="av-lessons">${memories.map(memory => `<li><strong>${h(label(memory.condition))}</strong><span>${h(memory.note)}</span><small>${h(memory.handler)} · ${h(label(memory.family))} · ${h(label(memory.status))}</small>${memory.source_quote ? `<blockquote>${h(memory.source_quote)}</blockquote>` : ''}</li>`).join('')}</ul>` : '<p>No reviewed lesson is available for this claim.</p>'}${fragments.length ? `<ul class="av-fragments">${fragments.map(fragment => `<li><strong>${h(fragment.name)}</strong><span>Version ${h(fragment.version)} · ${h(fragment.actor || fragment.handler || 'Recorded reviewer')}</span><small>Source claim ${h(fragment.source_claim_id || fragment.claim_id)}</small></li>`).join('')}</ul>` : ''}${useRows ? `<h4>Recorded reuse</h4><ul class="av-learning-uses">${useRows}</ul>` : '<p>No reviewed knowledge has been applied to this claim.</p>'}${learningFormMarkup(s, agent.owner?.accountable || s.input.claim?.owner)}<div class="av-learning-actions">${button('Review lessons', 'data-av-pane="lessons"')}${button('Existing fragment library', 'data-av-pane="fragments"')}</div></details>`;
  }
  function timeLabel(timestamp) {
    const date = new Date(timestamp);
    return Number.isNaN(date.valueOf()) ? timestamp : new Intl.DateTimeFormat('en-CH', {hour:'2-digit', minute:'2-digit', timeZone:'Europe/Zurich'}).format(date);
  }
  function decisionBody(question, answer, actor, reason, agent) {
    if (!question?.previewable || !question.answers?.some(item => item.answer_id === answer)) throw new Error('Choose one of the recorded answers.');
    if (!String(actor || '').trim()) throw new Error('Enter the reviewing handler.');
    if (answer !== question.proposal?.answer_id && !String(reason || '').trim()) throw new Error('Record why you chose a different answer.');
    return {question_id:question.question_id, answer_id:answer, actor:String(actor).trim(), reason:String(reason || '').trim(), expected_revision:agent.workspace_revision, expected_state_sha256:agent.workspace_state_sha256};
  }
  function storageRead(key) {
    try { return JSON.parse(global.sessionStorage?.getItem(key) || 'null'); } catch { return {invalid:true}; }
  }
  function storageWrite(key, value) {
    if (!global.sessionStorage) return;
    if (value == null) global.sessionStorage.removeItem(key);
    else global.sessionStorage.setItem(key, JSON.stringify(value));
  }
  function bind(options) {
    const root = options.root;
    if (!root?.addEventListener) return () => {};
    bindings.get(root)?.();
    const claimRoot = root.querySelector('[data-av-claim]');
    if (!claimRoot) return () => {};
    const id = claimRoot.dataset.avClaim, s = session(id), path = `/api/claim-loops/v1/workspace/claims/${encodeURIComponent(id)}/agent`;
    const api = typeof options.api === 'function' ? {request:options.api} : options.api;
    const pendingKey = `casepath:agent-claim-pending:${id}`;
    if (!s.pending) s.pending = storageRead(pendingKey);
    const paint = (focus = null) => {
      const mount = root.isConnected ? root : global.document?.querySelector('#agentClaimMount');
      if (!mount?.isConnected || mount !== root && mount.querySelector('[data-av-claim]')?.dataset.avClaim !== id) return;
      mount.innerHTML = render(s.input);
      bind(mount === root ? options : {...options, root:mount});
      if (focus) {
        const notice = mount.querySelector(focus);
        const failed = focus === '.av-notice' && Boolean(s.error);
        const target = failed && s.pending ? mount.querySelector('[data-av-recover]') || notice : notice;
        target?.focus({preventScroll:true});
        if (failed) notice?.scrollIntoView({block:'nearest', inline:'nearest', behavior:'instant'});
      }
    };
    const verified = async (value, field, contract) => {
      if (!api?.verify) throw new Error('The response cannot be verified. Reload the saved claim.');
      await api.verify(value, field, contract);
      return value;
    };
    const post = async (suffix, body, pending = null) => {
      if (!api?.request) throw new Error('The local claim service is unavailable. Reload and try again.');
      return api.request(path + suffix, {method:'POST', headers:{'Content-Type':'application/json', ...(pending ? {'X-CasePath-Idempotency-Key':pending.key} : {})}, body:JSON.stringify(body)});
    };
    const preview = async (kind, body) => {
      if (s.busy || s.pending) return;
      s.busy = true; s.error = ''; s.notice = 'Preparing the consequences…'; paint();
      try {
        const result = await post(kind === 'lesson' ? '/lessons/preview' : '/decisions/preview', body);
        await verified(result, kind === 'lesson' ? 'preview_sha256' : 'response_sha256', kind === 'lesson' ? 'casepath.agent-lesson-preview/1.0.0' : 'casepath.agent-decision-preview/1.0.0');
        if (result.causal) await verified(result.causal, 'preview_sha256', 'casepath.causal-process-preview/1.0.0');
        if (result.claim_id !== id || result.workspace_revision !== body.expected_revision || result.workspace_state_sha256 !== body.expected_state_sha256 || kind !== 'lesson' && (result.question?.question_id !== body.question_id || result.answer_id !== body.answer_id)) throw new Error('The preview does not match this claim and answer. Reload the saved work.');
        if (kind === 'lesson') { s.lessonPreview = result; s.lessonBody = body; s.open.add('learning'); }
        else { s.preview = result; s.previewBody = body; }
        s.notice = '';
      } catch (error) { s.error = error.message; s.notice = ''; }
      finally { s.busy = false; paint(kind === 'lesson' ? '.av-lesson-preview' : '.av-preview'); }
    };
    const mutate = async (kind, body, recovering = false) => {
      if (s.busy || s.pending && !recovering) return;
      s.busy = true; s.error = ''; s.notice = 'Saving and checking the journal…';
      const suffix = kind === 'decision' ? '/decisions/apply' : kind === 'lesson' ? '/lessons/apply' : '/control';
      let accepted = false;
      try {
        if (s.pending?.invalid) throw new Error('The recovery record cannot be read. Reload and inspect the journal before continuing.');
        const pending = s.pending || {kind, suffix, body, key:`agent-claim:${global.crypto.randomUUID()}`};
        s.pending = pending; storageWrite(pendingKey, pending); paint();
        const result = await post(pending.suffix, pending.body, pending);
        await verified(result, pending.kind === 'lesson' ? 'result_sha256' : pending.kind === 'control' ? 'projection_sha256' : 'response_sha256', pending.kind === 'lesson' ? 'casepath.causal-process-result/1.0.0' : pending.kind === 'control' ? 'casepath.agent-control-result/1.0.0' : 'casepath.agent-decision-result/1.0.0');
        if (result.causal_result) await verified(result.causal_result, 'result_sha256', 'casepath.causal-process-result/1.0.0');
        if (result.agent) await verified(result.agent, 'projection_sha256', 'casepath.agent-desk-claim/1.0.0');
        if (result.process) await verified(result.process, 'view_sha256', 'casepath.causal-process-view/1.0.0');
        if (result.agent?.claim_id && result.agent.claim_id !== id || result.process?.claim_id && result.process.claim_id !== id) throw new Error('The save returned another claim. Reload and inspect the journal.');
        if (pending.kind === 'decision') {
          const question = s.preview?.question || s.input.agent.questions?.find(item => item.question_id === pending.body.question_id);
          if (question && pending.body.answer_id !== question.proposal?.answer_id) s.lastOverride = {question_id:question.question_id, reason:pending.body.reason};
          s.preview = null; s.previewBody = null;
          s.lastApplied = {impact:result.impact, graph:result.process?.graph || {}}; s.open.add('saved-impact');
          s.notice = question?.kind === 'source_conflict' ? 'Review saved. The source conflict remains unresolved.' : question?.kind === 'draft_approval' ? pending.body.answer_id === 'approve' ? 'Draft approved, not sent.' : 'Draft kept for revision, not sent.' : 'Decision saved. The process, documents and next action were recalculated.';
        } else if (pending.kind === 'lesson') {
          s.lessonPreview = null; s.lessonBody = null;
          s.notice = 'Reviewed fragment saved. Other claims keep their current process.';
        } else s.notice = pending.body.action === 'pause' ? result.agent?.state === 'paused' ? 'The agent is paused.' : 'Pausing at next checkpoint.' : 'The resume request is recorded.';
        s.pending = null; storageWrite(pendingKey, null);
        accepted = true;
        if (result.agent) s.input.agent = result.agent;
        if (result.process) s.input.process = result.process;
        options.onNotice?.(s.notice);
        await options.refresh?.(result);
        if (pending.kind === 'decision' && pending.body.question_id.startsWith('draft:') && pending.body.answer_id === 'revise') options.onOpenPane?.('documents');
      } catch (error) {
        if (error.responseReceived && !error.ambiguousResponse) {s.pending = null; storageWrite(pendingKey, null);}
        s.error = `${accepted ? 'The save is confirmed. Refresh could not complete: ' : s.pending ? 'Save needs verification: ' : ''}${error.message}`; s.notice = '';
      } finally {s.busy = false; paint('.av-notice');}
    };
    const control = async (action, actor) => {
      if (s.busy || s.pending) return;
      s.busy = true; s.error = ''; s.notice = 'Checking saved work…'; paint();
      try {
        if (!api?.request) throw new Error('The local claim service is unavailable. Reload and try again.');
        const agent = await api.request(path, {method:'GET'});
        await verified(agent, 'projection_sha256', 'casepath.agent-desk-claim/1.0.0');
        if (agent.claim_id !== id) throw new Error('The saved work belongs to another claim. Reload before stopping or resuming.');
        if (!Number.isInteger(agent.workspace_revision) || !agent.workspace_state_sha256 || !Number.isInteger(agent.agent_revision) || !agent.agent_state_sha256) throw new Error('The saved work has no current control guards. Reload before stopping or resuming.');
        s.input.agent = agent;
        if (agent.pause_requested && agent.state === 'working') {s.notice = 'Pausing at next checkpoint.'; s.busy = false; paint('.av-notice'); return;}
        if (action === 'resume' && inspectRecovery(agent)) throw new Error(agent.recovery_ask || 'Inspect the saved work before requesting recovery.');
        const body = {action, actor, reason:action === 'pause' ? 'Handler stopped the agent from this claim.' : 'Handler requested that the agent resume this claim.', expected_revision:agent.workspace_revision, expected_state_sha256:agent.workspace_state_sha256, expected_agent_revision:agent.agent_revision, expected_agent_state_sha256:agent.agent_state_sha256};
        s.busy = false;
        await mutate('control', body);
      } catch (error) {s.busy = false; s.error = error.message; s.notice = ''; paint('.av-notice');}
    };
    const click = event => {
      const target = event.target.closest('button');
      if (!target || !root.contains(target)) return;
      if (target.hasAttribute('data-av-reload')) {s.error = ''; s.preview = null; s.lessonPreview = null; void options.refresh?.(); return;}
      if (target.hasAttribute('data-av-source')) {options.onOpenSource?.(s.sources[Number(target.dataset.avSource)]); return;}
      if (target.hasAttribute('data-av-pane')) {options.onOpenPane?.(target.dataset.avPane, {document_type:target.dataset.avDocument}); return;}
      if (s.busy) return;
      if (target.hasAttribute('data-av-recover')) {if (s.pending && !s.pending.invalid) void mutate(s.pending.kind, s.pending.body, true); return;}
      if (s.pending) return;
      if (target.hasAttribute('data-av-cancel')) {s.preview = null; s.previewBody = null; paint('[data-av-decision] input:checked'); return;}
      if (target.hasAttribute('data-av-lesson-cancel')) {s.lessonPreview = null; s.lessonBody = null; paint('.av-lesson-form input'); return;}
      if (target.hasAttribute('data-av-apply') && s.preview && s.previewBody) {void mutate('decision', {...s.previewBody, preview_sha256:s.preview.preview_sha256}); return;}
      if (target.hasAttribute('data-av-lesson-apply') && s.lessonPreview && s.lessonBody) {void mutate('lesson', {...s.lessonBody, preview_sha256:s.lessonPreview.preview_sha256}); return;}
      if (target.hasAttribute('data-av-control')) {
        const agent = s.input.agent, actor = agent.owner?.accountable || s.input.claim?.owner;
        if (agent.pause_requested && agent.state === 'working') {s.notice = 'Pausing at next checkpoint.'; paint('.av-notice'); return;}
        if (!actor) {s.error = 'Assign a handler before stopping or resuming the agent.'; paint('.av-notice'); return;}
        const action = target.dataset.avControl;
        void control(action, actor);
      }
      if (target.hasAttribute('data-av-prepare-reuse')) {s.open.add('learning'); paint('.av-lesson-form input');}
    };
    const submit = event => {
      const form = event.target;
      if (!form.matches('[data-av-decision],[data-av-lesson]')) return;
      event.preventDefault();
      if (s.busy || s.pending) return;
      const agent = s.input.agent;
      try {
        if (form.hasAttribute('data-av-decision')) {
          const question = agent.questions.find(item => item.question_id === form.dataset.avDecision), answer = form.elements.answer_id.value, reason = form.elements.reason?.value || '';
          s.answers[question.question_id] = answer; s.reasons[question.question_id] = reason;
          void preview('decision', decisionBody(question, answer, form.elements.actor.value, reason, agent));
        } else {
          const nodeIds = [...form.querySelectorAll('[name="node_ids"]:checked')].map(item => item.value);
          if (!nodeIds.length) throw new Error('Choose at least one validated step for this fragment.');
          const draft = {name:form.elements.name.value.trim(), node_ids:nodeIds, actor:form.elements.actor.value.trim(), reason:form.elements.reason.value.trim()};
          if (!draft.name || !draft.actor || !draft.reason) throw new Error('Enter a name, reviewing handler and reason for reuse.');
          s.lessonDraft = draft;
          void preview('lesson', {...draft, expected_revision:agent.workspace_revision, expected_state_sha256:agent.workspace_state_sha256});
        }
      } catch (error) {s.error = error.message; paint('.av-notice');}
    };
    const change = event => {
      if (event.target.matches('[data-av-question-select]')) {
        if (event.type === 'change' && !s.busy && !s.pending && s.input.agent.questions.some(question => question.question_id === event.target.value)) {s.selectedQuestion = event.target.value; paint('#avQuestionSelect');}
        return;
      }
      const lesson = event.target.closest('[data-av-lesson]');
      if (lesson) {s.lessonDraft = {name:lesson.elements.name.value, node_ids:[...lesson.querySelectorAll('[name="node_ids"]:checked')].map(item => item.value), actor:lesson.elements.actor.value, reason:lesson.elements.reason.value}; return;}
      const form = event.target.closest('[data-av-decision]');
      if (!form) return;
      const id = form.dataset.avDecision;
      s.answers[id] = form.elements.answer_id.value; s.reasons[id] = form.elements.reason?.value || '';
      s.actors = s.actors || {}; s.actors[id] = form.elements.actor?.value || '';
      const question = s.input.agent.questions.find(item => item.question_id === id), override = s.answers[id] !== question.proposal?.answer_id;
      const field = form.querySelector('.av-decision-reason');
      if (field) field.hidden = !override;
      if (form.elements.reason) form.elements.reason.required = override;
    };
    const disclosure = event => {
      const key = event.target.dataset?.avDisclosure;
      if (key) {if (event.target.open) s.open.add(key); else s.open.delete(key);}
    };
    root.addEventListener('click', click); root.addEventListener('submit', submit); root.addEventListener('input', change); root.addEventListener('change', change); root.addEventListener('toggle', disclosure, true);
    const cleanup = () => {root.removeEventListener('click', click); root.removeEventListener('submit', submit); root.removeEventListener('input', change); root.removeEventListener('change', change); root.removeEventListener('toggle', disclosure, true);};
    bindings.set(root, cleanup);
    return cleanup;
  }
  function render(input) {
    const claim = input.claim || {}, agent = input.agent, id = claim.claim_id || agent?.claim_id || '', s = session(id);
    s.input = input;
    s.sources = [];
    if (!s.pending) s.pending = storageRead(`casepath:agent-claim-pending:${id}`);
    if (!s.busy && !s.pending && s.preview && agent && (s.preview.workspace_revision !== agent.workspace_revision || s.preview.workspace_state_sha256 !== agent.workspace_state_sha256)) {s.preview = null; s.previewBody = null; s.error = 'The saved claim changed. Prepare a new preview from the current answers.';}
    if (!s.busy && !s.pending && s.lessonPreview && agent && (s.lessonPreview.workspace_revision !== agent.workspace_revision || s.lessonPreview.workspace_state_sha256 !== agent.workspace_state_sha256)) {s.lessonPreview = null; s.lessonBody = null; s.error = 'The saved process changed. Prepare a new reuse preview.';}
    if (s.notice === 'Pausing at next checkpoint.' && agent?.state === 'paused') s.notice = 'The agent is paused.';
    if (!agent) return `<section class="av-claim av-claim-loading" data-av-claim="${h(id)}" aria-busy="true"><p class="av-owner-line">Accountable handler <strong>${h(claim.owner || 'Unassigned')}</strong></p><h2 class="av-claim-title">CasePath agent</h2><p>Loading the saved work and next decision…</p></section>`;
    if (agent.error) return `<section class="av-claim" data-av-claim="${h(id)}"><h2 class="av-claim-title">CasePath agent</h2><p class="av-notice" data-kind="error" role="alert">${h(agent.error)}</p>${button('Reload saved work', 'data-av-reload')}</section>`;
    const owner = agent.owner?.accountable || claim.owner;
    const review = agent.run, coverage = agent.coverage || {}, summary = [];
    if (review) {
      summary.push(review.currentness === 'historical' ? 'Earlier review' : review.currentness === 'current' ? 'Current review' : 'Recorded review');
      if (Number.isInteger(review.completed_roles) && Number.isInteger(review.role_count) && review.completed_roles >= 0 && review.completed_roles <= review.role_count && review.role_count > 0) summary.push(`${review.completed_roles} of ${review.role_count} review roles finished`);
    }
    if (Number.isInteger(coverage.read_sources) && Number.isInteger(coverage.total_sources) && coverage.read_sources >= 0 && coverage.read_sources <= coverage.total_sources) summary.push(`${coverage.read_sources} of ${coverage.total_sources}${coverage.scope === 'original_bound_intake' ? ' original' : ''} sources read`);
    const draftWaiting = agent.questions?.some(question => question.kind === 'draft_approval');
    const pausing = agent.pause_requested && agent.state === 'working';
    const resume = agent.pause_requested || ['paused', 'failed', 'unknown'].includes(agent.state);
    const control = !pausing && inspectRecovery(agent) ? button('Inspect recorded work', 'data-av-pane="trace"') + (!owner ? button('Assign handler', 'data-edit-owner') : '') : agent.state === 'done' ? '' : owner ? button(pausing ? 'Pausing at next checkpoint' : resume ? agent.state === 'failed' || agent.state === 'unknown' && !agent.pause_requested && !agent.recovery_required ? 'Retry review' : 'Resume agent' : agent.state === 'waiting_for_you' ? 'Pause delegate' : 'Stop agent', `data-av-control="${resume ? 'resume' : 'pause'}"${s.busy || s.pending || pausing ? ' disabled' : ''}`) : button('Assign handler', 'data-edit-owner');
    return `<section class="av-claim" data-av-claim="${h(id)}" aria-busy="${s.busy}">
      <header class="av-claim-header"><div><p class="av-owner-line">Accountable handler <strong>${h(owner || 'Unassigned')}</strong> ${owner ? button('Change', 'data-edit-owner') : ''}</p><div class="av-agent-line"><h2 class="av-claim-title">${h(agent.owner?.delegate || 'CasePath agent')}</h2><span class="av-delegate">Delegate</span><span class="av-state" data-state="${h(agent.state)}">${h(agent.recovery_required === true ? 'Recovery needed' : pausing ? 'Pausing at next checkpoint' : states[agent.state] || states.unknown)}</span></div>${agent.recovery_required === true && agent.recovery_ask ? `<p class="av-recovery-ask">${h(agent.recovery_ask)}</p>` : ''}${summary.length ? `<p class="av-review-summary">${h(summary.join(' · '))}</p>` : ''}${draftWaiting ? '<p class="av-draft-status">Draft awaits review · not sent.</p>' : ''}</div><div class="av-control">${control}</div></header>
      ${mandateMarkup(agent, s)}
      <div class="av-notice" tabindex="-1" data-kind="${s.error ? 'error' : 'status'}" role="${s.error ? 'alert' : 'status'}"${!s.error && !s.notice ? ' hidden' : ''}>${h(s.error || s.notice)}${s.error ? ` ${button('Reload saved work', 'data-av-reload')}` : ''}</div>
      ${s.pending ? `<div class="av-pending" role="status"><p>${s.pending.invalid ? 'A recovery record could not be read. Reload and inspect the journal before continuing.' : 'A saved request needs verification. Recovery repeats that same request.'}</p>${s.pending.invalid ? button('Reload saved work', 'data-av-reload') : button('Recover saved request', `data-av-recover${s.busy ? ' disabled' : ''}`)}</div>` : ''}
      ${s.lastApplied?.impact ? `<details class="av-saved-impact" data-av-disclosure="saved-impact"${s.open.has('saved-impact') ? ' open' : ''}><summary>Last saved decision · consequences</summary>${impactMarkup(s.lastApplied)}</details>` : ''}
      <div class="av-decision-mount">${decisionsMarkup(agent, s, owner)}</div>
      <nav class="av-claim-tools" aria-label="Claim work">${button('Process and consequences', 'data-av-pane="process"')}${button('Documents and draft', 'data-av-pane="documents"')}${button('Sources', 'data-av-pane="sources"')}${button('What if', 'data-av-pane="what-if"')}${button('Export and journal', 'data-av-pane="activity"')}</nav>
      <div class="av-work-mount">${workMarkup(agent, s)}</div>
    </section>`;
  }
  return {render, bind, session, decisionBody};
});
