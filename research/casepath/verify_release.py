#!/usr/bin/env python3
"""Verify the whole CasePath research release with one command.

    python3 research/casepath/verify_release.py

Runs every check that can be run offline and prints one table:

  1. Study A reproduces        the frozen analysis, rerun on the released predictions, equals the
                               preserved held-out report
  2. Benchmark explorer data   the per-pair correct/spurious/missed marks sum to that report
  3. Manuscript numbers        regenerating every macro from the evidence files leaves the
                               committed numbers.tex and tables unchanged
  4. No hand-typed numbers     nothing numeric is left in the prose except the allowed exceptions
  5. Paper matches benchmark   every recomputable macro equals a fresh recomputation
  6. Paper builds              Tectonic compiles it and the main text ends on page 9 or earlier
  7. Anonymity                 no author, employer, agent or repository token in the sources the
                               paper inputs, and no /Author in the PDF metadata
  8. Study B reproduces        present only once the 150-claim release has been built

Exit status is 0 only if every check that ran passed. A check whose inputs do not exist is
reported as "not present", never as passing.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DOC = HERE / "iclr2027-integrated"
BENCH = HERE / "branch-benchmark"
NATIVE = HERE / "native-corpus"
TECTONIC = REPO / ".runtime" / "tools" / "tectonic" / "tectonic"
# Pinning the build clock makes the PDF byte-reproducible: without it every rebuild differs only
# by its embedded creation timestamp. 1789948800 = 2026-09-21T00:00:00Z.
SOURCE_DATE_EPOCH = "1789948800"

# Author-identifying tokens: these must not appear anywhere in the paper's sources.
IDENTITY = re.compile(r"navish|kumar|mobiliar|codex|chatgpt|astra|anthropic|"
                      r"@[a-z0-9.-]+\.(?:com|ch|org)", re.I)
# A link to the authors' own repository de-anonymises; third-party repository URLs in the
# bibliography do not, so this is checked outside references.bib only.
SELF_LINK = re.compile(r"github\.com/KumarNavish|casepath\.git", re.I)
PAPER_SOURCES = ["main.tex", "submitted_frontmatter.tex", "introduction.tex", "method.tex",
                 "benchmark.tex", "paired_results.tex", "native_study.tex", "related.tex",
                 "release.tex", "discussion.tex", "statements.tex", "appendix_studya.tex",
                 "appendix_native.tex", "numbers.tex", "references.bib"]

results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool | None, detail: str) -> None:
    results.append((name, "pass" if ok else ("not present" if ok is None else "FAIL"), detail))


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          env={**os.environ, **env} if env else None)
    return proc.returncode, (proc.stdout + proc.stderr)


def check_study_a() -> None:
    if not (BENCH / "reproduce.py").exists():
        record("Study A reproduces", None, "branch-benchmark/ not present")
        return
    code, out = run([sys.executable, "reproduce.py"], BENCH)
    tail = next((l for l in reversed(out.strip().splitlines()) if l.strip()), "")
    record("Study A reproduces", code == 0, tail.strip())


def check_explorer() -> None:
    if not (BENCH / "build_explorer_data.py").exists():
        record("Benchmark explorer data", None, "not present")
        return
    code, out = run([sys.executable, "build_explorer_data.py"], BENCH)
    # The builder asserts that per-pair marks sum to the preserved report's totals.
    record("Benchmark explorer data", code == 0,
           "per-pair marks sum to the report" if code == 0 else out.strip().splitlines()[-1][:90])


def check_numbers_stable() -> None:
    code, out = run([sys.executable, "evidence/build_manuscript_numbers.py"], DOC)
    if code != 0:
        record("Manuscript numbers", False, out.strip().splitlines()[-1][:90])
        return
    code, diff = run(["git", "status", "--porcelain", "--",
                      "numbers.tex", "table_main_results.tex", "table_claim_gates.tex",
                      "table_family_results.tex", "table_costs.tex", "table_native_execution.tex"], DOC)
    changed = [l.split()[-1] for l in diff.strip().splitlines() if l.strip()]
    record("Manuscript numbers", not changed,
           "regeneration leaves every macro and table unchanged" if not changed
           else "regeneration changed: " + ", ".join(changed))


def check_literals() -> None:
    script = DOC / "evidence" / "check_literal_numbers.py"
    if not script.exists():
        record("No hand-typed numbers", None, "checker not present")
        return
    code, out = run([sys.executable, str(script)], DOC)
    lines = [l for l in out.strip().splitlines() if l.strip()]
    record("No hand-typed numbers", code == 0,
           f"{len(lines)} allowed exception(s): figure widths, the quoted CHF example, the CI level")


def check_cross() -> None:
    script = DOC / "evidence" / "check_against_benchmark_release.py"
    if not script.exists():
        record("Paper matches benchmark", None, "checker not present")
        return
    code, out = run([sys.executable, str(script)], DOC)
    m = re.search(r"(\d+) macro\(s\) recomputed .* and matched", out)
    record("Paper matches benchmark", code == 0,
           f"{m.group(1)} macros recomputed and matched" if m else out.strip().splitlines()[-1][:90])


def check_build() -> None:
    if not TECTONIC.exists():
        record("Paper builds", None, "tectonic not present")
        return
    for stale in ("main.aux", "main.bbl"):
        (DOC / stale).unlink(missing_ok=True)
    code, out = run([str(TECTONIC), "--keep-logs", "--keep-intermediates", "main.tex"], DOC,
                    env={"SOURCE_DATE_EPOCH": SOURCE_DATE_EPOCH})
    if code != 0:
        record("Paper builds", False, "tectonic failed")
        return
    aux = (DOC / "main.aux").read_text(errors="ignore")
    m = re.search(r"\\newlabel\{end-of-main-text\}\{\{[^}]*\}\{(\d+)\}", aux)
    if not m:
        record("Paper builds", False, "end-of-main-text label not found")
        return
    page = int(m.group(1))
    log = (DOC / "main.log").read_text(errors="ignore")
    undefined = len(re.findall(r"LaTeX Warning: (?:Citation|Reference) `[^']*' [^\n]*undefined", log))
    overfull = len(re.findall(r"Overfull \\hbox", log))
    code, dirty = run(["git", "status", "--porcelain", "--", "main.pdf"], DOC)
    reproducible = not dirty.strip()
    record("Paper builds", page <= 9 and undefined == 0 and reproducible,
           f"main text ends on page {page} (limit 9); {undefined} undefined reference(s), "
           f"{overfull} overfull box(es); rebuild is "
           + ("byte-identical to the committed PDF" if reproducible else "NOT byte-identical"))


def check_anonymity() -> None:
    hits = []
    for name in PAPER_SOURCES:
        path = DOC / name
        if not path.exists():
            continue
        patterns = [IDENTITY] if name == "references.bib" else [IDENTITY, SELF_LINK]
        for i, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            for pattern in patterns:
                for m in pattern.finditer(line):
                    # The evaluated model's provider label and bibliography editor names are not
                    # identity leaks, and third-party repository URLs in citations are not either.
                    if "openai/gpt" in line or "editor" in line.lower():
                        continue
                    hits.append(f"{name}:{i} {line[max(0, m.start() - 12):m.end() + 12].strip()}")
    pdf = DOC / "main.pdf"
    meta_author = bool(re.search(rb"/Author\s*\(\s*[^)\s]", pdf.read_bytes())) if pdf.exists() else False
    ok = not hits and not meta_author
    detail = ("no author, employer or agent token in the paper's sources, no link to the authors' "
              "repository, no /Author in the PDF")
    if hits:
        detail = f"{len(hits)} token(s): " + "; ".join(hits[:3])
    elif meta_author:
        detail = "PDF metadata carries an /Author entry"
    record("Anonymity", ok, detail)


def check_study_b() -> None:
    if not (NATIVE / "reproduce.py").exists():
        record("Study B reproduces", None,
               "native-corpus/ not built yet - run evidence/build_native_release.py after the export")
        return
    code, out = run([sys.executable, "reproduce.py"], NATIVE)
    tail = next((l for l in reversed(out.strip().splitlines()) if l.strip()), "")
    record("Study B reproduces", code == 0, tail.strip())


def main() -> int:
    print("CasePath release verification\n")
    for check in (check_study_a, check_explorer, check_numbers_stable, check_literals,
                  check_cross, check_build, check_anonymity, check_study_b):
        check()
    width = max(len(n) for n, _, _ in results)
    print(f"  {'check'.ljust(width)}  status       detail")
    print(f"  {'-' * width}  -----------  ------")
    for name, status, detail in results:
        print(f"  {name.ljust(width)}  {status:<11}  {detail}")
    failed = [n for n, s, _ in results if s == "FAIL"]
    absent = [n for n, s, _ in results if s == "not present"]
    print()
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1
    print("OK: every check that ran passed." + (f" Not present: {', '.join(absent)}." if absent else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
