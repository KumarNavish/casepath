# The one cell of the "casepath diagnose" notebook: the one diagnostic run of the D11 episode on the pilot (MEASURE §3), an
# act task that needs Navish's typed approval. Standard library only; it calls the deployed app's API as the benchmark
# does (quality/evaluate.py, RemoteApi), never a model itself. It reads one notebook parameter, "confirm" (made with
# Edit > Add parameter):
#   hashes D11                                 read only: prints the running build's hash and the hash of D11's labels
#   diagnose D11 <tree hash> <labels sha256>   the run, on exactly that build and those labels (12 hex digits each)
#   diagnose D11 <tree hash> <labels sha256> keep    the same, keeping the base case for the inside review
# Anything else: nothing happens, no request is made. <tree hash> is the start of /api/manifest's source_tree_sha256;
# <labels sha256> the start of the sha256 of D11's labels as stored (sorted keys, compact JSON).
# The run, in this order, each step only if the one before succeeded; no retry, no second run (its receipt on the volume
# marks it done or stopped; a new run needs that file removed and a new approval):
#   1 cut D11 to the pages known before the customer's replies, looked at on the assessment's day (label n3);
#   2 prepare that base case once (a full preparation);
#   3 stop if it failed or used more than 200,000 non-cached input tokens;
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
PREPARE_CAP = 200_000  # the full preparation's non-cached input tokens, checked between steps (the soft cap)
ARRIVAL_PAGES = 20  # as CASEPATH_AUTO_UPDATE_MAX_PAGES: an arrival larger than this is not this run
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
    """("hashes", None, None, False) or ("diagnose", tree, labels, keep); AssertionError for anything else."""
    phrase = (phrase or "").strip()
    if phrase == f"hashes {DOSSIER}":
        return "hashes", None, None, False
    match = re.fullmatch(rf"diagnose {DOSSIER} ([0-9a-f]{{12}}) ([0-9a-f]{{12,64}})( keep)?", phrase)
    assert match, f"confirm must read: diagnose {DOSSIER} <tree hash> <labels sha256> [keep], or hashes {DOSSIER}"
    return "diagnose", match.group(1), match.group(2), bool(match.group(3))


def find(api):
    """D11's case id and labels, from the replay's content-free table: exactly one case labelled D11."""
    cases = sorted({r["case"] for r in api.call("GET", "/api/replay-points").get("rows") or () if r.get("dossier") == DOSSIER})
    if len(cases) != 1:
        raise Stop("find", "no_labelled_case" if not cases else "several_labelled_cases")
    return cases[0], api.call("GET", f"/api/cases/{cases[0]}/labels")


def documents(rows, pages):
    """The PDF's documents in page order, from the labels template's rows (each with its first page): an account entry starts
    a document, and so does a later-dated document the reader gave no entry; an undated or older one (an enclosure, a lease
    sent along) belongs to the document before it, as quality/asof.py dates pages. Each runs to the next one's first page."""
    docs = []
    for r in sorted((r for r in rows if isinstance(r.get("page"), int)), key=lambda r: (r["page"], r.get("n") is None)):
        entry = r.get("n") is not None
        if not docs or entry or (r.get("date") and (not docs[-1]["date"] or r["date"] > docs[-1]["date"])):
            if docs and docs[-1]["first"] == r["page"]:
                continue  # a second document on the same first page: the page's first governs
            docs.append({"date": r.get("date"), "from": r.get("from"), "first": r["page"]})
    for doc, nxt in zip(docs, docs[1:] + [{"first": pages + 1}]):
        doc["pages"] = list(range(doc["first"], nxt["first"]))
    return docs


def plan(labels, template, pdf):
    """From the labels and the labels template: the assessment's point (n3), the pages known before the customer's replies
    (those after the insurer's last action before n3 and before n3), and each reply's pages."""
    points = sorted(labels["points"], key=lambda p: (p["date"], p["n"]))
    n3 = next((p for p in points if p["kind"] == "A5"), None)
    if n3 is None:
        raise Stop("cut", "no_assessment_point")
    before = [p for p in points if p["date"] < n3["date"]]
    since = before[-1]["date"] if before else "0000-00-00"  # the insurer's last action before the assessment (the question back)
    pages = int((pdf.get("extraction") or {}).get("pages") or 0)
    docs = documents([r for r in template.get("documents") or () if r.get("file") in (None, pdf.get("name"))], pages)
    replies = [d for d in docs if d["from"] == "kunde" and d["date"] and since < d["date"] < n3["date"]]
    if not replies:
        raise Stop("cut", "no_reply_found")
    later = {p for d in docs if d["date"] and d["date"] >= min(r["date"] for r in replies) for p in d["pages"]}
    base = [p for p in range(1, pages + 1) if p not in later]
    arriving = sum(len(r["pages"]) for r in replies)
    if not base or not 0 < arriving <= ARRIVAL_PAGES:
        raise Stop("cut", "pages_out_of_bounds")
    return n3, base, [r["pages"] for r in replies]


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


def diagnose(api, volume, tree, wanted, keep, poll=10, prepare_timeout=2700, update_timeout=1800):
    """The run (steps 1 to 7); the receipt, also when it stops."""
    manifest = api.call("GET", "/api/manifest")
    if not str(manifest.get("source_tree_sha256") or "").startswith(tree):
        raise AssertionError("the running build is not the one approved: nothing done")
    try:
        case_id, labels = find(api)
    except Stop as stop:
        raise AssertionError(f"{stop.args[1]}: nothing done") from None
    signed = labels_sha256(labels)
    if not signed.startswith(wanted):
        raise AssertionError("D11's labels are not the ones approved: nothing done")
    path = f"{volume.rstrip('/')}/diagnose/{DOSSIER}-{signed[:12]}.json"
    if os.path.exists(path):
        print(f"already run: {path} holds its receipt; nothing done")
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    receipt = {"format": FORMAT, "dossier": DOSSIER.lower(), "build": tree, "labels": signed[:12], "status": "started", "stopped": None, "base": None,
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
            # 1 the cut: the pages known before the replies, looked at on the assessment's day
            files = [f for f in api.call("GET", f"/api/cases/{case_id}").get("files") or () if f.get("kind") == "pdf"]
            if len(files) != 1:
                raise Stop("cut", "not_one_pdf")
            pdf = files[0]
            n3, base_pages, replies = plan(labels, api.call("GET", f"/api/cases/{case_id}/labels-template"), pdf)
            receipt["cut"] = {"point": n3["n"], "pages": len(base_pages)}
            receipt["arrival"] = {"files": len(replies), "pages": sum(map(len, replies))}
            try:
                base = api.call("POST", f"/api/cases/{case_id}/cut", {"pages": spans(base_pages), "as_of": n3["date"], "file": pdf["id"]})["id"]
            except ApiError:
                raise Stop("cut", "refused") from None
            receipt["base"] = base
            save()
            # 2, 3 one full preparation, stopped on failure or past the soft cap
            full = wait(api, api.call("POST", f"/api/cases/{base}/runs")["id"], prepare_timeout, poll)
            receipt["runs"].append(run_row(full))
            save()
            if full.get("status") != "completed":
                raise Stop("prepare", "failed" if full.get("status") in ("failed", "interrupted", "discarded") else "not_finished")
            if receipt["runs"][-1]["non_cached"] > PREPARE_CAP:
                raise Stop("prepare", "over_soft_cap")
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
    """Read only: the running build's hash and the hash of D11's labels, to name in the approval."""
    tree = str(api.call("GET", "/api/manifest").get("source_tree_sha256") or "")[:12]
    try:
        case_id, labels = find(api)
    except Stop as stop:
        raise AssertionError(f"{stop.args[1]}: nothing done") from None
    out = {"build": tree, "labels": labels_sha256(labels)[:12], "case": case_id}
    print(f"approval reads: diagnose {DOSSIER} {out['build']} {out['labels']}")
    return out


def main(phrase, app, volume, environ):
    """The cell: refuses before any request unless the phrase is one of the two; the identity comes from ``environ``."""
    mode, tree, wanted, keep = parse(phrase)
    assert not app.startswith("FILL-IN") and not volume.startswith("FILL-IN"), "fill in APP and VOLUME in this cell first"
    header, identity = environ.get("CASEPATH_EVAL_IDENTITY_HEADER"), environ.get("CASEPATH_EVAL_IDENTITY")
    assert header and identity, "the identity the app expects: CASEPATH_EVAL_IDENTITY_HEADER and CASEPATH_EVAL_IDENTITY in the environment"
    api = Api(app, {header: identity})
    if mode == "hashes":
        return hashes(api)
    receipt = diagnose(api, volume, tree, wanted, keep)
    print(json.dumps(receipt, sort_keys=True))
    return receipt


if "dbutils" in globals():
    main(dbutils.widgets.get("confirm"), APP, VOLUME, os.environ)  # noqa: F821  (Databricks provides dbutils)
