"""Study 3 analysis (STUDY3_DESIGN.md; binding once copied to ANALYSIS_PLAN_STUDY3.md). No model calls, no network.

    python3 study3.py --data fresh|fresh2 --label <run label> [--spec study3_spec.json] [--out <path stem>]

What is fixed where:
- The study itself (designs, where their plans are stored, number of runs, hypotheses in order, tests, margins,
  secondary contrasts, subsets, cost sources) is data in study3_spec.json. Nothing of it is repeated here.
- Scoring and the statistics are those of Study 2 (analysis/study2.py), imported, not copied: ten_row, ten_summary,
  theft_row, theft_summary, dedup_errors, retest, contrast, paired_bootstrap, quantile.
- Data are loaded only through harness/v2/common.py::data(kind, data), so the fresh2 guard applies.

Additions to Study 2, fixed here before any fresh2 output exists:
- all deviations per claim = strict unsafe errors + held required-now documents + holds of documents the reference
  neither requires nor holds.
- Clusters: the changed fact (theft), the family (tenancy). A cluster's value is the mean over all its rows
  (runs, stories, claims). Pairs and claims are balanced within clusters, so this is also the mean of means.
- A missing plan file means the design did not run: every analysis that needs it is reported as "not run".
  A missing entry in a present file, or an entry without a plan, is a failed output and scores as an empty plan.
- Theft plans may name documents by workflow need id (d01); ids are mapped to catalogue names before scoring.
- The exact sign-flip test for more than 16 clusters is computed by meet-in-the-middle (same result as the
  enumeration in study2.signflip_p, which is used for 16 clusters or fewer; checked in test_study3.py).
- Fixed-sequence procedure at the spec's alpha. A "fewer" hypothesis tested by sign flips is significant if
  p < alpha and the difference favours the product; a non-inferiority hypothesis if its bootstrap p < alpha.
  An "all must hold" hypothesis is confirmed only if every one of its tests is significant.
- Cost per case-run. Designs whose stored entries carry the cache keys of their calls (the product) are costed by
  joining each distinct key to the ledger, whoever paid it; calls are split by agent when the entry's agent list
  lines up with its distinct keys. Other designs: matching ledger rows of the cases in scope, each distinct key
  once, times the spec's multiplier, divided by cases x runs.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import importlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMIS = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TMIS / "harness" / "v2"))
import study2 as s2  # noqa: E402

SPEC = HERE / "study3_spec.json"
EMPTY = {"requests": [], "holds": []}
NOT_TESTED = "not tested (an earlier hypothesis failed)"


# ======================================================================= statistics
_signflip_enumerate = s2.signflip_p


def signflip_p(diffs):
    """Exact two-sided sign-flip p. Up to 16 clusters: study2's enumeration. Above: the same count by
    meet-in-the-middle (the two halves' signed sums, sorted; same tolerance of 1e-12)."""
    diffs = list(diffs)
    if len(diffs) <= 16:
        return _signflip_enumerate(diffs)
    obs = abs(sum(diffs))
    t = obs - 1e-12
    if t <= 0:
        return 1.0
    half = len(diffs) // 2

    def sums(xs):
        out = [0.0]
        for x in xs:
            out = [s + x for s in out] + [s - x for s in out]
        return out
    left, right = sums(diffs[:half]), sorted(sums(diffs[half:]))
    n = len(right)
    extreme = sum((n - bisect.bisect_left(right, t - a)) + bisect.bisect_right(right, -t - a) for a in left)
    return extreme / 2 ** len(diffs)


s2.signflip_p = signflip_p  # study2.contrast looks the name up at call time


def configure(spec):
    st = spec["statistics"]
    s2.B = int(st["bootstrap_resamples"])
    s2.SEED = st["seed"]


def run_contrast(a_by_cluster, b_by_cluster, name, higher_is_better, test, margin=None):
    c = s2.contrast(a_by_cluster, b_by_cluster, name, higher_is_better=higher_is_better,
                    margin=margin if test == "noninferiority" else None)
    c["test"] = test
    c["p"] = c["p_noninferiority"] if test == "noninferiority" else c["p_signflip"]
    c["min_p"] = c["min_p_noninferiority"] if test == "noninferiority" else c["min_p_signflip"]
    return c


def significant(c, alpha):
    if c["test"] == "noninferiority":
        return c["p"] < alpha
    return c["p"] < alpha and c["favours"] == "a"


def fixed_sequence(results, alpha):
    """results: ordered list of (hypothesis id, [contrast or None per test]); None = a needed design did not run.
    Returns {id: status}. A hypothesis is tested only if all before it were confirmed."""
    status, open_ = {}, True
    for hid, tests in results:
        if not open_:
            status[hid] = NOT_TESTED
            continue
        if any(t is None for t in tests):
            status[hid] = "not run"
            open_ = False
            continue
        ok = all(significant(t, alpha) for t in tests)
        status[hid] = "confirmed" if ok else "not confirmed"
        open_ = ok
    return status


# ======================================================================= data and plans
def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Inputs:
    """Reads files once and records the hash of every file read."""

    def __init__(self, root=TMIS):
        self.root, self.cache, self.hashes, self.missing = Path(root), {}, {}, set()

    def path(self, rel):
        return self.root / rel

    def json(self, rel):
        if rel not in self.cache:
            p = self.path(rel)
            if not p.exists():
                self.missing.add(rel)
                self.cache[rel] = None
            else:
                self.hashes[rel] = sha256(p)
                text = p.read_text()
                self.cache[rel] = json.loads(text) if text.strip() else {}
        return self.cache[rel]

    def ledger(self, rel):
        key = ("ledger", rel)
        if key not in self.cache:
            p = self.path(rel)
            if not p.exists():
                self.missing.add(rel)
                self.cache[key] = None
            else:
                self.hashes[rel] = sha256(p)
                self.cache[key] = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        return self.cache[key]


def fmt(template, **kw):
    return template.format(**kw)


def field(row, dotted):
    for part in dotted.split("."):
        if not isinstance(row, dict):
            return None
        row = row.get(part)
    return row


def to_names(plan, inv):
    """Theft: workflow need ids (d07) -> catalogue names; names pass unchanged."""
    if plan is None:
        return None
    return {**plan, "requests": sorted(inv.get(str(d).lower(), d) for d in plan.get("requests", [])),
            "holds": sorted(inv.get(str(d).lower(), d) for d in plan.get("holds", []))}


def majority(plans):
    """Self-consistency: per document, requested if more than half the samples request it; else held if more than
    half request or hold it; handed over if more than half hand the claim over. A failed sample is an empty plan."""
    ok = [p or EMPTY for p in plans]
    n = len(ok)
    req = Counter(d for p in ok for d in set(p.get("requests", [])))
    rh = Counter(d for p in ok for d in set(p.get("requests", [])) | set(p.get("holds", [])))
    requests = sorted(d for d, c in req.items() if c > n / 2)
    return {"requests": requests, "holds": sorted(d for d, c in rh.items() if c > n / 2 and d not in requests),
            "deferred": sum(bool(p.get("deferred")) for p in ok) > n / 2}


_EXTRACTED = {}


def package_dir(package):
    """A product package given as a path, or as {"commit": sha, "subdir": "casepath-internal"[, "repo": path]}:
    the commit's tree is extracted read-only (git archive) into a temporary folder, once per process."""
    if isinstance(package, dict):
        repo = package.get("repo") or str(TMIS.parents[1])
        k = (repo, package["commit"], package.get("subdir", "casepath-internal"))
        if k not in _EXTRACTED:
            import atexit
            import shutil
            import subprocess
            import tempfile
            out = tempfile.mkdtemp(prefix="study3-product-")
            atexit.register(shutil.rmtree, out, True)
            arch = subprocess.run(["git", "-C", repo, "archive", "--format=tar", package["commit"], k[2]], capture_output=True)
            if arch.returncode:
                raise RuntimeError(f"git archive {package['commit']} failed: {arch.stderr.decode(errors='replace').strip()[:200]}")
            subprocess.run(["tar", "-x", "-C", out], input=arch.stdout, check=True)
            _EXTRACTED[k] = str(Path(out) / k[2])
        return _EXTRACTED[k]
    return package


def load_evaluator(package):
    """The product's evaluator (casepath.process.workflows) from a package folder or commit; a clean import each time."""
    package = package_dir(package)
    if not package or not Path(package).is_dir():
        raise RuntimeError(f"product package not found: {package}")
    for m in [m for m in sys.modules if m == "casepath" or m.startswith("casepath.")]:
        del sys.modules[m]
    sys.path.insert(0, str(package))
    try:
        W = importlib.import_module("casepath.process.workflows")
    finally:
        sys.path.remove(str(package))
    return W


def two_valued(entry, W, catalogue, unresolved_value):
    """Two-valued rule execution from the product's stored readings: accepted established facts and the
    presumptions that applied; every other boolean workflow fact set to unresolved_value; accepted document
    findings; the product's evaluator (checked=True) on the routed workflow. A handed-over or failed run is kept."""
    plan, extra = entry.get("plan"), entry.get("product_extra") or {}
    if plan is None or plan.get("deferred"):
        return plan
    wf = catalogue.get(plan["family"])
    facts = {}
    for k, f in (extra.get("facts") or {}).items():
        if (f["status"] == "established" and f.get("verdict") == "accepted") or f["status"] == "presumed":
            facts[k] = f["value"]
    facts.setdefault("dispute_family", plan["family"])
    for f in wf["facts"]:
        if facts.get(f["id"]) is None and f["type"] == "boolean":
            facts[f["id"]] = unresolved_value
    findings = {d: {"status": j["status"], "verdict": "accepted"} for d, j in (extra.get("document_judgments") or {}).items()
                if j["status"] in {"present", "unusable"} and j.get("verdict") == "accepted"}
    ev = W.evaluate(wf, facts, findings, checked=True)
    return {"family": plan["family"],
            "requests": sorted(r["document"] for r in ev["documents"] if r["required"] == "yes" and r["status"] in {"missing", "unusable"}),
            "holds": sorted(r["document"] for r in ev["documents"] if r["required"] == "depends"), "deferred": False}


class Study:
    def __init__(self, spec, data, label, D, inputs=None, evaluator_loader=load_evaluator):
        self.spec, self.data, self.label, self.D = spec, data, label, D  # D = {"tenancy": module, "theft": module}
        self.inputs = inputs or Inputs()
        self.dev = (spec.get("development_runs") or {}).get(f"{data}/{label}", {})
        self.designs = {d["key"]: d for d in spec["designs"]}
        self.evaluator_loader = evaluator_loader
        self._evaluators = {}
        stories = self.dev.get("theft_stories", (spec["data"].get(data) or {}).get("theft_stories"))
        self.cases = {}
        if D.get("tenancy") is not None:
            self.cases["tenancy"] = list(D["tenancy"].claim_ids("test"))
        if D.get("theft") is not None:
            T = D["theft"].texts()
            self.cases["theft"] = sorted(t for t, v in T.items() if stories is None or v["story"] in stories)
            self.pairs = [p for p in D["theft"].pairs() if stories is None or p["story"] in stories]
            ids = getattr(D["theft"], "doc_ids", None)
            if ids is None:
                from theft_data import doc_ids as ids
            self.inv = {v.lower(): k for k, v in ids().items()}
        self.plans = {}   # (design, regime) -> {case: [plan or None per run]}
        self.entries = {}  # (design, regime) -> {case: [stored entry or None per run]}
        self.status = {}  # (design, regime) -> {"status": "ran"|"not run", ...}
        self._rows, self._meta = {}, {}

    # ------------------------------------------------------------- where plans live
    def store(self, design, regime):
        over = ((self.dev.get("designs") or {}).get(design) or {}).get(regime)
        if over is not None:
            return over
        return (self.designs[design].get("store") or {}).get(regime)

    def runs(self, design, regime):
        return int(self.store(design, regime).get("runs", self.designs[design]["runs"]))

    def cost_spec(self, design, regime):
        st = self.store(design, regime) or {}
        if "cost" in st:
            return st["cost"]
        c = self.designs[design].get("cost") or {"method": "none"}
        return c.get(regime, c) if "method" not in c else c

    def fill(self, **kw):
        return dict(kw, label=self.label, data=self.data)

    # ------------------------------------------------------------- loading
    def load(self, design, regime):
        key = (design, regime)
        if key in self.status:
            return self.status[key]["status"] == "ran"
        st = self.store(design, regime)
        if regime not in self.designs[design]["regimes"] or st is None or regime not in self.cases:
            self.status[key] = {"status": "not run", "reason": "design not in this regime"}
            return False
        runs, cases = self.runs(design, regime), self.cases[regime]
        info = {"runs": runs}
        if "derive" in st:
            ok = self._derive(design, regime, st, runs, cases, info)
        else:
            rel = fmt(st["path"], **self.fill())
            raw = self.inputs.json(rel)
            info["file"] = rel
            if raw is None:
                self.status[key] = {**info, "status": "not run", "reason": f"file missing: {rel}"}
                return False
            ent = {c: [raw.get(fmt(st["key"], **self.fill(case=c, run=r))) for r in range(runs)] for c in cases}
            self.entries[key] = ent
            self.plans[key] = {c: [(e or {}).get(st.get("field", "plan")) for e in v] for c, v in ent.items()}
            ok = True
        if not ok:
            self.status[key] = {**info, "status": "not run"} if "status" not in info else info
            return False
        if regime == "theft":
            self.plans[key] = {c: [to_names(p, self.inv) for p in v] for c, v in self.plans[key].items()}
        ent = self.entries.get(key)
        info["missing_entries"] = sum(e is None for v in ent.values() for e in v) if ent is not None else None
        info["failed_outputs"] = sum(p is None for v in self.plans[key].values() for p in v)
        info["status"] = "ran"
        self.status[key] = info
        return True

    def _derive(self, design, regime, st, runs, cases, info):
        kind = st["derive"]
        info["derived"] = kind
        if kind == "majority":
            n = int(st["samples_per_run"])
            src = st["samples"]
            rel = fmt(src["path"], **self.fill())
            info.update(file=rel, samples_per_run=n)
            raw = self.inputs.json(rel)
            if raw is None:
                info.update(status="not run", reason=f"file missing: {rel}")
                return False
            samples = {c: [(raw.get(fmt(src["key"], **self.fill(case=c, sample=i))) or {}).get(src.get("field", "plan"))
                           for i in range(n * runs)] for c in cases}
            info["missing_samples"] = sum(p is None for v in samples.values() for p in v)
            self.plans[(design, regime)] = {c: [majority(v[r * n:(r + 1) * n]) for r in range(runs)] for c, v in samples.items()}
            return True
        if kind == "two_valued":
            base = st["from_design"]
            info["from_design"] = base
            if not self.load(base, regime) or (base, regime) not in self.entries:
                info.update(status="not run", reason=f"needs the stored runs of {base}")
                return False
            ev = (self.dev.get("product_evaluator") or self.spec.get("product_evaluator") or {}).get(regime) or {}
            try:
                W, cat = self.evaluator(regime, ev)
            except Exception as exc:  # reported, never silent
                info.update(status="not run", reason=f"product evaluator not available: {exc}")
                return False
            info.update(product_package=ev.get("package"), catalogue=ev.get("catalogue"))
            base_runs = self.runs(base, regime)
            if runs > base_runs:
                info.update(status="not run", reason=f"{base} has {base_runs} runs, {runs} needed")
                return False
            self.plans[(design, regime)] = {c: [None if e is None else two_valued(e, W, cat, bool(st["unresolved"]))
                                                for e in v[:runs]] for c, v in self.entries[(base, regime)].items()}
            return True
        raise ValueError(f"unknown derivation {kind}")

    def evaluator(self, regime, ev):
        k = (json.dumps(ev.get("package"), sort_keys=True), ev.get("catalogue"))
        if k not in self._evaluators:
            W = self.evaluator_loader(ev.get("package"))
            self._evaluators[k] = (W, W.Catalogue.load(self.inputs.path(ev["catalogue"])))
        return self._evaluators[k]

    # ------------------------------------------------------------- rows
    def tenancy_rows(self, design):
        if not self.load(design, "tenancy"):
            return None
        key = (design, "tenancy")
        if key in self._rows:
            return self._rows[key]
        D = self.D["tenancy"]
        rows = []
        for cid in self.cases["tenancy"]:
            ref, meta = D.reference(cid), self.claim_meta(cid)
            for r, plan in enumerate(self.plans[key][cid]):
                row = s2.ten_row(ref, plan)
                row["all_dev"] = row["strict_unsafe"] + row["held_req"] + row["spurious_hold"]
                row.update(case=cid, run=r, cluster=ref[self.spec["regimes"]["tenancy"]["cluster"]], **meta)
                rows.append(row)
        self._rows[key] = rows
        return rows

    def claim_meta(self, cid):
        if cid not in self._meta:
            D = self.D["tenancy"]
            ref = D.reference(cid)
            req = ref.get("request_set")
            held = ref.get("held_set")
            if req is None:
                req = [d for d, s in ref["document_states"].items() if s in s2.REQ_NOW]
            if held is None:
                held = [d for d, s in ref["document_states"].items() if s == "held"]
            try:
                lang = ((D.intake(cid) or {}).get("submission") or {}).get("language")
            except Exception:
                lang = None
            lang = lang or ref.get("language")
            group = next((g for g, prefixes in self.spec.get("languages", {}).items()
                          if lang and any(str(lang).lower().startswith(p) for p in prefixes)), "unknown")
            self._meta[cid] = {"open_fact": ref.get("open_fact") is not None, "request_set_empty": not req,
                               "held_set_empty": not held, "language": group}
        return self._meta[cid]

    def in_subset(self, cid, name):
        """A subset of the spec, defined from the reference only; a list of names is their union."""
        if isinstance(name, list):
            return any(self.in_subset(cid, n) for n in name)
        rule = self.spec["tenancy_subsets"][name]
        meta = self.claim_meta(cid)
        if "not" in rule:
            return not self.in_subset(cid, rule["not"])
        return all(meta[k] == v for k, v in rule.items() if k in ("open_fact", "request_set_empty", "held_set_empty"))

    def theft_rows(self, design):
        if not self.load(design, "theft"):
            return None
        key = (design, "theft")
        if key in self._rows:
            return self._rows[key]
        runs = self.runs(design, "theft")
        pairing = [(r, r) for r in range(runs)]
        P = self.plans[key]
        on = s2.theft_rows(None, [p for p in self.pairs if p["kind"] == "on"], P, pairing=pairing)
        un = s2.theft_rows(None, [p for p in self.pairs if p["kind"] == "unresolved"], P, pairing=pairing)
        s2.dedup_errors(on)
        self._rows[key] = (on, un)
        return self._rows[key]

    def clusters(self, design, regime, measure, subset=None):
        mean = lambda k: (lambda rs: sum(r[k] for r in rs) / len(rs))
        if regime == "tenancy":
            rows = self.tenancy_rows(design)
            if rows is None:
                return None
            if subset:
                rows = [r for r in rows if self.in_subset(r["case"], subset)]
            fn = {"strict_unsafe": s2.TEN_METRIC["strict_unsafe"], "requested_share": s2.TEN_METRIC["requested_share"],
                  "all_deviations": mean("all_dev")}[measure]
            return s2.by_cluster(rows, "cluster", fn)
        rows = self.theft_rows(design)
        if rows is None:
            return None
        key = {"errors": "errors", "errors_dedup": "errors_dedup"}[measure]
        return s2.by_cluster(rows[0], self.spec["regimes"]["theft"]["cluster"], mean(key))

    # ------------------------------------------------------------- summaries
    def tenancy_summary(self, rows):
        out = s2.ten_summary(rows)
        out["all_deviations_per_claim"] = sum(r["all_dev"] for r in rows) / len(rows)
        out["claims"] = len({r["case"] for r in rows})
        return out

    def design_summary(self, design, regime):
        st = dict(self.status[(design, regime)])
        if st["status"] != "ran":
            return st
        if regime == "tenancy":
            rows = self.tenancy_rows(design)
            st["measures"] = self.tenancy_summary(rows)
        else:
            on, un = self.theft_rows(design)
            st["measures"] = s2.theft_summary(on, un)
            st["measures"]["errors_dedup_per_pair"] = sum(r["errors_dedup"] for r in on) / len(on)
        rt = [x for x in (s2.retest(v) for v in self.plans[(design, regime)].values()) if x is not None]
        st["run_to_run_jaccard"] = sum(rt) / len(rt) if rt else None
        st["cost"] = self.cost(design, regime)
        return st

    def cost(self, design, regime):
        c = self.cost_spec(design, regime)
        cases, runs = self.cases[regime], self.runs(design, regime)
        method = c.get("method", "none")
        if method == "none":
            return {"method": "none", "cost_per_case_run": 0.0, "calls_per_case_run": 0.0}
        rows = self.inputs.ledger(fmt(c["ledger"], **self.fill()))
        if rows is None:
            return {"method": method, "status": "not run", "reason": f"ledger missing: {c['ledger']}"}
        if method == "plan_keys":
            return self._cost_keys(design, regime, rows)
        caseset = set(cases)
        seen, usd, calls = set(), 0.0, 0
        for r in rows:
            if field(r, c["case_field"]) not in caseset or any(field(r, k) != v for k, v in c["match"].items()):
                continue
            k = r.get("key")
            if k is not None and k in seen:
                continue
            seen.add(k)
            usd += float(field(r, c["cost_field"]) or 0)
            calls += 1
        mult = float(c.get("multiplier", 1))
        n = len(cases) * runs
        return {"method": "ledger", "ledger": c["ledger"], "match": c["match"], "multiplier": mult, "ledger_calls": calls,
                "usd_total": usd * mult, "case_runs": n, "cost_per_case_run": usd * mult / n, "calls_per_case_run": calls * mult / n}

    def _cost_keys(self, design, regime, rows):
        by_key = {}
        for r in rows:
            by_key.setdefault(r.get("key"), r)
        deciding = set(self.spec["deciding_agents"])
        ent = self.entries[(design, regime)]
        n = total = calls = unknown = aligned = 0
        groups = defaultdict(float)
        agents = defaultdict(lambda: [0, 0.0])
        for v in ent.values():
            for e in v:
                if e is None:
                    continue
                n += 1
                keys = list(dict.fromkeys(e.get("keys") or []))
                names = e.get("agents") or []
                line = len(keys) == len(names)
                aligned += line
                for i, k in enumerate(keys):
                    row = by_key.get(k)
                    if row is None:
                        unknown += 1
                        continue
                    usd = float(row.get("usd") or 0)
                    total += usd
                    calls += 1
                    if line:
                        agents[names[i]][0] += 1
                        agents[names[i]][1] += usd
                        groups["can decide the checklist" if names[i] in deciding else "the rest"] += usd
                    else:
                        groups["not attributed (agent list does not line up)"] += usd
        if not n:
            return {"method": "plan_keys", "status": "no entries"}
        return {"method": "plan_keys", "case_runs": n, "usd_total": total, "cost_per_case_run": total / n,
                "calls_per_case_run": calls / n, "calls_without_ledger_row": unknown, "case_runs_with_agents_lined_up": aligned,
                "by_group_per_case_run": {g: u / n for g, u in sorted(groups.items())},
                "by_agent": {a: {"calls_per_case_run": x[0] / n, "cost_per_case_run": x[1] / n,
                                 "decides_checklist": a in deciding} for a, x in sorted(agents.items())}}

    def checklist_changes(self, design, regime):
        """Which agents changed a checklist, as far as the stored result shows it: needs added by an agent and
        counted in the scored plan (plan differs from the workflow-only plan)."""
        if not self.load(design, regime) or (design, regime) not in self.entries:
            return {"status": "not run"}
        n = changed = 0
        added = Counter()
        for v in self.entries[(design, regime)].values():
            for e in v:
                if e is None or e.get("plan") is None:
                    continue
                n += 1
                p, w = e.get("plan") or {}, e.get("plan_workflow_only") or {}
                changed += (sorted(p.get("requests", [])), sorted(p.get("holds", []))) != (sorted(w.get("requests", [])), sorted(w.get("holds", [])))
                for x in (e.get("product_extra") or {}).get("agent_added_needs") or []:
                    added[str(x.get("required"))] += 1
        return {"case_runs": n, "case_runs_where_added_needs_entered_the_checklist": changed,
                "needs_added_by_agents_by_required": dict(sorted(added.items()))}

    # ------------------------------------------------------------- the analysis
    def partition(self):
        """Counts of the partition subsets; refuses if a claim falls in none or in more than one."""
        names = self.spec.get("tenancy_partition") or []
        if not names or "tenancy" not in self.cases:
            return None
        bad = [c for c in self.cases["tenancy"] if sum(self.in_subset(c, n) for n in names) != 1]
        if bad:
            raise ValueError(f"tenancy subsets {names} do not partition the claims: {len(bad)} claims in none or several, e.g. {bad[:3]}")
        return {"subsets": names, "claims": {n: sum(self.in_subset(c, n) for c in self.cases["tenancy"]) for n in names},
                "total": len(self.cases["tenancy"]), "is_partition": True}

    def contrast_of(self, regime, measure, a, b, test, margin, name, subset=None):
        fa, fb = self.clusters(a, regime, measure, subset), self.clusters(b, regime, measure, subset)
        if fa is None or fb is None or not set(fa) & set(fb):
            return None  # a design did not run, or no claim of the subset
        hib = self.spec["measures"][measure]["higher_is_better"]
        c = run_contrast(fa, fb, name, hib, test, margin)
        c.update(regime=regime, measure=measure, a=a, b=b, subset=subset)
        return c

    def not_run(self, *designs_regimes):
        out = []
        for d, reg in designs_regimes:
            self.load(d, reg)
            st = self.status[(d, reg)]
            if st["status"] != "ran":
                out.append(f"{d} ({reg}): {st.get('reason', 'not run')}")
        return out

    def analyse(self):
        spec, alpha = self.spec, self.spec["statistics"]["alpha"]
        res = {"data": self.data, "label": self.label, "designs": {}, "hypotheses": [], "secondary": {}}
        res["tenancy_partition"] = self.partition()
        for d in spec["designs"]:
            for regime in spec["regimes"]:
                if regime in d["regimes"] and regime in self.cases:
                    self.load(d["key"], regime)
        for d in spec["designs"]:
            res["designs"][d["key"]] = {"label": d["label"], "model": d["model"], "regimes": {}}
            for regime in d["regimes"]:
                if regime in self.cases:
                    res["designs"][d["key"]]["regimes"][regime] = self.design_summary(d["key"], regime)

        # ---- primary hypotheses, fixed sequence
        seq = []
        for h in spec["hypotheses"]:
            bs = h["b"] if isinstance(h["b"], list) else [h["b"]]
            tests = [self.contrast_of(h["regime"], h["measure"], h["a"], b, h["test"], h.get("margin"), f"primary|{h['id']}|{b}")
                     for b in bs]
            seq.append((h["id"], tests))
            missing = self.not_run(*[(x, h["regime"]) for x in [h["a"]] + bs])
            beside = []
            for x in h.get("beside", []):
                sub = x["subset"]
                sname = "+".join(sub) if isinstance(sub, list) else sub
                for b in bs:
                    r = self.contrast_of(h["regime"], h["measure"], h["a"], b, h["test"], h.get("margin"),
                                         f"beside|{h['id']}|{b}|{sname}", sub)
                    n = sum(self.in_subset(c, sub) for c in self.cases.get("tenancy", []))
                    note = "" if r is not None else ("no claim in this subset" if n == 0 else "not run")
                    beside.append({"subset": sname, "b": b, "descriptive": True, "claims": n, "result": r, "note": note})
            res["hypotheses"].append({"id": h["id"], "text": h["text"], "regime": h["regime"], "measure": h["measure"],
                                      "test": h["test"], "margin": h.get("margin"), "a": h["a"], "b": bs,
                                      "all_must_hold": len(bs) > 1, "not_run": missing, "beside": beside,
                                      "tests": [t if t is None else dict(t, significant=significant(t, alpha)) for t in tests]})
        status = fixed_sequence(seq, alpha)
        for h in res["hypotheses"]:
            h["status"] = status[h["id"]]
            h["inside_procedure"] = h["status"] != NOT_TESTED

        sec = res["secondary"]
        # ---- secondary contrasts
        sec["contrasts"] = []
        for c in spec["secondary"]["contrasts"]:
            r = self.contrast_of(c["regime"], c["measure"], c["a"], c["b"], c["test"], c.get("margin"), f"secondary|{c['id']}", c.get("subset"))
            runs = {x: self.runs(c[x], c["regime"]) for x in ("a", "b") if self.status.get((c[x], c["regime"]), {}).get("status") == "ran"}
            sec["contrasts"].append({**c, "result": r, "not_run": self.not_run((c["a"], c["regime"]), (c["b"], c["regime"])),
                                     "runs": runs, "descriptive": bool(c.get("descriptive"))})

        # ---- tenancy subsets and languages, every design
        if "tenancy" in self.cases:
            ids = self.cases["tenancy"]
            sec["tenancy_subsets"] = {"claims": {n: sum(self.in_subset(c, n) for c in ids) for n in spec["tenancy_subsets"]},
                                      "definitions": spec["tenancy_subsets"], "by_design": {}}
            langs = Counter(self.claim_meta(c)["language"] for c in ids)
            sec["tenancy_languages"] = {"claims": dict(sorted(langs.items())), "by_design": {}}
            for d in spec["designs"]:
                rows = self.tenancy_rows(d["key"]) if "tenancy" in d["regimes"] else None
                if rows is None:
                    continue
                sub = {"all claims": self.subset_summary(rows)}
                for n in spec["secondary"].get("subset_tables", spec["tenancy_subsets"]):
                    sub[n] = self.subset_summary([r for r in rows if self.in_subset(r["case"], n)])
                sec["tenancy_subsets"]["by_design"][d["key"]] = sub
                sec["tenancy_languages"]["by_design"][d["key"]] = {g: self.subset_summary([r for r in rows if r["language"] == g])
                                                                   for g in sorted(langs)}
        # ---- theft unresolved-fact pairs, every design
        if "theft" in self.cases:
            sec["theft_unresolved"] = {}
            for d in spec["designs"]:
                rows = self.theft_rows(d["key"]) if "theft" in d["regimes"] else None
                if rows is not None and rows[1]:
                    sec["theft_unresolved"][d["key"]] = s2.theft_summary(rows[0], rows[1])["unresolved"]
        # ---- cost per case-run and ratio to the baseline
        sec["cost"] = {}
        for regime in self.cases:
            base = spec["secondary"]["cost_baseline"].get(regime)
            bc = (res["designs"].get(base, {}).get("regimes", {}).get(regime, {}) or {}).get("cost", {}) if base else {}
            out = {}
            for d in spec["designs"]:
                st = res["designs"][d["key"]]["regimes"].get(regime)
                if not st or st.get("status") != "ran":
                    continue
                c = st["cost"]
                ratio = None
                if c.get("cost_per_case_run") is not None and bc.get("cost_per_case_run"):
                    ratio = c["cost_per_case_run"] / bc["cost_per_case_run"]
                out[d["key"]] = {"cost_per_case_run": c.get("cost_per_case_run"), "calls_per_case_run": c.get("calls_per_case_run"),
                                 f"ratio_to_{base}": ratio}
            sec["cost"][regime] = {"baseline": base, "by_design": out}
        # ---- product: which agents changed a checklist
        sec["product_checklist_changes"] = {f"{d}, {regime}": self.checklist_changes(d, regime)
                                            for d in spec["secondary"]["product_designs"] for regime in self.cases}
        # ---- run-to-run agreement
        sec["run_to_run_jaccard"] = {f"{d}, {reg}": v["run_to_run_jaccard"] for d, x in res["designs"].items()
                                     for reg, v in x["regimes"].items() if v.get("status") == "ran"}
        res["inputs"] = {"files_read": dict(sorted(self.inputs.hashes.items())), "files_missing": sorted(self.inputs.missing)}
        return res

    def subset_summary(self, rows):
        if not rows:
            return {"claim_runs": 0}
        s = self.tenancy_summary(rows)
        keep = ("claims", "claim_runs", "strict_unsafe_per_claim", "all_deviations_per_claim", "requested_share",
                "correct_hold_share", "premature_per_claim", "silent_skip_per_claim", "held_required_now_per_claim",
                "spurious_holds_per_claim", "unnecessary_per_claim", "missed_per_claim", "handed_per_claim", "handoffs")
        return {k: s[k] for k in keep}


# ======================================================================= report
def num(x, nd=3):
    if x is None:
        return "–"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, int):
        return str(x)
    return f"{x:.{nd}f}"


def pval(x):
    if x is None:
        return "–"
    if x == 0:
        return "< 0.0001"
    return f"{x:.1e}" if x < 0.0001 else f"{x:.4f}"


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def contrast_row(name, c, design_label):
    if c is None:
        return [name, "–", "–", "–", "–", "–", "–", "–", "–", "–", "not run"]
    return [name, design_label(c["a"]), design_label(c["b"]), num(c["a_value"]), num(c["b_value"]), num(c["diff"]),
            f"[{num(c['diff_ci'][0])}, {num(c['diff_ci'][1])}]", f"{c['clusters']} / {c['nonzero_clusters']}",
            pval(c["min_p"]), pval(c["p"]), c["test"] + (f" (margin {c['margin']})" if c.get("margin") is not None else "")]


def secondary_row(c, design_label):
    """A secondary contrast row; the test column says 'descriptive' and names unequal runs per case."""
    row = contrast_row(c["id"], c["result"], design_label)
    if c["result"] is not None:
        runs = c.get("runs") or {}
        notes = (["descriptive"] if c.get("descriptive") else []) + (
            [f"runs per case {runs['a']} vs {runs['b']}"] if runs.get("a") is not None and runs.get("a") != runs.get("b") else [])
        if notes:
            row[-1] += "; " + "; ".join(notes)
    return row


CHEAD = ["", "A", "B", "A value", "B value", "A − B", "95% interval", "clusters / non-zero", "smallest p", "p", "test"]


def markdown(res, spec):
    lab = {d["key"]: d["label"] for d in spec["designs"]}
    L = lambda k: lab.get(k, k)
    md = [f"# Study 3 analysis: data `{res['data']}`, run label `{res['label']}`", "",
          "Generated by `analysis/study3.py` from `analysis/study3_spec.json`. No model calls.", ""]
    md += ["## Designs", ""]
    rows = []
    for k, d in res["designs"].items():
        for reg, st in d["regimes"].items():
            rows.append([L(k), d["model"], reg, st.get("runs", "–"), st["status"],
                         st.get("file") or (f"derived ({st.get('derived')})" if st.get("derived") else "–"),
                         num(st.get("missing_entries")), num(st.get("failed_outputs")), st.get("reason", "")])
    md += [table(["Design", "Model", "Regime", "Runs", "Status", "Plans", "Missing entries", "Failed outputs", "Note"], rows), ""]

    md += ["## Tenancy (per claim-run)", ""]
    rows = []
    for k, d in res["designs"].items():
        st = d["regimes"].get("tenancy")
        if not st:
            continue
        if st["status"] != "ran":
            rows.append([L(k)] + ["not run"] + ["–"] * 12)
            continue
        m, c = st["measures"], st["cost"]
        rows.append([L(k), m["claim_runs"], num(m["strict_unsafe_per_claim"]), num(m["all_deviations_per_claim"]),
                     num(m["requested_share"]), num(m["held_required_now_per_claim"]), num(m["spurious_holds_per_claim"]),
                     num(m["correct_hold_share"]), num(m["unnecessary_per_claim"]), num(m["missed_per_claim"]),
                     num(m["handed_per_claim"]), num(m["premature_per_claim"]), num(m["silent_skip_per_claim"]),
                     num(c.get("cost_per_case_run"), 5)])
    md += [table(["Design", "Claim-runs", "Strict unsafe", "All deviations", "Requested share", "Held req.-now", "Spurious holds",
                  "Correct-hold share", "Unnecessary", "Missed", "Handed over", "Premature", "Silent skips", "USD per case-run"], rows), ""]

    md += ["## Theft (per changed-fact pair-run; unresolved-fact pairs at the right)", ""]
    rows = []
    for k, d in res["designs"].items():
        st = d["regimes"].get("theft")
        if not st:
            continue
        if st["status"] != "ran":
            rows.append([L(k)] + ["not run"] + ["–"] * 8)
            continue
        m, c = st["measures"], st["cost"]
        u = m.get("unresolved") or {}
        rows.append([L(k), m["pair_runs"], num(m["wrong_per_pair"]), num(m["missed_per_pair"]), num(m["errors_per_pair"]),
                     num(m["errors_dedup_per_pair"]), num(m["f1"]), num(u.get("premature_rate")), num(u.get("stable_rate")),
                     num(c.get("cost_per_case_run"), 5)])
    md += [table(["Design", "Pair-runs", "Wrong", "Missed", "Wrong + missed", "Repeated once", "F1", "Premature (open)",
                  "Unchanged (open)", "USD per text-run"], rows), ""]

    md += ["## Primary hypotheses (fixed sequence, alpha "
           f"{spec['statistics']['alpha']})", ""]
    rows = []
    for h in res["hypotheses"]:
        tag = "" if h["inside_procedure"] else " (outside the procedure)"
        for i, t in enumerate(h["tests"]):
            r = contrast_row(h["id"] + (f".{i + 1}" if len(h["tests"]) > 1 else ""), t, L)
            rows.append(r + [h["status"] + tag if i == 0 else ("" if not h["all_must_hold"] else "(all must hold)")])
        for x in h.get("beside", []):
            name = f"{h['id']} on {x['subset']}" + (f" (vs {L(x['b'])})" if len(h["b"]) > 1 else "")
            row = contrast_row(name, x["result"], L)
            if x["result"] is None:
                row[-1] = x["note"]
            rows.append(row + [f"descriptive, outside the procedure ({x['claims']} claims)"])
    md += [table(CHEAD + ["status"], rows), ""]
    for h in res["hypotheses"]:
        md.append(f"- **{h['id']}** {h['text']} Status: {h['status']}." + (f" Not run: {'; '.join(h['not_run'])}." if h["not_run"] else ""))
    md += ["", "Hypotheses marked 'outside the procedure' were not tested; their raw results are shown for completeness only. "
           "Rows named 'on <subset>' repeat a hypothesis's contrast on a subset of claims (families with at least one claim in it); "
           "they are descriptive and are not tested inside the procedure.", ""]

    sec = res["secondary"]
    md += ["## Secondary contrasts (outside the sequence)", ""]
    rows = [secondary_row(c, L) + [spec["measures"][c["measure"]]["label"]
                                   + (f", {c['subset']} claims" if c.get("subset") else ""), c["section"]]
            for c in sec["contrasts"]]
    md += [table(CHEAD + ["measure", "section"], rows), ""]
    if any(c.get("descriptive") for c in sec["contrasts"]):
        md += ["Rows marked 'descriptive' are reported with their test but are not hypotheses; a design with fewer runs per "
               "case than its comparator says so in the test column (its cluster value is the mean over its own runs).", ""]

    if "tenancy_subsets" in sec:
        ts = sec["tenancy_subsets"]
        md += ["## Tenancy subsets", ""]
        part = res.get("tenancy_partition")
        if part:
            md += [f"Partition of the {part['total']} claims (checked: every claim in exactly one): "
                   + "; ".join(f"{n} {k}" for n, k in part["claims"].items()) + ".", ""]
        md += ["Claims selected: " + "; ".join(f"{spec['tenancy_subsets'][n]['label']}: {k}" for n, k in ts["claims"].items()), ""]
        head = ["Design", "Subset", "Claims", "Strict unsafe", "All deviations", "Correct-hold share", "Premature", "Silent skips",
                "Requested share", "Unnecessary", "Missed", "Handed over", "Held req.-now", "Spurious holds"]
        rows = []
        for k, sub in ts["by_design"].items():
            for n, s in sub.items():
                if not s.get("claim_runs"):
                    rows.append([L(k), n, 0] + ["–"] * 11)
                    continue
                rows.append([L(k), n, s["claims"], num(s["strict_unsafe_per_claim"]), num(s["all_deviations_per_claim"]),
                             num(s["correct_hold_share"]), num(s["premature_per_claim"]), num(s["silent_skip_per_claim"]),
                             num(s["requested_share"]), num(s["unnecessary_per_claim"]), num(s["missed_per_claim"]),
                             num(s["handed_per_claim"]), num(s["held_required_now_per_claim"]), num(s["spurious_holds_per_claim"])])
        md += [table(head, rows), ""]
        tl = sec["tenancy_languages"]
        md += ["## Tenancy by language", "", "Claims: " + "; ".join(f"{g}: {n}" for g, n in tl["claims"].items()), ""]
        rows = []
        for k, sub in tl["by_design"].items():
            for g, s in sub.items():
                if not s.get("claim_runs"):
                    continue
                rows.append([L(k), g, s["claims"], num(s["strict_unsafe_per_claim"]), num(s["all_deviations_per_claim"]),
                             num(s["correct_hold_share"]), num(s["premature_per_claim"]), num(s["silent_skip_per_claim"]),
                             num(s["requested_share"])])
        md += [table(["Design", "Language"] + head[2:], rows), ""]
    if sec.get("theft_unresolved"):
        md += ["## Theft unresolved-fact pairs", ""]
        rows = [[L(k), u["pair_runs"], num(u["premature_rate"]), num(u["stable_rate"]), num(u["other_changes_per_pair"])]
                for k, u in sec["theft_unresolved"].items()]
        md += [table(["Design", "Pair-runs", "Premature request", "Left unchanged", "Other changes per pair"], rows), ""]

    md += ["## Cost per case-run", ""]
    for regime, c in sec["cost"].items():
        base = c["baseline"]
        rows = [[L(k), num(v["cost_per_case_run"], 5), num(v["calls_per_case_run"], 1), num(v[f"ratio_to_{base}"], 2)]
                for k, v in c["by_design"].items()]
        md += [f"{regime.capitalize()} (ratio to {L(base)}):", "", table(["Design", "USD", "Calls", "Ratio"], rows), ""]
        for k in c["by_design"]:
            cs = (res["designs"][k]["regimes"][regime].get("cost") or {})
            if cs.get("multiplier", 1) != 1:
                md += [f"{L(k)}: ledger cost of the paid calls × {num(cs['multiplier'], 0)} / (cases × runs). "
                       + (spec_note(spec, k, regime) or ""), ""]
    for k, d in res["designs"].items():
        for reg, st in d["regimes"].items():
            c = (st or {}).get("cost") or {}
            if c.get("method") != "plan_keys" or "by_agent" not in c:
                continue
            md += [f"{L(k)}, {reg}: USD per case-run by group: "
                   + "; ".join(f"{g} {num(u, 5)}" for g, u in c["by_group_per_case_run"].items())
                   + f" ({c['case_runs_with_agents_lined_up']} of {c['case_runs']} case-runs attributed).", ""]
            rows = [[a, num(x["calls_per_case_run"], 2), num(x["cost_per_case_run"], 5), num(x["decides_checklist"])]
                    for a, x in c["by_agent"].items()]
            md += [table(["Agent", "Calls", "USD", "Can decide the checklist"], rows), ""]

    md += ["## Which agents changed a checklist", ""]
    rows = [[k, v.get("case_runs", "–"), v.get("case_runs_where_added_needs_entered_the_checklist", "–"),
             json.dumps(v.get("needs_added_by_agents_by_required", {}), sort_keys=True) if v.get("status") != "not run" else "not run"]
            for k, v in sec["product_checklist_changes"].items()]
    md += [table(["Design, regime", "Case-runs", "Added needs in the checklist", "Added needs by 'required'"], rows), ""]

    md += ["## Run-to-run agreement (mean Jaccard of requests over run pairs)", ""]
    md += [table(["Design, regime", "Jaccard"], [[k, num(v)] for k, v in sec["run_to_run_jaccard"].items()]), ""]
    md += ["## Inputs", "", f"Files read: {len(res['inputs']['files_read'])}. Missing: "
           + (", ".join(res["inputs"]["files_missing"]) or "none") + ".", ""]
    return "\n".join(md)


def spec_note(spec, design, regime):
    c = next(d for d in spec["designs"] if d["key"] == design).get("cost") or {}
    return (c.get(regime, c) if "method" not in c else c).get("note")


def print_summary(res, spec):
    lab = {d["key"]: d["label"] for d in spec["designs"]}
    print(f"Study 3 analysis, data {res['data']}, label {res['label']}")
    for k, d in res["designs"].items():
        for reg, st in d["regimes"].items():
            if st["status"] != "ran":
                print(f"  {lab[k]:45s} {reg:8s} not run: {st.get('reason', '')}")
                continue
            m = st["measures"]
            v = m["strict_unsafe_per_claim"] if reg == "tenancy" else m["errors_per_pair"]
            print(f"  {lab[k]:45s} {reg:8s} runs {st['runs']}  {'strict unsafe per claim' if reg == 'tenancy' else 'wrong + missed per pair'} {v:.3f}")
    if res.get("tenancy_partition"):
        p = res["tenancy_partition"]
        print(f"  tenancy partition of {p['total']} claims (checked): " + ", ".join(f"{n} {k}" for n, k in p["claims"].items()))
    if "tenancy_subsets" in res["secondary"]:
        print("  tenancy subsets, claims selected:", json.dumps(res["secondary"]["tenancy_subsets"]["claims"], sort_keys=True))
    print("Primary hypotheses:")
    for h in res["hypotheses"]:
        tag = "" if h["inside_procedure"] else "  [outside the procedure]"
        print(f"  {h['id']}: {h['status']}{tag}")
        for t, b in zip(h["tests"], h["b"]):
            if t is None:
                print(f"     vs {lab.get(b, b)}: not run")
            else:
                print(f"     vs {lab.get(b, b)}: A {t['a_value']:.3f}  B {t['b_value']:.3f}  diff {t['diff']:+.3f} "
                      f"[{t['diff_ci'][0]:+.3f}, {t['diff_ci'][1]:+.3f}]  clusters {t['clusters']} (non-zero {t['nonzero_clusters']})  "
                      f"p {pval(t['p'])}  smallest p {pval(t['min_p'])}")
        for x in h.get("beside", []):
            t = x["result"]
            if t is None:
                print(f"     on {x['subset']} vs {lab.get(x['b'], x['b'])}: {x['note']}")
                continue
            print(f"     on {x['subset']} vs {lab.get(x['b'], x['b'])} (descriptive): A {t['a_value']:.3f}  B {t['b_value']:.3f}  "
                  f"diff {t['diff']:+.3f} [{t['diff_ci'][0]:+.3f}, {t['diff_ci'][1]:+.3f}]  clusters {t['clusters']} "
                  f"(non-zero {t['nonzero_clusters']})  p {pval(t['p'])}")


# ======================================================================= main
def load_data(data):
    import common  # harness/v2/common.py: the fresh2 guard applies here
    return {"tenancy": common.data("tenancy", data), "theft": common.data("theft", data)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", required=True, choices=["fresh", "fresh2"])
    ap.add_argument("--label", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--out", default=None, help="path stem; writes <stem>.json and <stem>.md")
    a = ap.parse_args(argv)
    spec = json.loads(Path(a.spec).read_text())
    configure(spec)
    D = load_data(a.data)
    study = Study(spec, a.data, a.label, D)
    res = study.analyse()
    res["spec"] = {"file": str(Path(a.spec).resolve().relative_to(TMIS)) if Path(a.spec).resolve().is_relative_to(TMIS) else a.spec,
                   "sha256": sha256(a.spec)}
    stem = Path(a.out) if a.out else HERE / f"study3_results_{a.data}_{a.label}"
    stem.with_suffix(".json").write_text(json.dumps(res, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    stem.with_suffix(".md").write_text(markdown(res, spec) + "\n")
    print_summary(res, spec)
    print("written", stem.with_suffix(".json"), "and", stem.with_suffix(".md"))
    return res


if __name__ == "__main__":
    main()
