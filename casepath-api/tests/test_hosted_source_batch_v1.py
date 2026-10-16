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


def assert_source_pages_closed(server):
    # Each bounded source SELECT now closes its Hrana stream in the same RPC.
    for request in server.requests:
        operations = request["requests"]
        if any(operation["type"] == "execute" and
               operation["stmt"]["sql"].startswith("SELECT sha256,chunk_index")
               for operation in operations):
            assert [operation["type"] for operation in operations] == ["execute", "close"]
            assert "LIMIT 8" in operations[0]["stmt"]["sql"]


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
    source_pages = pages * (2 if cold else 1)
    # The journal still uses one execute RPC and a separate close RPC.
    expected = {"http": source_pages + 2, "execute": source_pages + 1,
                "close": source_pages + 1, "batch": 0}
    assert measured == expected, measured
    assert_source_pages_closed(server)
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
    # This three-source packet fits one page; cold reads prefetch it once too.
    source_pages = 2 if cold else 1
    assert measured == {"http": source_pages + 2, "execute": source_pages + 1,
                        "close": source_pages + 1, "batch": 0}, measured
    assert_source_pages_closed(server)
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
    assert receipt(server) == {"http": pages, "execute": pages, "close": pages, "batch": 0}
    assert_source_pages_closed(server)
    assert sources.read(digest) == raw
    selects = [operation for request in server.requests for operation in request["requests"]
               if operation["type"] == "execute"]
    assert all("LIMIT 8" in operation["stmt"]["sql"] for operation in selects)
    assert server.open_streams == 0


def test_knowledge_source_pages_reduce_tiny_file_requests_without_changing_default_reads(remote):
    server, _ = remote
    sources = HostedSources(server.connection)
    originals = {sources.publish(('Isolated tiny original ' + str(index)).encode()):
                 ('Isolated tiny original ' + str(index)).encode() for index in range(40)}
    server.requests.clear()
    sources.verify_many(originals, page_chunks=128)
    assert receipt(server) == {'http': 1, 'execute': 1, 'close': 1, 'batch': 0}
    assert sources.PAGE_CHUNKS == 8 and server.open_streams == 0
    assert all(sources.read(digest) == raw for digest, raw in originals.items())
    server.requests.clear()
    sources.verify_many(originals)
    assert receipt(server) == {'http': 6, 'execute': 6, 'close': 6, 'batch': 0}
    assert_source_pages_closed(server)


def test_knowledge_byte_limited_short_pages_continue_until_all_chunks_are_verified(remote, monkeypatch):
    server, _ = remote
    sources = HostedSources(server.connection)
    original = b'P' * (8 * sources.CHUNK_BYTES) + b'An actual final partial chunk.'
    digest = sources.publish(original)
    pages = []
    statement = server._statement

    def count_page(connection, command):
        result = statement(connection, command)
        if command['sql'].startswith('SELECT sha256,chunk_index'):
            content_index = next(index for index, col in enumerate(result['cols']) if col['name'] == 'content')
            from casepath_api.hosted_sql_v1 import _decode
            pages.append([_decode(row[content_index]) for row in result['rows']])
        return result

    monkeypatch.setattr(server, '_statement', count_page)
    sources.verify_many([digest], page_chunks=128)
    assert [len(page) for page in pages] == [8, 1]
    assert all(sum(len(chunk) for chunk in page) <= 2 * 1024 * 1024 for page in pages)
    assert sources.read(digest) == original and server.open_streams == 0


@pytest.mark.parametrize('fault', ['changed_later_chunk', 'missing_later_chunk', 'gap_later_page', 'oversize_chunk', 'wrong_type'])
def test_knowledge_source_pages_keep_exact_hash_chunk_inventory_and_type_checks(remote, fault):
    server, _ = remote
    sources = HostedSources(server.connection)
    raw = b'P' * (8 * sources.CHUNK_BYTES) + b'An original final page.'
    digest = sources.publish(raw)
    with server.connection() as db:
        if fault == 'missing_later_chunk':
            db.execute('DROP TRIGGER autonomous_source_chunks_no_delete')
            db.execute('DELETE FROM autonomous_source_chunks WHERE sha256=? AND chunk_index=8', (digest,))
        elif fault in {'changed_later_chunk', 'wrong_type'}:
            db.execute('DROP TRIGGER autonomous_source_chunks_no_update')
            db.execute('UPDATE autonomous_source_chunks SET content=? WHERE sha256=? AND chunk_index=8',
                       ('Invalid text instead of original bytes.' if fault == 'wrong_type' else b'Changed final bytes.', digest))
        else:
            db.execute('INSERT INTO autonomous_source_chunks VALUES (?,?,?)',
                       (digest, 10 if fault == 'gap_later_page' else 9,
                        b'gap' if fault == 'gap_later_page' else b'X' * (sources.CHUNK_BYTES + 1)))
    with pytest.raises(AutonomousStoreError, match='source|hash|bytes|chunk'):
        sources.verify_many([digest], page_chunks=128)
    assert server.open_streams == 0


def test_knowledge_final_source_verification_still_detects_mutation_after_prefetch(remote, monkeypatch):
    store = new_store(remote)
    store.intake({'title': 'Knowledge final boundary fixture', 'message': 'Original customer evidence.'}, 'knowledge.final')
    server, _ = remote
    store = new_store(remote)
    reduce, changed = store._reduce, []

    def mutate_after_prefetch(state, event):
        result = reduce(state, event)
        if not changed:
            changed.append(True)
            digest = result['source_descriptors'][0]['sha256']
            with server.connection() as db:
                db.execute('DROP TRIGGER autonomous_source_chunks_no_update')
                db.execute('UPDATE autonomous_source_chunks SET content=? WHERE sha256=? AND chunk_index=0',
                           (b'Changed during replay.', digest))
        return result

    monkeypatch.setattr(store, '_reduce', mutate_after_prefetch)
    with pytest.raises(AutonomousStoreError, match='source|hash|bytes'):
        store.knowledge_snapshot()


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
    pages = first_group_pages + 1
    assert receipt(server) == {"http": pages, "execute": pages, "close": pages, "batch": 0}
    assert_source_pages_closed(server)
    assert [sources.read(digest) for digest in digests] == [
        ("Original source " + str(index)).encode() for index in range(sources.BATCH_DIGESTS + 1)]
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
