"""Verified-prefix reuse must retain the cold reducer's authority checks."""
import pytest

from casepath_api.claim_workspace_v1 import ClaimWorkspaceError, ClaimWorkspaceService
from casepath_api.causal_workspace_v1 import CausalWorkspaceService
from casepath_api.storage import Storage
from casepath_api.workspace_corpus import PublicCorpus, WorkspaceCorpusError, default_workspace_corpus_root

CLAIM = "clm_f69b1747447bc221"


@pytest.fixture
def workspace(tmp_path):
    corpus = PublicCorpus(default_workspace_corpus_root())
    corpus.start_inventory_watch()
    value = ClaimWorkspaceService(Storage(str(tmp_path / "workspace.sqlite3")), corpus)
    value.seed()
    parent = value.store.recover(CLAIM)
    value.start(CLAIM, expected_revision=parent["revision"], idempotency_key="prefix.cache.setup", process_model="casepath.causal-process/1.0.0")
    process = CausalWorkspaceService(value)
    for flag in ("family_home", "arrears"):
        parent = value.store.recover(CLAIM)
        body = {"operation": {"type": "conditions.set", "flag": flag, "verdict": "false"}, "actor": "Test handler",
            "reason": "Review the admitted evidence.", "expected_revision": parent["revision"], "expected_state_sha256": parent["state_sha256"]}
        preview = process.preview(CLAIM, **body)
        process.apply(CLAIM, **body, preview_sha256=preview["preview_sha256"], idempotency_key="prefix.cache.edit." + flag)
    yield value
    corpus.stop_inventory_watch()


def count_reductions(monkeypatch):
    import casepath_api.claim_workspace_v1 as module
    original = module._reduce
    calls = []
    def count(*args, **kwargs):
        calls.append(kwargs["sequence"])
        return original(*args, **kwargs)
    monkeypatch.setattr(module, "_reduce", count)
    return calls


def test_same_prefix_reuses_validation_and_returns_independent_states(workspace, monkeypatch):
    calls = count_reductions(monkeypatch)
    original = workspace.store.recover(CLAIM)
    parent = workspace.store.state_at_revision(CLAIM, original["revision"] - 1)
    count = len(calls)
    changed = workspace.store.recover(CLAIM)
    changed["owner"] = "Caller mutation"
    changed["causal_process"]["nodes"][0]["label"] = "Caller graph mutation"
    assert workspace.store.recover(CLAIM) == original
    assert workspace.store.state_at_revision(CLAIM, parent["revision"]) == parent
    assert len(calls) == count


@pytest.mark.parametrize("column,value,invalid", [
    ("created_at", "raw metadata changed", False),
    ("event_sha256", "0" * 64, True),
    ("command_sha256", "0" * 64, True),
    ("event_json", "{}", True),
])
def test_cache_rechecks_every_persisted_row_column(workspace, monkeypatch, column, value, invalid):
    saved = workspace.store.recover(CLAIM)
    calls = count_reductions(monkeypatch)
    with workspace.store.journal.connect() as db:
        # Fault injection is confined to this test's disposable public fixture.
        for trigger in db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='claim_loop_events'").fetchall():
            db.execute('DROP TRIGGER "' + trigger[0] + '"')
        db.execute(f"UPDATE claim_loop_events SET {column}=? WHERE loop_id=? AND sequence=1", (value, "workspace." + CLAIM))
    if invalid:
        with pytest.raises(ClaimWorkspaceError):
            workspace.store.recover(CLAIM)
    else:
        assert workspace.store.recover(CLAIM) == saved
        assert calls  # Metadata outside the JSON also invalidates reuse.


def test_append_changes_current_state_while_historical_prefix_stays_bound(workspace, monkeypatch):
    saved = workspace.store.recover(CLAIM)
    calls = count_reductions(monkeypatch)
    result = workspace.assign(CLAIM, owner="Accountable handler", expected_revision=saved["revision"], idempotency_key="prefix.cache.owner")
    current = workspace.store.recover(CLAIM)
    assert current["owner"] == "Accountable handler" and current["revision"] == saved["revision"] + 1
    assert current["state_sha256"] == result["state"]["state_sha256"] != saved["state_sha256"]
    count = len(calls)
    assert workspace.store.state_at_revision(CLAIM, saved["revision"]) == saved
    assert len(calls) == count


def test_deleted_historical_row_cannot_reuse_verified_prefix(workspace):
    workspace.store.recover(CLAIM)
    with workspace.store.journal.connect() as db:
        for trigger in db.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='claim_loop_events'").fetchall():
            db.execute('DROP TRIGGER "' + trigger[0] + '"')
        db.execute("DELETE FROM claim_loop_events WHERE loop_id=? AND sequence=2", ("workspace." + CLAIM,))
    with pytest.raises(ClaimWorkspaceError):
        workspace.store.recover(CLAIM)


def test_corpus_drift_is_checked_before_reusing_a_prefix(workspace, monkeypatch):
    workspace.store.recover(CLAIM)
    def drift():
        raise WorkspaceCorpusError("observed corpus inventory drift")
    monkeypatch.setattr(workspace.corpus, "observed_runtime_identity_token", drift)
    with pytest.raises(ClaimWorkspaceError, match="binding is invalid"):
        workspace.store.recover(CLAIM)


def test_corpus_drift_during_a_cache_hit_is_rechecked(workspace, monkeypatch):
    workspace.store.recover(CLAIM)
    token = workspace.corpus.observed_runtime_identity_token()
    reads = 0
    def drift_after_lookup():
        nonlocal reads
        reads += 1
        if reads > 1:
            raise WorkspaceCorpusError("corpus drift during cache lookup")
        return token
    monkeypatch.setattr(workspace.corpus, "observed_runtime_identity_token", drift_after_lookup)
    with pytest.raises(ClaimWorkspaceError, match="binding is invalid"):
        workspace.store.recover(CLAIM)


def test_cached_parent_cannot_hide_changed_authority_context(workspace):
    from casepath_api.agent_work.authority import ExistingCasePathAuthority, SourceChanged
    class AbsentLoop:
        def view(self, claim_id):
            raise ValueError("claim loop does not exist")
    authority = ExistingCasePathAuthority(lambda: workspace, lambda: AbsentLoop())
    before = authority.context(CLAIM)
    workspace.store.recover(CLAIM)
    workspace.assign(CLAIM, owner="New accountable handler", expected_revision=before["revision"], idempotency_key="prefix.cache.authority.owner")
    current = authority.context(CLAIM)
    assert current["revision"] == before["revision"] + 1
    assert current["state_sha256"] != before["state_sha256"]
    assert current["binding_sha256"] == before["binding_sha256"]
    with pytest.raises(SourceChanged, match="changed before setup"):
        authority.prepare(CLAIM, "isolated-stale-context", before)
