from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import time

import pytest

from casepath_api.data import ARTIFACTS, CLAIMS, HISTORICAL_CASES
from casepath_api.evidence_relations import (
    derive_evidence_relations,
    apply_evidence_relations,
)
from casepath_api.pipeline_v15 import (
    ClaimPipeline,
    digest,
    semantic_checklist_dto,
    semantic_process_dto,
)
from casepath_api.precedent_ranking import rank_precedents
from casepath_api.projections import checklist_derived_sections
from casepath_api.storage import Storage
from casepath_api.validation import ContractValidationError


def _wait(storage: Storage, run_id: str) -> dict:
    for _ in range(800):
        run = storage.get_run(run_id)
        if run and run["status"] in {"complete", "failed"}:
            return run
        time.sleep(0.01)
    raise AssertionError("run timeout")


@pytest.fixture
def runtime(tmp_path: Path) -> tuple[Storage, ClaimPipeline]:
    storage = Storage(str(tmp_path / "casepath.db"))
    return storage, ClaimPipeline(storage, pace_seconds=0)


def _assert_relations(result: dict) -> None:
    expected = derive_evidence_relations(
        result["process"], result["checklist"]["items"]
    )
    for item in result["checklist"]["items"]:
        assert {
            "node_ids": item["node_ids"],
            "node_id": item["node_id"],
            "current_path": item["current_path"],
        } == expected[item["item_id"]]


def _verify_result(
    pipeline: ClaimPipeline,
    storage: Storage,
    run: dict,
    result: dict,
    *,
    extension: bool = False,
) -> dict:
    return pipeline._verification_report(  # noqa: SLF001
        CLAIMS[run["claim_id"]],
        {
            "facts": result["facts"],
            "category": result["category"],
            "subcategory": result["subcategory"],
        },
        result["legal_research"],
        result["process"],
        result["checklist"],
        result["precedents"],
        result["precedent_ranking"],
        storage.memories(),
        allowed_process_extension_node_ids=(
            {"ventilation_dispute"} if extension else None
        ),
        allowed_process_extension_edge_pairs=(
            {
                ("evidence_gap", "ventilation_dispute"),
                ("ventilation_dispute", "causation"),
            }
            if extension
            else None
        ),
    )


def test_process_requirements_are_reciprocal_before_review_after_review_and_memory(
    runtime,
):
    storage, pipeline = runtime
    flagship = _wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    assert flagship["status"] == "complete", flagship.get("error")
    _assert_relations(flagship["result"])
    technical = next(
        item
        for item in flagship["result"]["checklist"]["items"]
        if item["item_id"] == "technical_assessment"
    )
    assert technical["node_ids"] == [
        "causation",
        "responsibility",
        "building_defect",
        "tenant_use",
        "mixed_cause",
        "evidence_gap",
    ]

    reviewed = pipeline.review(
        flagship["run_id"],
        {
            "decision": "approve_with_edit",
            "building_envelope_mode": "conditional",
            "confidence": 0.9,
            "justification": "Generated-demo edit only.",
        },
    )
    _assert_relations(reviewed["result"])
    reviewed_use = next(
        item
        for item in reviewed["result"]["checklist"]["items"]
        if item["item_id"] == "use_evidence"
    )
    assert reviewed_use["node_ids"] == ["ventilation_dispute"]

    later = _wait(storage, pipeline.create("DEMO-MOULD-002"))
    assert later["status"] == "complete", later.get("error")
    _assert_relations(later["result"])
    later_items = {
        item["item_id"]: item for item in later["result"]["checklist"]["items"]
    }
    assert later_items["management_position"]["node_ids"] == [
        "dispute",
        "ventilation_dispute",
    ]
    assert later_items["use_evidence"]["node_ids"] == ["ventilation_dispute"]
    assert later["result"]["memory_application"]["model_acceptance_reused"] is False


@pytest.mark.parametrize("field,value", [("node_id", "scope"), ("current_path", False)])
def test_verifier_rejects_forged_existing_evidence_relation(runtime, field, value):
    storage, pipeline = runtime
    run = _wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    forged = deepcopy(run["result"])
    target = next(
        item
        for item in forged["checklist"]["items"]
        if item["item_id"] == "technical_assessment"
    )
    target[field] = value
    with pytest.raises(ContractValidationError, match="reciprocal projection"):
        pipeline._verification_report(  # noqa: SLF001
            CLAIMS[run["claim_id"]],
            {"facts": forged["facts"]},
            forged["legal_research"],
            forged["process"],
            forged["checklist"],
            forged["precedents"],
        )


def test_law_passages_questions_and_process_joins_fail_closed(runtime):
    storage, pipeline = runtime
    run = _wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    for mutate in (
        lambda value: value["legal_research"]["sources"][0].update(
            passage_text="tampered official passage"
        ),
        lambda value: value["legal_research"]["questions"][0][
            "process_node_ids"
        ].append("unknown-node"),
        lambda value: value["legal_research"]["sources"].pop(0),
    ):
        forged = deepcopy(run["result"])
        mutate(forged)
        with pytest.raises(ContractValidationError, match="versioned official-source"):
            pipeline._verification_report(  # noqa: SLF001
                CLAIMS[run["claim_id"]],
                {"facts": forged["facts"]},
                forged["legal_research"],
                forged["process"],
                forged["checklist"],
                forged["precedents"],
            )


def test_attachment_ablation_removes_the_fact_grounding_boundary(runtime):
    storage, pipeline = runtime
    run = _wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    ablated_claim = deepcopy(CLAIMS[run["claim_id"]])
    ablated_claim["artifact_ids"].remove("art_lease")
    with pytest.raises(ContractValidationError, match="unknown source"):
        pipeline._verification_report(  # noqa: SLF001
            ablated_claim,
            {"facts": run["result"]["facts"]},
            run["result"]["legal_research"],
            run["result"]["process"],
            run["result"]["checklist"],
            run["result"]["precedents"],
        )


def test_visual_annotation_is_bound_to_the_exact_observable_image(runtime):
    storage, pipeline = runtime
    run = _wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    refs = [
        ref
        for fact in run["result"]["facts"]
        for ref in fact["source_refs"]
        if ref["locator_kind"] == "visual_observation"
    ]
    assert refs
    assert refs[0]["image_sha256"] == ARTIFACTS[refs[0]["artifact_id"]]["sha256"]
    forged = deepcopy(run["result"])
    ref = next(
        ref
        for fact in forged["facts"]
        for ref in fact["source_refs"]
        if ref["locator_kind"] == "visual_observation"
    )
    ref["image_sha256"] = "0" * 64
    with pytest.raises(ContractValidationError, match="observable image bytes"):
        pipeline._verification_report(  # noqa: SLF001
            CLAIMS[run["claim_id"]],
            {"facts": forged["facts"]},
            forged["legal_research"],
            forged["process"],
            forged["checklist"],
            forged["precedents"],
        )


def test_exact_three_precedents_bind_ranked_context_and_result(runtime):
    storage, pipeline = runtime
    run = _wait(storage, pipeline.create("DEMO-MOULD-002", knowledge_mode="baseline"))
    result = run["result"]
    ranking = result["precedent_ranking"]
    assert len(result["precedents"]) == 3
    assert ranking["selected_claim_ids"] == [
        item["claim_id"] for item in result["precedents"]
    ]
    assert ranking["context_hash"] == digest(ranking["context"])
    assert ranking["result_hash"] == digest(result["precedents"])
    assert [item["ranking"]["rank"] for item in result["precedents"]] == [1, 2, 3]

    forged = deepcopy(result)
    forged["precedents"][1]["ranking"]["context_hash"] = "0" * 64
    with pytest.raises(ContractValidationError, match="same context"):
        pipeline._verification_report(  # noqa: SLF001
            CLAIMS[run["claim_id"]],
            {"facts": forged["facts"]},
            forged["legal_research"],
            forged["process"],
            forged["checklist"],
            forged["precedents"],
        )


def test_verifier_recomputes_fully_rehashed_precedent_ranking(runtime):
    storage, pipeline = runtime
    run = _wait(storage, pipeline.create("DEMO-MOULD-002", knowledge_mode="baseline"))
    forged = deepcopy(run["result"])
    forged["precedents"].reverse()
    for rank, item in enumerate(forged["precedents"], 1):
        item["ranking"]["rank"] = rank
    forged["precedent_ranking"]["selected_claim_ids"] = [
        item["claim_id"] for item in forged["precedents"]
    ]
    forged["precedent_ranking"]["result_hash"] = digest(forged["precedents"])

    with pytest.raises(ContractValidationError, match="ranking"):
        pipeline._verification_report(  # noqa: SLF001
            CLAIMS[run["claim_id"]],
            {
                "facts": forged["facts"],
                "category": forged["category"],
                "subcategory": forged["subcategory"],
            },
            forged["legal_research"],
            forged["process"],
            forged["checklist"],
            forged["precedents"],
            forged["precedent_ranking"],
            storage.memories(),
        )


def test_verifier_rejects_known_but_unrelated_law_join(runtime):
    storage, pipeline = runtime
    run = _wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    forged = deepcopy(run["result"])
    intake = next(
        node for node in forged["process"]["nodes"] if node["node_id"] == "intake"
    )
    intake["legal_source_ids"].append("fedlex-or-259a")

    with pytest.raises(ContractValidationError, match="structured question registry"):
        pipeline._verification_report(  # noqa: SLF001
            CLAIMS[run["claim_id"]],
            {
                "facts": forged["facts"],
                "category": forged["category"],
                "subcategory": forged["subcategory"],
            },
            forged["legal_research"],
            forged["process"],
            forged["checklist"],
            forged["precedents"],
            forged["precedent_ranking"],
            storage.memories(),
        )


def test_verifier_rejects_rederived_but_unauthorized_evidence_ownership(runtime):
    storage, pipeline = runtime
    run = _wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    forged = deepcopy(run["result"])
    for node in forged["process"]["nodes"]:
        node["evidence_requirement_ids"] = [
            item_id
            for item_id in node["evidence_requirement_ids"]
            if item_id != "technical_assessment"
        ]
    intake = next(
        node for node in forged["process"]["nodes"] if node["node_id"] == "intake"
    )
    intake["evidence_requirement_ids"].append("technical_assessment")
    apply_evidence_relations(forged["process"], forged["checklist"]["items"])

    with pytest.raises(ContractValidationError, match="reciprocal projection"):
        pipeline._verification_report(  # noqa: SLF001
            CLAIMS[run["claim_id"]],
            {
                "facts": forged["facts"],
                "category": forged["category"],
                "subcategory": forged["subcategory"],
            },
            forged["legal_research"],
            forged["process"],
            forged["checklist"],
            forged["precedents"],
            forged["precedent_ranking"],
            storage.memories(),
        )


def test_verifier_rejects_caller_authorized_unknown_extension(runtime):
    storage, pipeline = runtime
    run = _wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    forged = deepcopy(run["result"])
    extension = deepcopy(forged["process"]["nodes"][-1])
    extension.update(
        node_id="forged_extension",
        state="inactive",
        fact_ids=[],
        legal_source_ids=[],
        evidence_requirement_ids=[],
        branches=[],
    )
    forged["process"]["nodes"].append(extension)
    forged["process"]["edges"].append(
        {
            "source": "evidence_gap",
            "target": "forged_extension",
            "condition": "forged",
            "state": "possible",
        }
    )

    with pytest.raises(ContractValidationError, match="exact governed memory extension"):
        pipeline._verification_report(  # noqa: SLF001
            CLAIMS[run["claim_id"]],
            {
                "facts": forged["facts"],
                "category": forged["category"],
                "subcategory": forged["subcategory"],
            },
            forged["legal_research"],
            forged["process"],
            forged["checklist"],
            forged["precedents"],
            forged["precedent_ranking"],
            storage.memories(),
            allowed_process_extension_node_ids={"forged_extension"},
            allowed_process_extension_edge_pairs={
                ("evidence_gap", "forged_extension")
            },
        )


def test_learning_semantic_hashes_ignore_only_run_specific_agent_attribution(runtime):
    storage, pipeline = runtime
    run = _wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    process = deepcopy(run["result"]["process"])
    checklist = deepcopy(run["result"]["checklist"])
    process["agent_contribution"] = {"call_id": "different-run"}
    process["nodes"][0]["agent_decision_contributions"] = [
        {"call_id": "different-run"}
    ]
    checklist["agent_contribution"] = {"call_id": "different-run"}
    checklist["items"][0]["agent_contribution"] = [
        {"call_id": "different-run"}
    ]
    assert digest(process) != digest(run["result"]["process"])
    assert digest(checklist) != digest(run["result"]["checklist"])
    assert semantic_process_dto(process) == semantic_process_dto(
        run["result"]["process"]
    )
    assert semantic_checklist_dto(checklist) == semantic_checklist_dto(
        run["result"]["checklist"]
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "process_fact_swap",
        "process_fact_reorder",
        "evidence_fact_swap",
        "semantic_role_move",
        "artifact_append",
        "same_fact_artifact_swap",
        "status_promotion",
    ],
)
def test_terminal_verifier_rejects_self_consistent_grounding_forgery(
    runtime, mutation
):
    storage, pipeline = runtime
    run = _wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    forged = deepcopy(run["result"])
    nodes = {node["node_id"]: node for node in forged["process"]["nodes"]}
    items = {item["item_id"]: item for item in forged["checklist"]["items"]}
    facts = {fact["fact_id"]: fact for fact in forged["facts"]}
    if mutation == "process_fact_swap":
        nodes["causation"]["fact_ids"] = ["fact_tenancy"]
    elif mutation == "process_fact_reorder":
        nodes["causation"]["fact_ids"].reverse()
    elif mutation == "evidence_fact_swap":
        items["building_envelope"]["fact_id"] = "fact_tenancy"
    elif mutation == "semantic_role_move":
        facts["fact_ventilation_allegation"]["semantic_role"] = None
        facts["fact_tenancy"]["semantic_role"] = (
            "management_ventilation_allegation"
        )
    elif mutation == "artifact_append":
        items["management_position"]["artifact_ids"].append("art_lease")
    elif mutation == "same_fact_artifact_swap":
        items["defect_notice"]["artifact_ids"] = ["art_delivery"]
    else:
        items["technical_assessment"]["status"] = "provided_sufficient"

    with pytest.raises(ContractValidationError):
        _verify_result(pipeline, storage, run, forged)


def test_terminal_verifier_accepts_bounded_dynamic_evidence_choices(runtime):
    storage, pipeline = runtime
    run = _wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    dynamic = deepcopy(run["result"])
    items = {item["item_id"]: item for item in dynamic["checklist"]["items"]}
    items["recurrence_chronology"]["status"] = "provided_sufficient"
    items["repair_history"]["artifact_ids"] = []
    for item_id in ("use_evidence", "remediation_plan", "completion_record"):
        items[item_id]["status"] = "conditional"
        items[item_id]["artifact_ids"] = []
    dynamic["checklist"].update(
        checklist_derived_sections(dynamic["checklist"]["items"])
    )
    understanding = {
        "facts": dynamic["facts"],
        "category": dynamic["category"],
        "subcategory": dynamic["subcategory"],
    }
    reranked = rank_precedents(
        current_claim_id=dynamic["claim_id"],
        understanding=understanding,
        process=dynamic["process"],
        checklist=dynamic["checklist"],
        memories=storage.memories(),
        corpus=HISTORICAL_CASES,
    )
    dynamic["precedents"] = reranked["results"]
    dynamic["precedent_ranking"] = reranked["receipt"]

    report = _verify_result(pipeline, storage, run, dynamic)

    assert report["valid"] is True
    assert report["computed"] is True


@pytest.mark.parametrize("claim_id", ["DEF-027-E0-DEMO", "DEMO-MOULD-002"])
def test_governed_extension_fact_is_independently_claim_bound(runtime, claim_id):
    storage, pipeline = runtime
    flagship = _wait(storage, pipeline.create("DEF-027-E0-DEMO"))
    pipeline.review(
        flagship["run_id"],
        {
            "decision": "approve_with_edit",
            "building_envelope_mode": "conditional",
            "confidence": 0.9,
            "justification": "Generated-demo edit only.",
        },
    )
    if claim_id == "DEF-027-E0-DEMO":
        run = storage.get_run(flagship["run_id"])
    else:
        run = _wait(storage, pipeline.create(claim_id))
    forged = deepcopy(run["result"])
    extension = next(
        node
        for node in forged["process"]["nodes"]
        if node["node_id"] == "ventilation_dispute"
    )
    extension["fact_ids"] = [
        "fact_tenancy" if claim_id == "DEF-027-E0-DEMO" else "later_fact_tenancy"
    ]

    with pytest.raises(ContractValidationError, match="relationship"):
        _verify_result(pipeline, storage, run, forged, extension=True)
