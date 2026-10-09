"""Fresh hosted byte verification batches bounded pages without provider calls."""
from hashlib import sha256
from math import ceil

import pytest

from hosted_hrana_fixture import MockHrana
from casepath_api.autonomous_corpus_v1 import CanonicalCorpus
from casepath_api.autonomous_store_v1 import AutonomousStoreError, MAX_FILE_BYTES
from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources, HostedStorageError


@pytest.fixture
def remote(tmp_path):
    server = MockHrana(tmp_path / "source-batches.sqlite3")
    journal = HostedJournal(tmp_path / "unused-journal", server.connection)
    yield server, journal
    server.close()


def new_store(remote):
    server, journal = remote
    return HostedAutonomousStore(journal.path, journal=journal, source_store=HostedSources(server.connection))


def receipt(server):
    operations = [operation["type"] for request in server.requests for operation in request["requests"]]
    return {"http": len(server.requests), "execute": operations.count("execute"),
            "close": operations.count("close"), "batch": operations.count("batch")}


def realistic_roster(remote):
    corpus, store = CanonicalCorpus(), new_store(remote)
    selected, needed = [], [3, 2, 2, 2, 2, 2, 2, 1, 1]
    by_size = {}
    for claim in corpus.ids:
        by_size.setdefault(len(corpus.preview_state(claim)["source_descriptors"]), []).append(claim)
    for count in needed:
        claim_id = by_size[count].pop(0)
        packet = corpus.packet(claim_id)
        result = store.admit_original(claim_id, packet, expected_revision=0,
                    expected_state_sha256=packet["initial_state_sha256"], idempotency_key="batch.fixture." + claim_id)
        assert not result["replayed"]
        selected.append(claim_id)
    for index in range(14):
        store.intake({"title": "Native legacy fixture " + str(index),
                      "message": "A unique original customer statement " + str(index) + "."},
                     "batch.legacy.fixture." + str(index))
    rows = store.list_summaries()
    states = store.list()
    digests = {source["sha256"] for state in states for source in state["source_descriptors"]}
    assert len(rows) == 23 and len(digests) == 31
    chunks = sum(ceil(len(store._source_store.read(digest)) / HostedSources.CHUNK_BYTES) for digest in digests)
    assert sum(len(store._source_store.read(digest)) for digest in digests) < HostedSources.CACHE_BYTES
    return store, selected[0], digests, chunks


@pytest.mark.parametrize("cold", [False, True])
def test_real_31_source_collection_uses_bounded_batched_roundtrips(remote, cold):
    store, _, digests, chunks = realistic_roster(remote)
    if cold:
        store = new_store(remote)
    server, _ = remote
    server.requests.clear()
    rows = store.list_summaries()
    measured = receipt(server)
    pages = ceil(chunks / 8) + (chunks % 8 == 0)
    expected = {"http": 2 * pages + 4 if cold else pages + 3, "execute": 2 * pages + 1 if cold else pages + 1,
                "close": 3 if cold else 2, "batch": 0}
    assert measured == expected, measured
    assert len(rows) == 23 and len(digests) == 31 and server.open_streams == 0
    print("31-source " + ("cold" if cold else "warm") + " collection receipt:", measured)


@pytest.mark.parametrize("cold", [False, True])
def test_real_three_source_snapshot_batches_fresh_verification(remote, cold):
    store, claim_id, _, _ = realistic_roster(remote)
    if cold:
        store = new_store(remote)
    server, _ = remote
    server.requests.clear()
    snapshot = store.snapshot(claim_id)
    measured = receipt(server)
    assert measured == {"http": 6 if cold else 4, "execute": 3 if cold else 2,
                        "close": 3 if cold else 2, "batch": 0}, measured
    assert len(snapshot["state"]["source_descriptors"]) == 3
    assert snapshot["events"][-1]["resulting_state_sha256"] == snapshot["current_state_sha256"]
    assert server.open_streams == 0
    print("3-source " + ("cold" if cold else "warm") + " snapshot receipt:", measured)


@pytest.mark.parametrize("length", [8 * HostedSources.CHUNK_BYTES, 8 * HostedSources.CHUNK_BYTES + 1, MAX_FILE_BYTES])
def test_chunk_page_boundaries_and_maximum_source_complete_verification(remote, length):
    server, _ = remote
    sources = HostedSources(server.connection)
    raw = (bytes(range(256)) * ceil(length / 256))[:length]
    digest = sources.publish(raw)
    server.requests.clear()
    sources.verify_many([digest, digest])
    chunks = ceil(length / sources.CHUNK_BYTES)
    pages = ceil(chunks / 8) + (chunks % 8 == 0)
    assert receipt(server) == {"http": pages + 1, "execute": pages, "close": 1, "batch": 0}
    assert sources.read(digest) == raw
    selects = [operation for request in server.requests for operation in request["requests"]
               if operation["type"] == "execute"]
    assert all("LIMIT 8" in operation["stmt"]["sql"] for operation in selects)
    assert server.open_streams == 0


@pytest.mark.parametrize("fault", ["changed_later_chunk", "missing_later_chunk", "extra_empty_chunk", "gap_later_page", "oversize_chunk"])
def test_warm_batch_checks_later_pages_and_exact_complete_chunk_inventory(remote, fault):
    server, _ = remote
    sources = HostedSources(server.connection)
    raw = b"P" * (8 * sources.CHUNK_BYTES) + b"An original final page."
    digest = sources.publish(raw)
    with server.connection() as db:
        if fault == "changed_later_chunk":
            db.execute("DROP TRIGGER autonomous_source_chunks_no_update")
            db.execute("UPDATE autonomous_source_chunks SET content=? WHERE sha256=? AND chunk_index=8",
                       (b"X" + raw[8 * sources.CHUNK_BYTES + 1:], digest))
        elif fault == "missing_later_chunk":
            db.execute("DROP TRIGGER autonomous_source_chunks_no_delete")
            db.execute("DELETE FROM autonomous_source_chunks WHERE sha256=? AND chunk_index=8", (digest,))
        elif fault == "extra_empty_chunk":
            db.execute("INSERT INTO autonomous_source_chunks VALUES (?,?,?)", (digest, 9, b""))
        elif fault == "gap_later_page":
            db.execute("INSERT INTO autonomous_source_chunks VALUES (?,?,?)", (digest, 10, b"extra gap"))
        else:
            db.execute("INSERT INTO autonomous_source_chunks VALUES (?,?,?)",
                       (digest, 9, b"X" * (sources.CHUNK_BYTES + 1)))
    with pytest.raises(AutonomousStoreError, match="source|hash|bytes|chunk"):
        sources.verify_many([digest])
    assert server.open_streams == 0


def test_empty_invalid_and_missing_batches_do_not_return_false_verification(remote):
    server, _ = remote
    sources = HostedSources(server.connection)
    server.requests.clear()
    sources.verify_many([])
    assert receipt(server)["http"] == 0
    with pytest.raises(AutonomousStoreError, match="identity"):
        sources.verify_many(["invalid"])
    assert receipt(server)["http"] == 0
    with pytest.raises(AutonomousStoreError, match="source|hash|bytes"):
        sources.verify_many([sha256(b"not published").hexdigest()])
    assert server.open_streams == 0


def test_digest_group_boundary_keeps_one_shared_connection(remote):
    server, _ = remote
    sources = HostedSources(server.connection)
    digests = [sources.publish(("Original source " + str(index)).encode())
               for index in range(sources.BATCH_DIGESTS + 1)]
    server.requests.clear()
    sources.verify_many(reversed(digests))
    first_group_pages = sources.BATCH_DIGESTS // sources.PAGE_CHUNKS + 1
    assert receipt(server) == {"http": first_group_pages + 2, "execute": first_group_pages + 1,
                               "close": 1, "batch": 0}
    assert server.open_streams == 0


def test_transport_failure_on_later_chunk_page_never_acknowledges_verification(remote, monkeypatch):
    server, _ = remote
    sources = HostedSources(server.connection)
    digest = sources.publish(b"P" * (8 * sources.CHUNK_BYTES + 23))
    statement, pages = server._statement, []
    def fail_second_page(connection, command):
        result = statement(connection, command)
        if command["sql"].startswith("SELECT sha256,chunk_index"):
            pages.append(True)
            if len(pages) == 2:
                server.fail_next("timeout", sql_prefix="SELECT sha256,chunk_index")
        return result
    monkeypatch.setattr(server, "_statement", fail_second_page)
    with pytest.raises(HostedStorageError):
        sources.verify_many([digest])
    assert len(pages) == 2
    assert digest not in sources._cache


def test_final_boundary_rechecks_bytes_changed_after_cold_prefetch(remote, monkeypatch):
    store, claim_id, _, _ = realistic_roster(remote)
    store = new_store(remote)
    server, _ = remote
    reduce, changed = store._reduce, []
    def mutate_after_read(state, event):
        result = reduce(state, event)
        if not changed:
            changed.append(True)
            digest = result["source_descriptors"][0]["sha256"]
            raw = store._source_store.read(digest)
            with server.connection() as db:
                db.execute("DROP TRIGGER autonomous_source_chunks_no_update")
                db.execute("UPDATE autonomous_source_chunks SET content=? WHERE sha256=? AND chunk_index=0",
                           (b"X" + raw[1:], digest))
        return result
    monkeypatch.setattr(store, "_reduce", mutate_after_read)
    with pytest.raises(AutonomousStoreError, match="source|hash|bytes"):
        store.snapshot(claim_id)
