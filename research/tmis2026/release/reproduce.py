"""Re-check the stored results of the paper from a clone. No model calls, no network.

    python3 release/reproduce.py [--keep] [--skip-latex]     (from research/tmis2026/; reproduce.sh calls this)

Every step prints one line, PASS, FAIL or SKIP, with a short reason. The exit status is 1 if any step fails.
Nothing in the checkout is changed: every output is written to a temporary folder and compared there.
Studies 1 and 2 are re-run by analysis/verify_paper.py inside a temporary copy of this folder, because that
script rewrites its outputs in place.

Guards against model calls: TMIS_MODEL is removed from the environment of every step, TMIS_BUDGET_USD is 0 (the
model client of Studies 1 and 2 then refuses any call that is not in its response cache), and the proxy variables
point to a closed local port, so an accidental request fails at once instead of reaching a server.

Where a script writes to a fixed path, this file loads the script and points that one path to the temporary
folder. It never edits the script on disk. If the line it redirects has changed, the step fails and says so.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TMIS = Path(__file__).resolve().parents[1]
REPO = TMIS.parents[1]
AN = TMIS / "analysis"
CLOSED = "http://127.0.0.1:9"  # nothing listens here; any request through the proxy fails immediately

RESULTS = []


# ----------------------------------------------------------------------------- helpers
def env():
    e = {k: v for k, v in os.environ.items() if k != "TMIS_MODEL"}
    e.update({"TMIS_BUDGET_USD": "0", "PYTHONDONTWRITEBYTECODE": "1", "MPLBACKEND": "pdf",
              "HTTP_PROXY": CLOSED, "HTTPS_PROXY": CLOSED, "http_proxy": CLOSED, "https_proxy": CLOSED,
              "ALL_PROXY": CLOSED, "NO_PROXY": "", "no_proxy": ""})
    return e


def run(cmd, cwd, timeout=3600):
    t = time.time()
    r = subprocess.run([str(c) for c in cmd], cwd=str(cwd), env=env(), capture_output=True, text=True, timeout=timeout)
    return r, time.time() - t


def tail(r, n=300):
    s = (r.stderr or "").strip() or (r.stdout or "").strip()
    return s[-n:].replace("\n", " | ")


def report(name, status, detail="", secs=None):
    RESULTS.append((name, status))
    t = f" ({secs:.0f} s)" if secs is not None and secs >= 1 else ""
    print(f"{status:<4} {name}{t}" + (f" - {detail}" if detail else ""), flush=True)


def same(a, b):
    a, b = Path(a), Path(b)
    if not a.exists():
        return False, f"{a.name} was not written"
    if not b.exists():
        return False, f"stored file {b} is missing"
    if a.read_bytes() == b.read_bytes():
        return True, ""
    la, lb = a.read_text(errors="replace").splitlines(), b.read_text(errors="replace").splitlines()
    diff = sum(x != y for x, y in zip(la, lb)) + abs(len(la) - len(lb))
    return False, f"{b.relative_to(REPO)} differs ({diff} lines)"


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def prefix_hash_found(path, digest):
    """True if `digest` is the SHA-256 of a prefix of the file that ends at a line break (an append-only ledger that
    grew after an analysis recorded its hash)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for line in f:
            h.update(line)
            if h.copy().hexdigest() == digest:
                return True
    return False


def ledger_growth_only(new_inputs, old_inputs):
    """The recorded input hashes differ only for development ledgers (runs/**/ledger_dev_*.jsonl) that have grown by
    appended lines since the stored analysis ran: the stored hash is that of a line-ending prefix of the current file and
    the new hash is the current file's. Returns (ok, list of such ledgers)."""
    keys = sorted(k for k in set(new_inputs) | set(old_inputs) if new_inputs.get(k) != old_inputs.get(k))
    grown = []
    for k in keys:
        f = TMIS / k
        if not (k.startswith("runs/") and Path(k).name.startswith("ledger_dev_") and f.is_file()):
            return False, keys
        if new_inputs.get(k) != sha256(f) or not prefix_hash_found(f, old_inputs.get(k, "")):
            return False, keys
        grown.append(k)
    return True, grown


def same_json_but_ledgers(new_path, old_path, inputs_path):
    """Compare two analysis JSON files; differences in the recorded hashes of development ledgers that only grew by
    appended lines are accepted and named."""
    ok, why = same(new_path, old_path)
    if ok:
        return True, ""
    a, b = json.loads(Path(new_path).read_text()), json.loads(Path(old_path).read_text())
    ia, ib = a, b
    for k in inputs_path:
        ia, ib = ia[k], ib[k]
    good, grown = ledger_growth_only(ia, ib)
    if not good:
        return False, why
    for k in grown:
        ia[k] = ib[k]
    if a != b:
        return False, why
    return True, ("equal except the recorded hash of " + ", ".join(grown) + ", which grew by appended development rows "
                  "after the analysis ran (the recorded version is a byte prefix of the current file)")


def script_step(name, cmd, cwd=TMIS, timeout=3600):
    r, s = run(cmd, cwd, timeout)
    report(name, "PASS" if r.returncode == 0 else "FAIL", "" if r.returncode == 0 else f"exit {r.returncode}: {tail(r)}", s)
    return r


# ----------------------------------------------------------------------------- child tasks (run in their own process)
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def exec_redirected(path, line, new_line):
    """Run a script whose work happens at import, with one assignment line replaced. Fails if the line is not
    there exactly once."""
    src = Path(path).read_text()
    if src.count(line) != 1:
        raise SystemExit(f"{Path(path).name}: the line to redirect was not found exactly once: {line}")
    code = compile(src.replace(line, new_line), str(path), "exec")
    sys.path.insert(0, str(Path(path).parent))
    exec(code, {"__name__": "__main__", "__file__": str(path)})


def load_patched(path, name, out, writes):
    """Load a script as a module with each of its output lines `(HERE / "x").write_text` pointed to the folder `out`.
    Fails if a line is not there exactly once. Inputs are still read from the analysis folder."""
    src = Path(path).read_text()
    for w in writes:
        if src.count(w) != 1:
            raise SystemExit(f"{Path(path).name}: the output line was not found exactly once: {w}")
        src = src.replace(w, w.replace("(HERE / ", "(_REPRODUCE_OUT / "))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(name, loader=None))
    mod.__file__ = str(path)
    mod._REPRODUCE_OUT = Path(out)
    sys.modules[name] = mod
    sys.path.insert(0, str(Path(path).parent))
    exec(compile(src, str(path), "exec"), mod.__dict__)
    return mod


def child(task, out):
    out = Path(out)
    sys.path.insert(0, str(AN))
    if task == "posthoc":
        m = load(AN / "study3_posthoc.py", "study3_posthoc")
        m.OUT = out / "study3_posthoc"
        m.main()
    elif task == "numbers_study3":
        exec_redirected(AN / "make_numbers_study3.py", 'OUT = TMIS / "paper" / "results" / "numbers_study3.tex"',
                        f"OUT = Path({str(out / 'numbers_study3.tex')!r})")
    elif task == "numbers_sharc":
        exec_redirected(AN / "make_numbers_sharc.py", 'OUT = HERE.parent / "paper" / "results" / "numbers_sharc.tex"',
                        f"OUT = Path({str(out / 'numbers_sharc.tex')!r})")
    elif task in ("fig_s6", "fig_s4", "figures", "fig_review"):
        m = load(AN / f"{task}.py", task)
        m.FIG = out
        names = {"fig_s6": ["fig_main", "fig_cost"], "fig_s4": ["fig_pipeline", "fig_hero", "fig_gestures"],
                 "figures": ["fig_reconverge", "fig_fate", "fig_outcomes", "fig_trace", "fig_models", "fig_knowledge",
                             "fig_study2"], "fig_review": ["fig_families"]}[task]
        for n in names:
            getattr(m, n)()
    elif task == "review":
        m = load(AN / "study3_review.py", "study3_review")
        m.OUT = out / "study3_review"
        m.main()
    elif task == "numbers_study3_review":
        exec_redirected(AN / "make_numbers_study3_review.py",
                        'OUT = TMIS / "paper" / "results" / "numbers_study3_review.tex"',
                        f"OUT = Path({str(out / 'numbers_study3_review.tex')!r})")
    elif task == "feedback":
        m = load(AN / "study3_feedback.py", "study3_feedback")
        m.OUT = out / "study3_feedback"
        m.main([])
    elif task == "numbers_study3_feedback":
        exec_redirected(AN / "make_numbers_study3_feedback.py",
                        'OUT = TMIS / "paper" / "results" / "numbers_study3_feedback.tex"',
                        f"OUT = Path({str(out / 'numbers_study3_feedback.tex')!r})")
    elif task == "decomposition":
        m = load_patched(AN / "decomposition.py", "decomposition", out,
                         ['(HERE / "decomposition.json").write_text', '(HERE / "decomposition.md").write_text'])
        m.main(None)
    elif task == "lint_followup":
        m = load_patched(AN / "lint_followup.py", "lint_followup", out,
                         ['(HERE / "lint_followup.json").write_text', '(HERE / "lint_followup.md").write_text',
                          '(HERE / "posthoc_numbers.tex").write_text'])
        m.main()
    elif task == "posthoc_macros":
        # Model-free and cache-free: the macro writer of lint_followup.py applied to the stored JSON files.
        m = load(AN / "lint_followup.py", "lint_followup")
        tex = m.macros(json.loads((AN / "lint_followup.json").read_text()), json.loads((AN / "decomposition.json").read_text()))
        (out / "posthoc_numbers.tex").write_text(tex)
    elif task == "baseline_check":
        m = load_patched(TMIS / "study4" / "baseline_check" / "analyse.py", "baseline_check_analyse", out,
                         ['(HERE / "REPORT.json").write_text'])
        m.main()
    elif task == "numbers_baseline_check":
        exec_redirected(AN / "make_numbers_baseline_check.py",
                        'OUT = TMIS / "paper" / "results" / "numbers_baseline_check.tex"',
                        f"OUT = Path({str(out / 'numbers_baseline_check.tex')!r})")
    elif task == "numbers_study4_dev":
        exec_redirected(AN / "make_numbers_study4_dev.py",
                        'OUT = TMIS / "paper" / "results" / "numbers_study4_dev.tex"',
                        f"OUT = Path({str(out / 'numbers_study4_dev.tex')!r})")
    elif task == "dev_probe":
        sys.path.insert(0, str(TMIS / "dev_probe"))
        m = load(TMIS / "dev_probe" / "build.py", "dev_probe_build")
        m.HERE = out
        m.main()
    else:
        raise SystemExit(f"unknown task {task}")


def child_step(name, task, out, timeout=3600):
    return script_step(name, [sys.executable, __file__, "--child", task, str(out)], timeout=timeout)


# ----------------------------------------------------------------------------- steps
def data_steps(tmp):
    script_step("data: fresh2 (Study 3) checks and manifest", [sys.executable, "fresh2/check.py"])

    m = json.loads((TMIS / "fresh" / "MANIFEST.json").read_text())
    bad = [f for f, h in m["files"].items() if not (TMIS / "fresh" / f).is_file() or sha256(TMIS / "fresh" / f) != h]
    report("data: fresh (Study 2) manifest hashes", "FAIL" if bad else "PASS",
           f"{len(bad)} of {len(m['files'])} files differ or are missing: {', '.join(bad[:5])}" if bad
           else f"{len(m['files'])} files")
    script_step("data: fresh (Study 2) tenancy oracle check", [sys.executable, "fresh/tenancy/oracle_check.py"])

    out = tmp / "dev_probe"
    out.mkdir()
    r = child_step("data: dev_probe rebuild (build.py into a temporary folder)", "dev_probe", out)
    if r.returncode == 0:
        diffs = [n for n in ("claims.json", "references.json") if not same(out / n, TMIS / "dev_probe" / n)[0]]
        report("data: dev_probe rebuilt files equal the stored ones", "FAIL" if diffs else "PASS", ", ".join(diffs))

    for d in ("casepath-tenancy-claims", "casepath-theft-pairs"):
        script_step(f"data: data/{d} (Study 1) verify.py", [sys.executable, REPO / "data" / d / "verify.py"])

    sums = (TMIS / "rule_review" / "SHA256SUMS").read_text().split("\n")
    bad = [f for h, f in (l.split(None, 1) for l in sums if l.strip()) if sha256(TMIS / "rule_review" / f.strip()) != h]
    report("data: rule_review SHA256SUMS", "FAIL" if bad else "PASS", ", ".join(bad))


def product_step(tmp):
    spec = json.loads((AN / "study3_spec.json").read_text())["product"]
    out = tmp / "product"
    out.mkdir()
    arch = subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", spec["commit"], spec["subdir"]],
                          capture_output=True)
    if arch.returncode:
        report("product: tested commit is in the clone", "FAIL",
               f"git archive {spec['commit'][:8]} failed; fetch branch claude/casepath-internal-paper-sync-20261110d")
        return False
    subprocess.run(["tar", "-x", "-C", str(out)], input=arch.stdout, check=True)
    report("product: tested commit is in the clone", "PASS", spec["commit"][:12])
    r, s = run([sys.executable, "-m", "casepath", "parity"], out / spec["subdir"])
    try:
        got = json.loads(r.stdout)["source_tree_sha256"]
    except Exception:  # noqa: BLE001
        report("product: parity source-tree hash", "FAIL", tail(r), s)
        return True
    ok = got == spec["source_tree_sha256"]
    report("product: parity source-tree hash", "PASS" if ok else "FAIL", f"{got[:16]}…" + ("" if ok else " expected "
                                                                                           + spec["source_tree_sha256"][:16]), s)
    r, s = run([sys.executable, AN / "check_fragment.py"], TMIS)
    counts = [l[5:] for l in r.stdout.splitlines() if l.startswith(("PASS counts", "FAIL counts"))]
    report("product: Appendix A fragment check (analysis/check_fragment.py)", "PASS" if r.returncode == 0 else "FAIL",
           ("; ".join(counts) + "; theft 5000 random assignments") if r.returncode == 0 else tail(r, 400), s)
    return True


def study3_steps(tmp):
    out = tmp / "study3"
    out.mkdir()
    r = script_step("study 3: analysis/study3.py --data fresh2 --label confirm",
                    [sys.executable, AN / "study3.py", "--data", "fresh2", "--label", "confirm", "--out", out / "s3"])
    if r.returncode == 0:
        for ext in (".json", ".md"):
            if ext == ".json":
                ok, why = same_json_but_ledgers(out / "s3.json", AN / "study3_results_fresh2_confirm.json", ["inputs", "files_read"])
            else:
                ok, why = same(out / f"s3{ext}", AN / f"study3_results_fresh2_confirm{ext}")
            report(f"study 3: results{ext} equal the stored file", "PASS" if ok else "FAIL", why)
    r = child_step("study 3: analysis/study3_posthoc.py", "posthoc", out)
    if r.returncode == 0:
        for ext in (".json", ".md"):
            ok, why = same(out / f"study3_posthoc{ext}", AN / f"study3_posthoc{ext}")
            report(f"study 3: post-hoc {ext} equals the stored file", "PASS" if ok else "FAIL", why)
    r = child_step("study 3: analysis/make_numbers_study3.py", "numbers_study3", out)
    if r.returncode == 0:
        ok, why = same(out / "numbers_study3.tex", TMIS / "paper" / "results" / "numbers_study3.tex")
        report("study 3: numbers_study3.tex equals the stored file", "PASS" if ok else "FAIL", why)
    fig = tmp / "figures"
    fig.mkdir()
    for task, names, label in (("fig_s6", ["fig_main", "fig_cost"], "study 3 figures (fig_s6.py)"),
                               ("fig_s4", ["fig_pipeline", "fig_hero", "fig_gestures"], "section 4 figures (fig_s4.py)")):
        r = child_step(f"{label} build", task, fig)
        if r.returncode == 0:
            miss = [n for n in names if not (fig / f"{n}.pdf").is_file() or (fig / f"{n}.pdf").stat().st_size == 0]
            report(f"{label}: {len(names)} PDFs written", "FAIL" if miss else "PASS", ", ".join(miss))


# Parts of analysis/study3_review.py that read the product's response cache (runs/product/cache, ignored by git): the
# readings in R3 and the cost split by component in R7. Everything else in the output must reproduce without it.
REVIEW_CACHE_PARTS = [("R3", d, k) for d in ("casepath", "casepath_checklist")
                      for k in ("readings_agreement", "readings_per_case_run", "all_readings_agree_on_wrong_value",
                                "admitted_wrong_with_all_readings_agreeing")] + [("R7", "cost"), ("cache_missing",)]
REVIEW_CACHE_MD = ("## R3.", "## R7.")


def _pop(d, path):
    for k in path[:-1]:
        d = d[k]
    return d.pop(path[-1])


def _md_sections(text):
    """Markdown split at '## ' headings; the line that counts missing cache files is dropped from 'Inputs'."""
    parts, cur = {}, "head"
    for line in text.splitlines():
        if line.startswith("## "):
            cur = line
        if "response-cache files missing" in line:
            continue
        parts.setdefault(cur, []).append(line)
    return parts


def review_steps(tmp):
    out = tmp / "review"
    out.mkdir()
    r = child_step("study 3 review: analysis/study3_review.py", "review", out)
    if r.returncode == 0:
        new = json.loads((out / "study3_review.json").read_text())
        old = json.loads((AN / "study3_review.json").read_text())
        missing = new.get("cache_missing")
        a, b = json.loads(json.dumps(new)), json.loads(json.dumps(old))
        for p in REVIEW_CACHE_PARTS:
            _pop(a, p)
            _pop(b, p)
        lg_ok, grown = ledger_growth_only(a.get("inputs", {}), b.get("inputs", {}))
        if lg_ok:
            a["inputs"] = b["inputs"]
        diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        report("study 3 review: JSON equal without the cache-dependent parts", "FAIL" if diff else "PASS",
               f"differ: {', '.join(diff)}" if diff else f"{len(a)} top-level entries; R3 and R7 compared without "
                                                          "their cache parts")
        ma, mb = _md_sections((out / "study3_review.md").read_text()), _md_sections((AN / "study3_review.md").read_text())
        mdiff = [k for k in set(ma) | set(mb) if not k.startswith(REVIEW_CACHE_MD) and ma.get(k) != mb.get(k)]
        report("study 3 review: .md equal outside sections R3 and R7", "FAIL" if mdiff else "PASS", ", ".join(mdiff)[:300])
        if missing == 0:
            for ext in (".json", ".md"):
                if ext == ".json":
                    ok, why = same_json_but_ledgers(out / "study3_review.json", AN / "study3_review.json", ["inputs"])
                else:
                    ok, why = same(out / f"study3_review{ext}", AN / f"study3_review{ext}")
                report(f"study 3 review: whole {ext} equals the stored file (cache present)", "PASS" if ok else "FAIL", why)
        else:
            msg = (f"{missing} response-cache files missing (runs/product/cache is not in git); the readings of R3 and "
                   "the cost split of R7 were not compared")
            for ext in (".json", ".md"):
                report(f"study 3 review: cache-dependent parts of {ext}", "SKIP", msg)
    r = child_step("study 3 review: analysis/make_numbers_study3_review.py", "numbers_study3_review", out)
    if r.returncode == 0:
        ok, why = same(out / "numbers_study3_review.tex", TMIS / "paper" / "results" / "numbers_study3_review.tex")
        report("study 3 review: numbers_study3_review.tex equals the stored file", "PASS" if ok else "FAIL", why)
    fig = tmp / "figures"
    fig.mkdir(exist_ok=True)
    r = child_step("study 3 review figure (fig_review.py) build", "fig_review", fig)
    if r.returncode == 0:
        ok = (fig / "fig_families.pdf").is_file() and (fig / "fig_families.pdf").stat().st_size > 0
        report("study 3 review figure: fig_families.pdf written", "PASS" if ok else "FAIL")


PRODUCT_CACHE = TMIS / "runs" / "product" / "cache"


def cache_present():
    return PRODUCT_CACHE.is_dir() and any(PRODUCT_CACHE.glob("*.json"))


def feedback_steps(tmp):
    """The checks added after the outside review (study3_feedback.py, decomposition.py, lint_followup.py). All three read
    the product's response cache (runs/product/cache, ignored by git); none makes a model call (the lint's mutation arm was
    run once in development and is read from its stored runs and ledger). With the cache archive in place they are re-run
    into the temporary folder and compared byte for byte; without it they are skipped, and only the model-free and
    cache-free parts are re-checked: the macros regenerated from the stored JSON files, and the tests that need no cache."""
    out = tmp / "feedback"
    out.mkdir()
    paper = TMIS / "paper" / "results"
    if cache_present():
        for task, label, files in (("feedback", "analysis/study3_feedback.py", ["study3_feedback.json", "study3_feedback.md"]),
                                   ("decomposition", "analysis/decomposition.py", ["decomposition.json", "decomposition.md"]),
                                   ("lint_followup", "analysis/lint_followup.py",
                                    ["lint_followup.json", "lint_followup.md", "posthoc_numbers.tex"])):
            r = child_step(f"study 3 feedback: {label} (cache present)", task, out)
            if r.returncode == 0:
                for f in files:
                    ok, why = same(out / f, AN / f)
                    report(f"study 3 feedback: {f} equals the stored file", "PASS" if ok else "FAIL", why)
    else:
        msg = ("runs/product/cache is not present (not in git; offered as a separate archive); the readings "
               "these scripts recompute were not re-checked")
        for label in ("analysis/study3_feedback.py", "analysis/decomposition.py", "analysis/lint_followup.py"):
            report(f"study 3 feedback: {label} re-run", "SKIP", msg)
    r = child_step("study 3 feedback: analysis/make_numbers_study3_feedback.py (from the stored JSON)", "numbers_study3_feedback", out)
    if r.returncode == 0:
        ok, why = same(out / "numbers_study3_feedback.tex", paper / "numbers_study3_feedback.tex")
        report("study 3 feedback: numbers_study3_feedback.tex equals the stored file", "PASS" if ok else "FAIL", why)
    r = child_step("study 3 feedback: post-hoc macros from the stored lint_followup.json and decomposition.json",
                   "posthoc_macros", out)
    if r.returncode == 0:
        for target in (AN / "posthoc_numbers.tex", paper / "numbers_posthoc.tex"):
            ok, why = same(out / "posthoc_numbers.tex", target)
            report(f"study 3 feedback: {target.relative_to(TMIS)} equals the regenerated macros", "PASS" if ok else "FAIL", why)
    script_step("tests: analysis/test_posthoc.py", [sys.executable, "test_posthoc.py"], cwd=AN)
    if cache_present():
        script_step("tests: analysis/test_study3_feedback.py", [sys.executable, "test_study3_feedback.py"], cwd=AN)
    else:
        names = [f"test_study3_feedback.{c}" for c in ("ClaimType", "Lines", "Orders", "Readings", "Votes", "AltReference",
                                                       "Amendments")]
        names += [f"test_study3_feedback.F5Hook.{t}" for t in ("test_registered_reference_reproduces_stored_numbers",
                                                              "test_h4_self_consistency_cluster_counts",
                                                              "test_perturbed_copy_moves_the_numbers",
                                                              "test_one_document_changed_by_hand")]
        script_step("tests: analysis/test_study3_feedback.py without the replay test, which reads the cache",
                    [sys.executable, "-m", "unittest"] + names, cwd=AN)


def baseline_check_steps(tmp):
    """The fair-baseline check of Study 4, step 1 (post hoc, on Study 3's data): study4/baseline_check/analyse.py scores
    the stored plans under study4/baseline_check/runs/ and Study 3's stored plans with the registered scorers. It makes
    no model call and reads no response cache; it is re-run into the temporary folder and its REPORT.json compared byte
    for byte. Then the macros are regenerated from the stored REPORT.json and compared, and their test runs."""
    out = tmp / "baseline_check"
    out.mkdir()
    r = child_step("study 4 step 1: study4/baseline_check/analyse.py", "baseline_check", out)
    if r.returncode == 0:
        ok, why = same(out / "REPORT.json", TMIS / "study4" / "baseline_check" / "REPORT.json")
        report("study 4 step 1: REPORT.json equals the stored file", "PASS" if ok else "FAIL", why)
    r = child_step("study 4 step 1: analysis/make_numbers_baseline_check.py (from the stored REPORT.json)",
                   "numbers_baseline_check", out)
    if r.returncode == 0:
        ok, why = same(out / "numbers_baseline_check.tex", TMIS / "paper" / "results" / "numbers_baseline_check.tex")
        report("study 4 step 1: numbers_baseline_check.tex equals the stored file", "PASS" if ok else "FAIL", why)
    script_step("tests: analysis/test_baseline_check.py", [sys.executable, "test_baseline_check.py"], cwd=AN)


def study4_dev_steps(tmp):
    """The benchmark from cited public text (Study 4, step 2; development material): the macros are regenerated from
    the stored records under study4/ (rule sets, development manifests, clean-room comparison, blind-check rounds, lint
    report, diagnosis and revision records) and compared byte for byte; then their test runs. No model call and no
    response cache: the runs behind these records are stored results, not re-run here."""
    out = tmp / "study4_dev"
    out.mkdir()
    r = child_step("study 4 step 2: analysis/make_numbers_study4_dev.py (from the stored study4/ records)",
                   "numbers_study4_dev", out)
    if r.returncode == 0:
        ok, why = same(out / "numbers_study4_dev.tex", TMIS / "paper" / "results" / "numbers_study4_dev.tex")
        report("study 4 step 2: numbers_study4_dev.tex equals the stored file", "PASS" if ok else "FAIL", why)
    script_step("tests: analysis/test_study4_dev.py", [sys.executable, "test_study4_dev.py"], cwd=AN)


def test_steps():
    for t in ("test_study3.py", "test_study3_review.py", "test_study2.py"):
        script_step(f"tests: analysis/{t}", [sys.executable, t], cwd=AN)


def copy_for_verify(tmp):
    """A copy of research/tmis2026 at the same depth, with data/ and casepath-api/ linked from the checkout."""
    root = tmp / "s12"
    dst = root / "research" / "tmis2026"
    skip = {TMIS / "runs" / "product" / "cache", TMIS / "runs" / "cache",
            TMIS / "deliverables", TMIS / "paper" / "figures" / "ui", TMIS / "release"}

    def ignore(d, names):
        return [n for n in names if Path(d) / n in skip or n == "__pycache__"]
    shutil.copytree(TMIS, dst, ignore=ignore, symlinks=True)
    for name in ("data", "casepath-api"):
        (root / name).symlink_to(REPO / name)
    subprocess.run(["tar", "-xzf", str(TMIS / "runs" / "responses_cache.tar.gz"), "-C", str(dst / "runs")], check=True)
    return dst


def study12_steps(tmp, skip_latex):
    t = time.time()
    dst = copy_for_verify(tmp)
    report("studies 1-2: temporary copy with the Study 1 response cache unpacked", "PASS", "", time.time() - t)
    r, s = run([sys.executable, "verify_paper.py"], dst / "analysis", timeout=7200)
    lines = [l for l in r.stdout.splitlines() if l.startswith(("PASS ", "FAIL "))]
    ran = [l for l in lines if " ran " in l]
    failed_runs = [l[5:] for l in ran if l.startswith("FAIL")]
    report(f"studies 1-2: verify_paper.py ran {len(ran)} analysis scripts", "FAIL" if failed_runs or not ran else "PASS",
           "; ".join(failed_runs)[:300] if failed_runs else ("no script ran: " + tail(r) if not ran else ""), s)

    latex = shutil.which("pdflatex") and shutil.which("bibtex")
    for l in lines:
        if " ran " in l:
            continue
        what = l[5:]
        compile_line = what.startswith(("main:", "supplement:"))
        if compile_line and (skip_latex or not latex):
            report(f"paper: {what.split(' — ')[0]}", "SKIP", "--skip-latex" if skip_latex else "pdflatex/bibtex not installed")
        else:
            report(("paper: " if compile_line or "citation" in what or "Section" in what or "wording" in what
                    else "verify_paper: ") + what.split(" — ")[0], l[:4], what.split(" — ")[1][:300] if " — " in what else "")
    if not any(l[5:].startswith("supplement:") for l in lines) and (TMIS / "paper" / "supplement.tex").exists():
        report("paper: supplement built", "FAIL", "verify_paper.py did not build supplement.tex")

    out = tmp / "s12_out"
    out.mkdir()
    r = child_step("studies 1-2: analysis/make_numbers_sharc.py", "numbers_sharc", out)
    if r.returncode == 0:
        ok, why = same(out / "numbers_sharc.tex", TMIS / "paper" / "results" / "numbers_sharc.tex")
        report("studies 1-2: numbers_sharc.tex equals the stored file", "PASS" if ok else "FAIL", why)
    fig = tmp / "figures"
    names = ["fig_reconverge", "fig_fate", "fig_outcomes", "fig_trace", "fig_models", "fig_knowledge", "fig_study2"]
    r = child_step("studies 1-2 figures (figures.py) build", "figures", fig)
    if r.returncode == 0:
        miss = [n for n in names if not (fig / f"{n}.pdf").is_file()]
        report(f"studies 1-2 figures: {len(names)} PDFs written", "FAIL" if miss else "PASS", ", ".join(miss))


def preflight():
    v = sys.version_info
    report("python version", "PASS" if v >= (3, 10) else "FAIL", f"{v.major}.{v.minor}.{v.micro}" +
           ("" if v >= (3, 10) else "; 3.10 or later is needed"))
    inside = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if inside.stdout.strip() != "true":
        report("git checkout", "FAIL", "run this in a git clone: the Study 3 data guard and the product evaluator use git")
        return False
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    report("git checkout", "PASS", f"HEAD {head[:12]}")
    miss = [mod for mod in ("matplotlib", "numpy", "PIL") if importlib.util.find_spec(mod) is None]
    report("packages for the figures", "FAIL" if miss else "PASS",
           f"missing {', '.join(miss)}; pip install -r requirements-reproduce.txt" if miss else "")
    # Study 1 reads the PDF attachments with pypdf; the text, and so the key of every cached model response, depends
    # on its version. Another version makes the cached responses unreachable and the Study 1 re-analysis fails.
    try:
        import pypdf
        version = pypdf.__version__
    except ImportError:
        version = None
    report("pypdf 5.9.0 for the Study 1 attachments", "PASS" if version == "5.9.0" else "FAIL",
           "" if version == "5.9.0" else f"found {version or 'none'}; pip install -r requirements-reproduce.txt")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keep", action="store_true", help="keep the temporary folder and print its path")
    ap.add_argument("--skip-latex", action="store_true", help="do not count the paper compile (it still runs inside verify_paper.py)")
    ap.add_argument("--child", nargs=2, metavar=("TASK", "OUT"), help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.child:
        return child(*a.child)
    start = time.time()
    tmp = Path(tempfile.mkdtemp(prefix="tmis-reproduce-"))
    try:
        if preflight():
            data_steps(tmp)
            product_step(tmp)
            study3_steps(tmp)
            review_steps(tmp)
            feedback_steps(tmp)
            baseline_check_steps(tmp)
            study4_dev_steps(tmp)
            test_steps()
            study12_steps(tmp, a.skip_latex)
    finally:
        if a.keep:
            print("temporary folder kept:", tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    fails = [n for n, s in RESULTS if s == "FAIL"]
    skips = [n for n, s in RESULTS if s == "SKIP"]
    print(f"{len(RESULTS) - len(fails) - len(skips)} passed, {len(fails)} failed, {len(skips)} skipped "
          f"in {time.time() - start:.0f} s")
    print("ALL STEPS PASSED" if not fails else "SOME STEPS FAILED: " + "; ".join(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
