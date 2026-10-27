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
  not_found: "nicht gefunden", confirmed: "bestätigt", active: "aktiv", candidate: "Vorschlag", retired: "zurückgezogen",
  reviewed: "geprüft", draft: "Entwurf", document_need: "Dokument", question: "Frage", note: "Hinweis",
};
const word = (value) => (LANG === "de" && WORDS[value]) || String(value ?? "").replace(/_/g, " ");
const TOOL_DE = { list_files: "listet die Dateien", open_process: "öffnet den Prozess", view_knowledge: "sieht das Wissen durch", evaluate: "wertet den Prozess aus",
                  get_findings: "holt die Feststellungen", record_fact: "hält eine Feststellung fest", record_document: "hält ein Dokument fest", propose_change: "schlägt eine Prozessänderung vor" };

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
            events: [], poll: null, follow: true, knowledge: null, workflows: null, message: "" };

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
  if (parts[0] === "case" && parts[1]) return { view: "case", id: parts[1], tab: parts[2] || "process_builder" };
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
    tabs = AGENTS.map(([id, title, ic]) => `<a class="cp-tab ${working === id ? "working" : ""}" href="#/case/${esc(route.id)}/${id}"
      ${route.tab === id ? 'aria-current="page"' : ""} data-tab="${id}">${icon(ic)}${title}<span class="cp-pulse" aria-hidden="true"></span></a>`).join("");
  } else {
    tabs = [["cases", T("Cases", "Fälle"), "folder"], ["knowledge", T("Knowledge", "Wissen"), "memory"]].map(([id, title, ic]) =>
      `<a class="cp-tab" href="#/${id}" ${route.view === id ? 'aria-current="page"' : ""}>${icon(ic)}${title}</a>`).join("");
  }
  const other = LANG === "de" ? "en" : "de";
  $("#top").innerHTML = `${wordmark}<nav class="cp-tabs" aria-label="${T("Views", "Ansichten")}">${tabs}</nav>
    <div class="cp-top-right">${route.view === "case" ? `<a class="cp-link" href="#/knowledge">${icon("memory")}${T("Knowledge", "Wissen")}</a>` : ""}<span>${esc(S.me || "")}</span>
      <a class="cp-link" href="?lang=${other}${esc(location.hash)}" lang="${other}">${other.toUpperCase()}</a></div>`;
  for (const link of document.querySelectorAll("[data-tab]")) link.addEventListener("click", () => { S.follow = false; });
}

// ---------- cases ----------
async function renderCases() {
  const [cases, workflows] = await Promise.all([api("/api/cases"), api("/api/workflows")]);
  S.workflows = workflows.workflows;
  const titles = Object.fromEntries(S.workflows.map((w) => [w.id, w.title]));
  const rows = cases.cases.map((c) => `<tr><td><a href="#/case/${esc(c.id)}/process_builder">${esc(c.title)}</a>
      ${c.intake && c.intake.synthetic ? ` <span class="cp-chip">${T("synthetic", "synthetisch")}</span>` : ""}</td>
      <td>${esc(titles[c.workflow_id] || c.workflow_id || "—")}</td><td>${c.file_count}</td><td>${statusChip(c.run_status)}</td><td>${dateText(c.updated_at)}</td></tr>`).join("");
  const catalogue = S.workflows.map((w) => `<tr><td>${esc(w.title)}</td><td><span class="cp-chip ${w.status === "reviewed" ? "good" : "wait"}">${esc(word(w.status))}</span></td>
      <td>${T(`${w.steps} steps · ${w.documents} document needs`, `${w.steps} Schritte · ${w.documents} Dokumente`)}</td><td>${w.open_questions ? T(`${w.open_questions} open questions`, `${w.open_questions} offene Fragen`) : "—"}</td>
      <td class="cp-muted">${w.sources.map((s) => esc(s.title)).join("; ")}</td></tr>`).join("");
  $("#app").innerHTML = `<main class="cp-main"><h1 class="cp-title">${T("Cases", "Fälle")}</h1>
    <form class="cp-form" id="new-case"><input name="title" placeholder="${T("New case: a short title", "Neuer Fall: kurzer Titel")}" aria-label="${T("New case title", "Titel des neuen Falls")}" required maxlength="300">
      <button class="cp-button primary">${icon("plus")}${T("Create case", "Fall anlegen")}</button></form>
    ${rows ? `<table class="cp-table"><thead><tr><th>${T("Case", "Fall")}</th><th>${T("Process", "Prozess")}</th><th>${T("Sources", "Quellen")}</th><th>${T("Last run", "Letzte Vorbereitung")}</th><th>${T("Updated", "Geändert")}</th></tr></thead><tbody>${rows}</tbody></table>`
           : `<p class="cp-empty">${T("No cases yet. Create one, then add its documents.", "Noch keine Fälle. Legen Sie einen an und fügen Sie dann seine Dokumente hinzu.")}</p>`}
    <h2 class="cp-section">${T("Processes", "Prozesse")}</h2>
    ${catalogue ? `<table class="cp-table"><thead><tr><th>${T("Process", "Prozess")}</th><th>Status</th><th>${T("Size", "Umfang")}</th><th>${T("Open questions", "Offene Fragen")}</th><th>${T("Sources", "Quellen")}</th></tr></thead><tbody>${catalogue}</tbody></table>`
               : `<p class="cp-empty">${T("No process is in the catalogue yet. Cases will show as unmapped until one is added.", "Noch kein Prozess im Katalog. Fälle bleiben ohne Prozess, bis einer erfasst ist.")}</p>`}</main>`;
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
function facts() { return (S.data.process && S.data.process.facts) || []; }
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

// ---------- rail ----------
function renderRail() {
  const d = S.data, files = d.files || [];
  const rows = files.map((f) => {
    const proof = proofFor(f.id);
    return `<button class="cp-source" data-file="${esc(f.id)}" aria-current="${S.file === f.id}">${fileIcon(f)}
      <span class="cp-source-label">${esc(f.name)}<small>${T("Received", "Eingegangen")} ${dateText(f.created_at)}${f.extraction && f.extraction.pages ? ` · ${f.extraction.pages} ${T("pages", "Seiten")}` : ""}</small>
      ${proof ? `<span class="cp-proof">${icon("tick")}${esc(proof)}</span>` : ""}</span></button>${segmentRows(f)}`;
  }).join("");
  const chooser = !d.case.workflow_id && S.workflows && S.workflows.length
    ? `<label class="cp-status">${T("Process", "Prozess")} <select id="workflow" aria-label="${T("Process for this case", "Prozess für diesen Fall")}"><option value="">${T("Find it from the documents", "Aus den Dokumenten bestimmen")}</option>
        ${S.workflows.map((w) => `<option value="${esc(w.id)}">${esc(w.title)}</option>`).join("")}</select></label>`
    : d.workflow ? `<span class="cp-status">${T("Process", "Prozess")}: ${esc(d.workflow.title)}</span>` : "";
  const run = d.run;
  const status = run ? (running() ? T(`${AGENT_TITLE[activeAgent()] || "Agents"} working…`, `${AGENT_TITLE[activeAgent()] || "Agenten"} arbeitet…`) : run.status === "failed" ? `${T("Failed", "Fehlgeschlagen")}: ${run.error}`
    : run.status === "completed" ? `${T("Prepared", "Vorbereitet am")} ${dateText(run.finished_at)}` : word(run.status)) : T("Not prepared yet", "Noch nicht vorbereitet");
  return `<aside class="cp-rail" aria-label="${T("Sources", "Quellen")}">
    <div class="cp-caseline">${esc(d.case.title)}<small>${esc(d.case.id.slice(-8).toUpperCase())}</small></div>
    <div class="cp-rail-head">${T("Sources", "Quellen")}<span>${files.length}</span><label class="cp-link">${icon("plus")}${T("Add source", "Hinzufügen")}<input type="file" id="upload" multiple hidden></label></div>
    ${rows || `<div class="cp-drop" id="drop">${T("Drop the case documents here", "Falldokumente hierher ziehen")}</div>`}
    ${S.message ? `<p class="cp-error" style="padding:0 27px">${esc(S.message)}</p>` : ""}
    <div class="cp-rail-foot">${chooser}
      <button class="cp-button primary" id="run" ${running() || !files.length ? "disabled" : ""}>${running() ? '<span class="cp-spinner"></span>' : icon("nodes")}${T("Prepare case", "Fall vorbereiten")}</button>
      <span class="cp-status ${run && run.status === "failed" ? "failed" : ""}">${esc(status)}</span>
      ${S.file ? `<a class="cp-button" href="/api/files/${esc(S.file)}/original" target="_blank" rel="noopener">${T("Open full source", "Original öffnen")} ${icon("external")}</a>` : ""}</div>
  </aside>`;
}

function segmentRows(file) {
  const segments = (file.extraction && file.extraction.segments) || [];
  if (!segments.length) return "";
  return `<ol class="cp-segs" aria-label="${T("Documents in", "Dokumente in")} ${esc(file.name)}">${segments.map((s) => `<li><button class="cp-seg" data-file="${esc(file.id)}" data-page="${s.first_page}">
    <span>${esc(s.title || s.kind)}</span><small>${esc([s.kind !== s.title ? s.kind : "", s.date, `${T("p.", "S.")} ${s.first_page}${s.last_page !== s.first_page ? `–${s.last_page}` : ""}`].filter(Boolean).join(" · "))}</small></button></li>`).join("")}</ol>`;
}

function bindRail() {
  for (const button of document.querySelectorAll("[data-file]")) button.addEventListener("click", () => { S.file = button.dataset.file; S.page = Number(button.dataset.page) || null; renderCase(); });
  const upload = $("#upload");
  if (upload) upload.addEventListener("change", () => uploadFiles(upload.files));
  const drop = $("#drop") || $(".cp-rail");
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("over"));
  drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); uploadFiles(e.dataTransfer.files); });
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
  for (let i = S.events.length - 1; i >= 0; i -= 1) if (S.events[i].cite) return S.events[i].cite;
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
  const ranges = cites.filter((c) => c.page === page && c.end <= map.length)
    .map((c) => ({ ...c, a: map[c.start], b: map[c.end - 1] + 1 })).filter((r) => r.a >= from).sort((x, y) => x.a - y.a);
  let out = "", at = from;
  for (const r of ranges) {
    if (r.a < at) continue;
    out += esc(raw.slice(at, r.a)) + `<mark class="cp-hit ${r.live ? "" : "cited"}" ${r.live ? 'id="live-hit"' : ""}>${esc(raw.slice(r.a, r.b))}</mark>`;
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
      <span class="grow">${esc(doc.name)}</span><a class="cp-icon-button" href="/api/files/${esc(fileId)}/original" target="_blank" rel="noopener" aria-label="${T("Open full source", "Original öffnen")}">${icon("external")}</a></div>
    ${head}<div class="cp-doc-body">${body}</div>${readingNote(doc)}</article>`;
}

function readingNote(doc) {
  const read = (doc.pages_transcribed || []).length, unread = (doc.pages_without_text || []).length;
  const parts = [read ? T(`${read} scanned page${read > 1 ? "s" : ""} read from the page image by the model.`, `${read} gescannte Seite${read > 1 ? "n" : ""} vom Modell aus dem Seitenbild gelesen.`) : "",
                 unread ? T(`${unread} page${unread > 1 ? "s" : ""} not read.`, `${unread} Seite${unread > 1 ? "n" : ""} nicht gelesen.`) : ""].filter(Boolean);
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
    "agent.start": () => `${T("started", "beginnt")}: ${e.instruction || ""}`, "agent.end": () => e.summary || T("done", "fertig"),
    "delegate": () => `${T("asks", "beauftragt")} ${AGENT_TITLE[e.to] || e.to}: ${e.instruction || ""}`,
    "fact.located": () => T(`found ${e.quotes} exact quote(s) for “${questionOf(e.fact)}”`, `${e.quotes} wörtliche Stelle(n) gefunden zu «${questionOf(e.fact)}»`),
    "fact.accepted": () => T(`supports “${questionOf(e.fact)}”`, `bestätigt «${questionOf(e.fact)}»`),
    "fact.rejected": () => `${T(`does not accept “${questionOf(e.fact)}”`, `bestätigt «${questionOf(e.fact)}» nicht`)}${e.reason ? `: ${e.reason}` : ""}`,
    "document.recorded": () => `${needOf(e.document)}: ${word(e.status)}`, "document.accepted": () => `${T("confirms", "bestätigt")} ${needOf(e.document)}`,
    "document.rejected": () => T(`does not accept ${needOf(e.document)}`, `bestätigt ${needOf(e.document)} nicht`), "process.changed": () => `${T("changed the process", "passt den Prozess an")} (${e.op})`,
    "reading.scanned": () => T(`reads ${e.pages} scanned page(s) of ${fileName(e.file)}`, `liest ${e.pages} gescannte Seite(n) von ${fileName(e.file)}`),
    "reading.progress": () => T(`${e.done} of ${e.of} pages read`, `${e.done} von ${e.of} Seiten gelesen`),
    "reading.segmented": () => T(`found ${e.documents} documents in ${fileName(e.file)}`, `${e.documents} Dokumente in ${fileName(e.file)} erkannt`),
    "tool": () => e.tool === "read_file" ? `${T("reads", "liest")} ${fileName(e.file)}` : e.tool === "search" ? `${T("searches", "sucht")} «${e.query}»`
      : (LANG === "de" && TOOL_DE[e.tool]) || e.tool.replace(/_/g, " "),
  }[e.kind];
  return what ? what() : e.kind;
}
const valueText = (v) => (v === true ? T("yes", "ja") : v === false ? T("no", "nein") : String(v));
const learnAction = (a) => ({ new: T("new", "neu"), refine: T("refine", "verfeinern"), contradict: T("contradict", "widerspricht") }[a] || a);
const questionOf = (id) => { const f = facts().find((x) => x.id === id); return f ? questionLabel(f) : id; };
const needOf = (id) => { const d = ((S.data.process || {}).documents || []).find((x) => x.id === id); return d ? d.title : id; };

function livePanel() {
  const agent = activeAgent() || "lead";
  const mine = S.events.filter((e) => e.agent === agent && e.kind !== "agent.start").slice(-4);
  const target = S.events.slice().reverse().find((e) => e.agent === agent && (e.target || e.fact || e.document));
  const asked = S.events.slice().reverse().find((e) => e.kind === "delegate" && e.to === agent);
  const title = target ? (target.fact || (target.target && facts().some((f) => f.id === target.target)) ? questionOf(target.fact || target.target) : needOf(target.document || target.target))
    : asked ? asked.instruction.replace(/\.$/, "") : AGENT_TITLE[agent];
  const rows = mine.map((e, i) => `<li class="${i === mine.length - 1 ? "active" : ""}">${i === mine.length - 1 ? '<span class="cp-spinner"></span>' : icon("check")}${esc(describe(e))}</li>`).join("")
    || `<li class="active"><span class="cp-spinner"></span>${T("Starting", "Beginnt")}</li>`;
  return `<aside><section class="cp-card cp-plan"><h3>${T(`Building “${esc(title)}”`, `In Arbeit: «${esc(title)}»`)}</h3><ol>${rows}</ol></section>
    <div class="cp-agent-chip"><span class="cp-hex">${icon(AGENT_ICON[agent])}</span>${esc(AGENT_TITLE[agent])}</div>
    <details style="margin-top:14px"><summary class="cp-link">${T("Work log", "Arbeitsprotokoll")}</summary>${workLog()}</details></aside>`;
}

function factCards() {
  const cite = liveCite();
  if (!cite) return "";
  const event = S.events.slice().reverse().find((e) => e.cite);
  return `<div class="cp-facts">${["file", "claim"].map((k, i) => k === "file"
      ? `<div class="cp-fact">${icon("doc")}<span>${esc(fileName(cite.file))}${cite.page ? `, ${T("page", "Seite")} ${cite.page}` : ""}</span></div>`
      : `<span>+</span><div class="cp-fact">${icon(event && event.fact ? "check" : "folder")}<span>${esc(event && event.fact ? questionOf(event.fact) : needOf(event && event.document))}</span></div>`).join("")}</div>`;
}

function workLog() {
  const events = running() ? S.events : ((result() || {}).events || []);
  return `<ul class="cp-log">${events.map((e) => `<li><b>${esc(AGENT_TITLE[e.agent] || e.agent)}</b><span>${esc(describe(e))}</span></li>`).join("")}</ul>`;
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
      <b>${i + 1}</b>${esc(n.step.title)}${originLabel(n.step)}</button>`;
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
  const missing = ev.documents.filter((d) => d.status === "missing" && !["suggested", "optional"].includes(d.required));
  const knowledge = ((S.data.provenance || {}).knowledge || []).filter((k) => k.applied);
  const sources = (S.data.process.sources || []).filter((s) => !["knowledge", "edit"].includes(s.id));
  const list = (items, empty) => items.length ? `<ul>${items.join("")}</ul>` : `<span class="cp-muted">${empty}</span>`;
  return `<div class="cp-chain">
    <section><h4>${icon("doc")}${T("Source facts", "Belegte Fakten")}</h4>${list(accepted.map((f) => `<li><span class="ok">${icon("check")}</span>${esc(questionOf(f.fact))}: ${esc(valueText(f.value))}</li>`), T("None accepted yet", "Noch keine bestätigt"))}</section>
    <section><h4>${icon("law")}${T("Basis", "Grundlage")}</h4>${list(sources.map((s) => `<li>${esc(s.title)}</li>`), "—")}</section>
    <section><h4>${icon("evidence")}${T("Current evidence", "Vorhandene Belege")}</h4>${list(present.map((d) => `<li>${esc(d.title)}</li>`), T("None found yet", "Noch keine gefunden"))}</section>
    <section><h4>${icon("doc")}${T("Evidence still needed", "Noch benötigte Belege")}</h4>${list(missing.map((d) => `<li>${esc(d.title)}</li>`), T("Nothing missing", "Nichts fehlt"))}</section>
    <section><h4>${icon("memory")}${T("From earlier cases", "Aus früheren Fällen")}</h4>${list(knowledge.map((k) => `<li>${esc(needOf(k.document) || k.note || k.item)}</li>`), T("No Knowledge applied", "Kein Wissen angewendet"))}</section>
    <a class="cp-missing-box" href="#/case/${esc(S.route.id)}/document_finder">${icon("folder", "big")}<span>${T("Documents", "Dokumente")}<br><b>${T(`${missing.length} missing`, `${missing.length} fehlen`)}</b></span>${icon("right")}</a></div>`;
}

function preview() {
  const r = result() || {};
  const timeline = (r.brief && r.brief.timeline) || [];
  if (!timeline.length) return "";
  return `<section class="cp-preview"><div class="cp-lines">${timeline.map((t, i) => `<div class="${i === timeline.length - 1 ? "cited" : ""}"><time>${esc(t.date)}</time><span>${esc(t.event)}</span></div>`).join("")}</div>
    <div class="cp-page">${timeline.map((t) => esc((t.citations[0] || {}).quote || "")).join("\n\n")}</div></section>`;
}

const OPS = [["add_document", T("Add a document need", "Dokument verlangen")], ["set_required_when", T("Change when a document is required", "Ändern, wann ein Dokument nötig ist")],
             ["add_question", T("Add a question", "Frage ergänzen")], ["set_transition", T("Redirect a branch", "Verzweigung umleiten")], ["rename_step", T("Rename this step", "Schritt umbenennen")]];

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
  if (op === "set_transition") { const step = process.steps.find((s) => s.id === args.step); const e = step.next[args.index]; return `${e.label || T("Next", "Weiter")} → ${process.steps.find((s) => s.id === e.to).title}`; }
  if (op === "rename_step") return process.steps.find((s) => s.id === args.step).title;
  return "";
}
function nowText(edit) {
  const a = edit.args;
  return { add_document: `${a.title}: ${a.why}`, set_required_when: `${needOf(a.document)}: ${conditionText(a.required_when)}`,
           add_question: a.question, set_transition: `→ ${(S.data.process.steps.find((s) => s.id === a.to) || {}).title}`, rename_step: a.title }[edit.op];
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
      <div class="arrow">→</div><div class="card"><h4>${T("Knowledge", "Wissen")} v${item.version} ${icon("shield")}</h4><p><b>${esc(item.content.title || item.content.question || item.content.text)}</b></p>
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
      ${(brief.timeline || []).length ? `<h2 class="cp-section">${T("Timeline", "Chronologie")}</h2><div class="cp-lines">${brief.timeline.map((t) => {
        const c = (t.citations || [])[0];
        return `<div><time>${esc(t.date)}</time><span>${c ? `<button class="cp-link" data-cite-file="${esc(c.file)}" data-page="${c.page || ""}" title="${esc(c.quote)}">${esc(t.event)}</button>` : esc(t.event)}</span></div>`;
      }).join("")}</div>` : ""}
    </section>` : `<p class="cp-empty">${T("The claim reader’s brief appears here after the case is prepared.", "Die Übersicht des Falllesers erscheint hier, sobald der Fall vorbereitet ist.")}</p>`}</aside></div>`;
}

function checkerView() {
  const rows = Object.values(recorded("fact")).map((f) => [questionOf(f.fact), f]).concat(Object.values(recorded("document")).map((d) => [needOf(d.document), d]));
  if (!rows.length) return `<p class="cp-empty">${T("The source checker’s verdicts appear here: every finding with the exact sentence it rests on.", "Hier erscheinen die Prüfergebnisse des Quellenprüfers: jede Feststellung mit dem genauen Satz, auf dem sie beruht.")}</p>`;
  return `<table class="cp-table"><thead><tr><th>${T("Finding", "Feststellung")}</th><th>${T("Verdict", "Prüfung")}</th><th>${T("Exact sentence", "Wörtliche Stelle")}</th></tr></thead><tbody>${rows.map(([label, row]) => `<tr>
    <td>${esc(label)}${row.value !== undefined && row.value !== null ? `: <b>${esc(valueText(row.value))}</b>` : row.status ? ` <span class="cp-muted">(${esc(word(row.status))})</span>` : ""}</td>
    <td>${row.verdict === "accepted" ? `<span class="cp-chip good">${T("supported", "belegt")}</span>` : row.verdict === "rejected" ? `<span class="cp-chip bad">${T("not supported", "nicht belegt")}</span><br><small class="cp-muted">${esc(row.verdict_reason || "")}</small>` : `<span class="cp-chip wait">${T("not checked", "nicht geprüft")}</span>`}</td>
    <td>${(row.citations || []).map((c) => `<button class="cp-link" data-cite-file="${esc(c.file)}" data-page="${c.page || ""}">“${esc(c.quote)}”</button><br><small class="cp-muted">${esc(fileName(c.file))}${c.page ? `, ${T("page", "Seite")} ${c.page}` : ""}</small>`).join("<br>") || '<span class="cp-muted">—</span>'}</td></tr>`).join("")}</tbody></table>`;
}

function documentsView() {
  const ev = S.data.evaluation;
  if (!ev) return `<p class="cp-empty">${T("The document checklist appears once the case has a process.", "Die Dokumenten-Checkliste erscheint, sobald der Fall einen Prozess hat.")}</p>`;
  const rows = recorded("document");
  const origin = (id) => { const d = S.data.process.documents.find((x) => x.id === id) || {}; return d.knowledge ? T("From Knowledge", "Aus dem Wissen") : d.edit ? T("Added for this case", "Für diesen Fall ergänzt") : T("From the process", "Aus dem Prozess"); };
  const missing = ev.documents.filter((d) => d.status === "missing" && !["suggested", "optional"].includes(d.required)).length;
  return `<h1 class="cp-title">${T("Documents", "Dokumente")} <span class="cp-muted">· ${T(`${missing} missing`, `${missing} fehlen`)}</span></h1>
    <table class="cp-table"><thead><tr><th>${T("Document", "Dokument")}</th><th>${T("Why", "Wozu")}</th><th>Status</th><th>${T("Proof", "Beleg")}</th><th>${T("Origin", "Herkunft")}</th></tr></thead><tbody>${ev.documents.map((d) => {
      const row = rows[d.document] || {};
      const chip = d.status === "present" ? "good" : d.status === "missing" || d.status === "unusable" ? (["suggested", "optional"].includes(d.required) ? "wait" : "bad") : "wait";
      const note = { depends: T("depends on an open answer", "hängt von einer offenen Antwort ab"), suggested: T("suggested by Knowledge", "vom Wissen vorgeschlagen"), optional: T("optional", "freiwillig") }[d.required];
      return `<tr><td><b>${esc(d.title)}</b>${note ? `<br><small class="cp-muted">${note}</small>` : ""}</td>
        <td>${esc(d.why)}</td><td><span class="cp-chip ${chip}">${esc(word(d.status))}</span></td>
        <td>${(row.citations || []).map((c) => `<button class="cp-link" data-cite-file="${esc(c.file)}" data-page="${c.page || ""}">“${esc(c.quote)}”</button>`).join("<br>") || "—"}</td><td class="cp-muted">${esc(origin(d.document))}</td></tr>`;
    }).join("")}</tbody></table>`;
}

function resultView() {
  const r = result();
  if (!r || !r.answer) return `<p class="cp-empty">${T("The result checker’s answer, open points and reply draft appear here after the case is prepared.", "Antwort, offene Punkte und Antwortentwurf des Ergebnisprüfers erscheinen hier, sobald der Fall vorbereitet ist.")}</p>`;
  const ev = S.data.evaluation;
  const today = new Date();
  const days = (iso) => Math.round((new Date(iso) - new Date(today.getFullYear(), today.getMonth(), today.getDate())) / 86400000);
  const left = (n) => (n < 0 ? T(`expired ${-n} days ago`, `abgelaufen seit ${-n} Tagen`) : n === 0 ? T("today", "heute") : T(`in ${n} days`, `in ${n} Tagen`));
  const deadlines = (r.deadlines || []).map((d) => { const n = days(d.date); return `<li><b>${dateText(d.date)}</b> · ${esc(d.question)} <span class="cp-chip ${n < 0 ? "bad" : n <= 14 ? "wait" : ""}">${Number.isNaN(n) ? "" : left(n)}</span></li>`; }).join("");
  const summary = (r.case_summary || []).length ? `<section class="cp-card" style="padding:16px 20px;max-width:900px;margin-bottom:18px"><h2 class="cp-section" style="margin-top:0">${T("Case summary", "Fallzusammenfassung")}</h2>
      <dl class="cp-doc-head" style="padding:0;border:0;grid-template-columns:180px 1fr">${r.case_summary.map((f) => `<dt>${esc(f.label)}</dt><dd>${esc(f.text)}</dd>`).join("")}</dl></section>` : "";
  const draft = r.reply && r.reply.clauses && r.reply.clauses.length && S.data.run ? `<a class="cp-button" href="/api/runs/${esc((S.data.lastCompleted || S.data.run).id)}/draft.docx">${T("Draft as .docx", "Entwurf als .docx")}</a>` : "";
  const action = { answer: T("Answer: ", "Klären: "), resolve: T("Not met: ", "Nicht erfüllt: "), obtain: T("Obtain: ", "Einholen: ") };
  return `${summary}${deadlines ? `<h2 class="cp-section" style="margin-top:0">${T("Deadlines", "Fristen")}</h2><ul>${deadlines}</ul>` : ""}
    <h1 class="cp-title">${T("Answer", "Antwort")}</h1><p class="cp-answer">${esc(r.answer)}</p><p>${esc(r.summary)}</p>
    ${ev && ev.current ? `<p class="cp-muted">${T("Current step", "Aktueller Schritt")}: <b>${esc(ev.current.title)}</b>${ev.waiting_for.length ? ` · ${T("waiting for", "wartet auf")}: ${ev.waiting_for.map((w) => esc(w.question)).join("; ")}` : ""}</p>` : ""}
    ${ev && ev.outcome ? `<p class="cp-muted">${T("Outcome in the process", "Ergebnis im Prozess")}: <b>${esc(ev.outcome.title)}</b></p>` : ""}
    ${ev && ev.next_actions.length ? `<h2 class="cp-section">${T("Next steps", "Nächste Schritte")}</h2><ul>${ev.next_actions.map((a) => `<li>${esc(action[a.kind])}${esc(a.text)}${a.kind === "resolve" ? ` <span class="cp-muted">(${esc(valueText(a.value))})</span>` : ""}</li>`).join("")}</ul>` : ""}
    ${(r.open_points || []).length ? `<h2 class="cp-section">${T("Open points", "Offene Punkte")}</h2><ul>${r.open_points.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>` : ""}
    ${r.reply && r.reply.needed ? `<h2 class="cp-section">${T("Reply draft", "Antwortentwurf")}</h2><article class="cp-reply"><header><span>${esc(r.reply.subject)}</span><span>${esc(T("AI-generated draft", "KI-generierter Entwurf"))}</span></header>
      <div class="clauses">${r.reply.clauses.map((c) => `<div class="clause ${c.supported ? "" : "unsupported"}"><p>${esc(c.text)}</p>
        <small class="cp-muted">${c.supported ? T("Rests on: ", "Beruht auf: ") + c.basis.map((b) => esc(b.startsWith("fact:") ? questionOf(b.slice(5)) : needOf(b.slice(9)))).join("; ")
          : T("Not supported by an accepted finding: review before use", "Durch keine bestätigte Feststellung gestützt: vor Verwendung prüfen")}</small></div>`).join("")}</div>
      <footer>${icon("shield")}${T("Draft · not sent — a person decides", "Entwurf · nicht versendet – ein Mensch entscheidet")}</footer></article><p>${draft}</p>` : ""}
    ${(r.learning || []).length ? `<h2 class="cp-section">${T("What CasePath proposes to learn", "Was CasePath lernen möchte")}</h2><ul>${r.learning.map((l) => `<li><b>${esc(learnAction(l.action))}</b> · ${esc(l.title || l.question || l.note)} <span class="cp-muted">— ${esc(l.reason)}</span></li>`).join("")}</ul>
      <p><a href="#/knowledge">${T("Review in Knowledge", "Im Wissen prüfen")}</a></p>` : ""}
    <h2 class="cp-section">${T("Work log", "Arbeitsprotokoll")}</h2>${workLog()}`;
}

// ---------- case page ----------
async function loadCase() {
  const id = S.route.id;
  const [data, workflows, knowledge] = await Promise.all([api(`/api/cases/${id}`), S.workflows ? null : api("/api/workflows"), api("/api/knowledge")]);
  if (workflows) S.workflows = workflows.workflows;
  S.knowledge = knowledge.knowledge;
  if (data.run && data.run.status !== "completed") {
    const all = await api(`/api/runs/${data.run.id}`);
    S.events = all.events;
  }
  S.data = data;
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
    S.events = S.events.concat(run.events);
    S.data.run.status = run.status;
    if (!["queued", "running"].includes(run.status)) { S.events = []; S.pages = {}; await loadCase(); return; }
    const agent = activeAgent();
    if (S.follow && agent && agent !== "lead" && S.route.tab !== agent) {
      // Follow the working agent without a navigation, so this poll keeps running.
      S.route.tab = agent;
      history.replaceState(null, "", `#/case/${S.route.id}/${agent}`);
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
  if (running() && (tab === activeAgent() || tab === "process_builder")) {
    main = `${spine()}<div class="cp-live"><div>${await sourceCard(S.file)}${factCards()}</div>${livePanel()}</div>`;
  } else if (tab === "claim_reader") main = claimView(await sourceCard(S.file));
  else if (tab === "source_checker") main = `${checkerView()}<div style="margin-top:22px;max-width:760px">${await sourceCard(S.file)}</div>`;
  else if (tab === "document_finder") main = `${documentsView()}<div style="margin-top:22px;max-width:760px">${await sourceCard(S.file)}</div>`;
  else if (tab === "result_checker") main = resultView();
  else main = processView();
  $("#app").innerHTML = `${renderRail()}<main class="cp-main">${main}</main>`;
  bindRail();
  for (const b of document.querySelectorAll("[data-step]")) b.addEventListener("click", () => { S.step = b.dataset.step; renderCase(); });
  for (const b of document.querySelectorAll("[data-step-file]")) b.addEventListener("click", () => { if (b.dataset.stepFile) { S.file = b.dataset.stepFile; renderCase(); } });
  for (const b of document.querySelectorAll("[data-cite-file]")) b.addEventListener("click", () => { S.file = b.dataset.citeFile; S.page = Number(b.dataset.page) || null; renderCase(); });
  const open = $("#edit-open");
  if (open) open.addEventListener("click", () => { S.editing = true; renderCase(); });
  const undo = $("#undo");
  if (undo) undo.addEventListener("click", async () => { await api(`/api/edits/${S.lastEdit.edit.id}/undo`, { method: "POST" }); S.lastEdit = null; await loadCase(); });
  bindEdit();
  const hit = $("#live-hit");
  if (hit) hit.scrollIntoView({ block: "center", behavior: "smooth" });
  else if (S.page && $(`#page-${S.page}`)) $(`#page-${S.page}`).scrollIntoView({ block: "start" });
  const notice = $("#notice");
  const used = ((S.data.provenance || {}).knowledge || []).some((k) => k.applied);
  notice.hidden = !used;
  document.body.classList.toggle("with-notice", used);
  notice.innerHTML = used ? `${icon("shield")}${T("This case used Knowledge from earlier cases. Qualified review is still required.", "Dieser Fall nutzt Wissen aus früheren Fällen. Eine fachliche Prüfung bleibt nötig.")}` : "";
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
        <span class="cp-chip">${esc(word(k.kind))}</span><span class="cp-chip">v${k.version}</span>${k.refines ? `<span class="cp-chip wait">${T("refinement", "Verfeinerung")}</span>` : ""}
        ${k.review_suggested ? `<span class="cp-chip bad">${T("review suggested: contradicted often", "Prüfung empfohlen: oft widersprochen")}</span>` : ""}</div>
      <b>${esc(k.content.title || k.content.question || k.content.text)}</b>${k.content.why ? `<span class="cp-muted">${esc(k.content.why)}</span>` : ""}
      ${k.applies_when_text ? `<span class="cp-muted">${T("Applies when", "Gilt, wenn")}: ${esc(k.applies_when_text)}</span>` : ""}
      <span>${T(`Used ${k.stats.uses} · confirmed ${k.stats.confirmed} · not found ${k.stats.not_found} · contradicted ${k.stats.contradicted}`,
                `${k.stats.uses}× verwendet · ${k.stats.confirmed}× bestätigt · ${k.stats.not_found}× nicht gefunden · ${k.stats.contradicted}× widersprochen`)}</span>
      ${(k.evidence || []).slice(0, 2).map((e) => `<span class="cp-muted">“${esc(e.quote)}” — <a href="#/case/${esc(e.case_id)}/claim_reader">${esc(titles[e.case_id] || T("case", "Fall"))}</a></span>`).join("")}
      <span class="cp-muted">${k.origin.kind === "case_edit" ? T("Learned from a case worker’s change in", "Gelernt aus einer Änderung in der Fallbearbeitung, im Fall") : T("Learned by the result checker in", "Gelernt vom Ergebnisprüfer im Fall")} <a href="#/case/${esc(k.origin.case_id)}/process_builder">${esc(titles[k.origin.case_id] || T("a case", "–"))}</a></span>
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
  if (next.view !== "case" || next.id !== S.route.id) Object.assign(S, { data: null, pages: {}, file: null, step: null, editing: false, lastEdit: null, events: [], follow: true, message: "" });
  S.route = next;
  renderTop();
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
  window.addEventListener("hashchange", route);
  route();
})();
