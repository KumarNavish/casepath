"""Theft diagnosis: why CasePath on the frontier model does not beat the frontier single prompt on theft. No model calls.

    python3 theft_diagnosis.py      # writes theft_diagnosis.json and theft_diagnosis.md next to this file

Post hoc, development analysis (fresh2 is development data since Study 3 finished). Reads stored runs only; changes
nothing. Parts:
 1. Rule floor: the converted theft workflow (reviewed and original rule bases, convert_theft.convert) executed by the
    product's evaluator (casepath.process.workflows at commit 6a72159c, loaded as analysis/study3.py loads it) on the
    designed facts of every text of stories 0-15, scored with study2/study3's pair scoring.
 2. Conversion: the same facts through the research engine (TheftPack.plan_exact) and a route-choice sensitivity.
 3. Readings: the product's admitted facts (stored product_extra.facts) and the three readings (response cache) of the
    finished test's runs, against the designed facts.
 4. Decomposition of wrong + missed per pair into floor, off-text misreadings, changed-condition reading, other
    conditions (spill-over), and the single prompt against the floor.
The mapping of the nine designed conditions to workflow facts (DESIGN below) is written from the condition texts of the
rule base and the nine condition sentences; it is NOT in the harness. Uncertain assignments are marked and varied.
"""
from __future__ import annotations

import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
sys.path[:0] = [str(HERE), str(TMIS / "harness"), str(TMIS / "harness" / "v2"), str(TMIS / "harness" / "product")]
import study3 as s3  # noqa: E402
import common  # noqa: E402
import convert_theft as ct  # noqa: E402
import load_reviewed  # noqa: E402
import theft_v2  # noqa: E402
import v3  # noqa: E402
from theft_data import doc_ids, catalogue  # noqa: E402

s2 = s3.s2
COMMIT = "6a72159cdb35a01059d0549b1d437c0b3d5c20cb"
REVIEWED = TMIS / "rule_review" / "final" / "reviewed_rules.json"
ORIGINAL = TMIS / "rule_review" / "bundle" / "rules.json"
CONFIRM = TMIS / "runs" / "study3" / "confirm"
CACHE = TMIS / "runs" / "product" / "cache"
IDS = doc_ids()
INV = {v.lower(): k for k, v in IDS.items()}
NAME2ID = {k: v for k, v in IDS.items()}
COND = ["PR_scheduled_valuable_1000", "PR_bicycle_claimed", "PR_sim_card_stolen", "PR_third_party_causer",
        "PR_expert_procedure_requested", "PR_repair_over_500", "PR_nachfrist_set", "PR_goods_recovered", "PR_declined"]
SHORT = {"PR_scheduled_valuable_1000": "Scheduled valuable", "PR_bicycle_claimed": "Bicycle", "PR_sim_card_stolen": "SIM card",
         "PR_third_party_causer": "Third party", "PR_expert_procedure_requested": "Expert procedure",
         "PR_repair_over_500": "Repair > 500", "PR_nachfrist_set": "Deadline demand", "PR_goods_recovered": "Recovered",
         "PR_declined": "Declined"}

# ------------------------------------------------------------------------------------------------ the designed facts
# Guard stems (gNNN; a reviewed guard 'g042_rev_92ab8925' has stem g042). Only facts that some document need depends on
# can change a checklist (27 in the reviewed workflow, 26 in the original); every other fact is set false and is inert.
# BACKGROUND: true in every text of every story by design (every story is a household theft after a forced entry).
BACKGROUND = {
    "g002": (True, "certain: the loss is connected with theft"),
    "g005": (True, "certain: household-contents coverage for theft-related damage"),
    "g006": (True, "certain: the reported event is theft"),
    "g004": (True, "near-certain: 'After the feared event occurs' (the event has occurred)"),
    "g003": (True, "uncertain: every story reports a forced entry, so crime-scene traces exist; constant within a story "
                   "either way, and its documents (D26, D27) are in no reference, so it cannot change a pair's floor"),
}
# CHANGED[c] = {stem: (value when c is true, certainty)}; every stem not listed for c is false in c's on text.
CHANGED = {
    "PR_scheduled_valuable_1000": {"g074": (True, "certain: object listed in the contract, insured value >= CHF 1,000"),
                                   "g016": (True, "uncertain: 'claim concerns valuables insurance' (a scheduled item); "
                                                  "same documents as g074, so the floor does not depend on it"),
                                   "g009": (False, "near-certain: watch scheduled at CHF 4,000, not > CHF 5,000")},
    "PR_bicycle_claimed": {"g015": (True, "certain")},
    "PR_sim_card_stolen": {"g084": (True, "certain"), "g088": (True, "certain (same text as g084)")},
    "PR_third_party_causer": {"g042": (True, "near-certain: an identified contractor caused the loss (fault implied)")},
    "PR_expert_procedure_requested": {"g021": (True, "certain: a party demands expert proceedings (no document depends on it)"),
                                      "g022": (True, "UNCERTAIN: is a written request by one party 'the expert-procedure route "
                                                     "has been selected'? varied below"),
                                      "g020": (True, "UNCERTAIN (reviewed rules only): 'the loss is to be determined ... in "
                                                     "expert proceedings'; varied below"),
                                      "g023": (False, "near-certain: no party has been requested to appoint an expert")},
    "PR_repair_over_500": {"g090": (True, "certain")},
    "PR_nachfrist_set": {"g070": (True, "certain: the insurer set a time limit"), "g098": (True, "certain")},
    "PR_goods_recovered": {"g040": (True, "certain")},
    "PR_declined": {"g043": (True, "certain")},
}
EXPERT_VARIANTS = {"primary (g022 T, g020 T)": {"g022": True, "g020": True}, "g022 T, g020 F": {"g022": True, "g020": False},
                   "g022 F, g020 T": {"g022": False, "g020": True}, "g022 F, g020 F": {"g022": False, "g020": False}}


def stem(fid):
    return fid.split("_")[0]


def designed(text_meta, facts_used, expert=None, always_true=()):
    """{fact id: True/False/None} for one text: background true, the changed condition true (on) or open (unresolved).
    always_true: stems set true in every text (the literal-reading variant of a broad condition)."""
    kind, cond = text_meta["kind"], text_meta["condition"]
    out = {}
    for f in facts_used:
        s = stem(f)
        v = True if s in always_true else BACKGROUND[s][0] if s in BACKGROUND else False
        if kind != "off" and s in CHANGED[cond]:
            val = CHANGED[cond][s][0]
            if expert and cond == "PR_expert_procedure_requested" and s in expert:
                val = expert[s]
            if val:
                v = True if kind == "on" else None
        out[f] = v
    return out


# ------------------------------------------------------------------------------------------------ data
def load_data():
    import theft_data as A
    B = common.data("theft", "fresh")
    C = common.data("theft", "fresh2")
    texts, pairs = {}, []
    for M in (A, B, C):
        texts.update(M.texts())
        pairs += [p for p in M.pairs()]
    return texts, pairs


def evaluator():
    return s3.load_evaluator({"commit": COMMIT, "subdir": "casepath-internal"})


def used_facts(wf):
    out = set()
    for d in wf["documents"]:
        rw = d.get("required_when")
        if rw:
            out |= {c["fact"] for c in ([rw] if "fact" in rw else rw["any"])}
    return sorted(out)


def run_wf(W, wf, facts):
    ev = W.evaluate(wf, {**facts, "claim_type": "household_theft"}, {}, checked=True)
    return {"requests": sorted(INV[r["document"]] for r in ev["documents"] if r["required"] == "yes" and r["status"] == "missing"),
            "holds": sorted(INV[r["document"]] for r in ev["documents"] if r["required"] == "depends")}


def score(pairs, plans, runs=1):
    """plans: {text: [plan per run]}. Returns (on rows, unresolved rows) with study2's scoring (same pairing as study3)."""
    on = s2.theft_rows(None, [p for p in pairs if p["kind"] == "on"], plans, pairing=[(r, r) for r in range(runs)])
    un = s2.theft_rows(None, [p for p in pairs if p["kind"] == "unresolved"], plans, pairing=[(r, r) for r in range(runs)])
    return on, un


def summ(on, un=None):
    n = len(on)
    out = {"pairs": n, "wrong": sum(r["wrong"] for r in on) / n, "missed": sum(r["missed"] for r in on) / n,
           "errors": sum(r["errors"] for r in on) / n}
    if un:
        out["unres_unchanged"] = sum(r["stable"] for r in un) / len(un)
        out["unres_premature"] = sum(r["premature"] for r in un) / len(un)
        out["unres_held"] = sum(r["held"] for r in un) / len(un)
    return out


def by_fact(on):
    g = defaultdict(list)
    for r in on:
        g[r["condition"]].append(r)
    return {c: sum(r["errors"] for r in g[c]) / len(g[c]) for c in COND if g[c]}


def atoms_by_fact(on):
    g = defaultdict(Counter)
    for r in on:
        for a in r["atoms"]:
            g[r["condition"]][(a[0], a[1][0] + IDS[a[1][1:]])] += 1
    return g


# ------------------------------------------------------------------------------------------------ Part 1 and 2
def floor(W, wf, texts, pairs, expert=None, always_true=()):
    fu = used_facts(wf)
    plans = {t: [run_wf(W, wf, designed(m, fu, expert, always_true))] for t, m in texts.items()}
    on, un = score(pairs, plans)
    return plans, on, un


def engine_plans(pack, wf, texts, expert=None):
    """TheftPack.plan_exact on the same designed facts (guard ids mapped to workflow fact ids as convert_theft does)."""
    fu = set(used_facts(wf))
    out = {}
    for t, m in texts.items():
        d = designed(m, [ct.fact_id(g) for g in pack.guards], expert)
        nu = {g: ("true" if d[ct.fact_id(g)] else "unresolved" if d[ct.fact_id(g)] is None else "false") for g in pack.guards}
        p = pack.plan_exact(nu)
        out[t] = [{"requests": p["requests"], "holds": p["holds"]}]
    return out


class RouteExec:
    """The rule base executed with a chosen route per evidence item (cheapest by default, as convert_theft and plan_exact),
    to see whether any floor error depends on the route fixed at conversion. Same semantics as the converted workflow."""

    def __init__(self, path):
        self.items = []  # (item key, fact id or None, routes)
        for rule in sorted(json.loads(Path(path).read_text())["rules"], key=lambda r: r["rule_id"]):
            cond = rule.get("condition")
            fid = ct.fact_id(load_reviewed._guard_id(rule["rule_id"], cond)) if cond else None
            caps = [e for f in rule["facts"] for e in f["evidence"]]
            if rule.get("confirming_evidence") and fid:
                caps.append(rule["confirming_evidence"])
            for cap in caps:
                if cap.get("routes"):
                    self.items.append((f"{rule['rule_id']}:{cap['capability_id']}", fid, cap["routes"]))
        self.alt = [i for i, it in enumerate(self.items) if len(it[2]) > 1]

    def plan(self, facts, choice=None):
        sup = defaultdict(list)
        for i, (key, fid, routes) in enumerate(self.items):
            r = routes[choice[i]] if choice and i in choice else min(routes, key=ct.route_key)
            v = True if fid is None else facts.get(fid, False)
            for d in r["documents"]:
                sup[d].append(v)
        st = {d: (True if True in vs else None if None in vs else False) for d, vs in sup.items()}
        return {"requests": sorted(d for d, v in st.items() if v is True), "holds": sorted(d for d, v in st.items() if v is None)}


def route_sensitivity(rx, wf, texts, pairs, base_errors, expert=None):
    """Each evidence item with alternative routes switched alone to each alternative: change in the floor."""
    fu = used_facts(wf)
    facts = {t: designed(m, fu, expert) for t, m in texts.items()}
    out = []
    for i in rx.alt:
        key, fid, routes = rx.items[i]
        cheapest = routes.index(min(routes, key=ct.route_key))
        for j, r in enumerate(routes):
            if j == cheapest:
                continue
            plans = {t: [rx.plan(facts[t], {i: j})] for t in texts}
            on, un = score(pairs, plans)
            e = summ(on, un)
            out.append({"item": key, "condition_fact": fid, "chosen": [IDS[d] for d in routes[cheapest]["documents"]],
                            "alternative": [IDS[d] for d in r["documents"]], "errors_per_pair": round(e["errors"], 4),
                            "change": round(e["errors"] - base_errors, 4), "by_fact": {k: round(v, 3) for k, v in by_fact(on).items()}})
    return out


# ------------------------------------------------------------------------------------------------ Part 3: readings
PRODUCT_ARMS = {  # design key in study3_spec -> (file, runs, model)
    "casepath": ("plans_theft_casepath.json", 3, "gpt-6-luna"),
    "casepath_checklist": ("plans_theft_casepath_checklist.json", 3, "gpt-6-luna"),
    "casepath_frontier_checklist": ("plans_theft_casepath_checklist_frontier.json", 1, "gpt-6.1-terra"),
}


def admitted(entry, fu):
    """The facts the product used: established and accepted (as study3.two_valued); every other used fact open (None)."""
    f = ((entry or {}).get("product_extra") or {}).get("facts") or {}
    out = {}
    for k in fu:
        x = f.get(k)
        out[k] = x["value"] if x and x["status"] == "established" and x.get("verdict") == "accepted" else None
    return out


def readings(entry, n_facts):
    """The readings' raw answers from the response cache, in call order: [{fact: (verdict, quote)}]. A conditions answer
    covering most facts starts a reading; a short one is the requote retry and replaces those answers."""
    out, seen = [], set()
    for k in (entry or {}).get("keys") or []:
        if k in seen:
            continue
        seen.add(k)
        p = CACHE / f"{k}.json"
        if not p.exists():
            continue
        try:
            body = json.loads(json.loads(p.read_text())["body"])
            content = json.loads(body["choices"][0]["message"]["content"])
        except Exception:  # noqa: BLE001
            continue
        rows = content.get("conditions") if isinstance(content, dict) else None
        if not rows or not any(str(r.get("id", "")).startswith("g") for r in rows):
            continue
        ans = {}
        for r in rows:
            ans.setdefault(r["id"], (r["verdict"], r.get("quote") or ""))
        if len(ans) >= 0.8 * n_facts or not out:
            out.append(ans)
        else:
            out[-1].update(ans)
    return out


def fact_state(entry, f):
    """true / false (admitted), conflict (readings gave different values), open (no admitted value)."""
    x = (((entry or {}).get("product_extra") or {}).get("facts") or {}).get(f)
    if not x:
        return "open"
    if x["status"] == "established" and x.get("verdict") == "accepted":
        return "true" if x["value"] else "false"
    return "conflict" if x["status"] == "conflicting" else "open"


def gset(cond, fu):
    """Workflow facts of the changed condition (every stem listed for it in CHANGED)."""
    return [f for f in fu if stem(f) in CHANGED[cond]]


KEY = {  # stems whose truth adds the reference document (any of them suffices)
    "PR_scheduled_valuable_1000": {"g074", "g016", "g009"}, "PR_bicycle_claimed": {"g015"},
    "PR_sim_card_stolen": {"g084", "g088"}, "PR_third_party_causer": {"g042"}, "PR_expert_procedure_requested": {"g022", "g023"},
    "PR_repair_over_500": {"g090"}, "PR_nachfrist_set": {"g070", "g098"}, "PR_goods_recovered": {"g040"},
    "PR_declined": {"g043"}}


def classify(texts, entries, fu, runs):
    """Per text-run, the admitted value of every used fact against the designed value."""
    rows = []
    for t, m in texts.items():
        if t not in entries:
            continue
        d = designed(m, fu)
        for r in range(runs):
            a = admitted(entries[t][r], fu)
            for f in fu:
                rows.append({"state": fact_state(entries[t][r], f), "text": t, "run": r, "kind": m["kind"], "story": m["story"], "condition": m["condition"],
                             "fact": f, "design": d[f], "admitted": a[f],
                             "in_changed": m["condition"] is not None and stem(f) in CHANGED[m["condition"]]})
    return rows


def reading_tables(rows, n_texts_by_kind):
    out = {}
    # (a) changed condition: is a key fact (designed true) admitted true in the on text? else conflict / open
    per = defaultdict(list)
    for r in rows:
        if r["kind"] == "on" and stem(r["fact"]) in KEY[r["condition"]] and r["design"] is True:
            per[(r["text"], r["run"], r["condition"])].append(r["state"])
    hit = defaultdict(Counter)
    for (t, run, c), st in per.items():
        hit[c]["text_runs"] += 1
        hit[c]["admitted_true" if "true" in st else "readings_conflict" if "conflict" in st else
               "admitted_false" if "false" in st else "left_open"] += 1
    out["changed_condition_on"] = {c: dict(hit[c]) for c in COND if c in hit}
    # (b) spill-over: false by design admitted true, by fact, in off / on / unresolved texts (outside the changed set)
    sp = defaultdict(Counter)
    for r in rows:
        if r["design"] is False and r["admitted"] is True and not r["in_changed"]:
            sp[r["kind"]][r["fact"]] += 1
    out["false_admitted_true"] = {k: dict(v.most_common()) for k, v in sp.items()}
    # background true facts not admitted true
    bg = defaultdict(Counter)
    for r in rows:
        if r["design"] is True and not r["in_changed"] and r["admitted"] is not True:
            bg[r["kind"]][(r["fact"], "false" if r["admitted"] is False else "open")] += 1
    out["true_not_admitted"] = {k: {f"{f}:{v}": n for (f, v), n in c.most_common()} for k, c in bg.items()}
    # (d) open condition given a value in unresolved texts
    og = Counter()
    for r in rows:
        if r["kind"] == "unresolved" and r["design"] is None and r["admitted"] is not None:
            og[(r["condition"], r["fact"], r["admitted"])] += 1
    out["open_given_value"] = {f"{c}|{f}|{v}": n for (c, f, v), n in og.most_common()}
    out["text_runs"] = n_texts_by_kind
    return out


# ------------------------------------------------------------------------------------------------ Part 4: decomposition
class Exec:
    """Evaluator with a cache keyed by the fact values."""

    def __init__(self, W, wf):
        self.W, self.wf, self.memo = W, wf, {}

    def __call__(self, facts):
        k = tuple(sorted(facts.items()))
        if k not in self.memo:
            self.memo[k] = run_wf(self.W, self.wf, facts)
        return self.memo[k]


def pair_err(ex, pair, fo, fv):
    r = s2.theft_row(pair, ex(fo), ex(fv))
    return r["errors"], r


def decompose(ex, pairs, texts, entries, fu, runs, expert=None):
    """For every changed-fact pair-run (method stated in the report):
    F  floor: designed facts in both texts;
    O  off misreading: the off text as the product read it, the variant read identically except that its changed
       condition has its designed value (what a misread off text costs every pair of its story);
    C  changed condition: from there, the variant's changed-condition facts as the product read them;
    S  other conditions (spill-over and unstable background facts): from O's state, the variant's other facts as read
       (the changed condition at its designed value);
    I  interaction remainder = measured - F - O - C - S.  F + O + C + S + I = measured exactly."""
    rows = []
    for p in pairs:
        if p["kind"] != "on" or p["off"] not in entries:
            continue
        Po, Pv = designed(texts[p["off"]], fu, expert), designed(texts[p["variant"]], fu, expert)
        Gc = set(gset(p["condition"], fu))
        for r in range(runs):
            Ao, Av = admitted(entries[p["off"]][r], fu), admitted(entries[p["variant"]][r], fu)
            mix = lambda base, gc: {f: (gc[f] if f in Gc else base[f]) for f in fu}  # noqa: E731
            F, _ = pair_err(ex, p, Po, Pv)
            M, row = pair_err(ex, p, Ao, Av)
            x1, _ = pair_err(ex, p, Ao, mix(Ao, Pv))
            x2, _ = pair_err(ex, p, Ao, mix(Ao, Av))
            x3, _ = pair_err(ex, p, Ao, mix(Av, Pv))
            O, C, S = x1 - F, x2 - x1, x3 - x1
            other_diff = sorted(f for f in fu if f not in Gc and Ao[f] != Av[f])
            off_bad = sorted(f for f in fu if Ao[f] != Po[f] and not (Po[f] is True and Ao[f] is None and stem(f) == "g003"))
            rows.append({"pair": p["pair_id"], "condition": p["condition"], "story": p["story"], "run": r, "measured": M,
                         "floor": F, "off": O, "changed": C, "other": S, "remainder": M - F - O - C - S,
                         "atoms": row["atoms"], "other_facts_differing": [(f, Ao[f], Av[f]) for f in other_diff],
                         "changed_read": {f: Av[f] for f in Gc}, "off_misread": [(f, Ao[f]) for f in off_bad]})
    return rows


def mean_rows(rows, keys=("measured", "floor", "off", "changed", "other", "remainder")):
    n = len(rows)
    return {k: sum(r[k] for r in rows) / n for k in keys} | {"pair_runs": n}


def reading_verdicts(texts, st, runs, nf, fu):
    """Per single reading (before agreement): verdicts on the key facts of on texts, on g042 in off texts, and on
    g003 everywhere; with up to two example quotations per (fact, verdict)."""
    out = {"key_on": defaultdict(Counter), "g042_off": Counter(), "g042_unres": Counter(), "g003": defaultdict(Counter)}
    ex = defaultdict(list)
    for t, m in texts.items():
        for r in range(runs):
            e = st.get(f"PRODUCT|{t}|{r}")
            rds = readings(e, nf)
            for i, rd in enumerate(rds):
                if m["kind"] == "on":
                    for f in fu:
                        if stem(f) in KEY[m["condition"]] and designed(m, [f])[f] is True:
                            v = (rd.get(f) or ("missing", ""))[0]
                            out["key_on"][f"{m['condition']}|{f}"][v] += 1
                            if len(ex[(f, v, "on")]) < 2 and v != "true":
                                ex[(f, v, "on")].append({"text": t, "run": r, "reading": i, "quote": (rd.get(f) or ("", ""))[1]})
                g42 = next(f for f in fu if stem(f) == "g042")
                v = (rd.get(g42) or ("missing", ""))[0]
                if m["kind"] == "off":
                    out["g042_off"][v] += 1
                elif m["kind"] == "unresolved" and m["condition"] != "PR_third_party_causer":
                    out["g042_unres"][v] += 1
                if v == "true" and m["kind"] == "off" and len(ex[(g42, v, "off")]) < 2:
                    ex[(g42, v, "off")].append({"text": t, "run": r, "reading": i, "quote": rd[g42][1]})
                v3_ = (rd.get("g003") or ("missing", ""))[0]
                out["g003"][m["kind"] if m["kind"] != "on" else ("on_repair" if m["condition"] == "PR_repair_over_500" else "on_other")][v3_] += 1
                if m["kind"] == "on" and m["condition"] == "PR_repair_over_500" and v3_ == "true" and len(ex[("g003", "true", "repair")]) < 4:
                    ex[("g003", "true", "repair")].append({"text": t, "run": r, "reading": i, "quote": rd["g003"][1]})
    return {"key_on": {k: dict(v) for k, v in out["key_on"].items()}, "g042_off": dict(out["g042_off"]),
            "g042_unresolved_other_conditions": dict(out["g042_unres"]), "g003": {k: dict(v) for k, v in out["g003"].items()},
            "examples": {"|".join(k): v for k, v in ex.items()}}


def unresolved_changes(ex, pairs, texts, entries, fu, runs):
    """Unresolved pairs whose requests changed: the changed documents and the facts whose admitted value differs."""
    rows = []
    for p in pairs:
        if p["kind"] != "unresolved" or p["off"] not in entries:
            continue
        for r in range(runs):
            Ao, Av = admitted(entries[p["off"]][r], fu), admitted(entries[p["variant"]][r], fu)
            po, pv = ex(Ao), ex(Av)
            delta = sorted({"+" + IDS[d] for d in set(pv["requests"]) - set(po["requests"])} |
                           {"-" + IDS[d] for d in set(po["requests"]) - set(pv["requests"])})
            if delta:
                rows.append({"pair": p["pair_id"], "run": r, "delta": delta,
                             "facts_differing": [(f, Ao[f], Av[f]) for f in fu if Ao[f] != Av[f]]})
    return rows


# ------------------------------------------------------------------------------------------------ same-model comparison
SINGLE = {  # design -> (file, key, model, rules)
    "ric": ("plans_theft_ric_luna.json", "Rpack|{case}|{run}", "gpt-6-luna", "reviewed"),
    "ric_original": ("plans_theft_ric_original_luna.json", "R|{case}|{run}", "gpt-6-luna", "original"),
    "ric_frontier": ("plans_theft_ric_terra.json", "Rpack|{case}|{run}", "gpt-6.1-terra", "reviewed"),
    "ric_original_frontier": ("plans_theft_ric_original_terra.json", "R|{case}|{run}", "gpt-6.1-terra", "original"),
}


def stored_plans(fn, key, runs, texts):
    raw = json.loads((CONFIRM / fn).read_text())
    return {t: [s3.to_names((raw.get(key.format(case=t, run=r)) or {}).get("plan"), INV) for r in range(runs)] for t in texts}


def counterfactual(ex, pairs, texts, entries, fu, runs, fixes, expert=None):
    """The stored admitted facts with the named facts replaced by their designed values in every text (a remedy that
    worked perfectly on those facts and changed nothing else). fixes: set of stems; 'changed' = the changed condition's
    facts in on/unresolved texts."""
    plans = {}
    for t, m in texts.items():
        if t not in entries:
            continue
        d = designed(m, fu, expert)
        plans[t] = []
        for r in range(runs):
            a = admitted(entries[t][r], fu)
            for f in fu:
                if stem(f) in fixes or ("changed" in fixes and m["condition"] and stem(f) in CHANGED[m["condition"]]):
                    a[f] = d[f]
            plans[t].append(ex(a))
    on, un = score([p for p in pairs if p["off"] in plans], plans, runs)
    return summ(on, un), by_fact(on)


# ------------------------------------------------------------------------------------------------ Part 5
PART5_ARM = "theft-diagnosis-passages"
PART5_DESIGN = {
    "question": "With each condition's cited source passage shown next to it in the reading form (variant (d), one general "
                "rule applied to all 89 conditions), do gpt-6.1-terra's three agreeing readings stop admitting g042 (third-party "
                "fault, reviewed rule 042) true on the off sentence 'No identifiable third party caused or enlarged the loss apart "
                "from the unidentified thief.'? (Also observed: g022, g074 would need on texts; g003 on the same texts.)",
    "why_this_one": "g042 read true in every off text is the largest reading-level cause of the frontier product's excess "
                    "(off misreading 0.111 per pair, all eight third-party unresolved pairs changed); the model-free upper "
                    "bound for (d) fixing g042, g022 and g074 is 0.472 against 0.671; without g042 it is about 0.64, which "
                    "one run cannot tell from 0.671.",
    "texts": "fresh2 s8-off, then s9-off (development data); one product run each, run index 0; checklist scope, "
             "reasoning on, as the stored frontier run; baseline = the stored run 0 (cached, reproduced from the cache "
             "with zero cost for s8-off before any paid call)",
    "decision_rule": "if g042 is still admitted true in the off texts, (d) cannot repair the decisive error and no further "
                     "run is made",
    "variant": "workflow fact question + ' (Read the condition as its source means it. Source: <texts of the passages the "
               "rule's condition cites>)'; validated with the product's validate_workflow; the product itself unchanged",
}


def part5(fu, nf):
    """Recorded from the dev ledger rows of PART5_ARM and the response cache (both in the repository)."""
    ledger = TMIS / "runs" / "product" / "ledger_dev_gpt-6.1-terra.jsonl"
    rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("arm") == PART5_ARM]
    out = {"design": PART5_DESIGN, "paid_calls": len(rows), "spend_usd": round(sum(r["usd"] or 0 for r in rows), 4), "texts": {}}
    st = json.loads((CONFIRM / "plans_theft_casepath_checklist_frontier.json").read_text())
    for case in dict.fromkeys(r["case"] for r in rows):
        keys = [r["key"] for r in rows if r["case"] == case]
        var = readings({"keys": keys}, nf)
        base = readings(st[f"PRODUCT|{case}|0"], nf)
        out["texts"][case] = {"usd": round(sum(r["usd"] for r in rows if r["case"] == case), 4),
                              "variant_readings": {f: [x.get(f) for x in var] for f in ("g042_rev_92ab8925", "g003", "g022", "g074")},
                              "baseline_readings": {f: [x.get(f) for x in base] for f in ("g042_rev_92ab8925", "g003", "g022", "g074")},
                              "baseline_admitted": {f: admitted(st[f"PRODUCT|{case}|0"], fu)[f] for f in fu if stem(f) in ("g042", "g003")}}
    return out


# ------------------------------------------------------------------------------------------------ report
FLOOR_RULES = {  # document -> the rule(s) that produce the floor error (checked against the rule files in main)
    "D33": ["overlay_rule_084"], "D14": ["overlay_rule_010"], "D23": ["overlay_rule_020"], "D10": ["overlay_rule_074", "overlay_rule_016"],
}
PRIMARY = "primary (g022 T, g020 T)"


def r3(x):
    return None if x is None else round(x, 3)


def rule_quote(path, rid):
    r = next(x for x in json.loads(Path(path).read_text())["rules"] if x["rule_id"] == rid)
    return {"condition": (r.get("condition") or {}).get("text"), "title": r.get("title"),
            "routes": [[[IDS[d] for d in rt["documents"]] for rt in e["routes"]] for f in r["facts"] for e in f["evidence"]]}


def main():
    texts, pairs = load_data()
    W = evaluator()
    R = {"note": "Post hoc development analysis; no model calls; nothing in the product, the plan, the spec or stored runs changed.",
         "product_commit": COMMIT}
    wfs = {"reviewed": ct.convert(REVIEWED), "original": ct.convert(ORIGINAL)}
    stored = json.loads((TMIS / "harness/product/workflows/theft-reviewed/household_theft.json").read_text())
    R["reviewed_workflow_equals_stored"] = json.dumps(wfs["reviewed"], sort_keys=True) == json.dumps(stored, sort_keys=True)
    W.validate_workflow(wfs["original"])
    R["mapping"] = {"background_true": {k: v[1] for k, v in BACKGROUND.items()},
                    "changed": {c: {s_: {"value": v[0], "certainty": v[1]} for s_, v in d.items()} for c, d in CHANGED.items()},
                    "other_facts": "false in every text (no sentence of any text states them; they are inert unless a document need depends on them)",
                    "expert_variants": EXPERT_VARIANTS,
                    "literal_g042_variant": "g042 true in every text: the reviewed condition ('... or the loss was caused or increased "
                                            "through the fault of a third party') read literally includes the unidentified thief"}
    # ---------------- Part 1 and 2
    packs = {"reviewed": theft_v2.TheftPack(load_reviewed.load(REVIEWED), judge_all=True),
             "original": theft_v2.TheftPack(v3.theft_pack("original"), judge_all=True)}
    P1 = {}
    for base, wf in wfs.items():
        P1[base] = {}
        for ev, ex_ in list(EXPERT_VARIANTS.items()) + [("literal g042 (+primary)", None)]:
            at = ("g042",) if ev.startswith("literal") else ()
            exv = EXPERT_VARIANTS[PRIMARY] if ex_ is None else ex_
            plans, on, un = floor(W, wf, texts, pairs, exv, at)
            eng = engine_plans(packs[base], wf, texts, exv) if not at else None
            diffs = None if eng is None else sum(set(plans[t][0]["requests"]) != set(eng[t][0]["requests"]) or
                                                 set(plans[t][0]["holds"]) != set(eng[t][0]["holds"]) for t in texts)
            per_story = defaultdict(list)
            for r_ in on:
                per_story[r_["story"]].append(r_["errors"])
            P1[base][ev] = {"summary": {k: r3(v) for k, v in summ(on, un).items()}, "by_fact": {k: r3(v) for k, v in by_fact(on).items()},
                            "atoms": {c: {f"{a[0]}{a[1]}": n for a, n in v.items()} for c, v in atoms_by_fact(on).items()},
                            "per_story_errors": sorted({r3(sum(v) / len(v)) for v in per_story.values()}),
                            "texts_where_engine_differs": diffs}
        rx = RouteExec(REVIEWED if base == "reviewed" else ORIGINAL)
        base_e = summ(floor(W, wf, texts, pairs, EXPERT_VARIANTS[PRIMARY])[1])["errors"]
        rs = route_sensitivity(rx, wf, texts, pairs, base_e, EXPERT_VARIANTS[PRIMARY])
        P1[base]["route_sensitivity"] = {"items_with_alternatives": len(rx.alt), "alternatives_tried": len(rs),
                                         "lowest_floor_change": min(x["change"] for x in rs),
                                         "changes": [x for x in rs if x["change"] != 0]}
    R["part1_2_floor"] = P1
    R["floor_rules"] = {d: {rid: {"reviewed": rule_quote(REVIEWED, rid), "original": rule_quote(ORIGINAL, rid)} for rid in rids}
                        for d, rids in FLOOR_RULES.items()}
    # ---------------- Part 3 and 4 (fresh2, the finished test)
    t2 = {t: m for t, m in texts.items() if m["story"] >= 8}
    p2 = [p for p in pairs if p["story"] >= 8]
    wf = stored
    fu = used_facts(wf)
    nf = len(wf["facts"])
    ex = Exec(W, wf)
    P3, P4 = {}, {}
    measured = {}
    for arm, (fn, runs, model) in PRODUCT_ARMS.items():
        st = json.loads((CONFIRM / fn).read_text())
        ent = {t: [st.get(f"PRODUCT|{t}|{r}") for r in range(runs)] for t in t2}
        rows = classify(t2, ent, fu, runs)
        tabs = reading_tables(rows, dict(Counter(m["kind"] for m in t2.values())))
        tabs["single_readings"] = reading_verdicts(t2, st, runs, nf, fu)
        tabs["unresolved_pairs_changed"] = unresolved_changes(ex, p2, t2, ent, fu, runs)
        recomputed = sum(sorted(st[k]["plan"]["requests"]) == ex(admitted(st[k], fu))["requests"] for k in st)
        tabs["stored_requests_reproduced_from_admitted_facts"] = f"{recomputed} of {len(st)}"
        P3[arm] = {"model": model, "runs": runs, **tabs}
        Pst = stored_plans(fn, "PRODUCT|{case}|{run}", runs, t2)
        on, un = score(p2, Pst, runs)
        measured[arm] = (on, un)
        P4[arm] = {"model": model}
        for ev in (PRIMARY, "g022 T, g020 F"):
            d = decompose(ex, p2, t2, ent, fu, runs, EXPERT_VARIANTS[ev])
            tot = mean_rows(d)
            tot["product_steps_beyond_readings"] = summ(on)["errors"] - tot["measured"]
            tot["stored_measured"] = summ(on)["errors"]
            P4[arm][ev] = {"total": {k: r3(v) for k, v in tot.items()},
                           "by_fact": {c: {k: r3(v) for k, v in mean_rows([x for x in d if x["condition"] == c]).items()} for c in COND}}
        cf = {}
        for fx in [(), ("g003",), ("g042",), ("g074", "g016"), ("g022",), ("g003", "g042"), ("g003", "g042", "g074", "g016", "g022"),
                   ("changed",), ("changed", "g003", "g042")]:
            s_, bf = counterfactual(ex, p2, t2, ent, fu, runs, set(fx), EXPERT_VARIANTS[PRIMARY])
            cf[",".join(fx) or "none"] = {"errors": r3(s_["errors"]), "unres_unchanged": r3(s_["unres_unchanged"]),
                                         "by_fact": {k: r3(v) for k, v in bf.items()}}
        P4[arm]["counterfactual_fixes"] = cf
    for k, (fn, key, model, rules) in SINGLE.items():
        Pst = stored_plans(fn, key, 3, t2)
        measured[k] = score(p2, Pst, 3)
    same = {}
    for name, (fn, key, model, rules) in SINGLE.items():
        cp = "casepath" if model == "gpt-6-luna" else "casepath_frontier_checklist"
        cps = [cp] + (["casepath_checklist"] if model == "gpt-6-luna" else [])
        rows_ = {}
        for c in COND:
            row = {"single": r3(by_fact(measured[name][0])[c]), "floor_rules_given": r3(P1[rules][PRIMARY]["by_fact"][c])}
            for x in cps:
                row[x] = r3(by_fact(measured[x][0])[c])
                row[f"{x}_minus_single"] = r3(by_fact(measured[x][0])[c] - by_fact(measured[name][0])[c])
            rows_[c] = row
        allr = {"single": r3(summ(*measured[name])["errors"])} | {x: r3(summ(*measured[x])["errors"]) for x in cps}
        same[name] = {"model": model, "rules": rules, "by_fact": rows_, "overall": allr,
                      "single_unres_unchanged": r3(summ(*measured[name])["unres_unchanged"]),
                      "single_atoms": {c: {f"{a[0]}{a[1]}": r3(n / 24) for a, n in sorted(v.items(), key=lambda z: -z[1])[:8]}
                                       for c, v in atoms_by_fact(measured[name][0]).items()}}
        # where the single prompt does better than the floor of the rules it was given
        fl = P1[rules][PRIMARY]["atoms"]
        rep = {}
        for c, at in fl.items():
            a = atoms_by_fact(measured[name][0]).get(c, Counter())
            rep[c] = {atom: {"floor_rate": 1.0, "single_rate": r3(sum(n for (k_, d_), n in a.items() if f"{k_}{d_}" == atom) / 24)}
                      for atom in at}
        same[name]["floor_atoms_in_single"] = rep
        same[name]["facts_below_floor"] = [c for c in COND if by_fact(measured[name][0])[c] < P1[rules][PRIMARY]["by_fact"][c] - 1e-9]
    P4["same_model"] = same
    R["part3_readings"] = P3
    R["part4_decomposition"] = P4
    R["part5"] = part5(fu, nf)
    prev = None
    try:
        prev = json.loads((HERE / "theft_diagnosis.json").read_text()).get("part6_casetype")
    except Exception:  # noqa: BLE001
        pass
    R["part6_casetype"] = part6(W, texts, pairs, prev)
    R["part6_casetype"]["harm"] = part6_harm(texts, pairs, W, prev)
    (HERE / "theft_diagnosis.json").write_text(json.dumps(R, indent=1, ensure_ascii=False, default=str) + "\n")
    (HERE / "theft_diagnosis.md").write_text(markdown(R))
    return R



# ------------------------------------------------------------------------------------------------ markdown
def tbl(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(x) for x in r) + " |" for r in rows])


def f3(x):
    return "–" if x is None else f"{x:.3f}"


ARM_LABEL = {"casepath": "CasePath (gpt-6-luna, 3 runs)", "casepath_checklist": "CasePath, checklist only (gpt-6-luna, 3 runs)",
             "casepath_frontier_checklist": "CasePath, checklist only (gpt-6.1-terra, 1 run)"}
SINGLE_LABEL = {"ric": "Rules in context, reviewed (gpt-6-luna)", "ric_original": "Rules in context, original (gpt-6-luna)",
                "ric_frontier": "Rules in context, reviewed (gpt-6.1-terra)",
                "ric_original_frontier": "Rules in context, original (gpt-6.1-terra)"}


def markdown(R):
    P1, P3, P4 = R["part1_2_floor"], R["part3_readings"], R["part4_decomposition"]
    L = ["# Theft diagnosis: why CasePath on the frontier model does not beat the frontier single prompt",
         "",
         "Generated by `analysis/theft_diagnosis.py`. Post hoc development analysis of the finished Study 3 test (fresh2 is "
         "development data now). Parts 1–4 make no model calls; Part 5 made "
         f"{R['part5']['paid_calls']} paid calls (USD {R['part5']['spend_usd']:.4f}). Nothing in the product, the plan, the "
         "spec, `analysis/study3.py` or the stored runs was changed. Measure throughout: wrong + missed signed changes per "
         "changed-fact pair (study2/study3 scoring, imported), lower is better; 'unchanged' = share of unresolved-fact pairs "
         "with the same requests as the off text.",
         "",
         "**Measured vs inferred.** Measured: every number computed from stored outputs, the product's evaluator at "
         f"`{COMMIT[:8]}` and the two rule files. Inferred: (i) the designed truth of each workflow fact (the mapping below is "
         "written by me from the condition texts; the harness has none), (ii) every counterfactual ('if fact X were read as "
         "designed'), (iii) every statement about what a rule or source *means*.",
         "",
         "## Mapping of the nine designed conditions to workflow facts (inferred; uncertain entries marked)",
         "",
         "Only facts some document need depends on can change a checklist (27 in the reviewed workflow, 26 in the "
         "original); all others are inert. Background facts true in every text:"]
    for k, v in R["mapping"]["background_true"].items():
        L.append(f"- `{k}` true: {v}")
    L.append("")
    L.append("Changed facts (true in the on text, open in the unresolved text, false elsewhere):")
    for c, d in R["mapping"]["changed"].items():
        L.append(f"- {SHORT[c]}: " + "; ".join(f"`{k}` {'T' if v['value'] else 'F'} ({v['certainty']})" for k, v in d.items()))
    L += ["", "Every other fact is false in every text. Two uncertainties are varied: the expert facts (g022 'route selected', "
          "g020 'loss to be determined in expert proceedings', reviewed rules only) and a literal reading of reviewed g042 "
          "that includes the unidentified thief (true in every text).", ""]
    # ---------------- Part 1
    L += ["## Part 1. The rule floor (designed facts, product evaluator, stories 0–15, 144 changed-fact pairs, 96 unresolved pairs)", ""]
    rows = []
    for base in ("reviewed", "original"):
        for ev, v in P1[base].items():
            if ev == "route_sensitivity":
                continue
            s_ = v["summary"]
            rows.append([base, ev, f3(s_["wrong"]), f3(s_["missed"]), f3(s_["errors"]), f3(s_["unres_unchanged"]), f3(s_["unres_held"]),
                         ", ".join(map(str, v["per_story_errors"])), "–" if v["texts_where_engine_differs"] is None else v["texts_where_engine_differs"]])
    L.append(tbl(["Rules", "Mapping", "Wrong", "Missed", "Wrong + missed", "Unresolved unchanged", "Unresolved held", "Per-story values", "Texts where plan_exact differs (of 256)"], rows))
    L += ["", "By changed fact (primary mapping; the floor is identical in all 16 stories):", ""]
    rows = []
    for c in COND:
        rows.append([SHORT[c]] + [f3(P1[b][ev]["by_fact"][c]) for b in ("reviewed", "original") for ev in (PRIMARY, "g022 T, g020 F", "literal g042 (+primary)")]
                    + ["; ".join(P1["reviewed"][PRIMARY]["atoms"].get(c, {}).keys()) or "–", "; ".join(P1["original"][PRIMARY]["atoms"].get(c, {}).keys()) or "–"])
    L.append(tbl(["Changed fact", "Reviewed, primary", "Reviewed, g020 F", "Reviewed, literal g042", "Original, primary", "Original, g020 F",
                  "Original, literal g042", "Floor errors (reviewed)", "Floor errors (original)"], rows))
    fr = R["floor_rules"]
    L += ["", "**Rules and documents responsible** (reference = the frozen contract's acceptable signed changes):", "",
          f"- **SIM card, +D33 wrong (both bases).** Rule 084, condition \"{fr['D33']['overlay_rule_084']['reviewed']['condition']}\", one route "
          f"{fr['D33']['overlay_rule_084']['reviewed']['routes']} (D32 report + D33 bank statement jointly). Reference: +D32 only. Cited source "
          "(theft-source-0185) is an exclusion clause (\"Vermögensschäden aufgrund von missbräuchlicher Nutzung von SIM-Karten, sofern sie "
          "nicht in der Zeit zwischen dem Diebstahl und der Meldung bei der CSS erfolgen\") that names no bank statement. Not changed by the "
          "review (queue item 084).",
          f"- **Third party, D14 missed (both bases).** Rule 010 has no condition; its fact f03 demands D14 (\"{fr['D14']['overlay_rule_010']['reviewed']['title']}\") "
          "on every claim, so D14 is on the off checklist and cannot be added. Reference: +D14 +D15. Not changed by the review (queue item 010: "
          "\"Should the causer section (D14) be requested on every claim, or only where a person who caused the loss is known?\").",
          f"- **Expert procedure, +D23 wrong (reviewed, primary mapping only).** Rule 020's condition was added by the review (\"{fr['D23']['overlay_rule_020']['reviewed']['condition']}\"); "
          "routes [D23] or [D21, D22], cheapest D23. If a written request by one party makes this condition true, D23 is added; the reference "
          "expects +D21 only. In the original, rule 020 is unconditional, so D23 is on both checklists and costs nothing. Whether g020 is true "
          "here is the uncertain mapping; with g020 false the reviewed floor for this fact is 0. Rule 022 (g022, \"The expert-procedure route has "
          "been selected\") gives D21; if a request does not count as 'selected', D21 is missed (g022 F rows).",
          f"- **Scheduled valuable, +D10 wrong (original only).** Rules 074 and 016 demanded receipt and expert valuation jointly (route "
          f"{fr['D10']['overlay_rule_074']['original']['routes']}); the reference accepts either. The review split both into alternatives "
          "(RECONCILIATION.md), which removes this floor error.",
          "- **Literal g042.** Reviewed condition: \"CSS has paid benefits for which the policyholder could assert claims against third parties, "
          "or the loss was caused or increased through the fault of a third party.\" Read literally, the unidentified thief is such a third "
          "party, so D15 is on every off checklist and the third-party pair misses it too (floor 2.0 for that fact). Reference: +D15 when an "
          "identified contractor caused the loss. Changed by the review only in wording ('has claims' -> 'could assert claims'), not narrowed.",
          ""]
    # ---------------- Part 2
    L += ["## Part 2. Conversion", ""]
    for b in ("reviewed", "original"):
        rs = P1[b]["route_sensitivity"]
        L.append(f"- {b}: the converted workflow under the product's evaluator equals `TheftPack.plan_exact` (requests and holds) on all "
                 f"256 texts under every mapping variant. {rs['items_with_alternatives']} evidence items have alternative routes; switching "
                 f"each alone to each alternative ({rs['alternatives_tried']} switches) never lowers the floor (smallest change "
                 f"{rs['lowest_floor_change']:+.3f}); the switches that change it raise it: "
                 + ("; ".join(f"{x['item']} {x['chosen']}->{x['alternative']} {x['change']:+.3f}" for x in rs["changes"]) or "none") + ".")
    L += ["", "**Finding:** no part of the floor is caused by the conversion. The joint routes that cost errors (084: D32+D33; original "
          "074/016: D09+D10) are joint in the rule base itself, and the cheapest-route choice is the one plan_exact makes.", ""]
    # ---------------- Part 3
    L += ["## Part 3. What the readings did (fresh2, the finished test)", "",
          "Admitted = established and accepted in the stored `product_extra.facts` (all readings agree, quotation found); these reproduce "
          + ", ".join(f"{P3[a]['stored_requests_reproduced_from_admitted_facts']} ({a})" for a in P3) + " stored request sets through the "
          "evaluator. Single readings are parsed from the response cache (three per text-run in every entry).", "",
          "**(a) The changed condition in on texts** (text-runs; a key fact is one whose truth adds the reference document):", ""]
    rows = []
    for c in COND:
        rows.append([SHORT[c]] + [", ".join(f"{k} {v}" for k, v in P3[a]["changed_condition_on"].get(c, {}).items() if k != "text_runs")
                                  + f" / {P3[a]['changed_condition_on'].get(c, {}).get('text_runs')}" for a in P3])
    L.append(tbl(["Changed fact"] + [ARM_LABEL[a] for a in P3], rows))
    L += ["", "Single readings on the key facts of on texts (all readings, before agreement):", ""]
    keys_ = sorted({k for a in P3 for k in P3[a]["single_readings"]["key_on"]}, key=lambda k: COND.index(k.split("|")[0]))
    L.append(tbl(["Condition, fact"] + [ARM_LABEL[a] for a in P3],
                 [[f"{SHORT[k.split('|')[0]]}, {k.split('|')[1]}"] + [", ".join(f"{x} {n}" for x, n in P3[a]["single_readings"]["key_on"].get(k, {}).items()) for a in P3] for k in keys_]))
    L += ["", "**(b) Facts false by design admitted true (outside the changed condition), text-runs:**", ""]
    L.append(tbl(["Text kind"] + [ARM_LABEL[a] for a in P3],
                 [[k] + [json.dumps(P3[a]["false_admitted_true"].get(k, {})) for a in P3] for k in ("off", "on", "unresolved")]))
    L += ["", "**(c) Background facts true by design not admitted true** (g003 = crime-scene traces; open = no agreed value):", ""]
    L.append(tbl(["Text kind"] + [ARM_LABEL[a] for a in P3],
                 [[k] + [json.dumps(P3[a]["true_not_admitted"].get(k, {})) for a in P3] for k in ("off", "on", "unresolved")]))
    L += ["", "Single readings of g042 and g003:", ""]
    L.append(tbl(["Item"] + [ARM_LABEL[a] for a in P3],
                 [["g042 in off texts"] + [json.dumps(P3[a]["single_readings"]["g042_off"]) for a in P3],
                  ["g042 in unresolved texts of other conditions"] + [json.dumps(P3[a]["single_readings"]["g042_unresolved_other_conditions"]) for a in P3]]
                 + [[f"g003 in {k} texts"] + [json.dumps(P3[a]["single_readings"]["g003"].get(k, {})) for a in P3] for k in ("off", "on_other", "on_repair", "unresolved")]))
    ex_ = P3["casepath_frontier_checklist"]["single_readings"]["examples"]
    exl = P3["casepath"]["single_readings"]["examples"]
    L += ["", "**Examples of quotations.**", "",
          "- g042 (rule 042, third-party fault) admitted true in an off text, gpt-6.1-terra: " + "; ".join(f"{e['text']} reading {e['reading']}: \"{e['quote']}\"" for e in ex_.get("g042_rev_92ab8925|true|off", [])) + ". "
          "gpt-6-luna, single readings that also said true (not admitted, others disagreed): " + "; ".join(f"{e['text']}: \"{e['quote']}\"" for e in exl.get("g042_rev_92ab8925|true|off", [])) + ".",
          "- g003 (rule 003, traces or contemplated alterations) true in repair texts, gpt-6.1-terra: " + "; ".join(f"{e['text']} reading {e['reading']}: \"{e['quote']}\"" for e in ex_.get("g003|true|repair", [])) + ".",
          "- g022 (expert route selected) not given a value by gpt-6.1-terra on \"The policyholder has requested the formal expert determination procedure in writing.\": "
          + "; ".join(f"{e['text']} reading {e['reading']} {k.split('|')[1]}: \"{e['quote']}\"" for k in ("g022|not_stated|on", "g022|open|on") for e in ex_.get(k, [])) + ".",
          "- g074 (\"The provision applies to valuables or individual objects listed in the insurance contract with an insured value of at least CHF 1'000\") on the watch sentence: gpt-6.1-terra not_stated in "
          + ", ".join(f"{e['text']} reading {e['reading']}" for e in ex_.get("g074|not_stated|on", [])) + "; gpt-6-luna false with the very sentence as quotation: "
          + "; ".join(f"{e['text']} reading {e['reading']}: \"{e['quote']}\"" for e in exl.get("g074|false|on", [])) + ".", ""]
    L += ["**(d) Open conditions given a value in unresolved texts:** " + "; ".join(f"{ARM_LABEL[a]}: {len(P3[a]['open_given_value'])}" for a in P3)
          + " (none). **Why the frontier product leaves only 75% of unresolved pairs unchanged:** the 12 changed unresolved pairs are:", ""]
    for a in P3:
        ch = P3[a]["unresolved_pairs_changed"]
        CAUSE = {"D15": "D15 via g042", "D26": "D26/D27 via g003", "D27": "D26/D27 via g003", "D07": "D07/D25 via background facts",
                 "D25": "D07/D25 via background facts"}
        cnt = Counter(c_ for r_ in ch for c_ in {CAUSE.get(d[1:], "other") for d in r_["delta"]})
        L.append(f"- {ARM_LABEL[a]}: {len(ch)} changed pair-runs of {R['part3_readings'][a]['text_runs']['unresolved'] * P3[a]['runs']}; "
                 "pair-runs involving each cause (a pair-run can have two): " + ", ".join(f"{k} {v}" for k, v in cnt.most_common()) + ".")
    L += ["", "With gpt-6.1-terra, 8 of 8 third-party unresolved pairs (and one scheduled-valuable pair) change because g042 is admitted true in the off text from the sentence "
          "\"No identifiable third party caused or enlarged the loss apart from the unidentified thief.\" (D15 requested), and the "
          "unresolved text replaces exactly that sentence by an open one (g042 open, D15 held): -D15 (in the scheduled-valuable pair g042 "
          "was simply not agreed in the variant). The other changes are +/-D26 +/-D27 from g003 (traces) flipping between texts of a story; "
          "with gpt-6-luna nearly all changes are of this kind. No condition left open by design received a value.", ""]
    # ---------------- Part 4
    L += ["## Part 4. Decomposition", "",
          "Method (per changed-fact pair-run, evaluator on admitted facts, path order fixed): F floor (designed facts in both texts); "
          "O off misreading = error with the off text as read and the variant read identically except its changed condition at its "
          "designed value, minus F (what a misread off text costs every pair of its story); C changed condition = from O's state, the "
          "variant's changed-condition facts as read; S other conditions = from O's state, the variant's other facts as read (spill-over "
          "and unstable background facts); I interaction remainder = measured - F - O - C - S. F + O + C + S + I equals the measured value "
          "recomputed from the admitted facts; 'product steps' is the stored value minus that (one luna entry whose stored requests differ "
          "from its admitted facts).", ""]
    rows = []
    for a in PRODUCT_ARMS:
        for ev in (PRIMARY, "g022 T, g020 F"):
            t = P4[a][ev]["total"]
            rows.append([ARM_LABEL[a], ev, f3(t["floor"]), f3(t["off"]), f3(t["changed"]), f3(t["other"]), f3(t["remainder"]),
                         f3(t["product_steps_beyond_readings"]), f3(t["stored_measured"])])
    L.append(tbl(["Design", "Mapping", "Floor F", "Off misreading O", "Changed condition C", "Other conditions S", "Interaction I",
                  "Product steps", "Measured (stored)"], rows))
    L += ["", "By changed fact (primary mapping; F / O / C / S, I is 0 in every cell):", ""]
    rows = []
    for c in COND:
        rows.append([SHORT[c]] + [" / ".join(f3(P4[a][PRIMARY]["by_fact"][c][k]) for k in ("floor", "off", "changed", "other")) + f" = {f3(P4[a][PRIMARY]['by_fact'][c]['measured'])}" for a in PRODUCT_ARMS])
    L.append(tbl(["Changed fact"] + [ARM_LABEL[a] for a in PRODUCT_ARMS], rows))
    L += ["", "**Counterfactual repairs of single facts** (inferred upper bounds: the stored admitted facts with the named facts set to their "
          "designed value in every text; nothing else changed; wrong + missed per pair, unresolved unchanged):", ""]
    cfk = list(P4["casepath_frontier_checklist"]["counterfactual_fixes"])
    L.append(tbl(["Facts set to design"] + [ARM_LABEL[a] for a in PRODUCT_ARMS],
                 [[k] + [f"{f3(P4[a]['counterfactual_fixes'][k]['errors'])} ({f3(P4[a]['counterfactual_fixes'][k]['unres_unchanged'])})" for a in PRODUCT_ARMS] for k in cfk]))
    # same model
    SM = P4["same_model"]
    L += ["", "### Same-model comparison per changed fact (fresh2; product minus single prompt; negative = product better)", ""]
    for name in ("ric_frontier", "ric_original_frontier", "ric", "ric_original"):
        v = SM[name]
        cps = [k for k in v["by_fact"][COND[0]] if k.endswith("_minus_single")]
        head = ["Changed fact", "Floor of the rules given", SINGLE_LABEL[name]] + [ARM_LABEL[k[:-len("_minus_single")]] for k in cps] + ["Difference: " + k[:-len("_minus_single")] for k in cps]
        rows = [[SHORT[c], f3(v["by_fact"][c]["floor_rules_given"]), f3(v["by_fact"][c]["single"])] + [f3(v["by_fact"][c][k[:-len("_minus_single")]]) for k in cps]
                + [f"{v['by_fact'][c][k]:+.3f}" for k in cps] for c in COND]
        rows.append(["**all**", "", f3(v["overall"]["single"])] + [f3(v["overall"][k[:-len("_minus_single")]]) for k in cps]
                    + [f"{v['overall'][k[:-len('_minus_single')]] - v['overall']['single']:+.3f}" for k in cps])
        L += [f"**{SINGLE_LABEL[name]}** (unresolved unchanged {f3(v['single_unres_unchanged'])}):", "", tbl(head, rows), ""]
    L += ["### Where the single prompt does better than the floor of the rules it was given", ""]
    for name in ("ric_frontier", "ric_original_frontier", "ric", "ric_original"):
        v = SM[name]
        rep = "; ".join(f"{SHORT[c]} {atom}: floor 1.000, single {d['single_rate']:.3f}" for c, at in v["floor_atoms_in_single"].items() for atom, d in at.items())
        L.append(f"- {SINGLE_LABEL[name]}: facts whose error is below the floor (primary mapping): "
                 f"{', '.join(SHORT[c] for c in v['facts_below_floor']) or 'none'}. Rate of the floor's own error atoms in the single prompt: {rep}.")
    L += ["", "Reading: the frontier single prompt repeats rule 084's +D33 on every SIM pair (reviewed and original) and rule 074/016's joint "
          "+D10 on every scheduled-valuable pair (original); it 'repairs' rule 010 (adds D14 when the contractor is identified) in 50% of "
          "third-party pair-runs with the reviewed rules and 12.5% with the original rules, but with the reviewed rules it also adds or "
          "withdraws D14 wrongly on the other facts (w+D14 / w-D14 on 8 of 9 facts). Its only fact below the floor is the expert procedure "
          "with the reviewed rules (0.708 vs 1.000), and only under the mapping in which g020 is true (with g020 false the floor is 0). Its "
          "losses are elsewhere: D24 (repair) missed in 100% of repair pairs with both rule bases, D31 (declined) missed in 100% with the "
          "reviewed and 42% with the original rules.", ""]
    # ---------------- Part 5
    p5 = R["part5"]
    L += ["## Part 5. Remedies", "",
          "Budget instruction followed: at most USD 2.00, only for a remedy Parts 1–4 point to, design written before any paid call, stop when "
          "the outcome cannot change the conclusion.", "",
          "- (a) Wording / a code-checkable 'the quoted sentence must state the value' rule: the frontier's main errors are not inferences "
          "beyond the text. Its g042 quotation is the sentence that literally states a third party at fault (the thief), and its g074 / g022 "
          "failures are refusals to infer (not_stated) where the condition's wording ('the provision applies', 'route selected') differs from "
          "the sentence. A stricter quotation rule would leave g042 unchanged and make g074 / g022 worse. Not run.",
          "- (b) Reasoning effort: the readings' effort is the constant `READING_EFFORT = \"low\"` in the product (sent, since the Study 3 "
          "spec sets `CASEPATH_MODEL_REASONING=true`; median 81 reasoning tokens per frontier call). Raising it needs a product code change, "
          "which this task excludes; it cannot fix g042 (a correct literal reading). Not run.",
          "- (c) Executing the original rules: model-free floor 0.333 (same as reviewed, primary mapping) and 0.333 vs 0.222 when g020 is "
          "false; the original rule 042 condition (\"... or a third party caused or increased the loss\") is at least as broad, and gpt-6-luna "
          "reads the same off sentence the same way. No floor gain; not run.",
          f"- (d) Source passage next to each condition: **run** (design below). {p5['paid_calls']} paid calls, USD {p5['spend_usd']:.4f}.", "",
          "Design: " + p5["design"]["question"] + " Why: " + p5["design"]["why_this_one"] + " Texts: " + p5["design"]["texts"]
          + ". Decision rule: " + p5["design"]["decision_rule"] + ". Variant: " + p5["design"]["variant"] + ".", ""]
    rows = []
    for t, d in p5["texts"].items():
        for f in ("g042_rev_92ab8925", "g003", "g022", "g074"):
            rows.append([t, f, "; ".join(f"{x[0]}" for x in d["baseline_readings"][f] if x), "; ".join(f"{x[0]}" for x in d["variant_readings"][f] if x),
                         (d["variant_readings"][f][0] or ["", ""])[1][:90]])
    L.append(tbl(["Text (run 0)", "Fact", "Baseline: three readings", "With passages: three readings", "Quotation (with passages, reading 1)"], rows))
    L += ["", "Result: with its source passages (including \"Rückgriff gegen Dritte (z. B. eine Transportfirma)\") shown, all three readings "
          "still admit g042 true on the off sentence in both stories, quoting it. (d) cannot repair the decisive error; by the decision rule "
          "no further text was run. Side observation (two texts only, not a result): g003 went from not agreed to three agreeing 'true' "
          "readings in both off texts.", "",
          "- (e) The floor and the rule conditions: the frontier product's excess over the floor comes mostly from two conditions flagged "
          "in Study 1 as broader than their sources (003, 042) and from two conditions whose wording is not a case fact (074 'the provision "
          "applies', 022 'route selected'). These are rule problems; readings cannot fix them without the rules changing.", "",
          "## Conclusion", ""]
    L += [CONCLUSION, ""]
    L += part6_md(R.get("part6_casetype") or {})
    return "\n".join(L) + "\n"


CONCLUSION = (
    "1. With these rules the product on gpt-6.1-terra cannot be shown to beat the frontier single prompt on theft: the floor of the "
    "reviewed rules under perfect facts is 0.333 wrong + missed per pair (0.222–0.444 over the uncertain mappings; original rules 0.333), "
    "the frontier product measured 0.833 in one run, and its excess of 0.500 over the floor comes from reading rule conditions that "
    "are broader than or worded differently from what the sources mean (g042 third-party fault includes the thief: off misreading "
    "0.111 and the 75% on unresolved pairs; g003 traces flip between texts: setting g003 to its designed value alone removes 0.250; g074 'the provision applies' and "
    "g022 'route selected' left open: 0.097, or 0.208 if g020 is false), not from conversion (0) or from open facts given values (0). "
    "2. The single prompt with the same rules makes the same floor errors (+D33 on every SIM pair; +D10 on every scheduled-valuable pair "
    "with the original rules), repairs rule 010's D14 only partly (50% and 12.5% of third-party pair-runs) and is below the floor on no "
    "fact except the expert procedure under the uncertain g020 mapping; it wins on third party (1.21–1.29 vs 2.38), expert (0.63–0.71 vs "
    "1.25) and bicycle (0.08–0.46 vs 0.63) and loses on repair, declined and deadline, where the product is at or near 0. "
    "3. The smallest general change that could make the product win is in the rule base, not in the readings: re-derive each "
    "condition from its cited passages as a case fact that a claim text can state, by independent derivations of the frontier model that "
    "must agree (disagreements, and every condition true for a bare theft by an unknown thief, go to a jurist), and resolve the review-"
    "queue items 003, 010, 042 and 084; the model-free bound for fixing only g003 and g042 is 0.417 (100% unchanged on unresolved pairs) "
    "against 0.671 and 0.949, and for all four flagged facts 0.222. "
    "4. Showing the source passages to the reading (variant (d)) did not change the decisive g042 reading in two off texts (USD 0.12), "
    "so the change has to be made in the conditions themselves; reasoning effort is a product constant and cannot repair a literally "
    "correct reading. "
    "5. Test: freeze the re-derived rule base before any run, convert it unchanged with convert_theft, and run the product (checklist "
    "only) and Rules in context with the same new rules and the original rules on gpt-6.1-terra, three runs each, on development stories "
    "4–15, with the floor recomputed model-free first; the claim holds only if the product is lower than both single prompts per changed "
    "fact cluster (sign-flip over the nine facts) and the result is then confirmed on unseen stories.")


# ------------------------------------------------------------------------------------------------ Part 6: case-type reading
SCRATCH = Path("/tmp/claude-0/-home-user-casepath/ef865128-25b1-5a5b-af7f-a334bf6c5b16/scratchpad")
CASETYPE_WORDING = ("The files are one case of the case type named above. Take as given what every case of that type involves. "
                    "Answer a condition true only when the files state something beyond what the case type itself involves: the "
                    "event that defines the case type, and what that event necessarily implies, never make a condition true. A "
                    "condition is true only if the sentence you quote states it; do not infer it from a neighbouring fact.")
FOUR = ("g042", "g003", "g074", "g016", "g022", "g020")


def compact(entry, fu, nf):
    rd = readings(entry, nf)
    facts = (entry.get("product_extra") or {}).get("facts") or {}
    return {"status": entry.get("status"), "plan": entry.get("plan"),
            "facts": {f: {k: facts[f].get(k) for k in ("status", "value", "verdict")} for f in fu if f in facts},
            "readings": {f: [x.get(f) for x in rd] for f in fu if stem(f) in FOUR}}


def part6(W, texts, pairs, prev):
    """Arms A (setting off) and B (setting on) of the case-type reading on the branch head with reading_case_type.patch."""
    wf = json.loads((TMIS / "harness/product/workflows/theft-reviewed/household_theft.json").read_text())
    fu, nf, ex = used_facts(wf), len(wf["facts"]), Exec(W, wf)
    data = {}
    for arm in ("A", "B"):
        f = SCRATCH / f"arm_{arm}.json"
        if f.exists():
            raw = json.loads(f.read_text())
            data[arm] = {k.split("|")[1]: compact(v, fu, nf) for k, v in raw.items()}
        else:
            data[arm] = ((prev or {}).get("data") or {}).get(arm, {})
    ledger = TMIS / "runs" / "product" / "ledger_dev_gpt-6.1-terra.jsonl"
    rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    spend = {arm: round(sum(r["usd"] for r in rows if r.get("arm") == f"theft-diagnosis-casetype-{arm}"), 4) for arm in ("A", "B")}
    out = {"wording": CASETYPE_WORDING, "data": data, "spend_usd_terra": spend}
    stored = json.loads((CONFIRM / "plans_theft_casepath_checklist_frontier.json").read_text())
    arms = {"stored product (6a72159c)": {t: stored[f"PRODUCT|{t}|0"] for t in texts if t in data["A"] or t in data["B"]}}
    for arm in ("A", "B"):
        arms[arm] = {t: {"plan": s3.to_names(v["plan"], INV), "product_extra": {"facts": v["facts"]}} for t, v in data[arm].items()}
    # admitted values of the four conditions
    adm = {}
    for name, ent in arms.items():
        adm[name] = {}
        for t in sorted(ent, key=lambda x: (texts[x]["story"], x)):
            a = admitted(ent[t], fu)
            adm[name][t] = {f: a[f] for f in fu if stem(f) in FOUR}
    out["admitted_four"] = adm
    # scores per story, on the pairs whose two texts arm B ran; every other design scored on the same pairs
    res, dec, sp_all = {}, {}, []
    for story in (8, 9):
        spB = [p for p in pairs if p["story"] == story and p["off"] in data["B"] and p["variant"] in data["B"]]
        if not spB:
            continue
        sp_all += spB
        tx = {t for p in spB for t in (p["off"], p["variant"])}
        key = f"story {story}"
        res[key] = {"pairs": {"on": sum(p["kind"] == "on" for p in spB), "unresolved": sum(p["kind"] == "unresolved" for p in spB)}}
        for name, ent in arms.items():
            if not tx <= set(ent):
                res[key][name] = "not run on these texts"
                continue
            on, un = score(spB, {t: [s3.to_names(ent[t]["plan"], INV)] for t in tx}, 1)
            res[key][name] = {"summary": {k: r3(v) for k, v in summ(on, un or None).items()}, "by_fact": {k: r3(v) for k, v in by_fact(on).items()},
                              "atoms": {c: {f"{a[0]}{a[1]}": n for a, n in v.items()} for c, v in atoms_by_fact(on).items()}}
        for k, (fn, key_, model, rules) in SINGLE.items():
            if model != "gpt-6.1-terra":
                continue
            P = stored_plans(fn, key_, 3, {t: texts[t] for t in tx})
            on, un = score(spB, P, 3)
            res[key][SINGLE_LABEL[k]] = {"summary": {kk: r3(v) for kk, v in summ(on, un or None).items()}, "by_fact": {kk: r3(v) for kk, v in by_fact(on).items()}}
        fl = floor(W, wf, {t: texts[t] for t in tx}, spB, EXPERT_VARIANTS[PRIMARY])
        res[key]["floor (reviewed, primary)"] = {"summary": {k: r3(v) for k, v in summ(fl[1], fl[2] or None).items()}, "by_fact": {k: r3(v) for k, v in by_fact(fl[1]).items()}}
        for name in ("A", "B", "stored product (6a72159c)"):
            if not tx <= set(arms[name]):
                continue
            ent = {t: [arms[name][t]] for t in tx}
            for ev in (PRIMARY, "g022 T, g020 F"):
                d = decompose(ex, spB, texts, ent, fu, 1, EXPERT_VARIANTS[ev])
                tot = mean_rows(d)
                tot["stored_measured"] = res[key][name]["summary"]["errors"]
                dec[f"{key} | {name} | {ev}"] = {k: r3(v) for k, v in tot.items()}
    out["decomposition"] = dec
    out["pairs_scored"] = {"on": sum(p["kind"] == "on" for p in sp_all), "unresolved": sum(p["kind"] == "unresolved" for p in sp_all)}
    out["reproduced"] = {name: f"{sum(sorted(s3.to_names(arms[name][t]['plan'], INV)['requests']) == ex(admitted(arms[name][t], fu))['requests'] for t in arms[name])} of {len(arms[name])}"
                         for name in ("A", "B")}
    sp = sp_all
    out["scores"] = res
    bgc = {}
    for name in ("stored product (6a72159c)", "A", "B"):
        ent = arms[name]
        n = len(ent)
        bgc[name] = {"text_runs": n,
                     "admitted_true": {stem(f): sum(admitted(ent[t], fu)[f] is True for t in ent) for f in fu if stem(f) in ("g002", "g004", "g005", "g006", "g003", "g042")},
                     "requested": {d: sum(d in {IDS.get(x, x) for x in s3.to_names(ent[t]["plan"], INV)["requests"]} for t in ent) for d in ("D07", "D25", "D15", "D26")},
                     "held": {d: sum(d in {IDS.get(x, x) for x in s3.to_names(ent[t]["plan"], INV)["holds"]} for t in ent) for d in ("D07", "D25", "D15", "D16", "D21", "D23")}}
    out["background_and_documents"] = bgc
    out["verdict"] = PART6_VERDICT
    # unresolved changes
    out["unresolved_changes"] = {name: unresolved_changes(ex, [p for p in sp if p["off"] in arms[name] and p["variant"] in arms[name]], texts,
                                                          {t: [arms[name][t]] for t in arms[name]}, fu, 1) for name in arms} if sp else {}
    return out



PART6_VERDICT = (
    "**Verdict.** Decision rule (fixed before running): supported if in B the third-party condition is no longer admitted true in "
    "the off texts and wrong + missed per pair on stories 8 and 9 is lower than A and lower than the frontier single prompt with "
    "both rule bases. Measured: g042 is admitted in no B text (off texts of both stories included); B 0.556 per pair on story 8 "
    "and 0.556 on story 9 against A 3.111 (story 8; A on story 9 not run, cap), Rules in context original 0.630 / 0.667 and reviewed "
    "0.926 / 1.037; unresolved pairs unchanged 6 of 6 (story 8). The rule is met, so the harm check was run, but the margin over "
    "the original-rules single prompt is less than one error per story in one run (5 vs 5.7 and 6.0 errors over 9 pairs). "
    "The harm check fails, and it shows what B's gain consists of: (1) on the frontier model the readings answer not_stated for the "
    "defining-event facts the rules use as conditions (g002, g004, g005, g006 admitted in 0 of 26 B text-runs against 26 of 26 "
    "stored), so the police report D07 and D25 are requested in no B checklist and held in all, and D15, D16, D21, D23 are held "
    "in every text; the pair measure cannot see this because the loss is the same in both texts of a pair; (2) on gpt-6-luna "
    "the same instruction makes those facts unstable between texts (g006 admitted 20 / 96 text-runs vs 96 / 96 off; D07 requested "
    "64 / 96, D25 29 / 96), and theft wrong + missed rises from 0.370 to 1.870 per pair (three runs each; per run 0.389, 0.389, "
    "0.333 vs 2.722, 1.556, 1.333) with unresolved pairs unchanged falling from 97% to 17%; (3) on tenancy (40 claims, one run) "
    "stated facts left open rise from 0.025 to 0.275 per claim (spread 0.095) and held required-now documents from 0 to 0.175: "
    "the readings refuse stated branch facts of a defect dispute (heating, mold, health effects) and the defining notice itself "
    "as 'what the case type involves'. Arm A shows separately that the branch's own reading sentences destabilise the frontier "
    "model's off text (g042 not agreed in s8-off but admitted in 13 of 15 variants; g003 the reverse): 3.111 per pair on story 8 "
    "against 0.778 for the stored run of the tested commit. The idea is not supported as a product setting.")


HARM_SPREAD = {  # 2 x standard error of a between-run mean difference over 40 claims, from the stored 3 luna checklist runs (fresh2)
    "note": "per-claim between-run difference sd over the 96 fresh2 claims x 3 run pairs of runs/study3/confirm/plans_tenancy_casepath_checklist.json",
    "strict_unsafe": 0.317, "spurious_hold": 0.429, "stated_open": 0.095}


def part6_harm(texts, pairs, W, prev):
    """Harm check on gpt-6-luna (setting on vs off, branch head + patch, checklist only)."""
    f = SCRATCH / "luna_results.json"
    if not f.exists():
        return (prev or {}).get("harm")
    sys.path.insert(0, str(TMIS / "dev_probe"))
    import tenancy_probe as TP  # noqa: E402
    Dt = common.data("tenancy", "fresh")
    raw = json.loads(f.read_text())
    ten, theft = {}, {}
    for job, e in raw.items():
        regime, c, r, setting = job.split("|")
        if regime.startswith("tenancy"):
            ref = (Dt if regime == "tenancy-fresh" else TP).reference(c)
            row = s2.ten_row(ref, e.get("plan"))
            fx = (e.get("product_extra") or {}).get("facts") or {}
            left = [k for k, v in ref["fact_states"].items() if v.startswith(("stated", "denied")) and k in fx and fx[k]["status"] != "established"]
            ten.setdefault(f"{regime}|{c}", {})[setting] = {"strict_unsafe": row["strict_unsafe"], "spurious_hold": row["spurious_hold"],
                                                            "held_req": row["held_req"], "stated_open": len(left), "stated_left_open": left,
                                                            "status": e.get("status")}
        else:
            theft.setdefault(setting, {}).setdefault(c, {})[int(r)] = s3.to_names(e.get("plan"), INV)
    out = {"spread": HARM_SPREAD, "tenancy": {}, "theft": {}}
    for subset in ("tenancy-fresh", "tenancy-probe", "all"):
        ks = [k for k in ten if subset == "all" or k.startswith(subset + "|")]
        if not ks:
            continue
        m_ = {}
        for m in ("strict_unsafe", "spurious_hold", "held_req", "stated_open"):
            off = sum(ten[k]["false"][m] for k in ks) / len(ks)
            on = sum(ten[k]["true"][m] for k in ks) / len(ks)
            m_[m] = {"off": r3(off), "on": r3(on), "on_minus_off": r3(on - off)}
        out["tenancy"][subset] = {"claims": len(ks), **m_}
    out["tenancy_stated_left_open_with_setting_on"] = dict(Counter(x for k in ten for x in ten[k]["true"]["stated_left_open"]))
    out["tenancy_stated_left_open_with_setting_off"] = dict(Counter(x for k in ten for x in ten[k]["false"]["stated_left_open"]))
    if theft:
        for setting in ("false", "true"):
            ent = theft.get(setting, {})
            runs = min((len(v) for v in ent.values()), default=0)
            tx = {t for t in ent if len(ent[t]) >= runs}
            sp = [p for p in pairs if p["off"] in tx and p["variant"] in tx]
            if not sp or runs == 0:
                continue
            P = {t: [ent[t][r] for r in range(runs)] for t in tx}
            per_run = []
            for r in range(runs):
                on, un = score(sp, {t: [P[t][r]] for t in tx}, 1)
                per_run.append({k: r3(v) for k, v in summ(on, un).items()})
            on, un = score(sp, P, runs)
            wfj = json.loads((TMIS / "harness/product/workflows/theft-reviewed/household_theft.json").read_text())
            fu_ = used_facts(wfj)
            raws = [e for job, e in raw.items() if job.startswith("theft|") and job.endswith("|" + setting)]
            out["theft"]["on" if setting == "true" else "off"] = {
                "runs": runs, "summary": {k: r3(v) for k, v in summ(on, un).items()}, "per_run": per_run,
                "by_fact": {k: r3(v) for k, v in by_fact(on).items()}, "text_runs": len(raws),
                "admitted_true": {stem(f): sum(admitted(e, fu_)[f] is True for e in raws) for f in fu_ if stem(f) in ("g002", "g004", "g005", "g006", "g003", "g042")},
                "requested": {d: sum(d in {IDS.get(x, x) for x in s3.to_names(e.get("plan"), INV)["requests"]} for e in raws) for d in ("D07", "D25", "D15")}}
    out["data_tenancy"] = ten
    return out



def part6_md(P):
    if not P or not P.get("data", {}).get("A"):
        return []
    L = ["## Part 6. Follow-up: the case-type reading (decided in advance)", "",
         "Setting `CASEPATH_READING_CASE_TYPE` (off by default) on the branch head `1b96f82e`, patch "
         "`analysis/reading_case_type.patch` (with `tests/test_reading_case_type.py`; the product's 242 tests pass with it). With the "
         "setting off the reading request is the branch's own, byte for byte. With it on, the line 'The case is a <workflow title>.' "
         "becomes 'Case type: <workflow title> (<description, if the workflow has one>).' followed by this wording, written once and not "
         "revised after any result:", "", "> " + P["wording"], "",
         f"Spend on gpt-6.1-terra: arm A USD {P['spend_usd_terra']['A']:.4f}, arm B USD {P['spend_usd_terra']['B']:.4f}. "
         f"Pairs scored (both texts run in both arms): {P.get('pairs_scored')}.", ""]
    adm = P["admitted_four"]
    names = list(adm)
    texts_ = list(adm.get("A", {}))
    facts_ = sorted({f for n in adm for t in adm[n] for f in adm[n][t]}, key=lambda f: FOUR.index(stem(f)))
    def v(x):
        return "T" if x is True else "F" if x is False else "·"
    L += ["Admitted values of the four conditions (T true, F false, · no agreed value); columns: " + ", ".join(stem(f) for f in facts_), ""]
    L.append(tbl(["Text"] + names, [[t] + [" ".join(v(adm[n].get(t, {}).get(f)) for f in facts_) for n in names] for t in texts_]))
    sc = P.get("scores") or {}
    for story, r in sc.items():
        cols = [n for n in r if n != "pairs" and isinstance(r[n], dict)]
        L += ["", f"**{story}** ({r['pairs']['on']} changed-fact pairs, {r['pairs']['unresolved']} unresolved pairs; one run per arm; single "
              "prompts: mean of 3 stored runs; not run: " + (", ".join(n for n in r if isinstance(r[n], str)) or "none") + "). Wrong + missed per pair:", ""]
        L.append(tbl(["Changed fact"] + cols, [[SHORT[c]] + [f3(r[n]["by_fact"].get(c)) for n in cols] for c in COND]
                     + [["**all**"] + [f3(r[n]["summary"]["errors"]) for n in cols],
                        ["unresolved unchanged"] + [f3(r[n]["summary"].get("unres_unchanged")) for n in cols]]))
    if P.get("decomposition"):
        L += ["", "Decomposition (method of Part 4; F + O + C + S + I = measured):", ""]
        L.append(tbl(["Story, design, mapping", "Floor F", "Off misreading O", "Changed condition C", "Other conditions S", "Interaction I", "Measured"],
                     [[k.replace(" | ", ", "), f3(d["floor"]), f3(d["off"]), f3(d["changed"]), f3(d["other"]), f3(d["remainder"]), f3(d["stored_measured"])]
                      for k, d in P["decomposition"].items()]))
    bg = P.get("background_and_documents") or {}
    if bg:
        L += ["", "Defining-event facts and the documents that depend on them, gpt-6.1-terra (text-runs; g002 'loss connected with theft', "
              "g004 'after the feared event', g005 'contents coverage for theft damage', g006 'the event is theft'; D07 police report, D25 "
              "insurer's instruction on measures; both depend only on these facts):", ""]
        L.append(tbl(["Design", "Text-runs", "Admitted true", "Requested", "Held"],
                     [[n, v["text_runs"], json.dumps(v["admitted_true"]), json.dumps(v["requested"]), json.dumps(v["held"])] for n, v in bg.items()]))
    H = P.get("harm")
    if H:
        L += ["", "**Harm check on gpt-6-luna** (setting on vs off, branch head with the patch, checklist only). Threshold for harm = the "
              "stored run-to-run spread: 2 x the standard error of a between-run mean difference over 40 claims ("
              + ", ".join(f"{k} {v}" for k, v in H["spread"].items() if k != "note") + ").", ""]
        rows = []
        for sub, v in H["tenancy"].items():
            rows.append([sub, v["claims"]] + [f"{f3(v[m]['off'])} / {f3(v[m]['on'])} ({v[m]['on_minus_off']:+.3f})" for m in ("strict_unsafe", "spurious_hold", "held_req", "stated_open")])
        L.append(tbl(["Tenancy subset", "Claims", "Strict unsafe off / on", "Spurious holds off / on", "Held required-now off / on", "Stated facts left open off / on"], rows))
        L += ["", "Stated facts left open with the setting on: " + json.dumps(H["tenancy_stated_left_open_with_setting_on"]) + "; off: "
              + json.dumps(H["tenancy_stated_left_open_with_setting_off"]) + ".", ""]
        if H.get("theft"):
            L.append(tbl(["Theft (stories 8-9), gpt-6-luna", "Runs", "Wrong + missed", "Per run", "Unresolved unchanged"],
                         [[k, v["runs"], f3(v["summary"]["errors"]), ", ".join(f3(x["errors"]) for x in v["per_run"]), f3(v["summary"].get("unres_unchanged"))]
                          for k, v in H["theft"].items()]))
            L += ["", "Defining-event facts admitted true and dependent documents requested, gpt-6-luna theft text-runs (off / on): "
                  + "; ".join(f"{k} {H['theft']['off']['admitted_true'][k]} / {H['theft']['on']['admitted_true'][k]}" for k in H["theft"]["off"]["admitted_true"])
                  + "; " + "; ".join(f"{d} requested {H['theft']['off']['requested'][d]} / {H['theft']['on']['requested'][d]}" for d in H["theft"]["off"]["requested"])
                  + f" (of {H['theft']['off']['text_runs']} / {H['theft']['on']['text_runs']}).", ""]
            L += ["", "By changed fact (off / on): " + "; ".join(f"{SHORT[c]} {f3(H['theft'].get('off', {}).get('by_fact', {}).get(c))} / "
                                                                f"{f3(H['theft'].get('on', {}).get('by_fact', {}).get(c))}" for c in COND) + "."]
    L += ["", P.get("verdict", ""), ""]
    return L


if __name__ == "__main__":
    main()
    print("wrote theft_diagnosis.json and theft_diagnosis.md")
