// The D11 episode on the preview, step by step, into a casepath.rehearsal/1 receipt (MEASURE §1): condition N on E1 or E2,
// and the baseline B0 of the same episode.
//   BASE=http://127.0.0.1:8805 EPISODE=e1 SESSION=1 OUT=/some/dir NODE_PATH=$(npm root -g) node deploy/preview/rehearse_episode.mjs
// MODE=scripted (default): the script takes every step itself, so the receipt holds the path's own clicks, scrolls, decisions
//   and confirmations as the screens make them. Its times are the machine's: the label says «scripted path», the receipt
//   names that asymmetry, and the declared external steps are not taken.
// MODE=rehearsal: a headed browser for the developer's rehearsal (two sessions, counterbalanced with the baseline B0). The
//   terminal names each step; the developer takes it and presses Enter.
// MODE=baseline: B0 without CasePath (the A5 form as a Word template, the files in a viewer, the module's law passages as
//   the search, a text file for the claims system and the diary), timed in the terminal; what no browser measures there
//   (clicks, scrolls, typing, passages) is null, never 0, and the receipt names that asymmetry.
// MODE=selftest: the timing rule and the edit adjudication on fixed inputs, printed as JSON (no browser, no preview).
// Time, the same rule for B0 and N: a step lasts from the prompt that names it to the Enter that ends it. Silent reading and
// reasoning count in full; nothing is capped. An interruption the developer declares («u», then Enter when back) is taken
// out of its step and kept as an entry of its own (timing.interruptions); the external steps are timed the same way.
// Counting, declared before any scoring: a decision is a click that records a judgment the expert owns ([data-decide],
// [data-cover-decline], the «Empfehlung» answers, «Freigeben», [data-action-reason], [data-line-reason], a question chip's
// «übernehmen»); a confirmation records a fact or moves text («Brief kopieren», «Versandt am», «Aktualisieren», the
// Versandpaket's download, «Aktennotiz kopieren»), counted apart. A passage is a document opened from a source chip;
// opened whole is a file or a document opened from the rail. A context switch is a change of route, and in a rehearsal
// each declared external window. A drop of files is one gesture.
// Edits, judged per edited part of the letter: substantive when it changes a fact (a date, an amount, a number, a legal
// citation), a polarity or negation, a state word (angenommen/abgelehnt, behoben/fortbestehend, bestätigt, erfüllt …), the
// recipient, a required part or the action, or adds or removes an answer, a way or a line to send in; stylistic only when
// nothing but punctuation, case, the notation of a date or an amount, or declared courtesy and function words changed;
// anything else (a changed word order included) «zu beurteilen» by a person, never guessed. The change ratio is reported and decides nothing. The draft and final text of every edited
// part are kept in OUT/inside/ (case content: inside only); the receipt holds part ids, verdicts, reasons and counts.
// A step that needs a part of the episode not built yet (A: the assessment; B: approval, copy and dispatch; C: the import,
// the duplicate's refusal and the update it starts; the integrator: the copy of E1 dispatched 91 days ago) stops the script
// with what is missing (exit 2, no receipt). KEEP_GOING=1 notes it, goes on where it can, and still writes no receipt.
import { createRequire } from "module";
import fs from "fs";
import path from "path";
import readline from "readline";
import { fileURLToPath } from "url";

const BASE = process.env.BASE || "http://127.0.0.1:8805", OUT = process.env.OUT || "", MODE = process.env.MODE || "scripted";
const EPISODE = (process.env.EPISODE || "e1").toLowerCase(), SESSION = Number(process.env.SESSION || 1), KEEP_GOING = process.env.KEEP_GOING === "1";
const TITLES = { e1: /D11-Analogon A\b(?!.*versandt)/, e2: /D11-Analogon B\b/ };  // E1, not its copy dispatched 91 days ago
const DISPATCHED = new RegExp(process.env.DISPATCHED || "D11-Analogon A.*(versandt|91)", "i");  // the copy of E1 dispatched 91 days ago
const REPLIES = path.join(path.dirname(fileURLToPath(import.meta.url)), "episode", EPISODE.toUpperCase());
const LABEL = MODE === "scripted" ? "scripted_path.synthetic_analog.no_handler_time" : "developer_rehearsal.synthetic_analog.handler_savings_unverified";
const RULE = MODE === "scripted" ? "machine" : "wall_minus_declared_interruptions";
const ASYMMETRY = { scripted: ["machine_time_not_handler_time", "external_steps_not_taken"], rehearsal: [],
                    baseline: ["counts_not_measured_without_a_browser"], selftest: [] }[MODE];
if (!["scripted", "rehearsal", "baseline", "selftest"].includes(MODE) || !TITLES[EPISODE] || ![1, 2].includes(SESSION)) {
  console.error("MODE scripted|rehearsal|baseline|selftest, EPISODE e1|e2, SESSION 1|2"); process.exit(2);
}

// -- time: one rule for both conditions ----------------------------------------------------------------------------------
const ask = (q) => new Promise((resolve) => {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  rl.question(q, (answer) => { rl.close(); resolve(answer || ""); });
});
const interruptions = [];
const activeMs = (start, end, paused) => end - start - paused.reduce((n, p) => n + p, 0);  // nothing capped, nothing guessed
async function timed(say, at) {  // from the prompt to the Enter that ends it; a declared interruption is an entry of its own
  const start = Date.now(), paused = [];
  while ((await ask(`${say} … Enter, wenn erledigt (u + Enter: Unterbrechung) `)).trim().toLowerCase() === "u") {
    const from = Date.now();
    await ask("Unterbrechung … Enter, wenn zurück ");
    paused.push(Date.now() - from);
    interruptions.push({ at, ms: paused[paused.length - 1] });
  }
  return activeMs(start, Date.now(), paused);
}

// -- edits: judged per part, never by a ratio ---------------------------------------------------------------------------
const STATE = /^(?:an(?:zu)?nehm|angenommen|ab(?:zu)?lehn|abgelehnt|bestätig|beheb|behob|fortbesteh|besteh|bestand|erfüll|unerfüll|genüg|ungenüg|bezahl|zahl|erhalt|versandt|versend|zugestellt|beigelegt|fehl|vorhanden|gewähr|verweiger|gedeckt|ungedeckt|deckung|anerkann|bestritt|offen|erledigt|abgeschlossen|zugesagt|zusag|widerruf|zurückgezog|aussicht)/;
const NEGATION = /^(?:nicht|kein|keine|keinen|keinem|keiner|keines|nie|niemals|ohne|weder|nichts)$/;
const OPTION = /^(?:hinterleg|kündig|herabsetz|reduk|reduz|minder|frist|rüge|mängelrüge|mahn|klage|klag|schlichtung|beseitig|ersatz|ersetz|auszieh|auszug|mandat|vergleich|einsprache|beschwerde|rekurs)/;
const CONDITION = /^(?:sofern|falls|sobald|soweit|wenn|vorbehalt|vorausgesetzt|bedingt|bedingung)$/;
const STYLE = new Set(["bitte", "gerne", "gern", "vielen", "besten", "herzlichen", "herzlich", "freundliche", "freundlichen", "dank", "danke", "sehr",
  "geehrte", "geehrter", "geehrten", "guten", "tag", "grüezi", "liebe", "lieber", "grüsse", "grüssen", "gruss",
  "nochmals", "höflich", "also", "nun", "ja", "eben", "einfach", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer",
  "und", "sie", "ihnen", "ihre", "ihr", "ihrer", "wir", "uns", "unsere", "unser", "es", "zu", "für", "mit"]);
const DATE = /\b\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}\b|\b\d{1,2}\.\s+(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+\d{4}\b|\b\d{4}-\d{2}-\d{2}\b/g;
const AMOUNT = /(?:CHF|Fr\.)\s?[\d'’.,]+(?:\.–|\.-)?|[\d'’]+(?:\.\d{2})?\s?(?:CHF|Franken)\b|\b\d[\d'’]*\.–/g;
const CITATION = /\bArt\.\s?\d+[a-z]?(?:\s(?:Abs\.|lit\.|Ziff\.)\s?\w+)*(?:\s[A-ZÄÖÜ][A-Za-zÄÖÜäöü]*)?/g;
const tokens = (t) => (t.toLowerCase().match(/[a-zäöüß0-9]+/g) || []);
const bag = (xs) => xs.reduce((m, x) => m.set(x, (m.get(x) || 0) + 1), new Map());
const minus = (a, b) => { const out = []; for (const [k, n] of a) for (let i = 0; i < n - (b.get(k) || 0); i += 1) out.push(k); return out; };
const same = (xs, ys) => xs.length === ys.length && xs.every((x, i) => x === ys[i]);
const MONTHS = ["januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "dezember"];
const dayOf = (m) => {  // one day however it is written: 30.11.2026, 30.11.26, 30. November 2026 and 2026-11-30 are the same
  const x = m.replace(/\s+/g, " ").trim();
  let r = x.match(/^(\d{4})-(\d{2})-(\d{2})$/), d, mo, y;
  if (r) [y, mo, d] = [r[1], r[2], r[3]];
  else if ((r = x.match(/^(\d{1,2})\. ?(\d{1,2})\. ?(\d{2,4})$/))) [d, mo, y] = [r[1], r[2], r[3]];
  else if ((r = x.match(/^(\d{1,2})\. (\S+) (\d{4})$/))) [d, mo, y] = [r[1], String(MONTHS.indexOf(r[2].toLowerCase()) + 1), r[3]];
  else return x;
  return `${y.length === 2 ? `20${y}` : y}-${mo.padStart(2, "0")}-${d.padStart(2, "0")}`;
};
const amountOf = (m) => {  // one amount however it is written: CHF 85, Fr. 85.–, CHF 85.00 and 85 Franken are the same
  const x = m.replace(/CHF|Fr\.|Franken/g, "").replace(/[’'\s]/g, "").replace(/\.[–-]$/, "").replace(/[.,]$/, "").replace(/,(\d{2})$/, ".$1").replace(/,/g, "");
  return Number.isFinite(Number(x)) && x ? String(Math.round(Number(x) * 100)) : x;
};
const found = (re, t, norm = (x) => x.replace(/\s+/g, " ")) => (t.match(re) || []).map(norm).sort();
// the words of a part, its dates, amounts and citations each one word of its value: a change of notation alone changes none
const plain = (t) => t.replace(DATE, (m) => ` d${dayOf(m).replace(/-/g, "")} `).replace(AMOUNT, (m) => ` a${amountOf(m)} `)
  .replace(CITATION, (m) => ` c${m.replace(/[^A-Za-z0-9]/g, "").toLowerCase()} `);
function slotOf(part, text) {
  const t = String(text || "").trim();
  if (part === "head" || /^(Sehr geehrte|Guten Tag)/.test(t)) return "head";
  if (/^In Ihrem Fall/.test(t)) return "im_fall";
  if (/^(Zu Ihren Fragen|– «)/.test(t)) return "zu_fragen";
  if (/^Wir empfehlen Ihnen/.test(t)) return "empfehlung";
  if (/^Bitte reichen Sie uns noch nach/.test(t)) return "nachzureichen";
  return "other";
}
// One edited part: {verdict: substantive | stylistic | zu_beurteilen, reasons}
function judge(part, draft, final, required = []) {
  draft = String(draft || ""); final = String(final || "");
  const reasons = [], slot = slotOf(part, draft || final);
  if (!same(found(DATE, draft, dayOf), found(DATE, final, dayOf))) reasons.push("date");
  if (!same(found(AMOUNT, draft, amountOf), found(AMOUNT, final, amountOf))) reasons.push("amount");
  if (!same(found(CITATION, draft), found(CITATION, final))) reasons.push("citation");
  const a = tokens(plain(draft)), b = tokens(plain(final)), gone = minus(bag(a), bag(b)), come = minus(bag(b), bag(a));
  if (!same(a.filter((x) => /^\d+$/.test(x)).sort(), b.filter((x) => /^\d+$/.test(x)).sort()) && !reasons.length) reasons.push("number");
  if (a.filter((x) => NEGATION.test(x)).length !== b.filter((x) => NEGATION.test(x)).length) reasons.push("negation");
  if ([...gone, ...come].some((x) => STATE.test(x))) reasons.push("state");
  if ([...gone, ...come].some((x) => OPTION.test(x))) reasons.push("option");
  if ([...gone, ...come].some((x) => CONDITION.test(x))) reasons.push("condition");
  if (slot === "head" && [...gone, ...come].some((x) => !STYLE.has(x))) reasons.push("recipient");
  if (required.some((m) => draft.includes(m) && !final.includes(m))) reasons.push("required_part");
  const lines = (t) => t.split("\n").map((l) => l.trim()).filter((l) => /^– /.test(l));
  if (["zu_fragen", "empfehlung", "nachzureichen"].includes(slot) && lines(draft).length !== lines(final).length) reasons.push("answer_added_or_removed");
  if (!draft.trim() !== !final.trim() && slot !== "other" && !reasons.includes("answer_added_or_removed")) reasons.push("part_added_or_removed");
  if (reasons.length) return { verdict: "substantive", reasons };
  const content = (xs) => xs.filter((x) => !STYLE.has(x));  // stylistic only when the words that carry content stand as they stood
  if (same(content(a), content(b))) return { verdict: "stylistic", reasons: [gone.length || come.length ? "courtesy_or_function_words" : "punctuation_case_or_notation"] };
  return { verdict: "zu_beurteilen", reasons: [same([...content(a)].sort(), [...content(b)].sort()) ? "word_order_changed" : "content_words_changed"] };
}
// The letter as parts: the case view's parts where it gives them (draft.parts), else its paragraphs (para.<i>)
const partsOf = (draft, text) => {
  const given = (draft || {}).parts;
  if (Array.isArray(given) && given.length) return given.map((p) => Array.isArray(p) ? { part: String(p[0]), text: String(p[1] || "") } : { part: String(p.part || p.id), text: String(p.text || "") });
  return String(text || "").split(/\n\s*\n/).map((t, i) => ({ part: `para.${i}`, text: t.trim() })).filter((p) => p.text);
};
function pairParts(before, after) {  // by part id where the view gives ids; paragraphs by an alignment that keeps unchanged ones in place
  if (before.every((p) => !p.part.startsWith("para.")) || after.every((p) => !p.part.startsWith("para."))) {
    const ids = [...new Set([...before.map((p) => p.part), ...after.map((p) => p.part)])];
    return ids.map((id) => ({ part: id, draft: (before.find((p) => p.part === id) || {}).text || "", final: (after.find((p) => p.part === id) || {}).text || "" }));
  }
  const x = before.map((p) => p.text), y = after.map((p) => p.text), n = x.length, m = y.length;
  const L = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i -= 1) for (let j = m - 1; j >= 0; j -= 1) L[i][j] = x[i] === y[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const out = []; let i = 0, j = 0, gone = [], come = [];
  const flush = () => { for (let k = 0; k < Math.max(gone.length, come.length); k += 1) out.push({ part: gone[k] != null ? `para.${gone[k]}` : `para.new.${come[k]}`, draft: gone[k] != null ? x[gone[k]] : "", final: come[k] != null ? y[come[k]] : "" }); gone = []; come = []; };
  while (i < n || j < m) {
    if (i < n && j < m && x[i] === y[j]) { flush(); out.push({ part: `para.${i}`, draft: x[i], final: y[j] }); i += 1; j += 1; }
    else if (j < m && (i === n || L[i][j + 1] >= L[i + 1][j])) { come.push(j); j += 1; } else { gone.push(i); i += 1; }
  }
  flush();
  return out;
}
const words = (t) => String(t).split(/\s+/).filter(Boolean);
const lcs = (a, b) => { let prev = new Array(b.length + 1).fill(0);
  for (const x of a) { const row = [0]; for (let j = 0; j < b.length; j += 1) row.push(x === b[j] ? prev[j] + 1 : Math.max(prev[j + 1], row[j])); prev = row; }
  return prev[b.length]; };
const ratio = (a, b) => { const x = words(a), y = words(b); return x.length || y.length ? Math.round((1 - lcs(x, y) / Math.max(x.length, y.length)) * 1000) / 1000 : 0; };
function adjudicate(pairs, { required = [], formBefore = null, formAfter = null } = {}) {
  const parts = [];
  if (formBefore !== formAfter) parts.push({ part: "letter", verdict: "substantive", reasons: ["action"] });
  for (const p of pairs) if (p.draft !== p.final) parts.push({ part: p.part, ...judge(p.part, p.draft, p.final, required) });
  const slots = { im_fall: 0, zu_fragen: 0, empfehlung: 0, nachzureichen: 0, other: 0 };
  for (const slot of Object.keys(slots)) {
    const mine = pairs.filter((p) => { const s = slotOf(p.part, p.draft || p.final); return s === slot || (slot === "other" && s === "head"); });
    slots[slot] = ratio(mine.map((p) => p.draft).join("\n"), mine.map((p) => p.final).join("\n"));
  }
  const count = (v) => parts.filter((p) => p.verdict === v).length;
  return { ratio_words: ratio(pairs.map((p) => p.draft).join("\n"), pairs.map((p) => p.final).join("\n")), substantive: count("substantive"),
           stylistic: count("stylistic"), zu_beurteilen: count("zu_beurteilen"), parts, slots };
}

if (MODE === "selftest") {
  const pair = (draft, final) => judge("para.0", draft, final);
  console.log(JSON.stringify({
    timing: { silent_five_minutes: { b0: activeMs(0, 300000, []), n: activeMs(0, 300000, []) },
              interrupted: { b0: activeMs(0, 300000, [120000]), n: activeMs(0, 300000, [120000]) } },
    edits: {
      accept_to_refuse: pair("Wir empfehlen Ihnen, das Angebot anzunehmen.", "Wir empfehlen Ihnen, das Angebot abzulehnen."),
      remedied_to_persisting: pair("Der Mangel ist nach Ihren Angaben behoben.", "Der Mangel ist nach Ihren Angaben fortbestehend."),
      courtesy: pair("Vielen Dank für Ihre Unterlagen.", "Besten Dank für Ihre Unterlagen."),
      punctuation: pair("Wir prüfen Ihre Unterlagen und melden uns.", "Wir prüfen Ihre Unterlagen, und melden uns!"),
      greeting: judge("head", "Sehr geehrte Frau Exempel", "Guten Tag Frau Exempel"),
      date_notation: pair("Bitte antworten Sie bis 30.11.2026.", "Bitte antworten Sie bis 30. November 2026."),
      amount_notation: pair("Sie machen Stromkosten von CHF 85 geltend.", "Sie machen Stromkosten von Fr. 85.– geltend."),
      negation: pair("Der Mangel ist behoben.", "Der Mangel ist nicht behoben."),
      date: pair("Bitte antworten Sie bis 30.11.2026.", "Bitte antworten Sie bis 07.12.2026."),
      amount: pair("Sie machen Stromkosten von CHF 85 geltend.", "Sie machen Stromkosten von CHF 58 geltend."),
      recipient: judge("head", "Sehr geehrte Frau Exempel", "Sehr geehrter Herr Probe"),
      required: judge("p4", "Wir beurteilen das Vorgehen als aussichtslos, weil …", "Wir haben Ihre Unterlagen geprüft.", ["beurteilen wir das Vorgehen als aussichtslos", "Vorgehen als aussichtslos"]),
      answer_removed: judge("p4", "Zu Ihren Fragen:\n– «Q1» A1.\n– «Q2» A2.", "Zu Ihren Fragen:\n– «Q1» A1."),
      content_word: pair("Wir empfehlen Ihnen, der Vermieterschaft zu schreiben.", "Wir empfehlen Ihnen, der Vermieterschaft rasch zu schreiben."),
      word_order: pair("Wir prüfen zuerst die Rechnung, dann den Vertrag.", "Wir prüfen zuerst den Vertrag, dann die Rechnung."),
      option: pair("Wir empfehlen Ihnen, eine Frist zur Beseitigung zu setzen.", "Wir empfehlen Ihnen, den Mietzins zu hinterlegen."),
      condition: pair("Wir empfehlen Ihnen, der Vermieterschaft zu schreiben.", "Wir empfehlen Ihnen, der Vermieterschaft zu schreiben, sofern der Schimmel noch da ist."),
    },
    letter: adjudicate(pairParts(partsOf(null, "Sehr geehrte Frau Exempel\n\nVielen Dank für Ihre Unterlagen.\n\nDer Mangel ist behoben."),
                                 partsOf(null, "Sehr geehrte Frau Exempel\n\nBesten Dank für Ihre Unterlagen.\n\nDer Mangel ist fortbestehend.")),
                       { formBefore: "A5", formAfter: "A5" }),
    action: adjudicate([], { formBefore: "A5", formAfter: "A6" }).parts,
  }, null, 1));
  process.exit(0);
}

const steps = [], external = [], started = Date.now();
const write = (receipt, inside) => {
  if (!OUT) return null;
  const name = `rehearsal-${EPISODE}-${receipt.condition}-session${SESSION}${receipt.condition === "n" ? `-${MODE}` : ""}`;
  fs.mkdirSync(path.join(OUT, "inside"), { recursive: true });
  fs.writeFileSync(path.join(OUT, `${name}.json`), JSON.stringify(receipt, null, 1) + "\n");
  if (inside) fs.writeFileSync(path.join(OUT, "inside", `${name}.parts.json`), JSON.stringify(inside, null, 1) + "\n");  // case content: inside only
  return path.join(OUT, `${name}.json`);
};

// -- B0: the same episode without CasePath, timed by the same rule; each step's declared window is a switch ----------------
if (MODE === "baseline") {
  const B0 = [["open_case", "den Fall im Text-Fallsystem öffnen", 1], ["read_reply", "die beiden Antworten im Viewer lesen", 1],
              ["reconstruct", "aus der Akte rekonstruieren, was verlangt, versprochen und beantwortet ist", 0],
              ["deckung", "über die Deckung entscheiden", 0], ["research", "die Gesetzesstellen des Moduls nachschlagen", 1],
              ["empfehlung", "die Empfehlung festlegen", 0], ["write_letter", "die Einschätzung in der Word-Vorlage schreiben", 1],
              ["review", "den Brief prüfen", 0]];
  for (const [name, say, window] of B0) {
    const n = steps.length + 1;
    steps.push({ n, name, ms: await timed(`B0 Schritt ${n}: ${say}`, `step:${n}`), clicks: null, decisions: ["deckung", "empfehlung"].includes(name) ? 1 : 0,
                 confirmations: 0, edits: null, chars: null, switches: window, opened_whole: null, passages: null, scrolls: { page: null, inner: null } });
  }
  for (const [name, say] of [["paste_email", "in die Antwort-E-Mail einfügen"], ["attach_template", "die Vorlage anhängen"], ["send", "senden"],
                             ["paste_note", "die Aktennotiz ins Text-Fallsystem schreiben"], ["set_diary", "die Wiedervorlage setzen"]]) {
    await ask(`Extern: ${say}. Enter zum Beginn `);
    external.push({ name, ms: await timed(`Extern: ${say}`, `external:${name}`) });
  }
  const receipt = { format: "casepath.rehearsal/1", label: LABEL, build: "none", episode: EPISODE, condition: "b0", session: SESSION, steps, external,
                    edit: { ratio_words: null, substantive: null, stylistic: null, zu_beurteilen: null, parts: [], slots: {} }, events: {},
                    duplicate_refused: null, timing: { rule: RULE, interruptions, asymmetry: ASYMMETRY }, wall_ms: Date.now() - started, model_tokens: 0 };
  write(receipt, null);
  console.log(`B0 · ${EPISODE} · session ${SESSION}: ${steps.reduce((n, x) => n + x.ms, 0)} ms in ${steps.length} steps, external `
              + `${external.reduce((n, x) => n + x.ms, 0)} ms, ${interruptions.length} interruption(s) taken out`);
  process.exit(0);
}

// -- N: the episode in the preview -------------------------------------------------------------------------------------
const { chromium } = createRequire(import.meta.url)("playwright");
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
const visible = async (locator) => (await locator.count()) > 0 && await locator.first().isVisible().catch(() => false);
const button = (name) => page.getByRole("button", { name });

// One step: in a rehearsal the developer takes it and its time is the shared rule's; scripted, the machine's time
async function step(name, act, say) {
  const n = steps.length + 1, from = log.length, start = Date.now();
  let ms;
  if (MODE === "rehearsal") ms = await timed(`Schritt ${n}: ${say}`, `step:${n}`);
  else { await act(); await sleep(400); ms = Date.now() - start; }
  const mine = log.slice(from), clicks = mine.filter((e) => e.type === "click" || e.type === "drop");
  steps.push({ n, name, ms, clicks: clicks.length, decisions: clicks.filter((e) => e.decision).length,
               confirmations: clicks.filter((e) => e.confirmation).length, edits: mine.filter((e) => e.type === "input").length,
               chars: mine.filter((e) => e.type === "input").reduce((k, e) => k + e.chars, 0), switches: mine.filter((e) => e.type === "route").length,
               opened_whole: clicks.filter((e) => e.whole).length, passages: clicks.filter((e) => e.passage).length,
               scrolls: { page: mine.filter((e) => e.type === "scroll" && e.page).length, inner: mine.filter((e) => e.type === "scroll" && !e.page).length } });
}
async function outside(name, say) {  // a declared external step: timed by the shared rule in a rehearsal, not taken by the script
  if (MODE !== "rehearsal") return;
  await ask(`Extern: ${say}. Enter zum Beginn `);
  external.push({ name, ms: await timed(`Extern: ${say}`, `external:${name}`) });
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
const draftBefore = (await get(`/api/cases/${id}`)).draft || {};  // the prepared letter, by part where the view gives parts
const textBefore = await letterText();
await step("edits", async () => {
  const part = page.locator("[data-item='letter:0'] [data-seg='text'], [data-item='letter:0'] [contenteditable]").first();
  if (!(await part.count())) return lacking("the letter's text can be changed in place");
  await part.click(); await page.keyboard.press("End"); await page.keyboard.type(" Vielen Dank für Ihre Geduld."); await sleep(1600);
}, "den Brief anpassen, wo nötig");
const textAfter = await letterText();
await step("freigeben", async () => {
  const approve = button(/^Freigeben$/);
  if (await visible(approve)) return click(approve, "approve");
  lacking("B: «Freigeben» stores the approval and the Versandpaket (B3)");
}, "freigeben");
const draftAfter = (await get(`/api/cases/${id}`)).draft || {};  // the approved letter (B), by part
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

// The edits, judged per part: the prepared letter against the approved one (the server's parts once B stores them)
const pairs = pairParts(partsOf(draftBefore.parts ? draftBefore : null, textBefore), partsOf(draftAfter.parts ? draftAfter : null, textAfter));
const edit = adjudicate(pairs, { required: (draftBefore.required || []).map((r) => r.marker).filter(Boolean), formBefore: draftBefore.form || null,
                                 formAfter: draftAfter.form || null });
const inside = { note: "INSIDE ONLY: the draft and the final text of every edited part; never part of a receipt",
                 parts: Object.fromEntries(pairs.filter((p) => p.draft !== p.final).map((p) => [p.part, { draft: p.draft, final: p.final,
                   ...(edit.parts.find((x) => x.part === p.part) || {}) }])) };

// The receipt: ids, counts and enums only
const kinds = {};
for (const e of (await get(`/api/cases/${id}/events`)).events || []) kinds[e.kind] = (kinds[e.kind] || 0) + 1;
const build = String((await get("/api/manifest")).source_tree_sha256 || "").slice(0, 12);
const receipt = { format: "casepath.rehearsal/1", label: LABEL, build, episode: EPISODE, condition: "n", session: SESSION, steps, external, edit,
  events: kinds, duplicate_refused: duplicateRefused, timing: { rule: RULE, interruptions, asymmetry: ASYMMETRY }, wall_ms: Date.now() - started,
  model_tokens: 0 };
const safe = (v) => typeof v !== "string" || (/^(?:[a-z0-9][a-z0-9_.:-]{0,79})$/.test(v) && !/\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4}/.test(v));
const leaks = JSON.stringify(receipt, (k, v) => (k === "format" || safe(v) ? v : "LEAK")).includes("LEAK");
const line = (s) => `${String(s.n).padStart(2)} ${s.name.padEnd(22)} ${String(s.ms).padStart(7)} ms · ${s.clicks} click(s) · ${s.decisions} decision(s) · ${s.confirmations} confirmation(s)`
  + `${s.edits ? ` · ${s.edits} input(s), ${s.chars} char(s)` : ""}${s.switches ? ` · ${s.switches} switch(es)` : ""}${s.passages ? ` · ${s.passages} passage(s)` : ""}`
  + `${s.opened_whole ? ` · ${s.opened_whole} opened whole` : ""}${s.scrolls.page + s.scrolls.inner ? ` · scrolls ${s.scrolls.page}/${s.scrolls.inner}` : ""}`;
console.log([`${LABEL} · ${EPISODE} · session ${SESSION} · build ${build} · time ${RULE}${ASYMMETRY.length ? ` (asymmetry: ${ASYMMETRY.join(", ")})` : ""}`,
  ...steps.map(line),
  `decisions ${steps.reduce((n, s) => n + s.decisions, 0)} · confirmations ${steps.reduce((n, s) => n + s.confirmations, 0)} (counted apart) · interruptions ${interruptions.length}`,
  `edits: substantive ${edit.substantive}, stylistic ${edit.stylistic}, zu beurteilen ${edit.zu_beurteilen} (change ratio ${edit.ratio_words}, deciding nothing)`
  + ` · duplicate refused ${duplicateRefused} · page errors ${pageErrors}`].join("\n"));
if (leaks) { console.log("the receipt holds more than ids, counts and enums: not written"); await finish(2); }
if (!missing.length && OUT) console.log(`receipt: ${write(receipt, inside)}`);
} catch (error) {
  if (!(error instanceof Missing)) throw error;
  console.log(`stopped at the first missing part (KEEP_GOING=1 lists them all)`);
}
await finish(missing.length ? 2 : 0);
