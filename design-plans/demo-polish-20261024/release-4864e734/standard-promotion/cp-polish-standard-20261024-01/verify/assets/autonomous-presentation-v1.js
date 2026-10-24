/* One presentation clock drives both the live product and its recorded film. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.CasepathPresentation = api;
})(typeof globalThis === 'object' ? globalThis : this, function () {
  'use strict';
  const EASING = 'cubic-bezier(.2,.8,.2,1)';
  const ACTS = Object.freeze(['customer','reading','process','decision','learning','cases']);
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
  return {ACTS,EASING,ease,interpolate,paint,createClock,timeline};
});
