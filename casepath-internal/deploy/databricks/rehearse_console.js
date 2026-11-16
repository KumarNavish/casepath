// The D11 diagnostic for the pilot page's own console: deploy/databricks/rehearse.py, step for step, for a deployment
// whose sign-in admits a person's browser session and no notebook call. It is pasted into the console of the pilot's
// page (the app's own origin, the person signed in) and calls the app's API exactly as the notebook cell does, never a
// model itself. Paste the file, then type one of:
//   await casepathDiagnose("hashes D11")                                        read only: the plan and the approving phrase
//   await casepathDiagnose("shape D11")                                         read only: why a plan cannot be made (see shape())
//   await casepathDiagnose("diagnose D11 <tree hash> <labels sha256> <plan>")    the run, on exactly that build, labels and cut
//   await casepathDiagnose("diagnose D11 <tree hash> <labels sha256> <plan> keep")   the same, keeping the base case
// Anything else: nothing happens, no request is made. The phrase is the approval of this run's steps only; the
// deployment of the build and the run's tokens need Navish's separate typed approval, as the plan says.
// The steps, their order, the stops and the receipt (casepath.diagnose/1: ids, counts and enums only) are the notebook
// cell's; tests/test_rehearsal_receipt.py runs both against one stand-in and requires the same receipt. Two differences,
// both forced by the browser:
//   - the receipt is kept in this origin's localStorage («casepath.diagnose/D11-<labels>») instead of on the volume; it
//     marks the run as made in this browser profile: no second run without removing that entry and a new approval;
//   - a GET that fails on the network or at the proxy (502, 503, 504) is tried again (up to three times); a POST never is;
//   - a tab can be lost. While a run's receipt reads «started», typing the same phrase again (after pasting the file
//     again) takes that run up where it stands: no step is repeated, a run the app already holds is waited for and
//     never started a second time, and the receipt then says «resumed». A sign-in that ran out (401, 403) or a server
//     fault (5xx) leaves the run «started» for that reason, where the cell would end it. A run that is done or stopped
//     is never taken up again.
// The tab should stay open until the receipt is printed: the run's later steps are taken from here.
(() => {
  const FORMAT = "casepath.diagnose/1", DOSSIER = "D11";
  const STOP_AFTER_PREPARE = 200000;  // non-cached input of the full preparation past which the run stops: a stop, never a budget
  const ARRIVAL_PAGES = 20, ARRIVALS = 2;
  const ESTIMATE = "about 100-155k non-cached input and 23-33k output tokens, plus the page readings if any, as MEASURE §3 estimates";
  const SAFE = /^(?:[a-z0-9][a-z0-9_.:-]{0,79}|h_[0-9a-f]{12})$/;
  const DATE = /\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4}/;
  const GAP = "[bitte ergänzen: ";
  const ROWS = [[3, "Verneinung"], [4, "Sie möchten"], [1, "Vorschlag (Stichwort)"], [2, "keine Regel des Gebiets"], [6, "Regel trifft nach der Akte"],
                [7, "beruht auf einer widersprüchlichen"], [11, "Absicht der Frage unklar"], [5, "Zuordnung prüfen"]];
  const GUARD_ROWS = new Set([1, 3, 4, 5, 6, 7, 11]);

  class Stop extends Error { constructor(step, reason) { super(`${step}: ${reason}`); this.step = step; this.reason = reason; } }
  class ApiError extends Error { constructor(status) { super(`HTTP ${status}`); this.status = status; } }
  class Refused extends Error {}  // nothing done: the phrase, the build, the labels or the cut is not the approved one
  class Interrupted extends Error {}  // the run stays «started»: the same phrase takes it up again

  // Python's truth of a value (an empty list, an empty object, "" and 0 are false), where the cell relies on it
  const truthy = (v) => (Array.isArray(v) ? v.length > 0 : v && typeof v === "object" ? Object.keys(v).length > 0 : Boolean(v));
  const byNumber = (a, b) => a - b;
  const byText = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
  // json.dumps as Python writes it: keys sorted; ``compact`` False gives ", " and ": " with non-ASCII escaped (the plan's
  // seal), True gives "," and ":" with non-ASCII kept (the labels' hash)
  const dumps = (v, compact) => {
    const text = (s) => (compact ? JSON.stringify(s) : JSON.stringify(s).replace(/[\u007f-￿]/g, (c) => "\\u" + c.charCodeAt(0).toString(16).padStart(4, "0")));
    if (v === null || v === undefined) return "null";
    if (typeof v === "string") return text(v);
    if (typeof v === "number" || typeof v === "boolean") return String(v);
    if (Array.isArray(v)) return "[" + v.map((x) => dumps(x, compact)).join(compact ? "," : ", ") + "]";
    return "{" + Object.keys(v).sort(byText).map((k) => text(k) + (compact ? ":" : ": ") + dumps(v[k], compact)).join(compact ? "," : ", ") + "}";
  };
  const sha256 = async (text) => {
    const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
    return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, "0")).join("");
  };
  const labelsSha256 = (labels) => sha256(dumps(labels, true));
  const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

  // The deployed app, as the cell's Api calls it; the identity is the browser's own signed-in session
  function Api(base) {
    const send = async (method, path, init, tries) => {
      for (let n = 1; ; n += 1) {
        let response;
        try {
          response = await fetch(base + path, { method, credentials: "same-origin", ...init });
        } catch (error) {
          if (n >= tries) throw error;
          await sleep(5000);
          continue;
        }
        if (method === "GET" && [502, 503, 504].includes(response.status) && n < tries) { await sleep(5000); continue; }
        if (!response.ok) throw new ApiError(response.status);
        return response;
      }
    };
    return {
      async call(method, path, body) {
        const init = body === undefined ? {} : { body: JSON.stringify(body), headers: { "Content-Type": "application/json" } };
        const response = await send(method, path, init, method === "GET" ? 3 : 1);
        const text = await response.text();
        return text ? JSON.parse(text) : null;
      },
      async raw(path) { return (await send("GET", path, {}, 3)).arrayBuffer(); },
      async upload(caseId, files) {  // [[name, bytes]] in one request (field «files»): [status, answer]
        const form = new FormData();
        for (const [name, data] of files) form.append("files", new Blob([data], { type: "application/pdf" }), name);
        try {
          const response = await send("POST", `/api/cases/${caseId}/files`, { body: form }, 1);
          return [201, await response.json()];
        } catch (error) {
          if (error instanceof ApiError) return [error.status, {}];
          throw error;
        }
      },
    };
  }

  function contentFree(value, path = "$") {
    if (value === null || value === undefined || typeof value === "boolean" || typeof value === "number") return value;
    if (typeof value === "string") {
      if (!SAFE.test(value) || DATE.test(value)) throw new Error(`${path}: not an id, an enum or a count`);
      return value;
    }
    if (Array.isArray(value)) return value.map((v, i) => contentFree(v, `${path}[${i}]`));
    if (typeof value === "object") {
      for (const key of Object.keys(value)) if (!SAFE.test(String(key))) throw new Error(`${path}: key is not an identifier`);
      return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, contentFree(v, `${path}.${k}`)]));
    }
    throw new Error(`${path}: unsupported value`);
  }

  function parse(phrase) {
    phrase = String(phrase || "").trim();
    if (phrase === `hashes ${DOSSIER}`) return { mode: "hashes" };
    if (phrase === `shape ${DOSSIER}`) return { mode: "shape" };
    const m = new RegExp(`^diagnose ${DOSSIER} ([0-9a-f]{12}) ([0-9a-f]{12,64}) ([0-9a-f]{12})( keep)?$`).exec(phrase);
    if (!m) throw new Refused(`confirm must read: diagnose ${DOSSIER} <tree hash> <labels sha256> <plan> [keep], or hashes ${DOSSIER}`);  // (or shape D11)
    return { mode: "diagnose", tree: m[1], wanted: m[2], plan: m[3], keep: Boolean(m[4]) };
  }

  async function find(api) {
    const rows = (await api.call("GET", "/api/replay-points")).rows || [];
    const cases = [...new Set(rows.filter((r) => r.dossier === DOSSIER).map((r) => r.case))].sort(byText);
    if (cases.length !== 1) throw new Stop("find", cases.length ? "several_labelled_cases" : "no_labelled_case");
    return [cases[0], await api.call("GET", `/api/cases/${cases[0]}/labels`)];
  }

  // The PDF's documents in page order, from the labels template's rows (the cell's documents())
  function documents(rows, pages) {
    const docs = [];
    const ordered = rows.filter((r) => Number.isInteger(r.page)).map((r, i) => [r, i])
      .sort(([a, i], [b, j]) => a.page - b.page || Number(a.n == null) - Number(b.n == null) || i - j).map(([r]) => r);
    for (const r of ordered) {
      const last = docs[docs.length - 1];
      const dated = truthy(r.date), older = Boolean(truthy(r.date) && last && truthy(last.date) && r.date < last.date);
      if (!last || ((r.n != null || dated) && !older)) {
        if (!last || last.first !== r.page) {
          docs.push({ date: r.date == null ? null : r.date, insurer: truthy(r.insurer) || r.from === "versicherer", first: r.page, n: r.n == null ? null : r.n, rows: 0 });
        }
      }
      docs[docs.length - 1].rows += 1;
    }
    docs.forEach((doc, i) => {
      const next = i + 1 < docs.length ? docs[i + 1].first : pages + 1;
      doc.pages = [];
      for (let p = doc.first; p < next; p += 1) doc.pages.push(p);
    });
    const days = docs.map((d) => d.date);
    docs.forEach((doc, i) => {
      const around = [...days.slice(0, i).filter(truthy).slice(-1), ...days.slice(i + 1).filter(truthy).slice(0, 1)];
      if (!truthy(doc.date) && around.length) doc.date = around.reduce((a, b) => (a > b ? a : b));
    });
    return docs;
  }

  // The cut, from the labels and the labels template (the cell's plan())
  function plan(labels, template, pdf) {
    const points = [...labels.points].sort((a, b) => byText(a.date, b.date) || a.n - b.n);
    const n3 = points.find((p) => p.kind === "A5");
    if (!n3) throw new Stop("cut", "no_assessment_point");
    const before = points.filter((p) => p.date < n3.date);
    const since = before.length ? before[before.length - 1].date : "0000-00-00";
    const pages = Math.trunc(Number((pdf.extraction || {}).pages || 0));
    const docs = documents((template.documents || []).filter((r) => r.file == null || r.file === pdf.name), pages);
    const replies = docs.filter((d) => !d.insurer && truthy(d.date) && since < d.date && d.date < n3.date);
    if (replies.length !== ARRIVALS) throw new Stop("cut", replies.length ? "arrival_not_as_in_the_outline" : "no_reply_found");
    const first = replies.map((r) => r.date).reduce((a, b) => (a < b ? a : b));
    const later = docs.filter((d) => !replies.includes(d) && truthy(d.date) && d.date >= first);
    if (later.some((d) => d.date < n3.date || (d.date === n3.date && !d.insurer))) throw new Stop("cut", "another_document_before_the_assessment");
    const earlier = docs.filter((d) => !replies.includes(d) && !later.includes(d));
    const sum = (list) => list.reduce((n, d) => n + d.rows, 0);
    const cut = { n3, base: earlier.flatMap((d) => d.pages).sort(byNumber), arrival: replies.map((d) => d.pages),
                  later: later.flatMap((d) => d.pages).sort(byNumber), entries: replies.map((d) => d.n),
                  rows: { base: sum(earlier), arrival: sum(replies), later: sum(later) } };
    const all = [...cut.base, ...cut.later, ...cut.arrival.flat()].sort(byNumber);
    if (all.length !== pages || all.some((p, i) => p !== i + 1)) throw new Stop("cut", "pages_not_in_exactly_one_part");
    const arriving = cut.arrival.reduce((n, a) => n + a.length, 0);
    if (!cut.base.length || !(arriving > 0 && arriving <= ARRIVAL_PAGES)) throw new Stop("cut", "pages_out_of_bounds");
    return cut;
  }

  const sealed = async (cut) => (await sha256(dumps({ point: cut.n3.n, as_of: cut.n3.date, base: cut.base, arrival: cut.arrival, later: cut.later }, false))).slice(0, 12);

  function spans(pages) {  // [1, 2, 3, 7] → «1-3,7», as the cut route reads pages
    const out = [];
    let start = null;
    pages.forEach((p, i) => {
      if (start === null) start = p;
      if (i + 1 === pages.length || pages[i + 1] !== p + 1) { out.push(p !== start ? `${start}-${p}` : String(p)); start = null; }
    });
    return out.join(",");
  }

  async function planLines(cut, tree, labels) {
    const arriving = cut.arrival.reduce((n, a) => n + a.length, 0);
    return [`The D11 diagnostic, its plan (nothing done but reading): build ${tree} · labels ${labels} · plan ${await sealed(cut)}`,
            `  the earlier state: pages ${spans(cut.base)} (${cut.rows.base} rows of the labels template), looked at on the day of point ${cut.n3.n}`,
            `  one full preparation of it; the run stops if it failed or its non-cached input passed ${STOP_AFTER_PREPARE.toLocaleString("en-US")} tokens: a stop, never a budget or an allowance`,
            `  the arrival, as the labels template lists it: ${cut.arrival.length} documents not the insurer's, pages ${cut.arrival.map(spans).join(", ")} (${arriving} pages) as one import, then one of them again`,
            `  left out: pages ${spans(cut.later) || "none"} (${cut.rows.later} rows of the labels template, from the replies' day on)`,
            "  the deployment's own caps hold throughout: CASEPATH_RUN_TOKEN_BUDGET per run, CASEPATH_UPDATE_TOKEN_BUDGET per update",
            `  needs, besides the confirm phrase, Navish's separate typed approval of the deployment of build ${tree} to the pilot and of this run's tokens: ${ESTIMATE}`];
  }

  // The run once it ended; one that has not ended in time is stopped («Anhalten») and returned as it stands
  async function wait(api, runId, timeout, poll, beat = () => {}) {
    const started = Date.now();
    const going = (r) => r.status === "queued" || r.status === "running";
    let run = await api.call("GET", `/api/runs/${runId}`);
    while (going(run) && Date.now() - started < timeout * 1000) {
      beat();
      await sleep(poll);
      run = await api.call("GET", `/api/runs/${runId}`);
    }
    if (going(run)) await api.call("POST", `/api/runs/${runId}/stop`);
    return run;
  }

  const kind = (value) => (truthy(value) ? String(value).toLowerCase() : null);
  const whole = (v) => Math.trunc(Number(v || 0));
  const pyRound = (x) => { const f = Math.floor(x); return x - f === 0.5 ? (f % 2 === 0 ? f : f + 1) : Math.round(x); };  // round half to even, as Python

  function runRow(run) {
    const usage = {};
    for (const u of (run.result || {}).usage || []) {
      const key = String(truthy(u.agent) ? u.agent : "model").toLowerCase().replace(/[^a-z0-9_]/g, "_");
      const row = usage[key] || (usage[key] = { calls: 0, input: 0, cached: 0, non_cached: 0, output: 0 });
      row.calls += 1;
      row.input += whole(u.input_tokens);
      row.cached += whole(u.cached_tokens);
      row.output += whole(u.output_tokens);
      row.non_cached = row.input - row.cached;
    }
    const a = Date.parse(run.finished_at), b = Date.parse(run.created_at);
    const seconds = Number.isNaN(a) || Number.isNaN(b) ? null : pyRound((a - b) / 1000);
    const total = (field) => Object.values(usage).reduce((n, u) => n + u[field], 0);
    return { id: run.id === undefined ? null : run.id, kind: truthy(run.kind) ? run.kind : "full", status: run.status === undefined ? null : run.status, seconds,
             pages_read: (usage.reader || {}).calls || 0, usage, non_cached: total("non_cached"), output: total("output") };
  }

  const stateOf = (q) => String(q.state || q.answer_state || "").replace(/ü/g, "ue") || null;
  const rowOf = (q) => {
    if (Number.isInteger(q.row)) return q.row;
    const reason = String(q.reason || "");
    const hit = ROWS.find(([, start]) => reason.startsWith(start));
    return hit ? hit[0] : null;
  };

  // What the receipt holds of the case after the update (the cell's read_case); a field the build does not give is
  // named in ``missing``, never filled in
  function readCase(detail, updateRun, fullRun, missing) {
    const result = (updateRun || {}).result || {};
    const brief = result.brief || {};
    let assessment = detail.assessment;
    if (assessment == null) { missing.push("assessment"); assessment = {}; }
    let questions = assessment.questions;
    if (questions == null) { missing.push("assessment.questions"); questions = brief.questions || []; }
    let claims = brief.claims;
    if (claims == null) { missing.push("brief.claims"); claims = []; }
    const update = result.update || {};
    const ledger = update.ledger == null ? null : update.ledger;
    if (ledger === null) missing.push("update.ledger");
    const count = (...keys) => {
      const key = keys.find((k) => (ledger || {})[k] != null);
      return key === undefined ? null : Array.isArray(ledger[key]) ? ledger[key].length : Math.trunc(Number(ledger[key]));
    };
    const record = result.record || {}, prior = ((fullRun || {}).result || {}).record || {};
    const dropped = brief.dropped_tags;
    const rows = questions.map(rowOf);
    const action = (detail.items || []).find((i) => i.kind === "next_action") || {};
    const text = (detail.draft || {}).text || "";
    const states = {};
    for (const s of ["beantwortet", "bedingt", "offen", "pruefen"]) states[s] = questions.filter((q) => stateOf(q) === s).length;
    const residual = assessment.residual || [];
    return {
      update: { new_entries: (update.entries || []).length, dropped: whole(record.dropped) - whole(prior.dropped), elsewhere: whole(record.elsewhere) - whole(prior.elsewhere),
                facts_changed: [...(update.facts || [])].sort(byText) },
      questions: { found: questions.length, tagged: questions.filter((q) => truthy(q.about)).length, tags_dropped: Array.isArray(dropped) ? dropped.length : whole(dropped),
                   rows: rows.map((r) => (r !== null ? r : 0)), guard_rows: [...new Set(rows.filter((r) => GUARD_ROWS.has(r)))].sort(byNumber), states,
                   intents: [...new Set(questions.filter((q) => truthy(q.intent)).map((q) => q.intent))].sort(byText) },
      claims: { found: claims.length, checked: claims.filter((c) => truthy(c.checked)).length, amount_kept: claims.filter((c) => truthy(c.amount)).length,
                documented: claims.filter((c) => truthy(c.documented)).length },
      ledger: { closed: count("closed"), held: (((ledger || {}).closed) || []).filter((r) => r && typeof r === "object" && !Array.isArray(r) && truthy(r.held)).length,
                refused: count("refused", "refusals"), partial: count("partial"), promised: count("promised"), unspecified: count("unspecified") },
      decision: [...new Set((assessment.blocking || []).filter((b) => b.kind === "decision" && truthy(b.key)).map((b) => b.key))].sort(byText),
      proposal: [...(assessment.proposal || [])],
      residual: { keys: residual.map((r) => (r.key === undefined ? null : r.key)), count: residual.length },
      gaps: text.split(GAP).length - 1, next_action: kind(action.action) };
  }

  function replayOf(row) {  // the narrow score and the expanded acceptance of n3, as the replay gives them
    if (!row) return null;
    const accept = row.accept || {};
    const pick = (block, keys) => Object.fromEntries(keys.map((k) => [k, (block || {})[k] === undefined ? null : (block || {})[k]]));
    const or = (v) => (v === undefined ? null : v);
    return { narrow: { kind: kind(row.kind), kind_ok: or(row.kind_ok), ready: or(row.ready), ...pick(row.documents, ["hits", "missed", "extras"]) },
             accept: { recipient: or((accept.recipient || {}).ok), residual: pick(accept.residual, ["hits", "missed", "extras", "ok"]),
                       questions: pick(accept.questions, ["beantwortet", "bedingt", "offen", "pruefen", "label", "ok"]),
                       substantive: pick(accept.substantive, ["present", "gaps", "status"]), authority: pick(accept.authority, ["missing", "ok"]) } };
  }

  async function located(api) {  // read only: D11's case id and labels
    try { return await find(api); } catch (stop) {
      if (stop instanceof Stop) throw new Refused(`${stop.reason}: nothing done`);
      throw stop;
    }
  }

  async function cutOf(api, caseId, labels) {  // read only: D11's one PDF and the cut its labels template gives
    try {
      const files = ((await api.call("GET", `/api/cases/${caseId}`)).files || []).filter((f) => f.kind === "pdf");
      if (files.length !== 1) throw new Stop("cut", "not_one_pdf");
      return [files[0], plan(labels, await api.call("GET", `/api/cases/${caseId}/labels-template`), files[0])];
    } catch (stop) {
      if (stop instanceof Stop) throw new Refused(`${stop.reason}: nothing done`);
      throw stop;
    }
  }

  // The run (steps 1 to 7) on exactly the approved build, labels and cut; the receipt, also when it stops. A run whose
  // receipt reads «started» is taken up where it stands (``progress``: the runs it started and whether the arrival went
  // in, kept beside the receipt); the app's own record of the base case's runs decides where the two disagree.
  async function diagnose(api, store, say, tree, wanted, approvedPlan, keep, poll = 10000, stale = 60000, prepareTimeout = 2700, updateTimeout = 1800) {
    const manifest = await api.call("GET", "/api/manifest");
    if (!String(manifest.source_tree_sha256 || "").startsWith(tree)) throw new Refused("the running build is not the one approved: nothing done");
    const [caseId, labels] = await located(api);
    const signed = await labelsSha256(labels);
    if (!signed.startsWith(wanted)) throw new Refused("D11's labels are not the ones approved: nothing done");
    const key = `casepath.diagnose/${DOSSIER}-${signed.slice(0, 12)}`;
    const held = store.getItem(key);
    let receipt = null, progress = {};
    if (held) {
      receipt = JSON.parse(held);
      if (receipt.status !== "started") {
        say(`already run: ${key} holds its receipt; nothing done`);
        return receipt;
      }
      progress = JSON.parse(store.getItem(`${key}#progress`) || "{}");
      if (receipt.plan !== approvedPlan || receipt.kept !== keep) throw new Refused("the run started here was approved with another phrase: nothing done");
      if (Date.now() - (progress.beat || 0) < stale) throw new Refused("this run is being taken in another tab, or stopped a moment ago: wait a minute and type the phrase again; nothing done");
    }
    const resumed = Boolean(held);
    const [pdf, cut] = await cutOf(api, caseId, labels);
    say((await planLines(cut, tree, signed.slice(0, 12))).join("\n"));
    if (await sealed(cut) !== approvedPlan) throw new Refused("the cut is not the approved plan: nothing done");
    if (resumed) {
      receipt.resumed = (receipt.resumed || 0) + 1;
      say(`taking up the run started here (base ${receipt.base || "not made yet"}, ${receipt.runs.length} of its runs recorded): no step is repeated`);
    } else {
      receipt = { format: FORMAT, dossier: DOSSIER.toLowerCase(), build: tree, labels: signed.slice(0, 12), plan: approvedPlan, status: "started", stopped: null, base: null,
                  kept: keep, cut: null, arrival: null, runs: [], auto: null, duplicate_refused: null, decisions: [], case: null, n3: null, missing: [],
                  model_calls_here: 0 };
    }
    const save = () => {
      const { format, ...rest } = receipt;
      contentFree(rest);
      store.setItem(key, JSON.stringify(receipt));
    };
    const mark = (fields = {}) => { Object.assign(progress, fields, { beat: Date.now() }); store.setItem(`${key}#progress`, JSON.stringify(progress)); };
    const latest = async (base) => ((await api.call("GET", `/api/cases/${base}`)) || {}).run || null;  // the app's own record
    save();  // from here on, the run counts as made: no second one without a new approval
    mark();
    try {
      try {
        // 1 the cut: the earlier state of the approved plan, looked at on the assessment's day
        const n3 = cut.n3, basePages = cut.base, replies = cut.arrival;
        receipt.cut = { point: n3.n, pages: basePages.length, left_out: cut.later.length };
        receipt.arrival = { files: replies.length, pages: replies.reduce((n, a) => n + a.length, 0) };
        let base = receipt.base;
        if (!base) {
          try {
            base = (await api.call("POST", `/api/cases/${caseId}/cut`, { pages: spans(basePages), as_of: n3.date, file: pdf.id })).id;
          } catch (error) {
            if (error instanceof ApiError && ![401, 403].includes(error.status) && error.status < 500) throw new Stop("cut", "refused");
            throw error;
          }
          receipt.base = base;
          save();
        }
        // 2, 3 one full preparation, stopped on failure or past the stop threshold (a stop, never a budget)
        let full;
        if (receipt.runs.length >= 1) {
          full = await api.call("GET", `/api/runs/${receipt.runs[0].id}`);  // recorded before the tab was lost
        } else {
          let id = progress.full || null;
          if (!id && resumed) id = ((await latest(base)) || {}).id || null;  // started, its id not kept: it is waited for, never started again
          if (!id) id = (await api.call("POST", `/api/cases/${base}/runs`)).id;
          mark({ full: id });
          full = await wait(api, id, prepareTimeout, poll, mark);
          receipt.runs.push(runRow(full));
          save();
        }
        if (full.status !== "completed") throw new Stop("prepare", ["failed", "interrupted", "discarded"].includes(full.status) ? "failed" : "not_finished");
        if (receipt.runs[0].non_cached > STOP_AFTER_PREPARE) throw new Stop("prepare", "past_the_stop_threshold");
        // 4 the arrival: the replies' pages as one import, then one of them again
        let update;
        if (receipt.runs.length >= 2) {
          update = await api.call("GET", `/api/runs/${receipt.runs[1].id}`);
        } else {
          const original = (pages) => api.raw(`/api/files/${pdf.id}/original?pages=${spans(pages)}`);
          let started = null;
          if (!progress.arrived) {
            const uploads = [];
            for (let i = 0; i < replies.length; i += 1) uploads.push([`Antwort-${i + 1}.pdf`, await original(replies[i])]);
            const [status, answer] = await api.upload(base, uploads);
            if (status === 409 && resumed) {
              // the tab was lost after the arrival went in and before its answer was seen: the app holds these bytes and
              // refuses them, which is what the second upload tests; whether the import started an update, the app's record says
              receipt.duplicate_refused = true;
              mark({ arrived: true });
              save();
            } else {
              if (status !== 201) throw new Stop("arrival", "upload_refused");
              receipt.auto = SAFE.test(String(answer.auto || "")) ? answer.auto : "other";
              started = receipt.auto === "gestartet" ? (answer.run || {}).id || null : null;
              mark({ arrived: true, update: started });
              save();
              const [again] = await api.upload(base, uploads.slice(0, 1));
              receipt.duplicate_refused = again === 409;
              save();
            }
          } else {
            started = progress.update || null;
            if (receipt.duplicate_refused === null) {  // the arrival went in, its second upload was not seen
              const [again] = await api.upload(base, [["Antwort-1.pdf", await original(replies[0])]]);
              receipt.duplicate_refused = again === 409;
              save();
            }
          }
          if (!started && resumed) { const run = await latest(base); if (run && run.kind === "update") started = run.id; }
          if (receipt.duplicate_refused !== true) {  // a duplicate that is not refused is a fault of its own: no update is spent on it
            if (started) await api.call("POST", `/api/runs/${started}/stop`);
            throw new Stop("arrival", "duplicate_accepted");
          }
          const id = started || (await api.call("POST", `/api/cases/${base}/update`)).id;
          mark({ update: id });
          update = await wait(api, id, updateTimeout, poll, mark);
          receipt.runs.push(runRow(update));
          save();
        }
        if (update.status !== "completed") throw new Stop("update", ["failed", "interrupted", "discarded", "stopped"].includes(update.status) ? "failed" : "not_finished");
        // 5 the handler's decisions in force on the assessment's day (those already set before the tab was lost are not set again)
        const inForce = (labels.decisions || []).filter((d) => d.from <= n3.date);
        const ordered = inForce.map((d, i) => [d, i]).sort(([a, i], [b, j]) => byText(a.from, b.from) || i - j).map(([d]) => d);
        for (const d of ordered.slice(receipt.decisions.length)) {
          await api.call("POST", `/api/cases/${base}/edits`, { op: "set_fact", args: { fact: d.fact, value: d.value },
                                                               reason: `Entscheid der Fallbearbeitung laut Labels (Punkt ${n3.n})`, recheck: false });
          receipt.decisions.push(d.fact);
          save();
        }
        // 6 the case and the replay of n3
        receipt.missing = receipt.missing.filter((m) => m.startsWith("deleted:"));
        receipt.case = readCase(await api.call("GET", `/api/cases/${base}`), update, full, receipt.missing);
        await api.call("POST", `/api/cases/${base}/labels`, { format: labels.format === undefined ? null : labels.format, dossier: DOSSIER, case: base, decisions: inForce, points: [n3] });
        const row = ((await api.call("GET", `/api/replay-points?case=${base}`)).rows || []).find((r) => r.n === n3.n);
        receipt.n3 = replayOf(row);
        receipt.status = "done";
      } catch (stop) {
        if (stop instanceof Stop) { receipt.status = "stopped"; receipt.stopped = { step: stop.step, reason: stop.reason }; }
        else if (stop instanceof ApiError && ([401, 403].includes(stop.status) || stop.status >= 500)) {
          throw new Interrupted(`interrupted (http_${stop.status}): the run stays started. Sign in again if asked, paste this file and type the same phrase: it is taken up where it stands`);
        } else if (stop instanceof ApiError) { receipt.status = "stopped"; receipt.stopped = { step: "api", reason: `http_${stop.status}` }; }
        else throw stop;
      }
    } finally {
      // 7 the base case goes, unless it is kept for the inside review; a run that is not ended keeps it, to be taken up
      if (receipt.status !== "started" && receipt.base && !keep) {
        try { await api.call("DELETE", `/api/cases/${receipt.base}`); } catch (error) {
          if (error instanceof ApiError) receipt.missing.push(`deleted:http_${error.status}`); else throw error;
        }
      }
      progress.beat = 0;  // nobody is taking the run any more
      store.setItem(`${key}#progress`, JSON.stringify(progress));
      save();
    }
    return receipt;
  }

  async function hashes(api, say) {  // read only: the plan and the phrase that approves exactly it
    const tree = String((await api.call("GET", "/api/manifest")).source_tree_sha256 || "").slice(0, 12);
    const [caseId, labels] = await located(api);
    const [, cut] = await cutOf(api, caseId, labels);
    const out = { build: tree, labels: (await labelsSha256(labels)).slice(0, 12), plan: await sealed(cut), case: caseId };
    say([...(await planLines(cut, tree, out.labels)), `approval reads: diagnose ${DOSSIER} ${out.build} ${out.labels} ${out.plan}`].join("\n"));
    return out;
  }

  // Read only, for the case where no plan can be made: the shape of D11's labels and labels template as the cut sees
  // them. Page numbers, flags and where each date lies among the labelled points' days («<p1», «=p2», «p2..p3», «>p4»,
  // «not_iso»): never a date, a name or a text. Four GETs, nothing kept.
  async function shape(api, say) {
    const rows = (await api.call("GET", "/api/replay-points")).rows || [];
    const ids = [...new Set(rows.filter((r) => r.dossier === DOSSIER).map((r) => r.case))];
    if (ids.length !== 1) { const none = { labelled_cases: ids.length }; say(dumps(none, false)); return none; }
    const labels = await api.call("GET", `/api/cases/${ids[0]}/labels`), detail = await api.call("GET", `/api/cases/${ids[0]}`);
    const template = await api.call("GET", `/api/cases/${ids[0]}/labels-template`);
    const iso = (d) => typeof d === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d);
    const points = [...(labels.points || [])].sort((a, b) => byText(a.date, b.date) || a.n - b.n);
    const where = (d) => {
      if (d == null || d === "") return null;
      if (!iso(d)) return "not_iso";
      for (let i = 0; i < points.length; i += 1) {
        if (d === points[i].date) return `=p${points[i].n}`;
        if (d < points[i].date) return i === 0 ? `<p${points[i].n}` : `p${points[i - 1].n}..p${points[i].n}`;
      }
      return points.length ? `>p${points[points.length - 1].n}` : "no_points";
    };
    const who = (f) => (["versicherer", "kunde", "gegenpartei", "kanzlei", "behoerde", "andere"].includes(f) ? f : f == null ? null : "text");
    const pdfs = (detail.files || []).filter((f) => f.kind === "pdf"), pdf = pdfs[0] || {};
    const all = template.documents || [], mine = all.filter((r) => r.file == null || r.file === pdf.name);
    const pages = Math.trunc(Number((pdf.extraction || {}).pages || 0));
    const n3 = points.find((p) => p.kind === "A5");
    const paged = mine.filter((r) => Number.isInteger(r.page)).map((r, i) => [r, i]).sort(([a, i], [b, j]) => a.page - b.page || i - j).map(([r]) => r);
    const out = {
      points: points.map((p, i) => ({ n: p.n, kind: p.kind, iso: iso(p.date), same_day_as_previous: i > 0 && p.date === points[i - 1].date })),
      assessment_point: n3 ? n3.n : null, decisions: (labels.decisions || []).length,
      files: (detail.files || []).length, pdfs: pdfs.length, pages, rows_all: all.length, rows_of_this_pdf: mine.length, rows_without_page: mine.length - paged.length,
      rows: paged.map((r) => [r.page, r.n != null ? "entry" : "segment", where(r.date), truthy(r.insurer), who(r.from)]),
      documents: n3 && pdfs.length === 1 ? documents(mine, pages).map((d) => [d.first, d.pages.length, d.rows, d.insurer, where(d.date), d.n != null ? "entry" : "segment"]) : [],
    };
    say(dumps(out, false));
    return out;
  }

  // The console's one command. ``options`` is for the tests only: {base, store, say, poll, stale}.
  globalThis.casepathDiagnose = async (phrase, options = {}) => {
    const { mode, tree, wanted, plan: approvedPlan, keep } = parse(phrase);  // refuses before any request
    const api = Api(options.base || "");
    const say = options.say || ((line) => console.log(line));
    if (mode === "hashes") return hashes(api, say);
    if (mode === "shape") return shape(api, say);
    const receipt = await diagnose(api, options.store || globalThis.localStorage, say, tree, wanted, approvedPlan, keep,
                                   options.poll === undefined ? 10000 : options.poll, options.stale === undefined ? 60000 : options.stale);
    say(dumps(receipt, false));
    return receipt;
  };
  globalThis.casepathDiagnose.parts = { plan, sealed, documents, labelsSha256, spans, contentFree, dumps };  // for the tests
})();
