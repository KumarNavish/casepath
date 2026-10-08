/* A view of sealed review milestones. No timers, authority or provider calls. */
(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CasePathWorkMotion = api;
})(typeof globalThis === 'object' ? globalThis : this, function (global) {
  'use strict';
  const h = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const labels = {waiting:'Not started',working:'Working',recorded:'Work recorded',complete:'Review recorded',paused:'Paused',needs_review:'Needs review'};
  const valid = work => work?.scope === 'recorded_review_work_not_claim_authority' && typeof work.claim_id === 'string' && typeof work.run_id === 'string' && Number.isSafeInteger(work.last_sequence) && work.last_sequence >= 0 && Array.isArray(work.stages) && Array.isArray(work.milestones);
  function markup(work, options = {}) {
    if (!valid(work)) return '';
    const latest = work.milestones.at(-1), selected = options.stage || work.active_stage || latest?.stage || 'sources';
    const stage = work.stages.find(item => item.id === selected) || work.stages[0];
    const milestone = work.milestones.find(item => item.sequence === stage?.milestone_sequence);
    const plain = item => `<span>${h(item.label)}</span>`;
    const source = options.sourceLink || (() => ''), node = work.currentness === 'current' && options.nodeLink || plain, document = work.currentness === 'current' && options.documentLink || plain;
    const reader = work.reader?.kind === 'model' ? `${work.reader.model || 'Model'} source reader · five deterministic checks` : 'Local reference reader · five deterministic checks';
    const stages = work.stages.map(item => `<li data-av-work-state="${h(item.state)}"><button type="button" id="av-work-stage-${h(item.id)}" data-av-work-stage="${h(item.id)}" aria-pressed="${item.id === stage?.id}" aria-controls="av-work-finding" aria-label="${h(`${item.label} review, ${labels[item.state] || 'State unavailable'}, ${item.count} ${item.unit}`)}"><span class="av-work-stage-label">${h(item.label)}</span></button><i class="av-work-arrival" data-av-work-arrival="${h(item.latest_milestone_sequence || item.milestone_sequence || '')}" aria-hidden="true"></i></li>`).join('');
    const selection = stage ? `<p class="av-work-selection"><strong>${h(stage.label)} review</strong><span class="av-work-stage-status">${h(labels[stage.state] || 'State unavailable')}</span><span class="av-work-stage-count">${h(stage.count)} ${h(stage.unit)}</span></p>` : '';
    const detailLabel = stage?.detail_label || (milestone && stage.latest_milestone_sequence > milestone.sequence ? stage.id === 'sources' ? 'Last cited passage' : stage.id === 'process' ? 'Last mapped step' : 'Recorded detail' : '');
    const retained = milestone && detailLabel ? `<p class="av-context-caption">${h(detailLabel)}</p>` : '';
    const linked = milestone?.connections.some(link => link.relation === 'required_by_process');
    const relation = milestone?.documents.length && milestone.documents.every(item => item.needed_now === true) ? 'requires'
      : milestone?.documents.length && milestone.documents.every(item => item.state === 'optional' && item.needed_now === false) ? 'may use' : 'lists';
    const detail = milestone ? `<div class="av-live-finding" id="av-work-finding" data-av-work-sequence="${h(milestone.sequence)}">${retained}<p class="av-live-summary">${h(milestone.summary)}</p>${milestone.sources.map(item => `<div class="av-live-source">${source(item)}<blockquote>${h(item.quote)}</blockquote></div>`).join('')}${milestone.nodes.length || milestone.documents.length ? `<div class="av-live-linked-work"${linked ? ' data-recorded-relation="required_by_process"' : ''}>${milestone.nodes.map(node).join('')}${linked ? `<span class="av-live-relation">${relation}</span>` : ''}${milestone.documents.map(document).join('')}</div>` : ''}</div>` : `<div class="av-live-finding" id="av-work-finding"><p>${stage?.state === 'working' ? 'Waiting for the next saved finding.' : 'No work has been recorded for this stage yet.'}</p></div>`;
    return `<section class="av-live-work" data-av-work-run="${h(work.run_id)}" data-av-work-status="${h(work.status)}" data-av-work-currentness="${h(work.currentness)}" aria-label="Source-grounded review"><div class="av-live-heading"><p class="av-live-intent">${h(work.headline)}</p></div><ol class="av-work-stages" aria-label="Recorded review stages">${stages}</ol>${selection}${detail}<p class="av-live-reader">${h(reader)}</p></section>`;
  }
  const observed = new Map(), animations = new Map();
  let reduced, initialized = false, keyboard = false;
  const cancel = () => {for (const animation of animations.values()) animation.cancel(); animations.clear();};
  const onKey = () => {keyboard = true; cancel();};
  const onPointer = () => {keyboard = false;};
  const onVisibility = () => {if (global.document?.hidden) cancel();};
  const onReduced = () => {if (reduced?.matches) cancel();};
  function initialize() {
    if (initialized) return;
    initialized = true;
    reduced = global.matchMedia?.('(prefers-reduced-motion: reduce)');
    reduced?.addEventListener?.('change', onReduced);
    global.document?.addEventListener('keydown', onKey, true);
    global.document?.addEventListener('pointerdown', onPointer, true);
    global.document?.addEventListener('visibilitychange', onVisibility);
  }
  function animate(element, frames, duration) {
    if (!element?.isConnected || !element.animate || element.closest?.('[hidden],[inert]')) return;
    if (element.contains?.(global.document?.activeElement)) return;
    const rect = element.getBoundingClientRect?.();
    if (rect && (!rect.width || !rect.height || rect.bottom <= 0 || rect.top >= global.innerHeight)) return;
    animations.get(element)?.cancel();
    const animation = element.animate(frames, {duration, easing:'cubic-bezier(.23,1,.32,1)'});
    animations.set(element, animation);
    const done = () => {if (animations.get(element) === animation) animations.delete(element);};
    animation.finished.then(done, done);
  }
  function observe(root, work) {
    if (!valid(work) || !root?.querySelector) return;
    initialize();
    const previous = observed.get(work.claim_id);
    if (previous?.run === work.run_id && previous.sequence > work.last_sequence) return;
    observed.set(work.claim_id, {run:work.run_id, sequence:work.last_sequence, currentness:work.currentness});
    if (observed.size > 150) observed.delete(observed.keys().next().value);
    for (const [node, animation] of animations) if (!node.isConnected) {animation.cancel(); animations.delete(node);}
    if (!previous || previous.run !== work.run_id || previous.sequence >= work.last_sequence ||
        ['historical','unconfirmed'].includes(work.currentness) || ['historical','unconfirmed'].includes(previous.currentness) ||
        keyboard || reduced?.matches || global.document?.hidden) return;
    const milestone = work.milestones.filter(item => item.sequence > previous.sequence && item.sequence <= work.last_sequence).at(-1);
    if (!milestone) return;
    animate(root.querySelector(`[data-av-work-sequence="${milestone.sequence}"]`), [{opacity:.3,transform:'translateY(5px)'},{opacity:1,transform:'none'}], 180);
    animate(root.querySelector(`[data-av-work-arrival="${milestone.sequence}"]`), [{opacity:.35,transform:'scaleX(.1)'},{opacity:1,transform:'scaleX(1)'}], 220);
  }
  function dispose() {
    cancel(); observed.clear();
    reduced?.removeEventListener?.('change', onReduced);
    global.document?.removeEventListener('keydown', onKey, true);
    global.document?.removeEventListener('pointerdown', onPointer, true);
    global.document?.removeEventListener('visibilitychange', onVisibility);
    reduced = undefined; initialized = false; keyboard = false;
  }
  return {markup, observe, dispose};
});
