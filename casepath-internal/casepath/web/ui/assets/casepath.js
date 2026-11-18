"use strict";
// CasePath internal workspace: one page on the live API. Everything shown comes from
// the case store, the agents' recorded work and the Knowledge base; nothing is staged.

// Case workers read German; English is the same product for a reader of English. The language is switched in place
// (no reload) and remembered in this browser; ?lang=en opens in English.
let LANG = (() => {
  const asked = new URLSearchParams(location.search).get("lang");
  try {
    if (asked) localStorage.setItem("casepath.lang", asked);
    return asked || localStorage.getItem("casepath.lang");
  } catch (error) { return asked; }
})() === "en" ? "en" : "de";
const T = (en, de) => (LANG === "de" ? de : en);
document.documentElement.lang = LANG;
// A wording fixed once (a list of names, a table of words) is made when it is read, so it follows the language.
const pageIn = () => { const now = S.pageIn; S.pageIn = false; return now ? " cp-page-in" : ""; };
const lazy = (make) => { let lang = null, value; return () => { if (lang !== LANG) { lang = LANG; value = make(); } return value; }; };
// What the case says, in the reader's language. Cases are worked in German; for another language the server sends, with
// each answer, the translation of the texts in it ("_tr"). Text is shown through esc(), which shows the translation
// where there is one; what is stored, sent or put into a field goes through raw() and is always the original.
const TR = new Map();
const reading = () => LANG !== "de";
// For whoever keeps the translation memory: with casepath.trmiss set in this browser, the texts shown untranslated are
// collected (window.casepathMissing()).
const TR_MISS = (() => { try { return localStorage.getItem("casepath.trmiss") ? new Set() : null; } catch (error) { return null; } })();
if (TR_MISS) window.casepathMissing = () => [...TR_MISS];
const TR_NONE = new Set();  // texts looked up without a translation, so a redraw does not look again
function trWhole(value) {
  const hit = TR.get(value);
  if (hit !== undefined) return hit;
  const core = value.trim();
  const inner = core === value ? undefined : TR.get(core);
  return inner === undefined ? undefined : value.replace(core, () => inner);
}
// A text put together from parts («Frage: …», «… · …»): each part in the reader's language where it is known.
function trParts(value, depth = 0) {
  for (const sep of [" · ", ": ", "; ", " – "]) {
    if (!value.includes(sep)) continue;
    let any = false;
    const out = value.split(sep).map((part) => {
      const t = trWhole(part) ?? (depth < 2 ? trParts(part, depth + 1) : undefined);
      if (t !== undefined) any = true;
      return t ?? part;
    });
    if (any) return out.join(sep);
  }
  return undefined;
}
function tr(value) {
  if (!reading() || typeof value !== "string" || !value || TR_NONE.has(value)) return value;
  const hit = trWhole(value) ?? trParts(value);
  if (hit !== undefined) { if (!TR.has(value)) TR.set(value, hit); return hit; }
  TR_NONE.add(value);
  if (TR_MISS && /[A-Za-zÄÖÜäöüß]{3}/.test(value)) TR_MISS.add(value.trim());
  wantTranslation(value.trim());
  return value;
}
// What the page showed untranslated is asked for, a little later and all at once, and the page is drawn again when it
// is there. Only what is shown is ever asked, each text once. The memory answers at once and costs nothing (a name the
// page shortened or put together itself is known to it, though no answer of the API carried it); the model is asked
// only where the deployment lets it translate.
const TR_ASK = new Set(), TR_ASKED = new Set();
const translates = () => S.translateMode === "memory" || S.translateMode === "model";
function wantTranslation(text) {
  if (!translates() || text.length < 3 || text.length > 700 || TR_ASKED.has(text) || !/[A-Za-zÄÖÜäöüß]{3}/.test(text)) return;
  if (/^[\w.+-]+@[\w.-]+$|^(case|file|run)_[0-9a-f]+$|\.(eml|msg|pdf|docx?|txt|png|jpe?g)$/i.test(text)) return;  // an address, an id, a file name
  TR_ASK.add(text);
  clearTimeout(S.trAskTimer);
  S.trAskTimer = setTimeout(askTranslations, 500);
}
async function askTranslations(again, tries = 0) {
  if (!reading() || !translates()) { TR_ASK.clear(); return; }
  const texts = again || [...TR_ASK].slice(0, 300);
  if (!again) for (const t of texts) { TR_ASK.delete(t); TR_ASKED.add(t); }
  if (!texts.length) return;
  const before = TR.size, where = `${S.route.view}:${S.route.id || ""}:${LANG}`;
  let res;
  try { res = await api("/api/translate", { method: "POST", body: JSON.stringify({ lang: LANG, texts, ...(S.route.view === "case" ? { case_id: S.route.id } : {}) }) }); }
  catch (error) { S.trWait = 0; return; }
  S.trWait = res._tr_wait || 0;
  if (where !== `${S.route.view}:${S.route.id || ""}:${LANG}`) return;  // the reader went on: what came is kept for the next look
  if (TR.size !== before || (!S.trWait && S.translateMode === "model")) {  // something arrived, or all of it: the page says it in the reader's language now
    const typing = document.activeElement && document.activeElement.closest && document.activeElement.closest("input, textarea, [contenteditable='true']");
    if (!typing) { if (S.route.view === "case") { if (S.data) await renderCase(); } else if (S.route.view === "cases") await renderCases(true); else await route(); } else renderTop();
  }
  if (S.trWait && tries < 40) setTimeout(() => askTranslations(texts.filter((t) => !TR.has(t)), tries + 1), 3000);
  if (TR_ASK.size) { clearTimeout(S.trAskTimer); S.trAskTimer = setTimeout(askTranslations, 500); }
}
function learn(body) {
  if (!body || typeof body !== "object" || !body._tr) return;
  if (TR.size > 40000) TR.clear();
  for (const [k, v] of Object.entries(body._tr)) TR.set(k, v);
  TR_NONE.clear();
}
const WORDS = {
  completed: "abgeschlossen", failed: "fehlgeschlagen", running: "läuft", queued: "wartet", interrupted: "unterbrochen", paused: "angehalten", discarded: "verworfen",
  present: "vorhanden", missing: "fehlt", unusable: "unbrauchbar", unchecked: "nicht geprüft", contradicted: "widersprochen",
  not_found: "nicht gefunden", confirmed: "bestätigt", conflicting: "widersprüchlich", established: "belegt", presumed: "vermutet", unknown: "unbekannt", active: "aktiv", candidate: "Vorschlag", retired: "zurückgezogen",
  reviewed: "geprüft", draft: "Entwurf", document_need: "Dokument", question: "Frage", step: "Schritt", note: "Hinweis",
  applied: "angewendet", absent: "fehlt",
};
const word = (value) => (LANG === "de" && WORDS[value]) || String(value ?? "").replace(/_/g, " ");
const TOOL_DE = { list_files: "listet die Dateien", open_process: "öffnet den Prozess", view_knowledge: "sieht das Wissen durch", evaluate: "wertet den Prozess aus",
                  get_findings: "holt die Feststellungen", record_fact: "hält eine Feststellung fest", record_document: "hält ein Dokument fest", propose_change: "schlägt eine Prozessänderung vor" };

// What each agent is doing, in the interface language; the lead's own instructions to the agents stay in the run record.
const TASK = lazy(() => ({
  lead: T("Prepare the case", "Den Fall vorbereiten"),
  claim_reader: T("Read the files and record the facts", "Dokumente lesen und Fakten festhalten"),
  process_builder: T("Build this case’s process", "Den Prozess dieses Falls aufbauen"),
  document_finder: T("Find each needed document in the files", "Jedes verlangte Dokument in den Dateien finden"),
  source_checker: T("Check each finding against its quote", "Jede Feststellung an ihrem Zitat prüfen"),
  result_checker: T("Evaluate, draft the reply and propose what to learn", "Auswerten, Antwort entwerfen, Lernvorschläge machen"),
}));

const ICONS = {
  doc: '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M9.5 12h6M9.5 15.5h6M9.5 9h3"/>',
  mail: '<rect x="3" y="5.5" width="18" height="13" rx="1.5"/><path d="m3.5 7 8.5 6.5L20.5 7"/>',
  image: '<rect x="3.5" y="4.5" width="17" height="15" rx="1.5"/><circle cx="9" cy="10" r="1.8"/><path d="m4 18 5.5-5 4 3.5 2.5-2 4 3.5"/>',
  shield: '<path d="M12 3 5 6v5.5c0 4.3 3 7.7 7 9.5 4-1.8 7-5.2 7-9.5V6z"/><path d="m9 12 2.2 2.2L15.5 10"/>',
  nodes: '<circle cx="12" cy="5.5" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M12 8v3.5M6 15.5V13.5h12v2M12 11.5v2"/>',
  folder: '<path d="M3.5 6.5h6l2 2h9v10.5h-17z"/>',
  chart: '<path d="M4.5 19.5h15M7.5 16v-5M12 16V6.5M16.5 16v-7.5"/>',
  clock: '<circle cx="12" cy="12" r="8"/><path d="M12 7.5V12l3 2"/>',
  book: '<path d="M4.5 5.5c2.5-.8 5-.8 7.5.5v13c-2.5-1.3-5-1.3-7.5-.5zM19.5 5.5c-2.5-.8-5-.8-7.5.5v13c2.5-1.3 5-1.3 7.5-.5z"/>',
  list: '<path d="M8.5 7h11M8.5 12h11M8.5 17h11M4.5 7h.01M4.5 12h.01M4.5 17h.01"/>',
  check: '<circle cx="12" cy="12" r="8.5"/><path d="m8.2 12.3 2.6 2.6 5-5.4"/>',
  tick: '<path d="m6.5 12.5 3.6 3.6 7.4-8"/>',
  pencil: '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
  xcircle: '<circle cx="12" cy="12" r="8.5"/><path d="m9 9 6 6m0-6-6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  left: '<path d="M19 12H5m5-5-5 5 5 5"/>',
  right: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9M18 14v6H4V6h6"/>',
  memory: '<path d="M12 3 5 6v5.5c0 4.3 3 7.7 7 9.5 4-1.8 7-5.2 7-9.5V6z"/>',
  law: '<path d="M12 4v16M5 8h14M7 8l-3 6h6zm10 0-3 6h6zM8 20h8"/>',
  evidence: '<path d="M7 3h7l4 4v14H7z"/><path d="m9.5 13 2 2 3.5-4"/>',
  search: '<circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/>',
};
const icon = (name, cls = "") => `<svg class="cp-icon ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ICONS.doc}</svg>`;
const AGENTS = lazy(() => ([
  ["claim_reader", T("Claim reader", "Fallleser"), "doc"], ["source_checker", T("Source checker", "Quellenprüfer"), "shield"],
  ["process_builder", T("Process builder", "Prozessbauer"), "nodes"], ["document_finder", T("Document finder", "Dokumentenfinder"), "folder"],
  ["result_checker", T("Result checker", "Ergebnisprüfer"), "check"],
]));
const AGENT_TITLE = new Proxy({}, { get: (_, id) => (id === "lead" ? T("Lead", "Leitung") : (AGENTS().find(([a]) => a === id) || [])[1]) });
const AGENT_ICON = Object.fromEntries(AGENTS().map(([id, , i]) => [id, i]).concat([["lead", "nodes"]]));
const raw = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const esc = (value) => raw(tr(value));
const plain = raw;  // the original, where a local name hides raw()
const $ = (selector, root = document) => root.querySelector(selector);
// The insurer this deployment works for (/api/health «house»): its name and how it names its policy conditions. Until
// the answer is here the built-in house's words stand.
const HOUSE = { name: "Protekta", conditions: { short: "AVB", name_inflected: "Allgemeinen Bedingungen" } };
let listMineStored = false;
try { listMineStored = localStorage.getItem("cp-list-mine") === "1"; } catch (error) { /* storage blocked: the list starts unfiltered */ }
const S = { listMine: listMineStored, me: null, route: {}, data: null, pages: {}, file: null, page: null, step: null, editing: false, lastEdit: null,
            events: [], poll: null, follow: true, knowledge: null, workflows: null, message: "", shown: new Set(), litKey: null };

async function api(path, options = {}) {
  const headers = options.body && !(options.body instanceof FormData) ? { "content-type": "application/json" } : {};
  if (reading()) headers["x-casepath-lang"] = LANG;
  // anything written may change how a case stands in the list; looking alone (a case opened, a source opened) does not
  if (options.method && options.method !== "GET" && !path.startsWith("/api/translate")
    && !(path.endsWith("/events") && /"kind":"(case\.opened|idle\.started|idle\.ended|source\.opened|item\.exposed)"/.test(String(options.body || "")))) S.listStale = true;
  const response = await fetch(path, { ...options, headers });
  const type = response.headers.get("content-type") || "";
  const body = type.includes("json") ? await response.json() : await response.text();
  learn(body);
  if (body && typeof body === "object" && "_tr" in body && body._tr_wait) awaitTranslation(body._tr_wait);
  if (!response.ok) throw new Error(plainError(body && body.detail, response.status, response.statusText));
  return body;
}
// What the server refused, in the handler's language: a message it words in English (the API's own) is said in German,
// a list of field errors as one sentence, and nothing technical is ever shown as it came.
const ERRORS_DE = [
  [/^Not found\.$/, "Nicht gefunden. Bitte die Liste neu laden."],
  [/^Sign-in required\.$/, "Bitte neu anmelden."],
  [/^Sign in again: CasePath calls the model as you\.$/, "Bitte neu anmelden: CasePath ruft das Modell in Ihrem Namen auf."],
  [/^This workspace needs an access role you do not have\.$/, "Für diesen Arbeitsbereich fehlt Ihnen die Berechtigung."],
  [/^This CasePath pilot is open to its named pilot group only\.$/, "Dieser Pilot steht nur der benannten Pilotgruppe offen."],
  [/^Sign-in is not configured for this deployment\.$/, "Die Anmeldung ist für diese Installation nicht eingerichtet."],
  [/^Files up to (\d+) MB are accepted\.$/, "Dateien bis $1 MB werden angenommen."],
  [/^The files? (?:is|are) empty\.$/, "Die Datei ist leer."],
  [/^A title of up to 300 characters is required\.$/, "Bitte einen Namen mit höchstens 300 Zeichen angeben."],
  [/^(?:A run is in progress for this case\.|this case already has a run in progress)$/, "Für diesen Fall läuft gerade eine Vorbereitung. Bitte warten, bis sie fertig ist."],
  [/^This file is already imported\.$/, "Diese Akte ist bereits importiert."],
  [/^No volume is configured for imports\.$/, "Für den Import ist kein Ablageort eingerichtet."],
  [/^Only case files in the volume's incoming folder can be imported\.$/, "Importiert werden nur Akten aus dem Eingangsordner."],
  [/^This runtime reads prepared cases only; prepare the file first\.$/, "Diese Installation liest nur vorbereitete Akten; die Datei muss zuerst vorbereitet werden."],
  [/^No such workflow\.$/, "Diesen Prozess gibt es nicht (mehr)."],
  [/^Name the one PDF to cut\.$/, "Bitte das eine PDF nennen, das zugeschnitten wird."],
  [/^Your own answer for this case is already saved and frozen\.$/, "Ihre eigene Antwort zu diesem Fall ist bereits gespeichert."],
  [/^This run has no draft\.$/, "Zu diesem Lauf gibt es keinen Entwurf."],
  [/^Choose or route a workflow before editing the process\.$/, "Zuerst muss der Prozess des Falls feststehen."],
  [/^Say why the process changes\.$/, "Bitte angeben, weshalb der Prozess ändert."],
  [/^This change cannot be applied: .*$/, "Diese Änderung lässt sich so nicht anwenden."],
  [/^(?:Unknown event kind.*|Unknown reason\.|Unknown item kind\.|Too much in one event\.)$/, "Das liess sich nicht festhalten. Bitte neu laden."],
];
function plainError(detail, status, fallback) {
  if (Array.isArray(detail)) return T("The entry does not fit; please check it.", "Die Eingabe passt so nicht; bitte prüfen.");
  const text = String(detail || "");
  if (LANG !== "de") return text || fallback;
  for (const [pattern, german] of ERRORS_DE) if (pattern.test(text)) return text.replace(pattern, german);
  if (!text) return status >= 500 ? "Der Dienst antwortet gerade nicht. Bitte gleich erneut versuchen." : "Das hat nicht geklappt. Bitte neu laden und erneut versuchen.";
  return text;
}

function parseRoute() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "case" && parts[1]) return { view: "case", id: parts[1], tab: parts[2] || "overview" };
  if (parts[0] === "knowledge" && parts[1] === "gebiet" && parts[2]) return { view: "review", id: decodeURIComponent(parts[2]) };
  if (parts[0] === "knowledge" && parts[1] === "brief" && parts[2]) return { view: "review", id: `brief:${decodeURIComponent(parts[2])}` };  // review in a case's letter
  if (parts[0] === "knowledge") return { view: "knowledge" };
  if (parts[0] === "auswertung") return { view: "auswertung" };
  return { view: "cases" };
}

const dateText = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? esc(iso) : `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
// An e-mail's Date header ("Mon, 10 Feb 2025 09:14:00 +0100") as the handler writes it ("10.02.2025, 09:14"), in the sender's own time.
const mailDate = (v) => {
  const m = /(\d{1,2}) (\w{3}) (\d{4}) (\d{1,2}):(\d{2})/.exec(String(v || "")), mon = m ? MONTHS.indexOf(m[2]) : -1;
  return mon >= 0 ? `${m[1].padStart(2, "0")}.${String(mon + 1).padStart(2, "0")}.${m[3]}, ${m[4].padStart(2, "0")}:${m[5]}` : String(v || "");
};
const isoToday = () => { const t = new Date(); return `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(t.getDate()).padStart(2, "0")}`; };
const daysTo = (iso) => Math.round((Date.parse(`${String(iso).slice(0, 10)}T00:00:00`) - Date.parse(`${isoToday()}T00:00:00`)) / 86400000);
// A process as handlers call it ("Mietmangel"); the long title with its provenance stays under Wissen.
const wfShort = (id, fallback) => { const w = (S.workflows || []).find((x) => x.id === id); return w ? w.short_title || w.title : fallback || id || ""; };

// ---------- top bar ----------
function renderTop() {
  const route = S.route;
  const wordmark = `<a class="cp-wordmark" href="#/cases"><svg viewBox="0 0 28 28" aria-hidden="true"><path d="M22 6.5A10 10 0 1 0 22 21.5" fill="none" stroke="currentColor" stroke-width="4.5" stroke-linecap="round"/></svg>CasePath</a>`;
  let tabs;
  if (route.view === "case") {
    tabs = [["overview", T("Overview", "Übersicht"), "check"], ["claim_reader", T("File", "Akte"), "doc"], ["process_builder", T("Process", "Prozess"), "nodes"],
            ["document_finder", T("Documents", "Unterlagen"), "folder"], ["history", T("History", "Verlauf"), "memory"]].map(([id, title, ic]) => `<a class="cp-tab" href="#/case/${raw(route.id)}/${id}"
      ${route.tab === id ? 'aria-current="page"' : ""} data-tab="${id}">${icon(ic)}${title}</a>`).join("");
  } else {
    // a page that is one view says its name; the ways between pages are the sidebar's
    const [href, name, ic] = route.view === "auswertung" ? ["#/auswertung", T("Evaluation", "Auswertung"), "chart"] : route.view === "knowledge" || route.view === "review" ? ["#/knowledge", T("Knowledge", "Wissen"), "book"] : ["#/cases", T("Cases", "Fälle"), "folder"];
    tabs = `<a class="cp-tab" href="${href}" aria-current="page">${icon(ic)}${name}</a>`;
  }
  const other = LANG === "de" ? "en" : "de";
  renderNav(wordmark);
  $("#top").innerHTML = `<nav class="cp-tabs" aria-label="${T("Views", "Ansichten")}">${tabs}</nav>
    ${route.view === "case" ? walkPlace(route.id).bar : ""}<div class="cp-top-right">${measureToggle()}${route.view === "case" ? `${walkPlace(route.id).label}<button class="cp-link" id="skip-case" type="button" title="${T("the next case that needs you, in the list's order", "der nächste Fall, der Sie braucht, in der Reihenfolge der Liste")}">${T("Next case", "Nächster Fall")} ${icon("right")}</button>` : ""}${S.me ? `<span class="cp-me" title="${T("Signed in as", "Angemeldet als")} ${raw(S.me)}"><i aria-hidden="true">${raw(meName().slice(0, 1).toUpperCase())}</i>${raw(meName())}</span>` : ""}
      <button class="cp-keys-open" id="keys-open" type="button" aria-label="${T("Keyboard shortcuts", "Tastenkürzel")}" title="${T("Keyboard shortcuts (?)", "Tastenkürzel (?)")}">?</button>
      ${langSwitch()}</div>`;
  glide();
}
const meName = () => { const me = String(S.me || "").trim(), local = me.includes("@") ? me.split("@")[0] : me; return /[A-ZÄÖÜ]/.test(local) && !me.includes("@") ? local : local.split(/[._-]+/).filter(Boolean).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join(" "); };
// The sidebar: the product's name, who works, and the ways through the product, always in the same place. In a case the
// case's own rail (its name, its parts, its files) continues the same column below.
function renderNav(wordmark) {
  let nav = document.getElementById("nav");
  if (!nav) { nav = document.createElement("aside"); nav.id = "nav"; nav.className = "cp-nav"; document.body.insertBefore(nav, document.body.firstChild); }
  const route = S.route;
  const item = (href, ic, title, on, side) => `<a class="cp-nav-item" href="${href}" ${on ? 'aria-current="page"' : ""}>${icon(ic)}<span>${title}</span>${side ? `<small>${side}</small>` : ""}</a>`;
  // only what leads somewhere: the list, and outside a case the two pages of those who look after the knowledge
  nav.innerHTML = `${wordmark}
    <nav aria-label="CasePath">${item("#/cases", "folder", T("Cases", "Fälle"), route.view === "cases", "")}
      ${S.mayReview && route.view !== "case" ? `<h4>${T("Administration", "Verwaltung")}</h4>${item("#/knowledge", "book", T("Knowledge", "Wissen"), route.view === "knowledge" || route.view === "review")}${item("#/auswertung", "chart", T("Evaluation", "Auswertung"), route.view === "auswertung")}` : ""}</nav>`;
  document.documentElement.style.setProperty("--nav-h", `${nav.offsetHeight}px`);
  document.documentElement.classList.toggle("cp-in-case", route.view === "case");
}
// One control, one fill: when the choice changes, the fill slides from the old choice to the new one (the tabs, the
// list's filter, the letters of a step). Called after a render; where nothing moved, nothing plays.
const GLIDES = [[".cp-tabs", '.cp-tab[aria-current="page"]'], [".cp-filter", ".cp-filter-item.on"], [".cp-doc-tabs", '.cp-doc-tab[aria-selected="true"]']];
function glide() {
  S.glideAt = S.glideAt || {};
  for (const [box, on] of GLIDES) {
    const host = document.querySelector(box), el = host && host.querySelector(on);
    if (!el) { delete S.glideAt[box]; continue; }
    const h = host.getBoundingClientRect(), r = el.getBoundingClientRect();
    const at = { x: r.left - h.left, y: r.top - h.top, w: r.width, h: r.height }, was = S.glideAt[box];
    S.glideAt[box] = at;
    if (!was || reducedMotion() || !el.animate || (Math.abs(was.x - at.x) < 1 && Math.abs(was.w - at.w) < 1) || host.querySelector(".cp-ink")) continue;
    const ink = document.createElement("i");
    ink.className = "cp-ink";
    Object.assign(ink.style, { left: `${at.x}px`, top: `${at.y}px`, width: `${at.w}px`, height: `${at.h}px` });
    host.classList.add("cp-gliding"); host.prepend(ink);
    const done = () => { ink.remove(); host.classList.remove("cp-gliding"); };
    const move = ink.animate([{ transform: `translate(${was.x - at.x}px, ${was.y - at.y}px)`, width: `${was.w}px` }, { transform: "none", width: `${at.w}px` }],
      { duration: 260, easing: "cubic-bezier(.2,.8,.2,1)" });
    move.onfinish = done; move.oncancel = done;
  }
}
// The language, one small control at the right of the header: both languages shown, the current one filled. A press
// changes the page in place; where the model is still translating a case's texts, a small dot says so.
function langSwitch() {
  const one = (l, name) => `<button type="button" class="cp-lang-item ${LANG === l ? "on" : ""}" data-lang="${l}" lang="${l}" aria-pressed="${LANG === l}" title="${name}">${l.toUpperCase()}</button>`;
  return `<span class="cp-lang" role="group" aria-label="${T("Language", "Sprache")}">${one("de", "Deutsch")}${one("en", "English")}</span>${
    S.trWait ? `<span class="cp-lang-wait" title="${T("The case's texts are being translated", "Die Texte des Falls werden übersetzt")}"></span>` : ""}`;
}
async function setLang(next) {
  if (next === LANG || S.langBusy || !["de", "en"].includes(next)) return;
  S.langBusy = true;
  try { localStorage.setItem("casepath.lang", next); } catch (error) { /* this page only */ }
  const swap = async () => {
    LANG = next; document.documentElement.lang = LANG;
    if (/[?&]lang=/.test(location.search)) history.replaceState(null, "", location.pathname + location.hash);
    S.trWait = 0; S.trTries = 0; clearTimeout(S.trTimer);
    if (S.workflows) { try { S.workflows = (await api("/api/workflows")).workflows; } catch (error) { /* the names stay as they were */ } }
    if (S.route.view === "case") Object.assign(S, { data: null, pages: {} });
    const y = window.scrollY;
    await route();
    window.scrollTo(0, y);  // the page turns where it stands
  };
  try {
    if (document.startViewTransition && !reducedMotion()) { document.documentElement.classList.add("cp-lang-turn"); await document.startViewTransition(swap).finished; }
    else {
      const app = $("#app"); app.classList.add("cp-lang-out");
      await new Promise((r) => setTimeout(r, reducedMotion() ? 0 : 130));
      await swap(); app.classList.remove("cp-lang-out");
    }
  } catch (error) { if (LANG !== next) await swap(); }
  finally { S.langBusy = false; document.documentElement.classList.remove("cp-lang-turn"); }
}
document.addEventListener("click", (event) => {
  const b = event.target.closest && event.target.closest("[data-lang]");
  if (b) setLang(b.dataset.lang);
  const more = document.querySelector("details.cp-more[open]");  // «Mehr» closes when the hand goes elsewhere
  if (more && !(event.target.closest && event.target.closest("details.cp-more"))) { more.open = false; S.moreOpen = false; }
});
document.addEventListener("keydown", (event) => {  // Esc leaves a menu or a small form without doing anything
  if (event.key === "Escape" && S.storyBig) { event.preventDefault(); storyBig(false); return; }
  if (event.key !== "Escape" || S.route.view !== "case" || !S.data) return;
  const typing = event.target.closest && event.target.closest("[data-editable], #case-title");
  if (typing) return;
  if (S.moreOpen || S.changing || S.noting || S.entryEdit || S.addrEdit) {
    Object.assign(S, { moreOpen: false, changing: false, pickAction: null, noting: false, entryEdit: null, entryDraft: null, entryError: "", addrEdit: null, addrDraft: null });
    renderCase();
  }
});
// Texts the model is still translating: the page asks again a few times, a little later each time, and shows them
// when they are there.
function awaitTranslation(n) {
  if (!n || !reading() || (S.trTries || 0) >= 8) return;
  S.trWait = n;
  clearTimeout(S.trTimer);
  S.trTimer = setTimeout(async () => {
    S.trTries = (S.trTries || 0) + 1; S.trWait = 0;
    if (!reading()) return;
    if (S.route.view === "case" && !running()) { await loadCase(); } else if (S.route.view !== "case") { await route(); }
  }, 2500 + 1500 * (S.trTries || 0));
}
// Wissen and Auswertung are for the people named to review the legal content (CASEPATH_REVIEWERS; with none named, for
// everyone): one quiet entry at the right of the header, never beside «Fälle».
function adminMenu(route) {
  if (!S.mayReview) return "";
  const here = { knowledge: route.view === "knowledge" || route.view === "review", auswertung: route.view === "auswertung" };
  return `<details class="cp-admin ${here.knowledge || here.auswertung ? "on" : ""}"><summary>${T("Administration", "Verwaltung")}</summary><div class="cp-admin-menu">
    <a href="#/knowledge" ${here.knowledge ? 'aria-current="page"' : ""}>${T("Knowledge", "Wissen")}</a>
    <a href="#/auswertung" ${here.auswertung ? 'aria-current="page"' : ""}>${T("Evaluation", "Auswertung")}</a></div></details>`;
}

// ---------- cases ----------
// Where a case stands, in the handler's words and in the order it needs the handler (rank), as the server says it
// (listing.py): a deadline or a set date running, first contact due, prepared, waiting until a date, paused, new files, done.
const STAND_EN = { frist: "deadline", contact: "first contact", prepared: "prepared", waiting: "waiting", due: "follow-up due", paused: "stopped",
                   working: "in progress", new: "not prepared", arrived: "new files", closed: "done", decision: "decision", check: "to check",
                   ready: "ready to send", failed: "failed" };
const standOf = (c) => (c.stand || {}).kind || "new";
// The status in the reader's language: the case's own words where they are translated, else the kind of status.
const standIn = (text, kind) => (LANG === "de" ? text : (text && tr(text) !== text ? tr(text) : STAND_EN[kind] || text));
const standText = (c) => standIn((c.stand || {}).text, standOf(c)) || "—";
// Search folds case and accents, so «larchenweg» finds «Lärchenweg».
const fold = (text) => String(text || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
// In the list the status stands beside «Als Nächstes»: it says only what that column does not («überfällig», not the
// step's name again); the full wording is its title. A case that is simply prepared says nothing there: its row and the
// group it stands in («Zu entscheiden») already do, so the column speaks only where something is out of the ordinary.
function standShort(c) {
  const full = standText(c), de = (c.stand || {}).text || "", next = (c.next_action || {}).text;
  const rest = next && de.includes(next) ? de.replace(next, "").replace(/\s*vorbereitet\s*$/, "").replace(/[:\s]+$/, "").trim() : null;
  if (rest === "" || (rest === null && de.trim() === "vorbereitet")) return "";
  return LANG !== "de" || rest === null ? full : rest;
}
// «Heute» narrows the list: a count is a filter (the cases behind it and nothing else), pressed again it shows all.
const LIST_FILTERS = {
  urteil: (c) => bucketOf(c) === "urteil", versandbereit: (c) => bucketOf(c) === "versandbereit", wartet: (c) => bucketOf(c) === "wartet",
  due: (c, today) => Boolean(c.due && c.due.date <= today && !c.as_of && !c.historic && standOf(c) !== "closed"),
};
// The first contact the insurer promises (three working days from the report) is the case's next date while it is open.
// «Fällig»: the earliest of the case's deadlines, set dates, follow-up and first contact, with its word (listing.due).
const DUE_EN = { Frist: "deadline", Termin: "date set", Wiedervorlage: "follow-up", Erstkontakt: "first contact" };
const dueWord = (w) => (LANG === "de" ? w : DUE_EN[w] || w);
function orderedCases(cases) {
  const rank = (c) => (c.stand || {}).rank ?? 5;
  return [...cases].sort((a, b) => rank(a) - rank(b) || ((a.stand || {}).date || (a.due || {}).date || "9999").localeCompare((b.stand || {}).date || (b.due || {}).date || "9999"));
}
// «Heute»: the day at a glance above the list. How many cases need the reader's judgment, are ready to send, fall due
// today or wait; and what happened on the reader's cases since they last looked (what CasePath noticed by itself, a
// preparation that finished, what a colleague did). The last visit is this browser's own note, kept nowhere else.
let visitFrom = null;
try { visitFrom = localStorage.getItem("cp-last-visit"); } catch (error) { /* without it «Heute» shows the counts only */ }
function todayPanel(rows, today, since, walkEnd, tools) {
  const open = rows.filter((c) => standOf(c) !== "closed" && !c.historic);
  if (!open.length) return "";
  const n = (bucket) => open.filter((c) => bucketOf(c) === bucket).length;
  const due = open.filter((c) => c.due && c.due.date <= today && !c.as_of).length;
  // the day as one statement, then the list's filters as one control: each names its cases and how many they are
  const urteil = n("urteil"), ready = n("versandbereit"), waits = n("wartet");
  const seg = (k, text, key) => { const on = (S.listFilter || "") === key;
    return `<button type="button" class="cp-filter-item ${on ? "on" : ""}" data-today-filter="${key}" aria-pressed="${on}" ${k || on ? "" : "disabled"}>${text}<b>${k}</b></button>`; };
  const first = due ? T(`${due} ${due === 1 ? "case is" : "cases are"} due.`, `${due} ${due === 1 ? "Fall ist" : "Fälle sind"} fällig.`)
    : urteil ? T(`${urteil} ${urteil === 1 ? "case is" : "cases are"} for you to decide.`, `${urteil} ${urteil === 1 ? "Fall wartet" : "Fälle warten"} auf Ihren Entscheid.`) : T("Nothing needs you right now.", "Im Moment braucht Sie nichts.");
  const second = due && urteil ? T(`${urteil} are for you to decide.`, `${urteil} warten auf Ihren Entscheid.`) : due || urteil ? (due ? "" : T("Nothing is overdue.", "Nichts ist überfällig."))
    : waits ? T(`${waits} ${waits === 1 ? "case waits" : "cases wait"} for an answer.`, `${waits} ${waits === 1 ? "Fall wartet" : "Fälle warten"} auf Antwort.`) : "";
  const events = (since && since.events) || [];
  const day = (iso) => { const d = new Date(iso); return Number.isNaN(d.getTime()) ? "" : `${dateText(iso)} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`; };
  const tick = (since && since.tick) || {};
  // how far the day has come: the cases the reader sent a letter in or closed today, beside those still needing them
  const done = (since && since.done && since.done.cases) || 0, left = open.filter(needsReader).length;
  const dayLine = done ? `<p class="cp-day" data-day><span class="cp-day-track" role="img" aria-label="${T(`${done} of ${done + left} done today`, `${done} von ${done + left} heute erledigt`)}"><span class="cp-day-fill" style="width:${Math.max(4, Math.round(100 * done / (done + left)))}%"></span></span>
      <span><b>${done}</b> ${T("done today", "heute erledigt")} · ${left} ${T("open", "offen")}</span></p>` : "";
  const weekday = (() => { try { return new Date(`${today}T12:00:00`).toLocaleDateString(LANG === "de" ? "de-CH" : "en-GB", { weekday: "long", day: "numeric", month: "long" }); } catch (error) { return dateText(today); } })();
  // a greeting by the time of day and the reader's name, then the day in one line
  const hour = new Date().getHours();
  const hello = hour < 11 ? T("Good morning", "Guten Morgen") : hour < 17 ? T("Good afternoon", "Guten Tag") : T("Good evening", "Guten Abend");
  const me = String(S.me || ""), name = me.includes("@") ? me.split("@")[0].split(/[._-]/)[0].replace(/^./, (c) => c.toUpperCase()) : me;
  // the working week ahead: how many cases fall due on each of the next five working days (today's tile holds what is overdue too)
  const days = []; for (let d = new Date(`${today}T12:00:00`); days.length < 5; d.setDate(d.getDate() + 1)) if (d.getDay() % 6) days.push(new Date(d));
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const week = days.map((d) => { const key = iso(d) === today ? "due" : `day:${iso(d)}`, k = key === "due" ? due : open.filter((c) => c.due && c.due.date === iso(d) && !c.as_of).length, on = S.listFilter === key;
    return `<button type="button" class="cp-wday ${iso(d) === today ? "today" : ""} ${on ? "on" : ""}" data-today-filter="${key}" aria-pressed="${on}" ${k || on ? "" : "disabled"} title="${dateText(iso(d))}">
      <span>${d.toLocaleDateString(LANG === "de" ? "de-CH" : "en-GB", { weekday: "short" }).replace(".", "")}</span><b>${d.getDate()}</b><i>${k ? T(`${k} due`, `${k} fällig`) : "–"}</i></button>`; }).join("");
  return `<section class="cp-hero" data-today aria-label="${T("Today", "Heute")}">
    <div class="cp-hero-top"><div class="cp-hero-text"><p class="cp-eyebrow">${esc(weekday)}</p>
        <h2 class="cp-hero-title">${hello}${name ? `, <em>${esc(name)}</em>` : ""}</h2>
        <p class="cp-hero-lead">${esc(first)}${second ? ` ${esc(second)}` : ""}</p>
        ${dayLine}${walkEnd ? `<p class="cp-walk-end" role="status">${icon("tick")}${T("You have been through every case that needs you.", "Sie haben alle Fälle durchgesehen, die Sie brauchen.")}</p>` : ""}</div>
      <div class="cp-hero-side"><div class="cp-week" role="group" aria-label="${T("Due in the coming days", "Fällig in den nächsten Tagen")}">${week}</div>
        ${open.some(needsReader) ? `<button class="cp-button primary cp-walk" id="walk-start" type="button">${T("Go through the cases", "Fälle durchgehen")} ${icon("right")}</button>` : ""}</div></div>
    <div class="cp-list-bar"><div class="cp-filter" role="group" aria-label="${T("Show", "Zeigen")}">${seg(open.length, T("All", "Alle"), "")}${seg(urteil, T("To decide", "Zu entscheiden"), "urteil")}${seg(due, T("Due", "Fällig"), "due")}
      ${seg(ready, T("Ready to send", "Versandbereit"), "versandbereit")}${seg(waits, T("Waiting", "Wartet"), "wartet")}</div>${tools || ""}</div>
    ${events.length ? `<div class="cp-today-since"><p class="cp-muted">${T("Since your last visit", "Seit Ihrem letzten Besuch")} (${day(since.since)}):</p><ul>${events.slice(0, 6).map((e) =>
      `<li><a href="#/case/${raw(e.case)}/overview">${e.reference ? `<span class="cp-ref">${esc(e.reference)}</span> ` : ""}${esc(e.title || "")}</a> · ${esc(e.what)} <span class="cp-muted">· ${esc(e.by || "")} · ${day(e.at)}</span></li>`).join("")}
      ${events.length + (since.more || 0) > 6 ? `<li class="cp-muted">${T(`and ${events.length + (since.more || 0) - 6} more`, `und ${events.length + (since.more || 0) - 6} weitere`)}</li>` : ""}</ul></div>` : ""}
    </section>`;
}
// A filter, a day or a typed search narrows the cases already here at once (kept: true); the list is fetched when it is
// opened and after anything that changes it.
// The list's data: the cases, the processes, the service's state and what happened since the reader last looked. Returns
// whether the cases differ from what the page held.
async function loadList(sinceMark) {
  const got = await Promise.all([api("/api/cases"), api("/api/workflows"), api("/api/health"),
    api(`/api/today${sinceMark ? `?since=${encodeURIComponent(sinceMark)}` : ""}`).catch(() => null)]);
  const imported = got[2].imports ? await api("/api/imports").catch(() => null) : null;
  const print = (d) => JSON.stringify([d.got[0], d.got[3] && d.got[3].events, d.got[3] && d.got[3].done, d.imported]);
  const changed = !S.listData || S.listData.lang !== LANG || print(S.listData) !== print({ got, imported });
  S.listData = { lang: LANG, got, imported };
  S.listStale = false;
  try { localStorage.setItem("cp-last-visit", new Date().toISOString()); } catch (error) { /* a convenience only */ }
  // a case whose status changed since the list was last on this screen (a letter approved, an answer arrived, a
  // day passed) says so on its row once: what it was before, beside what it is now
  const seen = S.listSeen || {}, moved = {};
  for (const c of got[0].cases || []) {
    const now = { text: (c.stand || {}).text || "", kind: (c.stand || {}).kind || "" };
    if (seen[c.id] && seen[c.id].text !== now.text) moved[c.id] = seen[c.id];
    seen[c.id] = now;
  }
  S.listSeen = seen; S.listMoved = moved;
  return changed;
}
// A row's quiet track: how far the case is along its process (the steps that lead on, then its closing), the step it is
// at marked. And its peek, for the hand that rests on the row or the keyboard that stands on it: the step by name, the
// one reason for what comes next, the whole status. Nothing here is asked of the server again: the row carries it.
function stageTrack(c, s) {
  const st = c.stage;
  if (!st || !st.of || s === "new") return "";
  const dots = Array.from({ length: st.of }, (_, i) => `<span class="${i + 1 < st.at || s === "closed" ? "done" : i + 1 === st.at ? "now" : ""}"></span>`).join("");
  return `<span class="cp-rowtrack" role="img" aria-label="${esc(T(`Step ${st.at} of ${st.of}`, `Schritt ${st.at} von ${st.of}`))}: ${esc(shortTitle(st.title || ""))}">${dots}</span>`;
}
function rowPeek(c, s) {
  const st = c.stage, why = c.why && s !== "closed" ? c.why : "";
  if (!st && !why) return "";
  return `<span class="cp-row-peek" aria-hidden="true">${st ? `<span><b>${esc(shortTitle(st.title || ""))}</b> <span class="cp-muted">· ${T(`step ${st.at} of ${st.of}`, `Schritt ${st.at} von ${st.of}`)}</span></span>` : ""}
    ${why ? `<span class="cp-peek-why"><span class="cp-muted">${T("Because", "Weil")}:</span> ${esc(clip(why, 150))}</span>` : ""}<span class="cp-peek-stand">${esc(standText(c))}</span></span>`;
}
async function renderCases(kept) {
  const sinceMark = visitFrom;
  const held = S.listData && S.listData.lang === LANG;
  if (!(kept && held)) {
    // Back from a case in which nothing was written, the list is there at once as it was and is brought up to date
    // behind it (redrawn only if something differs); after anything was written it is asked for anew first.
    if (held && !S.listStale) {
      loadList(sinceMark).then((changed) => {
        if (!changed || S.route.view !== "cases") return;
        const at = document.activeElement, typing = at && at.id === "list-search" ? [at.selectionStart, at.selectionEnd] : null;
        renderCases(true).then(() => { const el = typing && $("#list-search"); if (el) { el.focus(); try { el.setSelectionRange(typing[0], typing[1]); } catch (error) { /* not a text field */ } } });
      }).catch(() => {});
    } else await loadList(sinceMark);
  }
  const [casesGot, workflows, health, since] = S.listData.got, imports = S.listData.imported;
  const cases = { ...casesGot };
  const walkEnd = S.walkEnd; S.walkEnd = false;
  S.workflows = workflows.workflows;
  const today = isoToday();
  // One row per case, in the words its card uses: the case and its parties, what comes next (the card's title), when it
  // is due and why (a deadline, a date set, the follow-up, the first contact), its status (the card's chip).
  const row = (c) => {
    // a historic cut is looked at as of its own day: its dates are never overdue among live cases
    const s = standOf(c), due = s === "closed" ? null : c.due, late = due && due.date <= (c.as_of || today) && !c.as_of && !c.historic;
    const next = s === "closed" ? "" : c.next_action ? esc(LANG === "de" && c.next_action.text ? c.next_action.text : T(c.next_action.label.en, c.next_action.label.de))
      : s === "working" ? T("being prepared", "wird vorbereitet") : s === "new" ? T("prepare the case", "Fall vorbereiten") : "";
    const was = (S.listMoved || {})[c.id], shown = (S.movedShown = S.movedShown || new Set()), fresh = was && !shown.has(`${c.id}:${was.text}`);
    if (fresh) shown.add(`${c.id}:${was.text}`);
    return `<tr class="${s === "closed" ? "cp-done" : ""} ${bucketOf(c) === "wartet" ? "cp-quiet-row" : ""}${was ? " cp-row-moved" : ""}${fresh ? " cp-row-moved-in" : ""}"><td>${c.reference ? `<span class="cp-ref">${esc(c.reference)}</span> ` : ""}<a href="#/case/${raw(c.id)}/overview">${esc(c.headline || c.display_title || c.title)}</a>${c.parties ? `<small class="cp-parties">${esc(c.parties)}</small>` : ""}</td>
      <td class="cp-next">${next || '<span class="cp-muted">—</span>'}${stageTrack(c, s)}${rowPeek(c, s)}</td>
      <td class="cp-nowrap ${late ? "cp-late" : ""}">${due ? `${dateText(due.date)} <span class="cp-due-word">${esc(dueWord(due.word))}</span>` : '<span class="cp-muted">—</span>'}</td>
      <td>${standShort(c) ? `<span class="cp-stand ${s}" title="${esc(standText(c))}">${esc(standShort(c))}</span>` : `<span class="cp-sr">${esc(standText(c))}</span>`}${was && was.text ? `<small class="cp-muted cp-row-was">${T("before", "vorher")}: ${esc(clip(standIn(was.text, was.kind) || was.text, 60))}</small>` : ""}</td></tr>`;
  };
  const table = (rows) => `<table class="cp-table cp-cases"><thead><tr><th>${T("Case", "Fall")}</th><th>${T("Next", "Als Nächstes")}</th>
    <th>${T("Due", "Fällig")}</th><th>${T("Status", "Status")}</th></tr></thead><tbody>${rows.map(row).join("")}</tbody></table>`;
  // the list narrowed by what the handler types (reference, case, parties, next step, status, owner) and to the cases
  // the handler owns or deputises for («Meine»); both stay as set while the handler works
  const q = fold((S.listQuery || "").trim()), mineOnly = Boolean(S.listMine);
  const hay = (c) => fold([c.reference, String(c.reference || "").replace(/\D/g, ""), c.headline, tr(c.headline), c.display_title, c.title, c.parties, (c.next_action || {}).text, tr((c.next_action || {}).text),
    standText(c), c.owner, c.deputy, c.due ? dateText(c.due.date) : "", ...Object.values(c.due || {}).filter((v) => typeof v === "string").flatMap((v) => [v, dueWord(v)])].filter(Boolean).join(" "));
  const lockedRows = cases.cases.filter((c) => c.locked);  // cases of colleagues (need-to-know): the number and the owner only
  cases.cases = cases.cases.filter((c) => !c.locked);
  const dayOnly = /^day:/.test(S.listFilter || "") ? S.listFilter.slice(4) : null;  // a day of the week strip: what falls due then
  const only = dayOnly ? (c) => Boolean(c.due && c.due.date === dayOnly && !c.as_of && !c.historic && standOf(c) !== "closed") : LIST_FILTERS[S.listFilter] || null;
  const shownCases = cases.cases.filter((c) => (!mineOnly || c.mine) && (!q || q.split(/\s+/).every((w) => hay(c).includes(w))) && (!only || only(c, today)));
  const anyMine = cases.cases.some((c) => c.mine) && cases.cases.some((c) => !c.mine);
  const ordered = orderedCases(shownCases);
  // historic files (test cuts, whole old files uploaded for testing, or as a person placed them): listed apart, never overdue
  const historic = ordered.filter((c) => c.historic);
  const live = ordered.filter((c) => !historic.includes(c));
  const real = live.filter((c) => !(c.intake || {}).synthetic), examples = live.filter((c) => (c.intake || {}).synthetic);
  // files dropped anywhere on the list make a new case; the hint stands beside «Neuer Fall», a box only while there is no case
  const any = cases.cases.length && !S.creating;
  const tools = cases.cases.length > 6 || q || mineOnly || only ? `<div class="cp-list-tools"><input type="search" id="list-search" value="${raw(S.listQuery || "")}" placeholder="${T("Search: reference, name, status", "Suchen: Referenz, Name, Status")}" aria-label="${T("Search cases", "Fälle suchen")}">
      ${anyMine || mineOnly ? `<label class="cp-list-mine"><input type="checkbox" id="list-mine" ${mineOnly ? "checked" : ""}> ${T("Mine", "Meine")}</label>` : ""}
      ${q || mineOnly || only ? `<span class="cp-muted" id="list-count">${ordered.length} ${T("of", "von")} ${cases.cases.length}</span>` : ""}
      ${only ? `<button class="cp-link cp-quiet-link" id="list-all" type="button">${T("show all", "alle zeigen")}</button>` : ""}</div>` : "";
  const arriving = S.listFresh; S.listFresh = false;
  const rowsIn = S.rowsIn && !arriving; S.rowsIn = false;
  $("#app").innerHTML = `<main class="cp-main cp-list ${arriving ? "cp-list-in" : ""}${rowsIn ? " cp-rows-in" : ""}"><div class="cp-list-head"><h1 class="cp-title">${T("Cases", "Fälle")}</h1>
      ${S.canUpload === false ? "" : `<span class="cp-list-new">${any ? `<span class="cp-muted">${T("or drop files here", "oder Dateien hierher ziehen")}</span>` : ""}
        <label class="cp-button ${cases.cases.some((c) => needsReader(c) && standOf(c) !== "closed" && (!mineOnly || c.mine)) ? "" : "primary"}">${icon("plus")}${T("New case", "Neuer Fall")}<input type="file" id="new-files" multiple hidden></label></span>`}</div>
    ${todayPanel(cases.cases.filter((c) => !mineOnly || c.mine), today, since, walkEnd, tools)}
    ${(q || mineOnly || only) && !ordered.length ? `<p class="cp-muted cp-list-none">${T("No case matches.", "Kein Fall passt.")}</p>` : ""}
    ${real.length ? bucketTables(real, table, 2) : ""}
    ${S.canUpload === false || any ? "" : `<div class="cp-drop" id="drop">${S.creating ? T("Creating the case…", "Der Fall wird angelegt …") : T("Drop files here and CasePath prepares the case", "Dateien hierher ziehen, CasePath bereitet den Fall vor")}</div>`}
    ${S.message ? `<p class="cp-error">${esc(S.message)}</p>` : ""}
    ${examples.length ? `<h2 class="cp-section cp-muted">${T("Example cases (synthetic)", "Beispielfälle (synthetisch)")}</h2>${bucketTables(examples, table, 3)}` : ""}
    ${historic.length ? `<h2 class="cp-section cp-muted">${T("Historic files", "Historische Akten")}</h2>${table(historic)}` : ""}
    ${lockedRows.length ? `<h2 class="cp-section cp-muted">${T("Colleagues' cases", "Fälle von Kolleginnen und Kollegen")}</h2><table class="cp-table cp-locked"><tbody>${lockedRows
      .filter((c) => !q || [c.reference, c.owner].filter(Boolean).join(" ").toLowerCase().includes(q)).map((c) => `<tr><td><span class="cp-ref">${esc(c.reference || T("no reference", "ohne Referenz"))}</span></td>
        <td class="cp-muted">${esc(c.owner || "")}</td><td><button class="cp-button cp-small" data-takeover="${raw(c.id)}">${T("Deputise", "Vertretung übernehmen")}</button></td></tr>`).join("")}</tbody></table>` : ""}
    ${imports ? `<h2 class="cp-section">${T("Case files waiting to be imported", "Bereitgestellte Akten")}</h2>
      ${imports.files.length ? `<table class="cp-table"><tbody>${imports.files.map((f) =>
        `<tr><td><b>${esc(f.title || f.name)}</b>${f.title && f.title !== f.name ? `<br><small class="cp-muted">${esc(f.name)}</small>` : ""}</td>
        <td>${f.prepared ? T(`prepared · ${f.files ?? "?"} ${f.files === 1 ? "file" : "files"}${f.pages ? ` · ${f.pages} pages` : ""}`, `vorbereitet · ${f.files ?? "?"} ${f.files === 1 ? "Datei" : "Dateien"}${f.pages ? ` · ${f.pages} Seiten` : ""}`)
          : f.size ? `${(f.size / 1048576).toFixed(1)} MB` : "—"}</td><td>${f.case ? `<a class="cp-link" href="#/case/${raw(f.case)}/overview">${T("Open case", "Fall öffnen")}</a>`
          : `<button class="cp-button" data-import="${raw(f.path)}">${icon("plus")}${T("Import", "Importieren")}</button>`}</td></tr>`).join("")}</tbody></table>`
        : `<p class="cp-muted">${T("No files there yet.", "Noch keine Dateien dort.")}</p>`}` : ""}
    <p class="cp-muted cp-today-note">${T("Shows only cases recorded in CasePath.", "Zeigt nur Fälle, die in CasePath erfasst sind.")}${((since || {}).tick || {}).at ? ` ${T("Deadlines last checked on", "Fristen zuletzt geprüft am")} ${dateText(since.tick.at)}.` : ""}</p></main>`;
  S.message = "";
  for (const b of document.querySelectorAll("[data-today-filter]")) b.addEventListener("click", () => {  // a count narrows the list to its cases
    S.listFilter = !b.dataset.todayFilter || S.listFilter === b.dataset.todayFilter ? null : b.dataset.todayFilter; S.rowsIn = true; renderCases(true);
  });
  glide();
  const all = $("#list-all");
  if (all) all.addEventListener("click", () => { S.listFilter = null; S.listQuery = ""; S.rowsIn = true; renderCases(true); });
  for (const tr of document.querySelectorAll("table.cp-cases tbody tr")) tr.addEventListener("click", (event) => {
    if (event.target.closest("a, button, input, select, label") || String(window.getSelection() || "")) return;
    const a = tr.querySelector("a[href^='#/case/']"); if (a) location.hash = a.getAttribute("href");
  });
  const search = $("#list-search");
  if (search) {
    search.addEventListener("keydown", (event) => {  // Enter on a single hit opens it
      const hits = document.querySelectorAll("table.cp-cases tbody tr a[href^='#/case/']");
      if (event.key === "Enter" && hits.length === 1) location.hash = hits[0].getAttribute("href");
    });
    search.addEventListener("input", () => { S.listQuery = search.value; clearTimeout(S.listTimer); S.listTimer = setTimeout(() => { if (S.route.view === "cases") renderCases(true).then(() => { const el = $("#list-search"); if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); } }); }, 180); });
  }
  for (const b of document.querySelectorAll("[data-takeover]")) b.addEventListener("click", async () => {
    b.disabled = true;
    try { await api(`/api/cases/${b.dataset.takeover}/takeover`, { method: "POST" }); location.hash = `#/case/${b.dataset.takeover}/overview`; }
    catch (error) { S.message = error.message; renderCases(); }
  });
  const mine = $("#list-mine");
  if (mine) mine.addEventListener("change", () => { S.listMine = mine.checked; try { localStorage.setItem("cp-list-mine", mine.checked ? "1" : ""); } catch (error) { /* a per-person convenience only */ } renderCases(); });
  for (const button of document.querySelectorAll("[data-import]")) button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = T("Importing…", "Wird importiert …");
    try {
      const created = await api("/api/imports", { method: "POST", body: JSON.stringify({ path: button.dataset.import }) });
      location.hash = `#/case/${created.case.id}/overview`;
    } catch (error) { button.disabled = false; button.textContent = error.message; }
  });
  const pick = $("#new-files");
  if (pick) pick.addEventListener("change", () => createFromFiles(pick.files));
}
// Files dropped on the case list or picked with "Neuer Fall": one case, named from its first e-mail or file, prepared at once.
async function createFromFiles(list) {
  if (!list || !list.length || S.creating) return;
  const form = new FormData();
  for (const file of list) form.append("files", file);
  S.creating = true; renderCases().catch(() => {});
  try {
    const created = await api("/api/cases/from-files", { method: "POST", body: form });
    S.creating = false;
    location.hash = `#/case/${created.case.id}/overview`;
  } catch (error) { S.creating = false; S.message = error.message; renderCases(); }
}
// Dropping files anywhere: on the case list a new case, on a case its files.
document.addEventListener("dragover", (e) => { if (S.canUpload !== false && [...(e.dataTransfer || {}).types || []].includes("Files")) { e.preventDefault(); document.body.classList.add("dragging"); } });
document.addEventListener("dragleave", (e) => { if (!e.relatedTarget) document.body.classList.remove("dragging"); });
document.addEventListener("drop", (e) => {
  document.body.classList.remove("dragging");
  if (!e.dataTransfer || !e.dataTransfer.files.length || S.canUpload === false) return;
  e.preventDefault();
  if (S.route.view === "cases") createFromFiles(e.dataTransfer.files);
  else if (S.route.view === "case" && S.data && !unaidedPending()) uploadFiles(e.dataTransfer.files);
});
// A historic file (a cut looked at as of a past day, or an old file uploaded for testing) says so wherever it is shown,
// with the date of its newest document; its dates are never shown as overdue.
const quiet = () => Boolean(S.data && S.data.historic);
function standAm(d) {
  const h = d.historic;
  if (!h) return "";
  const day = h.as_of || h.newest;
  return `<span class="cp-chip wait cp-historic" title="${T("A historic file: its dates are not counted as overdue", "Historische Akte: ihre Daten gelten nicht als überfällig")}">${day ? `${T("File up to", "Akte bis")} ${dateText(day)}` : T("Historic file", "Historische Akte")}</span>`;
}
// The legal area of the case and whether a jurist released its content: «aus dem Gesetz abgeleitet, noch nicht
// freigegeben», «in Prüfung (n von m geprüft)» or «freigegeben am … · Name» (the server's review of the area).
function areaLine(d) {
  const a = d.area_review;
  if (!a || !a.label) return "";
  // the letter prepared now: how much of the reviewed content it rests on is checked, one click to see or review it there
  const r = (d.completion || {}).reviewed;
  // «freigegeben» is the handler's own word for an approved letter: the jurists' state is said as «juristisch geprüft», and
  // the count of reviewed elements is the reviewers' entry to their work, not a line every handler reads on every case
  const letter = r && r.of && S.mayReview ? ` <a class="cp-link cp-quiet-link cp-letter-review ${r.checked === r.of ? "released" : ""}" href="#/knowledge/brief/${encodeURIComponent(d.case.id)}">${T(`Legal review: ${r.checked} of ${r.of} text blocks checked`, `Dieser Brief: ${r.checked} von ${r.of} Bausteinen geprüft`)}${r.held ? T(` · ${r.held} under review`, ` · ${r.held} in Prüfung`) : ""}</a>` : "";  // needs a Knowledge item added are released under «Wissen», not counted here
  return `<small class="cp-area-review ${a.state === "freigegeben" ? "released" : ""}" title="${esc(a.title || "")}">${esc(LANG === "de" ? String(a.label).replace("noch nicht freigegeben", "juristisch noch nicht geprüft") : a.label)}</small>${letter}`;
}
// An element a jurist marked «Änderung nötig» shows «in Prüfung» beside it wherever the case's screens draw it: added after
// drawing, from the items the server marked (review); a deadline stays as it is, only marked.
function markInReview() {
  const items = (S.data && S.data.items) || [];
  const flagged = items.filter((i) => i.review);
  const draft = (S.data && S.data.draft) || {};
  const parts = (draft.required || []).filter((r) => r.review);
  const templates = (draft.also || []).filter((a) => a.review);
  if (!flagged.length && !parts.length && !templates.length) return;
  const mark = (extra = "") => ` <span class="cp-review-mark" title="${T("A jurist asked for a change: offered until it is resolved, never ticked by itself", "Eine Juristin oder ein Jurist hat eine Änderung verlangt: bis dahin nur angeboten, nie von selbst angekreuzt")}">${T("under review", "in Prüfung")}${extra}</span>`;
  const add = (el, extra) => { if (el && !el.querySelector(".cp-review-mark")) el.insertAdjacentHTML("beforeend", mark(extra)); };
  const labels = items.filter((i) => i.kind === "deadline").map((i) => plainQuestion((i.label || {}).de || "")).filter(Boolean);
  for (const i of flagged) {
    const own = [...document.querySelectorAll(`[data-item="${CSS.escape(i.item_id)}"]`)].filter((el) => el.tagName !== "SECTION");
    if (own.length) { own.forEach((el) => add(el)); continue; }
    if (i.kind !== "deadline") continue;
    const label = plainQuestion((i.label || {}).de || "");  // a deadline's rows, by its title (a longer title that holds it is another deadline)
    for (const el of document.querySelectorAll(".cp-frist, .cp-lead-frist")) {
      const text = el.textContent;
      if (label && text.includes(label) && !labels.some((other) => other !== label && other.includes(label) && text.includes(other))) add(el);
    }
  }
  if (parts.length) add($(".cp-required"), `: ${esc(parts.map((r) => r.title).join(", "))}`);
  for (const a of templates) add($(`[data-doc-tab="${CSS.escape(a.kind)}"]`));
}

// ---------- case data helpers ----------
const result = () => (S.data && S.data.run && ["completed", "paused"].includes(S.data.run.status) ? S.data.run.result : null) || lastResult();
function lastResult() { return S.data && S.data.lastCompleted ? S.data.lastCompleted.result : null; }
const running = () => S.data && S.data.run && ["queued", "running"].includes(S.data.run.status);
function activeAgent() {
  if (!running()) return null;
  const open = [];
  for (const e of S.events) {
    if (e.kind === "agent.start") open.push(e.agent);
    if (e.kind === "agent.end") { const i = open.lastIndexOf(e.agent); if (i >= 0) open.splice(i, 1); }
  }
  const inner = open.filter((a) => a !== "lead");
  return inner.length ? inner[inner.length - 1] : open.length ? "lead" : null;
}
function facts() {
  const live = (liveState() || {}).graph;
  return (live && live.facts) || (S.data.process && S.data.process.facts) || [];
}
function questionLabel(fact) {
  const r = result();
  return (r && r.questions && r.questions[fact.id]) || fact.question;
}
function recorded(kind) {
  const r = result();
  const live = {};
  for (const e of S.events) {
    if (kind === "fact" && e.kind === "fact.located") live[e.fact] = { fact: e.fact, status: e.status, citations: e.cite ? [e.cite] : [], verdict: null };
    if (kind === "fact" && (e.kind === "fact.accepted" || e.kind === "fact.rejected") && live[e.fact]) live[e.fact].verdict = e.kind.split(".")[1];
    if (kind === "document" && e.kind === "document.recorded") live[e.document] = { document: e.document, status: e.status, citations: e.cite ? [e.cite] : [], files: e.files, verdict: null };
  }
  const saved = {};
  for (const row of (r && (kind === "fact" ? r.facts : r.documents)) || []) saved[row[kind]] = row;
  return running() ? { ...saved, ...live } : saved;
}
function fileName(id) { const f = (S.data.files || []).find((x) => x.id === id); return f ? f.name : id; }
function fileIcon(file) {
  const kind = file.kind;
  if (kind === "image") return `<span class="cp-fileicon"><img alt="" src="/api/files/${raw(file.id)}/original" loading="lazy"></span>`;
  if (kind === "email") return `<span class="cp-fileicon">${icon("mail", "big")}</span>`;
  if (kind === "pdf") return `<span class="cp-fileicon">${icon("doc", "big")}<span class="tag">PDF</span></span>`;
  if (kind === "word") return `<span class="cp-fileicon">${icon("doc", "big")}<span class="tag word">W</span></span>`;
  return `<span class="cp-fileicon">${icon("doc", "big")}</span>`;
}

// A failed run's reason in plain words; the full reason stays in the run record.
function runError(error) {
  const reason = String(error || "").split(":")[0];
  const known = {
    token_budget: T("the run used its token budget; it can be raised for large cases", "Der Lauf hat sein Token-Budget aufgebraucht; für grosse Fälle kann es erhöht werden"),
    model_not_configured: T("no model is configured", "Kein Modell eingerichtet"),
    delegation_limit: T("the case needed more steps than allowed", "Der Fall brauchte mehr Schritte als erlaubt"),
    turn_limit: T("an agent did not finish in time", "Ein Agent wurde nicht rechtzeitig fertig"),
    no_files: T("the case has no files", "Der Fall hat keine Dokumente"),
    workflow_missing: T("the chosen process no longer exists; please choose again", "Der gewählte Prozess ist nicht mehr vorhanden; bitte neu wählen"),
    transport: T("the model could not be reached; please try again", "Das Modell war nicht erreichbar; bitte erneut versuchen"),
    schema_mismatch: T("the model gave an unusable answer; please try again", "Das Modell gab eine unbrauchbare Antwort; bitte erneut versuchen"),
    max_output_tokens: T("the page was too long for one answer", "die Seite war zu lang für eine Antwort"),
    "no image in the file": T("the file holds no image of this page", "die Datei enthält kein Bild dieser Seite"),
    interrupted: T("the service was restarted before the run finished", "Der Dienst wurde neu gestartet"),
    stopped: T("stopped; nothing was kept", "angehalten; nichts übernommen"),
  };
  if (known[reason]) return known[reason];
  if (/^The service restarted/.test(String(error || ""))) return known.interrupted;  // a run interrupted before this release
  if (/^http_(429|5\d\d)$/.test(reason)) return T("the model service is busy; please try again shortly", "Der Modelldienst ist ausgelastet; bitte gleich erneut versuchen");
  if (/^http_4\d\d$/.test(reason)) return T(`the model service refused the request (${reason.slice(5)})`, `Der Modelldienst hat die Anfrage abgelehnt (${reason.slice(5)})`);
  // anything else is technical: said plainly with a short code for support; the full text stays in the run's record
  const code = reason === "internal" ? (String(error).split(":")[1] || "").trim().replace(/[^A-Za-z0-9_]/g, "").slice(0, 40) : reason.replace(/[^A-Za-z0-9_ -]/g, "").slice(0, 40);
  return T(`the preparation was interrupted by an error on our side${code ? ` (for support: ${code})` : ""}`, `die Vorbereitung wurde durch einen Fehler bei uns unterbrochen${code ? ` (für den Support: ${code})` : ""}`);
}

// ---------- rail ----------
// The rail holds the case: its name (renamed in place), its parties, its status in the case list's words, a historic
// file's last day; then its files and «Hinzufügen»; everything else is under «Mehr».
const caseName = (c) => c.headline || c.display_title || c.title;
// The case's reference number and who is responsible for it, in the rail: the number it carries, one its files state
// (proposed with the file, taken over on a click), or «Referenz eintragen»; the owner and the deputy, changed in place.
// A file that names another case's reference number and not this case's (a mail dropped on the wrong case): said on
// the file and above the step, before its content is relied on.
const otherReference = (fileId) => ((((S.data || {}).case || {}).other_references || []).find((r) => r.file === fileId) || {}).reference || "";
function otherReferenceNote() {
  const rows = ((S.data || {}).case || {}).other_references || [];
  if (!rows.length) return "";
  const names = rows.slice(0, 3).map((r) => `«${raw(r.name)}» (${raw(r.reference)})`).join(", ");
  return `<p class="cp-stale-note" data-other-reference-note>${T(`Check: ${names} ${rows.length === 1 ? "names" : "name"} another case's reference. Does it belong here?`,
    `Bitte prüfen: ${names} ${rows.length === 1 ? "nennt" : "nennen"} die Referenz eines anderen Falls. Gehört das hierher?`)}
    <button class="cp-link cp-quiet-link" type="button" data-file="${raw(rows[0].file)}" id="other-reference-open">${T("open the file", "Datei öffnen")}</button></p>`;
}
function identityLine(c) {
  if ((c.intake || {}).study) return "";
  const p = c.reference_proposed;
  if (S.identityEdit) {  // what is typed is kept in S.identityEdit, so a re-render while typing loses nothing
    const v = S.identityEdit;
    return `<div class="cp-identity editing"><label>${T("Reference", "Referenz")} <input data-id-field="reference" value="${raw(v.reference)}" maxlength="60"></label>
      <label>${T("Responsible", "Zuständig")} <input data-id-field="owner" value="${raw(v.owner)}" maxlength="120"></label>
      <label>${T("Deputy", "Stellvertretung")} <input data-id-field="deputy" value="${raw(v.deputy)}" maxlength="120" placeholder="${T("none", "keine")}"></label>
      <span><button class="cp-button cp-small" id="id-save">${T("Save", "Speichern")}</button> <button class="cp-link cp-quiet-link" id="id-cancel">${T("cancel", "abbrechen")}</button></span></div>`;
  }
  const ref = c.reference ? `<span class="cp-ref">${esc(c.reference)}</span>`
    : p ? `<span class="cp-ref cp-ref-proposed" title="${esc(T(`from ${p.name}`, `aus ${p.name}`))}">${esc(p.value)}</span> <button class="cp-link cp-quiet-link" id="id-accept" data-reference="${raw(p.value)}">${T("take as reference", "als Referenz übernehmen")}</button>`
    : `<button class="cp-link cp-quiet-link" id="id-edit-ref">${T("enter a reference", "Referenz eintragen")}</button>`;
  const who = c.owner ? `${esc(c.owner)}${c.deputy ? ` · ${T("deputy", "Stv.")} ${esc(c.deputy)}` : ""}` : "";
  // one way into the editor: «Referenz eintragen» where there is none, «ändern» otherwise
  const change = c.reference || p ? ` <button class="cp-link cp-quiet-link" id="id-edit" aria-label="${T("Change reference and responsibility", "Referenz und Zuständigkeit ändern")}">${T("change", "ändern")}</button>` : "";
  // without a reference the owner stands first (the way to enter one shows on hover): no orphaned «·» before the name
  if (!c.reference && !p) return `<p class="cp-identity">${who ? `<span class="cp-muted">${who}</span> ` : ""}${ref}</p>`;
  return `<p class="cp-identity">${ref}${who ? ` <span class="cp-muted">· ${who}</span>` : ""}${change}</p>`;
}
async function saveIdentity(fields) {
  try {
    await api(`/api/cases/${S.route.id}/identity`, { method: "PUT", body: JSON.stringify(fields) });
    S.identityEdit = false; S.message = "";
  } catch (error) { S.message = error.message; S.messageOk = false; }
  await loadCase();
}
function bindIdentity() {
  const on = (sel, fn) => { const el = $(sel); if (el) el.addEventListener("click", () => fn(el)); };
  on("#id-accept", (b) => saveIdentity({ reference: b.dataset.reference }));
  const c = (S.data || {}).case || {};
  const open = () => { S.identityEdit = { reference: c.reference_set ? c.reference : (c.reference_proposed || {}).value || c.reference || "", owner: c.owner || "", deputy: c.deputy || "" }; renderCase(); const el = $("[data-id-field='reference']"); if (el) el.focus(); };
  on("#id-edit", open);
  on("#id-edit-ref", open);
  on("#id-cancel", () => { S.identityEdit = false; renderCase(); });
  on("#id-save", () => saveIdentity({ ...S.identityEdit }));
  for (const el of document.querySelectorAll("[data-id-field]")) el.addEventListener("input", () => { if (S.identityEdit) S.identityEdit[el.dataset.idField] = el.value; });
}
function renderRail() {
  const d = S.data, files = d.files || [], st = d.status || {};
  const rows = files.map((f) => `<button class="cp-source" data-file="${raw(f.id)}" aria-current="${S.file === f.id}">${fileIcon(f)}
      <span class="cp-source-label">${esc(f.name)}<small>${f.extraction && f.extraction.attached_to ? `${T("Attached to", "Anhang von")} ${esc(f.extraction.attached_to)}`
        : dateText(f.created_at)}${f.extraction && f.extraction.pages > 1 ? ` · ${(f.extraction.kept_pages || []).length || f.extraction.pages} ${T("pages", "Seiten")}` : ""}</small>
      ${(f.extraction && (f.extraction.instruction_like || []).length) ? `<span class="cp-warn">${T("Contains text addressed to an AI", "Enthält Text an die KI")}</span>` : ""}
      ${otherReference(f.id) ? `<span class="cp-warn" data-other-reference>${T("Names another case", "Nennt einen anderen Fall")}: ${raw(otherReference(f.id))}</span>` : ""}</span></button>${segmentRows(f)}`).join("");
  return `<aside class="cp-rail" aria-label="${T("Files", "Dateien")}">
    <div class="cp-caseline"><div id="case-title" contenteditable="plaintext-only" role="textbox" aria-label="${T("Name of the case", "Name des Falls")}" title="${T("Rename", "Umbenennen")}">${esc(caseName(d.case))}</div>
      ${d.case.parties ? `<small class="cp-parties">${esc(d.case.parties)}</small>` : ""}
      ${identityLine(d.case)}
      ${((chips) => (chips.trim() ? `<p class="cp-rail-chips">${chips}</p>` : ""))(`${st.text && !(st.kind === "new" && (d.items || []).some((i) => i.kind === "next_action")) ? railStand(st) : ""}${standAm(d)}`)}${areaLine(d)}</div>
    ${caseIndex()}
    <div class="cp-rail-head">${T("Files", "Dateien")}<span>${files.length}</span>${S.canUpload === false || unaidedPending() ? "" : `<label class="cp-link">${icon("plus")}${T("Add", "Hinzufügen")}<input type="file" id="upload" multiple hidden></label>`}</div>
    ${S.message ? `<p class="${S.messageOk ? "cp-muted" : "cp-error"}" style="padding:0 27px" role="status">${esc(S.message)}</p>` : ""}
    ${rows || `<div class="cp-drop" id="drop">${T("Drop the case files here", "Dateien hierher ziehen")}</div>`}
    <div class="cp-rail-foot">${unaidedPending() ? "" : moreMenu()}</div>
  </aside>`;
}
function railStand(st) {
  // worked out on the case's own (German) words, so a reader of English gets the same short status («overdue»), not the
  // step's name again in translation
  const stand = standIn(st.text, st.kind), de = String(st.text || "").trim(), title = (S.data.screen || {}).title || "";
  const cut = title && de.includes(title) ? (de.includes(":") ? de.split(":")[0].trim() : "") : de;
  // a case that is simply prepared says so above its step («CasePath · vorbereitet vor …»): no chip repeats it here
  const short = String(st.text || "").trim() === "vorbereitet" ? "" : cut === de ? stand : cut ? standIn(cut, st.kind) : "";
  return short ? `<span class="cp-stand ${raw(st.kind || "")}" data-status title="${raw(stand)}">${raw(short)}</span>` : "";
}
function moreMenu() {
  const d = S.data, run = d.run, done = S.data.lastCompleted;
  const options = (S.workflows || []).map((w) => `<option value="${raw(w.id)}" ${d.case.workflow_id === w.id ? "selected" : ""}>${esc(w.short_title || w.title)}</option>`).join("");
  return `<details class="cp-more" ${S.moreOpen ? "open" : ""}><summary class="cp-link">${T("More", "Mehr")}</summary><div class="cp-menu">
    <label>${T("Process", "Prozess")}<select id="workflow"><option value="">${T("from the files", "aus den Akten bestimmen")}</option>${options}</select></label>
    ${running() || !(d.files || []).length ? "" : `<button class="cp-link" id="run">${icon("nodes")}${run ? T("Prepare anew", "Ganz neu vorbereiten") : T("Prepare case", "Fall vorbereiten")}</button>`}
    ${S.file ? `<a class="cp-link" href="/api/files/${raw(S.file)}/original" target="_blank" rel="noopener">${icon("external")}${T("Open original", "Original öffnen")}</a>` : ""}
    ${done ? `<a class="cp-link" href="/api/cases/${raw(d.case.id)}/report.docx?lang=${LANG}">${icon("doc")}${T("Case report (.docx)", "Fallbericht (.docx)")}</a>` : ""}
    ${S.mayReview ? `<button class="cp-link" id="historic-toggle" data-historic="${d.historic ? "false" : "true"}">${d.historic ? T("Treat as a live case", "Als laufenden Fall führen") : T("Treat as a historic file", "Als historische Akte führen")}</button>` : ""}
    ${done ? `<small class="cp-muted">${T("Prepared", "Vorbereitet am")} ${dateText(done.finished_at)}</small>` : ""}</div></details>`;
}

// A document's date as the reading gives it (2024-08-14, 14.08.2024, 14. August 2024); null without one.
const DE_MONTHS = ["januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "dezember"];
function segmentDate(text) {
  const t = String(text || "").toLowerCase();
  let m = t.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]);
  m = t.match(/(\d{1,2})\.(\d{1,2})\.(\d{4})/);
  if (m) return new Date(+m[3], +m[2] - 1, +m[1]);
  m = t.match(/(\d{1,2})\.?\s+([a-zä]+)\s+(\d{4})/);
  if (m && DE_MONTHS.includes(m[2])) return new Date(+m[3], DE_MONTHS.indexOf(m[2]), +m[1]);
  return null;
}
// More than three years before the newest document of the files: flagged in the list, never left out.
function olderDocument(segment) {
  const all = (S.data.files || []).flatMap((f) => ((f.extraction || {}).segments || []).map((s) => segmentDate(s.date))).filter(Boolean);
  const own = segmentDate(segment.date);
  if (!own || !all.length) return false;
  const newest = new Date(Math.max(...all));
  return own < new Date(newest.getFullYear() - 3, newest.getMonth(), newest.getDate());
}
function segmentRows(file) {
  const segments = (file.extraction && file.extraction.segments) || [];
  if (!segments.length) return "";
  const unfolded = S.route.tab === "claim_reader" || (S.segsOpen || {})[file.id];
  return `<details class="cp-segs-fold" data-segs="${raw(file.id)}" ${unfolded ? "open" : ""}><summary>${segments.length} ${T("documents inside", "Dokumente darin")}</summary><ol class="cp-segs" aria-label="${T("Documents in", "Dokumente in")} ${esc(file.name)}">${segments.map((s) => `<li><button class="cp-seg" data-file="${raw(file.id)}" data-page="${s.first_page}" title="${esc(s.summary || "")}">
    <span>${esc(s.title || s.kind)}</span><small>${esc([s.kind !== s.title ? s.kind : "", s.date, `${T("p.", "S.")} ${s.first_page}${s.last_page !== s.first_page ? `–${s.last_page}` : ""}`].filter(Boolean).join(" · "))}${olderDocument(s) ? ` · <span class="cp-older">${T("older document", "älteres Dokument")}</span>` : ""}</small></button></li>`).join("")}</ol></details>`;
}

// "anderer Prozess" during a run: Anhalten, choose, Weiter in one gesture.
async function otherProcess(id) {
  const runId = S.data.run.id;
  S.pickProcess = false; S.switching = true; renderCase();
  await api(`/api/runs/${runId}/stop`, { method: "POST" }).catch(() => {});
  for (let i = 0; i < 120; i += 1) {  // the run ends before its next model turn
    const r = await api(`/api/runs/${runId}`);
    if (r.status !== "queued" && r.status !== "running") break;
    await new Promise((res) => setTimeout(res, 1000));
  }
  await api(`/api/cases/${S.route.id}/workflow`, { method: "PUT", body: JSON.stringify({ workflow_id: id }) });
  await api(`/api/runs/${runId}/continue`, { method: "POST" }).catch(() => {});
  S.switching = false;
  await loadCase();
}

function bindRail() {
  const title = $("#case-title");
  if (title) {
    const save = async () => {
      const value = title.textContent.replace(/\s+/g, " ").trim().slice(0, 300);
      const shown = caseName(S.data.case);
      if (!value || value === shown) { title.textContent = tr(shown); return; }
      const renamed = await api(`/api/cases/${S.route.id}/title`, { method: "PUT", body: JSON.stringify({ title: value }) }).catch(() => null);
      if (renamed) S.data.case = { ...S.data.case, ...renamed, display_title: renamed.title, headline: renamed.title };
      title.textContent = tr(caseName(S.data.case));
    };
    title.addEventListener("focus", () => { if (reading()) title.textContent = caseName(S.data.case); });
    title.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); title.blur(); } if (e.key === "Escape") { title.textContent = caseName(S.data.case); title.blur(); } });
    title.addEventListener("blur", save);
  }
  const more = $(".cp-more");
  if (more) more.addEventListener("toggle", () => { S.moreOpen = more.open; });
  const historicToggle = $("#historic-toggle");  // one action, logged: the latest word governs
  if (historicToggle) historicToggle.addEventListener("click", async () => {
    historicToggle.disabled = true;
    await api(`/api/cases/${S.route.id}/historic`, { method: "PUT", body: JSON.stringify({ historic: historicToggle.dataset.historic === "true" }) })
      .then(() => loadCase()).catch((error) => { S.message = error.message; renderCase(); });
  });
  const openPick = $("#other-process-open");
  if (openPick) openPick.addEventListener("click", () => { S.pickProcess = !S.pickProcess; renderCase(); });
  for (const b of document.querySelectorAll("[data-other-process]")) b.addEventListener("click", () => otherProcess(b.dataset.otherProcess));
  const continueRun = $("#continue-run");
  if (continueRun) continueRun.addEventListener("click", async () => {  // continue from what the stopped run established
    continueRun.disabled = true;
    await api(`/api/runs/${S.data.run.id}/continue`, { method: "POST" }).then(() => loadCase()).catch(() => { continueRun.disabled = false; });
  });
  const discardRun = $("#discard-run");
  if (discardRun) discardRun.addEventListener("click", async () => {  // back to the last finished result; the stopped run is kept
    discardRun.disabled = true;
    await api(`/api/runs/${S.data.run.id}/discard`, { method: "POST" }).then(() => loadCase()).catch(() => { discardRun.disabled = false; });
  });
  const stopRun = $("#stop-run");
  if (stopRun) stopRun.addEventListener("click", async () => {  // the run ends before its next step and keeps what it has
    stopRun.disabled = true; S.stopping = S.data.run.id;
    await api(`/api/runs/${S.data.run.id}/stop`, { method: "POST" }).catch(() => {});
  });
  // «Aktualisieren» and «Erneut aktualisieren» (after a failed or interrupted update): only what came in is read
  for (const updateRun of document.querySelectorAll("#update-run, #retry-update")) updateRun.addEventListener("click", async () => {
    updateRun.disabled = true;
    await api(`/api/cases/${S.route.id}/update`, { method: "POST" }).then(() => { S.events = []; S.follow = true; return loadCase(); }).catch((error) => { S.message = error.message; renderCase(); });
  });
  const prepareNew = $("#prepare-new");  // a person asks: the run is not started automatically (it spends tokens)
  if (prepareNew) prepareNew.addEventListener("click", async () => {
    if (S.data && S.data.lastCompleted && !confirmAnew()) return;
    prepareNew.disabled = true;
    await api(`/api/cases/${S.route.id}/runs`, { method: "POST" }).then(() => { S.events = []; return loadCase(); }).catch((error) => { S.message = error.message; renderCase(); });
  });
  for (const button of document.querySelectorAll("[data-file]")) button.addEventListener("click", () => { S.file = button.dataset.file; S.page = Number(button.dataset.page) || null; S.follow = !running(); renderCase(); });
  const upload = $("#upload");
  if (upload) upload.addEventListener("change", () => uploadFiles(upload.files));
  for (const run of document.querySelectorAll("#run, #start-run")) run.addEventListener("click", startRun);
  const workflow = $("#workflow");
  if (workflow) workflow.addEventListener("change", async () => {
    if (workflow.value) await api(`/api/cases/${S.route.id}/workflow`, { method: "PUT", body: JSON.stringify({ workflow_id: workflow.value }) });
    await loadCase();
  });
}

// One drop is one import: every file in one request. The server refuses a file the case already holds (named with the day
// it came) and skips an attachment it holds; where updates start by themselves, the update of what came in is followed.
async function uploadFiles(list) {
  S.message = ""; S.messageOk = false;
  const files = [...list];  // the picker is emptied at once: its value is never carried into the next page
  const picker = $("#upload");
  if (picker) picker.value = "";
  if (!files.length) return;
  const form = new FormData();
  for (const file of files) form.append("files", file);
  try {
    const answer = await api(`/api/cases/${S.route.id}/files`, { method: "POST", body: form });
    const skipped = answer.skipped || [];
    S.message = skipped.map((s) => s.attachment ? T(`Attachment already in the file: “${s.name}” (skipped)`, `Anhang bereits in der Akte: «${s.name}» (übersprungen)`)
      : T(`Already in the file: “${s.in_case || s.name}” of ${dateText(s.at)}`, `Bereits in der Akte: «${s.in_case || s.name}» vom ${dateText(s.at)}`)).join(" · ");
    S.messageOk = !skipped.some((s) => !s.attachment);
    if (answer.run) { S.events = []; S.follow = true; }
  } catch (error) { S.message = error.message; S.messageOk = false; }
  await loadCase();
}

// Preparing anew calls the model again for every file; a prepared case asks first.
const confirmAnew = () => window.confirm(T("This case is already prepared. Prepare it anew? Every file is read once more, which uses the model again; for new files “Update” is enough.",
  "Dieser Fall ist bereits vorbereitet. Ganz neu vorbereiten? Alle Dokumente werden erneut gelesen; das ruft das Modell nochmals auf. Für neu eingegangene Dateien genügt «Aktualisieren»."));
async function startRun(event) {
  // «Ganz neu vorbereiten» (in «Mehr») and «Erneut versuchen» after a failed run ask first once a preparation completed
  if (event && event.currentTarget && ["run", "start-run"].includes(event.currentTarget.id) && S.data && S.data.lastCompleted && !confirmAnew()) return;
  try {
    await api(`/api/cases/${S.route.id}/runs`, { method: "POST" });
    S.follow = true; S.moreOpen = false;
    S.events = [];
    await loadCase();
  } catch (error) { S.message = error.message; renderCase(); }
}

// ---------- source card ----------
async function pages(fileId) {
  if (!S.pages[fileId]) S.pages[fileId] = await api(`/api/files/${fileId}/pages`);
  return S.pages[fileId];
}
function citationsFor(fileId) {
  const cites = [];
  for (const row of Object.values(recorded("fact")).concat(Object.values(recorded("document")))) {
    for (const c of row.citations || []) if (c.file === fileId) cites.push({ ...c, accepted: row.verdict === "accepted" });
  }
  const live = liveCite();
  if (live && live.file === fileId) cites.push({ ...live, live: true });
  if (S.cite && S.cite.file === fileId) cites.push({ ...S.cite, chosen: true });  // the passage a source chip opened (assessment)
  return cites;
}
function liveCite() {
  if (!running()) return null;
  for (let i = S.events.length - 1; i >= 0; i -= 1) {
    const e = S.events[i];
    if (e.cite) return { ...e.cite, key: `hit:${e.seq}` };
    if (e.kind === "tool" && e.tool === "read_file" && e.file) return { file: e.file, page: e.page || null, key: `read:${e.seq}` };
  }
  return null;
}
// The same normalisation as the server's evidence module, keeping where each
// normalised character came from in the raw text: soft hyphens dropped, words
// split across a line break joined, whitespace runs collapsed, ends trimmed.
const WORD = /[\p{L}\p{N}_]/u;
function normaliseWithMap(raw) {
  const chars = [];
  for (let i = 0; i < raw.length; i += 1) if (raw[i] !== "\u00ad") chars.push([raw[i], i]);
  const joined = [];
  for (let i = 0; i < chars.length; i += 1) {
    if (chars[i][0] === "-" && i > 0 && WORD.test(chars[i - 1][0])) {
      let j = i + 1;
      while (j < chars.length && (chars[j][0] === " " || chars[j][0] === "\t")) j += 1;
      if (j < chars.length && chars[j][0] === "\n") {
        j += 1;
        while (j < chars.length && (chars[j][0] === " " || chars[j][0] === "\t")) j += 1;
        if (j < chars.length && WORD.test(chars[j][0])) { i = j - 1; continue; }
      }
    }
    joined.push(chars[i]);
  }
  const map = [];
  let space = false;
  for (const [c, at] of joined) {
    if (/\s/.test(c)) { space = map.length > 0; continue; }
    if (space) { map.push(at - 1); space = false; }
    map.push(at);
  }
  return map;
}
function highlight(raw, page, cites, from = 0) {
  const map = normaliseWithMap(raw);
  let ranges = cites.filter((c) => c.page === page && c.end <= map.length)
    .map((c) => ({ ...c, a: map[c.start], b: map[c.end - 1] + 1 })).filter((r) => r.a >= from).sort((x, y) => x.a - y.a);
  const live = ranges.find((r) => r.live) || ranges.find((r) => r.chosen);  // the quote worked on (or opened) wins over marks it overlaps
  if (live) ranges = ranges.filter((r) => r === live || r.b <= live.a || r.a >= live.b);
  let out = "", at = from;
  for (const r of ranges) {
    if (r.a < at) continue;
    out += plain(raw.slice(at, r.a)) + `<mark class="cp-hit ${r.live ? `live${S.litKey === r.key ? " lit" : ""}` : r.chosen ? "chosen" : "cited"}" ${r === live ? 'id="live-hit"' : ""}>${plain(raw.slice(r.a, r.b))}</mark>`;
    at = r.b;
  }
  return out + plain(raw.slice(at));
}
// A page for a reader of another language: the same lines, each in that language where it is known; a line a finding
// cites is marked as a whole (the exact words are marked in the original, one press away).
function readPage(text, page, cites, from = 0) {
  const map = normaliseWithMap(text);
  const ranges = cites.filter((c) => c.page === page && c.end <= map.length).map((c) => ({ ...c, a: map[c.start], b: map[c.end - 1] + 1 }));
  const live = ranges.find((r) => r.live) || ranges.find((r) => r.chosen);
  let at = from, lit = false;
  return text.slice(from).split("\n").map((line) => {
    const a = at, b = at + line.length; at = b + 1;
    const hit = ranges.filter((r) => r.a < b && r.b > a);
    if (!hit.length || !line.trim()) return esc(line);
    const top = hit.includes(live) ? live : hit[0], first = top === live && !lit;
    if (first) lit = true;
    return `<mark class="cp-hit ${top.live ? `live${S.litKey === top.key ? " lit" : ""}` : top.chosen ? "chosen" : "cited"}" ${first ? 'id="live-hit"' : ""}>${esc(line)}</mark>`;
  }).join("\n");
}
// Lines of a file the shipped memory does not know: where the deployment lets the model translate, the page asks for
// them once per file and shows them when they are there.
async function askPages(fileId, doc) {
  S.pagesAsked = S.pagesAsked || {};
  if (!reading() || S.translateMode !== "model" || (S.pagesAsked[fileId] || 0) >= 6) return;
  const lines = [...new Set(doc.pages.flatMap((p) => p.text.split("\n")).map((l) => l.trim()).filter((l) => l.length > 1 && !TR.has(l)))].slice(0, 600);
  if (!lines.length) return;
  S.pagesAsked[fileId] = (S.pagesAsked[fileId] || 0) + 1;
  try {
    const res = await api("/api/translate", { method: "POST", body: JSON.stringify({ lang: LANG, texts: lines, case_id: S.route.id }) });
    const got = Object.keys(res._tr || {}).length;
    if (got && S.route.view === "case" && S.file === fileId) renderCase();
    if (res._tr_wait) setTimeout(() => { if (S.route.view === "case" && S.file === fileId) askPages(fileId, doc); }, 3500);
  } catch (error) { /* the lines stay as written */ }
}
async function sourceCard(fileId) {
  if (!fileId) return `<div class="cp-card cp-empty">${T("Choose a source on the left.", "Wählen Sie links eine Quelle.")}</div>`;
  const doc = await pages(fileId);
  const cites = citationsFor(fileId);
  const files = S.data.files.map((f) => f.id), index = files.indexOf(fileId);
  const headerName = { From: T("From", "Von"), To: T("To", "An"), Date: T("Date", "Datum"), Subject: T("Subject", "Betreff") };
  const head = doc.headers ? `<dl class="cp-doc-head">${["From", "To", "Date", "Subject"].filter((k) => doc.headers[k]).map((k) => `<dt>${headerName[k]}:</dt><dd>${(S.sourceOriginal ? raw : esc)(k === "Date" ? mailDate(doc.headers[k]) : doc.headers[k])}</dd>`).join("")}</dl>` : "";
  // An e-mail's header lines are shown above; its body starts after the first blank line.
  const skip = (p) => (doc.headers && p === doc.pages[0] && p.text.indexOf("\n\n") >= 0 ? p.text.indexOf("\n\n") + 2 : 0);
  const isPdf = doc.media_type === "application/pdf";
  const pageUrl = (n) => `/api/files/${esc(fileId)}/original?pages=${n}`;  // one original page: always small enough to open
  const firstCited = (cites.find((c) => c.live && c.page) || cites.find((c) => c.page) || {}).page || (doc.pages[0] || {}).page;
  const readSource = reading() && !S.sourceOriginal && doc.pages.length > 0;
  if (readSource) setTimeout(() => askPages(fileId, doc), 0);
  const langToggle = reading() && doc.pages.length ? `<button class="cp-link cp-quiet-link cp-source-lang" id="source-lang" type="button" title="${S.sourceOriginal
    ? T("Read this file in English", "Diese Datei auf Englisch lesen") : T("The file as it was written; the exact words a finding cites are marked there", "Die Datei, wie sie geschrieben wurde; dort sind die zitierten Worte genau markiert")}">${S.sourceOriginal ? T("English", "Englisch") : T("Original", "Original")}</button>` : "";
  const body = doc.pages.length ? doc.pages.map((p) => `${p.page ? (isPdf
      ? `<a class="page" id="page-${p.page}" href="${pageUrl(p.page)}" target="_blank" rel="noopener" title="${T("Open this original page", "Originalseite öffnen")}">${T("Page", "Seite")} ${p.page} ${icon("external")}</a>`
      : `<span class="page" id="page-${p.page}">${T("Page", "Seite")} ${p.page}</span>`) : ""}${readSource ? readPage(p.text, p.page, cites, skip(p)) : highlight(p.text, p.page, cites, skip(p))}`).join("\n")
    : doc.kind === "image" ? `<img alt="${esc(doc.name)}" src="/api/files/${raw(fileId)}/original" style="max-width:100%">` : `<span class="cp-muted">${T("No readable text.", "Kein lesbarer Text.")}</span>`;
  return `<article class="cp-card" aria-label="${esc(doc.name)}"><div class="cp-doc-toolbar">
      <button class="cp-icon-button" data-step-file="${raw(files[index - 1] || "")}" aria-label="${T("Previous source", "Vorherige Quelle")}" ${index <= 0 ? "disabled" : ""}>${icon("left")}</button>
      <button class="cp-icon-button" data-step-file="${raw(files[index + 1] || "")}" aria-label="${T("Next source", "Nächste Quelle")}" ${index >= files.length - 1 ? "disabled" : ""}>${icon("right")}</button>
      <span class="grow"><span class="name">${esc(doc.name)}</span></span>${langToggle}<a class="cp-icon-button" href="${isPdf && firstCited ? pageUrl(firstCited) : `/api/files/${raw(fileId)}/original`}" target="_blank" rel="noopener" aria-label="${T("Open full source", "Original öffnen")}">${icon("external")}</a></div>
    ${head}<div class="cp-doc-body">${body}</div>${readingNote(doc)}</article>`;
}

function readingNote(doc) {
  const read = (doc.pages_transcribed || []).length, unread = (doc.pages_without_text || []).length;
  const why = [...new Set(Object.values(doc.unread_reasons || {}))].map((reason) => runError(reason)).join("; ");
  const parts = [read ? T(`${read} scanned page${read > 1 ? "s" : ""} read from the image`, `${read} gescannte Seite${read > 1 ? "n" : ""} aus dem Bild gelesen`) : "",
                 !unread ? "" : why ? T(`${unread} page${unread > 1 ? "s" : ""} not read (${why})`, `${unread} Seite${unread > 1 ? "n" : ""} nicht gelesen (${why})`)
                   : running() ? T(`${unread} scanned page${unread > 1 ? "s" : ""} being read`, `${unread} gescannte Seite${unread > 1 ? "n werden" : " wird"} gelesen`)
                   : T(`${unread} scanned page${unread > 1 ? "s" : ""} not read yet`, `${unread} gescannte Seite${unread > 1 ? "n" : ""} noch nicht gelesen`)].filter(Boolean);
  const note = parts.length ? parts.join(" · ") : doc.note;
  return note ? `<div class="cp-doc-note">${esc(note)}</div>` : "";
}

// ---------- spine and live work (01) ----------
function spine() {
  const factRows = recorded("fact");
  const building = running() ? (S.events.slice().reverse().find((e) => e.kind === "fact.located" || (e.kind === "tool" && e.tool === "record_fact")) || {}) : {};
  const nodes = facts().map((f) => {
    const row = factRows[f.id];
    const state = row && row.verdict === "accepted" ? "done" : row && row.verdict === "rejected" ? "rejected"
      : (building.fact === f.id || building.target === f.id) ? "building" : row && row.status === "established" ? "located" : "waiting";
    const mark = state === "done" ? icon("tick") : state === "rejected" ? icon("xcircle") : "";
    return `<div class="cp-q ${state}"><span class="cp-ring">${mark}</span><span>${esc(questionLabel(f))}</span></div>`;
  }).join("");
  return nodes ? `<div class="cp-spine" aria-label="${T("Questions", "Fragen")}">${nodes}</div>` : "";
}

function describe(e) {
  const what = {
    "agent.start": () => `${T("starts", "beginnt")}: ${TASK()[e.agent] || e.instruction || ""}`,
    "agent.end": () => { const c = e.counts || {};
      if (e.routing) {
        const title = ((S.workflows || []).find((w) => w.id === e.workflow) || {}).title || e.workflow;
        return { selected: T(`Process found: ${title}`, `Prozess bestimmt: ${title}`), fallback: T(`No specific process fits; general process: ${title}`, `Kein spezifischer Prozess passt; allgemeiner Prozess: ${title}`),
                 ambiguous: T("Several processes fit; please choose one", "Mehrere Prozesse passen; bitte einen wählen"),
                 needs_facts: T("The files do not yet show which process applies; please choose one", "Die Dokumente zeigen noch nicht, welcher Prozess gilt; bitte einen wählen"),
                 unmapped: T("No process fits this case", "Kein Prozess passt zu diesem Fall") }[e.routing] || e.summary; }
      if ("agreed" in c) return T(`Second reading: ${c.agreed} agree, ${c.differed} differ, ${c.added} found only now`, `Zweite Lesung: ${c.agreed} übereinstimmend, ${c.differed} abweichend, ${c.added} erst jetzt gefunden`);
      if ("checked" in c) return T(`${c.accepted} of ${c.checked} supported by their quotes`, `${c.accepted} von ${c.checked} durch ihre Zitate belegt`);
      return e.summary || T("done", "fertig"); },
    "delegate": () => `${T("asks", "beauftragt")} ${AGENT_TITLE[e.to] || e.to}: ${TASK()[e.to] || e.instruction || ""}`,
    "fact.located": () => T(`found ${e.quotes} exact quote(s) for “${questionOf(e.fact)}”`, `${e.quotes} wörtliche Stelle(n) gefunden zu «${questionOf(e.fact)}»`),
    "fact.accepted": () => T(`supports “${questionOf(e.fact)}”`, `bestätigt «${questionOf(e.fact)}»`),
    "fact.rejected": () => `${T(`does not accept “${questionOf(e.fact)}”`, `bestätigt «${questionOf(e.fact)}» nicht`)}${e.reason ? `: ${e.reason}` : ""}`,
    "document.recorded": () => `${needOf(e.document)}: ${word(e.status)}`, "document.accepted": () => `${T("confirms", "bestätigt")} ${needOf(e.document)}`,
    "document.rejected": () => T(`does not accept ${needOf(e.document)}`, `bestätigt ${needOf(e.document)} nicht`), "process.changed": () => ({ add_document: T("adds a document need for this case", "verlangt für diesen Fall ein weiteres Dokument"),
      add_question: T("adds a question for this case", "ergänzt eine Frage für diesen Fall"), add_step: T("adds a step for this case", "ergänzt einen Schritt für diesen Fall") }[e.op]
      || T("changes the process for this case", "passt den Prozess für diesen Fall an")),
    "reading.scanned": () => T(`reads ${e.pages} scanned page(s) of ${fileName(e.file)}`, `liest ${e.pages} gescannte Seite(n) von ${fileName(e.file)}`),
    "reading.progress": () => T(`${e.done} of ${e.of} pages read`, `${e.done} von ${e.of} Seiten gelesen`),
    "reading.segmented": () => T(`found ${e.documents} documents in ${fileName(e.file)}`, `${e.documents} Dokumente in ${fileName(e.file)} erkannt`),
    "reading.instructions": () => T(`${fileName(e.file)} contains text addressed to an AI; it is treated as evidence, never followed`,
                                   `${fileName(e.file)} enthält Text, der sich an die KI richtet; er gilt als Inhalt und wird nicht befolgt`),
    "fact.conflicting": () => T(`two independent readings differ on “${questionOf(e.fact)}”; a person decides`,
                                `zwei unabhängige Lesungen widersprechen sich bei «${questionOf(e.fact)}»; ein Mensch entscheidet`),
    "learning.withheld": () => T("a learning proposal with personal details was withheld", "ein Lernvorschlag mit Personendaten wurde zurückgehalten"),
    "reading.photo": () => T(`describes the photo ${fileName(e.file)}`, `beschreibt das Foto ${fileName(e.file)}`),
    "reading.unread": () => T(`${e.pages} page(s) of ${fileName(e.file)} could not be read`, `${e.pages} Seite(n) von ${fileName(e.file)} nicht lesbar`),
    "update.started": () => T(`updates the case with ${(e.files || []).map(fileName).join(", ")}`, `aktualisiert den Fall mit ${(e.files || []).map(fileName).join(", ")}`),
    "record.recorded": () => T(`${e.entries} entr${e.entries === 1 ? "y" : "ies"} of the course of the case recorded`, `${e.entries} Eintr${e.entries === 1 ? "ag" : "äge"} im Verlauf festgehalten`),
    "agent.skipped": () => e.skipped === "result_checker" ? T("the result checker does not run in an update", "der Ergebnisprüfer läuft in einer Aktualisierung nicht")
      : T(`${AGENT_TITLE[e.skipped] || e.skipped} not needed`, `${AGENT_TITLE[e.skipped] || e.skipped} nicht nötig`),
    "tool": () => e.tool === "read_file" ? `${T("reads", "liest")} ${fileName(e.file)}` : e.tool === "search" ? `${T("searches", "sucht")} «${e.query}»`
      : e.tool === "record_fact" && e.target ? T(`records “${questionOf(e.target)}”`, `hält fest: «${questionOf(e.target)}»`)
      : e.tool === "record_document" && e.target ? T(`records ${needOf(e.target)}`, `hält fest: ${needOf(e.target)}`)
      : (LANG === "de" && TOOL_DE[e.tool]) || e.tool.replace(/_/g, " "),
  }[e.kind];
  return what ? what() : e.kind;
}
const PERIOD_RE = /^(\d{1,3}) (days|weeks|months|years) (from|before) (\d{4})-(\d{2})-(\d{2})$/;
function computedDate(v) {
  // A stated period and its anchor ("5 years before 2024-09-05"): the date is our arithmetic, shown as such, never as a fact.
  const m = PERIOD_RE.exec(String(v || ""));
  if (!m) return null;
  const n = Number(m[1]) * (m[3] === "before" ? -1 : 1), d = new Date(Date.UTC(+m[4], +m[5] - 1, +m[6])), day = d.getUTCDate();
  if (m[2] === "days" || m[2] === "weeks") d.setUTCDate(day + n * (m[2] === "weeks" ? 7 : 1));
  else { d.setUTCMonth(d.getUTCMonth() + n * (m[2] === "years" ? 12 : 1)); if (d.getUTCDate() !== day) d.setUTCDate(0); }
  const iso = d.toISOString().slice(0, 10);
  const units = { days: ["days", "Tage"], weeks: ["weeks", "Wochen"], months: ["months", "Monate"], years: ["years", "Jahre"] }[m[2]];
  return { date: m[2] === "years" ? iso.slice(0, 4) : iso,
           stated: T(`${m[1]} ${units[0]} ${m[3]} ${m[4]}-${m[5]}-${m[6]}`, `${m[1]} ${units[1]} ${m[3] === "from" ? "ab" : "vor"} ${m[6]}.${m[5]}.${m[4]}`) };
}
const valueText = (v) => {
  const c = computedDate(v);
  if (c) return T(`≈ ${c.date} (computed from: ${c.stated})`, `≈ ${c.date} (berechnet aus: ${c.stated})`);
  return v === true ? T("yes", "ja") : v === false ? T("no", "nein") : v === "none" ? T("none", "keine") : String(v);
};
const learnAction = (a) => ({ new: T("new", "neu"), refine: T("refine", "verfeinern"), contradict: T("contradict", "widerspricht") }[a] || a);

// ---------- case workers' feedback on a prepared case ----------
// One verdict per person and item. Notes stay with the case; only counts are evaluated.
function ratedRun() { return S.data && S.data.lastCompleted ? S.data.lastCompleted.id : null; }
function verdictOf(target) { const row = (S.data.feedback || []).find((f) => f.target === target && f.by === S.me); return row ? row.verdict : null; }
function rate(target) {
  if (!ratedRun()) return "";
  const v = verdictOf(target);
  return `<span class="cp-rate" role="group" aria-label="${T("Your feedback", "Ihre Rückmeldung")}">
    <button type="button" data-rate="${raw(target)}" data-verdict="correct" aria-pressed="${v === "correct"}" title="${T("Correct", "Stimmt")}" aria-label="${T("Correct", "Stimmt")}">${icon("tick")}</button>
    <button type="button" data-rate="${raw(target)}" data-verdict="wrong" aria-pressed="${v === "wrong"}" title="${T("Not correct", "Stimmt nicht")}" aria-label="${T("Not correct", "Stimmt nicht")}">${icon("xcircle")}</button></span>`;
}
async function sendRating(button) {
  const target = button.dataset.rate, verdict = verdictOf(target) === button.dataset.verdict ? null : button.dataset.verdict;
  const response = await api(`/api/runs/${ratedRun()}/feedback`, { method: "PUT", body: JSON.stringify({ target, verdict }) });
  S.data.feedback = response.feedback;
  renderCase();
}
function feedbackLine() {
  const mine = (S.data.feedback || []).filter((f) => f.by === S.me && f.verdict !== "done");
  const right = mine.filter((f) => f.verdict === "correct").length, wrong = mine.length - right;
  return `<p class="cp-muted cp-feedback-line">${icon("check")}${T("Mark each item as correct or not. Your feedback stays with the case; only the counts are evaluated.",
    "Markieren Sie, was stimmt und was nicht. Ihre Rückmeldungen bleiben beim Fall; ausgewertet werden nur Anzahlen.")}${mine.length ? ` <b>${T(`${right} correct · ${wrong} not correct`, `${right} stimmt · ${wrong} stimmt nicht`)}</b>` : ""}</p>`;
}
const questionOf = (id) => { const f = facts().find((x) => x.id === id); return f ? questionLabel(f) : T("a question added for this case", "eine für diesen Fall ergänzte Frage"); };
const needOf = (id) => {
  const d = ((S.data.process || {}).documents || []).find((x) => x.id === id) || (((liveState() || {}).state || {}).documents || []).find((x) => x.document === id);
  return d ? d.title : T("a document added for this case", "ein für diesen Fall ergänztes Dokument");
};
const clip = (text, n) => { const t = String(tr(text)); return t.length > n ? `${t.slice(0, n - 1)}…` : t; };
const reducedMotion = () => Boolean(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
// Marks an element as new the first time it is drawn, so it enters once and stays still on later polls.
function enter(key) { if (S.shown.has(key)) return ""; S.shown.add(key); return " enter"; }

// The step an agent is on: how long it has been on it, and a bar that shows real progress when there is a count
// (pages read) and keeps moving otherwise, so a long model call never looks like a pause.
function activeRow(text, since) {
  const started = since ? since.seen || Date.parse(since.at) : Date.now();
  const seconds = Math.max(0, Math.round((Date.now() - started) / 1000));
  const elapsed = seconds < 60 ? `${seconds} s` : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")} min`;
  const count = since && since.kind === "reading.progress" && since.of ? Math.round((100 * since.done) / since.of) : null;
  const bar = count === null ? '<span class="cp-run moving"></span>' : `<span class="cp-run" style="width:${count}%"></span>`;
  return `<li class="active"><span class="cp-spinner"></span><span class="cp-grow">${esc(text)}</span>
    <span class="cp-elapsed" title="${T("on this step for", "an diesem Schritt seit")} ${elapsed}">${elapsed}</span><span class="cp-track" aria-hidden="true">${bar}</span></li>`;
}

// A redraw replaces the elements, which would restart every spinner and moving bar at its first frame; start each one
// at the phase the clock says, so the motion is continuous across redraws.
function keepMotion(root) {
  const now = performance.now();
  root.querySelectorAll(".cp-spinner").forEach((el) => { el.style.animationDelay = `-${(now % 1000) / 1000}s`; });
  root.querySelectorAll(".cp-run.moving").forEach((el) => { el.style.animationDelay = `-${(now % 1600) / 1000}s`; });
}

function livePanel(live) {
  const agent = activeAgent() || "lead";
  const mine = S.events.filter((e) => e.agent === agent && !["agent.start", "process.state", "reading.saved"].includes(e.kind)).slice(-4);
  const target = S.events.slice().reverse().find((e) => e.agent === agent && (e.target || e.fact || e.document));
  const title = target ? (target.fact || (target.target && facts().some((f) => f.id === target.target)) ? questionOf(target.fact || target.target) : needOf(target.document || target.target))
    : TASK()[agent] || AGENT_TITLE[agent];
  const rows = mine.map((e, i) => i === mine.length - 1 ? activeRow(describe(e), e)
    : `<li>${icon("check")}${esc(describe(e))}</li>`).join("") || activeRow(T("Starting", "Beginnt"), S.events[S.events.length - 1]);
  return `<aside><section class="cp-card cp-plan"><h3>${T(`Building “${esc(title)}”`, `In Arbeit: «${esc(title)}»`)}</h3><ol>${rows}</ol></section>
    ${live ? liveDocuments(live) : ""}
    <div class="cp-agent-chip"><span class="cp-hex">${icon(AGENT_ICON[agent])}</span>${esc(AGENT_TITLE[agent])}
      ${S.follow ? "" : `<button class="cp-link" id="follow" type="button">${icon("right")}${T("Show what the agents read", "Zeigen, was die Agenten lesen")}</button>`}</div>
    <details style="margin-top:14px"><summary class="cp-link">${T("Work log", "Arbeitsprotokoll")}</summary>${workLog()}</details></aside>`;
}

function factCards() {
  const cite = liveCite();
  if (!cite) return "";
  const event = S.events.slice().reverse().find((e) => e.cite);
  return `<div class="cp-facts">${["file", "claim"].map((k, i) => k === "file"
      ? `<div class="cp-fact">${icon("doc")}<span>${esc(fileName(cite.file))}${cite.page ? `, ${T("page", "Seite")} ${cite.page}` : ""}</span></div>`
      : `<span>+</span><div class="cp-fact">${icon(event && event.fact ? "check" : "folder")}<span>${esc(event && event.fact ? questionOf(event.fact) : needOf(event && event.document))}</span></div>`).join("")}<span class="cp-tie" aria-hidden="true"><i></i></span></div>`;
}

function workLog() {
  const events = (running() ? S.events : ((result() || {}).events || [])).filter((e) => e.kind !== "process.state");
  return `<ul class="cp-log">${events.map((e) => `<li><b>${esc(AGENT_TITLE[e.agent] || e.agent)}</b><span>${esc(describe(e))}</span></li>`).join("")}</ul>`;
}

// ---------- the process forming while the agents work ----------
// The agents report where the case stands after each finding (process.state): the path through the process, which
// steps the source checker has confirmed, and every document need under the step that needs it.
function liveState() {
  if (!running()) return null;
  let state = null, graph = null;
  for (const e of S.events) if (e.kind === "process.state") { state = e; if (e.graph) graph = e.graph; }
  return state && graph ? { state, graph, steps: Object.fromEntries(graph.steps.map((s) => [s.id, s])) } : null;
}
// A process step's title without its role prefix ("KI/System:", "User:"), cut after its first clause when long;
// the full title stays one hover away.
function shortTitle(title) {
  let text = String(title || "").replace(/^(KI\/System|User\/VN|User|Kunde|System|Entscheidung)\s*:\s*/i, "");
  if (text.length > 64) {
    const cut = text.search(/(\. |; | — | → )/);
    if (cut >= 12) text = text.slice(0, cut);
  }
  return clip(text, 64);
}
// A step whose way on depends on one answer is shown as that question; any other step by its title.
function stepLabel(step) {
  const asks = step.asks || [];
  const fact = asks.length === 1 && facts().find((f) => f.id === asks[0]);
  return fact ? questionLabel(fact) : shortTitle(step.title);
}
const branchLabel = (edge, steps) => edge.label || (steps[edge.to] || {}).title || edge.to;

function liveSpine(live) {
  const { state, steps } = live;
  const path = state.path, start = Math.max(0, path.length - 5);
  const nodes = start ? [`<div class="cp-q more"><span class="cp-ring">+${start}</span><span class="cp-q-label">${T(`${start} earlier step${start > 1 ? "s" : ""}`, `${start} frühere${start > 1 ? "" : "r"} Schritt${start > 1 ? "e" : ""}`)}</span></div>`] : [];
  path.slice(start).forEach((row, k) => {
    const step = steps[row.step] || { title: row.step, next: [] };
    const after = path[start + k + 1];
    const cls = row.state === "current" ? "building" : row.confirmed ? "done" : "located";
    // At a fork the case passed, the branches it did not take fall away.
    const dropped = after && !row.either && (step.next || []).length > 1 ? step.next.filter((e) => e.to !== after.step) : [];
    const end = row.state === "terminal" ? `<small class="cp-q-end">${T("End of the process", "Prozessende")}</small>` : "";
    nodes.push(`<div class="cp-q ${cls}${row.state === "terminal" ? " end" : ""}${enter(`node:${row.step}`)}" data-step-node="${raw(row.step)}" title="${esc(step.title)}">
      <span class="cp-ring">${cls === "done" ? icon("tick") : ""}</span><span class="cp-q-label">${esc(stepLabel(step))}</span>${end}
      ${dropped.length ? `<span class="cp-dropped">${dropped.map((e) => `<s class="${enter(`drop:${row.step}:${e.to}`).trim()}">${esc(clip(branchLabel(e, steps), 60))}</s>`).join("")}</span>` : ""}</div>`);
  });
  // Where the case can go next: the branches of the open question, or the one next step.
  const last = path[path.length - 1], open = last && last.state === "current" ? (steps[last.step] || {}).next || [] : [];
  if (open.length > 1) {
    nodes.push(`<div class="cp-q fork${enter(`fork:${last.step}`)}"><div class="cp-fork">${open.map((e) => `<span>${esc(clip(branchLabel(e, steps), 70))}</span>`).join("")}</div>
      <span class="cp-q-label">${T("Decided by the answer", "Entscheidet die Antwort")}</span></div>`);
  } else if (open.length === 1 && steps[open[0].to]) {
    nodes.push(`<div class="cp-q waiting"><span class="cp-ring"></span><span class="cp-q-label">${esc(stepLabel(steps[open[0].to]))}</span></div>`);
  }
  return `<div class="cp-spine live" aria-label="${T("The case’s process, forming from its files", "Der Prozess des Falls, aus den Dokumenten aufgebaut")}">${nodes.join("")}</div>`;
}

function liveDocuments(live) {
  const { state, graph, steps } = live;
  const order = Object.fromEntries(state.path.map((r, i) => [r.step, i]));
  const docs = state.documents.slice().sort((a, b) => (order[a.step] ?? 1e3) - (order[b.step] ?? 1e3));
  const counted = docs.filter((d) => !["suggested", "optional"].includes(d.required));
  const found = counted.filter((d) => d.status === "present" && d.verdict !== "rejected").length;
  const missing = counted.filter((d) => ["missing", "unusable"].includes(d.status)).length;
  const rows = docs.map((d) => {
    const mark = d.status === "present" && d.verdict !== "rejected" ? `<span class="${d.verdict === "accepted" ? "ok" : "found"}" title="${d.verdict === "accepted" ? T("found and confirmed", "gefunden und bestätigt") : T("found, being checked", "gefunden, wird geprüft")}">${icon("tick")}</span>`
      : ["missing", "unusable"].includes(d.status) ? `<span class="no" title="${esc(word(d.status))}">${icon("xcircle")}</span>` : `<span class="open" title="${T("not looked for yet", "noch nicht gesucht")}"></span>`;
    const step = d.step && steps[d.step];
    const origin = d.knowledge ? `<span class="cp-kv">${icon("memory")}${T("Knowledge", "Wissen")} v${esc(d.version)} ${d.suggested ? T("suggested", "vorgeschlagen") : T("used", "genutzt")}</span>`
      : d.edit && d.by_agent ? `<span class="cp-kv add">${icon(d.legal_basis ? "law" : "plus")}${d.legal_basis ? T(`required by law (${esc(d.legal_basis)})`, `nach Gesetz verlangt (${esc(d.legal_basis)})`)
        : T("suggested for this case", "für diesen Fall vorgeschlagen")}</span>` : "";
    return `<li class="st-${raw(d.status)}${enter(`doc:${d.document}`)}" data-doc="${raw(d.document)}">${mark}<span><b>${esc(d.title)}</b>
      <small>${step ? `${T("for", "für")} «${esc(clip(stepLabel(step), 64))}»` : T("for the whole case", "für den ganzen Fall")}${d.required === "depends" ? (d.questions && d.questions.length ? T(` · if the answer requires it: ${esc(d.questions.join(" / "))}`, ` · falls die Antwort es verlangt: ${esc(d.questions.join(" / "))}`) : T(" · if an open answer requires it", " · falls eine offene Antwort es verlangt")) : ""}</small>${origin}</span></li>`;
  }).join("");
  const used = (graph.knowledge || []).filter((k) => !docs.some((d) => d.knowledge === k.item));
  const more = used.map((k) => `<p class="cp-kv">${icon("memory")}${T("Knowledge", "Wissen")} v${esc(k.version)} ${T("used", "genutzt")}: ${esc(clip(knowledgeTitle(k), 48))}</p>`).join("");
  if (!rows && !more) return "";
  return `<section class="cp-card cp-docs" aria-label="${T("Documents this process needs", "Dokumente, die dieser Prozess verlangt")}">
    <h3>${icon("folder")}${T("Documents", "Dokumente")}<span>${T(`${found} found · ${missing} missing or unusable`, `${found} gefunden · ${missing} fehlen oder unbrauchbar`)}</span></h3><ul>${rows}</ul>${more}</section>`;
}

// One point of attention: where the working agent's latest operation is, in the source, the process or the checklist.
function attentionTarget(live) {
  for (let i = S.events.length - 1; i >= 0; i -= 1) {
    const e = S.events[i];
    if (["process.state", "agent.end", "reading.progress", "reading.saved"].includes(e.kind)) continue;
    const hit = $("#live-hit");
    if (e.cite && hit && e.cite.file === S.file) return { el: hit, key: `hit:${e.seq}`, hit: true };
    if (e.document) { const row = document.querySelector(`[data-doc="${CSS.escape(e.document)}"]`); if (row) return { el: row.querySelector("b") || row, key: `doc:${e.seq}` }; }
    if (e.fact && live) {
      const step = live.state.path.find((r) => ((live.steps[r.step] || {}).asks || []).includes(e.fact));
      const node = step && document.querySelector(`[data-step-node="${CSS.escape(step.step)}"] .cp-ring`);
      if (node) return { el: node, key: `fact:${e.seq}` };
    }
    if (e.kind === "tool" && e.file) {  // the file being read: its name above the source when shown, else its row in the sources
      const el = e.file === S.file ? $(".cp-doc-toolbar .name") : document.querySelector(`.cp-source[data-file="${CSS.escape(e.file)}"] .cp-source-label`);
      if (el) return { el, key: `tool:${e.seq}` };
    }
    break;
  }
  const row = $(".cp-plan li.active");
  return row ? { el: row, key: "plan" } : null;
}
function placeAttention(on, live) {
  let pointer = document.getElementById("cp-attention");
  if (!on) { if (pointer) pointer.hidden = true; return; }
  if (!pointer) {
    pointer = Object.assign(document.createElement("div"), { id: "cp-attention", hidden: true });
    pointer.setAttribute("aria-hidden", "true");
    document.body.appendChild(pointer);
  }
  const agent = activeAgent() || "lead";
  if (pointer.dataset.agent !== agent) {
    pointer.dataset.agent = agent;
    pointer.innerHTML = `<svg class="arrow" viewBox="0 0 24 24"><path d="M3 2 21 10.5l-7.6 2.3L10.2 21z"/></svg><span class="cp-hex">${icon(AGENT_ICON[agent])}</span>`;
  }
  const target = attentionTarget(live);
  const hit = $("#live-hit");
  if (!target) { pointer.hidden = true; if (hit) hit.classList.add("lit"); return; }
  const rects = target.el.getClientRects();
  const r = target.hit && rects.length ? rects[rects.length - 1] : target.el.getBoundingClientRect();
  const x = Math.round(r.right + window.scrollX - 4), y = Math.round(r.bottom + window.scrollY - 6);
  const first = pointer.hidden;
  pointer.classList.toggle("still", first);
  pointer.hidden = false;
  pointer.style.transform = `translate(${x}px, ${y}px)`;
  if (first) requestAnimationFrame(() => pointer.classList.remove("still"));
  // A new quote is lit once the pointer has arrived at it; a quote the pointer has moved on from stays lit.
  if (hit && !hit.classList.contains("lit")) {
    if (!target.hit || first || reducedMotion()) { hit.classList.add("lit"); if (target.hit) S.litKey = target.key; }
    else setTimeout(() => { S.litKey = target.key; const now = $("#live-hit"); if (now) now.classList.add("lit"); }, 520);
  }
}

// ---------- process (02) and edits (03) ----------
function graphModel() {
  const process = S.data.process, evaluation = S.data.evaluation;
  if (!process || !evaluation) return null;
  const steps = Object.fromEntries(process.steps.map((s) => [s.id, s]));
  const path = evaluation.path.map((p) => ({ ...p, step: steps[p.step] }));
  const seen = new Set(path.map((p) => p.step.id));
  const last = path[path.length - 1];
  const upcoming = [];
  let frontier = last ? (last.step.next || []).map((e) => e.to) : [];
  while (frontier.length && upcoming.length < 4) {
    const id = frontier.shift();
    if (seen.has(id)) continue;
    seen.add(id);
    upcoming.push({ state: "waiting", step: steps[id] });
    frontier = frontier.concat((steps[id].next || []).map((e) => e.to));
  }
  return { steps, path, nodes: path.concat(upcoming) };
}

function originLabel(step) {
  const refs = step.source_refs || [];
  if (refs.some((r) => r.startsWith("edit#"))) return `<span class="from edit">${T("Changed for this case", "Für diesen Fall geändert")}</span>`;
  return "";
}

// ---------- Prozess: the steps in order, the current one, and the facts that decided each, with their sources ----------
// What a branch rests on: the facts its condition reads.
function factsIn(when) {
  if (!when || when === true || typeof when !== "object") return [];
  if (Array.isArray(when)) return when.flatMap(factsIn);
  return [...(when.fact ? [when.fact] : []), ...["all", "any"].flatMap((k) => (when[k] || []).flatMap(factsIn)), ...(when.not ? factsIn(when.not) : [])];
}
// A value as a handler writes it: ja/nein, a day as 14.08.2024, words without underscores.
function plainValue(v) {
  if (v === true) return T("yes", "ja");
  if (v === false) return T("no", "nein");
  if (Array.isArray(v)) return v.map(plainValue).join(", ");
  const c = computedDate(v);
  if (c) return c.date.length === 10 ? dateText(c.date) : c.date;
  return isoDay(String(v ?? "")).replace(/_/g, " ");
}
function factLine(id) {
  const f = item("fact", id);
  if (!f || f.value === null || f.value === undefined || f.value === "") return "";
  const src = (f.evidence || []).find((e) => e.file);
  return `<li class="cp-step-fact" data-item="${raw(f.item_id)}">${esc(shortFact(id))}: <b>${esc(plainValue(f.value))}</b>${src ? sourceChip(src) : f.verdict === "set_by_handler" ? ` <span class="cp-muted">· ${T("your decision", "Ihr Entscheid")}</span>` : ""}</li>`;
}
// The decisions of the step the case is at: the cover check (while no later stage settles it), the handler's own decisions
// of this stage, and what a prescribed letter rests on; each answered here as on the card.
function stepDecisions(stepId) {
  const late = ["gegenpartei", "mandat", "abwicklung"].includes(stepId);
  const needs = (S.data.draft || {}).needs || [];
  const waiting = ((S.data.evaluation || {}).waiting_for || []).map((w) => w.fact);
  const set = (S.data.edits || []).filter((e) => e.status === "active" && e.op === "set_fact").map((e) => e.args.fact);
  const own = (S.data.items || []).filter((i) => i.kind === "fact" && (i.values || []).length && !chatOnly().has(i.key) && i.key !== "deckung" && !coverFacts().has(i.key)
    && !item("letter_question", i.key) && (needs.includes(i.key) || ((waiting.includes(i.key) || set.includes(i.key)) && /Entscheid/.test((i.label || {}).de || ""))
      || (i.key === "aussichten" && item("check", "aussichten"))));
  const sum = item("cover", "summary");
  const cover = sum && !late ? `<li class="cp-step-decide" data-item="cover:summary"><span>${T("Cover", "Deckung")} <span class="cp-muted">· ${esc(String(sum.value || "").replace(/^Deckung: /, ""))}</span></span>
      <span class="cp-point-actions">${coverButtons()}<button class="cp-link cp-quiet-link" data-cover-toggle aria-expanded="${Boolean(S.coverOpen)}">${T("check", "prüfen")}</button></span>
      ${S.coverOpen ? coverPanel() : ""}${S.coverDecline ? `<p class="cp-reasons cp-cover-why"><span class="cp-muted">${T("Which point fails?", "Welcher Punkt ist nicht erfüllt?")}</span>
      ${(S.data.items || []).filter((i) => i.kind === "cover" && i.key !== "summary").map((x) => `<button class="cp-chip" data-cover-reason="${raw(x.key)}">${esc(x.title)}</button>`).join("")}<button class="cp-chip" data-cover-reason="anderer Grund">${T("other reason", "anderer Grund")}</button></p>` : ""}</li>` : "";
  const prospects = item("check", "aussichten");
  const rows = own.map((f) => `<li class="cp-step-decide" data-item="${raw(f.item_id)}"><span>${esc(plainQuestion((f.label || {}).de))}${f.key === "aussichten" && prospects ? passagesToggle(`check:aussichten`, prospects.law) : ""}</span><span class="cp-point-actions">${decisionButtons(f.key)}</span></li>`).join("");
  return cover + rows + checkRows();
}
const passagesToggle = (key, law) => (law || []).length ? ` ${clauseTag(key, law)}` : "";
// What a prescribed letter rests on: the written demand before an end of benefits, consent before a settlement.
function checkRows() {
  return (S.data.items || []).filter((i) => i.kind === "check" && i.key !== "aussichten").map((c) => {
    const missing = c.key === "androhung" && c.value === "fehlt", others = c.key === "androhung" && c.value === "andere";
    const override = (missing || others) && c.decided !== true ? `<span class="cp-point-actions"><button class="cp-button cp-small" data-decide="leistungen_einstellen" data-value="ja">${T("End benefits all the same", "Leistungen trotzdem einstellen")}</button></span>` : "";
    return `<li class="cp-step-decide" data-item="${raw(c.item_id)}"><span>${esc(plainQuestion((c.label || {}).de))}${c.key === "androhung" ? `: <b class="${missing || others ? "cp-flag" : ""}">${missing ? T("missing", "fehlt") : others ? T("only by others", "nur durch Dritte") : T("in the file", "in der Akte")}</b>` : ""}
      ${clauseTag(c.item_id, c.law || c.clauses || [])}${(c.lines || []).map((l) => `<br><span class="cp-muted">${esc(isoDay(l))}</span>`).join("")}${sourceChips(c.evidence)}</span>${override}</li>`;
  }).join("");
}
function processView() {
  const model = graphModel();
  if (!model) return `<p class="cp-empty">${S.data.case.workflow_id ? T("Prepare the case to build its process", "Bereiten Sie den Fall vor, um seinen Prozess aufzubauen")
    : T("Choose a process under «More», or prepare the case", "Prozess unter «Mehr» wählen oder den Fall vorbereiten")}</p>`;
  const ev = S.data.evaluation, sc = scr();
  const current = model.path.find((p) => p.state === "current") || model.path[model.path.length - 1];
  if (!S.step || !model.steps[S.step]) S.step = current.step.id;
  const decided = (i) => {  // the facts that took the case from this step to the next
    const row = model.path[i], next = model.path[i + 1];
    if (!next) return [];
    const edge = (row.step.next || []).find((e) => e.to === next.step.id);
    return [...new Set(factsIn(edge && edge.when))];
  };
  const rows = model.path.map((n, i) => {
    const state = n.state === "passed" || n.state === "terminal" ? "done" : n.state === "current" ? "now" : "next";
    const mark = { done: "✓", now: "●", next: "○" }[state];
    const name = S.editing ? `<button class="cp-link cp-step-pick" data-step="${raw(n.step.id)}" aria-pressed="${S.step === n.step.id}">${esc(shortTitle(n.step.title))}</button>` : `<b>${esc(shortTitle(n.step.title))}</b>`;
    const facts = state === "done" ? decided(i).map(factLine).join("") : "";
    const asked = new Set(["deckung", ...((S.data.draft || {}).needs || [])]);  // a decision asked below is not also «offen»
    const waiting = state === "now" ? (ev.waiting_for || []).filter((w) => !asked.has(w.fact)).map((w) => `<li class="cp-step-open" data-item="fact:${raw(w.fact)}"><span class="cp-muted">${T("open", "offen")}:</span> ${esc(shortFact(w.fact))}</li>`).join("") : "";
    const here = state === "now" && !ev.outcome ? `${sc.title ? `<li class="cp-step-action">${T("Next", "Als Nächstes")}: ${esc(sc.title)}</li>` : ""}${stepDecisions(n.step.id)}
        ${sc.missing !== undefined ? `<li class="cp-step-docs"><a class="cp-link cp-quiet-link" href="#/case/${raw(S.route.id)}/document_finder" data-missing="${sc.missing}">${T("Documents", "Unterlagen")} · ${T(`${sc.missing} missing`, `${sc.missing} fehl${sc.missing === 1 ? "t" : "en"}`)}</a></li>` : ""}` : "";
    return `<li class="cp-step ${state}" data-item="step:${raw(n.step.id)}"><span class="cp-step-mark">${mark}</span><div class="cp-step-body">${name}${state === "now" ? ` <span class="cp-muted">· ${T("now", "jetzt")}</span>` : ""}${originLabel(n.step)}
      ${facts || waiting || here ? `<ul class="cp-step-facts">${facts}${waiting}${here}</ul>` : ""}</div></li>`;
  }).join("");
  const end = ev.outcome ? `<li class="cp-step done"><span class="cp-step-mark">✓</span><div class="cp-step-body"><b>${T("End", "Abschluss")}: ${esc(ev.outcome.title)}</b></div></li>` : "";
  // a case the file shows further along starts at its stage: the stages before it, passed as the file shows
  const onPath = new Set(model.path.map((p) => p.step.id)), first = (model.path[0] || {}).step;
  const order = (S.data.process.steps || []).map((x) => x.id);
  const behind = first ? (ev.reached || []).filter((id) => !onPath.has(id) && model.steps[id] && order.indexOf(id) < order.indexOf(first.id))
    .sort((a, b) => order.indexOf(a) - order.indexOf(b)) : [];
  const before = behind.map((id) => `<li class="cp-step done" data-item="step:${raw(id)}"><span class="cp-step-mark">✓</span><div class="cp-step-body"><b>${esc(shortTitle(model.steps[id].title))}</b> <span class="cp-muted">· ${T("as the file shows", "laut Akte")}</span></div></li>`).join("");
  // what may follow the current step: its branches, one line, never a sequence the case has not taken
  const after = ev.outcome ? [] : [...new Set((current.step.next || []).map((e) => (model.steps[e.to] || {}).title).filter(Boolean))];
  const ahead = after.length ? `<li class="cp-step next"><span class="cp-step-mark">○</span><div class="cp-step-body"><span class="cp-muted">${T("then, depending on the case", "danach, je nach Fall")}</span>
      <ul class="cp-step-then">${after.map((t) => `<li>${esc(shortTitle(t))}</li>`).join("")}</ul></div></li>` : "";
  const change = S.lastEdit ? (S.lastEdit.op ? beforeNow() : `<p class="cp-change">${esc(changeLine(S.lastEdit.diff))} <button class="cp-link" id="undo">${T("Undo", "Rückgängig")}</button></p>`) : "";
  return `<section class="cp-card cp-process"><header class="cp-process-head"><h1 class="cp-title">${T("Process", "Prozess")}${S.data.process.short_title ? ` <span class="cp-muted">· ${esc(S.data.process.short_title)}</span>` : ""}</h1>
      <button class="cp-link cp-quiet-link" id="edit-open" aria-expanded="${Boolean(S.editing)}">${T("Change for this case", "Für diesen Fall ändern")}</button></header>
    ${change}${S.editing ? editForm(model.steps[S.step]) : tabPicture("process", window.CasePathFlow ? Math.max(440, Math.min(640, window.innerHeight - 330)) : 300)}
    <ol class="cp-steps">${before}${rows}${end}${ahead}</ol></section>`;
}

// What an applied Knowledge item is called: its document need, question or note, from the Knowledge base when loaded.
function knowledgeTitle(applied) {
  const item = (S.knowledge || []).find((k) => k.id === applied.item);
  const content = (item || {}).content || {};
  const need = applied.document && needOf(applied.document);
  return content.title || content.question || content.text || (need !== applied.document && need) || applied.note || applied.item;
}
// "v2 used → v3 proposed": what a learning proposal would change in the Knowledge base once a person releases it.
function proposalVersion(row) {
  const target = row.target && (S.knowledge || []).find((k) => k.id === row.target);
  if (row.action === "refine" && target) return T(`v${target.version} used → v${target.version + 1} proposed`, `v${target.version} genutzt → v${target.version + 1} vorgeschlagen`);
  if (row.action === "contradict" && target) return T(`v${target.version} contradicted`, `v${target.version} widersprochen`);
  return row.action === "new" ? T("v1 proposed", "v1 vorgeschlagen") : "";
}

const OPS = lazy(() => ([["add_document", T("Add a document need", "Dokument verlangen")], ["set_required_when", T("Change when a document is required", "Ändern, wann ein Dokument nötig ist")],
             ["add_question", T("Add a question", "Frage ergänzen")], ["add_step", T("Add a step before this one", "Schritt davor ergänzen")],
             ["set_transition", T("Redirect a branch", "Verzweigung umleiten")], ["rename_step", T("Rename this step", "Schritt umbenennen")]]));

function conditionFields(prefix) {
  const options = facts().map((f) => `<option value="${raw(f.id)}">${esc(questionLabel(f))}</option>`).join("");
  return `<div class="row"><label>${T("Required when", "Nötig, wenn")}<select name="${prefix}-fact"><option value="">${T("Always", "Immer")}</option>${options}</select></label>
    <label>${T("is", "ist")}<select name="${prefix}-value"></select></label></div>`;
}

function editForm(step) {
  const docs = S.data.process.documents.map((d) => `<option value="${raw(d.id)}">${esc(d.title)}</option>`).join("");
  const steps = S.data.process.steps.map((s) => `<option value="${raw(s.id)}">${esc(s.title)}</option>`).join("");
  const edges = (step.next || []).map((e, i) => `<option value="${i}">${esc(e.label || T("next", "weiter"))} → ${esc(S.data.process.steps.find((s) => s.id === e.to).title)}</option>`).join("");
  return `<form class="cp-edit" id="edit-form"><h3>${T(`Edit “${esc(step.title)}”`, `«${esc(step.title)}» bearbeiten`)}</h3>
    <label>${T("Change", "Änderung")}<select name="op">${OPS().map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}</select></label>
    <div data-op="add_document"><label>${T("Document", "Dokument")}<input name="title" maxlength="200" placeholder="${T("e.g. Ventilation record", "z. B. Lüftungsprotokoll")}"></label>
      <label>${T("Why it is needed", "Wozu es nötig ist")}<input name="why" maxlength="400"></label>${conditionFields("add")}</div>
    <div data-op="set_required_when" hidden><label>${T("Document", "Dokument")}<select name="document">${docs}</select></label>${conditionFields("set")}</div>
    <div data-op="add_question" hidden><label>${T("Question", "Frage")}<input name="question" maxlength="300"></label>
      <label>${T("Only require this document when the answer is yes", "Dieses Dokument nur verlangen, wenn die Antwort ja ist")}<select name="gates"><option value="">${T("No document", "Kein Dokument")}</option>${docs}</select></label></div>
    <div data-op="add_step" hidden><label>${T("Step", "Schritt")}<input name="steptitle" maxlength="200" placeholder="${T("e.g. Object to the dismissal in writing", "z. B. Einsprache gegen die Kündigung schreiben")}"></label>
      <label>${T("Why this case needs it", "Wozu dieser Fall ihn braucht")}<input name="stepwhy" maxlength="400"></label>
      <label>${T("Legal basis (optional)", "Rechtsgrundlage (freiwillig)")}<input name="steplaw" maxlength="200" placeholder="${T("e.g. Art. 336b OR", "z. B. Art. 336b OR")}"></label></div>
    <div data-op="set_transition" hidden><label>${T("Branch", "Verzweigung")}<select name="edge">${edges}</select></label><label>${T("Now leads to", "Führt neu zu")}<select name="to">${steps}</select></label></div>
    <div data-op="rename_step" hidden><label>${T("New wording", "Neue Bezeichnung")}<input name="rename" maxlength="200" value="${raw(step.title)}"></label></div>
    <label>${T("Why this changes (required)", "Begründung (Pflicht)")}<textarea name="reason" rows="2" required maxlength="500"></textarea></label>
    <label class="cp-check"><input type="checkbox" name="similar"> ${T("Use for similar cases (a proposal in Knowledge, approved there after its replay)", "Für ähnliche Fälle übernehmen (Vorschlag im Wissen, dort nach dem Nachspielen freigeben)")}</label>
    <div class="row"><button class="cp-button primary">${T("Save change", "Änderung speichern")}</button><button type="button" class="cp-button" id="edit-cancel">${T("Cancel", "Abbrechen")}</button>
      <span class="cp-error" id="edit-error"></span></div></form>`;
}

function valuesFor(factId) {
  const f = facts().find((x) => x.id === factId);
  if (!f) return [];
  return f.type === "enum" ? f.values : f.type === "boolean" ? [true, false] : [];
}

function bindEdit() {
  const form = $("#edit-form");
  if (!form) return;
  const show = () => { for (const el of form.querySelectorAll("[data-op]")) el.hidden = el.dataset.op !== form.op.value; };
  const fillValues = (prefix) => {
    const select = form[`${prefix}-value`], values = valuesFor(form[`${prefix}-fact`].value);
    select.innerHTML = values.map((v) => `<option value='${esc(JSON.stringify(v))}'>${esc(valueText(v))}</option>`).join("");
  };
  form.op.addEventListener("change", show);
  for (const prefix of ["add", "set"]) form[`${prefix}-fact`].addEventListener("change", () => fillValues(prefix));
  $("#edit-cancel").addEventListener("click", () => { S.editing = false; renderCase(); });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const op = form.op.value, step = S.step;
    const condition = (prefix) => form[`${prefix}-fact`].value ? { fact: form[`${prefix}-fact`].value, is: JSON.parse(form[`${prefix}-value`].value) } : null;
    const args = {
      add_document: { title: form.title.value, why: form.why.value, step, required_when: condition("add") },
      set_required_when: { document: form.document.value, required_when: condition("set") },
      add_question: { question: form.question.value, type: "boolean", ...(form.gates.value ? { gates_document: form.gates.value } : {}) },
      add_step: { before: step, title: form.steptitle.value, why: form.stepwhy.value, legal_basis: form.steplaw.value || null },
      set_transition: { step, index: Number(form.edge.value), to: form.to.value },
      rename_step: { step, title: form.rename.value },
    }[op];
    const before = snapshot(op, args);
    try {
      const response = await api(`/api/cases/${S.route.id}/edits`, { method: "POST", body: JSON.stringify({
        op, args, reason: form.reason.value, use_for_similar: form.similar.checked }) });
      S.lastEdit = { ...response, op, args, before };
      S.editing = false;
      await loadCase();
    } catch (error) { $("#edit-error").textContent = error.message; }
  });
  show();
}

function conditionText(condition) {
  if (!condition || condition === true) return T("Always required", "Immer nötig");
  const parts = condition.all || [condition];
  return T("Required when ", "Nötig, wenn ") + parts.map((c) => `${questionOf(c.fact)} = ${valueText(c.is)}`).join(T(" and ", " und "));
}
function snapshot(op, args) {
  const process = S.data.process;
  if (op === "add_document") return T("Not part of this step", "Nicht Teil dieses Schritts");
  if (op === "set_required_when") return `${needOf(args.document)}: ${conditionText((process.documents.find((d) => d.id === args.document) || {}).required_when)}`;
  if (op === "add_question") return T("No such question", "Diese Frage gab es nicht");
  if (op === "add_step") return T(`Next: ${(process.steps.find((s) => s.id === args.before) || {}).title}`, `Danach: ${(process.steps.find((s) => s.id === args.before) || {}).title}`);
  if (op === "set_transition") { const step = process.steps.find((s) => s.id === args.step); const e = step.next[args.index]; return `${e.label || T("Next", "Weiter")} → ${process.steps.find((s) => s.id === e.to).title}`; }
  if (op === "rename_step") return process.steps.find((s) => s.id === args.step).title;
  return "";
}
function nowText(edit) {
  const a = edit.args;
  return { add_document: `${a.title}: ${a.why}`, set_required_when: `${needOf(a.document)}: ${conditionText(a.required_when)}`,
           add_question: a.question, add_step: `${a.title}${a.legal_basis ? ` (${a.legal_basis})` : ""}`, set_transition: `→ ${(S.data.process.steps.find((s) => s.id === a.to) || {}).title}`, rename_step: a.title }[edit.op];
}

function beforeNow() {
  const e = S.lastEdit, diff = e.diff;
  const current = Object.fromEntries(S.data.evaluation.documents.map((d) => [d.document, d]));
  const requiredText = { yes: T("now required", "neu nötig"), depends: T("now depends on an answer", "hängt neu von einer Antwort ab"),
                         suggested: T("now suggested", "neu vorgeschlagen"), optional: T("now optional", "neu freiwillig") };
  const items = diff.documents_added.map((d) => current[d.document] || d).map((d) => `<li class="${d.status === "present" ? "present" : ""}"><span class="x">${icon(d.status === "present" ? "check" : "xcircle")}</span>${esc(d.title)} · ${esc(d.status === "unchecked" ? T("not checked yet", "noch nicht geprüft") : word(d.status))}</li>`)
    .concat(diff.documents_removed.map((d) => `<li><span class="x">${icon("xcircle")}</span>${esc(d.title)} · ${T("no longer needed", "nicht mehr nötig")}</li>`))
    .concat(diff.documents_changed.map((d) => `<li><span class="x">${icon("xcircle")}</span>${esc(needOf(d.document))} · ${esc(requiredText[d.required_after] || word(d.required_after))}</li>`)).join("");
  const recheck = S.data.run && S.data.run.result && S.data.run.result.recheck_of ? T("Checked against the case's files.", "In den Falldokumenten geprüft.") : e.recheck ? T("Checking the case's files for it…", "Wird in den Falldokumenten geprüft…") : "";
  return `<section aria-label="${T("Your change", "Ihre Änderung")}"><div class="cp-before-now">
      <span class="label">${T("BEFORE", "VORHER")}</span><span></span><span class="label now">${T("NOW", "JETZT")} <span class="cp-edited-by">${icon("shield")}${T("Edited by", "Geändert von")} ${esc(e.edit.by)}</span></span>
      <div class="cp-before">${esc(e.before)}</div><div class="cp-arrow">→</div><div class="cp-now">${esc(nowText(e))}</div>
      <span></span><span></span><ul class="cp-missing">${items || `<li class="present"><span class="x">${icon("check")}</span>${T("The checklist did not change", "Die Checkliste hat sich nicht geändert")}</li>`}</ul></div>
    <p class="cp-muted">${esc(recheck)} ${e.knowledge ? T(`Saved for similar cases (${e.knowledge.status === "active" ? "applies to new cases" : "suggested until approved"}).`,
      `Für ähnliche Fälle gespeichert (${e.knowledge.status === "active" ? "gilt für neue Fälle" : "Vorschlag bis zur Freigabe"}).`) : ""}
      <button class="cp-link" id="undo">${T("Undo", "Rückgängig")}</button></p>${memoryChain()}</section>`;
}

function memoryChain() {
  const used = ((S.data.provenance || {}).knowledge || []).filter((k) => k.applied);
  if (!used.length || !S.knowledge) return "";
  const item = S.knowledge.find((k) => k.id === used[0].item);
  if (!item) return "";
  const evidence = (item.evidence || [])[0];
  const doc = S.data.evaluation.documents.find((d) => d.document === used[0].document);
  return `<p class="cp-retrieved">${T(`Retrieved ${used.length} Knowledge item${used.length > 1 ? "s" : ""} from earlier cases`, `${used.length} Wissenseintr${used.length > 1 ? "äge" : "ag"} aus früheren Fällen übernommen`)}</p>
    <div class="cp-memory"><div class="card"><h4>${T("Earlier case source", "Quelle im früheren Fall")} ${icon("check")}</h4>${evidence ? `<span class="boxed">${esc(evidence.quote)}</span>` : `<span class="cp-muted">${T("From a case worker’s change", "Aus der Änderung einer Fallbearbeiterin oder eines Fallbearbeiters")}</span>`}</div>
      <div class="arrow">→</div><div class="card"><h4>${T("Knowledge", "Wissen")} v${used[0].version || item.version} ${T("used", "genutzt")}${used[0].version && item.version > used[0].version ? T(` · now v${item.version}`, ` · jetzt v${item.version}`) : ""} ${icon("shield")}</h4><p><b>${esc(item.content.title || item.content.question || item.content.text)}</b></p>
        <p class="cp-muted">${esc(item.content.why || item.applies_when_text || "")}</p><p class="cp-muted">${T(`Used ${item.stats.uses} times · confirmed ${item.stats.confirmed}`, `${item.stats.uses}× verwendet · ${item.stats.confirmed}× bestätigt`)}${item.stats.contradicted ? T(` · contradicted ${item.stats.contradicted}`, ` · ${item.stats.contradicted}× widersprochen`) : ""}</p></div>
      <div class="arrow">→</div><div class="card"><h4>${T("Result", "Ergebnis")} ${icon("shield")}</h4><p class="headline">${esc(T(`${item.content.title || "Question"} added`, `${item.content.title || "Frage"} ergänzt`))}</p>
        <p>${doc ? esc(doc.status === "present" ? T("Found in this case’s files.", "In den Dokumenten dieses Falls gefunden.") : doc.status === "missing" ? T("Still missing in this case.", "Fehlt in diesem Fall noch.") : T("Not checked yet.", "Noch nicht geprüft.")) : ""}</p></div></div>`;
}

// ---------- other tabs ----------
// The Akte: the file itself beside what the case is (request, parties, the order of events), each event's source one click away.
// What a bundled file contains is listed once, under the file in the case panel (segmentRows), where it also steers the viewer.
function claimView(card) {
  const r = result(), brief = (r && r.brief) || {}, items = S.data.items || [];
  const summary = items.find((i) => i.kind === "summary" && i.value);
  const anliegen = (summary && summary.value) || brief.request || "";
  const timeline = brief.timeline || [];
  const parties = partiesHtml();
  return `${tabPicture("file", 280)}<div class="cp-live"><div>${card}</div><aside>${anliegen || parties || timeline.length ? `<section class="cp-card cp-brief">
      <h2 class="cp-section">${T("Request", "Anliegen")}</h2><p data-item="summary:0">${esc(anliegen) || "—"}</p>
      ${parties ? `<h2 class="cp-section">${T("Parties", "Parteien")}</h2><p data-item="party:0">${parties}</p>` : ""}
      ${timeline.length ? `<h2 class="cp-section">${T("Timeline", "Chronologie")}</h2><div class="cp-lines">${timeline.map((t, i) => {
        const c = (t.citations || [])[0];
        return `<div data-item="timeline:${i}"><time>${esc(isoDay(t.date))}</time><span>${c ? `<button class="cp-link" data-cite-file="${raw(c.file)}" data-page="${c.page || ""}" title="${esc(c.quote)}">${esc(t.event)}</button>` : esc(t.event)}${rate(`timeline:${i}`)}</span></div>`;
      }).join("")}</div>` : ""}
    </section>` : `<p class="cp-empty">${T("Not prepared yet", "Noch nicht vorbereitet")}</p>`}</aside></div>`;
}

function checkerView() {
  const rows = Object.values(recorded("fact")).map((f) => [questionOf(f.fact), f]).concat(Object.values(recorded("document")).map((d) => [needOf(d.document), d]));
  if (!rows.length) return `<p class="cp-empty">${T("The source checker’s verdicts appear here: every finding with the exact sentence it rests on.", "Hier erscheinen die Prüfergebnisse des Quellenprüfers: jede Feststellung mit dem genauen Satz, auf dem sie beruht.")}</p>`;
  return `${ratedRun() ? feedbackLine() : ""}<table class="cp-table"><thead><tr><th>${T("Finding", "Feststellung")}</th><th>${T("Verdict", "Prüfung")}</th><th>${T("Exact sentence", "Wörtliche Stelle")}</th></tr></thead><tbody>${rows.map(([label, row]) => `<tr>
    <td>${esc(label)}${row.value !== undefined && row.value !== null ? `: <b>${esc(row.part || valueText(row.value))}</b>` : row.status ? ` <span class="cp-muted">(${esc(word(row.status))})</span>` : ""}</td>
    <td>${row.verdict === "accepted" ? `<span class="cp-chip good">${T("supported", "belegt")}</span>` : row.verdict === "rejected" ? `<span class="cp-chip bad">${T("not supported", "nicht belegt")}</span><br><small class="cp-muted">${esc(row.verdict_reason || "")}</small>` : `<span class="cp-chip wait">${T("not checked", "nicht geprüft")}</span>`}${rate(row.fact ? `fact:${row.fact}` : `document:${row.document}`)}</td>
    <td>${(row.citations || []).map((c) => `<button class="cp-link" data-cite-file="${raw(c.file)}" data-page="${c.page || ""}">“${esc(c.quote)}”</button><br><small class="cp-muted">${esc(fileName(c.file))}${c.page ? `, ${T("page", "Seite")} ${c.page}` : ""}</small>`).join("<br>") || '<span class="cp-muted">—</span>'}</td></tr>`).join("")}</tbody></table>`;
}

// The Unterlagen: every document the case needs, the missing ones first, in the same count as the letter and the Prozess
// (screen.missing): what it is for, whether it is in the file (with its source) or asked, and «nicht nötig» for a missing one.
function documentsView() {
  const ev = S.data.evaluation, sc = scr();
  if (!ev) return `<p class="cp-empty">${T("The documents appear once the case has a process", "Die Unterlagen erscheinen, sobald der Fall einen Prozess hat")}</p>`;
  const proc = S.data.process || {};
  const docs = (S.data.items || []).filter((i) => i.kind === "document" && !i.part_of);
  const read = Boolean(S.data.screen);  // before a preparation nothing is read: nothing is counted as missing
  const gone = new Set(sc.missing_ids || []);
  const n = sc.missing ?? 0;
  const head = read ? `<h1 class="cp-title" data-missing="${n}">${T("Documents", "Unterlagen")} <span class="cp-muted">· ${T(`${n} missing`, `${n} fehl${n === 1 ? "t" : "en"}`)}</span></h1>`
    : `<h1 class="cp-title">${T("Documents", "Unterlagen")} <span class="cp-muted">· ${T("not read yet", "noch nicht gelesen")}</span></h1>`;
  if (!docs.length) return `${head}<p class="cp-empty">${T("No document needed for this process", "Für diesen Prozess keine Unterlagen verlangt")}</p>`;
  const state = (i) => !read ? [T("not read yet", "noch nicht gelesen"), "wait"] : gone.has(i.item_id) ? (i.status === "unusable" ? [T("unusable", "unbrauchbar"), "bad"] : [T("missing", "fehlt"), "bad"])
    : i.status === "present" ? [T("in the file", "liegt vor"), "good"] : i.status === "unusable" ? [T("unusable", "unbrauchbar"), "wait"]
    : i.required === "depends" ? [T("if needed", "falls nötig"), "wait"] : i.required === "suggested" ? [T("suggestion", "Vorschlag"), "wait"]
    : i.required === "optional" ? [T("optional", "freiwillig"), "wait"] : ["later", "proposed"].includes(i.ask) ? [T("if needed", "bei Bedarf"), "wait"] : [T("not asked", "nicht verlangt"), "wait"];
  const order = (i) => (gone.has(i.item_id) ? 0 : i.status === "present" ? 2 : 1);
  const rows = [...docs].sort((a, b) => order(a) - order(b)).map((i) => {
    const pd = (proc.documents || []).find((d) => d.id === i.key) || {};
    const [word_, chip] = state(i);
    const origin = i.practice || (pd.knowledge ? practiceNote(pd.knowledge) : i.legal_basis || pd.legal_basis || "");
    return `<tr data-item="${raw(i.item_id)}"><td><b>${esc((i.label || {}).de || pd.title || i.key)}</b></td>
      <td>${esc(pd.why || "")}${origin ? `<br><small class="cp-muted">${esc(origin)}</small>` : ""}</td>
      <td><span class="cp-chip ${chip}">${esc(word_)}</span>${i.status === "unusable" && i.reason ? `<br><small class="cp-muted">${esc(clip(i.reason, 160))}</small>` : ""}${gone.has(i.item_id) ? `<br><button class="cp-link cp-quiet-link" data-point-notneeded="${raw(i.key)}">${T("not needed", "nicht nötig")}</button>` : ""}</td>
      <td>${sourceChips(i.evidence) || '<span class="cp-muted">—</span>'}</td></tr>`;
  }).join("");
  return `${head}${read ? tabPicture("documents", 300) : ""}<table class="cp-table cp-docs-table"><thead><tr><th>${T("Document", "Unterlage")}</th><th>${T("What for", "Wozu")}</th><th>${T("State", "Stand")}</th><th>${T("Source", "Beleg")}</th></tr></thead><tbody>${rows}</tbody></table>`;
}

// A text the report fitting shortened says so: nothing is cut silently.
const trimmed = (kind, key) => ((item(kind, key) || {}).trimmed ? ` <span class="cp-chip wait">${T("shortened", "gekürzt")}</span>` : "");

function resultView() {
  const r = result();
  if (!r || !r.answer) return `<p class="cp-empty">${T("Where the case stands in its process, its document checklist, what CasePath proposes to learn and a draft appear here after the case is prepared.", "Stand im Prozess, Dokumenten-Checkliste, Lernvorschläge und ein Entwurf erscheinen hier, sobald der Fall vorbereitet ist.")}</p>`;
  const ev = S.data.evaluation;
  const today = new Date();
  const days = (iso) => Math.round((new Date(iso) - new Date(today.getFullYear(), today.getMonth(), today.getDate())) / 86400000);
  const left = (n) => (n < 0 ? T(`expired ${-n} days ago`, `abgelaufen seit ${-n} Tagen`) : n === 0 ? T("today", "heute") : T(`in ${n} days`, `in ${n} Tagen`));
  const deadlines = (r.deadlines || []).map((d, i) => { const n = days(d.date); return `<li><b>${dateText(d.date)}</b> · ${esc(d.question)} <span class="cp-chip ${n < 0 ? "bad" : n <= 14 ? "wait" : ""}">${Number.isNaN(n) ? "" : left(n)}</span>${rate(`deadline:${i}`)}</li>`; }).join("");
  const summary = (r.case_summary || []).length ? `<section class="cp-card" style="padding:16px 20px;max-width:900px;margin-bottom:18px"><h2 class="cp-section" style="margin-top:0">${T("Case summary", "Fallzusammenfassung")}</h2>
      <dl class="cp-doc-head" style="padding:0;border:0;grid-template-columns:180px 1fr">${r.case_summary.map((f, i) => `<dt>${esc(f.label)}</dt><dd>${esc(f.text)}${rate(`summary:${i}`)}</dd>`).join("")}</dl></section>` : "";
  // after an update the result checker's fields are the full preparation's: «Stand <Datum>», and its draft is no download (C6)
  const stale = r.stale_since ? ` <span class="cp-stale-chip" title="${esc(T(`Before ${r.stale_since.files} new document(s)`, `Vor ${r.stale_since.files} neuen Dokument(en)`))}">${T("As of", "Stand")} ${dateText(r.stale_since.prepared_at)}</span>` : "";
  const draft = r.reply && r.reply.clauses && r.reply.clauses.length && S.data.run && !r.stale_since ? `<a class="cp-button" href="/api/runs/${raw((S.data.lastCompleted || S.data.run).id)}/draft.docx">${T("Draft as .docx", "Entwurf als .docx")}</a>` : "";
  const action = { answer: T("Answer: ", "Klären: "), resolve: T("Not met: ", "Nicht erfüllt: "), obtain: T("Obtain: ", "Einholen: ") };
  const docs = ev ? ev.documents.filter((d) => !["suggested", "optional"].includes(d.required)) : [];
  const present = docs.filter((d) => d.status === "present").length, missing = docs.filter((d) => d.status !== "present").length;
  const position = ev ? `<section class="cp-card" style="padding:16px 20px;max-width:900px;margin-bottom:18px">
      <h2 class="cp-section" style="margin-top:0">${T("Where the case stands in its process", "Stand im Prozess")}</h2>
      <p>${ev.outcome ? `${T("End of the process", "Prozessende")}: <b>${esc(ev.outcome.title)}</b>` : ev.current ? `${T("Current step", "Aktueller Schritt")}: <b>${esc(ev.current.title)}</b>` : ""}
        ${ev.waiting_for.length ? ` · ${T("waiting for", "wartet auf")}: ${ev.waiting_for.map((w) => esc(w.question)).join("; ")}` : ""}</p>
      <p><a href="#/case/${raw(S.route.id)}/document_finder">${T(`Document checklist: ${present} present, ${missing} still needed`, `Dokumenten-Checkliste: ${present} vorhanden, ${missing} noch nötig`)}</a></p>
      ${ev.next_actions.length ? `<h3 class="cp-section" style="font-size:15px">${T("Next steps", "Nächste Schritte")}</h3><ul>${ev.next_actions.map((a) => `<li>${esc(action[a.kind])}${esc(a.text)}${a.kind === "resolve" ? ` <span class="cp-muted">(${esc(valueText(a.value))})</span>` : ""}</li>`).join("")}</ul>` : ""}</section>` : "";
  const learning = (r.learning || []).length ? `<h2 class="cp-section">${T("What CasePath proposes to learn", "Was CasePath lernen möchte")}</h2>
      <p class="cp-muted">${T("Proposals for the Knowledge base. They shape other cases only after a person approves them.", "Vorschläge für das Wissen. Sie prägen andere Fälle erst, wenn ein Mensch sie freigibt.")}</p>
      <ul>${r.learning.map((l) => `<li><b>${esc(learnAction(l.action))}</b> · ${esc(l.title || l.question || l.note)}${proposalVersion(l) ? ` <span class="cp-kv${l.action === "contradict" ? " add" : ""}">${icon("memory")}${esc(proposalVersion(l))}${l.action === "contradict" ? "" : T(" · waits for release", " · wartet auf Freigabe")}</span>` : ""} <span class="cp-muted">— ${esc(l.reason)}</span></li>`).join("")}</ul>
      <p><a href="#/knowledge">${T("Review in Knowledge", "Im Wissen prüfen")}</a></p>` : "";
  const report = `<p><a class="cp-button" href="/api/cases/${raw(S.route.id)}/report.docx?lang=${LANG}">${icon("doc")}${T("Case report as .docx", "Fallbericht als .docx")}</a>
    <span class="cp-muted">${T("Everything above with its sources, for the case file.", "Alles hier mit den Fundstellen, für das Dossier.")}</span></p>`;
  return `${ratedRun() ? feedbackLine() : ""}${report}${position}${summary}${deadlines ? `<h2 class="cp-section" style="margin-top:0">${T("Deadlines", "Fristen")}</h2><ul>${deadlines}</ul>` : ""}
    ${(r.open_points || []).length ? `<h2 class="cp-section">${T("Open points", "Offene Punkte")}${stale}</h2><ul>${r.open_points.map((p, i) => `<li>${esc(p)}${trimmed("open_point", String(i))}${rate(`open_point:${i}`)}</li>`).join("")}</ul>` : ""}
    ${learning}
    <h2 class="cp-section">${T("Short assessment (draft)", "Kurzeinschätzung (Entwurf)")}${stale}</h2><p class="cp-answer">${esc(r.answer)}${trimmed("answer", "0")}${rate("answer")}</p><p>${esc(r.summary)}</p>
    ${r.reply && r.reply.needed ? `<h2 class="cp-section">${T("Reply draft", "Antwortentwurf")}${stale}</h2><article class="cp-reply"><header><span>${esc(r.reply.subject)}</span><span>${esc(T("AI-generated draft", "KI-generierter Entwurf"))}</span></header>
      <div class="clauses">${r.reply.clauses.map((c, i) => `<div class="clause ${c.supported ? "" : "unsupported"}"><p>${esc(c.text)}${rate(`reply:${i}`)}</p>
        <small class="cp-muted">${c.supported ? (c.kind === "formal" ? "" : (c.kind === "request" ? T("Asks for: ", "Fragt nach: ") : T("Rests on: ", "Beruht auf: ")) + c.basis.map((b) => esc(b.startsWith("fact:") ? questionOf(b.slice(5)) : needOf(b.slice(9)))).join("; "))
          : T("Not supported by an accepted finding: review before use", "Durch keine bestätigte Feststellung gestützt: vor Verwendung prüfen")}</small></div>`).join("")}</div>
      <footer>${icon("shield")}${T("Draft · not sent — a person decides", "Entwurf · nicht versendet – ein Mensch entscheidet")}</footer></article><p>${draft}</p>` : ""}
    <h2 class="cp-section">${T("Work log", "Arbeitsprotokoll")}</h2>${workLog()}`;
}

// ---------- Übersicht: the case in thirty seconds, and what needs a person ----------
const CHAT_ROLE = /^user/i;  // a step the customer answers in the online form or chat
function chatOnly() {
  if (S.data.items) return new Set(S.data.items.filter((i) => i.kind === "fact" && i.chat_only).map((i) => i.key));
  // A fact only the customer's chat answers: every step it is asked on is a customer step. The files cannot settle it.
  const asked = {};
  for (const s of S.data.process.steps || []) for (const ref of s.source_refs || []) (asked[ref] = asked[ref] || []).push(s);
  return new Set(facts().filter((f) => {
    const on = (f.source_refs || []).flatMap((r) => asked[r] || []);
    return on.length && on.every((s) => CHAT_ROLE.test(s.role || ""));
  }).map((f) => f.id));
}
const redacted = (name) => !String(name || "").replace(/[\s.,\-–_[\]()]|geschwärzt|geschw-rzt|xxx/gi, "").length;
function seededNote(item) {
  if (!item || !item.origin || item.origin.by !== "build") return "";
  const e = (item.evidence || [])[0];
  return T(`activated for the pilot · from ${HOUSE.name}’s first request letters${e ? `: ${e.text}` : ""}`,
           `für den Pilot aktiviert · aus ${HOUSE.name}s ersten Unterlagenanforderungen${e ? `: ${e.text}` : ""}`);
}
const item = (kind, key) => (S.data.items || []).find((i) => i.kind === kind && i.key === key);  // the server's one item list
// ---------- Übersicht: one question per state, one primary button ----------
// The case's state decides the one primary button: prepared (copy, then Erledigt), running (Anhalten), paused (Weiter),
// failed (again), new files (prepare again), closed (next case), not prepared (prepare).
function caseState() {
  const run = S.data.run;
  const arrived = S.data.lastCompleted && (S.data.new_files || []).length;
  if (closed() && !arrived) return "closed";  // what arrives after closing reopens the case (the server logs case.reopened)
  if (running()) return "running";
  if (run && run.status === "paused") return "paused";
  if (run && ["failed", "interrupted"].includes(run.status)) return "failed";
  if (arrived) return "arrived";
  if (closed()) return "closed";
  if (!hasPrepared()) return (S.data.files || []).length ? "unprepared" : "empty";
  return "prepared";
}
// A case shows a prepared action only once a preparation finished (or stopped): before that its items hold nothing read.
const hasPrepared = () => S.data.file_note !== null && S.data.file_note !== undefined || Boolean(S.data.run && S.data.run.status === "paused");
// "in 6 von 7 Fällen verlangt": a seeded practice rule says how often the insurer asked for it.
function practiceNote(knowledgeId) {
  const k = (S.knowledge || []).find((x) => x.id === knowledgeId);
  const m = /(\d+) von (\d+)/.exec(((k && (k.evidence || [])[0]) || {}).text || "");
  return m ? T(`asked in ${m[1]} of ${m[2]} cases`, `in ${m[1]} von ${m[2]} Fällen verlangt`) : T("asked in practice", "in der Praxis verlangt");
}

// An update reads only what came in: no routing, no result checker; its expected time comes from earlier updates.
const UPDATE_STAGES = [
  { id: "lesen", de: "Lesen", en: "Reading", agents: ["reader"], expect: 10 },
  { id: "fakten", de: "Neues", en: "What is new", agents: ["claim_reader"], expect: 25 },
  { id: "unterlagen", de: "Unterlagen", en: "Documents", agents: ["document_finder"], expect: 15 },
  { id: "pruefung", de: "Prüfung", en: "Check", agents: ["source_checker"], expect: 15 },
];
const RUN_STAGES = [
  { id: "lesen", de: "Lesen", en: "Reading", agents: ["reader"], expect: 20 },
  { id: "prozess", de: "Prozess", en: "Process", agents: ["router", "process_builder"], expect: 10 },
  { id: "fakten", de: "Angaben", en: "Facts", agents: ["claim_reader"], expect: 70 },
  { id: "unterlagen", de: "Unterlagen", en: "Documents", agents: ["document_finder"], expect: 55 },
  { id: "pruefung", de: "Prüfung", en: "Check", agents: ["source_checker", "result_checker"], expect: 70 },
];
// The run as one line: the stages as done / now / next, one sentence on now with the expected rest (median of this
// deployment's recent runs, /api/run-profile; the fixed numbers above until runs exist), and its one button.
function stageLine() {
  const at = (e) => Date.parse(e.at || "") || Date.now(), now = Date.now();
  const span = (stage) => {
    const mine = S.events.filter((e) => stage.agents.includes(e.agent) || (stage.id === "prozess" && e.kind === "routing.decided"));
    if (!mine.length) return null;
    const open = mine.filter((e) => e.kind === "agent.start").length > mine.filter((e) => e.kind === "agent.end").length;
    return { start: at(mine[0]), open };
  };
  const known = (S.runProfile || {}).timed >= 3;  // a time is said only from three of this deployment's own runs on
  const learned = known ? (S.runProfile || {}).median_seconds || {} : {};
  const kind = (S.data.run || {}).kind === "update" ? "update" : "full";
  const pages = (S.data.files || []).reduce((n, f) => n + (((f.extraction || {}).kept_pages || []).length || (f.extraction || {}).pages || 1), 0);
  if (!S.runProfile || S.runProfile.forCase !== S.data.case.id || S.runProfile.kind !== kind) {
    S.runProfile = { forCase: S.data.case.id, kind };
    api(`/api/run-profile?pages=${pages}&kind=${kind}`).then((p) => { S.runProfile = { ...p, forCase: S.data.case.id, kind }; }).catch(() => {});
  }
  const rows = (kind === "update" ? UPDATE_STAGES : RUN_STAGES).map((stage) => ({ stage: { ...stage, expect: learned[stage.id] ?? stage.expect }, span: span(stage) }));
  let nowAt = rows.findIndex((x) => x.span && x.span.open);  // the stage at work, else the one after the last begun
  if (nowAt < 0) nowAt = rows.map((x) => Boolean(x.span)).lastIndexOf(true) + 1;
  const left = rows.filter((x) => !x.span || x.span.open).reduce((n, x) => n + Math.max(0, x.stage.expect - (x.span ? (now - x.span.start) / 1000 : 0)), 0);
  // a stage that already took longer than usual: no number that would stand still, the line says so instead
  const over = rows.some((x) => x.span && x.span.open && (now - x.span.start) / 1000 > x.stage.expect);
  if (S.finishing) nowAt = rows.length;  // finished: every stage is ticked for the moment before the prepared step arrives
  const cells = rows.map(({ stage }, i) => `<li class="${i < nowAt ? `done${enter(`stage:${stage.id}`)}` : i === nowAt ? "now" : ""}">${i < nowAt ? icon("tick") : ""}${T(stage.en, stage.de)}</li>`).join("");
  return { cells, left: known && !over ? Math.max(5, Math.round(left / 5) * 5) : null, over: known && over, agents: (rows[nowAt] || rows[rows.length - 1]).stage.agents };
}
function runLine(st) {
  const run = S.data.run;
  const wrap = (body, end) => `<section class="cp-runline" aria-live="polite">${body}<span class="cp-runline-end">${end}</span></section>`;
  if (st === "running") {
    const { cells, left, over, agents } = S.events.length ? stageLine() : { cells: "", left: null };
    // the file named is one the stage at work is on, never the last file of a stage that is over
    const last = S.events.slice().reverse().find((e) => e.file && e.agent !== "lead" && (!agents || agents.includes(e.agent))) || {};
    const doing = { reader: T("reads", "liest"), claim_reader: T("reads", "liest"), document_finder: T("looks for documents in", "sucht Unterlagen in"),
      source_checker: T("checks the sources in", "prüft die Belege in"), result_checker: T("checks the result against", "prüft das Ergebnis an") }[last.agent] || T("starts on", "beginnt mit");
    const where = last.file ? `<button class="cp-link" data-cite-file="${raw(last.file)}" data-page="${last.page || last.from_page || ""}">${esc(clip(fileName(last.file), 40))}${last.page || last.from_page ? `, ${T("p.", "S.")} ${last.page || last.from_page}` : ""}</button>` : T("with the files", "mit den Akten");
    const routed = S.events.find((e) => e.kind === "routing.decided");
    const others = (S.workflows || []).filter((w) => !routed || w.id !== routed.workflow);
    const stopping = S.stopping === run.id || S.switching;
    // what it found so far, counted from its own reports (the same events «Der Fall» below is filled from)
    const found = { entries: new Set(), facts: new Set(), needs: new Set() };
    let latest = null;
    for (const e of S.events) {
      if (e.kind === "record.recorded") for (const r of e.rows || []) found.entries.add(r.n);
      if (e.kind === "fact.located" && e.status === "established" && e.value !== undefined) { found.facts.add(e.fact); latest = e; }
      if (e.kind === "document.recorded") { found.needs.add(e.document); latest = e; }
    }
    const count = (n, one, many) => `<div class="cp-work-n ${n ? "" : "none"}"><b class="${n ? enter(`n:${many}:${n}`).trim() : ""}">${n}</b><span>${n === 1 ? one : many}</span></div>`;
    const finding = latest ? (latest.fact ? `${shortFact(latest.fact)}: ${valueText(latest.value)}` : `${needOf(latest.document)}: ${word(latest.status)}`) : "";
    const verb = { reader: T("Reading", "Liest"), claim_reader: T("Reading", "Liest"), document_finder: T("Looking for documents", "Sucht Unterlagen"),
      source_checker: T("Checking the sources", "Prüft die Belege"), result_checker: T("Checking the result", "Prüft das Ergebnis") }[last.agent] || T("Starting", "Beginnt");
    const time = left ? T(`about ${left} s to go`, `noch etwa ${left} s`) : over ? T("taking longer than usual", "dauert länger als üblich") : "";
    // a stage that has not named a file yet still says what it does (never «beginnt mit den Akten» at the last check)
    const stageAgent = last.agent || (agents || []).find((a) => ["reader", "claim_reader", "document_finder", "source_checker", "result_checker"].includes(a));
    const stageVerb = { reader: T("Reading", "Liest"), claim_reader: T("Reading", "Liest"), document_finder: T("Looking for documents", "Sucht Unterlagen"),
      source_checker: T("Checking the sources", "Prüft die Belege"), result_checker: T("Checking the result", "Prüft das Ergebnis") }[stageAgent] || verb;
    const stageWhere = last.file || !stageAgent ? where : stageAgent === "result_checker" ? T("against the file", "an der Akte") : T("in the files", "in den Akten");
    if (window.CasePathStory && tabOverviewLive()) {
      // the work as a picture: the files, what is found in them with the passage it rests on, the process, in the
      // order CasePath does it; above it what it does now, and the reader's own stop
      return `<section class="cp-runline cp-work cp-work-story" aria-live="polite" data-work>
        <div class="cp-work-head ${S.finishing ? "done" : ""}"><div><p class="cp-eyebrow" data-work-verb>${S.finishing ? "CasePath" : stopping ? T("Stopping", "Hält an") : esc(stageVerb)}</p>
            <p class="cp-runnow">${S.finishing ? `<span class="cp-work-done">${icon("tick")}</span>${run.kind === "update" ? T("Updated", "Aktualisiert") : T("Prepared", "Fertig vorbereitet")}` : stopping ? T("Stopping after this step…", "Hält nach diesem Schritt an …") : stageWhere}</p></div>
          <ol class="cp-stages">${cells}</ol>
          <p class="cp-work-foot">${time ? `<span class="cp-muted" data-work-time>${time}</span>` : ""}${routed ? `<span class="cp-muted">${esc(wfShort(routed.workflow, routed.title))}</span>` : ""}${routed && others.length && !stopping ? `<button class="cp-link cp-quiet-link" id="other-process-open">${T("other process", "anderer Prozess")}</button>` : ""}
            <button class="cp-button primary" id="stop-run" ${stopping ? "disabled" : ""}>${T("Stop", "Anhalten")}</button></p></div>
        ${arrivalNow(run)}${S.pickProcess ? `<p class="cp-pick">${others.map((w) => `<button class="cp-chip" data-other-process="${raw(w.id)}">${esc(w.short_title || w.title)}</button>`).join("")}</p>` : ""}
        <div class="cp-story" id="story" data-story="live" aria-label="${T("CasePath at work", "CasePath arbeitet")}"></div></section>`;
    }
    return `<section class="cp-runline cp-work" aria-live="polite" data-work>
      <svg class="cp-work-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><path d="M27 50 C 30 50, 31 50, 34 50"/><path d="M66 50 C 69 50, 69 28, 73 28"/><path d="M66 50 C 69 50, 69 74, 73 74"/></svg>
      <div class="cp-work-card cp-work-steps${enter("work:steps")}"><p class="cp-eyebrow">${T("CasePath at work", "CasePath arbeitet")}</p><ol class="cp-stages">${cells}</ol></div>
      <div class="cp-work-card cp-work-now${enter("work:now")} ${S.finishing ? "done" : ""}"><p class="cp-eyebrow">${S.finishing ? "CasePath" : stopping ? T("Stopping", "Hält an") : esc(verb)}</p>
        <p class="cp-runnow">${S.finishing ? `<span class="cp-work-done">${icon("tick")}</span>${run.kind === "update" ? T("Updated", "Aktualisiert") : T("Prepared", "Fertig vorbereitet")}` : stopping ? T("Stopping after this step…", "Hält nach diesem Schritt an …") : where}</p>
        <span class="cp-work-bar" aria-hidden="true"><i></i></span>${arrivalNow(run)}
        ${S.pickProcess ? `<p class="cp-pick">${others.map((w) => `<button class="cp-chip" data-other-process="${raw(w.id)}">${esc(w.short_title || w.title)}</button>`).join("")}</p>` : ""}
        <p class="cp-work-foot">${time ? `<span class="cp-muted">${time}</span>` : ""}${routed ? `<span class="cp-muted">${esc(wfShort(routed.workflow, routed.title))}</span>` : ""}${routed && others.length && !stopping ? `<button class="cp-link cp-quiet-link" id="other-process-open">${T("other process", "anderer Prozess")}</button>` : ""}
          <span class="grow"></span><button class="cp-button primary" id="stop-run" ${stopping ? "disabled" : ""}>${T("Stop", "Anhalten")}</button></p></div>
      <div class="cp-work-side"><div class="cp-work-card cp-work-found${enter("work:found")}"><p class="cp-eyebrow">${T("Found so far", "Bisher gefunden")}</p>
          <div class="cp-work-ns">${count(found.entries.size, T("entry in the course", "Eintrag im Verlauf"), T("entries in the course", "Einträge im Verlauf"))}${count(found.facts.size, T("fact", "Angabe"), T("facts", "Angaben"))}${count(found.needs.size, T("document", "Unterlage"), T("documents", "Unterlagen"))}</div></div>
        ${finding ? `<div class="cp-work-card cp-work-last${enter(`last:${finding}`)}"><p class="cp-eyebrow">${T("Latest", "Zuletzt")}</p><p>${esc(clip(finding, 120))}</p></div>` : ""}</div></section>`;
  }
  if (st === "paused") {
    const { cells } = S.events.length ? stageLine() : { cells: "" };
    // a run the model failed in keeps the steps it finished: said with its reason, continued with «Weiter»
    const failed = ((run || {}).result || {}).failed;
    return wrap(`<ol class="cp-stages paused">${cells}</ol><p class="cp-runnow"><b>${failed ? T("Interrupted", "Unterbrochen") : T("Stopped", "Angehalten")}</b>${failed
        ? `: ${esc(runError(failed.error))} · ${T("what was finished is kept; «Continue» goes on from there", "was fertig war, bleibt; «Weiter» setzt dort fort")}` : ""}</p>`,
      `<button class="cp-link cp-quiet-link" id="discard-run">${T("discard", "verwerfen")}</button><button class="cp-button primary" id="continue-run">${T("Continue", "Weiter")}</button>`);
  }
  if (st === "failed" && run.kind === "update") {  // the update only is offered again; a full preparation stays behind «Mehr»
    const interrupted = run.status === "interrupted";
    return wrap(`<p class="cp-runnow cp-arrival-failed"><b>${interrupted ? T("Update interrupted", "Aktualisierung unterbrochen") : T("Update failed", "Aktualisierung fehlgeschlagen")}</b>: ${esc(runError(run.error))}</p>`,
      `<button class="cp-button primary" id="retry-update">${T("Update again", "Erneut aktualisieren")}</button>`);
  }
  if (st === "failed") {
    return wrap(`<p class="cp-runnow"><b>${T("Not finished", "Nicht fertig")}</b>: ${esc(runError(run.error))}</p>`, `<button class="cp-button primary" id="start-run">${T("Try again", "Erneut versuchen")}</button>`);
  }
  if (st === "arrived") {
    const came = S.data.arrived || S.data.new_files.map((name) => ({ name })), u = S.data.update || {}, eta = updateEta();
    const names = came.map((f) => `${esc(f.name)}${f.added ? ` <span class="cp-muted">(${dateText(f.added)})</span>` : ""}`).join(", ");
    // why «Aktualisieren» did not start by itself, or cannot read them alone, is the button's title, not a paragraph to read
    return wrap(`<p class="cp-runnow"><b>${T(`${came.length} new ${came.length === 1 ? "file" : "files"}`, `${came.length} neue ${came.length === 1 ? "Datei" : "Dateien"}`)}</b> · ${names}</p>`,
      u.available ? `<button class="cp-button primary" id="update-run" title="${esc(autoTitle(u))}">${T("Update", "Aktualisieren")}${eta ? `<span class="cp-eta"> · ${eta}</span>` : ""}</button>`
        : `<button class="cp-button primary" id="prepare-new" title="${esc(u.text || "")}">${T("Prepare anew", "Ganz neu vorbereiten")}</button>`);
  }
  if (st === "unprepared") return wrap(`<p class="cp-runnow">${T("Not prepared yet", "Noch nicht vorbereitet")}</p>`, `<button class="cp-button primary" id="start-run">${T("Prepare case", "Fall vorbereiten")}</button>`);
  if (st === "empty") return `<div class="cp-drop" id="drop">${T("Drop the case files here, or add them on the left", "Dateien hierher ziehen oder links hinzufügen")}</div>`;
  return "";
}

// The time «Aktualisieren» takes, from this deployment's earlier updates (none yet: no time is promised).
function updateEta() {
  if (!S.updateProfile) {
    S.updateProfile = { loading: true };
    api("/api/run-profile?kind=update").then((p) => { S.updateProfile = p; if (S.route.view === "case" && caseState() === "arrived") renderCase(); }).catch(() => {});
  }
  const s = (S.updateProfile || {}).timed >= 3 ? S.updateProfile.median_total : null;
  if (!s) return "";
  return s < 90 ? T(`about ${Math.max(5, Math.round(s / 5) * 5)} s`, `etwa ${Math.max(5, Math.round(s / 5) * 5)} s`) : T(`about ${Math.round(s / 60)} min`, `etwa ${Math.round(s / 60)} Min.`);
}
// A handler's decision asked as a plain question: "Ist die Versicherungsdeckung gegeben?" [Ja] [Nein]; "offen" is no answer.
const plainQuestion = (text) => String(text || "").replace(/\s*\((Entscheid|CasePath)[^)]*\)?/g, "").trim();
const answered = (key) => { const i = item("fact", key); return i && i.value !== null && i.value !== undefined && i.value !== "offen" ? i.value : null; };
function decisionButtons(key) {
  const i = item("fact", key) || {}, now = answered(key);
  const label = { "bestätigt": T("Yes", "Ja"), "abgelehnt": T("No", "Nein"), ja: T("Yes", "Ja"), nein: T("No", "Nein"), true: T("Yes", "Ja"), false: T("No", "Nein") };
  return (i.values || []).filter((v) => v !== "offen").map((v) => `<button class="cp-button cp-small" data-decide="${raw(key)}" data-value="${raw(v)}" aria-pressed="${String(now) === String(v)}">${esc(label[v] || v)}</button>`).join("");
}
// ---------- Deckung: the cover points, prepared; the decision stays the handler's ----------
// The cover's own facts (edition, policy ticks, the reason a cover is refused) are set here, not asked as plain questions.
function coverFacts() {
  const own = ((S.data.process || {}).facts || []).filter((f) => (f.source_refs || []).some((r) => /^(avb|aufsicht)#/.test(r))).map((f) => f.id);
  return new Set([...own, "deckung"]);
}
const COVER_MARK = { akte: ["✓", "ok"], kein_hinweis: ["✓", "ok quiet"], police_ok: ["✓", "ok"], police: ["○", "open"], kunde: ["?", "open"], offen: ["–", "open"], hinweis: ["!", "flag"] };
function coverButtons() {
  const now = answered("deckung");
  return `<button class="cp-button cp-small" data-decide="deckung" data-value="bestätigt" aria-pressed="${now === "bestätigt"}">${T("confirm", "bestätigen")}</button><button class="cp-button cp-small" data-cover-decline aria-pressed="${now === "abgelehnt"}">${T("refuse", "ablehnen")}</button>`;
}
function clauseTag(key, rows, label) {
  if (!rows || !rows.length) return "";
  const cite = label || rows.map((r) => r.cite.replace(/^Art\. /, "")).join(", ");
  const open = S.coverPassage === key;
  return `<button class="cp-tag cp-law" type="button" data-cover-passage="${raw(key)}" aria-expanded="${open}" title="${esc(rows.map((r) => `${r.cite}: «${r.passage}»`).join(" "))}">${esc(cite)}</button>`
    + (open ? rows.map((r) => `<div class="cp-passage">${esc(r.cite)}: «${esc(r.passage)}»</div>`).join("") : "");
}
function coverPoint(p) {
  const [mark, cls] = COVER_MARK[p.value] || ["·", ""];
  const values = p.tick ? (item("fact", p.tick) || {}).values || [] : [];
  const pressed = (v) => String(p.tick_value) === String(v === "ja" ? true : v === "nein" ? false : v);
  const tick = values.length ? `<span class="cp-cover-tick">${values.map((v) => `<button class="cp-chip" data-decide="${raw(p.tick)}" data-value="${raw(v)}" aria-pressed="${pressed(v)}" title="${T("as the policy says", "laut Police")}">${esc(v)}</button>`).join("")}</span>` : "";
  const src = (p.evidence || [])[0];
  const line = [p.value === "police_ok" ? "" : p.text, p.aid].filter(Boolean).map(esc).join(" · ");
  const open = S.coverPassage === p.key;
  return `<li class="cp-cover-point ${cls}" data-item="${raw(p.item_id)}"><span class="cp-cover-mark" title="${esc(p.state_text || "")}">${mark}</span>
    <span class="cp-cover-body"><span class="cp-cover-title">${esc(p.title)}</span> ${clauseTag(p.key, p.clauses, (p.legal_basis || "").replace(/^Art\. /, "").replace(/, Art\. /g, ", "))}
      <span class="cp-cover-line">${line ? `<span class="cp-muted">${line}</span>` : p.value === "police_ok" ? `<span class="cp-muted">${T("as the policy says", "laut Police")}</span>` : ""}${src ? ` <button class="cp-source-chip" data-cite-file="${raw(src.file)}" data-page="${src.page || ""}" title="${esc(src.quote || "")}">${src.page ? `${T("p.", "S.")} ${src.page}` : T("source", "Quelle")}</button>` : ""}${tick}</span>
      ${p.note && open ? `<span class="cp-muted cp-cover-note">${esc(p.note)}</span>` : ""}</span></li>`;
}
const reasonChips = (attr, codes) => `<span class="cp-reasons">${codes.map((code) => `<button class="cp-chip" ${attr}="${code}">${esc(T(REASONS_EN[code], REASONS[code]))}</button>`).join("")}</span>`;

// ---------- Übersicht: the next piece of work, done; its reasons one click away ----------
// The card head says what this step is, why (one line), the one deadline that leads and the one decision that blocks
// this step; nothing else. What goes out is below it (several documents: tabs, each ticked once copied), its action bar
// always in view. «Der Fall» beside it says what the head does not. What the head says is decided once by the server
// (screen.py), in the case list's own words.
const scr = () => (S.data && S.data.screen) || {};
const isoDay = (v) => String(tr(v || "")).replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, "$3.$2.$1");
function overviewView() {
  const st = caseState();
  const top = runLine(st);
  if (!hasPrepared() || (!item("next_action", "0") && !result())) return top;
  const arrive = S.arrive; S.arrive = null;  // once per case opened: the sheet comes in (from the right when the reader went on)
  // the picture of how this step was prepared, opened from the line above the step: across the page's width
  const picture = S.storyOpen === S.route.id && window.CasePathStory && (S.data.prepared_run || {}).id
    ? `<section class="cp-story-wrap" data-story-wrap><header><p class="cp-eyebrow">${T("How CasePath prepared this step", "Wie CasePath diesen Schritt vorbereitet hat")}</p>
        <button class="cp-link cp-quiet-link" type="button" id="story-close">${T("close", "schliessen")}</button></header>
        <div class="cp-story" id="story" data-story="replay"></div></section>` : "";
  return `${top}${picture}<div class="cp-overview ${arrive ? `cp-arrive ${arrive === "next" ? "from-right" : ""}` : ""}">${preparedView(st)}${sideView()}</div>`;
}
// A source is one quiet chip, its page; what rests on the handler's own entry says so where the chip would stand.
function sourceChip(e) {
  const at = e && Number.isInteger(e.start) && Number.isInteger(e.end) ? ` data-start="${e.start}" data-end="${e.end}"` : "";  // opens at its passage
  return e && e.file ? ` <button class="cp-source-chip" data-cite-file="${raw(e.file)}" data-page="${e.page || ""}"${at} title="${esc(e.quote || "")}">${e.page ? `${T("p.", "S.")} ${e.page}` : T("source", "Quelle")}</button>` : "";
}
function sourceChips(evidence) {
  const seen = new Set();
  return (evidence || []).filter((e) => e.file && !seen.has(`${e.file}:${e.page}`) && seen.add(`${e.file}:${e.page}`)).slice(0, 2).map(sourceChip).join("");
}
const handlerTag = (h) => (h ? ` <span class="cp-entry-tag own" title="${esc(T("entered by the case handler", "von der Fallbearbeitung erfasst"))}${h.by ? ` · ${esc(h.by)}` : ""}">${T("case handling", "Fallbearbeitung")}</span>` : "");
const passages = (law) => (law || []).map((l) => `<div class="cp-passage">${esc(l.cite)}: «${esc(l.passage)}»</div>`).join("");

// What goes out with this step, each its own tab: the letter, a template for the customer's own letter, the mandate
// package, the fee note's query or partial refusal (the one its answer chose). The active tab is the first not copied.
const FEE_LETTERS = ["A11_rueckfrage", "A11_teilablehnung"];
function documentsOut() {
  const sc = scr(), draft = S.data.draft || {};
  const all = sc.documents || [...(draft.text ? [{ kind: draft.form || draft.kind, main: true, title: draft.title || T("Letter", "Brief"), copied: false }] : []),
    ...(draft.also || []).filter((a) => a.text).map((a) => ({ kind: a.kind, main: false, title: a.title, copied: false, template: Boolean(a.template) }))];
  const fee = (sc.decision || {}).key === "kostennote";
  const rows = all.filter((d) => (fee ? !d.main && d.kind === S.feeAnswer : !FEE_LETTERS.includes(d.kind)) && (d.main ? draft.text : true));
  const step = `${(item("next_action", "0") || {}).action || ""}:${draft.form || ""}`;
  if (S.docFor !== step) { S.docFor = step; S.docTab = null; S.docPicked = false; }  // another step: its first document
  const active = rows.find((d) => d.kind === S.docTab);
  const done = (d) => (d.state ? d.state === "versandt" : d.copied);  // a tab is done once its recipient's dispatch is confirmed
  if (!active || (done(active) && !S.docPicked)) S.docTab = (rows.find((d) => !done(d)) || active || rows[0] || {}).kind || null;
  // what the reader has had before their eyes, per step: an approval covers every document, so each is shown once first
  const seen = ((S.docSeen = S.docSeen || {})[`${S.route.id}:${step}`] = (S.docSeen[`${S.route.id}:${step}`] || new Set()));
  if (S.docTab) seen.add(S.docTab);
  return { rows, active: rows.find((d) => d.kind === S.docTab) || null, unseen: rows.filter((d) => !seen.has(d.kind) && !(d.state && d.state !== "entwurf")) };
}
function docText(doc) {
  const draft = S.data.draft || {};
  if (!doc) return "";
  if (doc.main) return draft.text || "";
  return (S.alsoEdits || {})[doc.kind] ?? (((draft.also || []).find((a) => a.kind === doc.kind) || {}).text || "");
}
// A part only the handler can write: «[bitte ergänzen: …]», highlighted; the card's button goes to the first one.
const GAP_RE = /\[bitte ergänzen: [^\]]*\]/g;
const gapsMarked = (text) => raw(text).replace(GAP_RE, (m) => `<mark class="cp-gap">${m}</mark>`);
// A letter goes out in the language it is written in. A reader of another language sees it translated, line by line, to
// read; it is edited in the original («show the original»), and what is copied, approved and sent is the original.
const readingLetter = () => reading() && !S.letterOriginal;
const readLines = (text) => String(text || "").split("\n").map((line) => tr(line)).join("\n");
const letterBlock = (text) => (readingLetter() ? gapsMarked(readLines(text)) : gapsMarked(text));
function letterLangNote() {
  if (!reading()) return "";
  return S.letterOriginal
    ? `<p class="cp-reading-note">${T("German text, as sent", "Deutscher Text, wie er hinausgeht")} · <button class="cp-link cp-quiet-link" id="letter-reading" type="button">${T("show the English reading copy", "englische Lesefassung zeigen")}</button></p>`
    : `<p class="cp-reading-note">${T("English reading copy · the letter is sent in German", "Englische Lesefassung · der Brief geht auf Deutsch hinaus")} · <button class="cp-link cp-quiet-link" id="letter-original" type="button">${T("show and edit the German text", "deutschen Text zeigen und bearbeiten")}</button></p>`;
}
function gapCount(doc) {
  let text = docText(doc);
  if (doc && doc.main) for (const [orig, now] of Object.entries(S.blockEdits || {})) text = text.split(orig).join(now);
  return (text.match(GAP_RE) || []).length;
}
// «Weil: …», one line: what led to this step; its source (and, for what came in, «bereits erledigt») when opened.
// After a partial answer: what the reading took as delivered, each with «doch offen» for the one that was not it (the
// request is open again and the letter asks it), so the handler corrects the reading where its consequence is shown.
function partialLine(act) {
  const part = act && act.partial;
  if (!part || !(part.received || []).length) return "";
  return `<p class="cp-partial" data-partial><span class="cp-head-label">${T("Received", "Eingegangen")}:</span> ${part.received.map((r) =>
    `<span class="cp-partial-item">${esc(r.what)} <button class="cp-link cp-quiet-link" data-settle="${raw(r.request)}" data-how="offen" title="${T("It did not come: ask for it again", "Das ist nicht eingegangen: nochmals verlangen")}">${T("still open", "doch offen")}</button></span>`).join(" · ")}</p>`;
}
function weilLine(act) {
  const sc = scr(), text = sc.weil || (act && act.reason);
  if (!text) return "";
  const src = act && (act.evidence || []).find((e) => e.file);
  const then = (sc.danach || []).length && !(act && act.deadline) ? ` · ${T("then", "danach")}: ${sc.danach.map(esc).join(" · ")}` : "";
  const came = act && act.incoming;
  const more = S.weilOpen ? `${sourceChip(src)}${came ? ` <button class="cp-link cp-quiet-link" data-decide="eingang_erledigt_bis" data-value="${raw(came.date || isoToday())}">${T("already done", "bereits erledigt")}</button>` : ""}` : "";
  const openable = Boolean(src || came || text.length > 90 || then);
  const body = `${T("Because", "Weil")}: ${esc(String(text).replace(/^Weil:?\s*/i, ""))}${then}`;
  return `<p class="cp-weil ${S.weilOpen ? "open" : ""}" data-item="next_action:0">${openable ? `<button class="cp-weil-text" id="weil-open" aria-expanded="${Boolean(S.weilOpen)}">${body}</button>${more}` : `<span class="cp-weil-text">${body}</span>`}</p>`;
}
// The one deadline that leads (screen.lead): what, when, how close; its article, rule, consequence and source when opened.
function leadLine(lead) {
  if (!lead) return "";
  const cls = quiet() ? "" : lead.days < 0 ? "past" : lead.urgency === "dringend" ? "late" : lead.days <= 14 ? "soon" : "";
  const more = [lead.basis, lead.rule, lead.missed, lead.by].filter(Boolean);
  const text = `${esc(lead.kind)} <b>${esc(lead.date)}</b> · ${esc(lead.title)} · ${esc(lead.word)}`;
  return `<p class="cp-lead-frist ${cls} ${S.leadOpen ? "open" : ""}" data-item="${raw(lead.item_id)}">${more.length || lead.source
    ? `<button class="cp-lead-text" id="lead-open" aria-expanded="${Boolean(S.leadOpen)}">${text}</button>${S.leadOpen ? `<span class="cp-lead-more">${more.map(esc).join(" · ")}${sourceChip(lead.source)}</span>` : ""}`
    : `<span class="cp-lead-text">${text}</span>`}</p>`;
}
// The one open decision that blocks this step (screen.decision), with its answers; what it rests on opens from the question.
// The decisions of this step as one set: those taken (each with its answer, changed where it stands), the one the card
// asks now, and those still to come, so the reader knows how many there are before the first click. Shown once the
// step has more than one decision or one was taken.
// What CasePath did and when it finished, above the step it prepared: «CasePath · vorbereitet 17.11.2026, 09:13 · 3 Dateien,
// 22 Seiten gelesen · 6 Min». Said in green, its tick drawn, when the preparation finished while the reader watched.
function preparedBy() {
  const run = S.data.prepared_run;
  if (!run || !run.finished_at || studyCopy()) return "";
  const files = S.data.files || [], pages = files.reduce((n, f) => n + (((f.extraction || {}).kept_pages || []).length || (f.extraction || {}).pages || 0), 0);
  const took = (Date.parse(run.finished_at) - Date.parse(run.created_at)) / 60000;
  // when, as a person says it (today with the time, else how many days ago): the exact day and time are the line's title,
  // so no date stands twice on the screen
  const done = new Date(run.finished_at), days = Number.isNaN(done.getTime()) ? null : -daysTo(run.finished_at);
  const clock = Number.isNaN(done.getTime()) ? "" : `${String(done.getHours()).padStart(2, "0")}:${String(done.getMinutes()).padStart(2, "0")}`;
  const when = days === null ? "" : days <= 0 ? T(`today, ${clock}`, `heute, ${clock}`) : days === 1 ? T("yesterday", "gestern") : T(`${days} days ago`, `vor ${days} Tagen`);
  const read = `${files.length} ${T(files.length === 1 ? "file" : "files", files.length === 1 ? "Datei" : "Dateien")}${pages > 1 ? `, ${pages} ${T("pages", "Seiten")}` : ""} ${T("read", "gelesen")}`;
  const lasted = took >= 1 && took < 180 ? ` · ${Math.round(took)} ${T("min", "Min")}` : "";
  const fresh = S.justFinished === S.route.id;
  const open = fresh || S.trailOpen || S.storyOpen === S.route.id;
  return `<p class="cp-by ${fresh ? "fresh" : ""}" data-prepared-by title="${esc(`${dateText(run.finished_at).slice(0, 10)}${clock ? `, ${clock}` : ""}`)}">${fresh ? icon("tick") : ""}<button type="button" class="cp-by-open" id="trail-open" aria-expanded="${open ? "true" : "false"}" title="${T("What CasePath did for this step", "Was CasePath für diesen Schritt getan hat")}">CasePath · ${run.kind === "update" ? T("updated", "aktualisiert") : T("prepared", "vorbereitet")} ${when} · ${read}${lasted}${icon("right")}</button></p>${open ? workTrail(fresh) : ""}`;
}
// ---------- the story: the case as a picture that builds itself (assets/story.js draws it) ----------
// The model is built from the case's real state: its files, the run's events in their order (a fact located with its
// passage, a document matched, the process placed, the history recorded), the needs the area learned from practice,
// the letter and the decisions left. Each beat says what happened and on what it rests. Live: the events so far.
function storyModel(events, live) {
  const d = S.data, id = S.route.id, items = d.items || [], proc = d.process || {};
  const nodes = [], edges = [], beats = [], have = new Set(), linked = new Set();
  const node = (n) => { if (!have.has(n.id)) { have.add(n.id); nodes.push(n); } return n.id; };
  const edge = (from, to, kind, label) => { const k = `${from}>${to}`; if (have.has(from) && have.has(to) && !linked.has(k)) { linked.add(k); edges.push({ from, to, kind, label }); return [from, to]; } return null; };
  const beat = (what, why, reveal, drawn, agent) => beats.push({ caption: { what, why: why || "" }, reveal: reveal.filter(Boolean), edges: (drawn || []).filter(Boolean), focus: reveal.filter(Boolean), agent: agent ? AGENT_TITLE[agent] || "" : "" });
  const label = (i) => tr(T((i.label || {}).en, (i.label || {}).de) || i.key || "");
  const page = (c) => (c && c.page ? `${T("p.", "S.")} ${c.page}` : "");
  const quote = (c) => (c && c.quote ? `«${clip(c.quote, 90)}»${c.page ? ` · ${page(c)}` : ""}` : "");
  const files = d.files || [];
  for (const f of files) node({ id: `file:${f.id}`, lane: "sources", kind: "file", title: f.name, sub: (f.extraction || {}).pages > 1 ? `${((f.extraction || {}).kept_pages || []).length || f.extraction.pages} ${T("pages", "Seiten")}` : dateText(f.created_at), href: `#/case/${id}/claim_reader` });
  const pages = files.reduce((n, f) => n + (((f.extraction || {}).kept_pages || []).length || (f.extraction || {}).pages || 0), 0);
  beat(T(files.length === 1 ? "The file arrived" : "The files arrived", files.length === 1 ? "Die Akte ist da" : "Die Dateien sind da"),
    `${files.length} ${T(files.length === 1 ? "file" : "files", files.length === 1 ? "Datei" : "Dateien")}${pages > 1 ? `, ${pages} ${T("pages", "Seiten")}` : ""}`, files.map((f) => `file:${f.id}`), [], "claim_reader");
  const factItems = Object.fromEntries(items.filter((i) => i.kind === "fact").map((i) => [i.key, i]));
  const docItems = Object.fromEntries(items.filter((i) => i.kind === "document" && !i.part_of).map((i) => [i.key, i]));
  const steps = Object.fromEntries((proc.steps || []).map((s) => [s.id, s]));
  let shownFacts = 0, lastStep = null;
  for (const e of events || []) {
    if (e.kind === "routing.decided" && (e.workflow || e.title)) {
      beat(T("Legal area recognised", "Rechtsgebiet erkannt"), tr(wfShort(e.workflow, e.title || "")), [], [], e.agent);
    } else if (e.kind === "record.recorded" && e.entries) {
      const nid = node({ id: "history", lane: "findings", kind: "entry", title: T("History of the case", "Verlauf des Falls"), sub: `${e.entries} ${T(e.entries === 1 ? "entry" : "entries", e.entries === 1 ? "Eintrag" : "Einträge")}`, href: `#/case/${id}/history` });
      beat(T("The history is recorded", "Der Verlauf ist festgehalten"), `${e.entries} ${T("documents and entries in order", "Dokumente und Einträge in ihrer Reihenfolge")}`, [nid], [e.cite && edge(`file:${e.cite.file}`, nid, "cites")], e.agent);
    } else if (e.kind === "fact.located" && e.fact && shownFacts < 16 && !have.has(`fact:${e.fact}`)) {
      const item = factItems[e.fact], value = e.value ?? (item || {}).value;
      if (value === null || value === undefined || value === "") continue;
      shownFacts += 1;
      const nid = node({ id: `fact:${e.fact}`, lane: "findings", kind: "fact", title: item ? label(item) : tr(questionOf(e.fact)), sub: tr(String(value === true ? T("yes", "ja") : value === false ? T("no", "nein") : value)), state: "done", href: `#/case/${id}/claim_reader` });
      beat(`${T("Found", "Gefunden")}: ${clip(item ? label(item) : tr(questionOf(e.fact)), 70)}`, quote(e.cite), [nid], [e.cite && edge(`file:${e.cite.file}`, nid, "cites", page(e.cite))], e.agent);
    } else if (e.kind === "document.recorded" && e.document && !have.has(`need:${e.document}`)) {
      const item = docItems[e.document], on = e.status === "present";
      const nid = node({ id: `need:${e.document}`, lane: "findings", kind: "need", title: item ? label(item) : tr(needOf(e.document)), sub: tr((item || {}).practice || ""), state: on ? "present" : "missing", href: `#/case/${id}/document_finder` });
      beat(`${on ? T("On file", "Liegt vor") : T("Missing", "Fehlt")}: ${clip(item ? label(item) : tr(needOf(e.document)), 70)}`, on ? quote(e.cite) : T("not found in the files", "in den Dateien nicht gefunden"), [nid], [on && e.cite && edge(`file:${e.cite.file}`, nid, "cites", page(e.cite))], e.agent);
    } else if (e.kind === "process.state" && (e.path || []).length) {
      const ids = e.path.filter((p) => steps[p.step]).map((p) => node({ id: `step:${p.step}`, lane: "process", kind: "step", title: tr(steps[p.step].title), state: p.state === "passed" ? "done" : p.state === "current" ? "now" : "open", href: `#/case/${id}/process_builder` }));
      for (const p of e.path) { const n = nodes.find((x) => x.id === `step:${p.step}`); if (n) n.state = p.state === "passed" ? "done" : p.state === "current" ? "now" : "open"; }
      const now = e.path.find((p) => p.state === "current"), at = now && steps[now.step] ? `step:${now.step}` : ids[ids.length - 1];
      if (at && at !== lastStep) {
        const drawn = ids.slice(1).map((to, i) => edge(ids[i], to, "leads"));
        beat(`${T("Where the case stands", "Wo der Fall steht")}: ${now && steps[now.step] ? tr(steps[now.step].title) : ""}`, T("placed on the area's process", "im Ablauf des Rechtsgebiets eingeordnet"), ids, drawn, e.agent);
        lastStep = at;
      }
    }
  }
  if (!live) {
    // what the run recorded beyond its events' first sixteen findings, and what the case needs that no event named
    const more = items.filter((i) => i.kind === "fact" && i.value !== null && i.value !== undefined && i.value !== "" && !have.has(`fact:${i.key}`));
    const kept = more.filter((i) => (i.evidence || []).some((x) => x.file)).slice(0, Math.max(0, 16 - shownFacts));
    const ids = kept.map((i) => node({ id: `fact:${i.key}`, lane: "findings", kind: "fact", title: label(i), sub: tr(String(i.value)), state: "done", href: `#/case/${id}/claim_reader` }));
    if (ids.length) beat(T("Further facts with their passages", "Weitere Angaben mit ihren Stellen"), `${ids.length} ${T("more", "weitere")}${more.length > kept.length ? ` · ${more.length - kept.length} ${T("without a passage of their own", "ohne eigene Stelle")}` : ""}`, ids,
      kept.map((i) => { const c = (i.evidence || []).find((x) => x.file); return edge(`file:${c.file}`, `fact:${i.key}`, "cites", page(c)); }), "source_checker");
    const needs = Object.values(docItems).filter((i) => !have.has(`need:${i.key}`));
    const nids = needs.map((i) => node({ id: `need:${i.key}`, lane: "findings", kind: "need", title: label(i), sub: tr(i.practice || ""), state: i.status === "present" ? "present" : "missing", href: `#/case/${id}/document_finder` }));
    const allNeeds = Object.values(docItems);
    if (nids.length) beat(T("What else the case needs", "Was der Fall sonst braucht"), `${allNeeds.filter((i) => i.status === "present").length} ${T("of", "von")} ${allNeeds.length} ${T("documents on file", "Unterlagen liegen vor")}`, nids,
      needs.map((i) => { const c = (i.evidence || []).find((x) => x.file); return c ? edge(`file:${c.file}`, `need:${i.key}`, "cites", page(c)) : null; }), "document_finder");
    const learned = Object.values(docItems).filter((i) => i.practice && have.has(`need:${i.key}`));
    if (learned.length) {
      const kid = node({ id: "knowledge", lane: "process", kind: "knowledge", title: T("Knowledge", "Wissen"), sub: T("from closed cases", "aus abgeschlossenen Fällen"), href: "#/knowledge" });
      beat(T("Asked for because practice shows it", "Verlangt, weil die Praxis es zeigt"), tr(learned[0].practice), [kid], learned.map((i) => edge(kid, `need:${i.key}`, "learned")), "process_builder");
    }
    const draft = d.draft || {}, st = completionOf();
    if (draft.text) {
      const lid = node({ id: "letter", lane: "outcome", kind: "letter", title: tr(draft.title || T("Letter", "Brief")), sub: tr((scr().title || "")), state: "now", lines: Math.min(14, draft.text.split("\n").filter((l) => l.trim()).length), href: `#/case/${id}/overview` });
      beat(`${T("Prepared", "Vorbereitet")}: ${tr(scr().title || draft.title || "")}`, tr(String((scr().weil || "")).replace(/^Weil:?\s*/i, "")), [lid], [lastStep && edge(lastStep, lid, "leads")], "result_checker");
      const taken = (st.decided || []).map((x) => node({ id: `decision:${x.key}`, lane: "outcome", kind: "decision", title: tr(x.word), sub: tr(x.value), state: "done", href: `#/case/${id}/overview` }));
      const open = (st.decisions || []).map((w) => node({ id: `decision:${w}`, lane: "outcome", kind: "decision", title: tr(w), state: "open", href: `#/case/${id}/overview` }));
      if (taken.length + open.length) beat(open.length ? T("Left for you to decide", "Für Sie zu entscheiden") : T("Decided", "Entschieden"), open.map((w) => tr(w)).join(" · "), taken.concat(open), taken.concat(open).map((x) => edge(lid, x, "branch")), "lead");
    }
  }
  return { lanes: [{ id: "sources", title: T("File", "Akte") }, { id: "findings", title: T("Found", "Gefunden") }, { id: "process", title: T("Process", "Prozess") }, { id: "outcome", title: T("Result", "Ergebnis") }],
    nodes, edges, beats, live: Boolean(live),
    labels: storyLabels() };
}
// The stage is mounted into its place after a render. While CasePath works the same stage lives on across the polls
// (it is updated, never redrawn), so nothing replays; a replay opened once is shown at its end when the page redraws.
const tabOverviewLive = () => S.route.view === "case" && (S.route.tab || "overview") === "overview";
function mountStory() {
  const box = document.getElementById("story");
  if (!box || !window.CasePathStory) { dropStory(); return; }
  if (box.dataset.story === "process" && window.CasePathFlow) { mountFlow(box); return; }
  const kind = box.dataset.story, live = kind === "live", timed = live || kind === "replay";
  const run = live ? (S.data.run || {}).id : kind === "replay" ? (S.data.prepared_run || {}).id : "";
  const events = live ? S.events : (S.storyEvents || {})[run];
  if (kind === "replay" && !events) { dropStory(); return; }
  // a tab's picture is the case's state as it stands; the run's picture is its events in their order
  const model = timed ? null : (TAB_STORY[kind] || (() => null))();
  // a picture too crowded to read is not shown: the page's own list says it better
  if (!timed && (!model || model.nodes.length > STORY_NODES)) { dropStory(); box.hidden = true; return; }
  // the stage lives in a layer of its own over the place the page keeps for it: a redraw of the page (every poll while
  // CasePath works) leaves it standing, so its movements are never cut or replayed
  let layer = document.getElementById("cp-story-layer");
  if (!layer) { layer = document.createElement("div"); layer.id = "cp-story-layer"; document.body.appendChild(layer); }
  const key = `${S.route.id}:${kind}:${run}:${LANG}`, seen = (S.storySeen = S.storySeen || {}), was = `${S.route.id}:${kind}:${run}`;
  const sig = timed ? "" : JSON.stringify([model.nodes.map((n) => [n.id, n.state, n.sub]), model.edges.length, model.beats.length]);
  if (!S.story || S.story.key !== key) {
    dropStory(true);
    const host = document.createElement("div");
    host.className = "cp-story-host";
    layer.appendChild(host);
    const first = !seen[was];
    const ctrl = window.CasePathStory.mount(host, timed ? storyModel(events, live) : model, { autoplay: kind === "replay" && first, start: live || !first ? "last" : "first", height: Number(box.dataset.height) || (live ? 360 : 460),
      onOpen: (n) => { if (S.storyBig) storyBig(false); openFromStory(n); }, onHover: (n) => pointFromStory(n), onExpand: () => storyBig(!S.storyBig),
      quiet: kind === "knowledge" || kind === "documents" ? ["learned"] : [],
      ...(timed ? {} : { onClose: () => { if (S.storyBig) storyBig(false); setPicture(false, kind); } }) });
    // a tab's picture stands as far as the case came before and plays what is current: where it is now, what is open, what follows
    if (!timed && first && model.beats.length) { if (model.from > 0) ctrl.seek(model.from - 1); ctrl.play(); }
    seen[was] = true;
    S.story = { ctrl, key, live, run, n: (events || []).length, sig, beats: timed ? 0 : model.beats.length, ids: timed ? [] : model.nodes.map((n) => n.id),
      height: Number(box.dataset.height) || (live ? 360 : 460) };
  } else if (live && S.story.n !== events.length) {
    S.story.n = events.length;
    S.story.ctrl.update(storyModel(events, true));
  } else if (!timed && S.story.sig !== sig) {
    // the case changed under the reader's eyes (an entry added, a document arrived, a step taken): the picture takes it up,
    // and what is new arrives as its own movement
    const ids = new Set(model.nodes.map((n) => n.id)), grew = model.beats.length > S.story.beats;
    if (S.story.ids.every((id) => ids.has(id)) && model.beats.length >= S.story.beats) {
      S.story.sig = sig; S.story.beats = model.beats.length; S.story.ids = [...ids];
      S.story.ctrl.update(model);
      if (grew) S.story.ctrl.play();
    } else {
      // the case went on (a step taken, a decision that changed its way): the picture is drawn again as far as the case
      // had come and plays where it stands now
      seen[was] = false;
      dropStory(true);
      mountStory();
      return;
    }
  }
  if (!timed) linkStoryRows(model);
  placeStory();
}
// Prozess is drawn as a flow: every step a block with what CasePath prepares there, what is the handler's to decide,
// what is open, and each way out by its own name leading to the step or the closing it ends in. The case is on it: the
// way it took, where it stands, the ways still open. It lives in the same layer as the other pictures, so it stays
// standing across redraws and takes up a change (a decision taken, a step on) as a change, never as a new drawing.
function mountFlow(box) {
  const model = processFlow();
  if (!model || !model.blocks.length) { dropStory(); box.hidden = true; return; }
  let layer = document.getElementById("cp-story-layer");
  if (!layer) { layer = document.createElement("div"); layer.id = "cp-story-layer"; document.body.appendChild(layer); }
  const key = `${S.route.id}:flow:${LANG}`, was = `${S.route.id}:flow`, seen = (S.storySeen = S.storySeen || {}), height = Number(box.dataset.height) || 440;
  const sig = JSON.stringify([model.now, model.path, model.blocks.map((b) => [b.id, b.tone, b.title, b.rows.map((r) => [r.id, r.state, r.value || "", r.text, r.sub || "", (r.actions || []).length])])]);
  if (!S.story || S.story.key !== key) {
    dropStory(true);
    const host = document.createElement("div");
    host.className = "cp-story-host";
    layer.appendChild(host);
    const flow = window.CasePathFlow.mount(host, model, { height, autoplay: !seen[was], onExpand: () => storyBig(!S.storyBig),
      onHover: (b) => pointFromStory(b && b.item ? { item: b.item } : null),
      onOpen: (t) => { if (S.storyBig) storyBig(false); openFromFlow(t || {}); },
      onAction: (row, action) => { if (S.storyBig) storyBig(false); actFromFlow(row, action); } });
    seen[was] = true;
    // the page speaks to every picture the same way
    S.story = { key, sig, height, live: false, run: "", flow: true, ctrl: { update: (m) => flow.update(m), destroy: () => flow.destroy(), highlight: (id) => flow.highlight(id || null),
      resize: (h, large) => flow.resize(h, large), rest: () => flow.here(), play: () => {}, pause: () => {}, seek: () => {} } };
  } else if (S.story.sig !== sig) { S.story.sig = sig; S.story.ctrl.update(model); }
  linkStoryRows({ nodes: model.blocks });
  placeStory();
}
// What is pressed on the flow opens where it lives on the page: a step its row, a point its fact, the documents their tab.
function openFromFlow(t) {
  const row = t.row || {}, end = t.end || row.end;
  if (row.href && !t.end) { location.hash = row.href; return; }
  openFromStory({ item: end ? `step:${end.id}` : row.item || (t.block || {}).item || "" });
}
// A decision offered on the flow is taken exactly as on the page: by the page's own control, so one rule holds for both.
function actFromFlow(row, action) {
  const [fact, value] = String((action || {}).id || "").split(":");
  if (fact !== "deckung") return;
  if (value === "bestätigt") { decideFact("deckung", "bestätigt"); return; }
  // a refusal names the point that fails: the page asks for it where the step stands
  S.coverDecline = true;
  renderCase().then(() => { const why = document.querySelector(".cp-cover-why"); if (why) { why.scrollIntoView({ block: "center", behavior: reducedMotion() ? "auto" : "smooth" }); const first = why.querySelector("button, input, select"); if (first) first.focus({ preventScroll: true }); } });
}
// The picture and the list under it are one thing seen twice: a card under the hand marks its row, a row under the hand
// brings its card forward with its lines and what they lead to.
const rowOfNode = (n) => (n && n.item && document.querySelector(`[data-item="${CSS.escape(n.item)}"]`)) || (n && n.row && document.querySelector(`[data-story-row="${CSS.escape(n.row)}"]`)) || null;
function pointFromStory(n) {
  for (const el of document.querySelectorAll(".cp-story-point")) el.classList.remove("cp-story-point");
  const row = rowOfNode(n);
  if (row) row.classList.add("cp-story-point");
}
function linkStoryRows(model) {
  for (const n of model.nodes) {
    const row = rowOfNode(n);
    if (!row || row.dataset.storyLinked) continue;
    row.dataset.storyLinked = "1";
    row.addEventListener("mouseenter", () => { if (S.story) S.story.ctrl.highlight(n.id); });
    row.addEventListener("mouseleave", () => { if (S.story) S.story.ctrl.highlight(null); });
    row.addEventListener("focusin", () => { if (S.story) S.story.ctrl.highlight(n.id); });
    row.addEventListener("focusout", () => { if (S.story) S.story.ctrl.highlight(null); });
  }
}
// The picture large, over the page: the same picture with room to be read, and back with Esc or its own control.
function storyBig(on) {
  const layer = document.getElementById("cp-story-layer");
  if (!layer || !S.story) { S.storyBig = false; return; }
  S.storyBig = Boolean(on);
  let back = document.getElementById("cp-story-back");
  if (on && !back) { back = document.createElement("div"); back.id = "cp-story-back"; back.addEventListener("click", () => storyBig(false)); document.body.appendChild(back); }
  if (!on && back) back.remove();
  layer.classList.toggle("cp-story-big", S.storyBig);
  document.documentElement.classList.toggle("cp-story-open", S.storyBig);
  // the flow has no caption and no time line under it: the whole height is its own
  S.story.ctrl.resize(on ? Math.max(360, window.innerHeight - 48 - 36 - (S.story.flow ? 12 : 150)) : S.story.height, on);
  if (!on) placeStory();
  setTimeout(() => { if (S.story) S.story.ctrl.rest(); }, 60);
}
// A node pressed opens the real thing: its page, or its row on this page (scrolled to and marked for a moment).
function openFromStory(n) {
  if (!n) return;
  const row = (n.item && document.querySelector(`[data-item="${CSS.escape(n.item)}"]`)) || (n.row && document.querySelector(`[data-story-row="${CSS.escape(n.row)}"]`));
  if (row) { row.scrollIntoView({ block: "center", behavior: reducedMotion() ? "auto" : "smooth" }); row.classList.remove("cp-story-hit"); void row.offsetWidth; row.classList.add("cp-story-hit"); return; }
  if (n.file) {  // the page it names: in the reader of this tab, or on «Akte»
    S.file = n.file; S.page = n.page || null; S.follow = false;
    if (S.route.tab === "claim_reader") renderCase().then(() => { const card = document.getElementById("source-card") || document.querySelector(".cp-live"); if (card) card.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" }); });
    else location.hash = `#/case/${S.route.id}/claim_reader`;
    return;
  }
  if (n.href) location.hash = n.href;
}
function placeStory() {
  const box = document.getElementById("story"), layer = document.getElementById("cp-story-layer");
  if (!box || !layer || !layer.firstElementChild) return;
  layer.style.display = "block";   // measured only once it is shown
  if (S.storyBig) return;          // large: it stands over the page, not in its place
  const h = layer.firstElementChild.offsetHeight;
  if (h && box.style.height !== `${h}px`) box.style.height = `${h}px`;
  const r = box.getBoundingClientRect();
  Object.assign(layer.style, { display: "block", top: `${r.top + window.scrollY}px`, left: `${r.left + window.scrollX}px`, width: `${r.width}px` });
}
function dropStory(keepLayer) {
  if (S.storyBig) { S.storyBig = false; const back = document.getElementById("cp-story-back"); if (back) back.remove(); document.documentElement.classList.remove("cp-story-open"); const l = document.getElementById("cp-story-layer"); if (l) l.classList.remove("cp-story-big"); }
  if (S.story) { try { S.story.ctrl.destroy(); } catch (error) { /* gone with its page */ } S.story = null; }
  const layer = document.getElementById("cp-story-layer");
  if (layer) { layer.innerHTML = ""; if (!keepLayer) layer.style.display = "none"; }
}
window.addEventListener("resize", placeStory);
if (window.ResizeObserver) new ResizeObserver(placeStory).observe(document.getElementById("app"));
async function openStory() {
  const run = (S.data.prepared_run || {}).id;
  S.storyOpen = S.storyOpen === S.route.id ? null : S.route.id;
  if (S.storyOpen && run && !(S.storyEvents || {})[run]) {
    try { (S.storyEvents = S.storyEvents || {})[run] = (await api(`/api/runs/${run}`)).events || []; } catch (error) { S.storyEvents[run] = []; }
  }
  renderCase();
}
// ---------- the tabs' pictures: the case's state as it stands, drawn by the same engine ----------
// A picture stands by itself where it is the best way to see the thing (the process as a flow, the knowledge as it
// travels). Where a table or the reader does the work (Akte, Unterlagen, Verlauf) it waits behind one quiet line and
// comes when asked for; the choice is kept per page.
const PICTURE_ASKED = new Set(["file", "documents", "history"]);
const pictureOff = (kind) => { try { const v = localStorage.getItem(`casepath.picture.${kind}`); return v ? v === "off" : PICTURE_ASKED.has(kind); } catch (error) { return PICTURE_ASKED.has(kind); } };
const TAB_STORY = { process: () => processStory(), history: () => historyStory(), documents: () => documentsStory(), knowledge: () => knowledgeStory(), file: () => fileStory() };
function tabPicture(kind, height) {
  if (!pictureOff(kind)) return `<div class="cp-story cp-story-tab" id="story" data-story="${kind}" data-height="${height}"></div>`;
  return TAB_STORY[kind]() ? `<p class="cp-story-show"><button class="cp-link cp-quiet-link" id="story-show" data-kind="${kind}">${icon("nodes")}${T("Show as a picture", "Als Bild zeigen")}</button></p>` : "";
}
function setPicture(shown, kind) { try { localStorage.setItem(`casepath.picture.${kind}`, shown ? "on" : "off"); } catch (error) { /* this visit only */ } if (S.route.view === "knowledge") renderKnowledge(); else renderCase(); }
const storyLabels = () => ({ big: T("Large", "Gross ansehen"), small: T("Back to the page", "Zurück zur Seite"), play: T("Play", "Abspielen"), pause: T("Pause", "Anhalten"), replay: T("Again", "Nochmals"), step: T("Step", "Schritt"), of: T("of", "von"), close: T("Close", "Schliessen"), whole: T("Whole picture", "Ganzes Bild") });
function storyKit() {
  const nodes = [], edges = [], beats = [], have = new Set(), linked = new Set();
  const node = (n) => { if (!have.has(n.id)) { have.add(n.id); nodes.push(n); } return n.id; };
  const edge = (from, to, kind, label) => { const k = `${from}>${to}`; if (from !== to && have.has(from) && have.has(to) && !linked.has(k)) { linked.add(k); edges.push({ from, to, kind, label }); return [from, to]; } return null; };
  const beat = (what, why, reveal, drawn, focus) => beats.push({ caption: { what, why: why || "" }, reveal: (reveal || []).filter(Boolean), edges: (drawn || []).filter(Boolean), focus: (focus || reveal || []).filter(Boolean), agent: "" });
  return { node, edge, beat, have, beats, model: (lanes, from) => ({ lanes, nodes, edges, beats, live: false, from: from || 0, labels: { ...storyLabels(), close: T("Hide the picture", "Bild ausblenden") } }) };
}
// Prozess: the way the case came (each step with the facts that took it on), where it stands, what is open there, and
// the branches it can take from here with what decides them.
function processStory() {
  const g = graphModel();
  if (!g || S.editing) return null;
  const k = storyKit(), id = S.route.id, ev = S.data.evaluation, sc = scr(), here = `#/case/${id}/process_builder`;
  const step = (st, state) => k.node({ id: `step:${st.id}`, lane: "path", kind: "step", title: tr(shortTitle(st.title)), state, item: `step:${st.id}`, href: here });
  const fact = (fid, open) => { const f = item("fact", fid) || {}, src = (f.evidence || []).find((e) => e.file) || {};
    return k.node({ id: `fact:${fid}`, lane: "facts", kind: "fact", title: tr(shortFact(fid)), sub: open ? T("open", "offen") : tr(plainValue(f.value)), state: open ? "missing" : "done", item: f.item_id, file: src.file, page: src.page, href: `#/case/${id}/claim_reader` }); };
  const settled = (fid) => { const f = item("fact", fid); return f && f.value !== null && f.value !== undefined && f.value !== ""; };
  const onPath = new Set(g.path.map((p) => p.step.id)), order = (S.data.process.steps || []).map((x) => x.id), first = (g.path[0] || {}).step;
  const behind = first ? (ev.reached || []).filter((x) => !onPath.has(x) && g.steps[x] && order.indexOf(x) < order.indexOf(first.id)).sort((a, b) => order.indexOf(a) - order.indexOf(b)) : [];
  let prev = null, from = 0;
  for (const x of behind) { const sid = step(g.steps[x], "done"); k.beat(`${T("Done", "Erledigt")}: ${tr(shortTitle(g.steps[x].title))}`, T("as the file shows", "laut Akte"), [sid], [prev && k.edge(prev, sid, "leads")]); prev = sid; }
  g.path.forEach((n, i) => {
    const now = n.state === "current", sid = step(n.step, now ? "now" : "done"), next = g.path[i + 1];
    const via = next ? (n.step.next || []).find((e) => e.to === next.step.id) : null;
    const decided = now ? [] : [...new Set(factsIn(via && via.when))].filter(settled).slice(0, 4);
    const fids = decided.map((f) => fact(f, false));
    if (now) from = k.beats.length;
    k.beat(`${now ? T("Now", "Jetzt") : T("Done", "Erledigt")}: ${tr(shortTitle(n.step.title))}`,
      now ? (sc.title ? `${T("Next", "Als Nächstes")}: ${tr(sc.title)}` : "") : decided.map((f) => `${tr(shortFact(f))}: ${tr(plainValue(item("fact", f).value))}`).join(" · "),
      [sid, ...fids], [prev && k.edge(prev, sid, "leads"), ...fids.map((f) => k.edge(f, sid, "cites"))]);
    prev = sid;
  });
  const current = g.path.find((p) => p.state === "current") || g.path[g.path.length - 1];
  if (!current) return null;
  const at = `step:${current.step.id}`;
  if (!ev.outcome) {
    const asked = new Set(["deckung", ...((S.data.draft || {}).needs || [])]);
    const waiting = (ev.waiting_for || []).filter((w) => !asked.has(w.fact)).slice(0, 5).map((w) => fact(w.fact, true));
    const docs = sc.missing ? k.node({ id: "docs", lane: "facts", kind: "need", title: T("Documents", "Unterlagen"), sub: T(`${sc.missing} missing`, `${sc.missing} fehl${sc.missing === 1 ? "t" : "en"}`), state: "missing", href: `#/case/${id}/document_finder` }) : null;
    const open = [...waiting, docs].filter(Boolean);
    if (open.length) k.beat(T("Still open at this step", "An diesem Schritt noch offen"), open.map((x) => (k.have.has(x) && x.startsWith("fact:") ? tr(shortFact(x.slice(5))) : T("Documents", "Unterlagen"))).join(" · "), open, open.map((x) => k.edge(x, at, "cites")), [at, ...open]);
    const seen = new Set(), ways = (current.step.next || []).filter((e) => g.steps[e.to] && !onPath.has(e.to) && !seen.has(e.to) && seen.add(e.to));
    const ids = ways.map((e) => k.node({ id: `step:${e.to}`, lane: "next", kind: "step", title: tr(shortTitle(g.steps[e.to].title)), state: "open", href: here }));
    const rests = [...new Set(ways.flatMap((e) => factsIn(e.when)))].slice(0, 3).map((f) => tr(shortFact(f)));
    if (ids.length) k.beat(T("Then, depending on the case", "Danach, je nach Fall"), rests.length ? `${T("decided by", "entscheidet sich an")}: ${rests.join(" · ")}` : "", ids, ids.map((x) => k.edge(at, x, "branch")), [at, ...ids]);
  } else {
    const oid = k.node({ id: "outcome", lane: "next", kind: "decision", title: tr(ev.outcome.title), state: "done", href: here });
    k.beat(`${T("End", "Abschluss")}: ${tr(ev.outcome.title)}`, "", [oid], [k.edge(at, oid, "leads")]);
  }
  return k.model([{ id: "facts", title: T("Rests on", "Beruht auf") }, { id: "path", title: T("The case's path", "Weg des Falls") }, { id: "next", title: T("Then", "Danach") }], from);
}
// Prozess as a flow: every step that leads on is a block (what CasePath prepares there, then each way out of it by its
// own name with what decides it), every closing a small end piece at the way that leads to it. The way the case came is
// marked, the block it stands in carries what is open there and the decisions that are the handler's to take.
function processFlow() {
  const g = graphModel();
  if (!g || S.editing) return null;
  const d = S.data, ev = d.evaluation, proc = d.process, here = new Map(g.path.map((p, i) => [p.step.id, { state: p.state, i }]));
  const reached = new Set([...(ev.reached || []), ...here.keys()]);
  const ends = new Set(proc.steps.filter((x) => !(x.next || []).length).map((x) => x.id));
  const settled = (fid) => { const f = item("fact", fid); return f && f.value !== null && f.value !== undefined && f.value !== ""; };
  const tone = (x) => ((here.get(x.id) || {}).state === "current" ? "now" : here.has(x.id) || reached.has(x.id) ? "done" : "open");
  const asked = new Set(["deckung", ...((d.draft || {}).needs || [])]), sc = scr();
  const blocks = proc.steps.filter((x) => !ends.has(x.id)).map((x) => {
    const t = tone(x), at = here.get(x.id), next = at ? g.path[at.i + 1] : null, rows = [];
    if (x.action && x.action.title) rows.push({ id: "action", kind: "action", text: tr(t === "now" && sc.title ? sc.title : x.action.title), sub: T("CasePath prepares", "bereitet CasePath vor"), state: t === "done" ? "done" : t === "now" ? "now" : "open" });
    if (t === "now" && !ev.outcome) {
      const cover = item("cover", "summary");
      if (cover && !["gegenpartei", "mandat", "abwicklung"].includes(x.id)) rows.push({ id: "cover", kind: "decision", text: T("Cover", "Deckung"), sub: tr(String(cover.value || "").replace(/^Deckung: /, "")), state: answered("deckung") ? "done" : "open",
        value: answered("deckung") ? tr(String(answered("deckung"))) : "", actions: answered("deckung") ? [] : [{ id: "deckung:bestätigt", text: T("confirm", "bestätigen"), primary: true }, { id: "deckung:abgelehnt", text: T("refuse", "ablehnen") }] });
      for (const w of (ev.waiting_for || []).filter((w) => !asked.has(w.fact)).slice(0, 4)) rows.push({ id: `open:${w.fact}`, kind: "open", text: tr(shortFact(w.fact)), sub: T("open", "offen"), state: "open", item: `fact:${w.fact}` });
      if (sc.missing) rows.push({ id: "docs", kind: "need", text: T("Documents", "Unterlagen"), sub: T(`${sc.missing} missing`, `${sc.missing} fehl${sc.missing === 1 ? "t" : "en"}`), state: "missing", href: `#/case/${S.route.id}/document_finder` });
    }
    let took = false;
    (x.next || []).forEach((e, i) => {
      const target = g.steps[e.to];
      if (!target) return;
      const facts = [...new Set(factsIn(e.when))], known = facts.filter(settled);
      // the way the case took: the one to the next step on its path whose facts the file settled (the first such, else the first to it)
      const taken = !took && next && next.step.id === e.to && (known.length === facts.length || !(x.next || []).some((o, j) => j > i && o.to === e.to));
      if (taken) took = true;
      rows.push({ id: `out:${i}`, kind: "outcome", text: tr(e.label || shortTitle(target.title)), state: taken ? "taken" : t === "done" ? "passed" : "possible",
        sub: known.slice(0, 2).map((f) => `${tr(shortFact(f))}: ${tr(plainValue(item("fact", f).value))}`).join(" · ") || facts.slice(0, 2).map((f) => tr(shortFact(f))).join(" · "),
        ...(ends.has(e.to) ? { end: { id: e.to, text: tr(shortTitle(target.title)), state: ev.outcome && taken ? "done" : "open" } } : { to: e.to }) });
    });
    return { id: x.id, title: tr(shortTitle(x.title)), tone: t, rows, item: `step:${x.id}` };
  });
  return { blocks, path: g.path.map((p) => p.step.id).filter((x) => !ends.has(x)), now: (g.path.find((p) => p.state === "current") || {}).step ? g.path.find((p) => p.state === "current").step.id : null,
    labels: { whole: T("Whole process", "Ganzer Prozess"), here: T("Where the case stands", "Wo der Fall steht"), big: T("Large", "Gross ansehen"), small: T("Back to the page", "Zurück zur Seite"),
      done: T("done", "erledigt"), now: T("now", "jetzt"), open: T("ahead", "noch offen"), taken: T("the way the case took", "der Weg des Falls") } };
}
// Verlauf: who wrote to whom, in the order it happened; a request is joined to its answer, what is open stays marked.
// The line under the picture is the case's time: drag along it to see the case as it stood then.
function historyStory() {
  const all = (S.data.verlauf || []).filter((r) => r.kind !== "gesture" && r.who);
  if (all.length < 2) return null;
  const rows = [...all].sort((a, b) => String(a.date || "9999").localeCompare(String(b.date || "9999")) || (a.number || 0) - (b.number || 0));
  const shown = rows.slice(-30), earlier = rows.length - shown.length;
  const k = storyKit(), lanes = [], byNo = {};
  const side = (r) => String(r.who).split("→")[0].trim();
  for (const r of shown) {
    const lane = side(r);
    if (!lanes.some((l) => l.id === lane)) lanes.push({ id: lane, title: tr(lane) });
    const to = String(r.who).split("→")[1] || "", src = (r.evidence || [])[0] || {};
    const nid = k.node({ id: `entry:${r.key}`, lane, kind: "entry", title: clip(r.what || r.title || "", 58), sub: `${dateText(r.date) || T("undated", "ohne Datum")} · ${T("to", "an")} ${tr(to.trim())}`, state: r.open ? "now" : "", item: String(r.key).startsWith("entry:") ? r.key : "", file: src.file, page: src.page });
    if (r.number !== null && r.number !== undefined) byNo[r.number] = nid;
  }
  // what the notes say of other entries («beantwortet (Nr. 9)», «zu Nr. 5»): the request and its answer, joined
  const links = (r) => (r.notes || []).flatMap((n) => [...String(n.text || "").matchAll(/Nr\.\s*(\d+(?:,\s*\d+)*)/g)].flatMap((m) => m[1].split(/,\s*/).map(Number))).filter((n) => byNo[n] && n !== r.number);
  const at = Object.fromEntries(shown.map((r, i) => [`entry:${r.key}`, i]));
  shown.forEach((r, i) => {
    const note = (r.notes || []).find((n) => n.open) || (r.notes || [])[0];
    k.beat(`${dateText(r.date) || T("undated", "ohne Datum")} · ${tr(r.who)}`, `${clip(r.what || r.title || "", 110)}${note ? ` · ${clip(note.text, 90)}` : ""}${i === 0 && earlier ? ` · ${earlier} ${T("earlier entries in the table", "frühere Einträge in der Tabelle")}` : ""}`, [`entry:${r.key}`]);
  });
  // the line runs from the earlier entry to the later one and is drawn when the later one arrives
  const joined = new Set();
  shown.forEach((r, i) => links(r).forEach((n) => {
    const j = at[byNo[n]], a = Math.min(i, j), b = Math.max(i, j), pair = `${a}-${b}`;
    if (joined.has(pair)) return;
    joined.add(pair);
    const e = k.edge(`entry:${shown[a].key}`, `entry:${shown[b].key}`, "leads");
    if (e) k.beats[b].edges.push(e);
  }));
  const open = shown.filter((r) => r.open).map((r) => `entry:${r.key}`);
  if (open.length) k.beat(T(`Open: ${open.length}`, `Offen: ${open.length}`), shown.filter((r) => r.open).map((r) => clip(((r.notes || []).find((n) => n.open) || {}).text || r.what || "", 70)).join(" · "), [], [], open);
  const rank = (l) => { const at = Object.values(PARTY_DE).indexOf(l.id); return at < 0 ? 99 : at; };
  return k.model(lanes.sort((a, b) => rank(a) - rank(b)), Math.max(0, k.beats.length - (open.length ? 3 : 2)));
}
// Unterlagen: what this case needs and why (what closed cases taught, what the law asks), what the files hold of it with
// the passage, and what is missing.
function documentsStory() {
  if (!S.data.evaluation || !S.data.screen) return null;
  const docs = (S.data.items || []).filter((i) => i.kind === "document" && !i.part_of);
  if (!docs.length) return null;
  const every = docs.length, id = S.route.id, proc = S.data.process || {}, sc = scr(), gone = new Set(sc.missing_ids || []);
  const rank = (i) => (gone.has(i.item_id) ? 0 : i.status === "present" ? 1 : 2);
  docs.sort((a, b) => rank(a) - rank(b));
  docs.length = Math.min(docs.length, 12);  // the missing and the found first; the table below holds every one
  const k = storyKit();
  const pd = (i) => (proc.documents || []).find((d) => d.id === i.key) || {};
  const name = (i) => tr((i.label || {}).de || pd(i).title || i.key);
  const practice = (i) => i.practice || (pd(i).knowledge ? practiceNote(pd(i).knowledge) : "");
  const law = (i) => (practice(i) ? "" : i.legal_basis || pd(i).legal_basis || "");
  const need = (i) => k.node({ id: `need:${i.key}`, lane: "needs", kind: "need", title: name(i), sub: tr(practice(i) || law(i) || ""), state: i.status === "present" ? "present" : gone.has(i.item_id) ? "missing" : "", item: i.item_id });
  const learned = docs.filter(practice), legal = docs.filter(law), plain = docs.filter((i) => !practice(i) && !law(i));
  if (learned.length) {
    const kid = k.node({ id: "knowledge", lane: "why", kind: "knowledge", title: T("Closed cases", "Abgeschlossene Fälle"), sub: T("what practice asked for", "was die Praxis verlangt hat"), href: "#/knowledge" });
    k.beat(T(`Learned from closed cases: ${learned.length}`, `Aus abgeschlossenen Fällen gelernt: ${learned.length}`), `${name(learned[0])}: ${tr(practice(learned[0]))}`, [kid, ...learned.map(need)], learned.map((i) => k.edge(kid, `need:${i.key}`, "learned")));
  }
  if (legal.length) {
    const lid = k.node({ id: "law", lane: "why", kind: "knowledge", title: T("Law", "Gesetz"), sub: T("what the law asks for", "was das Gesetz verlangt") });
    k.beat(T(`Asked for by the law: ${legal.length}`, `Vom Gesetz verlangt: ${legal.length}`), legal.slice(0, 3).map((i) => `${name(i)}: ${tr(law(i))}`).join(" · "), [lid, ...legal.map(need)], legal.map((i) => k.edge(lid, `need:${i.key}`, "cites")));
  }
  if (plain.length) k.beat(T(`Part of this process: ${plain.length}`, `Gehört zu diesem Prozess: ${plain.length}`), plain.slice(0, 4).map(name).join(" · "), plain.map(need));
  const from = k.beats.length, files = S.data.files || [], on = docs.filter((i) => i.status === "present");
  const fids = files.map((f) => k.node({ id: `file:${f.id}`, lane: "files", kind: "file", title: f.name, sub: (f.extraction || {}).pages > 1 ? `${((f.extraction || {}).kept_pages || []).length || f.extraction.pages} ${T("pages", "Seiten")}` : dateText(f.created_at), file: f.id }));
  k.beat(T(`In the file: ${on.length} of ${docs.length}`, `In der Akte: ${on.length} von ${docs.length}`), on.slice(0, 5).map(name).join(" · "), fids,
    on.map((i) => { const c = (i.evidence || []).find((x) => x.file); return c ? k.edge(`file:${c.file}`, `need:${i.key}`, "cites", c.page ? `${T("p.", "S.")} ${c.page}` : "") : null; }), [...fids, ...on.map((i) => `need:${i.key}`)]);
  const missing = docs.filter((i) => gone.has(i.item_id));
  if (missing.length) k.beat(T(`Missing: ${missing.length}`, `Fehlt: ${missing.length}`), missing.map(name).join(" · "), [], [], missing.map((i) => `need:${i.key}`));
  if (every > docs.length && k.beats.length) k.beats[k.beats.length - 1].caption.why += ` · ${every - docs.length} ${T("more in the table below", "weitere in der Tabelle unten")}`;
  return k.model([{ id: "files", title: T("In the file", "In der Akte") }, { id: "needs", title: T("The case needs", "Der Fall braucht") }, { id: "why", title: T("Why", "Warum") }], from);
}
// Wissen: where each rule came from (a case, a case worker's change, the first request letters of practice), and the
// cases it was applied in since, in the order it happened: what one case taught reaching the next.
// Akte: the documents the file holds, in the order of their dates, and what was taken from each with its passage; what
// stands without a passage is said last. A card opens the page it names in the reader below.
function fileStory() {
  const d = S.data, files = d.files || [];
  const facts = (d.items || []).filter((i) => i.kind === "fact" && i.value !== null && i.value !== undefined && i.value !== "" && !i.chat_only);
  if (!files.length || facts.length < 2 || !d.screen) return null;
  const k = storyKit(), docs = [];
  const day = (text) => { const m = String(text || "").match(/^(\d{2})\.(\d{2})\.(\d{4})$/); return m ? `${m[3]}-${m[2]}-${m[1]}` : String(text || "9999"); };
  for (const f of files) {
    const segs = (f.extraction || {}).segments || [];
    if (segs.length) segs.forEach((sg, n) => docs.push({ id: `doc:${f.id}:${n}`, file: f.id, from: sg.first_page || 1, to: sg.last_page || sg.first_page || 1, title: sg.title || sg.kind || f.name, date: sg.date || "",
      who: [sg.sender, sg.recipient].filter(Boolean).join(" → ") }));
    else docs.push({ id: `doc:${f.id}`, file: f.id, from: 1, to: 1e9, title: f.name, date: dateText(f.created_at), who: "" });
  }
  const docOf = (ev) => docs.find((x) => x.file === ev.file && (!ev.page || (ev.page >= x.from && ev.page <= x.to))) || docs.find((x) => x.file === ev.file);
  const rests = facts.map((i) => { const ev = (i.evidence || []).find((e) => e.file); return { i, ev, doc: ev ? docOf(ev) : null }; });
  const count = (x) => rests.filter((r) => r.doc === x).length;
  const cited = docs.filter(count).sort((a, b) => count(b) - count(a)).slice(0, 10).sort((a, b) => day(a.date).localeCompare(day(b.date)));
  if (!cited.length) return null;
  const name = (i) => tr((i.label || {}).de || shortFact(i.key)), pages = (x) => (x.to >= 1e9 ? "" : `${T("p.", "S.")} ${x.from}${x.to > x.from ? `–${x.to}` : ""}`);
  for (const x of cited) {
    const mine = rests.filter((r) => r.doc === x), shown = mine.slice(0, 3);
    const did = k.node({ id: x.id, lane: "docs", kind: "file", title: tr(x.title), sub: [x.date, pages(x)].filter(Boolean).join(" · "), file: x.file, page: x.to >= 1e9 ? null : x.from });
    const fids = shown.map((r) => k.node({ id: `fact:${r.i.key}`, lane: "facts", kind: "fact", title: clip(name(r.i), 80), sub: tr(plainValue(r.i.value)), state: "done", file: r.ev.file, page: r.ev.page || null }));
    k.beat(`${x.date ? `${x.date} · ` : ""}${tr(x.title)}`, `${x.who ? `${tr(x.who)} · ` : ""}${mine.length} ${T(mine.length === 1 ? "fact taken from it" : "facts taken from it", mine.length === 1 ? "Angabe daraus" : "Angaben daraus")}${mine.length > shown.length ? ` (${shown.length} ${T("drawn", "gezeichnet")})` : ""}`,
      [did, ...fids], shown.map((r) => k.edge(did, `fact:${r.i.key}`, "cites", r.ev.page ? `${T("p.", "S.")} ${r.ev.page}` : "")));
  }
  const bare = rests.filter((r) => !r.ev), own = bare.filter((r) => r.i.verdict === "set_by_handler").length;
  const quiet = docs.length - cited.length;
  if (bare.length || quiet) k.beat(bare.length ? T(`${bare.length} further facts are derived or decided, not read from a passage`, `${bare.length} weitere Angaben sind abgeleitet oder entschieden, nicht aus einer Textstelle gelesen`) : T("Every fact drawn has its passage", "Jede gezeichnete Angabe hat ihre Stelle"),
    [own ? `${own} ${T(own === 1 ? "is your own decision" : "are your own decisions", own === 1 ? "ist Ihr eigener Entscheid" : "sind Ihre eigenen Entscheide")}` : "",
      quiet ? `${quiet} ${T(quiet === 1 ? "document without a fact taken from it" : "documents without a fact taken from them", quiet === 1 ? "Dokument, aus dem keine Angabe stammt" : "Dokumente, aus denen keine Angabe stammt")}` : ""].filter(Boolean).join(" · "), [], [], cited.map((x) => x.id));
  return k.model([{ id: "docs", title: T("Documents in the file", "Dokumente der Akte") }, { id: "facts", title: T("Taken from them", "Daraus entnommen") }], Math.max(0, k.beats.length - 3));
}
const STORY_RULES = 8, STORY_CASES = 10, STORY_NODES = 44;  // what one picture holds and stays readable
function knowledgeStory() {
  const v = S.knowledgeView;
  if (!v || !v.entries.length) return null;
  const k = storyKit(), happened = [], applied = {};
  const name = (e) => tr(e.content.title || e.content.question || e.content.text || "");
  // a picture is read, so it holds what a reader can take in: the rules that came from a case or were applied in one,
  // the eight that moved last, and the cases they reached last; the list below holds every rule
  const last = (e) => [e.created_at || "", ...(e.uses || []).map((u) => u.at || "")].sort().pop();
  const moved = v.entries.filter((e) => (e.uses || []).length || (e.origin || {}).case_id);
  const drawn = (moved.length ? moved : v.entries).slice().sort((a, b) => String(last(b)).localeCompare(String(last(a)))).slice(0, STORY_RULES);
  const left = v.entries.length - drawn.length;
  for (const e of drawn) {
    happened.push({ at: e.created_at || ((e.history || [])[0] || {}).at || "", kind: "learned", e });
    for (const h of (e.history || []).filter((h) => h.version > 1 && /^refined/.test(h.change || ""))) happened.push({ at: h.at || "", kind: "refined", e, h });
    for (const u of e.uses || []) {
      // a case takes up its rules in one go: one moment per case, at the time it first did
      const g = applied[u.case_id] = applied[u.case_id] || { at: u.at || "", case: u.case_id, kind: "applied", parts: new Map() };
      if (String(u.at || "") < g.at) g.at = u.at || "";
      if (!g.parts.has(e)) g.parts.set(e, []);
      g.parts.get(e).push(u);
    }
  }
  happened.push(...Object.values(applied));
  happened.sort((a, b) => String(a.at).localeCompare(String(b.at)) || String(a.case || "").localeCompare(String(b.case || "")));
  const cases = [...new Set(happened.filter((x) => x.kind === "applied").map((x) => x.case))], shown = new Set(cases.slice(-STORY_CASES));
  const itemNode = (e) => k.node({ id: `k:${e.ids[0]}`, lane: "knowledge", kind: "knowledge", title: name(e), row: e.ids[0],
    sub: `${e.status === "active" ? `v${e.version}` : tr(word(e.status))} · ${T(`used ${e.stats.uses} times`, `${e.stats.uses}× verwendet`)}` });
  let i = 0;
  while (i < happened.length) {
    const x = happened[i];
    if (x.kind === "learned") {
      const o = x.e.origin || {}, quote = ((x.e.evidence || []).find((q) => q.quote) || {}).quote;
      const from = o.case_id ? k.node({ id: `from:${o.case_id}`, lane: "from", kind: "file", title: tr(v.caseName(o.case_id)), sub: o.kind === "case_edit" ? T("a case worker's change", "Änderung der Fallbearbeitung") : T("a prepared case", "ein vorbereiteter Fall"), href: `#/case/${o.case_id}/overview` })
        : k.node({ id: "from:practice", lane: "from", kind: "file", title: T("First request letters", "Erste Unterlagenanforderungen"), sub: T("practice, counts only", "Praxis, nur Zählungen") });
      const nid = itemNode(x.e);
      k.beat(`${T("Learned", "Gelernt")}: ${clip(name(x.e), 70)}`, o.case_id ? `${T("from", "aus")} ${tr(v.caseName(o.case_id))}${quote ? `: «${clip(quote, 90)}»` : ""}` : tr(seededNote(x.e) || byWhom(o.by)), [from, nid], [k.edge(from, nid, "cites")]);
      i += 1;
    } else if (x.kind === "refined") {
      k.beat(`${T("Refined", "Verfeinert")}: ${clip(name(x.e), 60)} · v${x.h.version}`, `${tr(changeText(x.h.change))}${x.h.by ? ` · ${byWhom(x.h.by)}` : ""}`, [], [], [itemNode(x.e)]);
      i += 1;
    } else {
      i += 1;
      if (!shown.has(x.case)) continue;
      const group = [...x.parts.keys()].map((e) => ({ e })), uses = [...x.parts.values()].flat(), count = (o) => uses.filter((u) => u.outcome === o).length;
      const said = [["present", T("on file", "liegt vor")], ["confirmed", T("confirmed", "bestätigt")], ["applied", T("asked for", "verlangt")], ["not_found", T("not found", "nicht gefunden")], ["contradicted", T("contradicted", "widersprochen")]]
        .filter(([o]) => count(o)).map(([o, w]) => `${count(o)} ${w}`).join(" · ");
      const to = k.node({ id: `to:${x.case}`, lane: "to", kind: "entry", title: tr(v.caseName(x.case)), sub: said, state: count("contradicted") ? "now" : "", href: `#/case/${x.case}/document_finder` });
      k.beat(`${T("Applied in", "Angewendet in")} ${clip(v.caseName(x.case), 60)}`, `${group.length} ${T(group.length === 1 ? "rule" : "rules", group.length === 1 ? "Regel" : "Regeln")} · ${said}`, [to], group.map((g) => k.edge(itemNode(g.e), to, "learned")), [to, ...group.map((g) => `k:${g.e.ids[0]}`)]);
    }
  }
  const rest = [cases.length > shown.size ? `${cases.length - shown.size} ${T("earlier cases not drawn", "frühere Fälle nicht gezeichnet")}` : "",
    left > 0 ? `${left} ${T(left === 1 ? "more rule in the list below" : "more rules in the list below", left === 1 ? "weitere Regel in der Liste unten" : "weitere Regeln in der Liste unten")}` : ""].filter(Boolean).join(" · ");
  if (rest && k.beats.length) k.beats[k.beats.length - 1].caption.why += ` · ${rest}`;
  return k.model([{ id: "from", title: T("Learned from", "Gelernt aus") }, { id: "knowledge", title: T("Knowledge", "Wissen") }, { id: "to", title: T("Applied in", "Angewendet in") }], Math.max(0, k.beats.length - 3));
}
// What CasePath did to get here, as the steps of its work with what each one gave, each leading to where it can be
// checked: said once, ticked in turn, when it finishes while the reader watches; later one press on the line above.
function workTrail(fresh) {
  const id = S.route.id, items = S.data.items || [], files = S.data.files || [];
  const pages = files.reduce((n, f) => n + (((f.extraction || {}).kept_pages || []).length || (f.extraction || {}).pages || 0), 0);
  const found = items.filter((i) => i.kind === "fact" && i.value !== null && i.value !== undefined && i.value !== "").length;
  const docs = items.filter((i) => i.kind === "document" && !i.part_of), have = docs.filter((i) => i.status === "present").length;
  const entries = (S.data.verlauf || []).length || items.filter((i) => i.kind === "entry").length;
  const dec = decisionsOpen();
  const draft = S.data.draft || {};
  const plural = (n, one, many) => (n === 1 ? one : many);
  const steps = [
    [`#/case/${id}/claim_reader`, `<b>${files.length}</b> ${T(plural(files.length, "file", "files"), plural(files.length, "Datei", "Dateien"))}${pages > 1 ? `, <b>${pages}</b> ${T("pages", "Seiten")}` : ""} ${T("read", "gelesen")}`],
    found ? [`#/case/${id}/claim_reader`, `<b>${found}</b> ${T(plural(found, "fact", "facts"), plural(found, "Angabe", "Angaben"))} ${T("found", "gefunden")}`] : null,
    entries ? [`#/case/${id}/history`, `<b>${entries}</b> ${T(plural(entries, "entry", "entries"), plural(entries, "Eintrag", "Einträge"))} ${T("in the history", "im Verlauf")}`] : null,
    docs.length ? [`#/case/${id}/document_finder`, `<b>${have}</b> ${T("of", "von")} <b>${docs.length}</b> ${T("documents on file", "Unterlagen liegen vor")}`] : null,
    draft.text ? [null, T("Letter written", "Brief geschrieben")] : null,
    dec ? [null, `<b>${dec}</b> ${T(plural(dec, "decision", "decisions"), plural(dec, "Entscheid", "Entscheide"))} ${T("for you", "für Sie")}`] : null,
  ].filter(Boolean);
  const watch = window.CasePathStory ? `<li class="cp-trail-watch"><button type="button" id="story-open" aria-expanded="${S.storyOpen === id}">${icon("right")}${S.storyOpen === id ? T("Close the picture", "Bild schliessen") : T("Watch how it was prepared", "Ansehen, wie es entstand")}</button></li>` : "";
  return `<ol class="cp-trail${fresh ? enter(`trail:${(S.data.prepared_run || {}).id}`) : ""}" data-trail aria-label="${T("What CasePath did", "Was CasePath getan hat")}">${steps.map(([href, text]) =>
    `<li><span class="cp-trail-tick">${icon("tick")}</span>${href ? `<a href="${href}">${text}</a>` : `<span>${text}</span>`}</li>`).join("")}${watch}</ol>`;
}
const decisionsOpen = () => (completionOf().decisions || []).length;
// The action bar answers a change of state (approved, sent, at rest) with a short movement, once, never on a mere re-render.
// A render that follows within the movement (the copy, the reload after it) carries it on from where it was.
function barChanged(kind) {
  const key = `${S.route.id}|${kind}`, was = S.barWas, now = Date.now();
  S.barWas = key;
  if (was && was !== key && was.split("|")[0] === S.route.id) S.barMoved = now;
  const gone = now - (S.barMoved || 0);
  return gone < 320 ? `cp-bar-changed" style="--cp-gone:-${gone}ms` : "";
}
function decisionsStrip(dec, primary) {
  const st = completionOf(), taken = st.decided || [], open = st.decisions || [];
  const now = dec ? decisionLine(dec, primary) : "";
  if (taken.length + open.length < 2 && !taken.length) return now;
  const nowWord = dec ? ({ deckung: "Deckung", empfehlung: "Empfehlung", aussichten: "Erfolgsaussichten", vorgehen: "Vorgehen" }[dec.key] || null) : null;
  const done = taken.map((d) => `<li class="cp-dstep done${enter(`dec:${d.key}:${d.edit || d.at || ""}`)}" data-decided="${raw(d.key)}" title="${esc([d.by, d.at ? dateText(d.at) : ""].filter(Boolean).join(" · "))}"><span class="cp-dmark">${icon("tick")}</span><span class="cp-dname">${esc(d.word)}</span>
      <span class="cp-dvalue">${esc(d.value)}</span><button class="cp-link cp-quiet-link" type="button" title="${T("Takes this decision back; it is then open again and asked anew", "Nimmt diesen Entscheid zurück; er ist dann wieder offen und wird neu gefragt")}" ${d.edit ? `data-decided-undo="${raw(d.edit)}"` : `data-decided-withdraw="${raw(d.key)}"`}>${T("take back", "zurücknehmen")}</button></li>`);
  let n = taken.length;
  const rest = open.map((w, i) => {
    n += 1;
    const current = dec && (w === nowWord || (!nowWord && i === 0));
    return current ? `<li class="cp-dstep now"><span class="cp-dmark">${n}</span>${now}</li>`
      : `<li class="cp-dstep open"><span class="cp-dmark">${n}</span><span class="cp-dname">${esc(w)}</span><span class="cp-dvalue cp-muted">${T("after that", "danach")}</span></li>`;
  });
  const shown = dec && !rest.some((r) => r.includes("cp-dstep now")) ? `<li class="cp-dstep now"><span class="cp-dmark">${taken.length + 1}</span>${now}</li>` : "";
  const left = open.length;
  return `<section class="cp-dsteps" data-decisions aria-label="${T("Decisions of this step", "Entscheide dieses Schritts")}"><p class="cp-dsteps-head">${T("Your decisions", "Ihre Entscheide")}
      <span class="cp-muted">· ${left ? T(`${left} open`, `${left} offen`) : T("all taken", "alle getroffen")}</span></p><ol>${[...done, shown, ...rest].join("")}</ol></section>`;
}
const policeOpen = () => (S.data.items || []).filter((i) => i.kind === "cover" && i.key !== "summary" && i.value === "police").length;
function decisionLine(dec, primary) {
  if (!dec) return "";
  const kg = dec.key === "kostennote" ? (S.data.items || []).filter((i) => i.kind === "stage_line" && /^kg-/.test(i.key)) : [];
  const detail = dec.key === "deckung" ? coverPanel() : kg.length ? kg.map((l) => `<div class="cp-decide-line" data-item="${raw(l.item_id)}">${esc(l.value)}${sourceChips(l.evidence)}</div>`).join("")
    : dec.key === "empfehlung" ? briefPanel(dec) : dec.key === "aussichten" ? prospectsPanel(dec)
    : (dec.sources || []).length ? `<div>${dec.sources.map((x) => sourceChip(x)).join(" ")}</div>` : dec.source ? `<div>${sourceChip(dec.source)}</div>` : "";
  const pressed = (a) => (a.document ? S.feeAnswer === a.document : a.decline ? answered("deckung") === "abgelehnt" : String(answered(a.decide)) === String(a.value));
  const first = primary ? (dec.answers || []).findIndex((a) => !a.choose) : -1;
  const answer = (a, n) => {
    const cls = `cp-button cp-small${n === first ? " primary" : ""}`;
    if (a.choose) return `<select class="cp-button cp-small" data-point-choose aria-label="${T("Choose process", "Prozess wählen")}"><option value="">${esc(a.label)} …</option>${(S.workflows || []).map((w) => `<option value="${raw(w.id)}">${esc(w.short_title || w.title)}</option>`).join("")}</select>`;
    if (a.decline) return `<button class="${cls}" data-cover-decline aria-pressed="${pressed(a)}">${esc(a.label)}</button>`;
    if (a.document) return `<button class="${cls}" data-fee-answer="${raw(a.document)}" aria-pressed="${pressed(a)}">${esc(a.label)}</button>`;
    if (a.stance) return `<button class="${cls}" data-stance="${raw(a.stance)}" aria-pressed="${dec.chosen === a.stance}" title="${esc(a.then || "")}">${esc(a.label)}</button>`;
    if (a.claim) return `<button class="cp-button cp-small" data-claim-settle="${raw(a.claim)}" data-as="${raw(a.as)}">${esc(a.label)}</button>`;  // none preselected: the handler's judgment
    if (a.adopt) return `<button class="${cls}" data-rec-adopt>${esc(a.label)}</button>`;
    if (a.change) return `<button class="${cls}" data-rec-change aria-expanded="${Boolean(S.recChange)}">${esc(a.label)}</button>`;
    return `<button class="${cls}" data-decide="${raw(a.decide)}" data-value="${raw(a.value ?? isoToday())}" aria-pressed="${pressed(a)}">${esc(a.label)}</button>`;
  };
  const why = S.coverDecline && dec.key === "deckung" ? `<p class="cp-reasons cp-cover-why"><span class="cp-muted">${T("Which point fails?", "Welcher Punkt ist nicht erfüllt?")}</span>
      ${(S.data.items || []).filter((i) => i.kind === "cover" && i.key !== "summary").map((x) => `<button class="cp-chip" data-cover-reason="${raw(x.key)}">${esc(x.title)}</button>`).join("")}<button class="cp-chip" data-cover-reason="anderer Grund">${T("other reason", "anderer Grund")}</button></p>` : "";
  const premise = dec.key === "deckung" && (brief() || {}).under_premise ? ` <span class="cp-muted cp-ddetail">${T("assessment prepared, subject to cover", "Einschätzung unter Vorbehalt der Deckung")}</span>` : "";
  const question = `<span class="cp-dq">${esc(dec.lapse || dec.question)}</span>${dec.detail ? ` <span class="cp-muted cp-ddetail">${esc(dec.detail)}</span>` : ""}${premise}`;
  // what follows each answer, said before it is given (an offer's three answers); once one is given, only its own line
  const thens = (dec.answers || []).filter((a) => a.then && (!dec.chosen || dec.chosen === a.stance));
  // the cover is confirmed as a whole: what only the policy can settle is named before the click, and kept with it
  const police = dec.key === "deckung" ? policeOpen() : 0;
  const follows = thens.length ? `<ul class="cp-decide-then">${thens.map((a) => `<li><b>${esc(a.label)}</b>: ${esc(a.then)}</li>`).join("")}</ul>`
    : police ? `<p class="cp-decide-note" data-police-open="${police}">${T(`«confirm» also confirms the ${police} point${police > 1 ? "s" : ""} only the policy settles.`, `«bestätigen» bestätigt auch ${police === 1 ? "den einen Punkt, den" : `die ${police} Punkte, die`} nur die Police klärt.`)}</p>` : "";
  const holder = dec.key === "kostennote" ? "next_action:0" : dec.key === "process" ? "point:process" : dec.key === "empfehlung" ? "point:empfehlung"
    : /^claim:/.test(dec.key) ? `point:${dec.key}` : `fact:${dec.key}`;
  const open = (S.decideOpen || (dec.key === "empfehlung" && S.recChange)) && detail;
  return `<div class="cp-decide" data-item="${raw(holder)}">${detail ? `<button class="cp-decide-q" id="decide-open" aria-expanded="${Boolean(open)}">${question}</button>` : `<span class="cp-decide-q">${question}</span>`}
    <span class="cp-point-actions">${(dec.answers || []).map(answer).join("")}</span>${follows}${open ? `<div class="cp-decide-more">${detail}</div>` : ""}${why}</div>`;
}
// The cover check, prepared: the edition and the policy's start, then each point with its clause and source; the policy
// ticks are the handler's. Opened from the cover decision, and on the Prozess tab.
function coverPanel() {
  const sum = item("cover", "summary");
  if (!sum) return "";
  const points = (S.data.items || []).filter((i) => i.kind === "cover" && i.key !== "summary");
  const editions = (item("fact", "avb_ausgabe") || {}).values || [];
  const begin = (item("fact", "police_beginn") || {}).value || "";
  return `<div class="cp-cover-open"><p class="cp-cover-head"><label>${T("Conditions", HOUSE.conditions.short)} <select class="cp-cover-select" data-cover-edition aria-label="${T("Edition of the conditions", `Ausgabe der ${HOUSE.conditions.name_inflected}`)}">${editions.map((v) => `<option ${v === sum.edition_value ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></label>
      <label>${T("Policy from", "Police ab")} <input type="date" class="cp-cover-select" data-cover-begin value="${raw(begin)}" aria-label="${T("Start of cover according to the policy", "Beginn des Versicherungsschutzes gemäss Police")}"></label></p>
    <ol class="cp-cover-points">${points.map(coverPoint).join("")}</ol></div>`;
}
// The payout as one line: «✓ Einigung · ✓ Bankverbindung · ● Auszahlung nachfragen · ○ Eingang · ○ Abschluss».
function progressLine(steps) {
  if (!steps || !steps.length) return "";
  const mark = { done: "✓", now: "●", next: "○" };
  return `<p class="cp-progress">${steps.map((s) => `<span class="${raw(s.state)}">${mark[s.state] || ""} ${esc(s.label)}</span>`).join(" · ")}</p>`;
}
function preparedView(st) {
  const act = item("next_action", "0"), sc = scr(), draft = S.data.draft || {};
  const c = closed();
  const stale = Boolean(S.data.draft_stale) && !c;  // new files not read yet (in every state: running, failed …): the draft may be out of date
  const editable = !c && st !== "running" && !stale;
  const { rows: docs, active } = documentsOut();
  const text = active ? docText(active) : "";
  const dec = c ? null : sc.decision;
  const acting = st === "prepared" && !c;  // the card's own primary: only when nothing above it (a run, new files) has one
  const open = dec && !(dec.key === "kostennote" && S.feeAnswer) && !(dec.key === "angebot" && dec.chosen);
  const decisionPrimary = Boolean(acting && open && (dec.answers || []).some((a) => !a.choose));
  const phone = !text && act && ["A2", "A9"].includes(act.action) && !c;
  const gaps = text ? gapCount(active) : 0;
  const docPrimary = acting && !decisionPrimary && Boolean(text) && !active.copied;
  const phonePrimary = acting && !decisionPrimary && phone;
  const closePrimary = acting && !decisionPrimary && !docPrimary && !phonePrimary && ((completionOf().bar || {}).kind === "study" || !text || closingStep(act, text));
  const label = gaps ? T(`Fill ${gaps} gap${gaps > 1 ? "s" : ""}`, `${gaps} Lücke${gaps > 1 ? "n" : ""} füllen`)
    : active && S.justCopied === active.kind ? `${icon("tick")}${T("Copied", "Kopiert")}` : active && active.copied ? T("Copy again", "Nochmals kopieren")
    : active && active.main ? T("Copy letter", "Brief kopieren") : T("Copy", "Kopieren");
  const f = S.data.follow_up, due = f && f.due;
  const then = act && act.deadline && (sc.danach || []).length ? `<span class="cp-date cp-then" title="${esc(sc.danach.join(" · "))}">${T("then", "danach")}: ${sc.danach.map(esc).join(" · ")}</span>` : "";
  const when = then || (due ? `<span class="cp-date ${daysTo(due) < 0 && !quiet() ? "late" : ""}" ${f.capped ? `title="${esc(T("before the deadline runs out", "vor Fristablauf"))}"` : ""}>${T("Follow-up", "Wiedervorlage")} <button class="cp-link" id="followup-show" type="button" title="${T("change", "ändern")}">${dateText(due)}</button>
        <input type="date" id="followup-date" value="${raw(due)}" aria-label="${T("Follow-up date", "Wiedervorlage")}" tabindex="-1"></span>` : "");
  // before «Freigeben»: the date the Versandpaket will file (counted from the dispatch, the reply date the letter sets, or
  // the handler's own), so the bar, the package, the note and the wait after the dispatch say one date
  const fa = S.data.follow_after_dispatch;
  const faWhy = !fa ? "" : fa.set ? T("set by you", "von Ihnen gesetzt") : fa.respond_by ? T("the reply date the letter sets", "das Antwortdatum im Brief")
    : fa.days ? T(`${fa.days} days after sending, if sent on ${dateText(fa.if_sent)}`, `${fa.days} Tage nach dem Versand, bei Versand am ${dateText(fa.if_sent)}`) : "";
  const whenAfter = then || (fa && fa.due ? `<span class="cp-date" title="${esc(faWhy)}">${T("Follow-up", "Wiedervorlage")} <button class="cp-link" id="followup-show" type="button" title="${T("change", "ändern")}">${dateText(fa.due)}</button>
        <input type="date" id="followup-date" value="${raw(fa.due)}" aria-label="${T("Follow-up date", "Wiedervorlage")}" tabindex="-1"></span>` : when);
  // a frozen study copy is copied and measured as frozen; any other case goes Freigeben → Brief kopieren → Versandt am
  const asFrozen = (completionOf().bar || {}).kind === "study" || !completionOf().bar;
  const docButton = !text || c ? "" : !asFrozen ? carryButtons(active, { primary: acting && !decisionPrimary, gaps, stale, when, whenAfter })
    : active.main ? `<button class="cp-button ${docPrimary ? "primary" : ""}" id="copy-draft" data-gaps="${gaps}" ${stale ? "disabled" : ""}>${label}</button>`
    : `<button class="cp-button ${docPrimary ? "primary" : ""}" data-copy-also="${raw(active.kind)}" data-gaps="${gaps}" ${stale ? "disabled" : ""}>${label}</button>`;
  const stage = ((S.data.evaluation || {}).current || {}).step || "";
  // whom the note is with: the step says it (a step that asks the customer is with the customer, whatever stage the case is at)
  const party = act && act.action === "A2" && draft.form !== "A2_bericht" ? "kunde"
    : act && (act.action === "A9" || stage === "gegenpartei" || stage === "abwicklung") ? "gegenpartei" : draft.form === "A2_bericht" || stage === "mandat" ? "kanzlei" : "kunde";
  const phoneButton = phone ? `<button class="cp-button ${phonePrimary ? "primary" : ""}" id="phone-note" type="button" data-kind="${draft.form === "A2_bericht" ? "notiz" : "telefon"}" data-party="${party}">${draft.form === "A2_bericht" ? T("Enter a note", "Aktennotiz erfassen") : T("Enter a phone note", "Telefonnotiz erfassen")}</button>` : "";
  // «Erledigt» only on a closing step, once its letter (if it has one) went out; a step with a letter ends with «Versandt am»
  const closable = asFrozen || closingStep(act, text);
  // the letter went out (or the case waits for its date): nothing is left to do here, the way on is the next case
  const barKind = (completionOf().bar || {}).kind;
  const settled = acting && !asFrozen && !decisionPrimary && !phonePrimary && !closePrimary && !stale && (barKind === "dispatched" || (barKind === "approve" && Boolean(completionOf().waits)));
  const onward = settled ? `<button class="cp-button primary" id="next-case" type="button">${T("Next case", "Nächster Fall")} ${icon("right")}</button>` : "";
  const bar = c ? `<span class="cp-closed">${icon("check")}<b>${c.form === "erledigt" ? T("Done", "Erledigt") : T("Done, with a reservation", "Erledigt, mit Vorbehalt")}</b>
        <span class="cp-muted">· ${dateText(c.at)} · ${esc(c.expert)}</span></span><span class="grow"></span><button class="cp-button primary" id="next-case">${T("Next case", "Nächster Fall")} ${icon("right")}</button>`
    : `${docButton}${asFrozen ? "" : restButtons()}${phoneButton}${asFrozen ? when : ""}<span class="grow"></span>${onward}
      ${["paused", "running"].includes(st) || !closable ? "" : `<span class="cp-split ${closePrimary ? "on" : ""}"><button class="cp-button ${closePrimary ? "primary" : ""}" data-close="erledigt">${T("Done", "Erledigt")}</button><details class="cp-split-more">
        <summary class="cp-button" aria-label="${T("more options", "weitere Möglichkeit")}">▾</summary><div class="cp-menu up"><input id="reservation" maxlength="2000" placeholder="${T("Reservation (optional)", "Vorbehalt (freiwillig)")}">
        <button class="cp-button" data-close="erledigt_mit_vorbehalt">${T("Done, with a reservation", "mit Vorbehalt")}</button></div></details></span>`}`;
  const options = (S.data.action_options || []).filter((o) => !act || o.kind !== act.action);
  const nextTitle = sc.title || (act ? T(act.label.en, act.label.de) : T("No prepared step", "Kein vorbereiteter Schritt"));
  // At rest: the letter went out and the case waits for its date. The card says so; the letter prepared for that day
  // waits folded behind one line and is never the thing to act on now.
  const waits = completionOf().waits, lastSent = completionOf().last || {}, went = (lastSent.dispatched || [])[0];
  const resting = Boolean(waits) && !c && !asFrozen && !dec && st === "prepared" && !stale && Boolean(went) && !(completionOf().bar || {}).rest;
  const folded = resting && S.restOpen !== S.route.id;
  const title = resting ? waits.charAt(0).toUpperCase() + waits.slice(1) : nextTitle;
  // «was hinausging»: the sent letter read in place (the package's own text), the package itself one link beside it
  const sentShown = resting && S.sentOpen && S.sentOpen.case === S.route.id && S.sentOpen.version === lastSent.version ? S.sentOpen : null;
  const restLine = !resting ? "" : `<p class="cp-rest"><span class="cp-sent">${icon("check")}${esc(lastSent.title ? `${lastSent.title} ` : "")}${T("sent", "versandt am")} ${dateText(went.date)}</span>
      ${((S.data.status || {}).bucket === "urteil" && (S.data.status || {}).text)  // the case waits, yet something in it asks for a look: said here as the rail and the list say it
        ? `<span class="cp-stand check" data-rest-status>· ${raw(standIn(S.data.status.text, S.data.status.kind))}</span>`
        : `<span class="cp-muted">· ${T("nothing to do until then", "bis dahin nichts zu tun")}</span>`}
      ${lastSent.version ? `<button class="cp-link cp-quiet-link" id="sent-open" type="button" data-version="${raw(lastSent.version)}" aria-expanded="${Boolean(sentShown)}">${sentShown ? "▾ " : "▸ "}${T("what went out", "was hinausging")}</button>` : ""}</p>
    ${sentShown ? sentLetter(sentShown, lastSent.version) : ""}
    <p class="cp-rest-next"><button class="cp-link cp-quiet-link" id="rest-open" type="button" aria-expanded="${!folded}">${folded ? "▸ " : "▾ "}${T("Prepared for then", "Für dann vorbereitet")}: ${esc(nextTitle)}</button></p>`;
  const tabs = docs.length > 1 || (docs[0] && docs[0].state && docs[0].state !== "entwurf") ? `<div class="cp-doc-tabs" role="tablist" aria-label="${T("What goes out", "Was hinausgeht")}">${docs.map((d) => `<button role="tab" class="cp-doc-tab ${d.state === "versandt" ? "copied" : ""}" data-doc-tab="${raw(d.kind)}" aria-selected="${d.kind === (active || {}).kind}">${esc(d.title)}${tabState(d)}</button>`).join("")}</div>` : "";
  // a call instead of a letter: what the call is about and what to ask stand in the card, and the note is written here
  const call = !text && draft.call && !c ? `<div class="cp-call" data-call>
      <p class="cp-call-head">${T("To settle in the call", "Im Gespräch zu klären")}</p><ol>${(draft.call.questions || []).map((q) => `<li>${esc(q)}</li>`).join("")}</ol></div>` : "";
  const noteHere = phone && S.noting && S.noteInCard && !S.entryEdit ? entryForm() : "";
  S.noteShown = Boolean(noteHere);  // the form stands once: here, or in «Der Fall» (sideView, rendered after the card)
  const body = text ? (active.main ? letterView(text, editable) : alsoView(active, editable))
    : call || noteHere ? `${call}${noteHere}` : `<p class="cp-muted cp-noletter">${esc(draft.none ? `${T("No draft", "Kein Entwurf")}: ${draft.none}` : T("No letter for this step", "Für diesen Schritt kein Brief"))}</p>`;
  const required = active && active.main && (draft.required || []).length ? `<p class="cp-required">${T("Required", "Pflichtteile")}: ${draft.required.map((r) => `${esc(r.title)} <span class="cp-muted">(${esc(r.basis)})</span>`).join(" · ")}</p>` : "";
  const head = `<section class="cp-card cp-prepared ${sc.urgency === "dringend" && !c ? "urgent" : ""} ${folded ? "cp-resting" : ""}">
    ${folded || c ? "" : preparedBy()}<header class="cp-prep-head">${folded ? `<span class="cp-done-badge${enter("rest")}" aria-hidden="true">${icon("tick")}</span>` : ""}<h2>${esc(title)}</h2>${!c && editable && options.length && !folded ? `<button class="cp-link cp-quiet-link" id="change-action" aria-expanded="${Boolean(S.changing)}">${T("change", "ändern")}</button>` : ""}</header>
    ${S.changing && !c ? `<div class="cp-change-panel">${S.pickAction ? `<span class="cp-muted">${T(`Instead: ${esc(S.pickAction.title)}, because`, `Stattdessen: ${esc(S.pickAction.title)}, weil`)}</span>${reasonChips("data-action-reason", ["1", "2", "5", "6"])}`
      : options.map((o) => `<button class="cp-chip" data-pick-action="${raw(o.kind)}">${esc(o.title)}${o.has_draft ? "" : T(" (no draft)", " (kein Entwurf)")}</button>`).join("")}</div>` : ""}
    ${restLine}${resting ? reconcileLine() : ""}`;
  if (folded) return `${head}<footer class="cp-bar cp-carry">${whenAfter || when}<span class="grow"></span>${onward}</footer></section>`;
  return `${head}
    ${c ? "" : `${resting ? "" : weilLine(act)}${resting ? "" : partialLine(act)}${resting ? "" : headBlock()}${leadLine(sc.lead)}${resting ? "" : decisionsStrip(dec, decisionPrimary)}${dec ? "" : progressLine(sc.progress)}${resting ? "" : changesStrip()}`}${tabs}
    ${stale && text ? `<p class="cp-stale-note">${T("Draft from before the new files", "Entwurf vor den neuen Dateien")} <button class="cp-link cp-quiet-link" id="use-anyway" type="button">${T("use anyway", "trotzdem verwenden")}</button></p>` : ""}
    ${c || asFrozen ? "" : conflictsView(active)}
    ${c || asFrozen ? "" : otherReferenceNote()}${text ? letterLangNote() : ""}
    ${asFrozen || c || !text ? "" : handoverLine()}
    <div class="cp-letter ${stale ? "cp-stale" : ""}" data-item="letter:0" data-doc="${raw((active || {}).kind || "")}" ${editable && text ? 'data-letter-edit="1"' : ""} ${sc.missing !== undefined ? `data-missing="${sc.missing}"` : ""}>${body}${required}</div>
    <footer class="cp-bar ${asFrozen || c ? "" : "cp-carry"} ${barChanged(c ? "closed" : resting ? "rest" : barKind || "")}">${bar}</footer>
  </section>`;
}
// A document that goes with the letter (a template for the customer, the cost guarantee, the summary for the firm …):
// its settings (the guarantee's scope and an amount only the handler enters) above it, its text editable on a click.
function alsoView(doc, editable) {
  const a = ((S.data.draft || {}).also || []).find((x) => x.kind === doc.kind) || {};
  const control = (key) => {
    const f = item("fact", key) || {}, now = f.value === null || f.value === undefined ? "" : String(f.value);
    return (f.values || []).length
      ? `<label class="cp-muted">${esc(plainQuestion((f.label || {}).de).replace(/\s*\(.*$/, ""))} <select class="cp-cover-select${now ? "" : " cp-unset"}" data-also-set="${raw(key)}">${now ? "" : `<option value="" selected disabled>${T("please choose", "bitte wählen")}</option>`}${f.values.map((v) => `<option ${v === now ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></label>`
      : `<label class="cp-muted">${T("Amount (optional)", "Betrag (freiwillig)")} CHF <input class="cp-cover-select" size="9" data-also-set="${raw(key)}" value="${raw(now)}" placeholder="${T("none", "keiner")}"></label>`;
  };
  return `${editable && (a.set || []).length ? `<p class="cp-also-set">${a.set.map(control).join(" ")}</p>` : ""}
    <div class="cp-text cp-also-text" data-seg="also" data-also-text="${raw(doc.kind)}" ${readingLetter() ? 'data-reading="1"' : editable ? `data-editable="1" tabindex="0" role="textbox" aria-multiline="true" aria-label="${esc(doc.title)}"` : ""}>${letterBlock(docText(doc))}</div>`;
}
// The letter's lines are its checklist: a tick is a request, unticking takes the line out at once. A line shows no tag:
// its reason (why, how often practice asks, the article's passage, its source) opens from the line, by click or keyboard.
// Offered lines wait folded under «Weitere Vorschläge»; the text around is the letter, editable on a click.
function letterLines() {
  const docs = (S.data.items || []).filter((i) => i.kind === "document" && i.ask && i.status !== "present" && !i.part_of);
  const qs = (S.data.items || []).filter((i) => i.kind === "letter_question" || i.kind === "hint");
  const lines = ((S.data || {}).caseEvents || []).filter((e) => e.kind === "letter.line").reduce((m, e) => { m[e.item_id] = e.included; return m; }, {});
  const proposal = (i) => i.ask === "later" || i.ask === "proposed" || (i.kind === "hint" && i.stated_as === "put_to_handler");
  const on = (i) => (proposal(i) ? lines[i.item_id] === true : lines[i.item_id] !== false);
  return { all: docs.concat(qs), on };
}
// The articles a line comes from, with their verbatim passages.
function lawOf(i) {
  const proc = S.data.process || {}, law = proc.law || {};
  const def = i.kind === "document" ? (proc.documents || []).find((d) => d.id === i.key)
    : i.kind === "letter_question" ? (proc.facts || []).find((f) => f.id === i.key) : i.kind === "hint" ? (proc.hints || []).find((h) => h.id === i.key) : null;
  return ((def || {}).source_refs || []).map((r) => r.match(/^law#(.+)$/)).filter((m) => m && law[m[1]]).map((m) => law[m[1]]);
}
function practiceCount(i) {
  const pd = ((S.data.process || {}).documents || []).find((d) => d.id === i.key) || {};
  const m = (pd.source_refs || []).map((r) => r.match(/^practice#(\d+)of(\d+)$/)).find(Boolean);
  return m ? T(`asked in ${m[1]} of ${m[2]} cases`, `in ${m[1]} von ${m[2]} Fällen verlangt`) : null;
}
const whyId = (i) => `why-${String(i.item_id).replace(/[^a-z0-9_-]/gi, "_")}`;
function lineWhy(i) {
  const pd = i.kind === "document" ? ((S.data.process || {}).documents || []).find((d) => d.id === i.key) || {} : {};
  const why = i.kind === "document" ? pd.why : i.kind === "letter_question" ? T("only the customer knows it", "nur die Kundschaft weiss es") : "";
  const practice = i.practice || (pd.knowledge ? practiceNote(pd.knowledge) : practiceCount(i));
  const when = i.ask === "later" ? T("later, if needed", "später, falls nötig") : i.ask === "proposed" ? (i.reason || T("for this case", "für diesen Fall")) : "";
  const src = (i.evidence || []).find((e) => e.file);
  return `<div class="cp-why" id="${whyId(i)}">${[why, practice, when].filter(Boolean).map(esc).join(" · ")}${passages(lawOf(i))}${sourceChip(src)}</div>`;
}
function letterView(text, editable) {
  const { all, on } = letterLines();
  const label = (i) => (i.kind === "document" ? (i.label || {}).de : i.value) || "";
  const pending = all.filter(on);
  const segs = [];  // {text} or {row: item, line}
  for (const raw of text.split("\n")) {
    const match = pending.filter((i) => (i.kind === "hint" ? raw.startsWith(label(i)) : raw.startsWith(`– ${label(i)}`))).sort((a, b) => label(b).length - label(a).length)[0];
    if (match) { pending.splice(pending.indexOf(match), 1); segs.push({ row: match, line: raw }); }
    else if (segs.length && "text" in segs[segs.length - 1]) segs[segs.length - 1].text += `\n${raw}`;
    else segs.push({ text: raw });
  }
  const offered = all.filter((i) => !on(i));
  const lastRow = segs.map((s) => Boolean(s.row)).lastIndexOf(true);
  const row = (i, line, extra = false) => {
    const shown = !extra ? line.replace(/^– /, "") : i.kind === "letter_question" ? `${T("Question", "Frage")}: ${i.value}` : i.kind === "hint" ? `${T("Hint", "Hinweis")}: ${i.value}` : label(i);
    return `<li class="cp-line ${extra ? "cp-offered" : ""} ${S.why === i.item_id ? "open" : ""}" data-item="${raw(i.item_id)}" data-text="${raw(line)}">
      <input type="checkbox" data-line="${raw(i.item_id)}" ${on(i) ? "checked" : ""} ${editable ? "" : "disabled"} aria-label="${esc(shown)}" aria-describedby="${whyId(i)}">
      <span class="cp-line-text" data-why="${raw(i.item_id)}">${esc(shown)}</span>${lineWhy(i)}
      ${S.askWhy === i.item_id ? `<div class="cp-why-row"><span class="cp-muted">${T("Left out of this letter. Not needed at all?", "In diesem Brief weggelassen. Gar nicht nötig?")}</span><span class="cp-reasons">
        <button class="cp-chip" data-line-reason="3">${T("not in this case", "in diesem Fall nicht")}</button><button class="cp-chip" data-line-reason="4">${T("never in such cases", "in solchen Fällen nie")}</button></span></div>` : ""}</li>`;
  };
  const extra = editable ? `${offered.length ? `<li class="cp-offers"><details ${S.askWhy || S.openOffers ? "open" : ""}><summary class="cp-link">${T("More suggestions", "Weitere Vorschläge")} · ${offered.length}</summary><ul>
      ${offered.map((i) => row(i, i.kind === "document" ? `– ${label(i)}` : i.value, true)).join("")}</ul></details></li>` : ""}
    <li class="cp-add">${icon("plus")}<input id="add-doc" maxlength="200" placeholder="${T("Add a document", "Unterlage hinzufügen")}" aria-label="${T("Add a document", "Unterlage hinzufügen")}">
      ${S.addedDoc && S.addedDoc.case === S.route.id ? `<span class="cp-added" role="status">${S.addedDoc.said ? esc(S.addedDoc.said)
        : `${T(`“${esc(S.addedDoc.title)}” is requested.`, `«${esc(S.addedDoc.title)}» wird verlangt.`)} <button class="cp-chip" type="button" data-add-general="${raw(S.addedDoc.edit)}">${T("always in such cases", "in solchen Fällen immer")}</button>`}</span>` : ""}</li>` : "";
  let n = 0, html = "", list = [];
  const flush = (more = "") => { if (list.length || more) html += `<ul class="cp-checklist" data-seg="list">${list.join("")}${more}</ul>`; list = []; };
  segs.forEach((s, k) => {
    if (s.row) { list.push(row(s.row, s.line)); if (k === lastRow) flush(extra); return; }
    flush();
    const shown = (S.blockEdits || {})[s.text] ?? s.text;
    html += `<div class="cp-text" data-seg="text" data-orig="${raw(s.text)}" ${readingLetter() ? 'data-reading="1"' : editable ? `data-editable="1" tabindex="0" role="textbox" aria-multiline="true" aria-label="${T("Letter text", "Brieftext")}"` : ""} data-block="${n += 1}">${letterBlock(shown)}</div>`;
  });
  // «Weitere Vorschläge» and «Unterlage hinzufügen» stand where the letter lists what it asks for (a request, a reminder):
  // a letter that asks for nothing line by line (an assessment, a status inquiry) would not carry what is added there
  const asksByLine = /^(A1|A2|A3|request)$/.test(String((S.data.draft || {}).form || "")) || /^(A1|A2|A3|request)$/.test(String((S.data.draft || {}).kind || ""));
  flush(lastRow < 0 && asksByLine ? extra : "");
  return html;
}
// The letter as it will be sent: the edited text blocks and the ticked lines, in order.
function letterText() {
  return [...document.querySelectorAll("[data-item='letter:0'] [data-seg]")].map((el) => el.dataset.seg === "list"
    ? [...el.querySelectorAll(":scope > li[data-text]")].filter((li) => (li.querySelector("input[data-line]") || {}).checked !== false).map((li) => li.dataset.text).join("\n")
    : el.dataset.reading ? ((S.blockEdits || {})[el.dataset.orig] ?? el.dataset.orig)  // shown translated: the letter is its original
    : el.innerText.replace(/\n$/, "")).join("\n");
}
// ---------- «Der Fall»: what the case is, what is open with whom, by when; nothing the card head says, no decision ----------
function partiesHtml() {
  const brief = (result() || {}).brief || {};
  const role = (text) => String(text || "").replace(/\s*\((VN|GP)\)/g, "");
  return (S.data.items || []).filter((i) => i.kind === "party").map((p) => `${redacted(p.value) ? `<i>${T("name redacted", "Name geschwärzt")}</i>` : esc(p.value)} <span class="cp-muted">· ${esc(role(T(p.label.en, p.label.de)))}</span>`).join("<br>")
    || (brief.parties || []).map((p) => `${esc(p.name)} <span class="cp-muted">· ${esc(String(p.role || "").replace(/\s*\((VN|GP)\)/g, ""))}</span>`).join("<br>");
}
// «Der Fall» is built from parts, each one slice's, so each changes its own: the request (sideAnliegen), the customer's
// questions (sideQuestions), «Als Nächstes» from the account (sideAccount), the line after a correction with its undo
// (sideChangeLine) and what changed with the last preparation (sideChanges).
function sideAnliegen() {
  const r = result() || {}, brief = r.brief || {}, items = S.data.items || [];
  const summary = items.find((i) => i.kind === "summary" && i.value);
  const anliegen = (summary && summary.value) || brief.request || "";  // never the result checker's answer (C6: after an update it is inherited)
  const long = anliegen.length > 95;  // about two lines: more opens on a click
  return `<dt>${T("Request", "Anliegen")}</dt><dd data-item="summary:0">${long ? `<button class="cp-anliegen ${S.anliegenOpen ? "open" : ""}" id="anliegen-open" aria-expanded="${Boolean(S.anliegenOpen)}">${esc(anliegen)}</button>` : esc(anliegen) || "—"}</dd>`;
}
function sideQuestions() {
  const b = brief();
  if (b && (b.assessment || b.follow_on) && (b.questions || []).length) return briefSide(b);  // an assessment's questions, the facts that decide it, what is still asked
  const asks = (S.data.items || []).filter((i) => i.kind === "customer_question" && i.value);
  return asks.length ? `<dt>${T("Questions", "Fragen")}</dt><dd class="cp-asks">${asks.map((q) => `<div data-item="${raw(q.item_id)}">«${esc(q.value)}»</div>`).join("")}</dd>` : "";
}
function sideAccount() {
  const sc = scr();
  const stand = sc.stand || [];  // the account's lines as the server words them for this screen (screen.account_lines)
  const stageLines = sc.lines || [];  // the stage's short lines, without what the card head states (screen.py)
  const next = stand.map((l) => !l.rows ? `<div class="cp-acct-line ${l.open ? "open" : ""}" data-item="${raw(l.item_id)}"><span class="cp-acct-label">${esc((l.label || {}).de || "")}</span> ${esc(l.value || "")}${sourceChips(l.evidence)}${handlerTag(l.handler)}</div>`
    : `<div class="cp-acct-line open" data-item="${raw(l.item_id)}"><span class="cp-acct-label">${esc((l.label || {}).de || "")}</span>${l.rows.map((x) => `<div class="cp-acct-item">${esc(x.text)}${sourceChips(x.evidence)}${handlerTag(x.handler)}${settleButtons(x)}</div>`).join("")}${l.more ? `<button class="cp-link cp-quiet-link" data-open-party="${raw(l.party)}">… ${l.more} ${T("more", "weitere")}</button>` : ""}</div>`)
    .concat(stageLines.map((l) => `<div class="cp-acct-line" data-item="${raw(l.item_id)}">${esc(l.value || "")}${sourceChips(l.evidence)}</div>`)).join("");
  return next ? `<dt>${T("Open", "Offen")}</dt><dd><div class="cp-acct">${next}</div></dd>` : "";
}
// After a correction: what changed in the prepared package, before and after, with its basis, and its undo; after an undo,
// what came back and what an undo cannot reach. Otherwise, after an update, how the reply was matched (C7), unless the
// card head (Slice B) already says it.
// The reader's own changes to this step, above the letter they change: the change just made with what it moved (step,
// letter, documents: before and after) and its undo; under it every earlier change still in force since the last
// dispatch, each taken back where it stands. It is read from the case's own log, so it is there again after a reload.
function lastChange() {
  if (S.lastUndo && S.lastUndo.case === S.route.id && !S.lastEdit) return consequencesBlock(S.lastUndo.consequences, T("Undone", "Rückgängig gemacht"), "", S.lastUndo.limits);
  // a decision of the step stands in the decisions' own row, with its «ändern»: no second box for it
  const decided = new Set((completionOf().decided || []).map((d) => d.edit).filter(Boolean));
  if (S.lastEdit && !S.lastEdit.op && !(S.lastEdit.edit && decided.has(S.lastEdit.edit.id))) {
    const undo = `<button class="cp-link" id="undo">${T("Undo", "Rückgängig")}</button>`;
    // what the correction teaches, said where it was made: proposed for similar cases (a reviewer releases it), or only here
    const k = S.lastEdit.knowledge;
    const taught = k ? `<p class="cp-change cp-taught">${T("Proposed for similar cases", "Für ähnliche Fälle vorgeschlagen")}${(k.replay || {}).because === "wiederholt" ? T(" (made in several cases)", " (in mehreren Fällen so korrigiert)") : ""}: ${T("a reviewer releases it under Knowledge; until then it changes no other case.", "freigegeben wird es unter «Wissen»; bis dahin ändert es keinen anderen Fall.")}</p>`
      : S.lastEdit.only_here ? `<p class="cp-change cp-taught">${esc(S.lastEdit.only_here)}</p>` : "";
    // a decision just taken is said in one quiet line with its way back; the long account of a correction is for corrections
    const e = S.lastEdit.edit || {}, plain = e.op === "set_fact" && e.args && !taught;
    if (plain) return `<p class="cp-change cp-change-short">${T("Decided", "Entschieden")}: ${esc(e.args.fact === "deckung" ? T("cover", "Deckung") : shortFact(e.args.fact))} <b>${esc(plainValue(e.args.value))}</b> ${undo}</p>`;
    return (S.lastEdit.consequences ? consequencesBlock(S.lastEdit.consequences, T("Changed", "Geändert"), undo)
      : `<p class="cp-change">${esc(changeLine(S.lastEdit.diff))} ${undo}</p>`) + taught;
  }
  return "";
}
function changesStrip() {
  const st = completionOf(), edits = S.data.edits || [];
  if (studyCopy() || closed()) return "";
  // this step: since CasePath last prepared the case and since the last letter went out (a dispatch is no change of the reader's)
  const sent = new Set(edits.filter((e) => e.op === "add_dispatch").map((e) => e.id));
  const cut = [...edits.filter((e) => sent.has(e.id)).map((e) => String(e.at || "")), String((S.data.prepared_run || {}).created_at || "")].sort().pop() || "";
  const shown = new Set([...(st.decided || []).map((d) => d.edit), S.lastEdit && S.lastEdit.edit && S.lastEdit.edit.id].filter(Boolean));
  const rows = (S.data.verlauf || []).filter((r) => r.kind === "gesture" && r.undo && !shown.has(r.undo) && !sent.has(r.undo) && String(r.at || "") > cut);
  const last = lastChange();
  if (!rows.length && !last) return "";
  const list = rows.slice(-4).reverse().map((r) => `<li data-change="${raw(r.undo)}"><span>${esc(clip(r.what, 110))}</span> <button class="cp-link cp-quiet-link" type="button" data-change-undo="${raw(r.undo)}">${T("undo", "rückgängig")}</button></li>`).join("");
  const more = rows.length > 4 ? `<li class="cp-muted"><a class="cp-quiet-link" href="#/case/${raw(S.route.id)}/history">${T(`and ${rows.length - 4} earlier`, `und ${rows.length - 4} frühere`)}</a></li>` : "";
  return `<div class="cp-changes${last ? enter(`chg:${(S.lastEdit && S.lastEdit.edit && S.lastEdit.edit.id) || (S.lastUndo && "undo")}`) : ""}" data-changes>${last}${rows.length ? `<p class="cp-changes-head">${T("Your changes to this step", "Ihre Änderungen an diesem Schritt")} · ${rows.length}</p><ul>${list}${more}</ul>` : ""}</div>`;
}
function sideChangeLine() {
  const ch = S.data.changes || {}, sc = scr();
  if (running() || !(ch.ledger || []).length || (sc.head && (sc.head.changed || sc.head.lines))) return "";
  return `<div class="cp-change cp-ledger"><b>${T("Updated", "Aktualisiert")}${ch.updated_at ? ` ${T("on", "am")} ${dateText(ch.updated_at)}` : ""}</b>
    <ul>${ch.ledger.map((line) => `<li class="${/prüfen|abgelehnt|teilweise|nicht eingegangen/.test(line) ? "check" : ""}">${esc(line)}</li>`).join("")}</ul></div>`;
}
function consequencesBlock(c, head, undo, limits) {
  const rows = (c && c.changes) || [];
  const side = (v) => Array.isArray(v) ? v.map((x) => esc(clip(x, 140))).join("<br>") || "—" : esc(clip(v == null ? "—" : String(v), 140));
  const why = c && c.basis ? ` · ${c.undone ? T("taken back", "zurückgenommen") : T("because", "weil")}: ${esc(c.basis)}` : "";
  return `<div class="cp-change cp-consequences" aria-live="polite"><p><b>${head}</b>${why} ${undo}</p>
    ${rows.length ? `<dl>${rows.map((r) => `<dt>${esc(r.what)}</dt><dd>${r.same ? `<span class="cp-muted">${T("follows (as above)", "folgt (wie oben)")}</span>`
      : `<div class="cp-chg-was">${side(r.before)}</div><div class="cp-chg-now">${side(r.after)}</div>`}</dd>`).join("")}</dl>`
      : `<p class="cp-muted">${T("Nothing else in the package changed", "Sonst änderte sich nichts am Paket")}</p>`}
    ${(limits || []).length ? `<p class="cp-limits"><b>${T("Not undone", "Nicht rückgängig")}</b>: ${limits.map(esc).join("; ")}</p>` : ""}</div>`;
}
function studyCopy() { return Boolean((((S.data || {}).case || {}).intake || {}).study); }
// «erledigt» and «nicht mehr nötig» on an open request of the account (C9): kept and undone like every correction
function settleButtons(x) {
  if (!x || !x.request || studyCopy() || running()) return "";
  return ` <span class="cp-settle"><button class="cp-link cp-quiet-link" data-settle="${raw(x.request)}" data-how="erledigt">${T("done", "erledigt")}</button>
    · <button class="cp-link cp-quiet-link" data-settle="${raw(x.request)}" data-how="nicht_mehr_noetig">${T("no longer needed", "nicht mehr nötig")}</button></span>`;
}
function sideChanges() {
  return "";  // what changed with the last preparation stands in the card head now (headBlock: «Was sich geändert hat»)
}
// «Der Fall» is read in lines: a section with more than a line or two folds to its name, how many entries it has and
// how it begins, and opens on a click (kept while the reader stays on the case). Deadlines never fold.
const SIDE_OPEN = new Set(["Fristen", "Deadlines", "Achtung", "Note", "Nicht gelesen", "Unread"]);
function foldSide() {
  const dl = $(".cp-casefacts");
  if (!dl) return;
  const open = S.sideOpen || (S.sideOpen = {});
  for (const dt of [...dl.querySelectorAll(":scope > dt")]) {
    const dd = dt.nextElementSibling;
    if (!dd || dd.tagName !== "DD") continue;
    const key = dt.textContent.trim(), rows = dd.children.length, text = dd.innerText.replace(/\s+/g, " ").trim();
    if (SIDE_OPEN.has(key) || (rows < 2 && text.length < 110)) continue;
    const isOpen = Boolean(open[key]);
    dt.innerHTML = `<button class="cp-fold" type="button" aria-expanded="${isOpen}">${esc(key)}${rows > 1 ? `<span class="cp-fold-n">${rows}</span>` : ""}</button>`;
    const toggle = () => { open[key] = !isOpen; renderCase(); };
    dt.querySelector("button").addEventListener("click", toggle);
    if (isOpen) continue;
    dd.hidden = true;
    const first = document.createElement("dd");
    first.className = "cp-fold-first"; first.textContent = clip(text.replace(/ (Quelle|ändern|neu|bedingt|beantwortet|S\. \d+)(?= |$)/g, ""), 64);
    first.addEventListener("click", toggle);
    dd.after(first);
  }
}
function sideView() {
  const sc = scr();
  const fristen = (sc.fristen || []).map((d) => `<div class="cp-frist ${quiet() ? "" : d.late ? "late" : d.soon ? "soon" : ""}" data-item="${raw(d.item_id)}" title="${esc([d.basis, d.rule].filter(Boolean).join(" · "))}">${d.condition ? `<span class="cp-muted">${esc(d.condition)}:</span> ` : ""}<b>${esc(d.date || d.state)}</b> · ${esc(d.title)}${d.date ? ` <span class="cp-muted">· ${esc(d.state)}</span>` : ""}${d.who ? ` <span class="cp-muted">· ${esc(d.who)}</span>` : ""}${(d.pair || []).length ? `<br><span class="cp-muted">${d.pair.map(esc).join(" · ")}</span>` : ""}${sourceChip(d.source)}</div>`).join("");
  const docs = sc.missing && !sc.missing_in_letter && !xOn() ? `<dt>${T("Documents", "Unterlagen")}</dt><dd><a class="cp-link cp-quiet-link" href="#/case/${raw(S.route.id)}/document_finder">${T(`${sc.missing} missing`, `${sc.missing} fehl${sc.missing === 1 ? "t" : "en"}`)}</a></dd>` : "";
  const points = (sc.points || []).map((p) => `<div class="cp-point-line ${p.open ? "open" : ""}" data-item="${raw(p.item_id)}"><button class="cp-link cp-point-text" data-key-point="${raw(String(p.item_id).replace(/^key_point:/, ""))}" aria-expanded="${S.keyPoint === String(p.item_id).replace(/^key_point:/, "")}">${esc(p.text)}</button> <span class="cp-muted">· ${esc(p.basis || "")}</span>
      ${S.keyPoint === String(p.item_id).replace(/^key_point:/, "") ? `<div class="cp-passage">${passages(p.law)}${p.follows ? `<div>${T("Follows", "Folge")}: ${esc(p.follows)}</div>` : ""}${p.check ? `<div>${T("To check", "Zu prüfen")}: ${esc(p.check)}</div>` : ""}</div>` : ""}</div>`).join("");
  const flagged = (S.data.files || []).filter((f) => ((f.extraction || {}).instruction_like || []).length);
  const unread = (S.data.files || []).filter((f) => Object.keys((f.extraction || {}).unread_reasons || {}).length);
  const cover = sc.cover && (sc.decision || {}).key !== "deckung" ? sc.cover : null;
  return `<aside class="cp-side">
    <section class="cp-card cp-case"><h3>${T("The case", "Der Fall")}</h3>
      <dl class="cp-casefacts">
        ${sideAnliegen()}
        ${sideQuestions()}
        <dt>${T("Parties", "Parteien")}</dt><dd data-item="party:0">${partiesHtml() || "—"}</dd>
        ${sideAccount()}
        ${docs}
        ${S.data.screen && (fristen || !sc.fristen_elsewhere) && !(xOn() && (sc.fristen || []).length) ? `<dt>${T("Deadlines", "Fristen")}</dt><dd>${fristen || `<span class="cp-muted">${T("none in the file", "keine in der Akte")}</span>`}</dd>` : ""}
        ${cover && !xOn() ? `<dt>${T("Cover", "Deckung")}</dt><dd data-item="cover:summary" class="cp-cover-state ${raw(cover.state)}">${esc(cover.text)}</dd>` : ""}
        ${points ? `<dt>${T("Law", "Rechtliches")}</dt><dd>${points}</dd>` : ""}
        ${flagged.length ? `<dt>${T("Note", "Achtung")}</dt><dd>${flagged.map((f) => esc(f.name)).join(", ")} ${T("contains text addressed to an AI; not followed", "enthält Text an die KI; nicht befolgt")}</dd>` : ""}
        ${unread.length ? `<dt>${T("Unread", "Nicht gelesen")}</dt><dd>${unread.map((f) => `${esc(f.name)}: ${Object.keys(f.extraction.unread_reasons).length} ${T("page(s)", "Seite(n)")}`).join("<br>")}</dd>` : ""}
      </dl>
      <p class="cp-case-tools">${S.data.file_note ? `<button class="cp-button cp-small" id="copy-note">${S.noteCopied ? T("File note copied", "Aktennotiz kopiert") : T("Copy file note", "Aktennotiz kopieren")}</button>` : ""}
        <button class="cp-link cp-quiet-link" id="add-note" aria-expanded="${Boolean(S.noting)}">${T("Add note", "Notiz hinzufügen")}</button></p>
      ${S.noting && !S.entryEdit && !S.noteShown ? entryForm() : ""}
      ${sideChangeLine()}
      ${sideChanges()}
    </section></aside>`;
}

// ---------- the handler's own entry: a call, a conversation, a note, an e-mail outside the file ----------
// One compact card: what kind, with whom (a name if wanted), the day (today), what was said; and, each behind one tap, one
// row of what was agreed, what was asked and the next step. It is an entry of the account and counts at once.
const PARTY_DE = { kunde: "Kundschaft", versicherer: HOUSE.name, kanzlei: "Kanzlei", gegenpartei: "Gegenpartei", behoerde: "Gericht/Behörde", andere: "Andere" };
const ENTRY_KINDS = lazy(() => ([["telefon", T("Phone", "Telefon")], ["gespraech", T("Conversation", "Gespräch")], ["notiz", T("Note", "Notiz")],
  ["email", T("E-mail outside the file", "E-Mail ausserhalb der Akte")]]));
const ENTRY_PARTIES = lazy(() => ([["kunde", T("customer", "Kundschaft")], ["gegenpartei", T("other side", "Gegenpartei")], ["kanzlei", T("law firm", "Kanzlei")],
  ["behoerde", T("authority", "Behörde")], ["andere", T("other", "andere")]]));
const ENTRY_PARTS = lazy(() => ({ agreed: T("Agreed", "Vereinbart"), asked: T("Asked", "Verlangt"), next: T("Next step", "Nächster Schritt") }));
function entryForm() {
  const d = S.entryDraft || {}, party = d.party || "kunde";
  const part = (k) => d[k] || {};
  const shown = (k) => Boolean((d.open || {})[k] || Object.values(part(k)).some(Boolean));
  const options = (rows, now, blank) => (blank ? `<option value="">${esc(blank)}</option>` : "") + rows.map(([k, label]) => `<option value="${k}" ${k === now ? "selected" : ""}>${esc(label)}</option>`).join("");
  const whom = (now, blank) => options(ENTRY_PARTIES().concat([["versicherer", T(`us (${HOUSE.name})`, `wir (${HOUSE.name})`)]]), now, blank);
  const input = (name, value, attrs) => `<input name="${name}" value="${raw(value || "")}" ${attrs}>`;
  const row = (k, body) => `<div class="cp-entry-part" data-part="${k}" ${shown(k) ? "" : "hidden"}><span class="cp-entry-part-label">${ENTRY_PARTS()[k]}</span>${body}</div>`;
  return `<form class="cp-entry-form" id="note-form" ${S.entryEdit ? `data-edit="${raw(S.entryEdit)}"` : ""} novalidate>
    <div class="cp-entry-kinds" role="radiogroup" aria-label="${T("Kind of entry", "Art des Eintrags")}">${ENTRY_KINDS().map(([k, label]) =>
      `<label class="cp-entry-kind"><input type="radio" name="kind" value="${k}" ${k === (d.kind || "telefon") ? "checked" : ""}><span>${esc(label)}</span></label>`).join("")}</div>
    <div class="cp-entry-row"><label>${T("with", "mit")} <select name="party">${options(ENTRY_PARTIES(), party)}</select></label>
      ${input("name", d.name, `maxlength="120" placeholder="${T("name (optional)", "Name (freiwillig)")}" aria-label="Name" class="cp-entry-name"`)}
      <label>${T("on", "am")} <input type="date" name="date" value="${raw(d.date || isoToday())}" aria-label="${T("Date", "Datum")}"></label></div>
    <textarea name="said" rows="3" maxlength="2000" placeholder="${T("What was said", "Was besprochen wurde")}" aria-label="${T("What was said", "Was besprochen wurde")}">${raw(d.said || "")}</textarea>
    ${row("agreed", `${input("agreed_what", part("agreed").what, `maxlength="120" placeholder="${T("what", "was")}" aria-label="${T("agreed: what", "vereinbart: was")}"`)}
      ${input("agreed_amount", part("agreed").amount, `maxlength="40" placeholder="CHF" size="8" aria-label="${T("amount", "Betrag")}"`)}
      <select name="agreed_payer" aria-label="${T("who pays", "wer zahlt")}">${options([["gegenpartei", T("other side pays", "Gegenpartei zahlt")], ["kunde", T("customer pays", "Kundschaft zahlt")],
        ["versicherer", T("we pay", `${HOUSE.name} zahlt`)], ["kanzlei", T("firm pays", "Kanzlei zahlt")], ["andere", T("others pay", "andere zahlen")]], part("agreed").payer || (party === "gegenpartei" ? "gegenpartei" : ""), T("who pays", "wer zahlt"))}</select>
      <label>${T("by", "bis")} <input type="date" name="agreed_by" value="${raw(part("agreed").by || "")}"></label>`)}
    ${row("asked", `${input("asked_what", part("asked").what, `maxlength="120" placeholder="${T("what", "was")}" aria-label="${T("asked: what", "verlangt: was")}"`)}
      <select name="asked_of" aria-label="${T("of whom", "von wem")}">${options(ENTRY_PARTIES(), part("asked").of || party)}</select>
      <label>${T("by", "bis")} <input type="date" name="asked_by" value="${raw(part("asked").by || "")}"></label>`)}
    ${row("next", `${input("next_what", part("next").what, `maxlength="120" placeholder="${T("what", "was")}" aria-label="${T("next step: what", "nächster Schritt: was")}"`)}
      <label>${T("by", "bis")} <input type="date" name="next_by" value="${raw(part("next").by || "")}"></label>
      <select name="next_who" aria-label="${T("who", "wer")}">${whom(part("next").who || party)}</select>`)}
    <p class="cp-entry-adds">${Object.keys(ENTRY_PARTS()).filter((k) => !shown(k)).map((k) => `<button type="button" class="cp-link cp-quiet-link" data-entry-part="${k}">+ ${ENTRY_PARTS()[k]}</button>`).join("")}</p>
    ${S.entryError ? `<p class="cp-error">${esc(S.entryError)}</p>` : ""}
    <span class="cp-entry-actions"><button class="cp-button cp-small">${S.entryEdit ? T("Save change", "Änderung speichern") : T("Save", "Speichern")}</button>
      <button type="button" class="cp-link cp-quiet-link" id="note-cancel">${T("cancel", "abbrechen")}</button></span></form>`;
}
// What the form holds, as the draft (kept across a redraw) and as the entry it sends: a part counts only when filled.
function entryDraftOf(form) {
  const v = (n) => ((form.elements[n] || {}).value || "").trim();
  const open = Object.fromEntries([...form.querySelectorAll("[data-part]")].map((el) => [el.dataset.part, !el.hidden]));
  return { kind: (form.querySelector("input[name=kind]:checked") || {}).value || "telefon", party: v("party"), name: v("name"), date: v("date"), said: v("said"), open,
           agreed: { what: v("agreed_what"), amount: v("agreed_amount"), payer: v("agreed_payer"), by: v("agreed_by") },
           asked: { what: v("asked_what"), of: v("asked_of"), by: v("asked_by") }, next: { what: v("next_what"), by: v("next_by"), who: v("next_who") } };
}
function entryBody(d) {
  const filled = (row, keys) => (keys.some((k) => row[k]) ? Object.fromEntries(Object.entries(row).filter(([, x]) => x)) : null);
  return { kind: d.kind, party: d.party || "kunde", name: d.name || "", date: d.date || isoToday(), said: d.said || "",
           agreed: d.open.agreed ? filled(d.agreed, ["what", "amount"]) : null, asked: d.open.asked ? filled(d.asked, ["what"]) : null,
           next: d.open.next ? filled(d.next, ["what"]) : null };
}
const REASONS = { "1": "Steht anders in den Akten", "2": "Steht nicht in den Akten", "3": "Hier nicht relevant", "4": "Gilt generell so",
  "5": "Weiss ich von ausserhalb der Akten", "6": "Formulierung", none: "ohne Angabe" };
const REASONS_EN = { "1": "The files say otherwise", "2": "Not in the files", "3": "Not relevant here", "4": "Generally so",
  "5": "I know from outside the files", "6": "Wording", none: "No reason" };
async function caseEvent(kind, itemId, fields) {
  return api(`/api/cases/${S.route.id}/events`, { method: "POST", body: JSON.stringify({ kind, item_id: itemId, fields: fields || {} }) });
}
async function sha256(text) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
}
function changeLine(diff) {
  // One line where the change was made: what moved in the process and the checklist.
  if (!diff) return T("Changed", "Geändert");
  const parts = [];
  const steps = Object.fromEntries((S.data.process.steps || []).map((x) => [x.id, x.title]));
  const end = (S.data.evaluation && S.data.evaluation.outcome || {}).title;
  const to = (id) => steps[id] || (end ? T(`end: ${end}`, `Abschluss: ${end}`) : "—");
  if (diff.current_step && diff.current_step.before !== diff.current_step.after) parts.push(`${T("Step", "Schritt")}: ${steps[diff.current_step.before] || "—"} → ${to(diff.current_step.after)}`);
  else if (diff.outcome && diff.outcome.before !== diff.outcome.after) parts.push(diff.outcome.after ? T(`end: ${end || diff.outcome.after}`, `Abschluss: ${end || diff.outcome.after}`) : T("open again", "wieder offen"));
  if (diff.documents_added.length) parts.push(T(`${diff.documents_added.length} document(s) now needed`, `${diff.documents_added.length} Unterlage(n) jetzt nötig`));
  if (diff.documents_removed.length) parts.push(T(`${diff.documents_removed.length} document(s) no longer needed`, `${diff.documents_removed.length} Unterlage(n) nicht mehr nötig`));
  if (diff.documents_changed.length) parts.push(T(`${diff.documents_changed.length} document(s) changed`, `${diff.documents_changed.length} Unterlage(n) geändert`));
  // a decision that moves nothing else is said as that, not as a change with an empty list
  return parts.length ? `${T("Changed", "Geändert")}: ${parts.join("; ")}` : T("Saved. Nothing else in the process moved.", "Gespeichert. Am Prozess hat sich sonst nichts verschoben.");
}
const EXPOSURE = { observer: null, since: {}, view: null };
function flushExposure(key, el) {
  const start = EXPOSURE.since[key];
  if (start === undefined) return;
  delete EXPOSURE.since[key];
  const item = key.split("|")[1];
  if (/^[a-z_]+:./.test(item) && S.route.id) caseEvent("item.exposed", item, { from_ms: start, to_ms: Math.round(performance.now()), view: EXPOSURE.view }).catch(() => {});
}
function watchExposure(view) {
  // Which items were on screen and for how long, for "seen and kept" versus "not seen". Raw intervals; no mouse data.
  if (EXPOSURE.observer) { EXPOSURE.observer.disconnect(); for (const key of Object.keys(EXPOSURE.since)) flushExposure(key); }
  if (typeof IntersectionObserver === "undefined" || unaidedPending()) return;
  EXPOSURE.view = view;
  EXPOSURE.observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const key = `${view}|${entry.target.dataset.item}`;
      if (entry.isIntersecting && entry.intersectionRatio >= 0.5) EXPOSURE.since[key] = EXPOSURE.since[key] ?? Math.round(performance.now());
      else flushExposure(key);
    }
  }, { threshold: [0, 0.5] });
  for (const el of document.querySelectorAll("[data-item]")) EXPOSURE.observer.observe(el);
}
document.addEventListener("visibilitychange", () => { if (document.hidden) for (const key of Object.keys(EXPOSURE.since)) flushExposure(key); });
// The Verlauf: one table of the case in time order (the server's verlauf.rows): the report as row 1, then every document
// of the file, every entry the handler made and every gesture the handler made here, each where it happened. A handler's
// entry is marked as theirs and can be changed or removed; a change that can be undone says so. One filter: only what is open.
// A reply that answers several requests of one letter says so once («beantwortet: 5 Anforderungen aus Nr. 5»); each
// request keeps its own line at the letter that made it, where it also says whether it was answered. One open note is
// never folded.
function foldNotes(notes) {
  const groups = new Map(), out = [];
  for (const n of notes) {
    const m = !n.open && /^beantwortet: .+ \(zu Nr\. (\d+)\)$/.exec(String(n.text || ""));
    if (!m) { out.push(n); continue; }
    if (!groups.has(m[1])) { groups.set(m[1], { first: n, items: [] }); out.push(groups.get(m[1])); }
    groups.get(m[1]).items.push(n);
  }
  return out.flatMap((x) => (x.items ? (x.items.length < 3 ? x.items : [{ ...x.first, text: LANG === "de" ? `beantwortet: ${x.items.length} Anforderungen aus Nr. ${[...groups.entries()].find(([, g]) => g === x)[0]}` : `answered: ${x.items.length} requests of no. ${[...groups.entries()].find(([, g]) => g === x)[0]}` }]) : [x]));
}
// A letter that asked one party for several things, all answered in one reply, says who and where once and lists the
// things under it; a request still open, asked again or answered elsewhere keeps its own line.
function foldAsks(notes) {
  const groups = new Map(), out = [];
  for (const n of notes) {
    const m = !n.open && n.kind === "asked" && /^verlangt von (.+?): (.+) · beantwortet \(Nr\. (\d+)\)$/.exec(String(n.text || ""));
    if (!m) { out.push(n); continue; }
    const key = `${m[1]}|${m[3]}`;
    if (!groups.has(key)) { groups.set(key, { of: m[1], no: m[3], notes: [], items: [] }); out.push(groups.get(key)); }
    groups.get(key).notes.push(n); groups.get(key).items.push(m[2]);
  }
  return out.flatMap((x) => (!x.items ? [x] : x.items.length < 3 ? x.notes
    : [{ kind: "asked", open: false, items: x.items, text: LANG === "de" ? `verlangt von ${x.of} · alle ${x.items.length} beantwortet (Nr. ${x.no})` : `requested · all ${x.items.length} answered (no. ${x.no})` }]));
}
// The case's time as one band: every dated entry at its day, by who wrote (customer above the line, the insurer on it,
// everyone else below), what is open ringed. A dot under the hand names its entry and marks its row; pressed, the page
// goes to the row. Gaps show at a glance: where nothing happened for weeks, the band is empty.
function timeBand() {
  const rows = (S.data.verlauf || []).filter((r) => r.kind !== "gesture" && /^\d{4}-\d{2}-\d{2}/.test(String(r.date || "")) && (!S.onlyOpen || r.open));
  if (rows.length < 3) return "";
  const day = (v) => Date.parse(`${String(v).slice(0, 10)}T12:00:00`), t = rows.map((r) => day(r.date));
  const from = Math.min(...t), now = day(isoToday()), to = Math.max(...t, quiet() ? 0 : now);
  // the axis is the case's time with its long silences shortened: a gap of more than forty days is drawn as forty and
  // says how long it really was, so a contract of years ago does not press the whole exchange into one corner
  const DAY = 864e5, CAP = 40, MIN = 5, days = [...new Set([...t, ...(quiet() || now < from ? [] : [now])])].sort((x, y) => x - y), eff = new Map([[days[0], 0]]), breaks = [];
  for (let i = 1; i < days.length; i++) { const gap = (days[i] - days[i - 1]) / DAY, drawn = Math.max(MIN, Math.min(gap, CAP)); eff.set(days[i], eff.get(days[i - 1]) + drawn);
    if (gap > CAP) breaks.push([eff.get(days[i - 1]) + drawn / 2, gap]); }
  const total = Math.max(eff.get(days[days.length - 1]), 1), at = (ms) => (100 * (eff.get(ms) || 0) / total).toFixed(2);
  const long = (d) => (d >= 365 ? T(`${Math.round(d / 36.5) / 10} years`, `${String(Math.round(d / 36.5) / 10).replace(".", ",")} Jahre`) : d >= 60 ? T(`${Math.round(d / 30)} months`, `${Math.round(d / 30)} Monate`) : T(`${Math.round(d)} days`, `${Math.round(d)} Tage`));
  const marks = breaks.map(([x, d]) => `<i class="cp-tb-break" style="left:${(100 * x / total).toFixed(2)}%"><span>${long(d)}</span></i>`).join("");
  const lane = (r) => { const w = String(r.who || "").split("→")[0].trim(); return /Kundschaft/.test(w) ? "k" : w.includes(HOUSE.name) ? "p" : "g"; };
  const seen = {}, dots = rows.map((r, i) => { const k = `${lane(r)}:${String(r.date).slice(0, 10)}`, n = (seen[k] = (seen[k] || 0) + 1) - 1;
    return `<button type="button" class="cp-tb-dot ${lane(r)}${r.open ? " open" : ""}" style="left:${at(t[i])}%;--n:${n};--i:${i}" data-tb-no="${raw(r.number ?? "")}" aria-label="${esc(`${dateText(r.date)} · ${r.who || ""} · ${r.what || r.title || ""}`)}" data-tb-tip="${esc(`${dateText(r.date)} · ${r.who || ""}`)}" data-tb-what="${esc(clip(r.what || r.title || "", 90))}"></button>`; }).join("");
  const today = !quiet() && eff.has(now) ? `<i class="cp-tb-today" style="left:${at(now)}%"><span>${T("today", "heute")}</span></i>` : "";
  const gap = Math.round((now - Math.max(...t)) / 864e5);
  return `<div class="cp-timeband" role="group" aria-label="${T("The case over time", "Der Fall in der Zeit")}"><div class="cp-tb-head"><span>${dateText(new Date(from).toISOString().slice(0, 10))}</span>
      <span class="cp-tb-key"><i class="k"></i>${T("customer", "Kundschaft")}<i class="p"></i>${raw(HOUSE.name)}<i class="g"></i>${T("others", "andere")}</span>
      <span>${!quiet() && gap > 13 ? T(`${gap} days since the last entry`, `${gap} Tage seit dem letzten Eintrag`) : dateText(new Date(to).toISOString().slice(0, 10))}</span></div>
    <div class="cp-tb-track">${marks}${today}${dots}</div><p class="cp-tb-tip" id="tb-tip" aria-hidden="true"></p></div>`;
}
const tbRow = (no) => (no === "" ? null : [...document.querySelectorAll(".cp-account-table tbody tr")].find((tr) => tr.firstElementChild && tr.firstElementChild.textContent.trim() === String(no)) || null);
document.addEventListener("mouseover", (event) => {
  const dot = event.target.closest && event.target.closest(".cp-tb-dot"), tip = document.getElementById("tb-tip");
  for (const el of document.querySelectorAll(".cp-tb-point")) el.classList.remove("cp-tb-point");
  if (!tip) return;
  if (!dot) { tip.classList.remove("on"); return; }
  tip.innerHTML = `<b>${raw(dot.dataset.tbTip)}</b> ${raw(dot.dataset.tbWhat)}`;
  tip.style.setProperty("--x", dot.style.left); tip.classList.add("on");
  const row = tbRow(dot.dataset.tbNo); if (row) row.classList.add("cp-tb-point");
});
document.addEventListener("click", (event) => {
  const dot = event.target.closest && event.target.closest(".cp-tb-dot"), row = dot && tbRow(dot.dataset.tbNo);
  if (row) { row.scrollIntoView({ block: "center", behavior: reducedMotion() ? "auto" : "smooth" }); row.classList.remove("cp-story-hit"); void row.offsetWidth; row.classList.add("cp-story-hit"); }
});
// The week under the hand: a day's tile shows its cases in the list before anything is pressed.
document.addEventListener("mouseover", (event) => {
  const tile = event.target.closest && event.target.closest(".cp-wday:not(:disabled)"), table = document.querySelector(".cp-cases");
  if (!table) return;
  if (!tile) { if (S.weekHover) { S.weekHover = null; table.classList.remove("cp-week-hover"); for (const tr of table.querySelectorAll("tr.cp-week-hit")) tr.classList.remove("cp-week-hit"); } return; }
  const key = tile.dataset.todayFilter; if (S.weekHover === key) return;
  S.weekHover = key;
  const all = ((S.listData && S.listData.got && S.listData.got[0]) || {}).cases || [], today = isoToday();
  const ids = new Set(all.filter((c) => c.due && c.due.date && !c.as_of && (key === "due" ? c.due.date <= today : `day:${c.due.date}` === key)).map((c) => c.id));
  table.classList.add("cp-week-hover");
  for (const tr of table.querySelectorAll("tbody tr")) { const a = tr.querySelector('a[href^="#/case/"]'), id = a ? a.getAttribute("href").split("/")[2] : ""; tr.classList.toggle("cp-week-hit", ids.has(id)); }
});
function historyView() {
  const all = S.data.verlauf || [];
  const party = S.onlyOpen && S.openParty;  // «… n weitere» in «Stand»: that party's open items
  // the table reads as the case ran: by day, what has no day last, the file's own order within a day
  const day = (r) => String(r.date || r.at || "9999").slice(0, 10);
  const rows = (S.onlyOpen ? all.filter((r) => r.open && (!party || (r.open_of || []).includes(party))) : all).map((r, i) => [r, i]).sort((a, b) => day(a[0]).localeCompare(day(b[0])) || a[1] - b[1]).map(([r]) => r);
  const gaps = (S.data.items || []).filter((i) => i.kind === "record_gap");
  const docs = all.filter((r) => r.kind !== "gesture").length, done = all.length - docs, open = all.filter((r) => r.open).length;
  const note = (n) => (n.text ? `<div class="cp-entry-note ${n.open ? "open" : ""} ${n.kind}">${esc(n.text)}${n.items ? `<ul class="cp-note-items">${n.items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : ""}</div>` : "");
  // the kind of an entry is said where it says something: «Anderes» says nothing, and the report is already tagged «Meldung»
  const kindOf = (r) => (!r.title || r.title === "Anderes" || (r.kind === "report" && /^Meldung/.test(r.title)) ? "" : r.title);
  const tag = (r) => r.kind === "report" ? `<span class="cp-entry-tag">${T("Report", "Meldung")}</span> ` : r.phone && r.title !== "Telefon" ? `<span class="cp-entry-tag">${T("Phone", "Telefon")}</span> ` : "";
  const own = (r) => r.handler ? `<br><span class="cp-entry-tag own">${T("entered by", "erfasst von")} ${esc(r.handler.by || T("the case handler", "der Fallbearbeitung"))}</span>${r.waiting
    ? ` <span class="cp-muted">${T("counts once the case is prepared anew", "zählt nach einer vollständigen Vorbereitung")}</span>` : ""}` : "";
  const tools = (r) => r.handler ? `<div class="cp-entry-tools"><button class="cp-link cp-quiet-link" data-entry-edit="${raw(String(r.key).split(":")[1])}">${T("change", "ändern")}</button>
      <button class="cp-link cp-quiet-link" data-entry-remove="${raw(String(r.key).split(":")[1])}">${T("remove", "entfernen")}</button></div>`
    : r.undo ? `<div class="cp-entry-tools"><button class="cp-link cp-quiet-link" data-undo-edit="${raw(r.undo)}">${T("undo", "rückgängig")}</button></div>` : "";
  const source = (r) => r.kind === "gesture" || r.handler ? "" : (r.evidence || []).some((e) => e.quote) ? sourceChips((r.evidence || []).slice(0, 1))
    : (r.evidence || [])[0] ? ` <button class="cp-source-chip" data-cite-file="${raw(r.evidence[0].file)}" data-page="">${T("open", "öffnen")}</button>` : "";
  const line = (r) => `<tr class="${r.open ? "open" : ""} cp-row-${raw(r.kind)}" ${String(r.key).startsWith("entry:") ? `data-item="${raw(r.key)}"` : ""}>
      <td>${r.number ?? ""}</td><td class="cp-nowrap">${dateText(r.date)}</td><td class="cp-nowrap">${esc(r.who || "")}</td>
      <td>${tag(r)}${kindOf(r) ? `<span class="cp-muted">${esc(kindOf(r))}</span>` : ""}${tag(r) || kindOf(r) ? "<br>" : ""}${esc(r.what || "")}${source(r)}${own(r)}</td>
      <td>${foldAsks(foldNotes(r.notes || [])).map(note).join("")}${tools(r)}</td></tr>`;
  return `${S.entryEdit ? `<section class="cp-card cp-case cp-entry-edit"><h3>${T("Change your entry", "Eigenen Eintrag ändern")}</h3>${entryForm()}</section>` : ""}
    <section class="cp-card cp-account"><header class="cp-account-head"><h2 class="cp-section">${T("History", "Verlauf")}</h2>
      <span class="cp-muted">${docs} ${docs === 1 ? T("document", "Dokument") : T("documents and entries", "Dokumente und Einträge")}${done ? ` · ${done} ${done === 1 ? T("step done here", "Bearbeitung") : T("steps done here", "Bearbeitungen")}` : ""}${open ? ` · ${open} ${T("open", "offen")}` : ""}</span>
      <label class="cp-account-filter"><input type="checkbox" id="only-open" ${S.onlyOpen ? "checked" : ""}> ${party ? esc(T(`only open with ${party}`, `nur Offenes ${({ kunde: "bei der Kundschaft", versicherer: "bei uns", kanzlei: "bei der Kanzlei", gegenpartei: "bei der Gegenpartei", behoerde: "bei Gericht/Behörde" })[party] || ""}`)) : T("only open", "nur Offenes")}</label></header>
    ${S.data.governing_version ? `<p class="cp-muted" title="${esc(`${S.data.run_version} → ${S.data.governing_version}`)}">${T("Process updated since the case was prepared", "Prozess seit der Vorbereitung aktualisiert")}</p>` : ""}
    ${gaps.length ? `<p class="cp-flag cp-account-gap">${gaps.map((g) => esc((g.label || {}).de || g.value)).join(" · ")}</p>` : ""}
    ${S.onlyOpen || S.entryEdit ? "" : tabPicture("history", 300)}${S.entryEdit ? "" : timeBand()}
    <table class="cp-table cp-account-table"><thead><tr><th>${T("No.", "Nr.")}</th><th>${T("Date", "Datum")}</th><th>${T("From → to", "Von → an")}</th><th>${T("What", "Was")}</th><th>${T("Asked, answered, agreed", "Verlangt, beantwortet, vereinbart")}</th></tr></thead>
    <tbody>${rows.map(line).join("") || `<tr><td colspan="5" class="cp-muted">${S.onlyOpen ? T("Nothing open.", "Nichts offen.") : T("Nothing in the file yet.", "Noch nichts in der Akte.")}</td></tr>`}</tbody></table></section>`;
}
// A fact as a short line names it: what came in by its kind's title, any other fact by its question's first clause.
function shortFact(id) {
  const kind = ((S.data.process || {}).incoming || []).find((k) => k.fact === id || (k.earlier || []).includes(id));
  if (kind) return kind.title + (kind.fact === id ? "" : T(" (earlier)", " (davor)"));
  return clip(plainQuestion(questionOf(id)).split(/(?<=\?)\s|:\s|,\s|\s\(/)[0], 80);
}
// While a run works, «Der Fall» fills in from its events: each document's entry as it is recorded, each fact with its
// value as it is found (then its check), each document need as it is found; the viewer beside it shows what is read.
function liveCase() {
  const found = {}, rows = [], needs = {};
  for (const e of S.events) {
    if (e.kind === "fact.located" && e.status === "established" && e.value !== undefined) found[e.fact] = { value: e.value, verdict: null };
    if (["fact.accepted", "fact.rejected", "fact.conflicting"].includes(e.kind) && found[e.fact]) found[e.fact].verdict = e.kind.split(".")[1];
    if (e.kind === "record.recorded") for (const r of e.rows || []) { const at = rows.findIndex((x) => x.n === r.n); if (at >= 0) rows[at] = r; else rows.push(r); }
    if (e.kind === "document.recorded") needs[e.document] = { status: e.status, verdict: null };
    if (["document.accepted", "document.rejected"].includes(e.kind) && needs[e.document]) needs[e.document].verdict = e.kind.split(".")[1];
  }
  rows.sort((a, b) => String(a.date || "9999").localeCompare(String(b.date || "9999")) || a.n - b.n);
  const mark = (v) => (v === "accepted" ? ` <span class="cp-live-ok">${icon("tick")}</span>` : v === "rejected" ? ` <span class="cp-muted">${T("(not confirmed)", "(nicht bestätigt)")}</span>` : v === "conflicting" ? ` <span class="cp-flag">${T("(readings differ)", "(Lesungen weichen ab)")}</span>` : "");
  const update = (S.data.run || {}).kind === "update";
  const entries = rows.map((r) => `<div class="cp-live-row${enter(`entry:${r.n}`)}"><span class="cp-muted">${dateText(r.date) || T("undated", "ohne Datum")} · ${esc(PARTY_DE[r.from] || r.from || "")} → ${esc(PARTY_DE[r.to] || r.to || "")}</span> ${esc(r.what || "")}</div>`).join("");
  const facts_ = Object.entries(found).map(([id, f]) => `<div class="cp-live-row${enter(`fact:${id}`)}">${esc(shortFact(id))}: <b>${esc(valueText(f.value))}</b>${mark(f.verdict)}</div>`).join("");
  const docs = Object.entries(needs).map(([id, d]) => `<div class="cp-live-row${enter(`need:${id}`)}">${esc(needOf(id))}: ${esc(word(d.status))}${mark(d.verdict)}</div>`).join("");
  const waiting = `<span class="cp-muted">${T("being read …", "wird gelesen …")}</span>`;
  const kept = !S.data.process || Boolean(S.data.process.record) || rows.length;  // a process without the running account records no entries
  return `<section class="cp-card cp-case cp-live-case"><h3>${update ? T("New in this update", "Neu in dieser Aktualisierung") : T("The case", "Der Fall")}</h3>
    <dl class="cp-casefacts">${kept ? `<dt>${T("Course", "Verlauf")}</dt><dd>${entries || waiting}</dd>` : ""}<dt>${T("Facts", "Angaben")}</dt><dd>${facts_ || waiting}</dd>
      ${docs ? `<dt>${T("Documents", "Unterlagen")}</dt><dd>${docs}</dd>` : ""}</dl></section>`;
}
function closed() { const last = ((S.data || {}).caseEvents || []).filter((e) => e.kind === "case.closed" || e.kind === "case.reopened").pop(); return last && last.kind === "case.closed" ? last : undefined; }
function unaidedPending() {
  // Own answer first: a case opened "unaided" for this person shows the files and one short form until it is answered.
  const mine = ((S.data || {}).caseEvents || []).filter((e) => e.expert === S.me);
  return mine.some((e) => e.kind === "case.opened" && e.condition === "unaided") && !mine.some((e) => e.kind === "reveal");
}
function unaidedView() {
  const steps = (S.data.process && S.data.process.steps || []).filter((x) => !CHAT_ROLE.test(x.role || ""));
  const docs = (S.data.process && S.data.process.documents || []).filter((d) => !d.suggested);
  return `<section class="cp-card" style="padding:18px 22px;max-width:760px"><h2 class="cp-section" style="margin-top:0">${T("Your own assessment first", "Zuerst Ihre eigene Einschätzung")}</h2>
    <p class="cp-muted">${T("Read the files on the left, then answer three questions. CasePath's result appears afterwards.", "Lesen Sie links die Akten und beantworten Sie dann drei Fragen. Danach erscheint das Ergebnis von CasePath.")}</p>
    <form id="unaided">
      <label><b>${T("Where does the case stand?", "Wo steht der Fall?")}</b><br><select name="step" class="cp-button"><option value="">—</option>${steps.map((x) => `<option value="${raw(x.id)}">${esc(shortTitle(x.title))}</option>`).join("")}</select></label>
      <p><b>${T("Which documents would you request now?", "Welche Unterlagen würden Sie jetzt anfordern?")}</b></p>
      ${docs.map((d) => `<label style="display:block"><input type="checkbox" name="doc" value="${raw(d.id)}"> ${esc(clip(d.title, 90))}</label>`).join("")}
      <label style="display:block">${T("Other", "Anderes")}: <input name="doc_other" class="cp-input" style="width:60%"></label>
      <p><b>${T("Next action", "Nächster Schritt")}</b><br><select name="action" class="cp-button"><option value="">—</option>
        <option value="request">${T("Request documents", "Unterlagen anfordern")}</option><option value="answer">${T("Ask the customer a question", "Rückfrage an die Kundschaft")}</option>
        <option value="advise">${T("Advise / give the legal position", "Rechtslage mitteilen")}</option><option value="close">${T("Close the case", "Fall abschliessen")}</option>
        <option value="other">${T("Other", "Anderes")}</option></select></p>
      <button class="cp-button primary" type="submit">${T("Save and show CasePath's result", "Speichern und Ergebnis von CasePath zeigen")}</button></form></section>`;
}
// A text block of the letter becomes editable where the hand or the keyboard goes into it, so reading it is not editing it.
function editable(el) {
  if (!el || !el.dataset.editable || el.isContentEditable) return;
  el.setAttribute("contenteditable", "true");
  el.spellcheck = true;
}
// The card's document button says how many gaps are left while the handler types (no redraw under the hand).
function updateGaps() {
  const box = $("[data-item='letter:0']"), button = $("#copy-draft, [data-copy-also], #fill-gaps");
  if (!box || !button || button.disabled) return;
  const n = (box.innerText.match(GAP_RE) || []).length, before = Number(button.dataset.gaps || 0);
  if (n === before) return;
  button.dataset.gaps = String(n);
  button.textContent = n ? T(`Fill ${n} gap${n > 1 ? "s" : ""}`, `${n} Lücke${n > 1 ? "n" : ""} füllen`) : button.id === "fill-gaps" ? T("Approve", "Freigeben")
    : button.id === "copy-draft" ? T("Copy letter", "Brief kopieren") : T("Copy", "Kopieren");
}
// The first gap, selected, so typing replaces it.
function goToGap() {
  // a gap already typed over keeps its mark element: the first mark that still holds a gap
  const gap = [...document.querySelectorAll("[data-item='letter:0'] mark.cp-gap")].find((m) => /^\[bitte ergänzen: [^\]]*\]$/.test(m.textContent)) || [...document.querySelectorAll("[data-item='letter:0'] [data-editable]")].find((el) => GAP_RE.test(el.innerText) && !(GAP_RE.lastIndex = 0));
  if (!gap) return false;
  const block = gap.closest("[data-editable]") || gap;
  editable(block);
  block.focus();
  const range = document.createRange();
  range.selectNodeContents(gap);
  const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range);
  gap.scrollIntoView({ block: "nearest" });
  return true;
}
// After a copy, the next document not yet copied is shown, so the one primary button is always the next thing to do.
function nextTab(kind) {
  S.docPicked = false;
  const rows = documentsOut().rows;
  const after = rows.slice(rows.findIndex((d) => d.kind === kind) + 1).concat(rows).find((d) => d.kind !== kind && !d.copied);
  if (after) S.docTab = after.kind;
}
function bindOverview() {
  const on = (sel, kind, fn) => { for (const el of document.querySelectorAll(sel)) el.addEventListener(kind, (e) => fn(el, e)); };
  const edit = (body) => api(`/api/cases/${S.route.id}/edits`, { method: "POST", body: JSON.stringify(body) });
  on("#copy-draft", "click", (b) => {
    if (Number(b.dataset.gaps || 0) && goToGap()) return;  // «n Lücken füllen»: the cursor goes to the first one
    const text = letterText(), draft = (S.data.draft || {}).text || "";
    const lost = ((S.data.draft || {}).required || []).filter((r) => !text.includes(r.marker));
    if (lost.length) {  // a part the law or the conditions require is not in the letter: it is not copied
      S.message = T(`Required part missing: ${lost.map((r) => `${r.title} (${r.basis})`).join(", ")}`, `Pflichtteil fehlt: ${lost.map((r) => `${r.title} (${r.basis})`).join(", ")}`); S.messageOk = false; renderCase();
      return;
    }
    if (GAP_RE.test(text) && !(GAP_RE.lastIndex = 0)) { goToGap(); return; }  // a part only the handler can write is still open
    const kind = (S.data.draft || {}).form || null, act = item("next_action", "0") || {};
    toClipboard(text, $("[data-item='letter:0']")).then((ok) => {  // the frozen study: copied and measured as frozen; a failed copy records nothing
      if (!ok) { S.copyFailed = true; S.message = T("Copying failed", "Kopieren fehlgeschlagen"); S.messageOk = false; renderCase(); return; }
      S.copyFailed = false; S.copied = true; S.justCopied = kind; nextTab(kind); renderCase();
      setTimeout(() => { S.justCopied = false; if (S.route.view === "case") renderCase(); }, 1800);
      caseEvent("letter.copied", null, { form: kind, edited: text.trim() !== draft.trim(), ...(act.deadline ? { deadline: act.deadline } : {}),
        change_ratio: Math.round(100 * Math.abs(text.length - draft.length) / Math.max(1, draft.length)) / 100 }).then(loadCase).catch(() => {});
    });
  });
  on("[data-copy-also]", "click", (b) => {
    if (Number(b.dataset.gaps || 0) && goToGap()) return;
    const kind = b.dataset.copyAlso, el = $(`[data-also-text='${CSS.escape(kind)}']`), text = !el ? "" : el.dataset.reading ? docText({ kind }) : el.innerText;
    const also = ((S.data.draft || {}).also || []).find((a) => a.kind === kind) || {};
    const lost = (also.required || []).filter((r) => !text.includes(r.marker));
    if (lost.length) { S.message = T("Please complete the letter first.", `Bitte zuerst ergänzen: ${lost.map((r) => r.title).join(", ")}`); S.messageOk = false; renderCase(); return; }
    if (GAP_RE.test(text) && !(GAP_RE.lastIndex = 0)) { goToGap(); return; }
    toClipboard(text, el).then((ok) => {
      if (!ok) { S.copyFailed = true; S.message = T("Copying failed", "Kopieren fehlgeschlagen"); S.messageOk = false; renderCase(); return; }
      S.copyFailed = false; S.justCopied = kind; nextTab(kind); renderCase();
      setTimeout(() => { S.justCopied = false; if (S.route.view === "case") renderCase(); }, 1800);
      const act = item("next_action", "0") || {};
      caseEvent("letter.copied", null, { also: kind, template: Boolean(also.template), edited: (also.text || "").trim() !== text.trim(), ...(act.deadline ? { deadline: act.deadline } : {}) })
        .then(loadCase).catch(() => {});
    });
  });
  on("[data-doc-tab]", "click", (b) => { S.docTab = b.dataset.docTab; S.docPicked = true; renderCase(); });
  on("[data-item='letter:0'] [data-editable]", "mousedown", (el) => editable(el));
  on("[data-item='letter:0'] [data-editable]", "focus", (el) => editable(el));
  on("[data-item='letter:0'] [data-seg='text'][data-editable]", "input", (el) => { (S.blockEdits = S.blockEdits || {})[el.dataset.orig] = el.innerText; updateGaps(); });
  on("[data-item='letter:0'] [data-seg='also'][data-editable]", "input", (el) => { (S.alsoEdits = S.alsoEdits || {})[el.dataset.alsoText] = el.innerText; updateGaps(); });
  // A line's reason opens from the line (its text); the tick stays the request.
  on("[data-why]", "click", (el) => {
    const id = el.dataset.why;
    S.why = S.why === id ? null : id;
    if (S.why) caseEvent("source.opened", id, { reason: "line" }).catch(() => {});
    renderCase();
  });
  // A tick is a request; unticking takes the line out at once and offers the one-tap reason beside it.
  on("[data-line]", "change", async (b) => {
    S.askWhy = b.checked ? null : b.dataset.line;
    if (b.checked) S.openOffers = true;
    await caseEvent("letter.line", b.dataset.line, { included: b.checked, reason: "none" });
    await loadCase();
  });
  on("[data-line-reason]", "click", async (b) => {
    const id = S.askWhy, code = b.dataset.lineReason; S.askWhy = null;
    await caseEvent("letter.line", id, { included: false, reason: code });
    // one strike: a document that is not relevant here, or generally not, leaves what the case needs (undoable), not only
    // this letter; «gilt generell so» is also proposed for similar cases, and said so (or said why it cannot be)
    if (/^document:/.test(id || "") && (code === "3" || code === "4")) {
      S.lastEdit = await edit({ op: "remove_document", args: { document: id.slice("document:".length) }, reason: "", reason_code: code, recheck: false })
        .catch((error) => { S.message = error.message; S.messageOk = false; return S.lastEdit; });
    }
    await loadCase();
  });
  on("#add-doc", "keydown", async (el, e) => {  // the handler asks for one more document: type it, Enter; it is in the letter at once
    if (e.key !== "Enter" || !el.value.trim() || el.disabled) return;
    const title = el.value.trim(); el.disabled = true;
    const step = (S.data.evaluation && S.data.evaluation.current && S.data.evaluation.current.step) || undefined;
    const made = await edit({ op: "add_document", args: { title, why: "von der Fallbearbeitung verlangt", ...(step ? { step } : {}) }, reason: "", reason_code: "none", recheck: false })
      .catch((error) => { S.message = error.message; S.messageOk = false; return null; });
    if (made) { S.lastEdit = made; S.lastUndo = null; S.addedDoc = { case: S.route.id, edit: made.edit.id, title, said: made.knowledge ? T("Proposed for similar cases.", "Für ähnliche Fälle vorgeschlagen.") : "" }; }
    await loadCase();
    const again = $("#add-doc"); if (again) again.focus();
  });
  on("[data-add-general]", "click", async (b) => {  // optional, afterwards: the same for similar cases (a reviewer releases it)
    b.disabled = true;
    const said = await api(`/api/edits/${b.dataset.addGeneral}/general`, { method: "POST" }).catch((error) => ({ only_here: error.message }));
    S.addedDoc = { ...S.addedDoc, said: said.knowledge ? T("Proposed for similar cases; a reviewer releases it under Knowledge.", "Für ähnliche Fälle vorgeschlagen; freigegeben wird es unter «Wissen».") : said.only_here || "" };
    renderCase();
  });
  on("#change-action", "click", () => { S.changing = !S.changing; S.pickAction = null; renderCase(); });
  on("#rest-open", "click", () => { S.restOpen = S.restOpen === S.route.id ? null : S.route.id; renderCase(); });
  on("[data-pick-action]", "click", (b) => { S.pickAction = (S.data.action_options || []).find((x) => x.kind === b.dataset.pickAction); renderCase(); });
  on("[data-action-reason]", "click", async (b) => {  // "andere Handlung": one reason; the draft and the date follow
    const kind = S.pickAction.kind; S.pickAction = null; S.changing = false; S.docTab = null; S.feeAnswer = null;
    await api(`/api/cases/${S.route.id}/action`, { method: "POST", body: JSON.stringify({ kind, reason_code: b.dataset.actionReason }) }).catch((error) => { S.message = error.message; });
    await loadCase();
  });
  on("[data-settle]", "click", async (b) => {  // an open request the handler settles: the package follows, with its undo
    S.lastUndo = null;
    S.lastEdit = await edit({ op: "settle_request", args: { request: b.dataset.settle, how: b.dataset.how }, reason: "", reason_code: "none", recheck: false })
      .catch((error) => { S.message = error.message; return S.lastEdit; });
    await loadCase();
  });
  on("[data-decide]", "click", (b) => decideFact(b.dataset.decide, b.dataset.value));  // the handler's own decision: one click, no reason asked
  on("[data-change-undo]", "click", async (b) => {  // an earlier change taken back where it stands; what came back is shown once
    b.disabled = true;
    const done = await api(`/api/edits/${b.dataset.changeUndo}/undo`, { method: "POST" }).catch((error) => { S.message = error.message; S.messageOk = false; return null; });
    S.lastUndo = done && { ...done, case: S.route.id }; S.lastEdit = null; await loadCase();
  });
  on("[data-decided-undo]", "click", async (b) => {  // a decision taken is changed where it stands: its edit undone, the card asks again
    b.disabled = true;
    await api(`/api/edits/${b.dataset.decidedUndo}/undo`, { method: "POST" }).catch((error) => { S.message = error.message; S.messageOk = false; });
    S.lastEdit = null; await loadCase();
  });
  on("[data-decided-withdraw]", "click", async (b) => {
    b.disabled = true;
    await api(`/api/cases/${S.route.id}/recommendation`, { method: "DELETE" }).catch((error) => { S.message = error.message; S.messageOk = false; });
    await loadCase();
  });
  on("[data-claim-settle]", "click", async (b) => {  // which statement of a claimed cost holds: one click, undoable like any edit
    S.lastEdit = await edit({ op: "set_claim", args: { claim: b.dataset.claimSettle, as: b.dataset.as }, reason: "", reason_code: "none", recheck: false }).catch(() => S.lastEdit);
    S.decideOpen = false;
    await loadCase();
  });
  on("[data-stance]", "click", async (b) => {  // the answer to an offer: one click writes the letter; the same click again takes it back
    const now = (scr().decision || {}).chosen === b.dataset.stance ? null : b.dataset.stance;
    try { await api(`/api/cases/${S.route.id}/offer/stance`, { method: "POST", body: JSON.stringify({ stance: now }) }); S.message = ""; } catch (error) { S.message = error.message; S.messageOk = false; }
    S.docTab = null;
    await loadCase();
  });
  on("[data-fee-answer]", "click", (b) => {  // the fee note: the query or the partial refusal, its letter shown to copy
    S.feeAnswer = S.feeAnswer === b.dataset.feeAnswer ? null : b.dataset.feeAnswer; S.docTab = S.feeAnswer; renderCase();
  });
  on("#weil-open", "click", () => { S.weilOpen = !S.weilOpen; renderCase(); });
  on("#lead-open", "click", () => { S.leadOpen = !S.leadOpen; renderCase(); });
  on("#decide-open", "click", () => { S.decideOpen = !S.decideOpen; renderCase(); });
  on("#anliegen-open", "click", () => { S.anliegenOpen = !S.anliegenOpen; renderCase(); });
  on("[data-cover-toggle]", "click", () => { S.coverOpen = !S.coverOpen; renderCase(); });
  on("[data-cover-passage]", "click", (b) => { S.coverPassage = S.coverPassage === b.dataset.coverPassage ? null : b.dataset.coverPassage; renderCase(); });
  on("[data-key-point]", "click", (b) => {
    S.keyPoint = S.keyPoint === b.dataset.keyPoint ? null : b.dataset.keyPoint;
    if (S.keyPoint) caseEvent("source.opened", `key_point:${S.keyPoint}`, {}).catch(() => {});
    renderCase();
  });
  on("[data-cover-decline]", "click", () => { S.coverDecline = !S.coverDecline; renderCase(); });
  on("[data-cover-reason]", "click", async (b) => {  // refusing cover: which point fails, one tap; both are the handler's facts, logged as such
    S.coverDecline = false;
    await edit({ op: "set_fact", args: { fact: "deckung_grund", value: b.dataset.coverReason }, reason: "", reason_code: "none", recheck: false });
    S.lastEdit = await edit({ op: "set_fact", args: { fact: "deckung", value: "abgelehnt" }, reason: "", reason_code: "none", recheck: false }).catch(() => S.lastEdit);
    await loadCase();
  });
  on("[data-cover-edition]", "change", async (sel) => {
    S.lastEdit = await edit({ op: "set_fact", args: { fact: "avb_ausgabe", value: sel.value }, reason: "", reason_code: "none", recheck: false }).catch(() => S.lastEdit);
    await loadCase();
  });
  on("[data-cover-begin]", "change", async (inp) => {
    if (!inp.value) return;
    S.lastEdit = await edit({ op: "set_fact", args: { fact: "police_beginn", value: inp.value }, reason: "", reason_code: "none", recheck: false }).catch(() => S.lastEdit);
    await loadCase();
  });
  on("[data-also-set]", "change", async (el) => {  // the guarantee's scope and an amount only the handler enters
    const value = el.value.trim();
    if (!value) return;
    S.lastEdit = await edit({ op: "set_fact", args: { fact: el.dataset.alsoSet, value }, reason: "", reason_code: "none", recheck: false }).catch(() => S.lastEdit);
    await loadCase();
  });
  on("[data-set-fact]", "click", (b) => { S.pick = { fact: b.dataset.setFact, value: b.dataset.value }; renderCase(); });
  on("[data-reason]", "click", async (b) => {
    const pick = S.pick; S.pick = null;
    S.lastEdit = await edit({ op: "set_fact", args: { fact: pick.fact, value: pick.value }, reason: "", reason_code: b.dataset.reason, recheck: false });
    await loadCase();
  });
  on("[data-undo-edit]", "click", async (b) => { await api(`/api/edits/${b.dataset.undoEdit}/undo`, { method: "POST" }); S.lastEdit = null; await loadCase(); });
  on("#copy-note", "click", () => copyNote());  // the file note writes itself; copied, it is logged; a failed copy records nothing
  // the handler's own entry: one tap opens the form, its draft survives a redraw, a part opens in place, saving counts at once
  const openForm = (draft, inCard) => { S.noting = true; S.noteInCard = Boolean(inCard); S.entryEdit = null; S.entryError = ""; S.entryDraft = draft || null; renderCase();
    const form = $("#note-form"); if (form) { form.scrollIntoView({ block: "nearest" }); const t = form.querySelector("textarea"); if (t) t.focus(); } };
  on("#add-note", "click", () => { if (S.noting && !S.entryEdit) { S.noting = false; renderCase(); } else openForm(); });
  on("#phone-note", "click", (b) => openForm({ kind: b.dataset.kind, party: b.dataset.party, date: isoToday() }, true));  // written where the button is
  on("#note-cancel", "click", () => { S.noting = false; S.entryEdit = null; S.entryDraft = null; S.entryError = ""; renderCase(); });
  on("#note-form select[name=party]", "change", (sel) => {  // who pays, of whom, who acts next follow «mit» until chosen by hand
    const form = sel.closest("form");
    for (const [name, fit] of [["agreed_payer", (p) => (p === "gegenpartei" ? p : "")], ["asked_of", (p) => p], ["next_who", (p) => p]]) {
      const el = form.elements[name];
      if (el && !el.dataset.touched) el.value = fit(sel.value);
    }
  });
  on("#note-form select[name=agreed_payer], #note-form select[name=asked_of], #note-form select[name=next_who]", "change", (el) => { el.dataset.touched = "1"; });
  on("#note-form", "input", (form) => { S.entryDraft = entryDraftOf(form); });
  on("#note-form", "change", (form) => { S.entryDraft = entryDraftOf(form); });
  on("[data-entry-part]", "click", (b) => {
    const form = b.closest("form"), row = form.querySelector(`[data-part='${b.dataset.entryPart}']`);
    if (row) { row.hidden = false; b.remove(); S.entryDraft = entryDraftOf(form); const first = row.querySelector("input"); if (first) first.focus(); }
  });
  on("#note-form", "submit", async (form, event) => {
    event.preventDefault();
    const draft = entryDraftOf(form), body = entryBody(draft), edit = form.dataset.edit;
    if (!body.said && !body.agreed && !body.asked && !body.next) {
      S.entryDraft = draft; S.entryError = T("Please note what was said.", "Bitte festhalten, was besprochen wurde."); renderCase(); return;
    }
    try {
      await api(edit ? `/api/cases/${S.route.id}/entries/${edit}` : `/api/cases/${S.route.id}/entries`, { method: edit ? "PUT" : "POST", body: JSON.stringify(body) });
    } catch (error) { S.entryDraft = draft; S.entryError = error.message; renderCase(); return; }
    S.noting = false; S.entryEdit = null; S.entryDraft = null; S.entryError = "";
    S.message = edit ? T("Entry changed.", "Eintrag geändert.") : T("Entry saved; the case is recomputed.", "Eintrag gespeichert; der Fall ist neu berechnet."); S.messageOk = true;
    await loadCase();
    setTimeout(() => { S.message = ""; if (S.route.view === "case") renderCase(); }, 2500);
  });
  on("[data-entry-edit]", "click", (b) => {  // a handler's entry, changed where it stands
    const row = (S.data.verlauf || []).find((r) => r.key === `entry:${b.dataset.entryEdit}`) || {};
    const f = (row.handler || {}).form || {};
    const open = { agreed: Boolean(f.agreed), asked: Boolean(f.asked), next: Boolean(f.next) };
    S.entryEdit = b.dataset.entryEdit; S.noting = false; S.entryError = "";
    S.entryDraft = { ...f, open, agreed: f.agreed || {}, asked: f.asked || {}, next: f.next || {} };
    renderCase();
    const form = $("#note-form"); if (form) form.scrollIntoView({ block: "nearest" });
  });
  on("[data-entry-remove]", "click", async (b) => {
    if (!window.confirm(T("Remove this entry? It no longer counts; the removal is kept in the course of the case.", "Diesen Eintrag entfernen? Er zählt nicht mehr; das Entfernen bleibt im Verlauf vermerkt."))) return;
    await api(`/api/cases/${S.route.id}/entries/${b.dataset.entryRemove}`, { method: "DELETE" }).catch((error) => { S.message = error.message; });
    await loadCase();
  });
  on("#story-open, #story-close", "click", () => { openStory().then(() => { const w = document.querySelector("[data-story-wrap]"); if (w) w.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" }); }); });
  on("#other-reference-open", "click", (b) => { S.file = b.dataset.file; location.hash = `#/case/${S.route.id}/claim_reader`; });
  on("#trail-open", "click", () => { S.trailOpen = !S.trailOpen; if (S.justFinished === S.route.id) { S.justFinished = null; S.trailOpen = false; } renderCase(); });
  on("#letter-original", "click", () => { S.letterOriginal = true; renderCase(); });
  on("#letter-reading", "click", async () => { if (await saveDraft()) { S.letterOriginal = false; renderCase(); } });
  on("#use-anyway", "click", async () => {  // the handler uses the draft before the new files are read: allowed, and logged
    await caseEvent("letter.unblocked", null, { files: (S.data.arrived || []).map((f) => f.name).slice(0, 20) }).catch(() => {});
    await loadCase();
  });
  on("[data-close]", "click", async (b) => {
    const line = b.dataset.close === "erledigt_mit_vorbehalt" ? (($("#reservation") || {}).value || "") : "";
    await caseEvent("case.closed", null, { form: b.dataset.close, note_present: Boolean(line.trim()), ...(line.trim() ? { text: line.trim().slice(0, 2000) } : {}) });
    await loadCase();
  });
  on("#followup-show", "click", () => { const fu = $("#followup-date"); try { fu.showPicker(); } catch (error) { fu.focus(); } });
  on("#followup-date", "change", async (fu) => {
    if (!fu.value) return;
    // the date set counts for this step only: it lapses with it, and with a later dispatch (clock.follow_up)
    await caseEvent("followup.set", "followup:0", { date: fu.value, before: fu.defaultValue || (S.data.follow_up || {}).due || null, step: (item("next_action", "0") || {}).action || null });
    await loadCase();
  });
  on("#unaided", "submit", async (unaided, event) => {
    event.preventDefault();
    const form = new FormData(unaided);
    // one POST: the server stores the answer, hashes and freezes it, and reveals; a second answer is refused
    await api(`/api/cases/${S.route.id}/own-answer`, { method: "POST", body: JSON.stringify({ step: form.get("step") || null, documents: form.getAll("doc"),
      documents_other: String(form.get("doc_other") || "").slice(0, 500), action_kind: form.get("action") || null }) });
    await loadCase();
  });
  on("[data-point-notneeded]", "click", async (b) => {
    S.lastEdit = await edit({ op: "remove_document", args: { document: b.dataset.pointNotneeded },
      reason: T("not needed in this case (case worker)", "in diesem Fall nicht nötig (Fallbearbeitung)"), use_for_similar: false });
    await loadCase();
  });
  on("[data-point-choose]", "change", async (sel) => {
    if (!sel.value) return;
    await api(`/api/cases/${S.route.id}/workflow`, { method: "PUT", body: JSON.stringify({ workflow_id: sel.value }) });
    await loadCase();
  });
  bindCarry(on);  // the decision carried through: saving per part, Freigeben, Brief kopieren, Versandt am (completion section)
  const asking = $(".cp-why-row");  // the optional follow-up stands where the hand already is
  if (asking) asking.scrollIntoView({ block: "nearest" });
}

// ---------- case page ----------
async function loadCase() {
  const id = S.route.id;
  if (S.loadedCase !== id) {  // an opened source, a tab, an opened reason and an unsent edit belong to their case
    Object.assign(S, { overviewSource: false, loadedCase: id, docTab: null, docFor: null, docPicked: false, feeAnswer: null, weilOpen: false, leadOpen: false, decideOpen: false, why: null,
                       anliegenOpen: false, keyPoint: null, coverOpen: false, coverDecline: false, blockEdits: {}, alsoEdits: {}, askWhy: null, openOffers: false, changing: false, pickAction: null, addedDoc: null, sideOpen: {}, segsOpen: {} });
  }
  const [data, workflows, knowledge] = await Promise.all([api(`/api/cases/${id}`), S.workflows ? null : api("/api/workflows"), api("/api/knowledge")]);
  if (workflows) S.workflows = workflows.workflows;
  S.knowledge = knowledge.knowledge;
  if (data.run && data.run.status !== "completed") {
    const all = await api(`/api/runs/${data.run.id}`);
    S.events = all.events;
  }
  S.data = data;
  try { S.data.caseEvents = (await api(`/api/cases/${id}/events`)).events; } catch (error) { S.data.caseEvents = []; }
  S.data.lastCompleted = data.run && data.run.status === "completed" ? data.run : data.prepared_run || null;
  if (!S.file && data.files.length) S.file = data.files[0].id;
  if (running()) schedulePoll();
  await renderCase();
}

// The person's own active time on a case, measured only where the deployment allows it and the person switched it on
// for this browser session (shown in the top bar while it runs): the case opened, a minute without input or the window
// hidden or the case left (idle), the return. Nothing is recorded otherwise.
const MEASURE = { allowed: false, on: false, caseId: null, active: false, timer: null };
try { MEASURE.on = sessionStorage.getItem("cp-measure") === "1"; } catch (error) { /* storage blocked: the measurement stays off */ }
function measureSend(caseId, kind) {
  if (!caseId) return;
  fetch(`/api/cases/${caseId}/events`, { method: "POST", keepalive: true, headers: { "content-type": "application/json" }, body: JSON.stringify({ kind, item_id: null, fields: {} }) }).catch(() => {});
}
function measureIdle() {
  clearTimeout(MEASURE.timer);
  if (MEASURE.active) { MEASURE.active = false; measureSend(MEASURE.caseId, "idle.started"); }
}
function measureTouch() {  // the person is at work on the case shown
  if (!MEASURE.allowed || !MEASURE.on || S.route.view !== "case" || document.hidden || ((S.data || {}).case || {}).id !== S.route.id) return;
  if (((S.data.case || {}).intake || {}).study) return;  // a study copy has its own session measurement
  if (MEASURE.caseId !== S.route.id) { measureIdle(); MEASURE.caseId = S.route.id; MEASURE.active = true; measureSend(MEASURE.caseId, "case.opened"); }
  else if (!MEASURE.active) { MEASURE.active = true; measureSend(MEASURE.caseId, "idle.ended"); }
  clearTimeout(MEASURE.timer);
  MEASURE.timer = setTimeout(measureIdle, 60000);
}
function measureLeave() { measureIdle(); MEASURE.caseId = null; }
for (const kind of ["keydown", "pointerdown", "wheel"]) document.addEventListener(kind, measureTouch, { passive: true, capture: true });
document.addEventListener("visibilitychange", () => { if (document.hidden) measureIdle(); else measureTouch(); });
window.addEventListener("pagehide", measureIdle);
function measureToggle() {
  if (!MEASURE.allowed) return "";
  return `<button class="cp-link cp-measure ${MEASURE.on ? "on" : ""}" id="measure-toggle" aria-pressed="${MEASURE.on}" title="${T("Measures your own active time on a case, for this browser session, only while you leave it switched on.",
    "Misst Ihre eigene aktive Zeit an einem Fall, für diese Browser-Sitzung und nur, solange Sie es eingeschaltet lassen.")}">${MEASURE.on ? `● ${T("Time is measured", "Zeitmessung läuft")}` : T("Measure time", "Zeit messen")}</button>`;
}
// A run the reader started and left: the browser keeps asking (cheaply, statuses only) and says when it is done, in
// the tab's title and in one quiet line that opens the case. Opening the case takes the notice away.
const WATCH = { runs: {}, done: [], timer: null };
function watchRun(run, c) {
  if (!run || !["queued", "running"].includes(run.status)) return;
  WATCH.runs[run.id] = { id: c.id, name: caseName(c), kind: run.kind };
  if (!WATCH.timer) WATCH.timer = setInterval(pulse, 4000);
}
async function pulse() {
  const ids = Object.keys(WATCH.runs);
  if (!ids.length) { clearInterval(WATCH.timer); WATCH.timer = null; return; }
  let now;
  try { now = (await api(`/api/pulse?runs=${ids.join(",")}`)).runs; } catch (error) { return; }
  for (const id of ids) {
    const status = now[id];
    if (status && ["queued", "running"].includes(status)) continue;
    const row = WATCH.runs[id];
    delete WATCH.runs[id];
    if (S.route.view === "case" && S.route.id === row.id && !document.hidden) continue;  // the reader is looking at it
    WATCH.done = WATCH.done.filter((d) => d.id !== row.id).concat([{ ...row, status }]);
  }
  showNotices();
}
function showNotices() {
  WATCH.done = WATCH.done.filter((d) => !(S.route.view === "case" && S.route.id === d.id && !document.hidden));
  const here = S.route.view === "case" ? (S.data && S.data.case ? tr(caseName(S.data.case)) : "") : S.route.view === "knowledge" || S.route.view === "review" ? T("Knowledge", "Wissen")
    : S.route.view === "auswertung" ? T("Evaluation", "Auswertung") : T("Cases", "Fälle");
  document.title = `${WATCH.done.length ? `(${WATCH.done.length}) ` : ""}${here ? `${here} · ` : ""}CasePath`;
  let box = document.getElementById("cp-notices");
  if (!WATCH.done.length) { if (box) box.remove(); return; }
  if (!box) { box = document.createElement("div"); box.id = "cp-notices"; box.className = "cp-notices"; box.setAttribute("role", "status"); document.body.appendChild(box); }
  const word = (d) => d.status === "completed" ? (d.kind === "update" ? T("Updated", "Aktualisiert") : T("Prepared", "Fertig vorbereitet"))
    : d.status === "paused" ? T("Stopped", "Angehalten") : T("Not finished", "Nicht fertig");
  box.innerHTML = WATCH.done.map((d) => `<a class="cp-notice ${d.status === "completed" ? "" : "warn"}" href="#/case/${raw(d.id)}/overview">${d.status === "completed" ? icon("check") : ""}<b>${word(d)}</b> ${esc(d.name)}</a>`).join("");
}
document.addEventListener("visibilitychange", () => { if (!document.hidden) showNotices(); });
function schedulePoll() {
  clearTimeout(S.poll);
  S.poll = setTimeout(async () => {
    if (S.route.view !== "case" || !running()) return;
    const run = await api(`/api/runs/${S.data.run.id}?after=${S.events.length ? S.events[S.events.length - 1].seq : 0}`);
    const seen = Date.now();
    S.events = S.events.concat(run.events.map((e) => ({ ...e, seen })));
    // a file's reading is saved while the run goes on: show the read text from then on
    run.events.forEach((e) => { if (e.file && e.kind === "reading.saved") delete S.pages[e.file]; });
    if (["queued", "running"].includes(run.status)) S.data.run.status = run.status;
    if (!["queued", "running"].includes(run.status)) {  // finished while the reader watched: said for a moment, then the prepared step arrives
      const here = S.route.id;
      if (run.status === "completed" && !reducedMotion()) {
        S.data.run.status = "running"; S.finishing = true;
        await renderCase();
        await new Promise((done) => setTimeout(done, 1100));
        S.finishing = false;
        if (S.route.view !== "case" || S.route.id !== here) return;
      }
      S.data.run.status = run.status;
      S.events = []; S.pages = {};
      if (run.status === "completed") { S.justFinished = here; S.arrive = "open"; }
      await loadCase(); return;
    }
    const cite = liveCite();
    if (cite && S.follow) S.file = cite.file;
    await renderCase();
    schedulePoll();
  }, 1200);
}

async function renderCase() {
  renderTop();
  const tab = S.route.tab;
  let main;
  const liveView = running();  // during a run every tab shows the work live; the working agent's tab pulses
  const live = liveView ? liveState() : null;
  if (liveView && tab === "overview") {  // a run is the Übersicht filling in (section U): the run line on top, then what is read and the case
    main = `${runLine(caseState())}<div class="cp-overview cp-live-overview"><div id="overview-source">${await sourceCard(S.file)}</div><aside class="cp-side">${liveCase()}</aside></div>`;
  } else if (liveView) {
    main = `${live ? liveSpine(live) : spine()}<div class="cp-live"><div>${await sourceCard(S.file)}${factCards()}</div>${livePanel(live)}</div>`;
  } else if (unaidedPending()) main = `${unaidedView()}<div style="margin-top:22px">${S.file ? `<iframe title="${T("Original file", "Originaldatei")}" src="/api/files/${raw(S.file)}/original" style="width:100%;height:78vh;border:1px solid var(--line)"></iframe>` : ""}</div>`;  // every tab: the original file only
  else if (tab === "claim_reader") main = claimView(await sourceCard(S.file));
  else if (tab === "source_checker") main = `${checkerView()}<div style="margin-top:22px;max-width:760px">${await sourceCard(S.file)}</div>`;
  else if (tab === "document_finder") main = `${documentsView()}${S.overviewSource ? `<div id="overview-source" class="cp-src-float">${srcClose()}${await sourceCard(S.file)}</div>` : ""}`;
  else if (tab === "result_checker") main = resultView();
  else if (tab === "history") main = `${historyView()}${S.overviewSource ? `<div id="overview-source" class="cp-src-float">${srcClose()}${await sourceCard(S.file)}</div>` : ""}`;
  else if (tab === "overview") main = `${overviewView()}${S.overviewSource && hasPrepared() ? `<div id="overview-source" class="cp-src-float">${srcClose()}${await sourceCard(S.file)}</div>`
    : !hasPrepared() ? `<div id="overview-source" style="margin-top:22px;max-width:760px">${await sourceCard(S.file)}</div>` : ""}`;
  else main = processView();
  // What the handler is typing survives a re-render (a run's progress or a reload redraws the page).
  const typing = [...document.querySelectorAll("#app input[id], #app textarea[id]")].filter((el) => el.value && !["file", "checkbox", "radio"].includes(el.type))
    .map((el) => ({ id: el.id, value: el.value, focus: el === document.activeElement, start: el.selectionStart, end: el.selectionEnd }));
  const tabIn = S.tabIn && !liveView && S.data; if (S.data) S.tabIn = false;

  $("#app").innerHTML = `${renderRail()}<main class="cp-main${tabIn ? " cp-tab-in" : ""}">${main}</main>`;
  glide();
  mountStory();
  watchRun(S.data.run, S.data.case);
  showNotices();
  if (MEASURE.on && MEASURE.caseId !== S.route.id) measureTouch();  // the case is on the screen: its measured span begins
  for (const t of typing) {
    const el = document.getElementById(t.id);
    if (!el || el.value || el.type === "file") continue;
    try { el.value = t.value; } catch (e) { continue; }  // a value the field refuses never stops the page
    if (t.focus) { el.focus(); try { el.setSelectionRange(t.start, t.end); } catch (e) { /* not a text field */ } }
  }
  for (const b of document.querySelectorAll("#story-show")) b.addEventListener("click", () => setPicture(true, b.dataset.kind));
  xRest();
  letterSources();
  keepMotion($("#app"));
  markInReview();
  bindIdentity();
  bindRail();
  for (const b of document.querySelectorAll("[data-step]")) b.addEventListener("click", () => { S.step = b.dataset.step; renderCase(); });
  for (const b of document.querySelectorAll("[data-step-file]")) b.addEventListener("click", () => { if (b.dataset.stepFile) { S.file = b.dataset.stepFile; S.follow = !running(); renderCase(); } });
  for (const b of document.querySelectorAll("#source-lang")) b.addEventListener("click", () => { S.sourceOriginal = !S.sourceOriginal; renderCase(); });
  for (const b of document.querySelectorAll("[data-cite-file]")) b.addEventListener("click", () => {
    const holder = b.closest("[data-item]");
    caseEvent("source.opened", holder && /^[a-z_]+:/.test(holder.dataset.item) ? holder.dataset.item : null, { file_id: b.dataset.citeFile, page: Number(b.dataset.page) || null }).catch(() => {});
  });
  for (const b of document.querySelectorAll("[data-cite-file]")) b.addEventListener("click", async () => { S.file = b.dataset.citeFile; S.page = Number(b.dataset.page) || null; S.overviewSource = ["overview", "history", "document_finder"].includes(tab); S.xPin = null; await renderCase(); const box = $("#overview-source"); if (box && !box.classList.contains("cp-src-float")) box.scrollIntoView({ block: "start", behavior: "smooth" }); });
  for (const b of document.querySelectorAll("[data-src-close]")) b.addEventListener("click", () => { S.overviewSource = false; renderCase(); });
  for (const b of document.querySelectorAll("[data-rate]")) b.addEventListener("click", () => sendRating(b).catch((error) => { S.message = error.message; renderCase(); }));
  const follow = $("#follow");
  if (follow) follow.addEventListener("click", () => {
    S.follow = true;
    const cite = liveCite();
    if (cite) S.file = cite.file;
    renderCase();
  });
  let previousBottom = null;  // a node that starts below the previous one's bottom begins a new row: no arrow into it
  for (const node of document.querySelectorAll(".cp-graph .cp-node")) {
    node.classList.toggle("row-start", previousBottom !== null && node.offsetTop >= previousBottom);
    previousBottom = node.offsetTop + node.offsetHeight;
  }
  const open = $("#edit-open");
  if (open) open.addEventListener("click", () => { S.editing = !S.editing; renderCase(); });
  const undo = $("#undo");
  if (undo) undo.addEventListener("click", async () => {  // what came back and what an undo cannot reach stay in view once
    const done = await api(`/api/edits/${S.lastEdit.edit.id}/undo`, { method: "POST" }).catch(() => null);
    S.lastUndo = done && { ...done, case: S.route.id }; S.lastEdit = null; await loadCase(); });
  const onlyOpen = $("#only-open");
  if (onlyOpen) onlyOpen.addEventListener("change", () => { S.onlyOpen = onlyOpen.checked; S.openParty = null; renderCase(); });
  for (const b of document.querySelectorAll("[data-open-party]")) b.addEventListener("click", () => {
    S.onlyOpen = true; S.openParty = b.dataset.openParty; location.hash = `#/case/${S.route.id}/history`; });
  bindEdit();
  bindOverview();
  foldSide();
  fitCard();
  watchExposure(tab);
  const hit = $("#live-hit"), body = hit && hit.closest(".cp-doc-body");
  const reading = liveView && !hit ? liveCite() : null, readPage = reading && reading.page && $(`#page-${reading.page}`);
  if (body) {  // centre the quote inside its card at once, so the pointer lands where the quote stays
    const a = hit.getBoundingClientRect(), b = body.getBoundingClientRect();
    body.scrollTop += a.top - b.top - body.clientHeight / 2 + a.height / 2;
  } else if (hit) hit.scrollIntoView({ block: "center" });
  else if (readPage && readPage.closest(".cp-doc-body")) {  // the page an agent reads, inside the viewer; the window stays where it is
    const box = readPage.closest(".cp-doc-body");
    box.scrollTop += readPage.getBoundingClientRect().top - box.getBoundingClientRect().top;
  } else if (S.page && $(`#page-${S.page}`)) $(`#page-${S.page}`).scrollIntoView({ block: "start" });
  placeAttention(liveView && tab !== "overview", live);
}

// The prepared card fills the window below what stands above it, so its action bar is always in view; «Der Fall» beside
// it scrolls within the same height, so the page itself does not.
function fitCard() {
  const el = $(".cp-prepared"), side = $(".cp-overview > .cp-side");
  // the card is at least as tall as the window leaves it (a short letter keeps its bar at the bottom) and grows with its
  // letter; «Der Fall» beside it stays in view and scrolls within that height
  if (!el || window.innerWidth < 1000 || el.classList.contains("cp-resting")) { if (el) el.style.minHeight = ""; if (side) side.style.maxHeight = el && window.innerWidth >= 1000 ? `${Math.max(400, window.innerHeight - 117)}px` : ""; return; }
  const top = el.parentElement.getBoundingClientRect().top + window.scrollY;  // where the card starts
  const height = Math.max(400, window.innerHeight - top - 26);
  el.style.minHeight = `${height}px`;
  if (side) side.style.maxHeight = `${height}px`;
}
window.addEventListener("resize", fitCard);

// ---------- knowledge ----------
// What ordinary use shows, content-free (L4): per case and in total; the export is the same JSON.
// How the operation runs, in the measures claims handling knows: how long a case waits for its first prepared step,
// its first letter and its cover decision, how long it takes to close, how old the open cases are. Each figure says how
// many cases it rests on; the bar of the open cases grows to its shares once.
function operationsView(o) {
  if (!o) return "";
  const time = (sec) => (sec == null ? "—" : sec < 90 ? `${Math.round(sec)} s` : sec < 5400 ? `${Math.round(sec / 60)} ${T("min", "Min")}` : sec < 172800 ? `${Math.round(sec / 3600)} h` : `${Math.round(sec / 86400)} ${T("days", "Tage")}`);
  const days = (d) => (d == null ? "—" : d < 1 ? time(d * 86400) : `${String(Math.round(d * 10) / 10).replace(".", LANG === "de" ? "," : ".")} ${d === 1 ? T("day", "Tag") : T("days", "Tage")}`);
  const basis = (m) => (m.cases ? T(`median of ${m.cases} ${m.cases === 1 ? "case" : "cases"}`, `Median aus ${m.cases} ${m.cases === 1 ? "Fall" : "Fällen"}`) : T("no case yet", "noch kein Fall"));
  const figure = (value, label, m) => `<div class="cp-figure"><b>${esc(value)}</b><span>${label}</span><small class="cp-muted">${basis(m)}</small></div>`;
  const ages = [["days_0_7", T("up to 7 days", "bis 7 Tage")], ["days_8_30", T("8 to 30 days", "8 bis 30 Tage")], ["days_31_90", T("31 to 90 days", "31 bis 90 Tage")], ["days_over_90", T("over 90 days", "über 90 Tage")]];
  const open = ages.reduce((n, [k]) => n + (o.aging[k] || 0), 0);
  const bar = open ? `<div class="cp-ops-bar" role="img" aria-label="${T("Open cases by age", "Offene Fälle nach Alter")}">${ages.map(([k], i) => (o.aging[k] ? `<span class="cp-ops-seg a${i}" style="flex-grow:${o.aging[k]}"></span>` : "")).join("")}</div>
      <ul class="cp-ops-legend">${ages.map(([k, w], i) => `<li><i class="cp-ops-dot a${i}"></i>${w} <b>${o.aging[k] || 0}</b></li>`).join("")}</ul>` : "";
  const share = (n, of) => (of ? `${n} ${T("of", "von")} ${of}` : "—");
  return `<h2 class="cp-section">${T("The operation", "Der Betrieb")}</h2>
    <section class="cp-today cp-figures cp-ops" aria-label="${T("The operation in figures", "Der Betrieb in Zahlen")}">
      ${figure(time(o.first_preparation_seconds.median), T("until the first step is prepared", "bis der erste Schritt vorbereitet ist"), o.first_preparation_seconds)}
      ${figure(days(o.first_letter_days.median), T("until the first letter is sent", "bis zum ersten versandten Brief"), o.first_letter_days)}
      ${figure(days(o.cover_decision_days.median), T("until cover is decided", "bis zum Deckungsentscheid"), o.cover_decision_days)}
      ${figure(days(o.cycle_days.median), T("from receipt to closing", "vom Eingang bis zum Abschluss"), o.cycle_days)}</section>
    <section class="cp-ops-open"><p class="cp-ops-line"><b>${o.open}</b> ${T(o.open === 1 ? "open case" : "open cases", o.open === 1 ? "offener Fall" : "offene Fälle")} <span class="cp-muted">· ${T("by age", "nach Alter")}</span></p>${bar}
      <p class="cp-muted cp-ops-facts">${T("Last 30 days", "Letzte 30 Tage")}: ${o.opened_30_days} ${T("opened", "eröffnet")} · ${o.closed_30_days} ${T("closed", "abgeschlossen")} · ${T("opened again", "wieder eröffnet")}: ${share(o.reopened, o.closed_ever)}
        · ${T("letters approved as prepared", "Briefe wie vorbereitet freigegeben")}: ${share(o.letters_approved_as_written, o.letters_approved)} · ${T("cover refused", "Deckung abgelehnt")}: ${share(o.cover_refused, o.cover_decided)}</p></section>`;
}
async function renderAuswertung() {
  const a = await api("/api/auswertung");
  const n = (v) => (v === null || v === undefined ? "—" : esc(String(v)));
  const reason = (k) => (k === "none" ? T("no reason given", "ohne Angabe") : REASONS[k] ? T(REASONS_EN[k], REASONS[k]) : String(k).replace(/_/g, " "));
  const kv = (o, name = (k) => String(k).replace(/_/g, " ")) => Object.entries(o || {}).map(([k, v]) => `${esc(name(k))} ${v}`).join(" · ") || "—";
  // a time is said in the unit a person reads, and never where it cannot be one (a seeded case with no real run)
  const span = (sec) => (sec == null || sec > 86400 || sec < 1 ? "—" : sec >= 90 ? `${Math.round(sec / 60)} ${T("min", "Min")}` : `${Math.round(sec)} s`);
  // the cases something was done in; the others are one line, not forty rows of zeros
  const active = a.cases.filter((c) => c.interventions || c.sources_opened || c.same_correction_again || c.handling_seconds != null || c.letter_changed_ratio);
  const rows = active.map((c) => `<tr><td><code>${esc(c.case)}</code></td><td>${c.interventions}</td><td>${kv(c.interventions_by_reason, reason)}</td><td>${n(c.letter_changed_ratio)}</td>
    <td>${c.handling_seconds == null ? "—" : span(c.handling_seconds)}</td><td>${c.sources_opened}</td><td>${c.same_correction_again}</td><td>${span(c.run_seconds)}</td>
    <td>${c.tokens_noncached >= 500 ? `${Math.round(c.tokens_noncached / 1000)}k` : "—"}</td></tr>`).join("");
  const figure = (value, label) => `<div class="cp-figure"><b>${n(value)}</b><span>${label}</span></div>`;
  $("#app").innerHTML = `<main class="cp-main cp-evaluation${pageIn()}"><h1 class="cp-title">${T("Evaluation", "Auswertung")}</h1>
    <section class="cp-today cp-figures" aria-label="${T("In figures", "In Zahlen")}">
      ${figure(a.total.cases, T("cases", "Fälle"))}${figure(a.total.cases_used, T("worked on", "bearbeitet"))}
      ${figure(a.total.interventions_per_used_case, T("corrections per case worked on", "Korrekturen pro bearbeitetem Fall"))}${figure(a.total.same_correction_again, T("same correction repeated", "gleiche Korrektur wiederholt"))}</section>
    <p class="cp-muted cp-eval-note">${T("From ordinary use, without questionnaires. Content-free: cases appear only as pseudonyms.", "Aus der normalen Arbeit, ohne Fragebogen. Ohne Inhalte: Fälle erscheinen nur als Pseudonyme.")}
      <a class="cp-link cp-quiet-link" href="/api/auswertung" download="auswertung.json">${T("Export", "Export")}</a> · <a class="cp-link cp-quiet-link" href="/api/manifest" download="manifest.json">${T("Manifest", "Manifest")}</a></p>
    ${operationsView(a.operations)}
    <h2 class="cp-section">${T("Cases worked on", "Bearbeitete Fälle")} · ${active.length}</h2>
    ${active.length ? `<table class="cp-table"><thead><tr><th>${T("Case", "Fall")}</th><th>${T("Corrections", "Eingriffe")}</th><th>${T("Reasons", "Gründe")}</th>
      <th>${T("Letter changed", "Brief geändert")}</th><th>${T("Handling", "Bearbeitung")}</th><th>${T("Sources opened", "Quellen geöffnet")}</th><th>${T("Repeated", "Wiederholt")}</th><th>${T("Preparation", "Vorbereitung")}</th><th>Tokens</th></tr></thead>
      <tbody>${rows}</tbody></table>` : `<p class="cp-muted">${T("No use recorded yet.", "Noch keine Nutzung erfasst.")}</p>`}
    ${a.cases.length > active.length ? `<p class="cp-muted cp-eval-rest">${T(`${a.cases.length - active.length} further cases without any recorded work.`, `${a.cases.length - active.length} weitere Fälle ohne erfasste Arbeit.`)}</p>` : ""}</main>`;
}

// What the Knowledge items and the areas are called where a handler meets them: never an internal id or an English word.
const CHANGE_DE = { created: "erstellt", refined: "verfeinert", active: "freigegeben", retired: "zurückgezogen", candidate: "wieder Vorschlag" };
const changeText = (c) => {
  const m = String(c || "").match(/^(created|refined|active|retired|candidate)(?::\s*(.*))?$/);
  if (!m || LANG !== "de") return String(c || "");
  return m[2] ? `${CHANGE_DE[m[1]]}: ${m[2]}` : CHANGE_DE[m[1]];
};
const byWhom = (by) => (by === "build" ? T("shipped with the build", "mit der Version ausgeliefert") : by || "");
// A process family as handlers call it: the area's own name, or the area that took over its intake («Mietmangel»).
function familyName(family) {
  const all = S.workflows || [];
  const own = all.find((w) => w.id === family);
  const over = all.find((w) => (w.supersedes || []).includes(family));
  const w = (own && own.area) ? own : over || own;
  if (w && w.example) return T("Example process (synthetic)", "Beispielprozess (synthetisch)");
  return w ? (w.short_title || w.title) : T("another process", "anderer Prozess");
}

async function renderKnowledge() {
  const [data, cases, workflows, review, byUse] = await Promise.all([api("/api/knowledge"), api("/api/cases"), api("/api/workflows"),
    S.mayReview ? api("/api/review").catch(() => null) : Promise.resolve(null),
    S.mayReview ? api("/api/review/by-use").catch(() => null) : Promise.resolve(null)]);
  S.workflows = workflows.workflows;
  const titles = Object.fromEntries(cases.cases.map((c) => [c.id, c.title]));
  const caseName = (id) => titles[id] || T("a deleted case", "ein gelöschter Fall");
  const byItem = {};
  for (const use of data.uses) (byItem[use.knowledge_id] = byItem[use.knowledge_id] || []).push(use);
  // One entry per item as handlers know it: the same item seeded for an area and the intake it replaced is one entry.
  const groups = {};
  for (const item of data.knowledge) {
    const name = familyName(item.family);
    const key = `${item.kind}|${item.content.title || item.content.question || item.content.text}`;
    const group = (groups[name] = groups[name] || {});
    const entry = group[key];
    if (!entry) group[key] = { ...item, ids: [item.id], uses: [...(byItem[item.id] || [])], stats: { ...item.stats } };
    else {
      entry.ids.push(item.id);
      entry.uses.push(...(byItem[item.id] || []));
      for (const k of ["uses", "confirmed", "not_found", "contradicted"]) entry.stats[k] += item.stats[k] || 0;
    }
  }
  S.knowledgeView = { entries: Object.values(groups).flatMap((g) => Object.values(g)), caseName };
  const card = (k) => `<article class="cp-card" data-story-row="${raw(k.ids[0])}" style="padding:16px 18px;display:grid;gap:8px;align-content:start">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><span class="cp-chip ${k.status === "active" ? "good" : k.status === "retired" ? "" : "wait"}">${esc(word(k.status))}</span>
        <span class="cp-chip">${esc(word(k.kind))}</span>${k.refines ? "" : `<span class="cp-chip">v${k.version}</span>`}${k.refines ? `<span class="cp-chip wait">${(() => { const t = data.knowledge.find((x) => x.id === k.refines); return t ? T(`refines v${t.version} → v${t.version + 1}`, `verfeinert v${t.version} → v${t.version + 1}`) : T("refinement", "Verfeinerung"); })()}</span>` : ""}
        ${k.review_suggested ? `<span class="cp-chip bad">${T("review suggested: contradicted often", "Prüfung empfohlen: oft widersprochen")}</span>` : ""}</div>
      <b>${esc(k.content.title || k.content.question || k.content.text)}</b>${k.content.why ? `<span class="cp-muted">${esc(k.content.why)}</span>` : ""}
      ${k.applies_when_text ? `<span class="cp-muted">${T("Applies when", "Gilt, wenn")}: ${esc(k.applies_when_text)}</span>` : ""}
      <span>${T(`Used ${k.stats.uses} · confirmed ${k.stats.confirmed} · not found ${k.stats.not_found} · contradicted ${k.stats.contradicted}`,
                `${k.stats.uses}× verwendet · ${k.stats.confirmed}× bestätigt · ${k.stats.not_found}× nicht gefunden · ${k.stats.contradicted}× widersprochen`)}</span>
      ${(k.evidence || []).filter((e) => e.quote).slice(0, 2).map((e) => `<span class="cp-muted">“${esc(e.quote)}” — <a href="#/case/${raw(e.case_id)}/claim_reader">${esc(caseName(e.case_id))}</a></span>`).join("")}
      ${seededNote(k) ? `<span class="cp-muted">${esc(seededNote(k))}</span>` : `<span class="cp-muted">${k.origin.kind === "case_edit" ? T("Learned from a case worker’s change in", "Gelernt aus einer Änderung in der Fallbearbeitung, im Fall") : T("Learned by the result checker in", "Gelernt vom Ergebnisprüfer im Fall")} <a href="#/case/${raw(k.origin.case_id)}/process_builder">${esc(caseName(k.origin.case_id))}</a></span>`}
      ${k.uses.length ? `<span>${T("Cases", "Fälle")}: ${k.uses.map((u) => `<a href="#/case/${raw(u.case_id)}/document_finder">${esc(caseName(u.case_id))}</a> <span class="cp-chip ${u.outcome === "present" ? "good" : u.outcome === "contradicted" ? "bad" : ""}">${esc(word(u.outcome))}</span>`).join(" ")}</span>` : ""}
      <details><summary class="cp-link">${T("History", "Verlauf")}</summary><ul class="cp-log">${k.history.map((h) => `<li><b>v${h.version}</b><span>${esc(changeText(h.change))}${h.by ? ` · ${esc(byWhom(h.by))}` : ""} · ${dateText(h.at)}</span></li>`).join("")}</ul></details>
      ${review && review.may_review && k.status !== "candidate" ? `<details class="cp-recall" data-recall="${raw(k.ids.join(","))}"><summary class="cp-link">${T("Letters resting on it", "Briefe, die darauf beruhen")}</summary><ul class="cp-log"><li class="cp-muted">…</li></ul></details>` : ""}
      ${k.status !== "active" && k.status !== "retired" ? replayLine(k, data.knowledge, caseName) : ""}
      <div class="row" style="display:flex;gap:10px">${k.status !== "active" && k.status !== "retired" ? (replayCurrent(k, data.knowledge)
          ? `<button class="cp-button primary" data-activate="${raw(k.ids.join(","))}">${k.refines ? T("Apply refinement", "Verfeinerung übernehmen") : T("Activate", "Freigeben")}</button>`
          : `<button class="cp-button primary" data-replay="${raw(k.ids.join(","))}">${T("Replay", "Nachspielen")}</button>`) : ""}
        ${k.status !== "retired" ? `<button class="cp-button" data-retire="${raw(k.ids.join(","))}">${T("Retire", "Zurückziehen")}</button>` : ""}</div></article>`;
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const sections = Object.entries(groups).sort(([a], [b]) => a.localeCompare(b, "de")).map(([name, entries]) => {
    const items = Object.values(entries), uses = items.reduce((n, k) => n + k.stats.uses, 0);
    return `<h2 class="cp-section">${esc(name)} <span class="cp-muted">· ${T(`${items.length} items · ${uses} uses`, `${plural(items.length, "Eintrag", "Einträge")} · ${plural(uses, "Verwendung", "Verwendungen")}`)}</span></h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px;align-items:start">${items.map(card).join("")}</div>`;
  }).join("");
  $("#app").innerHTML = `<main class="cp-main cp-knowledge${pageIn()}"><h1 class="cp-title">${T("Knowledge", "Wissen")}</h1>
    ${sections ? tabPicture("knowledge", 320) : ""}
    ${review && review.may_review ? reviewTable(review) + reviewByUse(byUse) : ""}
    ${review && review.may_review ? `<h2 class="cp-section cp-learned">${T("Learned from cases", "Aus Fällen gelernt")}</h2>` : ""}
    <p class="cp-muted">${T("What CasePath learned from earlier cases and case workers’ changes. Active items shape new cases; candidates are checked as suggestions until a person activates them.",
      "Was CasePath aus früheren Fällen und aus Änderungen der Fallbearbeitung gelernt hat. Freigegebene Einträge prägen neue Fälle; Vorschläge werden nur als Vorschlag geprüft, bis ein Mensch sie freigibt.")}</p>
    ${sections || `<p class="cp-empty">${T("Nothing learned yet. Knowledge appears after cases are prepared or a case worker saves a change for similar cases.", "Noch nichts gelernt. Wissen entsteht, wenn Fälle vorbereitet werden oder eine Änderung für ähnliche Fälle gespeichert wird.")}</p>`}</main>`;
  mountStory();
  for (const b of document.querySelectorAll("#story-show")) b.addEventListener("click", () => setPicture(true, b.dataset.kind));
  const each = (ids, path, reason) => Promise.all(ids.split(",").map((id) => api(`/api/knowledge/${id}/${path}`, { method: "POST", body: JSON.stringify({ reason }) })));
  for (const b of document.querySelectorAll("[data-replay]")) b.addEventListener("click", async () => {  // without a model: what this version would change
    b.disabled = true;
    await each(b.dataset.replay, "replay").catch(() => {});
    renderKnowledge();
  });
  // the recall: every approved letter whose case carried this rule when it was approved («Stand bei Freigabe»), read when opened
  for (const d of document.querySelectorAll("[data-recall]")) d.addEventListener("toggle", async () => {
    if (!d.open || d.dataset.loaded) return;
    d.dataset.loaded = "1";
    const found = await Promise.all(d.dataset.recall.split(",").map((id) => api(`/api/recall?knowledge=${encodeURIComponent(id)}`).catch(() => ({ rows: [] }))));
    d.querySelector("ul").innerHTML = recallRows(found.flatMap((x) => x.rows || []));
  });
  for (const b of document.querySelectorAll("[data-activate]")) b.addEventListener("click", async () => { await each(b.dataset.activate, "activate", T("approved in Knowledge", "im Wissen freigegeben")).catch(() => {}); renderKnowledge(); });
  for (const b of document.querySelectorAll("[data-retire]")) b.addEventListener("click", async () => { await each(b.dataset.retire, "retire", T("retired in Knowledge", "im Wissen zurückgezogen")); renderKnowledge(); });
}

// The rows of a recall (GET /api/recall): which case, which letter, approved when and by whom, sent or not.
function recallRows(rows) {
  if (!rows.length) return `<li class="cp-muted">${T("No approved letter rests on it.", "Kein freigegebener Brief beruht darauf.")}</li>`;
  return rows.map((r) => `<li><a href="#/case/${raw(r.case)}/overview">${esc(r.reference || r.title || r.case)}</a> <span>${esc(r.letter || r.form || "")} · ${T("approved", "freigegeben")} ${dateText(r.approved_at).slice(0, 10)}${r.approved_by ? ` · ${esc(r.approved_by)}` : ""}
    · ${r.sent.length ? `${T("sent", "versandt")} ${r.sent.map((x) => esc(dateText(x.date))).join(", ")}` : `<b>${T("not sent yet", "noch nicht versandt")}</b>`}</span></li>`).join("");
}

// ---------- review of the legal content (Wissen → Rechtsgebiete) ----------
// A jurist opens one area, sees each element in the words the handler or customer will see beside the passage it rests on
// and its official source, and marks it: geprüft, Änderung nötig …, Frage …. An area whose elements are all geprüft is
// freigegeben; the handler's screen says so (process/review.py).
const REVIEW_WORD = lazy(() => ({ geprueft: T("checked", "geprüft"), aenderung: T("change needed", "Änderung nötig"), frage: T("question", "Frage"),
                      geaendert: T("changed since review", "geändert seit Prüfung"), offen: T("open", "offen") }));
const REVIEW_CHIP = { geprueft: "good", aenderung: "bad", frage: "wait", geaendert: "wait" };
const reviewDay = (at) => dateText(at).slice(0, 10);
function reviewState(status) {
  const cls = status.state === "freigegeben" ? "released" : status.state === "in_pruefung" ? "busy" : "";
  return `<span class="cp-rv-state ${cls}">${esc(status.state === "offen" ? T("not released", "noch nicht freigegeben") : status.label)}</span>`;
}
// Release by use: the reviewed elements approved letters rest on, those not yet checked first, each reviewed in the
// latest letter that carries it (GET /api/review/by-use).
function reviewByUse(use) {
  if (!use) return "";
  const open = use.rows.filter((r) => r.state !== "geprueft");
  const head = `<h3 class="cp-rv-use-head">${T("Review first: used in approved letters", "Zuerst prüfen: in freigegebenen Briefen verwendet")} <span class="cp-muted">· ${T(`${use.checked} of ${use.elements} checked`, `${use.checked} von ${use.elements} geprüft`)}</span></h3>`;
  if (!use.elements) return `${head}<p class="cp-muted cp-rv-use-none">${T("No letter has been approved yet. A prepared letter is reviewed from its case («This letter: … checked»).", "Noch ist kein Brief freigegeben. Ein vorbereiteter Brief wird aus seinem Fall heraus geprüft («Dieser Brief: … geprüft»).")}</p>`;
  if (!open.length) return `${head}<p class="cp-muted cp-rv-use-none">${T("Every element approved letters rest on is checked.", "Alle Bausteine, auf denen freigegebene Briefe beruhen, sind geprüft.")}</p>`;
  return `${head}<ul class="cp-log cp-rv-use">${open.slice(0, 12).map((r) => `<li><a href="#/knowledge/brief/${encodeURIComponent(r.case)}">${esc(r.title)}</a>
    <span class="cp-muted">${T(`${r.letters} ${r.letters === 1 ? "letter" : "letters"}, ${r.sent} sent`, `${r.letters} ${r.letters === 1 ? "Brief" : "Briefe"}, davon ${r.sent} versandt`)}${r.state !== "offen" ? ` · ${esc(REVIEW_WORD()[r.state] || r.state_text)}` : ""}</span></li>`).join("")}</ul>
    ${open.length > 12 ? `<p class="cp-muted">${T(`and ${open.length - 12} more`, `und ${open.length - 12} weitere`)}</p>` : ""}`;
}
function reviewTable(review) {
  const n = (v, cls = "") => `<td class="num ${v ? cls : "zero"}">${v}</td>`;
  return `<h2 class="cp-section" id="rechtsgebiete">${T("Legal areas", "Rechtsgebiete")}</h2>
    <p class="cp-rv-intro">${T("Export requested changes and questions", "Änderungen und Fragen exportieren")}: <a class="cp-link cp-quiet-link" href="/api/review/export?format=md">Markdown</a> · <a class="cp-link cp-quiet-link" href="/api/review/export?format=json">JSON</a></p>
    <table class="cp-table cp-rv-table"><thead><tr><th>${T("Area", "Gebiet")}</th><th>${T("State", "Stand")}</th><th class="num">${T("checked", "geprüft")}</th><th class="num">${T("open", "offen")}</th>
      <th class="num">${T("change needed", "Änderung nötig")}</th><th class="num">${T("questions", "Fragen")}</th></tr></thead><tbody>${review.rows.map((r) => `<tr class="${r.kind === "area" ? "" : "cp-rv-common"}">
      <td><a href="#/knowledge/gebiet/${encodeURIComponent(r.id)}"><b>${esc(r.title)}</b></a><br><small class="cp-muted">${esc(r.subtitle || "")}</small></td><td>${reviewState(r.status)}</td>
      ${n(r.status.counts.geprueft)}${n(r.status.counts.offen)}${n(r.status.counts.aenderung, "flag")}${n(r.status.counts.frage)}</tr>`).join("")}</tbody></table>`;
}
// One area's elements, or (id «brief:<case>») the elements one case's letter rests on, beside that letter.
const reviewUrl = (id) => (/^brief:/.test(id) ? `/api/cases/${encodeURIComponent(id.slice(6))}/letter-review` : `/api/review/${encodeURIComponent(id)}`);
async function renderReview(id) {
  try { S.reviewRow = await api(reviewUrl(id)); } catch (error) {
    $("#app").innerHTML = `<main class="cp-main cp-review"><p class="cp-rv-back"><a class="cp-link cp-quiet-link" href="#/knowledge">${T("Legal areas", "Rechtsgebiete")}</a></p><p class="cp-empty">${esc(plainError(error.message))}</p></main>`;
    return;
  }
  drawReview();
}
// A passage as a jurist reads it: the article first, then its words, the official text one click away.
function lawRow(r, linked) {
  const title = `${r.source || ""}${r.version ? `, ${r.version}` : ""}`;
  const source = r.url && !linked ? `<a href="${raw(r.url)}" target="_blank" rel="noopener" title="${esc(title)}">${esc(r.link || r.source || "")}</a>` : "";
  return `<div class="cp-rv-passage"><p class="cp-rv-cite"><b>${esc(r.cite)}</b>${source ? ` ${source}` : ""}${r.verified ? "" : ` <span class="cp-flag">${T("not checked against the official text", "nicht am amtlichen Text geprüft")}</span>`}</p>
    <p class="cp-rv-words">«${esc(r.passage)}»</p></div>`;
}
function reviewElement(el, may) {
  const m = el.mark, editing = S.reviewing && S.reviewing.key === el.key ? S.reviewing.mark : null;
  const others = el.used_in.filter((t) => t !== S.reviewRow.title);
  const who = m && el.state !== "offen" ? `<span class="cp-rv-who">${el.state === "geaendert" ? `${T("earlier", "früher")} ${esc(REVIEW_WORD()[m.mark])}: ` : ""}${esc(m.reviewer)}, ${reviewDay(m.at)}</span>` : "";
  const said = m && el.state !== "offen" && (m.comment || m.suggestion) ? `<p class="cp-rv-meta">${m.comment ? `«${esc(m.comment)}»` : ""}${m.suggestion ? `${m.comment ? " · " : ""}${T("Wording", "Vorschlag")}: «${esc(m.suggestion)}»` : ""}</p>` : "";
  const form = editing ? `<form class="cp-rv-form" data-rv-form="${raw(el.key)}" data-mark="${editing}">
      <label>${editing === "aenderung" ? T("What must change", "Was zu ändern ist") : T("Your question", "Ihre Frage")}<textarea name="comment" rows="2" maxlength="4000" required></textarea></label>
      ${editing === "aenderung" ? `<label>${T("Proposed wording (optional)", "Vorschlag für den Wortlaut (freiwillig)")}<textarea name="suggestion" rows="2" maxlength="4000"></textarea></label>` : ""}
      <span><button class="cp-button cp-small">${T("Save", "Speichern")}</button> <button type="button" class="cp-link cp-quiet-link" data-rv-cancel>${T("cancel", "abbrechen")}</button></span></form>` : "";
  const actions = may ? `<div class="cp-rv-actions">
      <button class="cp-button cp-small" data-rv-mark="${raw(el.key)}" aria-pressed="${el.state === "geprueft"}">${T("checked", "geprüft")}</button>
      <button class="cp-button cp-small" data-rv-open="aenderung" data-key="${raw(el.key)}" aria-pressed="${el.state === "aenderung"}">${T("Change needed …", "Änderung nötig …")}</button>
      <button class="cp-button cp-small" data-rv-open="frage" data-key="${raw(el.key)}" aria-pressed="${el.state === "frage"}">${T("Question …", "Frage …")}</button>${who}</div>${form}` : who ? `<p class="cp-rv-meta">${who}</p>` : "";
  return `<article class="cp-rv-el ${el.state}" data-review="${raw(el.key)}">
    <div class="cp-rv-main"><h3>${esc(el.title)}${el.state !== "offen" ? ` <span class="cp-chip ${REVIEW_CHIP[el.state] || ""}">${esc(REVIEW_WORD()[el.state])}</span>` : ""}</h3>
      ${el.lines.length ? `<dl class="cp-rv-lines">${el.lines.map((l) => `<dt>${esc(l.label)}</dt><dd${l.pre ? ' class="pre"' : ""}>${esc(l.text)}</dd>`).join("")}</dl>` : ""}
      ${others.length ? `<p class="cp-rv-shared">${T("Also applies to", "Gilt auch für")}: ${esc(others.slice(0, 3).join(", "))}${others.length > 3 ? T(` and ${others.length - 3} more`, ` und ${others.length - 3} weitere`) : ""}</p>` : ""}
      ${el.questions.map((q) => `<p class="cp-rv-q"><b>${T("Open question", "Offene Frage")}</b> ${esc(q)}</p>`).join("")}
      ${said}${actions}</div>
    <div class="cp-rv-law">${el.law.map((r, n) => lawRow(r, el.law.slice(0, n).some((x) => x.url === r.url))).join("")  /* each official text linked once */
      || `<p class="cp-muted cp-rv-nolaw">${T("rests on no article", "ohne Gesetzesstelle")}</p>`}</div></article>`;
}
function drawReview() {
  const d = S.reviewRow, c = d.status.counts, only = Boolean(S.reviewOnlyOpen);
  const groups = d.groups.map((g) => ({ ...g, shown: g.elements.filter((el) => !only || el.state !== "geprueft") })).filter((g) => g.shown.length);
  $("#app").innerHTML = `<main class="cp-main cp-review${pageIn()}">
    <p class="cp-rv-back">${d.kind === "letter" ? `<a class="cp-link cp-quiet-link" href="#/case/${raw(d.case)}/overview">${T("Back to the case", "Zurück zum Fall")}</a> · ` : ""}<a class="cp-link cp-quiet-link" href="#/knowledge">${T("Legal areas", "Rechtsgebiete")}</a></p>
    <h1 class="cp-title">${esc(d.title)}</h1>
    <p class="cp-rv-sub">${esc(d.subtitle || "")} · ${reviewState(d.status)}</p>
    <p class="cp-rv-bar"><span>${T(`${c.total} elements · ${c.geprueft} checked · ${c.offen} open · ${c.aenderung} change needed · ${c.frage} questions`,
      `${c.total} Elemente · ${c.geprueft} geprüft · ${c.offen} offen · ${c.aenderung} Änderung nötig · ${c.frage} ${c.frage === 1 ? "Frage" : "Fragen"}`)}</span>
      <label class="cp-rv-filter"><input type="checkbox" id="rv-only-open" ${only ? "checked" : ""}> ${T("open only", "nur offene")}</label>
      ${d.kind === "letter" ? "" : `<a class="cp-link cp-quiet-link" href="/api/review/${encodeURIComponent(d.id)}/pruefpaket" target="_blank" rel="noopener">${T("Review pack (print)", "Prüfpaket")}</a>`}</p>
    ${d.kind === "letter" ? `<details class="cp-rv-letter" open><summary class="cp-link">${T("The letter as prepared", "Der Brief, wie er vorbereitet ist")}</summary><pre>${esc(d.letter)}</pre></details>
      <p class="cp-muted">${T("Below: every reviewed element this letter rests on. A mark applies wherever the element is used.", "Darunter: jeder geprüfte Baustein, auf dem dieser Brief beruht. Eine Markierung gilt überall, wo der Baustein verwendet wird.")}</p>` : ""}
    ${d.may_review ? "" : `<p class="cp-muted">${T("View only: marks are set by the people named to review.", "Nur Ansicht: markieren dürfen die für die Prüfung bestimmten Personen.")}</p>`}
    ${d.questions.length ? `<div class="cp-rv-areaq"><b>${T("Open questions on the area", "Offene Fragen zum Gebiet")}</b>${d.questions.map((q) => `<p>${esc(q)}</p>`).join("")}</div>` : ""}
    ${groups.map((g) => `<h2 class="cp-section cp-rv-group">${esc(g.title)} <span class="cp-muted">· ${g.shown.length}${only && g.shown.length !== g.elements.length ? ` ${T("of", "von")} ${g.elements.length}` : ""}</span></h2>
      ${g.shown.map((el) => reviewElement(el, d.may_review)).join("")}`).join("") || `<p class="cp-empty">${T("Every element is checked.", "Alle Elemente sind geprüft.")}</p>`}</main>`;
  bindReview();
}
async function saveMark(key, mark, comment = "", suggestion = "") {
  const el = S.reviewRow.groups.flatMap((g) => g.elements).find((x) => x.key === key);
  const [file, ...rest] = key.split(":");
  const y = window.scrollY;
  try {
    await api(`/api/review/${encodeURIComponent(file)}/${encodeURIComponent(rest.join(":"))}`, { method: "POST", body: JSON.stringify({ mark, comment, suggestion, sha256: el && el.sha256 }) });
    S.reviewing = null;
    S.reviewRow = await api(reviewUrl(S.reviewRow.id));
    drawReview();
    window.scrollTo(0, y);
  } catch (error) { alert(error.message); }
}
function bindReview() {
  const only = $("#rv-only-open");
  if (only) only.addEventListener("change", () => { const y = window.scrollY; S.reviewOnlyOpen = only.checked; drawReview(); window.scrollTo(0, y); });
  for (const b of document.querySelectorAll("[data-rv-mark]")) b.addEventListener("click", () => saveMark(b.dataset.rvMark, "geprueft"));
  for (const b of document.querySelectorAll("[data-rv-open]")) b.addEventListener("click", () => {
    const y = window.scrollY;
    S.reviewing = { key: b.dataset.key, mark: b.dataset.rvOpen };
    drawReview(); window.scrollTo(0, y);
    const t = $(`[data-rv-form="${CSS.escape(b.dataset.key)}"] textarea`);
    if (t) t.focus({ preventScroll: true });
  });
  for (const b of document.querySelectorAll("[data-rv-cancel]")) b.addEventListener("click", () => { const y = window.scrollY; S.reviewing = null; drawReview(); window.scrollTo(0, y); });
  for (const f of document.querySelectorAll("[data-rv-form]")) f.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(f);
    saveMark(f.dataset.rvForm, f.dataset.mark, String(data.get("comment") || ""), String(data.get("suggestion") || ""));
  });
}

// ---------- routing ----------
async function route() {
  const next = parseRoute();
  // what arrives is shown arriving, once: another case (from the right when the reader went on), or the list
  if (next.view === "case" && (S.route.view !== "case" || next.id !== S.route.id)) { S.arrive = S.arriveNext ? "next" : "open"; S.barWas = null; }
  if (next.view === "cases" && S.route.view !== "cases") S.listFresh = true;
  // a tab or a page arrives once: its blocks and rows come in in the order they are read
  if (next.view === "case" && (next.tab || "overview") !== "overview" && (S.route.view !== "case" || next.id !== S.route.id || next.tab !== S.route.tab)) S.tabIn = true;
  if (["knowledge", "review", "auswertung"].includes(next.view) && (next.view !== S.route.view || next.id !== S.route.id)) S.pageIn = true;
  if (next.view !== "case" || next.id !== S.justFinished) S.justFinished = null;
  S.arriveNext = false;
  if (next.view !== "case" || next.id !== MEASURE.caseId) measureLeave();  // the case is left: its measured span ends
  if (next.view !== "case" || next.id !== S.route.id) Object.assign(S, { data: null, pages: {}, file: null, step: null, editing: false, lastEdit: null, events: [], follow: true, message: "", shown: new Set(), litKey: null });
  const moved = next.view !== S.route.view || next.id !== S.route.id || next.tab !== S.route.tab;
  if (moved) { S.moreOpen = false; S.overviewSource = false; }  // a menu and an opened source belong to the page they were opened on
  // a case opened from the list grows out of its row, and goes back into it: the name travels, the rest changes around it
  const rowOf = (id) => document.querySelector(`.cp-list a[href^="#/case/${CSS.escape(id)}/"]`);
  const opened = next.view === "case" && S.route.view === "cases" ? rowOf(next.id) : null, left = next.view === "cases" && S.route.view === "case" ? S.route.id : null;
  const show = async () => {
    rowPeekHide(); S.peekRow = null;
    if (next.view !== "case" || next.id !== S.route.id) { S.xPin = null; xClear(); }
    S.route = next;
    if (moved) window.scrollTo(0, 0);  // what is opened is read from its top
    renderTop();
    if (next.view !== "case") dropStory();
    placeAttention(false);
    try {
      if (next.view === "case") { if (S.data) await renderCase(); else await loadCase(); }
      else if (next.view === "knowledge") await renderKnowledge();
      else if (next.view === "review") await renderReview(next.id);
      else if (next.view === "auswertung") await renderAuswertung();
      else await renderCases();
    } catch (error) {
      $("#app").innerHTML = `<main class="cp-main"><p class="cp-error">${esc(error.message)}</p></main>`;
    }
    const back = left && rowOf(left);
    if (back) back.style.viewTransitionName = "cp-case";
    showNotices();
  };
  if ((opened || left) && document.startViewTransition && !reducedMotion()) {
    if (opened) opened.style.viewTransitionName = "cp-case";
    document.documentElement.classList.add("cp-morph");
    try { await document.startViewTransition(show).finished; } catch (error) { /* a transition cut short: the page is there all the same */ }
    document.documentElement.classList.remove("cp-morph");
    const row = left && rowOf(left);
    if (row) row.style.viewTransitionName = "";
  } else await show();
}

(async () => {
  try { const me = await api("/api/me"); S.me = me.user; S.mayReview = Boolean(me.may_review); MEASURE.allowed = Boolean(me.time_measure); } catch (error) { S.me = ""; S.mayReview = false; }
  document.addEventListener("click", (event) => {  // the way through the cases: from the list, the header and a settled case
    const b = event.target.closest && event.target.closest("#walk-start, #skip-case, #next-case");
    if (!b || b.disabled) return;
    b.disabled = true;
    nextCase(b.id === "walk-start").catch((error) => { S.message = error.message; S.messageOk = false; b.disabled = false; });
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest || !event.target.closest("#measure-toggle")) return;
    MEASURE.on = !MEASURE.on;
    try { sessionStorage.setItem("cp-measure", MEASURE.on ? "1" : ""); } catch (error) { /* this session only, in memory */ }
    if (MEASURE.on) measureTouch(); else measureLeave();
    renderTop();
  });
  document.addEventListener("click", (event) => { if (event.target.closest && event.target.closest("#keys-open")) keysCard(true); });
  document.addEventListener("keydown", (event) => {
    const typing = event.target.closest && event.target.closest("input, textarea, select, [contenteditable], [data-editable]");
    if (event.key === "Escape" && document.getElementById("cp-keys")) { keysCard(false); return; }
    if (event.key === "Escape" && document.getElementById("xstage")) { S.xPin = null; xClear(); return; }
    if (event.key === "Escape" && document.querySelector("#overview-source.cp-src-float")) { S.overviewSource = false; renderCase(); return; }
    if (!typing && !event.ctrlKey && !event.metaKey && !event.altKey) {
      // the keys that work everywhere: the help, the list, and in a case its tabs, the next case and the large picture
      if (event.key === "?") { event.preventDefault(); keysCard(!document.getElementById("cp-keys")); return; }
      if (document.getElementById("cp-keys")) return;
      if (event.key === "/" && S.route.view === "cases" && $("#list-search")) { event.preventDefault(); $("#list-search").focus(); return; }
      if (event.key === "v" && S.story && !S.story.live) { event.preventDefault(); storyBig(!S.storyBig); return; }
      if (S.route.view === "case" && S.data && !S.storyBig) {
        const tabs = [...document.querySelectorAll("#top .cp-tabs a[href^='#/case/']")];
        if (/^[1-9]$/.test(event.key) && tabs[Number(event.key) - 1]) { event.preventDefault(); location.hash = tabs[Number(event.key) - 1].getAttribute("href"); return; }
        if (event.key === "n") { const b = document.querySelector("#next-case:not(:disabled), #skip-case:not(:disabled)"); if (b) { event.preventDefault(); b.click(); } return; }
        if (event.key === "l") { event.preventDefault(); location.hash = "#/cases"; return; }
      }
    }
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && S.route.view === "case") {  // the card's one primary, from the keyboard
      const b = document.querySelector(".cp-prepared .cp-button.primary:not(:disabled)");
      if (b) { event.preventDefault(); b.click(); }
      return;
    }
    if (typing || event.ctrlKey || event.metaKey || event.altKey || S.route.view !== "cases") return;
    const rows = [...document.querySelectorAll("table.cp-cases tbody tr")];
    if (!rows.length || !["ArrowDown", "ArrowUp", "j", "k", "Enter"].includes(event.key)) return;
    const at = rows.findIndex((r) => r.classList.contains("cp-row-on"));
    if (event.key === "Enter") { const a = at >= 0 && rows[at].querySelector("a[href^='#/case/']"); if (a) location.hash = a.getAttribute("href"); return; }
    event.preventDefault();
    const to = Math.max(0, Math.min(rows.length - 1, at < 0 ? 0 : at + (["ArrowDown", "j"].includes(event.key) ? 1 : -1)));
    if (at >= 0) rows[at].classList.remove("cp-row-on");
    rows[to].classList.add("cp-row-on"); rows[to].scrollIntoView({ block: "nearest" });
    clearTimeout(S.peekTimer); S.peekTimer = setTimeout(() => rowPeekShow(rows[to]), 160);  // the keyboard's row says its step and its reason too
  });
  try { const health = await api("/api/health"); S.canUpload = health.uploads !== false; S.translateMode = (health.translate || {}).mode || "off";
    if ((health.house || {}).name) { Object.assign(HOUSE, health.house); PARTY_DE.versicherer = HOUSE.name; } } catch (error) { S.canUpload = true; }
  window.addEventListener("hashchange", route);
  route();
})();

// The peek of a list row: one small card under the row the hand rests on (after a moment) or the keyboard stands on.
// It is filled from what the row already holds, stands over the page, and goes when the hand or the page moves.
function rowPeekShow(row) {
  rowPeekHide();
  const src = row && row.querySelector(".cp-row-peek"), cell = row && row.querySelector("td.cp-next");
  if (!src || !cell || S.route.view !== "cases") return;
  const card = document.createElement("div");
  card.id = "cp-peek";
  card.innerHTML = src.innerHTML;
  document.body.appendChild(card);
  const r = cell.getBoundingClientRect(), below = row.getBoundingClientRect().bottom;
  const top = below + card.offsetHeight + 12 > window.innerHeight ? row.getBoundingClientRect().top - card.offsetHeight - 6 : below - 4;
  Object.assign(card.style, { left: `${Math.max(12, Math.min(r.left - 14, window.innerWidth - card.offsetWidth - 12))}px`, top: `${top}px` });
}
function rowPeekHide() { clearTimeout(S.peekTimer); const old = document.getElementById("cp-peek"); if (old) old.remove(); }
document.addEventListener("mouseover", (event) => {
  const row = event.target.closest && event.target.closest("table.cp-cases tbody tr");
  if (row === S.peekRow) return;
  S.peekRow = row || null;
  rowPeekHide();
  if (row) S.peekTimer = setTimeout(() => { if (S.peekRow === row && document.contains(row)) rowPeekShow(row); }, 550);
});
document.addEventListener("scroll", () => { S.peekRow = null; rowPeekHide(); }, true);
document.addEventListener("mousedown", () => { S.peekRow = null; rowPeekHide(); });

// A decision that is the handler's, taken with one click wherever it is offered (the step, the flow, the stage).
async function decideFact(fact, value) {
  const police = fact === "deckung" && value === "bestätigt" ? policeOpen() : 0;
  const note = police ? `${police} ${police === 1 ? "Punkt" : "Punkte"} laut Police, nicht einzeln bestätigt` : "";
  S.lastEdit = await api(`/api/cases/${S.route.id}/edits`, { method: "POST", body: JSON.stringify({ op: "set_fact", args: { fact, value }, reason: note, reason_code: "none", recheck: false }) }).catch(() => S.lastEdit);
  S.decideOpen = false; S.docTab = null;
  await loadCase();
}
// ---------- the case under the hand: an index in the rail, a stage that answers it ----------
// Everything CasePath established about a case is named once in the rail, in a few groups. Resting the hand on a name
// shows that part on the stage at the right, as it stands now (its rows arrive in the order they are read, what is
// settled is ticked, what is open is marked); pressing the name keeps it there. The stage is built from what the page
// already holds; a row opens the passage or the tab it belongs to. Nothing here decides anything: decisions stay where
// they are taken.
const xFacts = () => (S.data.items || []).filter((i) => i.kind === "fact" && !i.chat_only && i.value !== null && i.value !== undefined && i.value !== "");
const xDocs = () => (S.data.items || []).filter((i) => i.kind === "document" && !i.part_of);
const xCover = () => (S.data.items || []).filter((i) => i.kind === "cover" && i.key !== "summary");
const xEntries = () => (S.data.verlauf || []).filter((r) => r.kind !== "gesture");
const xCite = (ev) => { const c = (ev || []).find((e) => e.file); return c ? ` data-x-file="${raw(c.file)}" data-x-page="${c.page || ""}"` : ""; };
const xPage = (ev) => { const c = (ev || []).find((e) => e.file && e.page); return c ? `<span class="cp-x-page">${T("p.", "S.")} ${c.page}</span>` : ""; };
const xMark = (state) => `<span class="cp-x-mark ${state}">${state === "done" ? icon("tick") : ""}</span>`;
const xRow = (i, state, main, side, sub, attrs) => `<li class="cp-x-row ${state || ""}" style="--i:${i}"${attrs || ""}>${xMark(state || "")}<span class="cp-x-main">${main}${sub ? `<small>${sub}</small>` : ""}</span>${side ? `<span class="cp-x-side">${side}</span>` : ""}</li>`;
const xRows = (rows) => `<ul class="cp-x-rows">${rows.join("")}</ul>`;
// In the sidebar stand only the parts a handler acts on or looks up while working a case; what the page already says
// (the request, the parties, the points of law, the process on its own tab) is not named again.
const X_ORDER = ["deckung", "fristen", "unterlagen", "verlauf", "angaben"];
// One entry per part: its name, what the rail says beside it (a count, or what needs a hand), and its stage.
const X_TOPICS = {
  deckung: { name: () => T("Cover", "Deckung"), show: () => xCover().length > 0, alert: () => !answered("deckung"), side: () => (answered("deckung") ? esc(String(answered("deckung"))) : T("to decide", "zu entscheiden")), stage: () => {
    const pts = xCover(), state = { akte: "done", police: "check", kunde: "ask" }, n = (k) => pts.filter((q) => q.value === k).length;
    return { title: T("Is the case covered?", "Ist der Fall gedeckt?"), tab: "process_builder",
      line: (() => { const sum = item("cover", "summary"); return sum && sum.value ? esc(String(sum.value).replace(/^Deckung: /, "")) : `${n("akte")} ${T("settled from the file", "aus der Akte geklärt")} · ${n("police")} ${T("to check in the policy", "in der Police zu prüfen")}`; })(),
      body: `${xRows(pts.map((q, i) => xRow(i, state[q.value] || "quiet", esc(q.title || (q.label || {}).de || ""), xPage(q.evidence), esc([q.state_text, q.aid ? clip(q.aid, 110) : ""].filter(Boolean).join(" · ")), xCite(q.evidence))))}
        <p class="cp-x-foot cp-x-decide" style="--i:${pts.length}">${answered("deckung") ? `${T("Decided", "Entschieden")}: <b>${esc(String(answered("deckung")))}</b>`
          : `<button type="button" class="cp-button cp-small primary" data-x-decide="bestätigt">${T("Confirm cover", "Deckung bestätigen")}</button><button type="button" class="cp-button cp-small" data-x-decide="abgelehnt">${T("Refuse …", "Ablehnen …")}</button>`}</p>` };
  } },
  fristen: { name: () => T("Deadlines", "Fristen"), show: () => (scr().fristen || []).length > 0, alert: () => (scr().fristen || []).some((f) => f.late || f.soon), side: () => { const fr = scr().fristen || [], dated = fr.filter((f) => f.date).length; return dated ? String(fr.length) : T(`${fr.length} without a date`, `${fr.length} ohne Datum`); }, stage: () => {
    const fr = scr().fristen || [];
    return { title: T("What runs against the clock", "Was an eine Frist gebunden ist"), line: fr.length ? "" : T("No deadline in the file.", "Keine Frist in der Akte."), tab: "overview",
      body: fr.length ? xRows(fr.map((f, i) => xRow(i, f.late ? "late" : f.soon ? "soon" : "date", `<b>${esc(f.date || f.state)}</b> ${esc(f.title)}`, f.date ? esc(f.state) : "", esc([f.condition, f.basis].filter(Boolean).join(" · "))))) : `<p class="cp-x-empty" style="--i:0">${T(`CasePath found no deadline the customer or ${HOUSE.name} must meet.`, `CasePath hat keine Frist gefunden, die die Kundschaft oder ${HOUSE.name} wahren muss.`)}</p>` };
  } },
  angaben: { name: () => T("Facts", "Angaben"), show: () => xFacts().length > 0, side: () => String(xFacts().length), stage: () => {
    const all = xFacts(), cited = (f) => (f.evidence || []).some((e) => e.file), shown = all.slice().sort((x, y) => Number(cited(y)) - Number(cited(x))).slice(0, 40);
    return { title: T("What CasePath read in the file", "Was CasePath in der Akte gelesen hat"), tab: "claim_reader", line: "",
      body: xRows(shown.map((f, i) => xRow(Math.min(i, 9), cited(f) ? "done" : "quiet", `<small class="cp-x-key">${esc(clip((f.label || {}).de || shortFact(f.key), 84))}</small><b>${esc(clip(plainValue(f.value), 90))}</b>`, xPage(f.evidence), "", xCite(f.evidence)))) };
  } },
  unterlagen: { name: () => T("Documents", "Unterlagen"), show: () => Boolean(S.data.screen) && xDocs().length > 0, alert: () => Boolean(scr().missing), side: () => (scr().missing ? T(`${scr().missing} missing`, `${scr().missing} fehl${scr().missing === 1 ? "t" : "en"}`) : String(xDocs().length)), stage: () => {
    const gone = new Set(scr().missing_ids || []), docs = xDocs().slice().sort((a, b) => (gone.has(a.item_id) ? 0 : a.status === "present" ? 1 : 2) - (gone.has(b.item_id) ? 0 : b.status === "present" ? 1 : 2)).slice(0, 9);
    const on = xDocs().filter((q) => q.status === "present").length;
    return { title: T("What the case needs, and what is there", "Was der Fall braucht und was da ist"), line: T(`${on} of ${xDocs().length} on file`, `${on} von ${xDocs().length} liegen vor`), tab: "document_finder",
      body: xRows(docs.map((q, i) => xRow(i, gone.has(q.item_id) ? "missing" : q.status === "present" ? "done" : "quiet", esc(clip((q.label || {}).de || q.key, 70)),
        `${gone.has(q.item_id) ? T("missing", "fehlt") : q.status === "present" ? T("on file", "liegt vor") : T("if needed", "falls nötig")}${xPage(q.evidence)}`, q.practice ? esc(q.practice) : "", xCite(q.evidence)))) };
  } },
  verlauf: { name: () => T("History", "Verlauf"), show: () => xEntries().length > 0, alert: () => xEntries().some((r) => r.open), side: () => { const o = xEntries().filter((r) => r.open).length; return o ? T(`${o} open`, `${o} offen`) : String(xEntries().length); }, stage: () => {
    const all = xEntries().slice().sort((a, b) => String(a.date || "9999").localeCompare(String(b.date || "9999"))), last = all.slice(-6), open = all.filter((r) => r.open).length;
    return { title: T("Who wrote to whom, lately", "Wer zuletzt wem geschrieben hat"), line: `${all.length} ${T("entries", "Einträge")}${open ? ` · ${open} ${T("open", "offen")}` : ""}`, tab: "history",
      body: `<ol class="cp-x-line">${last.map((r, i) => { const from = String(r.who || "").split("→")[0].trim(), note = (r.notes || []).find((q) => q.open);
        return `<li class="${r.open ? "open" : ""}" style="--i:${i}"${xCite(r.evidence)}><span class="cp-x-who" title="${esc(r.who || "")}">${esc((tr(from) || "·").slice(0, 1))}</span><span class="cp-x-entry"><small>${dateText(r.date) || T("undated", "ohne Datum")} · ${esc(r.who || "")}</small>${esc(clip(r.what || r.title || "", 96))}${note ? `<em>${esc(clip(note.text, 90))}</em>` : ""}</span></li>`; }).join("")}</ol>` };
  } },
};
const X_ICON = { deckung: "shield", fristen: "clock", angaben: "list", unterlagen: "folder", verlauf: "memory" };
const xOn = () => S.route.view === "case" && S.data && S.data.screen && !running() && !unaidedPending() && !((S.data.case.intake || {}).study);
function caseIndex() {
  if (!xOn()) return "";
  const keys = X_ORDER.filter((k) => X_TOPICS[k].show()), hand = (k) => (X_TOPICS[k].alert && X_TOPICS[k].alert() ? 0 : 1);
  const items = keys.map((k) => { const t = X_TOPICS[k], side = t.side ? t.side() : "";
    return `<button type="button" class="cp-xitem${hand(k) ? "" : " alert"}" data-x="${k}" aria-pressed="${S.xPin === k}">${icon(X_ICON[k] || "doc")}<b>${t.name()}</b>${side ? `<span>${side}</span>` : ""}</button>`; }).join("");
  return items ? `<nav class="cp-xindex" aria-label="${T("The case at a glance", "Der Fall im Blick")}"><div class="cp-xgroup">${items}</div></nav>` : "";
}
function xStage(key, pinned) {
  const t = X_TOPICS[key], st = t && t.show() ? t.stage() : null;
  if (!st) return "";
  const group = T("At a glance", "Im Blick");
  return `<section class="cp-card cp-xstage${pinned ? " pinned" : ""}" data-xstage="${key}"><header><p class="cp-x-eyebrow">${esc(group)} · ${t.name()}</p>
      <span class="cp-x-tools">${st.tab && st.tab !== (S.route.tab || "overview") ? `<a class="cp-link cp-quiet-link" href="#/case/${raw(S.route.id)}/${st.tab}">${T("open", "öffnen")} ${icon("right")}</a>` : ""}${pinned ? `<button type="button" class="cp-x-close" data-x-close aria-label="${T("Close", "Schliessen")}">×</button>` : ""}</span>
      <h3>${st.title}</h3>${st.line ? `<p class="cp-x-line-top">${st.line}</p>` : ""}</header><div class="cp-x-body">${st.body}</div>
</section>`;
}
// The stage takes the place of «Der Fall» on the Übersicht; on the other tabs it stands at the right over the page.
function xShow(key, pinned) {
  clearTimeout(S.xTimer);
  const html = xOn() ? xStage(key, pinned) : "";
  if (!html) { xClear(); return; }
  const side = document.querySelector("aside.cp-side");
  let host = document.getElementById("xstage");
  if (!host) { host = document.createElement("div"); host.id = "xstage"; }
  const home = side || document.body;
  if (host.parentElement !== home) home.appendChild(host);
  host.className = side ? "cp-x-inplace" : "cp-x-float";
  if (host.dataset.shown !== `${key}:${pinned}:${LANG}`) { host.innerHTML = html; host.dataset.shown = `${key}:${pinned}:${LANG}`; }
  if (side) side.classList.add("cp-x-on");
  for (const b of document.querySelectorAll(".cp-xitem")) { b.classList.toggle("on", b.dataset.x === key); b.setAttribute("aria-pressed", String(S.xPin === b.dataset.x)); }
}
function xClear() {
  const host = document.getElementById("xstage"), side = document.querySelector("aside.cp-side");
  if (host) host.remove();
  if (side) side.classList.remove("cp-x-on");
  for (const b of document.querySelectorAll(".cp-xitem.on")) b.classList.remove("on");
}
const xRest = () => { if (S.xPin && xOn() && X_TOPICS[S.xPin] && X_TOPICS[S.xPin].show()) xShow(S.xPin, true); else xClear(); };
document.addEventListener("mouseover", (event) => {
  const item = event.target.closest && event.target.closest(".cp-xitem");
  if (item) { clearTimeout(S.xTimer); S.xTimer = setTimeout(() => xShow(item.dataset.x, S.xPin === item.dataset.x), document.querySelector("aside.cp-side") ? 70 : 180); return; }
  if (event.target.closest && (event.target.closest(".cp-xindex") || event.target.closest("#xstage"))) { clearTimeout(S.xTimer); return; }
  if (document.getElementById("xstage") && !(S.xPin && (document.getElementById("xstage").dataset.shown || "").startsWith(`${S.xPin}:true`))) { clearTimeout(S.xTimer); S.xTimer = setTimeout(xRest, 240); }
});
document.addEventListener("focusin", (event) => { const item = event.target.closest && event.target.closest(".cp-xitem"); if (item) xShow(item.dataset.x, S.xPin === item.dataset.x); });
document.addEventListener("click", (event) => {
  const el = event.target.closest ? event.target : null;
  if (!el) return;
  const item = el.closest(".cp-xitem");
  if (item) { S.xPin = S.xPin === item.dataset.x ? null : item.dataset.x; if (S.xPin) xShow(S.xPin, true); else xShow(item.dataset.x, false); return; }
  if (el.closest("[data-x-close]")) { S.xPin = null; xClear(); return; }
  if (el.closest("#xstage .cp-x-tools a")) { S.xPin = null; xClear(); return; }   // «öffnen» leads on; the stage does not follow
  const dx = el.closest("[data-x-decide]");
  if (dx) {  // the same decision as on the step, by the same rule; a refusal names its point where the step stands
    S.xPin = null; xClear();
    if (dx.dataset.xDecide === "bestätigt") decideFact("deckung", "bestätigt");
    else { S.coverDecline = true; const go = () => renderCase().then(() => { const why = document.querySelector(".cp-cover-why"); if (why) why.scrollIntoView({ block: "center" }); }); if (S.route.tab === "process_builder") go(); else { location.hash = `#/case/${S.route.id}/process_builder`; setTimeout(go, 500); } }
    return;
  }
  const cite = el.closest("#xstage [data-x-file]");
  if (cite && !el.closest("a, button")) { S.file = cite.dataset.xFile; S.page = Number(cite.dataset.xPage) || null; S.follow = false; if (S.route.tab === "claim_reader") renderCase(); else location.hash = `#/case/${S.route.id}/claim_reader`; }
});

const srcClose = () => `<button type="button" class="cp-src-close" data-src-close aria-label="${T("Close the passage", "Textstelle schliessen")}">×</button>`;
// What the letter rests on, said under it: each fact of the file and each document asked for whose words stand in the
// letter is one small chip with its page. A chip under the hand marks its words in the letter (the browser's own
// highlight, so the text that can be edited is never touched); pressed, it opens the passage.
function letterSources() {
  for (const old of document.querySelectorAll(".cp-lsrc")) old.remove();
  if (window.CSS && CSS.highlights) CSS.highlights.delete("cp-src");
  const letter = document.querySelector('.cp-letter[data-item="letter:0"]'), body = letter && letter.querySelector('.cp-text[data-seg="text"]');
  if (!xOn() || !body || (S.route.tab || "overview") !== "overview") return;
  const text = body.textContent || "", found = [], have = new Set();
  const add = (words, label, ev, kind) => { const w = String(words || "").trim(); if (w.length < 4 || have.has(w) || !text.includes(w)) return; have.add(w); const c = (ev || []).find((e) => e.file) || {}; found.push({ w, label, file: c.file || "", page: c.page || "", kind }); };
  for (const f of xFacts()) { const v = plainValue(f.value); if (/^(ja|nein|yes|no)$/i.test(String(v))) continue;
    for (const form of [tr(v), dateText(String(f.value))]) add(form, tr((f.label || {}).de || shortFact(f.key)), f.evidence, "fact"); }
  const gone = new Set(scr().missing_ids || []);
  for (const d of xDocs().filter((q) => gone.has(q.item_id))) add(tr((d.label || {}).de || ""), d.practice ? tr(d.practice) : T("asked for", "verlangt"), [], "doc");
  for (const fr of scr().fristen || []) add(fr.date, tr(fr.title), [], "date");
  // who it is written to, the claim it names and the day it asks an answer by
  for (const q of (S.data.items || []).filter((i) => i.kind === "party")) { const name = String(q.value || "").trim().split(/\s+/).pop(); add(name, tr((q.label || {}).de || T("party", "Partei")), q.evidence, "fact"); }
  add(S.data.case.reference, T("claim number", "Schadennummer"), [], "date");
  const by = (S.data.draft || {}).respond_by; if (by) add(dateText(by), T("answer by", "Antwort bis"), [], "date");
  for (let i = found.length - 1; i >= 0; i--) if (!found[i].file && found[i].kind !== "doc") found.splice(i, 1);
  if (!found.length) return;
  found.sort((a, b) => ["fact", "date", "doc"].indexOf(a.kind) - ["fact", "date", "doc"].indexOf(b.kind));
  const row = document.createElement("p");
  row.className = "cp-lsrc";
  row.innerHTML = `<span class="cp-lsrc-head">${T("The letter rests on", "Der Brief stützt sich auf")}</span>${found.slice(0, 8).map((f, i) => `<button type="button" class="cp-lsrc-chip ${f.kind}" style="--i:${i}" data-ls="${i}" title="${raw(f.label)}">${raw(clip(f.w, 34))}<small>${f.page ? `${T("p.", "S.")} ${raw(f.page)}` : f.kind === "doc" ? T("practice", "Praxis") : raw(clip(f.label, 24))}</small></button>`).join("")}`;
  letter.after(row);
  const mark = (f) => { if (!(window.CSS && CSS.highlights && window.Highlight)) return; const ranges = [], walk = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) for (let at = n.data.indexOf(f.w); at >= 0; at = n.data.indexOf(f.w, at + f.w.length)) { const r = new Range(); r.setStart(n, at); r.setEnd(n, at + f.w.length); ranges.push(r); }
    if (ranges.length) CSS.highlights.set("cp-src", new Highlight(...ranges)); };
  for (const chip of row.querySelectorAll(".cp-lsrc-chip")) { const f = found[Number(chip.dataset.ls)];
    chip.addEventListener("mouseenter", () => mark(f)); chip.addEventListener("focus", () => mark(f));
    chip.addEventListener("mouseleave", () => { if (window.CSS && CSS.highlights) CSS.highlights.delete("cp-src"); }); chip.addEventListener("blur", () => { if (window.CSS && CSS.highlights) CSS.highlights.delete("cp-src"); });
    chip.addEventListener("click", () => { if (f.file) { S.file = f.file; S.page = Number(f.page) || null; S.follow = false; location.hash = `#/case/${S.route.id}/claim_reader`; } else if (f.kind === "doc") location.hash = `#/case/${S.route.id}/document_finder`; }); }
}
// The keys, said once where the reader asks for them («?»): what works everywhere, in the list, in a case, in a picture.
function keysCard(open) {
  const old = document.getElementById("cp-keys");
  if (old) old.remove();
  if (!open) return;
  const row = (keys, what) => `<li><span>${keys.map((k) => `<kbd>${k}</kbd>`).join(" ")}</span>${what}</li>`;
  const box = document.createElement("div");
  box.id = "cp-keys";
  box.setAttribute("role", "dialog"); box.setAttribute("aria-label", T("Keyboard shortcuts", "Tastenkürzel"));
  box.innerHTML = `<div class="cp-keys-card"><h2>${T("Keyboard", "Tastatur")}</h2>
    <div class="cp-keys-cols"><section><h3>${T("In the list", "In der Liste")}</h3><ul>
        ${row(["J", "K"], T("down and up through the cases", "durch die Fälle, ab und auf"))}${row(["↵"], T("open the case", "Fall öffnen"))}${row(["/"], T("search", "suchen"))}</ul>
      <h3>${T("Everywhere", "Überall")}</h3><ul>${row(["?"], T("this card", "diese Karte"))}${row(["Esc"], T("close, leave a small form", "schliessen, ein kleines Formular verlassen"))}</ul></section>
      <section><h3>${T("In a case", "In einem Fall")}</h3><ul>
        ${row(["1", "…", "5"], T("Overview, File, Process, Documents, History", "Übersicht, Akte, Prozess, Unterlagen, Verlauf"))}${row([T("Ctrl", "Strg"), "↵"], T("the step's main action (approve, copy)", "die Hauptaktion des Schritts (freigeben, kopieren)"))}
        ${row(["N"], T("next case that needs you", "nächster Fall, der Sie braucht"))}${row(["L"], T("back to the list", "zurück zur Liste"))}</ul>
      <h3>${T("In a picture", "In einem Bild")}</h3><ul>${row(["V"], T("large, and back", "gross ansehen und zurück"))}${row(["←", "→"], T("one moment back or on (picture in focus)", "ein Moment zurück oder weiter (Bild im Fokus)"))}${row([T("Space", "Leertaste")], T("play, pause", "abspielen, anhalten"))}</ul></section></div>
    <p class="cp-muted">${T("Keys do nothing while you type in a field.", "Solange Sie in ein Feld schreiben, tun die Tasten nichts.")}</p></div>`;
  box.addEventListener("click", (event) => { if (event.target === box) keysCard(false); });
  document.body.appendChild(box);
}

// Each slice's own functions go in its section below (function declarations: the start above runs after the whole script).
// ---------- assessment: the decision brief, the customer's questions and the recommendation (Slice A) ----------
// The prepared answer is reviewed beside the few facts that decide it: each question with its state and what it waits for,
// the facts the package rests on (each opening its source at the passage, «neu» when the latest arrival brought it,
// corrected in place), what is still asked and the judgment each ask would settle. The recommendation is adopted or changed
// on its own line; the prospects of success are a decision of their own (Art. 169 AVO).
function brief() { return (S.data && S.data.assessment) || null; }
const A_STATE = { beantwortet: ["answered", "beantwortet"], bedingt: ["conditional", "bedingt"], offen: ["open", "offen"], pruefen: ["check the rule", "Zuordnung prüfen"], erledigt: ["settled", "erledigt"] };
const A_COND = { "erfüllt": "met", "offen": "open", "nicht erfüllt": "not met", "widersprüchlich": "read two ways", "vermutet": "presumed", "nicht geprüft": "not checked" };
const aValue = (v) => (v === true ? T("yes", "ja") : v === false ? T("no", "nein") : v === null || v === undefined ? "—" : String(v));
const aChip = (state, label) => `<span class="cp-a-chip s-${raw(String(state).replace(/[^a-zäöü]+/gi, "-"))}">${esc(label || state)}</span>`;
const aCond = (state) => aChip(state, T(A_COND[state] || state, state === "widersprüchlich" ? "widersprüchlich gelesen" : state));
const aQuestionText = (id) => ((((brief() || {}).questions || []).find((q) => q.item_id === id)) || {}).text;
const aOptionTitle = (id) => ((((brief() || {}).options || []).find((o) => o.id === id)) || {}).title;
// What an ask would settle: the customer's question it answers, the way it decides, the condition it meets.
function aBlocks(blocks) {
  const b = blocks || {}, parts = [];
  if (b.question && aQuestionText(b.question)) parts.push(`${T("for", "für")} «${esc(clip(aQuestionText(b.question), 48))}»`);
  if (b.option && aOptionTitle(b.option)) parts.push(esc(aOptionTitle(b.option)));
  if (b.condition && b.condition !== aQuestionText(b.question)) parts.push(esc(clip(b.condition, 48)));
  return parts.length ? `<div class="cp-a-why">${parts.join(" · ")}</div>` : "";
}
// The questions, the facts that decide the package and what is still asked: the side of the letter.
function briefSide(b) {
  const states = (q) => (q.taken ? T("answered (case handling)", "beantwortet (Fallbearbeitung)") : T(...(A_STATE[q.state] || [q.state, q.state])));
  const why = (q) => {
    if (q.adopted && q.reason) return `${T("your answer of", "Ihre Antwort vom")} ${dateText(String(q.adopted.at || "").slice(0, 10))}: ${q.reason}`;  // taken, then marked by a jurist
    if (q.taken || !q.reason) return "";
    if (q.state === "bedingt") return q.row === 8 ? `${T("ask", "Rückfrage")}: ${q.reason}` : (q.next || {}).kind === "residual" || /^Belege/.test(q.reason) ? `${T("waits for", "wartet auf")}: ${q.reason}` : q.reason;
    return q.reason;
  };
  const offers = (q) => q.state === "pruefen" && q.item_id ? (q.offered || []).map((o) => `<button class="cp-chip cp-a-take" data-answer-take="${raw(q.item_id)}" data-point="${raw(o.point)}" ${o.intent ? `data-intent="${raw(o.intent)}"` : ""} title="${esc(o.text)}">${T("take the draft", "Entwurf übernehmen")}${(q.offered || []).length > 1 ? `: ${esc(o.point)}` : ""}</button>`).join("") : "";
  const questions = (b.questions || []).map((q) => `<div class="cp-a-q" data-item="${raw(q.item_id || `konto:${q.request || ""}`)}">«${esc(q.text)}» ${aChip(q.taken ? "taken" : q.state, states(q))}${sourceChips(q.evidence)}${(q.evidence_in || []).length ? `${sourceChips(q.evidence_in)}` : ""}
      ${why(q) ? `<div class="cp-a-why">${esc(why(q))}</div>` : ""}${offers(q) ? `<div class="cp-a-offers">${offers(q)}</div>` : ""}</div>`).join("");
  const facts = (b.deciding || []).map((f) => {
    const tag = f.changed === "neu" ? ` <span class="cp-a-tag">${T("new", "neu")}</span>` : f.changed === "korrigiert" ? ` <span class="cp-a-tag own">${T("corrected", "korrigiert")}</span>` : "";
    const fix = S.aFix === f.fact ? `<span class="cp-a-fix">${(f.values || []).map((v) => `<button class="cp-chip" data-decide="${raw(f.fact)}" data-value="${raw(v === true ? "ja" : v === false ? "nein" : v)}" aria-pressed="${String(v) === String(f.value)}">${esc(aValue(v))}</button>`).join("")}</span>` : "";
    return `<div class="cp-a-fact" data-item="fact:${raw(f.fact)}">${esc(clip(f.question, 64))} <b>${esc(aValue(f.value))}</b>${f.state !== "erfüllt" ? ` ${aCond(f.state)}` : ""}${tag}${f.read === "einmal gelesen" && !f.changed ? ` <span class="cp-muted">· ${T("read once", "einmal gelesen")}</span>` : ""}${sourceChips(f.evidence)}
      ${(f.values || []).length ? ` <button class="cp-link cp-quiet-link" data-a-fix="${raw(f.fact)}" aria-expanded="${S.aFix === f.fact}">${T("correct", "ändern")}</button>` : ""}${fix}</div>`;
  }).join("");
  const residual = (b.residual || []).filter((r) => r.ticked).map((r) => `<div class="cp-a-ask" data-item="${raw(r.key)}">– ${esc(r.line)}${sourceChips(r.evidence)}${aBlocks(r.blocks)}
      ${(r.set_aside || []).map((x) => `<div class="cp-a-why">${T("receipt set aside", "Beleg nicht zugeordnet")}: ${esc(clip(x.expense || "", 40))} · ${esc((x.why || []).join("; "))}${sourceChip({ file: x.file })}</div>`).join("")}</div>`).join("");
  const facts_asked = (b.asks || []).filter((a) => a.kind === "fact").map((a) => `<div class="cp-a-ask" data-item="${raw(a.key)}">${T("Question", "Frage")}: ${esc(a.what)}${a.decides ? `<div class="cp-a-why">${T("decides", "entscheidet")}: ${esc(clip(a.decides, 90))}</div>` : ""}${aBlocks(a.blocks)}</div>`).join("");
  const settled = (b.resolved || []).filter((r) => r.key.startsWith("residual:")).map((r) => `<div class="cp-a-ask done" data-item="${raw(r.key)}">✓ ${esc(r.line)} ${T("received", "eingegangen")}${sourceChips(r.by)}${aBlocks(r.blocks)}</div>`).join("");
  // the costs claimed, each with its current version beside the passage that states it; an earlier version or a withdrawal
  // stays visible, never as the current claim
  const chf = (v) => `CHF ${Number(v).toFixed(2).replace(/\.00$/, "")}`;
  const claimRow = (c) => {
    const was = (c.history || []).filter((h) => h.until === "amended").map((h) => h.amount).filter(Boolean);
    const state = c.state === "withdrawn" ? aChip("erledigt", T("withdrawn", "zurückgezogen")) : c.state === "unclear" ? aChip("pruefen", T("unclear", "unklar"))
      : c.contested ? aChip("pruefen", T("stated differently", "anders angegeben")) : c.documented ? aChip("beantwortet", T("documented", "belegt")) : "";
    const note = [c.version > 1 && c.state === "current" ? `${T("corrected", "korrigiert")}${c.stated ? ` ${dateText(c.stated)}` : ""}` : "",
      was.length ? `${T("before", "bisher")} ${was.join(", ")}` : ""].filter(Boolean).join(" · ");
    return `<div class="cp-a-fact" data-item="residual:claim.${c.i}">${esc(c.what)} <b>${esc(c.amount || "")}</b> ${state}${sourceChips((c.citations || []).slice(0, 1))}
      ${note ? `<div class="cp-a-why">${esc(note)}</div>` : ""}</div>`;
  };
  const shown = (b.claims || []).filter((c) => !["merged", "dismissed"].includes(c.state));
  const claims = shown.some((c) => c.version > 1 || c.state !== "current" || c.contested || shown.length > 1) || b.follow_on ? shown.map(claimRow).join("") : "";
  // the follow-on: what the arrival settled, what it does not establish, and what was decided before and stands
  const f = b.follow_on;
  const follow = f ? `${(f.resolved || []).map((r) => `<div class="cp-a-ask done" data-item="${raw(r.key)}">✓ ${esc(r.what)}${r.amount != null ? ` · ${chf(r.amount)}` : ""}${sourceChips(r.by)}
        ${r.condition ? `<div class="cp-a-why">${T("settles", "erfüllt")}: ${esc(r.condition)}</div>` : ""}</div>`).join("")}
      ${(f.remains || []).length && f.kind === "documented" ? `<div class="cp-a-why">${T("not established by it", "damit nicht belegt")}: ${esc([...new Set(f.remains.map((r) => r.condition))].join(", "))}</div>` : ""}
      ${(f.stands || []).length ? `<div class="cp-a-why">${T("stands", "gilt weiter")}: ${esc(f.stands.map((x) => (x.what === "Empfehlung übernommen" ? `Empfehlung «${x.value}»` : `${x.what} ${x.value}`)).join(" · "))}</div>` : ""}` : "";
  return `${follow ? `<dt>${T("Follow-on", "Nachtrag")}</dt><dd>${follow}</dd>` : ""}
    <dt>${T("Questions", "Fragen")}</dt><dd class="cp-asks">${questions}</dd>
    ${claims ? `<dt>${T("Costs", "Kosten")}</dt><dd class="cp-a-facts">${claims}</dd>` : ""}
    ${facts ? `<dt>${T("Deciding", "Entscheidend")}</dt><dd class="cp-a-facts">${facts}</dd>` : ""}
    ${residual || facts_asked || (settled && !follow) ? `<dt>${T("Still asked", "Noch offen")}</dt><dd>${follow ? "" : settled}${residual}${facts_asked}</dd>` : ""}`;
}
// The recommendation opened: the ways (the proposal, each alternative and why it is not the proposal), the rule with each
// condition met, open or not checked and its source, what would change it; «ändern» picks one holding way per wish.
function briefPanel(dec) {
  const b = brief() || {};
  const wishText = Object.fromEntries((b.wishes || []).map((w) => [w.fact, w.text]));
  const reserve = (o) => ((o.reserve || []).length ? ` · ${T("subject to", "unter Vorbehalt")}: ${o.reserve.map((r) => esc(r.condition)).join("; ")}` : "");
  let pick = "";
  if (S.recChange) {
    const groups = {};
    for (const o of dec.options || []) (groups[o.wish] = groups[o.wish] || []).push(o);
    pick = `<div class="cp-rec-pick">${Object.entries(groups).map(([wish, rows]) => `<fieldset><legend>${T("You want", "Sie möchten")} ${esc(wishText[wish] || wish)}</legend>
        ${rows.map((o) => `<label><input type="radio" name="rec-${raw(wish)}" value="${raw(o.id)}" data-rec-pick ${o.proposed ? "checked" : ""}> ${esc(o.title)} <span class="cp-muted">· ${esc(o.practice)} · ${esc(o.review)}${o.propose ? "" : ` · ${T("selectable only", "nur wählbar")}`}</span></label>`).join("")}</fieldset>`).join("")}
      <button class="cp-button cp-small primary" data-rec-confirm>${T("adopt", "übernehmen")}</button></div>`;
  }
  const ways = (b.options || []).filter((o) => o.proposed || o.chosen).map((o) => `<li><b>${esc(o.title)}</b> <span class="cp-muted">· ${esc(o.practice)} · ${esc(o.review)}${reserve(o)}</span>
      ${(b.alternatives || []).filter((a) => a.to === o.id).map((a) => `<div class="cp-a-why">${T("Alternative", "Alternative")}: ${esc(a.title)} · ${esc(a.why || "")} · ${esc(a.practice)}</div>`).join("")}</li>`).join("");
  const rules = (b.rules || []).filter((r) => !String(r.id).startsWith("punkt:")).map((r) => `<li><b>${esc(r.cite || "")}</b>${(r.law || []).length ? ` <button class="cp-link cp-quiet-link" data-a-law="${raw(r.id)}" aria-expanded="${S.aLaw === r.id}">${T("passage", "Wortlaut")}</button>` : ""}
      ${S.aLaw === r.id ? passages(r.law) : ""}<ul>${r.conditions.map((c) => `<li>${esc(c.text)}: ${aCond(c.state)}${c.read === "einmal gelesen" ? ` <span class="cp-muted">${T("read once", "einmal gelesen")}</span>` : ""}${sourceChips(c.evidence)}</li>`).join("")}</ul></li>`).join("");
  const changes = (b.changes_if || []).map((c) => esc(clip(c.question || c.title || c.condition || "", 60))).join(" · ");
  return `<div class="cp-brief">${pick}<p class="cp-a-head">${T("Ways", "Wege")}</p><ul class="cp-a-list">${ways}</ul>
    <p class="cp-a-head">${T("Rule and conditions", "Regel und Voraussetzungen")}</p><ul class="cp-a-list">${rules}</ul>
    ${changes ? `<p class="cp-a-head">${T("Changes if", "Ändert sich, wenn")}</p><p class="cp-a-why">${changes}</p>` : ""}</div>`;
}
// The prospects of success, a decision of its own: its basis and what «nicht genügend» prepares instead.
function prospectsPanel(dec) {
  return `${passages(dec.law)}${dec.consequence ? `<div class="cp-a-why">${esc(dec.consequence)}</div>` : ""}`;
}
async function recommend(chosen) {
  const dec = scr().decision || {};
  return api(`/api/cases/${S.route.id}/recommendation`, { method: "POST", body: JSON.stringify({ chosen, proposal: dec.proposal || [] }) });
}
document.addEventListener("click", (e) => {  // a source chip opens its source at the passage it stands for
  const b = e.target && e.target.closest ? e.target.closest("[data-cite-file]") : null;
  if (b) S.cite = b.dataset.end ? { file: b.dataset.citeFile, page: Number(b.dataset.page) || null, start: Number(b.dataset.start), end: Number(b.dataset.end) } : null;
}, true);
document.addEventListener("click", async (e) => {
  const el = e.target && e.target.closest ? e.target.closest("[data-rec-adopt],[data-rec-change],[data-rec-confirm],[data-answer-take],[data-a-fix],[data-a-law]") : null;
  if (!el || !S.data || S.route.view !== "case") return;
  if (el.matches("[data-a-fix]")) { S.aFix = S.aFix === el.dataset.aFix ? null : el.dataset.aFix; renderCase(); return; }
  if (el.matches("[data-a-law]")) { S.aLaw = S.aLaw === el.dataset.aLaw ? null : el.dataset.aLaw; renderCase(); return; }
  if (el.matches("[data-rec-change]")) { S.recChange = !S.recChange; renderCase(); return; }
  try {
    if (el.matches("[data-rec-adopt]")) await recommend((scr().decision || {}).proposal || []);
    else if (el.matches("[data-rec-confirm]")) await recommend([...document.querySelectorAll("[data-rec-pick]:checked")].map((x) => x.value));
    else await api(`/api/cases/${S.route.id}/answer`, { method: "POST", body: JSON.stringify({ item_id: el.dataset.answerTake, point: el.dataset.point, ...(el.dataset.intent ? { intent: el.dataset.intent } : {}) }) });
    S.recChange = false; S.decideOpen = false; S.message = "";
    await loadCase();
  } catch (error) { S.message = error.message; S.messageOk = false; renderCase(); }
});

// ---------- completion: approval, the Versandpaket, dispatch and the queue (Slice B) ----------
// The handler's decision carried through, as the server keeps it (process/completion.py, web/actions.py). The letter's text
// is saved on the server per part while typing (1.5 s after the last key, on leaving the text, before «Freigeben»); an
// edited block of the letter is mapped back to the parts its lines come from (draft.line_parts). «Freigeben» approves the
// version shown and stores its Versandpaket; «Brief kopieren» copies the approved text (a clipboard that refuses says
// «Kopieren fehlgeschlagen» and nothing is recorded); «Versandt am» is the handler's confirmation per recipient. A copy is
// measured (letter.copied with «measure»), never counted as a sending. Nothing is sent from here.
const CHANNELS = lazy(() => ([["email", T("E-mail", "E-Mail")], ["post", T("Post", "Post")], ["portal", T("Portal", "Portal")], ["andere", T("other", "andere")]]));
const SHA_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
const newOp = (what) => `${what}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
function completionOf() { return (S.data && S.data.completion) || {}; }
// A closing step (A12, a closing): «Erledigt» once its letter, if it has one, went out.
function closingStep(act, text) {
  if (!act || !["A12", "close"].includes(act.action)) return false;
  const st = completionOf();
  return !text || st.state === "versandt" || Boolean(((S.data || {}).draft || {}).optional);  // a closing letter that may be left out
}
// A tab says where its document stands: «Entwurf», «freigegeben», «Freigabe veraltet», «versandt am …».
function tabState(d) {
  if (!d.state || d.state === "entwurf") return "";
  return ` <span class="cp-tab-state ${raw(d.state)}">${d.state === "versandt" ? icon("tick") : ""}${esc(d.label || "")}</span>`;
}
// The case head between «Weil» and the decision: what changed, what it means, an approval that no longer holds, a letter
// that went out resting on something changed since (screen.head_block). Each line opens its details on a click.
function headBlock() {
  const h = scr().head;
  if (!h) return "";
  const line = (key, label, text, more, cls = "") => text ? `<p class="cp-head-line ${cls} ${S.headOpen === key ? "open" : ""}">${(more || []).length
      ? `<button class="cp-head-text" data-head-open="${key}" aria-expanded="${S.headOpen === key}"><span class="cp-head-label">${label}</span> ${esc(text)}</button>`
      : `<span class="cp-head-text"><span class="cp-head-label">${label}</span> ${esc(text)}</span>`}
      ${S.headOpen === key && (more || []).length ? `<span class="cp-head-more">${more.map((x) => esc(isoDay(x))).join("<br>")}</span>` : ""}</p>` : "";
  // one sentence: what the news means for this step; what changed is one click behind it (never two labelled lines to read)
  const changes = [...new Set([...(h.changed_all || []), h.changed].filter(Boolean))];
  const news = h.meaning || h.changed || "";
  const more = h.meaning ? [...changes, ...(h.meaning_all || []).filter((x) => x !== h.meaning)] : changes.filter((x) => x !== h.changed);
  const open = S.headOpen === "news";
  const newsLine = news ? `<p class="cp-head-line cp-news ${open ? "open" : ""}" data-news><span class="cp-head-text">${esc(news)}</span>
      ${more.length ? `<button class="cp-link cp-quiet-link" data-head-open="news" aria-expanded="${open}">${T("what changed", "was sich geändert hat")}</button>` : ""}
      ${open && more.length ? `<span class="cp-head-more">${more.map((x) => esc(isoDay(x))).join("<br>")}</span>` : ""}</p>` : "";
  return `<div class="cp-head" data-head>${newsLine}
    ${h.stale ? line("stale", "", h.stale, h.stale_all, "cp-head-stale") : ""}
    ${h.reconcile ? `<p class="cp-head-line cp-head-stale"><button class="cp-button cp-small" data-reconcile="${raw(h.reconcile)}" title="${T("The letter stays as sent; a correction would be a letter of its own", "Der Brief bleibt so versandt; eine Korrektur wäre ein eigener Brief")}">${T("Reconciled", "Abgleich erledigt")}</button></p>` : ""}</div>`;
}
function sentLetter(shown, version) {
  if (shown.error) return `<p class="cp-error">${esc(shown.error)}</p>`;
  if (!shown.letter) return `<p class="cp-muted cp-sent-letter">${T("loading …", "wird geladen …")}</p>`;
  const l = shown.letter, to = [l.to, l.address].filter(Boolean).join(" · ");
  const doc = (title, text) => `<div class="cp-sent-doc"><p class="cp-sent-head">${esc(title)}</p><div class="cp-text">${esc(text)}</div></div>`;
  return `<div class="cp-sent-letter" data-sent-letter><p class="cp-muted">${T("Approved", "Freigegeben")} ${dateText(l.approved_at)}${l.approved_by ? ` · ${esc(l.approved_by)}` : ""}${to ? ` · ${T("to", "an")} ${esc(to)}` : ""}
      · <a class="cp-link cp-quiet-link" href="/api/cases/${raw(S.route.id)}/actions/${raw(version)}/bundle">${T("dispatch package (.zip)", "Versandpaket (.zip)")}</a></p>
    ${doc(l.title || T("Letter", "Brief"), l.text)}${(l.also || []).map((a) => doc(String(a.name || a.kind).replace(/\.docx$/i, ""), a.text)).join("")}</div>`;
}
function reconcileLine() {
  const h = scr().head;
  if (!h || !h.reconcile) return "";
  return `<p class="cp-head-line cp-head-stale cp-rest-reconcile">${esc(h.stale || h.changed || T("Changed after it went out: check that the letter stands as sent.", "Nach dem Versand geändert: prüfen, ob der Brief so stimmt."))} <button class="cp-button cp-small" data-reconcile="${raw(h.reconcile)}" title="${T("The letter stays as sent; a correction would be a letter of its own", "Der Brief bleibt so versandt; eine Korrektur wäre ein eigener Brief")}">${T("Reconciled", "Abgleich erledigt")}</button></p>`;
}
// A part of the letter the case changed while the handler had edited it: both versions, the handler decides.
function conflictsView(active) {
  const draft = S.data.draft || {};
  const doc = !active || active.main ? draft : (draft.also || []).find((a) => a.kind === active.kind) || {};
  const clashes = doc.conflicts || [];
  if (!clashes.length) return "";
  const form = !active || active.main ? (draft.form || draft.kind) : active.kind;
  return `<div class="cp-conflicts" id="conflicts"><p class="cp-conflict-head">${T("Your text concerned a paragraph that changed: please check", "Ihr Text betraf einen geänderten Absatz: bitte prüfen")}</p>
    ${clashes.map((c) => `<div class="cp-conflict"><div><span class="cp-muted">${T("Mine", "Meine Fassung")}</span><div class="cp-conflict-text">${esc(c.mine)}</div></div>
      <div><span class="cp-muted">${T("New", "Neue Fassung")}</span><div class="cp-conflict-text">${esc(c.new || T("(no longer in the letter)", "(nicht mehr im Brief)"))}</div></div>
      <span class="cp-point-actions"><button class="cp-button cp-small" data-resolve="${raw(c.part)}" data-form="${raw(form)}" data-keep="mine">${T("keep mine", "meine Fassung behalten")}</button>
        <button class="cp-button cp-small" data-resolve="${raw(c.part)}" data-form="${raw(form)}" data-keep="new">${T("take the new one", "neue Fassung übernehmen")}</button></span></div>`).join("")}</div>`;
}
// «Versandt am [TT.MM.JJJJ] [E-Mail ▾]», per recipient not yet confirmed: today and the channel of the customer's last
// message preset, the first day allowed the approval's (or a copy's of the same text).
function dispatchControl(bar, row, primary, named) {
  const many = named || (bar.recipients || []).filter((r) => !r.dispatched).length > 1;
  const day = row.date || isoToday();
  const name = T("Sent on", "Versandt am"), to = many ? ` ${T("to", "an")} ${row.title}` : "";
  return `<span class="cp-dispatch" data-dispatch-row="${raw(row.to)}">${many ? `<span class="cp-dispatch-to">${esc(row.title)}:</span>` : ""}<button class="cp-button ${primary ? "primary" : ""}" data-dispatch="${raw(row.to)}" data-dispatch-version="${raw(bar.version || "")}" aria-label="${esc(`${name} ${dateText(day)}${to}`)}">${esc(name)}</button>
    <input type="date" class="cp-dispatch-date" data-dispatch-date="${raw(row.to)}" value="${raw(day)}" max="${raw(row.date || isoToday())}" ${bar.earliest ? `min="${raw(bar.earliest)}"` : ""} aria-label="${T("Day sent", "Versanddatum")}">
    <select class="cp-dispatch-channel" data-dispatch-channel="${raw(row.to)}" aria-label="${T("Channel", "Kanal")}">${CHANNELS().map(([k, w]) => `<option value="${k}" ${k === (row.channel || bar.channel) ? "selected" : ""}>${esc(w)}</option>`).join("")}</select></span>`;
}
// The bar of a letter that can be approved and sent: before approval «Freigeben» (the gaps, an open decision or a clash
// first); after it «Brief kopieren» for the letter (an enclosure: «Text kopieren» and «als .docx»), then «Versandt am»;
// «Versandpaket herunterladen» and «Aktennotiz kopieren» beside them; a stale approval «Erneut freigeben».
function carryButtons(active, opts) {
  const st = completionOf(), bar = st.bar || {}, draft = S.data.draft || {};
  const id = S.route.id;
  const gapsButton = `<button class="cp-button ${opts.primary ? "primary" : ""}" id="fill-gaps" data-gaps="${opts.gaps}">${T(`Fill ${opts.gaps} gap${opts.gaps > 1 ? "s" : ""}`, `${opts.gaps} Lücke${opts.gaps > 1 ? "n" : ""} füllen`)}</button>`;
  const saving = S.saveState === "error" ? `<span class="cp-save-state error">${esc(S.saveError || T("Not saved", "Nicht gespeichert"))}</span>`
    : S.saveState === "saving" ? `<span class="cp-save-state">${T("saving …", "wird gespeichert …")}</span>` : "";
  const failed = S.copyFailed ? `<span class="cp-save-state error" role="status">${T("Copying failed", "Kopieren fehlgeschlagen")}</span>` : "";
  const last = st.last || {}, wentOut = (last.dispatched || [])[0];
  const sentLine = wentOut ? `<span class="cp-sent">${icon("check")}${esc(last.title ? `${last.title} ` : "")}${T("sent", "versandt am")} ${dateText(wentOut.date)}</span>` : "";
  // what the letter rests on that a jurist holds: «Änderung nötig» blocks the approval, a «Frage» is shown beside it
  const heldNow = (st.held_now || []).find((h) => h.blocks) || (st.held_now || [])[0], heldBlocks = Boolean(heldNow && heldNow.blocks);
  const heldText = heldNow ? T(`Under legal review: ${heldNow.title} (${heldNow.mark})`, `In Prüfung: ${heldNow.title} (${heldNow.mark})`) : "";
  const heldNote = heldNow ? `<span class="cp-stale-bar" data-held-now>${esc(heldText)}</span>` : "";
  if (bar.kind === "approve" && st.waits) {
    // the case waits for its date: quiet; the follow-up is prepared for then and can be approved earlier, never pressed for
    // … but not past a decision that is open: what the customer said last is settled first
    const first = bar.decision ? T(`Decide first: ${bar.decision}`, `Zuerst entscheiden: ${bar.decision}`) : "";
    return `${sentLine}<span class="cp-waits">${esc(st.waits)}</span><button class="cp-button" id="approve" ${first ? `disabled title="${esc(first)}"` : `title="${T("prepared for the follow-up date", "für die Wiedervorlage vorbereitet")}"`}>${T("Approve and copy", "Freigeben und kopieren")}</button>${first ? `<span class="cp-blocked" data-blocked>${esc(first)}</span>` : ""}`;
  }
  if (bar.kind === "approve") {
    if (opts.gaps) return `${gapsButton}${saving}${opts.whenAfter || opts.when}`;
    if ((bar.conflicts || 0) > 0) return `<button class="cp-button" id="to-conflicts">${T("Check paragraph", "Absatz prüfen")}</button>${saving}`;
    const blocked = bar.decision ? T(`Decide first: ${bar.decision}`, `Zuerst entscheiden: ${bar.decision}`) : opts.stale ? T("New files are not read yet", "Neue Unterlagen sind noch nicht gelesen.")
      : heldBlocks ? heldText : "";
    const legacy = bar.legacy ? `<span class="cp-muted cp-legacy">${T("copied", "kopiert")} ${dateText(bar.legacy.at)}, ${T("sending not confirmed", "Versand nicht bestätigt")}</span>` : "";
    return `<button class="cp-button ${opts.primary && !blocked ? "primary" : ""}" id="approve" ${blocked ? `disabled title="${esc(blocked)}"` : ""}>${approveLabel()}</button>${blocked && !heldNote ? `<span class="cp-blocked" data-blocked>${esc(blocked)}</span>` : ""}${heldNote}${legacy}${saving}${opts.whenAfter || opts.when}`;
  }
  const rows = (bar.recipients || []).filter((r) => !r.dispatched);
  const copied = copiedApproved();
  const docx = active && !active.main && bar.version ? `<a class="cp-link" href="/api/cases/${raw(id)}/actions/${raw(bar.version)}/docx/${encodeURIComponent(active.kind)}">${T("as .docx", "als .docx")}</a>` : "";
  const packName = T("Download the dispatch package", "Versandpaket herunterladen");
  const pack = bar.version && (st.approved || {}).bundle ? `<a class="cp-link" id="bundle-download" href="/api/cases/${raw(id)}/actions/${raw(bar.version)}/bundle" aria-label="${packName}" title="${packName}">${T("Package", "Versandpaket")}</a>` : "";
  const note = "";  // «Aktennotiz kopieren» stands in «Der Fall», beside the note it copies
  if (bar.kind === "stale") {
    return `<span class="cp-stale-bar" title="${esc((bar.reasons || []).join(", "))}">${esc(bar.stale)}</span><button class="cp-button ${opts.primary && !heldBlocks ? "primary" : ""}" id="approve" ${heldBlocks ? `disabled title="${esc(heldText)}"` : ""}>${T("Approve again and copy", "Erneut freigeben und kopieren")}</button>${heldBlocks ? heldNote : ""}
      ${S.staleSent === id ? `<span class="cp-stale-sent">${T("The version approved before the change went out:", "Die Fassung vor der Änderung ging hinaus:")}</span>${rows.map((r) => dispatchControl(bar, r, false)).join("")}`
        : rows.length ? `<button class="cp-link cp-quiet-link" id="stale-sent" type="button">${T("the approved version already went out", "die freigegebene Fassung ging schon hinaus")}</button>` : ""}${saving}`;
  }
  if (bar.kind === "dispatch") {
    const copy = !active || active.main ? `<button class="cp-button ${opts.primary && !copied ? "primary" : ""}" id="copy-letter">${S.justCopied === "letter" ? `${icon("tick")}${T("Copied", "Kopiert")}` : T("Copy letter", "Brief kopieren")}</button>`
      : `<button class="cp-button ${opts.primary && !copied ? "primary" : ""}" data-copy-text="${raw(active.kind)}">${S.justCopied === active.kind ? `${icon("tick")}${T("Copied", "Kopiert")}` : T("Copy text", "Text kopieren")}</button>${docx}`;
    return `${copy}${failed}${rows.map((r, i) => dispatchControl(bar, r, opts.primary && copied && i === 0)).join("")}${pack}${note}${saving}`;
  }
  if (bar.kind === "dispatched") return `<span class="cp-sent">${icon("check")}${esc(bar.line || "")}</span>${docx}${pack}${opts.when}`;
  return opts.when || "";
}
// The way out, above the bar: per recipient the mail address (found in the file with its line, or set by the handler)
// and the subject. Before «Freigeben» they are shown, so the approval records the address; after it each copies on a
// click. No program is assumed for the sending.
function handoverLine() {
  const st = completionOf(), rows = st.handover || [], bar = st.bar || {};
  if (!rows.length || !["approve", "dispatch", "stale"].includes(bar.kind) || st.waits) return "";
  const approved = bar.kind === "dispatch", id = S.route.id, many = rows.length > 1;
  const row = (r) => {
    const a = r.address || {}, editing = S.addrEdit === r.to;
    const from = a.source ? T(`from ${a.source.name}: ${a.source.line}`, `aus ${a.source.name}: ${a.source.line}`) : a.set_by ? T(`set by ${a.set_by}`, `eingetragen von ${a.set_by}`) : "";
    const address = editing ? `<input type="email" class="cp-ho-input" data-ho-input="${raw(r.to)}" value="${raw(S.addrDraft === null || S.addrDraft === undefined ? a.value || "" : S.addrDraft)}" placeholder="name@beispiel.ch" aria-label="${T("Mail address", "E-Mail-Adresse")}">
        <button class="cp-button cp-small" data-ho-save="${raw(r.to)}">${T("Save", "Speichern")}</button>`
      : a.value ? `${approved ? `<button class="cp-ho-chip" data-ho-copy="${raw(a.value)}" title="${esc(from)}">${S.hoCopied === a.value ? icon("tick") : ""}${esc(a.value)}</button>` : `<span class="cp-ho-value" title="${esc(from)}">${esc(a.value)}</span>`}
        <button class="cp-link cp-quiet-link" data-ho-edit="${raw(r.to)}">${T("change", "ändern")}</button>`
      : `<span class="cp-ho-none">${T("no address in the file", "keine Adresse in der Akte")}</span> <button class="cp-link cp-quiet-link" data-ho-edit="${raw(r.to)}">${T("enter", "eintragen")}</button>`;
    const subject = approved ? `<button class="cp-ho-chip" data-ho-copy="${raw(r.subject)}">${S.hoCopied === r.subject ? icon("tick") : ""}${esc(r.subject)}</button>` : `<span class="cp-ho-value">${esc(r.subject)}</span>`;
    return `<p class="cp-ho-row" data-ho="${raw(r.to)}">${many ? `<b>${esc(r.title)}</b> ` : ""}<span class="cp-ho-label">${T("To", "An")}</span> ${address}
      <span class="cp-ho-label">${T("Subject", "Betreff")}</span> ${subject}</p>`;
  };
  return `<div class="cp-handover" data-handover>${rows.map(row).join("")}</div>`;
}
// A package sent to some of its recipients while the plan moved on: the others keep their «Versandt am» on the version
// approved, whatever is prepared now (completion.state ``rest``).
function restButtons() {
  const rest = (completionOf().bar || {}).rest;
  if (!rest || !(rest.recipients || []).length) return "";
  const stale = (rest.stale || []).length ? `<span class="cp-stale-bar" title="${esc(rest.stale.join(", "))}">${T("Approval stale", "Freigabe veraltet")}: ${esc(rest.stale[0])}</span>` : "";
  return `${stale}${rest.recipients.map((r) => dispatchControl(rest, r, false, true)).join("")}`;
}
// Whether the approved text was copied since it was approved (a measured copy of the same text).
function copiedApproved() {
  const st = completionOf(), at = (st.approved || {}).at, sha = (st.approved || {}).text_sha256;
  return ((S.data || {}).caseEvents || []).some((e) => e.kind === "letter.copied" && e.measure && !e.also && e.text_sha256 === sha && String(e.at || "") >= String(at || ""));
}
// Where an edited block of the letter lies in the server's text, and which parts its changed lines come from: the lines of
// the block before and after the edit are matched from both ends; what lies between is the changed region, given to the
// part of its first line (or, for an insertion, of the line above). Returns {part: new text} or null when not found.
function changedParts(text, lineParts, parts, edits) {
  const lines = String(text || "").split("\n");
  let owners = (lineParts || []).slice();
  if (owners.length !== lines.length) return null;
  const changed = new Set();
  for (const [orig, now] of Object.entries(edits)) {
    const was = String(orig).split("\n"), is = String(now).replace(/\n$/, "").split("\n");
    let at = -1;
    for (let i = 0; i + was.length <= lines.length && at < 0; i += 1) if (lines.slice(i, i + was.length).join("\n") === was.join("\n")) at = i;
    if (at < 0) return null;
    let a = 0;
    while (a < was.length && a < is.length && was[a] === is[a]) a += 1;
    let b = 0;
    while (b < was.length - a && b < is.length - a && was[was.length - 1 - b] === is[is.length - 1 - b]) b += 1;
    const from = at + a, to = at + was.length - b, middle = is.slice(a, is.length - b);
    const region = owners.slice(from, to).filter(Boolean);
    const owner = region[0] || owners.slice(0, from).filter(Boolean).pop() || owners.slice(to).find(Boolean);
    if (!owner) return null;
    owners.slice(from, to).filter(Boolean).forEach((x) => changed.add(x));
    changed.add(owner);
    lines.splice(from, to - from, ...middle);
    owners.splice(from, to - from, ...middle.map(() => owner));
  }
  const out = {};
  for (const part of changed) out[part] = lines.filter((_, i) => owners[i] === part).join("\n");
  return out;
}
// The handler's text, saved on the server per part. Returns true once nothing is left unsaved.
async function saveDraft() {
  clearTimeout(S.saveTimer);
  const d = S.data && S.data.draft;
  const study = (completionOf().bar || {}).kind === "study";
  if (!d || study || S.route.view !== "case") return true;
  if (S.saving) { await S.saving; return saveDraft(); }
  const jobs = [];
  if (Object.keys(S.blockEdits || {}).length) jobs.push({ form: d.form || d.kind, doc: d, edits: { ...S.blockEdits }, main: true });
  for (const [kind, now] of Object.entries(S.alsoEdits || {})) {
    const a = (d.also || []).find((x) => x.kind === kind);
    if (a && a.text !== now) jobs.push({ form: kind, doc: a, edits: { [a.text]: now }, main: false });
  }
  if (!jobs.length) return true;
  let ok = true;
  S.saving = (async () => {
    S.saveState = "saving";
    for (const job of jobs) {
      const parts = changedParts(job.doc.text, job.doc.line_parts, job.doc.parts, job.edits);
      if (!parts) { ok = false; S.saveState = "error"; S.saveError = T("Not saved: please reload", "Nicht gespeichert: bitte neu laden"); continue; }
      const base = (part) => ((job.doc.parts || []).find((x) => x.part === part) || {}).base_sha256 || SHA_EMPTY;
      const body = { parts: Object.entries(parts).map(([part, text]) => ({ part, base_sha256: base(part), text })), parent_id: job.doc.draft_id || null, op_id: newOp("draft") };
      try {
        const res = await api(`/api/cases/${S.route.id}/drafts/${encodeURIComponent(job.form)}`, { method: "PUT", body: JSON.stringify(body) });
        Object.assign(job.doc, { text: res.text, parts: res.parts, line_parts: res.line_parts, draft_id: res.draft_id, conflicts: res.conflicts });
        if (job.main) {
          d.version = res.version;
          for (const [orig, now] of Object.entries(job.edits)) {  // saved: the server's text holds it now; what is typed next builds on it
            const saved = String(now).replace(/\n$/, ""), later = S.blockEdits[orig];
            for (const el of document.querySelectorAll("[data-item='letter:0'] [data-seg='text']")) if (el.dataset.orig === orig) el.dataset.orig = saved;
            delete S.blockEdits[orig];
            if (later !== undefined && later !== now) S.blockEdits[saved] = later;  // typed while it was saved: kept, on the saved text
          }
        } else if (S.alsoEdits[job.form] === job.edits[Object.keys(job.edits)[0]]) delete S.alsoEdits[job.form];
        if (res.completion) S.data.completion = res.completion;
      } catch (error) { ok = false; S.saveState = "error"; S.saveError = error.message; }
    }
    if (ok) S.saveState = "saved";
  })();
  await S.saving;
  S.saving = null;
  return ok;
}
const onCase = () => S.route.view === "case" && Boolean(S.data);
function scheduleSave() {
  clearTimeout(S.saveTimer);
  S.saveTimer = setTimeout(() => { saveDraft().then(() => { if (onCase() && !inLetter()) renderCase(); }); }, 1500);
}
const inLetter = () => Boolean(document.activeElement && document.activeElement.closest && document.activeElement.closest("[data-item='letter:0']"));
// «Freigeben»: the text saved first, then the version shown approved; the server says why not, in the handler's words.
// One approval covers every document of the step. Until each has been shown, the button leads to the next one not yet
// seen and says so; only then does it approve.
// What a document of the step still asks the handler to choose (the scope of a cost approval): a list with values and
// none taken yet. It is never sent on a default.
const unsetChoices = () => ((S.data.draft || {}).also || []).flatMap((a) => (a.set || []).filter((key) => { const f = item("fact", key) || {}; return (f.values || []).length && (f.value === null || f.value === undefined || f.value === ""); })
  .map((key) => ({ kind: a.kind, key, name: plainQuestion(((item("fact", key) || {}).label || {}).de || key).replace(/\s*\(.*$/, "") })));
function approveLabel() {
  const out = documentsOut(), next = (out.unseen || [])[0], pend = unsetChoices()[0];
  if (!(next && out.rows.length > 1) && pend) return `${T("Choose", "Wählen")}: ${esc(clip(pend.name, 40))}`;
  return next && out.rows.length > 1 ? `${T("Next", "Weiter")}: ${esc(clip(next.title, 34))} <span class="cp-approve-n">${out.rows.length - out.unseen.length + 1} ${T("of", "von")} ${out.rows.length}</span>` : T("Approve and copy", "Freigeben und kopieren");
}
async function approve() {
  const out = documentsOut();
  if (out.rows.length > 1 && (out.unseen || []).length) { S.docTab = out.unseen[0].kind; S.docPicked = true; await renderCase(); const tabs = document.querySelector(".cp-doc-tabs"); if (tabs) tabs.scrollIntoView({ block: "nearest" }); return; }
  const pend = unsetChoices()[0];
  if (pend) { S.docTab = pend.kind; S.docPicked = true; await renderCase(); const sel = document.querySelector(`[data-also-set="${CSS.escape(pend.key)}"]`); if (sel) { sel.scrollIntoView({ block: "center" }); sel.focus(); } return; }
  S.docTab = null; S.docPicked = false;   // approved: back to the first document that still has to go out (the letter itself)
  if (!(await saveDraft())) { renderCase(); return; }
  const d = S.data.draft || {};
  try {
    await api(`/api/cases/${S.route.id}/actions/approve`, { method: "POST", body: JSON.stringify({ form: d.form || d.kind, version: d.version, op_id: newOp("approve") }) });
    S.message = ""; S.copyFailed = false;
  } catch (error) { S.message = error.message; S.messageOk = false; await loadCase(); return; }
  await loadCase();
  // the approval puts the approved text on the clipboard («Freigeben und kopieren»); where the browser refuses, «Brief
  // kopieren» stays the next step as before and nothing is recorded
  const active = documentsOut().active;
  if (onCase() && (completionOf().bar || {}).kind === "dispatch" && active) await copyLetter(active.main ? null : active.kind, true);
}
// A copy to the clipboard: awaited; refused or without a clipboard the text is selected and nothing is recorded.
// The approved text as the same paragraphs in HTML: a blank line ends a paragraph, a line break stays one.
function letterHtml(text) {
  const inner = String(text || "").replace(/^\n+|\n+$/g, "").split(/\n\s*\n/).filter((p) => p.trim())
    .map((p) => `<p style="margin:0 0 12px 0">${p.split("\n").map(esc).join("<br>")}</p>`).join("");
  return `<div style="font-family:Arial, Helvetica, sans-serif;font-size:11pt;line-height:1.35;color:#000">${inner}</div>`;
}
// A letter on the clipboard as formatted text and as plain text, so a mail keeps its paragraphs; plain text where the
// browser cannot write both.
async function letterToClipboard(text, select) {
  try {
    if (navigator.clipboard && navigator.clipboard.write && window.ClipboardItem) {
      await navigator.clipboard.write([new ClipboardItem({ "text/html": new Blob([letterHtml(text)], { type: "text/html" }), "text/plain": new Blob([text], { type: "text/plain" }) })]);
      return true;
    }
  } catch (error) { /* plain text below */ }
  return toClipboard(text, select);
}
async function toClipboard(text, select) {
  try {
    if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error("no clipboard");
    await navigator.clipboard.writeText(text);
    return true;
  } catch (error) {
    if (select) { const range = document.createRange(); range.selectNodeContents(select); const sel = window.getSelection(); sel.removeAllRanges(); sel.addRange(range); }
    return false;
  }
}
// «Brief kopieren»: the approved text (the version approved is the version shown: same text, same hash), measured.
async function copyLetter(kind, quietly) {
  const d = S.data.draft || {}, st = completionOf();
  const doc = kind ? (d.also || []).find((a) => a.kind === kind) || {} : d;
  const text = doc.text || "";
  if (!kind && (st.approved || {}).text_sha256 && (await sha256(text)) !== st.approved.text_sha256) {
    S.message = T("The text changed since the approval: please approve again", "Der Text hat sich seit der Freigabe geändert: bitte erneut freigeben"); S.messageOk = false; renderCase(); return;
  }
  const ok = await letterToClipboard(text, $(kind ? `[data-also-text='${CSS.escape(kind)}']` : "[data-item='letter:0']"));
  if (!ok) { S.copyFailed = !quietly; renderCase(); return; }
  S.copyFailed = false; S.justCopied = kind || "letter";
  const act = item("next_action", "0") || {};
  await caseEvent("letter.copied", null, { ...(kind ? { also: kind } : { form: d.form || d.kind }), measure: true, text_sha256: await sha256(text), edited: false,
    ...(act.deadline ? { deadline: act.deadline } : {}) }).catch(() => {});
  setTimeout(() => { S.justCopied = false; if (S.route.view === "case") renderCase(); }, 1800);
  await loadCase();
}
// «Versandt am»: the handler confirms that the approved version went out to this recipient, on this day, by this channel.
async function dispatchTo(role, version) {
  const bar = completionOf().bar || {};
  const day = ($(`[data-dispatch-date='${CSS.escape(role)}']`) || {}).value || isoToday();
  const channel = ($(`[data-dispatch-channel='${CSS.escape(role)}']`) || {}).value || bar.channel || "post";
  try {
    await api(`/api/cases/${S.route.id}/actions/dispatch`, { method: "POST", body: JSON.stringify({ version: version || bar.version, recipients: [role], date: day, channel, op_id: newOp("dispatch") }) });
    S.message = "";
  } catch (error) { S.message = error.message; S.messageOk = false; }
  await loadCase();
}
// The handlers of the carried decision, bound with the card's own (bindOverview).
function bindCarry(on) {
  on("[data-item='letter:0'] [data-seg='text'][data-editable]", "input", () => scheduleSave());
  on("[data-item='letter:0'] [data-seg='also'][data-editable]", "input", () => scheduleSave());
  on("[data-item='letter:0'] [data-editable]", "blur", () => { setTimeout(() => { if (onCase() && !inLetter()) saveDraft().then(() => { if (onCase() && !inLetter()) renderCase(); }); }, 0); });
  on("#approve", "click", (b) => { b.disabled = true; approve(); });
  on("#fill-gaps", "click", (b) => { if (Number(b.dataset.gaps || 0) && goToGap()) return; b.disabled = true; approve(); });
  on("#to-conflicts", "click", () => { const box = $("#conflicts"); if (box) box.scrollIntoView({ block: "nearest" }); });
  // a changed letter is approved again before it goes out; that the earlier version already went is said on purpose
  on("#stale-sent", "click", () => { S.staleSent = S.route.id; renderCase(); });
  on("#sent-open", "click", async (b) => {  // the letter that went out, read where the case is read
    const id = S.route.id, version = b.dataset.version;
    if (S.sentOpen && S.sentOpen.case === id && S.sentOpen.version === version) { S.sentOpen = null; renderCase(); return; }
    S.sentOpen = { case: id, version }; renderCase();
    try { S.sentOpen.letter = await api(`/api/cases/${id}/actions/${version}/letter`); } catch (error) { S.sentOpen.error = error.message; }
    if (onCase() && S.route.id === id) renderCase();
  });
  on("#copy-letter", "click", () => copyLetter(null));
  on("[data-copy-text]", "click", (b) => copyLetter(b.dataset.copyText));
  on("[data-dispatch]", "click", (b) => { b.disabled = true; dispatchTo(b.dataset.dispatch, b.dataset.dispatchVersion || null); });
  on("[data-dispatch-date]", "change", (el) => {  // the button's name says the day it confirms
    const b = $(`[data-dispatch='${CSS.escape(el.dataset.dispatchDate)}']`);
    if (b && el.value) b.setAttribute("aria-label", b.getAttribute("aria-label").replace(/\d{2}\.\d{2}\.\d{4}/, dateText(el.value)));
  });
  on("#copy-note-bar", "click", () => copyNote());
  on("[data-ho-copy]", "click", async (b) => {
    if (await toClipboard(b.dataset.hoCopy, b)) { S.hoCopied = b.dataset.hoCopy; renderCase(); setTimeout(() => { S.hoCopied = null; if (S.route.view === "case") renderCase(); }, 1800); }
  });
  on("[data-ho-edit]", "click", (b) => { S.addrEdit = b.dataset.hoEdit; S.addrDraft = null; renderCase(); const el = $("[data-ho-input]"); if (el) el.focus(); });
  on("[data-ho-input]", "input", (el) => { S.addrDraft = el.value; });
  const saveAddress = async (to) => {
    const el = $(`[data-ho-input='${CSS.escape(to)}']`);
    try {
      await api(`/api/cases/${S.route.id}/handover/address`, { method: "POST", body: JSON.stringify({ to, address: (el || {}).value || "" }) });
      S.addrEdit = null; S.addrDraft = null; S.message = "";
    } catch (error) { S.message = error.message; S.messageOk = false; }
    await loadCase();
  };
  on("[data-ho-save]", "click", (b) => saveAddress(b.dataset.hoSave));
  on("[data-ho-input]", "keydown", (el, event) => { if (event.key === "Enter") { event.preventDefault(); saveAddress(el.dataset.hoInput); } if (event.key === "Escape") { S.addrEdit = null; S.addrDraft = null; renderCase(); } });
  on("[data-head-open]", "click", (b) => { S.headOpen = S.headOpen === b.dataset.headOpen ? null : b.dataset.headOpen; renderCase(); });
  on("[data-reconcile]", "click", async (b) => {
    b.disabled = true;
    await api(`/api/cases/${S.route.id}/actions/reconcile`, { method: "POST", body: JSON.stringify({ version: b.dataset.reconcile, op_id: newOp("reconcile") }) })
      .catch((error) => { S.message = error.message; S.messageOk = false; });
    await loadCase();
  });
  on("[data-resolve]", "click", async (b) => {
    await api(`/api/cases/${S.route.id}/drafts/${encodeURIComponent(b.dataset.form)}/resolve`, { method: "POST", body: JSON.stringify({ part: b.dataset.resolve, keep: b.dataset.keep }) })
      .catch((error) => { S.message = error.message; S.messageOk = false; });
    await loadCase();
  });
  // the stable mark of the editable letter's parts (MEASURE, check_simple): each text block names the parts its lines come from
  const d = S.data.draft || {}, lines = d.line_parts || [];
  let at = 0;
  const text = String(d.text || "").split("\n");
  for (const el of document.querySelectorAll("[data-item='letter:0'] [data-seg]")) {
    const own = el.dataset.seg === "list" ? [...el.querySelectorAll(":scope > li[data-text]")].map((li) => li.dataset.text) : String(el.dataset.orig || "").split("\n");
    const first = text.indexOf(own[0], at);
    if (first < 0) continue;
    if (el.dataset.seg === "text") el.dataset.letterParts = [...new Set(lines.slice(first, first + own.length).filter(Boolean))].join(" ");
    at = first + own.length;
  }
}
// «Aktennotiz kopieren»: awaited; a failure says so and records nothing.
async function copyNote() {
  const ok = await toClipboard(S.data.file_note || "", null);
  if (!ok) { S.copyFailed = true; renderCase(); return; }
  S.copyFailed = false;
  await caseEvent("filenote.copied", null, { chars: (S.data.file_note || "").length, measure: true }).catch(() => {});
  S.noteCopied = true; renderCase(); setTimeout(() => { S.noteCopied = false; if (S.route.view === "case") renderCase(); }, 1800);
}
// The case list in its groups: what needs the handler's judgment, what is ready to send, what waits, what failed; done
// folded below. «Fehlgeschlagen» is shown only when a case is in it.
const BUCKETS = lazy(() => ([["urteil", T("To decide", "Zu entscheiden")], ["versandbereit", T("Ready to send", "Versandbereit")],
  ["wartet", T("Waiting", "Wartet")], ["fehlgeschlagen", T("Failed", "Fehlgeschlagen")]]));
function bucketOf(c) { return (c.stand || {}).bucket || (standOf(c) === "closed" ? "erledigt" : "urteil"); }
// Working through: the cases that need the reader, top to bottom as the list shows them (real cases before the examples,
// «Braucht Ihr Urteil» before «Versandbereit»). «Nächster Fall» opens the first one not yet passed in this walk, so a case
// left untouched is not offered twice; the walk ends at the list and starts afresh with «Fälle durchgehen».
const needsReader = (c) => !c.locked && !c.historic && ["urteil", "versandbereit"].includes(bucketOf(c));
function walkOrder(cases) {
  // the walk goes through what the list shows: «Meine», and the count the list is narrowed to
  const only = ["due", "urteil", "versandbereit"].includes(S.listFilter) ? LIST_FILTERS[S.listFilter] : null, today = isoToday();
  const rows = orderedCases(cases.filter((c) => needsReader(c) && (!S.listMine || c.mine) && (!only || only(c, today))));
  const group = (list) => ["urteil", "versandbereit"].flatMap((b) => list.filter((c) => bucketOf(c) === b));
  return [...group(rows.filter((c) => !(c.intake || {}).synthetic)), ...group(rows.filter((c) => (c.intake || {}).synthetic))];
}
function walkMemory() {
  let kept = S.walk;
  try { kept = JSON.parse(sessionStorage.getItem("cp-walk") || "null") || kept; } catch (error) { /* this page only, in memory */ }
  return { passed: (kept && kept.passed) || [], order: (kept && kept.order) || [], total: (kept && kept.total) || 0 };
}
// Where the reader stands in the walk: «3 / 31» beside «Nächster Fall» and a hairline under the top bar.
function walkPlace(id) {
  const kept = walkMemory(), order = kept.order, at = order.indexOf(id);
  if (at < 0 || order.length < 2) return { label: "", bar: "" };
  const left = order.length - at, total = Math.max(kept.total || 0, left);
  return { label: `<span class="cp-walk-count" title="${T("cases of this walk still ahead, this one included", "Fälle dieses Durchgangs, die noch vor Ihnen liegen, dieser eingeschlossen")}">${T(`${left} ${left === 1 ? "case" : "cases"} to go`, `noch ${left} ${left === 1 ? "Fall" : "Fälle"}`)}</span>`,
           bar: `<span class="cp-walkbar" style="width:${Math.round(100 * (total - left) / total)}%" aria-hidden="true"></span>` };
}
function walkKeep(kept) { S.walk = kept; try { sessionStorage.setItem("cp-walk", JSON.stringify(kept)); } catch (error) { /* this page only, in memory */ } }
async function nextCase(fresh) {
  const here = S.route.view === "case" ? S.route.id : null;
  const kept = fresh ? { passed: [], order: [], total: 0 } : walkMemory();
  const passed = [...new Set([...kept.passed, ...(here ? [here] : [])])];
  const order = walkOrder((await api("/api/cases")).cases);
  const open = order.filter((c) => c.id !== here && !passed.includes(c.id));
  // the case below the one shown: by the list as it is now, or, for a case that just left it, as it was read last
  const at = order.findIndex((c) => c.id === here);
  const below = at >= 0 ? order.slice(at + 1).map((c) => c.id) : kept.order.slice(kept.order.indexOf(here) + 1);
  const next = open.find((c) => below.includes(c.id)) || open[0];
  walkKeep(next ? { passed, order: order.map((c) => c.id), total: kept.total || order.length } : { passed: [], order: [], total: 0 });
  S.walkEnd = !next && !fresh;
  S.arriveNext = Boolean(next);  // the next case comes in from where the reader is going
  if (!next && S.route.view !== "case") { await route(); return; }
  location.hash = next ? `#/case/${next.id}/overview` : "#/cases";
}
function bucketTables(rows, table, level) {
  const out = BUCKETS().map(([key, title]) => {
    const own = rows.filter((c) => bucketOf(c) === key);
    if (!own.length) return "";
    return `<h${level} class="cp-bucket ${key}" data-bucket="${key}">${esc(title)} · ${own.length}</h${level}>${table(own)}`;
  }).join("");
  const done = rows.filter((c) => bucketOf(c) === "erledigt");
  return out + (done.length ? `<details class="cp-bucket-done" data-bucket="erledigt"><summary class="cp-bucket erledigt">${T("Done", "Erledigt")} · ${done.length}</summary>${table(done)}</details>` : "");
}

// ---------- arrival: what came in, the update, corrections and the account's checks (Slice C) ----------
// Why «Aktualisieren» did not start by itself after an upload (the server's reason, web/app.py _arrival_view): its title.
function autoTitle(u) {
  const reason = (u || {}).auto;
  if (!reason) return "";
  if (reason === "aus") return T("Automatic updating is switched off", "Automatische Aktualisierung ist ausgeschaltet");
  if (reason === "zu_gross") return T(`Automatically only up to ${u.max_pages} pages: please start it yourself`, `Automatisch nur bis ${u.max_pages} Seiten: bitte selbst starten`);
  if (reason === "lauf_aktiv") return T("A run is in progress", "Ein Lauf ist im Gang");
  if (reason === "anmelden") return T("Sign in again to update", "Zum Aktualisieren erneut anmelden");
  return u.text || "";
}
// Knowledge is approved only after a replay of its current version (HANDLER_BAR L3): each item of a card (the same item
// seeded for an area and the intake it replaced) has its own; «ändert n von m Fällen», the changes by case, then «Freigeben».
const KNOWLEDGE_CHANGE = lazy(() => ({ needs: T("documents", "Unterlagen"), now: T("asked now", "jetzt verlangt"), offered: T("offered", "angeboten"),
                           later: T("asked later", "später verlangt"), questions: T("questions", "Fragen"), next_action: T("next step", "nächster Schritt") }));
// A replay counts for the version it played and, for a refinement, for the version of the item it refines it played on.
function replayCurrent(k, all) {
  return k.ids.every((id) => {
    const it = all.find((x) => x.id === id), r = it && it.replay;
    if (!r || r.version !== it.version) return false;
    const target = it.refines ? all.find((x) => x.id === it.refines) : null;
    return !target || r.target_version === target.version;
  });
}
function replayLine(k, all, caseName) {
  if (!replayCurrent(k, all)) return `<span class="cp-muted">${T("Its effect on the stored cases is not known yet.", "Die Wirkung auf die vorbereiteten Fälle ist noch nicht bekannt.")}</span>`;
  const replays = k.ids.map((id) => all.find((x) => x.id === id).replay);
  const changed = {};
  for (const r of replays) for (const row of r.changed || []) changed[row.case] = [...new Set([...(changed[row.case] || []), ...row.changed])];
  const total = Math.max(...replays.map((r) => r.cases || 0)), n = Object.keys(changed).length;
  return `<details class="cp-replay"><summary class="cp-link">${T(`changes ${n} of ${total} cases`, `ändert ${n} von ${total} Fällen`)}</summary>
    <ul class="cp-log">${Object.entries(changed).map(([id, what]) => `<li><a href="#/case/${raw(id)}/overview">${esc(caseName(id))}</a> <span class="cp-muted">· ${what.map((w) => esc(KNOWLEDGE_CHANGE()[w] || w)).join(", ")}</span></li>`).join("")}</ul></details>`;
}
// An update at work says what it reads: «Neu eingegangen: 2 Datei(en) · wird aktualisiert»; one started again after a
// restart says so («wird fortgesetzt»).
function arrivalNow(run) {
  if (!run || run.kind !== "update") return "";
  const came = (S.data.arrived || []).length || (S.data.new_files || []).length;
  const resumed = ((S.data || {}).caseEvents || []).some((e) => e.kind === "update.started" && e.run === run.id && e.resumed);
  return `<p class="cp-runnow cp-arrival-now"><b>${resumed ? T("Update interrupted: the service was restarted", "Aktualisierung unterbrochen: Der Dienst wurde neu gestartet")
    : T(`${came} new ${came === 1 ? "file" : "files"}`, `${came} neue ${came === 1 ? "Datei" : "Dateien"}`)}</b> · ${resumed ? T("continues", "wird fortgesetzt") : T("updating", "wird aktualisiert")}</p>`;
}
