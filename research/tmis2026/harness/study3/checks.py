"""Preflight checks of run_all.py. Each returns (ok, one line, details). No model calls, no data access.

(a) plan       ANALYSIS_PLAN_STUDY3.md committed unmodified (fresh2/guard.py's own plan_committed).
(b) product    the worktree in CASEPATH_PRODUCT is clean, at the spec's commit, and its `python -m casepath parity`
               source-tree hash equals the spec's.
(c) templates  the tenancy rule templates of the data have the SHA-256 of those of fresh/ (both MANIFEST.json
               files); then the converted workflows of harness/product/workflows/fresh-serial-sync apply unchanged,
               otherwise they are converted again (convert.py --sync logic) into harness/study3/workflows/.
(d) compare    harness/product/compare.py (every true/false/unknown assignment of each tenancy family) and
               compare_theft.py (3,000 random assignments) pass against the product worktree.

    python checks.py compare --product WT --out DIR     (internal: runs compare.py with its result file in DIR)
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib  # noqa: E402

TEMPLATES = "tenancy/rules/static-rule-templates-v3-silence.json"
FRESH_CATALOGUE = lib.PRODUCT_DIR / "workflows" / "fresh-serial-sync"


def _guard():
    """fresh2/guard.py, compiled from its source text (no bytecode cache read or written; it opens no data)."""
    import types
    path = lib.TMIS / "fresh2" / "guard.py"
    mod = types.ModuleType("fresh2_guard")
    mod.__file__ = str(path)
    exec(compile(path.read_text(), str(path), "exec"), mod.__dict__)
    return mod


def plan():
    g = _guard()
    ok = g.plan_committed()
    return ok, f"check (a) plan: {g.PLAN.name} committed unmodified: {'yes' if ok else 'NO'}", {"message": g.MESSAGE}


def parity(product, catalogue, env):
    """The product's own manifest, run in the worktree with the run settings as its environment."""
    full = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", **env}
    cli = subprocess.run([sys.executable, "-m", "casepath", "parity", "--catalogue", str(catalogue)],
                         cwd=str(Path(product) / "casepath-internal"), env=full, capture_output=True, text=True)
    if cli.returncode:
        raise RuntimeError(f"parity failed: {cli.stderr.strip()[-300:]}")
    return json.loads(cli.stdout)


def resolved_settings(product, env):
    """Every setting the product reads, as its own load_settings resolves them from the run's environment (defaults
    included). Who may sign in is reduced to a count, as the product's parity output does."""
    code = ("import json, dataclasses; from casepath.config import load_settings; import os; "
            "s = dataclasses.asdict(load_settings(dict(os.environ))); "
            "s['allowed_users'] = f\"{len(s.get('allowed_users') or [])} named users\"; "
            "print(json.dumps(s, default=lambda x: sorted(x) if isinstance(x, (set, frozenset)) else str(x), sort_keys=True))")
    full = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", **env}
    cli = subprocess.run([sys.executable, "-c", code], cwd=str(Path(product) / "casepath-internal"), env=full, capture_output=True, text=True)
    if cli.returncode:
        raise RuntimeError(f"settings failed: {cli.stderr.strip()[-300:]}")
    return json.loads(cli.stdout)


def product(spec, wt, catalogue, env):
    want = spec.get("product") or {}
    if not wt or not (Path(wt) / "casepath-internal" / "casepath").is_dir():
        return False, f"check (b) product: CASEPATH_PRODUCT is not a product worktree ({wt})", {}
    dirty = lib.git("status", "--porcelain", "--untracked-files=all", cwd=wt)
    head = lib.git("rev-parse", "HEAD", cwd=wt)
    man = parity(wt, catalogue, env)
    tree = man.get("source_tree_sha256")
    modified = (man.get("git") or {}).get("package_modified")
    evaluators = {r: ((spec.get("product_evaluator") or {}).get(r) or {}).get("package", {}).get("commit") for r in lib.REGIMES}
    problems = []
    if dirty or modified:
        problems.append("worktree not clean")
    if head != want.get("commit"):
        problems.append(f"HEAD {head[:12]} is not the spec's commit {want.get('commit')}")
    if tree != want.get("source_tree_sha256"):
        problems.append(f"source tree {str(tree)[:12]} is not the spec's {str(want.get('source_tree_sha256'))[:16]}")
    if any(c != want.get("commit") for c in evaluators.values()):
        problems.append(f"product_evaluator commits {sorted(set(map(str, evaluators.values())))} are not product.commit")
    line = (f"check (b) product: {wt} at {head[:12]}, {'clean' if not (dirty or modified) else 'MODIFIED'}, source tree "
            f"{str(tree)[:16]}: " + ("matches the spec" if not problems else "; ".join(problems)))
    return not problems, line, {"head": head, "clean": not (dirty or modified), "parity": man}


def templates(data):
    """(ok, line, details with the tenancy catalogue to use and its file hashes)."""
    def h(which):
        return (json.loads((lib.TMIS / which / "MANIFEST.json").read_text()).get("files") or {}).get(TEMPLATES)
    mine, base = h(data), h("fresh")
    same = mine is not None and mine == base
    cat = FRESH_CATALOGUE if same else lib.HERE / "workflows" / f"{data}-serial-sync"
    line = (f"check (c) templates: {data} {str(mine)[:16]} vs fresh {str(base)[:16]}: "
            + ("identical, workflows/fresh-serial-sync apply unchanged" if same else f"DIFFERENT, convert into {cat.relative_to(lib.TMIS)}"))
    return mine is not None, line, {"same": same, "catalogue": cat, "data_sha256": mine, "fresh_sha256": base}


def convert_tenancy(data, out, wt):
    """Only if (c) finds different templates. convert.write fixes its pack to original|fresh, so its loop is copied:
    convert.convert(templates, family, "serial", sync=True) for each family, validated with the product's
    validate_workflow, written as convert.write writes. Templates come through common.data, so the guard applies."""
    code = f"""
import json, sys
sys.dont_write_bytecode = True
sys.path[:0] = [{str(lib.PRODUCT_DIR)!r}, {str(lib.HARNESS / 'v2')!r}, {str(Path(wt) / 'casepath-internal')!r}]
from pathlib import Path
import convert, common
from casepath.process.workflows import validate_workflow
t = common.data("tenancy", {data!r}).templates()
out = Path({str(out)!r}); out.mkdir(parents=True, exist_ok=True)
for family in convert.FAMILIES:
    wf = convert.convert(t, family, "serial", True)
    validate_workflow(wf)
    (out / f"{{family}}.json").write_text(json.dumps(wf, ensure_ascii=False, indent=1, sort_keys=True) + "\\n")
"""
    subprocess.run([sys.executable, "-c", code], check=True)
    return catalogue_hashes(out)


def catalogue_hashes(cat):
    return {p.name: lib.sha256_file(p) for p in sorted(Path(cat).glob("*.json"))}


def catalogue_sha256(cat):
    return hashlib.sha256(json.dumps(catalogue_hashes(cat), sort_keys=True).encode()).hexdigest()


def compare(wt, out):
    """(ok, line, details). compare.py prints counts and never fails by itself: it passes when every document
    decision agrees with exact deferral. compare_theft.py exits 1 on any difference."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    a = subprocess.run([sys.executable, str(lib.HERE / "checks.py"), "compare", "--product", str(wt), "--out", str(out)],
                       capture_output=True, text=True)
    tot = None
    res = out / "results" / "semantic_serial.json"
    if a.returncode == 0 and res.exists():
        tot = json.loads(res.read_text())["summary"]["total"]
    ok_t = tot is not None and tot["agree_exact"] == tot["doc_decisions"]
    b = subprocess.run([sys.executable, str(lib.PRODUCT_DIR / "compare_theft.py"), "--product", str(wt)], capture_output=True, text=True,
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    ok_h = b.returncode == 0
    tail = " / ".join(x for x in b.stdout.strip().splitlines()[-2:])
    line = (f"check (d) compare: tenancy {tot['agree_exact'] if tot else '?'} of {tot['doc_decisions'] if tot else '?'} decisions agree "
            f"with exact deferral ({'pass' if ok_t else 'FAIL'}); theft {tail or b.stderr.strip()[-200:]} ({'pass' if ok_h else 'FAIL'})")
    return ok_t and ok_h, line, {"tenancy_total": tot, "theft_stdout": b.stdout.strip()[-1000:], "tenancy_file": str(res)}


def _compare_main(argv):
    """Runs harness/product/compare.py unchanged except that its result file goes to --out (module global HERE)."""
    i = argv.index("--product")
    wt, out = argv[i + 1], argv[argv.index("--out") + 1]
    sys.argv = ["compare.py", "--product", wt]  # compare.py reads --product from sys.argv at import
    sys.path.insert(0, str(lib.PRODUCT_DIR))
    import compare as C
    C.HERE = Path(out)
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        C.main("serial", None)


if __name__ == "__main__":
    if sys.argv[1:2] == ["compare"]:
        _compare_main(sys.argv[2:])
