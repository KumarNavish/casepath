/* One presentation clock drives both the live product and its recorded film. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CasepathPresentation = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const EASING = 'cubic-bezier(.2,.8,.2,1)';
  const ACTS = Object.freeze(['customer','plan','reading','process','decision','learning','photo','library','cases']);
  // Editorial labels describe the recorded scene; they never claim live work.
  const CHAPTERS = Object.freeze({
    customer: Object.freeze({number:'01',label:'The request',title:'A customer asks for help.'}),
    plan: Object.freeze({number:'02',label:'The plan',title:'Turn the case into simple questions.'}),
    reading: Object.freeze({number:'03',label:'The checks',title:'Find the proof in the documents.'}),
    process: Object.freeze({number:'03',label:'The checks',title:'Find the proof in the documents.'}),
    decision: Object.freeze({number:'04',label:'The answer',title:'Suggest an answer a person can check.'}),
    learning: Object.freeze({number:'05',label:'The next case',title:'Reuse what was learned.'}),
    photo: Object.freeze({number:'06',label:'Photos',title:'Read photos like documents.'}),
    library: Object.freeze({number:'07',label:'Learning',title:'Learn once. Reuse across cases.'}),
    cases: Object.freeze({number:'08',label:'CasePath',title:'Every answer shows its proof.'})
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
  const decisive = context.decisivePredicate === 'contemporaneous_substantive_reasons';
  // A headline says what happens; the detail says why it matters. A lead cue
  // introduces live work and then clears the screen; a hold cue frames a result.
  // Claims that depend on the record appear only with that evidence supplied.
  const cue = (id, headline, detail, label, target, extra = {}) => ({id, headline, detail, label, target, spotlight: true, mode: 'lead', card: true, ...extra});
  const live = (id, label, target = 'source') => cue(id, '', '', label, target, {spotlight: false, card: false});
  const accepted = ['plan-recede', 'node-accepted', 'node-rest'].includes(phase);
  const nodeTarget = nodeId || op.object?.id;

  if (b.act === 'customer') {
    if (phase === 'ready' || phase === '') {
      if (local < 2600) return live('intro', 'CasePath', 'purpose');
      return cue('sources', 'A customer writes in, with documents.', 'CasePath’s assistants take it from here.', 'The documents', 'sources', {mode: 'hold', align: 'end', part: 'introduction'});
    }
    return cue('question', decisive ? 'The tenant wants a rent increase checked.' : 'First, find what the customer wants.',
      'The assistant marks the request in the message.', 'The question', 'source', {part: 'quote'});
  }

  if (b.act === 'plan') {
    if (phase === 'plan-reuse') {
      return cue('procedure', 'CasePath knows this kind of case.', context.procedureScope
        ? `It reuses its ${String(context.procedureScope).toLowerCase()} checklist, learned from an earlier case.` : 'It reuses a checklist learned from an earlier case.',
        'Reused checklist', 'procedure', {mode: 'hold'});
    }
    if (phase.startsWith('plan-node')) {
      return cue('questions', context.questionCount ? `It breaks the case into ${context.questionCount} questions.` : 'It breaks the case into questions.', 'Each circle is one question.', 'The process', 'spine');
    }
    if (phase === 'plan-rest') {
      return cue('plan-ready', 'The plan is ready.', context.questionCount && context.documentCount ? `${context.questionCount} questions. ${context.documentCount} documents to check.` : 'Now the assistants go to work.', 'The plan', 'procedure', {mode: 'hold'});
    }
    return cue('requirements', 'Then it lists the documents it needs.', 'Each document helps answer one question.', 'Evidence checklist', 'procedure');
  }

  if (b.act === 'reading' || b.act === 'process') {
    if (kind === 'document.check') {
      if (operationId !== context.firstCheckId) return live('document-checks', 'Document check');
      return ['document', 'document-rest', 'plan-tick', 'camera-out'].includes(phase)
        ? cue('document-checked', 'Checked, with proof.', 'The checklist ticks itself off.', 'Document check', 'checklist-row', {mode: 'hold', side: 'below', align: 'start', ...(op.object?.id ? {targetId: op.object.id} : {})})
        : cue('document-check', 'Now it checks each document.', 'It finds the exact sentence that proves it.', 'Document check', 'source', {part: 'quote'});
    }
    if (b.act === 'process') {
      return accepted
        ? cue('process-complete', context.questionCount ? `All ${context.questionCount} questions answered.` : 'All questions answered.', 'Each answer points to its proof.', 'The process', 'spine', {mode: 'hold'})
        : cue('final-check', 'The last question, the same way.', 'Shown faster.', 'The final process question', 'source', {part: 'quote'});
    }
    const firstFact = operationId && operationId === context.firstFactId;
    const factPhase = ['fact', 'connector', 'fact-rest', 'plan-tick', 'camera-out'].includes(phase);
    if (firstFact) {
      if (factPhase) {
        return cue('source-fact', decisive ? 'Found: no reasons were given.' : 'Found: a fact, with its proof.',
          'Linked to the exact sentence.', 'From source to fact', 'fact', {
            mode: 'hold', ...(operationId ? {targetId: operationId} : {}), part: phase === 'connector' ? 'connection' : 'proposed-fact'
          });
      }
      return cue('decisive-source', decisive ? 'The key question: did the landlord give reasons?' : 'The key question.',
        'The assistant searches the documents.', 'The decisive passage', 'source', {part: 'quote'});
    }
    if (accepted) {
      return cue('question-answered', operationId && operationId === context.firstCompletionId ? 'First question answered.' : 'Next question answered.',
        'The documents gave the answer.', 'The process', 'node', {mode: 'hold', ...(nodeTarget ? {targetId: nodeTarget} : {}), part: 'completed-question'});
    }
    return live('reading', 'Recorded work');
  }

  if (b.act === 'decision') {
    if (['completed', 'overview', 'chain', 'chain-rest'].includes(phase)) {
      const columns = {facts: 'Facts taken from the documents.', law: 'The legal rule that applies.', evidence: 'The documents that support it.', needed: 'Evidence still missing.', reference: 'The checklist it reused.'};
      return cue('reasoning', 'The finished process. Every step shows why.', columns[b.column] || 'Each step links its facts, rule and evidence.', 'The reasoning', 'chain', {
        mode: 'hold', targetId: b.column || 'facts', part: b.column || 'facts'
      });
    }
    if (['source-check', 'source-check-rest'].includes(phase)) {
      return cue('verified-passages', 'Every quote is matched to a received file.', 'Nothing in the answer rests on an unchecked quote.', 'Verified passages', 'verified', {mode: 'hold'});
    }
    if (['documents', 'documents-rest'].includes(phase)) {
      return cue('checklist', 'The evidence checklist.', 'Each document is listed because a step of the process needs it.', 'Supporting documents', 'documents', {mode: 'hold'});
    }
    if (['law', 'law-rest'].includes(phase)) {
      return cue('rule', context.decisiveRule === true ? 'The rule connects missing reasons with an invalid notice.' : 'The rule that applies.',
        context.decisiveRule === true ? 'Swiss Code of Obligations, Article 269d, paragraph 2(b).' : 'Quoted from the recorded law text.',
        context.decisiveRule === true ? 'Article 269d, paragraph 2(b)' : 'Rule', 'law', {mode: 'hold'});
    }
    if (phase === 'legal-test-lead') {
      return cue('legal-tests', 'Next, it checks the rules one by one.', context.testCount ? `${context.testCount} checks, from the law that applies.` : 'Each check comes from the law that applies.', 'Recorded legal tests', 'tests', {part: 'check'});
    }
    if (['legal-test', 'legal-test-rest'].includes(phase)) {
      const failed = (b.predicate_status || b.predicate?.status) === 'failed';
      if (failed) {
        return cue('unmet', decisive ? 'One check fails: no reasons were given.' : 'One check fails.', 'All the other checks pass.', 'Recorded legal tests', 'predicate', {
          mode: 'hold', side: 'left', ...(predicateId ? {targetId: predicateId} : {}), part: 'unmet', spotlight: Boolean(predicateId)
        });
      }
      return live('legal-checks', 'Recorded legal tests', 'predicate');
    }
    if (['answer', 'answer-rest'].includes(phase)) {
      if (phase === 'answer-rest' && local >= 3000) {
        return cue('open-questions', 'It also lists what is still open.', 'Open points are flagged, not guessed.', 'Still open', 'open', {mode: 'hold'});
      }
      return cue('proposed-assessment', context.assessmentSupportsInvalidity === true ? 'Suggested answer: the increase is not valid.' : 'A suggested answer is ready.',
        'A person reviews it before anything happens.', 'Proposed assessment', 'lead', {mode: 'hold', side: 'above'});
    }
    if (['draft', 'draft-rest'].includes(phase)) {
      const review = phase === 'draft-rest' && local >= 3000;
      return cue('human-review', 'A reply is drafted. A person decides.', 'Nothing is sent automatically.', 'Human review', review ? 'draft' : 'draft-body', {mode: 'hold', part: review ? 'review-boundary' : 'prepared-reply'});
    }
  }

  if (b.act === 'learning') {
    if (['later-case-rest', 'memory-open', 'memory-overview'].includes(phase)) {
      return cue('later-evidence', 'A new case of the same kind arrives.', 'A different tenant, with their own documents.', 'A later case', 'memory-source', {mode: 'hold'});
    }
    if (['memory-transfer', 'memory-landed'].includes(phase)) {
      const landed = phase === 'memory-landed', first = !(Number.isSafeInteger(b.item) && b.item > 0);
      if (!first) return live('reuse-items', 'Checklist reuse', landed ? 'memory-target' : 'memory-item');
      return cue('reuse-checklist', 'CasePath reuses what it learned.', 'The same checks, on the new documents.', 'Checklist reuse', landed ? 'memory-target' : 'memory-item', {
        ...(Number.isSafeInteger(b.item) && b.item >= 0 ? {targetId: b.item} : {}),
        part: landed ? 'destination' : 'origin',
        spotlight: Number.isSafeInteger(b.item) && b.item >= 0
      });
    }
    if (['memory-notice', 'memory-notice-rest'].includes(phase)) {
      return cue('fresh-facts', 'The checks are reused. The facts are new.', 'Every fact comes from the new case’s own documents.', 'Checklist reuse', 'count', {mode: 'hold', side: 'below', align: 'end'});
    }
    if (['answer', 'answer-rest'].includes(phase)) {
      return cue('later-assessment', 'The new case gets its own answer.', 'Based on its own documents.', "The later case's assessment", 'lead', {mode: 'hold'});
    }
  }

  if (b.act === 'photo') {
    if (['photo-open', 'photo-lead', 'photo-scan', 'photo-region'].includes(phase)) {
      return cue('photo', 'Customers send photos too.', 'CasePath reads them like documents.', 'A photo', 'photo');
    }
    return cue('photo-findings', 'It marks the spots and reads the date.', 'Each finding points to the exact place in the photo.', 'What the photo shows', 'photo-findings', {mode: 'hold'});
  }

  if (b.act === 'library') {
    return cue('library', 'It learns across different kinds of case.', 'Each checklist is learned once, then reused.', 'Knowledge', 'library-index', {mode: 'hold', side: 'corner', ...(b.family ? {targetId: b.family} : {})});
  }

  if (b.act === 'cases') {
    if (['wordmark', 'wordmark-rest'].includes(phase)) {
      return cue('finale', 'Every step has a reason.', '', 'CasePath', 'finale', {spotlight: false, card: false, mode: 'hold'});
    }
    return cue('recorded-examples', 'Every recorded example can be inspected.', 'Open any case to follow each answer back to its documents.', 'Recorded examples', 'cases', {mode: 'hold'});
  }
  return live('orientation', 'Recorded demonstration');
}

  return {ACTS,EASING,ease,interpolate,paint,createClock,timeline,chapter,ringTransform,documentaryRuleFocus,documentaryCue};
});
