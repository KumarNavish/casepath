"""Content-addressed provisional inquiry journal for CasePath integration.

This module never authors canonical facts, evidence sufficiency, legal outcomes,
or readiness.  Reader semantics and source roles remain proposals until a
separate authoritative product capability binds them.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from .claim_loop_contracts import ClaimSourceRef
from .foundation.common import digest_text, digest_value


class InquiryError(ValueError):
    pass


class InquiryConflictError(InquiryError):
    """The stream changed after a state-dependent operation was prepared."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _aware_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise InquiryError(f"{field} is not an aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InquiryError(f"{field} is not an aware ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InquiryError(f"{field} is not an aware ISO-8601 timestamp")
    return parsed


def _source_observed_at(source_ref: ClaimSourceRef) -> datetime:
    separator, observed_at = source_ref.source_version.rpartition("@")[1:]
    if not separator or not observed_at:
        raise InquiryError("source version lacks its aware observation timestamp")
    return _aware_timestamp(observed_at, "source first_observed_at")


def _event_timestamp(event: Mapping[str, Any]) -> datetime | None:
    payload = event["payload"]
    for field in ("observed_at", "issued_at", "admitted_at"):
        if field in payload:
            return _aware_timestamp(payload[field], field)
    return None


def _require_monotonic_time(events: list[dict[str, Any]], value: str, field: str) -> None:
    current = _aware_timestamp(value, field)
    prior = [timestamp for event in events if (timestamp := _event_timestamp(event))]
    if prior and current < max(prior):
        raise InquiryError(f"{field} precedes the observed inquiry history")


def validate_artifact_binding(
    binding: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if binding is None:
        return None
    required = {
        "raw_artifact_sha256", "raw_artifact_path", "rendered_image_sha256",
        "rendered_image_path", "input_receipt_sha256", "input_receipt_path",
        "artifact_registry_sha256", "artifact_registry_path",
        "source_prefix_sha256", "binding_status",
    }
    if set(binding) != required or binding["binding_status"] != "HASH_VERIFIED_LOCAL_REPLAY":
        raise InquiryError("original artifact binding is incomplete")
    for field in (
        "raw_artifact_sha256", "input_receipt_sha256",
        "artifact_registry_sha256", "source_prefix_sha256",
    ):
        value = binding[field]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise InquiryError("artifact binding hash is invalid")
    if not isinstance(binding["raw_artifact_path"], str) or not binding["raw_artifact_path"]:
        raise InquiryError("raw artifact path is absent")
    for field in ("input_receipt_path", "artifact_registry_path"):
        if not isinstance(binding[field], str) or not binding[field]:
            raise InquiryError("artifact identity path is absent")
    if (binding["rendered_image_sha256"] is None) != (binding["rendered_image_path"] is None):
        raise InquiryError("rendered artifact binding is partially populated")
    if binding["rendered_image_sha256"] is not None:
        value = binding["rendered_image_sha256"]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise InquiryError("rendered image hash is invalid")
    return deepcopy(dict(binding))


def source_pointer_from_resolved(
    value: Mapping[str, Any],
    *,
    adapter_id: str,
    artifact_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one exact observed text pointer with the canonical source schema."""

    required = {
        "kind", "source_id", "view_id", "first_observed_at", "text",
        "text_sha256", "view_text_sha256", "char_start", "char_end",
        "enclosing_context", "pointer_id",
    }
    if not required.issubset(value) or value["kind"] != "text":
        raise InquiryError("warrant is not a complete resolved text pointer")
    text = value["text"]
    context = value["enclosing_context"]
    start, end = value["char_start"], value["char_end"]
    if (
        not isinstance(text, str)
        or not isinstance(context, str)
        or not isinstance(start, int)
        or not isinstance(end, int)
        or context[start:end] != text
        or digest_text(text) != value["text_sha256"]
        or digest_text(context) != value["view_text_sha256"]
    ):
        raise InquiryError("resolved text pointer does not match its received view")
    _aware_timestamp(value["first_observed_at"], "source first_observed_at")
    source_ref = ClaimSourceRef.model_validate(
        {
            "source_id": value["source_id"],
            "source_sha256": value["view_text_sha256"],
            "source_version": f"{value['view_id']}@{value['first_observed_at']}",
            "locator_kind": "text_quote",
            "page": 1,
            "sanitized_excerpt": text,
            "text_start": start,
            "text_end": end,
            "field": None,
            "value": None,
            "span_sha256": value["text_sha256"],
            "adapter_id": adapter_id,
        }
    )
    _source_observed_at(source_ref)
    return {
        "pointer_id": value["pointer_id"],
        "ref": value.get("ref"),
        "view_id": value["view_id"],
        "source_ref": source_ref.model_dump(mode="json"),
        "identity_scope": "DERIVED_RENDERED_TEXT_VIEW",
        "original_artifact_binding": validate_artifact_binding(artifact_binding),
    }


def source_assertion_from_view(
    view: Mapping[str, Any],
    *,
    ref: str,
    adapter_id: str,
    proposed_role: str,
    artifact_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a provisional assertion from exact bytes, without accepting truth."""

    full_text = "".join(unit["text"] for unit in view["units"])
    start = 0
    match = None
    for unit in view["units"]:
        end = start + len(unit["text"])
        if unit["ref"] == ref:
            match = (start, end, unit["text"])
            break
        start = end
    if match is None:
        raise InquiryError(f"source unit {ref!r} is absent")
    start, end, text = match
    source_ref = ClaimSourceRef.model_validate(
        {
            "source_id": view["source_id"],
            "source_sha256": digest_text(full_text),
            "source_version": f"{view['view_id']}@{view['first_observed_at']}",
            "locator_kind": "text_quote",
            "page": 1,
            "sanitized_excerpt": text,
            "text_start": start,
            "text_end": end,
            "field": None,
            "value": None,
            "span_sha256": digest_text(text),
            "adapter_id": adapter_id,
        }
    )
    _source_observed_at(source_ref)
    material = {
        "contract": "casepath.provisional-source-assertion/1.0.0",
        "source_ref": source_ref.model_dump(mode="json"),
        "reported_text": text,
        "proposed_role": proposed_role,
        "role_status": "PROPOSED_UNVERIFIED",
        "truth_status": "SOURCE_REPORTED_NOT_WORLD_VERIFIED",
        "identity_scope": "DERIVED_RENDERED_TEXT_VIEW",
        "original_artifact_binding": validate_artifact_binding(artifact_binding),
    }
    return {
        **material,
        "assertion_id": "assertion." + digest_value(material),
        "assertion_sha256": digest_value(material),
        "status": "active",
    }


def validate_source_assertion(assertion: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "contract", "source_ref", "reported_text", "proposed_role",
        "role_status", "truth_status", "identity_scope",
        "original_artifact_binding", "assertion_id", "assertion_sha256", "status",
    }
    if set(assertion) != required or assertion.get("status") != "active":
        raise InquiryError("source assertion fields or initial status are invalid")
    source_ref = ClaimSourceRef.model_validate(assertion["source_ref"])
    if (
        assertion["reported_text"] != source_ref.sanitized_excerpt
        or assertion["identity_scope"] != "DERIVED_RENDERED_TEXT_VIEW"
        or assertion["role_status"] != "PROPOSED_UNVERIFIED"
        or assertion["truth_status"] != "SOURCE_REPORTED_NOT_WORLD_VERIFIED"
    ):
        raise InquiryError("source assertion overstates its text-view authority")
    _source_observed_at(source_ref)
    material = {
        key: value
        for key, value in assertion.items()
        if key not in {"assertion_id", "assertion_sha256", "status"}
    }
    expected = digest_value(material)
    if (
        assertion["assertion_sha256"] != expected
        or assertion["assertion_id"] != "assertion." + expected
    ):
        raise InquiryError("source assertion content identity mismatch")
    validate_artifact_binding(assertion["original_artifact_binding"])
    return deepcopy(dict(assertion))


class InquiryJournal:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS inquiry_events (
                stream_id TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                idempotency_key TEXT NOT NULL,
                event_type TEXT NOT NULL,
                request_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                previous_event_sha256 TEXT,
                event_sha256 TEXT NOT NULL,
                PRIMARY KEY (stream_id, sequence),
                UNIQUE (stream_id, idempotency_key),
                UNIQUE (event_sha256)
            )
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def append(
        self,
        *,
        stream_id: str,
        idempotency_key: str,
        event_type: str,
        payload: Mapping[str, Any],
        expected_parent_sha256: str | None = None,
        check_parent: bool = False,
    ) -> dict[str, Any]:
        request_sha = digest_value({"event_type": event_type, "payload": dict(payload)})
        if check_parent and expected_parent_sha256 is not None and (
            len(expected_parent_sha256) != 64
            or any(character not in "0123456789abcdef" for character in expected_parent_sha256)
        ):
            raise InquiryError("expected journal parent identity is invalid")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            existing = self.connection.execute(
                "SELECT * FROM inquiry_events WHERE stream_id=? AND idempotency_key=?",
                (stream_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["request_sha256"] != request_sha:
                    raise InquiryError("idempotency key reused with different input")
                result = {**self._row(existing), "replayed": True}
                self.connection.commit()
                return result
            last = self.connection.execute(
                "SELECT sequence,event_sha256 FROM inquiry_events WHERE stream_id=? ORDER BY sequence DESC LIMIT 1",
                (stream_id,),
            ).fetchone()
            sequence = 1 if last is None else int(last["sequence"]) + 1
            previous = None if last is None else str(last["event_sha256"])
            if check_parent and previous != expected_parent_sha256:
                raise InquiryConflictError("inquiry stream changed before append")
            event_material = {
                "contract": "casepath.provisional-inquiry-event/1.0.0",
                "stream_id": stream_id,
                "sequence": sequence,
                "idempotency_key": idempotency_key,
                "event_type": event_type,
                "request_sha256": request_sha,
                "payload": dict(payload),
                "previous_event_sha256": previous,
            }
            event_sha = digest_value(event_material)
            self.connection.execute(
                "INSERT INTO inquiry_events VALUES (?,?,?,?,?,?,?,?)",
                (
                    stream_id, sequence, idempotency_key, event_type,
                    request_sha, _json(dict(payload)), previous, event_sha,
                ),
            )
            row = self.connection.execute(
                "SELECT * FROM inquiry_events WHERE stream_id=? AND sequence=?",
                (stream_id, sequence),
            ).fetchone()
            assert row is not None
            result = {**self._row(row), "replayed": False}
            self.connection.commit()
            return result
        except Exception:
            self.connection.rollback()
            raise

    def event(self, stream_id: str, idempotency_key: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM inquiry_events WHERE stream_id=? AND idempotency_key=?",
            (stream_id, idempotency_key),
        ).fetchone()
        return None if row is None else self._row(row)

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "contract": "casepath.provisional-inquiry-event/1.0.0",
            "stream_id": row["stream_id"],
            "sequence": row["sequence"],
            "idempotency_key": row["idempotency_key"],
            "event_type": row["event_type"],
            "request_sha256": row["request_sha256"],
            "payload": json.loads(row["payload_json"]),
            "previous_event_sha256": row["previous_event_sha256"],
            "event_sha256": row["event_sha256"],
        }

    def events(self, stream_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM inquiry_events WHERE stream_id=? ORDER BY sequence",
            (stream_id,),
        ).fetchall()
        result = [self._row(row) for row in rows]
        previous = None
        for index, event in enumerate(result, 1):
            material = {key: value for key, value in event.items() if key != "event_sha256"}
            if (
                event["sequence"] != index
                or event["previous_event_sha256"] != previous
                or digest_value(material) != event["event_sha256"]
            ):
                raise InquiryError("inquiry journal hash chain is invalid")
            previous = event["event_sha256"]
        return result


class InquiryService:
    CHANNELS = {"internal_review", "external_evidence_request"}

    def __init__(
        self,
        journal: InquiryJournal,
        *,
        capabilities: Mapping[str, Mapping[str, Any]],
        source_adapter_id: str,
    ) -> None:
        self.journal = journal
        self.capabilities = deepcopy(dict(capabilities))
        self.source_adapter_id = source_adapter_id

    def _exact_replay(
        self,
        stream_id: str,
        idempotency_key: str,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        existing = self.journal.event(stream_id, idempotency_key)
        if existing is None:
            return None
        request_sha = digest_value({"event_type": event_type, "payload": dict(payload)})
        if existing["event_type"] != event_type or existing["request_sha256"] != request_sha:
            raise InquiryError("idempotency key reused with different input")
        return {**existing, "replayed": True}

    def state(self, stream_id: str) -> dict[str, Any]:
        assertions: dict[str, dict[str, Any]] = {}
        inquiries: dict[str, dict[str, Any]] = {}
        requests: dict[str, dict[str, Any]] = {}
        responses: dict[str, dict[str, Any]] = {}
        corrections: list[dict[str, Any]] = []
        events = self.journal.events(stream_id)
        for event in events:
            payload = event["payload"]
            if event["event_type"] == "SOURCE_ASSERTIONS_REGISTERED":
                for assertion in payload["assertions"]:
                    assertions[assertion["assertion_id"]] = deepcopy(assertion)
            elif event["event_type"] == "INQUIRY_ADMITTED":
                inquiries[payload["inquiry_id"]] = deepcopy(payload)
            elif event["event_type"] == "REQUEST_ISSUED":
                requests[payload["request_id"]] = deepcopy(payload)
            elif event["event_type"] == "RESPONSE_RECORDED":
                responses[payload["response_id"]] = deepcopy(payload)
                inquiry = inquiries[payload["inquiry_id"]]
                inquiry["lifecycle_status"] = "response_observed_unassessed"
                inquiry["response_ids"] = [
                    *inquiry.get("response_ids", []), payload["response_id"]
                ]
                for assertion in payload["source_assertions"]:
                    assertions[assertion["assertion_id"]] = deepcopy(assertion)
            elif event["event_type"] == "SOURCE_ASSERTION_CORRECTED":
                assertions = self._prospective_correction(assertions, payload)
                corrections.append(deepcopy(payload))
        material = {
            "contract": "casepath.provisional-inquiry-state/1.0.0",
            "stream_id": stream_id,
            "revision": len(events),
            "last_event_sha256": events[-1]["event_sha256"] if events else None,
            "inquiries": inquiries,
            "requests": requests,
            "responses": responses,
            "source_assertions": assertions,
            "corrections": corrections,
            "canonical_facts": {},
            "canonical_readiness": None,
        }
        return {**material, "state_sha256": digest_value(material)}

    @staticmethod
    def _prospective_correction(
        assertions: Mapping[str, Mapping[str, Any]],
        payload: Mapping[str, Any],
    ) -> dict[str, dict[str, Any]]:
        result = deepcopy(dict(assertions))
        target_id = payload["target_assertion_id"]
        if target_id not in result or result[target_id]["status"] != "active":
            raise InquiryError("correction target is not one active source assertion")
        new_assertions = [payload["correction_assertion"], *payload["neighbor_assertions"]]
        validated = [validate_source_assertion(value) for value in new_assertions]
        new_ids = [value["assertion_id"] for value in validated]
        if len(new_ids) != len(set(new_ids)) or any(value in result for value in new_ids):
            raise InquiryError("correction assertion identity collides with observed state")
        target = deepcopy(result[target_id])
        target["status"] = "superseded_by_source_correction"
        target["superseded_by_assertion_id"] = validated[0]["assertion_id"]
        result[target_id] = target
        for assertion in validated:
            result[assertion["assertion_id"]] = assertion
        return result

    def register_source_assertions(
        self,
        *,
        stream_id: str,
        assertions: list[dict[str, Any]],
        observed_at: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        assertions = [validate_source_assertion(value) for value in assertions]
        observed = _aware_timestamp(observed_at, "observed_at")
        if any(
            _source_observed_at(ClaimSourceRef.model_validate(value["source_ref"]))
            > observed
            for value in assertions
        ):
            raise InquiryError("source assertion was not observable at registration")
        payload = {"assertions": assertions, "observed_at": observed_at}
        replay = self._exact_replay(
            stream_id, idempotency_key, "SOURCE_ASSERTIONS_REGISTERED", payload
        )
        if replay is not None:
            return replay
        state = self.state(stream_id)
        replay = self._exact_replay(
            stream_id, idempotency_key, "SOURCE_ASSERTIONS_REGISTERED", payload
        )
        if replay is not None:
            return replay
        _require_monotonic_time(self.journal.events(stream_id), observed_at, "observed_at")
        existing_ids = set(state["source_assertions"])
        new_ids = [value["assertion_id"] for value in assertions]
        if len(new_ids) != len(set(new_ids)) or any(value in existing_ids for value in new_ids):
            raise InquiryError("source assertion identity collides with observed state")
        return self.journal.append(
            stream_id=stream_id,
            idempotency_key=idempotency_key,
            event_type="SOURCE_ASSERTIONS_REGISTERED",
            payload=payload,
            expected_parent_sha256=state["last_event_sha256"],
            check_parent=True,
        )

    def admit_inquiry(
        self,
        *,
        stream_id: str,
        reader_proposal: Mapping[str, Any],
        channel_proposal: Mapping[str, Any],
        observed_at: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        description = reader_proposal.get("description")
        raw_warrants = reader_proposal.get("warrants")
        warrant_bindings = reader_proposal.get("warrant_artifact_bindings", {})
        if not isinstance(description, str) or not description or not isinstance(raw_warrants, list) or not raw_warrants:
            raise InquiryError("reader proposal lacks a description or warrants")
        warrants = [
            source_pointer_from_resolved(
                value,
                adapter_id=self.source_adapter_id,
                artifact_binding=warrant_bindings.get(
                    f"{value['source_id']}::{value['view_id']}"
                ),
            )
            for value in raw_warrants
        ]
        admitted = _aware_timestamp(observed_at, "admitted_at")
        if any(
            _source_observed_at(ClaimSourceRef.model_validate(value["source_ref"]))
            > admitted
            for value in warrants
        ):
            raise InquiryError("inquiry warrant was not observable at admission")
        channel = channel_proposal.get("channel")
        if channel not in self.CHANNELS:
            raise InquiryError("channel proposal is outside the closed vocabulary")
        capability = self.capabilities.get(str(channel))
        if not isinstance(capability, Mapping) or not capability.get("capability_id"):
            raise InquiryError("proposed channel has no configured capability")
        proposal_material = {
            "description": description,
            "warrants": warrants,
            "reader_output_sha256": reader_proposal.get("reader_output_sha256"),
            "reader_proposal_sha256": reader_proposal.get("reader_proposal_sha256"),
        }
        proposal_sha = digest_value(proposal_material)
        inquiry_identity = {
            "contract": "casepath.provisional-inquiry-identity/1.0.0",
            "stream_id": stream_id,
            "description": description,
            "warrant_pointer_ids": [value["pointer_id"] for value in warrants],
        }
        inquiry_id = "inquiry." + digest_value(inquiry_identity)
        payload = {
            "inquiry_id": inquiry_id,
            "description": description,
            "proposal_sha256": proposal_sha,
            "reader_provenance": proposal_material,
            "warrants": warrants,
            "channel_proposal": dict(channel_proposal),
            "admitted_channel": channel,
            "capability": dict(capability),
            "lifecycle_status": "admitted_unresolved",
            "source_role_status": "PROPOSED_UNVERIFIED",
            "world_fact": None,
            "readiness": None,
            "admitted_at": observed_at,
        }
        replay = self._exact_replay(
            stream_id, idempotency_key, "INQUIRY_ADMITTED", payload
        )
        if replay is not None:
            return replay
        state = self.state(stream_id)
        replay = self._exact_replay(
            stream_id, idempotency_key, "INQUIRY_ADMITTED", payload
        )
        if replay is not None:
            return replay
        if inquiry_id in state["inquiries"]:
            raise InquiryError("stable inquiry identity is already admitted")
        _require_monotonic_time(self.journal.events(stream_id), observed_at, "admitted_at")
        return self.journal.append(
            stream_id=stream_id,
            idempotency_key=idempotency_key,
            event_type="INQUIRY_ADMITTED",
            payload=payload,
            expected_parent_sha256=state["last_event_sha256"],
            check_parent=True,
        )

    def issue_request(
        self,
        *,
        stream_id: str,
        inquiry_id: str,
        request_packet: Mapping[str, Any],
        recorded_dispatch_provenance: Mapping[str, Any],
        issued_at: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        issued = _aware_timestamp(issued_at, "issued_at")
        state = self.state(stream_id)
        inquiry = state["inquiries"].get(inquiry_id)
        if inquiry is None or inquiry["admitted_channel"] != "external_evidence_request":
            raise InquiryError("inquiry is not admitted to an external request capability")
        if request_packet.get("description") != inquiry["description"]:
            raise InquiryError("request meaning changed after inquiry admission")
        packet_warrants = request_packet.get("all_warrants")
        if not isinstance(packet_warrants, list) or not packet_warrants:
            raise InquiryError("request packet lacks complete warrants")
        pointer_ids = [
            source_pointer_from_resolved(value, adapter_id=self.source_adapter_id)["pointer_id"]
            for value in packet_warrants
        ]
        if pointer_ids != [value["pointer_id"] for value in inquiry["warrants"]]:
            raise InquiryError("request warrants differ from admitted inquiry")
        packet = deepcopy(dict(request_packet))
        packet.pop("need_id", None)
        packet.pop("model_index", None)
        packet_sha = digest_value(packet)
        request_id = "request." + digest_value(
            {
                "inquiry_id": inquiry_id,
                "capability_id": inquiry["capability"]["capability_id"],
                "request_packet_sha256": packet_sha,
            }
        )
        payload = {
            "request_id": request_id,
            "inquiry_id": inquiry_id,
            "request_packet": packet,
            "request_packet_sha256": packet_sha,
            "capability": inquiry["capability"],
            "recorded_dispatch_provenance": dict(recorded_dispatch_provenance),
            "delivery_status": "RECORDED_RESEARCH_REPLAY_ONLY",
            "external_delivery_receipt": None,
            "issued_at": issued_at,
            "world_fact": None,
            "readiness": None,
        }
        replay = self._exact_replay(
            stream_id, idempotency_key, "REQUEST_ISSUED", payload
        )
        if replay is not None:
            return replay
        if request_id in state["requests"]:
            raise InquiryError("stable request identity is already issued")
        if issued < _aware_timestamp(inquiry["admitted_at"], "admitted_at"):
            raise InquiryError("issued_at precedes inquiry admission")
        _require_monotonic_time(self.journal.events(stream_id), issued_at, "issued_at")
        return self.journal.append(
            stream_id=stream_id,
            idempotency_key=idempotency_key,
            event_type="REQUEST_ISSUED",
            payload=payload,
            expected_parent_sha256=state["last_event_sha256"],
            check_parent=True,
        )

    def record_response(
        self,
        *,
        stream_id: str,
        inquiry_id: str,
        request_id: str,
        source_assertions: list[dict[str, Any]],
        recorded_arrival_provenance: Mapping[str, Any],
        reader_update_sha256: str,
        observed_at: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        source_assertions = [validate_source_assertion(value) for value in source_assertions]
        observed = _aware_timestamp(observed_at, "observed_at")
        if any(
            _source_observed_at(ClaimSourceRef.model_validate(value["source_ref"]))
            > observed
            for value in source_assertions
        ):
            raise InquiryError("response assertion was not observable at response time")
        state = self.state(stream_id)
        request = state["requests"].get(request_id)
        if request is None or request["inquiry_id"] != inquiry_id:
            raise InquiryError("response is not tied to the issued inquiry request")
        response_id = "response." + digest_value(
            {
                "request_id": request_id,
                "arrival_provenance": dict(recorded_arrival_provenance),
                "assertion_ids": [value["assertion_id"] for value in source_assertions],
            }
        )
        payload = {
            "response_id": response_id,
            "inquiry_id": inquiry_id,
            "request_id": request_id,
            "request_event_sha256": next(
                event["event_sha256"]
                for event in self.journal.events(stream_id)
                if event["event_type"] == "REQUEST_ISSUED"
                and event["payload"]["request_id"] == request_id
            ),
            "source_assertions": source_assertions,
            "recorded_arrival_provenance": dict(recorded_arrival_provenance),
            "reader_update_sha256": reader_update_sha256,
            "semantic_assessment": None,
            "canonical_observation": None,
            "world_fact": None,
            "readiness": None,
            "observed_at": observed_at,
        }
        replay = self._exact_replay(
            stream_id, idempotency_key, "RESPONSE_RECORDED", payload
        )
        if replay is not None:
            return replay
        if response_id in state["responses"]:
            raise InquiryError("stable response identity is already recorded")
        if observed < _aware_timestamp(request["issued_at"], "issued_at"):
            raise InquiryError("response observed_at precedes its request")
        _require_monotonic_time(self.journal.events(stream_id), observed_at, "observed_at")
        existing_ids = set(state["source_assertions"])
        new_ids = [value["assertion_id"] for value in source_assertions]
        if len(new_ids) != len(set(new_ids)) or any(value in existing_ids for value in new_ids):
            raise InquiryError("response assertion identity collides with observed state")
        return self.journal.append(
            stream_id=stream_id,
            idempotency_key=idempotency_key,
            event_type="RESPONSE_RECORDED",
            payload=payload,
            expected_parent_sha256=state["last_event_sha256"],
            check_parent=True,
        )

    def apply_source_correction(
        self,
        *,
        stream_id: str,
        target_assertion_id: str,
        correction_assertion: dict[str, Any],
        neighbor_assertions: list[dict[str, Any]],
        recorded_arrival_provenance: Mapping[str, Any],
        observed_at: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        correction_assertion = validate_source_assertion(correction_assertion)
        neighbor_assertions = [validate_source_assertion(value) for value in neighbor_assertions]
        observed = _aware_timestamp(observed_at, "observed_at")
        if any(
            _source_observed_at(ClaimSourceRef.model_validate(value["source_ref"]))
            > observed
            for value in [correction_assertion, *neighbor_assertions]
        ):
            raise InquiryError("correction assertion was not observable at correction time")
        def correction_replay() -> dict[str, Any] | None:
            existing = self.journal.event(stream_id, idempotency_key)
            if existing is None:
                return None
            payload = existing["payload"]
            exact_replay = (
                existing["event_type"] == "SOURCE_ASSERTION_CORRECTED"
                and payload["target_assertion_id"] == target_assertion_id
                and payload["correction_assertion"] == correction_assertion
                and payload["neighbor_assertions"] == neighbor_assertions
                and payload["recorded_arrival_provenance"]
                == dict(recorded_arrival_provenance)
                and payload["observed_at"] == observed_at
            )
            if not exact_replay:
                raise InquiryError("idempotency key reused with different correction input")
            return {**existing, "replayed": True}

        replay = correction_replay()
        if replay is not None:
            return replay
        before = self.state(stream_id)
        replay = correction_replay()
        if replay is not None:
            return replay
        _require_monotonic_time(self.journal.events(stream_id), observed_at, "observed_at")
        assertions = before["source_assertions"]
        if target_assertion_id not in assertions or assertions[target_assertion_id]["status"] != "active":
            raise InquiryError("correction target is not one active source assertion")
        preserved_assertion_ids = sorted(
            value for value in assertions if value != target_assertion_id
        )
        before_hashes = {key: digest_value(value) for key, value in assertions.items()}
        payload = {
            "target_assertion_id": target_assertion_id,
            "target_before_sha256": before_hashes[target_assertion_id],
            "correction_assertion": correction_assertion,
            "neighbor_assertions": neighbor_assertions,
            "preserved_assertion_ids": preserved_assertion_ids,
            "preserved_before_sha256": {
                key: before_hashes[key] for key in preserved_assertion_ids
            },
            "effect_scope": "ONE_SOURCE_ASSERTION_ONLY",
            "canonical_correction": None,
            "world_fact_effect": None,
            "readiness_effect": None,
            "recorded_arrival_provenance": dict(recorded_arrival_provenance),
            "observed_at": observed_at,
        }
        prospective = self._prospective_correction(assertions, payload)
        if any(
            digest_value(prospective[key]) != before_hashes[key]
            for key in preserved_assertion_ids
        ):
            raise InquiryError("prospective correction changes a non-target assertion")
        event = self.journal.append(
            stream_id=stream_id,
            idempotency_key=idempotency_key,
            event_type="SOURCE_ASSERTION_CORRECTED",
            payload=payload,
            expected_parent_sha256=before["last_event_sha256"],
            check_parent=True,
        )
        return event
