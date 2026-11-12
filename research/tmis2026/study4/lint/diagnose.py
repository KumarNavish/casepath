"""Diagnosis of the clean-arm errors (study4 step 2d, follow-up). DEVELOPMENT, post hoc, not a result. No model calls.

    python3 -I -B study4/lint/diagnose.py            # writes DIAGNOSIS.json and DIAGNOSIS.md
    python3 -I -B study4/lint/diagnose.py --arm-suffix _rev1 --rules rev1   # the same on a revised re-run (part C)

Reads only stored material: the clean-arm results and run records (runs/results_clean_<regime>_gpt-6-luna.json,
runs/records/), the cached reading responses (runs/cache/), each file's design.json, reference.json and text, the rule
sets the runs read (rules/<regime>/rev0/: rules.json and workflow/), and the product's own evaluator
(casepath/process/workflows.py at the tested commit, imported read-only from the worktree). Judgments that need a
reading of the file text are not made here: they are read from diagnosis_review.json (written by reading the files and
the readings; every judgment there names its file and its reason).

Attribution rule (one cause per error; an error is a (file, document, kind) of lint/analyse.py's part (d) scoring):

1. Routing. The run was handed over unrouted (deferred) or routed to another type: every error of the file is a routing
   error, split by whether the file's defining event is stated false (denied-event file).
2-4. The file was routed to its type. Three replays through the product's evaluator (workflows.evaluate with checked=True,
   the inputs built as the product builds them: accepted established facts plus applicable presumptions; findings =
   documents present or unusable with an accepted verdict):
   D  = designed fact states + designed attachment states (exactly as generator/reference.py builds the reference);
   PD = the product's fact states + designed attachment states;
   DP = designed fact states + the product's document findings;
   PP = the product's facts and findings (must reproduce the stored plan; checked).
   If D already differs from reference.json for the document: cause 4 (workflow differs from reference).
   Else if PD shows the error and DP does not: cause 2 (fact reading). Else if DP shows the error and PD does not:
   cause 3 (document judgment). If both show it: each alone suffices; counted under cause 2 and flagged "also document".
   If neither shows it but PP does: the two together; counted under cause 2 and flagged "joint".
   The fact named for cause 2 is the fact whose correction alone (product state replaced by the designed state, all other
   product states kept, designed attachments) removes the error; where several do, the first in workflow order is named
   and the others listed; where none alone does, "several facts jointly".
   What the product did with the fact, from its recorded state and the three stored reading responses:
   - admitted the wrong value: established (all readings agreed, quotations located) a value other than the designed one;
   - readings disagreed and it held although the file states the fact: designed stated, product unresolved, and at least
     one reading gave the designed value or answered open (sub-pattern: the three verdicts);
   - read a stated fact as not stated: designed stated, and no reading gave a value or answered open (a presumption,
     where the fact has one, then filled the other value);
   - read an open fact as settled: designed open, product established a value or a presumption filled it;
   - read an unmentioned fact as open: designed not mentioned, product unresolved (a reading gave a value or answered
     open, so no presumption filled it).
5. Scoring convention: a need outside the type's catalogue (a process-builder addition) or an optional document. (On
   these runs the process builder added nothing and no optional document produced an error; the class is kept for the
   rule's completeness and for the revised re-run.)
6. Text and recorded state plausibly disagree: a cause-2 error is moved here when (a) the file was kept as read and the
   blind check changed this fact's state (design.json facts_designed) and the product's reading matches the original
   design, or (b) diagnosis_review.json records, after reading the file text, that the passage the readings quoted
   plausibly states what the product read (the judgment and its reason are listed).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
S4 = HERE.parent
sys.path[:0] = [str(HERE), str(S4 / "generator")]
import analyse as A  # noqa: E402
import genlib as G  # noqa: E402

PRODUCT = "/home/user/work/casepath-sync-e/casepath-internal"
sys.path.insert(0, PRODUCT)
from casepath.process import workflows as W  # noqa: E402  (read-only import of the product's evaluator)
from casepath.read.evidence import Evidence  # noqa: E402  (the product's own word-for-word quote location)

REGIMES = A.REGIMES
KINDS = A.KINDS
CAUSES = ["routing_denied", "routing_not_denied", "fact_reading", "document_judgment", "workflow_vs_reference",
          "scoring_convention", "text_state_disagree"]
CAUSE_LABEL = {"routing_denied": "routing failure, denied-event file", "routing_not_denied": "routing failure, other file",
               "fact_reading": "fact reading", "document_judgment": "supplied-document judgment",
               "workflow_vs_reference": "workflow differs from reference (same states)",
               "scoring_convention": "scoring convention", "text_state_disagree": "text and recorded state plausibly disagree"}
SUB_LABEL = {"admitted_wrong_value": "admitted the wrong value",
             "readings_disagreed_held": "readings disagreed and it held although the file states the fact",
             "read_stated_as_not_stated": "read a stated fact as not stated",
             "read_open_as_settled": "read an open fact as settled",
             "read_unmentioned_as_open": "read an unmentioned fact as open",
             "several_facts": "several facts jointly"}
SHORT = 160


def short(s, n=SHORT):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


# ------------------------------------------------------------------------------------------------- replay
def doc_states(regime, tid, facts, findings):
    """Reference-style state of each catalogue document under the given facts and findings (generator/reference.py's
    mapping, the product's evaluator)."""
    wf = regime.workflows[tid]
    ev = W.evaluate(wf, facts, findings, checked=True)
    rows = {r["document"]: r for r in ev["documents"]}
    out = {}
    for d in regime.documents(tid):
        r = rows.get(d["id"])
        if r is None:
            out[d["id"]] = ("not_needed", None)
        elif r["required"] in ("optional", "suggested"):
            out[d["id"]] = ({"present": "present_sufficient", "unusable": "present_insufficient"}.get(r["status"], "not_needed"), "optional")
        elif r["required"] == "depends":
            out[d["id"]] = ("hold", tuple(sorted(r.get("condition_facts") or [])))
        else:
            out[d["id"]] = ({"present": "present_sufficient", "unusable": "present_insufficient"}.get(r["status"], "request"), None)
    return out, ev


def plan_of(states):
    req = {d for d, (s, extra) in states.items() if extra != "optional" and s in ("request", "present_insufficient")}
    hold = {d for d, (s, _) in states.items() if s == "hold"}
    return req, hold


def doc_error(ref_entry, d, req, hold):
    """analyse.score_file's rule for one catalogue document."""
    st = ref_entry["state"]
    if st == "hold":
        return None if d in hold else "missed_hold"
    if ref_entry.get("request"):
        return None if d in req else ("unwarranted_hold" if d in hold else "missed_request")
    return "unneeded_request" if d in req else ("unwarranted_hold" if d in hold else None)


def designed_inputs(regime, design):
    """As generator/reference.py: stated -> established; not mentioned -> the workflow's presumption through the product's
    presumed(); open -> raised and left open; attachments: sufficient -> present, insufficient -> unusable."""
    tid = design["type"]
    wf = regime.workflows[tid]
    rf, rv = regime.routing_fact(tid)
    facts = {rf: rv} if rf else {}
    recorded = {}
    for f, s in design["facts"].items():
        if s in ("stated_true", "stated_false"):
            facts[f] = s == "stated_true"
            recorded[f] = {"status": "established", "value": facts[f]}
        elif s == "open":
            recorded[f] = {"status": "unknown", "readings": [None, None], "open_readings": [True, True],
                           "citations": [{"quote": "(designed: raised and left open)"}]}
    filled = W.presumed(wf, recorded)
    for f, s in design["facts"].items():
        if s == "not_mentioned" and f in filled:
            facts[f] = filled[f]["value"]
    findings = {a["document"]: {"status": "present" if a["sufficient"] else "unusable", "verdict": "accepted"}
                for a in design["attachments"] if a["supplied"]}
    return facts, findings


def product_inputs(res):
    """What the product's evaluation rested on (team.accepted_facts / document_inputs)."""
    facts = {}
    for row in res.get("facts", []):
        if (row["status"] == "established" and row.get("verdict") == "accepted") or row["status"] == "presumed":
            facts[row["fact"]] = row["value"]
    findings = {d["document"]: {"status": d["status"], "verdict": "accepted"} for d in res.get("documents", [])
                if d["status"] in ("present", "unusable") and d.get("verdict") == "accepted"}
    return facts, findings


def designed_supply(design):
    return {a["document"]: ("sufficient" if a["sufficient"] else "insufficient") for a in design["attachments"] if a["supplied"]}


def product_supply(res):
    out = {}
    for d in res.get("documents", []):
        eff = d["status"] if d["status"] in ("present", "unusable") and d.get("verdict") == "accepted" else "missing"
        out[d["document"]] = {"effective": eff, "status": d["status"], "verdict": d.get("verdict")}
    return out


# ------------------------------------------------------------------------------------------------- quote location
_EV = {}


def evidence(regime, fid, clean=False):
    """The product's Evidence over the file as uploaded (text.txt and attachments/<doc>.txt), or over the clean text
    beside it (text.clean.txt, attachments/<doc>.clean.txt) to see whether scan noise is what a quotation missed."""
    key = (regime, fid, clean)
    if key not in _EV:
        d = S4 / "dev" / regime / "final" / fid
        rows = [{"id": "text", "text": (d / ("text.clean.txt" if clean else "text.txt")).read_text(encoding="utf-8")}]
        if (d / "attachments").is_dir():
            for pth in sorted((d / "attachments").glob("*.txt")):
                if pth.name.endswith(".clean.txt") != clean:
                    continue
                rows.append({"id": pth.name, "text": pth.read_text(encoding="utf-8")})
        _EV[key] = Evidence(rows)
    return _EV[key]


def located(regime, fid, quote, clean=False):
    ev = evidence(regime, fid, clean)
    return bool(quote) and any(ev.locate(f, quote) for f in ev.files)


def held_pattern(regime, fid, state, verdicts, quotes):
    """Why a stated fact stayed unresolved, from the three stored reading responses: 'quotation not found' when every
    reading gave the designed value and at least one quotation is not found word for word in the file as uploaded (with
    whether it is found in the clean text, i.e. the reading corrected scan noise); otherwise the verdict pattern."""
    want = {"stated_true": "true", "stated_false": "false"}.get(state)
    if want and verdicts and all(v == want for v in verdicts):
        miss = [q for q in quotes if not located(regime, fid, q)]
        if miss:
            in_clean = sum(1 for q in miss if located(regime, fid, q, clean=True))
            noisy = A.files(regime)[fid]["meta"]["scan_noise"]
            how = (f"{in_clean} of them found in the clean text: the reading corrected the scan noise" if in_clean else
                   "found in neither the uploaded nor the clean text: the reading altered the words (a corrected noisy "
                   "character, a capital letter, joined words)" if noisy else
                   "the reading altered the words (a capital letter at the start of a quoted part sentence, or other wording)")
            return f"every reading gave the designed value; {len(miss)} quotation(s) not found word for word ({how})"
        return "every reading gave the designed value with a located quotation (held by the product's combination step)"
    c = Counter(v or "no answer" for v in verdicts)
    return "verdicts " + ", ".join(f"{k} {n}" for k, n in sorted(c.items()))


# ------------------------------------------------------------------------------------------------- what the product did
def verdict_rows(entry, wf):
    ids = {f["id"] for f in wf["facts"]}
    return A.readings(entry, ids)


def fact_sub(state, row, verdicts):
    """Classify what the product did with a fact whose designed state is ``state``."""
    status = (row or {}).get("status")
    value = (row or {}).get("value")
    vs = [v for v in verdicts if v is not None]
    if state in ("stated_true", "stated_false"):
        want = state == "stated_true"
        if status == "established":
            return "admitted_wrong_value" if value != want else None
        if status == "presumed":
            return "read_stated_as_not_stated" if value != want else None
        if any(v in ("true", "false", "open") for v in vs):
            return "readings_disagreed_held"
        return "read_stated_as_not_stated"
    if state == "open":
        return "read_open_as_settled" if status in ("established", "presumed") else None
    if state == "not_mentioned":
        if status == "established":
            return "admitted_wrong_value"
        if status in ("unknown", "conflicting", None):
            return "read_unmentioned_as_open"
    return None


def state_of_product(row):
    """The product's fact state in the design's vocabulary (for cause 6 (a))."""
    if not row:
        return None
    if row["status"] == "established":
        return "stated_true" if row["value"] is True else "stated_false" if row["value"] is False else None
    if row["status"] == "presumed":
        return "not_mentioned"
    return "open"


# ------------------------------------------------------------------------------------------------- per regime
def diagnose_regime(regime_name, arm="clean", rules_sub="rev0", model=A.MODEL, review=None, review_docs=None):
    regime = G.Regime(regime_name, S4 / "rules" / regime_name / rules_sub)
    F = A.files(regime_name)
    R = A.results(arm, regime_name, model)
    review = review or {}
    rows, files_out, checks = [], {}, Counter()
    for fid, x in F.items():
        design, ref, meta = x["design"], x["reference"], x["meta"]
        tid = design["type"]
        e = R.get(fid)
        s = A.score_file(x, e, None)
        base = {"regime": regime_name, "file": fid, "type": tid, "level": meta["level"], "denied_event": meta["denied_event"],
                "open_fact": bool(meta["open_facts"]), "kept": meta["kept"], "scan_noise": meta["scan_noise"]}
        fo = dict(base, errors=s["total"], routed=s["routed"], failed=s["failed"], routing_failure=s["routing_failure"])
        files_out[fid] = fo
        if s["failed"]:
            for d in s["detail"]:
                rows.append(dict(base, document=d["document"], kind=d["error"], cause="failed_run"))
            continue
        if s["routing_failure"]:
            cause = "routing_denied" if meta["denied_event"] else "routing_not_denied"
            for d in s["detail"]:
                rows.append(dict(base, document=d["document"], kind=d["error"], cause=cause, routed=s["routed"]))
            continue
        rec = A.record(e)
        res = rec["case"]["run"]["result"]
        wf = regime.workflows[tid]
        Df, Dd = designed_inputs(regime, design)
        Pf, Pd = product_inputs(res)
        D, _ = doc_states(regime, tid, Df, Dd)
        PD, _ = doc_states(regime, tid, Pf, Dd)
        DP, _ = doc_states(regime, tid, Df, Pd)
        PP, _ = doc_states(regime, tid, Pf, Pd)
        req, hold = plan_of(PP)
        stored = e["plan"]
        same = req == set(stored.get("requests") or []) and hold == set(stored.get("holds") or [])
        checks["replay_reproduces_stored_plan" if same else "replay_differs_from_stored_plan"] += 1
        for d, (st, extra) in D.items():
            r = ref["documents"][d]
            ok = st == r["state"] and (st != "hold" or list(extra) == r.get("waits_for"))
            checks["designed_replay_equals_reference" if ok else "designed_replay_differs"] += 1
        frow = {r["fact"]: r for r in res.get("facts", [])}
        rds = verdict_rows(e, wf)
        fact_order = [f["id"] for f in wf["facts"] if f["id"] != regime.routing_fact(tid)[0]]
        dsupply, psupply = designed_supply(design), product_supply(res)
        for det in s["detail"]:
            d, kind = det["document"], det["error"]
            row = dict(base, document=d, kind=kind)
            r = ref["documents"].get(d)
            if r is None:
                row.update(cause="scoring_convention", sub="need outside the catalogue")
                rows.append(row)
                continue
            dst = D[d]
            if dst[0] != r["state"] or (dst[0] == "hold" and list(dst[1]) != r.get("waits_for")):
                row.update(cause="workflow_vs_reference", designed_replay=dst[0], reference=r["state"])
                rows.append(row)
                continue
            if regime.optional(tid, d):
                row.update(cause="scoring_convention", sub="optional document")
                rows.append(row)
                continue
            e_pd = doc_error(r, d, *plan_of(PD))
            e_dp = doc_error(r, d, *plan_of(DP))
            if e_pd and not e_dp:
                cause, flag = "fact_reading", None
            elif e_dp and not e_pd:
                cause, flag = "document_judgment", None
            elif e_pd and e_dp:
                cause, flag = "fact_reading", "also document"
            else:
                cause, flag = "fact_reading", "joint"
            row.update(cause=cause, flag=flag, product_state=PP[d][0], reference=r["state"])
            if cause == "document_judgment" or flag:
                ds = dsupply.get(d, "not supplied")
                ps = psupply.get(d, {"effective": "missing", "status": "not recorded", "verdict": None})
                if ds == "sufficient" and ps["effective"] == "unusable":
                    sub = "sufficient judged insufficient"
                elif ds == "insufficient" and ps["effective"] == "present":
                    sub = "insufficient judged sufficient"
                elif ds in ("sufficient", "insufficient") and ps["effective"] == "missing":
                    sub = "present judged missing" + (" (source checker rejected the finding)" if ps["verdict"] == "rejected" else "")
                elif ds == "not supplied" and ps["effective"] in ("present", "unusable"):
                    sub = "not supplied judged present"
                else:
                    sub = f"supplied {ds}, product {ps['effective']}"
                row.update(doc_sub=sub, supplied=ds, product_document=ps)
                if cause == "document_judgment":
                    row["sub"] = sub
                    rv = (review_docs or {}).get(f"{regime_name}/{fid}/{d}")
                    if rv and rv.get("judgment") == "text_plausibly_states_product_reading":
                        row.update(cause="text_state_disagree", sub6="reviewed: " + rv["reason"])
            if cause == "fact_reading":
                diff = []
                for f in fact_order:
                    dv = Df.get(f, "unresolved")
                    pv = Pf.get(f, "unresolved")
                    if dv != pv:
                        diff.append(f)
                fixing = []
                for f in diff:
                    fx = dict(Pf)
                    if f in Df:
                        fx[f] = Df[f]
                    else:
                        fx.pop(f, None)
                    st2, _ = doc_states(regime, tid, fx, Dd if flag != "joint" else Pd)
                    if not doc_error(r, d, *plan_of(st2)):
                        fixing.append(f)
                if fixing:
                    f = fixing[0]
                    st = design["facts"].get(f)
                    fr = frow.get(f)
                    verdicts = [a.get(f, (None, ""))[0] for _, a in rds]
                    quotes = [{"verdict": a.get(f, (None, ""))[0], "quote": short(a.get(f, (None, ""))[1])} for _, a in rds]
                    sub = fact_sub(st, fr, verdicts)
                    rawq = [a.get(f, (None, ""))[1] for _, a in rds]
                    if sub in ("readings_disagreed_held", "read_unmentioned_as_open", "read_stated_as_not_stated"):
                        row["pattern"] = held_pattern(regime_name, fid, st, verdicts, rawq)
                    row["quotes_located"] = [located(regime_name, fid, q) if q else None for q in rawq]
                    row.update(fact=f, also_fixing=fixing[1:], designed_state=st,
                               product_fact={"status": (fr or {}).get("status"), "value": (fr or {}).get("value"),
                                             "reason_code": (fr or {}).get("reason_code"),
                                             "open_readings": (fr or {}).get("open_readings")},
                               verdicts=verdicts, reading_quotes=quotes, sub=sub or "state differs")
                    # cause 6 (a): kept as read, blind check changed this fact, product matches the original design
                    fdes = design.get("facts_designed") or {}
                    if meta["kept"] == "kept_as_read" and f in fdes and fdes[f] != st and state_of_product(fr) == fdes[f]:
                        row.update(cause="text_state_disagree", sub6="kept as read; blind check changed the state; product read the original design",
                                   original_design=fdes[f])
                    rv = review.get(f"{regime_name}/{fid}/{f}")
                    if rv and rv.get("judgment") == "text_plausibly_states_product_reading":
                        row.update(cause="text_state_disagree", sub6="reviewed: " + rv["reason"])
                else:
                    row.update(fact=None, sub="several_facts", differing_facts=diff)
            rows.append(row)
    return rows, files_out, checks


# ------------------------------------------------------------------------------------------------- routing detail
def routing_detail(regime_name, arm="clean", model=A.MODEL, judgments=None):
    F = A.files(regime_name)
    R = A.results(arm, regime_name, model)
    judgments = judgments or {}
    out = []
    for fid, x in F.items():
        e = R.get(fid)
        if e is None:
            continue
        p = e.get("plan")
        if p is None:
            out.append({"file": fid, "type": x["design"]["type"], "failed_run": True, "error": short(str(e.get("error")), 400)})
            continue
        if not (p.get("deferred") or p.get("family") != x["design"]["type"]):
            continue
        rec = A.record(e)
        ro = rec["case"]["run"].get("routing") or {}
        answer = [{"fact": f["fact"], "value": f.get("value"), "quotes": [short(c.get("quote"), 300) for c in f.get("citations") or []]}
                  for f in ro.get("facts", [])]
        raw = None
        for k in e.get("keys") or []:
            pth = A.CACHE / f"{k}.json"
            if not pth.exists():
                continue
            try:
                c = json.loads(json.loads(json.loads(pth.read_text())["body"])["choices"][0]["message"]["content"])
            except Exception:  # noqa: BLE001
                continue
            if isinstance(c, dict) and "other_topic" in c and "facts" in c:
                raw = c
                break
        if raw and not answer:
            answer = [{"fact": f.get("fact"), "value": f.get("value"), "quotes": [short(c.get("quote"), 300) for c in f.get("citations") or []]}
                      for f in raw.get("facts", [])]
        res = rec["case"]["run"].get("result") or {}
        d = x["design"]
        row = {"file": fid, "type": d["type"], "denied_event": x["meta"]["denied_event"], "level": x["meta"]["level"],
               "routing_status": ro.get("status"), "routed_to": p.get("family"), "routing_answer": answer,
               "other_topic": (ro.get("other_topic") or {}).get("topic"),
               "defining_event": d["defining_event"], "defining_event_state": d["facts"].get(d["defining_event"]),
               "facts_designed_states": d["facts"], "plan": {k: p.get(k) for k in ("requests", "holds")},
               "errors": A.score_file(x, e, None)["total"]}
        if res.get("facts"):
            row["product_facts"] = {f["fact"]: [f["status"], f.get("value")] for f in res["facts"]}
        j = judgments.get(f"{regime_name}/{fid}")
        if j:
            row["judgment"] = j
        out.append(row)
    return out


# ------------------------------------------------------------------------------------------------- summaries
def tables(rows, files_out):
    by = defaultdict(Counter)
    for r in rows:
        by[(r["regime"], r["cause"])][r["kind"]] += 1
    n_files = Counter(f["regime"] for fo in files_out.values() for f in fo.values())
    out = {}
    for (reg, cause), c in sorted(by.items()):
        out.setdefault(reg, {})[cause] = {**{k: c[k] for k in KINDS}, "total": sum(c.values())}
    tot = Counter()
    for reg in out:
        for cause, c in out[reg].items():
            for k in KINDS + ["total"]:
                tot[(cause, k)] += c[k]
    out["all_regimes"] = {}
    for (cause, k), v in tot.items():
        out["all_regimes"].setdefault(cause, {})[k] = v
    return out, dict(n_files)


def top_pairs(rows, n=10):
    c = Counter()
    ex = defaultdict(list)
    for r in rows:
        if r["cause"] in ("fact_reading", "text_state_disagree") and r.get("fact"):
            k = (r["regime"], r["type"], r["fact"], r["document"])
            c[k] += 1
            ex[k].append(r)
    out = []
    for k, v in c.most_common(n):
        rs = ex[k]
        quotes, seen = [], set()
        # two short quotations: preferably one reading that gave the designed value and one that did not, different files
        for want_right in (False, True):
            for r in rs:
                if r["file"] in seen and len(rs) > 1:
                    continue
                st = r.get("designed_state")
                right = {"stated_true": "true", "stated_false": "false", "open": "open", "not_mentioned": "not_stated"}.get(st)
                pick = None
                for q in r.get("reading_quotes") or []:
                    if q["quote"] and ((q["verdict"] == right) == want_right):
                        pick = q
                        break
                if pick:
                    quotes.append({"file": r["file"], "designed_state": st, "reading_verdict": pick["verdict"], "quote": pick["quote"]})
                    seen.add(r["file"])
                    break
        subs = Counter(r.get("sub") for r in rs)
        kinds = Counter(r["kind"] for r in rs)
        states = Counter(r.get("designed_state") for r in rs)
        out.append({"regime": k[0], "type": k[1], "fact": k[2], "document": k[3], "errors": v, "files": len({r['file'] for r in rs}),
                    "kinds": dict(kinds), "what_the_product_did": dict(subs), "designed_states": dict(states), "quotations": quotes[:2]})
    return out


def fact_level(rows):
    c = Counter()
    for r in rows:
        if r["cause"] in ("fact_reading", "text_state_disagree") and r.get("fact"):
            c[(r["regime"], r["type"], r["fact"], r.get("sub"))] += 1
    return [{"regime": a, "type": b, "fact": f, "what_the_product_did": s, "errors": n} for (a, b, f, s), n in c.most_common()]


def measures_pending(regime="theft"):
    """theft measures_pending in files where it is stated true and the run read the type's facts."""
    F = A.files(regime)
    R = A.results("clean", regime)
    wfs = A.workflows(regime, "clean")
    out = []
    for fid, x in F.items():
        d = x["design"]
        if d["facts"].get("measures_pending") != "stated_true":
            continue
        e = R[fid]
        v = A.run_view(e, wfs[d["type"]])
        if not v or v.get("facts") is None:
            out.append({"file": fid, "type": d["type"], "read": False, "routed": (v or {}).get("routed")})
            continue
        rec = A.record(e)
        fr = next((f for f in rec["case"]["run"]["result"]["facts"] if f["fact"] == "measures_pending"), {})
        rds = verdict_rows(e, wfs[d["type"]])
        out.append({"file": fid, "type": d["type"], "read": True, "status": fr.get("status"), "value": fr.get("value"),
                    "reason_code": fr.get("reason_code"), "open_readings": fr.get("open_readings"),
                    "readings": [{"verdict": a.get("measures_pending", (None, ""))[0], "quote": short(a.get("measures_pending", (None, ""))[1], 220)} for _, a in rds],
                    "imminent_danger": d["facts"].get("imminent_danger"),
                    "text_excerpt": None})
    return out


def frontier():
    """The frontier partial run (39 tenancy files): routing failures and the failed run only."""
    out = {}
    for r in REGIMES:
        R = A.results("clean", r, "gpt-6.1-terra")
        if R is None:
            continue
        out[r] = {"files_run": len(R), "routing": routing_detail(r, "clean", "gpt-6.1-terra")}
    return out


OWNERS = ["rule wording", "must_show wording", "product", "benchmark design", "text vs recorded state", "scoring convention"]


def assign_owner(rows, review):
    """Whose defect each error is, for the planner's question (rule stated in diagnosis_review.json 'notes')."""
    rj = review.get("routing") or {}
    fw = review.get("fact_wording") or []
    dj = review.get("documents") or {}
    for r in rows:
        c = r["cause"]
        if c in ("routing_denied", "routing_not_denied"):
            j = rj.get(f"{r['regime']}/{r['file']}") or {}
            r["owner"] = j.get("owner") or "unjudged"
        elif c == "text_state_disagree":
            r["owner"] = "text vs recorded state"
        elif c == "workflow_vs_reference":
            r["owner"] = "benchmark design"
        elif c == "scoring_convention":
            r["owner"] = "scoring convention"
        elif c == "fact_reading":
            r["owner"] = "product"
            for w in fw:
                if (r["regime"], r["type"], r.get("fact")) == (w["regime"], w["type"], w["fact"]) and w["verdict"] in (r.get("verdicts") or []) \
                        and (not w.get("designed_state") or w["designed_state"] == r.get("designed_state")):
                    r["owner"] = "rule wording"
                    r["wording_reason"] = w["reason"]
        elif c == "document_judgment":
            j = dj.get(f"{r['regime']}/{r['file']}/{r['document']}") or {}
            r["owner"] = "must_show wording" if j.get("judgment") == "must_show_read_strictly" else "product"
            if j:
                r["review"] = j["reason"]
        else:
            r["owner"] = "product"


def owner_table(rows):
    out = {}
    for reg in REGIMES + ["all_regimes"]:
        rs = [r for r in rows if reg == "all_regimes" or r["regime"] == reg]
        c = Counter(r["owner"] for r in rs)
        out[reg] = {"errors": len(rs), **{o: c[o] for o in OWNERS + ["unjudged"] if c[o]}}
    return out


def level_view(rows, files_out, regime, level):
    fo = [f for f in files_out[regime].values() if f["level"] == level]
    rs = [r for r in rows if r["regime"] == regime and r["level"] == level]
    by_file = defaultdict(list)
    for r in rs:
        by_file[r["file"]].append(r)
    return {"files": len(fo), "errors": len(rs), "by_kind": dict(Counter(r["kind"] for r in rs)),
            "by_cause": dict(Counter(r["cause"] for r in rs)), "by_owner": dict(Counter(r["owner"] for r in rs)),
            "per_file": [{"file": f, "errors": len(v), "kinds": dict(Counter(x["kind"] for x in v)),
                          "causes": sorted({(x["cause"] + (":" + x["fact"] if x.get("fact") else "") + (" (" + x["pattern"] + ")" if x.get("pattern") else ""))
                                            for x in v})} for f, v in sorted(by_file.items(), key=lambda kv: -len(kv[1]))]}


def md_table(head, rows):
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]


def markdown(rep):
    L = ["# Diagnosis of the clean-arm errors (Study 4, step 2d follow-up)", "",
         "**DEVELOPMENT material, post hoc, not a result.** Stored clean-arm runs on gpt-6-luna (one run per file) at the "
         "tested commit; no model call was made for this diagnosis. Written by `lint/diagnose.py` from the stored records "
         "and cached reading responses, the files' designs and references, the rule sets the runs read (`rules/<regime>/rev0/`) "
         "and the product's own evaluator; the judgments that need a reading of the text are in `lint/diagnosis_review.json`.", "",
         "## Attribution rule", "", "```", rep["rule"], "```", "",
         "Replay checks: " + "; ".join(f"{r}: " + ", ".join(f"{k} {v}" for k, v in c.items()) for r, c in rep["replay_checks"].items())
         + ". The product's evaluator, fed the stored facts and findings, reproduces every stored plan of the 139 correctly routed "
           "files, and fed the designed states it reproduces every reference document state: no error is of cause 4.", ""]
    L += ["## Errors by regime, cause and kind", "",
          "UR = request that should not be made, MR = request missed, UH = hold where the file settles the fact, MH = hold missed.", ""]
    rows = []
    for reg in REGIMES + ["all_regimes"]:
        for cause in CAUSES:
            c = rep["counts"].get(reg, {}).get(cause)
            if c:
                rows.append([reg, CAUSE_LABEL[cause], c["unneeded_request"], c["missed_request"], c["unwarranted_hold"], c["missed_hold"], c["total"]])
    L += md_table(["Regime", "Cause", "UR", "MR", "UH", "MH", "Errors"], rows) + [""]
    L += ["## Whose defect", "", "Owner classes as stated in `diagnosis_review.json` (notes). Denominator: all clean-arm errors of the regime.", ""]
    rows = []
    for reg, c in rep["owners"].items():
        n = c["errors"]
        rows.append([reg, n] + [f"{c.get(o, 0)} ({100 * c.get(o, 0) / n:.0f}%)" if n else "0" for o in OWNERS])
    L += md_table(["Regime", "Errors"] + OWNERS, rows) + [""]
    L += ["## The ten fact/document pairs with the most errors", "",
          "Fact-reading errors (cause 2, and cause 6 where the fact is named). Quotations are from the stored reading responses.", ""]
    for i, p in enumerate(rep["top_pairs"], 1):
        L.append(f"{i}. **{p['regime']} {p['type']}.{p['fact']} -> {p['document']}**: {p['errors']} errors in {p['files']} file(s); "
                 f"kinds {p['kinds']}; designed {p['designed_states']}; product: {', '.join(SUB_LABEL.get(k, k) for k in p['what_the_product_did'])}.")
        for q in p["quotations"]:
            L.append(f"   - {q['file']} (designed {q['designed_state']}), a reading answered {q['reading_verdict']}: \"{q['quote']}\"")
    L += ["", "Patterns behind the fact-reading errors (every cause-2 error, and cause-6 errors that name a fact):", ""]
    pat = Counter((r["regime"], r.get("fact"), r.get("pattern") or SUB_LABEL.get(r.get("sub"), r.get("sub")), r["owner"]) for r in rep["errors"]
                  if r["cause"] == "fact_reading" or (r["cause"] == "text_state_disagree" and r.get("fact")))
    L += md_table(["Regime", "Fact", "What the readings did", "Owner", "Errors"], [[a, b or "several facts", c, o, n] for (a, b, c, o), n in pat.most_common()]) + [""]
    lv = rep["level0_dismissal"]
    L += ["## Dismissal at share level 0", "",
          f"{lv['files']} files, {lv['errors']} errors ({lv['errors'] / lv['files']:.2f} per file); by kind {lv['by_kind']}; by cause {lv['by_cause']}; by owner {lv['by_owner']}.", ""]
    L += md_table(["File", "Errors", "Kinds", "Causes"], [[f["file"], f["errors"], f["kinds"], "; ".join(f["causes"])] for f in lv["per_file"]]) + [""]
    L += [rep.get("level0_text") or "", ""]
    L += ["## Theft: measures_pending", ""]
    mp = rep["theft_measures_pending"]
    L += md_table(["File", "Type", "Product", "Readings (verdict: quotation)"],
                  [[m["file"], m["type"], (f"{m.get('status')} {m.get('value')}" if m["read"] else f"not read (routed {m.get('routed')})"),
                    "; ".join(f"{q['verdict']}: {q['quote']}" for q in m.get("readings", []))] for m in mp]) + [""]
    L += [rep.get("measures_text") or "", ""]
    L += ["## Routing failures", ""]
    for reg, rs in rep["routing"].items():
        nd = [x for x in rs if not x.get("denied_event") and not x.get("failed_run")]
        dn = [x for x in rs if x.get("denied_event")]
        L += [f"### {reg}: {len(nd)} non-denied, {len(dn)} denied-event", ""]
        if nd:
            L += md_table(["File", "Type", "Routing answer", "Quotation", "Errors", "Owner", "Cause"],
                          [[x["file"], x["type"], ", ".join(f"{a['value']}" for a in x["routing_answer"]) or "-",
                            (x["routing_answer"][0]["quotes"][0] if x["routing_answer"] and x["routing_answer"][0]["quotes"] else "(no quotation; value null)"),
                            x["errors"], (x.get("judgment") or {}).get("owner", ""), (x.get("judgment") or {}).get("cause", "")] for x in nd]) + [""]
        if dn:
            L += md_table(["File", "Type", "Product did", "Errors", "Empty plan right under the rule text?", "Why"],
                          [[x["file"], x["type"], (x.get("judgment") or {}).get("product_did", f"routed to {x['routed_to']}"), x["errors"],
                            {True: "yes", False: "no"}.get((x.get("judgment") or {}).get("empty_plan_right"), "?"),
                            (x.get("judgment") or {}).get("why", "")] for x in dn]) + [""]
    fr = rep.get("frontier") or {}
    for reg, v in fr.items():
        L += [f"## Frontier partial run ({reg}, {v['files_run']} files): routing failures and the failed run", ""]
        L += md_table(["File", "Type", "Denied event", "Routing", "Answer", "Errors"],
                      [[x["file"], x["type"], x.get("denied_event", ""), ("failed run: " + x["error"]) if x.get("failed_run") else x.get("routing_status"),
                        ", ".join(f"{a['value']}" for a in x.get("routing_answer", [])) or "-", x.get("errors", "")] for x in v["routing"]]) + [""]
        L += [rep.get("frontier_text") or "", ""]
    L += ["## Limits", ""] + [f"- {t}" for t in rep.get("limits") or []] + [""]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="clean")
    ap.add_argument("--rules", default="rev0")
    ap.add_argument("--out", default="DIAGNOSIS")
    a = ap.parse_args()
    review = A.jl(HERE / "diagnosis_review.json") if (HERE / "diagnosis_review.json").exists() else {}
    rows, files_out, checks = [], {}, {}
    for r in REGIMES:
        rr, fo, ck = diagnose_regime(r, a.arm, a.rules, review=review.get("facts"), review_docs=review.get("documents"))
        rows += rr
        files_out[r] = fo
        checks[r] = dict(ck)
    assign_owner(rows, review)
    tab, n_files = tables(rows, files_out)
    owners = owner_table(rows)
    routing = {r: routing_detail(r, a.arm, judgments=review.get("routing")) for r in REGIMES}
    rep = {"label": "DEVELOPMENT, post hoc, not a result", "arm": a.arm, "model": A.MODEL, "rules_read": a.rules,
           "rule": __doc__.split("Attribution rule", 1)[1].strip(), "replay_checks": checks, "files": n_files,
           "counts": tab, "owners": owners, "level0_dismissal": level_view(rows, files_out, "dismissal", 0), "top_pairs": top_pairs(rows), "by_fact": fact_level(rows), "routing": routing,
           "theft_measures_pending": measures_pending(), "frontier": frontier() if a.arm == "clean" else None,
           "review_notes": review.get("notes"), **(review.get("explanations") or {}), "errors": rows}
    (HERE / f"{a.out}.md").write_text(markdown(rep), encoding="utf-8")
    (HERE / f"{a.out}.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"checks": checks, "counts": tab}, indent=1))


if __name__ == "__main__":
    main()
