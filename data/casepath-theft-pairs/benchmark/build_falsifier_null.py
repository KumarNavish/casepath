#!/usr/bin/env python3
"""Re-derive the full wrong-pairing null distribution so the figure can show it.

    python3 branch-benchmark/build_falsifier_null.py

The preserved held-out report keeps only the null's summary (mean, min, max, 95% interval,
p-value). Plotting the falsifier honestly needs the 5,008 values themselves. This replays the
frozen analysis module's own `wrong_pairing` construction, with its seed, its draw count and its
`pairing_score`, then asserts that every preserved summary statistic comes back identical. No new
inference, no scoring change, no preserved file rewritten.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "analysis"))
import theft_confirmatory_analysis_v5 as v5  # noqa: E402

OUT = HERE.parent / "iclr2027-integrated" / "evidence" / "WRONG_PAIRING_NULL.json"
REPORT = HERE.parent / "iclr2027-integrated" / "evidence" / "PAIRED_V5_REPRODUCED_RESULT.json"


def main() -> None:
    pairs = v5.load_pairs(HERE / "benchmark" / "BENCHMARK_V3.json")
    rows = v5.load_rows(HERE / "predictions" / "heldout" / "casepath.json",
                        HERE / "predictions" / "heldout" / "comparators.json")
    b5 = sorted((r for r in rows if r["arm"] == v5.B5), key=lambda r: str(r["pair_id"]))

    rows_by_family: dict[str, list] = defaultdict(list)
    targets_by_family: dict[str, list] = defaultdict(list)
    for row in b5:
        pair = pairs[str(row["pair_id"])]
        rows_by_family[str(pair["scenario"])].append(row)
        targets_by_family[str(pair["scenario"])].append(pair)
    families = sorted(rows_by_family)
    for family in families:
        rows_by_family[family].sort(key=lambda r: int(pairs[str(r["pair_id"])]["context_index"]))
        targets_by_family[family].sort(key=lambda p: int(p["context_index"]))
    prediction_rows = [row for f in families for row in rows_by_family[f]]

    def mapped(permutation) -> float:
        return v5.pairing_score(prediction_rows,
                                [p for i in permutation for p in targets_by_family[families[i]]])

    count = len(families)
    observed = mapped(range(count))
    cyclic = [mapped(tuple((i + s) % count for i in range(count))) for s in range(1, count)]
    rng = random.Random(v5.SEED)
    indices = list(range(count))
    draws: list[float] = []
    while len(draws) < v5.PAIRING_DRAWS:
        candidate = indices[:]
        rng.shuffle(candidate)
        if any(i == candidate[i] for i in indices):
            continue
        draws.append(mapped(candidate))
    null = cyclic + draws

    preserved = json.loads(REPORT.read_text())["wrong_pairing"]
    got = {"observed_micro_f1": observed,
           "null_mean": math.fsum(null) / len(null),
           "null_min": min(null),
           "null_max": max(null),
           "null_95": [v5.percentile(null, 0.025), v5.percentile(null, 0.975)],
           "p_ge_plus1": (1 + sum(v >= observed - 1e-15 for v in null)) / (1 + len(null))}
    for key, value in got.items():
        # The mean is compared with a tolerance, and only the mean: the preserved report was
        # written under a Python whose builtin sum() compensates float error (3.12+), so a plain
        # left fold here differs in the last two bits. Every other statistic must match exactly.
        ok = (math.isclose(preserved[key], value, rel_tol=1e-12) if key == "null_mean"
              else preserved[key] == value)
        if not ok:
            raise SystemExit(f"{key}: replayed {value!r} != preserved {preserved[key]!r}")
    if preserved["cyclic_shifts"] != cyclic:
        raise SystemExit("cyclic shifts differ from the preserved report")

    OUT.write_text(json.dumps({
        "schema": "casepath.wrong-pairing-null/1",
        "derivation": "Replay of theft_confirmatory_analysis_v5.wrong_pairing on the preserved "
                      "held-out predictions; every summary statistic verified identical to "
                      "PAIRED_V5_REPRODUCED_RESULT.json before writing.",
        "source_report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
        "seed": v5.SEED,
        "families": families,
        "derangement_draws": v5.PAIRING_DRAWS,
        "cyclic_shifts": cyclic,
        "null": null,
        **got,
    }, indent=2, sort_keys=True) + "\n")
    print(f"{OUT.name}: {len(null)} reassignments, observed {observed:.3f}, "
          f"null max {max(null):.3f}; all preserved statistics matched")


if __name__ == "__main__":
    main()
