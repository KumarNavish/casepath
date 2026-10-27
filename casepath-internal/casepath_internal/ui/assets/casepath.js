"use strict";
// CasePath internal workspace: one page on the live API. Everything shown comes from
// the case store, the agents' recorded work and the Knowledge base; nothing is staged.

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
  ["claim_reader", "Claim reader", "doc"], ["source_checker", "Source checker", "shield"],
  ["process_builder", "Process builder", "nodes"], ["document_finder", "Document finder", "folder"],
  ["result_checker", "Result checker", "check"],
];
const AGENT_TITLE = Object.fromEntries(AGENTS.map(([id, title]) => [id, title]).concat([["lead", "Lead"]]));
const AGENT_ICON = Object.fromEntries(AGENTS.map(([id, , i]) => [id, i]).concat([["lead", "nodes"]]));
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (selector, root = document) => root.querySelector(selector);
const S = { me: null, route: {}, data: null, pages: {}, file: null, step: null, editing: false, lastEdit: null,
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
    tabs = [["cases", "Cases", "folder"], ["knowledge", "Knowledge", "memory"]].map(([id, title, ic]) =>
      `<a class="cp-tab" href="#/${id}" ${route.view === id ? 'aria-current="page"' : ""}>${icon(ic)}${title}</a>`).join("");
  }
  $("#top").innerHTML = `${wordmark}<nav class="cp-tabs" aria-label="Views">${tabs}</nav>
    <div class="cp-top-right">${route.view === "case" ? `<a class="cp-link" href="#/knowledge">${icon("memory")}Knowledge</a>` : ""}<span>${esc(S.me || "")}</span></div>`;
  for (const link of document.querySelectorAll("[data-tab]")) link.addEventListener("click", () => { S.follow = false; });
}

// ---------- cases ----------
async function renderCases() {
  const [cases, workflows] = await Promise.all([api("/api/cases"), api("/api/workflows")]);
  S.workflows = workflows.workflows;
  const rows = cases.cases.map((c) => `<tr><td><a href="#/case/${esc(c.id)}/process_builder">${esc(c.title)}</a>
      ${c.intake && c.intake.synthetic ? ' <span class="cp-chip">synthetic</span>' : ""}</td>
      <td>${esc(c.workflow_id || "—")}</td><td>${c.file_count}</td><td>${statusChip(c.run_status)}</td><td>${dateText(c.updated_at)}</td></tr>`).join("");
  const catalogue = S.workflows.map((w) => `<tr><td>${esc(w.title)}</td><td><span class="cp-chip ${w.status === "reviewed" ? "good" : "wait"}">${esc(w.status)}</span></td>
      <td>${w.steps} steps · ${w.documents} document needs</td><td>${w.open_questions ? `${w.open_questions} open questions` : "—"}</td>
      <td class="cp-muted">${w.sources.map((s) => esc(s.title)).join("; ")}</td></tr>`).join("");
  $("#app").innerHTML = `<main class="cp-main"><h1 class="cp-title">Cases</h1>
    <form class="cp-form" id="new-case"><input name="title" placeholder="New case: a short title" aria-label="New case title" required maxlength="300">
      <button class="cp-button primary">${icon("plus")}Create case</button></form>
    ${rows ? `<table class="cp-table"><thead><tr><th>Case</th><th>Process</th><th>Sources</th><th>Last run</th><th>Updated</th></tr></thead><tbody>${rows}</tbody></table>`
           : `<p class="cp-empty">No cases yet. Create one, then add its documents.</p>`}
    <h2 class="cp-section">Processes</h2>
    ${catalogue ? `<table class="cp-table"><thead><tr><th>Process</th><th>Status</th><th>Size</th><th>Open questions</th><th>Sources</th></tr></thead><tbody>${catalogue}</tbody></table>`
               : `<p class="cp-empty">No process is in the catalogue yet. Cases will show as unmapped until one is added.</p>`}</main>`;
  $("#new-case").addEventListener("submit", async (event) => {
    event.preventDefault();
    const title = new FormData(event.target).get("title");
    const created = await api("/api/cases", { method: "POST", body: JSON.stringify({ title }) });
    location.hash = `#/case/${created.id}/claim_reader`;
  });
}

function statusChip(status) {
  if (!status) return '<span class="cp-muted">not run</span>';
  const kind = status === "completed" ? "good" : status === "failed" || status === "interrupted" ? "bad" : "wait";
  return `<span class="cp-chip ${kind}">${esc(status)}</span>`;
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
  if (numbers.length) parts.push(`Proof for question${numbers.length > 1 ? "s" : ""} ${numbers.join(", ")}`);
  if (needs.length) parts.push(`Meets ${needs.length} document need${needs.length > 1 ? "s" : ""}`);
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
      <span class="cp-source-label">${esc(f.name)}<small>Received ${dateText(f.created_at)}${f.extraction && f.extraction.pages ? ` · ${f.extraction.pages} pages` : ""}</small>
      ${proof ? `<span class="cp-proof">${icon("tick")}${esc(proof)}</span>` : ""}</span></button>`;
  }).join("");
  const chooser = !d.case.workflow_id && S.workflows && S.workflows.length
    ? `<label class="cp-status">Process <select id="workflow" aria-label="Process for this case"><option value="">Find it from the documents</option>
        ${S.workflows.map((w) => `<option value="${esc(w.id)}">${esc(w.title)}</option>`).join("")}</select></label>`
    : d.workflow ? `<span class="cp-status">Process: ${esc(d.workflow.title)}</span>` : "";
  const run = d.run;
  const status = run ? (running() ? `${AGENT_TITLE[activeAgent()] || "Agents"} working…` : run.status === "failed" ? `Failed: ${run.error}` : run.status === "completed" ? `Prepared ${dateText(run.finished_at)}` : run.status) : "Not prepared yet";
  return `<aside class="cp-rail" aria-label="Sources">
    <div class="cp-caseline">${esc(d.case.title)}<small>${esc(d.case.id.slice(-8).toUpperCase())}</small></div>
    <div class="cp-rail-head">Sources<span>${files.length}</span><label class="cp-link">${icon("plus")}Add source<input type="file" id="upload" multiple hidden></label></div>
    ${rows || `<div class="cp-drop" id="drop">Drop the case documents here</div>`}
    ${S.message ? `<p class="cp-error" style="padding:0 27px">${esc(S.message)}</p>` : ""}
    <div class="cp-rail-foot">${chooser}
      <button class="cp-button primary" id="run" ${running() || !files.length ? "disabled" : ""}>${running() ? '<span class="cp-spinner"></span>' : icon("nodes")}Prepare case</button>
      <span class="cp-status ${run && run.status === "failed" ? "failed" : ""}">${esc(status)}</span>
      ${S.file ? `<a class="cp-button" href="/api/files/${esc(S.file)}/original" target="_blank" rel="noopener">Open full source ${icon("external")}</a>` : ""}</div>
  </aside>`;
}

function bindRail() {
  for (const button of document.querySelectorAll("[data-file]")) button.addEventListener("click", () => { S.file = button.dataset.file; renderCase(); });
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
  if (!fileId) return `<div class="cp-card cp-empty">Choose a source on the left.</div>`;
  const doc = await pages(fileId);
  const cites = citationsFor(fileId);
  const files = S.data.files.map((f) => f.id), index = files.indexOf(fileId);
  const head = doc.headers ? `<dl class="cp-doc-head">${["From", "To", "Date", "Subject"].filter((k) => doc.headers[k]).map((k) => `<dt>${k}:</dt><dd>${esc(doc.headers[k])}</dd>`).join("")}</dl>` : "";
  // An e-mail's header lines are shown above; its body starts after the first blank line.
  const skip = (p) => (doc.headers && p === doc.pages[0] && p.text.indexOf("\n\n") >= 0 ? p.text.indexOf("\n\n") + 2 : 0);
  const body = doc.pages.length ? doc.pages.map((p) => `${p.page ? `<span class="page">Page ${p.page}</span>` : ""}${highlight(p.text, p.page, cites, skip(p))}`).join("\n")
    : doc.kind === "image" ? `<img alt="${esc(doc.name)}" src="/api/files/${esc(fileId)}/original" style="max-width:100%">` : `<span class="cp-muted">No readable text.</span>`;
  return `<article class="cp-card" aria-label="${esc(doc.name)}"><div class="cp-doc-toolbar">
      <button class="cp-icon-button" data-step-file="${esc(files[index - 1] || "")}" aria-label="Previous source" ${index <= 0 ? "disabled" : ""}>${icon("left")}</button>
      <button class="cp-icon-button" data-step-file="${esc(files[index + 1] || "")}" aria-label="Next source" ${index >= files.length - 1 ? "disabled" : ""}>${icon("right")}</button>
      <span class="grow">${esc(doc.name)}</span><a class="cp-icon-button" href="/api/files/${esc(fileId)}/original" target="_blank" rel="noopener" aria-label="Open full source">${icon("external")}</a></div>
    ${head}<div class="cp-doc-body">${body}</div>${doc.note ? `<div class="cp-doc-note">${esc(doc.note)}</div>` : ""}</article>`;
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
  return nodes ? `<div class="cp-spine" aria-label="Questions">${nodes}</div>` : "";
}

function describe(e) {
  const what = {
    "agent.start": () => `started: ${e.instruction || ""}`, "agent.end": () => e.summary || "done",
    "delegate": () => `asks ${AGENT_TITLE[e.to] || e.to}: ${e.instruction || ""}`,
    "fact.located": () => `found ${e.quotes} exact quote(s) for “${questionOf(e.fact)}”`,
    "fact.accepted": () => `supports “${questionOf(e.fact)}”`, "fact.rejected": () => `does not accept “${questionOf(e.fact)}”${e.reason ? `: ${e.reason}` : ""}`,
    "document.recorded": () => `${needOf(e.document)}: ${e.status}`, "document.accepted": () => `confirms ${needOf(e.document)}`,
    "document.rejected": () => `does not accept ${needOf(e.document)}`, "process.changed": () => `changed the process (${e.op})`,
    "tool": () => e.tool === "read_file" ? `reads ${fileName(e.file)}` : e.tool === "search" ? `searches “${e.query}”` : e.tool.replace(/_/g, " "),
  }[e.kind];
  return what ? what() : e.kind;
}
const valueText = (v) => (v === true ? "yes" : v === false ? "no" : String(v));
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
    || `<li class="active"><span class="cp-spinner"></span>Starting</li>`;
  return `<aside><section class="cp-card cp-plan"><h3>Building “${esc(title)}”</h3><ol>${rows}</ol></section>
    <div class="cp-agent-chip"><span class="cp-hex">${icon(AGENT_ICON[agent])}</span>${esc(AGENT_TITLE[agent])}</div>
    <details style="margin-top:14px"><summary class="cp-link">Work log</summary>${workLog()}</details></aside>`;
}

function factCards() {
  const cite = liveCite();
  if (!cite) return "";
  const event = S.events.slice().reverse().find((e) => e.cite);
  return `<div class="cp-facts">${["file", "claim"].map((k, i) => k === "file"
      ? `<div class="cp-fact">${icon("doc")}<span>${esc(fileName(cite.file))}${cite.page ? `, page ${cite.page}` : ""}</span></div>`
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
  if (refs.some((r) => r.startsWith("edit#"))) return '<span class="from edit">Changed for this case</span>';
  return "";
}

function processView() {
  const model = graphModel();
  if (!model) return `<p class="cp-empty">${S.data.case.workflow_id ? "Prepare the case to build its process." : "Choose a process on the left, or prepare the case and CasePath finds it from the documents."}</p>`;
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
    <div class="row" style="display:flex;gap:18px;align-items:center;margin-bottom:12px"><button class="cp-edit-link" id="edit-open">${icon("pencil")}Edit decision</button>
      <span class="cp-muted">Selected: ${esc(selected.title)}</span></div>
    ${S.editing ? editForm(selected) : ""}
    <div class="cp-graph" aria-label="Process">${nodes}</div>${branches}${chain()}${preview()}`;
}

function chain() {
  const ev = S.data.evaluation, r = result() || {};
  const accepted = (r.facts || []).filter((f) => f.verdict === "accepted");
  const present = ev.documents.filter((d) => d.status === "present");
  const missing = ev.documents.filter((d) => d.status === "missing" && d.required !== "suggested");
  const knowledge = ((S.data.provenance || {}).knowledge || []).filter((k) => k.applied);
  const sources = (S.data.process.sources || []).filter((s) => !["knowledge", "edit"].includes(s.id));
  const list = (items, empty) => items.length ? `<ul>${items.join("")}</ul>` : `<span class="cp-muted">${empty}</span>`;
  return `<div class="cp-chain">
    <section><h4>${icon("doc")}Source facts</h4>${list(accepted.map((f) => `<li><span class="ok">${icon("check")}</span>${esc(questionOf(f.fact))}: ${esc(valueText(f.value))}</li>`), "None accepted yet")}</section>
    <section><h4>${icon("law")}Basis</h4>${list(sources.map((s) => `<li>${esc(s.title)}</li>`), "—")}</section>
    <section><h4>${icon("evidence")}Current evidence</h4>${list(present.map((d) => `<li>${esc(d.title)}</li>`), "None found yet")}</section>
    <section><h4>${icon("doc")}Evidence still needed</h4>${list(missing.map((d) => `<li>${esc(d.title)}</li>`), "Nothing missing")}</section>
    <section><h4>${icon("memory")}From earlier cases</h4>${list(knowledge.map((k) => `<li>${esc(needOf(k.document) || k.note || k.item)}</li>`), "No Knowledge applied")}</section>
    <a class="cp-missing-box" href="#/case/${esc(S.route.id)}/document_finder">${icon("folder", "big")}<span>Documents<br><b>${missing.length} missing</b></span>${icon("right")}</a></div>`;
}

function preview() {
  const r = result() || {};
  const timeline = (r.brief && r.brief.timeline) || [];
  if (!timeline.length) return "";
  return `<section class="cp-preview"><div class="cp-lines">${timeline.map((t, i) => `<div class="${i === timeline.length - 1 ? "cited" : ""}"><time>${esc(t.date)}</time><span>${esc(t.event)}</span></div>`).join("")}</div>
    <div class="cp-page">${timeline.map((t) => esc((t.citations[0] || {}).quote || "")).join("\n\n")}</div></section>`;
}

const OPS = [["add_document", "Add a document need"], ["set_required_when", "Change when a document is required"], ["add_question", "Add a question"],
             ["set_transition", "Redirect a branch"], ["rename_step", "Rename this step"]];

function conditionFields(prefix) {
  const options = facts().map((f) => `<option value="${esc(f.id)}">${esc(questionLabel(f))}</option>`).join("");
  return `<div class="row"><label>Required when<select name="${prefix}-fact"><option value="">Always</option>${options}</select></label>
    <label>is<select name="${prefix}-value"></select></label></div>`;
}

function editForm(step) {
  const docs = S.data.process.documents.map((d) => `<option value="${esc(d.id)}">${esc(d.title)}</option>`).join("");
  const steps = S.data.process.steps.map((s) => `<option value="${esc(s.id)}">${esc(s.title)}</option>`).join("");
  const edges = (step.next || []).map((e, i) => `<option value="${i}">${esc(e.label || "next")} → ${esc(S.data.process.steps.find((s) => s.id === e.to).title)}</option>`).join("");
  return `<form class="cp-edit" id="edit-form"><h3>Edit “${esc(step.title)}”</h3>
    <label>Change<select name="op">${OPS.map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}</select></label>
    <div data-op="add_document"><label>Document<input name="title" maxlength="200" placeholder="e.g. Ventilation record"></label>
      <label>Why it is needed<input name="why" maxlength="400"></label>${conditionFields("add")}</div>
    <div data-op="set_required_when" hidden><label>Document<select name="document">${docs}</select></label>${conditionFields("set")}</div>
    <div data-op="add_question" hidden><label>Question<input name="question" maxlength="300"></label>
      <label>Only require this document when the answer is yes<select name="gates"><option value="">No document</option>${docs}</select></label></div>
    <div data-op="set_transition" hidden><label>Branch<select name="edge">${edges}</select></label><label>Now leads to<select name="to">${steps}</select></label></div>
    <div data-op="rename_step" hidden><label>New wording<input name="rename" maxlength="200" value="${esc(step.title)}"></label></div>
    <label>Why this changes (required)<textarea name="reason" rows="2" required maxlength="500"></textarea></label>
    <label class="cp-check"><input type="checkbox" name="similar"> Use for similar cases</label>
    <label class="cp-check"><input type="checkbox" name="activate" disabled> Apply to new cases now (otherwise it is suggested until approved)</label>
    <div class="row"><button class="cp-button primary">Save change</button><button type="button" class="cp-button" id="edit-cancel">Cancel</button>
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
    select.innerHTML = values.map((v) => `<option value='${esc(JSON.stringify(v))}'>${esc(v === true ? "yes" : v === false ? "no" : v)}</option>`).join("");
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
  if (!condition || condition === true) return "Always required";
  const parts = condition.all || [condition];
  return "Required when " + parts.map((c) => `${questionOf(c.fact)} = ${c.is === true ? "yes" : c.is === false ? "no" : c.is}`).join(" and ");
}
function snapshot(op, args) {
  const process = S.data.process;
  if (op === "add_document") return "Not part of this step";
  if (op === "set_required_when") return `${needOf(args.document)}: ${conditionText((process.documents.find((d) => d.id === args.document) || {}).required_when)}`;
  if (op === "add_question") return "No such question";
  if (op === "set_transition") { const step = process.steps.find((s) => s.id === args.step); const e = step.next[args.index]; return `${e.label || "Next"} → ${process.steps.find((s) => s.id === e.to).title}`; }
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
  const items = diff.documents_added.map((d) => current[d.document] || d).map((d) => `<li class="${d.status === "present" ? "present" : ""}"><span class="x">${icon(d.status === "present" ? "check" : "xcircle")}</span>${esc(d.title)} · ${esc(d.status === "unchecked" ? "not checked yet" : d.status)}</li>`)
    .concat(diff.documents_removed.map((d) => `<li><span class="x">${icon("xcircle")}</span>${esc(d.title)} · no longer needed</li>`))
    .concat(diff.documents_changed.map((d) => `<li><span class="x">${icon("xcircle")}</span>${esc(needOf(d.document))} · ${esc(d.required_after === "depends" ? "now depends on an answer" : d.required_after)}</li>`)).join("");
  const recheck = S.data.run && S.data.run.result && S.data.run.result.recheck_of ? "Checked against the case's files." : e.recheck ? "Checking the case's files for it…" : "";
  return `<section aria-label="Your change"><div class="cp-before-now">
      <span class="label">BEFORE</span><span></span><span class="label now">NOW <span class="cp-edited-by">${icon("shield")}Edited by ${esc(e.edit.by)}</span></span>
      <div class="cp-before">${esc(e.before)}</div><div class="cp-arrow">→</div><div class="cp-now">${esc(nowText(e))}</div>
      <span></span><span></span><ul class="cp-missing">${items || '<li class="present"><span class="x">' + icon("check") + "</span>The checklist did not change</li>"}</ul></div>
    <p class="cp-muted">${esc(recheck)} ${e.knowledge ? `Saved for similar cases (${esc(e.knowledge.status === "active" ? "applies to new cases" : "suggested until approved")}).` : ""}
      <button class="cp-link" id="undo">Undo</button></p>${memoryChain()}</section>`;
}

function memoryChain() {
  const used = ((S.data.provenance || {}).knowledge || []).filter((k) => k.applied);
  if (!used.length || !S.knowledge) return "";
  const item = S.knowledge.find((k) => k.id === used[0].item);
  if (!item) return "";
  const evidence = (item.evidence || [])[0];
  const doc = S.data.evaluation.documents.find((d) => d.document === used[0].document);
  return `<p class="cp-retrieved">Retrieved ${used.length} Knowledge item${used.length > 1 ? "s" : ""} from earlier cases</p>
    <div class="cp-memory"><div class="card"><h4>Earlier case source ${icon("check")}</h4>${evidence ? `<span class="boxed">${esc(evidence.quote)}</span>` : '<span class="cp-muted">From a case worker’s change</span>'}</div>
      <div class="arrow">→</div><div class="card"><h4>Knowledge v${item.version} ${icon("shield")}</h4><p><b>${esc(item.content.title || item.content.question || item.content.text)}</b></p>
        <p class="cp-muted">${esc(item.content.why || item.applies_when_text || "")}</p><p class="cp-muted">Used ${item.stats.uses} times · confirmed ${item.stats.confirmed}${item.stats.contradicted ? ` · contradicted ${item.stats.contradicted}` : ""}</p></div>
      <div class="arrow">→</div><div class="card"><h4>Result ${icon("shield")}</h4><p class="headline">${esc((item.content.title || "Question") + " added")}</p>
        <p>${doc ? esc(doc.status === "present" ? "Found in this case’s files." : doc.status === "missing" ? "Still missing in this case." : "Not checked yet.") : ""}</p></div></div>`;
}

// ---------- other tabs ----------
function claimView(card) {
  const r = result();
  const brief = r && r.brief;
  return `${spine()}<div class="cp-live"><div>${card}</div><aside>${brief ? `<section class="cp-card" style="padding:16px 18px">
      <h2 class="cp-section" style="margin-top:0">The request</h2><p>${esc(brief.request || "")}</p>
      ${(brief.parties || []).length ? `<h2 class="cp-section">Parties</h2><ul>${brief.parties.map((p) => `<li>${esc(p.name)} <span class="cp-muted">· ${esc(p.role)}</span></li>`).join("")}</ul>` : ""}
      ${(brief.timeline || []).length ? `<h2 class="cp-section">Timeline</h2><div class="cp-lines">${brief.timeline.map((t) => `<div><time>${esc(t.date)}</time><span>${esc(t.event)}</span></div>`).join("")}</div>` : ""}
    </section>` : `<p class="cp-empty">The claim reader’s brief appears here after the case is prepared.</p>`}</aside></div>`;
}

function checkerView() {
  const rows = Object.values(recorded("fact")).map((f) => [questionOf(f.fact), f]).concat(Object.values(recorded("document")).map((d) => [needOf(d.document), d]));
  if (!rows.length) return `<p class="cp-empty">The source checker’s verdicts appear here: every finding with the exact sentence it rests on.</p>`;
  return `<table class="cp-table"><thead><tr><th>Finding</th><th>Verdict</th><th>Exact sentence</th></tr></thead><tbody>${rows.map(([label, row]) => `<tr>
    <td>${esc(label)}${row.value !== undefined && row.value !== null ? `: <b>${esc(valueText(row.value))}</b>` : row.status ? ` <span class="cp-muted">(${esc(row.status)})</span>` : ""}</td>
    <td>${row.verdict === "accepted" ? '<span class="cp-chip good">supported</span>' : row.verdict === "rejected" ? `<span class="cp-chip bad">not supported</span><br><small class="cp-muted">${esc(row.verdict_reason || "")}</small>` : '<span class="cp-chip wait">not checked</span>'}</td>
    <td>${(row.citations || []).map((c) => `<button class="cp-link" data-cite-file="${esc(c.file)}">“${esc(c.quote)}”</button><br><small class="cp-muted">${esc(fileName(c.file))}${c.page ? `, page ${c.page}` : ""}</small>`).join("<br>") || '<span class="cp-muted">—</span>'}</td></tr>`).join("")}</tbody></table>`;
}

function documentsView() {
  const ev = S.data.evaluation;
  if (!ev) return `<p class="cp-empty">The document checklist appears once the case has a process.</p>`;
  const rows = recorded("document");
  const origin = (id) => { const d = S.data.process.documents.find((x) => x.id === id) || {}; return d.knowledge ? "From Knowledge" : d.edit ? "Added for this case" : "From the process"; };
  const missing = ev.documents.filter((d) => d.status === "missing" && d.required !== "suggested").length;
  return `<h1 class="cp-title">Documents <span class="cp-muted">· ${missing} missing</span></h1>
    <table class="cp-table"><thead><tr><th>Document</th><th>Why</th><th>Status</th><th>Proof</th><th>Origin</th></tr></thead><tbody>${ev.documents.map((d) => {
      const row = rows[d.document] || {};
      const chip = d.status === "present" ? "good" : d.status === "missing" || d.status === "unusable" ? (d.required === "suggested" ? "wait" : "bad") : "wait";
      return `<tr><td><b>${esc(d.title)}</b>${d.required === "depends" ? '<br><small class="cp-muted">depends on an open answer</small>' : d.required === "suggested" ? '<br><small class="cp-muted">suggested by Knowledge</small>' : ""}</td>
        <td>${esc(d.why)}</td><td><span class="cp-chip ${chip}">${esc(d.status)}</span></td>
        <td>${(row.citations || []).map((c) => `<button class="cp-link" data-cite-file="${esc(c.file)}">“${esc(c.quote)}”</button>`).join("<br>") || "—"}</td><td class="cp-muted">${esc(origin(d.document))}</td></tr>`;
    }).join("")}</tbody></table>`;
}

function resultView() {
  const r = result();
  if (!r || !r.answer) return `<p class="cp-empty">The result checker’s answer, open points and reply draft appear here after the case is prepared.</p>`;
  const ev = S.data.evaluation;
  return `<h1 class="cp-title">Answer</h1><p class="cp-answer">${esc(r.answer)}</p><p>${esc(r.summary)}</p>
    ${ev && ev.current ? `<p class="cp-muted">Current step: <b>${esc(ev.current.title)}</b>${ev.waiting_for.length ? ` · waiting for: ${ev.waiting_for.map((w) => esc(w.question)).join("; ")}` : ""}</p>` : ""}
    ${ev && ev.outcome ? `<p class="cp-muted">Outcome in the process: <b>${esc(ev.outcome.title)}</b></p>` : ""}
    ${(r.open_points || []).length ? `<h2 class="cp-section">Open points</h2><ul>${r.open_points.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>` : ""}
    ${r.reply && r.reply.needed ? `<h2 class="cp-section">Reply draft</h2><article class="cp-reply"><header><span>${esc(r.reply.subject)}</span><span>${esc(r.reply.label || "AI-generated draft")}</span></header>
      <div class="clauses">${r.reply.clauses.map((c) => `<div class="clause ${c.supported ? "" : "unsupported"}"><p>${esc(c.text)}</p>
        <small class="cp-muted">${c.supported ? "Rests on: " + c.basis.map((b) => esc(b.startsWith("fact:") ? questionOf(b.slice(5)) : needOf(b.slice(9)))).join("; ") : "Not supported by an accepted finding: review before use"}</small></div>`).join("")}</div>
      <footer>${icon("shield")}Draft · not sent — a person decides</footer></article>` : ""}
    ${(r.learning || []).length ? `<h2 class="cp-section">What CasePath proposes to learn</h2><ul>${r.learning.map((l) => `<li><b>${esc(l.action)}</b> · ${esc(l.title || l.question || l.note)} <span class="cp-muted">— ${esc(l.reason)}</span></li>`).join("")}</ul>
      <p><a href="#/knowledge">Review in Knowledge</a></p>` : ""}
    <h2 class="cp-section">Work log</h2>${workLog()}`;
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
  for (const b of document.querySelectorAll("[data-cite-file]")) b.addEventListener("click", () => { S.file = b.dataset.citeFile; renderCase(); });
  const open = $("#edit-open");
  if (open) open.addEventListener("click", () => { S.editing = true; renderCase(); });
  const undo = $("#undo");
  if (undo) undo.addEventListener("click", async () => { await api(`/api/edits/${S.lastEdit.edit.id}/undo`, { method: "POST" }); S.lastEdit = null; await loadCase(); });
  bindEdit();
  const hit = $("#live-hit");
  if (hit) hit.scrollIntoView({ block: "center", behavior: "smooth" });
  const notice = $("#notice");
  const used = ((S.data.provenance || {}).knowledge || []).some((k) => k.applied);
  notice.hidden = !used;
  document.body.classList.toggle("with-notice", used);
  notice.innerHTML = used ? `${icon("shield")}This case used Knowledge from earlier cases. Qualified review is still required.` : "";
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
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><span class="cp-chip ${k.status === "active" ? "good" : k.status === "retired" ? "" : "wait"}">${esc(k.status)}</span>
        <span class="cp-chip">${esc(k.kind.replace("_", " "))}</span><span class="cp-chip">v${k.version}</span>${k.refines ? '<span class="cp-chip wait">refinement</span>' : ""}
        ${k.review_suggested ? '<span class="cp-chip bad">review suggested: contradicted often</span>' : ""}</div>
      <b>${esc(k.content.title || k.content.question || k.content.text)}</b>${k.content.why ? `<span class="cp-muted">${esc(k.content.why)}</span>` : ""}
      ${k.applies_when_text ? `<span class="cp-muted">Applies when: ${esc(k.applies_when_text)}</span>` : ""}
      <span>Used ${k.stats.uses} · confirmed ${k.stats.confirmed} · not found ${k.stats.not_found} · contradicted ${k.stats.contradicted}</span>
      ${(k.evidence || []).slice(0, 2).map((e) => `<span class="cp-muted">“${esc(e.quote)}” — <a href="#/case/${esc(e.case_id)}/claim_reader">${esc(titles[e.case_id] || "case")}</a></span>`).join("")}
      <span class="cp-muted">Learned ${k.origin.kind === "case_edit" ? "from a case worker’s change" : "by the result checker"} in <a href="#/case/${esc(k.origin.case_id)}/process_builder">${esc(titles[k.origin.case_id] || "a case")}</a></span>
      ${(byItem[k.id] || []).length ? `<span>Cases: ${(byItem[k.id] || []).map((u) => `<a href="#/case/${esc(u.case_id)}/document_finder">${esc(titles[u.case_id] || u.case_id)}</a> <span class="cp-chip ${u.outcome === "present" ? "good" : u.outcome === "contradicted" ? "bad" : ""}">${esc(u.outcome)}</span>`).join(" ")}</span>` : ""}
      <details><summary class="cp-link">History</summary><ul class="cp-log">${k.history.map((h) => `<li><b>v${h.version}</b><span>${esc(h.change)} · ${esc(h.by || "")} · ${dateText(h.at)}</span></li>`).join("")}</ul></details>
      <div class="row" style="display:flex;gap:10px">${k.status !== "active" && k.status !== "retired" ? `<button class="cp-button primary" data-activate="${esc(k.id)}">${k.refines ? "Apply refinement" : "Activate"}</button>` : ""}
        ${k.status !== "retired" ? `<button class="cp-button" data-retire="${esc(k.id)}">Retire</button>` : ""}</div></article>`;
  const sections = Object.entries(families).map(([family, items]) => `<h2 class="cp-section">${esc(family)} <span class="cp-muted">· ${items.length} items · ${items.reduce((n, k) => n + k.stats.uses, 0)} uses</span></h2>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:16px;align-items:start">${items.map(card).join("")}</div>`).join("");
  $("#app").innerHTML = `<main class="cp-main"><h1 class="cp-title">Knowledge</h1><p class="cp-muted">What CasePath learned from earlier cases and case workers’ changes. Active items shape new cases; candidates are checked as suggestions until a person activates them.</p>
    ${sections || '<p class="cp-empty">Nothing learned yet. Knowledge appears after cases are prepared or a case worker saves a change for similar cases.</p>'}</main>`;
  for (const b of document.querySelectorAll("[data-activate]")) b.addEventListener("click", async () => { await api(`/api/knowledge/${b.dataset.activate}/activate`, { method: "POST", body: JSON.stringify({ reason: "approved in Knowledge" }) }); renderKnowledge(); });
  for (const b of document.querySelectorAll("[data-retire]")) b.addEventListener("click", async () => { await api(`/api/knowledge/${b.dataset.retire}/retire`, { method: "POST", body: JSON.stringify({ reason: "retired in Knowledge" }) }); renderKnowledge(); });
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
