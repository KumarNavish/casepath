from __future__ import annotations

from copy import deepcopy
import threading

import pytest

from casepath_api.foundation.common import digest_text
from casepath_api.provisional_inquiry_v1 import (
    InquiryConflictError,
    InquiryError,
    InquiryJournal,
    InquiryService,
    source_assertion_from_view,
)


T0 = "2025-05-24T13:00:00+02:00"
T1 = "2025-05-25T13:00:00+02:00"
T2 = "2025-05-26T13:00:00+02:00"
T3 = "2025-05-27T13:00:00+02:00"
ADAPTER = "casepath.test-source-adapter/1.0.0"
CAPABILITIES = {
    "internal_review": {
        "capability_id": "casepath.test-internal-review/1.0.0",
        "dispatch_mode": "internal_only",
    },
    "external_evidence_request": {
        "capability_id": "casepath.test-recorded-request/1.0.0",
        "dispatch_mode": "recorded_replay_only",
    },
}


def _service(path) -> InquiryService:
    return InquiryService(
        InquiryJournal(path), capabilities=CAPABILITIES, source_adapter_id=ADAPTER
    )


def _view(source_id: str, view_id: str, observed_at: str, *texts: str) -> dict:
    return {
        "source_id": source_id,
        "view_id": view_id,
        "first_observed_at": observed_at,
        "units": [
            {"ref": f"line-{index}", "text": text}
            for index, text in enumerate(texts, 1)
        ],
    }


def _assertion(view: dict, line: int, role: str) -> dict:
    return source_assertion_from_view(
        view,
        ref=f"line-{line}",
        adapter_id=ADAPTER,
        proposed_role=role,
    )


def _pointer(source_id: str, view_id: str, observed_at: str, text: str) -> dict:
    return {
        "kind": "text",
        "source_id": source_id,
        "view_id": view_id,
        "first_observed_at": observed_at,
        "text": text,
        "text_sha256": digest_text(text),
        "view_text_sha256": digest_text(text),
        "char_start": 0,
        "char_end": len(text),
        "enclosing_context": text,
        "pointer_id": "pointer." + digest_text(
            f"{source_id}\n{view_id}\n{observed_at}\n{text}"
        ),
    }


def _admit(service: InquiryService, stream: str, *, key: str = "admit") -> tuple[dict, dict]:
    warrant = _pointer(
        "customer-message", "message-view", T0, "Please obtain the dated repair report."
    )
    proposal = {
        "description": "Obtain the dated repair report for the reported incident.",
        "warrants": [warrant],
        "reader_output_sha256": "a" * 64,
        "reader_proposal_sha256": "b" * 64,
    }
    event = service.admit_inquiry(
        stream_id=stream,
        reader_proposal=proposal,
        channel_proposal={
            "channel": "external_evidence_request",
            "basis": "fallible reader proposal admitted to configured replay capability",
        },
        observed_at=T0,
        idempotency_key=key,
    )
    return event, proposal


def _issue(
    service: InquiryService,
    stream: str,
    inquiry_id: str,
    proposal: dict,
    *,
    issued_at: str = T1,
    key: str = "request",
) -> dict:
    return service.issue_request(
        stream_id=stream,
        inquiry_id=inquiry_id,
        request_packet={
            "description": proposal["description"],
            "request_text": "Please send the dated repair report.",
            "all_warrants": proposal["warrants"],
        },
        recorded_dispatch_provenance={"kind": "synthetic_local_replay"},
        issued_at=issued_at,
        idempotency_key=key,
    )


def test_provisional_sequence_preserves_lineage_and_neighbor(tmp_path) -> None:
    service = _service(tmp_path / "inquiries.sqlite3")
    stream = "claim.example"
    initial = _view("report-v1", "report-view-v1", T0, "Repair ended May 10.", "Window was sealed.")
    original, neighbor = _assertion(initial, 1, "candidate repair date"), _assertion(
        initial, 2, "neighboring source statement"
    )
    service.register_source_assertions(
        stream_id=stream,
        assertions=[original, neighbor],
        observed_at=T0,
        idempotency_key="register",
    )
    admission, proposal = _admit(service, stream)
    inquiry_id = admission["payload"]["inquiry_id"]
    request = _issue(service, stream, inquiry_id, proposal)
    reply_view = _view("reply", "reply-view", T2, "Attached is the requested report.")
    reply = _assertion(reply_view, 1, "candidate response to inquiry")
    response = service.record_response(
        stream_id=stream,
        inquiry_id=inquiry_id,
        request_id=request["payload"]["request_id"],
        source_assertions=[reply],
        recorded_arrival_provenance={"kind": "synthetic_local_replay"},
        reader_update_sha256="c" * 64,
        observed_at=T2,
        idempotency_key="response",
    )
    corrected_view = _view(
        "report-v2", "report-view-v2", T3, "Repair ended May 12.", "Window was sealed."
    )
    corrected, restated_neighbor = _assertion(
        corrected_view, 1, "candidate corrected repair date"
    ), _assertion(corrected_view, 2, "restated neighboring source statement")
    correction = service.apply_source_correction(
        stream_id=stream,
        target_assertion_id=original["assertion_id"],
        correction_assertion=corrected,
        neighbor_assertions=[restated_neighbor],
        recorded_arrival_provenance={"kind": "synthetic_local_replay"},
        observed_at=T3,
        idempotency_key="correction",
    )

    state = service.state(stream)
    assert response["payload"]["request_id"] == request["payload"]["request_id"]
    assert correction["payload"]["target_assertion_id"] == original["assertion_id"]
    assert state["source_assertions"][original["assertion_id"]]["status"] == (
        "superseded_by_source_correction"
    )
    assert state["source_assertions"][neighbor["assertion_id"]] == neighbor
    assert state["source_assertions"][reply["assertion_id"]] == reply
    assert state["canonical_facts"] == {}
    assert state["canonical_readiness"] is None
    service.journal.close()


def test_concurrent_corrections_use_parent_compare_and_swap(tmp_path) -> None:
    path = tmp_path / "concurrent.sqlite3"
    setup = _service(path)
    stream = "claim.concurrent"
    original_view = _view("report", "report-view", T0, "Repair ended May 10.")
    original = _assertion(original_view, 1, "candidate repair date")
    setup.register_source_assertions(
        stream_id=stream,
        assertions=[original],
        observed_at=T0,
        idempotency_key="register",
    )
    setup.journal.close()

    barrier = threading.Barrier(2)
    outcomes: list[str] = []
    errors: list[Exception] = []

    def correct(day: str) -> None:
        service = _service(path)
        replacement = _assertion(
            _view(f"report-{day}", f"report-view-{day}", T1, f"Repair ended {day}."),
            1,
            "candidate corrected repair date",
        )
        original_state = service.state

        def synchronized_state(stream_id: str) -> dict:
            snapshot = original_state(stream_id)
            barrier.wait(timeout=5)
            return snapshot

        service.state = synchronized_state  # type: ignore[method-assign]
        try:
            service.apply_source_correction(
                stream_id=stream,
                target_assertion_id=original["assertion_id"],
                correction_assertion=replacement,
                neighbor_assertions=[],
                recorded_arrival_provenance={"kind": "synthetic_local_replay"},
                observed_at=T1,
                idempotency_key=f"correction-{day}",
            )
            outcomes.append(replacement["assertion_id"])
        except Exception as exc:  # captured for cross-thread assertion below
            errors.append(exc)
        finally:
            service.journal.close()

    threads = [threading.Thread(target=correct, args=(day,)) for day in ("May 11", "May 12")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert len(outcomes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], InquiryConflictError)
    check = _service(path)
    state = check.state(stream)
    assert state["revision"] == 2
    assert state["source_assertions"][original["assertion_id"]]["status"] == (
        "superseded_by_source_correction"
    )
    assert outcomes[0] in state["source_assertions"]
    check.journal.close()


def test_same_inquiry_cannot_be_readmitted_or_reset_after_response(tmp_path) -> None:
    service = _service(tmp_path / "admission.sqlite3")
    stream = "claim.admission"
    admission, proposal = _admit(service, stream)
    inquiry_id = admission["payload"]["inquiry_id"]
    request = _issue(service, stream, inquiry_id, proposal)
    reply = _assertion(_view("reply", "reply-view", T2, "Report attached."), 1, "reply")
    service.record_response(
        stream_id=stream,
        inquiry_id=inquiry_id,
        request_id=request["payload"]["request_id"],
        source_assertions=[reply],
        recorded_arrival_provenance={"kind": "synthetic_local_replay"},
        reader_update_sha256="c" * 64,
        observed_at=T2,
        idempotency_key="response",
    )

    replay, _ = _admit(service, stream, key="admit")
    assert replay["replayed"] is True
    with pytest.raises(InquiryError, match="already admitted"):
        _admit(service, stream, key="redundant-admission")
    state = service.state(stream)
    assert state["revision"] == 3
    assert state["inquiries"][inquiry_id]["lifecycle_status"] == (
        "response_observed_unassessed"
    )
    service.journal.close()


def test_timestamps_are_aware_and_chronological(tmp_path) -> None:
    service = _service(tmp_path / "time.sqlite3")
    stream = "claim.time"
    warrant = _pointer("message", "message-view", T0, "Please obtain the report.")
    proposal = {
        "description": "Obtain the report.",
        "warrants": [warrant],
        "reader_output_sha256": "a" * 64,
        "reader_proposal_sha256": "b" * 64,
    }
    with pytest.raises(InquiryError, match="aware"):
        service.admit_inquiry(
            stream_id=stream,
            reader_proposal=proposal,
            channel_proposal={"channel": "external_evidence_request"},
            observed_at="2025-05-24T13:00:00",
            idempotency_key="naive",
        )
    admission = service.admit_inquiry(
        stream_id=stream,
        reader_proposal=proposal,
        channel_proposal={"channel": "external_evidence_request"},
        observed_at=T1,
        idempotency_key="admit",
    )
    with pytest.raises(InquiryError, match="precedes"):
        service.issue_request(
            stream_id=stream,
            inquiry_id=admission["payload"]["inquiry_id"],
            request_packet={
                "description": proposal["description"],
                "request_text": "Please send the report.",
                "all_warrants": proposal["warrants"],
            },
            recorded_dispatch_provenance={"kind": "synthetic_local_replay"},
            issued_at=T0,
            idempotency_key="too-early",
        )
    request = _issue(
        service,
        stream,
        admission["payload"]["inquiry_id"],
        proposal,
        issued_at=T2,
    )
    early_reply = _assertion(
        _view("early-reply", "early-reply-view", T1, "Report attached."), 1, "reply"
    )
    with pytest.raises(InquiryError, match="precedes"):
        service.record_response(
            stream_id=stream,
            inquiry_id=admission["payload"]["inquiry_id"],
            request_id=request["payload"]["request_id"],
            source_assertions=[early_reply],
            recorded_arrival_provenance={"kind": "synthetic_local_replay"},
            reader_update_sha256="c" * 64,
            observed_at=T1,
            idempotency_key="early-response",
        )
    reply = _assertion(_view("reply", "reply-view", T2, "Report attached."), 1, "reply")
    service.record_response(
        stream_id=stream,
        inquiry_id=admission["payload"]["inquiry_id"],
        request_id=request["payload"]["request_id"],
        source_assertions=[reply],
        recorded_arrival_provenance={"kind": "synthetic_local_replay"},
        reader_update_sha256="d" * 64,
        observed_at=T2,
        idempotency_key="response",
    )
    early_correction = _assertion(
        _view("correction", "correction-view", T1, "Report withdrawn."),
        1,
        "candidate correction",
    )
    with pytest.raises(InquiryError, match="precedes"):
        service.apply_source_correction(
            stream_id=stream,
            target_assertion_id=reply["assertion_id"],
            correction_assertion=early_correction,
            neighbor_assertions=[],
            recorded_arrival_provenance={"kind": "synthetic_local_replay"},
            observed_at=T1,
            idempotency_key="early-correction",
        )
    service.journal.close()


@pytest.mark.parametrize("entrypoint", ["register", "response", "correction"])
def test_assertion_integrity_is_uniform_at_every_entrypoint(tmp_path, entrypoint: str) -> None:
    service = _service(tmp_path / f"integrity-{entrypoint}.sqlite3")
    stream = f"claim.integrity.{entrypoint}"
    original = _assertion(_view("initial", "initial-view", T0, "Initial report."), 1, "initial")
    malformed = deepcopy(
        _assertion(_view("new", "new-view", T2, "New report."), 1, "new")
    )
    malformed["reported_text"] = "Tampered after hashing."

    if entrypoint == "register":
        with pytest.raises(InquiryError, match="overstates"):
            service.register_source_assertions(
                stream_id=stream,
                assertions=[malformed],
                observed_at=T2,
                idempotency_key="malformed",
            )
    else:
        service.register_source_assertions(
            stream_id=stream,
            assertions=[original],
            observed_at=T0,
            idempotency_key="register",
        )
        if entrypoint == "response":
            admission, proposal = _admit(service, stream)
            request = _issue(service, stream, admission["payload"]["inquiry_id"], proposal)
            with pytest.raises(InquiryError, match="overstates"):
                service.record_response(
                    stream_id=stream,
                    inquiry_id=admission["payload"]["inquiry_id"],
                    request_id=request["payload"]["request_id"],
                    source_assertions=[malformed],
                    recorded_arrival_provenance={"kind": "synthetic_local_replay"},
                    reader_update_sha256="c" * 64,
                    observed_at=T2,
                    idempotency_key="malformed",
                )
        else:
            with pytest.raises(InquiryError, match="overstates"):
                service.apply_source_correction(
                    stream_id=stream,
                    target_assertion_id=original["assertion_id"],
                    correction_assertion=malformed,
                    neighbor_assertions=[],
                    recorded_arrival_provenance={"kind": "synthetic_local_replay"},
                    observed_at=T2,
                    idempotency_key="malformed",
                )
    assert service.state(stream)["revision"] in {0, 1, 3}
    service.journal.close()
