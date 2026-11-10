"""Build the fresh2 theft stories (ids 8-15). No model calls, no method outputs consulted.

Steps:
1. Copy the frozen reference contract and the two released construction scripts into build/.
2. Run theft_branch_diagnostic.py on the contract (the branch-document projection).
3. Run theft_causal_benchmark.py with its CONTEXTS list replaced by: the four original contexts, the four
   fresh/ contexts (stories 4-7) and the eight new one-sentence contexts of stories.py (stories 8-15). Nothing
   else in the script is changed.
4. Checks: the rebuilt original stories reproduce BENCHMARK_V3 (texts identical; references identical except
   where amendments V2/V3 changed them); the rebuilt stories 4-7 reproduce fresh/theft/BENCHMARK_FRESH.json texts;
   the released input-free and minimal-edit preflight passes; the v1 reference of every condition is identical in
   all sixteen stories (the reference depends on the condition only).
5. Case texts: unlike stories 0-7 (a context paragraph followed by a bulleted list of the nine condition
   sentences), the texts of stories 8-15 are the composed documents of stories.py, with the nine condition
   sentences embedded verbatim. The off text has all nine false; each on text replaces exactly one false sentence
   by its true sentence. Checked: each sentence occurs exactly once, the on text differs from the off text only by
   that substitution, and the unresolved variant (built by the loader with str.replace) changes the text.
6. References: each new pair carries the V3 reference of its condition (requirement ids renamed), each unit the V3
   gold documents of its condition and value - exactly as for fresh/.

Output: fresh2/theft/BENCHMARK_FRESH2.json and fresh2/theft/build/ (work files, build log).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parents[1]
REPO = HERE.parents[3]
DATA = REPO / "data" / "casepath-theft-pairs"
V3 = json.loads((DATA / "benchmark" / "benchmark" / "BENCHMARK_V3.json").read_text())
FRESH = json.loads((TMIS / "fresh" / "theft" / "BENCHMARK_FRESH.json").read_text())
WORK = HERE / "build"
N_OLD = 4
sys.path.insert(0, str(TMIS / "harness"))
from theft_data import UNRESOLVED  # noqa: E402

_s = importlib.util.spec_from_file_location("fresh2_stories", HERE / "stories.py")
stories = importlib.util.module_from_spec(_s)
_s.loader.exec_module(stories)
NEW_IDS = sorted(stories.STORIES)
assert NEW_IDS == list(range(8, 16)), NEW_IDS


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def compose(story: int, states: dict, state_text: dict) -> str:
    text = stories.STORIES[story]["text"]
    for key, pred in stories.KEYS.items():
        text = text.replace(f"«{key}»", state_text[pred][1 if states[pred] else 0])
    assert "«" not in text and "»" not in text, story
    return text


def main() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    (WORK / "reference_contracts").mkdir(parents=True)
    (WORK / "artifacts").mkdir()
    shutil.copy(DATA / "reference-contract" / "theft.json", WORK / "reference_contracts" / "theft.json")
    shutil.copy(DATA / "construction" / "theft_branch_diagnostic.py", WORK / "theft_branch_diagnostic.py")
    src = (DATA / "construction" / "theft_causal_benchmark.py").read_text()
    start = src.index("CONTEXTS = [")
    end = src.index("]\n", start) + 2
    old_contexts = eval(src[start + len("CONTEXTS = "):end])  # the released list, a literal
    fresh_contexts = FRESH["fresh_build"]["contexts"]
    new_contexts = [stories.STORIES[i]["context"] for i in NEW_IDS]
    contexts = old_contexts + fresh_contexts + new_contexts
    assert len(contexts) == 16
    patched = src[:start] + "CONTEXTS = " + json.dumps(contexts, indent=4, ensure_ascii=False) + "\n" + src[end:]
    (WORK / "theft_causal_benchmark.py").write_text(patched)
    diag = subprocess.run([sys.executable, "theft_branch_diagnostic.py"], cwd=WORK, capture_output=True, text=True, check=True)
    (WORK / "artifacts" / "THEFT_BRANCH_DIAGNOSTIC.json").write_text(diag.stdout)
    run = subprocess.run([sys.executable, "theft_causal_benchmark.py"], cwd=WORK, capture_output=True, text=True, check=True)
    (WORK / "build_log.json").write_text(run.stdout)
    built = json.loads((WORK / "theft_causal" / "BENCHMARK.json").read_text())
    admission = json.loads(run.stdout)["shortcut_admission"]
    assert all(admission.values()), admission

    # the condition sentences, read from the released script itself (not retyped)
    ns: dict = {}
    s0 = src.index("STATE_TEXT = {")
    s1 = src.index("CONTEXTS = [")
    exec(src[s0:s1], ns)  # two literal dict statements
    state_text = ns["STATE_TEXT"]
    selected = built["selected_predicates"]
    assert set(selected) == set(state_text) == set(stories.KEYS.values())

    # ---- checks against the released and the fresh benchmark
    v3_units = {u["unit_id"]: u for u in V3["units"]}
    v3_pairs = {p["pair_id"]: p for p in V3["pairs"]}
    fresh_units = {u["unit_id"]: u for u in FRESH["units"]}
    amended = {"PR_scheduled_valuable_1000", "PR_bicycle_claimed"}  # BENCHMARK_AMENDMENT_V2 / _V3
    checks = {"original_texts_identical": 0, "original_v1_refs_identical_or_amended": 0, "fresh_4_7_texts_identical": 0}
    for u in built["units"]:
        if u["context_index"] < N_OLD:
            assert u["customer_message"] == v3_units[u["unit_id"]]["customer_message"], u["unit_id"]
            checks["original_texts_identical"] += 1
        elif u["context_index"] < 8:
            assert u["customer_message"] == fresh_units[u["unit_id"]]["customer_message"], u["unit_id"]
            checks["fresh_4_7_texts_identical"] += 1
    for p in built["pairs"]:
        if p["context_index"] < N_OLD:
            same = p["expected_added"] == v3_pairs[p["pair_id"]]["expected_added"]
            assert same or p["scenario"] in amended, p["pair_id"]
            checks["original_v1_refs_identical_or_amended"] += 1
    by_scen = {}
    for p in built["pairs"]:
        by_scen.setdefault(p["scenario"], set()).add(json.dumps(p["expected_added"]))
    assert all(len(v) == 1 for v in by_scen.values()), "v1 reference differs between stories"
    checks["v1_reference_depends_on_condition_only_16_stories"] = True
    checks["released_preflight_admission"] = admission

    # ---- composed texts for stories 8-15
    texts_checked = 0
    for s in NEW_IDS:
        off = compose(s, {p: False for p in selected}, state_text)
        for pred in selected:
            assert off.count(state_text[pred][0]) == 1, (s, pred)
            on = compose(s, {p: p == pred for p in selected}, state_text)
            assert on == off.replace(state_text[pred][0], state_text[pred][1]) and on != off, (s, pred)
            if pred in UNRESOLVED:
                assert off.replace(state_text[pred][0], UNRESOLVED[pred]) != off
            texts_checked += 1
    checks["composed_texts_single_substitution"] = texts_checked

    # ---- new stories in the V3 format
    template_pair = {p["scenario"]: p for p in V3["pairs"] if p["context_index"] == 1}
    template_unit = {(u["scenario"], u["target_value"]): u for u in V3["units"] if u["context_index"] == 1}
    units, pairs = [], []
    for u in built["units"]:
        if u["context_index"] < 8:
            continue
        t = template_unit[(u["scenario"], u["target_value"])]
        states = {p: (p == u["scenario"] and u["target_value"]) for p in selected}
        nu = {**u, "customer_message": compose(u["context_index"], states, state_text),
              "gold_branch_documents": t["gold_branch_documents"]}
        assert set(nu) == set(t)
        units.append(nu)
    for p in built["pairs"]:
        if p["context_index"] < 8:
            continue
        t = deepcopy(template_pair[p["scenario"]])
        np_ = {**t, "pair_id": p["pair_id"], "context_index": p["context_index"], "false_unit_id": p["false_unit_id"],
               "true_unit_id": p["true_unit_id"]}
        for i, req in enumerate(np_["expected_added_requirements"], 1):
            req["requirement_id"] = f"{p['pair_id']}-added-{i:02d}"
        for i, req in enumerate(np_["expected_withdrawn_requirements"], 1):
            req["requirement_id"] = f"{p['pair_id']}-withdrawn-{i:02d}"
        assert np_["changed_statement_false"] == p["changed_statement_false"]
        assert np_["changed_statement_true"] == p["changed_statement_true"]
        assert set(np_) == set(t)
        pairs.append(np_)
    words = sorted(len(compose(s, {p: False for p in selected}, state_text).split()) for s in NEW_IDS)
    out = {k: v for k, v in V3.items() if k not in ("units", "pairs")}
    out.update({"contract": V3["contract"] + "+fresh2-stories-8-15", "units": units, "pairs": pairs,
                "fresh_build": {"contexts": new_contexts, "context_indices": NEW_IDS,
                                "forms": {s: stories.STORIES[s]["form"] for s in NEW_IDS},
                                "text_layout": "composed documents with the nine condition sentences embedded verbatim (stories.py); stories 0-7 use a context paragraph and a bulleted list",
                                "off_text_words_min_max": [words[0], words[-1]],
                                "reference_contract_sha256": sha(DATA / "reference-contract" / "theft.json"),
                                "construction_script_sha256": {f: sha(DATA / "construction" / f) for f in
                                                               ("theft_causal_benchmark.py", "theft_branch_diagnostic.py")},
                                "benchmark_v3_sha256": sha(DATA / "benchmark" / "benchmark" / "BENCHMARK_V3.json"),
                                "benchmark_fresh_sha256": sha(TMIS / "fresh" / "theft" / "BENCHMARK_FRESH.json"),
                                "stories_sha256": sha(HERE / "stories.py"),
                                "checks": checks}})
    (HERE / "BENCHMARK_FRESH2.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"units": len(units), "pairs": len(pairs), "words": words, **checks}, indent=1))


if __name__ == "__main__":
    main()
