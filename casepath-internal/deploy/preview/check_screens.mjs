// Every screen a handler meets, measured on a fresh local preview (deploy/preview/preview.py), before and after a change:
//   BASE=http://127.0.0.1:8797 OUT=/some/dir NODE_PATH=$(npm root -g) node deploy/preview/check_screens.mjs
// For every case the preview seeds (every legal area, every stage) and every state, at 1440x900 (the Übersicht also at
// 1280x720), it opens the Übersicht and the tabs Akte, Prozess, Unterlagen and Verlauf, and records per screen:
//   clickable elements in view (whole page, and the main card); words in the main card above the letter body; repeats on
//   the Übersicht (each date and each deadline title shown more than once outside the letter text, the file list, the
//   file viewer and the customer's own words quoted from the file); internal words (the lexicon below); explanatory sentences (the heuristic of
//   check_simple.mjs); primary buttons in view (exactly one is right); whether the tabs agree on the missing documents and
//   the case list's next step and status agree with the card; page errors and events the route refused. Then, for every
//   letter and template a case can produce (its prepared action and every action it can be changed to), the lexicon and
//   the placeholders on the customer-facing text. Last, case B is prepared live (running, then stopped).
// It changes the preview (another action picked on each case, case B run): run it on a freshly started preview, and start
// a fresh one before check_simple.mjs. Writes OUT/screens.json, OUT/screens.md and the screenshots. An element counts as
// in view when it is inside the window and not scrolled out of a box that clips it (a letter that scrolls on its own).
import { createRequire } from "module";
import fs from "fs";
const { chromium } = createRequire(import.meta.url)("playwright");
const BASE = process.env.BASE || "http://127.0.0.1:8790", OUT = process.env.OUT;
if (!OUT) { console.error("OUT=<directory> is required"); process.exit(2); }
fs.mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const get = async (path) => (await fetch(BASE + path)).json();
const post = async (path, body) => fetch(BASE + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body || {}) });

// The lexicon of internal words: what a handler or a customer should never read.
const LEXICON = [
  ["Code", "\\bA(?:1[0-3]|[0-9])\\b"],
  ["Agent", "\\b(?:Fallleser|Quellenprüfer|Prozessbauer|Dokumentenfinder|Ergebnisprüfer|Agent(?:en)?|claim_reader|source_checker|process_builder|document_finder|result_checker)\\b"],
  ["Kernpunkt", "\\bKernpunkt\\w*"],
  ["Fakt", "\\bFakt(?:en)?\\b"],
  ["Englisch", "\\b(?:the|and|of|with|from|this|that|is|are|case|cases|file|files|request|requests|document|documents|deadline|deadlines|step|steps|found|missing|present|unknown|established|prepared|source|sources|check|checked|reader|finder|checker|builder|wants|because|tenant|landlord|management|true|false|undefined|none|yes|item|items|error|draft|summary|run|stage|workflow|fixture|synthetic|example|process|used|suggested)\\b"],
  ["ID", "\\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{8}\\b|\\bcase_[0-9a-f]{6,}"],
  ["Element-ID", "\\b(?:fact|document|step|deadline|next_action|letter|hint|key_point|stage_line|cover|check|contact|entry|party|summary|mention|vorlage|kp|cl)[:][\\w.-]+|\\bk-know-[\\w-]+|\\bknow-seed[\\w-]*"],
  ["ISO-Datum", "\\b\\d{4}-\\d{2}-\\d{2}\\b"],
  ["Platzhalter", "\\{[^{}\\s][^{}]*\\}|\\b(?:DD|TT)\\.MM\\.(?:YYYY|JJJJ)\\b|\\bJJJJ-MM-TT\\b|\\bYYYY-MM-DD\\b"],
  ["osm", "\\bOSM\\+?|\\bosm\\b"],
  ["Pfad", "\\b(?:docs|casepath|tests|deploy)/[\\w/.-]*"],
  ["Bedingung", "\\(nur bei|solange keine|nach unserer Berechnung"],
  ["Entfernt", "Entwurf · ein Mensch entscheidet|Feiertage nicht berücksichtigt"],
];
const lexicon = (text) => {
  const hits = [];
  // a mail address is data of the case's file (the recipient's, shown beside the letter), never CasePath's own words
  text = String(text || "").replace(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g, " ");
  for (const [name, source] of LEXICON) for (const m of String(text || "").matchAll(new RegExp(source, name === "osm" || name === "Englisch" ? "gi" : "g"))) hits.push(`${name}: ${m[0]}`);
  return hits;
};
// In a customer's text: rule titles in quotation marks, and gaps the file could fill are counted beside the lexicon.
const quotedTitle = (text, titles) => titles.filter((t) => t && String(text).includes(`«${t}»`)).map((t) => `Titel in Anführungszeichen: «${t}»`);

// What is on the screen, as text: visible text nodes outside the letter's own text, the file list and the file viewer.
async function screen(page, { titles }) {
  return page.evaluate(({ titles }) => {
    const H = innerHeight, W = innerWidth;
    // folded: inside a closed <details> other than its summary (the browser lays such content out but does not show it)
    const folded = (el) => { for (let d = el.closest("details:not([open])"); d; d = d.parentElement && d.parentElement.closest("details:not([open])")) {
      const summary = d.querySelector(":scope > summary"); if (!(summary && summary.contains(el))) return true; } return false; };
    const vis = (el) => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.opacity !== "0" && !el.closest("[hidden]") && !folded(el); };
    // in view: inside the window and not scrolled out of a box that clips it (a letter or a list that scrolls on its own)
    const inView = (el) => {
      let { top, bottom, left, right } = el.getBoundingClientRect();
      top = Math.max(top, 0); bottom = Math.min(bottom, H); left = Math.max(left, 0); right = Math.min(right, W);
      for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
        const o = getComputedStyle(a);
        if (!/(auto|scroll|hidden|clip)/.test(o.overflow + o.overflowX + o.overflowY)) continue;
        const b = a.getBoundingClientRect();
        top = Math.max(top, b.top); bottom = Math.min(bottom, b.bottom); left = Math.max(left, b.left); right = Math.min(right, b.right);
      }
      return bottom - top > 1 && right - left > 1;
    };
    const CLICK = "a[href], button, input:not([type=hidden]), select, textarea, summary, [contenteditable=true], [contenteditable=plaintext-only], label:has(> input[type=file])";
    const clickable = [...document.querySelectorAll(CLICK)].filter((el) => vis(el) && inView(el) && !(el.tagName === "INPUT" && el.type === "date" && getComputedStyle(el).opacity === "0"));
    const card = document.querySelector(".cp-prepared");
    const letterText = ".cp-letter [data-seg], .cp-letter li[data-text] > label > span, .cp-also-text, .cp-letter pre, [data-doc-text]";
    // the customer's own words quoted from the file (the request, the questions) are the file's, like the letter is the letter
    const skip = `${letterText}, .cp-doc-body, .cp-doc-head, .cp-doc-toolbar .name, .cp-source-label, .cp-segs, #overview-source, [data-item="summary:0"], [data-item^="customer_question:"]`;
    const textOf = (root, exclude = skip) => {
      if (!root) return "";
      const out = [], walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const n = walker.currentNode, el = n.parentElement;
        if (!n.textContent.trim() || !el || el.closest(exclude) || !el.getClientRects().length || getComputedStyle(el).visibility === "hidden" || folded(el)) continue;
        out.push(n.textContent);
      }
      return out.join(" ").replace(/\s+/g, " ");
    };
    // the card head: what stands in the main card above the letter body
    let head = "";
    if (card) {
      const letter = card.querySelector(".cp-letter"), bar = card.querySelector(".cp-bar");
      const walker = document.createTreeWalker(card, NodeFilter.SHOW_TEXT);
      const words = [];
      while (walker.nextNode()) {
        const n = walker.currentNode, el = n.parentElement;
        if (!n.textContent.trim() || !el || !el.getClientRects().length || folded(el)) continue;
        if (letter && (letter.contains(el) || (letter.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING))) continue;
        if (bar && bar.contains(el)) continue;
        words.push(n.textContent);
      }
      head = words.join(" ");
    }
    const countWords = (t) => String(t).split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length;
    // sentences a person would have to read to use the screen (the heuristic of check_simple.mjs): not the case's own
    // content (an item, the letter, the file's text and its documents' list), and a sentence ends after a word, not an
    // initial («N. Kumar», «S. 2»)
    const letterish = (el) => el.closest("[data-item], pre, .cp-checklist, .cp-letter, .cp-doc-body, .cp-doc-head, .cp-contents, .cp-segs, .cp-source-label");
    const blocks = new Set(), w2 = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (w2.nextNode()) {
      const n = w2.currentNode;
      if (!n.textContent.trim() || letterish(n.parentElement) || !n.parentElement.getClientRects().length || folded(n.parentElement)) continue;
      let b = n.parentElement;
      while (b.parentElement && /^inline/.test(getComputedStyle(b).display)) b = b.parentElement;
      blocks.add(b);
    }
    const own = (b) => [...b.childNodes].map((c) => c.nodeType === 3 ? c.textContent : c.nodeType === 1 && /^inline/.test(getComputedStyle(c).display) && !letterish(c) ? c.innerText : "\n").join("");
    const sentences = [...new Set([...blocks].flatMap((b) => own(b).split("\n")).map((t) => t.replace(/\s+/g, " ").trim()))].flatMap((t) => t.split(/(?<=[\p{L}\p{N}]{2}[.:])\s+/u))
      .filter((t) => /[\p{L}\p{N}]{2}[.:]$/u.test(t) && t.split(/\s+/).length >= 4);
    const primaries = [...document.querySelectorAll(".cp-button.primary")].filter((el) => vis(el) && inView(el)).map((el) => el.innerText.trim().replace(/\s+/g, " "));
    const main = document.querySelector("main");
    const all = textOf(document.body);
    // repeats: each date shown more than once (dd.mm.yyyy; a short dd.mm. counts for the full dates of that day and month)
    const full = {}, short = {};
    for (const m of all.matchAll(/(?<![\d.])(\d{2})\.(\d{2})\.(\d{4})?(?![\d])/g)) {
      const key = `${m[1]}.${m[2]}.`;
      if (m[3]) full[`${key}${m[3]}`] = (full[`${key}${m[3]}`] || 0) + 1; else short[key] = (short[key] || 0) + 1;
    }
    for (const [key, n] of Object.entries(short)) {
      const same = Object.keys(full).filter((k) => k.startsWith(key));
      if (same.length) same.forEach((k) => { full[k] += n; }); else full[key] = n;
    }
    const repeated = Object.entries(full).filter(([, n]) => n > 1).map(([d, n]) => `${d} ×${n}`);
    for (const t of titles) { const n = t ? all.split(t).length - 1 : 0; if (n > 1) repeated.push(`«${t}» ×${n}`); }
    const number = (re, root) => { const m = re.exec(textOf(root || main, letterText)); return m ? Number(m[1]) : null; };
    const missingAttr = document.querySelector("[data-missing]");
    const ticked = [...document.querySelectorAll(".cp-letter li.cp-line[data-item^='document:'] input:checked, .cp-letter li[data-item^='document:'] input:checked")].length;
    return {
      clickable: clickable.length, clickableCard: card ? clickable.filter((el) => card.contains(el)).length : null,
      clickableList: clickable.map((el) => (el.innerText || el.value || el.getAttribute("aria-label") || el.tagName).trim().replace(/\s+/g, " ").slice(0, 40)),
      headWords: card ? countWords(head) : null, head: head.replace(/\s+/g, " ").trim().slice(0, 400),
      repeats: repeated, text: all, sentences, primaries,
      pageHeight: document.documentElement.scrollHeight, viewHeight: H,
      title: (document.querySelector(".cp-prepared h2") || {}).innerText || null,
      status: (document.querySelector("[data-status]") || {}).innerText || null,
      missing: missingAttr ? Number(missingAttr.dataset.missing)
        : number(/(\d+) Unterlage(?:n)? (?:beim Kunden )?(?:fehl|anfordern)/) ?? (ticked || null),
      missingDocs: missingAttr ? Number(missingAttr.dataset.missing) : number(/·\s*(\d+) fehl/),
      missingProcess: missingAttr ? Number(missingAttr.dataset.missing) : number(/(\d+) fehlen oder unbrauchbar/),
    };
  }, { titles });
}

const report = { base: BASE, at: new Date().toISOString(), sizes: ["1440x900", "1280x720"], lexicon: LEXICON.map(([n, s]) => ({ name: n, pattern: s })),
                 list: null, cases: [], states: [], texts: [], errors: [] };
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, locale: "de-CH", timezoneId: "Europe/Zurich" });
const page = await context.newPage();
let pageErrors = [], refused = 0;
page.on("pageerror", (e) => pageErrors.push(String(e.message || e)));
page.on("response", (r) => { if (r.status() === 422 && r.url().includes("/events")) refused += 1; if (r.status() >= 500) pageErrors.push(`${r.status()} ${r.url()}`); });
const shot = async (name, full = false) => { await page.screenshot({ path: `${OUT}/${name}.png` }); if (full) await page.screenshot({ path: `${OUT}/${name}-full.png`, fullPage: true }); };
const go = async (hash, wait = 1600) => { await page.goto(`${BASE}/?lang=de#${hash}`); await sleep(wait); };
const tab = async (id, name) => { await page.evaluate((h) => { location.hash = h; }, `#/case/${id}/${name}`); await sleep(1300); };
const slugs = new Set();
const slug = (text) => { let s = String(text || "fall").toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 34).replace(/-$/, "");
  let out = s, n = 2; while (slugs.has(out)) out = `${s}-${n++}`; slugs.add(out); return out; };
const internal = (m) => lexicon(m.text);

// 1. The case list
const cases = (await get("/api/cases")).cases;
await go("/cases", 2000);
const listScreen = await screen(page, { titles: [] });
await shot("liste-1440x900", true);
const listRows = await page.evaluate(() => [...document.querySelectorAll("table.cp-cases tbody tr")].map((tr) => {
  const a = tr.querySelector("a[href*='#/case/']"), cells = [...tr.querySelectorAll("td")].map((td) => td.innerText.replace(/\s+/g, " ").trim());
  return { id: a ? a.getAttribute("href").split("/")[2] : null, cells };
}));
report.list = { clickable: listScreen.clickable, primaries: listScreen.primaries, internal: internal(listScreen), sentences: listScreen.sentences, rows: listRows.length,
                columns: await page.evaluate(() => [...document.querySelectorAll("table.cp-cases thead th")].map((th) => th.innerText.trim()).filter(Boolean).slice(0, 6)) };

// 2. Every case: the Übersicht at both sizes, then the tabs
for (const c of cases) {
  const data = await get(`/api/cases/${c.id}`);
  const titles = [...new Set((data.items || []).filter((i) => i.kind === "deadline").map((i) => (i.label || {}).de).filter((t) => t && t.length > 12))];
  const row = listRows.find((r) => r.id === c.id) || { cells: [] };
  const name = slug(c.display_title || c.title);
  const action = (data.items || []).find((i) => i.kind === "next_action") || {};
  const stage = ((data.evaluation || {}).current || {}).step || null;
  const state = c.run_status === "completed" ? (c.closed ? "erledigt" : c.new_files ? "neue Unterlagen" : c.historic ? "historisch" : "vorbereitet")
    : c.run_status ? (c.run_status === "failed" ? "abgebrochen" : c.run_status) : "nicht vorbereitet";
  pageErrors = []; const refusedBefore = refused;
  await go(`/case/${c.id}/overview`);
  const ov = await screen(page, { titles });
  await shot(`ov-${name}-1440x900`, true);
  // the menu «Mehr», opened: what it shows
  const more = await page.evaluate(async () => { const d = document.querySelector(".cp-more"); if (!d) return ""; d.open = true; await new Promise((r) => setTimeout(r, 150));
    const t = (d.querySelector(".cp-menu") || d).innerText; d.open = false; return t; });
  await page.setViewportSize({ width: 1280, height: 720 }); await sleep(700);
  const small = await screen(page, { titles });
  await shot(`ov-${name}-1280x720`);
  await page.setViewportSize({ width: 1440, height: 900 }); await sleep(500);
  const tabs = {};
  for (const [id, label] of [["claim_reader", "akte"], ["process_builder", "prozess"], ["document_finder", "unterlagen"], ["history", "verlauf"]]) {
    await tab(c.id, id);
    const m = await screen(page, { titles: [] });
    await shot(`${label}-${name}`);
    tabs[label] = { clickable: m.clickable, internal: internal(m), sentences: m.sentences.length, sentenceList: m.sentences, primaries: m.primaries,
                    missing: label === "unterlagen" ? m.missingDocs : label === "prozess" ? m.missingProcess : undefined };
  }
  const counts = [ov.missing, tabs.unterlagen.missing, tabs.prozess.missing];
  const shown = counts.filter((n) => n !== null && n !== undefined);
  const agreeDocs = new Set(shown).size <= 1 && !(ov.missing == null && shown.some((n) => n > 0));
  const listNext = row.cells[1] || null, listStatus = row.cells[row.cells.length - 1] || null;
  const cardText = `${ov.text} ${ov.status || ""}`;
  const agreeNext = !ov.title || !listNext || listNext === "—" || listNext.trim() === ov.title.trim();
  const agreeStatus = !listStatus || listStatus === "—" || cardText.includes(listStatus.trim()) || (ov.status || "").trim() === listStatus.trim();
  report.cases.push({
    id: c.id, title: c.display_title || c.title, workflow: (data.workflow || {}).id || c.workflow_id || null, stage, action: action.action || null,
    actionTitle: ov.title, state, screenshot: `ov-${name}-1440x900.png`,
    overview: { clickable: ov.clickable, clickableCard: ov.clickableCard, clickableList: ov.clickableList, headWords: ov.headWords, head: ov.head,
                repeats: ov.repeats, internal: [...internal(ov), ...lexicon(more).map((h) => `Mehr · ${h}`)], sentences: ov.sentences,
                primaries: ov.primaries, pageHeight: ov.pageHeight },
    small: { clickable: small.clickable, clickableCard: small.clickableCard, primaries: small.primaries, pageHeight: small.pageHeight, viewHeight: small.viewHeight },
    tabs, agree: { docs: agreeDocs, counts: { uebersicht: ov.missing, unterlagen: tabs.unterlagen.missing, prozess: tabs.prozess.missing },
                   next: agreeNext, listNext, status: agreeStatus, listStatus, cardStatus: ov.status },
    errors: [...pageErrors], refused: refused - refusedBefore });
  process.stdout.write(".");
}
process.stdout.write("\n");

// 3. Every letter and template a case can produce: the prepared action's and those of every action it can be changed to
const checkTexts = async (c, data, via) => {
  const titles = [...new Set((data.items || []).filter((i) => ["deadline", "key_point", "hint"].includes(i.kind)).map((i) => (i.label || {}).de).filter(Boolean))];
  const d = data.draft || {};
  for (const [kind, title, text] of [[d.form, d.title, d.text], ...(d.also || []).map((a) => [a.kind, a.title, a.text])]) {
    if (!text) continue;
    const hits = [...lexicon(text), ...quotedTitle(text, titles)];
    report.texts.push({ case: c.id, caseTitle: c.display_title || c.title, via, kind, title, internal: hits, chars: text.length,
                        gaps: (text.match(/\[bitte ergänzen: [^\]]*\]/g) || []).length, fills: (text.match(/\[einsetzen: [^\]]*\]/g) || []).length });
  }
};
for (const c of cases) {
  const data = await get(`/api/cases/${c.id}`);
  await checkTexts(c, data, "vorbereitet");
  const current = ((data.items || []).find((i) => i.kind === "next_action") || {}).action;
  const options = (data.action_options || []).filter((o) => o.kind !== current && o.has_draft);
  for (const o of options) {
    const r = await post(`/api/cases/${c.id}/action`, { kind: o.kind, reason_code: "6" });
    if (!r.ok) continue;
    await checkTexts(c, await get(`/api/cases/${c.id}`), `geändert zu ${o.title}`);
  }
  if (options.length && (data.action_options || []).some((o) => o.kind === current)) await post(`/api/cases/${c.id}/action`, { kind: current, reason_code: "6" });
}

// 4. The states of a live preparation, on case B: not prepared (measured above), running, stopped
const B = (cases.find((c) => /zweiter Fall/.test(c.title)) || {}).id;
if (B) {
  const started = await (await post(`/api/cases/${B}/runs`)).json().catch(() => ({}));
  await go(`/case/${B}/overview`, 2500);
  for (let i = 0; i < 20 && !(await page.$("#stop-run")); i += 1) await sleep(500);
  const running = await screen(page, { titles: [] });
  await shot("zustand-laeuft");
  report.states.push({ state: "läuft", clickable: running.clickable, primaries: running.primaries, internal: internal(running), sentences: running.sentences });
  if (started.id) await post(`/api/runs/${started.id}/stop`);
  for (let i = 0; i < 40 && (await get(`/api/cases/${B}`)).run.status !== "paused"; i += 1) await sleep(1000);
  await go(`/case/${B}/overview`, 2500);
  const paused = await screen(page, { titles: [] });
  await shot("zustand-angehalten");
  report.states.push({ state: "angehalten", clickable: paused.clickable, primaries: paused.primaries, internal: internal(paused), sentences: paused.sentences });
}
await browser.close();

// 5. The summary: the numbers per measure
const live = report.cases;
const intake = live.filter((c) => ["klaeren", "eingang"].includes(c.stage) && c.state === "vorbereitet");
const max = (xs) => (xs.length ? Math.max(...xs) : null), sum = (xs) => xs.reduce((a, b) => a + b, 0);
const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[Math.floor((s.length - 1) / 2)] : null; };
const screens = live.flatMap((c) => [{ where: `${c.title} · Übersicht`, ...c.overview }, ...Object.entries(c.tabs).map(([t, m]) => ({ where: `${c.title} · ${t}`, ...m }))]);
const onePrimary = [...live.map((c) => ({ where: c.title, n: c.overview.primaries.length })), ...live.map((c) => ({ where: `${c.title} (1280x720)`, n: c.small.primaries.length })),
                    ...report.states.map((s) => ({ where: s.state, n: s.primaries.length }))];
report.summary = {
  cases: live.length,
  clickableCardIntakeMax: max(intake.map((c) => c.overview.clickableCard ?? 0)), clickableCardIntakeMedian: median(intake.map((c) => c.overview.clickableCard ?? 0)),
  clickablePageMax: max(live.map((c) => c.overview.clickable)), clickablePageMedian: median(live.map((c) => c.overview.clickable)),
  headWordsMax: max(live.map((c) => c.overview.headWords ?? 0)), headWordsMedian: median(live.map((c) => c.overview.headWords ?? 0)),
  repeats: sum(live.map((c) => c.overview.repeats.length)), casesWithRepeats: live.filter((c) => c.overview.repeats.length).length,
  internalScreens: sum(screens.map((s) => s.internal.length)) + report.list.internal.length + sum(report.states.map((s) => s.internal.length)),
  internalTexts: sum(report.texts.map((t) => t.internal.length)), texts: report.texts.length,
  sentences: sum(screens.map((s) => (Array.isArray(s.sentences) ? s.sentences.length : s.sentences))) + report.list.sentences.length + sum(report.states.map((s) => s.sentences.length)),
  screensWithOnePrimary: onePrimary.filter((x) => x.n === 1).length, screensMeasuredForPrimary: onePrimary.length,
  wrongPrimary: onePrimary.filter((x) => x.n !== 1).map((x) => `${x.where}: ${x.n}`),
  agreeDocs: live.filter((c) => c.agree.docs).length, agreeNext: live.filter((c) => c.agree.next).length, agreeStatus: live.filter((c) => c.agree.status).length,
  agreeAll: live.filter((c) => c.agree.docs && c.agree.next && c.agree.status).length,
  pageErrors: sum(live.map((c) => c.errors.length)), refused: sum(live.map((c) => c.refused)),
  scrollAt1440: live.filter((c) => c.overview.pageHeight > 900).length, scrollAt1280: live.filter((c) => c.small.pageHeight > 720).length,
  // the assessment and the question back: the gaps a handler still fills («[bitte ergänzen: …]»), in every version a case can produce
  handlerGapsMax: max(report.texts.filter((t) => /^A[45](_|$)/.test(t.kind || "")).map((t) => t.gaps)),
  handlerGapsMedian: median(report.texts.filter((t) => /^A[45](_|$)/.test(t.kind || "")).map((t) => t.gaps)),
};
const urgent = live.find((c) => c.workflow === "verkehr");
if (urgent) report.summary.urgentTraffic = { action: urgent.actionTitle, head: urgent.overview.head, repeats: urgent.overview.repeats,
  documents: (report.texts.filter((t) => t.case === urgent.id && t.via === "vorbereitet").map((t) => t.title)) };
fs.writeFileSync(`${OUT}/screens.json`, JSON.stringify(report, null, 1));

const s = report.summary, cell = (x) => String(x ?? "—").replace(/\|/g, "/");
const lines = [`# Screens, measured ${report.at.slice(0, 16)} on ${BASE}`, "",
  "| Measure | Value |", "|---|---|",
  `| Cases (every area and stage) | ${s.cases} |`,
  `| Clickable in the main card at intake (max · median) | ${s.clickableCardIntakeMax} · ${s.clickableCardIntakeMedian} |`,
  `| Clickable on the page (max · median) | ${s.clickablePageMax} · ${s.clickablePageMedian} |`,
  `| Words in the card head (max · median) | ${s.headWordsMax} · ${s.headWordsMedian} |`,
  `| Repeats on the Übersicht (total · cases) | ${s.repeats} · ${s.casesWithRepeats} |`,
  `| Internal words on handler screens | ${s.internalScreens} |`,
  `| Internal words in customer texts (${s.texts} texts) | ${s.internalTexts} |`,
  `| A4/A5 Lücken für die Fallbearbeitung (max · median) | ${s.handlerGapsMax ?? "—"} · ${s.handlerGapsMedian ?? "—"} |`,
  `| Explanatory sentences | ${s.sentences} |`,
  `| Screens with exactly one primary in view | ${s.screensWithOnePrimary} of ${s.screensMeasuredForPrimary} |`,
  `| Cases where the tabs and the list agree (documents · next step · status · all) | ${s.agreeDocs} · ${s.agreeNext} · ${s.agreeStatus} · ${s.agreeAll} of ${s.cases} |`,
  `| Page errors · refused events | ${s.pageErrors} · ${s.refused} |`,
  `| Übersicht taller than the window (1440x900 · 1280x720) | ${s.scrollAt1440} · ${s.scrollAt1280} |`, "",
  ...(s.urgentTraffic ? [`Urgent traffic case: «${cell(s.urgentTraffic.action)}» · documents: ${s.urgentTraffic.documents.join(", ")} · repeats: ${s.urgentTraffic.repeats.join(", ") || "none"}`, ""] : []),
  "| Case | State | Action | Clickable page / card | Head words | Repeats | Internal (screens) | Sentences | Primary | Docs Ü/U/P | Next | Status | Errors |",
  "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
  ...live.map((c) => `| ${cell(c.title)} | ${c.state} | ${cell(c.actionTitle)} | ${c.overview.clickable} / ${cell(c.overview.clickableCard)} | ${cell(c.overview.headWords)} | ${c.overview.repeats.length} | `
    + `${c.overview.internal.length + Object.values(c.tabs).reduce((n, t) => n + t.internal.length, 0)} | ${c.overview.sentences.length + Object.values(c.tabs).reduce((n, t) => n + t.sentences, 0)} | `
    + `${c.overview.primaries.length} | ${[c.agree.counts.uebersicht, c.agree.counts.unterlagen, c.agree.counts.prozess].map(cell).join("/")}${c.agree.docs ? "" : " ✗"} | ${c.agree.next ? "✓" : "✗"} | ${c.agree.status ? "✓" : "✗"} | ${c.errors.length + c.refused} |`),
  "", "Internal words in customer texts:", "",
  ...report.texts.filter((t) => t.internal.length).map((t) => `- ${cell(t.caseTitle)} · ${cell(t.title)} (${t.via}): ${t.internal.slice(0, 6).join("; ")}${t.internal.length > 6 ? ` … ${t.internal.length}` : ""}`),
];
fs.writeFileSync(`${OUT}/screens.md`, lines.join("\n") + "\n");
console.log(lines.slice(0, 19).join("\n"));
