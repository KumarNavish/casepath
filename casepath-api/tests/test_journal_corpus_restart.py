"""Startup replay must use the immutable corpus identity recorded at import."""
from pathlib import Path
import json
import sqlite3

import pytest

from casepath_api.claim_workspace_v1 import ClaimWorkspaceService, ClaimWorkspaceStore
from casepath_api.foundation.common import digest_value
from casepath_api.storage import Storage
from casepath_api.validate_journal import JournalValidationError, validate_journal
from casepath_api.workspace_corpus import PublicCorpus, default_public_corpus_root


@pytest.mark.parametrize("corpus_id,count", [("synthetic-dev-60", 60), ("synthetic-150", 150)])
def test_startup_replays_each_bundled_corpus_without_changing_journal(
    tmp_path: Path, corpus_id: str, count: int,
) -> None:
    database = tmp_path / "casepath.db"
    corpus = PublicCorpus(default_public_corpus_root(corpus_id))
    service = ClaimWorkspaceService(Storage(str(database)), corpus)
    service.seed(timestamp="2026-09-19T00:00:00+00:00")
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    before = database.read_bytes()

    receipt = validate_journal(database)

    assert receipt["loop_count"] == count
    assert receipt["event_count"] == count
    assert database.read_bytes() == before


@pytest.mark.parametrize("replacement", ["other_bundle", "../synthetic-dev-60", None, {}])
def test_import_profile_selection_does_not_admit_a_changed_binding(
    tmp_path: Path, replacement: object,
) -> None:
    database = tmp_path / "casepath.db"
    corpus = PublicCorpus(default_public_corpus_root("synthetic-dev-60"))
    service = ClaimWorkspaceService(Storage(str(database)), corpus)
    claim_id = next(iter(corpus.bindings))
    binding = corpus.binding(claim_id)
    service.store.append(
        claim_id=claim_id,
        event_type="WORKSPACE_CLAIM_IMPORTED",
        idempotency_key="seed." + binding["binding_sha256"],
        command={"binding": binding, "corpus_identity": corpus.identity,
                 "request_expected_revision": 0},
        timestamp="2026-09-19T00:00:00+00:00",
        expected_revision=0,
    )
    with sqlite3.connect(database) as connection:
        raw = connection.execute("SELECT event_json FROM claim_loop_events").fetchone()[0]
        event = json.loads(raw)
        selected = (
            PublicCorpus(default_public_corpus_root("synthetic-150")).identity["manifest_sha256"]
            if replacement == "other_bundle" else replacement
        )
        event["command"]["corpus_identity"]["manifest_sha256"] = selected
        event["command_sha256"] = digest_value(event["command"])
        event["event_sha256"] = digest_value(ClaimWorkspaceStore._event_material(event))
        connection.execute(
            "UPDATE claim_loop_events SET event_json=?, command_sha256=?, event_sha256=?",
            (json.dumps(event), event["command_sha256"], event["event_sha256"]),
        )

    with pytest.raises(JournalValidationError, match="replay failed") as caught:
        validate_journal(database)
    expected = "binding is invalid" if replacement == "other_bundle" else "identity is unsupported"
    assert expected in str(caught.value.__cause__)
