from __future__ import annotations

from pathlib import Path
import json

import pytest

from casepath_api.claim_workspace_intake_v1 import compile_intake_assessment
from casepath_api.claim_workspace_v1 import ClaimWorkspaceError, ClaimWorkspaceService
from casepath_api.draft_request_v1 import COMPILER_ID, compile_draft_request
from casepath_api.storage import Storage
from casepath_api.validate_journal import validate_journal
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root


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
    assert "Mein Sohn hustet mehr" in draft["body_markdown"]
    assert "Seit Wochen wird die Ecke im Kinderzimmer schwarz" in draft["body_markdown"]
    assert "Ärztliche Bestätigung" in draft["body_markdown"]
    assert "die Meldung an die Vermieterschaft belegen können" in draft["body_markdown"]
    assert "meldung an die vermieterschaft" not in draft["body_markdown"]
    assert "Medical confirmation" not in draft["body_markdown"]
    assert "Ist die Heizung betroffen?" in draft["questions"]


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


def test_previous_sealed_head_draft_journal_boots_without_rewriting_it(tmp_path: Path) -> None:
    fixture = json.loads((Path(__file__).parent / "fixtures" / "7440d6a-workspace-draft-journal.json").read_text())
    assert fixture["source_commit"] == "7440d6a"
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
