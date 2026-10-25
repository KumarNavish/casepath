/* One presentation clock drives both the live product and its recorded film. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CasepathPresentation = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const EASING = 'cubic-bezier(.2,.8,.2,1)';
  const ACTS = Object.freeze(['customer','reading','process','decision','learning','cases']);
  // Editorial labels describe the recorded scene; they never claim live work.
  const CHAPTERS = Object.freeze({
    customer: Object.freeze({number:'01',label:'The question',title:'Start with the question.'}),
    reading: Object.freeze({number:'02',label:'The evidence',title:'Find the exact evidence.'}),
    process: Object.freeze({number:'03',label:'The process',title:'Build each step from evidence.'}),
    decision: Object.freeze({number:'04',label:'The assessment',title:'Make the answer reviewable.'}),
    learning: Object.freeze({number:'05',label:'The next case',title:'Reuse the checklist. Recheck the evidence.'}),
    cases: Object.freeze({number:'06',label:'CasePath',title:'Every step has a reason.'})
  });
  function chapter(act) {
    if (!Object.hasOwn(CHAPTERS,act)) throw new TypeError('Unknown presentation chapter.');
    return CHAPTERS[act];
  }
  const clamp = value => Math.max(0, Math.min(1, value));
  function ease(progress) {
    const x = clamp(progress);
    if (x === 0 || x === 1) return x;
    const bezier = (t, a, b) => 3*(1-t)*(1-t)*t*a + 3*(1-t)*t*t*b + t*t*t;
    let low = 0, high = 1;
    for (let i = 0; i < 40; i++) {
      const t = (low + high)/2;
      if (bezier(t,.2,.2) < x) low = t; else high = t;
    }
    return bezier((low+high)/2,.8,1);
  }
  // Native CSS/Web Animations have their own timebase. This interpolation
  // writes only compositor properties and creates no browser animation.
  function interpolate(from, to, progress) {
    const number = /[-+]?(?:\d*\.\d+|\d+)(?:e[-+]?\d+)?/giu;
    const a = String(from), b = String(to), av = a.match(number), bv = b.match(number);
    if (!av || !bv || av.length !== bv.length || a.replace(number,'#') !== b.replace(number,'#')) throw new TypeError('Motion endpoints must have matching transform functions and units.');
    let i = 0;
    return b.replace(number, () => {
      const value = Number(av[i]) + (Number(bv[i])-Number(av[i++]))*progress;
      return String(Math.round(value*1e9)/1e9);
    });
  }
  function paint(element, from, to, progress) {
    if (!element?.style) return;
    for (const key of new Set([...Object.keys(from), ...Object.keys(to)])) {
      if (!['opacity','transform'].includes(key) || from[key] === undefined || to[key] === undefined) throw new TypeError('Motion changes transform and opacity only, with two explicit endpoints.');
      element.style[key] = interpolate(from[key],to[key],progress);
    }
  }
  function createClock(runtime, {reducedMotion = false} = {}) {
    let origin = runtime.performance.now(), offset = 0, paused = false, manual = false, disposed = false, frame = null, effect = null;
    const waits = new Set(), listeners = new Set(), events = [];
    const now = () => paused || manual ? offset : offset + runtime.performance.now() - origin;
    const stopFrame = () => { if (frame !== null) runtime.cancelAnimationFrame(frame); frame = null; };
    function finishEffect(completed) {
      const held = effect;
      if (!held) return;
      effect = null;
      if (completed) paint(held.element,held.from,held.to,1);
      held.resolve(completed);
    }
    function schedule() {
      if (disposed || paused || manual || frame !== null || (!effect && !waits.size && !listeners.size)) return;
      frame = runtime.requestAnimationFrame(() => { frame = null; sample(); });
    }
    function sample(at = now()) {
      if (disposed) return at;
      if (effect && !effect.element.isConnected) finishEffect(false);
      if (effect) {
        const progress = clamp((at-effect.start)/effect.duration);
        paint(effect.element,effect.from,effect.to,ease(progress));
        if (progress >= 1-1e-7) finishEffect(true);
      }
      for (const wait of [...waits]) if (at >= wait.end-1e-7) { waits.delete(wait); wait.resolve(true); }
      for (const listener of listeners) listener(at);
      schedule();
      return at;
    }
    function hold(milliseconds) {
      if (!Number.isFinite(milliseconds) || milliseconds < 0) throw new TypeError('A hold needs a nonnegative duration.');
      if (disposed) return Promise.resolve(false);
      if (!milliseconds) return Promise.resolve(true);
      return new Promise(resolve => { waits.add({end:now()+milliseconds,resolve}); schedule(); });
    }
    function animate(element, keyframes, milliseconds) {
      if (disposed) return Promise.resolve(false);
      if (effect) throw new Error('The demonstration already has an active visual change.');
      if (!Number.isFinite(milliseconds) || milliseconds < 250 || milliseconds > 700) throw new RangeError('Demonstration motion lasts 250–700 ms.');
      if (!Array.isArray(keyframes) || keyframes.length !== 2) throw new TypeError('Motion needs two explicit endpoints.');
      const [from,to] = keyframes;
      paint({style:{}},from,to,0);
      if (!element?.isConnected) return Promise.resolve(false);
      paint(element,from,to,reducedMotion?1:0);
      if (reducedMotion) return Promise.resolve(true);
      return new Promise(resolve => { effect={element,from,to,duration:milliseconds,start:now(),resolve}; schedule(); });
    }
    function pause() { if (disposed || paused) return; offset=now(); paused=true; stopFrame(); sample(offset); }
    function resume() { if (disposed || !paused && !manual) return; origin=runtime.performance.now(); manual=false; paused=false; schedule(); }
    function seek(milliseconds) {
      if (!Number.isFinite(milliseconds) || milliseconds < 0) throw new RangeError('Presentation time must be nonnegative.');
      if (effect || waits.size) throw new Error('Seek is available only for an absolute presentation timeline.');
      paused=true; offset=milliseconds; stopFrame(); return sample(milliseconds);
    }
    function stepTo(milliseconds) {
      if (!Number.isFinite(milliseconds) || milliseconds < 0) throw new RangeError('Presentation time must be nonnegative.');
      if (effect || waits.size) throw new Error('External stepping requires an absolute presentation timeline.');
      // A virtual frame clock freezes wall time, not the user's playing state.
      manual=true; paused=false; offset=milliseconds; stopFrame(); return sample(milliseconds);
    }
    function cancel() {
      if (disposed) return;
      offset=now(); paused=true; disposed=true; stopFrame(); finishEffect(false);
      for (const wait of waits) wait.resolve(false);
      waits.clear(); listeners.clear();
    }
    return {
      now,sample,hold,animate,pause,resume,seek,stepTo,cancel,
      mark(kind,detail={}) { const event=Object.freeze({...detail,at:now(),kind}); events.push(event); return event; },
      onFrame(listener) { listeners.add(listener); schedule(); return () => listeners.delete(listener); },
      get paused() { return paused; }, get externallyDriven() { return manual; }, get disposed() { return disposed; },
      get activeEffects() { return effect?1:0; }, get events() { return events.slice(); }
    };
  }
  function timeline(rows) {
    let end = 0;
    const beats = rows.map((row,index) => {
      if (!ACTS.includes(row.act) || !Number.isFinite(row.duration) || row.duration <= 0) throw new TypeError('Each presentation beat needs an act and positive duration.');
      const start=end; end+=row.duration;
      return Object.freeze({...row,index,start,end});
    });
    return Object.freeze({beats:Object.freeze(beats),duration:end,acts:Object.freeze(ACTS.map(id=>{
      const group=beats.filter(row=>row.act===id);
      return Object.freeze({id,start:group[0]?.start??null,end:group.at(-1)?.end??null});
    })),at(milliseconds) {
      const at=Math.max(0,Math.min(end,milliseconds));
      const beat=beats.find(row=>at<row.end)||beats.at(-1);
      return {beat,elapsed:at-beat.start,progress:clamp((at-beat.start)/beat.duration),at};
    }});
  }
  function ringTransform(milliseconds,reducedMotion=false) {
    if(!Number.isFinite(milliseconds)||milliseconds<0)throw new RangeError('Ring time must be nonnegative.');
    return `rotate(${reducedMotion?0:Math.round((milliseconds%2400)*.15*1e6)/1e6}deg)`;
  }

// Locate an exact recorded clause, never a paraphrase or an inferred legal source.
// The caller must identify both the recorded failed check and the actual article.
function documentaryRuleFocus(text, context = {}) {
  if (typeof text !== 'string' || context.decisivePredicate !== 'contemporaneous_substantive_reasons' || String(context.article) !== '269d') return null;
  const lead = /2\s+Die Mietzinserhöhung ist nichtig, wenn der Vermieter:/u.exec(text);
  const matches = [...text.matchAll(/b\.\s*sie nicht begründet;/gu)];
  if (!lead || matches.length !== 1) return null;
  const match = matches[0], start = match.index, end = start + match[0].length;
  const paragraphStart = lead.index + lead[0].length;
  const nextParagraph = text.slice(paragraphStart).search(/(?:^|[\s.!?])3\s/u);
  if (start < paragraphStart || nextParagraph >= 0 && start >= paragraphStart + nextParagraph) return null;
  return {start, end, quote: match[0], article: '269d', paragraph: '2(b)'};
}

/* Pure editorial metadata. No DOM, timers, playback state, or outcome changes. */
function documentaryCue(beat, elapsed = 0, context = {}) {
  const b = beat && typeof beat === 'object' ? beat : {};
  const transition = b.phase === 'act-transition' || b.phase === 'scene-transition';
  const phase = transition ? b.nextPhase || '' : b.phase || '';
  const op = b.op && typeof b.op === 'object' ? b.op : {};
  const operationId = op.id || (typeof b.operation === 'string' ? b.operation : b.operation?.id) || b.operation_id;
  const kind = op.kind || b.kind || b.usekind;
  const finiteElapsed = Number.isFinite(elapsed) ? Math.max(0, elapsed) : 0;
  const local = transition ? 0 : Number.isFinite(b.duration) ? Math.min(finiteElapsed, b.duration) : finiteElapsed;
  const nodeId = b.node_id || b.nodeId || (kind === 'completed' || kind === 'node_completed' || kind === 'completion' ? op.object?.id : undefined);
  const predicateId = typeof b.predicate === 'string' ? b.predicate : b.predicate?.predicate_id || b.predicate?.id || b.predicate_id;
  const cue = (id, headline, label, target, detail = {}) => ({id, headline, label, target, spotlight: true, ...detail});

  // Cue IDs identify stable sentences. Targets may hand off within one sentence.
  // Every sentence lasts >= 2 seconds in the unchanged 98.55-second film.
  if (b.act === 'customer') {
    return cue('question', context.decisivePredicate === 'contemporaneous_substantive_reasons'
      ? 'The tenant asks us to check a rent-increase notice.'
      : "Start with the tenant's question.", 'The question', 'source', {
      part: phase === 'ready' ? 'introduction' : 'quote',
      spotlight: phase !== 'ready' && phase !== ''
    });
  }

  if (b.act === 'reading' || b.act === 'process') {
    const accepted = ['plan-recede', 'node-accepted', 'node-rest'].includes(phase);
    if (b.act === 'reading' && operationId && operationId === context.firstCompletionId) {
      return cue('circles', 'Each circle is one question to check.', 'How to read the circles', 'node', {
        ...(nodeId || op.object?.id ? {targetId: nodeId || op.object.id} : {}), part: accepted ? 'completed-question' : 'current-question'
      });
    }
    const firstFact = operationId && operationId === context.firstFactId;
    const factPhase = ['fact', 'connector', 'fact-rest', 'plan-tick', 'camera-out'].includes(phase);
    if (firstFact || kind === 'fact' || factPhase) {
      if (factPhase) {
        return cue('source-fact', firstFact && context.decisivePredicate === 'contemporaneous_substantive_reasons'
          ? 'Proposed finding: the original notice gave no reasons.'
          : 'This passage supports a proposed fact.', 'From source to fact', 'fact', {
          ...(operationId ? {targetId: operationId} : {}), part: phase === 'connector' ? 'connection' : 'proposed-fact'
        });
      }
      return cue('decisive-source', firstFact && context.decisivePredicate === 'contemporaneous_substantive_reasons'
        ? 'Look here: no reasons accompanied the original notice.'
        : 'Look for the exact passage supporting this fact.', 'The decisive passage', 'source', {part: 'quote'});
    }
    return cue(b.act === 'process' ? 'final-check' : 'source-question', b.act === 'process'
      ? 'Follow the final recorded check.'
      : 'The evidence helps answer this process question.', b.act === 'process'
      ? 'The final process question' : 'From evidence to process', accepted ? 'node' : 'source', {
      ...(accepted && (nodeId || op.object?.id) ? {targetId: nodeId || op.object.id} : {}), part: accepted ? 'completed-question' : 'quote'
    });
  }

  if (b.act === 'decision') {
    if (['completed', 'overview', 'chain', 'chain-rest'].includes(phase)) {
      return cue('reasoning', 'Follow the fact, rule and supporting sources.', 'The reasoning', 'chain', {
        targetId: b.column || 'facts', part: b.column || 'facts'
      });
    }
    if (['source-check', 'source-check-rest'].includes(phase)) {
      return cue('verified-passages', 'Each quoted passage is matched to a received file.', 'Verified passages', 'verified');
    }
    // The document cutaway is only 1.3s; keep its sentence continuous with the law scene.
    if (['law', 'law-rest', 'documents', 'documents-rest'].includes(phase)) {
      const documents = phase.startsWith('documents');
      return cue('rule-documents', context.decisiveRule === true
        ? 'The rule connects missing reasons with an invalid notice.'
        : 'See the rule and the documents used.', documents ? 'Supporting documents'
        : context.decisiveRule === true ? 'Article 269d, paragraph 2(b)' : 'Rule and documents', documents ? 'documents' : 'law');
    }
    if (['legal-test', 'legal-test-rest'].includes(phase)) {
      return cue('legal-tests', 'The recorded assessment flags one unmet requirement.', 'Recorded legal tests', 'predicate', {
        ...(predicateId ? {targetId: predicateId} : {}),
        part: (b.predicate_status || b.predicate?.status) === 'failed' ? 'unmet' : 'check',
        // A missing identity must never fall back to a numeric DOM position.
        spotlight: Boolean(predicateId)
      });
    }
    if (['answer', 'answer-rest'].includes(phase)) {
      // The existing 6s answer hold gives the unresolved issues their own 3s.
      if (phase === 'answer-rest' && local >= 3000) {
        return cue('open-questions', 'Other questions remain unanswered.', 'Still open', 'open');
      }
      return cue('proposed-assessment', context.assessmentSupportsInvalidity === true
        ? 'Proposed assessment: invalid on this ground.'
        : 'Read the proposed assessment.', 'Proposed assessment', 'lead');
    }
    if (['draft', 'draft-rest'].includes(phase)) {
      const review = phase === 'draft-rest' && local >= 3000;
      return cue('human-review', 'A draft for a person to review. Nothing is sent.', 'Human review', review ? 'draft' : 'draft-body', {part: review ? 'review-boundary' : 'prepared-reply'});
    }
  }

  if (b.act === 'learning') {
    if (['later-case-rest', 'memory-open', 'memory-overview'].includes(phase)) {
      return cue('later-evidence', 'This case brings its own evidence.', 'A later case', 'memory-source');
    }
    if (['memory-transfer', 'memory-landed'].includes(phase)) {
      const landed = phase === 'memory-landed';
      return cue('reuse-checklist', "Reuse the checklist. Recheck this case's evidence.", 'Checklist reuse', landed ? 'memory-target' : 'memory-item', {
        ...(Number.isSafeInteger(b.item) && b.item >= 0 ? {targetId: b.item} : {}),
        part: landed ? 'destination' : 'origin',
        spotlight: Number.isSafeInteger(b.item) && b.item >= 0
      });
    }
    if (['memory-notice', 'memory-notice-rest'].includes(phase)) {
      return cue('fresh-facts', 'The checks are reused. The facts belong to this case.', 'Checklist reuse', 'count');
    }
    if (['answer', 'answer-rest'].includes(phase)) {
      return cue('later-assessment', 'This case receives its own proposed assessment.', "The later case's assessment", 'lead');
    }
  }

  if (b.act === 'cases') {
    if (['wordmark', 'wordmark-rest'].includes(phase)) {
      return cue('finale', 'Every step has a reason.', 'CasePath', 'finale', {spotlight: false});
    }
    return cue('recorded-examples', 'Every recorded example can be inspected.', 'Recorded examples', 'cases');
  }
  return cue('orientation', 'Follow each question back to its evidence.', 'Recorded demonstration', 'source', {spotlight: false});
}


  return {ACTS,EASING,ease,interpolate,paint,createClock,timeline,chapter,ringTransform,documentaryRuleFocus,documentaryCue};
});
