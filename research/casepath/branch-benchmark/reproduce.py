#!/usr/bin/env python3
"""Reproduce every Study A number in the CasePath paper, offline.

    python3 reproduce.py            # verify hashes, rerun the frozen analysis, diff against the
                                    # preserved held-out result, print the paper's tables

No network, no API key and no provider account are needed: the recorded predictions of all four
arms are in predictions/, and the frozen analysis code in analysis/ recomputes the scores from
them. Nothing here regenerates model outputs; that would require provider access and is not
deterministic. Exit status is 0 only if every hash matches and every recomputed value reproduces the
preserved one to within TOLERANCE (see below).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANALYSIS = HERE / "analysis" / "theft_confirmatory_analysis_v5.py"
BENCHMARK = HERE / "benchmark" / "BENCHMARK_V3.json"
EXPECTED = HERE / "expected" / "HELDOUT_RESULT.json"

ARMS = [
    ("b5_process_compiled", "CasePath"),
    ("b1_direct", "Direct"),
    ("b3_representation_then_list", "Graph as context"),
    ("b6_evidence_first", "Evidence-first"),
]
GATES = [
    ("margin_at_least_0_10_against_all", "F1 margin >= 0.10 vs every comparator"),
    ("holm_p_at_most_0_05_against_all", "Holm-adjusted family-swap p <= 0.05 vs every comparator"),
    ("delta_precision_at_least_0_70", "signed-change precision >= 0.70"),
    ("predicted_gold_ratio_in_range", "predicted/reference change ratio in [0.75, 1.50]"),
    ("predicted_chain_attribution_at_least_0_90", "changes attributed to a changed guard >= 0.90"),
    ("gold_chain_coverage_at_least_0_80", "reference changes reachable through a source chain >= 0.80"),
    ("correct_pairing_above_null_97_5", "correct pairing above the wrong-pairing 97.5th percentile"),
    ("no_orphan_insertion_path", "no requested document without a source chain"),
]


def check_manifest() -> int:
    manifest = json.loads((HERE / "MANIFEST.json").read_text())
    bad = 0
    for entry in manifest["files"]:
        path = HERE / entry["path"]
        if not path.exists():
            print(f"  MISSING  {entry['path']}")
            bad += 1
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            print(f"  CHANGED  {entry['path']}")
            print(f"           manifest {entry['sha256']}")
            print(f"           on disk  {digest}")
            bad += 1
    print(f"  {len(manifest['files']) - bad}/{len(manifest['files'])} files match the manifest")
    return bad


def run_analysis(mode: str, split_dir: str, out: Path) -> dict:
    cmd = [
        sys.executable, str(ANALYSIS),
        "--b5", str(HERE / "predictions" / split_dir / "casepath.json"),
        "--baselines", str(HERE / "predictions" / split_dir / "comparators.json"),
        "--benchmark", str(BENCHMARK),
        "--output", str(out),
        "--mode", mode,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout[-2000:])
        print(proc.stderr[-2000:])
        raise SystemExit(f"analysis failed for {mode} split")
    return json.loads(out.read_text())


# Floating-point summation order differs between Python builds, so numeric values are compared to
# within TOLERANCE rather than bit-for-bit. Every quantity the paper reports is given to three
# decimals, which is nine orders of magnitude above this threshold. Counts, booleans and strings
# are compared exactly.
TOLERANCE = 1e-9


def diff(recomputed, preserved, path: str = "", drift: list | None = None) -> list[str]:
    """Deep comparison. Returns the list of substantive differences; appends float deviations
    within TOLERANCE to `drift` instead of reporting them as differences."""
    if isinstance(preserved, dict):
        if not isinstance(recomputed, dict):
            return [f"{path}: type {type(recomputed).__name__} != dict"]
        out = []
        for key in sorted(set(preserved) | set(recomputed)):
            if key not in recomputed:
                out.append(f"{path}/{key}: missing from the rerun")
            elif key not in preserved:
                out.append(f"{path}/{key}: absent from the preserved result")
            else:
                out += diff(recomputed[key], preserved[key], f"{path}/{key}", drift)
        return out
    if isinstance(preserved, list):
        if not isinstance(recomputed, list) or len(recomputed) != len(preserved):
            return [f"{path}: list length {len(recomputed) if isinstance(recomputed, list) else '?'} != {len(preserved)}"]
        out = []
        for i, (a, b) in enumerate(zip(recomputed, preserved)):
            out += diff(a, b, f"{path}[{i}]", drift)
        return out
    if isinstance(preserved, float) and isinstance(recomputed, (int, float)) and not isinstance(recomputed, bool):
        delta = abs(recomputed - preserved)
        if delta == 0:
            return []
        if delta <= TOLERANCE * max(1.0, abs(preserved)):
            if drift is not None:
                drift.append((delta, path))
            return []
        return [f"{path}: {recomputed!r} != {preserved!r}"]
    return [] if recomputed == preserved else [f"{path}: {recomputed!r} != {preserved!r}"]


def table(result: dict) -> None:
    scores = result["scores"]
    gold = scores["b5_process_compiled"]["gold_atoms"]
    print(f"  {'Method':<18}{'Prec':>7}{'Recall':>8}{'F1':>8}{'Exact':>8}{'Pred':>6}{'Spur':>6}{'Miss':>6}")
    for key, label in ARMS:
        s = scores[key]
        print(f"  {label:<18}{s['precision']:>7.3f}{s['recall']:>8.3f}{s['micro_f1']:>8.3f}"
              f"{s['exact_rate']:>8.3f}{s['predicted_atoms']:>6}{s['spurious_atoms']:>6}{s['missed_atoms']:>6}")
    print(f"  reference changes: {gold}   pairs: {scores['b5_process_compiled']['pairs']}")

    wp = result["wrong_pairing"]
    print(f"\n  wrong-family pairing: correct {wp['observed_micro_f1']:.3f} vs null max {wp['null_max']:.3f} "
          f"(mean {wp['null_mean']:.4f}, {wp['random_draws'] + len(wp['cyclic_shifts'])} reassignments, "
          f"add-one p = {wp['p_ge_plus1']:.2e})")
    chain = result["chain_metrics"]
    print(f"  source chains: {chain['attributed_predicted_atoms']}/{chain['predicted_atoms']} predicted changes attributed; "
          f"{chain['covered_gold_atoms']}/{chain['gold_atoms']} reference changes reachable "
          f"({100 * chain['gold_chain_coverage']:.1f}%)")

    print("\n  preregistered gate:")
    for key, label in GATES:
        print(f"    {'PASS' if result['positive_claim_gates'][key] else 'FAIL'}  {label}")
    print(f"    -> gate_pass = {result['gate_pass']}, claim_status = {result['claim_status']}")


def main() -> int:
    print("CasePath branch-intervention benchmark - offline reproduction\n")
    print("1. File integrity")
    bad = check_manifest()

    preflight = json.loads((HERE / "benchmark" / "SHORTCUT_PREFLIGHT_V3.json").read_text())
    print("\n2. Benchmark admission controls (computed before any system was run)")
    print(f"  input-free leave-one-family-out predictor: max held-out micro-F1 "
          f"{preflight['max_held_out_no_input_micro_f1']:.1f} over {preflight['scenarios']} families")
    print(f"  distinct target signatures: {preflight['distinct_acceptable_target_signatures']}/{preflight['scenarios']} "
          f"({preflight['target_signature_entropy_bits']:.2f} bits over {len(preflight['signed_document_universe'])} signed atoms)")
    print(f"  pairs: {preflight['pairs']}   case units: {preflight['units']}")
    if not preflight["admission"]["input_free_control_pass"] or not preflight["admission"]["target_diversity_pass"]:
        print("  ADMISSION FAILED"); bad += 1

    with tempfile.TemporaryDirectory() as tmp:
        print("\n3. Held-out split: rerunning the frozen analysis")
        recomputed = run_analysis("hidden", "heldout", Path(tmp) / "heldout.json")
        preserved = json.loads(EXPECTED.read_text())
        drift: list = []
        differences = diff(recomputed, preserved, drift=drift)
        if differences:
            print(f"  {len(differences)} value(s) differ from the preserved result:")
            for line in differences[:20]:
                print(f"    {line}")
            bad += len(differences)
        else:
            exact = "exactly" if not drift else f"to within {TOLERANCE:g}"
            print(f"  every value reproduces the preserved held-out result {exact}")
            if drift:
                worst, where = max(drift)
                print(f"  {len(drift)} value(s) differ only by floating-point summation order; "
                      f"largest deviation {worst:.2e} at {where}")
        print()
        table(recomputed)

        print("\n4. Development split (informational; the paper reports the held-out read)")
        dev = run_analysis("development", "development", Path(tmp) / "development.json")
        dev_scores = dev["scores"]
        for key, label in ARMS:
            s = dev_scores[key]
            print(f"  {label:<18} F1 {s['micro_f1']:.3f}   spurious {s['spurious_atoms']:>3}   pairs {s['pairs']}")

    print()
    if bad:
        print(f"FAILED: {bad} problem(s).")
        return 1
    print("OK: hashes, admission controls and every held-out value reproduce.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
