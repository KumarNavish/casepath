"""Freeze the held-out theft causal benchmark before any CasePath model run.

The reference contract was authored independently of the induced CasePath graph. This
builder strips its process labels from the model-visible authority snapshot, creates
minimal factual branch contrasts, and runs input-free shortcut diagnostics on gold labels.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "theft_causal"
OUT.mkdir(exist_ok=True)
GOAL = "a9cd441ef939e36d7ed2c546b76aa41554813aba11ba1a379f23479ded4cc37b"
REF_PATH = ROOT / "reference_contracts" / "theft.json"
DIAG_PATH = ROOT / "artifacts" / "THEFT_BRANCH_DIAGNOSTIC.json"
ref = json.loads(REF_PATH.read_text())["contract"]
diag = json.loads(DIAG_PATH.read_text())
SELECTED = [
    "PR_scheduled_valuable_1000",
    "PR_bicycle_claimed",
    "PR_sim_card_stolen",
    "PR_third_party_causer",
    "PR_expert_procedure_requested",
    "PR_repair_over_500",
    "PR_nachfrist_set",
    "PR_goods_recovered",
    "PR_declined",
]

STATE_TEXT = {
    "PR_scheduled_valuable_1000": (
        "No stolen item is separately scheduled in the policy with an insured value of CHF 1,000 or more.",
        "A stolen watch is separately scheduled in the policy with an insured value of CHF 4,000.",
    ),
    "PR_bicycle_claimed": (
        "No bicycle or e-bike is among the stolen items.",
        "A bicycle is among the stolen items.",
    ),
    "PR_sim_card_stolen": (
        "No SIM card was stolen and no loss from SIM-card misuse is claimed.",
        "A SIM card was stolen and loss from its misuse is part of the claim.",
    ),
}
STATE_TEXT.update({
    "PR_third_party_causer": (
        "No identifiable third party caused or enlarged the loss apart from the unidentified thief.",
        "An identified building contractor caused the loss and their identity is known.",
    ),
    "PR_expert_procedure_requested": (
        "Neither party has requested the formal expert determination procedure.",
        "The policyholder has requested the formal expert determination procedure in writing.",
    ),
    "PR_repair_over_500": (
        "No repair costing more than CHF 500 is contemplated for the damaged insured items.",
        "A repair to a damaged insured item is contemplated and is expected to cost CHF 1,200.",
    ),
    "PR_nachfrist_set": (
        "The insurer has not sent a written demand setting a document deadline under a forfeiture warning.",
        "The insurer sent a written demand warning that the claim will be forfeited unless the requested communications are supplied within 10 days.",
    ),
    "PR_goods_recovered": (
        "None of the stolen items has been recovered and no news of them has been received.",
        "One of the stolen items has been recovered and the policyholder has received news of its recovery.",
    ),
    "PR_declined": (
        "The insurer has not declined the claim for indemnity.",
        "The insurer has declined the claim for indemnity in writing.",
    ),
})

CONTEXTS = [
    "The claim concerns a household-contents theft reported after a forced entry into a Basel apartment on 12 February 2026. Police were notified and a laptop and camera are claimed as stolen.",
    "The claim concerns household property stolen after forced entry into a rented flat in Bern on 3 March 2026. The theft was reported to police and to the insurer.",
    "The policyholder reports a household-contents theft after a break-in at a Zurich home on 21 April 2026. Police attended and the insurer opened the claim.",
    "The file concerns insured household items stolen during a forced entry in Lausanne on 7 May 2026. Police notification and insurer notification have already occurred.",
]
URLS = {
    "vvg-": "https://www.fedlex.admin.ch/eli/cc/24/719_735_717/de",
    "css-avb-": "https://www.css.ch/content/dam/css/de/documents/privatkunden/richtig-versichert/avb/519_d_avb_hausratversicherung.pdf",
    "css-form-": "https://www.css.ch/content/dam/css/de/documents/privatkunden/richtig-versichert/formulare/15_d_formular_schadenanzeige_hausrat.pdf",
    "svv-": "https://svv.ch/sites/default/files/media/documents/2024-02/AVB%20Hausratversicherung%202022.pdf",
    "simpego-": "https://simpego.ch/dam/AVB_Simpego_Home_de.pdf",
    "axa-": "https://www.axa.ch/servlets/external/docstoredocument?accesscode=ag58y",
    "generali-": "https://www.generali.ch/content/dam/generali/pdf/produktdokumente/avb-ki/hausrat-haftpflicht/avb-haushaltversicherung-de.pdf",
}

def source_url(authority: str) -> str | None:
    for prefix, url in URLS.items():
        if authority.startswith(prefix):
            return url
    return None


def sha(obj) -> str:
    raw = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
# Build a model-visible authority snapshot from exact public-source quotations only.
# Contract decision/fact/predicate labels are deliberately not exposed to the model.
quote_provenance: dict[str, dict] = {}
for family in ("decisions", "predicates", "deadlines"):
    for elem in ref[family]:
        auth = elem.get("authorities") or []
        quotes = elem.get("quotes") or []
        aligned = len(auth) == len(quotes)
        for i, text in enumerate(quotes):
            q = " ".join(text.split())
            if not q:
                continue
            rec = quote_provenance.setdefault(q, {"candidate_authority_ids": set(), "aligned_authority_ids": set()})
            rec["candidate_authority_ids"].update(auth)
            if aligned:
                rec["aligned_authority_ids"].add(auth[i])

passages = []
for q in sorted(quote_provenance, key=lambda x: hashlib.sha256(x.encode()).hexdigest()):
    prov = quote_provenance[q]
    best = sorted(prov["aligned_authority_ids"] or prov["candidate_authority_ids"])
    urls = sorted({u for a in best if (u := source_url(a))})
    passages.append({
        "authority_id": f"theft-source-{len(passages)+1:04d}",
        "article": " | ".join(best),
        "exact_text": q,
        "source_url": urls[0] if len(urls) == 1 else None,
        "source_urls": urls,
        "canonical_authority_candidates": best,
        "text_sha256": hashlib.sha256(q.encode()).hexdigest(),
    })
source_bundle = {"contract": "casepath.theft-authority-snapshot/1.0.0", "passages": passages}
diag_by_pred = {x["predicate_id"]: x for x in diag["predicates"]}
missing = [p for p in SELECTED if p not in diag_by_pred]
if missing:
    raise SystemExit(f"selected predicates missing from diagnostic: {missing}")
if set(SELECTED) != set(STATE_TEXT):
    raise SystemExit("STATE_TEXT must cover exactly the selected predicates")

target_docs = {p: tuple(diag_by_pred[p]["released_if_false"]) for p in SELECTED}
flat_docs = [d for p in SELECTED for d in target_docs[p]]
if len(flat_docs) != len(set(flat_docs)):
    raise SystemExit("selected branch target document sets overlap")
contract_docs = {d["document_type"] for d in ref["documents"]}
if set(flat_docs) - contract_docs:
    raise SystemExit("target document absent from reference contract")
pairs = []
units = []
for scenario_index, target in enumerate(SELECTED):
    for context_index, context in enumerate(CONTEXTS):
        base_states = {p: False for p in SELECTED}
        variants = {}
        for target_value in (False, True):
            states = dict(base_states)
            states[target] = target_value
            state_lines = [STATE_TEXT[p][1 if states[p] else 0] for p in SELECTED]
            text = context + "\n\n" + "\n".join(f"- {line}" for line in state_lines)
            suffix = "true" if target_value else "false"
            unit_id = f"theft-{scenario_index+1:02d}-{context_index+1:02d}-{suffix}"
            gold = sorted(target_docs[target] if target_value else ())
            variants[target_value] = (unit_id, gold)
            units.append({"unit_id": unit_id, "scenario": target, "context_index": context_index,
                          "target_value": target_value, "customer_message": text,
                          "gold_branch_documents": gold})
        false_id, _ = variants[False]
        true_id, true_gold = variants[True]
        pairs.append({
            "pair_id": f"theft-{scenario_index+1:02d}-{context_index+1:02d}",
            "scenario": target,
            "context_index": context_index,
            "false_unit_id": false_id,
            "true_unit_id": true_id,
            "expected_added": true_gold,
            "expected_withdrawn": [],
            "changed_statement_false": STATE_TEXT[target][0],
            "changed_statement_true": STATE_TEXT[target][1],
        })

benchmark = {
    "contract": "casepath.theft-causal-branch-benchmark/1.0.0",
    "goal_contract_sha256": GOAL,
    "scope": "held-out household-contents theft",
    "paper_method_target": "active process state -> obligation -> fact -> evidence capability -> document route",
    "selected_predicates": SELECTED,
    "branch_document_universe": sorted(set(flat_docs)),
    "units": units,
    "pairs": pairs,
}
def pooled_f1(pred: set[str], gold_sets: list[set[str]]) -> float:
    tp = sum(len(pred & g) for g in gold_sets)
    predicted = len(pred) * len(gold_sets)
    gold = sum(len(g) for g in gold_sets)
    return 2 * tp / (predicted + gold) if predicted + gold else 0.0


def best_constant(gold_sets: list[set[str]], universe: list[str]) -> tuple[set[str], float]:
    best: tuple[set[str], float] = (set(), -1.0)
    for mask in range(1 << len(universe)):
        pred = {universe[i] for i in range(len(universe)) if mask & (1 << i)}
        score = pooled_f1(pred, gold_sets)
        if score > best[1] + 1e-12 or (abs(score - best[1]) < 1e-12 and len(pred) < len(best[0])):
            best = pred, score
    return best

pair_gold = {p["pair_id"]: set(p["expected_added"]) for p in pairs}
universe = sorted(set(flat_docs))
folds = []
for held in SELECTED:
    train = [pair_gold[p["pair_id"]] for p in pairs if p["scenario"] != held]
    test = [pair_gold[p["pair_id"]] for p in pairs if p["scenario"] == held]
    pred, train_f1 = best_constant(train, universe)
    folds.append({"held_out_scenario": held, "selected_constant": sorted(pred),
                  "train_micro_f1": round(train_f1, 6),
                  "held_out_micro_f1": round(pooled_f1(pred, test), 6)})
counts = Counter(tuple(p["expected_added"]) for p in pairs)
probs = [n / len(pairs) for n in counts.values()]
entropy = -sum(p * math.log2(p) for p in probs)
unit_by_id = {u["unit_id"]: u for u in units}
edit_checks = []
for pair in pairs:
    a = unit_by_id[pair["false_unit_id"]]["customer_message"].splitlines()
    b = unit_by_id[pair["true_unit_id"]]["customer_message"].splitlines()
    diffs = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
    edit_checks.append({"pair_id": pair["pair_id"], "changed_line_count": len(diffs), "changed_line_indices": diffs})

shortcut = {
    "contract": "casepath.theft-causal-shortcut-preflight/1.0.0",
    "pairs": len(pairs),
    "units": len(units),
    "scenarios": len(SELECTED),
    "distinct_gold_delta_sets": len(counts),
    "gold_delta_entropy_bits": round(entropy, 6),
    "branch_document_universe_size": len(universe),
    "crossfit_no_input_folds": folds,
    "max_held_out_no_input_micro_f1": max(x["held_out_micro_f1"] for x in folds),
    "all_pairs_change_exactly_one_line": all(x["changed_line_count"] == 1 for x in edit_checks),
    "edit_checks": edit_checks,
    "admission": {
        "input_free_control_pass": max(x["held_out_micro_f1"] for x in folds) <= 0.10,
        "target_diversity_pass": len(counts) == len(SELECTED),
        "minimal_edit_pass": all(x["changed_line_count"] == 1 for x in edit_checks),
    },
}
visible_source_text = json.dumps(source_bundle, ensure_ascii=False)
for forbidden in ("PR_scheduled_valuable_1000", "D12_valuables_precondition_checked", "released_if_false"):
    if forbidden in visible_source_text:
        raise SystemExit("reference-contract structure leaked into the source snapshot")

benchmark_path = OUT / "BENCHMARK.json"
source_path = OUT / "SOURCE_SNAPSHOT.json"
shortcut_path = OUT / "SHORTCUT_PREFLIGHT.json"
dump(benchmark_path, benchmark)
dump(source_path, source_bundle)
dump(shortcut_path, shortcut)
freeze = {
    "contract": "casepath.theft-causal-freeze/1.0.0",
    "goal_contract_sha256": GOAL,
    "reference_contract_sha256": hashlib.sha256(REF_PATH.read_bytes()).hexdigest(),
    "theft_branch_diagnostic_sha256": hashlib.sha256(DIAG_PATH.read_bytes()).hexdigest(),
    "benchmark_sha256": hashlib.sha256(benchmark_path.read_bytes()).hexdigest(),
    "source_snapshot_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
    "shortcut_preflight_sha256": hashlib.sha256(shortcut_path.read_bytes()).hexdigest(),
    "model_runs_consumed_for_this_benchmark": 0,
    "held_out_scope": True,
    "source_snapshot_note": "Exact quotations from the independently authored public-source reference contract; process labels are stripped and snippets are SHA-sorted.",
}
dump(OUT / "FREEZE.json", freeze)
print(json.dumps({
    "freeze": freeze,
    "shortcut_admission": shortcut["admission"],
    "passages": len(passages),
    "pairs": len(pairs),
    "units": len(units),
}, indent=2))
