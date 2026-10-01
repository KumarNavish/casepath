from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json

import pytest

from casepath_api.claim_workspace_intake_v1 import compile_intake_assessment
from casepath_api.claim_workspace_v1 import ClaimWorkspaceError, ClaimWorkspaceService
from casepath_api.draft_request_v1 import COMPILER_ID, CAUSAL_COMPILER_ID, compile_draft_request
from casepath_api.storage import Storage
from casepath_api.validate_journal import validate_journal
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root


def _german_causal_questions() -> dict:
    return {
        "language": "de-CH", "assessment_sha256": "b" * 64, "process_graph_sha256": "a" * 64,
        "noticed": [], "steps": [{"node_id": "lt_deadline", "label": "Preserve deadline"}],
        "conditions": {"termination_received": {"verdict": "unresolved", "quote": None}},
        "candidate_deadline": {"question": "On which dates did each notice arrive?"},
        "question_cards": [
            {"id": "deadline_anchor", "question": "On which dates did each notice arrive?", "document_types": ["proof_of_receipt"]},
            {"id": "termination_received", "question": "Does termination received apply?", "document_types": ["proof_of_receipt"]},
            {"id": "complete_notice", "question": "Can you send the complete second page of each notice?", "document_types": ["proof_of_receipt"]},
            {"id": "process:custom", "question": "What establishes whether 'Keep My Custom Label' applies?", "document_types": []},
        ],
        "documents": [{"document_type": "proof_of_receipt", "label": "Proof of receipt", "route_state": "held_behind_question",
                       "required_at_node_ids": ["lt_deadline"], "condition_flag": None, "authority": None,
                       "reason": "The process condition is unresolved."}],
    }


def _draft(claim_id: str) -> dict:
    corpus = PublicCorpus(default_workspace_corpus_root())
    assessment = compile_intake_assessment(corpus, claim_id)["claim_assessment"]
    draft = compile_draft_request(claim_id, assessment)
    assert draft == compile_draft_request(claim_id, assessment)
    assert draft["compiler_id"] == COMPILER_ID
    assert draft["status"] == "draft_not_sent"
    return draft


def test_flagship_request_traces_documents_to_quotes_and_articles() -> None:
    draft = _draft("clm_f69b1747447bc221")
    assert draft["body_markdown"].startswith("Dear Robin Foster,\n")
    requested = {row["document_type"]: row for row in draft["requested"]}
    assert {"proof_of_receipt", "notice_period_evidence", "spouse_notice_copy"} <= requested.keys()
    assert requested["spouse_notice_copy"]["article"] == "Art. 266n"
    assert "My wife's arrived on Wednesday" in requested["spouse_notice_copy"]["customer_quote"]
    assert all(row["step"] and row["customer_quote"] for row in requested.values())
    assert "rent_ledger_payment_evidence" in {row["document_type"] for row in draft["not_requested"]}
    assert "On which dates did each notice arrive?" in draft["questions"]
    assert "complete second page" in draft["body_markdown"].lower()


def test_german_health_handoff_keeps_customer_quote_and_german_copy() -> None:
    draft = _draft("clm_7ac806bd30792cfb")
    assert draft["kind"] == "specialist_handoff"
    assert draft["language"].startswith("de")
    assert draft["body_markdown"].startswith("Guten Tag,\n")
    assert "Mein Sohn hustet mehr" in draft["body_markdown"]
    assert "Seit Wochen wird die Ecke im Kinderzimmer schwarz" in draft["body_markdown"]
    assert "Ärztliche Bestätigung" in draft["body_markdown"]
    assert "die Meldung an die Vermieterschaft belegen können" in draft["body_markdown"]
    assert "meldung an die vermieterschaft" not in draft["body_markdown"]
    assert "Medical confirmation" not in draft["body_markdown"]
    assert "Ist die Heizung betroffen?" in draft["questions"]


def test_german_customer_request_uses_known_name_without_guessing_a_title() -> None:
    claim_id = "clm_f69b1747447bc221"
    corpus = PublicCorpus(default_workspace_corpus_root())
    assessment = deepcopy(compile_intake_assessment(corpus, claim_id)["claim_assessment"])
    assessment["language"] = "de-CH"
    draft = compile_draft_request(claim_id, assessment)
    assert draft["body_markdown"].startswith("Guten Tag Robin Foster,\n")


def test_ambiguous_tenant_names_keep_neutral_salutation() -> None:
    claim_id = "clm_f69b1747447bc221"
    corpus = PublicCorpus(default_workspace_corpus_root())
    assessment = deepcopy(compile_intake_assessment(corpus, claim_id)["claim_assessment"])
    source = next(item for item in assessment["noticed"] if item.get("fact_kind") == "named_party_candidate" and item["text"] == "Robin Foster")
    assessment["noticed"].append({**source, "text": "Another Person"})
    assert compile_draft_request(claim_id, assessment)["body_markdown"].startswith("Dear customer,\n")


def test_rent_request_asks_for_basis_without_renovation_breakdown() -> None:
    draft = _draft("clm_6f04d0907ecb96bb")
    assert "reference_rate_basis" in {row["document_type"] for row in draft["requested"]}
    assert "renovation_cost_breakdown" in {row["document_type"] for row in draft["not_requested"]}
    assert "On what date was the increase notified?" in draft["questions"]
    edited = compile_draft_request(
        draft["claim_id"],
        compile_intake_assessment(PublicCorpus(default_workspace_corpus_root()), draft["claim_id"])["claim_assessment"],
        edited_body=draft["body_markdown"] + "Handler note.\n",
    )
    assert edited["draft_sha256"] != draft["draft_sha256"]
    assert edited["requested"] == draft["requested"]


def test_draft_and_handler_edit_replay_from_workspace_journal(tmp_path: Path) -> None:
    corpus = PublicCorpus(default_workspace_corpus_root())
    workspace = ClaimWorkspaceService(Storage(str(tmp_path / "casepath.db")), corpus=corpus)
    claim_id = "clm_f69b1747447bc221"
    workspace.seed(timestamp="2026-09-24T08:00:00+00:00")
    initial = workspace.store.recover(claim_id)
    started = workspace.start(
        claim_id, expected_revision=initial["revision"],
        idempotency_key="workspace.start.draft.0001",
        timestamp="2026-09-24T08:00:01+00:00",
    )["state"]
    args = dict(
        expected_revision=started["revision"],
        expected_state_sha256=started["state_sha256"],
        idempotency_key="workspace.draft.initial.0001",
    )
    first = workspace.record_draft(claim_id, **args, timestamp="2026-09-24T08:00:02+00:00")
    assert workspace.record_draft(claim_id, **args, timestamp="2026-09-24T08:00:03+00:00") == first
    saved = workspace.drafts(claim_id)
    assert saved["latest"]["event_sha256"] == first["event_sha256"]
    assert saved["latest"]["body_sha256"]
    assert workspace._triage_snapshot([workspace.store.recover(claim_id)])[claim_id]["draft_ready"] is True
    assert workspace.store.recover(claim_id)["workflow_state"] == "in_review"
    revised_body = saved["latest"]["body_markdown"] + "Please call before sending.\n"
    revision = workspace.record_draft(
        claim_id, expected_revision=first["state"]["revision"],
        expected_state_sha256=first["state"]["state_sha256"],
        idempotency_key="workspace.draft.edit.0001",
        edited_body=revised_body,
        replaces_event_sha256=first["event_sha256"],
        timestamp="2026-09-24T08:00:04+00:00",
    )
    assert revision["event_sha256"] != first["event_sha256"]
    assert workspace.drafts(claim_id)["latest"]["body_markdown"] == revised_body
    restarted = ClaimWorkspaceService(Storage(str(tmp_path / "casepath.db")), corpus=corpus)
    assert restarted.drafts(claim_id) == workspace.drafts(claim_id)
    with pytest.raises(ClaimWorkspaceError, match="stale"):
        restarted.record_draft(
            claim_id, expected_revision=revision["state"]["revision"],
            expected_state_sha256=revision["state"]["state_sha256"],
            idempotency_key="workspace.draft.bad-edit.0001",
            edited_body="wrong branch", replaces_event_sha256=first["event_sha256"],
        )


@pytest.mark.parametrize("source_commit", ["7440d6a", "6678cd6"])
def test_previous_sealed_head_draft_journal_boots_without_rewriting_it(tmp_path: Path, source_commit: str) -> None:
    fixture = json.loads((Path(__file__).parent / "fixtures" / f"{source_commit}-workspace-draft-journal.json").read_text())
    assert fixture["source_commit"] == source_commit
    database = tmp_path / "casepath.db"
    workspace = ClaimWorkspaceService(Storage(str(database)), corpus=PublicCorpus(default_workspace_corpus_root()))
    columns = ("session_id", "loop_id", "sequence", "idempotency_key", "command_sha256", "event_sha256", "event_json", "created_at")
    with workspace.storage.connect() as connection:
        connection.executemany(
            f"INSERT INTO claim_loop_events ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
            [tuple(event[column] for column in columns) for event in fixture["events"]],
        )
    recorded = json.loads(fixture["events"][-1]["event_json"])["command"]["draft"]
    assert workspace.drafts(fixture["claim_id"])["latest"]["body_markdown"] == recorded["body_markdown"]
    assert workspace.store.recover(fixture["claim_id"])["revision"] == 3
    assert validate_journal(database)["event_count"] == 3


@pytest.mark.parametrize("claim_id,expected_sha256", [
    ("clm_f69b1747447bc221", "fb46fd3d9abbdf663df9f38d7233a0af8f88fd888b94b582620e3d339a751f20"),
    ("clm_7ac806bd30792cfb", "e9abf8fd05e675bc40e7ce90cfa171aefaa38ad335afee07b47ba0d456f463a4"),
    ("clm_6f04d0907ecb96bb", "32a73ee2d4633957f90dce7905bca79d09b3fc3379120736fe880a8a8977583a"),
])
def test_previous_sealed_draft_compiler_replays_exact_bytes(claim_id: str, expected_sha256: str) -> None:
    corpus = PublicCorpus(default_workspace_corpus_root())
    assessment = compile_intake_assessment(corpus, claim_id, legacy_v2=True)["claim_assessment"]
    assert compile_draft_request(claim_id, assessment, variant="legacy_7440")["draft_sha256"] == expected_sha256


@pytest.mark.parametrize("claim_id,expected_sha256", [
    ("clm_f69b1747447bc221", "2250867d2c82f7ebe3f02c4965242c759fbc5fb4629ed23706cc4530643e04a1"),
    ("clm_7ac806bd30792cfb", "90a1b68b89475311603b969731ec443e903fbc97ded30ab650bfca32fcddcabb"),
    ("clm_6f04d0907ecb96bb", "9f0ccfdcab758bd4fb8bc68b107ccef13288c2e9741239b949eb538a2a88a0ae"),
])
def test_prior_named_draft_compiler_replays_exact_bytes(claim_id: str, expected_sha256: str) -> None:
    corpus = PublicCorpus(default_workspace_corpus_root())
    assessment = compile_intake_assessment(corpus, claim_id)["claim_assessment"]
    assert compile_draft_request(claim_id, assessment, variant="sealed_1_1")["draft_sha256"] == expected_sha256


def test_corrected_family_route_draft_explains_actual_upstream_questions() -> None:
    from casepath_api.causal_process_v1 import build_graph, apply_edit, evaluate
    claim_id = "clm_f69b1747447bc221"
    corpus = PublicCorpus(default_workspace_corpus_root())
    intake = compile_intake_assessment(corpus, claim_id)
    graph = build_graph(corpus, claim_id, {**intake["claim_assessment"], "claim_type": intake["claim_type"]})
    assessment = evaluate(apply_edit(graph, {"type": "conditions.set", "flag": "family_home", "verdict": "false", "actor": "Handler", "reason": "The family-home branch does not apply."}))
    assert assessment["conditions"]["extension_relevant"]["verdict"] == "true"
    draft = compile_draft_request(claim_id, assessment)
    excluded = {row["document_type"]: row for row in draft["not_requested"]}
    for document_type in ("stated_reason", "housing_search_log", "landlord_correspondence"):
        assert excluded[document_type]["reason"] == "We first need to clarify: Were any rent payments overdue?"
    assert "None" not in draft["body_markdown"]
    assert "extension relevant is still a question" not in draft["body_markdown"]
    assert "?." not in draft["body_markdown"]
    assert "Were any rent payments overdue?" in draft["questions"]
    assert draft["compiler_id"] == CAUSAL_COMPILER_ID
    german = compile_draft_request(claim_id, {**assessment, "language": "de-CH"})
    german_reasons = {row["document_type"]: row["reason"] for row in german["not_requested"]}
    assert german_reasons["housing_search_log"] == "Zuerst müssen wir Folgendes klären: Waren Mietzinszahlungen ausstehend?"
    assert "None" not in german["body_markdown"]
    # A previously saved graph draft remains reproducible under its own compiler.
    old = compile_draft_request(claim_id, assessment, variant="sealed_1_2")
    assert old["compiler_id"] == COMPILER_ID
    assert "None is still a question" in old["body_markdown"]


def test_current_legacy_assessment_keeps_exact_previous_compiler_output() -> None:
    claim_id = "clm_f69b1747447bc221"
    assessment = compile_intake_assessment(PublicCorpus(default_workspace_corpus_root()), claim_id)["claim_assessment"]
    assert compile_draft_request(claim_id, assessment) == compile_draft_request(claim_id, assessment, variant="sealed_1_2")


@pytest.mark.parametrize("variant", ["sealed_1_2", "causal_1_0", "causal_1_1"])
def test_saved_prior_graph_draft_replays_before_corrected_draft(tmp_path: Path, variant: str) -> None:
    from casepath_api.causal_workspace_v1 import CausalWorkspaceService, effective_assessment
    from test_causal_workspace_v1 import _start, _edit
    claim_id = "clm_f69b1747447bc221"
    storage = Storage(str(tmp_path / "claims.db"))
    workspace = ClaimWorkspaceService(storage, corpus=PublicCorpus(default_workspace_corpus_root()))
    workspace.seed(timestamp="2026-10-01T08:00:00+00:00")
    _start(workspace, claim_id)
    _edit(CausalWorkspaceService(workspace), {"type": "conditions.set", "flag": "family_home", "verdict": "false"})
    state = workspace.store.recover(claim_id)
    old = compile_draft_request(claim_id, effective_assessment(state), variant=variant)
    saved, event, _ = workspace.store.append(claim_id=claim_id, event_type="WORKSPACE_DRAFT_RECORDED",
        idempotency_key="draft.previous.graph.0001", expected_revision=state["revision"],
        command={"draft": old, "replaces_event_sha256": None, "request_expected_revision": state["revision"]},
        timestamp="2026-10-01T09:00:00+00:00")
    restarted = ClaimWorkspaceService(storage, corpus=workspace.corpus)
    assert restarted.drafts(claim_id)["latest"]["draft_sha256"] == old["draft_sha256"]
    restarted.record_draft(claim_id, expected_revision=saved["revision"], expected_state_sha256=saved["state_sha256"],
        replaces_event_sha256=event["event_sha256"], idempotency_key="draft.corrected.graph.0001")
    assert restarted.drafts(claim_id)["latest"]["compiler_id"] == CAUSAL_COMPILER_ID
    assert "None is still a question" not in restarted.drafts(claim_id)["latest"]["body_markdown"]


@pytest.mark.parametrize("language", ["en", "de-CH"])
def test_graph_draft_omits_empty_document_sections_when_prerequisites_block(language: str) -> None:
    from casepath_api.causal_process_v1 import build_graph, apply_edit, evaluate, seal_graph
    claim_id = "clm_f69b1747447bc221"
    corpus = PublicCorpus(default_workspace_corpus_root())
    intake = compile_intake_assessment(corpus, claim_id)
    graph = build_graph(corpus, claim_id, {**intake["claim_assessment"], "claim_type": intake["claim_type"], "language": language})
    for document in graph["document_catalog"]:
        document["held_files"] = []
    graph = seal_graph(graph)
    graph = apply_edit(graph, {"type": "node.add", "node": {"node_id": "check_permission", "label": "Check permission", "entry": True}})
    graph = apply_edit(graph, {"type": "edge.add", "edge": {"edge_id": "permission.before.deadline", "source_node_id": "check_permission", "target_node_id": "lt_deadline", "relation": "requires"}})
    assessment = evaluate(graph)
    draft = compile_draft_request(claim_id, assessment)
    assert draft["requested"] == draft["held"] == []
    for heading in ("## Please send", "## Already held", "## Bitte senden Sie uns", "## Bereits vorhanden"):
        assert heading not in draft["body_markdown"]
    assert ("## Offene Fragen" if language.startswith("de") else "## Questions") in draft["body_markdown"]
    old = compile_draft_request(claim_id, assessment, variant="causal_1_0")
    assert ("## Bitte senden Sie uns" if language.startswith("de") else "## Please send") in old["body_markdown"]


def test_german_causal_draft_localizes_known_questions_and_deferred_reasons_only():
    assessment = _german_causal_questions()
    draft = compile_draft_request("test-claim", assessment)
    assert draft["compiler_id"] == "casepath.workspace-causal-request-draft-compiler/1.2.0"
    expected = ["An welchen Tagen haben Sie die einzelnen Kündigungsschreiben erhalten?",
                "Haben Sie die Kündigung erhalten?",
                "Können Sie die vollständige zweite Seite jedes Kündigungsschreibens senden?"]
    assert draft["questions"] == expected + ["What establishes whether 'Keep My Custom Label' applies?"]
    assert draft["not_requested"][0]["reason"] == "Zuerst müssen wir Folgendes klären: " + " ".join(expected)
    assert draft["body_markdown"].count(expected[0]) == 2  # one question plus its document explanation
    for card in assessment["question_cards"][:3]:
        assert card["question"] not in draft["body_markdown"]
    assert "?." not in draft["body_markdown"]


@pytest.mark.parametrize("question,translated", [
    ("On what date was the increase notified?", "An welchem Tag haben Sie die Mietzinserhöhungsanzeige erhalten?"),
    ("Does claim received apply?", "Haben Sie die Mietzinserhöhungsanzeige erhalten?"),
    ("Does health effects apply?", "Werden gesundheitliche Beschwerden geltend gemacht?"),
    ("Does mold apply?", "Liegt ein Schimmelbefall vor?"),
    ("Does extension relevant apply?", "Wird eine Erstreckung des Mietverhältnisses beantragt?"),
])
def test_german_causal_draft_localizes_remaining_builtin_questions(question, translated):
    assessment = _german_causal_questions()
    assessment["candidate_deadline"] = None
    assessment["question_cards"] = [{"id": "builtin", "question": question, "document_types": ["proof_of_receipt"]}]
    draft = compile_draft_request("test-claim", assessment)
    assert draft["questions"] == [translated]
    assert draft["not_requested"][0]["reason"] == "Zuerst müssen wir Folgendes klären: " + translated


@pytest.mark.parametrize("variant,expected_sha256", [
    ("causal_1_0", "cd7b91522e8602e7861cfd487579079cf74e765b6ca29a7138bc3072f86a2f67"),
    ("causal_1_1", "c20ab586b879788fd55375bfa6aac03f8f21ebdda59fb6fd9e03b38c7b7fc434"),
    ("sealed_1_2", "8921696fa544508c25e353450b8fa23fa10615498368c6982588749e62b4755d"),
    ("sealed_1_1", "819ebd6d9d0e49d84539d9ea239d3615f3897df9043c05de66cc485227b7cc29"),
    ("unversioned_current", "46100279b92c6199b1233d525a8567d502d540f8c17f4280ee1ca1af31f41e9b"),
    ("legacy_7440", "1d67ec21c2101f29ee35f3cfbf6550a75c3eb22c3667f7e5273361343e8e4855"),
])
def test_localized_causal_compiler_preserves_every_previous_variant_identity(variant, expected_sha256):
    assert compile_draft_request("test-claim", _german_causal_questions(), variant=variant)["draft_sha256"] == expected_sha256
