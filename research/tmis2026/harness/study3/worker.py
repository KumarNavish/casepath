"""Worker: runs one design on one regime for run_all.py, in its own process. Last output line: "DONE <json>".

    python worker.py --design D --regime tenancy|theft --data fresh|fresh2 --label L --k 3 --cap USD
                     [--limit N] [--workers 6] [--product WT --catalogue DIR --product-env JSON]

One process per design, because the repository's model client binds its model (TMIS_MODEL) and its ledger at import.
Runner functions are imported unchanged from harness/v2 and harness/product; where one is not importable, the
smallest piece is copied here and marked "copied". Every design writes the store file, keys and fields that
analysis/study3.py reads (from analysis/study3_spec.json), and its cost rows to the ledger the spec names for it.

Resumable: a key already in the store is never run again (a failed output stays failed). Spend: the cost of the
calls this process pays (cached answers cost nothing); no new case is started once it reaches --cap.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True
from concurrent.futures import ThreadPoolExecutor, as_completed  # noqa: E402
from pathlib import Path  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib  # noqa: E402

# Ledger tag or arm each runner writes; checked against the spec's cost "match" so that the analysis finds the rows.
WRITES = {
    ("ric", "tenancy"): {"tag.exp": "v2-tenancy", "tag.method": "B1v2p"},
    ("ric", "theft"): {"tag.exp": "v2-theft", "tag.method": "Rv2p"},
    ("ric_frontier", "tenancy"): {"tag.exp": "v2-tenancy", "tag.method": "B1v2p"},
    ("ric_frontier", "theft"): {"tag.exp": "v2-theft", "tag.method": "Rv2p"},
    ("core", "theft"): {"tag.exp": "v3-theft", "tag.method": "CPv3-read"},
    ("ric_original", "theft"): {"tag.exp": "theft", "tag.method": "R"},
    ("ric_original_frontier", "theft"): {"tag.exp": "theft", "tag.method": "R"},
    ("self_consistency", "tenancy"): {"arm": "B1V2P_SAMPLE"},
    ("self_consistency", "theft"): {"arm": "RPACK"},
    ("model_executes_rules", "tenancy"): {"arm": "COL"},
    ("model_executes_rules", "theft"): {"arm": "COL_THEFT"},
    ("react", "tenancy"): {"arm": "REACT"},
    ("react", "theft"): {"arm": "REACT_THEFT"},
}
V2_DESIGNS = {"ric", "ric_frontier", "core", "ric_original", "ric_original_frontier"}

_lock = threading.Lock()
SPENT = [0.0]


def add_spend(usd):
    with _lock:
        SPENT[0] += float(usd or 0)


def cases_of(D, regime, limit):
    """Tenancy: the test claims (first N with --limit). Theft: every text (the texts of the first story with --limit)."""
    if regime == "tenancy":
        ids = list(D.claim_ids("test"))
        return ids[:limit] if limit else ids
    T = D.texts()
    if limit:
        first = min(v["story"] for v in T.values())
        return sorted(t for t, v in T.items() if v["story"] == first)
    return sorted(T)


# ----------------------------------------------------------------------------------------------- model-client designs
def setup_v2(spec, design, regime):
    """harness/v2 client: ledger = the spec's ledger for this design; count what this process pays."""
    import common
    import llm
    cost = spec_cost(spec, design, regime)
    llm.LEDGER = lib.TMIS / cost["ledger"]
    llm.LEDGER.parent.mkdir(parents=True, exist_ok=True)
    inner = common._call  # the client's own call; common._retrying_call looks it up at call time

    def counting(**kw):
        r = inner(**kw)
        if not r.get("cached"):
            add_spend((r.get("usage") or {}).get("cost"))
        return r
    common._call = counting
    return common, llm


def setup_product_transport(spec, design, regime):
    """harness/product transport (baselines.chat): count what this process pays."""
    sys.path[:0] = [str(lib.PRODUCT_DIR), str(lib.HARNESS), str(lib.HARNESS / "v2")]
    import hashlib
    import run_product as rp
    cost = spec_cost(spec, design, regime)
    base = rp.CachingTransport
    assert (lib.TMIS / cost["ledger"]).resolve() == (rp.RUNS / f"ledger_dev_{spec_model(spec, design)}.jsonl").resolve(), \
        f"{design}/{regime}: spec ledger {cost['ledger']} is not the transport's ledger"

    class Counting(base):
        """A call is paid when the transport writes its cache file (it writes the ledger row at the same moment).
        Counted in `finally`: the transport can raise after writing both (it rebuilds the response with the
        provider's headers), and baselines.chat then retries, which the cache answers."""

        def handle_request(self, request):
            body = request.read()
            key = hashlib.sha256(str(request.url).encode() + b"\0" + body + b"\0" + str(self.run).encode()).hexdigest()
            path = rp.CACHE / f"{key}.json"
            cached = path.exists()
            try:
                return super().handle_request(request)
            finally:
                if not cached and path.exists():
                    try:
                        usage = json.loads(json.loads(path.read_text())["body"]).get("usage") or {}
                    except (ValueError, KeyError, TypeError):
                        usage = {}
                    add_spend(usage["cost"] if usage.get("cost") is not None else rp._list_price(self.model, usage))
    rp.CachingTransport = Counting
    return rp


def spec_cost(spec, design, regime):
    c = lib.designs(spec)[design]["cost"]
    return c.get(regime, c) if "method" not in c else c


def spec_model(spec, design):
    return lib.designs(spec)[design]["model"]


def check_writes(spec, design, regime):
    want = spec_cost(spec, design, regime).get("match") or {}
    have = WRITES[(design, regime)]
    if any(have.get(k) != v for k, v in want.items()):
        raise SystemExit(f"{design}/{regime}: the spec's cost match {want} differs from what the runner writes {have}")


def runner(spec, design, regime, D, k):
    """Return fn(case, index) -> stored entry. index = run, or sample index for self-consistency."""
    if design in V2_DESIGNS:
        check_writes(spec, design, regime)
        common, llm = setup_v2(spec, design, regime)
        if regime == "tenancy":  # ric, ric_frontier: Study 2's B1v2p, unchanged
            import tenancy_v2
            return lambda c, r: tenancy_v2.run_b1v2(D, c, r)
        T = D.texts()
        if design in ("ric_original", "ric_original_frontier"):  # Study 1's R, unchanged
            import theft_v2
            return lambda t, r: theft_v2.run_r(t, T[t]["text"], r)
        import load_reviewed
        import v3
        sys.path.insert(0, str(lib.PRODUCT_DIR))
        import convert_theft  # the reviewed rules file (RULES) the product's theft workflow was converted from
        system = v3.TheftV3(load_reviewed.load(convert_theft.RULES))
        if design in ("ric", "ric_frontier"):  # Rules in context on the reviewed rules (the CP4 harness's Rpack request)
            return lambda t, r: system.tp.run_rv2(t, T[t]["text"], r)

        def core(t, r):  # copied from harness/v2/cp4.py::cp4 (a script, not importable); pairing fixed modulo 3 runs
            a = system.reading(t, T[t]["text"], r)
            b = system.reading(t, T[t]["text"], (r + 1) % CORE_PAIRING)
            if a is None:
                return {"plan": None, "error": "reading failed"}
            nu = {g: (v if v in {"true", "false"} and b is not None and b.get(g) == v else "unresolved") for g, v in a.items()}
            return {"plan": system.tp.plan_exact(nu), "judgments": nu, "reading_a": a, "reading_b": b}
        return core

    check_writes(spec, design, regime)
    assert spec_model(spec, design) == "gpt-6-luna", "the product-transport baselines are fixed to gpt-6-luna"
    import common  # noqa: F401  (paths; data through common.data only)
    setup_product_transport(spec, design, regime)
    import baselines as B
    B.F = D  # the module's data loader (fresh/tenancy_fresh.py at import) -> the data selected through common.data
    if regime == "tenancy":
        if design == "model_executes_rules":
            material = B.col_material()
            return lambda c, r: B.run_col(c, r, material)
        if design == "react":
            wfs = {p.stem: json.loads(p.read_text()) for p in sorted(Path(ARGS.catalogue).glob("*.json"))}
            return lambda c, r: B.run_react(c, r, wfs)
        if design == "self_consistency":  # copied from baselines_theft.main (inline there): one B1v2p sample
            import tenancy_methods as s1
            import tenancy_v2 as t2
            system = t2.system_v2(t2.B1V2_TASK, t2.pack_for(D))

            def sample(c, i):
                res, _u, err = B.chat([{"role": "system", "content": system}, {"role": "user", "content": t2.case_block(D, c)}],
                                      s1.B1_SCHEMA, "evidence_plan", i, c, "B1V2P_SAMPLE")
                return {"plan": s1._plan_from_decisions(res, "documents") if res else None, "error": err}
            return sample
    else:
        import baselines_theft as BT
        T = D.texts()
        if design == "model_executes_rules":
            material = BT.theft_material()
            return lambda t, r: BT.run_col(t, r, T, material)
        if design == "react":
            wf = json.loads((Path(ARGS.catalogue) / "household_theft.json").read_text())
            return lambda t, r: BT.run_react(t, r, T, wf)
        if design == "self_consistency":
            material = BT.theft_material()
            return lambda t, i: {"plan": BT.rpack_sample(t, i, T, material)}
    raise SystemExit(f"no runner for {design}/{regime}")


CORE_PAIRING = 3  # Core pairs run r with run (r + 1) mod 3, as in development (cp4.py with --k 3)


# ----------------------------------------------------------------------------------------------- the product
class ArmSpend:
    """Cost of the ledger rows written under one arm since this object was made (read incrementally)."""

    def __init__(self, path, arm):
        self.path, self.arm, self.usd = Path(path), arm, 0.0
        self.offset = self.path.stat().st_size if self.path.exists() else 0

    def __call__(self):
        with _lock:
            if self.path.exists():
                with self.path.open("rb") as f:
                    f.seek(self.offset)
                    chunk = f.read()
                cut = chunk.rfind(b"\n") + 1
                for line in chunk[:cut].splitlines():
                    if line.strip():
                        row = json.loads(line)
                        if row.get("arm") == self.arm:
                            self.usd += float(row.get("usd") or 0)
                self.offset += cut
            return self.usd


def product_runner(spec, design, regime, D, label):
    sys.path[:0] = [str(lib.PRODUCT_DIR), str(lib.HARNESS), str(lib.HARNESS / "v2")]
    import run_product as rp
    import run_theft
    from theft_data import doc_ids
    model = spec_model(spec, design)
    ledger = rp.RUNS / f"ledger_dev_{model}.jsonl"
    assert (lib.TMIS / spec_cost(spec, design, regime)["ledger"]).resolve() == ledger.resolve()
    arm = f"STUDY3-{label}-{design}"
    meter = ArmSpend(ledger, arm)
    inv = {v.lower(): k for k, v in doc_ids().items()}

    def one(c, r):
        t0 = time.time()
        p = subprocess.run([sys.executable, str(HERE / "product_case.py"), "--product", ARGS.product, "--data", ARGS.data,
                            "--regime", regime, "--case", c, "--run", str(r), "--arm", arm, "--catalogue", ARGS.catalogue,
                            "--env", ARGS.product_env, "--model", model], capture_output=True, text=True)
        line = next((ln for ln in p.stdout.splitlines() if ln.startswith("RESULT ")), None)
        if line is None and (p.returncode < 0 or "KeyboardInterrupt" in p.stderr):
            return None  # stopped by an interrupt: not an output, run again on resume
        res = json.loads(line[7:]) if line else {"plan": None, "status": "adapter_error", "error": p.stderr[-800:], "usage": [], "keys": []}
        u = res.pop("usage", []) or []
        res["tokens"] = {"input": sum(x.get("input_tokens", 0) or 0 for x in u), "cached": sum(x.get("cached_tokens", 0) or 0 for x in u),
                         "output": sum(x.get("output_tokens", 0) or 0 for x in u)}
        res["agents"] = [x.get("agent") for x in u]
        if regime == "theft":  # need ids -> catalogue names, as run_theft.py stores them
            res["plan_ids"] = res.get("plan")
            res["plan"] = run_theft.map_plan(res.get("plan"), inv)
            res["plan_workflow_only"] = run_theft.map_plan(res.get("plan_workflow_only"), inv)
        res["seconds"] = round(time.time() - t0, 1)
        return res
    return one, meter


# ----------------------------------------------------------------------------------------------- main
def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--regime", required=True, choices=lib.REGIMES)
    ap.add_argument("--data", required=True, choices=["fresh", "fresh2"])
    ap.add_argument("--label", required=True)
    ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cap", type=float, required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--product", default=None)
    ap.add_argument("--catalogue", default=None)
    ap.add_argument("--product-env", default="{}")
    ap.add_argument("--spec", default=str(lib.SPEC))
    ARGS = a = ap.parse_args()
    spec = lib.load_spec(a.spec)
    d = lib.designs(spec)[a.design]
    os.environ["TMIS_MODEL"] = "openai/" + d["model"]  # before the model client is imported
    sys.path[:0] = [str(lib.HARNESS / "v2")]
    import common
    import llm
    D = common.data(a.regime, a.data)  # the only data access; the fresh2 guard applies
    cases = cases_of(D, a.regime, a.limit)
    st = lib.store_of(spec, a.design, a.regime, a.label)
    n_idx = st["samples_per_run"] * a.k if "samples_per_run" in st else a.k
    keyof = (lambda c, i: st["key"].format(case=c, sample=i)) if "samples_per_run" in st else (lambda c, i: st["key"].format(case=c, run=i))
    store = lib.read_json(st["path"])
    before = sum(keyof(c, i) in store for i in range(n_idx) for c in cases)
    jobs = [(c, i) for i in range(n_idx) for c in cases if keyof(c, i) not in store]
    if a.design in lib.PRODUCT_DESIGNS:
        fn, meter = product_runner(spec, a.design, a.regime, D, a.label)
        spent = meter
    else:
        fn = runner(spec, a.design, a.regime, D, a.k)
        if a.design in V2_DESIGNS:
            llm.BUDGET_USD = llm.spent() + a.cap  # the client's own hard stop on its (redirected) ledger, besides the check below
        spent = lambda: SPENT[0]
    print(f"{a.design}/{a.regime}: {len(cases)} cases x {n_idx} = {len(cases) * n_idx}; {before} stored, {len(jobs)} to do", flush=True)
    stopped, new, failed_new = "complete", 0, []

    def one(c, i):
        if spent() >= a.cap:
            return c, i, None, "spend cap"
        try:
            res = fn(c, i)
            return c, i, res, None if res is not None else "interrupted"
        except llm.BudgetExceeded:
            return c, i, None, "spend cap (model client's ledger budget)"
        except Exception as e:  # recorded as failed, never dropped or retried
            return c, i, {"plan": None, "status": "adapter_error", "error": f"{type(e).__name__}: {e}"}, None

    pool = ThreadPoolExecutor(a.workers)
    try:
        futs = [pool.submit(one, c, i) for c, i in jobs]
        for f in as_completed(futs):
            c, i, res, why = f.result()
            if res is None:
                stopped = why
                continue
            store[keyof(c, i)] = res
            new += 1
            if lib.failed(res):
                failed_new.append(keyof(c, i))
            lib.write_json(st["path"], store)
            p = res.get("plan") or {}
            print(f"  {keyof(c, i)} req {len(p.get('requests', []))} hold {len(p.get('holds', []))}"
                  f"{' FAILED ' + str(res.get('error'))[:120] if lib.failed(res) else ''}  spent {spent():.4f}", flush=True)
    except KeyboardInterrupt:
        stopped = "interrupted"
        pool.shutdown(wait=False, cancel_futures=True)
        lib.write_json(st["path"], store) if new else None
        print("DONE " + json.dumps({"design": a.design, "regime": a.regime, "expected": len(cases) * n_idx, "before": before,
                                    "after": before + new, "spent_usd": spent(), "stopped": stopped, "failed_new": failed_new}), flush=True)
        os._exit(130)
    pool.shutdown(wait=True)
    if stopped == "complete" and before + new < len(cases) * n_idx:
        stopped = "incomplete"
    print("DONE " + json.dumps({"design": a.design, "regime": a.regime, "expected": len(cases) * n_idx, "before": before,
                                "after": before + new, "spent_usd": spent(), "stopped": stopped, "failed_new": failed_new}), flush=True)


ARGS = None

if __name__ == "__main__":
    main()
