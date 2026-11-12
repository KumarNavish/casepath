"""End-to-end check that the paper matches its evidence.

1. Recompute every analysis from the saved plans and the cached model responses
   (no model calls: TMIS_BUDGET_USD=0) and regenerate the evidence files and the
   number macros; they must equal the saved files and paper/results/numbers.tex
   byte for byte.
2. Every citation key resolves to references.bib.
3. The Study 3, ShARC, review, feedback and post-hoc macros regenerate from their result files byte for byte
   (make_numbers_study3.py, make_numbers_sharc.py, make_numbers_followup.py, make_numbers_study3_review.py,
   make_numbers_study3_feedback.py; lint_followup.py writes analysis/posthoc_numbers.tex, copied to
   paper/results/numbers_posthoc.tex; the saved files are restored afterwards).
4. Structure of the included sections: no removed figure in the body, no "expert review" wording,
   model names in Sections 1-9 only once, in Section 6.
5. The paper (main.tex, and supplement.tex when present, built main, supplement, main) compiles from a
   clean copy without errors, undefined references, multiply defined labels or overfull boxes over 5pt.

    python3 verify_paper.py               all checks
    python3 verify_paper.py --paper-only  skip check 1 (Studies 1-2 recomputation, needs the unpacked cache)
"""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
PAPER = HERE.parent / "paper"
ok = True
PAPER_ONLY = "--paper-only" in sys.argv[1:]
def step(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))

if not PAPER_ONLY:
    # Every script that feeds numbers.tex, in dependency order. One process per model: the client binds
    # its model at import. TMIS_BUDGET_USD=0 makes any uncached model call fail instead of reaching the API.
    # Static inputs not regenerated here: rule_verification.json, reference_rederivation.json (cached model
    # runs of the harness), ../scicore/out_local/*.json (cluster jobs) and the tenancy entries of error_causes.json.
    TAGS = ("gpt-6.1-terra", "gpt-6-luna")
    PIPELINE = ([(["analyze.py", t], t) for t in TAGS] + [(["tenancy_extra.py", t], t) for t in TAGS]
                + [(["judgment_accuracy.py", t], t) for t in TAGS] + [(["two_valued.py"], t) for t in TAGS]
                + [(["handoff_causes.py", t], t) for t in TAGS] + [(["repair_family.py", t], t) for t in TAGS] + [(["theft_error_origin.py", "gpt-6.1-terra"], "gpt-6.1-terra"),
                   (["original_study.py"], None), (["primary_tests.py"], None), (["break_even.py"], None)])
    # Study 2 enters the pipeline only once the runner has written plans on the fresh data.
    if any((HERE.parent / "runs" / "v2").glob("plans_*_fresh_*.json")):
        PIPELINE.append((["study2.py"], None))
    PIPELINE.append((["make_numbers.py"], None))
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

# 3. Study 3 and ShARC macros from their result files (no model calls).
for script, name in (("make_numbers_study3.py", "numbers_study3.tex"), ("make_numbers_sharc.py", "numbers_sharc.tex"),
                     ("make_numbers_followup.py", "numbers_followup.tex"), ("make_numbers_study3_review.py", "numbers_study3_review.tex"),
                     ("make_numbers_study3_feedback.py", "numbers_study3_feedback.tex")):
    target = PAPER / "results" / name
    saved = target.read_bytes()
    try:
        r = subprocess.run([sys.executable, script], cwd=HERE, env={**os.environ, "TMIS_BUDGET_USD": "0"},
                           capture_output=True, text=True)
        same = r.returncode == 0 and target.read_bytes() == saved
        step(f"{name} reproduces byte for byte", same, r.stderr[-300:] if r.returncode else "")
    finally:
        target.write_bytes(saved)

# Post-hoc decomposition and lint macros: lint_followup.py writes analysis/posthoc_numbers.tex from the stored runs and
# decomposition.json (no model calls); the paper reads a copy, paper/results/numbers_posthoc.tex, made here.
src, target = HERE / "posthoc_numbers.tex", PAPER / "results" / "numbers_posthoc.tex"
saved_src = src.read_bytes()
saved = target.read_bytes() if target.exists() else None
r = subprocess.run([sys.executable, "lint_followup.py"], cwd=HERE, env={**os.environ, "TMIS_BUDGET_USD": "0"},
                   capture_output=True, text=True)
same_src = r.returncode == 0 and src.read_bytes() == saved_src
step("posthoc_numbers.tex reproduces byte for byte", same_src, r.stderr[-300:] if r.returncode else "")
if not same_src:
    src.write_bytes(saved_src)
step("numbers_posthoc.tex is the copy of posthoc_numbers.tex", saved == src.read_bytes())
target.write_bytes(src.read_bytes())

# 4. Structure of the sections that main.tex includes.
main = (PAPER / "main.tex").read_text()
included = [PAPER / (m + ".tex") for m in re.findall(r"\\input\{(sections/[^}]+)\}", main)]
body = [f for f in included if re.match(r"s[1-9]_", f.name)]
def text(f):
    return re.sub(r"(?<!\\)%.*", "", f.read_text())
removed = [f.name for f in body if re.search(r"fig_(gestures|agents|knowledge)|fig:(gestures|agents|knowledge)", text(f))]
step("no removed figure in Sections 1-9", not removed, ", ".join(removed))
allsec = included + [PAPER / "sections" / "appendix_prompts.tex"]
expert = [f.name for f in allsec if re.search(r"expert[ _]review\b|expert-review(ed)?\b", text(f), re.I)]
step("no 'expert review' wording", not expert, ", ".join(expert))
names = {f.name: len(re.findall(r"gpt-6(\.1)?-(luna|terra)", text(f))) for f in body}
extra = {n: c for n, c in names.items() if c and not n.startswith("s6_")}
step("model names in Sections 1-9 only in Section 6, once each", not extra and names.get("s6_test.tex", 0) == 2,
     str(extra or names.get("s6_test.tex")))
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
    # The paper is two documents that read each other's .aux through xr-hyper (prefixes S- and M-). Build order, as
    # main.tex states: main, supplement, main, each with BibTeX. Both logs are checked after the last pass.
    docs = ["main"] + (["supplement", "main"] if (dst / "supplement.tex").exists() else [])
    for doc in docs:
        for args in (["pdflatex", "-interaction=nonstopmode", f"{doc}.tex"], ["bibtex", doc],
                     ["pdflatex", "-interaction=nonstopmode", f"{doc}.tex"], ["pdflatex", "-interaction=nonstopmode", f"{doc}.tex"]):
            subprocess.run(args, cwd=dst, capture_output=True, text=True)
    for doc in dict.fromkeys(docs):
        log = (dst / f"{doc}.log").read_text(errors="ignore")
        step(f"{doc}: clean compile without errors", (dst / f"{doc}.pdf").exists() and "\n! " not in log)
        step(f"{doc}: no undefined references or citations", "undefined" not in re.sub(r"Font shape .*? undefined", "", log))
        step(f"{doc}: no multiply defined labels", "multiply defined" not in log)
        big = [float(m) for m in re.findall(r"Overfull \\[hv]box \(([0-9.]+)pt too", log) if float(m) > 5]
        step(f"{doc}: no overfull box over 5pt", not big, ", ".join(f"{b}pt" for b in big))
print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
sys.exit(0 if ok else 1)
