#!/usr/bin/env python3
"""Assemble the public research package from the repository, and hash every byte of it.

Run from the repository root. Everything it emits is copied out of the repo rather than re-derived, so the
package cannot drift from the code that produced the numbers.
"""
from __future__ import annotations

import hashlib, json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "release" / "package"
API = ROOT / "casepath-api"
R = ROOT / "research" / "ctes"

LAYOUT: dict[str, list[tuple[str, str]]] = {
    "benchmark/generator": [("casepath-api/casepath_api/arena_v1/generator.py", "generator.py"),
                            ("casepath-api/casepath_api/arena_v1/write_episodes.py", "write_episodes.py"),
                            ("casepath-api/casepath_api/arena_v1/assemble.py", "assemble.py"),
                            ("casepath-api/casepath_api/arena_v1/verify_episodes.py", "verify_episodes.py")],
    "benchmark/evaluator": [("casepath-api/casepath_api/arena_v1/evaluation.py", "evaluation.py"),
                            ("casepath-api/casepath_api/arena_v1/shortcut_audit.py", "shortcut_audit.py")],
    "benchmark/baselines": [("casepath-api/casepath_api/arena_v1/arms.py", "arms.py"),
                            ("casepath-api/casepath_api/artifact_gate_v1.py", "artifact_gate_v1.py")],
    "method": [("casepath-api/casepath_api/evidential_channel_v1.py", "evidential_state.py"),
               ("casepath-api/casepath_api/arena_v1/runner.py", "runner.py")],
    "analysis": [("casepath-api/casepath_api/arena_v1/analyze.py", "analyze.py"),
                 ("casepath-api/casepath_api/arena_v1/decide_confirm.py", "decide_confirm.py"),
                 ("casepath-api/casepath_api/arena_v1/decide_decisive.py", "decide_decisive.py"),
                 ("casepath-api/casepath_api/arena_v1/decide_swap.py", "decide_swap.py"),
                 ("casepath-api/casepath_api/arena_v1/decide_submission.py", "decide_submission.py"),
                 ("casepath-api/casepath_api/arena_v1/merge_runs.py", "merge_runs.py")],
    "product_adapter": [("casepath-api/casepath_api/agent_work/evidential_channel.py", "agent_work_channel.py"),
                        ("casepath-api/casepath_api/evidential_channel_gate_v1.py", "workspace_decoder_gate.py"),
                        ("casepath-api/casepath_api/arena_v1/product_corpus_study.py", "product_corpus_study.py")],
}

SPLIT_DIRS = ["confirm", "confirm2", "confirm_swap", "decisive", "decisive_swap", "submission"]
PREREGS = ["PRE_REGISTRATION_CONFIRM.md", "PRE_REGISTRATION_DECISIVE.md", "PRE_REGISTRATION_SWAP.md",
           "PRE_REGISTRATION_B6.md", "FINAL_PREREGISTRATION.md"]
RESULTS = ["CONFIRMATORY_RESULT.md", "CONFIRMATORY_DECISION.json", "CONFIRMATORY_EXPLORATORY.json",
           "DECISIVE_RESULT.md", "DECISIVE_DECISION.json", "SWAP_RESULT.md", "SWAP_DECISION.json",
           "MINIMAL_RULE_BASELINE.md", "FINAL_NOVELTY_AUDIT.md", "MODEL_GENERALIZATION_RESULT.md",
           "FINAL_PARETO_ANALYSIS.md", "FAILURE_ANALYSIS.md", "AUDIT_RESPONSE.md", "POWER_ANALYSIS.json",
           "WRITER_VALIDITY.json", "PRODUCT_INTEGRATION_RECEIPT.json", "PRODUCT_CORPUS_STUDY_FULL150.json",
           "EXTERNAL_RUN_REPLAY.json", "PRODUCT_MECHANISM_UNIFICATION.md", "FINAL_METHOD.md",
           "FINAL_SCIENTIFIC_DECISION.md", "COST_ACCOUNTING_FINAL.json", "CLAIMS_LEDGER.json"]


def copy(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    missing: list[str] = []

    for folder, items in LAYOUT.items():
        for rel, name in items:
            if not copy(ROOT / rel, OUT / folder / name):
                missing.append(rel)

    for split in SPLIT_DIRS:
        src = API / "arena_v1_data" / split
        if src.is_dir():
            for f in sorted(src.iterdir()):
                copy(f, OUT / "benchmark" / "data" / split / f.name)
        else:
            missing.append(str(src.relative_to(ROOT)))

    for name in PREREGS:
        if not copy(R / name, OUT / "benchmark" / "preregistrations" / name):
            missing.append(f"research/ctes/{name}")
    for name in RESULTS:
        if not copy(R / name, OUT / "research" / name):
            missing.append(f"research/ctes/{name}")
    for run in sorted((R / "runs").glob("*/RESULT.json.gz")):
        copy(run, OUT / "benchmark" / "raw_results" / run.parent.name / "RESULT.json.gz")
    for name in ("PAPER_DRAFT.md",):
        copy(R / name, OUT / "paper" / name)
    for name in ("REPRODUCE.md", "DATA_CARD.md", "BENCHMARK_CARD.md", "LICENSES.md"):
        copy(ROOT / "release" / name, OUT / name)
    copy(API / "requirements.lock", OUT / "environment.lock")

    files = sorted(p for p in OUT.rglob("*") if p.is_file())
    sums = []
    for p in files:
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        sums.append(f"{digest}  {p.relative_to(OUT)}")
    (OUT / "SHA256SUMS").write_text("\n".join(sums) + "\n")

    try:
        commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True).strip()
    except Exception:
        commit, dirty = "unknown", "unknown"

    manifest = {
        "contract": "casepath.release-manifest/1.0.0",
        "repository_commit": commit,
        "working_tree_clean": dirty == "",
        "files": len(files),
        "bytes": sum(p.stat().st_size for p in files),
        "missing_inputs": missing,
        "note": ("every file here is copied from the repository that produced the numbers; nothing is "
                 "re-derived for the package. missing_inputs must be empty for a submission freeze."),
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(json.dumps({k: manifest[k] for k in ("repository_commit", "working_tree_clean", "files", "bytes")}, indent=1))
    if missing:
        print(f"\nMISSING ({len(missing)}), the package is not submission-complete:")
        for m in missing:
            print("  -", m)
        sys.exit(1)
    print("\npackage complete")


if __name__ == "__main__":
    main()
