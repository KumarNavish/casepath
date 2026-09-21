#!/usr/bin/env python3
"""Build evidence/studyB_execution_status.json from the recorded Study B cells.

    python3 evidence/build_execution_snapshot.py

Study B's execution record is target-free: it reports only how each scheduled cell ended, never a
score, so it is reportable before the prediction freezes are scored. `build_manuscript_numbers.py`
reads this file to produce the execution table and its macros.

Each failed cell is assigned exactly one class by matching its full retained error text against the
rules below, first match winning. The rules are written against the messages the producer actually
emits; any cell that matches none is counted as `other_validation` and listed in the output, so a
new failure mode shows up instead of being absorbed silently.
"""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MATRIX = Path("/Users/kumar0002/.local/state/navish-acceptance-20260919/PRO_NATIVE150_MATRIX.jsonl")
CELLS_ROOT = Path("/Users/kumar0002/.local/state/navish-acceptance-20260919/mac-native150")

# (class, substrings) - matched case-insensitively against the whole error text, in order.
RULES = [
    ("unknown_relation_endpoint", ("unknown endpoint",)),
    ("invalid_codebook_index", ("codebook",)),
    ("truncated_or_nonterminal", ("truncated or nonterminal", "charged transport failure")),
    ("contradictory_presence_state", ("contradictory document presence",
                                      "contradicts upstream document-state")),
    ("review_envelope", ("review notes required", "incomplete assessment")),
    ("document_outside_route", ("document outside assessed route",)),
]

ARMS = ["CASEPATH_CONTROL", "DIRECT_REVIEWED", "DOCUMENT_FIRST_REVIEWED",
        "PROCESS_CONTEXT_REVIEWED", "RULE_FIRST_REVIEWED",
        "COMPILED_EQUIVALENT", "LOCAL_SCOPE_ABLATION"]


def classify(error: str) -> str:
    text = (error or "").lower()
    for name, needles in RULES:
        if any(n in text for n in needles):
            return name
    return "other_validation"


def main() -> None:
    plan = [json.loads(line) for line in MATRIX.open()]
    meta = {r["case_id"]: r for r in plan}
    cells_dir = max(CELLS_ROOT.glob("*/work/output/cells"),
                    key=lambda d: len(list(d.glob("*.json"))))

    states = collections.defaultdict(collections.Counter)
    fails = collections.defaultdict(collections.Counter)
    unmatched = collections.Counter()
    digest = hashlib.sha256()
    seen = set()
    n = 0
    for path in sorted(cells_dir.glob("*.json")):
        cell = json.loads(path.read_text())
        digest.update(path.read_bytes())
        n += 1
        key = (cell["case_id"], cell["arm"])
        if key in seen:
            raise SystemExit(f"duplicate cell for {key}")
        seen.add(key)
        info = meta.get(cell["case_id"])
        if info is None:
            raise SystemExit(f"cell {cell['case_id']} is not in the scheduled plan")
        split = info["split"]
        states[(split, cell["arm"])][cell["state"]] += 1
        if cell["state"] == "failed":
            cls = classify(cell.get("error"))
            fails[(split, cell["arm"])][cls] += 1
            if cls == "other_validation":
                first = (cell.get("error") or "").strip().splitlines()
                unmatched[first[0][:100] if first else "(empty)"] += 1

    domains = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in plan:
        domains[r["split"]][r["domain"]].add(r["family_id"])

    out = {
        "schema": "casepath.studyb-execution-status/2.0.0",
        "generated_by": "evidence/build_execution_snapshot.py",
        "scope": "Execution status only. No score, target or model output is read; this file is "
                 "reportable before the prediction freezes are scored. Failed cells enter the "
                 "final report with adverse unit penalties.",
        "cells_dir": str(cells_dir),
        "snapshot_cells": n,
        "scheduled_cells": len(plan),
        "cells_sha256_concat": digest.hexdigest(),
        "domain_family_counts": {s: {d: len(f) for d, f in sorted(ds.items())}
                                 for s, ds in sorted(domains.items())},
        "by_split_arm": {f"{s}|{a}": dict(c) for (s, a), c in sorted(states.items())},
        "failure_taxonomy_by_split_arm": {f"{s}|{a}": dict(c) for (s, a), c in sorted(fails.items())},
        "classification_rules": {name: list(needles) for name, needles in RULES},
        "unmatched_error_first_lines": dict(unmatched),
    }
    path = HERE / "studyB_execution_status.json"
    path.write_text(json.dumps(out, indent=1) + "\n")

    total = sum(sum(c.values()) for c in states.values())
    print(f"{n} cells from {cells_dir.parent.parent.parent.name} "
          f"({total} placed, {len(plan)} scheduled)")
    for split in ("public_dev", "hidden_test"):
        done = sum(sum(c.values()) for (s, _), c in states.items() if s == split)
        print(f"  {split}: {done} cells")
    grand = collections.Counter()
    for c in states.values():
        grand.update(c)
    print(f"  states: {dict(grand)}")
    classes = collections.Counter()
    for c in fails.values():
        classes.update(c)
    print(f"  failure classes: {dict(classes)}")
    if unmatched:
        print("  unmatched error lines counted as other_validation:")
        for line, count in unmatched.most_common():
            print(f"    {count:4}  {line}")


if __name__ == "__main__":
    main()
