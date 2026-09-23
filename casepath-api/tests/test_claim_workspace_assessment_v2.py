from __future__ import annotations

from collections import defaultdict

from casepath_api.assessment_grammar_v1 import _candidate_deadline, _verdict
from casepath_api.claim_workspace_intake_v1 import (
    _compile_intake_assessment_v1_1,
    compile_intake_assessment,
    validate_recorded_intake_assessment,
)
from casepath_api.workspace_corpus import (
    PublicCorpus,
    default_workspace_corpus_root,
    digest_value,
)


GOLDEN_ROSTER_SHA256 = "14791ea423c5270deecfd74619df5025c23dfacda077669b16acecab9879a565"


def _assessment(corpus: PublicCorpus, claim_id: str) -> dict:
    return compile_intake_assessment(corpus, claim_id)["claim_assessment"]


def test_three_demo_claims_have_distinct_grounded_routes() -> None:
    corpus = PublicCorpus(default_workspace_corpus_root())
    flagship = _assessment(corpus, "clm_f69b1747447bc221")
    assert flagship["conditions"]["termination_received"]["quote"] == "My form arrived on Monday"
    assert flagship["conditions"]["family_home"]["quote"] == (
        "My wife's arrived on Wednesday and says the end of July"
    )
    assert flagship["conditions"]["extension_relevant"]["quote"] == (
        "prepare a joint extension request"
    )
    assert flagship["conditions"]["arrears"]["verdict"] == "unresolved"
    assert flagship["conflicts"][0]["fact"] == "termination end date"
    assert {source["value"] for source in flagship["conflicts"][0]["sources"]} == {
        "30. Juni", "31. Juli"
    }
    routes = {row["document_type"]: row for row in flagship["documents"]}
    assert routes["termination_notice"]["route_state"] == "held_not_reviewed"
    assert len(routes["termination_notice"]["held_files"]) == 1
    assert routes["spouse_notice_copy"]["route_state"] == "held_not_reviewed"
    assert routes["proof_of_receipt"]["route_state"] == "needed_now"
    assert routes["payment_deadline_letter"]["request"] is False
    assert flagship["candidate_deadline"]["date"] is None
    assert flagship["candidate_deadline"]["authority"]["article"] == "Art. 273"

    mould = _assessment(corpus, "clm_7ac806bd30792cfb")
    assert mould["conditions"]["health_effects"]["quote"] == "Mein Sohn hustet mehr"
    assert mould["conditions"]["mold"]["verdict"] == "true"
    assert mould["conditions"]["specialist_needed"]["verdict"] == "unresolved"
    assert "welche technische Ursache" in mould["conditions"]["specialist_needed"]["candidate_quote"]
    assert mould["steps"][1]["state"] == "active"
    assert mould["steps"][1]["node_id"] == "dh_safety"
    mould_routes = {row["document_type"]: row for row in mould["documents"]}
    assert mould_routes["medical_confirmation"]["route_state"] == "needed_now"
    assert mould_routes["dated_photos"]["route_state"] == "held_not_reviewed"
    assert mould_routes["heating_service_report"]["request"] is False
    assert mould["language"] == "de-CH"

    rent = _assessment(corpus, "clm_6f04d0907ecb96bb")
    assert rent["conditions"]["reference_rate"]["quote"] == (
        "names a reference rate dated two weeks after the manager's signature"
    )
    assert rent["conditions"]["renovation"]["verdict"] == "unresolved"
    rent_routes = {row["document_type"]: row for row in rent["documents"]}
    assert rent_routes["rent_increase_notice"]["route_state"] == "needed_now"
    assert rent_routes["reference_rate_basis"]["request"] is True
    assert rent_routes["renovation_cost_breakdown"]["request"] is False
    assert rent["candidate_deadline"]["date"] is None
    assert rent["candidate_deadline"]["authority"]["article"] == "Art. 270b"


def test_grammar_keeps_denials_and_uncertainty_separate() -> None:
    denied = _verdict("There was no renovation work.", "renovation", "message")
    assert denied["verdict"] == "false"
    assert denied["quote"] == "no renovation work"
    unknown = _verdict("Perhaps there is mould behind the wall.", "mold", "message")
    assert unknown["verdict"] == "unresolved"
    assert unknown["quote"] is None
    assert unknown["candidate_quote"] == "mould"

    corpus = PublicCorpus(default_workspace_corpus_root())
    deadline = _candidate_deadline(
        "lease_termination_dispute",
        "The notice was received on 03 January 2025.",
        corpus.source_registry("clm_f69b1747447bc221"),
    )
    assert deadline is not None
    assert deadline["status"] == "candidate_to_verify"
    assert deadline["anchor_date"] == "2025-01-03"
    assert deadline["date"] == "2025-02-02"


def test_corpus_assessment_golden_roster_and_legacy_replay() -> None:
    corpus = PublicCorpus(default_workspace_corpus_root())
    rows = []
    profiles: dict[str, set[tuple]] = defaultdict(set)
    quoted_claims = 0
    for claim_id in sorted(corpus.bindings):
        assessment = compile_intake_assessment(corpus, claim_id)
        assert validate_recorded_intake_assessment(
            assessment, corpus=corpus, claim_id=claim_id
        ) == assessment
        detail = assessment["claim_assessment"]
        rows.append({"claim_id": claim_id, "assessment_sha256": assessment["assessment_sha256"]})
        profiles[assessment["claim_type"]].add(tuple(
            (key, value["verdict"]) for key, value in detail["conditions"].items()
        ))
        quoted_claims += any(
            value["verdict"] in {"true", "false"} and value["quote"]
            for value in detail["conditions"].values()
        )
        for document in detail["documents"]:
            if document["condition_flag"] and detail["conditions"][document["condition_flag"]]["verdict"] != "true":
                assert document["request"] is False
    assert quoted_claims >= 120
    assert all(len(value) >= 2 for value in profiles.values())
    assert digest_value(rows) == GOLDEN_ROSTER_SHA256

    old = _compile_intake_assessment_v1_1(corpus, "clm_f69b1747447bc221")
    assert validate_recorded_intake_assessment(
        old, corpus=corpus, claim_id="clm_f69b1747447bc221"
    ) == old
