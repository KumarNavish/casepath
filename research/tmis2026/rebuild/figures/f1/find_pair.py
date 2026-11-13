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

# Summary for CONTRACT.md: theft stated/open pairs (one sentence apart), full product, same run index.
wf = json.loads((T / "harness/product/workflows/theft-reviewed/household_theft.json").read_text())
DEP = {"PR_third_party_causer": ["d15"], "PR_repair_over_500": ["d24"], "PR_scheduled_valuable_1000": ["d10"],
       "PR_bicycle_claimed": ["d11", "d12"], "PR_sim_card_stolen": ["d32", "d33"],
       "PR_expert_procedure_requested": ["d21"]}
FACTS = {c: sorted({f for d in wf["documents"] if d["id"] in ds for f in
                    ([x["fact"] for x in d["required_when"]["any"]] if "any" in d["required_when"]
                     else [d["required_when"]["fact"]])}) for c, ds in DEP.items()}
rows = [r for r in out if r["regime"] == "theft" and "-on-" in r["a"]]
summ = {"pair_runs": len(rows), "dependent_line_request_to_hold": 0, "exactly_dependent_line_and_its_question": 0,
        "checklists_identical": 0, "other_lines_changed_hist": {}}
for r in rows:
    cond = r["b"].split("-unres-")[1]
    dep = DEP[cond]
    mv = {x: (a, b) for x, a, b in r["moves"]}
    if all(mv.get(d) == ("request", "hold") for d in dep):
        summ["dependent_line_request_to_hold"] += 1
    if sorted(mv) == sorted(dep) and all(mv[d] == ("request", "hold") for d in dep) and r["questions"] == FACTS[cond]:
        summ["exactly_dependent_line_and_its_question"] += 1
    if not r["moves"] and not r["questions"]:
        summ["checklists_identical"] += 1
    other = len([x for x in mv if x not in dep])
    summ["other_lines_changed_hist"][other] = summ["other_lines_changed_hist"].get(other, 0) + 1
(Path(__file__).parent / "pair_summary.json").write_text(json.dumps(summ, indent=1))
print(json.dumps(summ))
