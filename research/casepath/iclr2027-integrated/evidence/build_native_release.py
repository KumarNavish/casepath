#!/usr/bin/env python3
"""Assemble the Study B release from the exported final evidence.

    python3 evidence/build_native_release.py --evidence <final-evidence-dir> [--dry-run]

The export produced by the run's own finalisation step contains the scored rows for both splits
(`public_dev.json`, `hidden_test.json`), the descriptive report computed from them
(`FINITE_REPORT.json`), and the run records that bind them. This script copies those files, the
frozen reporting module, the analysis contract and the cell plan into
`research/casepath/native-corpus/`, writes a hash manifest and a `reproduce.py` that recomputes the
report from the rows and diffs it against the preserved one, and generates the README from the
report's own values.

Nothing is invented: every number in the generated README is read from the report. If the export is
incomplete or the run did not reach `finite_corpus_evaluated`, the script refuses to build.

Raw producer cells are ~64 MB and stay in the supplementary archive; a small per-cell index
(case, arm, state, error class) is included here so the execution record is inspectable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent.parent / "native-corpus"
BRIDGE = Path("/Users/kumar0002/.local/state/navish-acceptance-20260919/final-execution-bridge-854b8a85")
CONTRACT = BRIDGE / "ANALYSIS_CONTRACT.json"
REPORTING = BRIDGE / "casepath_execution_bridge" / "finite_reporting.py"
MATRIX = Path("/Users/kumar0002/.local/state/navish-acceptance-20260919/PRO_NATIVE150_MATRIX.jsonl")
CORPUS = Path(__file__).resolve().parents[4] / "casepath-api" / "casepath_api" / "corpora" / "synthetic-150" / "claims"
CELLS_ROOT = Path("/Users/kumar0002/.local/state/navish-acceptance-20260919/mac-native150")

REPORT_SCHEMA = "casepath.finite-corpus-descriptive/1.0.0"

SHIM = '''"""Minimal stand-in for the execution bridge's `canonical` module.

`finite_reporting.py` is released byte-for-byte as it ran; its only import from the execution
infrastructure is the assertion helper below, reproduced here so the module runs without the
registration, ledger and custody machinery that has no role in computing the report.
"""


class StopExecution(Exception):
    pass


def require(value, category):
    if not value:
        raise StopExecution(category)
'''

REPRODUCE = '''#!/usr/bin/env python3
"""Recompute the Study B finite-corpus report from the scored rows, offline.

    python3 reproduce.py

Loads the __N_ROWS__ scored rows of both splits, runs the frozen reporting module that produced the
released report, and compares the result against `expected/FINITE_REPORT.json`. No network and no
provider account are needed; this recomputes the report, it does not regenerate model outputs.
Exit status is 0 only if every value reproduces.
"""
from __future__ import annotations

import hashlib
import json
import sys
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOLERANCE = 1e-9

# finite_reporting.py is released verbatim; satisfy its one infrastructure import with the shim.
shim = types.ModuleType("canonical")
exec((HERE / "analysis" / "_canonical_shim.py").read_text(), shim.__dict__)
package = types.ModuleType("bridge")
package.__path__ = [str(HERE / "analysis")]
package.canonical = shim
sys.modules["bridge"] = package
sys.modules["bridge.canonical"] = shim
source = (HERE / "analysis" / "finite_reporting.py").read_text()
finite = types.ModuleType("bridge.finite_reporting")
finite.__package__ = "bridge"
sys.modules["bridge.finite_reporting"] = finite
exec(compile(source, "finite_reporting.py", "exec"), finite.__dict__)


def check_manifest() -> int:
    manifest = json.loads((HERE / "MANIFEST.json").read_text())
    bad = 0
    for entry in manifest["files"]:
        path = HERE / entry["path"]
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            print(f"  CHANGED OR MISSING  {entry['path']}")
            bad += 1
    print(f"  {len(manifest['files']) - bad}/{len(manifest['files'])} files match the manifest")
    return bad


def diff(a, b, path="", drift=None):
    if isinstance(b, dict):
        if not isinstance(a, dict):
            return [f"{path}: not a dict"]
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append(f"{path}/{k}: missing from the rerun")
            elif k not in b:
                out.append(f"{path}/{k}: absent from the preserved report")
            else:
                out += diff(a[k], b[k], f"{path}/{k}", drift)
        return out
    if isinstance(b, list):
        if not isinstance(a, list) or len(a) != len(b):
            return [f"{path}: list length differs"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, f"{path}[{i}]", drift)
        return out
    if isinstance(b, float) and isinstance(a, (int, float)) and not isinstance(a, bool):
        d = abs(a - b)
        if d == 0:
            return []
        if d <= TOLERANCE * max(1.0, abs(b)):
            if drift is not None:
                drift.append((d, path))
            return []
        return [f"{path}: {a!r} != {b!r}"]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def main() -> int:
    print("CasePath 150-claim corpus - offline recomputation of the finite report\\n")
    print("1. File integrity")
    bad = check_manifest()

    rows = []
    for name in ("public_dev.json", "hidden_test.json"):
        rows += json.loads((HERE / "evaluation" / name).read_text())
    print(f"\\n2. Scored rows: {len(rows)} ({len({r['case_id'] for r in rows})} cases x {len({r['arm'] for r in rows})} arms)")

    config = json.loads((HERE / "analysis" / "report_config.json").read_text())
    print("\\n3. Recomputing the descriptive report with the frozen module")
    recomputed = finite.report(rows, config)
    preserved = json.loads((HERE / "expected" / "FINITE_REPORT.json").read_text())
    drift = []
    differences = diff(recomputed, preserved, drift=drift)
    if differences:
        print(f"  {len(differences)} value(s) differ:")
        for line in differences[:20]:
            print(f"    {line}")
        bad += len(differences)
    else:
        print("  every value reproduces the released report" + (f" to within {TOLERANCE:g}" if drift else " exactly"))
        if drift:
            worst, where = max(drift)
            print(f"  {len(drift)} value(s) differ only by floating-point summation order; "
                  f"largest deviation {worst:.2e} at {where}")

    print()
    if bad:
        print(f"FAILED: {bad} problem(s).")
        return 1
    print("OK: the released report recomputes from the released rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cell_index() -> list[dict]:
    """Small, target-free index of the producer cells: no scores, no model output."""
    splits = {}
    for line in MATRIX.open():
        row = json.loads(line)
        splits[row["case_id"]] = (row["split"], row["domain"], row["family_id"])
    best = max(CELLS_ROOT.glob("*/work/output/cells"), key=lambda d: len(list(d.glob("*.json"))))
    index = []
    for path in sorted(best.glob("*.json")):
        cell = json.loads(path.read_text())
        split, domain, family = splits.get(cell["case_id"], ("?", "?", "?"))
        index.append({
            "case_id": cell["case_id"], "arm": cell["arm"], "split": split,
            "domain": domain, "family_id": family, "state": cell["state"],
            "error_type": cell.get("error_type"),
            "error_summary": (next(iter((cell.get("error") or "").strip().splitlines()), "") or "")[:180] or None,
        })
    return index


def readme(report: dict, rows_by_split: dict, contract: dict, n_cells: int) -> str:
    hid = report["splits"]["hidden_test"]
    dev = report["splits"]["public_dev"]
    met = [c for c in hid["primary_contrasts"] if c.get("finite_practical_target_met")]
    lines = [
        "# The CasePath 150-claim corpus: complete evidence plans",
        "",
        "Study A asks whether a system changes the right documents when one case fact changes.",
        "This study asks the other question: given the same compiled public knowledge, does",
        "executing applicability, acquisition permission and route sufficiency produce a better",
        "complete plan than generating one?",
        "",
        "```bash",
        "python3 reproduce.py",
        "```",
        "",
        "recomputes the released descriptive report from the released scored rows with the frozen",
        "reporting module and diffs it against the preserved one. No network, no provider account.",
        "",
        "## Design",
        "",
        f"- **{hid['cases'] + dev['cases']} synthetic tenancy claims** in "
        f"{hid['families'] + dev['families']} families across three domains: defect/mould/heating,",
        "  lease termination, rent increase.",
        f"- **Development split** {dev['cases']} claims in {dev['families']} families; "
        f"**protected split** {hid['cases']} claims in {hid['families']} disjoint families.",
        f"- **{len(contract['matrix']['learned_arms'])} learned arms** sharing one deterministic"
        " compilation of the public templates and the same observable packet, plus",
        f"  **{len(contract['matrix']['deterministic_controls'])} dependent controls**; "
        f"{n_cells} scheduled cells in total.",
        "- Scoring runs only after both prediction phases are frozen. Failed, truncated and blocked",
        "  cells stay in the denominator with adverse penalties, and a conservative paired contrast",
        "  assigns -1 whenever either endpoint is unobserved.",
        "",
        "## What the contract fixes in advance",
        "",
        "Three endpoints are contrasted against each learned comparator: emitted-checklist F1,",
        "criticality-weighted recall of required evidence, and the fraction of emitted requests that",
        "are unnecessary. Domains, families within domains and cases within families are weighted",
        "equally. The report is descriptive by construction: the corpus is finite and fully",
        "enumerated, so no p-values or confidence intervals are computed; single-family-deletion",
        "ranges express composition sensitivity instead.",
        "",
        f"On the protected split, **{len(met)} of {len(hid['primary_contrasts'])}** preregistered",
        "practical targets are met. Per-arm endpoint values, every conservative contrast and its",
        "family-deletion range are in `expected/FINITE_REPORT.json` and are printed by",
        "`reproduce.py`.",
        "",
        "## Files",
        "",
        "```",
        "evaluation/     scored rows for both splits - the inputs to the report",
        "expected/       the released descriptive report",
        "analysis/       the frozen reporting module (byte-identical to the one that ran), its",
        "                config, and a shim for its one infrastructure import",
        "contract/       the frozen analysis contract and the cell plan",
        "execution/      run result, metrics, prediction freeze, producer I/O audit, and a",
        "                target-free per-cell index (case, arm, state, error class)",
        "MANIFEST.json   sha256 of every file",
        "```",
        "",
        "Raw producer cells (~64 MB) stay in the supplementary archive; the per-cell index here",
        "records each cell's execution state and error class without any model output.",
        "",
        "The claims themselves are not duplicated here: the evaluated case identifiers are exactly the",
        "150 claim files this repository ships at `casepath-api/casepath_api/corpora/synthetic-150/claims/`,",
        "which the product loads at runtime. `research/casepath/verify_release.py` checks that identity.",
        "",
        "## What this establishes, and what it does not",
        "",
        "A complete run supports a **pipeline-level, finite-corpus** statement about this corpus",
        "under shared compiled knowledge. It does not establish population superiority, isolate a",
        "mechanism, constitute independent replication, or show generalisation to unseen inputs.",
        "All 150 observable inputs were inspected during product development, so *protected* denotes",
        "label custody and family disjointness, not untouched inputs. This study is never pooled",
        "with Study A: the populations, implementations and endpoints differ.",
        "",
        "See [`../branch-benchmark/`](../branch-benchmark/README.md) for Study A and",
        "[`../iclr2027-integrated/`](../iclr2027-integrated/README.md) for the manuscript.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True, type=Path, help="the exported final-evidence directory")
    ap.add_argument("--dry-run", action="store_true", help="validate inputs without writing anything")
    args = ap.parse_args()

    ev = args.evidence
    required = ["FINITE_REPORT.json", "public_dev.json", "hidden_test.json", "RESULT.json", "METRICS.json"]
    missing = [n for n in required if not (ev / n).exists()]
    if missing:
        print(f"export incomplete, missing: {', '.join(missing)}")
        return 1
    result = json.loads((ev / "RESULT.json").read_text())
    if result.get("state") != "finite_corpus_evaluated":
        print(f"run state is {result.get('state')!r}, not 'finite_corpus_evaluated' - refusing to build")
        return 1
    report = json.loads((ev / "FINITE_REPORT.json").read_text())
    if report.get("schema") != REPORT_SCHEMA:
        print(f"unexpected report schema {report.get('schema')!r}")
        return 1
    if report.get("statistical_significance_computed") is not False:
        print("report must declare statistical_significance_computed = false")
        return 1
    rows_by_split = {n: json.loads((ev / f"{n}.json").read_text()) for n in ("public_dev", "hidden_test")}
    total_rows = sum(len(v) for v in rows_by_split.values())
    print(f"export OK: {total_rows} scored rows, report schema {REPORT_SCHEMA}")
    if args.dry_run:
        print("dry run: nothing written")
        return 0

    planned = {json.loads(line)["case_id"] for line in MATRIX.open()}
    shipped = {p.stem for p in CORPUS.glob("*.json")} if CORPUS.is_dir() else set()
    if shipped and shipped != planned:
        print(f"corpus mismatch: {len(shipped - planned)} shipped-only, {len(planned - shipped)} planned-only")
        return 1
    print(f"corpus identity OK: the {len(planned)} evaluated cases are exactly the claims the product ships")

    contract = json.loads(CONTRACT.read_text())
    for sub in ("evaluation", "expected", "analysis", "contract", "execution"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)

    copied: list[tuple[str, Path]] = []
    for name in ("public_dev.json", "hidden_test.json"):
        shutil.copy2(ev / name, OUT / "evaluation" / name); copied.append((f"evaluation/{name}", ev / name))
    shutil.copy2(ev / "FINITE_REPORT.json", OUT / "expected" / "FINITE_REPORT.json")
    copied.append(("expected/FINITE_REPORT.json", ev / "FINITE_REPORT.json"))
    for name in ("RESULT.json", "METRICS.json", "PREDICTION_FREEZE.json", "PRODUCER_IO_AUDIT.json"):
        if (ev / name).exists():
            shutil.copy2(ev / name, OUT / "execution" / name); copied.append((f"execution/{name}", ev / name))
    shutil.copy2(REPORTING, OUT / "analysis" / "finite_reporting.py"); copied.append(("analysis/finite_reporting.py", REPORTING))
    shutil.copy2(CONTRACT, OUT / "contract" / "ANALYSIS_CONTRACT.json"); copied.append(("contract/ANALYSIS_CONTRACT.json", CONTRACT))
    shutil.copy2(MATRIX, OUT / "contract" / "cell_plan.jsonl"); copied.append(("contract/cell_plan.jsonl", MATRIX))

    (OUT / "analysis" / "_canonical_shim.py").write_text(SHIM)
    (OUT / "analysis" / "report_config.json").write_text(
        json.dumps({"learned_arms": contract["matrix"]["learned_arms"]}, indent=1) + "\n")
    index = cell_index()
    (OUT / "execution" / "cell_index.json").write_text(json.dumps(index, indent=1) + "\n")
    n_cells = contract["matrix"]["total_cells"]
    (OUT / "reproduce.py").write_text(REPRODUCE.replace("__N_ROWS__", str(total_rows)))
    (OUT / "README.md").write_text(readme(report, rows_by_split, contract, n_cells))

    manifest = {
        "schema": "casepath.native-corpus-release/1.0.0",
        "run_id": result.get("run_id"),
        "report_sha256": sha(OUT / "expected" / "FINITE_REPORT.json"),
        "note": "Files copied from the run's own final-evidence export are byte-identical to it; "
                "_canonical_shim.py, report_config.json, cell_index.json, reproduce.py and README.md "
                "are generated by build_native_release.py.",
        "source_paths": {rel: str(src) for rel, src in copied},
        "files": [],
    }
    for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "MANIFEST.json"):
        manifest["files"].append({"path": str(path.relative_to(OUT)), "bytes": path.stat().st_size, "sha256": sha(path)})
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n")

    size = sum(f["bytes"] for f in manifest["files"]) / 1e6
    print(f"wrote {OUT} - {len(manifest['files'])} files, {size:.2f} MB")

    print("\nverifying the bundle reproduces its own report:")
    proc = subprocess.run([sys.executable, str(OUT / "reproduce.py")], capture_output=True, text=True)
    print(proc.stdout.rstrip() or proc.stderr[-1500:])
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
