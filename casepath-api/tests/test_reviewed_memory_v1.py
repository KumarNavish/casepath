from __future__ import annotations

from pathlib import Path

import pytest

from casepath_api.claim_workspace_v1 import ClaimWorkspaceError, ClaimWorkspaceService
from casepath_api.storage import Storage
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root


def _start(workspace: ClaimWorkspaceService, claim_id: str, suffix: str) -> dict:
    state = workspace.store.recover(claim_id)
    return workspace.start(
        claim_id, expected_revision=state["revision"],
        idempotency_key=f"workspace.memory.start.{suffix}",
        timestamp="2026-09-24T08:00:01+00:00",
    )["state"]


def test_reviewed_memory_matches_only_same_family_statement_and_apply_is_journaled(tmp_path: Path) -> None:
    corpus = PublicCorpus(default_workspace_corpus_root())
    path = tmp_path / "casepath.db"
    workspace = ClaimWorkspaceService(Storage(str(path)), corpus=corpus)
    workspace.seed(timestamp="2026-09-24T08:00:00+00:00")
    source_id = "clm_f69b1747447bc221"
    source = _start(workspace, source_id, "source")
    reviewed, event, _ = workspace.store.append(
        claim_id=source_id, event_type="WORKSPACE_HANDLER_OBSERVATION_RECORDED",
        idempotency_key="workspace.memory.handler.0001",
        command={"kind": "condition", "target": "family_home", "verdict": "true",
                 "note": "Separate service is supported by the quoted message.",
                 "quote": None, "source_id": None, "action_id": None,
                 "request_expected_revision": source["revision"]},
        timestamp="2026-09-24T08:00:02+00:00", expected_revision=source["revision"],
    )
    args = dict(
        source_handler_event_sha256=event["event_sha256"], handler="Navish",
        expected_revision=reviewed["revision"], expected_state_sha256=reviewed["state_sha256"],
        idempotency_key="workspace.memory.keep.0001",
    )
    kept = workspace.keep_reviewed_memory(source_id, **args, timestamp="2026-09-24T08:00:03+00:00")
    assert workspace.keep_reviewed_memory(source_id, **args, timestamp="2026-09-24T08:00:04+00:00") == kept
    next_id = "clm_478488eeea2665d7"
    next_state = _start(workspace, next_id, "next")
    matches = workspace.reviewed_memories(next_id)["items"]
    assert len(matches) == 1
    assert matches[0]["handler"] == "Navish"
    assert matches[0]["support_count"] == 1
    assert matches[0]["qualified_review_required"] is True
    assert workspace.reviewed_memories(source_id)["items"] == []
    assert workspace._triage_snapshot([next_state])[next_id]["uses_reviewed_memory"] is True
    other_id = "clm_6f04d0907ecb96bb"
    _start(workspace, other_id, "other")
    assert workspace.reviewed_memories(other_id)["items"] == []
    before = workspace.store.handler_observations_at_revision(next_id, next_state["revision"])
    assert before == []
    applied = workspace.apply_reviewed_memory(
        next_id, memory_sha256=matches[0]["memory_sha256"],
        note="I checked the spouse notice and agree.", expected_revision=next_state["revision"],
        expected_state_sha256=next_state["state_sha256"],
        idempotency_key="workspace.memory.apply.0001",
        timestamp="2026-09-24T08:00:05+00:00",
    )
    observations = workspace.store.handler_observations_at_revision(next_id, applied["state"]["revision"])
    assert observations[-1]["memory_sha256"] == matches[0]["memory_sha256"]
    assert observations[-1]["verdict"] == "true"
    source_now = workspace.store.recover(source_id)
    retired = workspace.retire_reviewed_memory(
        source_id, memory_sha256=matches[0]["memory_sha256"],
        reason="This example should no longer guide later claims.",
        expected_revision=source_now["revision"], expected_state_sha256=source_now["state_sha256"],
        idempotency_key="workspace.memory.retire.0001",
        timestamp="2026-09-24T08:00:06+00:00",
    )
    assert retired["event_type"] == "WORKSPACE_REVIEWED_MEMORY_RETIRED"
    assert workspace.reviewed_memories(next_id)["items"] == []
    assert workspace._triage_snapshot([workspace.store.recover(next_id)])[next_id]["uses_reviewed_memory"] is False
    assert workspace.reviewed_memories(family="lease_termination_dispute")["items"][0]["status"] == "retired"
    restarted = ClaimWorkspaceService(Storage(str(path)), corpus=corpus)
    assert restarted.reviewed_memories(next_id) == workspace.reviewed_memories(next_id)
    assert restarted.store.handler_observations_at_revision(next_id, applied["state"]["revision"]) == observations
    with pytest.raises(ClaimWorkspaceError, match="does not match"):
        restarted.apply_reviewed_memory(
            other_id, memory_sha256=matches[0]["memory_sha256"], note="Not my family.",
            expected_revision=restarted.store.recover(other_id)["revision"],
            expected_state_sha256=restarted.store.recover(other_id)["state_sha256"],
            idempotency_key="workspace.memory.apply.bad.0001",
        )
