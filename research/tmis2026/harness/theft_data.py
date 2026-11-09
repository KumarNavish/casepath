"""Theft cases (Study A data) plus new unresolved-fact variants.

Each story has one 'off' case (all nine conditions false), nine 'on' cases
(one condition true) and six 'unresolved' cases (one condition left open).
Unresolved variants exist for the six conditions whose documents are
downstream requirements, so requesting them before the fact is settled is
premature. They are authored here, deterministically, without model calls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data" / "casepath-theft-pairs"
BENCH = DATA / "benchmark" / "benchmark"
sys.path.insert(0, str(DATA / "benchmark" / "analysis"))
from theft_confirmatory_analysis_v5 import best_realization  # noqa: E402  (frozen scorer)

UNRESOLVED = {
    "PR_scheduled_valuable_1000": "A stolen watch may be separately scheduled in the policy, but the policyholder has not yet found the policy schedule to confirm this.",
    "PR_bicycle_claimed": "The policyholder is not yet sure whether a bicycle kept in the cellar was also taken.",
    "PR_sim_card_stolen": "It is not yet known whether a SIM card was among the stolen items or whether any loss from SIM-card misuse will be claimed.",
    "PR_third_party_causer": "The policyholder suspects that a building contractor may have left the entrance insecure, but whether an identifiable third party caused or enlarged the loss has not been established.",
    "PR_expert_procedure_requested": "The policyholder is considering asking for the formal expert determination procedure but has not decided.",
    "PR_repair_over_500": "A damaged insured item may need repair; whether a repair will be made and what it would cost has not yet been assessed.",
}


def benchmark() -> dict:
    return json.loads((BENCH / "BENCHMARK_V3.json").read_text())


def catalogue() -> list[str]:
    return [d["document_type"] for d in json.loads((BENCH / "FULL_CATALOGUE.json").read_text())["documents"]]


def doc_ids() -> dict[str, str]:
    return {doc: f"D{i:02d}" for i, doc in enumerate(catalogue(), 1)}


def passages() -> list[dict]:
    return json.loads((BENCH / "SOURCE_SNAPSHOT_V2.json").read_text())["passages"]


def prepared() -> dict:
    return json.loads((DATA / "representation" / "PREPARED.json").read_text())


def texts() -> dict[str, dict]:
    """All case texts keyed by text id: s{story}-off, s{story}-on-{cond}, s{story}-unres-{cond}."""
    b = benchmark()
    out = {}
    units = {u["unit_id"]: u for u in b["units"]}
    for pair in b["pairs"]:
        s, cond = pair["context_index"], pair["scenario"]
        off, on = units[pair["false_unit_id"]], units[pair["true_unit_id"]]
        out[f"s{s}-off"] = {"story": s, "kind": "off", "condition": None, "text": off["customer_message"]}
        out[f"s{s}-on-{cond}"] = {"story": s, "kind": "on", "condition": cond, "text": on["customer_message"]}
        if cond in UNRESOLVED:
            text = off["customer_message"].replace(pair["changed_statement_false"], UNRESOLVED[cond])
            assert text != off["customer_message"], cond
            out[f"s{s}-unres-{cond}"] = {"story": s, "kind": "unresolved", "condition": cond, "text": text}
    return out


def pairs() -> list[dict]:
    """Scored pairs: off->on (reference changes) and off->unresolved (no change; documents held)."""
    rows = []
    for pair in benchmark()["pairs"]:
        s, cond = pair["context_index"], pair["scenario"]
        split = "dev" if s == 0 else "heldout"
        rows.append({"pair_id": f"s{s}-on-{cond}", "kind": "on", "story": s, "condition": cond, "split": split,
                     "off": f"s{s}-off", "variant": f"s{s}-on-{cond}", "reference": pair})
        if cond in UNRESOLVED:
            rows.append({"pair_id": f"s{s}-unres-{cond}", "kind": "unresolved", "story": s, "condition": cond,
                         "split": split, "off": f"s{s}-off", "variant": f"s{s}-unres-{cond}", "reference": pair})
    return rows
