"""Canonical validity audit for CasePath evaluation artifacts.

No model/network calls.  All quantities are recomputed from committed artifacts.
The audit asks whether a score supports an input-conditioned competence claim.
"""
from __future__ import annotations

import collections
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ART = HERE / "artifacts"
sys.path.insert(0, str(REPO / "casepath-api"))

from casepath_api import contract_scoring_v1 as cs  # noqa: E402

SEED = 20260916
N_BOOT = 5000
N_PERM = 5000
HELD = {"lease_contract"}

def load(name: str):
    return json.loads((ART / name).read_text())


def contract(name: str):
    return json.loads((HERE / "reference_contracts" / name).read_text())


def q025(values):
    values = sorted(values)
    return [values[int(0.025 * len(values))], values[int(0.975 * len(values))]]


def f1(pred, gold):
    pred, gold = set(pred), set(gold)
    if not pred and not gold:
        return 1.0
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def exact_random_hits(B, W, E):
    """Expected hits when |W| elements are drawn uniformly from B."""
    return (len(W) * len(B & E) / len(B)) if B else 0.0

def make_reference(raw_name: str, C):
    by = collections.defaultdict(list)
    meta = {}
    for row in load(raw_name):
        if row.get("decisions"):
            by[row["unit_id"]].append(row)
            meta[row["unit_id"]] = row.get("scenario")
    ref = {}
    for unit_id, votes in by.items():
        statuses = cs.adjudicate(votes)
        ref[unit_id] = {
            **cs.reference_set(C, statuses, held=sorted(HELD)),
            "statuses": statuses,
            "unanimity": (
                sum(v["unanimous"] for v in statuses.values()) / len(statuses)
                if statuses else 0.0
            ),
        }
    return ref, meta


def modal_set(sets):
    counts = collections.Counter(tuple(sorted(x)) for x in sets)
    value, count = counts.most_common(1)[0]
    return set(value), count

def static_summary(units_name: str, ref, suffix="__orig"):
    unit_ids = [u["unit_id"] for u in load(units_name) if u["unit_id"].endswith(suffix)]
    gold = [set(ref[u]["documents"]) for u in unit_ids if u in ref]
    modal, modal_n = modal_set(gold)
    return {
        "n": len(gold),
        "distinct_gold_sets": len({tuple(sorted(x)) for x in gold}),
        "modal_count": modal_n,
        "modal_share": modal_n / len(gold),
        "modal_documents": sorted(modal),
        "modal_oracle_mean_f1": sum(f1(modal, x) for x in gold) / len(gold),
        "mean_gold_size": sum(map(len, gold)) / len(gold),
    }


def document_layer_capacity(C):
    """Exact checklist capacity over all open/closed decision masks.

    This is not a legal reachability claim: it asks only what the document layer
    can express if arbitrary subsets of decisions are open.
    """
    values = {frozenset()}
    for d in C["decisions"]:
        docs = frozenset(set(d.get("required_documents") or []) - HELD)
        values |= {v | docs for v in tuple(values)}
    return len(values)

def paired_ids(A, ref, intervention_suffix):
    out = []
    for orig in sorted(A):
        if not orig.endswith("__orig"):
            continue
        mod = orig[:-6] + intervention_suffix
        if mod in A and orig in ref and mod in ref:
            out.append((orig, mod))
    return out


def records_for_arm(A, ref, meta, pairs, arm):
    rows = []
    for orig, mod in pairs:
        E = set(ref[orig]["documents"]) - set(ref[mod]["documents"])
        K = set(ref[mod]["documents"])
        B = set(A[orig]["arms"][arm].get("documents") or []) - HELD
        after = set(A[mod]["arms"][arm].get("documents") or []) - HELD
        W = B - after
        rows.append({
            "pair": orig,
            "scenario": meta[orig],
            "E": E, "K": K, "B": B, "W": W,
            "hits": len(W & E),
            "random_hits": exact_random_hits(B, W, E),
            "coverage": len(B & E),
        })
    return rows

def excess_for_indices(rows, idx):
    denom = sum(len(rows[i]["E"]) for i in idx)
    if not denom:
        return 0.0
    return (
        sum(rows[i]["hits"] for i in idx)
        - sum(rows[i]["random_hits"] for i in idx)
    ) / denom


def cluster_bootstrap(rows, seed=SEED):
    by = collections.defaultdict(list)
    for i, row in enumerate(rows):
        by[row["scenario"]].append(i)
    names = sorted(by)
    rng = random.Random(seed)
    draws = []
    for _ in range(N_BOOT):
        idx = []
        for _j in names:
            idx.extend(by[names[rng.randrange(len(names))]])
        draws.append(excess_for_indices(rows, idx))
    return q025(draws)


def summarize_rows(rows):
    E = sum(len(r["E"]) for r in rows)
    hits = sum(r["hits"] for r in rows)
    random_hits = sum(r["random_hits"] for r in rows)
    cover = sum(r["coverage"] for r in rows)
    ceiling_hits = sum(min(len(r["W"]), len(r["B"] & r["E"])) for r in rows)
    excess = (hits - random_hits) / E if E else 0.0
    ceiling = (ceiling_hits - random_hits) / E if E else 0.0
    return {
        "n": len(rows),
        "expected_withdrawals": E,
        "correct_withdrawals": hits,
        "withdrawal_recall": hits / E if E else 0.0,
        "exact_random_baseline": random_hits / E if E else 0.0,
        "excess": excess,
        "ci95_cluster_scenario": cluster_bootstrap(rows),
        "coverage": cover,
        "coverage_rate": cover / E if E else 0.0,
        "coverage_normalized_recall": hits / cover if cover else 0.0,
        "ceiling": ceiling,
        "fraction_of_ceiling": excess / ceiling if ceiling else None,
        "mean_requested": sum(len(r["B"]) for r in rows) / len(rows),
        "mean_withdrawn": sum(len(r["W"]) for r in rows) / len(rows),
        "distinct_request_sets": len({tuple(sorted(r["B"])) for r in rows}),
        "distinct_withdrawal_sets": len({tuple(sorted(r["W"])) for r in rows}),
    }

def _permuted_excess(rows, assigned_E):
    denom = sum(len(E) for E in assigned_E)
    hits = 0.0
    baseline = 0.0
    for row, E in zip(rows, assigned_E):
        hits += len(row["W"] & E)
        baseline += exact_random_hits(row["B"], row["W"], E)
    return (hits - baseline) / denom if denom else 0.0


def permutation_null(rows, *, within_scenario=False, seed=SEED + 1):
    observed = excess_for_indices(rows, range(len(rows)))
    original = [set(r["E"]) for r in rows]
    groups = [list(range(len(rows)))]
    if within_scenario:
        by = collections.defaultdict(list)
        for i, row in enumerate(rows):
            by[row["scenario"]].append(i)
        groups = list(by.values())
    rng = random.Random(seed)
    values = []
    for _ in range(N_PERM):
        assigned = list(original)
        for idx in groups:
            vals = [original[i] for i in idx]
            rng.shuffle(vals)
            for i, E in zip(idx, vals):
                assigned[i] = E
        values.append(_permuted_excess(rows, assigned))
    ge = sum(v >= observed - 1e-15 for v in values)
    le = sum(v <= observed + 1e-15 for v in values)
    return {
        "observed": observed,
        "null_mean": sum(values) / len(values),
        "null_range95": q025(values),
        "null_min": min(values),
        "null_max": max(values),
        "p_ge_observed_plus1": (ge + 1) / (len(values) + 1),
        "p_le_observed_plus1": (le + 1) / (len(values) + 1),
        "within_scenario": within_scenario,
        "permutations": len(values),
    }


def target_summary(rows):
    E_sets = [r["E"] for r in rows]
    modal, modal_n = modal_set(E_sets)
    total = sum(map(len, E_sets))
    covered = sum(len(modal & E) for E in E_sets)
    counts = collections.Counter(tuple(sorted(E)) for E in E_sets)
    probs = [n / len(E_sets) for n in counts.values()]
    entropy = -sum(p * math.log2(p) for p in probs)
    return {
        "distinct_release_sets": len(counts),
        "modal_release_set": sorted(modal),
        "modal_pair_count": modal_n,
        "modal_pair_share": modal_n / len(E_sets),
        "modal_core_withdrawal_coverage": covered,
        "total_expected_withdrawals": total,
        "modal_core_coverage_rate": covered / total if total else 0.0,
        "release_set_entropy_bits": entropy,
    }

def constant_oracle_rows(ref, meta, pairs):
    base_sets = [set(ref[o]["documents"]) for o, _ in pairs]
    release_sets = [set(ref[o]["documents"]) - set(ref[m]["documents"]) for o, m in pairs]
    B, _ = modal_set(base_sets)
    W, _ = modal_set(release_sets)
    W &= B
    rows = []
    for (orig, mod), E in zip(pairs, release_sets):
        rows.append({
            "pair": orig,
            "scenario": meta[orig],
            "E": E,
            "K": set(ref[mod]["documents"]),
            "B": set(B),
            "W": set(W),
            "hits": len(W & E),
            "random_hits": exact_random_hits(B, W, E),
            "coverage": len(B & E),
        })
    return rows


def paired_contrast(rows_a, rows_b, seed=SEED + 2):
    a = {r["pair"]: r for r in rows_a}
    b = {r["pair"]: r for r in rows_b}
    keys = sorted(set(a) & set(b))
    if not keys:
        raise ValueError("no paired rows")
    by = collections.defaultdict(list)
    for k in keys:
        by[a[k]["scenario"]].append(k)
    names = sorted(by)

    def score(table, sample):
        rows = [table[k] for k in sample]
        return excess_for_indices(rows, range(len(rows)))
    obs = score(a, keys) - score(b, keys)
    rng = random.Random(seed)
    draws = []
    for _ in range(N_BOOT):
        sample = []
        for _j in names:
            sample.extend(by[names[rng.randrange(len(names))]])
        draws.append(score(a, sample) - score(b, sample))
    return {"difference": obs, "ci95_cluster_scenario": q025(draws), "n": len(keys)}


def audit_dynamic(A, ref, meta, suffix, arms):
    pairs = paired_ids(A, ref, suffix)
    out = {"pairs": len(pairs), "scenarios": len({meta[o] for o, _ in pairs})}
    oracle_rows = constant_oracle_rows(ref, meta, pairs)
    out["target"] = target_summary(oracle_rows)
    out["constant_oracle"] = {
        **summarize_rows(oracle_rows),
        "global_permutation": permutation_null(oracle_rows),
        "within_scenario_permutation": permutation_null(oracle_rows, within_scenario=True),
    }
    best_rows = policy_rows(ref, meta, pairs)
    out["best_input_independent_oracle"] = summarize_rows(best_rows)
    cf_rows, cf_policies = crossfit_constant_rows(ref, meta, pairs)
    out["crossfit_input_independent_oracle"] = {
        **summarize_rows(cf_rows),
        "policy_count": len({(tuple(sorted(B)),tuple(sorted(W))) for B,W in cf_policies.values()}),
        "policies": {k:{"requested":sorted(B),"withdrawn":sorted(W)} for k,(B,W) in cf_policies.items()},
    }
    out["arms"] = {}
    all_rows = {}
    for arm in arms:
        rows = records_for_arm(A, ref, meta, pairs, arm)
        all_rows[arm] = rows
        out["arms"][arm] = {
            **summarize_rows(rows),
            "global_permutation": permutation_null(rows),
            "within_scenario_permutation": permutation_null(rows, within_scenario=True),
        }
    return out, all_rows


def best_constant_policy(ref, meta, pairs, train_pair_ids=None):
    """Best fixed withdrawal under the exact volume control.

    The request set is the modal pre-intervention reference checklist.  The
    withdrawal set is selected without reading any case: choose document types
    whose training frequency beats the random-drop contribution for that fixed B.
    """
    train = pairs if train_pair_ids is None else [p for p in pairs if p[0] in train_pair_ids]
    base_sets = [set(ref[o]["documents"]) for o, _ in train]
    B, _ = modal_set(base_sets)
    E_train = [set(ref[o]["documents"]) - set(ref[m]["documents"]) for o, m in train]
    total_intersection = sum(len(B & E) for E in E_train)
    per_slot = total_intersection / len(B) if B else 0.0
    freq = collections.Counter(d for E in E_train for d in E if d in B)
    W = {d for d in B if freq[d] > per_slot}
    return B, W


def policy_rows(ref, meta, pairs, policy_by_scenario=None):
    rows=[]
    for orig, mod in pairs:
        B, W = policy_by_scenario[meta[orig]] if policy_by_scenario else best_constant_policy(ref, meta, pairs)
        E=set(ref[orig]["documents"])-set(ref[mod]["documents"])
        rows.append({"pair":orig,"scenario":meta[orig],"E":E,"K":set(ref[mod]["documents"]),
                     "B":set(B),"W":set(W),"hits":len(W&E),
                     "random_hits":exact_random_hits(B,W,E),"coverage":len(B&E)})
    return rows


def crossfit_constant_rows(ref, meta, pairs):
    scenarios=sorted({meta[o] for o,_ in pairs})
    policies={}
    for held in scenarios:
        train_ids={o for o,_ in pairs if meta[o]!=held}
        policies[held]=best_constant_policy(ref,meta,pairs,train_ids)
    return policy_rows(ref,meta,pairs,policies), policies

def audit_dynamic_subset(A, ref, meta, suffix, arms, exclude_scenarios):
    pairs=[p for p in paired_ids(A,ref,suffix) if meta[p[0]] not in set(exclude_scenarios)]
    oracle=constant_oracle_rows(ref,meta,pairs)
    cf,pol=crossfit_constant_rows(ref,meta,pairs)
    out={"pairs":len(pairs),"scenarios":sorted({meta[o] for o,_ in pairs}),
         "target":target_summary(oracle),
         "constant_oracle":summarize_rows(oracle),
         "crossfit_input_independent_oracle":{**summarize_rows(cf),
             "policy_count":len({(tuple(sorted(B)),tuple(sorted(W))) for B,W in pol.values()}),
             "policies":{k:{"requested":sorted(B),"withdrawn":sorted(W)} for k,(B,W) in pol.items()}},
         "arms":{}}
    for arm in arms:
        rows=records_for_arm(A,ref,meta,pairs,arm)
        out["arms"][arm]={**summarize_rows(rows),
            "global_permutation":permutation_null(rows),
            "within_scenario_permutation":permutation_null(rows,within_scenario=True)}
    return out



def set_micro_f1(rows):
    """Symmetric release-set score: rows are (predicted withdrawal, gold release)."""
    tp=sum(len(p & g) for p,g in rows)
    pred=sum(len(p) for p,g in rows)
    gold=sum(len(g) for p,g in rows)
    micro=(2*tp/(pred+gold)) if pred+gold else 1.0
    macro=sum((2*len(p&g)/(len(p)+len(g)) if len(p)+len(g) else 1.0) for p,g in rows)/len(rows)
    exact=sum(p==g for p,g in rows)/len(rows)
    return {"micro_f1":micro,"macro_f1":macro,"exact_set_accuracy":exact,
            "true_positive_documents":tp,"predicted_documents":pred,"gold_documents":gold}


def best_constant_release(train_gold, universe):
    """Exact best fixed release set for micro-F1 on training units."""
    n=len(train_gold); total_gold=sum(map(len,train_gold))
    freq=collections.Counter(d for g in train_gold for d in g)
    ranked=sorted(universe,key=lambda d:(-freq[d],d))
    best_score=(1.0 if total_gold==0 else 0.0); best=set(); tp=0
    for k,d in enumerate(ranked,1):
        tp += freq[d]
        score=2*tp/(n*k+total_gold) if n*k+total_gold else 1.0
        if score > best_score + 1e-15:
            best_score=score; best=set(ranked[:k])
    return best_score,best


def release_prediction_audit(A, ref, meta, suffix, arms):
    pairs=paired_ids(A,ref,suffix)
    scenarios=sorted({meta[o] for o,_ in pairs})
    universe=set().union(*(set(ref[o]["documents"]) | set(ref[m]["documents"]) for o,m in pairs))
    # Train a fixed release set on all other scenarios; never read the held-out case.
    policies={}; constant_rows=[]; fold_scores={}
    for held in scenarios:
        train=[set(ref[o]["documents"])-set(ref[m]["documents"]) for o,m in pairs if meta[o]!=held]
        _,W=best_constant_release(train,universe); policies[held]=W
        fold=[]
        for o,m in pairs:
            if meta[o]==held:
                g=set(ref[o]["documents"])-set(ref[m]["documents"])
                constant_rows.append((set(W),g)); fold.append((set(W),g))
        fold_scores[held]=set_micro_f1(fold)
    out={"crossfit_constant":{**set_micro_f1(constant_rows),
                               "policy_count":len({tuple(sorted(v)) for v in policies.values()}),
                               "policies":{k:sorted(v) for k,v in policies.items()},
                               "fold_metrics":fold_scores},"arms":{}}
    for arm in arms:
        rows=[]
        for o,m in pairs:
            b=set(A[o]["arms"][arm].get("documents") or [])-HELD
            af=set(A[m]["arms"][arm].get("documents") or [])-HELD
            rows.append((b-af,set(ref[o]["documents"])-set(ref[m]["documents"])))
        out["arms"][arm]=set_micro_f1(rows)
    return out

def main():
    rent = contract("rent_increase.json")
    term = contract("termination.gated.json")
    rent_ref, rent_meta = make_reference("conf_ref_raw.json", rent)
    term_ref, term_meta = make_reference("term_ref_raw.json", term)

    result = {
        "contract": "casepath.evaluation-validity/1.0.0",
        "analysis_seed": SEED,
        "bootstrap_draws": N_BOOT,
        "permutation_draws": N_PERM,
        "reference_adjudication": {
            "rent_increase_model": "openai/gpt-5.6-terra",
            "votes_per_unit": 3,
            "temperature": 0.0,
            "independent_model_families": 1,
        },
        "static": {
            "rent_increase": static_summary("conf_cases.json", rent_ref),
            "termination": static_summary("term_units.json", term_ref),
        },
        "document_layer_capacity": {
            "definition": "distinct document unions over every open/closed decision mask; not a legal reachability claim",
            "rent_increase": document_layer_capacity(rent),
            "termination": document_layer_capacity(term),
        },
    }
    model_files = {
        "gpt-5.6-terra": "conf_arms.json",
        "claude-haiku-4.5": "mm_haiku.json",
        "gemini-2.5-flash": "mm_gemini.json",
        "deepseek-v3.2": "mm_deepseek.json",
    }
    result["rent_dynamic"] = {"models": {}}
    b5_rows = {}
    for model, filename in model_files.items():
        A = {r["unit_id"]: r for r in load(filename)}
        arms = ["b1_direct", "b5_induced_graph"]
        if model == "gpt-5.6-terra":
            arms.insert(1, "b3_graph_then_list")
        audit, rows = audit_dynamic(A, rent_ref, rent_meta, "__e07", arms)
        result["rent_dynamic"]["models"][model] = audit
        b5_rows[model] = rows["b5_induced_graph"]

    first_model = result["rent_dynamic"]["models"]["gpt-5.6-terra"]
    result["rent_dynamic"]["target"] = first_model["target"]
    result["rent_dynamic"]["constant_oracle"] = first_model["constant_oracle"]
    result["rent_dynamic"]["best_input_independent_oracle"] = first_model["best_input_independent_oracle"]
    result["rent_dynamic"]["crossfit_input_independent_oracle"] = first_model["crossfit_input_independent_oracle"]
    rent_gpt_A={r["unit_id"]:r for r in load("conf_arms.json")}
    result["rent_dynamic"]["release_set_prediction"] = release_prediction_audit(
        rent_gpt_A,rent_ref,rent_meta,"__e07",["b1_direct","b3_graph_then_list","b5_induced_graph"])
    contrasts = {}
    models = list(model_files)
    for i, left in enumerate(models):
        for right in models[i + 1:]:
            contrasts[f"{left} minus {right}"] = paired_contrast(
                b5_rows[left], b5_rows[right], seed=SEED + 10 + i
            )
    result["rent_dynamic"]["b5_cross_model_contrasts"] = contrasts
    gpt_A={r["unit_id"]:r for r in load("conf_arms.json")}
    result["rent_dynamic"]["sensitivity_excluding_truncated_S8"] = audit_dynamic_subset(
        gpt_A,rent_ref,rent_meta,"__e07",
        ["b1_direct","b3_graph_then_list","b5_induced_graph"],
        ["S8_nebenkosten_reclass"]
    )

    term_A = {r["unit_id"]: r for r in load("term_arms.json")}
    term_audit, _ = audit_dynamic(
        term_A,
        term_ref,
        term_meta,
        "__e05",
        ["b1_direct", "b3_graph_then_list", "b5_induced_graph"],
    )
    result["termination_dynamic"] = term_audit
    result["termination_dynamic"]["release_set_prediction"] = release_prediction_audit(
        term_A,term_ref,term_meta,"__e05",["b1_direct","b3_graph_then_list","b5_induced_graph"])

    out = ART / "EVALUATION_VALIDITY.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "static": result["static"],
        "capacity": result["document_layer_capacity"],
        "rent_target": result["rent_dynamic"]["target"],
        "rent_oracle": result["rent_dynamic"]["constant_oracle"],
        "rent_models": {
            m: a["arms"]["b5_induced_graph"]
            for m, a in result["rent_dynamic"]["models"].items()
        },
        "termination_target": result["termination_dynamic"]["target"],
        "termination_oracle": result["termination_dynamic"]["constant_oracle"],
        "output": str(out.relative_to(REPO)),
    }, indent=2))


if __name__ == "__main__":
    main()
