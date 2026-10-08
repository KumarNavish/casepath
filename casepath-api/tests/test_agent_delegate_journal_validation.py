"""Startup must validate mandate receipts without treating them as lifecycle authority."""
from argparse import Namespace
import json
from pathlib import Path
import sqlite3

import pytest

from casepath_api.agent_desk_v1 import AgentDeskServiceV1, DelegateJournal, EVENT_CONTRACT
from casepath_api.agent_work.authority import ExistingCasePathAuthority
from casepath_api.agent_work.service import AgentWorkService
from casepath_api.agent_work.store import WorkStore
from casepath_api import cli
from casepath_api.claim_workspace_v1 import WORKSPACE_SESSION_ID
from casepath_api.validate_journal import JournalValidationError, validate_journal
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root, digest_value
from test_workspace_claim_loop_v1 import _system
from test_cli_v1 import _history_verifier_module

CLAIM = "clm_f69b1747447bc221"


@pytest.fixture
def delegated_workspace(tmp_path):
    corpus = PublicCorpus(default_workspace_corpus_root())
    storage, workspace, _, facade = _system(tmp_path, corpus=corpus)
    binding = corpus.binding(CLAIM)
    workspace.store.append(claim_id=CLAIM, event_type="WORKSPACE_CLAIM_IMPORTED",
        idempotency_key="seed." + binding["binding_sha256"], expected_revision=0,
        command={"binding": binding, "corpus_identity": corpus.identity, "request_expected_revision": 0},
        timestamp="2026-10-01T08:00:00+00:00")
    parent = workspace.store.recover(CLAIM)
    parent = workspace.start(CLAIM, expected_revision=parent["revision"], idempotency_key="delegate.validator.start",
        process_model="casepath.causal-process/1.0.0")["state"]
    workspace.record_draft(CLAIM, expected_revision=parent["revision"], expected_state_sha256=parent["state_sha256"],
        idempotency_key="delegate.validator.draft")
    work = AgentWorkService(WorkStore(tmp_path / "work.sqlite3"), ExistingCasePathAuthority(lambda: workspace, lambda: facade))
    desk = AgentDeskServiceV1(workspace, work)
    agent = desk.claim(CLAIM)
    desk.control(CLAIM, action="pause", actor="Test handler", reason="Inspect the local draft before continuing.",
        expected_revision=agent["workspace_revision"], expected_state_sha256=agent["workspace_state_sha256"],
        expected_agent_revision=agent["agent_revision"], expected_agent_state_sha256=agent["agent_state_sha256"],
        idempotency_key="delegate.validator.pause")
    for kind, answer in (("source_conflict", "keep_open"), ("draft_approval", "approve")):
        agent = desk.claim(CLAIM)
        question = next(q for q in agent["questions"] if q["kind"] == kind)
        body = {"question_id": question["question_id"], "answer_id": answer, "actor": "Test handler", "reason": "",
            "expected_revision": agent["workspace_revision"], "expected_state_sha256": agent["workspace_state_sha256"]}
        preview = desk.preview_decision(CLAIM, **body)
        desk.apply_decision(CLAIM, **body, preview_sha256=preview["preview_sha256"],
            idempotency_key="delegate.validator." + kind, dispatch=False)
    assert work.store.list_runs(CLAIM) == []  # The saved pause is authoritative.
    yield Path(storage.path), workspace
    work.shutdown()


def test_global_validator_and_cli_replay_accept_scoped_delegate_receipts_without_writes(
    delegated_workspace, monkeypatch, capsys,
):
    database, workspace = delegated_workspace
    state = workspace.store.recover(CLAIM)
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = database.read_bytes()
    receipt = validate_journal(database)
    assert receipt["loop_count"] == 2 and receipt["event_count"] == 6
    assert receipt["receipt_sha256"] == digest_value({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    monkeypatch.setenv("CASEPATH_DB_PATH", str(database))
    assert cli.replay(Namespace(claim_id=CLAIM)) == 0
    replay = json.loads(capsys.readouterr().out)
    assert replay["revision"] == state["revision"] and replay["state_sha256"] == state["state_sha256"]
    assert replay["journal_verified"] is True
    assert replay["model_calls"] == replay["provider_calls"] == replay["credential_reads"] == replay["cost_usd"] == 0
    assert database.read_bytes() == before and workspace.store.recover(CLAIM) == state


def test_boot_history_validator_accepts_real_delegate_receipts_without_writes(delegated_workspace):
    database, workspace = delegated_workspace
    journal = DelegateJournal(workspace)
    state = workspace.store.recover(CLAIM)
    agent = journal.state(CLAIM)
    journal.append(CLAIM, "AGENT_MANDATE_RESUMED", {
        "actor": "Test handler", "reason": "Continue after inspecting the recorded approvals.",
        "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"],
        "expected_agent_revision": agent["revision"], "expected_agent_state_sha256": agent["state_sha256"],
    }, "delegate.validator.resume")
    agent = journal.state(CLAIM)
    journal.append(CLAIM, "AGENT_RECOVERY_REQUESTED", {
        "actor": "Test handler", "reason": "Inspect the exact local checkpoint before reconstructing its proposal.",
        "expected_revision": state["revision"], "expected_state_sha256": state["state_sha256"],
        "expected_agent_revision": agent["revision"], "expected_agent_state_sha256": agent["state_sha256"],
        "reconciliation": {"run_id": "work." + "a" * 32, "call_id": "reference.process_decision_mapping.4",
            "object_id": "lt_deadline", "expected_last_event_sha256": "b" * 64, "expected_work_state_sha256": "c" * 64},
    }, "delegate.validator.reconciliation")
    verifier = _history_verifier_module()
    with sqlite3.connect(database) as db:
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = database.read_bytes()
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        roster = verifier.validate_event_journal(db)
        types = {json.loads(row[0])["event_type"] for row in db.execute(
            "SELECT event_json FROM claim_loop_events WHERE loop_id=?", ("delegate." + CLAIM,))}
    assert types == {"AGENT_MANDATE_PAUSED", "AGENT_MANDATE_RESUMED", "AGENT_HANDLER_DECISION_RECORDED", "AGENT_RECOVERY_REQUESTED"}
    assert len(roster) == validate_journal(database)["event_count"] == 8
    assert database.read_bytes() == before and workspace.store.recover(CLAIM) == state


@pytest.mark.parametrize("fault", ["contract", "event_type", "command", "session", "prefix", "empty_claim"])
def test_boot_history_validator_rejects_delegate_unknown_type_tamper_and_foreign_namespace(
    delegated_workspace, fault,
):
    database, _ = delegated_workspace
    verifier = _history_verifier_module()
    with sqlite3.connect(database) as db:
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='claim_loop_events'").fetchall():
            db.execute('DROP TRIGGER "' + row[0] + '"')
        rows = db.execute("SELECT sequence,event_json FROM claim_loop_events WHERE loop_id=? ORDER BY sequence",
            ("delegate." + CLAIM,)).fetchall()
        previous = None
        for sequence, raw in rows:
            event = json.loads(raw)
            event["previous_event_sha256"] = previous
            if fault == "session":
                event["session_id"] = "foreign-session"
            elif fault == "prefix":
                event["loop_id"] = "foreign." + CLAIM
            elif fault == "empty_claim":
                event["loop_id"] = "delegate."
            elif sequence == 1:
                if fault == "contract":
                    event["contract"] = EVENT_CONTRACT.replace("1.0.0", "9.0.0")
                elif fault == "event_type":
                    event["event_type"] = "WORKSPACE_CLAIM_READY"
                else:
                    event["command"]["reason"] = "Caller-altered reason without the recorded command hash."
            # Rehash the full chain and match its raw columns. This isolates the
            # contract/namespace checks; command tampering retains its old hash.
            event["event_sha256"] = digest_value({k: v for k, v in event.items()
                if k not in {"event_sha256", "resulting_state_sha256"}})
            db.execute("UPDATE claim_loop_events SET session_id=?,loop_id=?,event_sha256=?,event_json=? WHERE loop_id=? AND sequence=?",
                (event["session_id"], event["loop_id"], event["event_sha256"], verifier.canonical(event).decode(),
                 "delegate." + CLAIM, sequence))
            previous = event["event_sha256"]
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        with pytest.raises(verifier.HistoryError, match="event chain is invalid"):
            verifier.validate_event_journal(db)


@pytest.mark.parametrize("fault", ["chain", "unsupported_event", "extra_authority", "parent", "draft_scope"])
def test_global_validator_rejects_invalid_delegate_chain_schema_parent_and_scope(delegated_workspace, fault):
    database, _ = delegated_workspace
    with sqlite3.connect(database) as db:
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='claim_loop_events'").fetchall():
            db.execute('DROP TRIGGER "' + row[0] + '"')
        sequence = 3 if fault == "draft_scope" else 1
        event = json.loads(db.execute("SELECT event_json FROM claim_loop_events WHERE loop_id=? AND sequence=?",
            ("delegate." + CLAIM, sequence)).fetchone()[0])
        if fault == "chain":
            event["previous_event_sha256"] = "f" * 64
        elif fault == "unsupported_event":
            event["event_type"] = "WORKSPACE_CLAIM_READY"
        elif fault == "extra_authority":
            event["command"]["claim_ready"] = True
        elif fault == "parent":
            event["command"]["expected_state_sha256"] = "f" * 64
        else:
            event["command"]["decision"]["draft_event_sha256"] = "f" * 64
        # Rehash caller-altered material: an authentic-looking hash cannot
        # authorize a foreign command or substitute its validated claim parent.
        event["command_sha256"] = digest_value(event["command"])
        event["event_sha256"] = digest_value({k: v for k, v in event.items()
            if k not in {"event_sha256", "resulting_state_sha256"}})
        db.execute("UPDATE claim_loop_events SET event_json=?,command_sha256=?,event_sha256=? WHERE loop_id=? AND sequence=?",
            (json.dumps(event), event["command_sha256"], event["event_sha256"], "delegate." + CLAIM, sequence))
    with pytest.raises(JournalValidationError, match="replay failed"):
        validate_journal(database)


@pytest.mark.parametrize("session,loop", [
    ("foreign-session", "delegate." + CLAIM),
    (WORKSPACE_SESSION_ID, "foreign." + CLAIM),
    (WORKSPACE_SESSION_ID, "delegate.clm_absent"),
])
def test_global_validator_keeps_delegate_namespace_bound_to_its_imported_claim(delegated_workspace, session, loop):
    database, _ = delegated_workspace
    with sqlite3.connect(database) as db:
        for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='claim_loop_events'").fetchall():
            db.execute('DROP TRIGGER "' + row[0] + '"')
        db.execute("UPDATE claim_loop_events SET session_id=?,loop_id=? WHERE loop_id=?",
            (session, loop, "delegate." + CLAIM))
    with pytest.raises(JournalValidationError):
        validate_journal(database)
