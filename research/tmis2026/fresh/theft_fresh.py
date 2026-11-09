"""Fresh theft stories (Study 2): same interface as harness/theft_data.py.

Four new stories (context indices 4-7) built by fresh/theft/build_theft.py with the released
construction scripts; references from the frozen source contract (BENCHMARK_V3 format). The
sources, catalogue, prepared representation, open-condition sentences and frozen scorer are
those of Study 1, imported unchanged. Every fresh pair is held out (split 'heldout').
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "harness"))
import theft_data as _base  # noqa: E402
from theft_data import (DATA, BENCH, UNRESOLVED, best_realization, catalogue, doc_ids,  # noqa: E402,F401
                        passages, prepared)

FRESH = HERE / "theft" / "BENCHMARK_FRESH.json"


def benchmark() -> dict:
    return json.loads(FRESH.read_text())


def texts() -> dict[str, dict]:
    """All fresh case texts keyed by text id: s{story}-off, s{story}-on-{cond}, s{story}-unres-{cond}."""
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
    """Scored fresh pairs: off->on (reference changes) and off->unresolved (no change; documents held)."""
    rows = []
    for pair in benchmark()["pairs"]:
        s, cond = pair["context_index"], pair["scenario"]
        rows.append({"pair_id": f"s{s}-on-{cond}", "kind": "on", "story": s, "condition": cond, "split": "heldout",
                     "off": f"s{s}-off", "variant": f"s{s}-on-{cond}", "reference": pair})
        if cond in UNRESOLVED:
            rows.append({"pair_id": f"s{s}-unres-{cond}", "kind": "unresolved", "story": s, "condition": cond,
                         "split": "heldout", "off": f"s{s}-off", "variant": f"s{s}-unres-{cond}", "reference": pair})
    return rows
