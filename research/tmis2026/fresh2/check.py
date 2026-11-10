"""Model-free checks of the sealed fresh2 data. Imports no model client and makes no network call.

  1. tenancy oracle: an independent rebuild of every reference from the true flags and fact states under the
     silence policy (production engine, exact deferral) reproduces document states, request set, held set and
     the answered plan;
  2. open facts: every open-fact claim holds at least one document, and resolving the open fact changes the plan;
  3. theft oracle: reference plans built from the frozen reference (off: nothing; on: the condition's documents;
     unresolved: those documents held) score perfectly with the frozen best_realization scorer (theft_score);
  4. loaders: both loaders serve every claim, text and pair; counts match the design;
  5. novelty: flag combinations unused by the 150 Study 1 and 72 fresh/ claims; no claim text repeats an original,
     fresh/ or other fresh2 text (token-set and word-trigram Jaccard); theft stories differ from stories 0-7 once
     the shared condition sentences are removed;
  6. manifest: every file's SHA-256 matches MANIFEST.json (if present).

Usage: python3 fresh2/check.py   (exit status 0 when every check passes)
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
REPO = TMIS.parents[1]
sys.path.insert(0, str(TMIS / "harness"))
sys.path.insert(0, str(REPO / "casepath-api"))
assert "llm" not in sys.modules


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


T2 = load("fresh2_tenancy_data", HERE / "tenancy_fresh2.py")
H2 = load("fresh2_theft_data", HERE / "theft_fresh2.py")
T1 = load("fresh_tenancy_data", TMIS / "fresh" / "tenancy_fresh.py")
H1 = load("fresh_theft_data", TMIS / "fresh" / "theft_fresh.py")
import tenancy_data as T0  # noqa: E402
import theft_data as H0  # noqa: E402
from theft_score import score_pair  # noqa: E402
from casepath_tenancy import plan_from_verified_exact  # noqa: E402
from casepath_api.assessment_grammar_v1 import FAMILY_FLAGS  # noqa: E402
from casepath_api.autonomous_policy_v1 import REQUIRED_FIELDS  # noqa: E402

assert "llm" not in sys.modules, "check.py must not load the model client"
REQ = {"needed_now", "needed_later"}
results: dict = {}
failures: list[str] = []


def check(name: str, ok: bool, detail=None):
    results[name] = {"ok": bool(ok), **({"detail": detail} if detail is not None else {})}
    if not ok:
        failures.append(name)


# ------------------------------------------------------------------ 1-2 tenancy oracle and open facts
def engine(ref, sources, verdicts):
    conds = [{"flag": f, "verdict": v, "summary": "", "citations": []} for f, v in verdicts.items()]
    docs = [{"document_type": a["document_type"], "artifact_id": a["artifact_id"],
             "assessment": "sufficient" if a["sufficient"] else "insufficient", "summary": "", "citations": [],
             "independently_verified": True} for a in ref["attachments"]]
    verified = {"category": {"family": ref["family"], "summary": "", "citations": []}, "conditions": conds,
                "documents": docs, "steps": [], "item_rejections": []}
    plan = plan_from_verified_exact(ref["claim_id"], verified, sources)
    supplied = {a["document_type"] for a in ref["attachments"]}
    return {d: ("supplied_insufficient" if d in supplied else "required_now") if r in REQ else
            "held" if r == "held_behind_question" else "supplied_sufficient" if r == "established" else "not_needed"
            for d, r in plan["document_states"].items()}


ids = T2.claim_ids("test")
bad, open_bad, n_open = [], [], 0
for cid in ids:
    ref = T2.reference(cid)
    truth = {**ref["implicit_flags"], **ref["scenario"]}
    routing = next(iter(ref["implicit_flags"]), None)
    verdicts, answered = {}, {}
    for f, s in ref["fact_states"].items():
        if s == "stated_true":
            assert truth[f], (cid, f)
            v = "true"
        elif s == "stated_false":
            assert not truth[f], (cid, f)
            v = "false"
        elif s == "absent":
            assert not truth[f] and f != routing, (cid, f)
            v = "false"                      # silence policy: an unmentioned branch fact is presumed absent
        elif s == "unmentioned":
            assert truth[f] and f == routing, (cid, f)
            v = "true"                       # silence policy: the defining event is presumed to have occurred
        else:
            assert s == "open" and ref["open_fact"] == {"flag": f, "true_value": truth[f]}, cid
            v = "unresolved"
        verdicts[f] = v
        answered[f] = ("true" if truth[f] else "false") if v == "unresolved" else v
    srcs = T2.sources(cid)
    assert {a["artifact_id"] for a in ref["attachments"]} == {s["artifact_id"] for s in srcs[1:]}, cid
    st = engine(ref, srcs, verdicts)
    an = engine(ref, srcs, answered)
    ok = (st == ref["document_states"] and an == ref["answered"]["document_states"]
          and sorted(d for d, x in st.items() if x in ("required_now", "supplied_insufficient")) == ref["request_set"]
          and sorted(d for d, x in st.items() if x == "held") == ref["held_set"])
    if not ok:
        bad.append(cid)
    if ref["open_fact"]:
        n_open += 1
        f = ref["open_fact"]["flag"]
        alt = dict(answered, **{f: "false" if answered[f] == "true" else "true"})
        other = engine(ref, srcs, alt)
        if not (ref["held_set"] and st != an and an != other):
            open_bad.append(cid)
check("tenancy_oracle_reproduces_every_reference", not bad and len(ids) == 96,
      {"claims": len(ids), "reproduced": len(ids) - len(bad), "mismatches": bad})
check("open_facts_are_open_under_the_engine", not open_bad and n_open == 32,
      {"open_fact_claims": n_open, "each_holds_documents_and_resolution_changes_plan": n_open - len(open_bad),
       "failing": open_bad})

# ------------------------------------------------------------------ 3 theft oracle
texts = H2.texts()
prs = H2.pairs()
rows = []
for p in prs:
    ref = p["reference"]
    opt = sorted(d.lstrip("+") for d in ref["acceptable_signed_deltas"][0])
    off = {"requests": [], "holds": []}
    var = {"requests": opt, "holds": []} if p["kind"] == "on" else {"requests": [], "holds": opt}
    rows.append(score_pair(p, off, var))
on = [r for r in rows if r["kind"] == "on"]
un = [r for r in rows if r["kind"] == "unresolved"]
check("theft_reference_plans_score_perfectly",
      all(r["exact"] and r["wrong"] == 0 and r["missed"] == 0 for r in on)
      and all(r["held"] and not r["premature"] and r["stable"] for r in un),
      {"on_pairs": len(on), "exact": sum(r["exact"] for r in on), "wrong": sum(r["wrong"] for r in on),
       "missed": sum(r["missed"] for r in on), "unresolved_pairs": len(un),
       "held_correctly": sum(r["held"] for r in un), "premature": sum(r["premature"] for r in un)})

# ------------------------------------------------------------------ 4 loaders and counts
refs = [T2.reference(c) for c in ids]
intakes = [T2.intake(c) for c in ids]
srcs_all = [T2.sources(c) for c in ids]
atts = [a for r in refs for a in r["attachments"]]
fam = Counter(r["family_id"] for r in refs)
stories = sorted({v["story"] for v in texts.values()})
check("tenancy_counts", len(ids) == 96 and len(fam) == 24 and set(fam.values()) == {4}
      and sum(r["open_fact"] is not None for r in refs) == 32
      and all(len(s) == 1 + len(i["attachments"]) and all(x["complete"] for x in s) for s, i in zip(srcs_all, intakes))
      and T2.claim_ids("dev") == [] and len(T2.templates()["templates"]) == 3 and len(T2.cohort()["cases"]) == 96,
      {"claims": len(ids), "families": len(fam), "open_fact_claims": sum(r["open_fact"] is not None for r in refs),
       "open_true_value": dict(Counter(str(r["open_fact"]["true_value"]) for r in refs if r["open_fact"])),
       "by_dispute": dict(Counter(r["family"] for r in refs)),
       "defining_event_false_claims": sum(not next(iter(r["implicit_flags"].values()), True) for r in refs),
       "language": dict(Counter(i["submission"]["language"] for i in intakes)),
       "channel": dict(Counter(i["submission"]["channel"] for i in intakes)),
       "attachments": len(atts), "attachments_sufficient": sum(a["sufficient"] for a in atts),
       "claims_with_attachments": sum(bool(r["attachments"]) for r in refs),
       "document_states": dict(Counter(s for r in refs for s in r["document_states"].values())),
       "required_documents": sum(len(r["request_set"]) for r in refs),
       "held_documents": sum(len(r["held_set"]) for r in refs),
       "claims_with_empty_request_set": sum(not r["request_set"] for r in refs),
       "fact_states": dict(Counter(s for r in refs for s in r["fact_states"].values())),
       "stated_fact_expression": dict(Counter(e for r in refs for e in r["expression"].values())),
       "words_min_max": [min(len(i["customer_message"]["body"].split()) for i in intakes),
                         max(len(i["customer_message"]["body"].split()) for i in intakes)]})
fields_ok = all(a["omitted_field"] is None or a["omitted_field"] in REQUIRED_FIELDS[a["document_type"]] for a in atts)
check("attachments_recorded_with_sufficiency", fields_ok and all(a["sufficient"] == (a["omitted_field"] is None) for a in atts))
check("theft_counts", stories == list(range(8, 16)) and len(texts) == 8 * 16 and len(prs) == 8 * 15
      and Counter(p["kind"] for p in prs) == Counter({"on": 72, "unresolved": 48})
      and all(p["split"] == "heldout" for p in prs),
      {"stories": stories, "texts": len(texts), "pairs": dict(Counter(p["kind"] for p in prs)),
       "build_checks": H2.benchmark()["fresh_build"]["checks"],
       "off_text_words": H2.benchmark()["fresh_build"]["off_text_words_min_max"]})

# ------------------------------------------------------------------ 5 novelty
used = set()
for split in ("dev", "test"):
    for c in T0.claim_ids(split):
        r = T0.reference(c)
        used.add((r["family"], next(iter(r["implicit_flags"].values()), None), tuple(sorted(k for k, v in r["scenario"].items() if v))))
for c in T1.claim_ids("test"):
    r = T1.reference(c)
    used.add((r["family"], next(iter(r["implicit_flags"].values()), None), tuple(sorted(k for k, v in r["scenario"].items() if v))))
new = {(r["family"], next(iter(r["implicit_flags"].values()), None), tuple(sorted(k for k, v in r["scenario"].items() if v)))
       for r in refs}
check("flag_combinations_unused", len(new) == 24 and not (new & used), {"new": len(new), "overlap": sorted(map(str, new & used))})

WORD = re.compile(r"\w+", re.UNICODE)


def toks(s):
    return [w.lower() for w in WORD.findall(s)]


def jac(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def tri(t):
    return {tuple(t[i:i + 3]) for i in range(len(t) - 2)}


def texts_of(mod, cids):
    out = {}
    for c in cids:
        i = mod.intake(c)
        out[c] = i["customer_message"]["body"]
        for a in i.get("attachments", []):
            if a.get("media_type") == "text/plain":
                out[f"{c}/{a['artifact_id']}"] = base64.b64decode(a["content_base64"]).decode()
    return out


old = {}
for split in ("dev", "test"):
    old.update({f"S1:{k}": v for k, v in texts_of(T0, T0.claim_ids(split)).items()})
old.update({f"fresh:{k}": v for k, v in texts_of(T1, T1.claim_ids("test")).items()})
new_t = texts_of(T2, ids)
old_tok = {k: (set(toks(v)), tri(toks(v))) for k, v in old.items()}
new_tok = {k: (set(toks(v)), tri(toks(v))) for k, v in new_t.items()}
TH_SET, TH_TRI = 0.6, 0.3
worst_old, worst_new, flagged = (0, 0, None), (0, 0, None), []
for k, (s, t) in new_tok.items():
    for k2, (s2, t2) in old_tok.items():
        js, jt = jac(s, s2), jac(t, t2)
        if (js, jt) > worst_old[:2]:
            worst_old = (js, jt, (k, k2))
        if js >= TH_SET or jt >= TH_TRI:
            flagged.append((k, k2, round(js, 3), round(jt, 3)))
bodies = {k: v for k, v in new_tok.items() if "/" not in k}
for (k, (s, t)), (k2, (s2, t2)) in combinations(bodies.items(), 2):
    js, jt = jac(s, s2), jac(t, t2)
    if (js, jt) > worst_new[:2]:
        worst_new = (js, jt, (k, k2))
    if js >= TH_SET or jt >= TH_TRI:
        flagged.append((k, k2, round(js, 3), round(jt, 3)))
check("tenancy_no_near_duplicate_text", not flagged,
      {"thresholds": {"token_set_jaccard": TH_SET, "word_trigram_jaccard": TH_TRI},
       "fresh2_texts": len(new_tok), "compared_with": {"study1_and_fresh_texts": len(old_tok)},
       "max_vs_original_and_fresh": [round(worst_old[0], 3), round(worst_old[1], 3), worst_old[2]],
       "max_between_fresh2_messages": [round(worst_new[0], 3), round(worst_new[1], 3), worst_new[2]],
       "flagged": flagged})

sentences = set()
for pr in H0.benchmark()["pairs"]:
    sentences |= {pr["changed_statement_false"], pr["changed_statement_true"]}
sentences |= set(H0.UNRESOLVED.values())


def strip(text):
    for s in sorted(sentences, key=len, reverse=True):
        text = text.replace(s, " ")
    return text


old_th = {f"s{v['story']}": strip(v["text"]) for v in list(H0.texts().values()) + list(H1.texts().values()) if v["kind"] == "off"}
new_th = {f"s{v['story']}": strip(v["text"]) for v in texts.values() if v["kind"] == "off"}
th_flag, th_worst = [], (0, 0, None)
for k, v in new_th.items():
    a = toks(v)
    for k2, v2 in list(old_th.items()) + [(x, y) for x, y in new_th.items() if x > k]:
        b = toks(v2)
        js, jt = jac(set(a), set(b)), jac(tri(a), tri(b))
        if (js, jt) > th_worst[:2]:
            th_worst = (js, jt, (k, k2))
        if js >= TH_SET or jt >= TH_TRI:
            th_flag.append((k, k2, round(js, 3), round(jt, 3)))
check("theft_stories_differ_from_stories_0_7_and_each_other", not th_flag and len(old_th) == 8,
      {"max": [round(th_worst[0], 3), round(th_worst[1], 3), th_worst[2]], "flagged": th_flag,
       "note": "condition and open-condition sentences removed before comparison (they are shared by design)"})

# ------------------------------------------------------------------ 6 manifest
man = HERE / "MANIFEST.json"
if man.exists():
    m = json.loads(man.read_text())
    files = sorted(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != "MANIFEST.json")
    now = {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    diff = sorted(set(now) ^ set(m["files"])) + sorted(k for k in now if k in m["files"] and now[k] != m["files"][k])
    check("manifest_hashes_match", not diff, {"files": len(m["files"]), "differences": diff})
else:
    check("manifest_hashes_match", False, "MANIFEST.json missing")

out = {"ok": not failures, "failures": failures, "checks": results}
print(json.dumps(out, ensure_ascii=False, indent=1))
sys.exit(1 if failures else 0)
