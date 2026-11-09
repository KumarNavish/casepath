"""End-to-end check that the paper matches its evidence.

1. Recompute every analysis from the saved plans and the cached model responses
   (no model calls: TMIS_BUDGET_USD=0) and regenerate the evidence files and the
   number macros; they must equal the saved files and paper/results/numbers.tex
   byte for byte.
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

# Every script that feeds numbers.tex, in dependency order. One process per model: the client binds
# its model at import. TMIS_BUDGET_USD=0 makes any uncached model call fail instead of reaching the API.
# Static inputs not regenerated here: rule_verification.json, reference_rederivation.json (cached model
# runs of the harness), ../scicore/out_local/*.json (cluster jobs) and the tenancy entries of error_causes.json.
TAGS = ("gpt-6.1-terra", "gpt-6-luna")
PIPELINE = ([(["analyze.py", t], t) for t in TAGS] + [(["tenancy_extra.py", t], t) for t in TAGS]
            + [(["judgment_accuracy.py", t], t) for t in TAGS] + [(["two_valued.py"], t) for t in TAGS]
            + [(["handoff_causes.py", t], t) for t in TAGS] + [(["repair_family.py", t], t) for t in TAGS] + [(["theft_error_origin.py", "gpt-6.1-terra"], "gpt-6.1-terra"),
               (["original_study.py"], None), (["primary_tests.py"], None), (["break_even.py"], None), (["make_numbers.py"], None)])
evidence = sorted(HERE.glob("*.json"))
before_json = {f.name: f.read_bytes() for f in evidence}
before = (PAPER / "results" / "numbers.tex").read_text()
for cmd, tag in PIPELINE:
    env = {**os.environ, "TMIS_BUDGET_USD": "0"}
    if tag:
        env["TMIS_MODEL"] = f"openai/{tag}"
    r = subprocess.run([sys.executable, *cmd], cwd=HERE, env=env, capture_output=True, text=True)
    step("ran " + " ".join(cmd), r.returncode == 0, r.stderr[-300:] if r.returncode else "")
changed = [n for n, b in before_json.items() if (HERE / n).read_bytes() != b]
step("evidence files reproduce byte for byte", not changed, ", ".join(changed))
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
