#!/usr/bin/env python3
"""Recompute every decision file from the raw records and diff against what the paper cites.

No model is called. Exit 0 means every pre-registered and exploratory number in the paper was reproduced
from the committed per-turn records; any difference is printed in full and exits non-zero.
"""
from __future__ import annotations

import gzip, json, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "casepath-api"
R = ROOT / "research" / "ctes"
RUNS = R / "runs"

# committed decision file  <-  module, and the runs it is computed from
CHECKS = [
    ("CONFIRMATORY_DECISION.json", "decide_confirm",
     {"--run": ["confirm_mini", "confirm2_mini"], "--swap-run": ["confirm_swap_mini"]}),
    ("DECISIVE_DECISION.json", "decide_decisive", {"--run": ["decisive_mini"]}),
    ("SWAP_DECISION.json", "decide_swap",
     {"--swap-run": ["decisive_swap"], "--original-run": ["decisive_mini"]}),
]

IGNORE_KEYS = {"run", "swap_run", "original_run"}


def unpack(tag: str, into: Path) -> Path:
    src = RUNS / tag / "RESULT.json.gz"
    if not src.exists():
        raise SystemExit(f"missing raw records: {src}")
    d = into / tag
    d.mkdir(parents=True, exist_ok=True)
    with gzip.open(src) as fh:
        (d / "RESULT.json").write_bytes(fh.read())
    return d


def strip(obj):
    """Drop path-valued fields so a recomputation in a temp directory can compare equal."""
    if isinstance(obj, dict):
        return {k: strip(v) for k, v in obj.items() if k not in IGNORE_KEYS}
    if isinstance(obj, list):
        return [strip(v) for v in obj]
    return obj


def main() -> None:
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        for committed, module, args in CHECKS:
            target = R / committed
            if not target.exists():
                print(f"SKIP  {committed}: not committed")
                continue
            cmd = [sys.executable, "-m", f"casepath_api.arena_v1.{module}"]
            merged = None
            for flag, tags in args.items():
                if len(tags) > 1:
                    merged = tmpdir / "pooled"
                    dirs = [unpack(t, tmpdir) for t in tags]
                    subprocess.run([sys.executable, "-m", "casepath_api.arena_v1.merge_runs",
                                    *sum((["--run", str(d)] for d in dirs), []), "--out", str(merged)],
                                   cwd=API, check=True, capture_output=True)
                    cmd += [flag, str(merged)]
                else:
                    cmd += [flag, str(unpack(tags[0], tmpdir))]
            out = tmpdir / f"recomputed-{committed}"
            cmd += ["--out", str(out)]
            proc = subprocess.run(cmd, cwd=API, capture_output=True, text=True)
            if proc.returncode != 0:
                failures.append((committed, f"recomputation failed: {proc.stderr.strip()[-400:]}"))
                continue
            got, want = strip(json.loads(out.read_text())), strip(json.loads(target.read_text()))
            if got == want:
                print(f"OK    {committed}")
            else:
                diffs = [k for k in set(got) | set(want) if got.get(k) != want.get(k)]
                failures.append((committed, f"differs in: {sorted(diffs)}"))

    if failures:
        print("\nREPRODUCTION FAILED")
        for name, why in failures:
            print(f"  {name}: {why}")
        sys.exit(1)
    print("\nPASS - every committed decision file reproduces from the raw records")


if __name__ == "__main__":
    main()
