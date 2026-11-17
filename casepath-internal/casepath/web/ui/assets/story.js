/* CasePath story engine: the work of a case as a picture that builds itself.
 *
 *   const story = CasePathStory.mount(element, model, options);
 *   story.update(model); story.play(); story.pause(); story.seek(i); story.whole(); story.destroy();
 *
 * A world (cards in lanes, edges in one SVG layer under them) sits in a viewport; a camera (one transform on the
 * world) frames what the current beat is about. Everything a beat changes is a class on a node or an edge, so the
 * choreography lives in story.css and the browser animates transform and opacity only. No JS runs per frame except
 * while the reader drags or pinches the stage.
 */
(function () {
  "use strict";

  const SVGNS = "http://www.w3.org/2000/svg";
  // Card sizes in world px. They are fixed per kind so the layout is pure arithmetic: nothing is measured in the DOM.
  const SIZE = { file: [228, 72], fact: [236, 78], need: [236, 78], step: [232, 58], knowledge: [232, 64], letter: [272, 0], decision: [224, 56], entry: [232, 62] };
  const GAP = { row: 14, step: 26, group: 28, col: 40, lane: 104 };
  // The camera never goes where text blurs (max) or titles stop being readable (min); only the whole picture of a
  // large case may go below min, because showing all of it is its purpose.
  const CAM = { min: 0.55, max: 1.25, beat: 1.1, whole: 0.2, top: 58, side: 28, bottom: 24 };   // top: the band of lane titles
  const ICON = {
    sheet: "M5 1.5h9.5l6 6V25a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 25V3A1.5 1.5 0 0 1 5 1.5zM14.5 1.5v6h6M7.5 13h9M7.5 17h9M7.5 21h5.5",
    tick: "M3.6 8.5l2.9 2.9 5.9-6.6",
    layers: "M12 4.5l8 4-8 4-8-4zM4 12.5l8 4 8-4M4 16.5l8 4 8-4",
    play: "M8.5 5.6v12.8L19 12z", pause: "M7.5 5.5h3v13h-3zM13.5 5.5h3v13h-3z",
    replay: "M5.5 12a6.5 6.5 0 1 0 2-4.7M5 4.6v3.6h3.6", whole: "M4 9V5h4M16 5h4v4M20 15v4h-4M8 19H4v-4", close: "M6 6l12 12M18 6L6 18",
  };
  const LABELS = { play: "Play", pause: "Pause", replay: "Again", step: "Step", of: "of", close: "Close", whole: "Whole picture" };
  const LINE_W = [100, 93, 97, 86, 95, 78, 90, 99, 84, 92, 70, 96, 88, 60];

  const memory = new Map();      // model signature → beat index: a story mounted again is shown where it was, not replayed
  const mounted = new WeakMap(); // element → instance, so a second mount on the same element replaces the first

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  function el(tag, cls, text, parent) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;   // every model text goes in as text, never as HTML
    if (parent) parent.appendChild(e);
    return e;
  }
  function svg(tag, attrs, parent) {
    const e = document.createElementNS(SVGNS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function icon(name, box, cls, parent) {
    const s = svg("svg", { viewBox: box || "0 0 24 24", class: cls, "aria-hidden": "true" }, parent);
    svg("path", { d: ICON[name] }, s);
    return s;
  }
  function readModel(m) {
    m = m || {};
    return { lanes: m.lanes || [], nodes: m.nodes || [], edges: m.edges || [], beats: m.beats || [], live: Boolean(m.live), labels: Object.assign({}, LABELS, m.labels) };
  }
  // What makes two models "the same story": used to remember where a finished story stood.
  const signature = (m) => [m.lanes.map((l) => l.id).join(","), m.nodes.length, m.edges.length, m.beats.length, (m.nodes[0] || {}).id,
    ((m.beats[m.beats.length - 1] || {}).caption || {}).what].join("|");

  function mount(host, rawModel, options) {
    if (mounted.has(host)) mounted.get(host).destroy();
    const opt = Object.assign({ autoplay: true, start: "first", height: 420, compact: false, onOpen: null, onClose: null }, options);
    const abort = new AbortController(), on = { signal: abort.signal };
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let M = readModel(rawModel), reduced = motion.matches, dead = false;
    const nodes = new Map(), edges = new Map(), byEl = new WeakMap();   // id → record, "from>to" → record, button → record
    let lanes = [], cols = [], W = 0, H = 0, rows = 0;
    const S = { index: -1, playing: false, rest: false, timer: 0, view: "whole", cam: { x: 0, y: 0, s: 1 }, vw: 0, vh: 0, marked: [], capLayer: 0, capText: "" };
    const last = () => M.beats.length - 1;

    // ---------- the fixed parts: stage, world, caption, controls ----------
    const root = el("div", "cps" + (opt.compact ? " cps-compact" : ""), null, host);
    const stage = el("div", "cps-stage", null, root);
    stage.style.height = `${opt.height}px`;
    stage.tabIndex = 0;
    stage.setAttribute("role", "group");
    const world = el("div", "cps-world", null, stage);
    const edgeLayer = svg("svg", { class: "cps-edges", "aria-hidden": "true" }, world);
    const heads = el("div", "cps-heads", null, stage);
    const caption = el("div", "cps-caption", null, root);
    caption.setAttribute("aria-live", "polite");
    const capLayers = [0, 1].map(() => {
      const c = el("div", "cps-cap", null, caption);
      return { el: c, agent: el("span", "cps-agent", null, c), what: el("span", "cps-what", null, c), why: el("span", "cps-why", null, c) };
    });
    const bar = el("div", "cps-bar", null, root);
    const playBtn = el("button", "cps-play", null, bar);
    playBtn.type = "button";
    const playIcon = icon("play", null, "cps-ico", playBtn).firstChild;
    const timeline = el("div", "cps-timeline", null, bar);
    timeline.tabIndex = 0;
    timeline.setAttribute("role", "slider");
    const track = el("span", "cps-track", null, timeline), fill = el("span", "cps-fill", null, track);
    const tickBox = el("span", "cps-ticks", null, timeline);
    const count = el("span", "cps-count", null, bar);
    const wholeBtn = el("button", "cps-ghost", null, bar);
    wholeBtn.type = "button";
    icon("whole", null, "cps-ico", wholeBtn);
    const wholeText = el("span", null, null, wholeBtn);
    let closeBtn = null;
    if (typeof opt.onClose === "function") {
      closeBtn = el("button", "cps-ghost cps-close", null, bar);
      closeBtn.type = "button";
      icon("close", null, "cps-ico", closeBtn);
      closeBtn.addEventListener("click", () => opt.onClose(), on);
    }

    // ---------- nodes and edges ----------
    function makeNode(n) {
      const kind = SIZE[n.kind] ? n.kind : "entry";
      const btn = el("button", `cps-node cps-k-${kind}`);
      btn.type = "button";
      const card = el("span", "cps-card", null, btn), P = {};
      if (kind === "file") icon("sheet", "0 0 24 28", "cps-sheet", card);
      else if (kind === "knowledge") icon("layers", null, "cps-sheet", card);
      else if (kind !== "fact" && kind !== "letter") icon("tick", "0 0 16 16", "cps-tick", el("span", "cps-mark", null, card));
      const body = el("span", "cps-body", null, card);
      P.title = el("span", "cps-title", null, body);
      const foot = el("span", "cps-foot", null, body);
      if (kind === "need") P.ratio = el("i", null, null, el("span", "cps-ratio", null, foot));
      P.sub = el("span", "cps-sub", null, foot);
      P.ref = el("span", "cps-ref", null, foot);   // the label of the edge it rests on («S. 6»): shown once that edge is drawn
      if (kind === "letter") P.lines = el("span", "cps-lines", null, body);
      const rec = { id: n.id, n, kind, el: btn, P, w: SIZE[kind][0], h: SIZE[kind][1], x: -1, y: -1, at: -1, col: 0, lane: n.lane };
      world.appendChild(btn);
      nodes.set(n.id, rec); byEl.set(btn, rec);
      return rec;
    }
    // Texts and state can change between updates of a live run (a step turns from "now" to "done").
    function paint(rec, n) {
      const P = rec.P, sub = n.sub && n.sub !== n.title ? String(n.sub) : "", is = [n.title, sub, n.state, n.href, n.lines].join("\n");
      rec.n = n;
      rec.lane = n.lane;
      if (is === rec.is) return;   // nothing about it changed: nothing is written
      rec.is = is;
      P.title.textContent = n.title || "";
      P.sub.textContent = sub;
      rec.el.dataset.state = n.state || "";
      rec.el.classList.toggle("cps-link", Boolean(n.href));
      rec.el.setAttribute("aria-label", [n.title, n.sub !== n.title && n.sub].filter(Boolean).join(", "));
      if (String(n.title || "").length > 52) rec.el.title = n.title; else rec.el.removeAttribute("title");
      if (P.ratio) {   // «in 6 von 7 Fällen verlangt»: the two numbers as a small bar that fills
        const m = /(\d+)\D+(\d+)/.exec(sub), r = m && +m[2] > 0 && +m[1] <= +m[2] ? +m[1] / +m[2] : -1;
        P.ratio.parentNode.hidden = r < 0;
        P.ratio.style.setProperty("--cps-r", String(Math.max(0, r)));
      }
      if (P.lines) {
        const want = clamp(n.lines | 0, 0, LINE_W.length);
        while (P.lines.childNodes.length > want) P.lines.removeChild(P.lines.lastChild);
        while (P.lines.childNodes.length < want) {
          const i = P.lines.childNodes.length, line = el("i", null, null, P.lines);
          line.style.setProperty("--cps-w", `${i === want - 1 && want > 1 ? 46 : LINE_W[i]}%`);
          line.style.setProperty("--cps-i", String(i));
        }
        rec.h = 74 + (sub ? 20 : 0) + want * 11;
      }
      rec.el.style.width = `${rec.w}px`;
      rec.el.style.height = `${rec.h}px`;
    }
    function makeEdge(e) {
      const kind = /^(cites|leads|learned|branch)$/.test(e.kind) ? e.kind : "cites";
      const g = svg("g", { class: `cps-edge cps-e-${kind}` }, edgeLayer);
      const rec = { key: `${e.from}>${e.to}`, from: e.from, to: e.to, kind, label: e.label || "", g, path: svg("path", {}, g), dot: svg("circle", { r: kind === "leads" ? 3.4 : 2.8 }, g), d: "", at: -1, ms: 0 };
      edges.set(rec.key, rec);
      return rec;
    }
    // Bring the DOM in line with the model: only what is not there yet is created.
    function sync() {
      for (const n of M.nodes) paint(nodes.get(n.id) || makeNode(n), n);
      for (const e of M.edges) if (nodes.has(e.from) && nodes.has(e.to) && !edges.has(`${e.from}>${e.to}`)) makeEdge(e);
      // when does each piece enter the picture: with the first beat that names it, else it is there from the start
      const first = new Map(), firstEdge = new Map();
      M.beats.forEach((b, i) => {
        for (const id of b.reveal || []) if (!first.has(id)) first.set(id, i);
        for (const p of b.edges || []) if (p && !firstEdge.has(`${p[0]}>${p[1]}`)) firstEdge.set(`${p[0]}>${p[1]}`, i);
      });
      nodes.forEach((r) => { r.at = first.has(r.id) ? first.get(r.id) : -1; });
      edges.forEach((e) => { e.at = Math.max(firstEdge.has(e.key) ? firstEdge.get(e.key) : -1, nodes.get(e.from).at, nodes.get(e.to).at); });
    }

    // ---------- layout: lanes left to right, a long lane in sub-columns ----------
    function plan(R, place) {
      const out = []; let x = 0, tall = 0;
      lanes.forEach((lane, li) => {
        if (li) x += GAP.lane;
        // Cards of one kind stay together, in the order the model names them. A lane with more than R cards runs on
        // in further columns: a column is closed when it is full, or when the next kind would not fit under it.
        // Columns are filled one after the other, so a card added to a live run lands at the end and the others
        // stay where they are. Decisions always stand in a column of their own: that lets them fork from the letter.
        const kinds = new Map(), split = lane.recs.length > R, parts = [[]];
        lane.recs.forEach((r) => { if (!kinds.has(r.kind)) kinds.set(r.kind, []); kinds.get(r.kind).push(r); });
        kinds.forEach((list, kind) => list.forEach((r, i) => {
          const cur = parts[parts.length - 1];
          const turn = i === 0 && cur.length > 0 && (kind === "decision" || (split && cur.length >= 3 && R - cur.length < list.length));
          if (cur.length >= R || turn) parts.push([r]); else cur.push(r);
        }));
        lane.x = x; lane.h = 0;
        const mine = parts.map((items, ci) => {
          if (ci) x += GAP.col;
          let w = 200, h = 0, prev = null;
          const ys = items.map((r) => { h += prev ? (prev.kind !== r.kind ? GAP.group : r.kind === "step" ? GAP.step : GAP.row) : 0; const y = h; h += r.h; w = Math.max(w, r.w); prev = r; return y; });
          const col = { lane, x, w, h, items, ys, split };
          x += w; lane.h = Math.max(lane.h, h);
          return col;
        });
        lane.w = x - lane.x;
        tall = Math.max(tall, lane.h);
        out.push(...mine);
      });
      if (place) {
        // every lane is centred on the picture's middle line; the columns of a long lane share one top edge (a grid)
        out.forEach((col, ci) => col.items.forEach((r, i) => {
          const nx = col.x + (col.w - r.w) / 2, ny = Math.round((tall - (col.split ? col.lane.h : col.h)) / 2) + col.ys[i];
          r.col = ci;
          if (nx !== r.x || ny !== r.y) { r.x = nx; r.y = ny; r.el.style.transform = `translate(${nx}px,${ny}px)`; }
        }));
      }
      return { cols: out, w: x, h: tall };
    }
    function layout() {
      const ids = M.lanes.map((l) => l.id);
      nodes.forEach((r) => { if (!ids.includes(r.lane)) ids.push(r.lane); });
      lanes = ids.map((id) => ({ id, title: (M.lanes.find((l) => l.id === id) || {}).title || "", recs: [], x: 0, h: 0 }));
      for (const n of M.nodes) lanes[ids.indexOf(n.lane)].recs.push(nodes.get(n.id));
      // rows per sub-column: the count that lets the whole picture fill this viewport best. It is kept across
      // updates unless another count is clearly better, so a live run does not reshuffle with every new card.
      const fill = (R) => { const p = plan(R, false); return Math.min((S.vw - 2 * CAM.side) / p.w, (S.vh - CAM.top - CAM.bottom) / Math.max(p.h, 1)); };
      let best = rows || 6, score = rows ? fill(rows) * 1.12 : 0;
      for (let R = 4; R <= 12; R += 1) { const f = fill(R); if (f > score * 1.001) { best = R; score = f; } }
      rows = best;
      const p = plan(rows, true);
      if (p.w !== W || p.h !== H) { world.style.width = `${p.w}px`; world.style.height = `${p.h}px`; edgeLayer.setAttribute("width", p.w); edgeLayer.setAttribute("height", p.h); }
      // lane titles stand in screen space above the world (always 11 px, whatever the zoom) and follow the camera
      while (heads.childNodes.length > lanes.length) heads.removeChild(heads.lastChild);
      lanes.forEach((lane, i) => { const h = heads.childNodes[i] || el("span", "cps-head", null, heads); if (h.textContent !== lane.title) h.textContent = lane.title; lane.head = h; });
      cols = p.cols; W = p.w; H = p.h;
      stage.setAttribute("aria-label", lanes.map((l) => l.title).filter(Boolean).join(", "));
      return routeAll();
    }

    // ---------- edges: from the side of one card to the side of the other, between the cards, never across them ----------
    // An edge that has to pass other columns runs in a free horizontal channel (a gap between rows that is open in
    // every column it crosses), so lines stay readable instead of disappearing behind cards.
    function channel(crossed, ya, yb) {
      const cands = [yb, ya, -GAP.row, H + GAP.row];
      crossed.forEach((c) => c.items.forEach((r) => cands.push(r.y - GAP.row / 2, r.y + r.h + GAP.row / 2)));
      let best = -GAP.row, cost = Infinity;
      for (const y of cands) {
        if (!crossed.every((c) => c.items.every((r) => y < r.y - 3 || y > r.y + r.h + 3))) continue;
        const k = Math.abs(y - yb) + 0.4 * Math.abs(y - ya);
        if (k < cost) { cost = k; best = y; }
      }
      return best;
    }
    const bend = (p, q) => `C${(p[0] + q[0]) / 2},${p[1]} ${(p[0] + q[0]) / 2},${q[1]} ${q[0]},${q[1]}`;
    function route(a, b, kind, da, db) {
      if (a.col === b.col) {
        const down = b.y > a.y, top = down ? a : b, bot = down ? b : a;
        if (!cols[a.col].items.some((r) => r.y > top.y && r.y < bot.y)) {   // neighbours: a straight piece of path
          const x = top.x + (kind === "leads" ? 22 : top.w / 2), y0 = down ? a.y + a.h : a.y, y1 = down ? b.y : b.y + b.h;
          return { d: `M${x},${y0} L${x},${y1}`, end: [x, y1] };
        }
        const y0 = a.y + a.h / 2, y1 = b.y + b.h / 2;
        return { d: `M${a.x},${y0} C${a.x - 34},${y0} ${b.x - 34},${y1} ${b.x},${y1}`, end: [b.x, y1] };
      }
      const fwd = b.col > a.col;
      const p0 = [fwd ? a.x + a.w : a.x, a.y + a.h / 2 + da], p3 = [fwd ? b.x : b.x + b.w, b.y + b.h / 2 + db];
      const crossed = cols.slice(Math.min(a.col, b.col) + 1, Math.max(a.col, b.col));
      if (!crossed.length) return { d: `M${p0[0]},${p0[1]} ${bend(p0, p3)}`, end: p3 };
      const cy = channel(crossed, p0[1], p3[1]), near = fwd ? crossed[0] : crossed[crossed.length - 1], far = fwd ? crossed[crossed.length - 1] : crossed[0];
      const p1 = [fwd ? near.x : near.x + near.w, cy], p2 = [fwd ? far.x + far.w : far.x, cy];
      return { d: `M${p0[0]},${p0[1]} ${bend(p0, p1)} L${p2[0]},${p2[1]} ${bend(p2, p3)}`, end: p3 };
    }
    function routeAll() {
      // Edges that share a side of a card leave it next to each other, in the order of where they go: a fan of
      // lines that never cross at the card, instead of a knot in one point.
      const sides = new Map(), off = new Map();
      edges.forEach((e) => {
        const a = nodes.get(e.from), b = nodes.get(e.to);
        if (a.col === b.col) return;
        const crossed = cols.slice(Math.min(a.col, b.col) + 1, Math.max(a.col, b.col));
        const via = crossed.length ? channel(crossed, a.y + a.h / 2, b.y + b.h / 2) : null;   // where the line goes first
        const put = (r, other, end) => { const k = `${r.id}|${other.col > r.col}`; if (!sides.has(k)) sides.set(k, []); sides.get(k).push({ key: e.key + end, y: via === null ? other.y + other.h / 2 : via, h: r.h }); };
        put(a, b, "a"); put(b, a, "b");
      });
      sides.forEach((list) => {
        const gap = Math.min(7, list[0].h * 0.56 / Math.max(list.length - 1, 1));
        list.sort((p, q) => p.y - q.y).forEach((p, i) => off.set(p.key, (i - (list.length - 1) / 2) * gap));
      });
      const changed = []; let moved = 0;
      edges.forEach((e) => {
        const r = route(nodes.get(e.from), nodes.get(e.to), e.kind, off.get(e.key + "a") || 0, off.get(e.key + "b") || 0);
        if (r.d === e.d) return;
        if (e.d) moved += 1;
        e.d = r.d;
        e.path.setAttribute("d", r.d);
        e.dot.setAttribute("cx", r.end[0]); e.dot.setAttribute("cy", r.end[1]);
        changed.push(e);
      });
      const quiet = clamp(8 / Math.max(edges.size, 1), 0.1, 0.3).toFixed(2);   // many lines: each one lighter
      if (quiet !== S.quiet) { S.quiet = quiet; edgeLayer.style.setProperty("--cps-quiet", quiet); }
      // lengths are read once, after all paths are written: an edge is drawn by letting its dash offset run out
      for (const e of changed) {
        const len = Math.ceil(e.path.getTotalLength()) + 1;
        e.g.style.setProperty("--cps-len", String(len));
        // a dashed edge is drawn the same way: its dashes, then one gap as long as the whole line
        if (e.kind === "learned") e.path.style.strokeDasharray = `${"5 6 ".repeat(Math.ceil(len / 11))}0 ${len}`;
      }
      return moved;   // edges that had a place before and have another now
    }

    // ---------- the state of the picture at a beat ----------
    // The entrance of a beat in order: its edges one after the other; what an edge leads to arrives as the line does.
    function choreography(i, beat) {
      const n = new Map(), e = new Map(); let j = 0, k = 0;
      const enters = (id) => nodes.has(id) && nodes.get(id).at === i;
      for (const p of beat.edges || []) {
        const ed = p && edges.get(`${p[0]}>${p[1]}`);
        if (!ed || ed.at !== i) continue;
        const ms = (enters(ed.from) ? 320 : 0) + 80 * k++;
        e.set(ed.key, ms);
        if (enters(ed.to) && !n.has(ed.to)) n.set(ed.to, { ms: ms + 340, from: nodes.get(ed.from) });
      }
      for (const id of beat.reveal || []) if (enters(id) && !n.has(id)) n.set(id, { ms: 90 * j++, from: null });
      return { n, e };
    }
    // mode "play": the beat enters with its choreography; "jump": the picture simply is as it was at that beat;
    // "keep": a live update or the end, running entrances are left alone. S.rest: the story is over and shown whole,
    // so no node is the subject any more and all of them carry their full weight.
    function render(i, mode) {
      const beat = M.beats[i] || {}, act = new Set(S.rest ? [] : (beat.focus || []).concat(beat.reveal || []));
      const actEdges = new Set(S.rest ? [] : (beat.edges || []).filter(Boolean).map((p) => `${p[0]}>${p[1]}`));
      const apply = () => {
        const order = mode === "play" ? choreography(i, beat) : null;
        nodes.forEach((r) => {
          const shown = r.at <= i, cl = r.el.classList;
          cl.toggle("cps-on", shown);
          cl.toggle("cps-act", shown && act.has(r.id));
          if (mode === "keep") return;
          const step = order && order.n.get(r.id);
          cl.toggle("cps-enter", Boolean(step));
          if (!step) return;
          // a card rises from the direction of what it rests on (a fact out of its file, a decision out of the letter)
          const f = step.from, dx = f ? f.x + f.w / 2 - r.x - r.w / 2 : 0, dy = f ? f.y + f.h / 2 - r.y - r.h / 2 : 16, far = Math.hypot(dx, dy) || 1;
          r.el.style.setProperty("--cps-d", `${step.ms}ms`);
          r.el.style.setProperty("--cps-fx", `${Math.round(dx / far * (f ? 30 : 16))}px`);
          r.el.style.setProperty("--cps-fy", `${Math.round(dy / far * (f ? 30 : 16))}px`);
        });
        edges.forEach((e) => {
          const shown = e.at <= i, ms = order ? order.e.get(e.key) || 0 : 0;
          if (mode !== "keep" && ms !== e.ms) { e.ms = ms; e.g.style.setProperty("--cps-d", `${ms}ms`); }
          e.g.classList.toggle("cps-on", shown);
          e.g.classList.toggle("cps-act", shown && actEdges.has(e.key));
        });
        const refs = new Map();
        edges.forEach((e) => { if (e.label && e.at <= i) refs.set(e.to, (refs.has(e.to) ? `${refs.get(e.to)} · ` : "") + e.label); });
        nodes.forEach((r) => { const t = refs.get(r.id) || ""; if (r.P.ref.textContent !== t) r.P.ref.textContent = t; });
        world.classList.toggle("cps-has-act", act.size > 0);
      };
      if (mode === "jump") still(apply); else apply();
    }
    // Change state without any of it animating (a seek, reduced motion): switch transitions off, apply, let the
    // browser take it in once, switch them on again. The camera is not part of this; it may still travel.
    function still(fn) {
      root.classList.add("cps-still");
      fn();
      if (!reduced) { void root.offsetWidth; root.classList.remove("cps-still"); }
    }

    // ---------- caption and timeline ----------
    function showCaption(i) {
      const b = M.beats[i] || {}, c = b.caption || {}, text = [i, b.agent, c.what, c.why].join("\n");
      if (text === S.capText) return;
      S.capText = text;
      const old = capLayers[S.capLayer], now = capLayers[S.capLayer = 1 - S.capLayer];
      now.agent.textContent = b.agent ? String(b.agent).replace(/_/g, " ") : "";
      now.what.textContent = c.what || "";
      now.why.textContent = c.why || "";
      now.what.title = c.what || ""; now.why.title = c.why || "";
      old.el.classList.remove("cps-show"); old.el.setAttribute("aria-hidden", "true");
      now.el.classList.add("cps-show"); now.el.removeAttribute("aria-hidden");
    }
    function buildTimeline() {
      const n = M.beats.length;
      while (tickBox.childNodes.length > n) tickBox.removeChild(tickBox.lastChild);
      while (tickBox.childNodes.length < n) el("i", "cps-tick-mark", null, tickBox);
      timeline.style.setProperty("--cps-n", String(Math.max(n, 1)));
      timeline.classList.toggle("cps-dense", n > 48);
      timeline.setAttribute("aria-valuemin", "1"); timeline.setAttribute("aria-valuemax", String(Math.max(n, 1)));
      bar.hidden = caption.hidden = n === 0;
    }
    function showControls() {
      const i = S.index, n = M.beats.length, L = M.labels, c = (M.beats[i] || {}).caption || {};
      for (let k = 0; k < tickBox.childNodes.length; k += 1) {
        const cl = tickBox.childNodes[k].classList;
        cl.toggle("cps-past", k < i); cl.toggle("cps-now", k === i);
      }
      fill.style.transform = `scaleX(${n > 1 ? clamp(i, 0, n - 1) / (n - 1) : 0})`;
      count.textContent = i >= 0 ? `${L.step} ${i + 1} ${L.of} ${n}` : "";
      timeline.setAttribute("aria-valuenow", String(i + 1));
      timeline.setAttribute("aria-valuetext", `${L.step} ${i + 1} ${L.of} ${n}${c.what ? `: ${c.what}` : ""}`);
      timeline.setAttribute("aria-label", L.step);
      const mode = S.playing ? "pause" : !M.live && i >= n - 1 ? "replay" : "play";
      if (playBtn.dataset.mode !== mode) { playBtn.dataset.mode = mode; playIcon.setAttribute("d", ICON[mode]); }
      playBtn.setAttribute("aria-label", L[mode]); playBtn.title = L[mode];
      wholeText.textContent = L.whole;
      if (closeBtn) { closeBtn.setAttribute("aria-label", L.close); closeBtn.title = L.close; }
      root.classList.toggle("cps-live", M.live);
      root.classList.toggle("cps-tail", i === n - 1);
    }

    // ---------- camera ----------
    function setCam(c, instant) {
      const next = { x: Math.round(c.x), y: Math.round(c.y), s: c.s }, same = S.cam.set && next.x === S.cam.x && next.y === S.cam.y && next.s === S.cam.s;
      S.cam = Object.assign(next, { set: true });
      if (instant) stage.classList.add("cps-grab");
      if (!same) world.style.transform = `translate(${next.x}px,${next.y}px) scale(${next.s})`;
      // titles move with the camera's own x and scale under the same transition, so they stay above their lane
      // (a lane that reaches out of the frame on the left keeps its title at the frame's edge while it is in view)
      for (const lane of lanes) {
        const left = next.x + lane.x * next.s, t = `translateX(${Math.round(Math.min(Math.max(left, 26), Math.max(left, left + lane.w * next.s - 110)))}px)`;
        if (lane.head.style.transform !== t) lane.head.style.transform = t;
      }
      if (instant) { void stage.offsetWidth; stage.classList.remove("cps-grab"); }
    }
    function fit(box, lo, hi) {
      const aw = S.vw - 2 * CAM.side, ah = S.vh - CAM.top - CAM.bottom;
      const raw = Math.min(aw / box.w, ah / box.h), s = clamp(raw, lo, hi);
      return { s, raw, x: CAM.side + (aw - box.w * s) / 2 - box.x * s, y: CAM.top + (ah - box.h * s) / 2 - box.y * s };
    }
    function boxOf(ids, pad) {
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (const id of ids) { const r = nodes.get(id); if (!r) continue; x0 = Math.min(x0, r.x); y0 = Math.min(y0, r.y); x1 = Math.max(x1, r.x + r.w); y1 = Math.max(y1, r.y + r.h); }
      return x1 < x0 ? null : { x: x0 - pad, y: y0 - pad, w: x1 - x0 + 2 * pad, h: y1 - y0 + 2 * pad };
    }
    const wholeCam = () => fit({ x: 0, y: 0, w: Math.max(W, 1), h: Math.max(H, 1) }, CAM.whole, 1);
    // A beat is framed with what it rests on (the file a fact was found in) when both fit at a readable size;
    // otherwise its own nodes are the subject.
    function beatCam(i) {
      const b = M.beats[i] || {}, ids = (b.focus || []).concat(b.reveal || []);
      const core = boxOf(ids, 0);
      if (!core) return null;
      const all = ids.concat(...(b.edges || []).filter(Boolean)), wide = fit(boxOf(all, 44), CAM.min, CAM.beat);
      const c = wide.raw >= CAM.min ? wide : fit(boxOf(ids, 44), CAM.min, CAM.beat);
      c.subject = wide.raw >= CAM.min ? boxOf(all, 0) : core;
      return c;
    }
    function toBeat(i, instant) {
      const c = beatCam(i);
      if (!c) return;
      S.view = "beat";
      // stay calm: if the subject is already well inside the frame at about the right size, the camera does not move
      const k = S.cam, m = 30, b = c.subject;
      const inside = b.x * k.s + k.x >= m && b.y * k.s + k.y >= CAM.top + 8 && (b.x + b.w) * k.s + k.x <= S.vw - m && (b.y + b.h) * k.s + k.y <= S.vh - m;
      if (!instant && inside && k.s >= c.s * 0.82 && k.s <= c.s * 1.2) return;
      setCam(c, instant);
    }
    function toWhole(instant) { S.view = "whole"; setCam(wholeCam(), instant); }
    // the reader's own zoom, about a point of the stage: never past the caps, never smaller than the whole picture needs
    function zoomed(k, px, py, factor) {
      const s = clamp(k.s * factor, Math.min(CAM.min, wholeCam().s), CAM.max);
      return { s, x: px - (px - k.x) * s / k.s, y: py - (py - k.y) * s / k.s };
    }
    function zoomAt(px, py, factor) { S.view = "free"; setCam(zoomed(S.cam, px, py, factor), true); }

    // ---------- playing ----------
    function dwell(i) {
      if (i < 0) return 650;
      let ms = 1650, fresh = 0;
      for (const id of (M.beats[i] || {}).reveal || []) { const r = nodes.get(id); if (r && r.at === i) { fresh += 1; if (r.kind === "letter") ms += 420 + 130 * r.P.lines.childNodes.length; } }
      ms += 90 * clamp(fresh - 1, 0, 8);
      // a live run that is ahead of the picture is caught up with at a brisker pace, but never skipped
      return M.live && last() - i > 2 ? Math.round(ms * 0.6) : ms;
    }
    function goTo(i, mode, rest) {
      S.index = clamp(i, -1, last());
      S.rest = Boolean(rest);
      render(S.index, reduced && mode === "play" ? "jump" : mode);
      showCaption(S.index);
      showControls();
      remember();
    }
    function remember() {
      if (M.live) return;
      memory.delete(signature(M));
      memory.set(signature(M), { index: S.index, playing: S.playing, rest: S.rest });
      if (memory.size > 100) memory.delete(memory.keys().next().value);
    }
    function queue(ms) { clearTimeout(S.timer); S.timer = setTimeout(advance, ms); }
    function advance() {
      S.timer = 0;
      if (!S.playing || dead) return;
      if (S.index < last()) { goTo(S.index + 1, "play"); toBeat(S.index, reduced); queue(dwell(S.index)); }
      else if (!M.live) { S.playing = false; S.rest = true; render(S.index, "keep"); toWhole(reduced); showControls(); remember(); }   // the end: the whole picture, complete
      // live and nothing new yet: wait; update() calls on
    }
    function play() {
      if (dead || !M.beats.length) return;
      if (!M.live && S.index >= last()) { goTo(-1, "jump"); toWhole(reduced); }   // «again»: from the empty picture
      S.playing = true;
      showControls(); remember();
      queue(S.index < 0 ? 700 : 260);
    }
    function pause() { S.playing = false; clearTimeout(S.timer); S.timer = 0; showControls(); remember(); }
    function seek(i) {
      if (dead || !M.beats.length) return;
      i = clamp(Math.round(i), 0, last());
      S.playing = false; clearTimeout(S.timer); S.timer = 0;
      if (i === S.index && !S.rest) { toBeat(i, reduced); showControls(); return; }
      goTo(i, i === S.index + 1 ? "play" : "jump");   // one step forward plays; anywhere else simply shows that moment
      toBeat(i, reduced);
    }
    function whole() { if (!dead) toWhole(reduced); }

    function begin() {
      sync();
      S.vw = stage.clientWidth || 1000; S.vh = stage.clientHeight || opt.height;
      still(layout);
      buildTimeline();
      const seen = M.live ? null : memory.get(signature(M));
      if (M.live) {   // the agent is working: everything so far is there, the camera is where the work is
        goTo(last(), "jump"); S.playing = true;
        if (beatCam(S.index)) toBeat(S.index, true); else toWhole(true);
      } else if (opt.start === "last" || !M.beats.length) {
        goTo(last(), "jump", true); toWhole(true);
      } else if (seen) {   // the same story mounted again: it stands where it stood; if it was playing it plays on
        goTo(seen.index, "jump", seen.rest); toWhole(true);
        if (!seen.rest && seen.index >= 0) toBeat(seen.index, true);
        if (seen.playing && opt.autoplay && seen.index < last()) play();
      } else if (opt.autoplay) { goTo(-1, "jump"); toWhole(true); play(); }
      else { goTo(0, "jump"); toWhole(true); toBeat(0, true); }
      showControls();
    }
    function update(raw) {
      if (dead) return;
      const next = readModel(raw), ids = new Set(next.nodes.map((n) => n.id));
      let same = next.beats.length >= M.beats.length;
      nodes.forEach((r) => { if (!ids.has(r.id)) same = false; });
      if (!same) {   // another story: start over, shown complete
        clearTimeout(S.timer); S.timer = 0; S.playing = false; S.capText = ""; rows = 0;
        nodes.forEach((r) => r.el.remove()); edges.forEach((e) => e.g.remove());
        nodes.clear(); edges.clear();
        M = next; opt.start = "last"; opt.autoplay = false;
        begin();
        return;
      }
      const atTail = S.index === last(), wasLive = M.live;
      M = next;
      sync();
      // when cards had to move for new ones, the lines are taken away for the moment of the move and fade back in
      if (layout()) { edgeLayer.classList.add("cps-settle"); void edgeLayer.getBoundingClientRect(); edgeLayer.classList.remove("cps-settle"); }
      buildTimeline();
      render(S.index, "keep");
      showControls();
      if (S.view === "whole") toWhole(reduced); else if (S.view === "beat") toBeat(S.index, reduced);
      // new beats are played one after the other from where the picture stands; nothing else is touched
      if (S.playing && !S.timer && (S.index < last() || (wasLive && !M.live && atTail))) queue(S.index < last() ? 220 : dwell(S.index));
    }
    // ---------- interaction ----------
    const recOf = (target) => { const b = target && target.closest ? target.closest(".cps-node") : null; return (b && byEl.get(b)) || null; };
    // relationships on demand: a node's own edges and their other ends come forward, the rest steps back
    function relate(rec) {
      for (const m of S.marked) m.classList.remove("cps-rel");
      S.marked = [];
      world.classList.toggle("cps-hov", Boolean(rec));
      if (!rec) return;
      const mark = (e) => { e.classList.add("cps-rel"); S.marked.push(e); };
      mark(rec.el);
      edges.forEach((e) => { if ((e.from === rec.id || e.to === rec.id) && e.g.classList.contains("cps-on")) { mark(e.g); mark(nodes.get(e.from === rec.id ? e.to : e.from).el); } });
    }
    world.addEventListener("pointerover", (e) => { if (!drag.moved) relate(recOf(e.target)); }, on);
    world.addEventListener("pointerout", (e) => { if (!recOf(e.relatedTarget)) relate(null); }, on);
    world.addEventListener("focusin", (e) => {
      const r = recOf(e.target);
      relate(r);
      if (!r || !r.el.matches(":focus-visible")) return;
      // a node reached by keyboard outside the frame: the camera goes to it
      const k = S.cam, out = r.x * k.s + k.x < 0 || r.y * k.s + k.y < CAM.top - 10 || (r.x + r.w) * k.s + k.x > S.vw || (r.y + r.h) * k.s + k.y > S.vh;
      if (out) { S.view = "free"; setCam(fit(boxOf([r.id], 120), Math.max(k.s, CAM.min), Math.max(k.s, CAM.min)), reduced); }
    }, on);
    world.addEventListener("focusout", () => relate(null), on);
    stage.addEventListener("scroll", () => { stage.scrollLeft = 0; stage.scrollTop = 0; }, on);   // focus must not scroll the viewport
    world.addEventListener("click", (e) => {
      const r = recOf(e.target);
      if (r && !drag.moved && typeof opt.onOpen === "function") opt.onOpen(r.n);
    }, on);

    // drag pans, two fingers pinch; the pointer is only captured once it really moves, so a press stays a press
    const drag = { pts: new Map(), moved: false, raf: 0, next: null, span: 0 };
    const flush = () => { drag.raf = 0; if (drag.next) { setCam(drag.next); drag.next = null; } };   // .cps-drag already holds the transitions off
    stage.addEventListener("pointerdown", (e) => {
      if (e.button) return;
      if (!drag.pts.size) drag.moved = false;
      drag.pts.set(e.pointerId, { x: e.clientX, y: e.clientY, x0: e.clientX, y0: e.clientY });
      drag.span = 0;
    }, on);
    stage.addEventListener("pointermove", (e) => {
      const p = drag.pts.get(e.pointerId);
      if (!p) return;
      const dx = e.clientX - p.x, dy = e.clientY - p.y;
      if (!drag.moved && Math.hypot(e.clientX - p.x0, e.clientY - p.y0) < 5) return;
      if (!drag.moved) { drag.moved = true; relate(null); stage.classList.add("cps-drag"); for (const id of drag.pts.keys()) try { stage.setPointerCapture(id); } catch (err) { /* pointer already gone */ } }
      p.x = e.clientX; p.y = e.clientY;
      const k = drag.next || S.cam;
      if (drag.pts.size === 2) {
        const [a, b] = [...drag.pts.values()], span = Math.hypot(a.x - b.x, a.y - b.y), box = stage.getBoundingClientRect();
        if (drag.span) drag.next = zoomed(k, (a.x + b.x) / 2 - box.left, (a.y + b.y) / 2 - box.top, span / drag.span);
        drag.span = span;
      } else {
        // the world can be pushed around but not out of sight
        drag.next = { s: k.s, x: clamp(k.x + dx, 80 - W * k.s, S.vw - 80), y: clamp(k.y + dy, 80 - H * k.s, S.vh - 80) };
      }
      S.view = "free";
      if (!drag.raf) drag.raf = requestAnimationFrame(flush);
    }, on);
    const release = (e) => {
      drag.pts.delete(e.pointerId); drag.span = 0;
      if (drag.pts.size) return;
      if (drag.next) flush();
      stage.classList.remove("cps-drag");
      setTimeout(() => { drag.moved = false; }, 0);   // after the click this release may still send
    };
    stage.addEventListener("pointerup", release, on);
    stage.addEventListener("pointercancel", release, on);
    // a plain wheel belongs to the page; with Ctrl/⌘ (which is also what a trackpad pinch sends) it zooms the picture
    stage.addEventListener("wheel", (e) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const box = stage.getBoundingClientRect();
      zoomAt(e.clientX - box.left, e.clientY - box.top, Math.exp(-clamp(e.deltaY, -60, 60) * 0.012));
    }, { signal: abort.signal, passive: false });
    let pinch = 1;   // Safari reports a trackpad pinch as gesture events
    stage.addEventListener("gesturestart", (e) => { e.preventDefault(); pinch = 1; }, on);
    stage.addEventListener("gesturechange", (e) => { e.preventDefault(); const box = stage.getBoundingClientRect(); zoomAt(e.clientX - box.left, e.clientY - box.top, e.scale / pinch); pinch = e.scale; }, on);
    stage.addEventListener("dblclick", (e) => { if (!recOf(e.target)) toWhole(reduced); }, on);

    playBtn.addEventListener("click", () => (S.playing ? pause() : play()), on);
    wholeBtn.addEventListener("click", whole, on);
    // the timeline: press a tick, or drag along it; every position shows the picture as it was then
    let scrub = null;
    const pick = (e) => clamp(Math.floor((e.clientX - scrub.left) / scrub.width * M.beats.length), 0, last());
    timeline.addEventListener("pointerdown", (e) => { if (e.button || !M.beats.length) return; scrub = timeline.getBoundingClientRect(); try { timeline.setPointerCapture(e.pointerId); } catch (err) { /* no capture, the press still seeks */ } seek(pick(e)); }, on);
    timeline.addEventListener("pointermove", (e) => { if (scrub) { const i = pick(e); if (i !== S.index) seek(i); } }, on);
    timeline.addEventListener("pointerup", () => { scrub = null; }, on);
    timeline.addEventListener("pointercancel", () => { scrub = null; }, on);
    root.addEventListener("keydown", (e) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const onButton = e.target.closest && e.target.closest("button");
      if ((e.key === " " || e.key === "Spacebar") && !onButton) { S.playing ? pause() : play(); }
      else if (e.key === "ArrowRight") seek(S.index + 1);
      else if (e.key === "ArrowLeft") seek(S.index - 1);
      else if (e.key === "Home") seek(0);
      else if (e.key === "End") seek(last());
      else if (e.key === "Escape" && closeBtn) opt.onClose();
      else return;
      e.preventDefault();
    }, on);

    const setReduced = () => { reduced = motion.matches; root.classList.toggle("cps-still", reduced); root.classList.toggle("cps-reduced", reduced); };
    motion.addEventListener("change", setReduced, on);
    setReduced();
    // the viewport changed: the same subject is framed again, at once
    const resize = new ResizeObserver(() => {
      const w = stage.clientWidth, h = stage.clientHeight;
      if (!w || !h || (w === S.vw && h === S.vh)) return;
      S.vw = w; S.vh = h;
      if (S.view === "whole") toWhole(true); else if (S.view === "beat" && beatCam(S.index)) setCam(beatCam(S.index), true);
    });
    resize.observe(stage);

    function destroy() {
      if (dead) return;
      dead = true;
      clearTimeout(S.timer);
      cancelAnimationFrame(drag.raf);
      abort.abort();
      resize.disconnect();
      root.remove();
      if (mounted.get(host) === api) mounted.delete(host);
    }
    const api = { update, play, pause, seek, whole, destroy };
    mounted.set(host, api);
    begin();
    return api;
  }

  window.CasePathStory = { mount };
})();
