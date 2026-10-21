// CasePath closing-gate browser walk-through (GET-only, localhost-only, headless Chromium 1440x900).
// Usage: node gate_browse.mjs <base-url> <outdir> <comma-separated claim ids> [<worktree>]
// Env: GATE_BROWSER_BUDGET_S (default 2100) bounds the whole run; partial results are still written.
//
// Works on the W-series desk UI and the north star UI: controls are found by data attribute when the
// served assets use one, else by role and visible text; every control that cannot be found, and every
// expectation that does not hold, becomes a recorded failure {case, step, reason} instead of a crash.
// What the UI shows is checked against the case's own recorded state (GET .../claims/<id>/snapshot):
// step count, legal-test counts, cited passages (must be recorded quotes), draft letter body.
// Writes <outdir>/browser.json and <outdir>/shots/*.png. Exit code 0 whenever browser.json was written.
import {chromium} from '/opt/node22/lib/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';

const [,, BASE_ARG, OUT, IDS_ARG, WT] = process.argv;
if (!BASE_ARG || !OUT || !IDS_ARG) { console.error('usage: node gate_browse.mjs <base-url> <outdir> <ids> [<worktree>]'); process.exit(2); }
const BASE = BASE_ARG.replace(/\/$/, '');
const ORIGIN = new URL(BASE).origin;
const API = BASE + '/api/claim-loops/v1/autonomous';
const IDS = IDS_ARG.split(',').map(s => s.trim()).filter(Boolean);
const SHOTS = path.join(OUT, 'shots');
fs.mkdirSync(SHOTS, {recursive: true});
const BUDGET_MS = Number(process.env.GATE_BROWSER_BUDGET_S || 2100) * 1000;
const T0 = Date.now();
const ACTION_MS = 10000, SETTLE_MS = 45000, DEMO_MS = 300000;
// GATE_MODE=full adds every step/document, reasoning, History and direct-address checks; the default is the
// minimum gate. Overlaps are always audited and reported; they gate only in full mode. GATE_DEMO=1 adds the
// Demonstration check (always on in full mode).
const FULL = process.env.GATE_MODE === 'full', DEMO = FULL || process.env.GATE_DEMO === '1';

const R = {
  base: BASE, viewport: {width: 1440, height: 900}, cases_total: IDS.length, cases_passed: 0,
  cases: [], console_errors: [], page_errors: [], write_requests: [], external_requests: [],
  http_errors: [], dialogs: [], overlaps: 0, overlap_details: [], chrome_overlaps_scrollable: 0,
  failures: [], observations: [], matched_by_fallback: [], screenshots: [], discovery: null,
  demonstration: null, list: null, duration_s: null, completed: false,
};
let ctx = 'startup';
let currentCase = null;
let shotCount = 0;

function fail(step, reason, extra) {
  const f = {case: currentCase ? currentCase.case : 'global', step, reason};
  if (extra !== undefined) f.detail = extra;
  R.failures.push(f);
  if (currentCase) currentCase.failures.push({step, reason});
  console.log(`FAIL [${f.case}] ${step}: ${reason}`);
}
function observe(text) { if (!R.observations.includes(text)) R.observations.push(text); }
function write() {
  R.duration_s = Math.round((Date.now() - T0) / 100) / 10;
  R.cases_passed = R.cases.filter(c => c.passed).length;
  fs.writeFileSync(path.join(OUT, 'browser.json'), JSON.stringify(R, null, 1));
}
const overBudget = () => Date.now() - T0 > BUDGET_MS;
// Appended to "control not found" reasons: whether the served assets contain the label at all.
const hint = (...labels) => { const L = R.discovery?.labels || {}; const gone = labels.filter(l => L[l] === false); return gone.length && gone.length === labels.length ? ` (the served UI's assets never mention ${gone.map(l => `"${l}"`).join(' or ')})` : ''; };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const norm = s => String(s ?? '').normalize('NFKC').replace(/[\u2018\u2019\u201B]/g, "'").replace(/[\u201C\u201D\u201E]/g, '"')
  .replace(/[\u2010-\u2015\u2212]/g, '-').replace(/\u00AD/g, '').replace(/\s+/g, ' ').trim();
const stripEllipsis = s => s.replace(/\s*(\u2026|\.\.\.)\s*$/, '').replace(/^\s*(\u2026|\.\.\.)\s*/, '').trim();
const short = (s, n = 80) => { const t = norm(s); return t.length > n ? t.slice(0, n - 1) + '…' : t; };

// ---------------------------------------------------------------- ground truth (recorded state, GET only)
const truthCache = new Map();
async function getJSON(url) {
  const res = await fetch(url, {headers: {accept: 'application/json'}});
  if (!res.ok) throw new Error(`GET ${url.slice(ORIGIN.length)} -> ${res.status}`);
  return res.json();
}
function collectQuotes(value, into) {
  if (Array.isArray(value)) { for (const v of value) collectQuotes(v, into); return; }
  if (value && typeof value === 'object') {
    if (typeof value.quote === 'string' && value.quote.trim()) into.add(norm(value.quote));
    for (const v of Object.values(value)) if (v && typeof v === 'object') collectQuotes(v, into);
  }
}
async function truthFor(id) {
  if (truthCache.has(id)) return truthCache.get(id);
  const t = {ok: false, error: null};
  try {
    const snap = await getJSON(`${API}/claims/${encodeURIComponent(id)}/snapshot?after=0`);
    const s = snap.state || snap;
    const o = s.outcome || {};
    const preds = Array.isArray(o.legal_predicates) ? o.legal_predicates : [];
    const quotes = new Set(); collectQuotes(snap, quotes);
    const cited = new Map();   // artifact_id -> number of fact/result/outcome citations
    const addCites = rows => { for (const r of rows || []) for (const c of r?.citations || []) if (c?.artifact_id) cited.set(c.artifact_id, (cited.get(c.artifact_id) || 0) + 1); };
    addCites(s.facts); addCites(s.results); addCites(preds); addCites([o]);
    Object.assign(t, {
      ok: true, status: s.status, assessment: o.assessment_status || null, title: s.title || '',
      nodes: (s.graph?.nodes || []).map(n => ({id: n.node_id, label: n.label || ''})),
      predicates: {total: preds.length, failed: preds.filter(p => p.status === 'failed').length,
        open: preds.filter(p => !['supported', 'failed'].includes(p.status)).length},
      quotes, cited,
      sources: (s.acquired_sources || []).map(a => ({id: a.artifact_id, name: a.file_name || '', role: a.role || '', text: norm(a.text || '')})),
      draft: o.request_draft && typeof o.request_draft === 'object' ? {subject: norm(o.request_draft.subject || ''), body: norm(o.request_draft.body || '')} : null,
      opsLoaded: false,
    });
  } catch (e) { t.error = String(e.message || e); }
  truthCache.set(id, t);
  return t;
}
// Adds the quotes of the recorded operation trace (what the live/demo views cite) once per case.
async function loadOperationQuotes(t, id) {
  if (!t.ok || t.opsLoaded) return;
  t.opsLoaded = true;
  try {
    const res = await fetch(`${API}/claims/${encodeURIComponent(id)}/operations?mode=live`);
    if (!res.ok) return;
    for (const line of (await res.text()).split('\n')) { if (!line.trim()) continue; try { collectQuotes(JSON.parse(line), t.quotes); } catch (_) { /* skip */ } }
  } catch (_) { /* quotes from the snapshot remain */ }
}
function quoteMatch(text, quotes) {
  const t = stripEllipsis(norm(text));
  if (t.length < 3) return null;
  if (quotes.has(t)) return 'exact';
  for (const q of quotes) {
    if (t.length >= 12 && q.includes(t)) return 'part of a recorded quote';
    if (q.length >= 12 && t.includes(q)) return 'contains a recorded quote';
  }
  return null;
}
async function checkRecorded(t, id, text) {
  let m = quoteMatch(text, t.quotes);
  if (!m) { await loadOperationQuotes(t, id); m = quoteMatch(text, t.quotes); }
  return m;
}
// Which recorded source is on screen: the one containing most 40-character windows of the shown text.
function identifySource(t, shown) {
  const body = norm(shown);
  if (!t.ok || body.length < 40) return null;
  const wins = [];
  for (let i = 0; i + 40 <= body.length && wins.length < 12; i += Math.max(40, Math.floor(body.length / 12))) wins.push(body.slice(i, i + 40));
  let best = null, bestHits = 0;
  for (const s of t.sources) { const hits = wins.filter(w => s.text.includes(w)).length; if (hits > bestHits) { best = s; bestHits = hits; } }
  return best && bestHits >= Math.min(2, wins.length) ? best : null;
}

// ---------------------------------------------------------------- browser setup
const browser = await chromium.launch({executablePath: process.env.PLAYWRIGHT_CHROMIUM || undefined});
const context = await browser.newContext({viewport: R.viewport, acceptDownloads: false, serviceWorkers: 'block'});
const page = await context.newPage();
page.setDefaultTimeout(ACTION_MS);
let inflight = 0, lastNet = Date.now();
const loadedAssets = new Set();
page.on('console', m => { if (m.type() === 'error') R.console_errors.push({text: m.text().slice(0, 500), at: ctx, location: m.location()?.url || ''}); });
page.on('pageerror', e => R.page_errors.push({message: String(e.message || e).slice(0, 500), at: ctx}));
page.on('dialog', d => { R.dialogs.push({type: d.type(), message: d.message().slice(0, 200), at: ctx}); d.dismiss().catch(() => {}); });
page.on('request', q => { inflight++; lastNet = Date.now(); try { const u = new URL(q.url()); if (u.origin === ORIGIN && /^\/assets\/[^/]+\.(m?js|css)$/.test(u.pathname)) loadedAssets.add(u.pathname.slice(1)); } catch (_) { /* data: */ } });
const done = () => { inflight = Math.max(0, inflight - 1); lastNet = Date.now(); };
page.on('requestfinished', done);
page.on('requestfailed', done);
page.on('response', r => {
  const u = r.url();
  if (u.startsWith(ORIGIN) && r.status() >= 400) R.http_errors.push({status: r.status(), method: r.request().method(), url: u.slice(ORIGIN.length, ORIGIN.length + 300), at: ctx});
});
await context.route('**/*', async route => {
  const q = route.request(), u = q.url();
  let origin = null; try { origin = new URL(u).origin; } catch (_) { /* data:, blob: */ }
  const local = origin === ORIGIN;
  if (origin && origin !== 'null' && !local && /^https?:/.test(u)) {
    R.external_requests.push({method: q.method(), url: u.slice(0, 300), at: ctx});
    return route.abort('blockedbyclient');
  }
  if (local && !['GET', 'HEAD', 'OPTIONS'].includes(q.method())) {
    R.write_requests.push({method: q.method(), url: u.slice(ORIGIN.length, ORIGIN.length + 300), at: ctx});
    return route.abort('blockedbyclient');   // a gate never lets a write land, even on a disposable root
  }
  return route.continue();
});

// ---------------------------------------------------------------- helpers
async function quiet(maxMs = 8000, idleMs = 400) {
  const end = Date.now() + maxMs;
  while (Date.now() < end) { if (inflight === 0 && Date.now() - lastNet >= idleMs) return true; await sleep(60); }
  return false;
}
// Network quiet, no loading marker, and visible text unchanged across two samples.
async function settle(maxMs = 8000) {
  const end = Date.now() + maxMs; let prev = null;
  while (Date.now() < end) {
    await quiet(Math.max(500, end - Date.now()));
    const sig = await page.evaluate(() => {
      const busy = [...document.querySelectorAll('[data-au-skeleton],[data-au-desk-loading],[aria-busy="true"]')].some(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden');
      const m = document.querySelector('main') || document.body;
      return (busy ? 'busy:' : '') + location.hash + '|' + (m.innerText || '').length + '|' + document.querySelectorAll('dialog[open]').length;
    }).catch(() => null);
    if (sig && sig === prev && !sig.startsWith('busy:')) return true;
    prev = sig; await sleep(300);
  }
  return false;
}
async function shot(name, always = false) {
  if (!always && shotCount >= 30) return;
  shotCount++;
  const file = `${String(shotCount).padStart(2, '0')}-${name.replace(/[^a-z0-9_.-]+/gi, '_')}.png`;
  try { await page.screenshot({path: path.join(SHOTS, file)}); R.screenshots.push(file); } catch (e) { observe(`screenshot ${file} failed: ${e.message}`); }
}
// First visible match of an ordered candidate list; records when only a fallback matched.
async function find(label, candidates, scope = page) {
  for (let i = 0; i < candidates.length; i++) {
    try {
      const loc = candidates[i](scope);
      const n = Math.min(await loc.count(), 50);
      for (let k = 0; k < n; k++) {
        const one = loc.nth(k);
        if (await one.isVisible()) {
          if (i > 0) R.matched_by_fallback.push({what: label, candidate: i, at: ctx});
          return one;
        }
      }
    } catch (_) { /* next candidate */ }
  }
  return null;
}
async function click(loc) { await loc.scrollIntoViewIfNeeded({timeout: ACTION_MS}).catch(() => {}); await loc.click({timeout: ACTION_MS}); }
const hash = () => { try { return new URL(page.url()).hash; } catch (_) { return ''; } };
const cssValue = v => String(v).replace(/["\\]/g, '\\$&');
async function errorBanner() {
  return page.evaluate(() => {
    const m = document.querySelector('main') || document.body, t = m.innerText || '';
    const hit = t.match(/(could not be opened|could not be loaded|refresh failed|failed to load|something went wrong|is unavailable|not available right now)/i);
    const retry = [...m.querySelectorAll('button')].find(b => b.offsetParent && /^(try again|retry)$/i.test(b.textContent.trim()));
    return hit ? hit[0] : retry ? `"${retry.textContent.trim()}" button shown` : null;
  }).catch(() => null);
}

// Overlap audit (check_overlaps.mjs logic: visible boxed or text-bearing boxes under main/.au-workspace that
// overlap by more than 2px without containing each other), with boxes clipped by their overflow ancestors
// and the viewport, closed disclosures and svg internals skipped, and a modal audited on its own. Overlaps
// between sticky/fixed chrome and content that can still scroll out from under it are counted separately.
async function audit(frame) {
  let res;
  try {
    res = await page.evaluate(() => {
      const dlg = [...document.querySelectorAll('dialog[open]')].pop();
      const scope = dlg ? [...dlg.querySelectorAll('*')] : [...document.querySelectorAll('main *, .au-workspace *')];
      const vw = innerWidth, vh = innerHeight;
      const clipRect = e => {
        const r0 = e.getBoundingClientRect(); let l = r0.left, t = r0.top, rt = r0.right, b = r0.bottom;
        for (let a = e.parentElement; a && a !== document.documentElement; a = a.parentElement) {
          const s = getComputedStyle(a);
          if (+s.opacity === 0 || s.visibility === 'hidden' || s.display === 'none') return null;
          if (s.overflowX !== 'visible' || s.overflowY !== 'visible' || s.contain.includes('paint')) {
            const q = a.getBoundingClientRect(); l = Math.max(l, q.left); t = Math.max(t, q.top); rt = Math.min(rt, q.right); b = Math.min(b, q.bottom);
          }
          if (s.position === 'fixed') break;
        }
        l = Math.max(l, 0); t = Math.max(t, 0); rt = Math.min(rt, vw); b = Math.min(b, vh);
        return rt - l >= 4 && b - t >= 4 ? {l, t, r: rt, b} : null;
      };
      const chromeOf = e => { for (let a = e; a; a = a.parentElement) { const p = getComputedStyle(a).position; if (p === 'fixed' || p === 'sticky') return a; } return null; };
      const scrollEnd = e => { for (let a = e.parentElement; a; a = a.parentElement) { const s = getComputedStyle(a); if (/(auto|scroll)/.test(s.overflowY) && a.scrollHeight > a.clientHeight + 1) return a.scrollTop + a.clientHeight >= a.scrollHeight - 2; } const d = document.scrollingElement; return d.scrollTop + innerHeight >= d.scrollHeight - 2; };
      const els = [];
      for (const e of scope) {
        if (e.closest('svg') && e.tagName.toLowerCase() !== 'svg') continue;
        if (e.closest('details:not([open])') && !e.closest('summary')) continue;
        const s = getComputedStyle(e);
        if (s.visibility === 'hidden' || s.display === 'none' || +s.opacity === 0) continue;
        if (e.closest('[hidden],[aria-hidden="true"]') && !(e.textContent || '').trim()) continue;
        const boxed = (s.borderTopStyle !== 'none' && parseFloat(s.borderTopWidth) > 0) || (s.backgroundColor !== 'rgba(0, 0, 0, 0)' && s.backgroundColor !== 'transparent');
        const leafText = [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
        if (!boxed && !leafText) continue;
        const r = clipRect(e); if (!r) continue;
        els.push({e, r, chrome: chromeOf(e)});
      }
      const name = e => (e.className && typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/)[0] : e.tagName.toLowerCase()) + ' "' + (e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 32) + '"';
      const hits = [], soft = [];
      for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) {
        const A = els[i], C = els[j];
        if (A.e.contains(C.e) || C.e.contains(A.e)) continue;
        const x = Math.min(A.r.r, C.r.r) - Math.max(A.r.l, C.r.l), y = Math.min(A.r.b, C.r.b) - Math.max(A.r.t, C.r.t);
        if (!(x > 2 && y > 2)) continue;
        const text = `${name(A.e)}  x  ${name(C.e)}  (${Math.round(x)}x${Math.round(y)})`;
        if (A.chrome !== C.chrome) { const content = A.chrome ? C.e : A.e; if (!scrollEnd(content)) { soft.push(text); continue; } }
        hits.push(text);
      }
      return {hits: [...new Set(hits)].slice(0, 30), soft: new Set(soft).size, horizontal: document.documentElement.scrollWidth > innerWidth + 1};
    });
  } catch (e) { observe(`overlap audit failed at ${frame}: ${e.message}`); return; }
  R.overlaps += res.hits.length;
  R.chrome_overlaps_scrollable += res.soft;
  if (res.horizontal) (FULL ? fail : (_, r) => observe(r))('layout', `horizontal page scroll at 1440px (${frame})`);
  if (res.hits.length) { R.overlap_details.push({frame, at: ctx, hits: res.hits}); await shot(`overlap-${frame}`, true); }
}

// ---------------------------------------------------------------- UI discovery (worktree assets the page loaded)
const LABELS = ['Cases', 'Demonstration', 'Knowledge', 'Watch the analysis', 'Show the reasoning', 'Back to the answer', 'Open draft letter',
  'Draft letter', 'History', 'Work log', 'Open documents', 'Open full source', 'Claim reader', 'Source checker', 'Process builder',
  'Document finder', 'Result checker', 'Source facts', 'Current evidence', 'Evidence still needed', 'Relevant reference case', 'Skip to answer'];
function discover() {
  const d = {worktree: WT || null, assets: [...loadedAssets].sort(), attrs: [], labels: {}, summary: {}};
  if (!WT) { d.error = 'no worktree given'; return d; }
  try {
    const root = path.join(WT, 'casepath');
    const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
    const referenced = [...html.matchAll(/(?:src|href)=["'](?:\.\/)?(assets\/[^"'?#]+\.(?:m?js|css))/g)].map(m => m[1]);
    const files = [...new Set([...referenced, ...loadedAssets])];
    let text = html;
    for (const f of files) { try { text += '\n' + fs.readFileSync(path.join(root, f), 'utf8'); } catch (_) { d.missing = [...(d.missing || []), f]; } }
    d.assets = files.sort();
    d.attrs = [...new Set(text.match(/data-au-[a-z0-9-]+/g) || [])].sort();
    for (const l of LABELS) d.labels[l] = text.includes(l);
    const has = a => d.attrs.includes(a);
    d.summary = {desk: has('data-au-desk-select'), northstar: has('data-au-ns'), ns_nodes: has('data-au-ns-node'), ns_start: has('data-au-ns-start'),
      role_tabs: Boolean(d.labels['Claim reader'] && d.labels['Result checker']), work_log: d.labels['Work log'], open_documents: d.labels['Open documents'],
      chain_columns: Boolean(d.labels['Evidence still needed']), reasoning_disclosure: d.labels['Show the reasoning'], draft_letter: d.labels['Open draft letter']};
  } catch (e) { d.error = String(e.message || e); }
  return d;
}

// ---------------------------------------------------------------- page-side probes
// Steps / process nodes on the completed view, in display order.
const enumerateSteps = () => page.evaluate(() => {
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const label = e => (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120);
  const byAttr = (attr, exclude) => {
    const seen = new Set(), items = [];
    for (const e of document.querySelectorAll(`[${attr}]`)) {
      if (!vis(e) || (exclude && e.closest(exclude))) continue;
      const key = e.getAttribute(attr); if (!key || seen.has(key)) continue; seen.add(key);
      items.push({key, label: label(e), attr});
    }
    return items;
  };
  for (const [attr, exclude] of [['data-au-desk-select', '[data-au-desk-next]'], ['data-au-ns-node', null], ['data-au-node', null]]) {
    const items = byAttr(attr, exclude);
    if (items.length) return {via: attr, items};
  }
  document.querySelectorAll('[data-gate-step]').forEach(e => e.removeAttribute('data-gate-step'));
  const list = [...document.querySelectorAll('main [aria-label]')].find(e => vis(e) && /process|steps|nodes/i.test(e.getAttribute('aria-label')));
  let els = list ? [...list.querySelectorAll('button, [role="button"], a[href]')].filter(vis) : [];
  let via = 'aria-labelled process list';
  if (!els.length) { els = [...document.querySelectorAll('main button, main [role="button"]')].filter(b => vis(b) && /^\s*\d{1,2}[.)]?\s+\S/.test(b.innerText || '')); via = 'numbered buttons'; }
  return {via: els.length ? via : null, items: els.map((e, i) => { e.setAttribute('data-gate-step', String(i)); return {key: String(i), label: label(e), attr: 'data-gate-step'}; })};
});
// Documents and files on the completed view.
const enumerateDocuments = () => page.evaluate(() => {
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 1 && r.height > 1 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const label = e => (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 120);
  const out = [], seen = new Set();
  const add = (e, attr, kind) => {
    const key = e.getAttribute(attr); if (!key || seen.has(attr + key)) return; seen.add(attr + key);
    const li = e.closest('li') || e.parentElement; const facts = (li?.innerText || '').match(/(\d+)\s+facts?\b/);
    out.push({key, label: label(e), attr, kind, facts: facts ? Number(facts[1]) : null});
  };
  for (const e of document.querySelectorAll('[data-au-desk-document-select]')) if (vis(e) && !e.closest('[data-au-desk-next]')) add(e, 'data-au-desk-document-select', 'document');
  for (const e of document.querySelectorAll('[data-au-desk-file-select]')) if (vis(e)) add(e, 'data-au-desk-file-select', 'file');
  if (out.length) return {via: 'desk attributes', items: out};
  document.querySelectorAll('[data-gate-doc]').forEach(e => e.removeAttribute('data-gate-doc'));
  const rail = document.querySelector('[data-au-ns-sources], .au-ns-sources') || [...document.querySelectorAll('main aside, main section, main nav')].find(e => vis(e) && /^\s*(sources|documents|files)\b/i.test(e.querySelector('h1,h2,h3')?.textContent || ''));
  let els = rail ? [...rail.querySelectorAll('button, a[href]')].filter(e => vis(e) && !/^(previous|next|open full source)/i.test(label(e))) : [];
  let via = rail ? 'sources rail' : null;
  if (!els.length) { els = [...document.querySelectorAll('main [data-au-source]')].filter(vis); via = els.length ? 'data-au-source' : null; }
  els.forEach((e, i) => { e.setAttribute('data-gate-doc', String(i)); out.push({key: String(i), label: label(e), attr: 'data-gate-doc', kind: 'source', facts: null}); });
  return {via, items: out};
});
// The highlighted cited passage currently shown (mark / quote attributes / highlight colour), and its source pane.
const passageState = () => page.evaluate(() => {
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity !== 0; };
  const dlg = [...document.querySelectorAll('dialog[open]')].pop();
  const scope = dlg || document.querySelector('main') || document.body;
  let marks = [...scope.querySelectorAll('mark, [data-au-ns-quote], [data-au-desk-quote], [data-au-quote]')].filter(e => vis(e) && (e.textContent || '').trim());
  if (!marks.length) {
    const HL = new Set(['rgb(254, 246, 197)', 'rgb(223, 185, 195)']);   // north star --yellow / --crimson-tint
    marks = [...scope.querySelectorAll('span, p, div, li, td, pre')].filter(e => vis(e) && HL.has(getComputedStyle(e).backgroundColor) && (e.textContent || '').trim().length > 2);
  }
  const PANE = '[data-au-desk-source],[data-au-ns-paper],[data-au-ns-preview],.au-ns-page,[data-au-source-content],.au-source-dialog,[data-au-source-preview]';
  const pick = marks.find(m => m.closest(PANE)) || marks[0] || null;
  const pane = pick ? (pick.closest(PANE) || pick.closest('section,article,aside,dialog') || scope) : (scope.querySelector(PANE) || null);
  let visible = false;
  if (pick) {
    const r = pick.getBoundingClientRect(); visible = r.bottom > 1 && r.top < innerHeight - 1 && r.right > 1 && r.left < innerWidth - 1;
    for (let a = pick.parentElement; a && visible; a = a.parentElement) { const s = getComputedStyle(a); if (/(auto|scroll|hidden)/.test(s.overflowY) && a.scrollHeight > a.clientHeight + 1) { const q = a.getBoundingClientRect(); if (r.bottom <= q.top + 1 || r.top >= q.bottom - 1) visible = false; break; } }
  }
  const bodyEl = pane ? (pane.querySelector('pre, .au-desk-source-text, .au-ns-source-scroll, [data-au-source-text]') || pane) : null;
  const nameEl = pane ? pane.querySelector('.au-desk-source-name, header h2, header h3, h2, h3') : null;
  return {pane: Boolean(pane), mark: pick ? pick.textContent.replace(/\s+/g, ' ').trim() : null, marks: marks.length, visible,
    name: nameEl ? nameEl.textContent.replace(/\s+/g, ' ').trim().slice(0, 120) : '', body: bodyEl ? (bodyEl.innerText || '').slice(0, 6000) : '',
    noSource: /no (source|passage) is cited|no cited passage/i.test(pane?.textContent || '')};
});
// Whether the clicked item now reads as selected (address or ARIA/data state on it or its row).
const selectedState = (attr, key) => page.evaluate(([attr, key]) => {
  const el = [...document.querySelectorAll(`[${attr}]`)].find(e => e.getAttribute(attr) === key);
  const nodes = el ? [el, el.closest('li,[role="listitem"],[role="option"],[role="tab"]')].filter(Boolean) : [];
  const on = nodes.some(n => ['aria-current', 'aria-pressed', 'aria-selected', 'aria-expanded'].some(a => n.getAttribute(a) && n.getAttribute(a) !== 'false')
    || [...n.attributes].some(a => /selected|active|current/.test(a.name) && a.value === 'true') || /\b(is-)?(selected|active|current)\b/.test(n.className || ''));
  return {found: Boolean(el), on, hash: location.hash};
}, [attr, key]);

// ---------------------------------------------------------------- navigation pieces
async function goCasesList(first) {
  ctx = `${currentCase?.case || 'global'}:cases-list`;
  if (first) await page.goto(BASE + '/#autonomous/cases', {waitUntil: 'domcontentloaded'});
  else {
    const nav = await find('Cases navigation', [
      s => s.locator('header [data-au-nav="work"]'),
      s => s.locator('header').getByRole('button', {name: /^Cases$/}),
      s => s.locator('header').getByRole('link', {name: /^Cases$/}),
      s => s.locator('header a[href="#autonomous/cases"], a.au-brand'),
      s => s.getByRole('link', {name: /^CasePath\b/}),
    ]);
    if (!nav) { (FULL ? fail : (_, r) => observe(r))('cases-list', 'no "Cases" control (header Cases button or wordmark) to return to the Cases list'); await page.goto(BASE + '/#autonomous/cases'); }
    else await click(nav);
  }
  const rows = page.locator('[data-au-claim], [data-au-claim-row], main a[href*="#autonomous/claim/"]');
  try { await rows.first().waitFor({state: 'visible', timeout: SETTLE_MS}); }
  catch (_) { (FULL ? fail : (_, r) => observe(r))('cases-list', 'the Cases list shows no case rows'); return false; }
  await settle(6000);
  if (first && !R.discovery) R.discovery = discover();
  const filter = await find('answers-ready filter', [
    s => s.locator('[data-au-filter="investigation_complete"]'),
    s => s.getByRole('button', {name: /answers? ready/i}),
    s => s.getByRole('button', {name: /\b(complete|completed|ready)\b/i}),
  ]);
  if (!filter) { if (first) observe('no "answers ready" filter on the Cases list; cases are looked up by search/pagination'); return true; }
  const label = (await filter.innerText()).trim();
  const pressed = await filter.getAttribute('aria-pressed');
  if (pressed !== 'true') { await click(filter); await settle(5000); }
  if (first) {
    const ids = await page.$$eval('[data-au-claim]', es => [...new Set(es.map(e => e.dataset.auClaim))]);
    R.list = {filter_label: label, rows_after_filter: ids.length, ids};
    const m = label.match(/(\d+)/);
    const f = FULL ? fail : (_, r) => observe(r);
    if (m && Number(m[1]) !== ids.length) f('cases-filter', `filter says "${label}" but the list shows ${ids.length} rows`);
    for (const id of IDS) if (ids.length && !ids.includes(id)) f('cases-filter', `reference case ${id} is not among the "${label}" rows`);
  }
  return true;
}
async function rowFor(id, t) {
  const sel = `[data-au-claim="${cssValue(id)}"], main a[href*="${cssValue(id)}"]`;
  let row = page.locator(sel);
  for (let pageNo = 0; !(await row.count()) && pageNo < 10; pageNo++) {
    if (pageNo === 0) {
      const search = await find('case search', [s => s.locator('[data-au-claim-search] input, input[data-au-claim-search]'), s => s.getByRole('searchbox'), s => s.getByRole('textbox', {name: /search/i})]);
      if (search) { await search.fill(t.title || id); await settle(4000); row = page.locator(sel); if (await row.count()) break; await search.fill(''); await settle(3000); }
    }
    const next = await find('next page', [s => s.locator('[data-au-pagination]').getByRole('button', {name: /^next/i}), s => s.getByRole('button', {name: /^next( page)?$/i})]);
    if (!next || await next.isDisabled()) break;
    await click(next); await settle(4000); row = page.locator(sel);
  }
  if (!(await row.count())) return null;
  const info = await row.first().evaluate(e => {
    const r = e.closest('[data-au-claim-row], article, li, tr') || e;
    const ps = [...r.querySelectorAll('p, span, div')];
    const notMet = ps.find(x => /^\W*Not met:/i.test(x.textContent.trim()));
    const titleEl = r.querySelector('.au-case-label, [data-au-case-label], h2, h3, strong');
    return {text: r.innerText.replace(/\s+/g, ' ').trim(), title: titleEl ? titleEl.textContent.replace(/\s+/g, ' ').trim() : null,
      status: r.querySelector('.au-claim-status-word, .au-claim-state, [data-au-case-status]')?.textContent.trim() || null,
      notMet: notMet ? notMet.textContent.replace(/^\W*Not met:\s*/i, '').replace(/\s+/g, ' ').trim() : null, allMet: /All legal tests met/i.test(r.innerText)};
  }).catch(() => ({text: '', status: null, notMet: null, allMet: false}));
  return {row: row.first(), ...info};
}
async function caseReady(id, label) {
  const end = Date.now() + SETTLE_MS; let last = null;
  while (Date.now() < end) {
    last = await page.evaluate(cid => {
      const v = document.querySelector('[data-au-view]');
      const nums = [...document.querySelectorAll('[data-au-desk-metric] .au-desk-number')].map(e => e.textContent.trim());
      const waiting = [...document.querySelectorAll('[data-au-desk-file-state]')].some(e => /wait|reading/i.test(e.getAttribute('data-au-desk-file-state') || ''));
      const h1 = document.querySelector('main h1, [data-au-claim-title], h1');
      return {hash: location.hash, view: v?.getAttribute('data-au-view-state') || null, read: v?.getAttribute('data-au-read-state') || null,
        desk: Boolean(document.querySelector('[data-au-agent-desk]')), ns: document.querySelector('[data-au-ns]')?.getAttribute('data-au-ns-state') || null,
        nums, waiting, title: (h1?.textContent || '').replace(/\s+/g, ' ').trim(),
        busy: [...document.querySelectorAll('[data-au-skeleton],[data-au-desk-loading],[aria-busy="true"]')].some(e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden'),
        ok: location.hash.startsWith('#autonomous/claim/' + cid)};
    }, id).catch(() => null);
    if (last && last.ok && last.title && !last.busy && last.read !== 'refreshing' && (!last.view || last.view === 'claim')
        && (!last.nums.length || (!last.nums.includes('—') && !last.waiting)) && inflight === 0) {
      await settle(5000);
      return last;
    }
    await sleep(200);
  }
  fail(label, `case view did not settle within ${SETTLE_MS / 1000}s`, last);
  return null;
}

// Clicks one step/document/file and checks that its cited passage (a recorded quote) is shown.
async function inspectItem(t, step, item, needPassage) {
  const id = currentCase.case;
  ctx = `${id}:${step.kind}:${step.key}`;
  const loc = page.locator(`[${item.attr}="${cssValue(item.key)}"]`).first();
  if (!(await loc.count())) { fail(`${step.kind}:${step.key}`, `"${item.label}" disappeared before it could be clicked`); return; }
  const before = await passageState().catch(() => null);
  const target = (await loc.locator('button').count()) && !(await loc.evaluate(e => e.matches('button,a,[role="button"]'))) ? loc.locator('button').first() : loc;
  await click(target);
  let st = null; const end = Date.now() + 8000;
  while (Date.now() < end) {
    await sleep(150);
    st = await passageState();
    if ((st.mark || (!needPassage && st.body.length > 0)) && inflight === 0) break;
  }
  await settle(4000);
  st = await passageState();
  const sel = item.attr.startsWith('data-gate') ? {on: false, hash: hash()} : await selectedState(item.attr, item.key);
  const entry = {kind: step.kind, id: item.key, label: item.label, source: st.name, cited: st.mark ? short(st.mark, 120) : null, selected: sel.on, hash: sel.hash};
  currentCase.items.push(entry);
  const where = `${step.kind}:${item.key}`;
  const changed = !before || before.mark !== st.mark || before.name !== st.name || norm(before.body).slice(0, 200) !== norm(st.body).slice(0, 200);
  const keyInHash = !item.attr.startsWith('data-gate') && decodeURIComponent(sel.hash).includes(item.key);
  const addressChanged = sel.hash !== (step.prevHash ?? '');
  const reflected = sel.on || addressChanged || keyInHash;
  step.prevHash = sel.hash;
  entry.effect = {selected: sel.on, address_changed: addressChanged, key_in_address: keyInHash, content_changed: changed};
  if (step.visits) step.visits.set(sel.hash, st.mark || null);
  if (!reflected && !changed) { fail(where, `clicking "${item.label}" changed nothing (no selection state, same address, same source and passage)`); return; }
  if (!st.mark) {
    checkDocumentIdentity(t, step, item, st, entry, where);
    if (needPassage) { fail(where, st.noSource ? `"${item.label}" says no source is cited` : st.pane ? `"${item.label}" shows "${st.name || 'a source'}" without a highlighted cited passage` : `clicking "${item.label}" shows no source`); return; }
    if (norm(st.body).length < 20) { fail(where, `clicking "${item.label}" shows no source text`); return; }
    entry.note = 'no recorded citation for this source; text shown without a highlight';
    return;
  }
  const how = await checkRecorded(t, id, st.mark);
  entry.match = how;
  if (!how) { fail(where, `cited passage for "${item.label}" is not a recorded quote of this case: "${short(st.mark, 90)}"`); return; }
  if (!st.visible) fail(where, `cited passage for "${item.label}" is not scrolled into view`);
  checkDocumentIdentity(t, step, item, st, entry, where);
  if (addressChanged || keyInHash) currentCase.direct.push({hash: sel.hash, mark: norm(st.mark), label: item.label, where});
}
// A clicked file/source must open that source: by recorded artifact id when the control names one,
// else by the label the control shows against the name the viewer shows.
function checkDocumentIdentity(t, step, item, st, entry, where) {
  if (['step', 'node', 'failed-test', 'document'].includes(step.kind)) return;
  const shown = identifySource(t, st.body);
  entry.shown_source = shown ? shown.name : null;
  const byKey = t.ok ? t.sources.find(s => s.id === item.key) : null;
  if (byKey && shown && byKey.name !== shown.name) { fail(where, `clicking "${item.label}" opens ${shown.name}, not ${byKey.name}`); return; }
  if (st.name) {   // the control's label and the opened viewer's name must agree
    const a = norm(item.label).toLowerCase(), b = norm(st.name).toLowerCase();
    if (a && b && !a.startsWith(b.slice(0, 16)) && !b.startsWith(a.slice(0, 16))) fail(where, `clicking "${item.label}" opens a source named "${st.name}"`);
  }
}

async function directChecks(id) {
  const seen = new Set();
  for (const d of currentCase.direct) {
    if (seen.has(d.hash) || overBudget()) continue;
    seen.add(d.hash);
    ctx = `${id}:direct:${d.where}`;
    // A fresh document load: nothing the click path left in memory can leak into what the address shows.
    await page.goto('about:blank');
    await page.goto(`${BASE}/${d.hash}`, {waitUntil: 'domcontentloaded'});
    if (!(await caseReady(id, `direct:${d.where}`))) continue;
    let st = null; const end = Date.now() + 8000;
    while (Date.now() < end) { st = await passageState(); if (st.mark && inflight === 0) break; await sleep(150); }
    await settle(3000);
    st = await passageState();
    if (!st.mark) fail(d.where, `opening "${d.label}" by its own address (${short(decodeURIComponent(d.hash), 70)}) shows no cited passage; the click showed "${short(d.mark, 50)}"`);
    else if (norm(st.mark) !== d.mark) fail(d.where, `clicking "${d.label}" showed "${short(d.mark, 50)}" but its own address shows "${short(st.mark, 50)}" (stale or wrong selection)`);
  }
  currentCase.direct_checked = seen.size;
}

// ---------------------------------------------------------------- one case
async function runCase(id, idx) {
  currentCase = {case: id, index: idx + 1, passed: false, title: null, list_row: null, truth: null, metrics: null, test_status: null,
    steps: 0, documents: 0, items: [], draft: null, reasoning: null, history: null, navigation: null, direct: [], failures: []};
  R.cases.push(currentCase);
  const first = idx === 0;
  const t = await truthFor(id);
  currentCase.truth = t.ok ? {status: t.status, assessment: t.assessment, nodes: t.nodes.length, predicates: t.predicates, quotes: t.quotes.size, sources: t.sources.length, draft: Boolean(t.draft?.body)} : {error: t.error};
  if (!t.ok) fail('recorded-state', `cannot read the case's recorded state: ${t.error}`);
  else if (t.assessment !== 'complete') fail('recorded-state', `seeded case is not complete (assessment ${t.assessment}, status ${t.status})`);
  try {
    // ---- Cases list -> open
    if (!(await goCasesList(first))) await page.goto(`${BASE}/#autonomous/claim/${id}`);
    ctx = `${id}:open`;
    const row = await rowFor(id, t);
    const listHash = hash();
    if (!row) { fail('open', 'case is not reachable from the Cases list (no row; search and pagination found nothing); opened by address instead'); await page.goto(`${BASE}/#autonomous/claim/${id}`); }
    else {
      currentCase.list_row = {text: short(row.text, 300), title: row.title, status: row.status, not_met: row.notMet, all_met: row.allMet};
      if (row.status && !/(answer|ready|complete|done|finished)/i.test(row.status)) fail('cases-list', `Cases row status for a completed case is "${row.status}"`);
      await click(row.row);
    }
    const ready = await caseReady(id, 'open');
    if (!ready) { await shot(`fail-open-${id}`, true); return finish(); }
    const visited = new Set([hash()]), visitedMarks = new Map();
    currentCase.title = ready.title;
    if (row && ready.title && !norm(row.text).includes(norm(ready.title))) fail('list-vs-case', `the Cases row names this case "${row.title || short(row.text, 60)}" but its page is titled "${ready.title}"`);
    const banner = await errorBanner();
    if (banner) fail('open', `the case view shows an error: ${banner}`);
    if (first) await shot(`case${idx + 1}-completed`);
    if (ready.read === 'failed') fail('open', 'the case view says its saved copy could not be refreshed');

    // ---- Back to the list and Forward again (first case), before anything else touches history
    if (first && row) {
      ctx = `${id}:back-to-list`;
      await page.goBack(); await settle(5000);
      const backOk = hash() === listHash && (await page.locator(`[data-au-claim="${cssValue(id)}"], main a[href*="${cssValue(id)}"]`).count()) > 0;
      if (!backOk) fail('back-to-list', `Back from the case should return to the Cases list ${listHash} with the row present, got ${hash()}`);
      ctx = `${id}:forward-to-case`;
      await page.goForward();
      const again = await caseReady(id, 'forward-to-case');
      if (!again) fail('forward-to-case', 'Forward did not restore the case view');
      currentCase.navigation = {back_to_list: backOk, forward_to_case: Boolean(again)};
    }
    await audit(`case${idx + 1}-completed`);

    // ---- metrics (desk) and the answer's legal-test line
    const view = await page.evaluate(() => {
      const labels = [...document.querySelectorAll('[data-au-desk-metric]')].map(m => `${(m.querySelector('.au-desk-number')?.textContent || '').trim()} ${(m.querySelector('.au-desk-metric-label')?.textContent || '').replace(/\s+/g, ' ').trim()}`.trim());
      const main = document.querySelector('main') || document.body;
      const status = (main.innerText.match(/(All \d+ legal tests? met|\d+ of \d+ legal tests? (?:not met|still open)|No legal tests available)/) || [])[1] || null;
      return {labels, status, next: document.querySelector('[data-au-desk-next]')?.textContent.replace(/\s+/g, ' ').trim() || null};
    });
    currentCase.metrics = view.labels; currentCase.test_status = view.status;
    const stepsDone = view.labels.find(l => /steps? done/i.test(l)), sd = stepsDone && stepsDone.match(/(\d+)\s*\/\s*(\d+)/);
    if (sd && (sd[1] !== sd[2] || sd[2] === '0')) fail('metrics', `the completed case says "${stepsDone}"`);

    // ---- every step / node
    const steps = await enumerateSteps();
    currentCase.steps = steps.items.length; currentCase.steps_via = steps.via;
    if (!steps.items.length) fail('steps', 'no steps or process nodes found on the completed case (tried desk steps, north star nodes, a process list, numbered buttons)');
    else {
      if (steps.via !== 'data-au-desk-select' && steps.via !== 'data-au-ns-node') R.matched_by_fallback.push({what: 'steps', via: steps.via, at: ctx});
      if (t.ok && steps.items.length !== t.nodes.length) fail('steps', `the view lists ${steps.items.length} steps but the recorded process has ${t.nodes.length}`);
      if (sd && Number(sd[2]) !== steps.items.length) fail('metrics', `"${stepsDone}" but ${steps.items.length} steps are listed`);
    }
    const stepCtl = {kind: 'step', index: 0, prevHash: hash(), visits: visitedMarks};
    for (const [i, item] of steps.items.entries()) {
      if (overBudget()) break;
      stepCtl.index = i; stepCtl.key = item.key;
      await inspectItem(t, stepCtl, item, true);
      visited.add(hash());
      if (i === 0 && idx < 2) { await shot(`case${idx + 1}-step`); await audit(`case${idx + 1}-step`); }
    }
    const stepMarks = currentCase.items.filter(i => i.kind === 'step' && i.cited).map(i => i.cited);
    if (stepMarks.length >= 3 && new Set(stepMarks).size === 1) fail('steps', `every step shows the same passage ("${short(stepMarks[0], 60)}")`);
    // ---- every document / file
    let docs = await enumerateDocuments();
    if (!docs.items.length) {
      ctx = `${id}:documents`;
      const open = await find('Open documents', [s => s.getByRole('button', {name: /open documents|documents\b/i}), s => s.getByRole('link', {name: /open documents/i})]);
      if (open) { await click(open); await settle(4000); docs = await enumerateDocuments(); }
    }
    currentCase.documents = docs.items.length; currentCase.documents_via = docs.via;
    if (!docs.items.length) fail('documents', 'no documents found on the completed case (tried desk documents/files, the Sources rail, Open documents)' + hint('Open documents'));
    const docCtl = {kind: 'document', index: 0, prevHash: hash(), visits: visitedMarks};
    for (const [i, item] of docs.items.entries()) {
      if (overBudget()) break;
      docCtl.index = i; docCtl.key = item.key; docCtl.kind = item.kind;
      // A passage is required for a step document, for a file the view says has facts, and for any
      // shown source that the case records citations for; a missing document needs no passage.
      const missing = /\b(missing|not received|requested|still needed)\b/i.test(item.label);
      const need = missing ? false : item.kind === 'document' ? true : item.kind === 'file' ? (item.facts ?? 0) > 0 : false;
      await inspectItem(t, docCtl, item, need);
      const last = currentCase.items[currentCase.items.length - 1];
      if (last && last.id === item.key && !last.cited && !missing) {
        const shown = await passageState();
        const src = identifySource(t, shown.body);
        if (src && (t.cited.get(src.id) || 0) > 0) fail(`${item.kind}:${item.key}`, `"${item.label}" shows ${src.name || src.id}, which has ${t.cited.get(src.id)} recorded citation(s), without highlighting one`);
      }
      visited.add(hash());
    }
    if (idx < 2) await audit(`case${idx + 1}-item`);

    // ---- back to the answer / overview
    ctx = `${id}:back-to-answer`;
    const back = await find('Back to the answer', [s => s.getByRole('button', {name: /back to the answer/i}), s => s.locator('[data-au-desk-result]'), s => s.getByRole('button', {name: /^(answer|result|overview)$/i})]);
    if (back) { await click(back); await settle(5000); visited.add(hash()); }

    // ---- failed legal tests listed with the answer open their passage (desk UI only)
    const failedTests = await page.evaluate(() => [...document.querySelectorAll('[data-au-desk-answer] [data-au-desk-predicate-source]')]
      .filter(e => e.offsetParent).map(e => ({key: e.getAttribute('data-au-desk-predicate-source'), label: e.textContent.replace(/\s+/g, ' ').trim().slice(0, 120), attr: 'data-au-desk-predicate-source'})));
    const testCtl = {kind: 'failed-test', index: 0, prevHash: hash(), visits: visitedMarks};
    for (const [i, item] of failedTests.entries()) {
      if (overBudget()) break;
      if (i > 0) { const b = await find('Back to the answer', [s => s.getByRole('button', {name: /back to the answer/i}), s => s.locator('[data-au-desk-result]')]); if (b) { await click(b); await settle(4000); } }
      testCtl.index = i; testCtl.key = item.key;
      await inspectItem(t, testCtl, item, true);
      visited.add(hash());
    }
    currentCase.failed_tests_checked = failedTests.length;
    if (failedTests.length) { const b = await find('Back to the answer', [s => s.getByRole('button', {name: /back to the answer/i}), s => s.locator('[data-au-desk-result]')]); if (b) { await click(b); await settle(4000); visited.add(hash()); } }

    // ---- draft letter
    ctx = `${id}:draft`;
    const draftBtn = await find('Open draft letter', [s => s.locator('[data-au-desk-draft]'), s => s.getByRole('button', {name: /open draft letter/i}), s => s.getByRole('button', {name: /draft letter|draft|letter to/i}), s => s.getByRole('link', {name: /draft letter/i})]);
    if (!draftBtn) fail('draft', 'no "Open draft letter" control (tried data-au-desk-draft, buttons/links named draft/letter)' + hint('Open draft letter', 'Draft letter'));
    else {
      await click(draftBtn);
      try { await page.locator('dialog[open]').first().waitFor({state: 'visible', timeout: ACTION_MS}); } catch (_) { /* checked below */ }
      await settle(3000);
      const d = await page.evaluate(() => {
        const x = [...document.querySelectorAll('dialog[open]')].pop() || [...document.querySelectorAll('main section, main article, main aside')].find(e => /draft|letter/i.test(e.querySelector('h1,h2,h3')?.textContent || ''));
        if (!x) return null;
        const b = x.querySelector('textarea, .au-desk-draft pre, .au-desk-draft blockquote, .au-desk-draft article, .au-desk-draft, pre, blockquote, article');
        return {dialog: x.tagName === 'DIALOG', heading: x.querySelector('h2,h1,h3')?.textContent.trim() || '', text: (x.innerText || '').replace(/\s+/g, ' ').trim(),
          body: (b?.value || b?.innerText || '').replace(/\s+/g, ' ').trim(), notSent: /not sent/i.test(x.innerText), buttons: [...x.querySelectorAll('button')].map(b => b.textContent.trim()).filter(Boolean)};
      });
      if (!d) fail('draft', 'the draft control opened no dialog or draft panel');
      else {
        currentCase.draft = {heading: d.heading, length: d.body.length, not_sent_shown: d.notSent, buttons: d.buttons};
        if (!/draft|letter/i.test(d.heading)) fail('draft', `the draft view is headed "${d.heading}"`);
        if (d.body.length < 60) fail('draft', `the draft letter body is ${d.body.length} characters`);
        if (t.ok && t.draft?.body) {
          const shown = norm(d.text), want = t.draft.body;
          const probe = want.slice(0, Math.min(60, want.length));
          if (!shown.includes(probe)) fail('draft', `the draft letter does not show the recorded draft ("${short(want, 60)}")`);
          currentCase.draft.matches_recorded = shown.includes(probe);
        }
        if (first) await shot(`case${idx + 1}-draft`);
        await audit(`case${idx + 1}-draft`);
        if (d.dialog) {
          const close = await find('Close draft', [s => s.locator('dialog[open] [data-au-close-record]'), s => s.locator('dialog[open]').getByRole('button', {name: /^close$/i}), s => s.locator('dialog[open]').getByRole('button', {name: /close/i})]);
          if (close) await click(close); else await page.keyboard.press('Escape');
          await sleep(300);
          if (await page.locator('dialog[open]').count()) { fail('draft', 'the draft dialog did not close'); await page.keyboard.press('Escape'); }
        }
      }
    }

    // ---- show the reasoning (or its successor)
    ctx = `${id}:reasoning`;
    const summary = await find('Show the reasoning', [
      s => s.locator('summary', {hasText: /show the reasoning/i}), s => s.locator('[data-au-disclosure="outcome-why"] > summary'),
      s => s.getByRole('button', {name: /show the reasoning|reasoning|why this answer|how this was decided/i}),
      s => s.getByRole('button', {name: /^result checker$/i}), s => s.getByRole('tab', {name: /result checker|reasoning/i}),
      s => s.getByRole('button', {name: /^law\b/i}), s => s.locator('[data-au-desk-answer] summary'),
    ]);
    let why = null;
    if (!summary) fail('reasoning', 'no "Show the reasoning" control or successor (tried the disclosure, Reasoning/Why/Result checker/Law controls)' + hint('Show the reasoning', 'Result checker'));
    else {
      await click(summary); await settle(3000);
      why = await page.evaluate(() => {
        const d = [...document.querySelectorAll('details[open]')].find(x => /reasoning|why/i.test(x.querySelector('summary')?.textContent || '')) || document.querySelector('[data-au-disclosure="outcome-why"][open]')
          || [...document.querySelectorAll('dialog[open]')].pop() || document.querySelector('[data-au-reasoning], [data-au-result-checker]');
        if (!d) return null;
        const tests = [...new Set([...d.querySelectorAll('[data-au-desk-predicate], .au-desk-tests li, [data-au-predicate], [data-au-legal-test]')])];
        const failedOf = t => t.dataset.status === 'failed' || /✕|×|not met/i.test(t.textContent);
        return {text: (d.innerText || '').length, steps: d.querySelectorAll('ol li').length, tests: tests.length,
          failed: tests.filter(failedOf).map(t => t.textContent.replace(/[✕✓×]/g, '').replace(/\s+/g, ' ').trim().slice(0, 120)),
          open_tests: tests.filter(t => t.dataset.status && !['failed', 'supported'].includes(t.dataset.status)).length,
          status: ((d.innerText || '').match(/(All \d+ legal tests? met|\d+ of \d+ legal tests? (?:not met|still open))/) || [])[1] || null,
          cites: d.querySelectorAll('[data-au-outcome-cite]').length};
      });
      if (!why) fail('reasoning', 'the reasoning control opened nothing');
      else {
        currentCase.reasoning = why;
        if (why.text < 80) fail('reasoning', 'the reasoning is (nearly) empty');
        if (!why.tests) fail('reasoning', 'the reasoning lists no legal tests');
        if (t.ok && why.tests) {
          if (why.tests !== t.predicates.total) fail('reasoning', `the reasoning lists ${why.tests} legal tests; the case records ${t.predicates.total}`);
          if (why.failed.length !== t.predicates.failed) fail('reasoning', `the reasoning marks ${why.failed.length} legal test(s) not met; the case records ${t.predicates.failed}`);
        }
        if (first) await shot(`case${idx + 1}-reasoning`);
        await audit(`case${idx + 1}-reasoning`);
        if (why.cites) {   // the reasoning's citation opens the exact cited span
          ctx = `${id}:outcome-citation`;
          const cite = page.locator('[data-au-outcome-cite]').first();
          const quote = norm((await cite.locator('q').textContent().catch(() => '')) || '');
          await click(cite);
          try { await page.locator('dialog[open]').first().waitFor({state: 'visible', timeout: ACTION_MS}); } catch (_) { /* checked below */ }
          await settle(4000);
          const src = await passageState();
          currentCase.reasoning.citation = {quote: short(quote, 120), mark: src.mark ? short(src.mark, 120) : null, visible: src.visible};
          if (!src.mark) fail('outcome-citation', 'the reasoning citation opens no highlighted cited span');
          else {
            const q = stripEllipsis(quote), m = norm(src.mark);
            if (q && !(m === q || m.startsWith(q))) fail('outcome-citation', `the citation quotes "${short(q, 60)}" but the viewer highlights "${short(m, 60)}"`);
            if (!(await checkRecorded(t, id, src.mark))) fail('outcome-citation', `the highlighted span is not a recorded quote: "${short(m, 80)}"`);
            if (!src.visible) fail('outcome-citation', 'the highlighted cited span is not scrolled into view');
            if (first) await shot(`case${idx + 1}-citation`);
            await audit(`case${idx + 1}-citation`);
          }
          const close = await find('Close source', [s => s.locator('dialog[open] [data-au-close]'), s => s.locator('dialog[open]').getByRole('button', {name: /close/i})]);
          if (close) await click(close); else await page.keyboard.press('Escape');
          await sleep(300);
          if (await page.locator('dialog[open]').count()) { fail('outcome-citation', 'the source viewer did not close'); await page.keyboard.press('Escape'); }
        }
      }
    }
    // ---- the case's result agrees with its recorded legal tests (answer line, else reasoning)
    const status = view.status || why?.status || null;
    currentCase.test_status = status;
    if (t.ok) {
      const P = t.predicates; let m;
      if (!status) fail('result', `the completed case states no legal-test result (recorded: ${P.total} tests, ${P.failed} not met)`);
      else if ((m = status.match(/^All (\d+) legal tests? met/))) { if (Number(m[1]) !== P.total || P.failed || P.open) fail('result', `the case says "${status}"; recorded: ${P.total} tests, ${P.failed} not met, ${P.open} open`); }
      else if ((m = status.match(/^(\d+) of (\d+) legal tests? not met/))) { if (Number(m[2]) !== P.total || Number(m[1]) !== P.failed) fail('result', `the case says "${status}"; recorded: ${P.total} tests, ${P.failed} not met`); }
      else if ((m = status.match(/^(\d+) of (\d+) legal tests? still open/))) { if (Number(m[2]) !== P.total || Number(m[1]) !== P.open) fail('result', `the case says "${status}"; recorded: ${P.total} tests, ${P.open} open`); }
      else if (/No legal tests available/.test(status) && P.total) fail('result', `the case says "${status}" but records ${P.total} legal tests`);
      const lr = currentCase.list_row || {};
      if (lr.all_met && P.failed) fail('list-vs-case', `the Cases row says "All legal tests met" but the case records ${P.failed} not met`);
      if (lr.text && !lr.all_met && !lr.not_met) observe(`Cases rows do not state the legal-test result (e.g. ${id})`);
      if (lr.not_met && !P.failed) fail('list-vs-case', `the Cases row says "Not met: ${short(lr.not_met, 60)}" but the case records every legal test met`);
      if (lr.text && lr.not_met === null && P.failed && /legal tests/i.test(lr.text)) fail('list-vs-case', `the case records ${P.failed} legal test(s) not met but the Cases row does not say so`);
    }

    // ---- History / Work log
    ctx = `${id}:history`;
    const beforeHistory = hash();
    const histBtn = await find('History / Work log', [s => s.locator('[data-au-detail="activity"]'), s => s.getByRole('button', {name: /^work log\b/i}), s => s.getByRole('button', {name: /^history$/i}), s => s.getByRole('link', {name: /^(history|work log)\b/i})]);
    if (!histBtn) { fail('history', 'no "History" or "Work log" control on the case' + hint('History', 'Work log')); return finish(); }
    await click(histBtn);
    const readHistory = async label => {
      const r = await caseReady(id, label);
      const h = await page.evaluate(() => {
        const panel = document.querySelector('[data-au-panel="activity"], [data-au-context="activity"], .au-activity')
          || [...document.querySelectorAll('main h2, main h3, main h1')].find(x => /^(history|work log)$/i.test(x.textContent.trim()))?.closest('section,article,div');
        if (!panel) return null;
        return {entries: panel.querySelectorAll('li').length, headings: [...panel.querySelectorAll('h2,h3')].map(x => x.textContent.trim()).slice(0, 8), text: (panel.innerText || '').length};
      });
      return {r, h};
    };
    const h1 = await readHistory('history');
    const historyHash = hash();
    currentCase.history = h1.h ? {...h1.h, hash: historyHash} : null;
    if (!h1.h) fail('history', 'the History / Work log view did not render');
    else if (!h1.h.entries) fail('history', 'History lists no entries');
    if (first) await shot(`case${idx + 1}-history`);
    await audit(`case${idx + 1}-history`);

    // ---- reload, Back, Forward (first case)
    if (first) {
      ctx = `${id}:reload`;
      const titleBefore = await page.title();
      await page.reload({waitUntil: 'domcontentloaded'});
      const h2 = await readHistory('reload');
      const nav = currentCase.navigation || {};
      nav.reload_same_address = hash() === historyHash; nav.reload_history = Boolean(h2.h && h2.h.entries);
      if (!nav.reload_same_address) fail('reload', `reload changed the address from ${historyHash} to ${hash()}`);
      if (!nav.reload_history) fail('reload', 'the History view is missing after reload');
      if ((await page.title()) !== titleBefore) fail('reload', `the page title changed on reload: "${titleBefore}" -> "${await page.title()}"`);
      ctx = `${id}:back`;
      await page.goBack(); await sleep(300);
      const rb = await caseReady(id, 'back');
      const backHash = hash();
      nav.back_address = backHash;
      nav.back_to_view_before_history = backHash === beforeHistory;
      if (backHash === historyHash) fail('back', `Back from History did nothing (still ${backHash})`);
      else if (!visited.has(backHash)) fail('back', `Back from History went to ${backHash}, a view never visited in this case`);
      else if (rb) {
        const bb = await errorBanner(); if (bb) fail('back', `the view restored by Back shows an error: ${bb}`);
        if (visitedMarks.get(backHash)) { const ps = await passageState(); if (!ps.mark) fail('back', `Back restored ${decodeURIComponent(backHash).slice(0, 90)} without the cited passage it showed before`); }
      }
      if (!nav.back_to_view_before_history) observe(`History replaces the current history entry: Back from History returns to ${decodeURIComponent(backHash).slice(0, 90)} rather than the view History was opened from (${decodeURIComponent(beforeHistory).slice(0, 60)})`);
      ctx = `${id}:forward`;
      await page.goForward(); await sleep(300);
      const h3 = await readHistory('forward');
      nav.forward_history = hash() === historyHash && Boolean(h3.h && h3.h.entries);
      if (!nav.forward_history) fail('forward', `Forward should return to History ${historyHash}, got ${hash()}`);
      currentCase.navigation = nav;
    }
    // ---- every selection made by click shows the same passage when its own address is opened fresh
    await directChecks(id);
  } catch (e) {
    fail(ctx.split(':').slice(1).join(':') || 'case', `exception: ${String(e.message || e).split('\n')[0].slice(0, 300)}`);
    await shot(`exception-${id}`, true);
  }
  return finish();
  async function finish() {
    currentCase.passed = currentCase.failures.length === 0;
    if (!currentCase.passed) await shot(`fail-${id}`);
    write();
    return currentCase.passed;
  }
}


// ---------------------------------------------------------------- one case, minimum gate (default)
// Cases list -> open the case -> select one process node and see its cited passage (a recorded quote)
// -> open the draft letter (or the Result checker view) -> on the first case: Back/Forward and reload.
async function runCaseMinimal(id, idx) {
  currentCase = {case: id, index: idx + 1, passed: false, title: null, list_row: null, truth: null, node: null, result_view: null, navigation: null, items: [], direct: [], failures: []};
  R.cases.push(currentCase);
  const first = idx === 0;
  const t = await truthFor(id);
  currentCase.truth = t.ok ? {assessment: t.assessment, nodes: t.nodes.length, predicates: t.predicates, quotes: t.quotes.size, draft: Boolean(t.draft?.body)} : {error: t.error};
  if (!t.ok) fail('recorded-state', `cannot read the case's recorded state: ${t.error}`);
  else if (t.assessment !== 'complete') fail('recorded-state', `seeded case is not complete (assessment ${t.assessment})`);
  try {
    if (!(await goCasesList(first))) await page.goto(`${BASE}/#autonomous/claim/${id}`);
    ctx = `${id}:open`;
    const row = await rowFor(id, t);
    const listHash = hash();
    if (!row) { observe(`case ${id} has no row on the Cases list (filter, search, pagination); opened by address`); await page.goto(`${BASE}/#autonomous/claim/${id}`); }
    else { currentCase.list_row = {text: short(row.text, 200), title: row.title}; await click(row.row); }
    const ready = await caseReady(id, 'open');
    if (!ready) { await shot(`fail-open-${id}`, true); return finishMinimal(); }
    currentCase.title = ready.title;
    const banner = await errorBanner();
    if (banner) fail('open', `the case view shows an error: ${banner}`);
    if (row && ready.title && !norm(row.text).includes(norm(ready.title))) observe(`Cases row and case page name ${id} differently: "${row.title || short(row.text, 60)}" vs "${ready.title}"`);
    if (idx < 2) await shot(`case${idx + 1}-opened`);
    await audit(`case${idx + 1}-opened`);

    if (first && row) {   // Back to the list, Forward to the case
      ctx = `${id}:back`;
      await page.goBack(); await settle(5000);
      const backOk = hash() === listHash && (await page.locator(`[data-au-claim="${cssValue(id)}"], main a[href*="${cssValue(id)}"]`).count()) > 0;
      if (!backOk) fail('back', `Back from the case should return to the Cases list (${listHash}) with its row, got ${hash()}`);
      ctx = `${id}:forward`;
      await page.goForward();
      const again = await caseReady(id, 'forward');
      if (!again) fail('forward', 'Forward did not restore the case');
      currentCase.navigation = {back_to_list: backOk, forward_to_case: Boolean(again)};
    }

    // one process node: prefer one that is not already selected, so the click has to work
    ctx = `${id}:node`;
    const steps = await enumerateSteps();
    currentCase.nodes_listed = steps.items.length; currentCase.nodes_via = steps.via;
    if (!steps.items.length) fail('node', 'no process node or step to select (tried desk/north star step buttons, node lists, numbered buttons)');
    else {
      const pressed = await page.evaluate(([attr, keys]) => keys.map(k => { const e = [...document.querySelectorAll(`[${attr}]`)].find(x => x.getAttribute(attr) === k); return Boolean(e && (e.getAttribute('aria-pressed') === 'true' || e.getAttribute('aria-current') === 'true' || e.closest('[data-selected="true"]'))); }), [steps.items[0].attr, steps.items.map(i => i.key)]);
      const pick = steps.items[pressed.findIndex(x => !x)] || steps.items[0];
      const ctl = {kind: 'node', index: 0, key: pick.key, prevHash: hash(), visits: new Map()};
      await inspectItem(t, ctl, pick, true);
      currentCase.node = currentCase.items[currentCase.items.length - 1] || null;
      if (first) await shot(`case${idx + 1}-node`);
      await audit(`case${idx + 1}-node`);
      if (first) {   // reload keeps the address and shows the same cited passage
        ctx = `${id}:reload`;
        const before = hash(), mark = currentCase.node?.cited;
        await page.reload({waitUntil: 'domcontentloaded'});
        const r = await caseReady(id, 'reload');
        let ps = null; const end = Date.now() + 8000;
        while (r && Date.now() < end) { ps = await passageState(); if (ps.mark) break; await sleep(200); }
        currentCase.navigation = {...(currentCase.navigation || {}), reload_same_address: hash() === before, reload_passage: Boolean(ps?.mark)};
        if (hash() !== before) fail('reload', `reload changed the address from ${before} to ${hash()}`);
        else if (mark && !ps?.mark) fail('reload', 'after reload the selected node no longer shows its cited passage');
      }
    }

    // the draft letter, else the Result checker / answer view
    ctx = `${id}:result`;
    let opener = await find('Open draft letter', [s => s.locator('[data-au-desk-draft]'), s => s.getByRole('button', {name: /open draft letter/i})]);
    if (!opener) {
      const via = await find('answer / Result checker', [s => s.locator('[data-au-ns-reasoning]'), s => s.getByRole('button', {name: /show the reasoning|back to the answer/i}),
        s => s.getByRole('button', {name: /^result checker$/i}), s => s.getByRole('tab', {name: /result checker/i})]);
      if (via) { await click(via); await settle(4000); opener = await find('Open draft letter', [s => s.locator('[data-au-desk-draft]'), s => s.getByRole('button', {name: /open draft letter/i})]); }
      if (!opener && via) {
        const view = await page.evaluate(() => { const a = document.querySelector('[data-au-desk-answer], .au-desk-why, [data-au-result-checker]'); return a && a.getClientRects().length ? (a.innerText || '').replace(/\s+/g, ' ').trim() : ''; });
        currentCase.result_view = {kind: 'result view', length: view.length};
        if (view.length < 60) fail('result', 'neither a draft letter nor a readable Result checker / answer view could be opened');
      }
    }
    if (opener) {
      await click(opener);
      try { await page.locator('dialog[open]').first().waitFor({state: 'visible', timeout: ACTION_MS}); } catch (_) { /* checked below */ }
      await settle(3000);
      const d = await page.evaluate(() => {
        const x = [...document.querySelectorAll('dialog[open]')].pop(); if (!x) return null;
        return {heading: x.querySelector('h2,h1,h3')?.textContent.trim() || '', text: (x.innerText || '').replace(/\s+/g, ' ').trim()};
      });
      if (!d) fail('draft', 'the draft letter control opened no dialog');
      else {
        currentCase.result_view = {kind: 'draft letter', heading: d.heading, length: d.text.length};
        if (d.text.length < 60) fail('draft', `the draft letter dialog shows ${d.text.length} characters`);
        if (t.ok && t.draft?.body) {
          const ok = norm(d.text).includes(t.draft.body.slice(0, Math.min(60, t.draft.body.length)));
          currentCase.result_view.matches_recorded = ok;
          if (!ok) fail('draft', `the draft letter does not show the recorded draft ("${short(t.draft.body, 60)}")`);
        }
        if (first) await shot(`case${idx + 1}-draft`);
        await audit(`case${idx + 1}-draft`);
        const close = await find('Close', [s => s.locator('dialog[open] [data-au-close-record]'), s => s.locator('dialog[open]').getByRole('button', {name: /^close$/i}), s => s.locator('dialog[open]').getByRole('button', {name: /close/i})]);
        if (close) await click(close); else await page.keyboard.press('Escape');
        await sleep(300);
        if (await page.locator('dialog[open]').count()) { fail('draft', 'the draft letter dialog did not close'); await page.keyboard.press('Escape'); }
      }
    } else if (!currentCase.result_view) fail('result', 'no "Open draft letter" control and no Result checker / answer view');
  } catch (e) {
    fail(ctx.split(':').slice(1).join(':') || 'case', `exception: ${String(e.message || e).split('\n')[0].slice(0, 300)}`);
    await shot(`exception-${id}`, true);
  }
  return finishMinimal();
  async function finishMinimal() {
    currentCase.passed = currentCase.failures.length === 0;
    if (!currentCase.passed) await shot(`fail-${id}`);
    write();
    return currentCase.passed;
  }
}

// ---------------------------------------------------------------- Demonstration: plays to its first accepted node
async function runDemonstration() {
  currentCase = null; ctx = 'demonstration:open';
  const D = R.demonstration = {result: 'not reached', detail: '', reached_by: null, start_control: null, first_accepted_s: null};
  try {
    await goCasesList(false).catch(() => {});
    ctx = 'demonstration:open';
    const nav = await find('Demonstration', [s => s.locator('header [data-au-nav="demonstration"]'), s => s.locator('header').getByRole('button', {name: /^demonstration$/i}),
      s => s.getByRole('link', {name: /demonstration/i}), s => s.getByRole('button', {name: /demonstration|watch the analysis/i})]);
    if (nav) { D.reached_by = 'control'; await click(nav); }
    else { D.reached_by = 'address'; observe('no visible Demonstration control on the Cases page; opened #autonomous/demonstration by address'); await page.goto(BASE + '/#autonomous/demonstration'); }
    // Accepted only when watched happening: some observation with process nodes on screen and none
    // accepted, then a later one with an accepted node (a finished case shown instead does not count).
    const t0 = Date.now(); let started = false, last = null, sawUnaccepted = false, acceptedAt = null, doneOnly = null;
    const doneOf = x => x ? Math.max(x.nsDone, x.deskDone, x.stepsDone ?? 0) : 0;
    while (Date.now() - t0 < DEMO_MS) {
      last = await page.evaluate(() => {
        const txt = (document.querySelector('main') || document.body).innerText || '';
        const sd = txt.match(/\b(\d+)\s*\/\s*(\d+)\s*steps? done/i);
        return {hash: location.hash, nodes: document.querySelectorAll('[data-au-ns-node], [data-au-desk-select]').length,
          nsDone: document.querySelectorAll('[data-au-ns-node][data-state="done"]').length,
          deskDone: document.querySelectorAll('[data-au-desk-done="true"]').length, stepsDone: sd ? Number(sd[1]) : null,
          start: Boolean([...document.querySelectorAll('[data-au-ns-start]')].find(e => e.offsetParent))};
      }).catch(() => null);
      if (last && last.nodes > 0 && doneOf(last) === 0) sawUnaccepted = true;
      if (last && doneOf(last) > 0) {
        if (sawUnaccepted) { acceptedAt = Date.now(); break; }
        doneOnly ??= Date.now();
        if (Date.now() - doneOnly > 30000) break;   // only ever shows accepted nodes: not playing
      }
      if (!started) {
        const start = await find('demonstration start', [s => s.locator('[data-au-ns-start]'), s => s.getByRole('button', {name: /^watch the analysis$/i}),
          s => s.getByRole('button', {name: /^(play|play recorded work|play saved history|start)$/i})]);
        if (start) { D.start_control = (await start.innerText()).trim(); started = true; ctx = 'demonstration:play'; await click(start); }
      }
      await sleep(250);
    }
    D.state = last;
    if (acceptedAt) {
      D.result = 'first node accepted'; D.first_accepted_s = Math.round((acceptedAt - t0) / 100) / 10;
      D.detail = `${last.nsDone ? last.nsDone + ' north star node(s) done' : last.deskDone ? last.deskDone + ' desk step(s) done' : last.stepsDone + ' steps done'} after ${D.first_accepted_s}s${D.start_control ? ` (started with "${D.start_control}")` : ''}, ${last.hash.slice(0, 80)}`;
      ctx = 'demonstration:accepted';
      await shot('demonstration-first-accepted', true);
      await audit('demonstration-first-accepted');
      const stop = await find('pause', [s => s.locator('[data-au-demo-stop]'), s => s.getByRole('button', {name: /^pause$/i})]);
      if (stop) await click(stop).catch(() => {});
    } else {
      D.detail = doneOnly && !sawUnaccepted ? `only ever showed accepted nodes; never watched one being accepted (${JSON.stringify(last)})` : `no node accepted within ${DEMO_MS / 1000}s (${JSON.stringify(last)})`;
      fail('demonstration', doneOnly && !sawUnaccepted ? 'the Demonstration shows an already-finished process instead of playing to its first accepted node'
        : `the Demonstration did not reach its first accepted node within ${DEMO_MS / 1000}s${D.start_control ? '' : '; no start control found'}`, last);
      await shot('demonstration-not-accepted', true);
    }
  } catch (e) {
    D.detail = `exception: ${String(e.message || e).split('\n')[0]}`;
    fail('demonstration', D.detail);
  }
}

// ---------------------------------------------------------------- main
const guard = setTimeout(() => { fail('budget', `browser run exceeded ${BUDGET_MS / 1000}s; partial results`); write(); process.exit(0); }, BUDGET_MS + 60000);
try {
  for (let i = 0; i < IDS.length; i++) {
    if (overBudget()) { currentCase = null; fail('budget', `browser budget of ${BUDGET_MS / 1000}s exhausted before case ${IDS[i]}`); break; }
    console.log(`case ${i + 1}/${IDS.length} ${IDS[i]}`);
    await (FULL ? runCase(IDS[i], i) : runCaseMinimal(IDS[i], i));
    if (i === 0) { R.discovery = discover(); console.log('ui:', JSON.stringify(R.discovery.summary)); }   // refresh: lazily loaded assets
  }
  const titles = new Map();
  for (const c of R.cases) if (c.title) titles.set(c.title, [...(titles.get(c.title) || []), c.case]);
  for (const [title, ids] of titles) if (ids.length > 1) for (const cid of ids) {
    currentCase = R.cases.find(c => c.case === cid); fail('titles', `${ids.length} different cases open with the same title "${title}": ${ids.join(', ')}`); currentCase.passed = false;
  }
  currentCase = null;
  if (DEMO && !overBudget()) { console.log('demonstration'); await runDemonstration(); }
  else if (DEMO) { currentCase = null; fail('demonstration', 'not run: browser budget exhausted'); }
  currentCase = null; ctx = 'end';
  // Events recorded during a case also fail that case; 5xx answers fail it too.
  for (const c of R.cases) {
    const own = [...R.console_errors, ...R.page_errors, ...R.write_requests, ...R.external_requests, ...R.http_errors.filter(h => h.status >= 500)]
      .filter(x => (x.at || '').startsWith(c.case + ':'));
    if (own.length && c.passed) { c.passed = false; c.failures.push({step: 'events', reason: `${own.length} console/page error(s), blocked request(s) or 5xx response(s) during this case`}); }
  }
  for (const h of R.http_errors.filter(h => h.status >= 500)) fail('http', `${h.status} for ${h.method} ${h.url} (${h.at})`);
  if (R.http_errors.some(h => h.status < 500)) observe(`${R.http_errors.filter(h => h.status < 500).length} 4xx response(s), e.g. ${R.http_errors.find(h => h.status < 500).status} ${R.http_errors.find(h => h.status < 500).url}`);
  R.mode = FULL ? 'full' : 'minimum'; R.overlaps_gating = FULL;
  R.completed = true;
} catch (e) {
  currentCase = null; fail('harness', `browser run aborted: ${String(e.message || e).slice(0, 300)}`);
} finally {
  clearTimeout(guard);
  if (!R.discovery) R.discovery = discover();
  write();
  await browser.close().catch(() => {});
}
console.log(`browser: ${R.cases.filter(c => c.passed).length}/${R.cases_total} cases passed, ${R.failures.length} failures, ${R.console_errors.length} console errors, ${R.page_errors.length} page errors, ${R.write_requests.length} writes, ${R.overlaps} overlaps`);
process.exit(0);
