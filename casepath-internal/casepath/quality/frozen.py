"""Whether every frozen study case keeps its item list under a build, checked before that build is deployed.

A study is frozen on one stored run per case: POST /api/cases/{id}/freeze records ``study.frozen`` with the run's id,
the hash of its item list (``items_sha256``) and the process version, and each expert works on a copy that points to
that run (``intake.study``). A copy is made, and a session starts, only while the item list still hashes as it did
when frozen (``study_mismatch`` in web/app.py). A new build can change how the item list is built (an account rule, an
item field) and with it the hash, which would stop every session of the study.

``check`` recomputes with this build's code what ``study_mismatch`` computes, for every case with a ``study.frozen``
event (as a new copy of it is checked) and for every study copy (as a session start checks it): «equal» or «unequal».
Both are evaluated as study_mismatch evaluates them, by the study's frozen account rules (``case_state(..., study=True)``).
``receipt`` adds why (``run_missing``, ``version_differs``, ``items_differ``, ``error``) and the counts, content-free
(case ids, enums and counts; ``casepath.frozen-check/1``). The deployment's speed trials, which study_mismatch also
compares, are a setting of the deployment, not of the build, and are not checked here.

``preflight`` is the release check: on a copy of the store it first runs the candidate build's own startup, as a deploy
starts the app (``create_app``: the store's schema, the Knowledge the build seeds, interrupted runs marked), with no
network, no model and no volume, and only then recomputes the hashes. A Knowledge item the candidate seeds at startup
changes a frozen case's item list after the deploy; without its startup the check would not see it.

Model-free; nothing is written to the store but what the candidate's startup writes, and preflight runs on a copy.
deploy/databricks/frozen_check.py runs it in a notebook on a copy of the pilot's store with the package of the build about
to be deployed.
"""
from ..agents.runner import case_state
from ..process.items import build_items, items_sha256
from .scorecard import guard

FORMAT = "casepath.frozen-check/1"


def frozen_event(store, case_id):
    """The case's latest ``study.frozen`` event (what a copy made now is checked against), or None."""
    return next((e for e in reversed(store.list_case_events(case_id)) if e.get("kind") == "study.frozen"), None)


def expected(store, case):
    """(``frozen`` | ``copy`` | None, {frozen_run_id, items_sha256, workflow_version}) for one case of the store."""
    study = (case.get("intake") or {}).get("study")
    if study:
        return "copy", study
    event = frozen_event(store, case["id"])
    return ("frozen", event) if event else (None, None)


def mismatch(store, catalogue, case_id, want):
    """Why the case's item list no longer matches the frozen one, in study_mismatch's order and by its frozen account rules,
    or None."""
    try:
        current = case_state(store, catalogue, case_id, study=True)
    except Exception:  # a run named by the study that the store no longer holds, or a build that cannot evaluate it
        return "run_missing" if not want.get("frozen_run_id") else "error"
    run = current.get("run")
    if not run or run.get("id") != want.get("frozen_run_id"):
        return "run_missing"
    if (current.get("workflow") or {}).get("version") != want.get("workflow_version"):
        return "version_differs"
    try:
        listed = build_items(current, run.get("result"), store.list_files(case_id))
    except Exception:
        return "error"
    return None if items_sha256(listed) == want.get("items_sha256") else "items_differ"


def rows(store, catalogue):
    """[(case id, frozen | copy, reason or None)] for every frozen case and study copy, in the store's order."""
    out = []
    for case in store.list_cases():
        kind, want = expected(store, case)
        if kind:
            out.append((case["id"], kind, mismatch(store, catalogue, case["id"], want)))
    return out


def check(store, catalogue):
    """{case id: «equal» | «unequal»} for every case with a ``study.frozen`` event and every study copy."""
    return {case_id: "equal" if reason is None else "unequal" for case_id, _, reason in rows(store, catalogue)}


def startup(store, catalogue, data_dir):
    """The candidate build's own startup on the store, as a deploy starts the app (web/app.py create_app), without a network,
    a model or a volume; its run service is shut down again. Returns how many Knowledge items the startup added or renewed."""
    from ..config import load_settings
    from ..web.app import create_app

    known = lambda: {(k["id"], k.get("version")) for k in store.list_knowledge()}
    before = known()
    app = create_app(load_settings({"CASEPATH_DATA_DIR": str(data_dir), "CASEPATH_DEV_USER": "frozen-check"}), model_factory=lambda: None,
                     store=store, catalogue=catalogue)
    app.state.runs.shutdown()
    return len(known() - before)


def preflight(data_dir, catalogue, build, source=None):
    """The release check on a copy of a store (``data_dir``): the candidate's startup, then the receipt."""
    from ..web.store import CaseStore

    store = CaseStore(data_dir)
    try:
        added = startup(store, catalogue, data_dir)
        return receipt(store, catalogue, build, source, started={"ran": "create_app", "knowledge_added": added})
    finally:
        store.close()


def receipt(store, catalogue, build, source=None, started=None):
    """The content-free receipt (``casepath.frozen-check/1``): the build checked (``build``: the tree hash package.sh
    prints; ``source``: the start of the package's source tree hash, which /api/manifest shows once deployed), whether the
    candidate's startup ran first (``startup``), each case's verdict, its kind and, when unequal, why; the counts. Raises
    scorecard.ScorecardLeak if anything but ids, enums and counts got in."""
    found = rows(store, catalogue)
    return {"format": FORMAT, **guard({  # the format names itself with a slash, which the guard's identifiers never hold
        "build": build, "source": source, "model_calls": 0, "startup": started or {"ran": "none", "knowledge_added": None},
        "cases": {case_id: "equal" if reason is None else "unequal" for case_id, _, reason in found},
        "kinds": {case_id: kind for case_id, kind, _ in found},
        "why": {case_id: reason for case_id, _, reason in found if reason},
        "counts": {"cases": len(found), "frozen": sum(1 for _, k, _ in found if k == "frozen"), "copies": sum(1 for _, k, _ in found if k == "copy"),
                   "equal": sum(1 for _, _, r in found if r is None), "unequal": sum(1 for _, _, r in found if r)}})}


def lines(out):
    """The receipt as the bridge reads it: one line per case, then the counts and the verdict."""
    rows_ = [f"{case_id} {out['kinds'][case_id]} {verdict}" + (f" ({out['why'][case_id]})" if case_id in out["why"] else "")
             for case_id, verdict in out["cases"].items()]
    c, started = out["counts"], out.get("startup") or {}
    verdict = ("deploy: no, fix the difference first" if c["unequal"] else "deploy: the frozen study is unchanged" if c["cases"]
               else "no frozen case and no study copy in this store")
    ran = (f"after the candidate's startup ({started['knowledge_added']} Knowledge item(s) seeded or renewed)" if started.get("ran") == "create_app"
           else "without the candidate's startup: not the release check")
    return rows_ + [f"build {out['build']}: {c['equal']} equal, {c['unequal']} unequal of {c['cases']} "
                    f"({c['frozen']} frozen, {c['copies']} copies), {ran}, no model", verdict]
