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
  completed: "abgeschlossen", failed: "fehlgeschlagen", running: "läuft", queued: "wartet", interrupted: "unterbrochen",
  present: "vorhanden", missing: "fehlt", unusable: "unbrauchbar", unchecked: "nicht geprüft", contradicted: "widersprochen",
  not_found: "nicht gefunden", confirmed: "bestätigt", conflicting: "widersprüchlich", established: "belegt", presumed: "vermutet", unknown: "unbekannt", active: "aktiv", candidate: "Vorschlag", retired: "zurückgezogen",
  reviewed: "geprüft", draft: "Entwurf", document_need: "Dokument", question: "Frage", step: "Schritt", note: "Hinweis",
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
  if (parts[0] === "knowledge") return { view: "knowledge" };
  return { view: "cases" };
}

const dateText = (iso) => {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? esc(iso) : `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;
};

// ---------- top bar ----------
function renderTop() {
  const route = S.route;
  const wordmark = `<a class="cp-wordmark" href="#/cases"><svg viewBox="0 0 28 28" aria-hidden="true"><path d="M22 6.5A10 10 0 1 0 22 21.5" fill="none" stroke="#82072a" stroke-width="4.5" stroke-linecap="round"/></svg>CasePath</a>`;
  let tabs;
  if (route.view === "case") {
    const working = activeAgent();
    const work = { claim_reader: "claim_reader", source_checker: "claim_reader", process_builder: "process_builder", document_finder: "document_finder", result_checker: "overview" };
    tabs = [["overview", T("Overview", "Übersicht"), "check"], ["claim_reader", T("File", "Akte"), "doc"], ["process_builder", T("Process", "Prozess"), "nodes"],
            ["document_finder", T("Documents", "Unterlagen"), "folder"], ["history", T("History", "Verlauf"), "memory"]].map(([id, title, ic]) => `<a class="cp-tab ${work[working] === id ? "working" : ""}" href="#/case/${esc(route.id)}/${id}"
      ${route.tab === id ? 'aria-current="page"' : ""} data-tab="${id}">${icon(ic)}${title}<span class="cp-pulse" aria-hidden="true"></span></a>`).join("");
  } else {
    tabs = [["cases", T("Cases", "Fälle"), "folder"], ["knowledge", T("Knowledge", "Wissen"), "memory"]].map(([id, title, ic]) =>
      `<a class="cp-tab" href="#/${id}" ${route.view === id ? 'aria-current="page"' : ""}>${icon(ic)}${title}</a>`).join("");
  }
  const other = LANG === "de" ? "en" : "de";
  $("#top").innerHTML = `${wordmark}<nav class="cp-tabs" aria-label="${T("Views", "Ansichten")}">${tabs}</nav>
    <div class="cp-top-right">${route.view === "case" ? `<a class="cp-link" href="#/knowledge">${icon("memory")}${T("Knowledge", "Wissen")}</a>` : ""}<span>${esc(S.me || "")}</span>
      <a class="cp-link" href="?lang=${other}${esc(location.hash)}" lang="${other}">${other.toUpperCase()}</a></div>`;
}

// ---------- cases ----------
async function renderCases() {
  const [cases, workflows, health] = await Promise.all([api("/api/cases"), api("/api/workflows"), api("/api/health")]);
  const imports = health.imports ? await api("/api/imports").catch(() => null) : null;
  S.workflows = workflows.workflows;
  const titles = Object.fromEntries(S.workflows.map((w) => [w.id, w.title]));
  const today = new Date().toISOString().slice(0, 10);
  const ordered = [...cases.cases].sort((a, b) => (a.follow_up || "9999") < (b.follow_up || "9999") ? -1 : (a.follow_up || "9999") > (b.follow_up || "9999") ? 1 : 0);
  const rows = ordered.map((c) => `<tr><td><a href="#/case/${esc(c.id)}/overview">${esc(c.title)}</a>
      ${c.next_action ? `<br><small class="cp-muted">${esc(T(c.next_action.label.en, c.next_action.label.de))}</small>` : ""}
      ${c.intake && c.intake.synthetic ? ` <span class="cp-chip">${T("synthetic", "synthetisch")}</span>` : ""}</td>
      <td>${esc(titles[c.workflow_id] || c.workflow_id || "—")}</td><td>${c.file_count}</td><td>${statusChip(c.run_status)}</td><td>${c.follow_up ? `<span class="cp-chip ${c.follow_up <= today ? "bad" : ""}">${dateText(c.follow_up)}</span>` : "—"}</td></tr>`).join("");
  const catalogue = S.workflows.map((w) => `<tr><td>${esc(w.title)}</td><td><span class="cp-chip ${w.status === "reviewed" ? "good" : "wait"}">${esc(word(w.status))}</span></td>
      <td>${T(`${w.steps} steps · ${w.documents} document needs`, `${w.steps} Schritte · ${w.documents} Dokumente`)}</td><td>${w.open_questions ? T(`${w.open_questions} open questions`, `${w.open_questions} offene Fragen`) : "—"}</td>
      <td class="cp-muted">${w.sources.map((s) => esc(s.title)).join("; ")}</td></tr>`).join("");
  $("#app").innerHTML = `<main class="cp-main"><h1 class="cp-title">${T("Cases", "Fälle")}</h1>
    <p class="cp-muted" style="max-width:820px">${T("CasePath finds each case's process from its files, keeps its document checklist (required, present, missing) and builds Knowledge that grows with every case. New Knowledge is reused only after a person approves it.",
      "CasePath erkennt aus den Akten den Prozess jedes Falls, führt seine Dokumenten-Checkliste (nötig, vorhanden, fehlend) und baut Wissen auf, das mit jedem Fall wächst. Neues Wissen wird erst nach Freigabe durch einen Menschen wiederverwendet.")}</p>
    <form class="cp-form" id="new-case"><input name="title" placeholder="${T("New case: a short title", "Neuer Fall: kurzer Titel")}" aria-label="${T("New case title", "Titel des neuen Falls")}" required maxlength="300">
      <button class="cp-button primary">${icon("plus")}${T("Create case", "Fall anlegen")}</button></form>
    ${rows ? `<table class="cp-table"><thead><tr><th>${T("Case", "Fall")}</th><th>${T("Process", "Prozess")}</th><th>${T("Sources", "Quellen")}</th><th>${T("Last run", "Letzte Vorbereitung")}</th><th>${T("Follow-up", "Wiedervorlage")}</th></tr></thead><tbody>${rows}</tbody></table>`
           : `<p class="cp-empty">${T("No cases yet. Create one, then add its documents.", "Noch keine Fälle. Legen Sie einen an und fügen Sie dann seine Dokumente hinzu.")}</p>`}
    ${imports ? `<h2 class="cp-section">${T("Case files waiting to be imported", "Bereitgestellte Akten")}</h2>
      <p class="cp-muted">${T("Files placed in the shared folder", "Dateien im gemeinsamen Ordner")} <code>${esc(imports.folder)}</code>. ${T("Each file becomes one case.", "Jede Datei wird zu einem Fall.")}</p>
      ${imports.files.length ? `<table class="cp-table"><thead><tr><th>${T("File", "Datei")}</th><th>${T("Contents", "Inhalt")}</th><th></th></tr></thead><tbody>${imports.files.map((f) =>
        `<tr><td><b>${esc(f.title || f.name)}</b>${f.title && f.title !== f.name ? `<br><small class="cp-muted">${esc(f.name)}</small>` : ""}</td>
        <td>${f.prepared ? T(`prepared · ${f.files ?? "?"} file(s)${f.pages ? ` · ${f.pages} pages` : ""}`, `vorbereitet · ${f.files ?? "?"} Datei(en)${f.pages ? ` · ${f.pages} Seiten` : ""}`)
          : f.size ? `${(f.size / 1048576).toFixed(1)} MB` : "—"}</td><td>${f.case ? `<a class="cp-link" href="#/case/${esc(f.case)}/overview">${T("Open case", "Fall öffnen")}</a>`
          : `<button class="cp-button" data-import="${esc(f.path)}">${icon("plus")}${T("Import", "Importieren")}</button>`}</td></tr>`).join("")}</tbody></table>`
        : `<p class="cp-empty">${T("No files there yet.", "Noch keine Dateien dort.")}</p>`}` : ""}
    <h2 class="cp-section">${T("Processes", "Prozesse")}</h2>
    ${catalogue ? `<table class="cp-table"><thead><tr><th>${T("Process", "Prozess")}</th><th>Status</th><th>${T("Size", "Umfang")}</th><th>${T("Open questions", "Offene Fragen")}</th><th>${T("Sources", "Quellen")}</th></tr></thead><tbody>${catalogue}</tbody></table>`
               : `<p class="cp-empty">${T("No process is in the catalogue yet. Cases will show as unmapped until one is added.", "Noch kein Prozess im Katalog. Fälle bleiben ohne Prozess, bis einer erfasst ist.")}</p>`}</main>`;
  for (const button of document.querySelectorAll("[data-import]")) button.addEventListener("click", async () => {
    button.disabled = true;
    button.textContent = T("Importing…", "Wird importiert …");
    try {
      const created = await api("/api/imports", { method: "POST", body: JSON.stringify({ path: button.dataset.import }) });
      location.hash = `#/case/${created.case.id}/claim_reader`;
    } catch (error) { button.disabled = false; button.textContent = error.message; }
  });
  $("#new-case").addEventListener("submit", async (event) => {
    event.preventDefault();
    const title = new FormData(event.target).get("title");
    const created = await api("/api/cases", { method: "POST", body: JSON.stringify({ title }) });
    location.hash = `#/case/${created.id}/claim_reader`;
  });
}

function statusChip(status) {
  if (!status) return `<span class="cp-muted">${T("not run", "nicht vorbereitet")}</span>`;
  const kind = status === "completed" ? "good" : status === "failed" || status === "interrupted" ? "bad" : "wait";
  return `<span class="cp-chip ${kind}">${esc(word(status))}</span>`;
}

// ---------- case data helpers ----------
const result = () => (S.data && S.data.run && S.data.run.status === "completed" ? S.data.run.result : null) || lastResult();
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
function proofFor(fileId) {
  if (unaidedPending()) return "";  // the own answer comes first: no result shows beside the files
  const factRows = recorded("fact"), docRows = recorded("document");
  const numbers = facts().map((f, i) => (factRows[f.id] && factRows[f.id].verdict === "accepted" && factRows[f.id].citations.some((c) => c.file === fileId) ? i + 1 : null)).filter(Boolean);
  const needs = Object.values(docRows).filter((d) => d.verdict === "accepted" && (d.files || []).includes(fileId));
  const parts = [];
  if (numbers.length) parts.push(T(`Proof for question${numbers.length > 1 ? "s" : ""} ${numbers.join(", ")}`, `Beleg für Frage ${numbers.join(", ")}`));
  if (needs.length) parts.push(T(`Meets ${needs.length} document need${needs.length > 1 ? "s" : ""}`, `Erfüllt ${needs.length} Dokument${needs.length > 1 ? "e" : ""}`));
  return parts.join(" · ");
}

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
    transport: T("the model could not be reached; please try again", "Das Modell war nicht erreichbar; bitte erneut versuchen"),
    schema_mismatch: T("the model gave an unusable answer; please try again", "Das Modell gab eine unbrauchbare Antwort; bitte erneut versuchen"),
    max_output_tokens: T("the page was too long for one answer", "die Seite war zu lang für eine Antwort"),
    "no image in the file": T("the file holds no image of this page", "die Datei enthält kein Bild dieser Seite"),
  };
  if (known[reason]) return known[reason];
  if (/^http_(429|5\d\d)$/.test(reason)) return T("the model service is busy; please try again shortly", "Der Modelldienst ist ausgelastet; bitte gleich erneut versuchen");
  if (/^http_4\d\d$/.test(reason)) return T(`the model service refused the request (${reason.slice(5)})`, `Der Modelldienst hat die Anfrage abgelehnt (${reason.slice(5)})`);
  return error;
}

// ---------- rail ----------
function renderRail() {
  const d = S.data, files = d.files || [];
  const rows = files.map((f) => {
    const proof = proofFor(f.id);
    return `<button class="cp-source" data-file="${esc(f.id)}" aria-current="${S.file === f.id}">${fileIcon(f)}
      <span class="cp-source-label">${esc(f.name)}<small>${f.extraction && f.extraction.attached_to ? `${T("Attached to", "Anhang von")} ${esc(f.extraction.attached_to)}`
        : `${T("Received", "Eingegangen")} ${dateText(f.created_at)}`}${f.extraction && f.extraction.pages ? ` · ${(f.extraction.kept_pages || []).length || f.extraction.pages} ${T("pages", "Seiten")}` : ""}</small>
      ${proof ? `<span class="cp-proof">${icon("tick")}${esc(proof)}</span>` : ""}
      ${(f.extraction && (f.extraction.instruction_like || []).length) ? `<span class="cp-warn">${T("Contains text addressed to an AI", "Enthält Text an die KI")}</span>` : ""}</span></button>${segmentRows(f)}`;
  }).join("");
  const chooser = !d.case.workflow_id && S.workflows && S.workflows.length
    ? `<label class="cp-status">${T("Process", "Prozess")} <select id="workflow" aria-label="${T("Process for this case", "Prozess für diesen Fall")}"><option value="">${T("Find it from the documents", "Aus den Dokumenten bestimmen")}</option>
        ${S.workflows.map((w) => `<option value="${esc(w.id)}">${esc(w.title)}</option>`).join("")}</select></label>`
    : d.workflow ? `<span class="cp-status">${T("Process", "Prozess")}: ${esc(d.workflow.title)}</span>` : "";
  const run = d.run;
  const status = run ? (running() ? T(`${AGENT_TITLE[activeAgent()] || "Agents"} working…`, `${AGENT_TITLE[activeAgent()] || "Agenten"} arbeitet…`) : run.status === "failed" ? `${T("Failed", "Fehlgeschlagen")}: ${esc(runError(run.error))}`
    : run.status === "completed" ? `${T("Prepared", "Vorbereitet am")} ${dateText(run.finished_at)}` : word(run.status)) : T("Not prepared yet", "Noch nicht vorbereitet");
  return `<aside class="cp-rail" aria-label="${T("Sources", "Quellen")}">
    <div class="cp-caseline">${esc(d.case.title)}<small>${esc(d.case.id.slice(-8).toUpperCase())}</small></div>
    <div class="cp-rail-head">${T("Sources", "Quellen")}<span>${files.length}</span>${S.canUpload === false ? "" : `<label class="cp-link">${icon("plus")}${T("Add source", "Hinzufügen")}<input type="file" id="upload" multiple hidden></label>`}</div>
    ${rows || `<div class="cp-drop" id="drop">${T("Drop the case documents here", "Falldokumente hierher ziehen")}</div>`}
    ${S.message ? `<p class="${S.messageOk ? "cp-muted" : "cp-error"}" style="padding:0 27px">${esc(S.message)}</p>` : ""}
    <div class="cp-rail-foot">${unaidedPending() ? "" : chooser}
      <button class="cp-button ${run && run.status === "completed" ? "cp-quiet" : "primary"}" id="run" ${unaidedPending() ? "hidden" : ""} ${running() || !files.length ? "disabled" : ""}>${running() ? '<span class="cp-spinner"></span>' : icon("nodes")}${run && run.status === "completed" ? T("Prepare again", "erneut vorbereiten") : T("Prepare case", "Fall vorbereiten")}</button>
      <span class="cp-status ${run && run.status === "failed" ? "failed" : ""}">${esc(status)}</span>
      ${S.file ? `<a class="cp-button" href="/api/files/${esc(S.file)}/original" target="_blank" rel="noopener">${T("Open full source", "Original öffnen")} ${icon("external")}</a>` : ""}</div>
  </aside>`;
}

function segmentRows(file) {
  const segments = (file.extraction && file.extraction.segments) || [];
  if (!segments.length) return "";
  return `<ol class="cp-segs" aria-label="${T("Documents in", "Dokumente in")} ${esc(file.name)}">${segments.map((s) => `<li><button class="cp-seg" data-file="${esc(file.id)}" data-page="${s.first_page}" title="${esc(s.summary || "")}">
    <span>${esc(s.title || s.kind)}</span><small>${esc([s.kind !== s.title ? s.kind : "", s.date, `${T("p.", "S.")} ${s.first_page}${s.last_page !== s.first_page ? `–${s.last_page}` : ""}`].filter(Boolean).join(" · "))}</small></button></li>`).join("")}</ol>`;
}

function bindRail() {
  for (const button of document.querySelectorAll("[data-file]")) button.addEventListener("click", () => { S.file = button.dataset.file; S.page = Number(button.dataset.page) || null; S.follow = !running(); renderCase(); });
  const upload = $("#upload");
  if (upload) upload.addEventListener("change", () => uploadFiles(upload.files));
  const drop = $("#drop") || $(".cp-rail");
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); if (S.canUpload !== false) uploadFiles(e.dataTransfer.files); });
  const run = $("#run");
  if (run) run.addEventListener("click", startRun);
  const workflow = $("#workflow");
  if (workflow) workflow.addEventListener("change", async () => {
    if (workflow.value) await api(`/api/cases/${S.route.id}/workflow`, { method: "PUT", body: JSON.stringify({ workflow_id: workflow.value }) });
    await loadCase();
  });
}

async function uploadFiles(list) {
  S.message = "";
  for (const file of list) {
    const form = new FormData();
    form.append("file", file);
    try { await api(`/api/cases/${S.route.id}/files`, { method: "POST", body: form }); }
    catch (error) { S.message = `${file.name}: ${error.message}`; }
  }
  await loadCase();
}

async function startRun() {
  // Preparing again calls the model again; a prepared case asks first.
  if (S.data && S.data.lastCompleted && !window.confirm(T("This case is already prepared. Prepare it again? The agents read the files once more, which uses the model again.",
      "Dieser Fall ist bereits vorbereitet. Nochmals vorbereiten? Die Agenten lesen die Dokumente erneut; das ruft das Modell nochmals auf."))) return;
  try {
    await api(`/api/cases/${S.route.id}/runs`, { method: "POST" });
    S.follow = true;
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
  for (let i = S.events.length - 1; i >= 0; i -= 1) if (S.events[i].cite) return { ...S.events[i].cite, key: `hit:${S.events[i].seq}` };
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
  const head = doc.headers ? `<dl class="cp-doc-head">${["From", "To", "Date", "Subject"].filter((k) => doc.headers[k]).map((k) => `<dt>${headerName[k]}:</dt><dd>${esc(doc.headers[k])}</dd>`).join("")}</dl>` : "";
  // An e-mail's header lines are shown above; its body starts after the first blank line.
  const skip = (p) => (doc.headers && p === doc.pages[0] && p.text.indexOf("\n\n") >= 0 ? p.text.indexOf("\n\n") + 2 : 0);
  const body = doc.pages.length ? doc.pages.map((p) => `${p.page ? `<span class="page" id="page-${p.page}">${T("Page", "Seite")} ${p.page}</span>` : ""}${highlight(p.text, p.page, cites, skip(p))}`).join("\n")
    : doc.kind === "image" ? `<img alt="${esc(doc.name)}" src="/api/files/${esc(fileId)}/original" style="max-width:100%">` : `<span class="cp-muted">${T("No readable text.", "Kein lesbarer Text.")}</span>`;
  return `<article class="cp-card" aria-label="${esc(doc.name)}"><div class="cp-doc-toolbar">
      <button class="cp-icon-button" data-step-file="${esc(files[index - 1] || "")}" aria-label="${T("Previous source", "Vorherige Quelle")}" ${index <= 0 ? "disabled" : ""}>${icon("left")}</button>
      <button class="cp-icon-button" data-step-file="${esc(files[index + 1] || "")}" aria-label="${T("Next source", "Nächste Quelle")}" ${index >= files.length - 1 ? "disabled" : ""}>${icon("right")}</button>
      <span class="grow"><span class="name">${esc(doc.name)}</span></span><a class="cp-icon-button" href="/api/files/${esc(fileId)}/original" target="_blank" rel="noopener" aria-label="${T("Open full source", "Original öffnen")}">${icon("external")}</a></div>
    ${head}<div class="cp-doc-body">${body}</div>${readingNote(doc)}</article>`;
}

function readingNote(doc) {
  const read = (doc.pages_transcribed || []).length, unread = (doc.pages_without_text || []).length;
  const why = [...new Set(Object.values(doc.unread_reasons || {}))].map((reason) => runError(reason)).join("; ");
  const parts = [read ? T(`${read} scanned page${read > 1 ? "s" : ""} read from the page image by the model.`, `${read} gescannte Seite${read > 1 ? "n" : ""} vom Modell aus dem Seitenbild gelesen.`) : "",
                 !unread ? "" : why ? T(`${unread} page${unread > 1 ? "s" : ""} not read (${why}).`, `${unread} Seite${unread > 1 ? "n" : ""} nicht gelesen (${why}).`)
                   : running() ? T(`${unread} scanned page${unread > 1 ? "s are" : " is"} being read.`, `${unread} gescannte Seite${unread > 1 ? "n werden" : " wird"} gerade gelesen.`)
                   : T(`${unread} scanned page${unread > 1 ? "s" : ""} not read yet; “Prepare case” reads ${unread > 1 ? "them" : "it"}.`, `${unread} gescannte Seite${unread > 1 ? "n" : ""} noch nicht gelesen; «Fall vorbereiten» liest sie.`)].filter(Boolean);
  const note = parts.length ? parts.join(" ") : doc.note;
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

function processView() {
  const model = graphModel();
  if (!model) return `<p class="cp-empty">${S.data.case.workflow_id ? T("Prepare the case to build its process.", "Bereiten Sie den Fall vor, um seinen Prozess aufzubauen.")
    : T("Choose a process on the left, or prepare the case and CasePath finds it from the documents.", "Wählen Sie links einen Prozess, oder bereiten Sie den Fall vor: CasePath bestimmt ihn aus den Dokumenten.")}</p>`;
  if (!S.step || !model.steps[S.step]) S.step = (model.path.find((p) => p.state === "current") || model.path[model.path.length - 1]).step.id;
  const nodes = model.nodes.map((n, i) => {
    const cls = n.state === "passed" || n.state === "terminal" ? "done" : n.state === "current" ? "current" : "";
    return `<button class="cp-node ${cls}" data-step="${esc(n.step.id)}" aria-pressed="${S.step === n.step.id}"><span class="badge">${cls === "done" ? icon("tick") : ""}</span>
      <b>${i + 1}</b><span title="${esc(n.step.title)}">${esc(shortTitle(n.step.title))}</span>${originLabel(n.step)}</button>`;
  }).join("");
  const selected = model.steps[S.step];
  const pathIds = model.path.map((p) => p.step.id);
  const taken = pathIds[pathIds.indexOf(S.step) + 1];
  const branches = (selected.next || []).length > 1 ? `<div class="cp-branches">${selected.next.map((e) => `<span class="cp-branch ${e.to === taken ? "taken" : ""}">${esc(e.label || model.steps[e.to].title)}</span>`).join("")}</div>` : "";
  return `${S.lastEdit ? beforeNow() : ""}
    <div class="row" style="display:flex;gap:18px;align-items:center;margin-bottom:12px"><button class="cp-edit-link" id="edit-open">${icon("pencil")}${T("Edit decision", "Entscheid bearbeiten")}</button>
      <span class="cp-muted">${T("Selected", "Ausgewählt")}: ${esc(selected.title)}</span></div>
    ${S.editing ? editForm(selected) : ""}
    <div class="cp-graph" aria-label="${T("Process", "Prozess")}">${nodes}</div>${branches}${chain()}${preview()}`;
}

function chain() {
  const ev = S.data.evaluation, r = result() || {};
  const accepted = (r.facts || []).filter((f) => f.verdict === "accepted");
  const present = ev.documents.filter((d) => d.status === "present");
  const missing = ev.documents.filter((d) => ["missing", "unusable"].includes(d.status) && !["suggested", "optional"].includes(d.required));
  const knowledge = ((S.data.provenance || {}).knowledge || []).filter((k) => k.applied);
  const sources = (S.data.process.sources || []).filter((s) => !["knowledge", "edit"].includes(s.id));
  const list = (items, empty) => items.length ? `<ul>${items.join("")}</ul>` : `<span class="cp-muted">${empty}</span>`;
  return `<div class="cp-chain">
    <section><h4>${icon("doc")}${T("Source facts", "Belegte Fakten")}</h4>${list(accepted.slice(0, 6).map((f) => `<li><span class="ok">${icon("check")}</span>${esc(clip(questionOf(f.fact), 70))}: ${esc(clip(valueText(f.value), 60))}</li>`)
      .concat(accepted.length > 6 ? [`<li><a class="cp-link" href="#/case/${esc(S.route.id)}/source_checker">${T(`and ${accepted.length - 6} more`, `und ${accepted.length - 6} weitere`)}</a></li>`] : []), T("None accepted yet", "Noch keine bestätigt"))}</section>
    <section><h4>${icon("law")}${T("Basis", "Grundlage")}</h4>${list(sources.map((s) => `<li>${esc(s.title)}</li>`), "—")}</section>
    <section><h4>${icon("evidence")}${T("Current evidence", "Vorhandene Belege")}</h4>${list(present.map((d) => `<li>${esc(d.title)}</li>`), T("None found yet", "Noch keine gefunden"))}</section>
    <section><h4>${icon("doc")}${T("Evidence still needed", "Noch benötigte Belege")}</h4>${list(missing.map((d) => `<li>${esc(d.title)}</li>`), T("Nothing missing", "Nichts fehlt"))}</section>
    <section><h4>${icon("memory")}${T("From earlier cases", "Aus früheren Fällen")}</h4>${list(knowledge.map((k) => `<li>${esc(knowledgeTitle(k))}${k.version ? ` <span class="cp-kv">v${esc(k.version)} ${T("used", "genutzt")}</span>` : ""}</li>`), T("No Knowledge applied", "Kein Wissen angewendet"))}</section>
    <a class="cp-missing-box" href="#/case/${esc(S.route.id)}/document_finder">${icon("folder", "big")}<span>${T("Documents", "Dokumente")}<br><b>${T(`${missing.length} missing or unusable`, `${missing.length} fehlen oder unbrauchbar`)}</b></span>${icon("right")}</a></div>`;
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

function preview() {
  const r = result() || {};
  const timeline = (r.brief && r.brief.timeline) || [];
  if (!timeline.length) return "";
  return `<section class="cp-preview"><div class="cp-lines">${timeline.map((t, i) => `<div class="${i === timeline.length - 1 ? "cited" : ""}"><time>${esc(t.date)}</time><span>${esc(t.event)}</span></div>`).join("")}</div>
    <div class="cp-page">${timeline.map((t) => esc((t.citations[0] || {}).quote || "")).join("\n\n")}</div></section>`;
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
    <label class="cp-check"><input type="checkbox" name="similar"> ${T("Use for similar cases", "Für ähnliche Fälle übernehmen")}</label>
    <label class="cp-check"><input type="checkbox" name="activate" disabled> ${T("Apply to new cases now (otherwise it is suggested until approved)", "Ab sofort bei neuen Fällen anwenden (sonst nur Vorschlag bis zur Freigabe)")}</label>
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
  form.similar.addEventListener("change", () => { form.activate.disabled = !form.similar.checked; if (!form.similar.checked) form.activate.checked = false; });
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
        op, args, reason: form.reason.value, use_for_similar: form.similar.checked, activate: form.activate.checked }) });
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
function claimView(card) {
  const r = result();
  const brief = r && r.brief;
  return `${spine()}<div class="cp-live"><div>${card}</div><aside>${brief ? `<section class="cp-card" style="padding:16px 18px">
      <h2 class="cp-section" style="margin-top:0">${T("The request", "Das Anliegen")}</h2><p>${esc(brief.request || "")}</p>
      ${(brief.parties || []).length ? `<h2 class="cp-section">${T("Parties", "Parteien")}</h2><ul>${brief.parties.map((p) => `<li>${esc(p.name)} <span class="cp-muted">· ${esc(p.role)}</span></li>`).join("")}</ul>` : ""}
      ${(brief.timeline || []).length ? `<h2 class="cp-section">${T("Timeline", "Chronologie")}</h2><div class="cp-lines">${brief.timeline.map((t, i) => {
        const c = (t.citations || [])[0];
        return `<div><time>${esc(t.date)}</time><span>${c ? `<button class="cp-link" data-cite-file="${esc(c.file)}" data-page="${c.page || ""}" title="${esc(c.quote)}">${esc(t.event)}</button>` : esc(t.event)}${rate(`timeline:${i}`)}</span></div>`;
      }).join("")}</div>` : ""}
    </section>` : `<p class="cp-empty">${T("The claim reader’s brief appears here after the case is prepared.", "Die Übersicht des Falllesers erscheint hier, sobald der Fall vorbereitet ist.")}</p>`}${dossierContents()}</aside></div>`;
}

// What each bundled file contains, document by document, from the reading step.
function dossierContents() {
  const files = (S.data.files || []).filter((f) => ((f.extraction || {}).segments || []).length);
  if (!files.length) return "";
  const count = files.reduce((n, f) => n + f.extraction.segments.length, 0);
  return `<section class="cp-card cp-contents"><h2 class="cp-section" style="margin-top:0">${T(`Contents of the files · ${count} documents`, `Inhalt der Dossiers · ${count} Dokumente`)}</h2>
    ${files.map((f) => `${files.length > 1 ? `<h3>${esc(f.name)}</h3>` : ""}<ol>${f.extraction.segments.map((s) => `<li><button class="cp-link" data-cite-file="${esc(f.id)}" data-page="${s.first_page}">
      <span>${esc([s.date, s.kind].filter(Boolean).join(" · "))} <small>${T("p.", "S.")} ${s.first_page}${s.last_page !== s.first_page ? `–${s.last_page}` : ""}</small></span>
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

function documentsView() {
  const ev = S.data.evaluation;
  if (!ev) return `<p class="cp-empty">${T("The document checklist appears once the case has a process.", "Die Dokumenten-Checkliste erscheint, sobald der Fall einen Prozess hat.")}</p>`;
  const rows = recorded("document");
  const origin = (id) => { const d = S.data.process.documents.find((x) => x.id === id) || {};
    const k = d.knowledge && (S.knowledge || []).find((x) => x.id === d.knowledge);
    return d.knowledge ? (seededNote(k) ? `${T("From Knowledge", "Aus dem Wissen")} · ${seededNote(k)}` : T("From Knowledge", "Aus dem Wissen")) : d.legal_basis ? T(`Required by law (${d.legal_basis})`, `Nach Gesetz verlangt (${d.legal_basis})`)
      : d.edit ? T("Added for this case", "Für diesen Fall ergänzt") : T("From the process", "Aus dem Prozess"); };
  const missing = ev.documents.filter((d) => ["missing", "unusable"].includes(d.status) && !["suggested", "optional", "depends"].includes(d.required)).length;
  if (!ev.documents.length) return `<h1 class="cp-title">${T("Documents", "Dokumente")}</h1><p class="cp-empty">${T("No document needs: no documented process with documents applies to this case yet. Choose the fitting process in the overview, then prepare the case again.", "Keine Dokumente verlangt: Für diesen Fall gilt noch kein hinterlegter Prozess mit Dokumenten. Wählen Sie in der Übersicht den passenden Prozess und bereiten Sie den Fall erneut vor.")}</p>`;
  return `<h1 class="cp-title">${T("Documents", "Dokumente")} <span class="cp-muted">· ${T(`${missing} missing or unusable`, `${missing} fehlen oder unbrauchbar`)}</span></h1>
    <table class="cp-table"><thead><tr><th>${T("Document", "Dokument")}</th><th>${T("Why", "Wozu")}</th><th>Status</th><th>${T("Proof", "Beleg")}</th><th>${T("Origin", "Herkunft")}</th></tr></thead><tbody>${ev.documents.map((d) => {
      const row = rows[d.document] || {};
      const chip = d.status === "present" ? "good" : d.status === "missing" || d.status === "unusable" ? (["suggested", "optional"].includes(d.required) ? "wait" : "bad") : "wait";
      const note = { depends: d.questions && d.questions.length ? T(`depends on: ${esc(d.questions.map((q) => q.question).join(" / "))}`, `hängt ab von: ${esc(d.questions.map((q) => q.question).join(" / "))}`) : T("depends on an open answer", "hängt von einer offenen Antwort ab"), suggested: T("suggested by Knowledge", "vom Wissen vorgeschlagen"), optional: T("optional", "freiwillig") }[d.required];
      return `<tr data-item="document:${esc(d.document)}"><td><b>${esc(d.title)}</b>${note ? `<br><small class="cp-muted">${note}</small>` : ""}</td>
        <td>${esc(d.why)}</td><td><span class="cp-chip ${chip}">${esc(word(d.status))}</span>${d.status === "unusable" && (item("document", d.document) || {}).reason ? `<br><small class="cp-muted">${esc(clip(item("document", d.document).reason, 160))}</small>` : ""}${d.partial ? `<br><small class="cp-muted">${T(`${d.partial.files.length || 1} already in the file; the rest is asked`, `${d.partial.files.length || 1} liegt/liegen vor; der Rest wird angefordert`)}</small>` : ""}${["missing", "unusable"].includes(d.status) && d.required !== "suggested" ? `<br><button class="cp-link" data-point-notneeded="${esc(d.document)}">${T("not needed", "nicht nötig")}</button>` : ""}</td>
        <td>${(row.citations || []).map((c) => `<button class="cp-link" data-cite-file="${esc(c.file)}" data-page="${c.page || ""}">“${esc(c.quote)}”</button>`).join("<br>") || "—"}</td><td class="cp-muted">${esc(origin(d.document))}</td></tr>`;
    }).join("")}</tbody></table>`;
}

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
  const draft = r.reply && r.reply.clauses && r.reply.clauses.length && S.data.run ? `<a class="cp-button" href="/api/runs/${esc((S.data.lastCompleted || S.data.run).id)}/draft.docx">${T("Draft as .docx", "Entwurf als .docx")}</a>` : "";
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
    ${(r.open_points || []).length ? `<h2 class="cp-section">${T("Open points", "Offene Punkte")}</h2><ul>${r.open_points.map((p, i) => `<li>${esc(p)}${rate(`open_point:${i}`)}</li>`).join("")}</ul>` : ""}
    ${learning}
    <h2 class="cp-section">${T("Short assessment (draft)", "Kurzeinschätzung (Entwurf)")}</h2><p class="cp-answer">${esc(r.answer)}${rate("answer")}</p><p>${esc(r.summary)}</p>
    ${r.reply && r.reply.needed ? `<h2 class="cp-section">${T("Reply draft", "Antwortentwurf")}</h2><article class="cp-reply"><header><span>${esc(r.reply.subject)}</span><span>${esc(T("AI-generated draft", "KI-generierter Entwurf"))}</span></header>
      <div class="clauses">${r.reply.clauses.map((c, i) => `<div class="clause ${c.supported ? "" : "unsupported"}"><p>${esc(c.text)}${rate(`reply:${i}`)}</p>
        <small class="cp-muted">${c.supported ? (c.kind === "formal" ? "" : (c.kind === "request" ? T("Asks for: ", "Fragt nach: ") : T("Rests on: ", "Beruht auf: ")) + c.basis.map((b) => esc(b.startsWith("fact:") ? questionOf(b.slice(5)) : needOf(b.slice(9)))).join("; "))
          : T("Not supported by an accepted finding: review before use", "Durch keine bestätigte Feststellung gestützt: vor Verwendung prüfen")}</small></div>`).join("")}</div>
      <footer>${icon("shield")}${T("Draft · not sent — a person decides", "Entwurf · nicht versendet – ein Mensch entscheidet")}</footer></article><p>${draft}</p>` : ""}
    <h2 class="cp-section">${T("Work log", "Arbeitsprotokoll")}</h2>${workLog()}`;
}

// ---------- Übersicht: the case in thirty seconds, and what needs a person ----------
const DEADLINES_RELIABLE = false;  // until the claim reader lists deadlines with their quotes (verified on real dossiers)
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
function chatFacts(ev) {
  return [...chatOnly()].filter((id) => { const r = recorded("fact")[id]; return !r || r.status === "unknown"; });
}
const statement = (text) => (/\?\s*$/.test(text) ? T(`open question: ${text}`, `offene Frage: ${text}`) : text);
const redacted = (name) => !String(name || "").replace(/[\s.,\-–_[\]()]|geschwärzt|geschw-rzt|xxx/gi, "").length;
function seededNote(item) {
  if (!item || !item.origin || item.origin.by !== "build") return "";
  const e = (item.evidence || [])[0];
  return T(`activated for the pilot · from Protekta’s first request letters${e ? `: ${e.text}` : ""}`,
           `für den Pilot aktiviert · aus Protektas ersten Unterlagenanforderungen${e ? `: ${e.text}` : ""}`);
}
const item = (kind, key) => (S.data.items || []).find((i) => i.kind === kind && i.key === key);  // the server's one item list
function askNow(ev) {
  if (S.data.items) {
    const ask = (d) => (item("document", d.document) || {}).ask;
    return { now: ev.documents.filter((d) => ask(d) === "now"), later: ev.documents.filter((d) => ask(d) === "later") };
  }
  if (ev.outcome) return { now: [], later: [] };  // a process at its end sends no first request
  // The first request asks for what every path needs and what practice asks for; a builder's case-specific
  // conditional need waits until its condition is settled.
  const docs = S.data.process.documents || [];
  const fromEdit = (id) => { const d = docs.find((x) => x.id === id) || {}; return Boolean(d.edit) && !d.knowledge; };
  const now = ev.documents.filter((d) => d.required === "yes" || (d.required === "depends" && !fromEdit(d.document)));
  const later = ev.documents.filter((d) => d.required === "depends" && fromEdit(d.document));
  return { now, later };
}
function draftFor(ev) {
  // The letter the prepared action needs, in the form Protekta's handlers use (from the development dossiers).
  const act = item("next_action", "0");
  const kind = act && act.action;
  if (!kind || kind === "A1" || kind === "request") return requestDraft(ev);
  const due = (S.data.follow_up || {}).due;
  const by = due ? dateText(due) : "…";
  const ref = (String(S.data.case.title || "") + " " + JSON.stringify(S.data.case.intake || {})).match(/\d{4}\.\d{4}\.\d{4}/);
  const head = [...(ref ? [`Unsere Referenz: ${ref[0]}`, ""] : []), "Sehr geehrte/r …", ""];
  const tail = ["", "Für Ihre Kenntnisnahme und Bemühungen danken wir Ihnen bestens. Bei Fragen stehen wir Ihnen gerne zur Verfügung.", "", "Freundliche Grüsse"];
  const close = `Ohne Ihre Rückmeldung bis ${by} gehen wir davon aus, dass sich der Fall erledigt hat, und wir Ihr Dossier daher schliessen können.`;
  if (kind === "A6") return [...head, "Vielen Dank für Ihre Nachricht. Wir halten Ihr Dossier vorerst noch pendent und erwarten die angeforderten Unterlagen und Angaben.", "", close, ...tail].join("\n");
  if (kind === "A7") return [...head, "Nachdem bereits einige Zeit seit unserem letzten Kontakt vergangen ist und wir seither nichts mehr von Ihnen gehört haben, erlauben wir uns, uns bei Ihnen zu erkundigen, ob Sie hinsichtlich Ihres Anliegens noch rechtliche Unterstützung benötigen oder ob die Angelegenheit zwischenzeitlich erledigt werden konnte.", "", close, ...tail].join("\n");
  if (kind === "A12") return [...head, (S.data.evaluation && S.data.evaluation.outcome && S.data.evaluation.outcome.id === "mitwirkung")
    ? "Wir haben Sie mehrfach um die für die Prüfung notwendigen Unterlagen gebeten. Da uns diese bis heute nicht vorliegen, stellen wir unsere Leistungen in dieser Angelegenheit ein und schliessen Ihr Dossier."
    : "Wir schliessen Ihr Dossier in dieser Angelegenheit. Sollte sich die Situation ändern, können Sie sich jederzeit wieder an uns wenden.", ...tail].join("\n");
  return "";
}
function requestDraft(ev) {
  const { now, later } = askNow(ev);
  const lineState = (S.data.caseEvents || []).filter((e) => e.kind === "letter.line").reduce((m, e) => { m[e.item_id] = e.included; return m; }, {});
  const keep = (i) => lineState[i.item_id] !== false;
  const ask = now.filter((d) => d.status !== "present" && lineState[`document:${d.document}`] !== false)
    .concat(later.filter((d) => lineState[`document:${d.document}`] === true))
    .concat(ev.documents.filter((d) => (item("document", d.document) || {}).ask === "proposed" && lineState[`document:${d.document}`] === true));
  if (!ask.length) return "";
  const ref = (String(S.data.case.title || "") + " " + JSON.stringify(S.data.case.intake || {})).match(/\d{4}\.\d{4}\.\d{4}/);
  const procDocs = Object.fromEntries((S.data.process.documents || []).map((x) => [x.id, x]));
  const partOf = (id) => ask.find((w) => (procDocs[w.document] || {}).includes && procDocs[w.document].includes.includes(id));
  const parts = (w) => ask.filter((d) => ((procDocs[w.document] || {}).includes || []).includes(d.document));
  const questions = (S.data.items || []).filter((i) => i.kind === "letter_question" && keep(i));
  const hints = (S.data.items || []).filter((i) => i.kind === "hint" && (i.stated_as === "put_to_handler" ? lineState[i.item_id] === true : keep(i)));
  const lines = ask.filter((d) => !partOf(d.document)).map((d) => `– ${d.title}${parts(d).length ? T(`, in particular ${parts(d).map((x) => x.title).join(", ")}`, `, insbesondere ${parts(d).map((x) => x.title).join(", ")}`) : ""}${d.required === "depends" && (d.questions || []).length ? ` (falls ${d.questions.map((q) => q.question.replace(/\?$/, "")).join(" / ")})` : ""}`);
  return [...(ref ? [T(`Our reference: ${ref[0]}`, `Unsere Referenz: ${ref[0]}`), ""] : []), T("Dear …", "Sehr geehrte/r …"), "",
    ref ? T(`Thank you for registering your matter. It is provisionally registered under reference ${ref[0]}; please quote it in every message.`,
            `Vielen Dank für die Anmeldung Ihres Anliegens. Ihr Dossier ist unter der Referenz ${ref[0]} provisorisch registriert; bitte geben Sie diese bei jeder Mitteilung an.`)
        : T("Thank you for registering your matter. It is provisionally registered with us.", "Vielen Dank für die Anmeldung Ihres Anliegens. Ihr Dossier ist bei uns provisorisch registriert."), "",
    T("To check the insurance cover and assess the facts and the law, we need in particular:", "Um die Versicherungsdeckung prüfen und die Sach- und Rechtslage beurteilen zu können, brauchen wir insbesondere noch:"),
    ...lines, T("– any further relevant documents and information.", "– allfällige weitere relevante Unterlagen und Informationen."), "",
    ...(questions.length ? [T("Please also answer the following questions:", "Weiter bitten wir Sie um die Beantwortung folgender Fragen:"), ...questions.map((q) => `– ${q.value}`), ""] : []),
    ...(hints.length ? [T("On the situation you describe, we can already say:", "Betreffend die geschilderte Situation erlauben wir uns bereits folgende Hinweise:"), ...hints.map((h) => `${h.value}${h.legal_basis ? ` (${h.legal_basis})` : ""}`), ""] : []),
    T("Please send copies or scans, not originals. We will then inform you about the next steps and the legal position.",
      "Bitte senden Sie uns Kopien oder Scans, keine Originale. Anschliessend informieren wir Sie über das weitere Vorgehen und die Rechtslage."), "",
    T("Until the cover is confirmed, you remain responsible for keeping any running deadlines.",
      "Bis zur definitiven Deckungsprüfung sind Sie selbst für die Einhaltung allfällig laufender Fristen zuständig."), "",
    T("Kind regards", "Freundliche Grüsse"),
    ...(later.length ? ["", T("(Not in this letter, possibly needed later:", "(Nicht in diesem Schreiben, später evtl. nötig:"), ...later.map((d) => `· ${d.title}`), ")"] : [])].join("\n");
}
function judgementPoints(ev, r) {
  const pts = [];
  const routing = (S.data.run || {}).routing || ((S.data.lastCompleted || {}).routing) || {};
  const other = routing.other_topic;
  if (other) pts.push({ key: "other-topic", urgency: 2, text: T(`Confirm the process: the case also concerns ${other.topic}`, `Prozess bestätigen: auch «${other.topic}»`), cite: (other.citations || [])[0], choose: true });
  if (ev && !ev.documents.length) pts.push({ key: "no-process", urgency: 1, text: T("No documented process gives this case document needs yet. Choose the process that fits.",
      "Für diesen Fall ist noch kein passender Prozess mit Dokumenten hinterlegt. Wählen Sie den Prozess, der passt."), choose: true });
  for (const f of Object.values(recorded("fact"))) {
    if (f.status === "conflicting") pts.push({ key: `conflict.${f.fact}`, fact: f.fact, urgency: 2, text: T(`The files disagree: ${questionOf(f.fact)}`, `Die Akten widersprechen sich: ${questionOf(f.fact)}`), cite: (f.citations || [])[0], tab: "source_checker" });
  }
  for (const w of (ev ? ev.waiting_for : [])) {
    if (!chatOnly().has(w.fact)) pts.push({ key: `path.${w.fact}`, fact: w.fact, urgency: 3, text: T(`Decides the path, no source yet: ${w.question}`, `Entscheidet den Weg, noch ohne Beleg: ${w.question}`), tab: "source_checker" });
  }
  const { now } = ev ? askNow(ev) : { now: [] };
  const toAsk = now.filter((d) => ["missing", "unusable"].includes(d.status));
  if (toAsk.length) pts.push({ key: `request.${toAsk.length}`, urgency: 1, text: T(`Request ${toAsk.length} document(s) from the customer: ${toAsk.map((d) => clip(d.title, 48)).join(" · ")}`,
      `${toAsk.length} Unterlage(n) beim Kunden anfordern: ${toAsk.map((d) => clip(d.title, 48)).join(" · ")}`), request: true, docs: toAsk.map((d) => d.document) });
  const today = new Date();
  for (const d of DEADLINES_RELIABLE ? (r && r.deadlines) || [] : []) {
    const n = Math.round((new Date(d.date) - new Date(today.getFullYear(), today.getMonth(), today.getDate())) / 86400000);
    if (!Number.isNaN(n) && n <= 14) pts.push({ key: `deadline.${d.date}`, urgency: 0, text: T(`Deadline ${dateText(d.date)}: ${d.question}`, `Frist ${dateText(d.date)}: ${d.question}`) });
  }
  for (const f of S.data.files || []) {
    if (((f.extraction || {}).instruction_like || []).length) pts.push({ key: `ai.${f.id}`, urgency: 0, text: T(`${f.name} contains text addressed to an AI`, `${f.name} enthält Text an die KI`) });
    const unread = Object.entries((f.extraction || {}).unread_reasons || {});
    if (unread.length) pts.push({ key: `unread.${f.id}`, urgency: 3, text: T(`${unread.length} page(s) of ${f.name} could not be read (${unread.map(([p, why]) => `p. ${p}: ${why}`).join(", ")})`, `${unread.length} Seite(n) von ${f.name} nicht gelesen (${unread.map(([p, why]) => `S. ${p}: ${why}`).join(", ")})`) });
  }
  for (const d of ev ? ev.documents.filter((x) => x.required === "suggested") : []) {
    const pd = (S.data.process.documents || []).find((x) => x.id === d.document) || {};
    if (pd.knowledge) pts.push({ key: `knowledge.${pd.knowledge}`, urgency: 4, text: T(`Knowledge suggests: ${d.title}`, `Das Wissen schlägt vor: ${d.title}`), knowledge: pd.knowledge });
  }
  const chat = ev ? chatFacts(ev) : [];
  if (chat.length) pts.push({ key: `chat.${chat.length}`, urgency: 5, text: T(`${chat.length} details the customer settles in the chat: ${chat.map(questionOf).join(" · ")}`, `${chat.length} Angaben klärt der Kunde im Chat: ${chat.map(questionOf).join(" · ")}`), info: true });
  return pts.sort((a, b) => a.urgency - b.urgency);
}
const doneRows = () => (S.data.feedback || []).filter((f) => f.target.startsWith("point:") && f.verdict === "done");
function overviewView() {
  const r = result(), ev = S.data.evaluation;
  if (!r) return `<p class="cp-empty">${T("The overview appears once the case is prepared.", "Die Übersicht erscheint, sobald der Fall vorbereitet ist.")}</p>`;
  const brief = r.brief || {};
  const cite = (c) => (c ? ` <button class="cp-source-chip" data-cite-file="${esc(c.file)}" data-page="${c.page || ""}" title="${esc(c.quote)}">${esc(clip(fileName(c.file), 22))}${c.page ? `, ${T("p.", "S.")} ${c.page}` : ""}</button>`
    : ` <span class="cp-source-chip none">${T("no source", "ohne Beleg")}</span>`);
  const factCite = (id) => { const f = recorded("fact")[id]; return f && f.status === "established" ? (f.citations || [])[0] : null; };
  const claimCite = factCite("rechtsgebiet");  // the first timeline event is often unrelated to the claim
  const anliegen = clip(brief.request || r.answer || "", 320);
  const parties = (brief.parties || []).map((p) => `${redacted(p.name) ? `<i>${T("name redacted", "Name geschwärzt")}</i>` : esc(p.name)} <span class="cp-muted">· ${esc(p.role)}</span>`).join("; ");
  const next = ev && ev.beyond ? ev.beyond.find((b) => b.state === "reached") || ev.beyond[0] : null;
  const obtain = ev ? ev.next_actions.filter((a) => a.kind === "obtain").length : 0;
  const why = ev && ev.waiting_for.length ? T(`because it is still open: ${ev.waiting_for[0].question}`, `weil noch offen ist: ${ev.waiting_for[0].question}`)
    : obtain ? T(`because ${obtain} document(s) are still missing`, `weil noch ${obtain} Unterlage(n) fehlen`) : "";
  const curStep = (ev && ev.current) || {};  // a path row: step, title, role
  const label = (id) => statement(stepLabel(id));
  const nowText = !(ev && ev.current) ? "" : CHAT_ROLE.test(curStep.role || "") ? T("waiting for the customer's details (online form)", "wartet auf Angaben der Kundschaft (Online-Formular)") : label(ev.current);
  const stand = !ev ? T("no process yet", "noch kein Prozess")
    : ev.outcome ? `${T("The process has reached its end", "Der Prozess ist abgeschlossen mit")}: <b>${esc(ev.outcome.title || stepLabel(ev.outcome))}</b>.`
    : ev.current ? `${T("Now", "Stand")}: <b>${esc(nowText)}</b>.${next ? ` ${T("Next", "Als Nächstes")}: <b>${esc(label(next))}</b>${why ? `, ${esc(why)}` : ""}.` : why ? ` ${esc(why[0].toUpperCase() + why.slice(1))}.` : ""}` : "—";
  const today = new Date();
  const fristen = !DEADLINES_RELIABLE ? `<span class="cp-muted">${T("not yet read reliably — check the files", "werden noch nicht zuverlässig gelesen – bitte in den Akten prüfen")}</span>` : (r.deadlines || []).length ? r.deadlines.map((d) => { const n = Math.round((new Date(d.date) - new Date(today.getFullYear(), today.getMonth(), today.getDate())) / 86400000);
    return `${dateText(d.date)} <span class="cp-chip ${n < 0 ? "bad" : n <= 14 ? "wait" : ""}">${Number.isNaN(n) ? "" : n < 0 ? T(`expired ${-n} d ago`, `abgelaufen seit ${-n} T.`) : T(`${n} d`, `${n} T.`)}</span> ${esc(d.question)}${cite((d.citations || [])[0])}`; }).join("<br>")
    : T("none established in the files", "in den Akten keine festgestellt");
  const docs = ev ? ev.documents.filter((d) => !["suggested", "optional", "depends"].includes(d.required)) : [];
  const present = docs.filter((d) => d.status === "present").length;
  const open = S.data.items ? S.data.items.filter((i) => i.kind === "document" && i.ask === "now").length  // the same list the letter asks from
    : docs.filter((d) => ["missing", "unusable"].includes(d.status)).length;
  const draft = ev ? draftFor(ev) : "";
  const done = doneRows(), doneKeys = new Set(done.map((f) => f.target.slice(6)));
  const all = judgementPoints(ev, r).filter((p) => !p.request && !String(p.key).startsWith("chat.")), pts = all.filter((p) => !doneKeys.has(p.key));
  const settled = all.filter((p) => doneKeys.has(p.key));
  const shown = S.allPoints ? pts : pts.slice(0, 7);
  const button = (p, i) => [p.request ? `<button class="cp-button primary" data-point-request>${T("Open draft", "Entwurf öffnen")}</button>` : "",
    p.docs ? `<a class="cp-link" href="#/case/${esc(S.route.id)}/document_finder">${T("check list", "Liste prüfen")}</a>` : "",
    p.knowledge ? `<button class="cp-button primary" data-point-adopt="${esc(p.knowledge)}">${T("Adopt", "Übernehmen")}</button><button class="cp-button" data-point-retire="${esc(p.knowledge)}">${T("Not needed", "Nicht nötig")}</button>` : "",
    p.choose && S.workflows ? `<select class="cp-button" data-point-choose aria-label="${T("Choose process", "Prozess wählen")}"><option value="">${T("Choose process…", "Prozess wählen…")}</option>${S.workflows.map((w) => `<option value="${esc(w.id)}">${esc(w.title)}</option>`).join("")}</select>` : "",
    p.fact && (item("fact", p.fact) || {}).values ? (S.pick && S.pick.fact === p.fact
      ? `<span class="cp-reasons"><span class="cp-muted">${T("Why?", "Warum?")}</span> ${Object.entries(REASONS).map(([code, text]) => `<button class="cp-chip" data-reason="${code}">${esc(T(REASONS_EN[code], text))}</button>`).join("")}</span>`
      : item("fact", p.fact).values.map((v) => `<button class="cp-button" data-set-fact="${esc(p.fact)}" data-value="${esc(v)}">${esc(v)}</button>`).join("")) : "",
    p.tab ? `<a class="cp-link" href="#/case/${esc(S.route.id)}/${p.tab}">${T("check", "prüfen")}</a>` : "",
    `<button class="cp-link" data-note="${esc(p.fact ? `fact:${p.fact}` : `point:${p.key}`)}">${T("note", "Anmerkung")}</button>`,
    ratedRun() && !(p.fact && (item("fact", p.fact) || {}).values) ? `<button class="cp-button" data-point-done="${esc(p.key)}">${T("Done", "Erledigt")}</button>` : ""].join("");
  const setByYou = (S.data.edits || []).filter((e) => e.status === "active" && e.op === "set_fact").length;
  const checked = `${Object.values(recorded("fact")).filter((f) => f.status !== "unknown").length} ${T("facts", "Fakten")}${setByYou ? T(` (${setByYou} set by a person)`, ` (${setByYou} von Ihnen gesetzt)`) : ""}, ${ev ? ev.documents.length : 0} ${T("documents", "Dokumente")}, ${(r.deadlines || []).length} ${T("deadlines", "Fristen")}`;
  return `<div class="cp-overview"><div>
    ${preparedView(ev, draft)}
    <section class="cp-card" style="padding:18px 22px;margin-top:18px"><h2 class="cp-section" style="margin-top:0">${T("The case", "Der Fall")}</h2>
      <dl class="cp-doc-head cp-casefacts">
        <dt>${T("Request", "Anliegen")}</dt><dd data-item="summary:0">${esc(anliegen)}${claimCite ? cite(claimCite) : ""}</dd>
        <dt>${T("Parties", "Parteien")}</dt><dd data-item="party:0">${parties || "—"}${factCite("gegenpartei") ? cite(factCite("gegenpartei")) : ""}</dd>
        <dt>${T("Process", "Prozessstand")}</dt><dd data-item="step:${esc((ev && ev.current && ev.current.step) || "")}">${stand} <a class="cp-link" href="#/case/${esc(S.route.id)}/process_builder">${T("open", "öffnen")}</a></dd>
        <dt>${T("Deadlines", "Fristen")}</dt><dd>${fristen}</dd>
        <dt>${T("Documents", "Dokumente")}</dt><dd>${ev ? `<a href="#/case/${esc(S.route.id)}/document_finder">${T(`${present} present · ${open} missing or unusable`, `${present} vorhanden · ${open} fehlen oder unbrauchbar`)}</a>` : `<span class="cp-muted">${T("no checklist without a process", "ohne Prozess keine Checkliste")}</span>`}</dd>
        <dt>${T("Next action", "Nächster Schritt")}</dt><dd data-item="next_action:0">${draft ? `${T("Ask the customer for the documents", "Unterlagen beim Kunden anfordern")} <span class="cp-muted">· ${T("prepared above", "oben vorbereitet")}</span>` : ev && ev.outcome ? esc(T(`Close the case: ${ev.outcome.title}`, `Fall abschliessen: ${ev.outcome.title}`)) : item("next_action", "0") ? esc(T(item("next_action", "0").label.en, item("next_action", "0").label.de)) : ev && ev.next_actions.length ? esc(statement(ev.next_actions[0].text)) : "—"}</dd>
      </dl>
      </section></div>
    <section class="cp-card cp-judgement" style="padding:18px 22px"><h2 class="cp-section" style="margin-top:0">${T("To settle first", "Vorher zu klären")} <span class="cp-muted">· ${pts.length}</span></h2>
      ${pts.length ? `<ol class="cp-points">${shown.map((p, i) => `<li data-item="${esc(p.fact ? `fact:${p.fact}` : p.request ? "next_action:0" : `point:${p.key}`)}"><span>${esc(p.text)}${p.cite ? cite(p.cite) : ""}</span><span class="cp-point-actions">${p.info ? "" : button(p, i)}</span></li>`).join("")}</ol>
        ${pts.length > 7 && !S.allPoints ? `<button class="cp-link" id="all-points">+${pts.length - 7} ${T("more", "weitere")}</button>` : ""}`
        : `<p>${T("Nothing open.", "Nichts offen.")} <span class="cp-muted">${T("Checked", "Geprüft")}: ${checked}.</span></p>`}
      ${settled.length ? `<details class="cp-muted"><summary class="cp-link">${T(`${settled.length} settled`, `${settled.length} erledigt`)}</summary><ul>${settled.map((p) => { const f = done.find((x) => x.target === `point:${p.key}`);
        return `<li>${esc(p.text)} <span>· ${esc(f.by)} · ${dateText(f.at)}</span> ${f.by === S.me ? `<button class="cp-link" data-point-undone="${esc(p.key)}">${T("undo", "rückgängig")}</button>` : ""}</li>`; }).join("")}</ul></details>` : ""}
      ${S.lastEdit ? `<p class="cp-change">${esc(changeLine(S.lastEdit.diff))} <button class="cp-link" id="undo">${T("Undo", "Rückgängig")}</button></p>` : ""}
      ${myChanges()}
      </section>
    ${closeView()}</div>`;
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
  if (!diff) return T("Changed.", "Geändert.");
  const parts = [];
  const steps = Object.fromEntries((S.data.process.steps || []).map((x) => [x.id, x.title]));
  const end = (S.data.evaluation && S.data.evaluation.outcome || {}).title;
  const to = (id) => steps[id] || (end ? T(`end: ${end}`, `Abschluss: ${end}`) : "—");
  if (diff.current_step && diff.current_step.before !== diff.current_step.after) parts.push(`${T("Step", "Schritt")}: ${steps[diff.current_step.before] || "—"} → ${to(diff.current_step.after)}`);
  else if (diff.outcome && diff.outcome.before !== diff.outcome.after) parts.push(diff.outcome.after ? T(`end: ${end || diff.outcome.after}`, `Abschluss: ${end || diff.outcome.after}`) : T("open again", "wieder offen"));
  if (diff.documents_added.length) parts.push(T(`${diff.documents_added.length} document(s) now needed`, `${diff.documents_added.length} Unterlage(n) jetzt nötig`));
  if (diff.documents_removed.length) parts.push(T(`${diff.documents_removed.length} document(s) no longer needed`, `${diff.documents_removed.length} Unterlage(n) nicht mehr nötig`));
  if (diff.documents_changed.length) parts.push(T(`${diff.documents_changed.length} document(s) changed`, `${diff.documents_changed.length} Unterlage(n) geändert`));
  return `${T("Changed", "Geändert")}: ${parts.join("; ") || T("nothing else moved", "sonst nichts verschoben")}.`;
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
function myChanges() {
  // A person's changes to this case stay on the Übersicht after a reload: what, before → after, reason, when, undo.
  const edits = (S.data.edits || []).filter((e) => e.status === "active" && ["set_fact", "remove_document", "add_document", "set_required_when"].includes(e.op));
  if (!edits.length) return "";
  const event = (id) => (S.data.caseEvents || []).find((e) => e.edit_id === id && e.kind !== "item.propagated") || {};
  const what = (e) => e.op === "set_fact" ? questionOf(e.args.fact) : e.op === "remove_document" ? T(`not needed: ${titleOf(e.args.document)}`, `nicht nötig: ${titleOf(e.args.document)}`)
    : e.op === "add_document" ? T(`added: ${e.args.title}`, `hinzugefügt: ${e.args.title}`) : titleOf(e.args.document);
  const change = (e) => { const ev = event(e.id); return e.op === "set_fact" ? ` · ${esc(valueText(ev.before ?? "—"))} → <b>${esc(valueText(ev.after ?? e.args.value))}</b>` : ""; };
  return `<details class="cp-mine" ${S.openMine ? "open" : ""}><summary class="cp-link">${T(`Your changes: ${edits.length}`, `Ihre Änderungen: ${edits.length}`)}</summary><ul>${edits.map((e) =>
    `<li>${esc(clip(what(e), 90))}${change(e)} <span class="cp-muted">· ${esc(e.reason || "")} · ${esc(e.by)} · ${dateText(e.at)}</span> <button class="cp-link" data-undo-edit="${esc(e.id)}">${T("undo", "rückgängig")}</button></li>`).join("")}</ul></details>`;
}
function titleOf(documentId) { const d = (S.data.process.documents || []).find((x) => x.id === documentId); return d ? d.title : documentId; }
function followUpLine() {
  const f = S.data.follow_up;
  if (!f) return "";
  return `${T("Follow-up", "Wiedervorlage")}: <input type="date" id="followup-date" value="${esc(f.due)}" aria-label="${T("Follow-up date", "Wiedervorlage")}">
    <span class="cp-muted">${f.set_by ? T(`set by ${esc(f.set_by)}`, `gesetzt von ${esc(f.set_by)}`) : T("proposed from practice; documents expected by then", "aus der Praxis vorgeschlagen; Unterlagen bis dann erwartet")}</span>`;
}
function preparedView(ev, draft) {
  // The next piece of the handler's work, already done: the letter itself, its list as the checklist, why, and when.
  const act = item("next_action", "0");
  if (!act) return "";
  const docs = (S.data.items || []).filter((i) => i.kind === "document" && i.ask);
  const qs = (S.data.items || []).filter((i) => i.kind === "letter_question" || i.kind === "hint");
  const lines = (S.data.caseEvents || []).filter((e) => e.kind === "letter.line").reduce((m, e) => { m[e.item_id] = e.included; return m; }, {});
  const proposal = (i) => i.ask === "later" || i.ask === "proposed" || (i.kind === "hint" && i.stated_as === "put_to_handler");
  const on = (i) => proposal(i) ? lines[i.item_id] === true : lines[i.item_id] !== false;
  const pd = Object.fromEntries((S.data.process.documents || []).map((d) => [d.id, d]));
  const whyOf = (i) => {  // the short reason at the end of a line: the law, the practice, or the condition
    if (i.legal_basis) return i.legal_basis;
    const d = pd[i.key] || {};
    if (d.knowledge) return T("asked in practice", "in der Praxis verlangt");
    if (i.ask === "proposed") return T("proposed for this case", "für diesen Fall vorgeschlagen");
    if (i.ask === "later") return T("later, if needed", "später, falls nötig");
    if (i.kind === "letter_question") return T("only the customer can say", "nur die Kundschaft weiss es");
    return "";
  };
  const line = (i, text) => `<li class="${on(i) ? "" : "cp-offered"}"><label><input type="checkbox" data-line="${esc(i.item_id)}" ${on(i) ? "checked" : ""}> ${esc(text)}</label>${whyOf(i) ? ` <span class="cp-why">${esc(whyOf(i))}</span>` : ""}</li>`;
  const textOf = (i) => i.kind === "hint" ? `${T("Hint", "Hinweis")}: ${clip(i.value, 140)}` : i.kind === "letter_question" ? `${T("Question", "Frage")}: ${i.value}` : i.label.de;
  const all = docs.concat(qs);
  const missing = docs.filter((d) => d.ask === "now").length;
  const cover = (S.data.evaluation && S.data.evaluation.waiting_for || []).some((w) => w.fact === "deckung");
  const reason = [T("claim received", "Schadenmeldung eingegangen"), missing ? T(`documents incomplete (${missing} missing)`, `Unterlagen unvollständig (${missing} fehlen)`) : "",
    cover ? T("cover open", "Deckung offen") : ""].filter(Boolean).join(", ");
  const stage = (S.data.process.steps || []).find((x) => x.id === (ev && ev.current && ev.current.step)) || {};
  return `<section class="cp-card cp-prepared" style="padding:18px 22px"><h2 class="cp-section" style="margin-top:0">${T("Prepared", "Vorbereitet")}: ${esc(T(act.label.en, act.label.de))}</h2>
    <p class="cp-muted" style="margin:0 0 10px">${T("Because", "Weil")}: ${esc(reason)}.${stage.title ? ` <a class="cp-link" href="#/case/${esc(S.route.id)}/process_builder">${T("Stage", "Stufe")}: ${esc(stage.title)}</a>` : ""}</p>
    ${draft ? `<pre data-item="letter:0" class="cp-reply" contenteditable="true" spellcheck="true" style="white-space:pre-wrap;padding:14px 16px;font:inherit">${esc(S.letterText || draft)}</pre>` : ""}
    ${all.length ? `<p class="cp-muted" style="margin:12px 0 4px">${T("The letter's list: untick what is not needed, tick what an offer should add.", "Liste des Briefs: Nicht Nötiges abwählen, Angebotenes anwählen.")}</p>
      <ul class="cp-checklist">${all.filter(on).map((i) => line(i, textOf(i))).join("")}${all.filter((i) => !on(i)).map((i) => line(i, textOf(i))).join("")}</ul>` : ""}
    ${draft ? `<p><button class="cp-button primary" id="copy-draft">${T("Copy letter", "Brief kopieren")}</button> <span class="cp-muted">${T("Draft · not sent — a person decides", "Entwurf · nicht versendet – ein Mensch entscheidet")}</span></p>` : ""}
    <p class="cp-tools">${followUpLine()}${followUpLine() ? " · " : ""}<button class="cp-link" id="phone-note">${T("Record phone note", "Telefonnotiz erfassen")}</button> · <button class="cp-link" data-note="case:0">${T("Note", "Anmerkung")}</button></p>
  </section>`;
}
function historyView() {
  const words = { "item.corrected": T("corrected", "korrigiert"), "item.dismissed": T("not needed", "nicht nötig"), "item.added": T("added", "ergänzt"),
    "correction.undone": T("undone", "rückgängig"), "note.added": T("note", "Anmerkung"), "letter.copied": T("letter copied", "Brief kopiert"),
    "case.closed": T("closed", "erledigt"), "followup.set": T("follow-up set", "Wiedervorlage gesetzt"), "letter.line": T("letter changed", "Brief geändert"),
    "source.opened": T("source opened", "Quelle geöffnet"), "reveal": T("own answer saved", "eigene Einschätzung gespeichert"), "point.settled": T("settled", "erledigt") };
  const rows = (S.data.caseEvents || []).filter((e) => words[e.kind]).reverse();
  return `<section class="cp-card" style="padding:18px 22px;max-width:900px"><h2 class="cp-section" style="margin-top:0">${T("History", "Verlauf")}</h2>
    ${S.data.governing_version ? `<p class="cp-muted">${T(`Process updated since the case was prepared (${S.data.run_version} → ${S.data.governing_version}).`, `Prozess seit der Vorbereitung aktualisiert (${S.data.run_version} → ${S.data.governing_version}).`)}</p>` : ""}
    ${rows.length ? `<ul>${rows.map((e) => `<li>${dateText(e.at)} · ${esc(e.expert || "")} · <b>${esc(words[e.kind])}</b>${e.item_id ? ` <span class="cp-muted">${esc(e.item_id)}</span>` : ""}${e.text ? ` — ${esc(clip(e.text, 120))}` : ""}</li>`).join("")}</ul>`
      : `<p class="cp-empty">${T("Nothing done on this case yet.", "Noch nichts an diesem Fall erledigt.")}</p>`}</section>`;
}
function closed() { return (S.data.caseEvents || []).filter((e) => e.kind === "case.closed").pop(); }
function closeView() {
  const c = closed();
  return `<section class="cp-card" style="padding:14px 22px;margin-top:18px;grid-column:1 / -1">${c
    ? `<b>${c.form === "erledigt" ? T("Closed", "Erledigt") : T("Closed, with a reservation", "Erledigt, mit Vorbehalt")}</b> <span class="cp-muted">· ${esc(c.expert)} · ${dateText(c.at)}</span>`
    : `<span class="cp-muted">${T("When you are done with this case:", "Wenn Sie mit dem Fall fertig sind:")}</span>
       <button class="cp-button primary" data-close="erledigt">${T("Closed", "Erledigt")}</button>
       <button class="cp-button" data-close="erledigt_mit_vorbehalt">${T("Closed, with a reservation", "Erledigt, mit Vorbehalt")}</button>
       <span class="cp-muted">${T("What you leave unchanged counts as checked.", "Was Sie unverändert lassen, gilt als geprüft.")}</span>`}</section>`;
}
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
function bindOverview() {
  const show = $("#show-draft");
  if (show) show.addEventListener("click", () => { S.showDraft = !S.showDraft; renderCase(); });
  const copy = $("#copy-draft");
  if (copy) copy.addEventListener("click", () => {
    const text = $("pre[data-item='letter:0']").innerText, draft = draftFor(S.data.evaluation);
    if (navigator.clipboard) navigator.clipboard.writeText(text);
    S.letterText = text;
    caseEvent("letter.copied", null, { edited: text.trim() !== draft.trim(), change_ratio: Math.round(100 * Math.abs(text.length - draft.length) / Math.max(1, draft.length)) / 100 });
  });
  for (const b of document.querySelectorAll("[data-line]")) b.addEventListener("change", async () => {
    const reason = b.checked ? "none" : (window.prompt(T("Why? 1 files say otherwise · 2 not in the files · 3 not relevant here · 4 generally so · 5 known from outside · 6 wording",
      "Warum? 1 Akten anders · 2 nicht in den Akten · 3 hier nicht relevant · 4 gilt generell · 5 von ausserhalb bekannt · 6 Formulierung")) || "none").trim().slice(0, 4);
    await caseEvent("letter.line", b.dataset.line, { included: b.checked, reason: /^[1-6]$/.test(reason) ? reason : "none" });
    await loadCase();
  });
  for (const b of document.querySelectorAll("[data-undo-edit]")) b.addEventListener("click", async () => {
    await api(`/api/edits/${b.dataset.undoEdit}/undo`, { method: "POST" }); S.lastEdit = null; S.openMine = true; await loadCase();
  });
  for (const b of document.querySelectorAll("[data-set-fact]")) b.addEventListener("click", () => { S.pick = { fact: b.dataset.setFact, value: b.dataset.value }; renderCase(); });
  for (const b of document.querySelectorAll("[data-reason]")) b.addEventListener("click", async () => {
    const pick = S.pick; S.pick = null;
    S.lastEdit = await api(`/api/cases/${S.route.id}/edits`, { method: "POST", body: JSON.stringify({ op: "set_fact", args: { fact: pick.fact, value: pick.value }, reason: "", reason_code: b.dataset.reason, recheck: false }) });
    await loadCase();
  });
  for (const b of document.querySelectorAll("[data-note]")) b.addEventListener("click", async () => {
    const text = window.prompt(T("Note (stays inside Mobiliar)", "Anmerkung (bleibt in der Mobiliar)"));
    if (text && text.trim()) { await caseEvent("note.added", b.dataset.note === "case:0" ? null : b.dataset.note, { text: text.trim().slice(0, 2000), note_present: true }); S.message = T("Note saved.", "Anmerkung gespeichert."); S.messageOk = true; renderCase(); setTimeout(() => { S.message = null; S.messageOk = false; renderCase(); }, 2500); }
  });
  for (const b of document.querySelectorAll("[data-close]")) b.addEventListener("click", async () => {
    const line = b.dataset.close === "erledigt_mit_vorbehalt" ? window.prompt(T("Reservation (optional)", "Vorbehalt (freiwillig)")) || "" : "";
    await caseEvent("case.closed", null, { form: b.dataset.close, note_present: Boolean(line.trim()), ...(line.trim() ? { text: line.trim().slice(0, 2000) } : {}) });
    await loadCase();
  });
  const phone = $("#phone-note");
  if (phone) phone.addEventListener("click", async () => {
    const who = window.prompt(T("Phone call with (e.g. customer, other side's lawyer)", "Telefon mit (z.B. VN, Gegenanwalt)"), "VN");
    if (!who) return;
    const reached = window.confirm(T("Reached? OK = yes, Cancel = not reached", "Erreicht? OK = ja, Abbrechen = nicht erreicht"));
    const text = reached ? (window.prompt(T("A few lines: what was said or agreed", "Einige Zeilen: was besprochen oder vereinbart wurde")) || "") : "";
    const at = new Date(), stamp = `${at.toISOString().slice(0, 10)} ${at.toTimeString().slice(0, 5)}`;
    const body = `Aktennotiz Telefon ${stamp}\n${reached ? `Telefon mit ${who}` : `Telefonversuch an ${who} – nicht erreicht`}\n${text}\nErfasst von ${S.me}`;
    const form = new FormData();
    form.append("file", new File([body], `Aktennotiz Telefon ${stamp.replace(":", "")}.txt`, { type: "text/plain" }));
    await api(`/api/cases/${S.route.id}/files`, { method: "POST", body: form });
    await caseEvent("note.added", null, { text: `phone: ${reached ? "reached" : "not reached"}`, phone: true, note_present: Boolean(text) });
    await loadCase();
  });
  const fu = $("#followup-date");
  if (fu) fu.addEventListener("change", async () => {
    if (!fu.value) return;
    await caseEvent("followup.set", "followup:0", { date: fu.value, before: (S.data.follow_up || {}).due || null });
    await loadCase();
  });
  const unaided = $("#unaided");
  if (unaided) unaided.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(unaided);
    const answer = { step: form.get("step") || null, documents: form.getAll("doc"), documents_free_text_present: Boolean((form.get("doc_other") || "").trim()),
                     action_kind: form.get("action") || null, action_free_text_present: false };
    // one POST: the server stores the answer, hashes and freezes it, and reveals; a second answer is refused
    await api(`/api/cases/${S.route.id}/own-answer`, { method: "POST", body: JSON.stringify({ step: answer.step, documents: answer.documents,
      documents_other: String(form.get("doc_other") || "").slice(0, 500), action_kind: answer.action_kind }) });
    await loadCase();
  });
  const all = $("#all-points");
  if (all) all.addEventListener("click", () => { S.allPoints = true; renderCase(); });
  for (const b of document.querySelectorAll("[data-point-request]")) b.addEventListener("click", () => { S.showDraft = true; renderCase(); });
  const mark = async (key, verdict) => {
    const response = await api(`/api/runs/${ratedRun()}/feedback`, { method: "PUT", body: JSON.stringify({ target: `point:${key}`, verdict }) });
    S.data.feedback = response.feedback; renderCase();
  };
  for (const b of document.querySelectorAll("[data-point-done]")) b.addEventListener("click", () => mark(b.dataset.pointDone, "done"));
  for (const b of document.querySelectorAll("[data-point-undone]")) b.addEventListener("click", () => mark(b.dataset.pointUndone, null));
  for (const b of document.querySelectorAll("[data-point-notneeded]")) b.addEventListener("click", async () => {
    S.lastEdit = await api(`/api/cases/${S.route.id}/edits`, { method: "POST", body: JSON.stringify({ op: "remove_document", args: { document: b.dataset.pointNotneeded },
      reason: T("not needed in this case (case worker)", "in diesem Fall nicht nötig (Fallbearbeitung)"), use_for_similar: false }) });
    await loadCase();
  });
  for (const [attr, path] of [["pointAdopt", "activate"], ["pointRetire", "retire"]]) {
    for (const b of document.querySelectorAll(`[data-${attr.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}]`)) b.addEventListener("click", async () => {
      await api(`/api/knowledge/${b.dataset[attr]}/${path}`, { method: "POST", body: JSON.stringify({ reason: T("decided in the case overview", "in der Fallübersicht entschieden") }) });
      await loadCase();
    });
  }
  for (const sel of document.querySelectorAll("[data-point-choose]")) sel.addEventListener("change", async () => {
    if (!sel.value) return;
    await api(`/api/cases/${S.route.id}/workflow`, { method: "PUT", body: JSON.stringify({ workflow_id: sel.value }) });
    S.message = T("Process chosen. Prepare the case again to apply it.", "Prozess gewählt. Bereiten Sie den Fall erneut vor, um ihn anzuwenden.");
    await loadCase();
  });
}

// ---------- case page ----------
async function loadCase() {
  const id = S.route.id;
  if (S.loadedCase !== id) { S.overviewSource = false; S.loadedCase = id; }  // an opened source belongs to its case
  const [data, workflows, knowledge] = await Promise.all([api(`/api/cases/${id}`), S.workflows ? null : api("/api/workflows"), api("/api/knowledge")]);
  if (workflows) S.workflows = workflows.workflows;
  S.knowledge = knowledge.knowledge;
  if (data.run && data.run.status !== "completed") {
    const all = await api(`/api/runs/${data.run.id}`);
    S.events = all.events;
  }
  S.data = data;
  try { S.data.caseEvents = (await api(`/api/cases/${id}/events`)).events; } catch (error) { S.data.caseEvents = []; }
  if (data.run && data.run.status === "completed") S.data.lastCompleted = data.run;
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
  if (liveView) {
    main = `${live ? liveSpine(live) : spine()}<div class="cp-live"><div>${await sourceCard(S.file)}${factCards()}</div>${livePanel(live)}</div>`;
  } else if (unaidedPending()) main = `${unaidedView()}<div style="margin-top:22px">${S.file ? `<iframe title="${T("Original file", "Originaldatei")}" src="/api/files/${esc(S.file)}/original" style="width:100%;height:78vh;border:1px solid var(--line)"></iframe>` : ""}</div>`;  // every tab: the original file only
  else if (tab === "claim_reader") main = claimView(await sourceCard(S.file));
  else if (tab === "source_checker") main = `${checkerView()}<div style="margin-top:22px;max-width:760px">${await sourceCard(S.file)}</div>`;
  else if (tab === "document_finder") main = `${documentsView()}<div style="margin-top:22px;max-width:760px">${await sourceCard(S.file)}</div>`;
  else if (tab === "result_checker") main = resultView();
  else if (tab === "history") main = historyView();
  else if (tab === "overview") main = `${overviewView()}${S.overviewSource ? `<div id="overview-source" style="margin-top:22px;max-width:760px">${await sourceCard(S.file)}</div>` : ""}`;
  else main = processView();
  $("#app").innerHTML = `${renderRail()}<main class="cp-main">${main}</main>`;
  keepMotion($("#app"));
  bindRail();
  for (const b of document.querySelectorAll("[data-step]")) b.addEventListener("click", () => { S.step = b.dataset.step; renderCase(); });
  for (const b of document.querySelectorAll("[data-step-file]")) b.addEventListener("click", () => { if (b.dataset.stepFile) { S.file = b.dataset.stepFile; S.follow = !running(); renderCase(); } });
  for (const b of document.querySelectorAll("[data-cite-file]")) b.addEventListener("click", () => {
    const holder = b.closest("[data-item]");
    caseEvent("source.opened", holder && /^[a-z_]+:/.test(holder.dataset.item) ? holder.dataset.item : null, { file_id: b.dataset.citeFile, page: Number(b.dataset.page) || null }).catch(() => {});
  });
  for (const b of document.querySelectorAll("[data-cite-file]")) b.addEventListener("click", async () => { S.file = b.dataset.citeFile; S.page = Number(b.dataset.page) || null; S.overviewSource = tab === "overview"; await renderCase(); const box = $("#overview-source"); if (box) box.scrollIntoView({ block: "start", behavior: "smooth" }); });
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
  if (open) open.addEventListener("click", () => { S.editing = true; renderCase(); });
  const undo = $("#undo");
  if (undo) undo.addEventListener("click", async () => { await api(`/api/edits/${S.lastEdit.edit.id}/undo`, { method: "POST" }); S.lastEdit = null; await loadCase(); });
  bindEdit();
  bindOverview();
  watchExposure(tab);
  const hit = $("#live-hit"), body = hit && hit.closest(".cp-doc-body");
  if (body) {  // centre the quote inside its card at once, so the pointer lands where the quote stays
    const a = hit.getBoundingClientRect(), b = body.getBoundingClientRect();
    body.scrollTop += a.top - b.top - body.clientHeight / 2 + a.height / 2;
  } else if (hit) hit.scrollIntoView({ block: "center" });
  else if (S.page && $(`#page-${S.page}`)) $(`#page-${S.page}`).scrollIntoView({ block: "start" });
  placeAttention(liveView, live);
  const notice = $("#notice");
  const used = ((S.data.provenance || {}).knowledge || []).some((k) => k.applied);
  const flagged = (S.data.files || []).some((f) => ((f.extraction || {}).instruction_like || []).length);
  const messages = [flagged ? T("A document contains text addressed to an AI. CasePath treated it as evidence and did not follow it; check the document.",
                                "Ein Dokument enthält Text, der sich an die KI richtet. CasePath hat ihn als Inhalt behandelt und nicht befolgt; bitte das Dokument prüfen.") : "",
                    used ? T("This case used Knowledge from earlier cases. Qualified review is still required.", "Dieser Fall nutzt Wissen aus früheren Fällen. Eine fachliche Prüfung bleibt nötig.") : ""].filter(Boolean);
  notice.hidden = !messages.length;
  document.body.classList.toggle("with-notice", Boolean(messages.length));
  notice.innerHTML = messages.length ? `${icon("shield")}${messages.join(" ")}` : "";
}

// ---------- knowledge ----------
async function renderKnowledge() {
  const [data, cases] = await Promise.all([api("/api/knowledge"), api("/api/cases")]);
  const titles = Object.fromEntries(cases.cases.map((c) => [c.id, c.title]));
  const byItem = {};
  for (const use of data.uses) (byItem[use.knowledge_id] = byItem[use.knowledge_id] || []).push(use);
  const families = {};
  for (const item of data.knowledge) (families[item.family] = families[item.family] || []).push(item);
  const card = (k) => `<article class="cp-card" style="padding:16px 18px;display:grid;gap:8px;align-content:start">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><span class="cp-chip ${k.status === "active" ? "good" : k.status === "retired" ? "" : "wait"}">${esc(word(k.status))}</span>
        <span class="cp-chip">${esc(word(k.kind))}</span>${k.refines ? "" : `<span class="cp-chip">v${k.version}</span>`}${k.refines ? `<span class="cp-chip wait">${(() => { const t = data.knowledge.find((x) => x.id === k.refines); return t ? T(`refines v${t.version} → v${t.version + 1}`, `verfeinert v${t.version} → v${t.version + 1}`) : T("refinement", "Verfeinerung"); })()}</span>` : ""}
        ${k.review_suggested ? `<span class="cp-chip bad">${T("review suggested: contradicted often", "Prüfung empfohlen: oft widersprochen")}</span>` : ""}</div>
      <b>${esc(k.content.title || k.content.question || k.content.text)}</b>${k.content.why ? `<span class="cp-muted">${esc(k.content.why)}</span>` : ""}
      ${k.applies_when_text ? `<span class="cp-muted">${T("Applies when", "Gilt, wenn")}: ${esc(k.applies_when_text)}</span>` : ""}
      <span>${T(`Used ${k.stats.uses} · confirmed ${k.stats.confirmed} · not found ${k.stats.not_found} · contradicted ${k.stats.contradicted}`,
                `${k.stats.uses}× verwendet · ${k.stats.confirmed}× bestätigt · ${k.stats.not_found}× nicht gefunden · ${k.stats.contradicted}× widersprochen`)}</span>
      ${(k.evidence || []).filter((e) => e.quote).slice(0, 2).map((e) => `<span class="cp-muted">“${esc(e.quote)}” — <a href="#/case/${esc(e.case_id)}/claim_reader">${esc(titles[e.case_id] || T("case", "Fall"))}</a></span>`).join("")}
      ${seededNote(k) ? `<span class="cp-muted">${esc(seededNote(k))}</span>` : `<span class="cp-muted">${k.origin.kind === "case_edit" ? T("Learned from a case worker’s change in", "Gelernt aus einer Änderung in der Fallbearbeitung, im Fall") : T("Learned by the result checker in", "Gelernt vom Ergebnisprüfer im Fall")} <a href="#/case/${esc(k.origin.case_id)}/process_builder">${esc(titles[k.origin.case_id] || T("a case", "–"))}</a></span>`}
      ${(byItem[k.id] || []).length ? `<span>${T("Cases", "Fälle")}: ${(byItem[k.id] || []).map((u) => `<a href="#/case/${esc(u.case_id)}/document_finder">${esc(titles[u.case_id] || u.case_id)}</a> <span class="cp-chip ${u.outcome === "present" ? "good" : u.outcome === "contradicted" ? "bad" : ""}">${esc(word(u.outcome))}</span>`).join(" ")}</span>` : ""}
      <details><summary class="cp-link">${T("History", "Verlauf")}</summary><ul class="cp-log">${k.history.map((h) => `<li><b>v${h.version}</b><span>${esc(h.change)} · ${esc(h.by || "")} · ${dateText(h.at)}</span></li>`).join("")}</ul></details>
      <div class="row" style="display:flex;gap:10px">${k.status !== "active" && k.status !== "retired" ? `<button class="cp-button primary" data-activate="${esc(k.id)}">${k.refines ? T("Apply refinement", "Verfeinerung übernehmen") : T("Activate", "Freigeben")}</button>` : ""}
        ${k.status !== "retired" ? `<button class="cp-button" data-retire="${esc(k.id)}">${T("Retire", "Zurückziehen")}</button>` : ""}</div></article>`;
  const sections = Object.entries(families).map(([family, items]) => `<h2 class="cp-section">${esc(family)} <span class="cp-muted">· ${T(`${items.length} items · ${items.reduce((n, k) => n + k.stats.uses, 0)} uses`, `${items.length} Eintr${items.length === 1 ? "ag" : "äge"} · ${items.reduce((n, k) => n + k.stats.uses, 0)} Verwendung${items.reduce((n, k) => n + k.stats.uses, 0) === 1 ? "" : "en"}`)}</span></h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px;align-items:start">${items.map(card).join("")}</div>`).join("");
  $("#app").innerHTML = `<main class="cp-main"><h1 class="cp-title">${T("Knowledge", "Wissen")}</h1><p class="cp-muted">${T("What CasePath learned from earlier cases and case workers’ changes. Active items shape new cases; candidates are checked as suggestions until a person activates them.",
      "Was CasePath aus früheren Fällen und aus Änderungen der Fallbearbeitung gelernt hat. Freigegebene Einträge prägen neue Fälle; Vorschläge werden nur als Vorschlag geprüft, bis ein Mensch sie freigibt.")}</p>
    ${sections || `<p class="cp-empty">${T("Nothing learned yet. Knowledge appears after cases are prepared or a case worker saves a change for similar cases.", "Noch nichts gelernt. Wissen entsteht, wenn Fälle vorbereitet werden oder eine Änderung für ähnliche Fälle gespeichert wird.")}</p>`}</main>`;
  for (const b of document.querySelectorAll("[data-activate]")) b.addEventListener("click", async () => { await api(`/api/knowledge/${b.dataset.activate}/activate`, { method: "POST", body: JSON.stringify({ reason: T("approved in Knowledge", "im Wissen freigegeben") }) }); renderKnowledge(); });
  for (const b of document.querySelectorAll("[data-retire]")) b.addEventListener("click", async () => { await api(`/api/knowledge/${b.dataset.retire}/retire`, { method: "POST", body: JSON.stringify({ reason: T("retired in Knowledge", "im Wissen zurückgezogen") }) }); renderKnowledge(); });
}

// ---------- routing ----------
async function route() {
  const next = parseRoute();
  if (next.view !== "case" || next.id !== S.route.id) Object.assign(S, { data: null, pages: {}, file: null, step: null, editing: false, lastEdit: null, events: [], follow: true, message: "", shown: new Set(), litKey: null });
  S.route = next;
  renderTop();
  placeAttention(false);
  $("#notice").hidden = true;
  try {
    if (next.view === "case") { if (S.data) await renderCase(); else await loadCase(); }
    else if (next.view === "knowledge") await renderKnowledge();
    else await renderCases();
  } catch (error) {
    $("#app").innerHTML = `<main class="cp-main"><p class="cp-error">${esc(error.message)}</p></main>`;
  }
}

(async () => {
  try { S.me = (await api("/api/me")).user; } catch (error) { S.me = ""; }
  try { S.canUpload = (await api("/api/health")).uploads !== false; } catch (error) { S.canUpload = true; }
  window.addEventListener("hashchange", route);
  route();
})();
