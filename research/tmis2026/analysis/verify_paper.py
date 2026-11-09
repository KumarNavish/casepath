"""End-to-end check that the paper matches its evidence.

1. Recompute every analysis from the saved plans and the cached model responses
   (no model calls: the budget cap is set to the current spend) and regenerate
   the number macros; they must equal paper/results/numbers.tex byte for byte.
2. Every citation key resolves to references.bib.
3. The paper compiles from a clean copy without errors or undefined references.
"""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
PAPER = HERE.parent / "paper"
ok = True
def step(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))

sys.path.insert(0, str(HERE.parent / "harness"))
import llm
env = {**os.environ, "TMIS_BUDGET_USD": f"{llm.spent():.4f}"}  # any uncached call would be refused
before = (PAPER / "results" / "numbers.tex").read_text()
for cmd in (["analyze.py", "gpt-6.1-terra"], ["analyze.py", "gpt-6-luna"], ["primary_tests.py"], ["make_numbers.py"]):
    r = subprocess.run([sys.executable, *cmd], cwd=HERE, env=env, capture_output=True, text=True)
    step("ran " + " ".join(cmd), r.returncode == 0, r.stderr[-300:] if r.returncode else "")
after = (PAPER / "results" / "numbers.tex").read_text()
step("number macros reproduce byte for byte", before == after,
     "" if before == after else f"{sum(a != b for a, b in zip(before.splitlines(), after.splitlines()))} lines differ")
cites = set()
for f in PAPER.glob("sections/*.tex"):
    for group in re.findall(r"\\cite[pt]?\{([^}]*)\}", f.read_text()):
        cites |= {c.strip() for c in group.split(",")}
keys = set(re.findall(r"^@\w+\{([^,]+),", (PAPER / "references.bib").read_text(), re.M))
step("all citation keys resolve", cites <= keys, ", ".join(sorted(cites - keys)))
with tempfile.TemporaryDirectory() as tmp:
    dst = Path(tmp) / "paper"
    shutil.copytree(PAPER, dst, ignore=shutil.ignore_patterns("*.aux", "*.log", "*.bbl", "*.blg", "*.out", "*.pdf", "build*.log", "comment.cut"))
    for fig in (PAPER / "figures").glob("*.pdf"):
        shutil.copy(fig, dst / "figures" / fig.name)
    for args in (["pdflatex", "-interaction=nonstopmode", "main.tex"], ["bibtex", "main"],
                 ["pdflatex", "-interaction=nonstopmode", "main.tex"], ["pdflatex", "-interaction=nonstopmode", "main.tex"]):
        subprocess.run(args, cwd=dst, capture_output=True, text=True)
    log = (dst / "main.log").read_text(errors="ignore")
    step("clean compile without errors", (dst / "main.pdf").exists() and "\n! " not in log)
    step("no undefined references or citations", "undefined" not in re.sub(r"Font shape .*? undefined", "", log))
print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
sys.exit(0 if ok else 1)
