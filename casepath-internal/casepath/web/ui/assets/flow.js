"use strict";
/*
 * CasePath process-flow canvas: the process of a case as blocks (steps) with their named ways out, and the case on it.
 *
 *   const flow = CasePathFlow.mount(element, model, options);
 *   flow.update(model); flow.whole(); flow.here(); flow.resize(height, large); flow.highlight(blockId | null); flow.destroy();
 *
 * The stage is a view onto one world (blocks as HTML, all connectors in one SVG underneath) with a camera (translate +
 * scale), and under it a slim foot of its own for the key to the tones and the camera controls.
 * Layout: columns by the longest way from the first block; a block's band sits at the height of the port that leads to
 * it, so the usual way in is a straight line. Connectors run orthogonally in the gutters between columns: every target
 * has one lane (its trunk), so ways to the same block merge before they enter it.
 */
(function () {
  const SVG_NS = "http://www.w3.org/2000/svg";
  // World metrics at scale 1, in px. BAND_Y and PORT_Y are the mid heights CSS gives the band and a row's first line;
  // PORT_OUT is how far a port's tab reaches beyond the block's edge, STUB where the end pills start.
  const W = 300, BAND_Y = 17, PORT_Y = 19, PORT_OUT = 10, GAP = 48, LANE = 14, STUB = 36, PILL_H = 26, GRID = 24, CORNER = 9;
  const PAD = 20, REST_MIN = 0.86, REST_ALL = 0.92, ZOOM_MAX = 1.5, STEP = 450;
  const WORDS = { whole: "Whole process", here: "Where the case stands", big: "Enlarge", small: "Back to the page",
    done: "done", now: "now", open: "ahead", taken: "the way the case took" };
  // The few glyphs, drawn here: 16 px box, stroked with the current colour unless CSS says otherwise.
  const GLYPHS = {
    tick: ["path", { d: "M3.6 8.4l2.9 2.9 5.9-6.4" }],
    dot: ["circle", { cx: 8, cy: 8, r: 3.5 }],
    ring: ["circle", { cx: 8, cy: 8, r: 4.25 }],
    miss: ["circle", { cx: 8, cy: 8, r: 4.25 }],
    way: ["path", { d: "M3.5 8h8.5M8.8 4.8L12 8l-3.2 3.2" }],
    line: ["path", { d: "M1.5 8h13" }],
    flag: ["path", { d: "M4.5 13.6V2.9M4.5 3.4h7l-1.7 2.5 1.7 2.5h-7" }],
    expand: ["path", { d: "M9.5 2.8h3.7v3.7M13.2 2.8L9 7M6.5 13.2H2.8V9.5M2.8 13.2L7 9" }],
    shrink: ["path", { d: "M13.2 6.5H9.5V2.8M9.5 6.5l3.9-3.9M2.8 9.5h3.7v3.7M6.5 9.5l-3.9 3.9" }]
  };

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;   // every text of the model enters as text
    return n;
  }
  function svg(tag, attrs) {
    const n = document.createElementNS(SVG_NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    return n;
  }
  function glyph(name) {
    const g = svg("svg", { class: "cpf-g cpf-g-" + name, viewBox: "0 0 16 16", "aria-hidden": "true" });
    g.appendChild(svg(GLYPHS[name][0], GLYPHS[name][1]));
    return g;
  }
  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
  const snap = (v) => Math.ceil(v / GRID) * GRID;

  // An orthogonal polyline as a path with rounded corners (points that add nothing are dropped first).
  function rounded(points) {
    const p = [];
    points.forEach((q) => {
      const a = p[p.length - 2], b = p[p.length - 1];
      if (b && b[0] === q[0] && b[1] === q[1]) return;
      if (a && ((a[0] === b[0] && b[0] === q[0]) || (a[1] === b[1] && b[1] === q[1]))) p.pop();
      p.push(q);
    });
    let d = "M" + p[0][0] + " " + p[0][1];
    for (let i = 1; i < p.length - 1; i++) {
      const a = p[i - 1], b = p[i], c = p[i + 1];
      const la = Math.abs(b[0] - a[0]) + Math.abs(b[1] - a[1]), lc = Math.abs(c[0] - b[0]) + Math.abs(c[1] - b[1]);
      const r = Math.min(CORNER, la / 2, lc / 2);
      const ux = (b[0] - a[0]) / la, uy = (b[1] - a[1]) / la, vx = (c[0] - b[0]) / lc, vy = (c[1] - b[1]) / lc;
      d += "L" + (b[0] - ux * r) + " " + (b[1] - uy * r) + "A" + r + " " + r + " 0 0 " + (ux * vy - uy * vx > 0 ? 1 : 0) +
        " " + (b[0] + vx * r) + " " + (b[1] + vy * r);
    }
    return d + "L" + p[p.length - 1][0] + " " + p[p.length - 1][1];
  }

  // Stack one column: every block wants its own y, neighbours keep GAP apart. With `spread` a group that collides is
  // centred on what its members want (two targets of one fork sit above and below it); otherwise the later is pushed down.
  function stack(list, spread) {
    const groups = [];
    list.forEach((b) => {
      let g = { items: [b], y: b.want, h: b.h };
      while (groups.length && groups[groups.length - 1].y + groups[groups.length - 1].h + GAP > g.y) {
        const before = groups.pop(), items = before.items.concat(g.items);
        let off = 0, sum = 0;
        items.forEach((it) => { sum += it.want - off; off += it.h + GAP; });
        g = { items: items, y: spread ? sum / items.length : before.y, h: off - GAP };
      }
      groups.push(g);
    });
    groups.forEach((g) => { let y = Math.round(g.y); g.items.forEach((it) => { it.y = y; y += it.h + GAP; }); });
  }

  // The order of the lanes of one gutter with the fewest crossings. A lane is a vertical run from lo to hi; lines
  // reach it from the left at the heights `left` and leave it to the right at the heights `right`.
  function orderLanes(lanes) {
    if (lanes.length < 2 || lanes.length > 6) return lanes;
    const within = (ys, lane) => ys.filter((y) => y > lane.lo + 1 && y < lane.hi - 1).length;
    const cost = (order) => {
      let n = 0;
      for (let i = 0; i < order.length; i++) for (let j = i + 1; j < order.length; j++) n += within(order[j].left, order[i]) + within(order[i].right, order[j]);
      return n;
    };
    let best = lanes, least = cost(lanes);
    const permute = (head, rest) => {
      if (!rest.length) { const c = cost(head); if (c < least) { least = c; best = head; } return; }
      rest.forEach((x, i) => permute(head.concat([x]), rest.slice(0, i).concat(rest.slice(i + 1))));
    };
    if (least) permute([], lanes);
    return best;
  }

  // What the model says about the ways: every outcome with a port (to a block, or to an end pill), which of them are
  // back-links, and the column of every block (the longest way from a first block, back-links left out).
  function analyse(model) {
    const ids = new Set(model.blocks.map((b) => b.id)), ways = [], next = {}, col = {};
    model.blocks.forEach((b) => { next[b.id] = []; col[b.id] = 0; });
    model.blocks.forEach((b) => (b.rows || []).forEach((r) => {
      const tone = r.state === "taken" ? "taken" : r.state === "possible" && (b.id === model.now || b.tone === "now") ? "possible" : "pale";
      const way = { key: b.id + "|" + r.id, from: b.id, row: r.id, tone: tone };
      if (r.to != null && ids.has(r.to)) { way.to = r.to; next[b.id].push(r.to); }
      else if (r.end) way.end = r.end;
      else return;
      ways.push(way);
    }));
    // a back-link closes a loop and leads to a block the model names earlier; without them the rest has no loops
    const index = {}, below = {};
    const down = (id, seen) => { next[id].forEach((to) => { if (!seen.has(to)) { seen.add(to); down(to, seen); } }); return seen; };
    model.blocks.forEach((b, i) => { index[b.id] = i; below[b.id] = down(b.id, new Set()); });
    const back = (w) => below[w.to].has(w.from) && index[w.to] <= index[w.from];
    for (let i = 0; i < model.blocks.length; i++) ways.forEach((w) => {
      if (w.to != null && !back(w)) col[w.to] = Math.max(col[w.to], col[w.from] + 1);
    });
    return { ways: ways, col: col };
  }

  function mount(host, firstModel, options) {
    const opt = Object.assign({ height: 420, autoplay: true }, options);
    const calm = () => !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    let model = firstModel || { blocks: [] };
    const blocks = new Map();         // id -> { id, m, el, rows: Map(rowId -> { m, el, body, port, pill, py, pw }), x, y, h, col }
    let ways = [], col = {}, cols = [], gutters = [], lanes = {}, bounds = null;
    let cam = { x: 0, y: 0, s: 1 }, mode = "here", follow = false, large = false, ready = false, seenW = 0, seenH = 0;
    let hover = null, pinned = null, over = null, walking = false, waiting = false, walkAt = null, dash = null, dead = false, swallow = false;
    const timers = new Set(), anims = new Set(), offs = [], ptrs = new Map();
    const lineOf = new Map();         // way key -> { g, line, arrow }: the drawn connectors, kept across updates

    const on = (target, type, fn, o) => { target.addEventListener(type, fn, o); offs.push(() => target.removeEventListener(type, fn, o)); };
    const later = (fn, ms) => { const t = setTimeout(() => { timers.delete(t); if (!dead) fn(); }, ms); timers.add(t); };
    const word = (k) => (model.labels && model.labels[k]) || WORDS[k];
    const nowId = () => (blocks.has(model.now) ? model.now : (model.path || []).filter((id) => blocks.has(id)).pop() || (model.blocks[0] || {}).id);

    /* ---------- the stage ---------- */
    const stage = el("div", "cpf-stage"), view = el("div", "cpf-view"), world = el("div", "cpf-world"), ground = el("div", "cpf-ground");
    const linesEl = svg("svg", { class: "cpf-lines", "aria-hidden": "true" });
    const foot = el("div", "cpf-foot"), controls = el("div", "cpf-controls"), legend = el("div", "cpf-legend"), ctl = {};
    stage.tabIndex = 0;
    stage.setAttribute("role", "group");
    stage.style.height = opt.height + "px";
    const seg = el("div", "cpf-seg");
    controls.append(seg);
    [["here", "dot"], ["whole", null], ["expand", "expand"]].forEach((c) => {
      if (c[0] === "expand" && typeof opt.onExpand !== "function") return;
      const b = el("button", "cpf-ctl cpf-ctl-" + c[0]);
      b.type = "button";
      b.dataset.act = c[0];
      b.append(c[1] ? glyph(c[1]) : "", el("span"));
      ctl[c[0]] = b;
      (c[0] === "expand" ? controls : seg).append(b);
    });
    world.append(ground, linesEl);
    view.append(world);
    foot.append(legend, controls);     // a place of their own: the world never draws under them
    stage.append(view, foot);
    host.appendChild(stage);

    // The UI words come with the model; they may change with it.
    function words() {
      stage.setAttribute("aria-label", word("whole"));
      ctl.here.lastChild.textContent = word("here");
      ctl.whole.lastChild.textContent = word("whole");
      if (ctl.expand) {
        ctl.expand.replaceChildren(glyph(large ? "shrink" : "expand"));
        ctl.expand.title = word(large ? "small" : "big");
        ctl.expand.setAttribute("aria-label", ctl.expand.title);
      }
      legend.replaceChildren();
      [["now", "dot"], ["done", "tick"], ["open", "ring"], ["taken", "line"]].forEach((k) => {
        const item = el("span", "cpf-key cpf-key-" + k[0]);
        item.append(glyph(k[1]), el("span", "", word(k[0])));
        legend.append(item);
      });
    }

    /* ---------- blocks, rows and pills from the model ---------- */
    function makeBlock(id) {
      const b = { id: id, el: el("div", "cpf-block"), band: el("div", "cpf-band"), mark: el("span", "cpf-bandmark"),
        title: el("span", "cpf-title"), word: el("span", "cpf-word"), rowsEl: el("div", "cpf-rows"), rows: new Map(), x: 0, y: 0, h: 0, placed: false };
      b.el.tabIndex = 0;
      b.el.setAttribute("role", "group");
      b.el.dataset.b = id;
      b.band.append(b.mark, b.title, b.word);
      b.el.append(b.band, b.rowsEl);
      world.appendChild(b.el);
      return b;
    }
    // The tone a block shows. While the path is being walked a block not yet reached shows as «open».
    function setTone(b, tone) {
      if (b.el.dataset.tone === tone) return;
      b.el.dataset.tone = tone;
      b.mark.replaceChildren(glyph(tone === "done" ? "tick" : tone === "now" ? "dot" : tone === "hand" ? "miss" : "ring"));
      b.word.textContent = tone === "now" ? word("now") : "";
    }
    function fillRow(r, fresh) {
      const m = r.m, taken = m.kind === "decision" && m.value;
      const was = fresh ? 0 : r.el.offsetHeight, gone = was && taken ? r.body.querySelector(".cpf-acts") : null;
      const mark = m.kind === "outcome" ? "way" : m.kind === "need" ? "miss" : m.state === "done" || taken ? "tick" : m.state === "now" ? "dot" : "ring";
      const head = el("div", "cpf-head");
      head.append(el("span", "cpf-text", m.text));
      if (m.value) head.append(el("span", "cpf-value", m.value));
      r.body.replaceChildren(glyph(mark), head);
      if (m.sub) r.body.append(el("div", "cpf-sub", m.sub));
      if (!taken && m.actions && m.actions.length) {
        const acts = el("div", "cpf-acts");
        m.actions.forEach((a) => {
          const bt = el("button", "cpf-act" + (a.primary ? " cpf-primary" : ""), a.text);
          bt.type = "button";
          bt.dataset.a = a.id;
          acts.append(bt);
        });
        r.body.append(acts);
      }
      // On an update a row keeps the height it had, so nothing under it moves. A decision just taken: its buttons give
      // way to the value in a short cross-fade and the tick is drawn.
      if (was) r.el.style.minHeight = was + "px";
      if (gone && !calm()) {
        gone.className = "cpf-acts cpf-leave";
        gone.querySelectorAll("button").forEach((bt) => { bt.disabled = true; });
        r.body.append(gone);
        r.el.classList.add("cpf-decided");
        later(() => { gone.remove(); r.el.classList.remove("cpf-decided"); }, 600);
      }
      r.el.dataset.kind = m.kind;
      r.el.dataset.state = taken ? "done" : m.state || "";
      const opens = !!(m.href || m.item);
      r.el.classList.toggle("cpf-opens", opens);
      if (opens) { r.el.tabIndex = 0; r.el.setAttribute("role", "link"); } else { r.el.removeAttribute("tabindex"); r.el.removeAttribute("role"); }
    }
    function sync(fresh) {
      const graph = analyse(model), wayOf = new Map(graph.ways.map((w) => [w.key, w])), live = new Set();
      model.blocks.forEach((m) => {
        live.add(m.id);
        const b = blocks.get(m.id) || makeBlock(m.id);
        blocks.set(m.id, b);
        b.m = m;
        b.col = graph.col[m.id];
        b.title.textContent = m.title;
        b.title.title = m.title;
        b.el.setAttribute("aria-label", m.title + (WORDS[m.tone] ? ", " + word(m.tone) : ""));
        setTone(b, m.tone);
        const kept = new Set();
        let tail = b.el;      // end pills follow their block in the document, so Tab goes block, its rows, its pills, next block
        (m.rows || []).forEach((rm, i) => {
          kept.add(rm.id);
          let r = b.rows.get(rm.id);
          if (!r) {
            r = { el: el("div", "cpf-row" + (fresh ? "" : " cpf-enter")), body: el("div", "cpf-body") };
            r.el.dataset.r = rm.id;
            r.el.append(r.body);
            b.rows.set(rm.id, r);
          }
          const sig = JSON.stringify(rm);
          r.m = rm;
          if (sig !== r.sig) { r.sig = sig; fillRow(r, fresh); }
          if (b.rowsEl.children[i] !== r.el) b.rowsEl.insertBefore(r.el, b.rowsEl.children[i] || null);
          // the port of a way out, and the end pill of a way that closes the case
          const way = wayOf.get(m.id + "|" + rm.id);
          if (way) { way.block = b; way.r = r; r.el.dataset.way = way.tone; } else delete r.el.dataset.way;
          if (way && !r.port) { r.port = el("i", "cpf-port"); r.el.append(r.port); }
          if (!way && r.port) { r.port.remove(); r.port = null; }
          if (way && way.end) {
            if (!r.pill) {
              r.pill = el("button", "cpf-pill");
              r.pill.type = "button";
              r.pill.dataset.b = m.id;
              r.pill.dataset.r = rm.id;
              world.insertBefore(r.pill, tail.nextSibling);
            }
            tail = r.pill;
            r.pill.replaceChildren(glyph("flag"), el("span", "", way.end.text));
            r.pill.dataset.state = way.end.state || "open";
            r.pill.dataset.way = way.tone;
            way.pill = r.pill;
          } else if (r.pill) { r.pill.remove(); r.pill = null; }
        });
        b.rows.forEach((r, id) => { if (!kept.has(id)) { r.el.remove(); if (r.pill) r.pill.remove(); b.rows.delete(id); } });
      });
      blocks.forEach((b, id) => {
        if (live.has(id)) return;
        b.rows.forEach((r) => { if (r.pill) r.pill.remove(); });
        b.el.remove();
        blocks.delete(id);
      });
      ways = graph.ways;
      col = graph.col;
      words();
    }
    // The shape of the process: while it stays the same an update keeps every block where it is.
    const shape = () => model.blocks.map((b) => b.id + ":" + col[b.id]).join() + "/" + ways.map((w) => w.from + ">" + (w.to != null ? w.to : "")).join();

    /* ---------- layout: columns, heights, lanes ---------- */
    function measure() {
      blocks.forEach((b) => {
        b.h = b.el.offsetHeight;
        b.rows.forEach((r) => { r.py = b.el.clientTop + r.el.offsetTop + PORT_Y; r.pw = r.pill ? r.pill.offsetWidth : 0; });
      });
      ready = view.clientWidth > 0 && model.blocks.every((m) => blocks.get(m.id).h > 0);
    }
    function lane(gutter, id) {
      const set = lanes[gutter] || (lanes[gutter] = new Map());
      if (!set.has(id)) set.set(id, { id: id });
      return set.get(id);
    }
    // Where a block wants its band: at the port that leads to it (of one block's several the topmost, so the others
    // come up to it like a comb; of several blocks' the middle). Only the shape of the process decides, not the state
    // of the case: the same process is the same picture every day.
    function wanted(b) {
      const ins = ways.filter((w) => w.to === b.id && col[w.from] < b.col).map((w) => ({ y: w.block.y + w.r.py, from: w.from }));
      if (!ins.length) return 0;
      const one = ins.every((p) => p.from === ins[0].from);
      return Math.round(one ? Math.min.apply(null, ins.map((p) => p.y)) : ins.reduce((sum, p) => sum + p.y, 0) / ins.length) - BAND_Y;
    }
    function layout(anchored) {
      cols = [];
      lanes = {};
      model.blocks.forEach((m, i) => { const b = blocks.get(m.id); b.order = i; (cols[b.col] || (cols[b.col] = [])).push(b); });
      // every target has one trunk lane in the gutter before it; a way that skips columns or runs back also has an exit lane
      ways.forEach((w) => {
        if (w.to == null) return;
        w.trunk = lane(col[w.to] - 1, "to:" + w.to);
        w.exit = col[w.to] === col[w.from] + 1 ? null : lane(col[w.from], "out:" + w.to);
      });
      // x: a gutter holds the end pills of its column in a tidy column, then the lanes, then room for the arrowhead
      let x = 0;
      gutters = [];
      for (let c = 0; c < cols.length; c++) {
        const list = cols[c] || (cols[c] = []), n = lanes[c] ? lanes[c].size : 0;
        let pw = 0;
        list.forEach((b) => { b.x = x; b.rows.forEach((r) => { pw = Math.max(pw, r.pw); }); });
        const pills = pw ? STUB + pw + 44 : 0;      // the lanes run clearly right of the column of pills, never through it
        const width = snap(pw ? pills + (n ? (n - 1) * LANE + 44 : 0) : Math.max(4 * GRID, 72 + (n - 1) * LANE));
        gutters[c] = { pillX: x + W + STUB, x0: pw ? x + W + pills : x + W + (width - (n - 1) * LANE) / 2 };
        x += W + width;
      }
      const n0 = lanes[-1] ? lanes[-1].size : 0;
      gutters[-1] = { x0: -36 - (n0 - 1) * LANE };
      // y: column by column, each block at the height of the port that leads to it
      cols.forEach((list) => {
        list.forEach((b) => { b.want = anchored && b.placed ? b.y : wanted(b); });
        list.sort((a, b) => a.want - b.want || a.order - b.order);
        stack(list, !anchored);
        list.forEach((b) => { b.placed = true; b.el.style.transform = "translate(" + b.x + "px," + b.y + "px)"; });
      });
    }

    /* ---------- connectors ---------- */
    function route() {
      const channel = {}, taken = [];
      const attach = (ln, side, y) => { (ln[side] || (ln[side] = [])).push(y); ln.lo = Math.min(ln.lo == null ? y : ln.lo, y); ln.hi = Math.max(ln.hi == null ? y : ln.hi, y); };
      Object.keys(lanes).forEach((g) => lanes[g].forEach((ln) => { ln.left = []; ln.right = []; ln.lo = ln.hi = null; }));
      ways.forEach((w) => {
        w.px = w.block.x + W + PORT_OUT;
        w.py = w.block.y + w.r.py;
        if (w.to == null) return;
        const t = blocks.get(w.to), cs = col[w.from], ct = col[w.to], forward = ct > cs;
        w.tx = t.x;
        w.ty = t.y + BAND_Y;
        if (!w.exit) { attach(w.trunk, "left", w.py); attach(w.trunk, "right", w.ty); return; }
        // around the columns in between: the free corridor (above, below or between their blocks) nearest to the straight way
        const key = cs + ">" + w.to;
        if (channel[key] == null) {
          const busy = taken.map((y) => [y - LANE + 1, y + LANE - 1]), mid = (w.py + w.ty) / 2;
          for (let c = forward ? cs + 1 : ct; c <= (forward ? ct - 1 : cs); c++) cols[c].forEach((b) => busy.push([b.y - 24, b.y + b.h + 24]));
          let from = -Infinity, best = null, least = Infinity;
          busy.sort((a, b) => a[0] - b[0]).concat([[Infinity, Infinity]]).forEach((iv) => {
            const y = clamp(mid, from, iv[0]), cost = Math.abs(w.py - y) + Math.abs(w.ty - y);
            if (iv[0] >= from && cost < least) { least = cost; best = y; }
            from = Math.max(from, iv[1]);
          });
          taken.push(channel[key] = Math.round(best));
        }
        w.cy = channel[key];
        attach(w.exit, "left", w.py);
        attach(w.exit, forward ? "right" : "left", w.cy);
        attach(w.trunk, forward ? "left" : "right", w.cy);
        attach(w.trunk, "right", w.ty);
      });
      Object.keys(lanes).forEach((g) => orderLanes(Array.from(lanes[g].values())).forEach((ln, i) => { ln.x = gutters[g].x0 + i * LANE; }));

      const box = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
      const grow = (x, y) => { box.x0 = Math.min(box.x0, x); box.x1 = Math.max(box.x1, x); box.y0 = Math.min(box.y0, y); box.y1 = Math.max(box.y1, y); };
      blocks.forEach((b) => { grow(b.x, b.y); grow(b.x + W, b.y + b.h); });
      const live = new Set();
      ways.forEach((w) => {
        let pts;
        if (w.pill) {
          const px = gutters[col[w.from]].pillX;
          pts = [[w.px, w.py], [px, w.py]];
          w.pill.style.transform = "translate(" + px + "px," + (w.py - PILL_H / 2) + "px)";
          grow(px + w.r.pw, w.py);
        } else if (!w.exit) pts = [[w.px, w.py], [w.trunk.x, w.py], [w.trunk.x, w.ty], [w.tx - 6, w.ty]];
        else pts = [[w.px, w.py], [w.exit.x, w.py], [w.exit.x, w.cy], [w.trunk.x, w.cy], [w.trunk.x, w.ty], [w.tx - 6, w.ty]];
        pts.forEach((p) => grow(p[0], p[1]));
        let d = lineOf.get(w.key);
        if (!d) {
          d = { g: svg("g", { class: "cpf-way" }), line: svg("path", { class: "cpf-line" }) };
          d.g.appendChild(d.line);
          lineOf.set(w.key, d);
        }
        if (!w.pill && !d.arrow) d.arrow = d.g.appendChild(svg("path", { class: "cpf-arrow" }));
        if (w.pill && d.arrow) { d.arrow.remove(); d.arrow = null; }
        d.line.setAttribute("d", rounded(pts));
        if (d.arrow) d.arrow.setAttribute("d", "M" + (w.tx - 7.5) + " " + (w.ty - 4) + "L" + (w.tx - 1) + " " + w.ty + "L" + (w.tx - 7.5) + " " + (w.ty + 4) + "Z");
        d.g.dataset.way = w.tone;
        w.g = d.g; w.line = d.line; w.arrow = d.arrow;
        live.add(w.key);
      });
      lineOf.forEach((d, key) => { if (!live.has(key)) { d.g.remove(); lineOf.delete(key); } });
      // the world's extent; the SVG and the dotted ground are laid over it once
      if (!ways.length && !blocks.size) grow(0, 0);
      bounds = box;
      const m = 40, gx = Math.floor((box.x0 - 3000) / GRID) * GRID, gy = Math.floor((box.y0 - 3000) / GRID) * GRID;
      linesEl.setAttribute("viewBox", (box.x0 - m) + " " + (box.y0 - m) + " " + (box.x1 - box.x0 + 2 * m) + " " + (box.y1 - box.y0 + 2 * m));
      linesEl.style.cssText = "left:" + (box.x0 - m) + "px;top:" + (box.y0 - m) + "px;width:" + (box.x1 - box.x0 + 2 * m) + "px;height:" + (box.y1 - box.y0 + 2 * m) + "px";
      ground.style.cssText = "left:" + gx + "px;top:" + gy + "px;width:" + (box.x1 - gx + 3000) + "px;height:" + (box.y1 - gy + 3000) + "px";
      paint();
      if (!walking) travel();
    }
    // The slow dash that travels along the last way the case took, into the block where it stands: one short lighter stretch.
    function travel() {
      const p = model.path || [], last = p[p.length - 1];
      const w = p.length > 1 && last === model.now ? ways.find((x) => x.from === p[p.length - 2] && x.to === last && x.tone === "taken") : null;
      if (!w) { if (dash) dash.remove(); dash = null; return; }
      dash = dash || svg("path", { class: "cpf-dash" });
      const len = Math.round(w.line.getTotalLength());
      dash.setAttribute("d", w.line.getAttribute("d"));
      dash.style.cssText = "--cpf-len:" + len + ";stroke-dasharray:9 " + (len + 9) + ";animation-duration:" + Math.max(2.4, len / 45).toFixed(1) + "s";
      linesEl.appendChild(dash);
    }
    // A connector draws itself from its port to its target.
    function draw(w) {
      if (calm() || !w.line.animate) return;
      const len = w.line.getTotalLength(), end = () => { w.line.style.strokeDasharray = ""; };
      w.line.style.strokeDasharray = len + " " + len;
      const a = w.line.animate([{ strokeDashoffset: len }, { strokeDashoffset: 0 }], { duration: STEP, easing: "cubic-bezier(.4,0,.2,1)" });
      a.onfinish = a.oncancel = () => { end(); anims.delete(a); };
      anims.add(a);
      if (w.arrow) {
        const f = w.arrow.animate([{ opacity: 0 }, { opacity: 0, offset: 0.85 }, { opacity: 1 }], { duration: STEP });
        f.onfinish = f.oncancel = () => anims.delete(f);
        anims.add(f);
      }
    }

    /* ---------- bringing forward: hover and highlight() ---------- */
    function paint() {
      const f = hover || pinned, hotBlocks = new Set(), near = new Set(), hotWays = new Set();
      ways.forEach((w) => {
        if (!f) return;
        if (f.way === w.key) { hotWays.add(w.key); near.add(w.from); if (w.to != null) hotBlocks.add(w.to); }
        if (f.block != null && (w.from === f.block || w.to === f.block)) { hotWays.add(w.key); near.add(w.from); if (w.to != null) near.add(w.to); }
      });
      if (f && f.block != null) hotBlocks.add(f.block);
      stage.classList.toggle("cpf-focus", !!f);
      blocks.forEach((b, id) => { b.el.classList.toggle("cpf-hot", hotBlocks.has(id)); b.el.classList.toggle("cpf-near", near.has(id) && !hotBlocks.has(id)); });
      ways.forEach((w) => {
        const hot = hotWays.has(w.key);
        w.g.classList.toggle("cpf-hot", hot);
        w.r.el.classList.toggle("cpf-hot", !!f && f.way === w.key);
        if (w.pill) w.pill.classList.toggle("cpf-hot", hot);
      });
      // what matters lies on top where lines share a trunk: pale, possible, taken, then whatever is brought forward
      const rank = (w) => (w.g.classList.contains("cpf-hot") ? 8 : 0) + (w.g.classList.contains("cpf-wait") ? 1 : { pale: 1, possible: 2, taken: 3 }[w.tone]);
      const sorted = ways.slice().sort((a, b) => rank(a) - rank(b));
      if (sorted.some((w, i) => linesEl.children[i] !== w.g)) sorted.forEach((w) => linesEl.appendChild(w.g));
      if (dash && dash.parentNode) linesEl.appendChild(dash);
    }
    function setHover(focus, blockId) {
      if (JSON.stringify(focus) !== JSON.stringify(hover)) { hover = focus; paint(); }
      if (blockId !== over) { over = blockId; if (opt.onHover) opt.onHover(blockId != null && blocks.has(blockId) ? blocks.get(blockId).m : null); }
    }

    /* ---------- camera ---------- */
    function apply(animate) {
      world.style.transition = animate && !calm() ? "transform .65s cubic-bezier(.4,0,.2,1)" : "none";
      world.style.transform = "translate(" + Math.round(cam.x) + "px," + Math.round(cam.y) + "px) scale(" + cam.s.toFixed(4) + ")";
      ctl.here.setAttribute("aria-pressed", String(mode === "here"));
      ctl.whole.setAttribute("aria-pressed", String(mode === "whole"));
    }
    // a block with its end pills
    function reach(b) {
      let x1 = b.x + W;
      b.rows.forEach((r) => { if (r.pill) x1 = Math.max(x1, gutters[b.col].pillX + r.pw); });
      return { x0: b.x, y0: b.y, x1: x1, y1: b.y + b.h };
    }
    function fitWhole(animate) {
      if (!bounds) return;
      const vw = view.clientWidth - 2 * PAD, vh = view.clientHeight - 2 * PAD, bw = bounds.x1 - bounds.x0, bh = bounds.y1 - bounds.y0;
      const s = Math.min(1, vw / bw, vh / bh);
      cam = { s: s, x: PAD + (vw - bw * s) / 2 - bounds.x0 * s, y: PAD + (vh - bh * s) / 2 - bounds.y0 * s };
      apply(animate);
    }
    // Rest on one block at a readable scale. In view, in this order of weight: the block itself (its band at the top
    // if it is taller than the view), the block the case came from with the connector between them, its end pills;
    // within that its neighbourhood is centred. The scale gives way a little where that brings one of these in whole.
    function frame(id, animate) {
      const b = blocks.get(id);
      if (!b) return fitWhole(animate);
      const vw = view.clientWidth - 2 * PAD, vh = view.clientHeight - 2 * PAD, own = reach(b), all = Object.assign({}, own);
      const ins = ways.filter((w) => w.to === id && w.block.x < b.x), came = ins.filter((w) => w.tone === "taken");
      const lead = came.length ? came : ins, before = Math.min.apply(null, [b.x].concat(lead.map((w) => w.block.x)));
      // where the way in comes down from a port above the block, that port's row stays in view over a tall block
      const drop = Math.max.apply(null, [0].concat(lead.map((w) => b.y - (w.block.y + w.r.py)))), above = drop ? Math.min(0.3 * vh, drop + 34) : 0;
      ways.forEach((w) => {
        const other = w.from === id ? w.to : w.to === id ? w.from : null;
        if (other == null || !blocks.has(other)) return;
        const o = reach(blocks.get(other));
        all.x0 = Math.min(all.x0, o.x0); all.y0 = Math.min(all.y0, o.y0); all.x1 = Math.max(all.x1, o.x1); all.y1 = Math.max(all.y1, o.y1);
      });
      let s = 1;
      [vh / b.h, vw / (b.x + W - before), vw / (own.x1 - before)].forEach((fit) => { if (fit >= REST_MIN) s = Math.min(s, fit); });
      [vw / (all.x1 - all.x0), vh / (all.y1 - all.y0)].forEach((fit) => { if (fit >= REST_ALL) s = Math.min(s, fit); });
      let x0 = b.x, x1 = b.x + W;
      if ((x1 - before) * s <= vw) x0 = before;
      if ((own.x1 - x0) * s <= vw) x1 = own.x1;
      cam.s = s;
      cam.x = Math.min(PAD - x0 * s, Math.max(PAD + vw - x1 * s, PAD + (vw - (all.x0 + all.x1) * s) / 2));
      cam.y = b.h * s > vh ? PAD + above * s - b.y * s : Math.min(PAD - b.y * s, Math.max(PAD + vh - (b.y + b.h) * s, PAD + (vh - (all.y0 + all.y1) * s) / 2));
      apply(animate);
    }
    function inView(b) {
      const x = b.x * cam.s + cam.x, y = b.y * cam.s + cam.y, w = W * cam.s;
      return x > -0.4 * w && x + w < view.clientWidth + 0.4 * w && y > -8 && y < view.clientHeight - 40;
    }
    // Keep some of the world in view, whatever the hand does.
    function hold() {
      const vw = view.clientWidth, vh = view.clientHeight, keep = 80;
      cam.x = clamp(cam.x, keep - bounds.x1 * cam.s, vw - keep - bounds.x0 * cam.s);
      cam.y = clamp(cam.y, keep - bounds.y1 * cam.s, vh - keep - bounds.y0 * cam.s);
    }
    function byHand() { mode = "free"; follow = false; }
    function pan(dx, dy, animate) { byHand(); cam.x += dx; cam.y += dy; hold(); apply(animate); }
    function zoomAt(px, py, factor) {
      const least = Math.min(0.3, (view.clientWidth - 2 * PAD) / (bounds.x1 - bounds.x0), (view.clientHeight - 2 * PAD) / (bounds.y1 - bounds.y0));
      const s = clamp(cam.s * factor, least, ZOOM_MAX);
      byHand();
      cam.x = px - (px - cam.x) * s / cam.s;
      cam.y = py - (py - cam.y) * s / cam.s;
      cam.s = s;
      hold();
      apply(false);
    }
    function refit(animate) {
      if (!bounds) return;
      stage.classList.toggle("cpf-narrow", view.clientWidth < 700);
      if (mode === "whole") fitWhole(animate);
      else if (mode === "here") frame(walking ? walkAt : nowId(), animate);
      else { hold(); apply(animate); }
    }
    function arrange(anchored) { measure(); layout(anchored); route(); }

    /* ---------- the walk: on mount the path of the case is walked once ---------- */
    function veil(b, on) {
      b.el.classList.toggle("cpf-wait", on);
      setTone(b, on ? "open" : b.m.tone);
      ways.forEach((w) => { if (w.from === b.id) { w.g.classList.toggle("cpf-wait", on); w.r.el.classList.toggle("cpf-wait", on); if (w.pill) w.pill.classList.toggle("cpf-wait", on); } });
    }
    function settle(animate) {
      walking = false;
      follow = false;
      blocks.forEach((b) => veil(b, false));
      paint();
      travel();
      if (mode === "here") frame(nowId(), animate);
    }
    function walk() {
      const path = (model.path || []).filter((id) => blocks.has(id));
      if (!opt.autoplay || calm() || !path.length) return settle(false);
      walking = follow = true;
      blocks.forEach((b) => veil(b, true));     // the process is there at once, in pale
      paint();
      frame(walkAt = path[0], false);
      const step = (i) => {
        if (!walking) return;
        veil(blocks.get(path[i]), false);
        paint();
        if (i === path.length - 1) return later(() => { if (walking) settle(true); }, STEP);
        const w = ways.find((x) => x.from === path[i] && x.to === path[i + 1] && x.tone === "taken");
        if (w) draw(w);
        if (follow) frame(walkAt = path[i + 1], true);
        later(() => step(i + 1), STEP);
      };
      later(() => {
        if (!walking) return;
        blocks.forEach((b) => { if (path.indexOf(b.id) < 0) veil(b, false); });   // what the case did not walk shows as it is
        step(0);
      }, STEP);
    }

    /* ---------- the hand: press, drag, zoom, keys ---------- */
    const open = (b, r, pill) => {
      const thing = { block: b.m };
      if (r) thing.row = r.m;
      if (pill) thing.end = r.m.end;
      if (opt.onOpen) opt.onOpen(thing);
      else if (r && !pill && r.m.href) window.location.assign(r.m.href);
    };
    const find = (target) => {
      const pe = target.closest(".cpf-pill"), be = pe || target.closest(".cpf-block"), re = pe || target.closest(".cpf-row");
      const b = be ? blocks.get(be.dataset.b) : null;
      return { b: b, r: b && re ? b.rows.get(re.dataset.r) : null, pill: !!pe };
    };
    on(stage, "click", (e) => {
      if (swallow) { swallow = false; e.preventDefault(); e.stopPropagation(); return; }
      const c = e.target.closest(".cpf-ctl"), a = e.target.closest(".cpf-act"), at = find(e.target);
      if (c) return c.dataset.act === "here" ? api.here() : c.dataset.act === "whole" ? api.whole() : opt.onExpand();
      if (!at.b) return;
      if (a) { if (opt.onAction) opt.onAction(at.r.m, at.r.m.actions.find((x) => String(x.id) === a.dataset.a), at.b.m); return; }
      if (at.pill) open(at.b, at.r, true);
      else if (at.r) { if (at.r.m.href || at.r.m.item) open(at.b, at.r); }
      else if (e.target.closest(".cpf-band")) open(at.b);
    }, true);
    on(stage, "keydown", (e) => {
      const arrows = { ArrowLeft: [1, 0], ArrowRight: [-1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] }, t = e.target;
      if (arrows[e.key]) { e.preventDefault(); pan(arrows[e.key][0] * 80, arrows[e.key][1] * 80, true); return; }
      if (e.key !== "Enter" && e.key !== " ") return;
      const at = find(t);
      if (t.classList.contains("cpf-block") && e.key === "Enter") open(at.b);
      else if (t.classList.contains("cpf-opens")) { e.preventDefault(); open(at.b, at.r); }
    });
    // Tab may land on a block outside the view: the camera goes there (the view itself never scrolls).
    on(stage, "focusin", (e) => {
      view.scrollLeft = view.scrollTop = 0;
      const b = find(e.target).b;
      if (b && e.target.matches(":focus-visible") && !inView(b)) { byHand(); frame(b.id, true); }
    });
    on(view, "scroll", () => { view.scrollLeft = view.scrollTop = 0; });
    on(view, "pointerdown", (e) => {
      if (e.button || e.target.closest("button")) return;     // a press on a button never starts a pan
      ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY, moved: false });
    });
    on(view, "pointermove", (e) => {
      const p = ptrs.get(e.pointerId);
      if (!p) return;
      const dx = e.clientX - p.x, dy = e.clientY - p.y;
      if (!p.moved && ptrs.size === 1 && Math.hypot(dx, dy) < 4) return;
      if (!p.moved) { p.moved = true; try { view.setPointerCapture(e.pointerId); } catch (x) { /* a pointer that is gone */ } stage.classList.add("cpf-drag"); setHover(null, over); }
      const two = ptrs.size === 2 ? Array.from(ptrs.values()) : null, gap = two ? Math.hypot(two[0].x - two[1].x, two[0].y - two[1].y) : 0;
      p.x = e.clientX; p.y = e.clientY;
      if (two && gap > 0) {     // pinch: zoom about the middle of the two fingers
        const r = view.getBoundingClientRect();
        zoomAt((two[0].x + two[1].x) / 2 - r.left, (two[0].y + two[1].y) / 2 - r.top, Math.hypot(two[0].x - two[1].x, two[0].y - two[1].y) / gap);
      }
      pan(dx / ptrs.size, dy / ptrs.size, false);
    });
    const release = (e) => {
      const p = ptrs.get(e.pointerId);
      if (!p) return;
      ptrs.delete(e.pointerId);
      if (p.moved) { swallow = true; later(() => { swallow = false; }, 0); }     // a drag is not a press
      if (!ptrs.size) stage.classList.remove("cpf-drag");
    };
    on(view, "pointerup", release);
    on(view, "pointercancel", release);
    on(view, "wheel", (e) => {
      if (!e.ctrlKey && !e.metaKey) return;      // a plain wheel scrolls the page
      e.preventDefault();
      const r = view.getBoundingClientRect();
      zoomAt(e.clientX - r.left, e.clientY - r.top, Math.exp(-e.deltaY * (e.deltaMode ? 0.05 : 0.0022)));
    }, { passive: false });
    on(world, "pointerover", (e) => {
      if (ptrs.size) return;
      const at = find(e.target), way = at.r && at.r.port ? at.b.id + "|" + at.r.m.id : null;
      setHover(way ? { way: way } : at.b ? { block: at.b.id } : null, at.b && !at.pill ? at.b.id : null);
    });
    on(view, "pointerleave", () => setHover(null, null));
    // The stage changed its size, or the font arrived and the rows have other heights.
    const again = () => { if (dead) return; arrange(false); refit(false); };
    const sized = () => {
      if (dead || (view.clientWidth === seenW && view.clientHeight === seenH)) return;
      seenW = view.clientWidth; seenH = view.clientHeight;
      if (ready && !waiting) return refit(false);
      again();
      if (ready && waiting) { waiting = false; walk(); }      // mounted before it had a size: the walk starts now
    };
    const watch = window.ResizeObserver ? new ResizeObserver(sized) : null;
    if (watch) watch.observe(view); else on(window, "resize", sized);
    if (document.fonts && document.fonts.addEventListener) on(document.fonts, "loadingdone", again);

    /* ---------- the public face ---------- */
    const api = {
      update: function (next) {
        if (dead || !next) return;
        if (walking) settle(false);
        waiting = false;
        const before = shape(), took = new Set(ways.filter((w) => w.tone === "taken").map((w) => w.key));
        model = next;
        sync(false);
        const same = shape() === before;
        // what changed shows as it changes; where a block must give way it glides
        world.classList.toggle("cpf-glide", same && !calm());
        later(() => world.classList.remove("cpf-glide"), 500);
        arrange(same);
        if (same) ways.forEach((w) => { if (w.tone === "taken" && !took.has(w.key)) draw(w); });
        const b = blocks.get(nowId());
        if (!same) refit(false);
        else if (b && !inView(b)) { mode = "here"; frame(b.id, true); }
        else { hold(); apply(false); }
      },
      whole: function () { if (dead) return; mode = "whole"; follow = false; fitWhole(true); },
      here: function () { if (dead) return; mode = "here"; follow = false; frame(nowId(), true); },
      resize: function (height, big) {
        if (dead) return;
        stage.style.height = height + "px";
        large = !!big;
        stage.classList.toggle("cpf-large", large);
        words();
        seenW = view.clientWidth; seenH = view.clientHeight;
        refit(false);
      },
      highlight: function (id) { if (dead) return; pinned = id != null && blocks.has(id) ? { block: id } : null; paint(); },
      destroy: function () {
        if (dead) return;
        dead = true;
        offs.forEach((off) => off());
        timers.forEach((t) => clearTimeout(t));
        Array.from(anims).forEach((a) => a.cancel());
        if (watch) watch.disconnect();
        stage.remove();
      }
    };

    sync(true);
    arrange(false);
    seenW = view.clientWidth; seenH = view.clientHeight;
    stage.classList.toggle("cpf-narrow", seenW < 700);
    if (ready) walk(); else waiting = true;
    return api;
  }

  window.CasePathFlow = { mount: mount };
})();
