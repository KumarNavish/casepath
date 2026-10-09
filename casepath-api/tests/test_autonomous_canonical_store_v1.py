"""Canonical admission and recorded replay use only the existing accepted journal."""
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from hashlib import sha256
import json
from threading import Event

import pytest

from casepath_api.autonomous_controller_v1 import AutonomousController
from casepath_api.autonomous_store_v1 import (
    AutonomousStore, AutonomousStoreError, SOURCE_CONTRACT, SESSION_ID,
)
from casepath_api.workspace_corpus import digest_value


CLAIM = "clm_canonical_fixture_01"


def sealed(value, key):
    return {**value, key: digest_value(value)}


def original_packet(claim_id=CLAIM):
    message = "Please inspect the original notice."
    native = (b"From: tenant@example.test\r\nTo: landlord@example.test\r\n"
              b"Subject: Original notice\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
              + message.encode() + b"\r\n")
    raws = [native, b"An original supporting statement.\r\n"]
    sources = []
    for name, media, role, raw in zip(
        ["original-intake.eml", "statement.txt"],
        ["message/rfc822", "text/plain; charset=utf-8"],
        ["customer_message", "supporting_document"], raws,
    ):
        identity = {"claim_id": claim_id, "file_name": name, "media_type": media,
                    "role": role, "sha256": sha256(raw).hexdigest()}
        sources.append(sealed({"contract": SOURCE_CONTRACT, **identity, "size_bytes": len(raw),
                               "artifact_id": "src_" + digest_value(identity)[:32]}, "descriptor_sha256"))
    binding = sealed({"contract": "casepath.autonomous-original-binding/1.0.0", "claim_id": claim_id,
                      "corpus_id": "synthetic-150", "claim_binding_sha256": "a" * 64,
                      "intake": {"submission": {"claim_id": claim_id, "channel": "email"},
                                 "customer_message": {"body": message,
                                 "from": "tenant@example.test", "to": "landlord@example.test",
                                 "raw_file": {**{k: sources[0][k] for k in
                                     ("file_name", "media_type", "sha256", "size_bytes")},
                                     "artifact_id": "com_canonical_fixture_01"}},
                                 "attachments": [{**{k: sources[1][k] for k in
                                     ("file_name", "media_type", "sha256", "size_bytes")},
                                     "artifact_id": "doc_canonical_fixture_01"}]},
                      "source_map": [{"original_artifact_id": original, "artifact_id": source["artifact_id"],
                                      "sha256": source["sha256"]} for original, source in
                                     zip(["com_canonical_fixture_01", "doc_canonical_fixture_01"], sources)]},
                     "original_binding_sha256")
    return {"title": "Original canonical claim", "message": message, "sources": sources,
            "original_binding": binding, "source_bytes": {s["artifact_id"]: raw for s, raw in zip(sources, raws)},
            "initial_state_sha256": digest_value({"claim_id": claim_id, "original_binding": binding})}


def admit(store, packet=None, key="canonical.start.01", **overrides):
    packet = packet or original_packet()
    options = {"expected_revision": 0, "expected_state_sha256": packet["initial_state_sha256"],
               "idempotency_key": key, **overrides}
    return store.admit_original(packet["original_binding"]["claim_id"], packet, **options)


def append(store, state, kind, payload, key):
    return store.append(state["claim_id"], kind, payload, expected_revision=state["revision"],
                        expected_state_sha256=state["state_sha256"], idempotency_key=key)


def test_native_admission_preserves_identity_metadata_and_zero_acquisition(tmp_path, monkeypatch):
    store, packet = AutonomousStore(tmp_path / "claims.db"), original_packet()
    monkeypatch.setattr(store, "_extract", lambda *a: pytest.fail("admission extracted original evidence"))
    result = admit(store, packet)
    state = result["state"]
    assert result["replayed"] is False
    assert state["claim_id"] == CLAIM and state["revision"] == 1
    assert state["source_descriptors"] == packet["sources"]
    assert state["original_binding"] == packet["original_binding"]
    assert state["message"] == packet["message"]
    assert state["graph"] is None and state["acquired_sources"] == []
    assert not any(s["file_name"] == "customer-message.txt" for s in state["source_descriptors"])
    for source in packet["sources"]:
        assert store.artifact(CLAIM, source["artifact_id"])[0] == packet["source_bytes"][source["artifact_id"]]
    event = store.events(CLAIM)[0]
    assert event["kind"] == "intake" and event["expected_revision"] == 0
    assert event["expected_state_sha256"] is None
    assert event["payload"]["initial_state_sha256"] == packet["initial_state_sha256"]
    assert "source_bytes" not in event["payload"]
    with store.journal.connect() as connection:
        assert connection.execute("SELECT loop_id FROM claim_loop_events").fetchone()[0] == "autonomous." + CLAIM


@pytest.mark.parametrize("fault", ["stale_revision", "stale_hash", "bad_bytes", "bad_descriptor", "bad_binding", "bad_map",
                                   "bad_original_metadata", "bad_original_claim", "bad_attachments"])
def test_invalid_original_admission_fails_before_source_publication(tmp_path, fault):
    store, packet = AutonomousStore(tmp_path / "claims.db"), original_packet()
    options = {}
    if fault == "stale_revision":
        options["expected_revision"] = 1
    elif fault == "stale_hash":
        options["expected_state_sha256"] = "0" * 64
    elif fault == "bad_bytes":
        packet["source_bytes"][packet["sources"][0]["artifact_id"]] = b"Changed email"
    elif fault == "bad_descriptor":
        packet["sources"][0]["claim_id"] = "clm_other"
    elif fault == "bad_binding":
        packet["original_binding"]["intake"]["submission"]["channel"] = "invented"
    else:
        binding = packet["original_binding"]
        if fault == "bad_map":
            binding["source_map"][0]["artifact_id"] = packet["sources"][1]["artifact_id"]
        elif fault == "bad_original_metadata":
            binding["intake"]["customer_message"]["raw_file"]["media_type"] = "text/plain"
        elif fault == "bad_original_claim":
            binding["intake"]["submission"]["claim_id"] = "clm_other"
        else:
            binding["intake"]["attachments"] = []
        packet["original_binding"] = sealed({k: v for k, v in binding.items() if k != "original_binding_sha256"},
                                             "original_binding_sha256")
    with pytest.raises(AutonomousStoreError):
        admit(store, packet, **options)
    assert list(store.source_root.iterdir()) == []
    assert store.list() == []


def test_exact_original_retry_returns_persisted_admission_after_work_and_restart(tmp_path, monkeypatch):
    store, packet = AutonomousStore(tmp_path / "claims.db"), original_packet()
    first = admit(store, packet)["state"]
    current = append(store, first, "work.started", {"run_id": "run.canonical", "policy_id": "local/1"}, "canonical.work")
    restarted = AutonomousStore(store.path)
    monkeypatch.setattr(restarted, "_publish", lambda *a: pytest.fail("exact retry published evidence"))
    assert admit(restarted, packet) == {"state": first, "replayed": True}
    assert restarted.get(CLAIM) == current
    with pytest.raises(AutonomousStoreError, match="idempotency"):
        admit(restarted, {**packet, "title": "Changed original title"})
    with pytest.raises(AutonomousStoreError, match="stale|already"):
        admit(restarted, packet, "canonical.other.key")


@pytest.mark.parametrize("keys", [["same.start", "same.start"], ["one.start", "two.start"]])
def test_concurrent_canonical_admission_has_one_new_result(tmp_path, keys):
    store = AutonomousStore(tmp_path / "claims.db")
    def attempt(key):
        try:
            return admit(store, key=key)
        except AutonomousStoreError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, keys))
    accepted = [r for r in results if r is not None]
    assert sum(not result["replayed"] for result in accepted) == 1
    assert len(accepted) == (2 if keys[0] == keys[1] else 1)
    assert len(store.events(CLAIM)) == 1


@pytest.mark.parametrize("hosted", [False, True])
def test_failed_admission_transaction_never_returns_an_accepted_result(tmp_path, monkeypatch, hosted):
    from test_hosted_storage_v1 import autonomous, SERVERS
    path = tmp_path / "claims.db"
    try:
        store = autonomous(path) if hosted else AutonomousStore(path)
        insert = store._insert_prepared
        def failed_commit(connection, parameters):
            insert(connection, parameters)
            raise AutonomousStoreError("unconfirmed fixture transaction")
        monkeypatch.setattr(store, "_insert_prepared", failed_commit)
        with pytest.raises(AutonomousStoreError, match="unconfirmed"):
            admit(store)
        assert store.list_summaries() == []
        with pytest.raises(AutonomousStoreError, match="does not exist"):
            store.get(CLAIM)
        monkeypatch.setattr(store, "_insert_prepared", insert)
        accepted = admit(store)
        assert accepted["replayed"] is False and accepted["state"]["revision"] == 1
        assert len(store.events(CLAIM)) == 1
    finally:
        server = SERVERS.pop(path, None)
        if server:
            server.close()


def test_only_explicit_controller_acquisition_admits_native_sources(tmp_path):
    store, packet = AutonomousStore(tmp_path / "claims.db"), original_packet()
    original = admit(store, packet)["state"]
    source = store.acquire(CLAIM, original["source_descriptors"][1]["artifact_id"])
    assert source["media_type"] == "text/plain; charset=utf-8"
    assert source["text"] == "An original supporting statement.\r\n"
    assert store.get(CLAIM) == original
    controller = AutonomousController(store, {"templates": []}, None)
    try:
        controller.run(CLAIM)
    finally:
        controller.shutdown()
    current = store.get(CLAIM)
    assert {s["artifact_id"] for s in current["acquired_sources"]} == {s["artifact_id"] for s in packet["sources"]}
    assert len([e for e in store.events(CLAIM) if e["kind"] == "sources.acquired"]) == 2


def test_collection_cache_reuses_reducer_and_validates_entire_journal_and_sources(tmp_path, monkeypatch):
    store = AutonomousStore(tmp_path / "claims.db")
    first = admit(store)["state"]
    current = append(store, first, "work.started", {"run_id": "run.canonical", "policy_id": "local/1"}, "canonical.work")
    calls, reducer = [], store._reduce
    def counted(*args):
        calls.append(1)
        return reducer(*args)
    monkeypatch.setattr(store, "_reduce", counted)
    rows = store.list_summaries()
    assert rows[0]["revision"] == current["revision"] and rows[0]["claim_id"] == CLAIM
    assert "semantic_contexts" not in rows[0] and "events" not in rows[0]
    count = len(calls)
    assert count == 2 and store.list_summaries() == rows and len(calls) == count
    with store.journal.connect() as connection:
        connection.execute("UPDATE claim_loop_events SET created_at='tampered' WHERE session_id=? AND sequence=1", (SESSION_ID,))
    with pytest.raises(AutonomousStoreError, match="journal|identity|hash"):
        store.list_summaries()


def test_cached_collection_rejects_source_tampering(tmp_path):
    store = AutonomousStore(tmp_path / "claims.db")
    state = admit(store)["state"]
    store.list_summaries()
    (store.source_root / state["source_descriptors"][0]["sha256"]).write_bytes(b"changed original")
    with pytest.raises(AutonomousStoreError, match="source|hash|bytes"):
        store.list_summaries()


@pytest.mark.parametrize("delete_all", [False, True])
def test_cached_collection_rejects_deleted_accepted_tail_or_stream(tmp_path, delete_all):
    store = AutonomousStore(tmp_path / "claims.db")
    first = admit(store)["state"]
    append(store, first, "work.started", {"run_id": "run.canonical", "policy_id": "local/1"}, "canonical.work")
    store.list_summaries()
    with store.journal.connect() as connection:
        connection.execute("DELETE FROM claim_loop_events WHERE session_id=? AND sequence>=?",
                           (SESSION_ID, 1 if delete_all else 2))
    with pytest.raises(AutonomousStoreError, match="journal|regress|disappear"):
        store.list_summaries()


def test_concurrent_collection_snapshots_do_not_misreport_new_stream_as_deleted(tmp_path, monkeypatch):
    store = AutonomousStore(tmp_path / "claims.db")
    fetched, release, seen = Event(), Event(), []
    connect = store.journal.connect
    class Cursor:
        def __init__(self, raw):
            self.raw = raw
        def fetchall(self):
            rows = self.raw.fetchall()
            if not seen:
                seen.append(True)
                fetched.set()
                assert release.wait(5)
            return rows
    class Connection:
        def __init__(self):
            self.raw = connect()
        def __enter__(self):
            self.raw.__enter__()
            return self
        def __exit__(self, *args):
            return self.raw.__exit__(*args)
        def execute(self, sql, args=()):
            cursor = self.raw.execute(sql, args)
            return Cursor(cursor) if "ORDER BY loop_id,sequence" in sql else cursor
    monkeypatch.setattr(store.journal, "connect", Connection)
    with ThreadPoolExecutor(max_workers=2) as pool:
        older = pool.submit(store.list_summaries)
        assert fetched.wait(5)
        try:
            admit(store)
            newer = pool.submit(store.list_summaries)
            try:
                newer.result(timeout=0.25)
            except FutureTimeout:
                pass
        finally:
            release.set()
        assert older.result(timeout=5) == []
        assert newer.result(timeout=5)[0]["claim_id"] == CLAIM


def test_prefix_replay_preserves_recorded_state_validates_suffix_and_never_writes(tmp_path):
    store = AutonomousStore(tmp_path / "claims.db")
    first = admit(store)["state"]
    head = append(store, first, "work.started", {"run_id": "run.canonical", "policy_id": "local/1"}, "canonical.work")
    before = store.events(CLAIM)
    replay = store.replay(CLAIM, through_seq=1)
    assert replay["state"] == first and replay["replay_only"] is True
    assert replay["current_revision"] == 2 and replay["current_state_sha256"] == head["state_sha256"]
    assert replay["current_event_sha256"] == head["last_event_sha256"]
    assert replay["events"] == before[:1]
    assert replay["provenance"]["source_roster_sha256"] == first["source_roster_sha256"]
    assert store.events(CLAIM) == before and store.get(CLAIM) == head
    for cursor in [0, 3, True, -1]:
        with pytest.raises(AutonomousStoreError, match="cursor|revision|sequence"):
            store.replay(CLAIM, through_seq=cursor)
    with store.journal.connect() as connection:
        event = json.loads(connection.execute("SELECT event_json FROM claim_loop_events WHERE sequence=2").fetchone()[0])
        event["payload"]["run_id"] = "tampered.suffix"
        connection.execute("UPDATE claim_loop_events SET event_json=? WHERE sequence=2", (json.dumps(event),))
    with pytest.raises(AutonomousStoreError, match="journal|hash|identity"):
        store.replay(CLAIM, through_seq=1)


def test_snapshot_state_events_and_head_share_one_verified_read(tmp_path, monkeypatch):
    store = AutonomousStore(tmp_path / "claims.db")
    first = admit(store)["state"]
    rows, read = [], store._rows
    def counted(*args):
        rows.append(1)
        return read(*args)
    monkeypatch.setattr(store, "_rows", counted)
    snapshot = store.snapshot(CLAIM, after=0)
    assert len(rows) == 1
    assert snapshot["state"] == first and snapshot["current_revision"] == 1
    assert snapshot["current_state_sha256"] == first["state_sha256"]
    assert snapshot["events"][-1]["resulting_state_sha256"] == snapshot["current_state_sha256"]
    assert snapshot["events"][-1]["event_sha256"] == snapshot["current_event_sha256"]
    assert store.snapshot(CLAIM, after=1)["events"] == []


def test_hosted_canonical_admission_retry_summaries_and_prefix_use_remote_journal(tmp_path):
    from test_hosted_storage_v1 import autonomous, SERVERS
    path = tmp_path / "remote-surrogate.db"
    try:
        store = autonomous(path)
        first = admit(store)["state"]
        head = append(store, first, "work.started", {"run_id": "run.hosted", "policy_id": "local/1"}, "canonical.hosted.work")
        restarted = autonomous(path)
        assert admit(restarted) == {"state": first, "replayed": True}
        assert restarted.list_summaries()[0]["state_sha256"] == head["state_sha256"]
        assert restarted.replay(CLAIM, through_seq=1)["state"] == first
        assert not restarted.path.exists()
    finally:
        server = SERVERS.pop(path, None)
        if server:
            server.close()


@pytest.mark.parametrize("view", ["summary", "snapshot", "prefix", "head"])
@pytest.mark.parametrize("fault", ["extra_chunk", "changed_chunk"])
def test_warm_hosted_projection_revalidates_persisted_source_bytes(tmp_path, view, fault):
    from test_hosted_storage_v1 import autonomous, SERVERS, connection_factory
    path = tmp_path / "remote-surrogate.db"
    try:
        store = autonomous(path)
        first = admit(store)["state"]
        store.list_summaries()
        digest = first["source_descriptors"][0]["sha256"]
        with connection_factory(path)() as connection:
            if fault == "extra_chunk":
                connection.execute("INSERT INTO autonomous_source_chunks VALUES (?,?,?)", (digest, 1, b"extra tamper chunk"))
            else:
                connection.execute("DROP TRIGGER autonomous_source_chunks_no_update")
                raw = original_packet()["source_bytes"][first["source_descriptors"][0]["artifact_id"]]
                connection.execute("UPDATE autonomous_source_chunks SET content=? WHERE sha256=? AND chunk_index=0",
                                   (b"X" + raw[1:], digest))
        with pytest.raises(AutonomousStoreError, match="source|hash|bytes"):
            if view == "summary":
                store.list_summaries()
            elif view == "snapshot":
                store.snapshot(CLAIM)
            elif view == "prefix":
                store.replay(CLAIM, 1)
            else:
                store.get(CLAIM)
    finally:
        server = SERVERS.pop(path, None)
        if server:
            server.close()


def test_all_150_original_bindings_admit_native_sources_without_processing(tmp_path):
    from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
    corpus, store = CanonicalCorpus(), AutonomousStore(tmp_path / "all-originals.db")
    source_count, channels = 0, set()
    forbidden = {"domain", "family", "split", "gold", "expected_answers", "evaluator_output", "reference_graph"}
    def inspect_keys(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for child in value.values():
                inspect_keys(child)
        elif isinstance(value, list):
            for child in value:
                inspect_keys(child)
    assert store.list_summaries() == []
    for claim_id in corpus.ids:
        preview, packet = corpus.preview_state(claim_id), corpus.packet(claim_id)
        assert preview["revision"] == 0 and preview["status"] == "not_started"
        result = store.admit_original(claim_id, packet, expected_revision=0,
                    expected_state_sha256=preview["state_sha256"], idempotency_key="all-originals." + claim_id)
        state = result["state"]
        assert result["replayed"] is False and state["claim_id"] == claim_id and state["revision"] == 1
        assert state["source_descriptors"] == preview["source_descriptors"]
        assert state["original_binding"] == preview["original_binding"]
        assert state["message"] == preview["message"] and state["initial_state_sha256"] == preview["state_sha256"]
        assert state["graph"] is None and state["evaluation"] is None and state["run_id"] is None
        assert state["acquired_sources"] == [] and state["facts"] == [] and state["receipts"] == []
        inspect_keys(state["original_binding"])
        intake = state["original_binding"]["intake"]
        channels.add(intake["submission"]["channel"])
        originals = [intake["customer_message"]["raw_file"], *intake["attachments"]]
        for original, descriptor, mapping in zip(originals, state["source_descriptors"],
                                                state["original_binding"]["source_map"], strict=True):
            assert mapping["original_artifact_id"] == original["artifact_id"]
            assert mapping["artifact_id"] == descriptor["artifact_id"] and mapping["sha256"] == descriptor["sha256"]
            for key in ("file_name", "media_type", "sha256", "size_bytes"):
                assert descriptor[key] == original[key]
            raw, downloaded = store.artifact(claim_id, descriptor["artifact_id"])
            assert raw == packet["source_bytes"][descriptor["artifact_id"]] and downloaded == descriptor
            assert sha256(raw).hexdigest() == descriptor["sha256"]
            source_count += 1
        events = store.events(claim_id)
        assert len(events) == 1 and events[0]["kind"] == "intake" and events[0]["expected_state_sha256"] is None
    rows = store.list_summaries()
    assert {row["claim_id"] for row in rows} == set(corpus.ids) and len(rows) == 150
    assert source_count == 207 and "email" in channels
