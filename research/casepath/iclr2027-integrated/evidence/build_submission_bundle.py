#!/usr/bin/env python3
"""Build dist/casepath_iclr2027_submission_source.zip: the paper's LaTeX input closure.

    python3 evidence/build_submission_bundle.py

The file list is derived from main.tex by following \\input and \\includegraphics, so a file that
stops being used drops out and a newly used one is picked up without editing a list here.

Every entry is checked before zipping and again after. A figure regenerated concurrently can be
observed at zero length, and a zip built at that moment ships a submission that does not compile;
that happened once, so the guard is not hypothetical.
"""
from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from pathlib import Path

DOC = Path(__file__).resolve().parent.parent
ROOTS = {"main.tex", "references.bib", "iclr2027_conference.sty", "iclr2027_conference.bst"}
EXTRA = {"README.md"}  # shipped so a reviewer can read what the archive is


def closure() -> list[str]:
    need, queue = set(ROOTS), ["main.tex"]
    while queue:
        path = DOC / queue.pop()
        if not path.exists():
            continue
        text = path.read_text(errors="ignore")
        for m in re.finditer(r"\\input\{([^}]+)\}", text):
            name = m.group(1)
            if not name.endswith(".tex"):
                name += ".tex"
            if name not in need:
                need.add(name)
                queue.append(name)
        for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text):
            name = m.group(1)
            need.add(name if (DOC / name).exists() else name + ".pdf")
    return sorted(need | {n for n in EXTRA if (DOC / n).exists()})


def check(names: list[str]) -> list[str]:
    problems = []
    for name in names:
        path = DOC / name
        if not path.exists():
            problems.append(f"{name}: missing")
        elif path.stat().st_size == 0:
            problems.append(f"{name}: empty on disk")
        elif path.suffix == ".pdf" and b"%%EOF" not in path.read_bytes()[-64:]:
            problems.append(f"{name}: PDF has no %%EOF trailer, probably written concurrently")
    return problems


def main() -> int:
    names = closure()
    problems = check(names)
    if problems:
        print("refusing to build the bundle:")
        for p in problems:
            print(f"  {p}")
        return 1

    out = DOC / "dist" / "casepath_iclr2027_submission_source.zip"
    out.parent.mkdir(exist_ok=True)
    if out.exists():
        out.unlink()
    subprocess.run(["zip", "-q", "-X", str(out)] + names, cwd=DOC, check=True)

    sizes = {i.filename: i.file_size for i in zipfile.ZipFile(out).infolist()}
    wrong = [n for n in names if sizes.get(n) != (DOC / n).stat().st_size]
    if wrong:
        out.unlink()
        print("bundle removed: entries did not match the files on disk: " + ", ".join(wrong))
        return 1

    pdf = DOC / "main.pdf"
    if pdf.exists():
        (DOC / "dist" / "casepath_iclr2027_submission.pdf").write_bytes(pdf.read_bytes())
    print(f"wrote {out.name}: {len(names)} files, {out.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
