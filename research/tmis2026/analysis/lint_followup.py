"""POST HOC follow-up of the rule lint (analysis/rule_lint.py). Not part of ANALYSIS_PLAN_STUDY3.md.

    python3 lint_followup.py            # writes lint_followup.json and lint_followup.md (no model calls)
    python3 lint_followup.py --design   # only prints the mutation design (seed, draw, texts); used before the paid run

Part 2. "A flagged condition is treated as open": theft results from the stored readings of Study 3 (fresh2; gpt-6-luna
full product, 3 runs; gpt-6.1-terra checklist only, 1 run) and the product's evaluator at 6a72159c, with each model's
own lint flags (analysis/rule_lint.json; note: the lint was computed on the same off texts, so this is in-sample):
  (a) every flagged condition is unresolved;
  (b) flagged conditions that both blind editors made unconditional (rule_review/lint/final/RECONCILIATION.md: rules 001,
      002, 005, 006, 026, 044, 057, 061) are true, the other flagged conditions unresolved.
Also the lint on the tenancy workflows from the stored readings of Study 3 (ordinary claims: request set not empty, no
open fact): the false-alarm baseline for Part 3.
Part 3. Mutation test of the lint on the tenancy workflows (design fixed below, before any run; the run itself is made by
the scratch driver and read back from its results file).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
sys.path.insert(0, str(HERE))
import decomposition as DC  # noqa: E402
import theft_diagnosis as TD  # noqa: E402

s3, s2, common = TD.s3, TD.s2, TD.common
CACHE = TMIS / "runs" / "product" / "cache"
TEN_WF = TMIS / "harness/product/workflows/fresh-serial-sync"
SCRATCH = Path("/tmp/claude-0/-home-user-casepath/ef865128-25b1-5a5b-af7f-a334bf6c5b16/scratchpad")
CASE_TYPE_RULES = ("001", "002", "005", "006", "026", "044", "057", "061")  # both editors: condition removed

# ------------------------------------------------------------------------------------------------ Part 3 design (fixed)
SEED = 20261112
DEFINING = {"lease_termination_dispute": "termination_received", "rent_increase_dispute": "claim_received"}
# An over-broad version of EVERY branch condition, written before the draw, so that no text is chosen after it. Each is
# meant to hold in an ordinary claim of its workflow although the original would not.
MUTATIONS = {
    "defect_mold_heating": {
        "health_effects": "Does the claim describe effects of the defect on the tenant's use or comfort of the flat?",
        "mold": "Does the defect concern the condition of the flat's rooms, walls, windows or fittings?",
        "heating": "Does the defect affect the comfort of living in the flat?",
        "specialist_needed": "Does the defect need to be examined or repaired by someone?",
        "deposit_considered": "Is the tenant considering any step to make the landlord remedy the defect?",
    },
    "lease_termination_dispute": {
        "family_home": "Does the tenant live in the flat?",
        "arrears": "Does the claim mention the rent or payments under the lease?",
        "retaliation_screen": "Is the tenant contesting or objecting to the termination?",
        "extension_relevant": "Does the tenant want to stay in the flat or need time to move out?",
    },
    "rent_increase_dispute": {
        "reference_rate": "Does the notice or the claim state a reason or basis for the increase?",
        "renovation": "Does the claim mention the flat, the building or its condition?",
    },
}


def draw():
    """Seeded draw: about a third of each workflow's branch conditions (rounded up), at least two."""
    rng = random.Random(SEED)
    out = {}
    for wf in sorted(MUTATIONS):
        conds = sorted(MUTATIONS[wf])
        k = max(2, -(-len(conds) // 3))
        out[wf] = sorted(rng.sample(conds, min(k, len(conds))))
    return out


def design_record():
    d = draw()
    rec = {"seed": SEED, "drawn": d, "mutated_questions": {wf: {c: MUTATIONS[wf][c] for c in cs} for wf, cs in d.items()},
           "all_written_mutations": MUTATIONS, "defining_events_excluded": DEFINING,
           "ordinary_claims": "fresh/ (request set not empty, no open fact) of each dispute type; rent increase has only 3 there and none in "
                              "fresh2, so the 3 control claims of dev_probe (defining event stated or implied) are added",
           "readings": "product at 6a72159c, checklist only, gpt-6-luna, one run per claim (run index 0), three readings"}
    rec["sha256"] = hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
    return rec


def mutated_workflows(outdir):
    d = draw()
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for f in sorted(TEN_WF.glob("*.json")):
        wf = json.loads(f.read_text())
        for fact in wf["facts"]:
            if fact["id"] in d.get(wf["id"], []):
                fact["question"] = MUTATIONS[wf["id"]][fact["id"]]
        (outdir / f.name).write_text(json.dumps(wf, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    return outdir


# ------------------------------------------------------------------------------------------------ readings (generic)
def norm(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()


def readings(entry, fact_ids):
    """[(cache keys, {fact: (verdict, quote)})] for the reading calls of a stored entry: a conditions answer covering most of the
    workflow's facts starts a reading; a short one right after it is its requote retry."""
    out, seen = [], set()
    for k in (entry or {}).get("keys") or []:
        if k in seen:
            continue
        seen.add(k)
        p = CACHE / f"{k}.json"
        if not p.exists():
            continue
        try:
            content = json.loads(json.loads(json.loads(p.read_text())["body"])["choices"][0]["message"]["content"])
        except Exception:  # noqa: BLE001
            continue
        rows = content.get("conditions") if isinstance(content, dict) else None
        if not rows or not all(r.get("id") in fact_ids for r in rows):
            continue
        ans = {}
        for r in rows:
            ans.setdefault(r["id"], (r.get("verdict"), r.get("quote") or ""))
        if len(ans) >= 0.8 * len(fact_ids) or not out:
            out.append([k, ans])
        else:
            out[-1][0] += "+" + k
            out[-1][1].update(ans)
    return [(k, a) for k, a in out]


def lint_counts(units, cond_ids):
    """units: [(reading keys tuple, readings, text)] of ordinary-case runs; identical reading responses count once."""
    seen = set()
    stat = {c: {"runs": 0, "admitted_true": 0, "some_reading_true": 0, "quotes": []} for c in cond_ids}
    for keys, rds, text in units:
        if keys in seen or len(rds) != 3:
            continue
        seen.add(keys)
        t = norm(text)
        for c in cond_ids:
            s = stat[c]
            s["runs"] += 1
            vs = [a.get(c) for _, a in rds]
            if all(v and v[0] == "true" and v[1] and norm(v[1]) in t for v in vs):
                s["admitted_true"] += 1
            if any(v and v[0] == "true" for v in vs):
                s["some_reading_true"] += 1
                for v in vs:
                    if v and v[0] == "true" and v[1] and v[1] not in s["quotes"] and len(s["quotes"]) < 3:
                        s["quotes"].append(v[1])
    for c, s in stat.items():
        n = s["runs"]
        s["flagged"] = bool(n) and (s["admitted_true"] >= n / 2 or s["some_reading_true"] >= 0.75 * n)
    return stat


def claim_text(D, cid):
    """The claim's files as the product received them (harness/product/pilot.py::inputs, inlined: that module imports the HTTP
    transport): message subject and body, and the attachments' text."""
    import base64
    packet = D.intake(cid)
    msg = packet["customer_message"]
    text = (f"Subject: {msg.get('subject', '')}\n\n" if msg.get("subject") else "") + msg["body"]
    atts = [base64.b64decode(a["content_base64"]).decode("utf-8", "replace") for a in packet.get("attachments", [])]
    return text + "\n" + "\n".join(atts)


def ordinary(ref):
    req = ref.get("request_set")
    if req is None:
        req = [d for d, s in ref["document_states"].items() if s in ("required_now", "supplied_insufficient")]
    return bool(req) and ref.get("open_fact") is None


def tenancy_lint_stored():
    """The lint on the three tenancy workflows from the stored readings of Study 3 (fresh2), ordinary claims only."""
    sys.path.insert(0, str(TMIS / "harness" / "product"))
    D = common.data("tenancy", "fresh2")
    wfs = {json.loads(f.read_text())["id"]: json.loads(f.read_text()) for f in sorted(TEN_WF.glob("*.json"))}
    sources = {"gpt-6-luna": ["plans_tenancy_casepath.json", "plans_tenancy_casepath_checklist.json"],
               "gpt-6.1-terra": ["plans_tenancy_casepath_checklist_frontier.json"]}
    out = {}
    for model, files in sources.items():
        units = defaultdict(list)
        for fn in files:
            st = json.loads((TMIS / "runs/study3/confirm" / fn).read_text())
            for k, e in st.items():
                cid = k.split("|")[1]
                ref = D.reference(cid)
                if not ordinary(ref):
                    continue
                wf = wfs[ref["family"]]
                ids = {f["id"] for f in wf["facts"]}
                rds = readings(e, ids)
                units[ref["family"]].append((tuple(k_ for k_, _ in rds), rds, claim_text(D, cid)))
        out[model] = {fam: lint_counts(u, [f["id"] for f in wfs[fam]["facts"] if f["type"] == "boolean"]) for fam, u in units.items()}
    return out


# ------------------------------------------------------------------------------------------------ Part 2: theft
def flags():
    rl = json.loads((HERE / "rule_lint.json").read_text())
    return {m: set(v) for m, v in rl["flagged"].items()}


def case_type_ids(wf_facts):
    return {f for f in wf_facts if TD.stem(f) in {"g" + r for r in CASE_TYPE_RULES}}


def theft_variant(design, model, variant, flagset=None):
    st, Dm = DC.study()
    W = TD.evaluator()
    wf = json.loads((TMIS / "harness/product/workflows/theft-reviewed/household_theft.json").read_text())
    fu = TD.used_facts(wf)
    allf = [f["id"] for f in wf["facts"] if f["id"] != "claim_type"]
    fl = set(flagset) if flagset is not None else flags()[model]
    ex = TD.Exec(W, wf)
    st.load(design, "theft")
    ent = st.entries[(design, "theft")]
    runs = st.runs(design, "theft")
    T = Dm["theft"].texts()
    forced = {}
    if variant in ("a", "c_a"):
        forced = {f: None for f in fl}
    elif variant in ("b", "c_b"):
        ct_ = case_type_ids(fl)
        forced = {f: (True if f in ct_ else None) for f in fl}

    def facts_of(e):
        a = TD.admitted(e, fu)
        a.update({f: v for f, v in forced.items() if f in a})
        return a
    plans = {t: [ex(facts_of(ent[t][r])) for r in range(runs)] for t in T}
    pairs = st.pairs
    on, un = TD.score(pairs, plans, runs)
    res = {"summary": {k: TD.r3(v) for k, v in TD.summ(on, un).items()}, "by_fact": {k: TD.r3(v) for k, v in TD.by_fact(on).items()},
           "by_fact_raw": TD.by_fact(on),
           "forced": {f: v for f, v in sorted(forced.items())}, "forced_need_bearing": sorted(f for f in forced if f in fu)}
    offs = [plans[t][r] for t in T if T[t]["kind"] == "off" for r in range(runs)]
    res["off_requested_in_every_run"] = sorted(TD.IDS[d] for d in set.intersection(*[set(p["requests"]) for p in offs]))
    res["off_held_in_every_run"] = sorted(TD.IDS[d] for d in set.intersection(*[set(p["holds"]) for p in offs]))
    res["off_requested_counts"] = dict(sorted(Counter(TD.IDS[d] for p in offs for d in p["requests"]).items()))
    res["off_held_counts"] = dict(sorted(Counter(TD.IDS[d] for p in offs for d in p["holds"]).items()))
    res["off_runs"] = len(offs)
    # questions a handler would get in an off text: the open facts some document depends on
    qs = Counter()
    for t in T:
        if T[t]["kind"] != "off":
            continue
        for r in range(runs):
            a = facts_of(ent[t][r])
            for f in fu:
                if a[f] is None:
                    qs[f] += 1
    res["off_open_need_bearing_facts_per_run"] = TD.r3(sum(qs.values()) / len(offs))
    res["off_questions_from_forced_facts"] = {f: qs[f] for f in sorted(forced) if f in fu}
    # decomposition (rule / reading / hold) with the variant applied to designed and admitted facts alike
    rows = []
    for p in [p for p in pairs if p["kind"] == "on"]:
        Po = TD.designed(T[p["off"]], fu)
        Pv = TD.designed(T[p["variant"]], fu)
        for f, v in forced.items():
            if f in Po:
                Po[f] = v
                Pv[f] = v
        Gc = set(TD.gset(p["condition"], fu))
        for r in range(runs):
            Ao, Av = facts_of(ent[p["off"]][r]), facts_of(ent[p["variant"]][r])

            def cls(A, P, changed):
                rd, hd = set(), set()
                for f in fu:
                    a, d = A[f], P[f]
                    if a is not None and d is not None and a != d:
                        rd.add(f)
                    elif changed and f in Gc and d is True and a is None:
                        rd.add(f)
                    elif (a is None) != (d is None):
                        hd.add(f)
                return rd, hd
            ro, ho = cls(Ao, Po, False)
            rv, hv = cls(Av, Pv, True)

            def E(fix):
                o = {f: (Po[f] if (f in ro and "reading" in fix) or (f in ho and "hold" in fix) else Ao[f]) for f in fu}
                v = {f: (Pv[f] if (f in rv and "reading" in fix) or (f in hv and "hold" in fix) else Av[f]) for f in fu}
                return TD.pair_err(ex, p, o, v)[0]
            m0 = E(())
            m1 = E(("reading",))
            m2 = E(("reading", "hold"))
            rows.append({"measured": m0, "reading": m0 - m1, "hold": m1 - m2, "rule": m2,
                         "interaction": (m0 - m2) - (m0 - m1) - (m0 - E(("hold",)))})
    n = len(rows)
    res["decomposition"] = {k: TD.r3(sum(r[k] for r in rows) / n) for k in ("rule", "reading", "hold", "measured", "interaction")}
    return res


# ------------------------------------------------------------------------------------------------ Part 2 (c): out-of-sample flags
DEV_SOURCES = {  # stored development theft runs (stories 4-7 of fresh/) whose reading requests equal the tested commit's
    "gpt-6-luna": [("runs/product/plans_theft_gpt-6-luna_fresh_e-check.json", "runs/product/manifest_theft_gpt-6-luna_fresh_e-check.json"),
                   ("runs/product/plans_theft_gpt-6-luna_fresh_e-full-s4.json", "runs/product/manifest_theft_gpt-6-luna_fresh_e-full-s4.json"),
                   ("runs/product/plans_theft_gpt-6-luna_fresh_e67-check.json", "runs/product/manifest_theft_gpt-6-luna_fresh_e67-check.json")],
    "gpt-6.1-terra": [("runs/product/plans_theft_gpt-6.1-terra_fresh_t1-check.json", "runs/product/manifest_theft_gpt-6.1-terra_fresh_t1-check.json")],
}
DEV_NOTE = ("gpt-6-luna: e-check, e-full-s4, e67-check, all produced by the tested commit 6a72159c (manifest source tree "
            "0304802...) with the same workflow file. gpt-6.1-terra: t1-check, produced by commit 1ee2c8b (source tree f748205...), "
            "checklist only, reasoning on, same workflow file; its reading requests were verified to be byte-identical to the tested "
            "commit's by re-running the tested commit cache-only on s4-off, s5-off, s6-off, s7-off and s5-on-PR_bicycle_claimed (every "
            "request found in the cache under the same key, identical checklists, no call).")


def dev_flags(model):
    import rule_lint as RL  # noqa: E402
    T = RL.texts()
    wf = json.loads(RL.WORKFLOW.read_text())
    facts = [f["id"] for f in wf["facts"] if f["id"] != "claim_type"]
    seen, stat, used = set(), {c: {"off_runs": 0, "admitted_true": 0, "some_reading_true": 0} for c in facts}, []
    for path, manifest in DEV_SOURCES[model]:
        m = json.loads((TMIS / manifest).read_text())
        used.append({"file": path, "commit": (m.get("git") or {}).get("commit"), "source_tree_sha256": m.get("source_tree_sha256"),
                     "workflow_sha256": (m.get("workflows") or {}).get("household_theft.json")})
        for k, e in json.loads((TMIS / path).read_text()).items():
            _, t, r = k.split("|")
            if T[t]["kind"] != "off":
                continue
            rds = RL.readings(e, len(wf["facts"]))
            keys = tuple(x for x, _ in rds)
            if len(rds) != 3 or keys in seen:
                continue
            seen.add(keys)
            for c in facts:
                s_ = stat[c]
                s_["off_runs"] += 1
                if RL.value(rds, c, T[t]["text"]) == "true":
                    s_["admitted_true"] += 1
                if any(a.get(c) and a[c][0] == "true" for _, a in rds):
                    s_["some_reading_true"] += 1
    n = max(s_["off_runs"] for s_ in stat.values())
    fl = sorted(c for c, s_ in stat.items() if s_["off_runs"] and (s_["admitted_true"] >= s_["off_runs"] / 2 or s_["some_reading_true"] >= 0.75 * s_["off_runs"]))
    texts = sorted({t for path, _ in DEV_SOURCES[model] for k in json.loads((TMIS / path).read_text()) for t in [k.split("|")[1]] if T[t]["kind"] == "off"})
    return {"flags": fl, "off_runs": n, "off_texts": texts, "sources": used, "counts": {c: stat[c] for c in fl}}


def paired(model_design_rows, single, model):
    """Paired comparison over the nine changed-fact clusters (descriptive): variant cluster values (its own runs) against a
    single prompt's (3 stored runs); exact two-sided sign-flip p (study2.signflip_p)."""
    st, Dm = DC.study()
    on, _ = st.theft_rows(single)
    sv = TD.by_fact(on)
    diffs = [model_design_rows[c] - sv[c] for c in TD.COND]
    return {"single": single, "single_value": TD.r3(sum(sv.values()) / len(sv)), "variant_value": TD.r3(sum(model_design_rows.values()) / 9),
            "mean_difference": TD.r3(sum(diffs) / 9), "differences": {TD.SHORT[c]: TD.r3(d) for c, d in zip(TD.COND, diffs)},
            "favouring_product": sum(d < 0 for d in diffs), "favouring_single": sum(d > 0 for d in diffs), "p_signflip": s2.signflip_p(diffs)}


# ------------------------------------------------------------------------------------------------ Part 3 analysis
def part3():
    f = SCRATCH / "mutation_results.json"
    if not f.exists():
        return None
    raw = json.loads(f.read_text())
    sys.path.insert(0, str(TMIS / "harness" / "product"))
    sys.path.insert(0, str(TMIS / "dev_probe"))
    import tenancy_probe as TP  # noqa: E402
    Df = common.data("tenancy", "fresh")
    d = draw()
    out = {"design": design_record(), "arms": {}}
    for arm in ("baseline", "mutated"):
        wfdir = TEN_WF if arm == "baseline" else SCRATCH / "wf_mutated"
        wfs = {json.loads(p.read_text())["id"]: json.loads(p.read_text()) for p in sorted(Path(wfdir).glob("*.json"))}
        units = defaultdict(list)
        statuses = Counter()
        for job, e in raw.items():
            a, regime, cid = job.split("|")
            if a != arm:
                continue
            statuses[e.get("status")] += 1
            D = Df if regime == "tenancy-fresh" else TP
            fam = D.reference(cid)["family"]
            ids = {x["id"] for x in wfs[fam]["facts"]}
            rds = readings(e, ids)
            units[fam].append((tuple(k for k, _ in rds), rds, claim_text(D, cid)))
        out["arms"][arm] = {"statuses": dict(statuses),
                            "lint": {fam: lint_counts(u, [x["id"] for x in wfs[fam]["facts"] if x["type"] == "boolean"]) for fam, u in units.items()}}
    det = {}
    for fam, planted in d.items():
        m = out["arms"]["mutated"]["lint"].get(fam, {})
        b = out["arms"]["baseline"]["lint"].get(fam, {})
        other = [c for c in MUTATIONS[fam] if c not in planted]
        det[fam] = {"planted": planted, "planted_flagged": [c for c in planted if m.get(c, {}).get("flagged")],
                    "planted_already_flagged_unmutated": [c for c in planted if b.get(c, {}).get("flagged")],
                    "planted_newly_flagged": [c for c in planted if m.get(c, {}).get("flagged") and not b.get(c, {}).get("flagged")],
                    "unmutated_branch": other, "unmutated_flagged_in_mutated_run": [c for c in other if m.get(c, {}).get("flagged")],
                    "unmutated_flagged_in_baseline_run": [c for c in other if b.get(c, {}).get("flagged")],
                    "defining_event": DEFINING.get(fam), "defining_event_flagged": {arm: out["arms"][arm]["lint"].get(fam, {}).get(DEFINING.get(fam), {}).get("flagged")
                                                                                  for arm in ("baseline", "mutated")} if fam in DEFINING else None,
                    "runs": m.get(planted[0], {}).get("runs") if planted else None}
    out["detection"] = det
    out["totals"] = {"planted": sum(len(v["planted"]) for v in det.values()), "planted_flagged": sum(len(v["planted_flagged"]) for v in det.values()),
                     "planted_already_flagged_unmutated": sum(len(v["planted_already_flagged_unmutated"]) for v in det.values()),
                     "planted_newly_flagged": sum(len(v["planted_newly_flagged"]) for v in det.values()),
                     "unmutated": sum(len(v["unmutated_branch"]) for v in det.values()),
                     "unmutated_flagged_mutated_run": sum(len(v["unmutated_flagged_in_mutated_run"]) for v in det.values()),
                     "unmutated_flagged_baseline_run": sum(len(v["unmutated_flagged_in_baseline_run"]) for v in det.values())}
    ledger = TMIS / "runs/product/ledger_dev_gpt-6-luna.jsonl"
    rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    out["spend_usd"] = {a: round(sum(r["usd"] or 0 for r in rows if r.get("arm") == f"lint-mutation-{a}"), 4) for a in ("baseline", "mutated")}
    return out


def criterion2_theft():
    """Second criterion, measured on stored theft readings: 'unresolved in most ordinary cases although the claim addresses the
    matter' = no agreed value (all three readings the same value with a quotation found) in at least half of the off-text runs,
    while at least one reading answers true, false or open in at least half of them."""
    rl = json.loads((HERE / "rule_lint.json").read_text())
    import rule_lint as RL  # noqa: E402
    T = RL.texts()
    wf = json.loads(RL.WORKFLOW.read_text())
    facts = [f["id"] for f in wf["facts"] if f["id"] != "claim_type"]
    out = {}
    for model, label, path, runs, manifest in RL.SOURCES:
        if manifest:
            m = json.loads((TMIS / manifest).read_text())
            if m.get("source_tree_sha256") != RL.TESTED_TREE:
                continue
        stored = json.loads((TMIS / path).read_text())
        o = out.setdefault(model, {"seen": set(), "stat": {c: {"runs": 0, "no_agreed_value": 0, "addressed": 0} for c in facts}})
        for k, e in stored.items():
            _, t, r = k.split("|")
            if T[t]["kind"] != "off":
                continue
            rds = RL.readings(e, len(wf["facts"]))
            keys = tuple(x for x, _ in rds)
            if len(rds) != 3 or keys in o["seen"]:
                continue
            o["seen"].add(keys)
            for c in facts:
                s = o["stat"][c]
                s["runs"] += 1
                if RL.value(rds, c, T[t]["text"]) == "open":
                    s["no_agreed_value"] += 1
                if any(a.get(c) and a[c][0] in ("true", "false", "open") for _, a in rds):
                    s["addressed"] += 1
    res = {}
    for model, o in out.items():
        st = o["stat"]
        fl = {c: s for c, s in st.items() if s["runs"] and s["no_agreed_value"] >= s["runs"] / 2 and s["addressed"] >= s["runs"] / 2}
        res[model] = {"flagged": sorted(fl), "counts": {c: st[c] for c in ("g074", "g016", "g022", "g020_rev_b4712e29", "g042_rev_92ab8925", "g003")}}
    return res


# ------------------------------------------------------------------------------------------------ main
def main():
    out = {"label": "POST HOC: not part of ANALYSIS_PLAN_STUDY3.md", "note": __doc__}
    fl = flags()
    out["flags"] = {m: sorted(v) for m, v in fl.items()}
    p2, devf, cmp_ = {}, {}, {}
    for design, model in (("casepath", "gpt-6-luna"), ("casepath_frontier_checklist", "gpt-6.1-terra")):
        devf[model] = dev_flags(model)
        p2[model] = {v: theft_variant(design, model, v) for v in ("tested", "a", "b")}
        p2[model].update({v: theft_variant(design, model, v, devf[model]["flags"]) for v in ("c_a", "c_b")})
        ins, dev = set(fl[model]), set(devf[model]["flags"])
        devf[model]["shared_with_in_sample"] = sorted(ins & dev)
        devf[model]["only_development"] = sorted(dev - ins)
        devf[model]["only_in_sample"] = sorted(ins - dev)
    out["part2_theft"] = p2
    out["development_flags"] = {"note": DEV_NOTE, **devf}
    for v in ("tested", "a", "b", "c_a", "c_b"):
        cmp_[v] = [paired(p2["gpt-6.1-terra"][v]["by_fact_raw"], sg, "gpt-6.1-terra") for sg in ("ric_frontier", "ric_original_frontier")]
    out["paired_frontier"] = cmp_
    out["tenancy_lint_stored"] = tenancy_lint_stored()
    out["part3"] = part3()
    out["criterion2_theft"] = criterion2_theft()
    (HERE / "lint_followup.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str) + "\n")
    (HERE / "lint_followup.md").write_text(markdown(out))
    (HERE / "posthoc_numbers.tex").write_text(macros(out, json.loads((HERE / "decomposition.json").read_text())))
    return out


def _num(x, nd=3):
    """Rounded half up, as analysis/make_numbers_study3.py does."""
    from decimal import ROUND_HALF_UP, Decimal
    return str(Decimal(repr(x)).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP))


def macros(lf, dc):
    """POST HOC numbers as LaTeX macros (prefix \\spost), from lint_followup.json and decomposition.json. Never edit by hand."""
    M = {}
    MOD = {"casepath": "Luna", "casepath_frontier_checklist": "Terra", "gpt-6-luna": "Luna", "gpt-6.1-terra": "Terra"}
    PART = {"rule": "Rule", "routing": "Routing", "document": "Doc", "reading": "Reading", "hold": "Hold", "measured": "Measured",
            "product_steps": "ProductSteps", "interaction": "Interaction"}
    MEASW = {"strict_unsafe": "Strict", "all_dev": "AllDev"}
    SUBW = {"all": "All", "ordinary": "Ordinary", "denied_event": "Denied", "open_event": "OpenEvent"}
    for d, v in dc["tenancy_product"].items():
        for m in ("strict_unsafe", "all_dev"):
            for sub, s_ in v[m].items():
                for k, w in PART.items():
                    M[f"spostDecTen{MOD[d]}{MEASW[m]}{SUBW[sub]}{w}"] = _num(s_[k])
    for d, v in dc["theft_product"].items():
        for k in ("rule", "reading", "hold", "measured", "product_steps", "interaction"):
            M[f"spostDecTh{MOD[d]}{PART[k]}"] = _num(v["all"][k])
    SG = {"ric": "Ric", "ric_frontier": "RicFrontier", "ric_original": "RicOrig", "ric_original_frontier": "RicOrigFrontier",
          "self_consistency": "SelfCons", "model_executes_rules": "Mer", "react": "React"}
    KIND = {"unnecessary": "Unnecessary", "missed": "Missed", "handed": "Handed", "premature": "Premature",
            "silent_skip": "SilentSkip", "held_req": "HeldReq", "spurious_hold": "SpurHold", "strict_unsafe": "Strict",
            "all_dev": "AllDev"}
    for d, v in dc["tenancy_single"].items():
        for sub, s_ in v.items():
            for k, w in KIND.items():
                M[f"spostKindTen{SG[d]}{SUBW[sub]}{w}"] = _num(s_[k])
    for d, v in dc["theft_single"].items():
        M[f"spostDecTh{SG[d]}SameAsFloor"] = _num(v["same_as_rule_floor"])
        M[f"spostDecTh{SG[d]}Other"] = _num(v["other"])
    VW = {"tested": "Tested", "a": "FlagOpen", "b": "FlagCaseType", "c_a": "DevFlagOpen", "c_b": "DevFlagCaseType"}
    for m, v in lf["part2_theft"].items():
        for var, r in v.items():
            M[f"spostHeld{MOD[m]}{VW[var]}Errors"] = _num(r["summary"]["errors"])
            M[f"spostHeld{MOD[m]}{VW[var]}Unchanged"] = _num(r["summary"]["unres_unchanged"])
            M[f"spostHeld{MOD[m]}{VW[var]}OpenFacts"] = _num(r["off_open_need_bearing_facts_per_run"], 2)
            M[f"spostHeld{MOD[m]}{VW[var]}HeldEveryOff"] = str(len(r["off_held_in_every_run"]))
            for k in ("rule", "reading", "hold"):
                M[f"spostHeld{MOD[m]}{VW[var]}{PART[k]}"] = _num(r["decomposition"][k])
    for m in ("gpt-6-luna", "gpt-6.1-terra"):
        d = lf["development_flags"][m]
        M[f"spostDevFlags{MOD[m]}N"] = str(len(d["flags"]))
        M[f"spostDevFlags{MOD[m]}OffRuns"] = str(d["off_runs"])
        M[f"spostInSampleFlags{MOD[m]}N"] = str(len(lf["flags"][m]))
    SGW = {"ric_frontier": "RicFrontier", "ric_original_frontier": "RicOrigFrontier"}
    for var, cs in lf["paired_frontier"].items():
        for c in cs:
            M[f"spostPaired{VW[var]}{SGW[c['single']]}Diff"] = _num(c["mean_difference"])
            M[f"spostPaired{VW[var]}{SGW[c['single']]}P"] = _num(c["p_signflip"], 4)
    p3 = lf.get("part3")
    if p3:
        for k, w in (("planted", "Planted"), ("planted_flagged", "PlantedFlagged"), ("planted_already_flagged_unmutated", "PlantedAlready"),
                     ("planted_newly_flagged", "PlantedNew"), ("unmutated", "Unmutated"), ("unmutated_flagged_mutated_run", "FalseAlarmMutated"),
                     ("unmutated_flagged_baseline_run", "FalseAlarmBaseline")):
            M[f"spostMut{w}"] = str(p3["totals"][k])
        M["spostMutSpendUSD"] = _num(sum(p3["spend_usd"].values()), 2)
    for m, v in lf["tenancy_lint_stored"].items():
        n = sum(len(st) for st in v.values())
        M[f"spostTenLint{MOD[m]}Flagged"] = str(sum(s_["flagged"] for st in v.values() for s_ in st.values()))
        M[f"spostTenLint{MOD[m]}Conditions"] = str(n)
    assert all(re.fullmatch(r"[A-Za-z]+", k) for k in M), [k for k in M if not re.fullmatch(r"[A-Za-z]+", k)]
    lines = ["% POST HOC numbers (not part of ANALYSIS_PLAN_STUDY3.md). Written by analysis/lint_followup.py from",
             "% analysis/lint_followup.json and analysis/decomposition.json. Never edit by hand."]
    lines += [f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(M.items())]
    return "\n".join(lines) + "\n"


def f3(x):
    return "–" if x is None else f"{x:.3f}"


def markdown(o):
    L = ["# Lint follow-up (POST HOC)", "", "**Post hoc, not part of the pre-registered plan.** Generated by `analysis/lint_followup.py`.", "",
         "## Part 2. A flagged condition is treated as open (theft, stored readings, no model calls)", "",
         "Each model's own flags (`analysis/rule_lint.json`). The lint was computed on the same off texts, so these results are "
         "in-sample. (a) every flagged condition unresolved; (b) the flagged conditions both blind editors made unconditional (rules "
         + ", ".join(CASE_TYPE_RULES) + ") true, the other flagged conditions unresolved. Single prompts (stored, same data): "
         "gpt-6.1-terra 0.949 (reviewed rules) and 0.671 (original rules); gpt-6-luna 1.736 and 1.468.", ""]
    for model, v in o["part2_theft"].items():
        L += [f"**{model}** (flags: {', '.join(o['flags'][model])})", "",
              "| Variant | Wrong + missed per pair | Unresolved unchanged | Rule | Reading | Hold | Interaction | Requested in every off run | Held in every off run | Open document-deciding facts per off run |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for var, r in v.items():
            dd = r["decomposition"]
            L.append(f"| {var} | {f3(r['summary']['errors'])} | {f3(r['summary']['unres_unchanged'])} | {f3(dd['rule'])} | {f3(dd['reading'])} | "
                     f"{f3(dd['hold'])} | {f3(dd['interaction'])} | {', '.join(r['off_requested_in_every_run'])} | {', '.join(r['off_held_in_every_run']) or '–'} | "
                     f"{f3(r['off_open_need_bearing_facts_per_run'])} |")
        L += ["", "By changed fact:", "", "| Variant | " + " | ".join(TD.SHORT[c] for c in TD.COND) + " |", "|---|" + "---|" * len(TD.COND)]
        for var, r in v.items():
            L.append(f"| {var} | " + " | ".join(f3(r["by_fact"].get(c)) for c in TD.COND) + " |")
        L += ["", "Questions a handler would get in the off texts from the forced-open facts that decide a document (off runs in which the "
              "fact is open): " + "; ".join(f"{var}: " + json.dumps(r["off_questions_from_forced_facts"]) for var, r in v.items() if var != "tested"), ""]
    df = o.get("development_flags") or {}
    if df:
        L += ["### Variant (c): flags computed out of sample, from development runs only", "", df["note"], "",
              "Variants c_a and c_b apply these flags exactly as (a) and (b). Rows c_a / c_b in the tables above.", "",
              "| Model | Development off runs (texts) | Development flags | Shared with in-sample | Only development | Only in-sample |", "|---|---|---|---|---|---|"]
        for m in ("gpt-6-luna", "gpt-6.1-terra"):
            d = df[m]
            L.append(f"| {m} | {d['off_runs']} ({', '.join(d['off_texts'])}) | {', '.join(d['flags'])} | {', '.join(d['shared_with_in_sample'])} | "
                     f"{', '.join(d['only_development']) or '–'} | {', '.join(d['only_in_sample']) or '–'} |")
        L += ["", "Note: the in-sample lint of gpt-6-luna (`rule_lint.py`) already pooled these development runs with the Study 3 runs.", ""]
    pf = o.get("paired_frontier") or {}
    if pf:
        L += ["### Frontier model: paired comparison with the frontier single prompts (descriptive)", "",
              "Nine changed-fact clusters; cluster value = mean over the cluster's pair-runs (product variant: 1 run; single prompt: 3 stored runs); "
              "exact two-sided sign-flip p over 2^9 sign patterns (study2.signflip_p). Descriptive: post hoc, one product run, flags in-sample for (a)/(b).", "",
              "| Variant | Single prompt | Variant value | Single-prompt value | Mean difference | Clusters favouring product / single prompt | Sign-flip p |",
              "|---|---|---|---|---|---|---|"]
        for var, cs in pf.items():
            for c in cs:
                L.append(f"| {var} | {c['single']} | {f3(c['variant_value'])} | {f3(c['single_value'])} | {c['mean_difference']:+.3f} | "
                         f"{c['favouring_product']} / {c['favouring_single']} | {c['p_signflip']:.4f} |")
        L.append("")
    L += ["## Tenancy lint baseline (stored readings, ordinary claims of Study 3)", "",
          "| Model | Workflow | Condition | Ordinary runs | Admitted true | Some reading true | Flagged |", "|---|---|---|---|---|---|---|"]
    for model, v in o["tenancy_lint_stored"].items():
        for fam, st in v.items():
            for c, s in st.items():
                L.append(f"| {model} | {fam} | {c} | {s['runs']} | {s['admitted_true']} | {s['some_reading_true']} | {'yes' if s['flagged'] else 'no'} |")
    p3 = o.get("part3")
    if p3:
        L += ["", "## Part 3. Mutation test of the lint (tenancy, gpt-6-luna, one run per claim)", "",
              f"Design fixed before the run (seed {p3['design']['seed']}, record sha256 {p3['design']['sha256'][:16]}); mutated questions:", ""]
        for wf, qs in p3["design"]["mutated_questions"].items():
            for c, q in qs.items():
                L.append(f"- {wf} / `{c}`: \"{q}\"")
        L += ["", f"Totals: planted {p3['totals']['planted']}, flagged {p3['totals']['planted_flagged']} (of these, already flagged with the "
              f"original wording in the baseline run: {p3['totals']['planted_already_flagged_unmutated']}; flagged only after mutation: "
              f"{p3['totals']['planted_newly_flagged']} of {p3['totals']['planted'] - p3['totals']['planted_already_flagged_unmutated']}); unmutated branch conditions "
              f"{p3['totals']['unmutated']}, flagged in the mutated run {p3['totals']['unmutated_flagged_mutated_run']}, in the baseline run "
              f"{p3['totals']['unmutated_flagged_baseline_run']}. Spend USD {json.dumps(p3['spend_usd'])}.", "",
              "| Workflow | Planted | Planted flagged | Planted, already flagged unmutated | Unmutated | Unmutated flagged (mutated run) | Unmutated flagged (baseline run) | Defining event flagged (baseline, mutated) |",
              "|---|---|---|---|---|---|---|---|"]
        for fam, x in p3["detection"].items():
            L.append(f"| {fam} | {', '.join(x['planted'])} | {', '.join(x['planted_flagged']) or '–'} | {', '.join(x['planted_already_flagged_unmutated']) or '–'} | {', '.join(x['unmutated_branch'])} | "
                     f"{', '.join(x['unmutated_flagged_in_mutated_run']) or '–'} | {', '.join(x['unmutated_flagged_in_baseline_run']) or '–'} | {json.dumps(x['defining_event_flagged'])} |")
        L += ["", "| Arm | Workflow | Condition | Runs | Admitted true | Some reading true | Flagged | Quotations |", "|---|---|---|---|---|---|---|---|"]
        for arm, a in p3["arms"].items():
            for fam, st in a["lint"].items():
                for c, s in st.items():
                    L.append(f"| {arm} | {fam} | {c} | {s['runs']} | {s['admitted_true']} | {s['some_reading_true']} | {'yes' if s['flagged'] else 'no'} | "
                             + "; ".join(f"\"{q[:90]}\"" for q in s["quotes"][:2]) + " |")
    if p3:
        L += ["", "What this test can and cannot show: one model (gpt-6-luna), one run per claim, three workflows with 11 branch conditions, "
              "57 claims (rent increase: 6), mutations written by the same analyst who knows the lint, and 'ordinary' claims that are "
              "designed test claims with several true branch flags each. It shows that a condition widened to the general circumstance "
              "is read true more often and crosses the threshold; it cannot show detection of subtler, realistic over-breadth, it cannot "
              "estimate a false-alarm rate on a real population of ordinary cases, and it does not test a second model.", ""]
    c2 = o.get("criterion2_theft") or {}
    L += ["", "## A second criterion for under-specified conditions (theft, stored readings, no new calls)", "",
          "'No agreed value in at least half of the off-text runs although at least one reading answers true, false or open in at least "
          "half of them.'", ""]
    for model, v in c2.items():
        L.append(f"- {model}: flagged {len(v['flagged'])}: {', '.join(v['flagged'])}; counts " + json.dumps(v["counts"]))
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", action="store_true")
    ap.add_argument("--write-mutated", default=None)
    a = ap.parse_args()
    if a.design:
        print(json.dumps(design_record(), indent=1, ensure_ascii=False))
    elif a.write_mutated:
        print(mutated_workflows(a.write_mutated))
    else:
        o = main()
        for m, v in o["part2_theft"].items():
            for var, r in v.items():
                print(m, var, r["summary"]["errors"], r["summary"]["unres_unchanged"], r["decomposition"], r["off_requested_in_every_run"], r["off_held_in_every_run"])
