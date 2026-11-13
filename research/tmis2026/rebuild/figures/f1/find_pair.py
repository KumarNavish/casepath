"""Search the stored Study 3 outputs for Figure 1's pair (read-only; no model call).

For every pair of texts that share a story or family, measure
  text_diff  = number of differing sentences (difflib on sentence lists)
  list_diff  = number of checklist lines whose state differs (request / hold / not listed), plus added questions
in each of the three stored product runs (plans_*_casepath.json, the full product, default settings).
Writes pair_search.json next to this script.
"""
import difflib, json, re, sys
from pathlib import Path

T = Path(__file__).resolve().parents[3]          # research/tmis2026
sys.path.insert(0, str(T / "fresh2"))
RUNS = T / "runs" / "study3" / "confirm"

def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]

def text_diff(a, b):
    sa, sb = sentences(a), sentences(b)
    sm = difflib.SequenceMatcher(None, sa, sb, autojunk=False)
    return sum(max(i2 - i1, j2 - j1) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal")

def states(plan):
    st = {d: "request" for d in plan["requests"]}
    st.update({d: "hold" for d in plan["holds"]})
    return st

def list_diff(pa, pb):
    sa, sb = states(pa), states(pb)
    lines = sorted(d for d in set(sa) | set(sb) if sa.get(d) != sb.get(d))
    qa, qb = set(pa["questions"]), set(pb["questions"])
    return lines, sorted(qa ^ qb)

out = []
# theft: off vs unresolved (one sentence replaced by construction)
import theft_fresh2
texts = theft_fresh2.texts()
th = json.loads((RUNS / "plans_theft_casepath.json").read_text())
for tid, t in texts.items():
    if t["kind"] != "unresolved":
        continue
    off = f"s{t['story']}-off"
    for base in (off, f"s{t['story']}-on-{t['condition']}"):
     for r in range(3):
        a, b = th.get(f"PRODUCT|{base}|{r}"), th.get(f"PRODUCT|{tid}|{r}")
        if not a or not b or a.get("status") != "completed" or b.get("status") != "completed":
            continue
        lines, q = list_diff(a["plan_ids"], b["plan_ids"])
        sa, sb = states(a["plan_ids"]), states(b["plan_ids"])
        out.append({"regime": "theft", "a": base, "b": tid, "run": r, "text_diff": text_diff(texts[base]["text"], t["text"]),
                    "lines": lines, "moves": [[x, sa.get(x, "-"), sb.get(x, "-")] for x in lines],
                    "questions": q, "n": len(lines) + len(q)})
# tenancy: every pair inside a family
import tenancy_fresh2 as tf
tn = json.loads((RUNS / "plans_tenancy_casepath.json").read_text())
ids = tf.claim_ids("test")
fam = {}
for c in ids:
    fam.setdefault(tf.reference(c)["family_id"], []).append(c)
def msg(c):
    m = tf.intake(c)["customer_message"]
    return m.get("subject", "") + "\n" + m["body"]
for f, cs in fam.items():
    for i, a in enumerate(cs):
        for b in cs[i + 1:]:
            td = text_diff(msg(a), msg(b))
            for r in range(3):
                pa, pb = tn.get(f"PRODUCT|{a}|{r}"), tn.get(f"PRODUCT|{b}|{r}")
                if not pa or not pb:
                    continue
                lines, q = list_diff(pa["plan"], pb["plan"])
                sa, sb = states(pa["plan"]), states(pb["plan"])
                out.append({"regime": "tenancy", "family": f, "a": a, "b": b, "run": r, "text_diff": td,
                            "lines": lines, "moves": [[x, sa.get(x, "-"), sb.get(x, "-")] for x in lines],
                            "questions": q, "n": len(lines) + len(q)})
(Path(__file__).parent / "pair_search.json").write_text(json.dumps(out, indent=1))

# Summary for CONTRACT.md and the caption: theft stated/open pairs (one sentence apart), same run index, per design.
import collections
wf = json.loads((T / "harness/product/workflows/theft-reviewed/household_theft.json").read_text())
DEP = {"PR_third_party_causer": ["d15"], "PR_repair_over_500": ["d24"], "PR_scheduled_valuable_1000": ["d10"],
       "PR_bicycle_claimed": ["d11", "d12"], "PR_sim_card_stolen": ["d32", "d33"],
       "PR_expert_procedure_requested": ["d21"]}
assert all(d["required_when"] for d in wf["documents"] if any(d["id"] in v for v in DEP.values()))
def facts_of(rw):
    return [x["fact"] for x in rw["any"]] if "any" in rw else [rw["fact"]]
WDOC = {d["id"]: d for d in wf["documents"]}
FACTS = {c: sorted({f for d in ds for f in facts_of(WDOC[d]["required_when"])}) for c, ds in DEP.items()}


def pair_stats(fname):
    th = json.loads((RUNS / fname).read_text())
    st = {"pair_runs": 0, "governed_lines_request_to_hold": 0,
          "exactly_governed_lines_and_their_questions_nothing_else": 0,
          "something_else_also_moves": 0, "checklists_identical": 0,
          "other_lines_moved_per_pair_run": {}, "most_often_moving_other_lines": {}}
    other_doc = collections.Counter()
    for tid, t in texts.items():
        if t["kind"] != "unresolved":
            continue
        on = f"s{t['story']}-on-{t['condition']}"
        dep, qf = DEP[t["condition"]], FACTS[t["condition"]]
        for r in range(3):
            a, b = th.get(f"PRODUCT|{on}|{r}"), th.get(f"PRODUCT|{tid}|{r}")
            if not a or not b or a.get("status") != "completed" or b.get("status") != "completed":
                continue
            st["pair_runs"] += 1
            sa, sb = states(a["plan_ids"]), states(b["plan_ids"])
            moved = {x for x in set(sa) | set(sb) if sa.get(x) != sb.get(x)}
            qd = set(a["plan_ids"]["questions"]) ^ set(b["plan_ids"]["questions"])
            gov = all(sa.get(d) == "request" and sb.get(d) == "hold" for d in dep)
            st["governed_lines_request_to_hold"] += gov
            other = moved - set(dep)
            other_q = qd - set(qf)
            if gov and not other and not other_q and set(qf) <= qd:
                st["exactly_governed_lines_and_their_questions_nothing_else"] += 1
            if other or other_q:
                st["something_else_also_moves"] += 1
            if not moved and not qd:
                st["checklists_identical"] += 1
            k = str(len(other))
            st["other_lines_moved_per_pair_run"][k] = st["other_lines_moved_per_pair_run"].get(k, 0) + 1
            other_doc.update(other)
    st["most_often_moving_other_lines"] = {d: {"pair_runs": n, "title": WDOC[d]["title"],
                                               "governed_by": facts_of(WDOC[d]["required_when"]) if WDOC[d]["required_when"] else []}
                                           for d, n in other_doc.most_common(5)}
    return st


def stability(fname, key):
    d = json.loads((RUNS / fname).read_text())
    by = collections.defaultdict(list)
    for k, r in d.items():
        _, t, _i = k.split("|")
        if r.get("status") != "completed":
            continue
        p = r[key]
        by[t].append((tuple(sorted(p["requests"])), tuple(sorted(p["holds"]))))
    full = [v for v in by.values() if len(v) == 3]
    return {"texts_with_3_runs": len(full), "identical_checklist_in_all_runs": sum(len(set(v)) == 1 for v in full)}


summ = {"definition": "pair-run = the stated text and the open text of one theft pair, same run index; governed lines = "
                      "the needs whose rule names the condition's fact; questions compared as sets",
        "core_checklist_only": {"pairs": pair_stats("plans_theft_casepath_checklist.json"),
                                "stability_theft": stability("plans_theft_casepath_checklist.json", "plan_ids"),
                                "stability_tenancy": stability("plans_tenancy_casepath_checklist.json", "plan")},
        "full_product": {"pairs": pair_stats("plans_theft_casepath.json"),
                         "stability_theft": stability("plans_theft_casepath.json", "plan_ids"),
                         "stability_tenancy": stability("plans_tenancy_casepath.json", "plan")}}
(Path(__file__).parent / "pair_summary.json").write_text(json.dumps(summ, indent=1))
print(json.dumps(summ, indent=1))
