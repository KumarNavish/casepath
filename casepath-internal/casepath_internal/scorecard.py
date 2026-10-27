"""Content-free scorecards: what may leave Mobiliar about a run on a real case.

A scorecard holds counts, statuses, workflow ids and hashed file ids. Its
guard rejects any string that is not one of those, so case text, names,
quotes and model wording can never be published by accident. Full results
stay in the internal store.

    python -m casepath_internal.scorecard <data-dir> > scorecard.json
"""
from hashlib import sha256
import json
import re
import sys

from .store import CaseStore

SAFE = re.compile(r"^(?:[a-z0-9][a-z0-9_.:-]{0,79}|h_[0-9a-f]{12})$")
STATUSES = {"completed", "failed", "interrupted", "queued", "running", "selected", "fallback", "ambiguous",
            "needs_facts", "unmapped", "present", "unusable", "missing", "unchecked", "established", "unknown",
            "conflicting", "accepted", "rejected", "yes", "depends", "draft", "reviewed", "suggested", "applied",
            "contradicted", "not_checked"}


class ScorecardLeak(ValueError):
    pass


def hashed(value, salt):
    return "h_" + sha256((salt + "\0" + value).encode()).hexdigest()[:12]


def guard(value, path="$"):
    """Allow only numbers, booleans, null and short identifiers or enums."""
    if value is None or isinstance(value, bool) or (type(value) in (int, float)):
        return value
    if isinstance(value, str):
        if value in STATUSES or SAFE.match(value):
            return value
        raise ScorecardLeak(f"{path}: free text is not allowed in a scorecard")
    if isinstance(value, list):
        return [guard(v, f"{path}[{i}]") for i, v in enumerate(value)]
    if isinstance(value, dict):
        for key in value:
            if not SAFE.match(key):
                raise ScorecardLeak(f"{path}: key {key!r} is not an identifier")
        return {k: guard(v, f"{path}.{k}") for k, v in value.items()}
    raise ScorecardLeak(f"{path}: unsupported value")


def run_card(run, salt):
    result = run.get("result") or {}
    evaluation = result.get("evaluation") or {}
    routing = run.get("routing") or {}
    facts = result.get("facts") or []
    documents = evaluation.get("documents") or []
    usage = result.get("usage") or []
    card = {
        "run": hashed(run["id"], salt), "case": hashed(run["case_id"], salt), "status": run["status"],
        "error_kind": (run.get("error") or "").split(":", 1)[0] or None,
        "routing": routing.get("status"), "workflow": run.get("workflow_id"), "workflow_version": run.get("workflow_version"),
        "steps_reached": len(evaluation.get("path") or []),
        "current_step": (evaluation.get("current") or {}).get("step"),
        "outcome": (evaluation.get("outcome") or {}).get("id"),
        "waiting_for": [w["fact"] for w in evaluation.get("waiting_for") or []],
        "facts": {status: sum(1 for f in facts if f["status"] == status) for status in ("established", "unknown", "conflicting")},
        "facts_rejected_by_check": sum(1 for f in facts if f.get("verdict") == "rejected"),
        "quotes_rejected": sum(1 for e in result.get("events") or [] if e.get("kind", "").endswith(".rejected")),
        "documents": {d["document"]: d["status"] for d in documents},
        "reply_clauses": len((result.get("reply") or {}).get("clauses") or []),
        "reply_clauses_supported": sum(1 for c in (result.get("reply") or {}).get("clauses") or [] if c.get("supported")),
        "process_edits_by_agents": len(result.get("agent_edits") or []),
        "knowledge_applied": sum(1 for k in (result.get("provenance") or {}).get("knowledge", []) if k.get("applied")),
        "knowledge_proposed": len(((result.get("learned") or {}).get("proposals")) or []),
        "knowledge_outcomes": {o["item"]: o["outcome"] for o in ((result.get("learned") or {}).get("outcomes")) or []},
        "agent_turns": _turns(usage),
        "input_tokens": sum(u.get("input_tokens", 0) for u in usage),
        "output_tokens": sum(u.get("output_tokens", 0) for u in usage),
    }
    return guard(card)


def _turns(usage):
    turns = {}
    for row in usage:
        turns[row.get("agent", "model")] = turns.get(row.get("agent", "model"), 0) + 1
    return turns


def scorecard(store, salt):
    runs = [store.latest_run(case["id"]) for case in store.list_cases()]
    return guard({"format": "casepath.scorecard.v1", "runs": [run_card(r, salt) for r in runs if r]})


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        sys.exit("usage: python -m casepath_internal.scorecard <data-dir> <salt-kept-inside-mobiliar>")
    json.dump(scorecard(CaseStore(argv[0]), argv[1]), sys.stdout, indent=1)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
