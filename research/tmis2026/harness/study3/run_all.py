"""Study 3: run every design of analysis/study3_spec.json on both regimes with one command.

    CASEPATH_PRODUCT=<product worktree> <venv>/bin/python harness/study3/run_all.py --data fresh|fresh2 --label L
        [--designs a,b,...|all] [--k 3] [--limit N] [--cap-usd X] [--workers 6]

Writes exactly the files analysis/study3.py reads under runs/study3/<label>/ (store files, keys and fields from the
spec), plus MANIFEST.json (settings) and RUNLOG.jsonl (one line per invocation). Then:

    python3 analysis/study3.py --data <data> --label <label>

fresh2 (sealed): the driver refuses to start unless (a) ANALYSIS_PLAN_STUDY3.md is committed unmodified, (b) the
product worktree is clean, at the spec's commit and source-tree hash, (c) the tenancy templates match fresh/'s (else
the workflows are converted again) and (d) compare.py and compare_theft.py pass. On fresh the checks are reported,
not enforced. See README.md in this folder.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import checks  # noqa: E402
import lib  # noqa: E402


def say(lines, text):
    print(text, flush=True)
    lines.append(text)


def refuse(text):
    print(text, flush=True)
    e = SystemExit(2)
    e.text = text
    raise e


def count_entries(spec, unit_list, label):
    out = {}
    for d, r in unit_list:
        st = lib.store_of(spec, d, r, label)
        out[f"{d}/{r}"] = len(lib.read_json(st["path"]))
    return out


def failed_entries(spec, unit_list, label):
    out = []
    for d, r in unit_list:
        st = lib.store_of(spec, d, r, label)
        out += [f"{st['path'].name}: {k}" for k, e in sorted(lib.read_json(st["path"]).items()) if lib.failed(e)]
    return out


def settings_env(catalogue, model, extra):
    """The product's settings for a run (harness/product/run_api.settings_env, which names no secret) plus extra."""
    sys.path[:0] = [str(lib.PRODUCT_DIR), str(lib.HARNESS)]
    import run_api
    return {**run_api.settings_env("<temporary>", catalogue, model), **extra}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", required=True, choices=["fresh", "fresh2"])
    ap.add_argument("--label", required=True)
    ap.add_argument("--designs", default="all")
    ap.add_argument("--k", type=int, default=3, help="runs per case (self-consistency: 5 samples per run)")
    ap.add_argument("--limit", type=int, default=None, help="smoke tests: first N tenancy claims, texts of the first theft story")
    ap.add_argument("--cap-usd", type=float, default=None, help="spend cap of this invocation (stops cleanly between cases)")
    ap.add_argument("--workers", type=int, default=6, help="cases in parallel inside a design, as the existing runners do")
    ap.add_argument("--spec", default=str(lib.SPEC))
    a = ap.parse_args(argv)
    started = lib.now()
    spec = lib.load_spec(a.spec)
    sealed = a.data == "fresh2"
    lines = []

    # ---------------------------------------------------------------- (a) the analysis plan, first, before anything else
    if sealed:
        ok, line, det = checks.plan()
        say(lines, line)
        if not ok:
            refuse(det["message"])
    else:
        say(lines, "check (a) plan: not required on development data (fresh)")
    if sealed and a.limit:
        refuse("--limit is for smoke tests on development data; a fresh2 run covers every case")
    if sealed and a.cap_usd is None:
        refuse("--cap-usd is required on fresh2")

    try:
        return run(a, spec, sealed, lines, started, argv)
    except (SystemExit, KeyboardInterrupt) as e:  # refused or interrupted before the runs: still one RUNLOG line
        if isinstance(e, SystemExit) and e.code in (0, None):
            raise
        why = "interrupted during the checks" if isinstance(e, KeyboardInterrupt) else f"refused: {getattr(e, 'text', e.code)}"
        out = lib.RUNS / a.label
        out.mkdir(parents=True, exist_ok=True)
        with (out / "RUNLOG.jsonl").open("a") as f:
            f.write(json.dumps({"start": started, "end": lib.now(), "argv": sys.argv[1:] if argv is None else argv, "data": a.data,
                                "label": a.label, "designs": a.designs, "k": a.k, "limit": a.limit, "cap_usd": a.cap_usd,
                                "spent_usd": 0.0, "stopped": why, "checks": lines}) + "\n")
        raise


def run(a, spec, sealed, lines, started, argv):
    D = lib.designs(spec)
    wanted = None if a.designs == "all" else a.designs.split(",")
    for w in wanted or []:
        if w not in D:
            refuse(f"unknown design {w}; designs: {', '.join(D)}")
    unit_list = lib.units(spec, wanted)
    left = [k for k in (wanted or D) if not any(u[0] == k for u in unit_list)]
    if left:
        print(f"no model calls, left to analysis/study3.py: {', '.join(left)}")
    needs_product = sealed or any(d in lib.PRODUCT_DESIGNS for d, _ in unit_list)

    # ---------------------------------------------------------------- (b)-(d)
    wt = os.environ.get("CASEPATH_PRODUCT")
    pspec = spec.get("product") or {}
    ok_c, line, tdet = checks.templates(a.data)
    tenancy_cat = tdet["catalogue"]
    theft_cat = lib.TMIS / pspec["catalogues"]["theft"]
    if (lib.TMIS / pspec["catalogues"]["tenancy"]).resolve() != Path(tenancy_cat).resolve():
        line += f"; spec product.catalogues.tenancy is {pspec['catalogues']['tenancy']}: update it"
        ok_c = False
    pe = ((spec.get("product_evaluator") or {}).get("tenancy") or {}).get("catalogue")
    if sealed and pe and (lib.TMIS / pe).resolve() != Path(tenancy_cat).resolve():
        line += f"; spec product_evaluator.tenancy.catalogue is {pe}: update it"
        ok_c = False
    say(lines, line)
    if sealed and not ok_c:
        refuse("refusing: tenancy workflows")
    if not tdet["same"]:
        if not wt:
            refuse("refusing: converting the workflows needs CASEPATH_PRODUCT (its validator)")
        say(lines, f"converted tenancy workflows into {Path(tenancy_cat).relative_to(lib.TMIS)}: "
                   + json.dumps(checks.convert_tenancy(a.data, tenancy_cat, wt)))
    base_env = dict(pspec.get("env") or {})
    parities = {}
    if needs_product:
        if not wt:
            refuse("refusing: set CASEPATH_PRODUCT to the product worktree")
        ok_b, line, bdet = checks.product(spec, wt, tenancy_cat, settings_env(tenancy_cat, "gpt-6-luna", base_env))
        if not sealed and not ok_b:
            line += " (not enforced on development data)"
        say(lines, line)
        if sealed and not ok_b:
            refuse("refusing: product worktree")
        if not bdet.get("clean", False):
            refuse("refusing: the product worktree is modified")
        ok_d, line, ddet = checks.compare(wt, lib.RUNS / a.label / "checks")
        if not sealed and not ok_d:
            line += " (not enforced on development data)"
        say(lines, line)
        if sealed and not ok_d:
            refuse("refusing: compare checks")
        for d in sorted(lib.PRODUCT_DESIGNS):
            for regime, cat in (("tenancy", tenancy_cat), ("theft", theft_cat)):
                env = settings_env(cat, D[d]["model"], {**base_env, **((pspec.get("design_env") or {}).get(d) or {})})
                parities[f"{d}/{regime}"] = {"run_settings_env": env, "parity": checks.parity(wt, cat, env),
                                             "resolved_settings": checks.resolved_settings(wt, env)}
        trees = {v["parity"]["source_tree_sha256"] for v in parities.values()}
        if len(trees) != 1:
            refuse(f"refusing: parity source trees differ between runs: {trees}")

    # ---------------------------------------------------------------- MANIFEST.json (settings), unchanged on resume
    out = lib.RUNS / a.label
    out.mkdir(parents=True, exist_ok=True)
    data_manifest = lib.TMIS / a.data / "MANIFEST.json"
    fixed = {
        "data": a.data, "k": a.k, "limit": a.limit,
        "spec": {"path": str(Path(a.spec).resolve().relative_to(lib.TMIS)) if Path(a.spec).resolve().is_relative_to(lib.TMIS) else a.spec,
                 "sha256": lib.sha256_file(a.spec)},
        "data_manifest": {"path": f"{a.data}/MANIFEST.json", "sha256": lib.sha256_file(data_manifest)},
        "models": {k: D[k]["model"] for k in D},
        "self_consistency_samples_per_run": {r: (lib.store_of(spec, "self_consistency", r, a.label) or {}).get("samples_per_run")
                                             for r in D["self_consistency"]["regimes"]},
        "catalogues": {"tenancy": {"path": str(Path(tenancy_cat).relative_to(lib.TMIS)), "files": checks.catalogue_hashes(tenancy_cat)},
                       "theft": {"path": str(theft_cat.relative_to(lib.TMIS)), "files": checks.catalogue_hashes(theft_cat)}},
        "product": None if not parities else {
            "worktree": wt, "commit": bdet["head"], "source_tree_sha256": next(iter(parities.values()))["parity"]["source_tree_sha256"],
            "settings_env_by_run": {k: v["run_settings_env"] for k, v in parities.items()},
            "resolved_settings_by_run": {k: v["resolved_settings"] for k, v in parities.items()}},
    }
    mpath = out / "MANIFEST.json"
    manifest = lib.read_json(mpath)
    if manifest:
        prev = manifest["fixed"]
        changed = sorted(k for k in fixed if prev.get(k) not in (None, fixed[k]) and fixed[k] is not None)
        if changed:
            refuse(f"refusing: settings differ from the first invocation of label {a.label}: {', '.join(changed)} "
                   f"(an interrupted run resumes with settings unchanged; use a new label)")
        fixed = {k: fixed[k] if fixed[k] is not None else prev.get(k) for k in fixed}
    manifest.setdefault("format", "study3-run/1")
    manifest["label"] = a.label
    manifest["fixed"] = fixed
    manifest["analysis_plan"] = {"path": "ANALYSIS_PLAN_STUDY3.md", "committed_unmodified": checks._guard().plan_committed(),
                                 "sha256": lib.sha256_file(lib.TMIS / "ANALYSIS_PLAN_STUDY3.md") if (lib.TMIS / "ANALYSIS_PLAN_STUDY3.md").exists() else None}
    manifest["repository_head"] = lib.git("rev-parse", "HEAD")
    manifest["harness_files_sha256"] = {str(p.relative_to(lib.TMIS)): lib.sha256_file(p) for p in sorted(HERE.glob("*.py"))}
    manifest["run_environment"] = {
        "model_client": "harness/llm.py through harness/v2/common.py (ledger per design as the spec names it); TMIS_MODEL=openai/<model> per design",
        "product_transport": "harness/product/run_product.CachingTransport (cache runs/product/cache, ledger runs/product/ledger_dev_<model>.jsonl)",
        "product_entry_point": "harness/product/run_api.run_case (create_app + HTTP API), one subprocess per case-run, store ids deterministic per case-run",
        "secrets": "none recorded; the container's proxy adds the provider credential (environment values are never written)",
        "python": sys.version.split()[0]}
    if parities:
        manifest["product_parity"] = {k: v["parity"] for k, v in parities.items()}
    manifest.setdefault("invocations", []).append({"start": started, "argv": sys.argv[1:] if argv is None else argv,
                                                   "designs": [f"{d}/{r}" for d, r in unit_list], "cap_usd": a.cap_usd,
                                                   "workers": a.workers, "checks": lines})
    lib.write_json(mpath, manifest)

    # ---------------------------------------------------------------- the runs
    runlog = out / "RUNLOG.jsonl"
    prior = sum(json.loads(x).get("spent_usd", 0) for x in runlog.read_text().splitlines() if x.strip()) if runlog.exists() else 0.0
    before = count_entries(spec, unit_list, a.label)
    cap = a.cap_usd if a.cap_usd is not None else float("inf")
    spent, stopped, results = 0.0, "complete", []
    try:
        for d, regime in unit_list:
            if spent >= cap:
                stopped = "spend cap"
                break
            cmd = [sys.executable, str(HERE / "worker.py"), "--design", d, "--regime", regime, "--data", a.data, "--label", a.label,
                   "--k", str(a.k), "--cap", repr(cap - spent if cap != float("inf") else 1e9), "--workers", str(a.workers),
                   "--spec", a.spec]
            if a.limit:
                cmd += ["--limit", str(a.limit)]
            if d in lib.PRODUCT_DESIGNS:
                env = {**base_env, **((pspec.get("design_env") or {}).get(d) or {})}
                cmd += ["--product", wt, "--catalogue", str(tenancy_cat if regime == "tenancy" else theft_cat), "--product-env", json.dumps(env)]
            elif d == "react":
                cmd += ["--catalogue", str(tenancy_cat if regime == "tenancy" else theft_cat)]
            print(f"== {d} / {regime}", flush=True)
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
            done = None
            try:
                for ln in proc.stdout:
                    if ln.startswith("DONE "):
                        done = json.loads(ln[5:])
                    else:
                        print(ln, end="", flush=True)
                proc.wait()
            except KeyboardInterrupt:
                for ln in proc.stdout:  # the worker saves its store and reports
                    if ln.startswith("DONE "):
                        done = json.loads(ln[5:])
                proc.wait()
                raise
            finally:
                if done:
                    results.append(done)
                    spent += float(done.get("spent_usd") or 0)
            if done is None:
                stopped = f"worker failed for {d}/{regime} (exit {proc.returncode})"
                break
            print(f"   {d}/{regime}: {done['after']} of {done['expected']} stored, spent {done['spent_usd']:.4f} USD; {done['stopped']}", flush=True)
            if done["stopped"] != "complete":
                stopped = f"{done['stopped']} in {d}/{regime}"
                break
    except KeyboardInterrupt:
        stopped = "interrupted"
    after = count_entries(spec, unit_list, a.label)
    failed = failed_entries(spec, unit_list, a.label)
    row = {"start": started, "end": lib.now(), "argv": sys.argv[1:] if argv is None else argv, "data": a.data, "label": a.label,
           "designs": [f"{d}/{r}" for d, r in unit_list], "k": a.k, "limit": a.limit, "cap_usd": a.cap_usd,
           "entries_before": before, "entries_after": after, "spent_usd": round(spent, 6), "spent_usd_label_total": round(prior + spent, 6),
           "stopped": stopped, "units": results, "failed_outputs": len(failed)}
    with runlog.open("a") as f:
        f.write(json.dumps(row) + "\n")
    print(f"stopped: {stopped}; spent this invocation {spent:.4f} USD, label total {prior + spent:.4f} USD")
    print(f"failed outputs stored as failed ({len(failed)}):" + ("".join(f"\n  {x}" for x in failed) if failed else " none"))
    print(f"next: python3 analysis/study3.py --data {a.data} --label {a.label}")
    return 130 if stopped == "interrupted" else 0


if __name__ == "__main__":
    sys.exit(main())
