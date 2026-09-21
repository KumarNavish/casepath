"""Build the teaching explorer with the actual obligation/evidence controller.

Invented repair policy only. No benchmark inputs, targets, API, or provider.
Run from the repository root with the prepared Python environment.
"""
from __future__ import annotations
import hashlib
import itertools
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "casepath-api"))
from casepath_api.obligation_control.obligation_control_v1 import Graph
from casepath_api.obligation_control.evidence_demand_v1 import capabilities, evidence_state, plan

POLICY = (
    "For a qualifying repair, establish the cause before authorizing work. "
    "Request evidence only after acquisition permission is confirmed. "
    "A complete inspection report is sufficient, or a service note and photo "
    "that jointly establish the cause."
)
REF = "teaching-policy#repair"
GRAPH = {
    "contract": "casepath.obligation-control/1.0.0",
    "variables": ["qualifies", "permission"],
    "scopes": [{"scope_id": "repair", "when": {"var": "qualifies"}, "parents": [], "join": "all", "source_refs": [REF]}],
    "obligations": [{"obligation_id": "establish_cause", "scope_id": "repair", "when": {"const": True}, "acquire_when": {"var": "permission"}, "capability_ids": ["cause_proof"], "source_refs": [REF]}],
    "actions": [{"action_id": "authorize_repair", "scope_id": "repair", "prerequisites": {"const": True}, "obligation_ids": ["establish_cause"], "source_refs": [REF]}],
}
CAPABILITIES = [{"capability_id": "cause_proof", "fact_id": "cause", "fact_statement": "The cause of the equipment fault is established.", "must_show": "Establish the cause of the equipment fault.", "source_refs": [REF], "routes": [
    {"route_id": "report", "document_ids": ["REPORT"], "source_refs": [REF]},
    {"route_id": "pair", "document_ids": ["NOTE", "PHOTO"], "source_refs": [REF]},
]}]


def build():
    graph = Graph.parse(GRAPH, {REF})
    caps = capabilities(CAPABILITIES, {REF})
    scenarios = {}
    for branch, permission, held in itertools.product(
        ("true", "false", "unknown"), ("true", "false", "unknown"),
        ("missing", "unreviewed", "sufficient", "pair", "joint_unknown"),
    ):
        observations = {"qualifies": {"true": True, "false": False, "unknown": None}[branch],
                        "permission": {"true": True, "false": False, "unknown": None}[permission]}
        evidence = {"documents": {d: {"presence": "missing", "native_state": "missing", "source_refs": ["teaching_inventory"]} for d in ("REPORT", "NOTE", "PHOTO")}, "slot_assessments": [], "joint_assessments": []}
        present = ["REPORT"] if held in {"unreviewed", "sufficient"} else ["NOTE", "PHOTO"] if held in {"pair", "joint_unknown"} else []
        for doc in present:
            evidence["documents"][doc] = {"presence": "present", "native_state": "unknown", "source_refs": ["teaching_inventory"]}
            if held != "unreviewed":
                evidence["slot_assessments"].append({"capability_id": "cause_proof", "route_id": "report" if doc == "REPORT" else "pair", "document_id": doc, "adequate": True, "source_refs": ["teaching_assessment"]})
        if held == "pair":
            evidence["joint_assessments"].append({"capability_id": "cause_proof", "route_id": "pair", "adequate": True, "source_refs": ["teaching_assessment"]})
        result = plan(graph, caps, observations, evidence_state(evidence, caps, {"teaching_inventory", "teaching_assessment"}))
        scenarios[f"{branch}:{permission}:{held}"] = {"observations": observations, "evidence": evidence, "planning": result}
    modules = ["obligation_control_v1.py", "evidence_demand_v1.py"]
    paths = ["casepath-api/casepath_api/obligation_control/" + name for name in modules]
    return {"schema": "casepath.teaching-explorer/1", "purpose": "Invented teaching example; deterministic controller execution, not benchmark or model evidence.", "policy": POLICY, "graph": GRAPH, "capabilities": CAPABILITIES, "documents": {"REPORT": "Inspection report", "NOTE": "Service note", "PHOTO": "Photo"}, "source_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}, "scenarios": scenarios}


if __name__ == "__main__":
    output = ROOT / "casepath/assets/method-guide-data.json"
    raw = json.dumps(build(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if "--check" in sys.argv:
        if output.read_text() != raw:
            raise SystemExit("Method guide data differs from the actual controller. Regenerate it.")
        print("45 teaching states match the current controller and source hashes.")
    else:
        output.write_text(raw)
        print(output)
