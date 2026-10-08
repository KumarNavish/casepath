"""Operational intake/journal tests use only newly authored temporary bytes."""
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from casepath_api.autonomous_store_v1 import AutonomousStore, AutonomousStoreError, SESSION_ID
from casepath_api.causal_process_v1 import seal_graph
from casepath_api.storage import Storage, ReservedSessionResetError
from casepath_api.workspace_corpus import digest_value


def file(name="support.txt", content=b"A supporting statement.", media="text/plain"):
    return {"file_name": name, "media_type": media,
            "content_base64": base64.b64encode(content).decode()}


def intake(store, key="intake.first"):
    return store.intake({"title": "New incoming claim", "message": "Please inspect this claim.",
                         "files": [file()]}, idempotency_key=key)


def append(store, state, kind, payload, key):
    return store.append(state["claim_id"], kind, payload,
                        expected_revision=state["revision"],
                        expected_state_sha256=state["state_sha256"], idempotency_key=key)


def receipt():
    value = {"proposal_sha256": "a" * 64, "verifier_sha256": "b" * 64,
             "gate_sha256": "c" * 64, "policy_id": "policy.v1"}
    return {**value, "receipt_sha256": digest_value(value)}


def test_intake_is_immutable_idempotent_and_only_message_is_acquired(tmp_path):
    storage = Storage(str(tmp_path / "state.db"))
    store = AutonomousStore(storage)
    state = intake(store)
    assert state == intake(store)
    assert len(state["source_descriptors"]) == 2
    assert [s["role"] for s in state["acquired_sources"]] == ["customer_message"]
    assert state["graph"] is None
    assert state["status"] == "received"
    assert AutonomousStore(storage).get(state["claim_id"]) == state
    with pytest.raises(ReservedSessionResetError):
        storage.reset(session_id=SESSION_ID)
    with pytest.raises(AutonomousStoreError, match="idempotency"):
        store.intake({"title": "Different", "message": "Different"}, idempotency_key="intake.first")


def test_acquisition_is_read_only_then_exactly_journaled_and_cross_claim_closed(tmp_path):
    store = AutonomousStore(tmp_path / "state.db")
    state = intake(store)
    descriptor = state["source_descriptors"][1]
    source = store.acquire(state["claim_id"], descriptor["artifact_id"])
    assert source["text"] == "A supporting statement."
    assert source["complete"] is True
    assert store.get(state["claim_id"]) == state
    current = append(store, state, "sources.acquired", {"sources": [source]}, "acquire.first")
    assert len(current["acquired_sources"]) == 2
    assert append(store, state, "sources.acquired", {"sources": [source]}, "acquire.first") == current
    other = intake(store, "intake.second")
    with pytest.raises(AutonomousStoreError, match="source|claim"):
        append(store, other, "sources.acquired", {"sources": [source]}, "bad.source")
    forged = {**source, "text": "Invented"}
    with pytest.raises(AutonomousStoreError, match="receipt|source"):
        append(store, current, "sources.acquired", {"sources": [forged]}, "forged.source")


def test_cas_replay_chain_tamper_and_namespace_isolation(tmp_path):
    store = AutonomousStore(tmp_path / "state.db")
    state = intake(store)
    def start(key):
        try:
            return append(store, state, "work.started", {"run_id": key, "policy_id": "policy.v1"}, key)
        except AutonomousStoreError:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(start, ["run.one", "run.two"]))
    assert sum(result is not None for result in results) == 1
    with store.journal.connect() as con:
        con.execute("UPDATE claim_loop_events SET created_at='tampered' WHERE session_id=? AND sequence=1", (SESSION_ID,))
    with pytest.raises(AutonomousStoreError, match="journal|identity|hash"):
        store.get(state["claim_id"])


def test_graph_acceptance_seals_evaluates_and_rejects_wrong_claim(tmp_path):
    store = AutonomousStore(tmp_path / "state.db")
    state = intake(store)
    state = append(store, state, "work.started", {"run_id": "run.a", "policy_id": "policy.v1"}, "run.start")
    graph = seal_graph({"family": "local", "claim_id": state["claim_id"],
                        "nodes": [{"node_id": "inspect", "label": "Inspect evidence", "entry": True}]})
    payload = {"graph": graph, "facts": [], "obligations": [], "receipt": receipt()}
    after = append(store, state, "interpretation.accepted", payload, "interpret.first")
    assert after["graph"] == graph
    assert after["evaluation"]["nodes"][0]["execution_state"] == "ready"
    assert AutonomousStore(tmp_path / "state.db").get(state["claim_id"]) == after
    invalid = deepcopy(payload)
    invalid["graph"]["claim_id"] = "other"
    with pytest.raises(AutonomousStoreError, match="graph|claim"):
        append(store, after, "interpretation.accepted", invalid, "interpret.invalid")
    with pytest.raises(AutonomousStoreError, match="event|fields"):
        append(store, after, "state.overwrite", {"status": "resolved"}, "overwrite")


def test_receipts_bind_parent_and_graph_sources_require_real_acquisition(tmp_path):
    store = AutonomousStore(tmp_path / "state.db")
    state = intake(store)
    source = state["source_descriptors"][1]
    graph = seal_graph({"family": "local", "claim_id": state["claim_id"],
                       "nodes": [{"node_id": "inspect", "label": "Inspect", "entry": True, "document_types": ["proof"]}],
                       "document_catalog": [{"document_type": "proof", "label": "Proof", "held_files": [
                           {"artifact_id": source["artifact_id"], "sha256": source["sha256"], "source_quote": "A supporting statement."}]}]})
    payload = {"graph": graph, "facts": [], "obligations": [], "receipt": receipt()}
    with pytest.raises(AutonomousStoreError, match="acquired"):
        append(store, state, "interpretation.accepted", payload, "not.acquired")
    acquired = store.acquire(state["claim_id"], source["artifact_id"])
    state = append(store, state, "sources.acquired", {"sources": [acquired]}, "acquire.proof")
    bound = {k: v for k, v in receipt().items() if k != "receipt_sha256"}
    bound.update(parent_revision=state["revision"], parent_state_sha256=state["state_sha256"], after_graph_sha256=graph["graph_sha256"])
    bound["receipt_sha256"] = digest_value(bound)
    payload["receipt"] = bound
    valid = append(store, state, "interpretation.accepted", payload, "valid.bound")
    with pytest.raises(AutonomousStoreError, match="bound"):
        append(store, valid, "interpretation.accepted", payload, "stale.receipt")
    wrong = deepcopy(payload)
    wrong["receipt"] = {**receipt(), "gate_sha256": "d" * 64}
    with pytest.raises(AutonomousStoreError, match="seal"):
        append(store, valid, "interpretation.accepted", wrong, "broken.seal")
    with pytest.raises(AutonomousStoreError, match="complete"):
        append(store, valid, "outcome.recorded", {"outcome": {"status": "resolved"}, "receipt": receipt()}, "premature.resolution")


def test_exact_concurrent_intake_and_later_retries_preserve_original_result(tmp_path):
    store = AutonomousStore(tmp_path / "state.db")
    with ThreadPoolExecutor(max_workers=2) as pool:
        states = list(pool.map(lambda _: intake(store), range(2)))
    assert states[0] == states[1]
    original = states[0]
    current = append(store, original, "work.started", {"run_id": "run.a", "policy_id": "casepath.local/1.0.0"}, "start.a")
    assert intake(store) == original
    assert store.get(original["claim_id"]) == current
    assert store.list(statuses={"running"}) == [current]
    assert [event["kind"] for event in store.events(original["claim_id"], after=1)] == ["work.started"]
    assert store.get(original["claim_id"]) == current


def test_action_context_updates_fact_projection_and_preserves_old_namespaces(tmp_path):
    store = AutonomousStore(tmp_path / "state.db")
    with store.journal.connect() as connection:
        connection.execute("INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)",
                           ("unrelated", "untouched", 1, "old", "x", "y", "old-bytes", "old-time"))
    state = intake(store)
    facts = [{"fact_id": "local-record", "status": "unresolved", "citations": []}]
    graph = seal_graph({"family": "local", "claim_id": state["claim_id"],
                       "nodes": [{"node_id": "inspect", "label": "Inspect", "entry": True}],
                       "assessment_context": {"facts": facts, "obligations": []}})
    current = append(store, state, "action.completed", {"graph": graph, "result": {"action": "internal_inspection"}, "receipt": receipt()}, "action.first")
    assert current["facts"] == facts
    assert current["actions"][0]["result"] == {"action": "internal_inspection"}
    with store.journal.connect() as connection:
        row = connection.execute("SELECT event_json FROM claim_loop_events WHERE session_id='unrelated'").fetchone()
    assert row["event_json"] == "old-bytes"


def test_new_sources_reopen_deferral_and_file_validation(tmp_path):
    store = AutonomousStore(tmp_path / "state.db")
    state = intake(store)
    deferred = append(store, state, "work.deferred", {"code": "missing_evidence", "reason": "Receipt missing."}, "defer.first")
    next_state = store.add_sources(state["claim_id"], [file("receipt.txt", b"Receipt arrived.")],
                                  expected_revision=deferred["revision"], expected_state_sha256=deferred["state_sha256"],
                                  idempotency_key="arrive.first")
    assert next_state["status"] == "received"
    assert len(next_state["source_descriptors"]) == 3
    assert len(next_state["acquired_sources"]) == 1
    for bad in [file("../../secret.txt"), file("bad\x00.txt"), {**file(), "content_base64": "!bad!"}]:
        with pytest.raises(AutonomousStoreError):
            store.intake({"title": "Bad", "message": "Bad intake", "files": [bad]}, idempotency_key="bad." + str(len(str(bad))))


def test_pdf_email_and_unsupported_extraction_preserve_limits(tmp_path):
    import fitz
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((40, 40), "Original PDF passage.")
    raw_pdf = pdf.tobytes()
    pdf.close()
    email = b"Subject: Source\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Transfer-Encoding: base64\r\n\r\nRXhhY3QgZW1haWwgcGFzc2FnZS4=\r\n"
    store = AutonomousStore(tmp_path / "state.db")
    state = store.intake({"title": "Formats", "message": "Check original files", "files": [
        file("notice.pdf", raw_pdf, "application/pdf"), file("source.eml", email, "message/rfc822"),
        file("scan.png", b"\x89PNG\r\n\x1a\nunknown-pixels", "image/png")]}, idempotency_key="formats.first")
    sources = [store.acquire(state["claim_id"], d["artifact_id"]) for d in state["source_descriptors"][1:]]
    assert "Original PDF passage." in sources[0]["text"]
    assert sources[0]["complete"] is True
    assert "Exact email passage." in sources[1]["text"]
    assert "Subject: Source" in sources[1]["text"]
    assert sources[2]["text"] == "" and sources[2]["complete"] is False
    blob = store.source_root / sources[0]["sha256"]
    blob.write_bytes(b"changed")
    with pytest.raises(AutonomousStoreError, match="source|hash|bytes"):
        store.get(state["claim_id"])


def test_email_headers_and_nested_decode_defects_are_part_of_extraction_coverage(tmp_path):
    store = AutonomousStore(tmp_path / "state.db")
    valid = (b"From: owner@example.test\r\nTo: spouse@example.test\r\n"
             b"Date: Mon, 5 Oct 2026 10:20:00 +0200\r\n"
             b"Subject: =?utf-8?b?S8O8bmRpZ3VuZw==?=\r\n"
             b"Content-Type: text/plain; charset=utf-8\r\n\r\nA separate notice.\r\n")
    damaged = (b"Content-Type: multipart/mixed; boundary=parts\r\n\r\n--parts\r\n"
               b"Content-Type: text/plain; charset=utf-8\r\n"
               b"Content-Transfer-Encoding: base64\r\n\r\nSGVsbG8=???\r\n--parts--\r\n")
    state = store.intake({"title": "Email provenance", "message": "Inspect actual mail metadata.", "files": [
        file("notice.eml", valid, "message/rfc822"), file("damaged.eml", damaged, "message/rfc822")]},
        idempotency_key="email.provenance")
    normal, invalid = [store.acquire(state["claim_id"], d["artifact_id"]) for d in state["source_descriptors"][1:]]
    assert normal["complete"] is True
    for field in ["From: owner@example.test", "To: spouse@example.test", "Date: Mon, 05 Oct 2026 10:20:00 +0200", "Subject: Kündigung"]:
        assert field in normal["text"]
    assert invalid["complete"] is False
    assert invalid["coverage"]["parse_defects"] > 0
