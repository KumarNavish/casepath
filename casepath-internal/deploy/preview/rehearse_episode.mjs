// The D11 episode on the preview, step by step, into a casepath.rehearsal/1 receipt (MEASURE §1): condition N on E1 or E2.
//   BASE=http://127.0.0.1:8805 EPISODE=e1 SESSION=1 OUT=/some/dir NODE_PATH=$(npm root -g) node deploy/preview/rehearse_episode.mjs
// MODE=scripted (default): the script takes every step itself, so the receipt holds the path's own clicks, scrolls, decisions
//   and confirmations as the screens make them. Its times are the machine's: the label says «scripted path», never a
//   handler's time, and the declared external steps are not taken.
// MODE=baseline: the baseline B0 of the same rehearsal, without CasePath (the A5 form as a Word template, the files in a
//   viewer, the module's law passages as the search, a text file for the claims system and the diary): no browser to
//   measure, so the terminal times each step (Enter at its end) and its declared window counts as a switch; clicks, scrolls
//   and typing are not measured there (null, never 0).
// MODE=rehearsal: a headed browser for the developer's rehearsal (two sessions, counterbalanced with the baseline B0). The
//   terminal names each step; the developer takes it and presses Enter. The external steps (paste into the e-mail, attach,
//   send, paste the note, set the diary) are timed with Enter at their start and end. A stretch of more than 60 s without a
//   click, a key or a scroll is idle and not counted. The label says «developer rehearsal, synthetic analog; handler
//   savings unverified».
// Counting, declared before any scoring: a decision is a click that records a judgment the expert owns ([data-decide],
// [data-cover-decline], the «Empfehlung» answers, «Freigeben», [data-action-reason], [data-line-reason], a question chip's
// «übernehmen»); a confirmation records a fact or moves text («Brief kopieren», «Versandt am», «Aktualisieren», the
// Versandpaket's download, «Aktennotiz kopieren»), counted apart. A passage is a document opened from a source chip;
// opened whole is a file or a document opened from the rail. A context switch is a change of route, and in a rehearsal
// each declared external window. A drop of files is one gesture.
// A step that needs a part of the episode not built yet (A: the assessment; B: approval, copy and dispatch; C: the import,
// the duplicate's refusal and the update it starts; the integrator: the copy of E1 dispatched 91 days ago) stops the script
// with what is missing (exit 2, no receipt). KEEP_GOING=1 notes it, goes on where it can, and still writes no receipt.
import { createRequire } from "module";
import fs from "fs";
import path from "path";
import readline from "readline";
import { fileURLToPath } from "url";

const { chromium } = createRequire(import.meta.url)("playwright");
const BASE = process.env.BASE || "http://127.0.0.1:8805", OUT = process.env.OUT || "", MODE = process.env.MODE || "scripted";
const EPISODE = (process.env.EPISODE || "e1").toLowerCase(), SESSION = Number(process.env.SESSION || 1), KEEP_GOING = process.env.KEEP_GOING === "1";
const TITLES = { e1: /D11-Analogon A\b/, e2: /D11-Analogon B\b/ };
const DISPATCHED = new RegExp(process.env.DISPATCHED || "D11-Analogon A.*(versandt|91)", "i");  // the copy of E1 dispatched 91 days ago
const REPLIES = path.join(path.dirname(fileURLToPath(import.meta.url)), "episode", EPISODE.toUpperCase());
const LABEL = MODE === "scripted" ? "scripted_path.synthetic_analog.no_handler_time" : "developer_rehearsal.synthetic_analog.handler_savings_unverified";
const IDLE = 60000;
if (!["scripted", "rehearsal", "baseline"].includes(MODE) || !TITLES[EPISODE] || ![1, 2].includes(SESSION)) {
  console.error("MODE scripted|rehearsal|baseline, EPISODE e1|e2, SESSION 1|2"); process.exit(2);
}
const ask = (q) => new Promise((resolve) => { const rl = readline.createInterface({ input: process.stdin, output: process.stdout }); rl.question(q, () => { rl.close(); resolve(); }); });

// B0: the same episode without CasePath, timed step by step in the terminal; each step's declared window is a switch
if (MODE === "baseline") {
  const B0 = [["open_case", "den Fall im Text-Fallsystem öffnen", 1], ["read_reply", "die beiden Antworten im Viewer lesen", 1],
              ["reconstruct", "aus der Akte rekonstruieren, was verlangt, versprochen und beantwortet ist", 0],
              ["deckung", "über die Deckung entscheiden", 0], ["research", "die Gesetzesstellen des Moduls nachschlagen", 1],
              ["empfehlung", "die Empfehlung festlegen", 0], ["write_letter", "die Einschätzung in der Word-Vorlage schreiben", 1],
              ["review", "den Brief prüfen", 0]];
  const external = [], steps = [], started = Date.now();
  for (const [name, say, window] of B0) {
    const start = Date.now();
    await ask(`B0 Schritt ${steps.length + 1}: ${say} … dann Enter `);
    steps.push({ n: steps.length + 1, name, ms: Date.now() - start, clicks: null, decisions: ["deckung", "empfehlung"].includes(name) ? 1 : 0,
                 confirmations: 0, edits: null, chars: null, switches: window, opened_whole: null, passages: null, scrolls: { page: null, inner: null } });
  }
  for (const [name, say] of [["paste_email", "in die Antwort-E-Mail einfügen"], ["attach_template", "die Vorlage anhängen"], ["send", "senden"],
                             ["paste_note", "die Aktennotiz ins Text-Fallsystem schreiben"], ["set_diary", "die Wiedervorlage setzen"]]) {
    await ask(`Extern: ${say}. Enter zum Beginn `);
    const start = Date.now();
    await ask("… Enter, wenn erledigt ");
    external.push({ name, ms: Date.now() - start });
  }
  const receipt = { format: "casepath.rehearsal/1", label: LABEL, build: "none", episode: EPISODE, condition: "b0", session: SESSION, steps, external,
                    edit: { ratio_words: null, substantive: null, stylistic: null, slots: {} }, events: {}, duplicate_refused: null,
                    wall_ms: Date.now() - started, model_tokens: 0 };
  if (OUT) { fs.mkdirSync(OUT, { recursive: true }); fs.writeFileSync(path.join(OUT, `rehearsal-${EPISODE}-b0-session${SESSION}.json`), JSON.stringify(receipt, null, 1) + "\n"); }
  console.log(`B0 · ${EPISODE} · session ${SESSION}: ${steps.reduce((n, x) => n + x.ms, 0)} ms in ${steps.length} steps, external ${external.reduce((n, x) => n + x.ms, 0)} ms`);
  process.exit(0);
}
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const get = async (p) => (await fetch(BASE + p)).json();

// What a click is, by the counting rule above (run in the page)
const DECISIONS = ["Freigeben", "Erneut freigeben", "übernehmen · Aussichten genügend", "Aussichten nicht genügend", "übernehmen"];
const CONFIRMATIONS = ["Brief kopieren", "Versandt am", "Aktualisieren", "Erneut aktualisieren", "Versandpaket herunterladen", "Aktennotiz kopieren"];
function recorder({ decisions, confirmations }) {
  const send = (e) => window.__rehearsal && window.__rehearsal(e);
  const name = (el) => (el.innerText || el.value || "").replace(/\s+/g, " ").trim();
  addEventListener("click", (ev) => {
    const el = ev.target.closest("button, a, summary, label, [role=button], [contenteditable], input, select, textarea");
    if (!el) return;
    const text = name(el);
    const decision = el.matches("[data-decide], [data-cover-decline], [data-action-reason], [data-line-reason]") || decisions.some((d) => text === d);
    const confirmation = !decision && confirmations.some((c) => text === c || text.startsWith(c + " "));
    send({ type: "click", decision, confirmation, passage: Boolean(el.closest("[data-cite-file], .cp-source-chip")),
           whole: Boolean(el.closest(".cp-source[data-file], .cp-seg[data-file]")) });
  }, true);
  addEventListener("change", (ev) => { if (ev.target.type === "file" && ev.target.files.length) send({ type: "drop" }); }, true);
  addEventListener("drop", (ev) => { if (ev.dataTransfer && ev.dataTransfer.files.length) send({ type: "drop" }); }, true);
  let last = { target: null, at: 0 };
  addEventListener("scroll", (ev) => {  // one gesture per target until it rests for half a second
    const page = ev.target === document || ev.target === document.documentElement || ev.target === document.body;
    const now = Date.now();
    if (last.target !== ev.target || now - last.at > 500) send({ type: "scroll", page });
    last = { target: ev.target, at: now };
  }, true);
  addEventListener("input", (ev) => {  // typing in the letter or a field; a file chosen is the drop above
    if (ev.target.type !== "file" && ev.target.closest("[contenteditable], textarea, input")) send({ type: "input", chars: (ev.data || "").length });
  }, true);
  addEventListener("keydown", () => send({ type: "key" }), true);
  addEventListener("hashchange", () => send({ type: "route" }));
}

const missing = [];
class Missing extends Error {}
function lacking(what) {  // a part of the episode not built yet: noted, and the run stops unless KEEP_GOING
  missing.push(what);
  console.log(`MISSING: ${what}`);
  if (!KEEP_GOING) throw new Missing(what);
}

const browser = await chromium.launch({ headless: MODE !== "rehearsal" });
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, permissions: ["clipboard-read", "clipboard-write"] });
const log = [];
await context.exposeFunction("__rehearsal", (e) => { log.push({ ...e, at: Date.now() }); });
await context.addInitScript(recorder, { decisions: DECISIONS, confirmations: CONFIRMATIONS });
const page = await context.newPage();
const responses = [];
page.on("response", (r) => { if (r.request().method() === "POST" && /\/api\/cases\/[^/]+\/files$/.test(r.url())) responses.push(r.status()); });
let pageErrors = 0;
page.on("pageerror", (e) => { pageErrors += 1; console.log("page error: " + e.message); });

const steps = [], external = [];
const visible = async (locator) => (await locator.count()) > 0 && await locator.first().isVisible().catch(() => false);
const button = (name) => page.getByRole("button", { name });

// One step: its events between start and end; in a rehearsal the developer takes it, the script only names it
async function step(name, act, say) {
  const start = Date.now(), from = log.length;
  if (MODE === "rehearsal") { await ask(`Schritt ${steps.length + 1}: ${say} … dann Enter `); } else { await act(); await sleep(400); }
  const end = Date.now(), mine = log.slice(from);
  const marks = [start, ...mine.map((e) => e.at), end];
  const active = marks.slice(1).reduce((sum, t, i) => sum + Math.min(t - marks[i], IDLE), 0);
  const clicks = mine.filter((e) => e.type === "click" || e.type === "drop");
  steps.push({ n: steps.length + 1, name, ms: active, clicks: clicks.length, decisions: clicks.filter((e) => e.decision).length,
               confirmations: clicks.filter((e) => e.confirmation).length, edits: mine.filter((e) => e.type === "input").length,
               chars: mine.filter((e) => e.type === "input").reduce((n, e) => n + e.chars, 0), switches: mine.filter((e) => e.type === "route").length,
               opened_whole: clicks.filter((e) => e.whole).length, passages: clicks.filter((e) => e.passage).length,
               scrolls: { page: mine.filter((e) => e.type === "scroll" && e.page).length, inner: mine.filter((e) => e.type === "scroll" && !e.page).length } });
}
async function outside(name, say) {  // a declared external step: timed in a rehearsal, not taken by the script
  if (MODE !== "rehearsal") return;
  await ask(`Extern: ${say}. Enter zum Beginn `);
  const start = Date.now();
  await ask("… Enter, wenn erledigt ");
  external.push({ name, ms: Date.now() - start });
}
async function click(locator, what) {  // a click as a person makes it: on what is in view, after scrolling to it
  await locator.first().scrollIntoViewIfNeeded();
  await locator.first().click();
  await sleep(1200);
  return what;
}
const caseOf = async (re) => ((await get("/api/cases")).cases || []).find((c) => re.test(c.title || "") || re.test(c.display_title || ""));
const letterText = () => page.evaluate(() => (document.querySelector("[data-item='letter:0']") || {}).innerText || "");
const waitRun = async (id, kind) => {
  for (let i = 0; i < 240; i += 1) {
    const run = (await get(`/api/cases/${id}`)).run || {};
    if (run.kind === kind && !["queued", "running"].includes(run.status)) return run;
    await sleep(500);
  }
  return null;
};

async function finish(code) {
  if (missing.length) console.log(`not measured: ${missing.length} part(s) of the episode are missing; no receipt`);
  await browser.close().catch(() => {});
  process.exit(code ?? (missing.length ? 2 : 0));
}

// The episode
try {
const target = await caseOf(TITLES[EPISODE]);
if (!target) { console.error(`no case «${TITLES[EPISODE]}» in the preview: start it with deploy/preview/preview.py 8805`); await finish(2); }
const id = target.id;
const replies = fs.readdirSync(REPLIES).filter((n) => n.endsWith(".eml")).sort().map((n) => path.join(REPLIES, n));
const started = Date.now();
await page.goto(`${BASE}/?lang=de#/cases`); await sleep(2000);

await step("open_from_queue", () => click(page.locator(`a[href*="${id}"]`), "open"), "den Fall aus der Liste öffnen");
await step("drop_reply", async () => { await page.setInputFiles("#upload", replies); await sleep(2500); }, "die beiden Antworten auf den Fall ziehen");
const before = responses.length;
await step("drop_duplicate", async () => { await page.setInputFiles("#upload", replies.slice(0, 1)); await sleep(2000); }, "eine der Antworten nochmals ziehen");
const duplicateRefused = responses.slice(before).includes(409);
if (!duplicateRefused) lacking("C: a file already in the case is refused (C2)");
await step("wait_update", async () => {
  if (await visible(page.locator("#update-run"))) { lacking("C: the import starts the update by itself (C1)"); await click(page.locator("#update-run"), "update"); }
  if (!await waitRun(id, "update")) lacking("C: an update of the replies (C1)");
  await page.reload(); await sleep(2500);
}, "warten, bis die Aktualisierung fertig ist");
await step("read_head", async () => {
  const head = await page.evaluate(() => document.body.innerText);
  if (!/Was sich geändert hat/.test(head) || !/Was das bedeutet/.test(head)) lacking("B: the case head «Was sich geändert hat» · «Was das bedeutet» (B14)");
}, "den Kopf lesen: was sich geändert hat, was das bedeutet");
await step("deckung", async () => {
  const onCard = page.locator("[data-decide='deckung'][data-value='bestätigt']");
  if (await visible(onCard)) return click(onCard, "decide");
  lacking("A: the assessment under the premise shows the «Deckung» decision on the card (A4)");
  await page.evaluate((c) => { location.hash = `#/case/${c}/process_builder`; }, id); await sleep(1500);
  if (await visible(onCard)) await click(onCard, "decide");
  await page.evaluate((c) => { location.hash = `#/case/${c}/overview`; }, id); await sleep(1500);
}, "Deckung bestätigen");
await step("empfehlung", async () => {
  const adopt = button(/^übernehmen · Aussichten genügend$/);
  if (await visible(adopt)) return click(adopt, "adopt");
  lacking("A: the «Empfehlung» decision with «übernehmen · Aussichten genügend» (A5)");
  const prospects = page.locator("[data-decide='aussichten'][data-value='genügend']");
  if (await visible(prospects)) await click(prospects, "prospects");
}, "die Empfehlung übernehmen (Aussichten genügend) oder ändern");
const prepared = await letterText();
await step("edits", async () => {
  const part = page.locator("[data-item='letter:0'] [data-seg='text'], [data-item='letter:0'] [contenteditable]").first();
  if (!(await part.count())) return lacking("the letter's text can be changed in place");
  await part.click(); await page.keyboard.press("End"); await page.keyboard.type(" Vielen Dank für Ihre Geduld."); await sleep(1600);
}, "den Brief anpassen, wo nötig");
const approved = await letterText();
await step("freigeben", async () => {
  const approve = button(/^Freigeben$/);
  if (await visible(approve)) return click(approve, "approve");
  lacking("B: «Freigeben» stores the approval and the Versandpaket (B3)");
}, "freigeben");
await step("brief_kopieren", async () => {
  const copy = button(/^Brief kopieren$/);
  if (!(await visible(copy))) return lacking("B: «Brief kopieren» after the approval, the letter without a gap (A, B18)");
  await click(copy, "copy");
  const copied = ((await get(`/api/cases/${id}/events`)).events || []).some((e) => e.kind === "letter.copied" && e.measure === true);
  if (!copied) lacking("B: a copy is recorded for measurement only («measure», B9)");
}, "Brief kopieren");
await outside("paste_email", "in die Antwort-E-Mail einfügen");
await outside("attach_template", "die Vorlage als .docx anhängen");
await outside("send", "senden");
await outside("paste_note", "die Aktennotiz in das Fallsystem einfügen");
await outside("set_diary", "die Wiedervorlage im Fallsystem setzen");
await step("versandt_am", async () => {
  const dispatched = button(/^Versandt am/);
  if (await visible(dispatched)) return click(dispatched, "dispatch");
  lacking("B: «Versandt am» records the dispatch per recipient (B5)");
}, "«Versandt am» bestätigen");
const copyCase = await caseOf(DISPATCHED);
await step("open_dispatched_copy", async () => {
  if (!copyCase) return lacking("the integrator's seed: the copy of E1 dispatched 91 days ago (needs B's add_dispatch)");
  await page.goto(`${BASE}/?lang=de#/cases`); await sleep(1500);
  await click(page.locator(`a[href*="${copyCase.id}"]`), "open");
}, "die vor 91 Tagen versandte Kopie von E1 öffnen");
await step("a7", async () => {
  if (!copyCase) return;
  for (const [name, what] of [[/^Freigeben$/, "approve"], [/^Brief kopieren$/, "copy"], [/^Versandt am/, "dispatch"]]) {
    const b = button(name);
    if (await visible(b)) await click(b, what); else return lacking(`B: the status inquiry's «${String(name).slice(2, -2)}» (A7 after silence)`);
  }
}, "Statusanfrage: freigeben, Brief kopieren, Versandt am");

// The receipt: ids, counts and enums only
const words = (t) => t.split(/\s+/).filter(Boolean);
const lcs = (a, b) => { let prev = new Array(b.length + 1).fill(0);
  for (const x of a) { const row = [0]; for (let j = 0; j < b.length; j += 1) row.push(x === b[j] ? prev[j] + 1 : Math.max(prev[j + 1], row[j])); prev = row; }
  return prev[b.length]; };
const ratio = (a, b) => { const x = words(a), y = words(b); return x.length || y.length ? Math.round((1 - lcs(x, y) / Math.max(x.length, y.length)) * 1000) / 1000 : 0; };
const SLOTS = [["im_fall", /^In Ihrem Fall/], ["zu_fragen", /^(Zu Ihren Fragen|– «)/], ["empfehlung", /^Wir empfehlen Ihnen/], ["nachzureichen", /^(Bitte reichen Sie uns noch nach|– )/]];
const bySlot = (text) => { const out = { im_fall: "", zu_fragen: "", empfehlung: "", nachzureichen: "", other: "" }; let slot = "other";
  for (const line of text.split("\n")) { const s = SLOTS.find(([, re]) => re.test(line.trim())); slot = s ? s[0] : line.trim() ? (slot === "nachzureichen" && /^– /.test(line.trim()) ? slot : "other") : slot; out[slot] += line + "\n"; }
  return out; };
const sentences = (t) => t.split(/(?<=[.?!])\s+|\n+/).map((s) => s.trim()).filter(Boolean);
const decisive = (s) => (s.match(/\d{1,2}\.\d{1,2}\.\d{4}|CHF\s?[\d'.,–-]+|Art\.\s?\d+\w*(?:\s(?:Abs|lit)\.\s?\w+)*|\b\d+\b|\bnicht\b|\bkein\w*\b|\bnie\b/g) || []).join("|");
const changed = (a, b) => { const x = sentences(a), y = sentences(b); return { gone: x.filter((s) => !y.includes(s)), come: y.filter((s) => !x.includes(s)) }; };
let substantive = 0, stylistic = 0;
for (const [slot, text] of Object.entries(bySlot(approved))) {
  const { gone, come } = changed(bySlot(prepared)[slot], text);
  for (let i = 0; i < Math.max(gone.length, come.length); i += 1) {
    const was = gone[i] || "", now = come[i] || "";
    const answers = ["zu_fragen", "empfehlung", "nachzureichen"].includes(slot) && (!was || !now);  // an answer, a way or a line added or removed
    if (answers || decisive(was) !== decisive(now)) substantive += 1; else stylistic += 1;
  }
}
const kinds = {};
for (const e of (await get(`/api/cases/${id}/events`)).events || []) kinds[e.kind] = (kinds[e.kind] || 0) + 1;
const build = String((await get("/api/manifest")).source_tree_sha256 || "").slice(0, 12);
const receipt = { format: "casepath.rehearsal/1", label: LABEL, build, episode: EPISODE, condition: "n", session: SESSION, steps, external,
  edit: { ratio_words: ratio(prepared, approved), substantive, stylistic,
          slots: Object.fromEntries(Object.entries(bySlot(prepared)).map(([k, v]) => [k, ratio(v, bySlot(approved)[k])])) },
  events: kinds, duplicate_refused: duplicateRefused, wall_ms: Date.now() - started, model_tokens: 0 };
const safe = (v) => typeof v !== "string" || (/^(?:[a-z0-9][a-z0-9_.:-]{0,79})$/.test(v) && !/\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4}/.test(v));
const leaks = JSON.stringify(receipt, (k, v) => (k === "format" || safe(v) ? v : "LEAK")).includes("LEAK");
const line = (s) => `${String(s.n).padStart(2)} ${s.name.padEnd(22)} ${String(s.ms).padStart(7)} ms · ${s.clicks} click(s) · ${s.decisions} decision(s) · ${s.confirmations} confirmation(s)`
  + `${s.edits ? ` · ${s.edits} input(s), ${s.chars} char(s)` : ""}${s.switches ? ` · ${s.switches} switch(es)` : ""}${s.passages ? ` · ${s.passages} passage(s)` : ""}`
  + `${s.opened_whole ? ` · ${s.opened_whole} opened whole` : ""}${s.scrolls.page + s.scrolls.inner ? ` · scrolls ${s.scrolls.page}/${s.scrolls.inner}` : ""}`;
console.log([`${LABEL} · ${EPISODE} · session ${SESSION} · build ${build}`, ...steps.map(line),
  `decisions ${steps.reduce((n, s) => n + s.decisions, 0)} · confirmations ${steps.reduce((n, s) => n + s.confirmations, 0)} (counted apart)`,
  `edit ratio ${receipt.edit.ratio_words} (substantive ${substantive}, stylistic ${stylistic}) · duplicate refused ${duplicateRefused} · page errors ${pageErrors}`].join("\n"));
if (leaks) { console.log("the receipt holds more than ids, counts and enums: not written"); await finish(2); }
if (!missing.length && OUT) {
  fs.mkdirSync(OUT, { recursive: true });
  const file = path.join(OUT, `rehearsal-${EPISODE}-n-session${SESSION}-${MODE}.json`);
  fs.writeFileSync(file, JSON.stringify(receipt, null, 1) + "\n");
  console.log(`receipt: ${file}`);
}
} catch (error) {
  if (!(error instanceof Missing)) throw error;
  console.log(`stopped at the first missing part (KEEP_GOING=1 lists them all)`);
}
await finish(missing.length ? 2 : 0);
