# The one cell of the "casepath diagnose" notebook: the one diagnostic run of the D11 episode on the pilot (MEASURE §3), an
# act task. Standard library only; it calls the deployed app's API as the benchmark does (quality/evaluate.py, RemoteApi),
# never a model itself. It reads one notebook parameter, "confirm" (made with Edit > Add parameter):
#   hashes D11                                         read only: prints the plan and the phrase that approves exactly it
#   diagnose D11 <tree hash> <labels sha256> <plan>    the run, on exactly that build, those labels and that cut (12 hex each)
#   diagnose D11 <tree hash> <labels sha256> <plan> keep    the same, keeping the base case for the inside review
# Anything else: nothing happens, no request is made. <tree hash> is the start of /api/manifest's source_tree_sha256;
# <labels sha256> the start of the sha256 of D11's labels as stored (sorted keys, compact JSON); <plan> the start of the
# sha256 of the cut the plan prints. The plan is D11's earlier state and its two arrivals as the labels template lists the
# file's documents: every page of the file in exactly one of the earlier state, the arrival (the two documents not the
# insurer's dated between the question back and the assessment: D11's two customer e-mails of one day) and what is left out
# (from the replies' day on). It reads the template as the stored reading gives it, with or without account entries, and
# with the file's documents oldest first or latest first (D11's file is printed with the newest on top).
# The confirm phrase is the approval of this run's steps only. The run also needs Navish's separate typed approval of the
# deployment of the build to the pilot and of the run's tokens; the plan says so, and this cell checks neither.
# The run, in this order, each step only if the one before succeeded; no retry, no second run (its receipt on the volume
# marks it done or stopped; a new run needs that file removed and a new approval):
#   1 cut D11 to the pages of the earlier state, looked at on the assessment's day (label n3);
#   2 prepare that base case once (a full preparation);
#   3 stop if it failed, or if its non-cached input passed 200,000 tokens: a stop, never a budget or an allowance;
#   4 the replies' pages, fetched from the original file, uploaded to the base case as one import (the update starts by
#     itself where auto-update is on, else one POST /update); one of them uploaded again: refused (409) or the run stops;
#   5 the handler's decisions in force on n3 (Deckung bestätigt) as set_fact edits;
#   6 read the case and the replay of n3 into the receipt;
#   7 delete the base case, unless kept.
# The deployment's own caps hold throughout: CASEPATH_RUN_TOKEN_BUDGET per run, CASEPATH_UPDATE_TOKEN_BUDGET per update.
# The receipt casepath.diagnose/1 holds ids, counts and enums only (no name, quote, date or amount); it is printed and
# written to <VOLUME>/diagnose/D11-<labels sha256>.json. Whatever the receipt cannot carry (the letter, the answers, the
# residual's words) stays in the base case for the inside review, if kept.
# Filled in here in the notebook only, never in Git: APP (the app's address) and VOLUME. The identity the app expects comes
# from the environment: CASEPATH_EVAL_IDENTITY_HEADER names the header, CASEPATH_EVAL_IDENTITY holds its value (as for
# quality/evaluate.py --identity-header).
# Keep this as the notebook's only cell.
from datetime import datetime
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid

APP = "FILL-IN: https://<the app's address>"
VOLUME = "FILL-IN: /Volumes/<catalog>/<schema>/<volume>"
FORMAT = "casepath.diagnose/1"
DOSSIER = "D11"
STOP_AFTER_PREPARE = 200_000  # non-cached input of the full preparation past which the run stops: a stop, never a budget
ARRIVAL_PAGES = 20  # as CASEPATH_AUTO_UPDATE_MAX_PAGES: an arrival larger than this is not this run
ARRIVALS = 2  # D11's arrival: the customer's two e-mails of one day (the bridge's outline)
ESTIMATE = "about 100-155k non-cached input and 23-33k output tokens, plus the page readings if any, as MEASURE §3 estimates"
SAFE = re.compile(r"^(?:[a-z0-9][a-z0-9_.:-]{0,79}|h_[0-9a-f]{12})$")  # as quality/scorecard.py
DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{2,4}")
GAP = "[bitte ergänzen: "
# SLICE_A A2: the reason each row of a question's status gives, in the order they are tried (a row number the build gives wins)
ROWS = ((3, "Verneinung"), (4, "Sie möchten"), (1, "Vorschlag (Stichwort)"), (2, "keine Regel des Gebiets"), (6, "Regel trifft nach der Akte"),
        (7, "beruht auf einer widersprüchlichen"), (11, "Absicht der Frage unklar"), (5, "Zuordnung prüfen"))
GUARD_ROWS = {1, 3, 4, 5, 6, 7, 11}


class Stop(Exception):
    """The run stops here: (step, reason), both enums."""


class ApiError(RuntimeError):
    def __init__(self, status, detail):
        super().__init__(f"HTTP {status}")
        self.status, self.detail = status, detail


class Api:
    """The deployed app, as quality/evaluate.py's RemoteApi calls it; ``headers`` carries the identity."""

    def __init__(self, url, headers):
        self.url, self.headers = url.rstrip("/"), dict(headers)

    def _send(self, method, path, data=None, content_type=None, raw=False):
        headers = {**self.headers, **({"Content-Type": content_type} if content_type else {})}
        request = urllib.request.Request(self.url + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=900) as response:
                body = response.read()
                return body if raw else json.loads(body or b"null")
        except urllib.error.HTTPError as error:
            raise ApiError(error.code, error.read()[:300].decode(errors="replace")) from None

    def call(self, method, path, body=None):
        return self._send(method, path, None if body is None else json.dumps(body).encode(), "application/json" if body is not None else None)

    def raw(self, path):
        return self._send("GET", path, raw=True)

    def upload(self, case_id, files):
        """[(name, bytes)] in one request (field «files»): (status, answer)."""
        boundary = uuid.uuid4().hex
        body = b"".join(f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"{name}\"\r\nContent-Type: application/pdf\r\n\r\n"
                        .encode() + data + b"\r\n" for name, data in files) + f"--{boundary}--\r\n".encode()
        try:
            return 201, self._send("POST", f"/api/cases/{case_id}/files", body, f"multipart/form-data; boundary={boundary}")
        except ApiError as error:
            return error.status, {}


def content_free(value, path="$"):
    """Only numbers, booleans, null and short identifiers or enums, and no date (quality/scorecard.py's guard, and no date)."""
    if value is None or isinstance(value, bool) or type(value) in (int, float):
        return value
    if isinstance(value, str):
        if not SAFE.match(value) or DATE.search(value):
            raise ValueError(f"{path}: not an id, an enum or a count")
        return value
    if isinstance(value, list):
        return [content_free(v, f"{path}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, dict):
        for key in value:
            if not SAFE.match(str(key)):
                raise ValueError(f"{path}: key is not an identifier")
        return {k: content_free(v, f"{path}.{k}") for k, v in value.items()}
    raise ValueError(f"{path}: unsupported value")


def labels_sha256(labels):
    return hashlib.sha256(json.dumps(labels, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def parse(phrase):
    """("hashes", None, None, None, False) or ("diagnose", tree, labels, plan, keep); AssertionError for anything else."""
    phrase = (phrase or "").strip()
    if phrase == f"hashes {DOSSIER}":
        return "hashes", None, None, None, False
    match = re.fullmatch(rf"diagnose {DOSSIER} ([0-9a-f]{{12}}) ([0-9a-f]{{12,64}}) ([0-9a-f]{{12}})( keep)?", phrase)
    assert match, f"confirm must read: diagnose {DOSSIER} <tree hash> <labels sha256> <plan> [keep], or hashes {DOSSIER}"
    return "diagnose", match.group(1), match.group(2), match.group(3), bool(match.group(4))


def find(api):
    """D11's case id and labels, from the replay's content-free table: exactly one case labelled D11."""
    cases = sorted({r["case"] for r in api.call("GET", "/api/replay-points").get("rows") or () if r.get("dossier") == DOSSIER})
    if len(cases) > 1:
        # a base case a run kept carries D11's labels too (step 6): a case cut from another labelled case is not the dossier
        cuts = [c for c in cases if any((((f.get("extraction") or {}).get("cut_of") or {}).get("case")) in cases
                                        for f in api.call("GET", f"/api/cases/{c}").get("files") or ())]
        cases = [c for c in cases if c not in cuts]
    if len(cases) != 1:
        raise Stop("find", "no_labelled_case" if not cases else "several_labelled_cases")
    return cases[0], api.call("GET", f"/api/cases/{cases[0]}/labels")


def newest_first(rows):
    """Whether the file lists its documents latest first (a dossier printed with the newest on top, as D11's is): of its
    dated rows in page order, more step back in time than forward."""
    days = [r["date"] for r in sorted((r for r in rows if isinstance(r.get("page"), int) and r.get("date")), key=lambda r: (r["page"], r.get("n") is None))]
    return sum(1 for a, b in zip(days, days[1:]) if b < a) > sum(1 for a, b in zip(days, days[1:]) if b > a)


def documents(rows, pages):
    """The PDF's documents in page order, from the labels template's rows (each with its first page: an account entry, or
    a segment of the reading the entries do not cover; a reading without entries gives segments only). An entry or a dated
    segment starts a document, a second one of the same day too (D11's two e-mails of one day); an undated segment (a
    photo, a receipt) and anything dated before the document it follows (a lease or an older letter sent along) belong to
    that document, as an enclosure no later than its letter does in quality/points.py. In a file that lists its documents
    latest first (newest_first) every next document is older than the one before it, so a date tells no enclosure from
    the next document there: every dated row starts a document, and only an undated one rides with the document before
    it. Each runs to the next one's first page and counts the template rows it holds; an undated document takes the
    later of the days around it, as quality/asof.py bounds an undated page."""
    docs, reverse = [], newest_first(rows)
    for r in sorted((r for r in rows if isinstance(r.get("page"), int)), key=lambda r: (r["page"], r.get("n") is None)):
        dated = bool(r.get("date"))
        older = bool(not reverse and r.get("date") and docs and docs[-1]["date"] and r["date"] < docs[-1]["date"])
        if not docs or ((r.get("n") is not None or dated) and not older):
            if not docs or docs[-1]["first"] != r["page"]:  # a second document on the same first page: the page's first governs
                docs.append({"date": r.get("date"), "insurer": bool(r.get("insurer")) or r.get("from") == "versicherer",
                             "first": r["page"], "n": r.get("n"), "rows": 0})
        docs[-1]["rows"] += 1
    for doc, nxt in zip(docs, docs[1:] + [{"first": pages + 1}]):
        doc["pages"] = list(range(doc["first"], nxt["first"]))
    days = [d["date"] for d in docs]
    for i, doc in enumerate(docs):
        around = [x for x in days[:i] if x][-1:] + [x for x in days[i + 1:] if x][:1]
        if not doc["date"] and around:
            doc["date"] = max(around)
    return docs


def plan(labels, template, pdf):
    """The cut, from the labels and the labels template: the assessment's point (n3); the arrival, the documents not the
    insurer's dated after its last action before n3 and before n3 (D11: the customer's two e-mails of one day); what is left
    out, the documents from the replies' day on, of which only the insurer's own may be dated on n3's day or before it (a
    document of another known on that day would be missing from the base case); the earlier state, every other document.
    Each part is made of whole documents of the template, and every page of the file lies in exactly one part; anything
    else stops the run before it does anything."""
    points = sorted(labels["points"], key=lambda p: (p["date"], p["n"]))
    n3 = next((p for p in points if p["kind"] == "A5"), None)
    if n3 is None:
        raise Stop("cut", "no_assessment_point")
    before = [p for p in points if p["date"] < n3["date"]]
    since = before[-1]["date"] if before else "0000-00-00"  # the insurer's last action before the assessment (the question back)
    pages = int((pdf.get("extraction") or {}).get("pages") or 0)
    rows = [r for r in template.get("documents") or () if r.get("file") in (None, pdf.get("name"))]
    docs, reverse = documents(rows, pages), newest_first(rows)
    replies = [d for d in docs if not d["insurer"] and d["date"] and since < d["date"] < n3["date"]]
    if len(replies) != ARRIVALS:
        raise Stop("cut", "no_reply_found" if not replies else "arrival_not_as_in_the_outline")
    if reverse:
        # latest first, a date cannot tell a reply's own enclosure from an older document that follows it: the replies must
        # stand together and be followed at once by the document of the day they answer (the insurer's question back), so
        # that no page between them and it is of unknown standing
        at = sorted(docs.index(r) for r in replies)
        after = docs[at[-1] + 1] if at[-1] + 1 < len(docs) else None
        if at != list(range(at[0], at[0] + len(at))) or (after is not None and after["date"] != since):
            raise Stop("cut", "arrival_not_followed_by_its_question")
    first = min(r["date"] for r in replies)
    later = [d for d in docs if d not in replies and d["date"] and d["date"] >= first]
    if any(d["date"] < n3["date"] or (d["date"] == n3["date"] and not d["insurer"]) for d in later):
        raise Stop("cut", "another_document_before_the_assessment")
    earlier = [d for d in docs if d not in replies and d not in later]
    cut = {"n3": n3, "base": sorted(p for d in earlier for p in d["pages"]), "arrival": [d["pages"] for d in replies],
           "later": sorted(p for d in later for p in d["pages"]), "entries": [d["n"] for d in replies], "newest_first": reverse,
           "rows": {"base": sum(d["rows"] for d in earlier), "arrival": sum(d["rows"] for d in replies), "later": sum(d["rows"] for d in later)}}
    if sorted(cut["base"] + cut["later"] + [p for a in cut["arrival"] for p in a]) != list(range(1, pages + 1)):
        raise Stop("cut", "pages_not_in_exactly_one_part")
    if not cut["base"] or not 0 < sum(map(len, cut["arrival"])) <= ARRIVAL_PAGES:
        raise Stop("cut", "pages_out_of_bounds")
    return cut


def sealed(cut):
    """The start of the sha256 of the cut: the approval names exactly this plan."""
    body = {"point": cut["n3"]["n"], "as_of": cut["n3"]["date"], "base": cut["base"], "arrival": cut["arrival"], "later": cut["later"]}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:12]


def plan_lines(cut, tree, labels):
    """The plan as the notebook prints it before the run does anything: pages and counts, no content."""
    return [f"The D11 diagnostic, its plan (nothing done but reading): build {tree} · labels {labels} · plan {sealed(cut)}"] + \
           (["  the file lists its documents latest first: the earlier state is its later pages, what is left out its first"] if cut.get("newest_first") else []) + [
            f"  the earlier state: pages {spans(cut['base'])} ({cut['rows']['base']} rows of the labels template), looked at on the day of point {cut['n3']['n']}",
            f"  one full preparation of it; the run stops if it failed or its non-cached input passed {STOP_AFTER_PREPARE:,} tokens:"
            " a stop, never a budget or an allowance",
            f"  the arrival, as the labels template lists it: {len(cut['arrival'])} documents not the insurer's, pages "
            f"{', '.join(spans(a) for a in cut['arrival'])} ({sum(map(len, cut['arrival']))} pages) as one import, then one of them again",
            f"  left out: pages {spans(cut['later']) or 'none'} ({cut['rows']['later']} rows of the labels template, from the replies' day on)",
            "  the deployment's own caps hold throughout: CASEPATH_RUN_TOKEN_BUDGET per run, CASEPATH_UPDATE_TOKEN_BUDGET per update",
            f"  needs, besides the confirm phrase, Navish's separate typed approval of the deployment of build {tree} to the pilot"
            f" and of this run's tokens: {ESTIMATE}"]


def spans(pages):
    """[1, 2, 3, 7] → «1-3,7», as the cut route reads pages."""
    out, start = [], None
    for i, p in enumerate(pages):
        if start is None:
            start = p
        if i + 1 == len(pages) or pages[i + 1] != p + 1:
            out.append(f"{start}-{p}" if p != start else str(p))
            start = None
    return ",".join(out)


def wait(api, run_id, timeout, poll):
    """The run once it ended; one that has not ended in time is stopped («Anhalten») and returned as it stands."""
    started = time.monotonic()
    run = api.call("GET", f"/api/runs/{run_id}")
    while run.get("status") in ("queued", "running") and time.monotonic() - started < timeout:
        time.sleep(poll)
        run = api.call("GET", f"/api/runs/{run_id}")
    if run.get("status") in ("queued", "running"):
        api.call("POST", f"/api/runs/{run_id}/stop")
    return run


def kind(value):
    """An action kind as a receipt holds it, in lower case (a5)."""
    return str(value).lower() if value else None


def run_row(run):
    """A run as the receipt holds it: id, kind, status, seconds, pages read by a model, usage per agent."""
    usage = {}
    for u in (run.get("result") or {}).get("usage") or ():
        row = usage.setdefault(re.sub(r"[^a-z0-9_]", "_", str(u.get("agent") or "model").lower()), {"calls": 0, "input": 0, "cached": 0, "non_cached": 0, "output": 0})
        row["calls"] += 1
        row["input"] += int(u.get("input_tokens") or 0)
        row["cached"] += int(u.get("cached_tokens") or 0)
        row["output"] += int(u.get("output_tokens") or 0)
        row["non_cached"] = row["input"] - row["cached"]
    try:
        seconds = round((datetime.fromisoformat(run["finished_at"]) - datetime.fromisoformat(run["created_at"])).total_seconds())
    except (KeyError, TypeError, ValueError):
        seconds = None
    return {"id": run.get("id"), "kind": run.get("kind") or "full", "status": run.get("status"), "seconds": seconds,
            "pages_read": (usage.get("reader") or {}).get("calls", 0), "usage": usage,
            "non_cached": sum(u["non_cached"] for u in usage.values()), "output": sum(u["output"] for u in usage.values())}


def state_of(question):
    return str(question.get("state") or question.get("answer_state") or "").replace("ü", "ue") or None


def row_of(question):
    if isinstance(question.get("row"), int):
        return question["row"]
    reason = str(question.get("reason") or "")
    return next((n for n, start in ROWS if reason.startswith(start)), None)


def read_case(detail, update_run, full_run, missing):
    """What the receipt holds of the case after the update, from the slices' fields where the build has them; each field
    the build does not give is named in ``missing``, never filled in."""
    result = (update_run or {}).get("result") or {}
    brief = result.get("brief") or {}
    assessment = detail.get("assessment")
    if assessment is None:
        missing.append("assessment")
        assessment = {}
    questions = assessment.get("questions")
    if questions is None:
        missing.append("assessment.questions")
        questions = brief.get("questions") or []
    claims = brief.get("claims")
    if claims is None:
        missing.append("brief.claims")
        claims = []
    ledger = (result.get("update") or {}).get("ledger")
    if ledger is None:
        missing.append("update.ledger")
    count = lambda *keys: next((len(ledger[k]) if isinstance(ledger[k], list) else int(ledger[k]) for k in keys if (ledger or {}).get(k) is not None), None)
    record, prior = result.get("record") or {}, ((full_run or {}).get("result") or {}).get("record") or {}
    dropped = brief.get("dropped_tags")
    rows = [row_of(q) for q in questions]
    action = next((i for i in detail.get("items") or () if i.get("kind") == "next_action"), {})
    text = (detail.get("draft") or {}).get("text") or ""
    return {
        "update": {"new_entries": len((result.get("update") or {}).get("entries") or ()), "dropped": int(record.get("dropped") or 0) - int(prior.get("dropped") or 0),
                   "elsewhere": int(record.get("elsewhere") or 0) - int(prior.get("elsewhere") or 0),
                   "facts_changed": sorted((result.get("update") or {}).get("facts") or ())},
        "questions": {"found": len(questions), "tagged": sum(1 for q in questions if q.get("about")),
                      "tags_dropped": len(dropped) if isinstance(dropped, list) else int(dropped or 0),
                      "rows": [r if r is not None else 0 for r in rows], "guard_rows": sorted({r for r in rows if r in GUARD_ROWS}),
                      "states": {s: sum(1 for q in questions if state_of(q) == s) for s in ("beantwortet", "bedingt", "offen", "pruefen")},
                      "intents": sorted({q["intent"] for q in questions if q.get("intent")})},
        "claims": {"found": len(claims), "checked": sum(1 for c in claims if c.get("checked")), "amount_kept": sum(1 for c in claims if c.get("amount")),
                   "documented": sum(1 for c in claims if c.get("documented"))},
        "ledger": {"closed": count("closed"), "held": sum(1 for r in (ledger or {}).get("closed") or () if isinstance(r, dict) and r.get("held")),
                   "refused": count("refused", "refusals"), "partial": count("partial"), "promised": count("promised"),
                   "unspecified": count("unspecified")},
        "decision": sorted({b.get("key") for b in assessment.get("blocking") or () if b.get("kind") == "decision" and b.get("key")}),
        "proposal": list(assessment.get("proposal") or []),
        "residual": {"keys": [r.get("key") for r in assessment.get("residual") or ()], "count": len(assessment.get("residual") or ())},
        "gaps": text.count(GAP), "next_action": kind(action.get("action"))}


def replay_of(row):
    """The narrow score and the expanded acceptance of n3, as the replay gives them (both content-free)."""
    if not row:
        return None
    accept = row.get("accept") or {}
    pick = lambda block, keys: {k: (block or {}).get(k) for k in keys}
    return {"narrow": {"kind": kind(row.get("kind")), "kind_ok": row.get("kind_ok"), "ready": row.get("ready"),
                       **pick(row.get("documents"), ("hits", "missed", "extras"))},
            "accept": {"recipient": (accept.get("recipient") or {}).get("ok"),
                       "residual": pick(accept.get("residual"), ("hits", "missed", "extras", "ok")),
                       "questions": pick(accept.get("questions"), ("beantwortet", "bedingt", "offen", "pruefen", "label", "ok")),
                       "substantive": pick(accept.get("substantive"), ("present", "gaps", "status")),
                       "authority": pick(accept.get("authority"), ("missing", "ok"))}}


def located(api):
    """Read only: D11's case id and labels; AssertionError, nothing done, unless the replay's table names exactly one case."""
    try:
        return find(api)
    except Stop as stop:
        raise AssertionError(f"{stop.args[1]}: nothing done") from None


def cut_of(api, case_id, labels):
    """Read only: D11's one PDF and the cut its labels template gives; AssertionError, nothing done, where it gives none."""
    try:
        files = [f for f in api.call("GET", f"/api/cases/{case_id}").get("files") or () if f.get("kind") == "pdf"]
        if len(files) != 1:
            raise Stop("cut", "not_one_pdf")
        return files[0], plan(labels, api.call("GET", f"/api/cases/{case_id}/labels-template"), files[0])
    except Stop as stop:
        raise AssertionError(f"{stop.args[1]}: nothing done") from None


def diagnose(api, volume, tree, wanted, approved_plan, keep, poll=10, prepare_timeout=2700, update_timeout=1800):
    """The run (steps 1 to 7) on exactly the approved build, labels and cut; the receipt, also when it stops."""
    manifest = api.call("GET", "/api/manifest")
    if not str(manifest.get("source_tree_sha256") or "").startswith(tree):
        raise AssertionError("the running build is not the one approved: nothing done")
    case_id, labels = located(api)
    signed = labels_sha256(labels)
    if not signed.startswith(wanted):
        raise AssertionError("D11's labels are not the ones approved: nothing done")
    path = f"{volume.rstrip('/')}/diagnose/{DOSSIER}-{signed[:12]}.json"
    if os.path.exists(path):
        print(f"already run: {path} holds its receipt; nothing done")
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    pdf, cut = cut_of(api, case_id, labels)
    print("\n".join(plan_lines(cut, tree, signed[:12])))
    if sealed(cut) != approved_plan:
        raise AssertionError("the cut is not the approved plan: nothing done")
    receipt = {"format": FORMAT, "dossier": DOSSIER.lower(), "build": tree, "labels": signed[:12], "plan": approved_plan, "status": "started", "stopped": None, "base": None,
               "kept": keep, "cut": None, "arrival": None, "runs": [], "auto": None, "duplicate_refused": None, "decisions": [], "case": None,
               "n3": None, "missing": [], "model_calls_here": 0}

    def save():
        content_free({k: v for k, v in receipt.items() if k != "format"})
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, sort_keys=True)

    save()  # from here on, the run counts as made: no second one without a new approval
    try:
        try:
            # 1 the cut: the earlier state of the approved plan, looked at on the assessment's day
            n3, base_pages, replies = cut["n3"], cut["base"], cut["arrival"]
            receipt["cut"] = {"point": n3["n"], "pages": len(base_pages), "left_out": len(cut["later"])}
            receipt["arrival"] = {"files": len(replies), "pages": sum(map(len, replies))}
            try:
                base = api.call("POST", f"/api/cases/{case_id}/cut", {"pages": spans(base_pages), "as_of": n3["date"], "file": pdf["id"]})["id"]
            except ApiError:
                raise Stop("cut", "refused") from None
            receipt["base"] = base
            save()
            # 2, 3 one full preparation, stopped on failure or past the stop threshold (a stop, never a budget)
            full = wait(api, api.call("POST", f"/api/cases/{base}/runs")["id"], prepare_timeout, poll)
            receipt["runs"].append(run_row(full))
            save()
            if full.get("status") != "completed":
                raise Stop("prepare", "failed" if full.get("status") in ("failed", "interrupted", "discarded") else "not_finished")
            if receipt["runs"][-1]["non_cached"] > STOP_AFTER_PREPARE:  # a stop, never a budget
                raise Stop("prepare", "past_the_stop_threshold")
            # 4 the arrival: the replies' pages as one import, then one of them again
            uploads = [(f"Antwort-{i}.pdf", api.raw(f"/api/files/{pdf['id']}/original?pages={spans(pages)}")) for i, pages in enumerate(replies, 1)]
            status, answer = api.upload(base, uploads)
            if status != 201:
                raise Stop("arrival", "upload_refused")
            receipt["auto"] = answer.get("auto") if SAFE.match(str(answer.get("auto") or "")) else "other"
            again, _ = api.upload(base, uploads[:1])
            receipt["duplicate_refused"] = again == 409
            started = (answer.get("run") or {}).get("id") if receipt["auto"] == "gestartet" else None
            if again != 409:  # a duplicate that is not refused is a fault of its own: no update is spent on it
                if started:
                    api.call("POST", f"/api/runs/{started}/stop")
                raise Stop("arrival", "duplicate_accepted")
            update = wait(api, started or api.call("POST", f"/api/cases/{base}/update")["id"], update_timeout, poll)
            receipt["runs"].append(run_row(update))
            save()
            if update.get("status") != "completed":
                raise Stop("update", "failed" if update.get("status") in ("failed", "interrupted", "discarded", "stopped") else "not_finished")
            # 5 the handler's decisions in force on the assessment's day
            for d in sorted((d for d in labels.get("decisions") or () if d["from"] <= n3["date"]), key=lambda d: d["from"]):
                api.call("POST", f"/api/cases/{base}/edits", {"op": "set_fact", "args": {"fact": d["fact"], "value": d["value"]},
                                                              "reason": f"Entscheid der Fallbearbeitung laut Labels (Punkt {n3['n']})", "recheck": False})
                receipt["decisions"].append(d["fact"])
            # 6 the case and the replay of n3
            receipt["case"] = read_case(api.call("GET", f"/api/cases/{base}"), update, full, receipt["missing"])
            api.call("POST", f"/api/cases/{base}/labels", {"format": labels.get("format"), "dossier": DOSSIER, "case": base,
                                                           "decisions": [d for d in labels.get("decisions") or () if d["from"] <= n3["date"]],
                                                           "points": [n3]})
            row = next((r for r in api.call("GET", f"/api/replay-points?case={base}").get("rows") or () if r.get("n") == n3["n"]), None)
            receipt["n3"] = replay_of(row)
            receipt["status"] = "done"
        except Stop as stop:
            receipt["status"], receipt["stopped"] = "stopped", {"step": stop.args[0], "reason": stop.args[1]}
        except ApiError as error:
            receipt["status"], receipt["stopped"] = "stopped", {"step": "api", "reason": f"http_{error.status}"}
    finally:
        # 7 the base case goes, unless it is kept for the inside review
        if receipt["base"] and not keep:
            try:
                api.call("DELETE", f"/api/cases/{receipt['base']}")
            except ApiError as error:
                receipt["missing"].append(f"deleted:http_{error.status}")
        save()
    return receipt


def hashes(api):
    """Read only: the plan and the phrase that approves exactly it (the running build, D11's labels, the cut)."""
    tree = str(api.call("GET", "/api/manifest").get("source_tree_sha256") or "")[:12]
    case_id, labels = located(api)
    _, cut = cut_of(api, case_id, labels)
    out = {"build": tree, "labels": labels_sha256(labels)[:12], "plan": sealed(cut), "case": case_id}
    print("\n".join(plan_lines(cut, tree, out["labels"]) + [f"approval reads: diagnose {DOSSIER} {out['build']} {out['labels']} {out['plan']}"]))
    return out


def main(phrase, app, volume, environ):
    """The cell: refuses before any request unless the phrase is one of the two; the identity comes from ``environ``."""
    mode, tree, wanted, approved_plan, keep = parse(phrase)
    assert not app.startswith("FILL-IN") and not volume.startswith("FILL-IN"), "fill in APP and VOLUME in this cell first"
    header, identity = environ.get("CASEPATH_EVAL_IDENTITY_HEADER"), environ.get("CASEPATH_EVAL_IDENTITY")
    assert header and identity, "the identity the app expects: CASEPATH_EVAL_IDENTITY_HEADER and CASEPATH_EVAL_IDENTITY in the environment"
    api = Api(app, {header: identity})
    if mode == "hashes":
        return hashes(api)
    receipt = diagnose(api, volume, tree, wanted, approved_plan, keep)
    print(json.dumps(receipt, sort_keys=True))
    return receipt


if "dbutils" in globals():
    main(dbutils.widgets.get("confirm"), APP, VOLUME, os.environ)  # noqa: F821  (Databricks provides dbutils)
