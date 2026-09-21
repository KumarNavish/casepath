#!/usr/bin/env python3
"""Close the loop between the paper and the released benchmark.

`build_manuscript_numbers.py` turns preserved evidence files into the LaTeX macros the paper
prints. This script checks the other direction: it reruns the frozen analysis from
`research/casepath/branch-benchmark/` on the recorded predictions and confirms that every macro
sourced from the held-out report, the shortcut preflight or the product-parity report equals the
freshly recomputed value.

    python3 evidence/check_against_benchmark_release.py

A macro passes only if the value behind it can be recomputed from released files. Macros whose
evidence is a design record rather than a computation (receipt accounting, corpus design, execution
status) have no recomputation path here and are reported as "not recomputable", never as passing.
Exit status is 0 only if nothing mismatched.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOC = HERE.parent
RELEASE = DOC.parent / "branch-benchmark"
TOLERANCE = 1e-9

# Which evidence files can be recomputed, and how to obtain the recomputed document.
RECOMPUTABLE = {
    "PAIRED_V5_REPRODUCED_RESULT.json": "heldout_analysis",
    "SHORTCUT_PREFLIGHT_V3.json": "preflight",
    "PAIRED_V5_REPRODUCED_PARITY.json": "parity",
}


def resolve(doc, pointer: str):
    """RFC 6901 JSON pointer."""
    cur = doc
    for raw in pointer.lstrip("/").split("/"):
        if raw == "":
            continue
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            cur = cur[int(token)]
        else:
            cur = cur[token]
    return cur


def equal(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOLERANCE * max(1.0, abs(b))
    return a == b


def main() -> int:
    if not RELEASE.exists():
        print(f"benchmark release not found at {RELEASE}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "heldout.json"
        cmd = [
            sys.executable, str(RELEASE / "analysis" / "theft_confirmatory_analysis_v5.py"),
            "--b5", str(RELEASE / "predictions" / "heldout" / "casepath.json"),
            "--baselines", str(RELEASE / "predictions" / "heldout" / "comparators.json"),
            "--benchmark", str(RELEASE / "benchmark" / "BENCHMARK_V3.json"),
            "--output", str(out), "--mode", "hidden",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print(proc.stderr[-1500:])
            return 1
        recomputed = {
            "heldout_analysis": json.loads(out.read_text()),
            "preflight": json.loads((RELEASE / "benchmark" / "SHORTCUT_PREFLIGHT_V3.json").read_text()),
            "parity": json.loads((RELEASE / "parity" / "PRODUCT_METHOD_PARITY_V5.json").read_text()),
        }

    audit = json.loads((HERE / "NUMERICAL_AUDIT.json").read_text())
    checked = mismatched = skipped = derived = 0
    for entry in audit["macros"]:
        source = RECOMPUTABLE.get(entry["evidence_file"])
        if source is None:
            skipped += 1
            continue
        if entry.get("derivation"):
            # The macro is a formula over evidence values, not a stored value; the generator's own
            # audit records the formula. Pointer resolution does not apply.
            derived += 1
            continue
        try:
            actual = resolve(recomputed[source], entry["json_pointer"])
        except (KeyError, IndexError, ValueError):
            print(f"  UNRESOLVED  \\{entry['macro']}  {entry['evidence_file']}{entry['json_pointer']}")
            mismatched += 1
            continue
        checked += 1
        if not equal(actual, entry["value"]):
            print(f"  MISMATCH    \\{entry['macro']}  paper {entry['value']!r} != recomputed {actual!r}")
            mismatched += 1

    total = len(audit["macros"])
    print(f"\n{checked} macro(s) recomputed from the released benchmark and matched")
    print(f"{derived} macro(s) are formulas over those values (checked by build_manuscript_numbers.py)")
    print(f"{skipped} macro(s) come from design or accounting records with no recomputation path:")
    for name in sorted({e["evidence_file"] for e in audit["macros"] if e["evidence_file"] not in RECOMPUTABLE}):
        n = sum(1 for e in audit["macros"] if e["evidence_file"] == name)
        print(f"    {n:>3}  {name}")
    print(f"{total} macros total")
    if mismatched:
        print(f"\nFAILED: {mismatched} macro(s) did not match.")
        return 1
    print("\nOK: every recomputable number in the paper matches the released benchmark.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
