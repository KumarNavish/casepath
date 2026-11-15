// Browser check on a fresh local preview (make preview), one window size per run (each run closes case C):
//   SIZE=1440x900 SHOTS=/some/dir NODE_PATH=$(npm root -g) node deploy/preview/check_simple.mjs
// It measures, as a handler meets them: the main path on case C (open it from the case list, untick one line, copy the
// letter, Erledigt) in clicks and scrolls; the one primary button in each state (prepared, running, paused, closed, new
// files); instruction sentences and interactive elements above the fold on the Übersicht; that every handler gesture
// on case D still leaves its event (the cover decision on the Prozess tab, where the stage's decisions are); that a file
// added in the rail leaves every button working without a reload, that the
// draft waits while new files are unread, that the Verlauf is one table with the report first and every gesture, that
// «Der Fall» fills in while a run works and the viewer shows what is read, and that no element's event is refused.
// MODE=before runs only the measures that also apply to an older build.
import { createRequire } from "module";
const { chromium } = createRequire(import.meta.url)("playwright");
const BASE = process.env.BASE || "http://127.0.0.1:8790", SHOTS = process.env.SHOTS || "", BEFORE = process.env.MODE === "before";
const [W, H] = (process.env.SIZE || "1440x900").split("x").map(Number), tag = `${W}x${H}`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const get = async (path) => (await fetch(BASE + path)).json();
const cases = (await get("/api/cases")).cases, by = (re) => (cases.find((c) => re.test(c.title)) || {}).id;
const C = by(/Handler-Prozess/), D = by(/zweite Meldung/), B = by(/zweiter Fall/), A = by(/Kramgasse 5$/);
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, permissions: ["clipboard-read", "clipboard-write"] });
const page = await context.newPage();
let dialogs = 0, pageErrors = 0, refused = 0;
page.on("dialog", async (d) => { dialogs += 1; await d.accept(d.type() === "prompt" ? "3" : undefined); });
page.on("pageerror", (e) => { pageErrors += 1; console.log("page error: " + e.message); });
page.on("response", (r) => { if (r.status() === 422 && r.url().includes("/events")) refused += 1; });  // an element's event the route refused
const out = [];
const shot = async (name) => { if (!SHOTS) return; await page.screenshot({ path: `${SHOTS}/${name}-${tag}.png` }); await page.screenshot({ path: `${SHOTS}/${name}-${tag}-full.png`, fullPage: true }); };
const open = async (hash) => { await page.goto(`${BASE}/?lang=de#${hash}`); await sleep(2500); };
const events = async (id) => (await get(`/api/cases/${id}/events`)).events;

// Measures of the screen as it stands
const measure = () => page.evaluate(() => {
  const vis = (el) => { const r = el.getBoundingClientRect(), s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.opacity !== "0" && r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth; };
  const interactive = [...document.querySelectorAll("a[href], button, input:not([type=hidden]), select, textarea, summary, [contenteditable=true], [contenteditable=plaintext-only]")]
    .filter((el) => vis(el) && !el.closest("[hidden]") && (el.type !== "date" || getComputedStyle(el).opacity !== "0"));
  // Sentences a person would have to read to use the screen: everything outside the letter, its list and the case content.
  const letter = (el) => el.closest("[data-item], pre, .cp-checklist, .cp-letter");
  const blocks = new Set();  // each piece of text by the block it stands in
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const n = walker.currentNode;
    if (!n.textContent.trim() || letter(n.parentElement) || !n.parentElement.getClientRects().length) continue;
    let b = n.parentElement;
    while (b.parentElement && /^inline/.test(getComputedStyle(b).display)) b = b.parentElement;
    blocks.add(b);
  }
  const own = (b) => [...b.childNodes].map((c) => c.nodeType === 3 ? c.textContent : c.nodeType === 1 && /^inline/.test(getComputedStyle(c).display) && !letter(c) ? c.innerText : "\n").join("");
  const sentences = [...new Set([...blocks].flatMap((b) => own(b).split("\n")).map((t) => t.replace(/\s+/g, " ").trim()))].flatMap((t) => t.split(/(?<=[.:])\s+/))
    .filter((t) => /[.:]$/.test(t) && t.split(/\s+/).length >= 4);
  const primary = [...document.querySelectorAll(".cp-button.primary")].filter((el) => getComputedStyle(el).display !== "none");
  const p = primary[0], r = p && p.getBoundingClientRect();
  return { interactive: interactive.length, sentences, primaries: primary.map((x) => x.innerText.trim()), primaryInView: Boolean(r && r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth),
           pageHeight: document.documentElement.scrollHeight };
});
// A click as a person makes it: on what is in view, or after scrolling to it (counted).
const scroll = { page: 0, inner: 0 };
async function click(selector, what) {
  const el = await page.waitForSelector(selector, { state: "attached", timeout: 8000 })
    .catch(async (error) => { if (SHOTS) await page.screenshot({ path: `${SHOTS}/failed-${tag}.png` }); throw error; });
  let box = await el.boundingBox();
  const top = await page.evaluate(() => (document.querySelector(".cp-top") || { offsetHeight: 0 }).offsetHeight);  // under the fixed top bar is out of view
  const hidden = await el.evaluate((e) => { const r = e.getBoundingClientRect(), at = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return !at || !(e === at || e.contains(at) || at.contains(e) && at.tagName === "LABEL"); });
  if (!box || box.y < top || box.y + box.height > H || hidden) {
    const before = await page.evaluate(() => scrollY);
    await el.evaluate((e) => e.scrollIntoView({ block: "center" })); await sleep(300);
    const after = await page.evaluate(() => scrollY);
    if (after !== before) scroll.page += 1; else scroll.inner += 1;
    box = await el.boundingBox();
  }
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await sleep(1200);
  return what;
}

// 1. The case list
await open("/cases");
await shot("case-list");
const list = await measure();
out.push(`case list: ${list.interactive} interactive elements in view, primary "${list.primaries.join(", ")}" in view ${list.primaryInView}`);

// 2. The main path on case C: open, untick one line, copy, Erledigt
let clicks = 0;
dialogs = 0;
await click(`a[href*="${C}"]`, "open"); clicks += 1; await sleep(1500);
const prepared = await measure();
await shot("prepared-case");
out.push(`prepared (Übersicht): ${prepared.interactive} interactive elements above the fold; instruction sentences ${prepared.sentences.length}${prepared.sentences.length ? ": " + prepared.sentences.map((s) => `«${s.slice(0, 70)}»`).join(" ") : ""}; ` +
  `primary "${prepared.primaries.join(", ")}" in view ${prepared.primaryInView}`);
await click("[data-line]", "untick"); clicks += 1; await sleep(800);
await click("#copy-draft", "copy"); clicks += 1;
const afterCopy = await measure();
await click("[data-close='erledigt']", "done"); clicks += 1; await sleep(800);
const log = await events(C);
const kinds = ["letter.line", "letter.copied", "case.closed"].map((k) => `${k} ${log.some((e) => e.kind === k)}`).join(", ");
out.push(`main path: ${clicks} clicks${dialogs ? ` + ${dialogs} dialog(s)` : ""}, page scrolls ${scroll.page}, scrolls inside a box ${scroll.inner}; ` +
  `after copying the primary is "${afterCopy.primaries.join(", ")}"; events: ${kinds}`);
const closedState = await measure();
await shot("closed-case");
out.push(`closed: primary "${closedState.primaries.join(", ")}" (${closedState.primaries.length}) in view ${closedState.primaryInView}`);

if (!BEFORE) {
  // 3. Running and paused on case B: "Fall vorbereiten", then "Anhalten"
  await open(`/case/${B}/overview`);
  const fresh = await measure();
  out.push(`not prepared: primary "${fresh.primaries.join(", ")}" (${fresh.primaries.length}) in view ${fresh.primaryInView}`);
  await click("#start-run", "prepare");
  const started = Date.now();  // «Der Fall» fills in from the run's events; the viewer beside it shows what is read
  let filled = 0;
  for (let i = 0; i < 50 && !filled; i += 1) { await sleep(500); filled = await page.evaluate(() => document.querySelectorAll(".cp-live-case .cp-live-row").length); }
  const viewer = await page.evaluate(() => (document.querySelector("#overview-source .cp-doc-toolbar .name") || {}).innerText || null);
  const run = await measure();
  await shot("running-case");
  out.push(`running: primary "${run.primaries.join(", ")}" (${run.primaries.length}) in view ${run.primaryInView}; prepare button shown ${await page.$("#run, #start-run") !== null}; ` +
    `«Der Fall» filled during the run ${filled > 0} (${filled} row(s) after ${Math.round((Date.now() - started) / 1000)} s), viewer shows «${viewer}»`);
  await click("#stop-run", "stop");
  for (let i = 0; i < 30 && (await get(`/api/cases/${B}`)).run.status !== "paused"; i += 1) await sleep(1000);
  await sleep(2500);
  const paused = await measure();
  await shot("paused-case");
  out.push(`paused: primary "${paused.primaries.join(", ")}" (${paused.primaries.length}) in view ${paused.primaryInView}`);

  // 4. New files on case A, added in the rail: every button still works without a reload, the draft waits
  await open(`/case/${A}/overview`);
  const errorsBefore = pageErrors;
  await page.setInputFiles("#upload", { name: "Nachtrag.txt", mimeType: "text/plain", buffer: Buffer.from("Nachtrag der Mieterin: Fotos folgen.") });
  await sleep(2500);
  const arrived = await measure();
  await shot("new-files");
  await click("#add-note", "note"); const formOpens = await page.$("#note-form") !== null; await click("#note-cancel", "cancel");
  const blocked = await page.evaluate(() => Boolean((document.querySelector("#copy-draft") || {}).disabled) && Boolean(document.querySelector(".cp-letter.cp-stale")));
  await click("#use-anyway", "use anyway");
  const usable = await page.evaluate(() => (document.querySelector("#copy-draft") || { disabled: true }).disabled === false);
  const unblocked = (await events(A)).some((e) => e.kind === "letter.unblocked");
  out.push(`new files: primary "${arrived.primaries.join(", ")}" (${arrived.primaries.length}) in view ${arrived.primaryInView}; banner «${(await page.evaluate(() => (document.querySelector(".cp-runnow") || {}).innerText || "")).replace(/\s+/g, " ").slice(0, 90)}»; ` +
    `after adding a file in the rail: page errors ${pageErrors - errorsBefore}, a button works without reload ${formOpens}; draft held back ${blocked}, «trotzdem verwenden» unblocks it ${usable} (logged ${unblocked})`);

  // 5. Every handler gesture on case D leaves its event
  await open(`/case/${D}/overview`);
  const last = async (kind, test = () => true) => (await events(D)).filter((e) => e.kind === kind).some(test);
  const checks = [];
  const n0 = (await events(D)).length;
  await click("[data-line]", "untick"); await sleep(600); await click("[data-line-reason='3']", "reason");
  checks.push(["untick with reason", await last("letter.line", (e) => e.included === false && e.reason === "3")]);
  await page.fill("#add-doc", "Wohnungsabnahmeprotokoll"); await page.keyboard.press("Enter"); await sleep(600); await click("[data-add-doc-reason='4']", "add");
  const inLetter = await page.evaluate(() => [...document.querySelectorAll("[data-item='letter:0'] li[data-text]")].some((li) => li.dataset.text.includes("Wohnungsabnahmeprotokoll")));
  checks.push(["add a document (and it is ticked in the letter: " + inLetter + ")", await last("item.added", (e) => e.reason === "4")]);
  // the cover decision is not asked at intake on the card: the Prozess tab holds the stage's decisions
  await page.evaluate((id) => { location.hash = `#/case/${id}/process_builder`; }, D); await sleep(1500);
  await click("[data-decide='deckung'][data-value='bestätigt']", "decide");
  checks.push(["change a fact (Deckung bestätigen, Prozess)", await last("item.corrected", (e) => e.op === "set_fact" && e.item_id === "fact:deckung")]);
  await click("#undo", "undo");
  checks.push(["undo", await last("correction.undone")]);
  await page.evaluate((id) => { location.hash = `#/case/${id}/overview`; }, D); await sleep(1500);
  await page.click("[data-item='letter:0'] [data-seg='text']"); await page.keyboard.press("End"); await page.keyboard.type(" Mit freundlichem Gruss"); await sleep(300);
  await click("#copy-draft", "copy");
  checks.push(["reword the letter (copied as edited)", await last("letter.copied", (e) => e.edited === true)]);
  await click("#add-note", "note"); await page.fill("#note-form textarea", "Kundin ruft morgen zurück."); await click("#note-form button:not([type])", "save");
  checks.push(["note (an entry of the account)", await last("entry.added", (e) => e.text === "Kundin ruft morgen zurück.")]);
  await page.evaluate(() => { const i = document.querySelector("#followup-date"); i.value = "2026-12-20"; i.dispatchEvent(new Event("change")); }); await sleep(1500);
  checks.push(["follow-up date", await last("followup.set", (e) => e.date === "2026-12-20")]);
  await click("#change-action", "change"); await click("[data-pick-action='A5']", "pick"); await click("[data-action-reason='5']", "reason");
  const title = await page.evaluate(() => document.querySelector(".cp-prepared h2").textContent);
  checks.push([`andere Handlung (now «${title}»)`, await last("item.corrected", (e) => e.item_id === "next_action:0" && e.chosen === "A5")]);
  await page.goto(`${BASE}/?lang=de#/case/${D}/document_finder`); await sleep(2500);
  const counts = await page.evaluate(() => document.querySelector("h1.cp-title").innerText);
  await shot("documents-tab");
  out.push(`Unterlagen tab: «${counts}»`);
  await open(`/case/${D}/overview`);
  await click(".cp-split summary", "more"); await page.fill("#reservation", "Deckung nochmals prüfen"); await click("[data-close='erledigt_mit_vorbehalt']", "close");
  checks.push(["close with reservation", await last("case.closed", (e) => e.form === "erledigt_mit_vorbehalt" && e.text === "Deckung nochmals prüfen")]);
  out.push(`gestures (${(await events(D)).length - n0} events): ` + checks.map(([what, ok]) => `${what} ${ok ? "ok" : "MISSING"}`).join(" · "));
  const mine = await page.evaluate(() => document.body.innerText.includes("Ihre Änderungen"));
  await open(`/case/${D}/history`);
  const verlauf = await page.evaluate(() => ({ first: (document.querySelector(".cp-account-table tbody tr") || { className: "" }).className,
    gestures: document.querySelectorAll(".cp-account-table tr.cp-row-gesture").length, entries: document.querySelectorAll(".cp-account-table tr.cp-row-entry").length,
    tables: document.querySelectorAll("main table").length }));
  await shot("verlauf");
  out.push(`Verlauf: ${verlauf.tables} table, row 1 the report ${/cp-row-report/.test(verlauf.first)}, ${verlauf.gestures} gestures, ${verlauf.entries} entry; «Ihre Änderungen» on the Übersicht ${mine}`);
}
out.push(`events refused by the route: ${refused}; page errors: ${pageErrors}`);
console.log(`${tag}${BEFORE ? " (before)" : ""}\n` + out.join("\n"));
await browser.close();
