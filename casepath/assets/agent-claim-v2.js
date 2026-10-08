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
  const stoppingText = agent => agent.run?.facts_worker === 'external_facts' ? 'Stopping after current request' : 'Pausing at next checkpoint';
  const canClearPause = agent => agent.pause_requested === true && agent.recovery_required !== true && (agent.can_clear_external_pause === true && agent.run?.facts_worker === 'external_facts' || agent.run?.status === 'completed' && agent.run.facts_worker === 'reference' && agent.run.provider_requests === 0 && Array.isArray(agent.run.pending_calls) && agent.run.pending_calls.length === 0);
  const inspectRecovery = agent => !canClearPause(agent) && (agent.recovery_required === true || agent.pause_requested || ['paused', 'failed', 'unknown'].includes(agent.state)) && (agent.run ? agent.run.recovery?.can_resume !== true || agent.run.facts_worker !== 'reference' : agent.recovery_required === true);
  const reconciliationCandidate = agent => {
    const run=agent?.run, candidate=run?.recovery?.reconciliation;
    return agent?.recovery_required === true && run?.facts_worker === 'reference' && run.provider_requests === 0 && candidate?.kind === 'process_node' && candidate.run_id === run.run_id && ['call_id','object_id','expected_last_event_sha256','expected_work_state_sha256'].every(key=>typeof candidate[key] === 'string' && candidate[key]) ? candidate : null;
  };
  const reconciliationBody = (agent, candidate) => ({run_id:candidate.run_id,call_id:candidate.call_id,object_id:candidate.object_id,expected_last_event_sha256:candidate.expected_last_event_sha256,expected_work_state_sha256:candidate.expected_work_state_sha256,expected_revision:agent.workspace_revision,expected_state_sha256:agent.workspace_state_sha256,expected_agent_revision:agent.agent_revision,expected_agent_state_sha256:agent.agent_state_sha256});
  function reconciliationMarkup(s) {
    const review=s.reconciliationReview;
    return review ? `<section id="av-reconcile-review" class="av-preview" tabindex="-1" aria-labelledby="av-reconcile-title"><p class="av-question-kicker">Interrupted local review</p><h3 id="av-reconcile-title">${h(review.title || 'Review the interrupted step')}</h3><p>Reconstruct this local proposal from the saved process. The working process stays unchanged. You can resume the review after reconciliation.</p><form class="av-lesson-form" data-av-reconcile-form><label for="av-reconcile-reason">Recovery note<textarea id="av-reconcile-reason" name="reason" maxlength="1000" required${s.busy || s.pending ? ' disabled' : ''}>${h(s.reconciliationReason || '')}</textarea></label><div class="av-learning-actions"><button type="submit" class="av-button av-button-primary"${s.busy || s.pending ? ' disabled' : ''}>Reconcile saved proposal</button>${button('Keep stopped','data-av-reconcile-cancel'+(s.busy || s.pending ? ' disabled' : ''))}</div></form></section>` : '';
  }
  const sessions = new Map(), bindings = new WeakMap();
  const session = id => {
    if (!sessions.has(id)) sessions.set(id, {answers:{}, reasons:{}, preview:null, lessonPreview:null, error:'', notice:'', busy:false, sources:[], open:new Set()});
    return sessions.get(id);
  };
  const button = (text, attrs = '', primary = false, key = '') => `<button type="button" class="av-button${primary ? ' av-button-primary' : ''}" id="av-${h(key || encodeURIComponent(JSON.stringify([text, attrs])))}" ${attrs}>${h(text)}</button>`;
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
  function releaseReviewPosition(id) {
    const s=sessions.get(id);
    if(!s)return;
    if(s.workPlacement?.anchored)s.open.delete('live-work');
    s.workPlacement=null;
  }
  function completedReviewAfterDecision(agent,s) {
    const work=agent.live_work;
    if(!work?.run_id){s.workPlacement=null;return false;}
    if(s.workPlacement?.run_id!==work.run_id)s.workPlacement={run_id:work.run_id,observed_working:false,anchored:false};
    const placement=s.workPlacement;
    if(!placement.observed_working&&agent.state==='working'&&['queued','running'].includes(work.status)&&work.currentness==='current'){
      placement.observed_working=true;
      placement.anchored=true;
      s.open.add('live-work');
    }
    return work.status==='completed'&&agent.state!=='working'&&!placement.anchored;
  }
  function liveWorkMarkup(agent, s) {
    const work = agent.live_work, review = agent.live_review;
    const motion = global.CasePathWorkMotion?.markup(work, {
      stage:s.workStage,
      sourceLink:source => citation(source, s),
      nodeLink:node => button('Inspect step: '+(node.label || label(node.node_id)), `data-av-node="${h(node.node_id)}"`),
      documentLink:doc => doc.document_type ? button('Inspect document: '+(doc.label || label(doc.document_type)), `data-av-pane="documents" data-av-document="${h(doc.document_type)}"`) : `<span>${h(doc.label)}</span>`,
    }) || '';
    const reasons = {accountable_handler_required:'Assign a handler to start a live review.',paused_by_handler:'The delegate is paused.',inspect_existing_work:'Inspect the current review before starting another.',claim_changed:'Refresh saved work before starting.',local_budget_not_configured:'Live review budget is unavailable.',external_run_limit:'The demo review limit has been reached.',external_cost_limit:'The demo budget has been reached.',external_call_limit:'The demo request limit has been reached.',external_run_active:'A live review is already running.'};
    const money = value => Number.isFinite(Number(value)) ? '$'+Number(value).toFixed(2) : 'unavailable';
    const control = review?.available ? `<div class="av-live-launch"><div><p>up to ${h(money(review.run_cost_limit_usd))} per review</p><details class="av-live-config" data-av-disclosure="live-configuration"${s.open.has('live-configuration') ? ' open' : ''}><summary id="av-live-config-summary">Review details</summary><p>Model: ${h(review.model)}</p><small>Reads synthetic sources. Process changes need your approval.</small></details></div>${review.can_start && /^[a-f0-9]{64}$/.test(review.context_sha256 || '') ? button('Review sources live', `data-av-live-start${s.busy || s.pending ? ' disabled' : ''}`, false, 'live-start') : `<p class="av-live-limit">${h(reasons[review.reason] || 'Live review is unavailable while the current work or budget needs inspection.')}</p>`}</div>` : '';
    if (!motion) return {control, review:''};
    const detail = `<div class="av-live-mount">${motion}${s.workStage ? button(agent.state === 'working' ? 'Follow live review' : 'Show latest recorded work', 'data-av-work-follow', false, 'work-follow') : ''}<p class="av-stream-status" role="status" hidden></p></div>`;
    return {control, review:`<details class="av-live-details" data-av-disclosure="live-work"${s.open.has('live-work') ? ' open' : ''}><summary id="av-live-summary">Source-grounded review <span>${work.currentness === 'historical' ? 'Earlier recorded work' : agent.state === 'working' ? 'Live work' : work.status === 'completed' ? 'Recorded findings' : 'Inspect saved work'}</span></summary>${detail}</details>`};
  }
  function conditionComparisonMarkup(question,s,answer) {
    const flag=question.kind==='condition'&&question.question_id.startsWith('condition:')?question.question_id.slice('condition:'.length):null;
    const savedCondition=flag&&(s.input.claim?.causal_process!=null?s.input.claim.causal_process.conditions?.[flag]:s.input.claim?.intake_assessment?.claim_assessment?.conditions?.[flag]);
    const savedVerdict=savedCondition?.verdict;
    const savedAnswer=['true','false','unresolved'].includes(savedVerdict)&&question.answers?.find(item=>item.answer_id===savedVerdict);
    const selectedAnswer=question.answers?.find(item=>item.answer_id===answer);
    return savedAnswer&&selectedAnswer?`<p class="av-answer-comparison"><span>${s.input.claim?.causal_process!=null?'Saved reading · unconfirmed':'Intake reading · unconfirmed'}: <strong>${h(savedAnswer.label)}</strong></span><span class="av-answer-arrow" aria-hidden="true">→</span><span>${Object.prototype.hasOwnProperty.call(s.answers,question.question_id)?'Your answer':'Proposed answer'}: <strong>${h(selectedAnswer.label)}</strong> · not saved</span></p>`:'';
  }
  const sourceBasis = question => question.kind === 'draft_approval' ? 'The saved process determines this request. Review its scope and wording.' : ['step_validation', 'relationship_validation', 'inconsistent_completion'].includes(question.kind) ? 'This question comes from the saved process. Source evidence remains separate.' : 'No exact source passage supports this question yet.';
  function questionMarkup(question, s, owner) {
    const id = question.question_id, answer = s.answers[id] || question.proposal?.answer_id;
    const override = answer !== question.proposal?.answer_id, reasonId = `av-reason-${id}`, locked = s.busy || s.pending;
    const proposed=question.proposal?.answer_id&&question.answers?.find(item=>item.answer_id===question.proposal.answer_id);
    const comparison=conditionComparisonMarkup(question,s,answer);
    const citations = (question.sources || []).map(source => `<li>${citation(source, s)}${source.quote ? `<blockquote>${h(source.quote)}</blockquote>` : ''}</li>`).join('');
    const action = question.previewable ? `<fieldset class="av-answer-list"><legend>Choose your answer</legend>${(question.answers || []).map(item => `<label class="av-answer" data-proposed="${item.answer_id === question.proposal?.answer_id}"><input id="av-answer-${h(id)}-${h(item.answer_id)}" type="radio" name="answer_id" value="${h(item.answer_id)}"${item.answer_id === answer ? ' checked' : ''} required${locked ? ' disabled' : ''}><span><strong>${h(item.label)}</strong>${item.answer_id === question.proposal?.answer_id ? '<small class="av-proposal-label">Agent proposal · not saved</small>' : ''}${item.description ? `<span>${h(item.description)}</span>` : ''}</span></label>`).join('')}</fieldset>
      <div class="av-decision-reason"${override ? '' : ' hidden'}><label for="${h(reasonId)}">Reason for choosing another answer</label><textarea id="${h(reasonId)}" name="reason" maxlength="2000" aria-describedby="${h(reasonId)}-help"${override ? ' required' : ''}${locked ? ' disabled' : ''}>${h(s.reasons[id] || '')}</textarea><small id="${h(reasonId)}-help">Your reason stays with this decision. Reuse is a separate approval.</small></div>
      ${owner ? `<input type="hidden" name="actor" value="${h(owner)}">` : `<label class="av-reviewing-handler">Reviewing handler<input id="av-actor-${h(id)}" name="actor" required maxlength="80" autocomplete="name" value="${h(s.actors?.[id] || '')}"></label>`}
      <div class="av-decision-actions"><button id="av-preview-${h(id)}" type="submit" class="av-button av-button-primary"${locked ? ' disabled' : ''}>Preview consequences</button><span>Preview is read-only. Nothing is saved yet.</span></div>` : `<div class="av-decision-actions">${button(question.pane === 'draft' ? 'Review draft, not sent' : question.pane === 'process' ? 'Review process' : 'Open source review', `data-av-pane="${h(question.pane === 'draft' ? 'documents' : question.pane || 'sources')}"`)}<span>The source gap stays open until reviewed.</span></div>`;
    const draft = question.kind === 'draft_approval' ? `<div class="av-draft-review">${question.draft?.body_markdown ? `<details data-av-disclosure="draft"${s.open.has('draft') ? ' open' : ''}><summary id="av-draft-summary">Read draft, not sent</summary><pre>${h(question.draft.body_markdown)}</pre></details>` : '<p>The saved request is not prepared yet. Inspect its scope in Documents.</p>'}${button('Inspect request in Documents', 'data-av-pane="documents"')}</div>` : '';
    return `<section class="av-decision" data-question-kind="${h(question.kind)}" aria-labelledby="av-question-${h(id)}"><form data-av-decision="${h(id)}"><p class="av-question-kicker">${h(question.decider || 'Handler decision')} · ${h(label(question.kind))}</p><h3 class="av-question-title" id="av-question-${h(id)}">${h(question.prompt)}</h3>${comparison}${question.why && question.why !== question.proposal?.reason ? `<p class="av-question-why">${h(question.why)}</p>` : ''}${!comparison && proposed?.label || question.proposal?.reason ? `<p class="av-proposal">${!comparison && proposed?.label ? `<span class="av-proposed-answer">Agent proposal: <strong>${h(proposed.label)}</strong> · not saved</span>` : ''}${question.proposal?.reason ? `<span>Agent reading:</span> ${h(question.proposal.reason)}` : ''}</p>` : ''}${question.counter_reading ? `<details class="av-counter" data-av-disclosure="counter:${h(id)}"${s.open.has('counter:'+id) ? ' open' : ''}><summary id="av-counter-${h(id)}">Counter-reading</summary><p class="av-counter-reading"><span>Counter-reading:</span> ${h(question.counter_reading)}</p></details>` : ''}${citations ? `<ul class="av-citations" aria-label="Evidence for this question">${citations}</ul>` : `<p class="av-source-gap">${h(sourceBasis(question))}</p>`}${draft}${action}</form></section>`;
  }
  function impactMarkup(preview, s, scope = 'preview') {
    return global.CasePathCausal?.impactMarkup ? global.CasePathCausal.impactMarkup(preview.impact, preview.graph || {}, {scope, open:s.open}) : `<p>Inspect the process preview before applying this decision.</p>${button('Open process', 'data-av-pane="process"')}`;
  }
  function evidenceStatesMarkup(process, agent, s) {
    const states = {needed_now:['missing', 'Missing · needed now'], needed_later:['missing-later', 'Missing · needed later'], held_not_reviewed:['held-not-reviewed', 'Held · not reviewed'], held_behind_question:['unknown', 'Unknown · depends on an answer'], not_needed:['not-applicable', 'Not applicable on this route'], established:['handler-confirmed', 'Handler confirmed'], optional:['optional', 'Optional']};
    const rank = {conflicting:0, insufficient:1, 'held-not-reviewed':2, missing:3, 'missing-later':4, unknown:5, optional:6, 'not-applicable':7, 'handler-confirmed':8};
    const documents = (process?.evaluation?.documents || []).map(doc => {const [state, text] = doc.review_state === 'insufficient' ? ['insufficient', 'Received · insufficient'] : states[doc.route_state] || ['unknown', 'State not yet checked']; return {doc, state, text};}).sort((a, b) => rank[a.state] - rank[b.state]);
    const conflicts = agent.conflicts || [];
    const rows = conflicts.map(conflict => `<li class="av-coverage-row" data-state="conflicting"><strong>${h(conflict.fact || conflict.prompt || 'Conflicting source statements')}</strong><span>${h(conflict.message || conflict.why || '')}</span>${(conflict.sources || []).map(source => citation(source, s)).join('')}${conflict.review?.reason ? `<small>Handler review: ${h(conflict.review.reason)}</small>` : ''}${conflict.truth_status === 'unresolved' ? '<small>Source conflict remains unresolved.</small>' : ''}</li>`).join('') + documents.map(({doc, state, text}) => `<li class="av-coverage-row" data-state="${state}"><strong>${h(doc.label || label(doc.document_type))}</strong><span>${text}</span>${button('Inspect document', `data-av-pane="documents" data-av-document="${h(doc.document_type)}"`)}</li>`).join('');
    return rows ? `<details class="av-document-states" data-av-disclosure="documents"${s.open.has('documents') ? ' open' : ''}><summary id="av-evidence-summary">Evidence gaps and confirmed documents</summary><ul>${rows}</ul></details>` : '';
  }
  // This is a view of the saved graph. Only the server computes consequences.
  function contextNode(process, question) {
    const graph = process?.graph, nodes = process?.evaluation?.nodes || [];
    if (!graph || !question) return null;
    const [kind, ...parts] = question.question_id.split(':'), key = parts.join(':');
    const direct = kind === 'node' || kind === 'completion' ? key : kind === 'edge' ? graph.edges?.find(edge => edge.edge_id === key)?.target_node_id : kind === 'condition' ? nodes.find(node => node.condition_flags?.includes(key))?.node_id : null;
    return graph.nodes.find(node => node.node_id === direct) || graph.nodes.find(node => node.node_id === process.evaluation?.focus_node_id) || null;
  }
  function contextMarkup(process, agent, question) {
    if (!process?.graph || process.error) return '';
    const node = contextNode(process, question), graph = process.graph;
    const learning = agent.learning || {}, versions = learning.fragments || [], uses = learning.uses || [];
    const docs = node ? (process.evaluation?.documents || []).filter(doc => doc.required_at_node_ids?.includes(node.node_id) || node.document_types?.includes(doc.document_type)) : [];
    const names = {needed_now:'Needed now', needed_later:'Needed later', held_not_reviewed:'Received · review needed', held_behind_question:'Depends on an answer', not_needed:'Not needed on this route', established:'Handler confirmed', optional:'Optional'};
    const checklist = `<section class="av-node-checklist" aria-label="Documents derived from this step"><h4>Documents from this step</h4>${process.process_adopted === false ? '<p>Proposed requirements · the current request has not changed.</p>' : ''}<ul>${docs.map(doc => `<li data-state="${h(doc.route_state)}"><span><strong>${h(doc.label || label(doc.document_type))}</strong><small>${h(`${names[doc.route_state] || 'State not yet checked'}${doc.review_state === 'insufficient' ? ' · Received · insufficient' : ''}`)}</small></span>${button(doc.held_files?.length || doc.route_state === 'held_not_reviewed' || doc.route_state === 'established' ? 'Review evidence' : 'Link evidence', `data-av-review-document="${h(doc.document_type)}" data-av-node-id="${h(node.node_id)}" aria-label="Review ${h(doc.label || label(doc.document_type))}"`, false, 'review-'+doc.document_type)}</li>`).join('') || '<li>No document is attached to this step.</li>'}</ul></section>`;
    const diagram = node && global.CasePathCausal?.contextMarkup?.(process, node.node_id, {scope:'decision', selectedContent:checklist});
    const provenance = node?.validation?.status === 'validated' ? 'Handler-validated step · source evidence remains separate.' : node?.provenance?.modified_by ? 'Saved handler edit · step validation needed.' : node?.provenance?.source === 'static_policy' ? 'Policy-derived step · source evidence is reviewed separately.' : 'Working interpretation · handler review is still required.';
    return `<aside class="av-consequence" aria-labelledby="av-context-title"><div class="av-section-head"><h3 id="av-context-title">${process.process_adopted === false ? 'Proposed process' : 'Saved process'}</h3>${button('Open graph', 'data-av-pane="process"', false, 'context-graph')}</div>${node ? `<p class="av-context-basis">${h(provenance)}<span>${process.process_adopted === false ? 'This process has not been adopted.' : 'Your proposed answer has not been applied here.'}</span></p>${diagram || `<button type="button" class="av-context-node" data-av-node="${h(node.node_id)}">${h(node.label)}</button>`}${diagram ? '' : checklist}` : `<p>The working graph contains ${graph.nodes.length} steps. This decision has no direct step link.</p>`}<div class="av-knowledge-bridge"><span class="av-context-caption">Reviewed knowledge</span><p>${versions.length} saved process ${versions.length === 1 ? 'version' : 'versions'} available · ${uses.length} recorded ${uses.length === 1 ? 'use' : 'uses'} here</p><p>Reuse needs your approval.</p>${button('Inspect knowledge', 'data-av-knowledge', false, 'knowledge')}</div></aside>`;
  }
  function decisionsMarkup(agent, s, owner) {
    if (s.preview) {
      const question = s.preview.question || {};
      const answer = question.answers?.find(item => item.answer_id === s.preview.answer_id)?.label || label(s.preview.answer_id);
      const proposedAnswer = question.answers?.find(item => item.answer_id === question.proposal?.answer_id)?.label;
      const handlerReason = s.previewBody?.reason || (s.preview.answer_id !== question.proposal?.answer_id ? s.preview.reason : '');
      const citations = (question.sources || []).map(source => {const link = citation(source, s);return link ? `<li>${link}<blockquote>${h(source.quote || source.exact_text || source.locator?.exact_text)}</blockquote></li>` : '';}).join('');
      return `<section id="av-confirm" class="av-preview" tabindex="-1" aria-labelledby="av-preview-title"><p class="av-question-kicker">Decision preview</p><h3 id="av-preview-title">${h(question.prompt || 'Review the consequences')}</h3><p class="av-preview-answer"><span>Your answer:</span> <strong>${h(answer)}</strong></p>${handlerReason ? `<p class="av-handler-reason"><span>Your reason</span> ${h(handlerReason)}</p>` : ''}${question.proposal?.reason ? `<p class="av-proposal">${proposedAnswer ? `<span class="av-proposed-answer">Agent proposal: <strong>${h(proposedAnswer)}</strong> · not saved</span>` : ''}<span>Agent reading:</span> ${h(question.proposal.reason)}</p>` : ''}${question.counter_reading ? `<p class="av-counter-reading"><span>Counter-reading:</span> ${h(question.counter_reading)}</p>` : ''}${citations ? `<ul class="av-citations av-preview-citations" aria-label="Evidence for your answer">${citations}</ul>` : `<p class="av-source-gap">${h(sourceBasis(question))}</p>`}<div class="av-decision-actions"><p class="av-apply-context"><span>${h(question.prompt || 'Review the consequences')}</span><strong>Your answer: ${h(answer)}</strong></p>${button('Apply decision', `data-av-apply${s.busy || s.pending ? ' disabled' : ''}`, true)}${button('Keep current state', `data-av-cancel${s.busy || s.pending ? ' disabled' : ''}`)}<span>Apply saves your answer and resumes review. Drafts stay unsent.</span></div>${impactMarkup(s.preview, s)}<p class="av-preview-authority">${s.preview.operation ? 'This changes the working process.' : 'This records your review; the source gap remains visible.'} The claim outcome remains for separate review.</p></section>`;
    }
    const questions = agent.questions || [];
    if (!questions.length) return `<section class="av-decision av-decision-empty"><h3>${agent.recovery_required === true ? 'Recovery needed' : agent.state === 'working' ? 'Review in progress' : agent.state === 'paused' ? 'The agent is paused' : agent.state === 'failed' ? 'The review needs recovery' : agent.state === 'waiting_for_others' ? 'Waiting for the next source' : agent.state === 'done' ? 'No handler decision is waiting' : 'No checked decision is available yet'}</h3><p>${h((agent.recovery_required === true && agent.recovery_ask) || agent.next_action || (agent.state === 'working' ? 'The next ask appears when a recorded check needs your decision.' : 'The saved process and sources remain available below.'))}</p></section>`;
    const current = questions.find(question => question.question_id === s.selectedQuestion) || questions[0];
    s.selectedQuestion = current.question_id;
    const picker = questions.length > 1 ? `<div class="av-decision-picker"><label for="avQuestionSelect">Choose a decision</label><small>${questions.length} decisions in this claim</small><select id="avQuestionSelect" data-av-question-select${s.busy || s.pending ? ' disabled' : ''}>${questions.map(question => `<option value="${h(question.question_id)}"${question.question_id === current.question_id ? ' selected' : ''}>${h(question.prompt)}</option>`).join('')}</select></div>` : '';
    return `<div class="av-handoff-layout"><div class="av-handoff-decision">${questionMarkup(current, s, owner)}${picker}</div>${contextMarkup(s.input.process, agent, current)}</div>`;
  }
  function learningPreviewMarkup(preview, s) {
    const scope = preview.scope || {};
    const names = new Map((s.input.process?.graph?.nodes || []).map(node => [node.node_id, node.label]));
    const documents = new Map((preview.fragment_preview?.document_catalog || []).map(doc => [doc.document_type, doc.label]));
    const boundary = item => typeof item === 'string' ? item : `${names.get(item.source_node_id) || label(item.source_node_id)} → ${label(item.relation)} → ${names.get(item.target_node_id) || label(item.target_node_id)}`;
    return `<section id="av-use-scope" class="av-lesson-preview" tabindex="-1"><p class="av-question-kicker">Reusable knowledge · approval required</p><h4 class="av-lesson-title">${h(preview.name || 'Review reuse scope')}</h4>${preview.reason ? `<p class="av-lesson-rationale">${h(preview.reason)}</p>` : ''}<p class="av-lesson-reviewer">Reviewing handler: <strong>${h(preview.actor || 'Not recorded')}</strong></p><dl class="av-lesson-scope"><dt>Claim family</dt><dd>${h(label(scope.family))}</dd><dt>Included steps</dt><dd>${(scope.node_ids || []).map(id => h(names.get(id) || label(id))).join(', ') || 'None'}</dd><dt>Connections outside this fragment</dt><dd>${(scope.boundary_relationships || []).map(item => h(boundary(item))).join(', ') || 'None'}</dd><dt>Document definitions</dt><dd>${(scope.documents || []).map(item => h(typeof item === 'string' ? documents.get(item) || label(item) : item.label || label(item.document_type))).join(', ') || 'None'}</dd></dl><h4>Conflicts</h4>${preview.conflicts?.length ? `<ul>${preview.conflicts.map(item => `<li>${h(typeof item === 'string' ? item : item.reason || item.message || item.label)}</li>`).join('')}</ul>` : '<p>Conflicts with other claims have not been checked. Review them when applying this fragment.</p>'}<p class="av-knowledge-effect">Approval creates a new fragment at version 1. Saved fragments stay unchanged. Applying it to another claim requires a separate preview and approval.</p><div class="av-learning-actions">${button('Approve new fragment', `data-av-lesson-apply${s.busy || s.pending ? ' disabled' : ''}`, true)}${button('Cancel reuse', `data-av-lesson-cancel${s.busy || s.pending ? ' disabled' : ''}`)}</div></section>`;
  }
  function learningFormMarkup(s, owner) {
    const nodes = (s.input.process?.graph?.nodes || []).filter(node => node.validation?.status === 'validated');
    if (s.lessonPreview) return learningPreviewMarkup(s.lessonPreview, s);
    return nodes.length ? `<form class="av-lesson-form" data-av-lesson><h4>Prepare a reusable fragment</h4><label>Name<input id="av-lesson-name" name="name" maxlength="100" required value="${h(s.lessonDraft?.name || '')}"></label><fieldset><legend>Validated steps to include</legend>${nodes.map(node => `<label><input id="av-lesson-node-${h(node.node_id)}" type="checkbox" name="node_ids" value="${h(node.node_id)}"${s.lessonDraft?.node_ids?.includes(node.node_id) ? ' checked' : ''}>${h(node.label)}</label>`).join('')}</fieldset>${owner ? `<input type="hidden" name="actor" value="${h(owner)}">` : `<label>Reviewing handler<input id="av-lesson-actor" name="actor" maxlength="80" required value="${h(s.lessonDraft?.actor || '')}"></label>`}<label>Why this can be reused<textarea id="av-lesson-reason" name="reason" maxlength="2000" required>${h(s.lessonDraft?.reason ?? s.lastOverride?.reason ?? '')}</textarea></label><button id="av-lesson-preview" type="submit" class="av-button"${s.busy ? ' disabled' : ''}>Preview reuse scope</button></form>` : `<p>Validate the relevant process steps before saving a reusable fragment.</p>${button('Review process steps', 'data-av-pane="process"')}`;
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
    return `<section class="av-work" aria-labelledby="av-work-title"><div class="av-section-head"><h3 id="av-work-title">Recorded work</h3>${agent.run?.completed_roles != null ? `<span>${h(agent.run.completed_roles)} of 6 review roles complete</span>` : ''}</div>${rows ? `<ol class="av-activity">${rows}</ol>` : '<p class="av-work-empty">No agent activity has been recorded for this claim.</p>'}<details class="av-trace" data-av-disclosure="trace"${s.open.has('trace') ? ' open' : ''}><summary id="av-trace-summary">Recent recorded work <span>${activity.length} ${activity.length === 1 ? 'milestone' : 'milestones'}</span></summary>${trace ? `<ol>${trace}</ol>` : '<p>No recorded events.</p>'}${agent.run?.run_id ? `<p class="av-run-id">Run ${h(agent.run.run_id)}</p>` : ''}</details>${agent.run?.run_id ? button('Inspect full review', 'data-av-pane="trace"') : ''}</section>
      <section class="av-coverage" aria-labelledby="av-coverage-title"><div class="av-section-head"><h3 id="av-coverage-title">Source coverage</h3><span>${h(read)}</span></div>${coverage.note ? `<p>${h(coverage.note)}</p>` : ''}<ul class="av-coverage-counts"><li data-state="unreadable"><strong>${count(coverage.unreadable_sources)}</strong> could not be read</li><li data-state="held-not-reviewed"><strong>${count(coverage.unread_sources)}</strong> not read</li><li data-state="arrived-since"><strong>${count(coverage.arrived_since)}</strong> arrived since this review</li></ul>${gapRows ? `<ul class="av-coverage-gaps">${gapRows}</ul>` : ''}${evidenceStatesMarkup(s.input.process, agent, s)}${button('Inspect sources', 'data-av-pane="sources"')}</section>
      <details class="av-learning" data-av-disclosure="learning"${s.open.has('learning') ? ' open' : ''}><summary id="av-learning-summary">Reviewed knowledge <span>${memories.length} ${memories.length === 1 ? 'lesson' : 'lessons'} · ${fragments.length} saved process ${fragments.length === 1 ? 'version' : 'versions'}</span></summary><p>Corrections stay with the claim. A lesson or process fragment needs its own review before reuse.</p><div class="av-knowledge-layout"><section class="av-knowledge-library" aria-label="Saved reusable knowledge"><h4>Saved knowledge</h4>${s.lastOverride ? `<p class="av-learning-change"><strong>Recorded in this claim</strong> ${h(s.lastOverride.reason)} ${button('Prepare reuse', 'data-av-prepare-reuse')}</p>` : ''}${memories.length ? `<ul class="av-lessons">${memories.map(memory => `<li><strong>${h(label(memory.condition))}</strong><span>${h(memory.note)}</span><small>${h(memory.handler)} · ${h(label(memory.family))} · ${h(label(memory.status))}</small>${memory.source_quote ? `<blockquote>${h(memory.source_quote)}</blockquote>` : ''}</li>`).join('')}</ul>` : '<p>No reviewed lesson is available for this claim.</p>'}${fragments.length ? `<ul class="av-fragments">${fragments.map(fragment => `<li><strong>${h(fragment.name)}</strong><span>Version ${h(fragment.version)} · ${h(fragment.actor || fragment.handler || 'Recorded reviewer')}</span><small>Source claim ${h(fragment.source_claim_id || fragment.claim_id)}</small></li>`).join('')}</ul>` : ''}${useRows ? `<h4>Recorded reuse</h4><ul class="av-learning-uses">${useRows}</ul>` : '<p>No reviewed knowledge has been applied to this claim.</p>'}</section><div class="av-knowledge-editor">${learningFormMarkup(s, agent.owner?.accountable || s.input.claim?.owner)}</div></div><div class="av-learning-actions">${button('Review lessons', 'data-av-pane="lessons"')}${button('Existing fragment library', 'data-av-pane="fragments"')}</div></details>`;
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
  function renderInto(mount, html) {
    const document=mount.ownerDocument;
    if(!document?.createElement){mount.innerHTML=html;return;}
    const template=document.createElement('template');template.innerHTML=html;
    const current=mount.querySelector('[data-av-claim]'),next=template.content.firstElementChild;
    const header=current?.querySelector('.av-claim-header'),nextHeader=next?.querySelector('.av-claim-header');
    const controls=header?.querySelector('.av-supervision'),nextControls=nextHeader?.querySelector('.av-supervision');
    const metadata=header?.firstElementChild,nextMetadata=nextHeader?.firstElementChild;
    if(!current||current.parentElement!==mount||!next||current.dataset.avClaim!==next.dataset.avClaim||!header||header.parentElement!==current||!nextHeader||nextHeader.parentElement!==next||!controls||!nextControls||metadata?.tagName!=='DIV'||nextMetadata?.tagName!=='DIV'){
      mount.innerHTML=html;return;
    }
    // Progress may arrive between pointerdown and click. An unchanged Controls
    // subtree must stay connected while the surrounding recorded work updates.
    if(!metadata.isEqualNode(nextMetadata))metadata.replaceWith(nextMetadata);
    if(!controls.isEqualNode(nextControls))controls.replaceWith(nextControls);
    for(const name of ['class','aria-busy'])if(current.getAttribute(name)!==next.getAttribute(name))current.setAttribute(name,next.getAttribute(name));
    for(const child of [...current.childNodes])if(child!==header)child.remove();
    for(const child of [...next.childNodes])if(child!==nextHeader)current.append(child);
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
      renderInto(mount, render(s.input));
      bind(mount === root ? options : {...options, root:mount});
      global.CasePathWorkMotion?.observe(mount, s.input.agent?.live_work);
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
      const live = pending?.kind === 'live';
      return api.request(live ? `/api/agent-work/v1/claims/${encodeURIComponent(id)}/runs` : path + suffix, {method:'POST', headers:{'Content-Type':'application/json', ...(pending ? {'X-CasePath-Idempotency-Key':pending.key} : {}), ...(live || suffix === '/reconcile' ? {'X-CasePath-Agent-Work':'1'} : {})}, body:JSON.stringify(body)});
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
      const suffix = kind === 'decision' ? '/decisions/apply' : kind === 'lesson' ? '/lessons/apply' : kind === 'reconcile' ? '/reconcile' : '/control';
      let accepted = false;
      try {
        if (s.pending?.invalid) throw new Error('The recovery record cannot be read. Reload and inspect the journal before continuing.');
        const pending = s.pending || {kind, suffix, body, key:`agent-claim:${global.crypto.randomUUID()}`};
        if (kind === 'live' && !s.pending) pending.body = {...body, idempotency_key:pending.key};
        s.pending = pending; storageWrite(pendingKey, pending); paint();
        const result = await post(pending.suffix, pending.body, pending);
        await verified(result, pending.kind === 'lesson' ? 'result_sha256' : ['control','reconcile'].includes(pending.kind) ? 'projection_sha256' : 'response_sha256', pending.kind === 'live' ? 'casepath.agent-work/1.0.0' : pending.kind === 'lesson' ? 'casepath.causal-process-result/1.0.0' : pending.kind === 'control' ? 'casepath.agent-control-result/1.0.0' : pending.kind === 'reconcile' ? 'casepath.agent-reconciliation-result/1.0.0' : 'casepath.agent-decision-result/1.0.0');
        if (pending.kind === 'live' && (result.summary?.claim_id !== id || result.summary.facts_worker !== 'external_facts' || result.summary.requested_context_sha256 !== pending.body.expected_context_sha256 || result.summary.idempotency_key !== pending.key || !result.summary.run_id)) throw new Error('The live review receipt does not match this request. Inspect saved work before continuing.');
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
        } else if (pending.kind === 'reconcile') {
          const receipt=result.reconciliation;
          if(receipt?.reconciled === false && receipt.reason === 'superseded_recovery_request')s.notice='The recovery request was superseded. Read the current work before continuing.';
          else if(receipt?.reconciled === true && receipt.event_sha256 && receipt.claim_state_changed === false)s.notice='Local proposal reconciled. Review the checkpoint, then resume the agent.';
          else throw new Error('The recovery outcome could not be verified. Read the current work before continuing.');
          s.reconciliationReview = null; s.reconciliationReason = '';
        } else if (pending.kind === 'live') {s.workStage = null; s.open.add('live-work'); s.notice = 'Live review requested. Findings appear as work is recorded.';}
        else s.notice = pending.body.action === 'pause' ? result.agent?.state === 'paused' ? 'The agent is paused.' : stoppingText(result.agent || s.input.agent)+'.' : 'The resume request is recorded.';
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
        if (agent.pause_requested && agent.state === 'working') {s.notice = stoppingText(agent)+'.'; s.busy = false; paint('.av-notice'); return;}
        if (action === 'resume' && inspectRecovery(agent)) throw new Error(agent.recovery_ask || 'Inspect the saved work before requesting recovery.');
        const body = {action, actor, reason:action === 'pause' ? 'Handler stopped the agent from this claim.' : 'Handler requested that the agent resume this claim.', expected_revision:agent.workspace_revision, expected_state_sha256:agent.workspace_state_sha256, expected_agent_revision:agent.agent_revision, expected_agent_state_sha256:agent.agent_state_sha256};
        s.busy = false;
        await mutate('control', body);
      } catch (error) {s.busy = false; s.error = error.message; s.notice = ''; paint('.av-notice');}
    };
    const closingDisclosures = new WeakSet();
    const rememberDisclosure = (target, open) => {
      const key=target.dataset?.avDisclosure;
      if(key){if(open)s.open.add(key);else s.open.delete(key);}
      if(key!=='live-work')return;
      if(open&&s.workPlacement?.observed_working&&s.input.agent.state==='working'&&['queued','running'].includes(s.input.agent.live_work?.status))s.workPlacement.anchored=true;
      if(!open&&s.workPlacement?.anchored){s.workPlacement.anchored=false;closingDisclosures.add(target);}
    };
    const click = event => {
      const summary=event.target.closest('summary'),disclosure=summary?.parentElement;
      if(event.isTrusted===true&&!event.defaultPrevented&&disclosure?.dataset?.avDisclosure&&disclosure.querySelector('summary')===summary&&root.isConnected&&bindings.get(root)===cleanup&&root.contains(disclosure)){
        // Native activation follows this click; save its intent before a
        // refresh can replace the details ahead of the queued toggle event.
        rememberDisclosure(disclosure,!disclosure.open);
        return;
      }
      const target = event.target.closest('button');
      if (!target || !root.contains(target)) return;
      if (target.hasAttribute('data-av-reload')) {s.error = ''; s.preview = null; s.lessonPreview = null; void options.refresh?.(); return;}
      if (target.hasAttribute('data-av-source')) {options.onOpenSource?.(s.sources[Number(target.dataset.avSource)]); return;}
      if (target.hasAttribute('data-av-pane')) {options.onOpenPane?.(target.dataset.avPane, {document_type:target.dataset.avDocument}); return;}
      if (target.hasAttribute('data-av-knowledge')) {s.open.add('learning'); paint('#av-learning-summary');root.querySelector('.av-learning')?.scrollIntoView({block:'start'});return;}
      if (target.hasAttribute('data-av-node') || target.hasAttribute('data-causal-node')) {options.onOpenPane?.('process', {node_id:target.dataset.avNode || target.dataset.causalNode});return;}
      if (target.hasAttribute('data-causal-edge')) {options.onOpenPane?.('process', {edge_id:target.dataset.causalEdge});return;}
      if (target.hasAttribute('data-av-review-document')) {options.onOpenPane?.('process', {node_id:target.dataset.avNodeId, document_type:target.dataset.avReviewDocument});return;}
      if (target.hasAttribute('data-av-work-stage')) {if(s.input.agent.live_work?.stages.some(stage => stage.id === target.dataset.avWorkStage)){s.workStage=target.dataset.avWorkStage;paint('#av-work-stage-'+s.workStage);}return;}
      if (target.hasAttribute('data-av-work-follow')) {s.workStage=null;paint('#av-work-stage-'+s.input.agent.live_work?.active_stage);return;}
      if (s.busy) return;
      if (target.hasAttribute('data-av-recover')) {if (s.pending && !s.pending.invalid) void mutate(s.pending.kind, s.pending.body, true); return;}
      if (s.pending) return;
      if (target.hasAttribute('data-av-live-start')) {const review=s.input.agent.live_review;if(review?.available && review.can_start && /^[a-f0-9]{64}$/.test(review.context_sha256 || ''))void mutate('live',{expected_context_sha256:review.context_sha256,facts_worker:'external_facts'});return;}
      if (target.hasAttribute('data-av-reconcile-review')) {const candidate=reconciliationCandidate(s.input.agent);if(candidate){s.reconciliationReview={title:candidate.title,body:reconciliationBody(s.input.agent,candidate)};s.error='';paint('#av-reconcile-review');root.querySelector('#av-reconcile-review')?.scrollIntoView({block:'start'});}return;}
      if (target.hasAttribute('data-av-reconcile-cancel')) {s.reconciliationReview=null;paint('#avSupervisionSummary');return;}
      if (target.hasAttribute('data-av-cancel')) {s.preview = null; s.previewBody = null; paint('[data-av-decision] input:checked'); return;}
      if (target.hasAttribute('data-av-lesson-cancel')) {s.lessonPreview = null; s.lessonBody = null; paint('.av-lesson-form input'); return;}
      if (target.hasAttribute('data-av-apply') && s.preview && s.previewBody) {void mutate('decision', {...s.previewBody, preview_sha256:s.preview.preview_sha256}); return;}
      if (target.hasAttribute('data-av-lesson-apply') && s.lessonPreview && s.lessonBody) {void mutate('lesson', {...s.lessonBody, preview_sha256:s.lessonPreview.preview_sha256}); return;}
      if (target.hasAttribute('data-av-control')) {
        const agent = s.input.agent, actor = agent.owner?.accountable || s.input.claim?.owner;
        if (agent.pause_requested && agent.state === 'working') {s.notice = stoppingText(agent)+'.'; paint('.av-notice'); return;}
        if (!actor) {s.error = 'Assign a handler before stopping or resuming the agent.'; paint('.av-notice'); return;}
        const action = target.dataset.avControl;
        void control(action, actor);
      }
      if (target.hasAttribute('data-av-prepare-reuse')) {s.open.add('learning'); paint('.av-lesson-form input');}
    };
    const submit = event => {
      const form = event.target;
      if (!form.matches('[data-av-decision],[data-av-lesson],[data-av-reconcile-form]')) return;
      event.preventDefault();
      if (s.busy || s.pending) return;
      const agent = s.input.agent;
      try {
        if (form.hasAttribute('data-av-reconcile-form')) {
          const candidate=reconciliationCandidate(agent),review=s.reconciliationReview,reason=form.elements.reason.value.trim(),actor=agent.owner?.accountable || s.input.claim?.owner;
          if(!candidate || !review || JSON.stringify(review.body)!==JSON.stringify(reconciliationBody(agent,candidate)))throw new Error('The saved work changed. Review the interrupted step again.');
          if(!actor || !reason)throw new Error('A reviewing handler and recovery note are required.');
          s.reconciliationReason=reason;void mutate('reconcile',{...review.body,actor,reason});
        } else if (form.hasAttribute('data-av-decision')) {
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
      if(event.target.id === 'av-reconcile-reason')s.reconciliationReason=event.target.value;
      if (event.target.matches('[data-av-question-select]')) {
        if (event.type === 'change' && !s.busy && !s.pending && s.input.agent.questions.some(question => question.question_id === event.target.value)) {const changed = s.selectedQuestion !== event.target.value;s.selectedQuestion = event.target.value; paint('#avQuestionSelect');if (changed && !global.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches) root.querySelector('.av-consequence')?.animate?.([{opacity:.35,transform:'translateY(5px)'},{opacity:1,transform:'none'}],{duration:180,easing:'ease-out'});}
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
      const comparison=conditionComparisonMarkup(question,s,s.answers[id]),current=form.querySelector('.av-answer-comparison');
      if(current)current.outerHTML=comparison;
      else if(comparison)form.querySelector('.av-question-title')?.insertAdjacentHTML('afterend',comparison);
    };
    const disclosure = event => {
      if(!root.isConnected||bindings.get(root)!==cleanup||!root.contains(event.target))return;
      const key = event.target.dataset?.avDisclosure;
      rememberDisclosure(event.target,event.target.open);
      if(key==='live-work'&&!event.target.open&&closingDisclosures.has(event.target)){
        closingDisclosures.delete(event.target);
        // Moving a focused disclosure can leave native focus on the body.
        // Recover only that lost focus, then reveal the user's moved summary.
        if(s.input.agent.live_work?.status==='completed'){
          const summary=event.target.querySelector('summary'),document=summary?.ownerDocument;
          const focused=summary&&document?.activeElement===summary;
          root.querySelector('.av-decision-mount')?.after(event.target);
          if(focused&&summary.isConnected){
            if(!document.activeElement||document.activeElement===document.body)summary.focus({preventScroll:true});
            if(document.activeElement===summary)summary.scrollIntoView({block:'nearest',inline:'nearest',behavior:'instant'});
          }
        }
      }
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
    if(!s.busy && !s.pending && s.reconciliationReview){const candidate=reconciliationCandidate(agent);if(!candidate || JSON.stringify(s.reconciliationReview.body)!==JSON.stringify(reconciliationBody(agent,candidate))){s.reconciliationReview=null;s.error='The saved work changed. Review the interrupted step again.';}}
    if (['Pausing at next checkpoint.','Stopping after current request.'].includes(s.notice) && agent?.state === 'paused') s.notice = 'The agent is paused.';
    if (!agent) return `<section class="av-claim av-claim-loading" data-av-claim="${h(id)}" aria-busy="true"><p class="av-owner-line">Accountable handler <strong>${h(claim.owner || 'Unassigned')}</strong></p><h2 class="av-claim-title">CasePath agent</h2><p>Loading the saved work and next decision…</p></section>`;
    if (agent.error) return `<section class="av-claim" data-av-claim="${h(id)}"><h2 class="av-claim-title">CasePath agent</h2><p id="av-notice" class="av-notice" data-kind="error" role="alert">${h(agent.error)}</p>${button('Reload saved work', 'data-av-reload')}</section>`;
    const owner = agent.owner?.accountable || claim.owner;
    const review = agent.run, coverage = agent.coverage || {}, summary = [];
    if (review) {
      summary.push(review.currentness === 'historical' ? 'Earlier review' : review.currentness === 'current' ? 'Current review' : 'Recorded review');
      if (Number.isInteger(review.completed_roles) && Number.isInteger(review.role_count) && review.completed_roles >= 0 && review.completed_roles <= review.role_count && review.role_count > 0) summary.push(`${review.completed_roles}/${review.role_count} roles finished`);
    }
    if (Number.isInteger(coverage.read_sources) && Number.isInteger(coverage.total_sources) && coverage.read_sources >= 0 && coverage.read_sources <= coverage.total_sources) summary.push(`${coverage.read_sources}/${coverage.total_sources}${coverage.scope === 'original_bound_intake' ? ' original' : ''} sources read`);
    const draftWaiting = agent.questions?.some(question => question.kind === 'draft_approval');
    const recordedAfterDecision=completedReviewAfterDecision(agent,s);
    const liveWork=liveWorkMarkup(agent,s);
    const pausing = agent.pause_requested && agent.state === 'working';
    const resume = agent.pause_requested || ['paused', 'failed', 'unknown'].includes(agent.state);
    const control = !pausing && inspectRecovery(agent) ? button('Inspect recorded work', 'data-av-pane="trace"') + (owner && reconciliationCandidate(agent) ? button('Review interrupted step','data-av-reconcile-review') : '') + (!owner ? button('Assign handler', 'data-edit-owner') : '') : agent.state === 'done' ? '' : owner ? button(pausing ? stoppingText(agent) : resume ? agent.can_clear_external_pause === true ? 'Resume delegate' : agent.state === 'failed' || agent.state === 'unknown' && !agent.pause_requested && !agent.recovery_required ? 'Retry review' : 'Resume agent' : agent.state === 'waiting_for_you' ? 'Pause delegate' : agent.run?.facts_worker === 'external_facts' ? 'Stop after current request' : 'Stop agent', `data-av-control="${resume ? 'resume' : 'pause'}"${s.busy || s.pending || pausing ? ' disabled' : ''}`) : button('Assign handler', 'data-edit-owner');
    return `<section class="av-claim" data-av-claim="${h(id)}" aria-busy="${s.busy}">
      <header class="av-claim-header"><div><p class="av-owner-line">Accountable handler <strong>${h(owner || 'Unassigned')}</strong> </p><div class="av-agent-line"><h2 class="av-claim-title">${h(agent.owner?.delegate || 'CasePath agent')}</h2><span class="av-delegate">Delegated agent</span><span class="av-state" data-state="${h(agent.state)}">${h(agent.recovery_required === true ? 'Recovery needed' : pausing ? stoppingText(agent) : states[agent.state] || states.unknown)}</span></div>${agent.recovery_required === true && agent.recovery_ask ? `<p class="av-recovery-ask">${h(agent.recovery_ask)}</p>` : ''}${summary.length ? `<p class="av-review-summary">${h(summary.join(' · '))}</p>` : ''}${draftWaiting ? '<p class="av-draft-status">Draft awaits review · not sent.</p>' : ''}</div><details class="av-supervision" data-av-disclosure="supervision"${s.open.has('supervision') || agent.recovery_required ? ' open' : ''}><summary id="avSupervisionSummary">Controls</summary><div class="av-control">${control}${owner ? button('Change handler', 'data-edit-owner') : ''}</div>${mandateMarkup(agent, s)}${liveWork.control}</details></header>
      <div id="av-notice" class="av-notice" tabindex="-1" data-kind="${s.error ? 'error' : 'status'}" role="${s.error ? 'alert' : 'status'}"${!s.error && !s.notice ? ' hidden' : ''}>${h(s.error || s.notice)}${s.error ? ` ${button('Reload saved work', 'data-av-reload')}` : ''}</div>
      ${s.pending ? `<div class="av-pending" role="status"><p>${s.pending.invalid ? 'A recovery record could not be read. Reload and inspect the journal before continuing.' : 'A saved request needs verification. Recovery repeats that same request.'}</p>${s.pending.invalid ? button('Reload saved work', 'data-av-reload', false, 'reload-pending') : button('Recover saved request', `data-av-recover${s.busy ? ' disabled' : ''}`)}</div>` : ''}
      ${s.lastApplied?.impact ? `<details class="av-saved-impact" data-av-disclosure="saved-impact"${s.open.has('saved-impact') ? ' open' : ''}><summary id="av-impact-summary">Last saved decision · consequences</summary>${impactMarkup(s.lastApplied, s, 'saved')}</details>` : ''}
      ${reconciliationMarkup(s)}
      ${recordedAfterDecision?'':liveWork.review}
      <div class="av-decision-mount">${decisionsMarkup(agent, s, owner)}</div>
      ${recordedAfterDecision?liveWork.review:''}
      <nav class="av-claim-tools" aria-label="Claim work">${button('Process and consequences', 'data-av-pane="process"')}${button('Documents and draft', 'data-av-pane="documents"')}${button('Sources', 'data-av-pane="sources"')}${button('What if', 'data-av-pane="what-if"')}${button('Export and journal', 'data-av-pane="activity"')}</nav>
      <div class="av-work-mount">${workMarkup(agent, s)}</div>
    </section>`;
  }
  return {render, renderInto, bind, session, decisionBody, contextNode, releaseReviewPosition};
});
