"use strict";
// CasePath internal workspace: one page on the live API. Everything shown comes from
// the case store, the agents' recorded work and the Knowledge base; nothing is staged.

// Case workers read German; English stays available for demonstrations (?lang=en, remembered in this browser).
const LANG = (() => {
  const asked = new URLSearchParams(location.search).get("lang");
  try {
    if (asked) localStorage.setItem("casepath.lang", asked);
    return asked || localStorage.getItem("casepath.lang");
  } catch (error) { return asked; }
})() === "en" ? "en" : "de";
const T = (en, de) => (LANG === "de" ? de : en);
document.documentElement.lang = LANG;
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
const TASK = {
  lead: T("Prepare the case", "Den Fall vorbereiten"),
  claim_reader: T("Read the files and record the facts", "Dokumente lesen und Fakten festhalten"),
  process_builder: T("Build this case’s process", "Den Prozess dieses Falls aufbauen"),
  document_finder: T("Find each needed document in the files", "Jedes verlangte Dokument in den Dateien finden"),
  source_checker: T("Check each finding against its quote", "Jede Feststellung an ihrem Zitat prüfen"),
  result_checker: T("Evaluate, draft the reply and propose what to learn", "Auswerten, Antwort entwerfen, Lernvorschläge machen"),
};

const ICONS = {
  doc: '<path d="M7 3h7l4 4v14H7z"/><path d="M14 3v4h4M9.5 12h6M9.5 15.5h6M9.5 9h3"/>',
  mail: '<rect x="3" y="5.5" width="18" height="13" rx="1.5"/><path d="m3.5 7 8.5 6.5L20.5 7"/>',
  image: '<rect x="3.5" y="4.5" width="17" height="15" rx="1.5"/><circle cx="9" cy="10" r="1.8"/><path d="m4 18 5.5-5 4 3.5 2.5-2 4 3.5"/>',
  shield: '<path d="M12 3 5 6v5.5c0 4.3 3 7.7 7 9.5 4-1.8 7-5.2 7-9.5V6z"/><path d="m9 12 2.2 2.2L15.5 10"/>',
  nodes: '<circle cx="12" cy="5.5" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M12 8v3.5M6 15.5V13.5h12v2M12 11.5v2"/>',
  folder: '<path d="M3.5 6.5h6l2 2h9v10.5h-17z"/>',
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
const AGENTS = [
  ["claim_reader", T("Claim reader", "Fallleser"), "doc"], ["source_checker", T("Source checker", "Quellenprüfer"), "shield"],
  ["process_builder", T("Process builder", "Prozessbauer"), "nodes"], ["document_finder", T("Document finder", "Dokumentenfinder"), "folder"],
  ["result_checker", T("Result checker", "Ergebnisprüfer"), "check"],
];
const AGENT_TITLE = Object.fromEntries(AGENTS.map(([id, title]) => [id, title]).concat([["lead", T("Lead", "Leitung")]]));
const AGENT_ICON = Object.fromEntries(AGENTS.map(([id, , i]) => [id, i]).concat([["lead", "nodes"]]));
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (selector, root = document) => root.querySelector(selector);
const S = { me: null, route: {}, data: null, pages: {}, file: null, page: null, step: null, editing: false, lastEdit: null,
            events: [], poll: null, follow: true, knowledge: null, workflows: null, message: "", shown: new Set(), litKey: null };

async function api(path, options = {}) {
  const headers = options.body && !(options.body instanceof FormData) ? { "content-type": "application/json" } : {};
  const response = await fetch(path, { ...options, headers });
  const type = response.headers.get("content-type") || "";
  const body = type.includes("json") ? await response.json() : await response.text();
  if (!response.ok) throw new Error((body && body.detail) || response.statusText);
  return body;
}

function parseRoute() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "case" && parts[1]) return { view: "case", id: parts[1], tab: parts[2] || "overview" };
  if (parts[0] === "knowledge" && parts[1] === "gebiet" && parts[2]) return { view: "review", id: decodeURIComponent(parts[2]) };
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
  const wordmark = `<a class="cp-wordmark" href="#/cases"><svg viewBox="0 0 28 28" aria-hidden="true"><path d="M22 6.5A10 10 0 1 0 22 21.5" fill="none" stroke="#82072a" stroke-width="4.5" stroke-linecap="round"/></svg>CasePath</a>`;
  let tabs;
  if (route.view === "case") {
    tabs = [["overview", T("Overview", "Übersicht"), "check"], ["claim_reader", T("File", "Akte"), "doc"], ["process_builder", T("Process", "Prozess"), "nodes"],
            ["document_finder", T("Documents", "Unterlagen"), "folder"], ["history", T("History", "Verlauf"), "memory"]].map(([id, title, ic]) => `<a class="cp-tab" href="#/case/${esc(route.id)}/${id}"
      ${route.tab === id ? 'aria-current="page"' : ""} data-tab="${id}">${icon(ic)}${title}</a>`).join("");
  } else {
    tabs = `<a class="cp-tab" href="#/cases" ${route.view === "cases" ? 'aria-current="page"' : ""}>${icon("folder")}${T("Cases", "Fälle")}</a>`;
  }
  const other = LANG === "de" ? "en" : "de";
  $("#top").innerHTML = `${wordmark}<nav class="cp-tabs" aria-label="${T("Views", "Ansichten")}">${tabs}</nav>
    <div class="cp-top-right">${route.view === "case" ? `<a class="cp-link" href="#/cases">${T("Cases", "Fälle")}</a>` : adminMenu(route)}<span>${esc(S.me || "")}</span>
      <a class="cp-link" href="?lang=${other}${esc(location.hash)}" lang="${other}">${other.toUpperCase()}</a></div>`;
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
                   working: "in progress", new: "not prepared", arrived: "new files", closed: "done" };
const standOf = (c) => (c.stand || {}).kind || "new";
const standText = (c) => (LANG === "de" ? (c.stand || {}).text : STAND_EN[standOf(c)]) || "—";
// The first contact the insurer promises (three working days from the report) is the case's next date while it is open.
// «Fällig»: the earliest of the case's deadlines, set dates, follow-up and first contact, with its word (listing.due).
const DUE_EN = { Frist: "deadline", Termin: "date set", Wiedervorlage: "follow-up", Erstkontakt: "first contact" };
const dueWord = (w) => (LANG === "de" ? w : DUE_EN[w] || w);
function orderedCases(cases) {
  const rank = (c) => (c.stand || {}).rank ?? 5;
  return [...cases].sort((a, b) => rank(a) - rank(b) || ((a.stand || {}).date || (a.due || {}).date || "9999").localeCompare((b.stand || {}).date || (b.due || {}).date || "9999"));
}
async function renderCases() {
  const [cases, workflows, health] = await Promise.all([api("/api/cases"), api("/api/workflows"), api("/api/health")]);
  const imports = health.imports ? await api("/api/imports").catch(() => null) : null;
  S.workflows = workflows.workflows;
  const today = isoToday();
  // One row per case, in the words its card uses: the case and its parties, what comes next (the card's title), when it
  // is due and why (a deadline, a date set, the follow-up, the first contact), its status (the card's chip).
  const row = (c) => {
    // a historic cut is looked at as of its own day: its dates are never overdue among live cases
    const s = standOf(c), due = s === "closed" ? null : c.due, late = due && due.date <= (c.as_of || today) && !c.as_of && !c.historic;
    const next = s === "closed" ? "" : c.next_action ? esc(LANG === "de" && c.next_action.text ? c.next_action.text : T(c.next_action.label.en, c.next_action.label.de))
      : s === "working" ? T("being prepared", "wird vorbereitet") : s === "new" ? T("prepare the case", "Fall vorbereiten") : "";
    return `<tr class="${s === "closed" ? "cp-done" : ""}"><td><a href="#/case/${esc(c.id)}/overview">${esc(c.headline || c.display_title || c.title)}</a>${c.parties ? `<small class="cp-parties">${esc(c.parties)}</small>` : ""}</td>
      <td>${next || '<span class="cp-muted">—</span>'}</td>
      <td class="cp-nowrap ${late ? "cp-late" : ""}">${due ? `${dateText(due.date)} <span class="cp-due-word">${esc(dueWord(due.word))}</span>` : '<span class="cp-muted">—</span>'}</td>
      <td><span class="cp-stand ${s}">${esc(standText(c))}</span></td></tr>`;
  };
  const table = (rows) => `<table class="cp-table cp-cases"><thead><tr><th>${T("Case", "Fall")}</th><th>${T("Next", "Als Nächstes")}</th>
    <th>${T("Due", "Fällig")}</th><th>${T("Status", "Status")}</th></tr></thead><tbody>${rows.map(row).join("")}</tbody></table>`;
  const ordered = orderedCases(cases.cases);
  // historic files (test cuts, whole old files uploaded for testing, or as a person placed them): listed apart, never overdue
  const historic = ordered.filter((c) => c.historic);
  const live = ordered.filter((c) => !historic.includes(c));
  const real = live.filter((c) => !(c.intake || {}).synthetic), examples = live.filter((c) => (c.intake || {}).synthetic);
  // files dropped anywhere on the list make a new case; the hint stands beside «Neuer Fall», a box only while there is no case
  const any = ordered.length && !S.creating;
  $("#app").innerHTML = `<main class="cp-main cp-list"><div class="cp-list-head"><h1 class="cp-title">${T("Cases", "Fälle")}</h1>
      ${S.canUpload === false ? "" : `<span class="cp-list-new">${any ? `<span class="cp-muted">${T("or drop files here", "oder Dateien hierher ziehen")}</span>` : ""}
        <label class="cp-button primary">${icon("plus")}${T("New case", "Neuer Fall")}<input type="file" id="new-files" multiple hidden></label></span>`}</div>
    ${real.length ? table(real) : ""}
    ${S.canUpload === false || any ? "" : `<div class="cp-drop" id="drop">${S.creating ? T("Creating the case…", "Der Fall wird angelegt …") : T("Drop files here and CasePath prepares the case", "Dateien hierher ziehen, CasePath bereitet den Fall vor")}</div>`}
    ${S.message ? `<p class="cp-error">${esc(S.message)}</p>` : ""}
    ${examples.length ? `<h2 class="cp-section cp-muted">${T("Examples", "Beispiele")}</h2>${table(examples)}` : ""}
    ${historic.length ? `<h2 class="cp-section cp-muted">${T("Historic files", "Historische Akten")}</h2>${table(historic)}` : ""}
    ${imports ? `<h2 class="cp-section">${T("Case files waiting to be imported", "Bereitgestellte Akten")}</h2>
      ${imports.files.length ? `<table class="cp-table"><tbody>${imports.files.map((f) =>
        `<tr><td><b>${esc(f.title || f.name)}</b>${f.title && f.title !== f.name ? `<br><small class="cp-muted">${esc(f.name)}</small>` : ""}</td>
        <td>${f.prepared ? T(`prepared · ${f.files ?? "?"} file(s)${f.pages ? ` · ${f.pages} pages` : ""}`, `vorbereitet · ${f.files ?? "?"} Datei(en)${f.pages ? ` · ${f.pages} Seiten` : ""}`)
          : f.size ? `${(f.size / 1048576).toFixed(1)} MB` : "—"}</td><td>${f.case ? `<a class="cp-link" href="#/case/${esc(f.case)}/overview">${T("Open case", "Fall öffnen")}</a>`
          : `<button class="cp-button" data-import="${esc(f.path)}">${icon("plus")}${T("Import", "Importieren")}</button>`}</td></tr>`).join("")}</tbody></table>`
        : `<p class="cp-muted">${T("No files there yet.", "Noch keine Dateien dort.")}</p>`}` : ""}</main>`;
  S.message = "";
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
  return `<small class="cp-area-review ${a.state === "freigegeben" ? "released" : ""}" title="${esc(a.title || "")}">${esc(a.label)}</small>`;
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
  if (kind === "image") return `<span class="cp-fileicon"><img alt="" src="/api/files/${esc(file.id)}/original" loading="lazy"></span>`;
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
  return error;
}

// ---------- rail ----------
// The rail holds the case: its name (renamed in place), its parties, its status in the case list's words, a historic
// file's last day; then its files and «Hinzufügen»; everything else is under «Mehr».
const caseName = (c) => c.headline || c.display_title || c.title;
function renderRail() {
  const d = S.data, files = d.files || [], st = d.status || {};
  const rows = files.map((f) => `<button class="cp-source" data-file="${esc(f.id)}" aria-current="${S.file === f.id}">${fileIcon(f)}
      <span class="cp-source-label">${esc(f.name)}<small>${f.extraction && f.extraction.attached_to ? `${T("Attached to", "Anhang von")} ${esc(f.extraction.attached_to)}`
        : dateText(f.created_at)}${f.extraction && f.extraction.pages > 1 ? ` · ${(f.extraction.kept_pages || []).length || f.extraction.pages} ${T("pages", "Seiten")}` : ""}</small>
      ${(f.extraction && (f.extraction.instruction_like || []).length) ? `<span class="cp-warn">${T("Contains text addressed to an AI", "Enthält Text an die KI")}</span>` : ""}</span></button>${segmentRows(f)}`).join("");
  return `<aside class="cp-rail" aria-label="${T("Files", "Dateien")}">
    <div class="cp-caseline"><div id="case-title" contenteditable="plaintext-only" role="textbox" aria-label="${T("Name of the case", "Name des Falls")}" title="${T("Rename", "Umbenennen")}">${esc(caseName(d.case))}</div>
      ${d.case.parties ? `<small class="cp-parties">${esc(d.case.parties)}</small>` : ""}
      ${st.text || d.historic ? `<p class="cp-rail-chips">${st.text ? `<span class="cp-stand ${esc(st.kind || "")}" data-status>${esc(LANG === "de" ? st.text : STAND_EN[st.kind] || st.text)}</span>` : ""}${standAm(d)}</p>` : ""}${areaLine(d)}</div>
    <div class="cp-rail-head">${T("Files", "Dateien")}<span>${files.length}</span>${S.canUpload === false || unaidedPending() ? "" : `<label class="cp-link">${icon("plus")}${T("Add", "Hinzufügen")}<input type="file" id="upload" multiple hidden></label>`}</div>
    ${S.message ? `<p class="${S.messageOk ? "cp-muted" : "cp-error"}" style="padding:0 27px" role="status">${esc(S.message)}</p>` : ""}
    ${rows || `<div class="cp-drop" id="drop">${T("Drop the case files here", "Dateien hierher ziehen")}</div>`}
    <div class="cp-rail-foot">${unaidedPending() ? "" : moreMenu()}</div>
  </aside>`;
}
function moreMenu() {
  const d = S.data, run = d.run, done = S.data.lastCompleted;
  const options = (S.workflows || []).map((w) => `<option value="${esc(w.id)}" ${d.case.workflow_id === w.id ? "selected" : ""}>${esc(w.short_title || w.title)}</option>`).join("");
  return `<details class="cp-more" ${S.moreOpen ? "open" : ""}><summary class="cp-link">${T("More", "Mehr")}</summary><div class="cp-menu">
    <label>${T("Process", "Prozess")}<select id="workflow"><option value="">${T("from the files", "aus den Akten bestimmen")}</option>${options}</select></label>
    ${running() || !(d.files || []).length ? "" : `<button class="cp-link" id="run">${icon("nodes")}${run ? T("Prepare anew", "Ganz neu vorbereiten") : T("Prepare case", "Fall vorbereiten")}</button>`}
    ${S.file ? `<a class="cp-link" href="/api/files/${esc(S.file)}/original" target="_blank" rel="noopener">${icon("external")}${T("Open original", "Original öffnen")}</a>` : ""}
    ${done ? `<a class="cp-link" href="/api/cases/${esc(d.case.id)}/report.docx?lang=${LANG}">${icon("doc")}${T("Case report (.docx)", "Fallbericht (.docx)")}</a>` : ""}
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
  return `<ol class="cp-segs" aria-label="${T("Documents in", "Dokumente in")} ${esc(file.name)}">${segments.map((s) => `<li><button class="cp-seg" data-file="${esc(file.id)}" data-page="${s.first_page}" title="${esc(s.summary || "")}">
    <span>${esc(s.title || s.kind)}</span><small>${esc([s.kind !== s.title ? s.kind : "", s.date, `${T("p.", "S.")} ${s.first_page}${s.last_page !== s.first_page ? `–${s.last_page}` : ""}`].filter(Boolean).join(" · "))}${olderDocument(s) ? ` · <span class="cp-older">${T("older document", "älteres Dokument")}</span>` : ""}</small></button></li>`).join("")}</ol>`;
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
      if (!value || value === shown) { title.textContent = shown; return; }
      const renamed = await api(`/api/cases/${S.route.id}/title`, { method: "PUT", body: JSON.stringify({ title: value }) }).catch(() => null);
      if (renamed) S.data.case = { ...S.data.case, ...renamed, display_title: renamed.title, headline: renamed.title };
      title.textContent = caseName(S.data.case);
    };
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
  const live = ranges.find((r) => r.live);  // the quote being worked on wins over earlier marks it overlaps
  if (live) ranges = ranges.filter((r) => r.live || r.b <= live.a || r.a >= live.b);
  let out = "", at = from;
  for (const r of ranges) {
    if (r.a < at) continue;
    out += esc(raw.slice(at, r.a)) + `<mark class="cp-hit ${r.live ? `live${S.litKey === r.key ? " lit" : ""}` : "cited"}" ${r.live ? 'id="live-hit"' : ""}>${esc(raw.slice(r.a, r.b))}</mark>`;
    at = r.b;
  }
  return out + esc(raw.slice(at));
}
async function sourceCard(fileId) {
  if (!fileId) return `<div class="cp-card cp-empty">${T("Choose a source on the left.", "Wählen Sie links eine Quelle.")}</div>`;
  const doc = await pages(fileId);
  const cites = citationsFor(fileId);
  const files = S.data.files.map((f) => f.id), index = files.indexOf(fileId);
  const headerName = { From: T("From", "Von"), To: T("To", "An"), Date: T("Date", "Datum"), Subject: T("Subject", "Betreff") };
  const head = doc.headers ? `<dl class="cp-doc-head">${["From", "To", "Date", "Subject"].filter((k) => doc.headers[k]).map((k) => `<dt>${headerName[k]}:</dt><dd>${esc(k === "Date" ? mailDate(doc.headers[k]) : doc.headers[k])}</dd>`).join("")}</dl>` : "";
  // An e-mail's header lines are shown above; its body starts after the first blank line.
  const skip = (p) => (doc.headers && p === doc.pages[0] && p.text.indexOf("\n\n") >= 0 ? p.text.indexOf("\n\n") + 2 : 0);
  const isPdf = doc.media_type === "application/pdf";
  const pageUrl = (n) => `/api/files/${esc(fileId)}/original?pages=${n}`;  // one original page: always small enough to open
  const firstCited = (cites.find((c) => c.live && c.page) || cites.find((c) => c.page) || {}).page || (doc.pages[0] || {}).page;
  const body = doc.pages.length ? doc.pages.map((p) => `${p.page ? (isPdf
      ? `<a class="page" id="page-${p.page}" href="${pageUrl(p.page)}" target="_blank" rel="noopener" title="${T("Open this original page", "Originalseite öffnen")}">${T("Page", "Seite")} ${p.page} ${icon("external")}</a>`
      : `<span class="page" id="page-${p.page}">${T("Page", "Seite")} ${p.page}</span>`) : ""}${highlight(p.text, p.page, cites, skip(p))}`).join("\n")
    : doc.kind === "image" ? `<img alt="${esc(doc.name)}" src="/api/files/${esc(fileId)}/original" style="max-width:100%">` : `<span class="cp-muted">${T("No readable text.", "Kein lesbarer Text.")}</span>`;
  return `<article class="cp-card" aria-label="${esc(doc.name)}"><div class="cp-doc-toolbar">
      <button class="cp-icon-button" data-step-file="${esc(files[index - 1] || "")}" aria-label="${T("Previous source", "Vorherige Quelle")}" ${index <= 0 ? "disabled" : ""}>${icon("left")}</button>
      <button class="cp-icon-button" data-step-file="${esc(files[index + 1] || "")}" aria-label="${T("Next source", "Nächste Quelle")}" ${index >= files.length - 1 ? "disabled" : ""}>${icon("right")}</button>
      <span class="grow"><span class="name">${esc(doc.name)}</span></span><a class="cp-icon-button" href="${isPdf && firstCited ? pageUrl(firstCited) : `/api/files/${esc(fileId)}/original`}" target="_blank" rel="noopener" aria-label="${T("Open full source", "Original öffnen")}">${icon("external")}</a></div>
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
    "agent.start": () => `${T("starts", "beginnt")}: ${TASK[e.agent] || e.instruction || ""}`,
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
    "delegate": () => `${T("asks", "beauftragt")} ${AGENT_TITLE[e.to] || e.to}: ${TASK[e.to] || e.instruction || ""}`,
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
    <button type="button" data-rate="${esc(target)}" data-verdict="correct" aria-pressed="${v === "correct"}" title="${T("Correct", "Stimmt")}" aria-label="${T("Correct", "Stimmt")}">${icon("tick")}</button>
    <button type="button" data-rate="${esc(target)}" data-verdict="wrong" aria-pressed="${v === "wrong"}" title="${T("Not correct", "Stimmt nicht")}" aria-label="${T("Not correct", "Stimmt nicht")}">${icon("xcircle")}</button></span>`;
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
const clip = (text, n) => (String(text).length > n ? `${String(text).slice(0, n - 1)}…` : String(text));
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
    : TASK[agent] || AGENT_TITLE[agent];
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
    nodes.push(`<div class="cp-q ${cls}${row.state === "terminal" ? " end" : ""}${enter(`node:${row.step}`)}" data-step-node="${esc(row.step)}" title="${esc(step.title)}">
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
    return `<li class="st-${esc(d.status)}${enter(`doc:${d.document}`)}" data-doc="${esc(d.document)}">${mark}<span><b>${esc(d.title)}</b>
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
  return `<li class="cp-step-fact" data-item="${esc(f.item_id)}">${esc(shortFact(id))}: <b>${esc(plainValue(f.value))}</b>${src ? sourceChip(src) : f.verdict === "set_by_handler" ? ` <span class="cp-muted">· ${T("your decision", "Ihr Entscheid")}</span>` : ""}</li>`;
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
      ${(S.data.items || []).filter((i) => i.kind === "cover" && i.key !== "summary").map((x) => `<button class="cp-chip" data-cover-reason="${esc(x.key)}">${esc(x.title)}</button>`).join("")}<button class="cp-chip" data-cover-reason="anderer Grund">${T("other reason", "anderer Grund")}</button></p>` : ""}</li>` : "";
  const prospects = item("check", "aussichten");
  const rows = own.map((f) => `<li class="cp-step-decide" data-item="${esc(f.item_id)}"><span>${esc(plainQuestion((f.label || {}).de))}${f.key === "aussichten" && prospects ? passagesToggle(`check:aussichten`, prospects.law) : ""}</span><span class="cp-point-actions">${decisionButtons(f.key)}</span></li>`).join("");
  return cover + rows + checkRows();
}
const passagesToggle = (key, law) => (law || []).length ? ` ${clauseTag(key, law)}` : "";
// What a prescribed letter rests on: the written demand before an end of benefits, consent before a settlement.
function checkRows() {
  return (S.data.items || []).filter((i) => i.kind === "check" && i.key !== "aussichten").map((c) => {
    const missing = c.key === "androhung" && c.value === "fehlt", others = c.key === "androhung" && c.value === "andere";
    const override = (missing || others) && c.decided !== true ? `<span class="cp-point-actions"><button class="cp-button cp-small" data-decide="leistungen_einstellen" data-value="ja">${T("End benefits all the same", "Leistungen trotzdem einstellen")}</button></span>` : "";
    return `<li class="cp-step-decide" data-item="${esc(c.item_id)}"><span>${esc(plainQuestion((c.label || {}).de))}${c.key === "androhung" ? `: <b class="${missing || others ? "cp-flag" : ""}">${missing ? T("missing", "fehlt") : others ? T("only by others", "nur durch Dritte") : T("in the file", "in der Akte")}</b>` : ""}
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
    const name = S.editing ? `<button class="cp-link cp-step-pick" data-step="${esc(n.step.id)}" aria-pressed="${S.step === n.step.id}">${esc(shortTitle(n.step.title))}</button>` : `<b>${esc(shortTitle(n.step.title))}</b>`;
    const facts = state === "done" ? decided(i).map(factLine).join("") : "";
    const asked = new Set(["deckung", ...((S.data.draft || {}).needs || [])]);  // a decision asked below is not also «offen»
    const waiting = state === "now" ? (ev.waiting_for || []).filter((w) => !asked.has(w.fact)).map((w) => `<li class="cp-step-open" data-item="fact:${esc(w.fact)}"><span class="cp-muted">${T("open", "offen")}:</span> ${esc(shortFact(w.fact))}</li>`).join("") : "";
    const here = state === "now" && !ev.outcome ? `${sc.title ? `<li class="cp-step-action">${T("Next", "Als Nächstes")}: ${esc(sc.title)}</li>` : ""}${stepDecisions(n.step.id)}
        ${sc.missing !== undefined ? `<li class="cp-step-docs"><a class="cp-link cp-quiet-link" href="#/case/${esc(S.route.id)}/document_finder" data-missing="${sc.missing}">${T("Documents", "Unterlagen")} · ${T(`${sc.missing} missing`, `${sc.missing} fehl${sc.missing === 1 ? "t" : "en"}`)}</a></li>` : ""}` : "";
    return `<li class="cp-step ${state}" data-item="step:${esc(n.step.id)}"><span class="cp-step-mark">${mark}</span><div class="cp-step-body">${name}${state === "now" ? ` <span class="cp-muted">· ${T("now", "jetzt")}</span>` : ""}${originLabel(n.step)}
      ${facts || waiting || here ? `<ul class="cp-step-facts">${facts}${waiting}${here}</ul>` : ""}</div></li>`;
  }).join("");
  const end = ev.outcome ? `<li class="cp-step done"><span class="cp-step-mark">✓</span><div class="cp-step-body"><b>${T("End", "Abschluss")}: ${esc(ev.outcome.title)}</b></div></li>` : "";
  // a case the file shows further along starts at its stage: the stages before it, passed as the file shows
  const onPath = new Set(model.path.map((p) => p.step.id)), first = (model.path[0] || {}).step;
  const order = (S.data.process.steps || []).map((x) => x.id);
  const behind = first ? (ev.reached || []).filter((id) => !onPath.has(id) && model.steps[id] && order.indexOf(id) < order.indexOf(first.id))
    .sort((a, b) => order.indexOf(a) - order.indexOf(b)) : [];
  const before = behind.map((id) => `<li class="cp-step done" data-item="step:${esc(id)}"><span class="cp-step-mark">✓</span><div class="cp-step-body"><b>${esc(shortTitle(model.steps[id].title))}</b> <span class="cp-muted">· ${T("as the file shows", "laut Akte")}</span></div></li>`).join("");
  // what may follow the current step: its branches, one line, never a sequence the case has not taken
  const after = ev.outcome ? [] : [...new Set((current.step.next || []).map((e) => (model.steps[e.to] || {}).title).filter(Boolean))];
  const ahead = after.length ? `<li class="cp-step next"><span class="cp-step-mark">○</span><div class="cp-step-body"><span class="cp-muted">${T("then, depending on the case", "danach, je nach Fall")}</span>
      <ul class="cp-step-then">${after.map((t) => `<li>${esc(shortTitle(t))}</li>`).join("")}</ul></div></li>` : "";
  const change = S.lastEdit ? (S.lastEdit.op ? beforeNow() : `<p class="cp-change">${esc(changeLine(S.lastEdit.diff))} <button class="cp-link" id="undo">${T("Undo", "Rückgängig")}</button></p>`) : "";
  return `<section class="cp-card cp-process"><header class="cp-process-head"><h1 class="cp-title">${T("Process", "Prozess")}${S.data.process.short_title ? ` <span class="cp-muted">· ${esc(S.data.process.short_title)}</span>` : ""}</h1>
      <button class="cp-link cp-quiet-link" id="edit-open" aria-expanded="${Boolean(S.editing)}">${T("Change for this case", "Für diesen Fall ändern")}</button></header>
    ${change}${S.editing ? editForm(model.steps[S.step]) : ""}
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

const OPS = [["add_document", T("Add a document need", "Dokument verlangen")], ["set_required_when", T("Change when a document is required", "Ändern, wann ein Dokument nötig ist")],
             ["add_question", T("Add a question", "Frage ergänzen")], ["add_step", T("Add a step before this one", "Schritt davor ergänzen")],
             ["set_transition", T("Redirect a branch", "Verzweigung umleiten")], ["rename_step", T("Rename this step", "Schritt umbenennen")]];

function conditionFields(prefix) {
  const options = facts().map((f) => `<option value="${esc(f.id)}">${esc(questionLabel(f))}</option>`).join("");
  return `<div class="row"><label>${T("Required when", "Nötig, wenn")}<select name="${prefix}-fact"><option value="">${T("Always", "Immer")}</option>${options}</select></label>
    <label>${T("is", "ist")}<select name="${prefix}-value"></select></label></div>`;
}

function editForm(step) {
  const docs = S.data.process.documents.map((d) => `<option value="${esc(d.id)}">${esc(d.title)}</option>`).join("");
  const steps = S.data.process.steps.map((s) => `<option value="${esc(s.id)}">${esc(s.title)}</option>`).join("");
  const edges = (step.next || []).map((e, i) => `<option value="${i}">${esc(e.label || T("next", "weiter"))} → ${esc(S.data.process.steps.find((s) => s.id === e.to).title)}</option>`).join("");
  return `<form class="cp-edit" id="edit-form"><h3>${T(`Edit “${esc(step.title)}”`, `«${esc(step.title)}» bearbeiten`)}</h3>
    <label>${T("Change", "Änderung")}<select name="op">${OPS.map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}</select></label>
    <div data-op="add_document"><label>${T("Document", "Dokument")}<input name="title" maxlength="200" placeholder="${T("e.g. Ventilation record", "z. B. Lüftungsprotokoll")}"></label>
      <label>${T("Why it is needed", "Wozu es nötig ist")}<input name="why" maxlength="400"></label>${conditionFields("add")}</div>
    <div data-op="set_required_when" hidden><label>${T("Document", "Dokument")}<select name="document">${docs}</select></label>${conditionFields("set")}</div>
    <div data-op="add_question" hidden><label>${T("Question", "Frage")}<input name="question" maxlength="300"></label>
      <label>${T("Only require this document when the answer is yes", "Dieses Dokument nur verlangen, wenn die Antwort ja ist")}<select name="gates"><option value="">${T("No document", "Kein Dokument")}</option>${docs}</select></label></div>
    <div data-op="add_step" hidden><label>${T("Step", "Schritt")}<input name="steptitle" maxlength="200" placeholder="${T("e.g. Object to the dismissal in writing", "z. B. Einsprache gegen die Kündigung schreiben")}"></label>
      <label>${T("Why this case needs it", "Wozu dieser Fall ihn braucht")}<input name="stepwhy" maxlength="400"></label>
      <label>${T("Legal basis (optional)", "Rechtsgrundlage (freiwillig)")}<input name="steplaw" maxlength="200" placeholder="${T("e.g. Art. 336b OR", "z. B. Art. 336b OR")}"></label></div>
    <div data-op="set_transition" hidden><label>${T("Branch", "Verzweigung")}<select name="edge">${edges}</select></label><label>${T("Now leads to", "Führt neu zu")}<select name="to">${steps}</select></label></div>
    <div data-op="rename_step" hidden><label>${T("New wording", "Neue Bezeichnung")}<input name="rename" maxlength="200" value="${esc(step.title)}"></label></div>
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
function claimView(card) {
  const r = result(), brief = (r && r.brief) || {}, items = S.data.items || [];
  const summary = items.find((i) => i.kind === "summary" && i.value);
  const anliegen = (summary && summary.value) || brief.request || "";
  const timeline = brief.timeline || [];
  const parties = partiesHtml();
  return `<div class="cp-live"><div>${card}</div><aside>${anliegen || parties || timeline.length ? `<section class="cp-card cp-brief">
      <h2 class="cp-section">${T("Request", "Anliegen")}</h2><p data-item="summary:0">${esc(anliegen) || "—"}</p>
      ${parties ? `<h2 class="cp-section">${T("Parties", "Parteien")}</h2><p data-item="party:0">${parties}</p>` : ""}
      ${timeline.length ? `<h2 class="cp-section">${T("Timeline", "Chronologie")}</h2><div class="cp-lines">${timeline.map((t, i) => {
        const c = (t.citations || [])[0];
        return `<div data-item="timeline:${i}"><time>${esc(isoDay(t.date))}</time><span>${c ? `<button class="cp-link" data-cite-file="${esc(c.file)}" data-page="${c.page || ""}" title="${esc(c.quote)}">${esc(t.event)}</button>` : esc(t.event)}${rate(`timeline:${i}`)}</span></div>`;
      }).join("")}</div>` : ""}
    </section>` : `<p class="cp-empty">${T("Not prepared yet", "Noch nicht vorbereitet")}</p>`}${dossierContents()}</aside></div>`;
}

// What each bundled file contains, document by document, from the reading step.
function dossierContents() {
  const files = (S.data.files || []).filter((f) => ((f.extraction || {}).segments || []).length);
  if (!files.length) return "";
  const count = files.reduce((n, f) => n + f.extraction.segments.length, 0);
  return `<section class="cp-card cp-contents"><h2 class="cp-section">${T(`Contents of the files · ${count} documents`, `Inhalt der Dossiers · ${count} Dokumente`)}</h2>
    ${files.map((f) => `${files.length > 1 ? `<h3>${esc(f.name)}</h3>` : ""}<ol>${f.extraction.segments.map((s) => `<li><button class="cp-link" data-cite-file="${esc(f.id)}" data-page="${s.first_page}">
      <span>${esc([isoDay(s.date), s.kind].filter(Boolean).join(" · "))} <small>${T("p.", "S.")} ${s.first_page}${s.last_page !== s.first_page ? `–${s.last_page}` : ""}</small>${olderDocument(s) ? ` <small class="cp-older">${T("older document", "älteres Dokument")}</small>` : ""}</span>
      <b>${esc(s.title)}</b>${s.summary ? `<small>${esc(s.summary)}</small>` : ""}</button></li>`).join("")}</ol>`).join("")}</section>`;
}

function checkerView() {
  const rows = Object.values(recorded("fact")).map((f) => [questionOf(f.fact), f]).concat(Object.values(recorded("document")).map((d) => [needOf(d.document), d]));
  if (!rows.length) return `<p class="cp-empty">${T("The source checker’s verdicts appear here: every finding with the exact sentence it rests on.", "Hier erscheinen die Prüfergebnisse des Quellenprüfers: jede Feststellung mit dem genauen Satz, auf dem sie beruht.")}</p>`;
  return `${ratedRun() ? feedbackLine() : ""}<table class="cp-table"><thead><tr><th>${T("Finding", "Feststellung")}</th><th>${T("Verdict", "Prüfung")}</th><th>${T("Exact sentence", "Wörtliche Stelle")}</th></tr></thead><tbody>${rows.map(([label, row]) => `<tr>
    <td>${esc(label)}${row.value !== undefined && row.value !== null ? `: <b>${esc(row.part || valueText(row.value))}</b>` : row.status ? ` <span class="cp-muted">(${esc(word(row.status))})</span>` : ""}</td>
    <td>${row.verdict === "accepted" ? `<span class="cp-chip good">${T("supported", "belegt")}</span>` : row.verdict === "rejected" ? `<span class="cp-chip bad">${T("not supported", "nicht belegt")}</span><br><small class="cp-muted">${esc(row.verdict_reason || "")}</small>` : `<span class="cp-chip wait">${T("not checked", "nicht geprüft")}</span>`}${rate(row.fact ? `fact:${row.fact}` : `document:${row.document}`)}</td>
    <td>${(row.citations || []).map((c) => `<button class="cp-link" data-cite-file="${esc(c.file)}" data-page="${c.page || ""}">“${esc(c.quote)}”</button><br><small class="cp-muted">${esc(fileName(c.file))}${c.page ? `, ${T("page", "Seite")} ${c.page}` : ""}</small>`).join("<br>") || '<span class="cp-muted">—</span>'}</td></tr>`).join("")}</tbody></table>`;
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
    return `<tr data-item="${esc(i.item_id)}"><td><b>${esc((i.label || {}).de || pd.title || i.key)}</b></td>
      <td>${esc(pd.why || "")}${origin ? `<br><small class="cp-muted">${esc(origin)}</small>` : ""}</td>
      <td><span class="cp-chip ${chip}">${esc(word_)}</span>${i.status === "unusable" && i.reason ? `<br><small class="cp-muted">${esc(clip(i.reason, 160))}</small>` : ""}${gone.has(i.item_id) ? `<br><button class="cp-link cp-quiet-link" data-point-notneeded="${esc(i.key)}">${T("not needed", "nicht nötig")}</button>` : ""}</td>
      <td>${sourceChips(i.evidence) || '<span class="cp-muted">—</span>'}</td></tr>`;
  }).join("");
  return `${head}<table class="cp-table cp-docs-table"><thead><tr><th>${T("Document", "Unterlage")}</th><th>${T("What for", "Wozu")}</th><th>${T("State", "Stand")}</th><th>${T("Source", "Beleg")}</th></tr></thead><tbody>${rows}</tbody></table>`;
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
  const draft = r.reply && r.reply.clauses && r.reply.clauses.length && S.data.run && !r.stale_since ? `<a class="cp-button" href="/api/runs/${esc((S.data.lastCompleted || S.data.run).id)}/draft.docx">${T("Draft as .docx", "Entwurf als .docx")}</a>` : "";
  const action = { answer: T("Answer: ", "Klären: "), resolve: T("Not met: ", "Nicht erfüllt: "), obtain: T("Obtain: ", "Einholen: ") };
  const docs = ev ? ev.documents.filter((d) => !["suggested", "optional"].includes(d.required)) : [];
  const present = docs.filter((d) => d.status === "present").length, missing = docs.filter((d) => d.status !== "present").length;
  const position = ev ? `<section class="cp-card" style="padding:16px 20px;max-width:900px;margin-bottom:18px">
      <h2 class="cp-section" style="margin-top:0">${T("Where the case stands in its process", "Stand im Prozess")}</h2>
      <p>${ev.outcome ? `${T("End of the process", "Prozessende")}: <b>${esc(ev.outcome.title)}</b>` : ev.current ? `${T("Current step", "Aktueller Schritt")}: <b>${esc(ev.current.title)}</b>` : ""}
        ${ev.waiting_for.length ? ` · ${T("waiting for", "wartet auf")}: ${ev.waiting_for.map((w) => esc(w.question)).join("; ")}` : ""}</p>
      <p><a href="#/case/${esc(S.route.id)}/document_finder">${T(`Document checklist: ${present} present, ${missing} still needed`, `Dokumenten-Checkliste: ${present} vorhanden, ${missing} noch nötig`)}</a></p>
      ${ev.next_actions.length ? `<h3 class="cp-section" style="font-size:15px">${T("Next steps", "Nächste Schritte")}</h3><ul>${ev.next_actions.map((a) => `<li>${esc(action[a.kind])}${esc(a.text)}${a.kind === "resolve" ? ` <span class="cp-muted">(${esc(valueText(a.value))})</span>` : ""}</li>`).join("")}</ul>` : ""}</section>` : "";
  const learning = (r.learning || []).length ? `<h2 class="cp-section">${T("What CasePath proposes to learn", "Was CasePath lernen möchte")}</h2>
      <p class="cp-muted">${T("Proposals for the Knowledge base. They shape other cases only after a person approves them.", "Vorschläge für das Wissen. Sie prägen andere Fälle erst, wenn ein Mensch sie freigibt.")}</p>
      <ul>${r.learning.map((l) => `<li><b>${esc(learnAction(l.action))}</b> · ${esc(l.title || l.question || l.note)}${proposalVersion(l) ? ` <span class="cp-kv${l.action === "contradict" ? " add" : ""}">${icon("memory")}${esc(proposalVersion(l))}${l.action === "contradict" ? "" : T(" · waits for release", " · wartet auf Freigabe")}</span>` : ""} <span class="cp-muted">— ${esc(l.reason)}</span></li>`).join("")}</ul>
      <p><a href="#/knowledge">${T("Review in Knowledge", "Im Wissen prüfen")}</a></p>` : "";
  const report = `<p><a class="cp-button" href="/api/cases/${esc(S.route.id)}/report.docx?lang=${LANG}">${icon("doc")}${T("Case report as .docx", "Fallbericht als .docx")}</a>
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
  return T(`activated for the pilot · from Protekta’s first request letters${e ? `: ${e.text}` : ""}`,
           `für den Pilot aktiviert · aus Protektas ersten Unterlagenanforderungen${e ? `: ${e.text}` : ""}`);
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
// "in 6 von 7 Fällen verlangt": a seeded practice rule says how often Protekta asked for it.
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
  const learned = (S.runProfile || {}).median_seconds || {};
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
  const cells = rows.map(({ stage }, i) => `<li class="${i < nowAt ? "done" : i === nowAt ? "now" : ""}">${i < nowAt ? icon("tick") : ""}${T(stage.en, stage.de)}</li>`).join("");
  return { cells, left: Math.max(5, Math.round(left / 5) * 5) };
}
function runLine(st) {
  const run = S.data.run;
  const wrap = (body, end) => `<section class="cp-runline" aria-live="polite">${body}<span class="cp-runline-end">${end}</span></section>`;
  if (st === "running") {
    const { cells, left } = S.events.length ? stageLine() : { cells: "", left: null };
    const last = S.events.slice().reverse().find((e) => e.file && e.agent !== "lead") || {};
    const doing = { reader: T("reads", "liest"), claim_reader: T("reads", "liest"), document_finder: T("looks for documents in", "sucht Unterlagen in"),
      source_checker: T("checks the sources in", "prüft die Belege in"), result_checker: T("checks the result against", "prüft das Ergebnis an") }[last.agent] || T("starts on", "beginnt mit");
    const where = last.file ? `<button class="cp-link" data-cite-file="${esc(last.file)}" data-page="${last.page || last.from_page || ""}">${esc(clip(fileName(last.file), 40))}${last.page || last.from_page ? `, ${T("p.", "S.")} ${last.page || last.from_page}` : ""}</button>` : T("the files", "den Akten");
    const routed = S.events.find((e) => e.kind === "routing.decided");
    const others = (S.workflows || []).filter((w) => !routed || w.id !== routed.workflow);
    const stopping = S.stopping === run.id || S.switching;
    return wrap(`<ol class="cp-stages">${cells}</ol>${arrivalNow(run)}<p class="cp-runnow">${stopping ? T("Stopping after this step…", "Hält nach diesem Schritt an …")
        : `${T("Now", "Jetzt")}: ${doing} ${where}${left ? ` · ${T("about", "etwa")} ${left} s ${T("to go", "noch")}` : ""}`}</p>
      ${S.pickProcess ? `<p class="cp-pick">${others.map((w) => `<button class="cp-chip" data-other-process="${esc(w.id)}">${esc(w.short_title || w.title)}</button>`).join("")}</p>` : ""}`,
      `${routed ? `<span class="cp-muted">${esc(wfShort(routed.workflow, routed.title))}</span>` : ""}${routed && others.length && !stopping ? `<button class="cp-link cp-quiet-link" id="other-process-open">${T("other process", "anderer Prozess")}</button>` : ""}
      <button class="cp-button primary" id="stop-run" ${stopping ? "disabled" : ""}>${T("Stop", "Anhalten")}</button>`);
  }
  if (st === "paused") {
    const { cells } = S.events.length ? stageLine() : { cells: "" };
    return wrap(`<ol class="cp-stages paused">${cells}</ol><p class="cp-runnow"><b>${T("Stopped", "Angehalten")}</b></p>`,
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
    return wrap(`<p class="cp-runnow"><b>${T(`New: ${came.length} file(s)`, `Neu eingegangen: ${came.length} Datei(en)`)}</b> · ${names}</p>`,
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
  const s = (S.updateProfile || {}).median_total;
  if (!s) return "";
  return s < 90 ? T(`about ${Math.max(5, Math.round(s / 5) * 5)} s`, `etwa ${Math.max(5, Math.round(s / 5) * 5)} s`) : T(`about ${Math.round(s / 60)} min`, `etwa ${Math.round(s / 60)} Min.`);
}
// A handler's decision asked as a plain question: "Ist die Versicherungsdeckung gegeben?" [Ja] [Nein]; "offen" is no answer.
const plainQuestion = (text) => String(text || "").replace(/\s*\((Entscheid|CasePath)[^)]*\)?/g, "").trim();
const answered = (key) => { const i = item("fact", key); return i && i.value !== null && i.value !== undefined && i.value !== "offen" ? i.value : null; };
function decisionButtons(key) {
  const i = item("fact", key) || {}, now = answered(key);
  const label = { "bestätigt": T("Yes", "Ja"), "abgelehnt": T("No", "Nein"), ja: T("Yes", "Ja"), nein: T("No", "Nein"), true: T("Yes", "Ja"), false: T("No", "Nein") };
  return (i.values || []).filter((v) => v !== "offen").map((v) => `<button class="cp-button cp-small" data-decide="${esc(key)}" data-value="${esc(v)}" aria-pressed="${String(now) === String(v)}">${esc(label[v] || v)}</button>`).join("");
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
  return `<button class="cp-tag cp-law" type="button" data-cover-passage="${esc(key)}" aria-expanded="${open}" title="${esc(rows.map((r) => `${r.cite}: «${r.passage}»`).join(" "))}">${esc(cite)}</button>`
    + (open ? rows.map((r) => `<div class="cp-passage">${esc(r.cite)}: «${esc(r.passage)}»</div>`).join("") : "");
}
function coverPoint(p) {
  const [mark, cls] = COVER_MARK[p.value] || ["·", ""];
  const values = p.tick ? (item("fact", p.tick) || {}).values || [] : [];
  const pressed = (v) => String(p.tick_value) === String(v === "ja" ? true : v === "nein" ? false : v);
  const tick = values.length ? `<span class="cp-cover-tick">${values.map((v) => `<button class="cp-chip" data-decide="${esc(p.tick)}" data-value="${esc(v)}" aria-pressed="${pressed(v)}" title="${T("as the policy says", "laut Police")}">${esc(v)}</button>`).join("")}</span>` : "";
  const src = (p.evidence || [])[0];
  const line = [p.value === "police_ok" ? "" : p.text, p.aid].filter(Boolean).map(esc).join(" · ");
  const open = S.coverPassage === p.key;
  return `<li class="cp-cover-point ${cls}" data-item="${esc(p.item_id)}"><span class="cp-cover-mark" title="${esc(p.state_text || "")}">${mark}</span>
    <span class="cp-cover-body"><span class="cp-cover-title">${esc(p.title)}</span> ${clauseTag(p.key, p.clauses, (p.legal_basis || "").replace(/^Art\. /, "").replace(/, Art\. /g, ", "))}
      <span class="cp-cover-line">${line ? `<span class="cp-muted">${line}</span>` : p.value === "police_ok" ? `<span class="cp-muted">${T("as the policy says", "laut Police")}</span>` : ""}${src ? ` <button class="cp-source-chip" data-cite-file="${esc(src.file)}" data-page="${src.page || ""}" title="${esc(src.quote || "")}">${src.page ? `${T("p.", "S.")} ${src.page}` : T("source", "Quelle")}</button>` : ""}${tick}</span>
      ${p.note && open ? `<span class="cp-muted cp-cover-note">${esc(p.note)}</span>` : ""}</span></li>`;
}
const reasonChips = (attr, codes) => `<span class="cp-reasons">${codes.map((code) => `<button class="cp-chip" ${attr}="${code}">${esc(T(REASONS_EN[code], REASONS[code]))}</button>`).join("")}</span>`;

// ---------- Übersicht: the next piece of work, done; its reasons one click away ----------
// The card head says what this step is, why (one line), the one deadline that leads and the one decision that blocks
// this step; nothing else. What goes out is below it (several documents: tabs, each ticked once copied), its action bar
// always in view. «Der Fall» beside it says what the head does not. What the head says is decided once by the server
// (screen.py), in the case list's own words.
const scr = () => (S.data && S.data.screen) || {};
const isoDay = (v) => String(v || "").replace(/\b(\d{4})-(\d{2})-(\d{2})\b/g, "$3.$2.$1");
function overviewView() {
  const st = caseState();
  const top = runLine(st);
  if (!hasPrepared() || (!item("next_action", "0") && !result())) return top;
  return `${top}<div class="cp-overview">${preparedView(st)}${sideView()}</div>`;
}
// A source is one quiet chip, its page; what rests on the handler's own entry says so where the chip would stand.
function sourceChip(e) {
  return e && e.file ? ` <button class="cp-source-chip" data-cite-file="${esc(e.file)}" data-page="${e.page || ""}" title="${esc(e.quote || "")}">${e.page ? `${T("p.", "S.")} ${e.page}` : T("source", "Quelle")}</button>` : "";
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
  if (!active || (active.copied && !S.docPicked)) S.docTab = (rows.find((d) => !d.copied) || active || rows[0] || {}).kind || null;
  return { rows, active: rows.find((d) => d.kind === S.docTab) || null };
}
function docText(doc) {
  const draft = S.data.draft || {};
  if (!doc) return "";
  if (doc.main) return draft.text || "";
  return (S.alsoEdits || {})[doc.kind] ?? (((draft.also || []).find((a) => a.kind === doc.kind) || {}).text || "");
}
// A part only the handler can write: «[bitte ergänzen: …]», highlighted; the card's button goes to the first one.
const GAP_RE = /\[bitte ergänzen: [^\]]*\]/g;
const gapsMarked = (text) => esc(text).replace(GAP_RE, (m) => `<mark class="cp-gap">${m}</mark>`);
function gapCount(doc) {
  let text = docText(doc);
  if (doc && doc.main) for (const [orig, now] of Object.entries(S.blockEdits || {})) text = text.split(orig).join(now);
  return (text.match(GAP_RE) || []).length;
}
// «Weil: …», one line: what led to this step; its source (and, for what came in, «bereits erledigt») when opened.
function weilLine(act) {
  const sc = scr(), text = sc.weil || (act && act.reason);
  if (!text) return "";
  const src = act && (act.evidence || []).find((e) => e.file);
  const then = (sc.danach || []).length && !(act && act.deadline) ? ` · ${T("then", "danach")}: ${sc.danach.map(esc).join(" · ")}` : "";
  const came = act && act.incoming;
  const more = S.weilOpen ? `${sourceChip(src)}${came ? ` <button class="cp-link cp-quiet-link" data-decide="eingang_erledigt_bis" data-value="${esc(came.date || isoToday())}">${T("already done", "bereits erledigt")}</button>` : ""}` : "";
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
  return `<p class="cp-lead-frist ${cls} ${S.leadOpen ? "open" : ""}" data-item="${esc(lead.item_id)}">${more.length || lead.source
    ? `<button class="cp-lead-text" id="lead-open" aria-expanded="${Boolean(S.leadOpen)}">${text}</button>${S.leadOpen ? `<span class="cp-lead-more">${more.map(esc).join(" · ")}${sourceChip(lead.source)}</span>` : ""}`
    : `<span class="cp-lead-text">${text}</span>`}</p>`;
}
// The one open decision that blocks this step (screen.decision), with its answers; what it rests on opens from the question.
function decisionLine(dec, primary) {
  if (!dec) return "";
  const kg = dec.key === "kostennote" ? (S.data.items || []).filter((i) => i.kind === "stage_line" && /^kg-/.test(i.key)) : [];
  const detail = dec.key === "deckung" ? coverPanel() : kg.length ? kg.map((l) => `<div class="cp-decide-line" data-item="${esc(l.item_id)}">${esc(l.value)}${sourceChips(l.evidence)}</div>`).join("")
    : dec.key === "aussichten" ? passages(dec.law) : dec.source ? `<div>${sourceChip(dec.source)}</div>` : "";
  const pressed = (a) => (a.document ? S.feeAnswer === a.document : a.decline ? answered("deckung") === "abgelehnt" : String(answered(a.decide)) === String(a.value));
  const first = primary ? (dec.answers || []).findIndex((a) => !a.choose) : -1;
  const answer = (a, n) => {
    const cls = `cp-button cp-small${n === first ? " primary" : ""}`;
    if (a.choose) return `<select class="cp-button cp-small" data-point-choose aria-label="${T("Choose process", "Prozess wählen")}"><option value="">${esc(a.label)} …</option>${(S.workflows || []).map((w) => `<option value="${esc(w.id)}">${esc(w.short_title || w.title)}</option>`).join("")}</select>`;
    if (a.decline) return `<button class="${cls}" data-cover-decline aria-pressed="${pressed(a)}">${esc(a.label)}</button>`;
    if (a.document) return `<button class="${cls}" data-fee-answer="${esc(a.document)}" aria-pressed="${pressed(a)}">${esc(a.label)}</button>`;
    return `<button class="${cls}" data-decide="${esc(a.decide)}" data-value="${esc(a.value ?? isoToday())}" aria-pressed="${pressed(a)}">${esc(a.label)}</button>`;
  };
  const why = S.coverDecline && dec.key === "deckung" ? `<p class="cp-reasons cp-cover-why"><span class="cp-muted">${T("Which point fails?", "Welcher Punkt ist nicht erfüllt?")}</span>
      ${(S.data.items || []).filter((i) => i.kind === "cover" && i.key !== "summary").map((x) => `<button class="cp-chip" data-cover-reason="${esc(x.key)}">${esc(x.title)}</button>`).join("")}<button class="cp-chip" data-cover-reason="anderer Grund">${T("other reason", "anderer Grund")}</button></p>` : "";
  const question = `${esc(dec.question)}${dec.detail ? ` <span class="cp-muted">· ${esc(dec.detail)}</span>` : ""}`;
  const holder = dec.key === "kostennote" ? "next_action:0" : dec.key === "process" ? "point:process" : `fact:${dec.key}`;
  return `<div class="cp-decide" data-item="${esc(holder)}">${detail ? `<button class="cp-decide-q" id="decide-open" aria-expanded="${Boolean(S.decideOpen)}">${question}</button>` : `<span class="cp-decide-q">${question}</span>`}
    <span class="cp-point-actions">${(dec.answers || []).map(answer).join("")}</span>${S.decideOpen && detail ? `<div class="cp-decide-more">${detail}</div>` : ""}${why}</div>`;
}
// The cover check, prepared: the edition and the policy's start, then each point with its clause and source; the policy
// ticks are the handler's. Opened from the cover decision, and on the Prozess tab.
function coverPanel() {
  const sum = item("cover", "summary");
  if (!sum) return "";
  const points = (S.data.items || []).filter((i) => i.kind === "cover" && i.key !== "summary");
  const editions = (item("fact", "avb_ausgabe") || {}).values || [];
  const begin = (item("fact", "police_beginn") || {}).value || "";
  return `<div class="cp-cover-open"><p class="cp-cover-head"><label>${T("Conditions", "AVB")} <select class="cp-cover-select" data-cover-edition aria-label="${T("Edition of the conditions", "Ausgabe der Allgemeinen Bedingungen")}">${editions.map((v) => `<option ${v === sum.edition_value ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></label>
      <label>${T("Policy from", "Police ab")} <input type="date" class="cp-cover-select" data-cover-begin value="${esc(begin)}" aria-label="${T("Start of cover according to the policy", "Beginn des Versicherungsschutzes gemäss Police")}"></label></p>
    <ol class="cp-cover-points">${points.map(coverPoint).join("")}</ol></div>`;
}
// The payout as one line: «✓ Einigung · ✓ Bankverbindung · ● Auszahlung nachfragen · ○ Eingang · ○ Abschluss».
function progressLine(steps) {
  if (!steps || !steps.length) return "";
  const mark = { done: "✓", now: "●", next: "○" };
  return `<p class="cp-progress">${steps.map((s) => `<span class="${esc(s.state)}">${mark[s.state] || ""} ${esc(s.label)}</span>`).join(" · ")}</p>`;
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
  const open = dec && !(dec.key === "kostennote" && S.feeAnswer);
  const decisionPrimary = Boolean(acting && open && (dec.answers || []).some((a) => !a.choose));
  const phone = !text && act && ["A2", "A9"].includes(act.action) && !c;
  const gaps = text ? gapCount(active) : 0;
  const docPrimary = acting && !decisionPrimary && Boolean(text) && !active.copied;
  const phonePrimary = acting && !decisionPrimary && phone;
  const closePrimary = acting && !decisionPrimary && !docPrimary && !phonePrimary;
  const label = gaps ? T(`Fill ${gaps} gap${gaps > 1 ? "s" : ""}`, `${gaps} Lücke${gaps > 1 ? "n" : ""} füllen`)
    : active && S.justCopied === active.kind ? `${icon("tick")}${T("Copied", "Kopiert")}` : active && active.copied ? T("Copy again", "Nochmals kopieren")
    : active && active.main ? T("Copy letter", "Brief kopieren") : T("Copy", "Kopieren");
  const docButton = !text || c ? "" : active.main ? `<button class="cp-button ${docPrimary ? "primary" : ""}" id="copy-draft" data-gaps="${gaps}" ${stale ? "disabled" : ""}>${label}</button>`
    : `<button class="cp-button ${docPrimary ? "primary" : ""}" data-copy-also="${esc(active.kind)}" data-gaps="${gaps}" ${stale ? "disabled" : ""}>${label}</button>`;
  const stage = ((S.data.evaluation || {}).current || {}).step || "";
  const party = act && (act.action === "A9" || stage === "gegenpartei" || stage === "abwicklung") ? "gegenpartei" : draft.form === "A2_bericht" || stage === "mandat" ? "kanzlei" : "kunde";
  const phoneButton = phone ? `<button class="cp-button ${phonePrimary ? "primary" : ""}" id="phone-note" type="button" data-kind="${draft.form === "A2_bericht" ? "notiz" : "telefon"}" data-party="${party}">${draft.form === "A2_bericht" ? T("Enter a note", "Aktennotiz erfassen") : T("Enter a phone note", "Telefonnotiz erfassen")}</button>` : "";
  const f = S.data.follow_up, due = f && f.due;
  const then = act && act.deadline && (sc.danach || []).length ? `<span class="cp-date cp-then" title="${esc(sc.danach.join(" · "))}">${T("then", "danach")}: ${sc.danach.map(esc).join(" · ")}</span>` : "";
  const when = then || (due ? `<span class="cp-date ${daysTo(due) < 0 && !quiet() ? "late" : ""}" ${f.capped ? `title="${esc(T("before the deadline runs out", "vor Fristablauf"))}"` : ""}>${T("Follow-up", "Wiedervorlage")} <button class="cp-link" id="followup-show" type="button" title="${T("change", "ändern")}">${dateText(due)}</button>
        <input type="date" id="followup-date" value="${esc(due)}" aria-label="${T("Follow-up date", "Wiedervorlage")}" tabindex="-1"></span>` : "");
  const bar = c ? `<span class="cp-closed">${icon("check")}<b>${c.form === "erledigt" ? T("Done", "Erledigt") : T("Done, with a reservation", "Erledigt, mit Vorbehalt")}</b>
        <span class="cp-muted">· ${dateText(c.at)} · ${esc(c.expert)}</span></span><span class="grow"></span><button class="cp-button primary" id="next-case">${T("Next case", "Nächster Fall")} ${icon("right")}</button>`
    : `${docButton}${phoneButton}${when}<span class="grow"></span>
      ${["paused", "running"].includes(st) ? "" : `<span class="cp-split ${closePrimary ? "on" : ""}"><button class="cp-button ${closePrimary ? "primary" : ""}" data-close="erledigt">${T("Done", "Erledigt")}</button><details class="cp-split-more">
        <summary class="cp-button" aria-label="${T("more options", "weitere Möglichkeit")}">▾</summary><div class="cp-menu up"><input id="reservation" maxlength="2000" placeholder="${T("Reservation (optional)", "Vorbehalt (freiwillig)")}">
        <button class="cp-button" data-close="erledigt_mit_vorbehalt">${T("Done, with a reservation", "mit Vorbehalt")}</button></div></details></span>`}`;
  const options = (S.data.action_options || []).filter((o) => !act || o.kind !== act.action);
  const title = sc.title || (act ? T(act.label.en, act.label.de) : T("No prepared step", "Kein vorbereiteter Schritt"));
  const tabs = docs.length > 1 ? `<div class="cp-doc-tabs" role="tablist" aria-label="${T("What goes out", "Was hinausgeht")}">${docs.map((d) => `<button role="tab" class="cp-doc-tab ${d.copied ? "copied" : ""}" data-doc-tab="${esc(d.kind)}" aria-selected="${d.kind === (active || {}).kind}">${esc(d.title)}${d.copied ? ` ${icon("tick")}` : ""}</button>`).join("")}</div>` : "";
  const body = text ? (active.main ? letterView(text, editable) : alsoView(active, editable))
    : `<p class="cp-muted cp-noletter">${esc(draft.none ? `${T("No draft", "Kein Entwurf")}: ${draft.none}` : T("No letter for this step", "Für diesen Schritt kein Brief"))}</p>`;
  const required = active && active.main && (draft.required || []).length ? `<p class="cp-required">${T("Required", "Pflichtteile")}: ${draft.required.map((r) => `${esc(r.title)} <span class="cp-muted">(${esc(r.basis)})</span>`).join(" · ")}</p>` : "";
  return `<section class="cp-card cp-prepared ${sc.urgency === "dringend" && !c ? "urgent" : ""}">
    <header class="cp-prep-head"><h2>${esc(title)}</h2>${!c && editable && options.length ? `<button class="cp-link cp-quiet-link" id="change-action" aria-expanded="${Boolean(S.changing)}">${T("change", "ändern")}</button>` : ""}</header>
    ${S.changing && !c ? `<div class="cp-change-panel">${S.pickAction ? `<span class="cp-muted">${T(`Instead: ${esc(S.pickAction.title)}, because`, `Stattdessen: ${esc(S.pickAction.title)}, weil`)}</span>${reasonChips("data-action-reason", ["1", "2", "5", "6"])}`
      : options.map((o) => `<button class="cp-chip" data-pick-action="${esc(o.kind)}">${esc(o.title)}${o.has_draft ? "" : T(" (no draft)", " (kein Entwurf)")}</button>`).join("")}</div>` : ""}
    ${c ? "" : `${weilLine(act)}${leadLine(sc.lead)}${dec ? decisionLine(dec, decisionPrimary) : progressLine(sc.progress)}`}${tabs}
    ${stale && text ? `<p class="cp-stale-note">${T("Draft from before the new files", "Entwurf vor den neuen Dateien")} <button class="cp-link cp-quiet-link" id="use-anyway" type="button">${T("use anyway", "trotzdem verwenden")}</button></p>` : ""}
    <div class="cp-letter ${stale ? "cp-stale" : ""}" data-item="letter:0" data-doc="${esc((active || {}).kind || "")}" ${sc.missing !== undefined ? `data-missing="${sc.missing}"` : ""}>${body}${required}</div>
    <footer class="cp-bar">${bar}</footer>
  </section>`;
}
// A document that goes with the letter (a template for the customer, the cost guarantee, the summary for the firm …):
// its settings (the guarantee's scope and an amount only the handler enters) above it, its text editable on a click.
function alsoView(doc, editable) {
  const a = ((S.data.draft || {}).also || []).find((x) => x.kind === doc.kind) || {};
  const control = (key) => {
    const f = item("fact", key) || {}, now = f.value === null || f.value === undefined ? "" : String(f.value);
    return (f.values || []).length
      ? `<label class="cp-muted">${esc(plainQuestion((f.label || {}).de).replace(/\s*\(.*$/, ""))} <select class="cp-cover-select" data-also-set="${esc(key)}">${f.values.map((v) => `<option ${v === now || (!now && v === f.values[0]) ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></label>`
      : `<label class="cp-muted">${T("Amount (optional)", "Betrag (freiwillig)")} CHF <input class="cp-cover-select" size="9" data-also-set="${esc(key)}" value="${esc(now)}" placeholder="${T("none", "keiner")}"></label>`;
  };
  return `${editable && (a.set || []).length ? `<p class="cp-also-set">${a.set.map(control).join(" ")}</p>` : ""}
    <div class="cp-text cp-also-text" data-seg="also" data-also-text="${esc(doc.kind)}" ${editable ? `data-editable="1" tabindex="0" role="textbox" aria-multiline="true" aria-label="${esc(doc.title)}"` : ""}>${gapsMarked(docText(doc))}</div>`;
}
// The letter's lines are its checklist: a tick is a request, unticking takes the line out at once. A line shows no tag:
// its reason (why, how often practice asks, the article's passage, its source) opens from the line, by click or keyboard.
// Offered lines wait folded under «Weitere Vorschläge»; the text around is the letter, editable on a click.
function letterLines() {
  const docs = (S.data.items || []).filter((i) => i.kind === "document" && i.ask && i.status !== "present" && !i.part_of);
  const qs = (S.data.items || []).filter((i) => i.kind === "letter_question" || i.kind === "hint");
  const lines = (S.data.caseEvents || []).filter((e) => e.kind === "letter.line").reduce((m, e) => { m[e.item_id] = e.included; return m; }, {});
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
    return `<li class="cp-line ${extra ? "cp-offered" : ""} ${S.why === i.item_id ? "open" : ""}" data-item="${esc(i.item_id)}" data-text="${esc(line)}">
      <input type="checkbox" data-line="${esc(i.item_id)}" ${on(i) ? "checked" : ""} ${editable ? "" : "disabled"} aria-label="${esc(shown)}" aria-describedby="${whyId(i)}">
      <span class="cp-line-text" data-why="${esc(i.item_id)}">${esc(shown)}</span>${lineWhy(i)}
      ${S.askWhy === i.item_id ? `<div class="cp-why-row"><span class="cp-muted">${T("Why?", "Warum?")}</span>${reasonChips("data-line-reason", ["3", "4", "2", "1", "5"])}</div>` : ""}</li>`;
  };
  const extra = editable ? `${offered.length ? `<li class="cp-offers"><details ${S.askWhy || S.openOffers ? "open" : ""}><summary class="cp-link">${T("More suggestions", "Weitere Vorschläge")} · ${offered.length}</summary><ul>
      ${offered.map((i) => row(i, i.kind === "document" ? `– ${label(i)}` : i.value, true)).join("")}</ul></details></li>` : ""}
    <li class="cp-add">${S.addDoc ? `<span class="cp-reasons"><span class="cp-muted">${T(`Add “${esc(S.addDoc)}” because`, `«${esc(S.addDoc)}» verlangen, weil`)}</span>${reasonChips("data-add-doc-reason", ["2", "4", "5"]).replace(/^<span class="cp-reasons">|<\/span>$/g, "")}</span>`
      : `${icon("plus")}<input id="add-doc" maxlength="200" placeholder="${T("Add a document", "Unterlage hinzufügen")}" aria-label="${T("Add a document", "Unterlage hinzufügen")}">`}</li>` : "";
  let n = 0, html = "", list = [];
  const flush = (more = "") => { if (list.length || more) html += `<ul class="cp-checklist" data-seg="list">${list.join("")}${more}</ul>`; list = []; };
  segs.forEach((s, k) => {
    if (s.row) { list.push(row(s.row, s.line)); if (k === lastRow) flush(extra); return; }
    flush();
    const shown = (S.blockEdits || {})[s.text] ?? s.text;
    html += `<div class="cp-text" data-seg="text" data-orig="${esc(s.text)}" ${editable ? `data-editable="1" tabindex="0" role="textbox" aria-multiline="true" aria-label="${T("Letter text", "Brieftext")}"` : ""} data-block="${n += 1}">${gapsMarked(shown)}</div>`;
  });
  flush(lastRow < 0 ? extra : "");
  return html;
}
// The letter as it will be sent: the edited text blocks and the ticked lines, in order.
function letterText() {
  return [...document.querySelectorAll("[data-item='letter:0'] [data-seg]")].map((el) => el.dataset.seg === "list"
    ? [...el.querySelectorAll(":scope > li[data-text]")].filter((li) => (li.querySelector("input[data-line]") || {}).checked !== false).map((li) => li.dataset.text).join("\n")
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
  const asks = (S.data.items || []).filter((i) => i.kind === "customer_question" && i.value);
  return asks.length ? `<dt>${T("Questions", "Fragen")}</dt><dd class="cp-asks">${asks.map((q) => `<div data-item="${esc(q.item_id)}">«${esc(q.value)}»</div>`).join("")}</dd>` : "";
}
function sideAccount() {
  const sc = scr();
  const stand = sc.stand || [];  // the account's lines as the server words them for this screen (screen.account_lines)
  const stageLines = sc.lines || [];  // the stage's short lines, without what the card head states (screen.py)
  const next = stand.map((l) => !l.rows ? `<div class="cp-acct-line ${l.open ? "open" : ""}" data-item="${esc(l.item_id)}"><span class="cp-acct-label">${esc((l.label || {}).de || "")}</span> ${esc(l.value || "")}${sourceChips(l.evidence)}${handlerTag(l.handler)}</div>`
    : `<div class="cp-acct-line open" data-item="${esc(l.item_id)}"><span class="cp-acct-label">${esc((l.label || {}).de || "")}</span>${l.rows.map((x) => `<div class="cp-acct-item">${esc(x.text)}${sourceChips(x.evidence)}${handlerTag(x.handler)}${settleButtons(x)}</div>`).join("")}${l.more ? `<button class="cp-link cp-quiet-link" data-open-party="${esc(l.party)}">… ${l.more} ${T("more", "weitere")}</button>` : ""}</div>`)
    .concat(stageLines.map((l) => `<div class="cp-acct-line" data-item="${esc(l.item_id)}">${esc(l.value || "")}${sourceChips(l.evidence)}</div>`)).join("");
  return next ? `<dt>${T("Next", "Als Nächstes")}</dt><dd><div class="cp-acct">${next}</div></dd>` : "";
}
// After a correction: what changed in the prepared package, before and after, with its basis, and its undo; after an undo,
// what came back and what an undo cannot reach. Otherwise, after an update, how the reply was matched (C7), unless the
// card head (Slice B) already says it.
function sideChangeLine() {
  if (S.lastUndo && S.lastUndo.case === S.route.id && !S.lastEdit) return consequencesBlock(S.lastUndo.consequences, T("Undone", "Rückgängig gemacht"), "", S.lastUndo.limits);
  if (S.lastEdit && !S.lastEdit.op) {
    const undo = `<button class="cp-link" id="undo">${T("Undo", "Rückgängig")}</button>`;
    return S.lastEdit.consequences ? consequencesBlock(S.lastEdit.consequences, T("Changed", "Geändert"), undo)
      : `<p class="cp-change">${esc(changeLine(S.lastEdit.diff))} ${undo}</p>`;
  }
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
  return ` <span class="cp-settle"><button class="cp-link cp-quiet-link" data-settle="${esc(x.request)}" data-how="erledigt">${T("done", "erledigt")}</button>
    · <button class="cp-link cp-quiet-link" data-settle="${esc(x.request)}" data-how="nicht_mehr_noetig">${T("no longer needed", "nicht mehr nötig")}</button></span>`;
}
function sideChanges() {
  const ch = S.data.changes || {}, any = (ch.added || []).length + (ch.changed || []).length + (ch.removed || []).length + (ch.entries || []).length;
  return !running() && any ? `<details class="cp-mine"><summary class="cp-link cp-quiet-link">${T("What changed", "Was sich geändert hat")} · ${any}</summary>
        ${[["added", T("new", "neu")], ["changed", T("changed", "geändert")], ["removed", T("no longer", "nicht mehr")]].filter(([k]) => (ch[k] || []).length)
          .map(([k, w]) => `<p><span class="cp-muted">${w}:</span> ${(ch[k] || []).map(esc).join(" · ")}</p>`).join("")}
        ${(ch.entries || []).length ? `<ul class="cp-new-entries">${ch.entries.map((x) => `<li>${esc(isoDay(x))}</li>`).join("")}</ul>` : ""}</details>` : "";
}
function sideView() {
  const sc = scr();
  const fristen = (sc.fristen || []).map((d) => `<div class="cp-frist ${quiet() ? "" : d.late ? "late" : d.soon ? "soon" : ""}" data-item="${esc(d.item_id)}" title="${esc([d.basis, d.rule].filter(Boolean).join(" · "))}">${d.condition ? `<span class="cp-muted">${esc(d.condition)}:</span> ` : ""}<b>${esc(d.date || d.state)}</b> · ${esc(d.title)}${d.date ? ` <span class="cp-muted">· ${esc(d.state)}</span>` : ""}${d.who ? ` <span class="cp-muted">· ${esc(d.who)}</span>` : ""}${(d.pair || []).length ? `<br><span class="cp-muted">${d.pair.map(esc).join(" · ")}</span>` : ""}${sourceChip(d.source)}</div>`).join("");
  const docs = sc.missing && !sc.missing_in_letter ? `<dt>${T("Documents", "Unterlagen")}</dt><dd><a class="cp-link cp-quiet-link" href="#/case/${esc(S.route.id)}/document_finder">${T(`${sc.missing} missing`, `${sc.missing} fehl${sc.missing === 1 ? "t" : "en"}`)}</a></dd>` : "";
  const points = (sc.points || []).map((p) => `<div class="cp-point-line ${p.open ? "open" : ""}" data-item="${esc(p.item_id)}"><button class="cp-link cp-point-text" data-key-point="${esc(String(p.item_id).replace(/^key_point:/, ""))}" aria-expanded="${S.keyPoint === String(p.item_id).replace(/^key_point:/, "")}">${esc(p.text)}</button> <span class="cp-muted">· ${esc(p.basis || "")}</span>
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
        ${S.data.screen && (fristen || !sc.fristen_elsewhere) ? `<dt>${T("Deadlines", "Fristen")}</dt><dd>${fristen || `<span class="cp-muted">${T("none in the file", "keine in der Akte")}</span>`}</dd>` : ""}
        ${cover ? `<dt>${T("Cover", "Deckung")}</dt><dd data-item="cover:summary" class="cp-cover-state ${esc(cover.state)}">${esc(cover.text)}</dd>` : ""}
        ${points ? `<dt>${T("Law", "Rechtliches")}</dt><dd>${points}</dd>` : ""}
        ${flagged.length ? `<dt>${T("Note", "Achtung")}</dt><dd>${flagged.map((f) => esc(f.name)).join(", ")} ${T("contains text addressed to an AI; not followed", "enthält Text an die KI; nicht befolgt")}</dd>` : ""}
        ${unread.length ? `<dt>${T("Unread", "Nicht gelesen")}</dt><dd>${unread.map((f) => `${esc(f.name)}: ${Object.keys(f.extraction.unread_reasons).length} ${T("page(s)", "Seite(n)")}`).join("<br>")}</dd>` : ""}
      </dl>
      <p class="cp-case-tools">${S.data.file_note ? `<button class="cp-button cp-small" id="copy-note">${S.noteCopied ? T("File note copied", "Aktennotiz kopiert") : T("Copy file note", "Aktennotiz kopieren")}</button>` : ""}
        <button class="cp-link cp-quiet-link" id="add-note" aria-expanded="${Boolean(S.noting)}">${T("Add note", "Notiz hinzufügen")}</button></p>
      ${S.noting && !S.entryEdit ? entryForm() : ""}
      ${sideChangeLine()}
      ${sideChanges()}
    </section></aside>`;
}

// ---------- the handler's own entry: a call, a conversation, a note, an e-mail outside the file ----------
// One compact card: what kind, with whom (a name if wanted), the day (today), what was said; and, each behind one tap, one
// row of what was agreed, what was asked and the next step. It is an entry of the account and counts at once.
const PARTY_DE = { kunde: "Kundschaft", versicherer: "Protekta", kanzlei: "Kanzlei", gegenpartei: "Gegenpartei", behoerde: "Gericht/Behörde", andere: "Andere" };
const ENTRY_KINDS = [["telefon", T("Phone", "Telefon")], ["gespraech", T("Conversation", "Gespräch")], ["notiz", T("Note", "Notiz")],
  ["email", T("E-mail outside the file", "E-Mail ausserhalb der Akte")]];
const ENTRY_PARTIES = [["kunde", T("customer", "Kundschaft")], ["gegenpartei", T("other side", "Gegenpartei")], ["kanzlei", T("law firm", "Kanzlei")],
  ["behoerde", T("authority", "Behörde")], ["andere", T("other", "andere")]];
const ENTRY_PARTS = { agreed: T("Agreed", "Vereinbart"), asked: T("Asked", "Verlangt"), next: T("Next step", "Nächster Schritt") };
function entryForm() {
  const d = S.entryDraft || {}, party = d.party || "kunde";
  const part = (k) => d[k] || {};
  const shown = (k) => Boolean((d.open || {})[k] || Object.values(part(k)).some(Boolean));
  const options = (rows, now, blank) => (blank ? `<option value="">${esc(blank)}</option>` : "") + rows.map(([k, label]) => `<option value="${k}" ${k === now ? "selected" : ""}>${esc(label)}</option>`).join("");
  const whom = (now, blank) => options(ENTRY_PARTIES.concat([["versicherer", T("us (Protekta)", "wir (Protekta)")]]), now, blank);
  const input = (name, value, attrs) => `<input name="${name}" value="${esc(value || "")}" ${attrs}>`;
  const row = (k, body) => `<div class="cp-entry-part" data-part="${k}" ${shown(k) ? "" : "hidden"}><span class="cp-entry-part-label">${ENTRY_PARTS[k]}</span>${body}</div>`;
  return `<form class="cp-entry-form" id="note-form" ${S.entryEdit ? `data-edit="${esc(S.entryEdit)}"` : ""} novalidate>
    <div class="cp-entry-kinds" role="radiogroup" aria-label="${T("Kind of entry", "Art des Eintrags")}">${ENTRY_KINDS.map(([k, label]) =>
      `<label class="cp-entry-kind"><input type="radio" name="kind" value="${k}" ${k === (d.kind || "telefon") ? "checked" : ""}><span>${esc(label)}</span></label>`).join("")}</div>
    <div class="cp-entry-row"><label>${T("with", "mit")} <select name="party">${options(ENTRY_PARTIES, party)}</select></label>
      ${input("name", d.name, `maxlength="120" placeholder="${T("name (optional)", "Name (freiwillig)")}" aria-label="Name" class="cp-entry-name"`)}
      <label>${T("on", "am")} <input type="date" name="date" value="${esc(d.date || isoToday())}" aria-label="${T("Date", "Datum")}"></label></div>
    <textarea name="said" rows="3" maxlength="2000" placeholder="${T("What was said", "Was besprochen wurde")}" aria-label="${T("What was said", "Was besprochen wurde")}">${esc(d.said || "")}</textarea>
    ${row("agreed", `${input("agreed_what", part("agreed").what, `maxlength="120" placeholder="${T("what", "was")}" aria-label="${T("agreed: what", "vereinbart: was")}"`)}
      ${input("agreed_amount", part("agreed").amount, `maxlength="40" placeholder="CHF" size="8" aria-label="${T("amount", "Betrag")}"`)}
      <select name="agreed_payer" aria-label="${T("who pays", "wer zahlt")}">${options([["gegenpartei", T("other side pays", "Gegenpartei zahlt")], ["kunde", T("customer pays", "Kundschaft zahlt")],
        ["versicherer", T("we pay", "Protekta zahlt")], ["kanzlei", T("firm pays", "Kanzlei zahlt")], ["andere", T("others pay", "andere zahlen")]], part("agreed").payer || (party === "gegenpartei" ? "gegenpartei" : ""), T("who pays", "wer zahlt"))}</select>
      <label>${T("by", "bis")} <input type="date" name="agreed_by" value="${esc(part("agreed").by || "")}"></label>`)}
    ${row("asked", `${input("asked_what", part("asked").what, `maxlength="120" placeholder="${T("what", "was")}" aria-label="${T("asked: what", "verlangt: was")}"`)}
      <select name="asked_of" aria-label="${T("of whom", "von wem")}">${options(ENTRY_PARTIES, part("asked").of || party)}</select>
      <label>${T("by", "bis")} <input type="date" name="asked_by" value="${esc(part("asked").by || "")}"></label>`)}
    ${row("next", `${input("next_what", part("next").what, `maxlength="120" placeholder="${T("what", "was")}" aria-label="${T("next step: what", "nächster Schritt: was")}"`)}
      <label>${T("by", "bis")} <input type="date" name="next_by" value="${esc(part("next").by || "")}"></label>
      <select name="next_who" aria-label="${T("who", "wer")}">${whom(part("next").who || party)}</select>`)}
    <p class="cp-entry-adds">${Object.keys(ENTRY_PARTS).filter((k) => !shown(k)).map((k) => `<button type="button" class="cp-link cp-quiet-link" data-entry-part="${k}">+ ${ENTRY_PARTS[k]}</button>`).join("")}</p>
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
  return `${T("Changed", "Geändert")}: ${parts.join("; ") || T("nothing else moved", "sonst nichts verschoben")}`;
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
function historyView() {
  const all = S.data.verlauf || [];
  const party = S.onlyOpen && S.openParty;  // «… n weitere» in «Stand»: that party's open items
  const rows = S.onlyOpen ? all.filter((r) => r.open && (!party || (r.open_of || []).includes(party))) : all;
  const gaps = (S.data.items || []).filter((i) => i.kind === "record_gap");
  const docs = all.filter((r) => r.kind !== "gesture").length, done = all.length - docs, open = all.filter((r) => r.open).length;
  const note = (n) => (n.text ? `<div class="cp-entry-note ${n.open ? "open" : ""} ${n.kind}">${esc(n.text)}</div>` : "");
  const tag = (r) => r.kind === "report" ? `<span class="cp-entry-tag">${T("Report", "Meldung")}</span> ` : r.phone && r.title !== "Telefon" ? `<span class="cp-entry-tag">${T("Phone", "Telefon")}</span> ` : "";
  const own = (r) => r.handler ? `<br><span class="cp-entry-tag own">${T("entered by", "erfasst von")} ${esc(r.handler.by || T("the case handler", "der Fallbearbeitung"))}</span>${r.waiting
    ? ` <span class="cp-muted">${T("counts once the case is prepared anew", "zählt nach einer vollständigen Vorbereitung")}</span>` : ""}` : "";
  const tools = (r) => r.handler ? `<div class="cp-entry-tools"><button class="cp-link cp-quiet-link" data-entry-edit="${esc(String(r.key).split(":")[1])}">${T("change", "ändern")}</button>
      <button class="cp-link cp-quiet-link" data-entry-remove="${esc(String(r.key).split(":")[1])}">${T("remove", "entfernen")}</button></div>`
    : r.undo ? `<div class="cp-entry-tools"><button class="cp-link cp-quiet-link" data-undo-edit="${esc(r.undo)}">${T("undo", "rückgängig")}</button></div>` : "";
  const source = (r) => r.kind === "gesture" || r.handler ? "" : (r.evidence || []).some((e) => e.quote) ? sourceChips((r.evidence || []).slice(0, 1))
    : (r.evidence || [])[0] ? ` <button class="cp-source-chip" data-cite-file="${esc(r.evidence[0].file)}" data-page="">${T("open", "öffnen")}</button>` : "";
  const line = (r) => `<tr class="${r.open ? "open" : ""} cp-row-${esc(r.kind)}" ${String(r.key).startsWith("entry:") ? `data-item="${esc(r.key)}"` : ""}>
      <td>${r.number ?? ""}</td><td class="cp-nowrap">${dateText(r.date)}</td><td class="cp-nowrap">${esc(r.who || "")}</td>
      <td>${tag(r)}<span class="cp-muted">${esc(r.title || "")}</span><br>${esc(r.what || "")}${source(r)}${own(r)}</td>
      <td>${(r.notes || []).map(note).join("")}${tools(r)}</td></tr>`;
  return `${S.entryEdit ? `<section class="cp-card cp-case cp-entry-edit"><h3>${T("Change your entry", "Eigenen Eintrag ändern")}</h3>${entryForm()}</section>` : ""}
    <section class="cp-card cp-account"><header class="cp-account-head"><h2 class="cp-section">${T("Course of the case", "Verlauf")}</h2>
      <span class="cp-muted">${docs} ${docs === 1 ? T("document", "Dokument") : T("documents and entries", "Dokumente und Einträge")}${done ? ` · ${done} ${done === 1 ? T("step done here", "Bearbeitung") : T("steps done here", "Bearbeitungen")}` : ""}${open ? ` · ${open} ${T("open", "offen")}` : ""}</span>
      <label class="cp-account-filter"><input type="checkbox" id="only-open" ${S.onlyOpen ? "checked" : ""}> ${party ? esc(T(`only open with ${party}`, `nur Offenes ${({ kunde: "bei der Kundschaft", versicherer: "bei uns", kanzlei: "bei der Kanzlei", gegenpartei: "bei der Gegenpartei", behoerde: "bei Gericht/Behörde" })[party] || ""}`)) : T("only open", "nur Offenes")}</label></header>
    ${S.data.governing_version ? `<p class="cp-muted" title="${esc(`${S.data.run_version} → ${S.data.governing_version}`)}">${T("Process updated since the case was prepared", "Prozess seit der Vorbereitung aktualisiert")}</p>` : ""}
    ${gaps.length ? `<p class="cp-flag cp-account-gap">${gaps.map((g) => esc((g.label || {}).de || g.value)).join(" · ")}</p>` : ""}
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
function closed() { return (S.data.caseEvents || []).filter((e) => e.kind === "case.closed").pop(); }
function unaidedPending() {
  // Own answer first: a case opened "unaided" for this person shows the files and one short form until it is answered.
  const mine = (S.data.caseEvents || []).filter((e) => e.expert === S.me);
  return mine.some((e) => e.kind === "case.opened" && e.condition === "unaided") && !mine.some((e) => e.kind === "reveal");
}
function unaidedView() {
  const steps = (S.data.process && S.data.process.steps || []).filter((x) => !CHAT_ROLE.test(x.role || ""));
  const docs = (S.data.process && S.data.process.documents || []).filter((d) => !d.suggested);
  return `<section class="cp-card" style="padding:18px 22px;max-width:760px"><h2 class="cp-section" style="margin-top:0">${T("Your own assessment first", "Zuerst Ihre eigene Einschätzung")}</h2>
    <p class="cp-muted">${T("Read the files on the left, then answer three questions. CasePath's result appears afterwards.", "Lesen Sie links die Akten und beantworten Sie dann drei Fragen. Danach erscheint das Ergebnis von CasePath.")}</p>
    <form id="unaided">
      <label><b>${T("Where does the case stand?", "Wo steht der Fall?")}</b><br><select name="step" class="cp-button"><option value="">—</option>${steps.map((x) => `<option value="${esc(x.id)}">${esc(shortTitle(x.title))}</option>`).join("")}</select></label>
      <p><b>${T("Which documents would you request now?", "Welche Unterlagen würden Sie jetzt anfordern?")}</b></p>
      ${docs.map((d) => `<label style="display:block"><input type="checkbox" name="doc" value="${esc(d.id)}"> ${esc(clip(d.title, 90))}</label>`).join("")}
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
  const box = $("[data-item='letter:0']"), button = $("#copy-draft, [data-copy-also]");
  if (!box || !button || button.disabled) return;
  const n = (box.innerText.match(GAP_RE) || []).length, before = Number(button.dataset.gaps || 0);
  if (n === before) return;
  button.dataset.gaps = String(n);
  button.textContent = n ? T(`Fill ${n} gap${n > 1 ? "s" : ""}`, `${n} Lücke${n > 1 ? "n" : ""} füllen`) : button.id === "copy-draft" ? T("Copy letter", "Brief kopieren") : T("Copy", "Kopieren");
}
// The first gap, selected, so typing replaces it.
function goToGap() {
  const gap = $("[data-item='letter:0'] mark.cp-gap") || [...document.querySelectorAll("[data-item='letter:0'] [data-editable]")].find((el) => GAP_RE.test(el.innerText) && !(GAP_RE.lastIndex = 0));
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
    if (navigator.clipboard) navigator.clipboard.writeText(text).catch(() => {});
    const kind = (S.data.draft || {}).form || null, act = item("next_action", "0") || {};
    S.copied = true; S.justCopied = kind; nextTab(kind); renderCase();
    setTimeout(() => { S.justCopied = false; if (S.route.view === "case") renderCase(); }, 1800);
    caseEvent("letter.copied", null, { form: kind, edited: text.trim() !== draft.trim(), ...(act.deadline ? { deadline: act.deadline } : {}),
      change_ratio: Math.round(100 * Math.abs(text.length - draft.length) / Math.max(1, draft.length)) / 100 }).then(loadCase).catch(() => {});
  });
  on("[data-copy-also]", "click", (b) => {
    if (Number(b.dataset.gaps || 0) && goToGap()) return;
    const kind = b.dataset.copyAlso, el = $(`[data-also-text='${CSS.escape(kind)}']`), text = el ? el.innerText : "";
    const also = ((S.data.draft || {}).also || []).find((a) => a.kind === kind) || {};
    const lost = (also.required || []).filter((r) => !text.includes(r.marker));
    if (lost.length) { S.message = T("Please complete the letter first.", `Bitte zuerst ergänzen: ${lost.map((r) => r.title).join(", ")}`); S.messageOk = false; renderCase(); return; }
    if (GAP_RE.test(text) && !(GAP_RE.lastIndex = 0)) { goToGap(); return; }
    if (navigator.clipboard) navigator.clipboard.writeText(text).catch(() => {});
    S.justCopied = kind; nextTab(kind); renderCase();
    setTimeout(() => { S.justCopied = false; if (S.route.view === "case") renderCase(); }, 1800);
    const act = item("next_action", "0") || {};
    caseEvent("letter.copied", null, { also: kind, template: Boolean(also.template), edited: (also.text || "").trim() !== text.trim(), ...(act.deadline ? { deadline: act.deadline } : {}) })
      .then(loadCase).catch(() => {});
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
    const id = S.askWhy; S.askWhy = null;
    await caseEvent("letter.line", id, { included: false, reason: b.dataset.lineReason });
    await loadCase();
  });
  on("#add-doc", "keydown", (el, e) => { if (e.key === "Enter" && el.value.trim()) { S.addDoc = el.value.trim(); renderCase(); } });
  on("[data-add-doc-reason]", "click", async (b) => {  // the handler asks for one more document: type it, Enter, one reason; ticked at once
    const title = S.addDoc, code = b.dataset.addDocReason; S.addDoc = null;
    const step = (S.data.evaluation && S.data.evaluation.current && S.data.evaluation.current.step) || undefined;
    await edit({ op: "add_document", args: { title, why: REASONS[code], ...(step ? { step } : {}) }, reason: "", reason_code: code, recheck: false }).catch((error) => { S.message = error.message; });
    await loadCase();
  });
  on("#change-action", "click", () => { S.changing = !S.changing; S.pickAction = null; renderCase(); });
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
  on("[data-decide]", "click", async (b) => {  // the handler's own decision: one click, no reason asked
    S.lastEdit = await edit({ op: "set_fact", args: { fact: b.dataset.decide, value: b.dataset.value }, reason: "", reason_code: "none", recheck: false }).catch(() => S.lastEdit);
    S.decideOpen = false; S.docTab = null;
    await loadCase();
  });
  on("[data-fee-answer]", "click", (b) => {  // the fee note: the query or the partial refusal, its letter shown to copy
    S.feeAnswer = S.feeAnswer === b.dataset.feeAnswer ? null : b.dataset.feeAnswer; S.docTab = S.feeAnswer; renderCase();
  });
  on("#weil-open", "click", () => { S.weilOpen = !S.weilOpen; renderCase(); });
  on("#lead-open", "click", () => { S.leadOpen = !S.leadOpen; if (S.leadOpen) caseEvent("source.opened", (scr().lead || {}).item_id || null, { reason: "deadline" }).catch(() => {}); renderCase(); });
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
  on("#copy-note", "click", () => {  // the file note writes itself; copying it is logged like the letter
    if (navigator.clipboard) navigator.clipboard.writeText(S.data.file_note).catch(() => {});
    caseEvent("filenote.copied", null, { chars: S.data.file_note.length }).catch(() => {});
    S.noteCopied = true; renderCase(); setTimeout(() => { S.noteCopied = false; if (S.route.view === "case") renderCase(); }, 1800);
  });
  // the handler's own entry: one tap opens the form, its draft survives a redraw, a part opens in place, saving counts at once
  const openForm = (draft) => { S.noting = true; S.entryEdit = null; S.entryError = ""; S.entryDraft = draft || null; renderCase();
    const form = $("#note-form"); if (form) { form.scrollIntoView({ block: "nearest" }); const t = form.querySelector("textarea"); if (t) t.focus(); } };
  on("#add-note", "click", () => { if (S.noting && !S.entryEdit) { S.noting = false; renderCase(); } else openForm(); });
  on("#phone-note", "click", (b) => openForm({ kind: b.dataset.kind, party: b.dataset.party, date: isoToday() }));
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
  on("#use-anyway", "click", async () => {  // the handler uses the draft before the new files are read: allowed, and logged
    await caseEvent("letter.unblocked", null, { files: (S.data.arrived || []).map((f) => f.name).slice(0, 20) }).catch(() => {});
    await loadCase();
  });
  on("[data-close]", "click", async (b) => {
    const line = b.dataset.close === "erledigt_mit_vorbehalt" ? (($("#reservation") || {}).value || "") : "";
    await caseEvent("case.closed", null, { form: b.dataset.close, note_present: Boolean(line.trim()), ...(line.trim() ? { text: line.trim().slice(0, 2000) } : {}) });
    await loadCase();
  });
  on("#next-case", "click", async () => {  // the next case that needs the handler, in the case list's order
    const cases = orderedCases((await api("/api/cases")).cases).filter((c) => c.id !== S.route.id && standOf(c) !== "closed");
    const real = cases.filter((c) => !(c.intake || {}).synthetic), next = real[0] || cases[0];
    location.hash = next ? `#/case/${next.id}/overview` : "#/cases";
  });
  on("#followup-show", "click", () => { const fu = $("#followup-date"); try { fu.showPicker(); } catch (error) { fu.focus(); } });
  on("#followup-date", "change", async (fu) => {
    if (!fu.value) return;
    await caseEvent("followup.set", "followup:0", { date: fu.value, before: (S.data.follow_up || {}).due || null });
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
  const asking = $(".cp-why-row") || (S.addDoc && $(".cp-add"));  // the one-tap reason stands where the hand already is
  if (asking) asking.scrollIntoView({ block: "nearest" });
}

// ---------- case page ----------
async function loadCase() {
  const id = S.route.id;
  if (S.loadedCase !== id) {  // an opened source, a tab, an opened reason and an unsent edit belong to their case
    Object.assign(S, { overviewSource: false, loadedCase: id, docTab: null, docFor: null, docPicked: false, feeAnswer: null, weilOpen: false, leadOpen: false, decideOpen: false, why: null,
                       anliegenOpen: false, keyPoint: null, coverOpen: false, coverDecline: false, blockEdits: {}, alsoEdits: {}, askWhy: null, openOffers: false, changing: false, pickAction: null });
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

function schedulePoll() {
  clearTimeout(S.poll);
  S.poll = setTimeout(async () => {
    if (S.route.view !== "case" || !running()) return;
    const run = await api(`/api/runs/${S.data.run.id}?after=${S.events.length ? S.events[S.events.length - 1].seq : 0}`);
    const seen = Date.now();
    S.events = S.events.concat(run.events.map((e) => ({ ...e, seen })));
    // a file's reading is saved while the run goes on: show the read text from then on
    run.events.forEach((e) => { if (e.file && e.kind === "reading.saved") delete S.pages[e.file]; });
    S.data.run.status = run.status;
    if (!["queued", "running"].includes(run.status)) { S.events = []; S.pages = {}; await loadCase(); return; }
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
  } else if (unaidedPending()) main = `${unaidedView()}<div style="margin-top:22px">${S.file ? `<iframe title="${T("Original file", "Originaldatei")}" src="/api/files/${esc(S.file)}/original" style="width:100%;height:78vh;border:1px solid var(--line)"></iframe>` : ""}</div>`;  // every tab: the original file only
  else if (tab === "claim_reader") main = claimView(await sourceCard(S.file));
  else if (tab === "source_checker") main = `${checkerView()}<div style="margin-top:22px;max-width:760px">${await sourceCard(S.file)}</div>`;
  else if (tab === "document_finder") main = `${documentsView()}${S.overviewSource ? `<div id="overview-source" style="margin-top:22px;max-width:760px">${await sourceCard(S.file)}</div>` : ""}`;
  else if (tab === "result_checker") main = resultView();
  else if (tab === "history") main = `${historyView()}${S.overviewSource ? `<div id="overview-source" style="margin-top:22px;max-width:760px">${await sourceCard(S.file)}</div>` : ""}`;
  else if (tab === "overview") main = `${overviewView()}${S.overviewSource || !hasPrepared() ? `<div id="overview-source" style="margin-top:22px;max-width:760px">${await sourceCard(S.file)}</div>` : ""}`;
  else main = processView();
  // What the handler is typing survives a re-render (a run's progress or a reload redraws the page).
  const typing = [...document.querySelectorAll("#app input[id], #app textarea[id]")].filter((el) => el.value && !["file", "checkbox", "radio"].includes(el.type))
    .map((el) => ({ id: el.id, value: el.value, focus: el === document.activeElement, start: el.selectionStart, end: el.selectionEnd }));
  $("#app").innerHTML = `${renderRail()}<main class="cp-main">${main}</main>`;
  for (const t of typing) {
    const el = document.getElementById(t.id);
    if (!el || el.value || el.type === "file") continue;
    try { el.value = t.value; } catch (e) { continue; }  // a value the field refuses never stops the page
    if (t.focus) { el.focus(); try { el.setSelectionRange(t.start, t.end); } catch (e) { /* not a text field */ } }
  }
  keepMotion($("#app"));
  markInReview();
  bindRail();
  for (const b of document.querySelectorAll("[data-step]")) b.addEventListener("click", () => { S.step = b.dataset.step; renderCase(); });
  for (const b of document.querySelectorAll("[data-step-file]")) b.addEventListener("click", () => { if (b.dataset.stepFile) { S.file = b.dataset.stepFile; S.follow = !running(); renderCase(); } });
  for (const b of document.querySelectorAll("[data-cite-file]")) b.addEventListener("click", () => {
    const holder = b.closest("[data-item]");
    caseEvent("source.opened", holder && /^[a-z_]+:/.test(holder.dataset.item) ? holder.dataset.item : null, { file_id: b.dataset.citeFile, page: Number(b.dataset.page) || null }).catch(() => {});
  });
  for (const b of document.querySelectorAll("[data-cite-file]")) b.addEventListener("click", async () => { S.file = b.dataset.citeFile; S.page = Number(b.dataset.page) || null; S.overviewSource = ["overview", "history", "document_finder"].includes(tab); await renderCase(); const box = $("#overview-source"); if (box) box.scrollIntoView({ block: "start", behavior: "smooth" }); });
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
  if (!el || window.innerWidth < 1000) { if (el) el.style.height = ""; if (side) side.style.maxHeight = ""; return; }
  const top = el.parentElement.getBoundingClientRect().top + window.scrollY;  // where the card starts, stuck or not
  const height = Math.max(400, window.innerHeight - top - 26);
  el.style.height = `${height}px`;
  if (side) side.style.maxHeight = `${height}px`;
}
window.addEventListener("resize", fitCard);

// ---------- knowledge ----------
// What ordinary use shows, content-free (L4): per case and in total; the export is the same JSON.
async function renderAuswertung() {
  const a = await api("/api/auswertung");
  const n = (v) => (v === null || v === undefined ? "—" : esc(String(v)));
  const kv = (o) => Object.entries(o || {}).map(([k, v]) => `${esc(k)} ${v}`).join(" · ") || "—";
  const rows = a.cases.map((c) => `<tr><td><code>${esc(c.case)}</code></td><td>${kv(c.accepted_unchanged)}</td><td>${c.interventions}</td>
    <td>${kv(c.interventions_by_reason)}</td><td>${n(c.letter_changed_ratio)}</td><td>${c.handling_seconds == null ? "—" : Math.round(c.handling_seconds / 60) + " min"}</td>
    <td>${c.sources_opened}</td><td>${c.same_correction_again}</td><td>${c.run_seconds == null ? "—" : c.run_seconds + " s"}</td><td>${c.tokens_noncached == null ? "—" : Math.round(c.tokens_noncached / 1000) + "k"}</td></tr>`).join("");
  $("#app").innerHTML = `<main class="cp-main"><h1 class="cp-title">${T("Evaluation", "Auswertung")}</h1>
    <p class="cp-muted">${T("From ordinary use, without questionnaires. Content-free: cases appear only as pseudonyms.", "Aus der normalen Arbeit, ohne Fragebogen. Ohne Inhalte: Fälle erscheinen nur als Pseudonyme.")}
      <a class="cp-link" href="/api/auswertung" download="auswertung.json">${T("Export", "Export")}</a> · <a class="cp-link" href="/api/manifest" download="manifest.json">${T("Manifest", "Manifest")}</a></p>
    <p>${T("Cases", "Fälle")} ${a.total.cases} · ${T("in use", "genutzt")} ${a.total.cases_used} · ${T("interventions per case", "Eingriffe pro Fall")} ${n(a.total.interventions_per_used_case)} · ${T("same correction again", "gleiche Korrektur erneut")} ${a.total.same_correction_again}</p>
    <table class="cp-table"><thead><tr><th>${T("Case", "Fall")}</th><th>${T("Accepted unchanged", "Unverändert übernommen")}</th><th>${T("Interventions", "Eingriffe")}</th><th>${T("Reasons", "Gründe")}</th>
      <th>${T("Letter changed", "Brief geändert")}</th><th>${T("Handling", "Bearbeitung")}</th><th>${T("Sources opened", "Quellen geöffnet")}</th><th>${T("Same again", "Erneut gleich")}</th><th>${T("Run", "Lauf")}</th><th>Tokens</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="10" class="cp-muted">${T("No use recorded yet.", "Noch keine Nutzung erfasst.")}</td></tr>`}</tbody></table></main>`;
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
  const [data, cases, workflows, review] = await Promise.all([api("/api/knowledge"), api("/api/cases"), api("/api/workflows"),
    S.mayReview ? api("/api/review").catch(() => null) : Promise.resolve(null)]);
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
  const card = (k) => `<article class="cp-card" style="padding:16px 18px;display:grid;gap:8px;align-content:start">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><span class="cp-chip ${k.status === "active" ? "good" : k.status === "retired" ? "" : "wait"}">${esc(word(k.status))}</span>
        <span class="cp-chip">${esc(word(k.kind))}</span>${k.refines ? "" : `<span class="cp-chip">v${k.version}</span>`}${k.refines ? `<span class="cp-chip wait">${(() => { const t = data.knowledge.find((x) => x.id === k.refines); return t ? T(`refines v${t.version} → v${t.version + 1}`, `verfeinert v${t.version} → v${t.version + 1}`) : T("refinement", "Verfeinerung"); })()}</span>` : ""}
        ${k.review_suggested ? `<span class="cp-chip bad">${T("review suggested: contradicted often", "Prüfung empfohlen: oft widersprochen")}</span>` : ""}</div>
      <b>${esc(k.content.title || k.content.question || k.content.text)}</b>${k.content.why ? `<span class="cp-muted">${esc(k.content.why)}</span>` : ""}
      ${k.applies_when_text ? `<span class="cp-muted">${T("Applies when", "Gilt, wenn")}: ${esc(k.applies_when_text)}</span>` : ""}
      <span>${T(`Used ${k.stats.uses} · confirmed ${k.stats.confirmed} · not found ${k.stats.not_found} · contradicted ${k.stats.contradicted}`,
                `${k.stats.uses}× verwendet · ${k.stats.confirmed}× bestätigt · ${k.stats.not_found}× nicht gefunden · ${k.stats.contradicted}× widersprochen`)}</span>
      ${(k.evidence || []).filter((e) => e.quote).slice(0, 2).map((e) => `<span class="cp-muted">“${esc(e.quote)}” — <a href="#/case/${esc(e.case_id)}/claim_reader">${esc(caseName(e.case_id))}</a></span>`).join("")}
      ${seededNote(k) ? `<span class="cp-muted">${esc(seededNote(k))}</span>` : `<span class="cp-muted">${k.origin.kind === "case_edit" ? T("Learned from a case worker’s change in", "Gelernt aus einer Änderung in der Fallbearbeitung, im Fall") : T("Learned by the result checker in", "Gelernt vom Ergebnisprüfer im Fall")} <a href="#/case/${esc(k.origin.case_id)}/process_builder">${esc(caseName(k.origin.case_id))}</a></span>`}
      ${k.uses.length ? `<span>${T("Cases", "Fälle")}: ${k.uses.map((u) => `<a href="#/case/${esc(u.case_id)}/document_finder">${esc(caseName(u.case_id))}</a> <span class="cp-chip ${u.outcome === "present" ? "good" : u.outcome === "contradicted" ? "bad" : ""}">${esc(word(u.outcome))}</span>`).join(" ")}</span>` : ""}
      <details><summary class="cp-link">${T("History", "Verlauf")}</summary><ul class="cp-log">${k.history.map((h) => `<li><b>v${h.version}</b><span>${esc(changeText(h.change))}${h.by ? ` · ${esc(byWhom(h.by))}` : ""} · ${dateText(h.at)}</span></li>`).join("")}</ul></details>
      ${k.status !== "active" && k.status !== "retired" ? replayLine(k, data.knowledge, caseName) : ""}
      <div class="row" style="display:flex;gap:10px">${k.status !== "active" && k.status !== "retired" ? (replayCurrent(k, data.knowledge)
          ? `<button class="cp-button primary" data-activate="${esc(k.ids.join(","))}">${k.refines ? T("Apply refinement", "Verfeinerung übernehmen") : T("Activate", "Freigeben")}</button>`
          : `<button class="cp-button primary" data-replay="${esc(k.ids.join(","))}">${T("Replay", "Nachspielen")}</button>`) : ""}
        ${k.status !== "retired" ? `<button class="cp-button" data-retire="${esc(k.ids.join(","))}">${T("Retire", "Zurückziehen")}</button>` : ""}</div></article>`;
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  const sections = Object.entries(groups).sort(([a], [b]) => a.localeCompare(b, "de")).map(([name, entries]) => {
    const items = Object.values(entries), uses = items.reduce((n, k) => n + k.stats.uses, 0);
    return `<h2 class="cp-section">${esc(name)} <span class="cp-muted">· ${T(`${items.length} items · ${uses} uses`, `${plural(items.length, "Eintrag", "Einträge")} · ${plural(uses, "Verwendung", "Verwendungen")}`)}</span></h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px;align-items:start">${items.map(card).join("")}</div>`;
  }).join("");
  $("#app").innerHTML = `<main class="cp-main"><h1 class="cp-title">${T("Knowledge", "Wissen")}</h1>
    ${review && review.may_review ? reviewTable(review) : ""}
    ${review && review.may_review ? `<h2 class="cp-section cp-learned">${T("Learned from cases", "Aus Fällen gelernt")}</h2>` : ""}
    <p class="cp-muted">${T("What CasePath learned from earlier cases and case workers’ changes. Active items shape new cases; candidates are checked as suggestions until a person activates them.",
      "Was CasePath aus früheren Fällen und aus Änderungen der Fallbearbeitung gelernt hat. Freigegebene Einträge prägen neue Fälle; Vorschläge werden nur als Vorschlag geprüft, bis ein Mensch sie freigibt.")}</p>
    ${sections || `<p class="cp-empty">${T("Nothing learned yet. Knowledge appears after cases are prepared or a case worker saves a change for similar cases.", "Noch nichts gelernt. Wissen entsteht, wenn Fälle vorbereitet werden oder eine Änderung für ähnliche Fälle gespeichert wird.")}</p>`}</main>`;
  const each = (ids, path, reason) => Promise.all(ids.split(",").map((id) => api(`/api/knowledge/${id}/${path}`, { method: "POST", body: JSON.stringify({ reason }) })));
  for (const b of document.querySelectorAll("[data-replay]")) b.addEventListener("click", async () => {  // without a model: what this version would change
    b.disabled = true;
    await each(b.dataset.replay, "replay").catch(() => {});
    renderKnowledge();
  });
  for (const b of document.querySelectorAll("[data-activate]")) b.addEventListener("click", async () => { await each(b.dataset.activate, "activate", T("approved in Knowledge", "im Wissen freigegeben")).catch(() => {}); renderKnowledge(); });
  for (const b of document.querySelectorAll("[data-retire]")) b.addEventListener("click", async () => { await each(b.dataset.retire, "retire", T("retired in Knowledge", "im Wissen zurückgezogen")); renderKnowledge(); });
}

// ---------- review of the legal content (Wissen → Rechtsgebiete) ----------
// A jurist opens one area, sees each element in the words the handler or customer will see beside the passage it rests on
// and its official source, and marks it: geprüft, Änderung nötig …, Frage …. An area whose elements are all geprüft is
// freigegeben; the handler's screen says so (process/review.py).
const REVIEW_WORD = { geprueft: T("checked", "geprüft"), aenderung: T("change needed", "Änderung nötig"), frage: T("question", "Frage"),
                      geaendert: T("changed since review", "geändert seit Prüfung"), offen: T("open", "offen") };
const REVIEW_CHIP = { geprueft: "good", aenderung: "bad", frage: "wait", geaendert: "wait" };
const reviewDay = (at) => dateText(at).slice(0, 10);
function reviewState(status) {
  const cls = status.state === "freigegeben" ? "released" : status.state === "in_pruefung" ? "busy" : "";
  return `<span class="cp-rv-state ${cls}">${esc(status.state === "offen" ? T("not released", "noch nicht freigegeben") : status.label)}</span>`;
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
async function renderReview(id) {
  S.reviewRow = await api(`/api/review/${encodeURIComponent(id)}`);
  drawReview();
}
// A passage as a jurist reads it: the article first, then its words, the official text one click away.
function lawRow(r, linked) {
  const title = `${r.source || ""}${r.version ? `, ${r.version}` : ""}`;
  const source = r.url && !linked ? `<a href="${esc(r.url)}" target="_blank" rel="noopener" title="${esc(title)}">${esc(r.link || r.source || "")}</a>` : "";
  return `<div class="cp-rv-passage"><p class="cp-rv-cite"><b>${esc(r.cite)}</b>${source ? ` ${source}` : ""}${r.verified ? "" : ` <span class="cp-flag">${T("not checked against the official text", "nicht am amtlichen Text geprüft")}</span>`}</p>
    <p class="cp-rv-words">«${esc(r.passage)}»</p></div>`;
}
function reviewElement(el, may) {
  const m = el.mark, editing = S.reviewing && S.reviewing.key === el.key ? S.reviewing.mark : null;
  const others = el.used_in.filter((t) => t !== S.reviewRow.title);
  const who = m && el.state !== "offen" ? `<span class="cp-rv-who">${el.state === "geaendert" ? `${T("earlier", "früher")} ${esc(REVIEW_WORD[m.mark])}: ` : ""}${esc(m.reviewer)}, ${reviewDay(m.at)}</span>` : "";
  const said = m && el.state !== "offen" && (m.comment || m.suggestion) ? `<p class="cp-rv-meta">${m.comment ? `«${esc(m.comment)}»` : ""}${m.suggestion ? `${m.comment ? " · " : ""}${T("Wording", "Vorschlag")}: «${esc(m.suggestion)}»` : ""}</p>` : "";
  const form = editing ? `<form class="cp-rv-form" data-rv-form="${esc(el.key)}" data-mark="${editing}">
      <label>${editing === "aenderung" ? T("What must change", "Was zu ändern ist") : T("Your question", "Ihre Frage")}<textarea name="comment" rows="2" maxlength="4000" required></textarea></label>
      ${editing === "aenderung" ? `<label>${T("Proposed wording (optional)", "Vorschlag für den Wortlaut (freiwillig)")}<textarea name="suggestion" rows="2" maxlength="4000"></textarea></label>` : ""}
      <span><button class="cp-button cp-small">${T("Save", "Speichern")}</button> <button type="button" class="cp-link cp-quiet-link" data-rv-cancel>${T("cancel", "abbrechen")}</button></span></form>` : "";
  const actions = may ? `<div class="cp-rv-actions">
      <button class="cp-button cp-small" data-rv-mark="${esc(el.key)}" aria-pressed="${el.state === "geprueft"}">${T("checked", "geprüft")}</button>
      <button class="cp-button cp-small" data-rv-open="aenderung" data-key="${esc(el.key)}" aria-pressed="${el.state === "aenderung"}">${T("Change needed …", "Änderung nötig …")}</button>
      <button class="cp-button cp-small" data-rv-open="frage" data-key="${esc(el.key)}" aria-pressed="${el.state === "frage"}">${T("Question …", "Frage …")}</button>${who}</div>${form}` : who ? `<p class="cp-rv-meta">${who}</p>` : "";
  return `<article class="cp-rv-el ${el.state}" data-review="${esc(el.key)}">
    <div class="cp-rv-main"><h3>${esc(el.title)}${el.state !== "offen" ? ` <span class="cp-chip ${REVIEW_CHIP[el.state] || ""}">${esc(REVIEW_WORD[el.state])}</span>` : ""}</h3>
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
  $("#app").innerHTML = `<main class="cp-main cp-review">
    <p class="cp-rv-back"><a class="cp-link cp-quiet-link" href="#/knowledge">${T("Legal areas", "Rechtsgebiete")}</a></p>
    <h1 class="cp-title">${esc(d.title)}</h1>
    <p class="cp-rv-sub">${esc(d.subtitle || "")} · ${reviewState(d.status)}</p>
    <p class="cp-rv-bar"><span>${T(`${c.total} elements · ${c.geprueft} checked · ${c.offen} open · ${c.aenderung} change needed · ${c.frage} questions`,
      `${c.total} Elemente · ${c.geprueft} geprüft · ${c.offen} offen · ${c.aenderung} Änderung nötig · ${c.frage} ${c.frage === 1 ? "Frage" : "Fragen"}`)}</span>
      <label class="cp-rv-filter"><input type="checkbox" id="rv-only-open" ${only ? "checked" : ""}> ${T("open only", "nur offene")}</label>
      <a class="cp-link cp-quiet-link" href="/api/review/${encodeURIComponent(d.id)}/pruefpaket" target="_blank" rel="noopener">${T("Review pack (print)", "Prüfpaket")}</a></p>
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
    S.reviewRow = await api(`/api/review/${encodeURIComponent(S.reviewRow.id)}`);
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
  if (next.view !== "case" || next.id !== S.route.id) Object.assign(S, { data: null, pages: {}, file: null, step: null, editing: false, lastEdit: null, events: [], follow: true, message: "", shown: new Set(), litKey: null });
  S.route = next;
  renderTop();
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
}

(async () => {
  try { const me = await api("/api/me"); S.me = me.user; S.mayReview = Boolean(me.may_review); } catch (error) { S.me = ""; S.mayReview = false; }
  try { S.canUpload = (await api("/api/health")).uploads !== false; } catch (error) { S.canUpload = true; }
  window.addEventListener("hashchange", route);
  route();
})();

// Each slice's own functions go in its section below (function declarations: the start above runs after the whole script).
// ---------- assessment: the decision brief, the customer's questions and the recommendation (Slice A) ----------

// ---------- completion: approval, the Versandpaket, dispatch and the queue (Slice B) ----------

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
const KNOWLEDGE_CHANGE = { needs: T("documents", "Unterlagen"), now: T("asked now", "jetzt verlangt"), offered: T("offered", "angeboten"),
                           later: T("asked later", "später verlangt"), questions: T("questions", "Fragen"), next_action: T("next step", "nächster Schritt") };
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
    <ul class="cp-log">${Object.entries(changed).map(([id, what]) => `<li><a href="#/case/${esc(id)}/overview">${esc(caseName(id))}</a> <span class="cp-muted">· ${what.map((w) => esc(KNOWLEDGE_CHANGE[w] || w)).join(", ")}</span></li>`).join("")}</ul></details>`;
}
// An update at work says what it reads: «Neu eingegangen: 2 Datei(en) · wird aktualisiert»; one started again after a
// restart says so («wird fortgesetzt»).
function arrivalNow(run) {
  if (!run || run.kind !== "update") return "";
  const came = (S.data.arrived || []).length || (S.data.new_files || []).length;
  const resumed = (S.data.caseEvents || []).some((e) => e.kind === "update.started" && e.run === run.id && e.resumed);
  return `<p class="cp-runnow cp-arrival-now"><b>${resumed ? T("Update interrupted: the service was restarted", "Aktualisierung unterbrochen: Der Dienst wurde neu gestartet")
    : T(`New: ${came} file(s)`, `Neu eingegangen: ${came} Datei(en)`)}</b> · ${resumed ? T("continues", "wird fortgesetzt") : T("updating", "wird aktualisiert")}</p>`;
}
