from __future__ import annotations

from collections import defaultdict

from casepath_api.assessment_grammar_v1 import _candidate_deadline, _verdict, simulate_condition
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


GOLDEN_ROSTER_SHA256 = "f78686f197fceaad0be8304d17b3beba183ea4d7ff428f66adcdcb39abac85d2"


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
    assert flagship["question_cards"][0]["id"] == "deadline_anchor"
    assert flagship["question_cards"][2]["document_types"] == ["payment_deadline_letter", "rent_ledger_payment_evidence"]

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
    assert {card["id"] for card in mould["question_cards"]} == {"heating", "specialist_needed", "deposit_considered"}

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
    assert next(card for card in rent["question_cards"] if card["id"] == "renovation")["if_no"].endswith("not requested.")


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
    previous_v2 = compile_intake_assessment(corpus, "clm_f69b1747447bc221", legacy_v2=True)
    assert previous_v2["assessment_sha256"] == "5be638263bc57a47b7584f3d3c8d1e65be71217939b17aeb3be797f954b0eedf"
    assert validate_recorded_intake_assessment(previous_v2, corpus=corpus, claim_id="clm_f69b1747447bc221") == previous_v2


def test_what_if_replans_spouse_route_without_changing_saved_assessment() -> None:
    corpus = PublicCorpus(default_workspace_corpus_root())
    claim_id = "clm_f69b1747447bc221"
    saved = _assessment(corpus, claim_id)
    saved_hash = saved["assessment_sha256"]
    domain = "lease_termination_dispute"
    false = simulate_condition(corpus, claim_id, domain, saved, "family_home", "false")
    true = simulate_condition(corpus, claim_id, domain, saved, "family_home", "true", "false")
    unresolved = simulate_condition(corpus, claim_id, domain, saved, "family_home", "unresolved", "true")
    route = lambda result: next(row for row in result["scenario"]["documents"] if row["document_type"] == "spouse_notice_copy")
    assert route(false)["route_state"] == "not_needed"
    assert route(true)["route_state"] == "held_not_reviewed"
    assert route(unresolved)["route_state"] == "held_behind_question"
    spouse = lambda result: next(row for row in result["changes"] if row["label"] == "Separate spouse notice")
    assert spouse(false)["sign"] == "-"
    assert spouse(true)["sign"] == "+"
    assert spouse(true)["authority"]["article"] == "Art. 266n"
    assert spouse(unresolved)["sign"] == "?"
    assert saved["assessment_sha256"] == saved_hash
    assert saved["conditions"]["family_home"]["verdict"] == "true"
