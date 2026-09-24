from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from casepath_api.claim_workspace_v1 import ClaimWorkspaceError, ClaimWorkspaceService
from casepath_api.storage import Storage
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root


NOW = "2026-09-24T08:00:00+00:00"


def test_triage_queue_distinguishes_claims_and_filters_matching_profiles(tmp_path: Path) -> None:
    workspace = ClaimWorkspaceService(
        Storage(str(tmp_path / "casepath.db")),
        corpus=PublicCorpus(default_workspace_corpus_root()),
    )
    workspace.seed(timestamp=NOW)
    first = workspace.queue(now=NOW, limit=100)
    second = workspace.queue(cursor=first["next_cursor"], limit=100)
    rows = first["items"] + second["items"]
    assert len(rows) == 150
    noticed = Counter(row["triage"]["noticed_fact"] for row in rows)
    assert len(noticed) >= 120
    assert max(noticed.values()) <= 5
    assert sum(first["facets"]["waiting_on"].values()) == 150
    assert sum(item["count"] for item in first["facets"]["condition_profiles"]) == 150
    assert all(row["triage"]["waiting_on"] == "Handler" for row in rows)
    assert all(not row["triage"]["draft_ready"] for row in rows)

    for claim_id in (
        "clm_f69b1747447bc221",
        "clm_7ac806bd30792cfb",
        "clm_6f04d0907ecb96bb",
    ):
        state = workspace.store.recover(claim_id)
        workspace.start(
            claim_id, expected_revision=state["revision"],
            idempotency_key=f"triage.start.{claim_id}", timestamp=NOW,
        )
    reviewed = workspace.queue(now=NOW, limit=100)
    all_rows = reviewed["items"] + workspace.queue(cursor=reviewed["next_cursor"], limit=100)["items"]
    by_id = {row["claim_id"]: row for row in all_rows}
    flagship = by_id["clm_f69b1747447bc221"]["triage"]
    mould = by_id["clm_7ac806bd30792cfb"]["triage"]
    rent = by_id["clm_6f04d0907ecb96bb"]["triage"]
    assert flagship["noticed_source"] == "assessment"
    assert len({flagship["condition_profile"], mould["condition_profile"], rent["condition_profile"]}) == 3
    assert mould["waiting_on"] == "Specialist"
    assert flagship["waiting_on"] == rent["waiting_on"] == "Customer"
    assert by_id["clm_7ac806bd30792cfb"]["language"].startswith("de")
    profile_rows = workspace.queue(now=NOW, profile=flagship["condition_profile"])
    assert profile_rows["items"]
    assert all(row["triage"]["condition_profile"] == flagship["condition_profile"] for row in profile_rows["items"])
    with pytest.raises(ClaimWorkspaceError, match="condition-profile"):
        workspace.queue(now=NOW, profile="invalid")
    with pytest.raises(ClaimWorkspaceError, match="stale"):
        workspace.queue(cursor=first["next_cursor"], limit=100)
