from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

from casepath_api.arena_v1 import evaluation, generator

E76 = Path("/Users/kumar0002/Documents/Die Mobiliar/.discovery-loop/coordinator-work/pro-investigator-r1/pro-reconvergence-r12/casepath-end-to-end-loop-20260912")


def _frozen_e76():
    spec = importlib.util.spec_from_file_location("e76_evaluation", E76 / "evaluation.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_extended_evaluator_reproduces_frozen_e76_references_when_no_extension_is_used() -> None:
    if not (E76 / "EVALUATION_DRAFT.json").exists():
        return
    frozen = _frozen_e76()
    cases = frozen.load_cases(E76 / "EVALUATION_DRAFT.json")
    for case in cases:
        state = evaluation.initial_state(case)
        for requested in ([], [case["actor_initial"]["document_catalog"][0]["document_id"]]):
            assert evaluation.reference(case, state) == frozen.reference(case, state)
            state, _ = evaluation.advance(case, state, requested)
        assert evaluation.reference(case, state) == frozen.reference(case, state)


def _toy_case(active_trigger: bool) -> dict:
    latent = generator.sample_latent("heating_defect", "boiler", 1, "dev")
    latent["conditional_active"] = active_trigger
    latent["availability"] = {d: "final_t1" for d in latent["availability"]}
    latent["availability"]["A7"] = "irrelevant"; latent["availability"]["A6"] = "unavailable"
    latent["motifs"] = [{"motif": "possession_report", "document_id": "A1"}]
    brief = generator.build_brief(latent)
    texts = {p["id"]: f"TEXT[{p['id']}]" for p in brief["paragraphs"]}
    return generator.assemble_case(latent, brief, texts)


def test_generated_case_validates_and_activation_changes_reference() -> None:
    case = _toy_case(active_trigger=True)
    evaluation._validate_case(case)
    state = evaluation.initial_state(case)
    ref0 = evaluation.reference(case, state)
    assert "R-HEALTH" not in ref0["active_critical_requirement_ids"]
    assert ref0["document_states"][4]["state"] == "pending"          # A5 pending before the trigger fires
    state1, receipt = evaluation.advance(case, state, ["A2", "A1"])
    ref1 = evaluation.reference(case, state1)
    assert "R-HEALTH" in ref1["active_critical_requirement_ids"]
    assert ref1["document_states"][4]["state"] == "missing"
    # unavailable artifact becomes not_required after the negative return
    state2, _ = evaluation.advance(case, state1, ["A6"])
    ref2 = evaluation.reference(case, state2)
    assert ref2["document_states"][5]["state"] == "not_required"
    inactive = _toy_case(active_trigger=False)
    s = evaluation.initial_state(inactive); s, _ = evaluation.advance(inactive, s, ["A2"])
    assert "R-HEALTH" not in evaluation.reference(inactive, s)["active_critical_requirement_ids"]


def test_hearsay_receipt_metric_counts_unreturned_received_claims() -> None:
    case = _toy_case(active_trigger=False)
    state = evaluation.initial_state(case)
    ref = evaluation.reference(case, state)
    catalog = [r["document_id"] for r in case["actor_initial"]["document_catalog"]]
    plan = {"document_states": [{"document_id": d, "state": ("received" if d == "A1" else "missing"), "source_refs": []} for d in catalog],
            "checklist_document_ids": [], "requested_document_ids": [], "next_action": {"kind": "proceed", "document_ids": []}, "ready": True, "justifications": []}
    m = evaluation.score(case, state, plan)
    assert m["hearsay_receipts"] == 1 and m["premature_readiness"] == 1
