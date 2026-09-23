from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .claim_loop import (
    ClaimLoopError,
    CorrectionToolAdapter,
    CorrectionToolResult,
    EvidenceArtifactInterpreter,
    playbook_template_from_accepted_v1,
    project_claim_loop_artifacts_v1,
    reduce_claim_loop_event,
)
from .claim_loop_contracts import (
    AcquisitionReceiptV1,
    ClaimLoopCommandReceipt,
    ClaimLoopEvent,
    ClaimLoopState,
    CorrectionArtifactReceipt,
    CorrectionReuseReceipt,
    ProjectionLedgerEntry,
    ScopedCorrection,
    ToolArtifactReceipt,
    claim_loop_internal_event_key_v1,
    load_claim_loop_event_v1,
)
from .foundation.common import canonical_json_bytes, digest_text, digest_value
from .insurance_protocol_v1 import (
    ActionReceiptStatus,
    InsuranceProtocolRecordSetV1,
)
from .insurance_protocol_v2 import (
    InsuranceThinWaistRecordSetV2,
    build_thin_waist_replan_intent_v2,
)
from .projections import DECISION_OPTIONS


class ClaimLoopStoreError(RuntimeError):
    pass


_INITIALIZE_LOCK = threading.Lock()


def _json(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _client_request_identity(command: Mapping[str, Any]) -> tuple[str, Any]:
    request_type = command.get("client_request_type", "advance")
    request_sha256 = command.get(
        "client_request_sha256", command.get("advance_request_sha256")
    )
    return request_type, request_sha256


def _protocol_record_set(
    command: Mapping[str, Any],
) -> InsuranceProtocolRecordSetV1 | None:
    value = command.get("insurance_protocol_v1")
    if value is None:
        return None
    try:
        records = InsuranceProtocolRecordSetV1.model_validate_json(
            canonical_json_bytes(value)
        )
    except (TypeError, ValueError) as exc:
        raise ClaimLoopStoreError("insurance protocol record set is invalid") from exc
    if command.get("protocol_record_set_sha256") != records.record_set_sha256:
        raise ClaimLoopStoreError("insurance protocol record-set identity diverged")
    return records


def _thin_waist_record_set(
    command: Mapping[str, Any],
) -> InsuranceThinWaistRecordSetV2 | None:
    value = command.get("insurance_thin_waist_v2")
    if value is None:
        return None
    try:
        records = InsuranceThinWaistRecordSetV2.model_validate_json(
            canonical_json_bytes(value)
        )
    except (TypeError, ValueError) as exc:
        raise ClaimLoopStoreError("insurance thin-waist record set is invalid") from exc
    if command.get("thin_waist_record_set_sha256") != records.record_set_sha256:
        raise ClaimLoopStoreError("insurance thin-waist record-set identity diverged")
    return records


def _same_protocol_authority(
    left: InsuranceProtocolRecordSetV1,
    right: InsuranceProtocolRecordSetV1,
) -> bool:
    return (
        left.proposal == right.proposal
        and left.staged_artifact == right.staged_artifact
        and left.decision == right.decision
        and left.intent == right.intent
    )


def _protocol_changes_only(
    left: InsuranceProtocolRecordSetV1,
    right: InsuranceProtocolRecordSetV1,
    *allowed_fields: str,
) -> bool:
    """Prove that an immutable record-set prefix gained only named records."""

    excluded = {"record_set_sha256", *allowed_fields}
    return left.model_dump(mode="json", exclude=excluded) == right.model_dump(
        mode="json", exclude=excluded
    )


def _validate_protocol_epistemic_authority(
    connection: sqlite3.Connection,
    *,
    current: ClaimLoopState,
    records: InsuranceProtocolRecordSetV1,
    require: str,
) -> None:
    """Recompute each epistemic prefix from the registered artifact authority."""

    receipt = records.action_receipt
    if (
        receipt is None
        or receipt.status is not ActionReceiptStatus.COMMITTED
        or current.active_dispatch_sha256 is None
    ):
        raise ClaimLoopStoreError(
            "protocol epistemic records lack a committed active action"
        )
    row = connection.execute(
        """SELECT artifact_json FROM claim_loop_tool_artifacts
        WHERE session_id=? AND loop_id=? AND dispatch_sha256=?""",
        (current.session_id, current.loop_id, current.active_dispatch_sha256),
    ).fetchone()
    if row is None:
        raise ClaimLoopStoreError(
            "protocol epistemic records lack registered artifact authority"
        )
    try:
        artifact = ToolArtifactReceipt.model_validate(json.loads(row["artifact_json"]))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ClaimLoopStoreError(
            "protocol registered artifact authority is invalid"
        ) from exc
    acquisition = artifact.acquisition_receipt
    source = records.source_observation
    if (
        source is None
        or source.action_receipt_sha256 != receipt.receipt_sha256
        or source.session_id != artifact.session_id
        or source.loop_id != artifact.loop_id
        or source.record_version != artifact.artifact_source_version
        or source.content_sha256 != acquisition.sanitized_content_sha256
        or source.exact_text_sha256 != acquisition.sanitized_content_sha256
        or source.text_start != 0
        or source.text_end != len(acquisition.sanitized_content or "")
        or source.page != artifact.artifact_page_count
        or source.artifact_uri != receipt.artifact_uri
        or source.observed_at != receipt.committed_at
        or source.authority != "local_artifact_registry_receipt"
    ):
        raise ClaimLoopStoreError(
            "protocol source observation differs from registered artifact"
        )
    if require == "source":
        return
    assertion = records.normalized_assertion
    if (
        assertion is None
        or assertion.source_observation_sha256 != source.observation_sha256
        or assertion.fact_id != artifact.observation.fact_id
        or assertion.evidence_item_id != artifact.observation.evidence_item_id
        or assertion.fact_state != artifact.observation.fact_state
        or assertion.normalized_value != artifact.observation.normalized_value
        or assertion.extraction_method != artifact.interpretation.implementation
        or assertion.extraction_method_source_sha256
        != artifact.interpretation.implementation_source_sha256
        or assertion.claim_observation_sha256 != artifact.observation.observation_sha256
        or assertion.claim_observation != artifact.observation
        or assertion.canonical_interpretation != artifact.interpretation
    ):
        raise ClaimLoopStoreError(
            "protocol normalized assertion differs from registered artifact"
        )
    if require == "assertion":
        return
    interpretation = records.interpretation
    expected_status = (
        "supported"
        if artifact.observation.fact_state == "known"
        and artifact.observation.evidence_status == "provided_sufficient"
        else (
            "disputed"
            if artifact.observation.fact_state == "conflicting"
            else "insufficient"
        )
    )
    if (
        interpretation is None
        or interpretation.assertion_sha256 != assertion.assertion_sha256
        or interpretation.canonical_interpretation_receipt_sha256
        != artifact.interpretation.receipt_sha256
        or interpretation.prior_fact_sha256 != artifact.interpretation.prior_fact_sha256
        or interpretation.assertion_catalog_sha256
        != artifact.interpretation.assertion_catalog_sha256
        or interpretation.selected_assertion_id
        != artifact.interpretation.selected_assertion_id
        or interpretation.playbook_template_sha256
        != current.accepted_artifacts.get("playbook_template", {}).get(
            "template_sha256"
        )
        or interpretation.policy_version
        != "casepath.claim-loop-interpretation-policy/1.0.0"
        or interpretation.status != expected_status
    ):
        raise ClaimLoopStoreError(
            "protocol interpretation differs from registered artifact"
        )


class ClaimLoopStore:
    """Hash-chained loop journal with a derived, repairable SQLite checkpoint."""

    def __init__(
        self,
        path: str | Path,
        *,
        artifact_interpreter: EvidenceArtifactInterpreter | None = None,
        adapter_identities: Mapping[str, tuple[str, str, str]] | None = None,
        correction_adapters: Mapping[str, CorrectionToolAdapter] | None = None,
        protocol_registry: Any | None = None,
    ) -> None:
        self.path = Path(path).resolve()
        self.artifact_interpreter = artifact_interpreter
        self.adapter_identities = dict(adapter_identities or {})
        self.correction_adapters = dict(correction_adapters or {})
        self.protocol_registry = protocol_registry
        self._replay_cache_lock = threading.RLock()
        self._replay_cache: dict[
            tuple[str, str], tuple[tuple[bytes, ...], bytes]
        ] = {}
        self._data_version_lock = threading.RLock()
        self._data_version_connection: sqlite3.Connection | None = None
        self._data_version_file_identity: tuple[int, int] | None = None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def journal_version_token(self) -> tuple[int, int, int, int, int]:
        """Return a process-stable token that changes on any SQLite commit.

        SQLite's ``data_version`` is meaningful across repeated reads on the
        same connection, so this method keeps one query-only connection behind
        a lock.  File identity/size/mtime additionally detect path replacement.
        The token is only a cache invalidator; journal bytes remain authority.
        """

        stat_value = self.path.stat()
        identity = (stat_value.st_dev, stat_value.st_ino)
        with self._data_version_lock:
            if (
                self._data_version_connection is None
                or self._data_version_file_identity != identity
            ):
                if self._data_version_connection is not None:
                    self._data_version_connection.close()
                connection = sqlite3.connect(
                    self.path,
                    timeout=30,
                    isolation_level=None,
                    check_same_thread=False,
                )
                connection.execute("PRAGMA query_only=ON")
                self._data_version_connection = connection
                self._data_version_file_identity = identity
            data_version = self._data_version_connection.execute(
                "PRAGMA data_version"
            ).fetchone()[0]
        return (
            stat_value.st_dev,
            stat_value.st_ino,
            stat_value.st_size,
            stat_value.st_mtime_ns,
            int(data_version),
        )

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with _INITIALIZE_LOCK, self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS claim_loop_events (
                    session_id TEXT NOT NULL,
                    loop_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    command_sha256 TEXT NOT NULL,
                    event_sha256 TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, loop_id, sequence),
                    UNIQUE(session_id, loop_id, idempotency_key),
                    UNIQUE(session_id, loop_id, event_sha256)
                );
                CREATE TABLE IF NOT EXISTS claim_loop_checkpoints (
                    session_id TEXT NOT NULL,
                    loop_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    last_event_sha256 TEXT NOT NULL,
                    state_sha256 TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, loop_id)
                );
                CREATE TABLE IF NOT EXISTS claim_loop_corrections (
                    correction_id TEXT PRIMARY KEY,
                    correction_sha256 TEXT NOT NULL UNIQUE,
                    source_session_id TEXT NOT NULL,
                    source_loop_id TEXT NOT NULL,
                    correction_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS claim_loop_correction_artifacts (
                    receipt_sha256 TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    loop_id TEXT NOT NULL,
                    parent_state_sha256 TEXT NOT NULL,
                    artifact_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS claim_loop_tool_artifacts (
                    receipt_sha256 TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    loop_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    dispatch_sha256 TEXT NOT NULL,
                    artifact_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, loop_id, dispatch_sha256)
                );
                CREATE TABLE IF NOT EXISTS claim_loop_acquisitions (
                    receipt_sha256 TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    loop_id TEXT NOT NULL,
                    action_id TEXT NOT NULL,
                    dispatch_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    acquisition_json TEXT NOT NULL,
                    raw_payload BLOB,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, loop_id, dispatch_sha256)
                );
                CREATE TABLE IF NOT EXISTS claim_loop_client_requests (
                    session_id TEXT NOT NULL,
                    loop_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    request_type TEXT NOT NULL,
                    request_sha256 TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'RESERVED',
                    result_event_idempotency_key TEXT,
                    result_event_sha256 TEXT,
                    result_revision INTEGER,
                    result_state_sha256 TEXT,
                    response_sha256 TEXT,
                    response_json TEXT,
                    completed_at TEXT,
                    dispatch_started_at TEXT,
                    dispatch_expires_at TEXT,
                    dispatch_generation INTEGER NOT NULL DEFAULT 0,
                    reserved_event_idempotency_key TEXT,
                    reserved_event_sha256 TEXT,
                    reserved_revision INTEGER,
                    reserved_state_sha256 TEXT,
                    PRIMARY KEY(session_id, loop_id, idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS claim_loop_event_tail
                    ON claim_loop_events(session_id, loop_id, sequence);
                """
            )
            migrations = {
                "status": "TEXT NOT NULL DEFAULT 'RESERVED'",
                "result_event_idempotency_key": "TEXT",
                "result_event_sha256": "TEXT",
                "result_revision": "INTEGER",
                "result_state_sha256": "TEXT",
                "response_sha256": "TEXT",
                "response_json": "TEXT",
                "completed_at": "TEXT",
                "dispatch_started_at": "TEXT",
                "dispatch_expires_at": "TEXT",
                "dispatch_generation": "INTEGER NOT NULL DEFAULT 0",
                "reserved_event_idempotency_key": "TEXT",
                "reserved_event_sha256": "TEXT",
                "reserved_revision": "INTEGER",
                "reserved_state_sha256": "TEXT",
            }
            connection.execute("BEGIN IMMEDIATE")
            try:
                columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(claim_loop_client_requests)"
                    )
                }
                for name, declaration in migrations.items():
                    if name not in columns:
                        connection.execute(
                            "ALTER TABLE claim_loop_client_requests "
                            f"ADD COLUMN {name} {declaration}"
                        )
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def bind_client_request(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_type: str,
        request: Mapping[str, Any],
        timestamp: str,
    ) -> str:
        """Reserve one caller key for one exact route/body across the loop."""

        request_value = deepcopy_json(request)
        request_sha256 = digest_value(request_value)
        request_json = _json(request_value)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT request_type,request_sha256,request_json
                FROM claim_loop_client_requests
                WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                (session_id, loop_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if (
                    existing["request_type"] != request_type
                    or existing["request_sha256"] != request_sha256
                    or existing["request_json"] != request_json
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "idempotency key was reused for a different client request"
                    )
                connection.commit()
                return request_sha256
            rows = self._event_rows(connection, session_id, loop_id)
            reserved_state = (
                self._replay_rows(rows, session_id=session_id, loop_id=loop_id)
                if rows
                else None
            )
            reserved_event = rows[-1] if rows else None
            connection.execute(
                """INSERT INTO claim_loop_client_requests
                (session_id,loop_id,idempotency_key,request_type,request_sha256,
                 request_json,created_at,reserved_event_idempotency_key,
                 reserved_event_sha256,reserved_revision,reserved_state_sha256)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id,
                    loop_id,
                    idempotency_key,
                    request_type,
                    request_sha256,
                    request_json,
                    timestamp,
                    (
                        reserved_event["idempotency_key"]
                        if reserved_event is not None
                        else None
                    ),
                    (
                        reserved_event["event_sha256"]
                        if reserved_event is not None
                        else None
                    ),
                    reserved_state.revision if reserved_state is not None else None,
                    (
                        reserved_state.state_sha256
                        if reserved_state is not None
                        else None
                    ),
                ),
            )
            connection.commit()
        return request_sha256

    def client_request(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_type: str,
        request_sha256: str,
    ) -> dict[str, Any]:
        """Load and fully validate one reserved or completed client request."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM claim_loop_client_requests
                WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                (session_id, loop_id, idempotency_key),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ClaimLoopStoreError("client request reservation is absent")
            if (
                row["request_type"] != request_type
                or row["request_sha256"] != request_sha256
                or digest_value(json.loads(row["request_json"])) != request_sha256
            ):
                connection.rollback()
                raise ClaimLoopStoreError("client request reservation diverged")
            status = row["status"]
            result: dict[str, Any] = {
                "status": status,
                "created_at": row["created_at"],
                "dispatch_started_at": row["dispatch_started_at"],
                "dispatch_expires_at": row["dispatch_expires_at"],
                "dispatch_generation": row["dispatch_generation"],
                "response": None,
                "failure": None,
                "reserved_state": None,
                "request": None,
            }
            try:
                request_value = json.loads(row["request_json"])
            except (TypeError, json.JSONDecodeError) as exc:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "client request reservation body is invalid"
                ) from exc
            if digest_value(request_value) != request_sha256:
                connection.rollback()
                raise ClaimLoopStoreError("client request reservation body diverged")
            result["request"] = request_value
            reserved_names = (
                "reserved_event_idempotency_key",
                "reserved_event_sha256",
                "reserved_revision",
                "reserved_state_sha256",
            )
            reserved_values = tuple(row[name] for name in reserved_names)
            if any(value is not None for value in reserved_values):
                if any(value is None for value in reserved_values):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "client request reservation snapshot is partial"
                    )
                rows = self._event_rows(connection, session_id, loop_id)
                revision = row["reserved_revision"]
                if (
                    not isinstance(revision, int)
                    or isinstance(revision, bool)
                    or revision < 1
                    or revision > len(rows)
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "client request reservation is not a journal prefix"
                    )
                event_row = rows[revision - 1]
                if (
                    event_row["idempotency_key"]
                    != row["reserved_event_idempotency_key"]
                    or event_row["event_sha256"] != row["reserved_event_sha256"]
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "client request reservation event binding diverged"
                    )
                reserved_state = self._replay_rows(
                    rows[:revision], session_id=session_id, loop_id=loop_id
                )
                if reserved_state.state_sha256 != row["reserved_state_sha256"]:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "client request reservation state binding diverged"
                    )
                result["reserved_state"] = reserved_state
            if status == "RESERVED":
                if any(
                    row[name] is not None
                    for name in (
                        "result_event_idempotency_key",
                        "result_event_sha256",
                        "result_revision",
                        "result_state_sha256",
                        "response_sha256",
                        "response_json",
                        "completed_at",
                    )
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "reserved client request has partial completion state"
                    )
            elif status in {"COMPLETED", "SUPERSEDED"}:
                if any(
                    row[name] is None
                    for name in (
                        "result_event_idempotency_key",
                        "result_event_sha256",
                        "result_revision",
                        "result_state_sha256",
                        "response_sha256",
                        "response_json",
                        "completed_at",
                    )
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "completed client request lacks its result binding"
                    )
                rows = self._event_rows(connection, session_id, loop_id)
                revision = row["result_revision"]
                if (
                    not isinstance(revision, int)
                    or isinstance(revision, bool)
                    or revision < 1
                    or revision > len(rows)
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "client result revision is not a journal prefix"
                    )
                event_row = rows[revision - 1]
                if (
                    event_row["event_sha256"] != row["result_event_sha256"]
                    or event_row["idempotency_key"]
                    != row["result_event_idempotency_key"]
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError("client result event binding diverged")
                state = self._replay_rows(
                    rows[:revision], session_id=session_id, loop_id=loop_id
                )
                if state.state_sha256 != row["result_state_sha256"]:
                    connection.rollback()
                    raise ClaimLoopStoreError("client result state binding diverged")
                try:
                    response = json.loads(row["response_json"])
                except (TypeError, json.JSONDecodeError) as exc:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "client result response is invalid"
                    ) from exc
                if (
                    digest_value(response) != row["response_sha256"]
                    or response.get("revision") != state.revision
                    or response.get("state_sha256") != state.state_sha256
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError("client result response binding diverged")
                if status == "COMPLETED":
                    result["response"] = response
                else:
                    if (
                        response.get("contract")
                        != "casepath.claim-loop-client-conflict/1.0.0"
                        or response.get("error_code") != "REQUEST_PREFIX_SUPERSEDED"
                        or not isinstance(response.get("detail"), str)
                        or response.get("failure_sha256")
                        != digest_value(
                            {
                                key: value
                                for key, value in response.items()
                                if key != "failure_sha256"
                            }
                        )
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "superseded client request response is invalid"
                        )
                    result["failure"] = response
            elif status == "ABANDONED":
                if any(
                    row[name] is not None
                    for name in (
                        "result_event_idempotency_key",
                        "result_event_sha256",
                        "result_revision",
                        "result_state_sha256",
                    )
                ) or any(
                    row[name] is None
                    for name in ("response_sha256", "response_json", "completed_at")
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "abandoned client request has an invalid result binding"
                    )
                try:
                    response = json.loads(row["response_json"])
                except (TypeError, json.JSONDecodeError) as exc:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "abandoned client response is invalid"
                    ) from exc
                if (
                    digest_value(response) != row["response_sha256"]
                    or response.get("contract")
                    != "casepath.claim-loop-client-conflict/1.0.0"
                    or response.get("error_code") != "REQUEST_ABANDONED"
                    or response.get("revision") != 0
                    or response.get("state_sha256") is not None
                    or response.get("failure_sha256")
                    != digest_value(
                        {
                            key: value
                            for key, value in response.items()
                            if key != "failure_sha256"
                        }
                    )
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "abandoned client request response is invalid"
                    )
                result["failure"] = response
            else:
                connection.rollback()
                raise ClaimLoopStoreError("client request status is invalid")
            connection.commit()
            return result

    def lookup_client_request(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_type: str,
        request: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Read an exact client binding without reserving a fresh request."""

        request_value = deepcopy_json(request)
        request_sha256 = digest_value(request_value)
        with self.connect() as connection:
            row = connection.execute(
                """SELECT request_type,request_sha256,request_json
                FROM claim_loop_client_requests
                WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                (session_id, loop_id, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        if (
            row["request_type"] != request_type
            or row["request_sha256"] != request_sha256
            or row["request_json"] != _json(request_value)
        ):
            raise ClaimLoopStoreError(
                "idempotency key was reused for a different client request"
            )
        return self.client_request(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            request_type=request_type,
            request_sha256=request_sha256,
        )

    def reserved_client_requests(
        self, *, limit: int = 128
    ) -> tuple[dict[str, Any], ...]:
        """List a bounded, deterministic batch of unfinished request identities."""

        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 1024
        ):
            raise ClaimLoopStoreError("reserved request scan limit is invalid")
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT session_id,loop_id,idempotency_key,request_type,
                request_sha256,created_at FROM claim_loop_client_requests
                WHERE status='RESERVED'
                ORDER BY created_at,session_id,loop_id,idempotency_key
                LIMIT ?""",
                (limit,),
            ).fetchall()
        return tuple(dict(row) for row in rows)

    def event_prefix_result(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
    ) -> tuple[ClaimLoopEvent, ClaimLoopState, ClaimLoopCommandReceipt] | None:
        """Read one validated immutable event prefix without repairing caches."""

        with self.connect() as connection:
            connection.execute("BEGIN")
            rows = self._event_rows(connection, session_id, loop_id)
            if not rows:
                connection.commit()
                return None
            self._replay_rows(rows, session_id=session_id, loop_id=loop_id)
            match_index = next(
                (
                    index
                    for index, row in enumerate(rows)
                    if row["idempotency_key"] == idempotency_key
                ),
                None,
            )
            if match_index is None:
                connection.commit()
                return None
            event = load_claim_loop_event_v1(
                json.loads(rows[match_index]["event_json"])
            )
            state = self._replay_rows(
                rows[: match_index + 1],
                session_id=session_id,
                loop_id=loop_id,
            )
            receipt = self._receipt(
                loop_id=loop_id,
                idempotency_key=idempotency_key,
                event_sha256=event.event_sha256,
                state=state,
            )
            connection.commit()
        return event, state, receipt

    def bind_client_dispatch(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_type: str,
        request_sha256: str,
        dispatch_idempotency_key: str,
        started_at: str,
        expires_at: str,
    ) -> tuple[str, str, int]:
        """CAS the first exact dispatch clock into the parent request."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM claim_loop_client_requests
                WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                (session_id, loop_id, idempotency_key),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ClaimLoopStoreError("client request reservation is absent")
            if (
                row["request_type"] != request_type
                or row["request_sha256"] != request_sha256
                or row["status"] != "RESERVED"
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "client dispatch reservation differs from its request"
                )
            if row["dispatch_started_at"] is not None:
                if row["dispatch_expires_at"] is None:
                    connection.rollback()
                    raise ClaimLoopStoreError("client dispatch reservation is partial")
                event = connection.execute(
                    """SELECT 1 FROM claim_loop_events
                    WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                    (session_id, loop_id, dispatch_idempotency_key),
                ).fetchone()
                try:
                    prior_expiry = datetime.fromisoformat(
                        row["dispatch_expires_at"].replace("Z", "+00:00")
                    )
                    proposed_start = datetime.fromisoformat(
                        started_at.replace("Z", "+00:00")
                    )
                except (AttributeError, ValueError) as exc:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "client dispatch reservation timestamp is invalid"
                    ) from exc
                if event is None and proposed_start >= prior_expiry:
                    generation = row["dispatch_generation"] + 1
                    updated = connection.execute(
                        """UPDATE claim_loop_client_requests
                        SET dispatch_started_at=?,dispatch_expires_at=?,
                            dispatch_generation=?
                        WHERE session_id=? AND loop_id=? AND idempotency_key=?
                            AND status='RESERVED'
                            AND dispatch_started_at=? AND dispatch_expires_at=?""",
                        (
                            started_at,
                            expires_at,
                            generation,
                            session_id,
                            loop_id,
                            idempotency_key,
                            row["dispatch_started_at"],
                            row["dispatch_expires_at"],
                        ),
                    ).rowcount
                    if updated != 1:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "expired client dispatch refresh CAS failed"
                        )
                    connection.commit()
                    return started_at, expires_at, generation
                connection.commit()
                return (
                    row["dispatch_started_at"],
                    row["dispatch_expires_at"],
                    row["dispatch_generation"],
                )
            if row["dispatch_expires_at"] is not None:
                connection.rollback()
                raise ClaimLoopStoreError("client dispatch reservation is partial")
            updated = connection.execute(
                """UPDATE claim_loop_client_requests
                SET dispatch_started_at=?,dispatch_expires_at=?,dispatch_generation=1
                WHERE session_id=? AND loop_id=? AND idempotency_key=?
                    AND status='RESERVED' AND dispatch_started_at IS NULL
                    AND dispatch_expires_at IS NULL""",
                (
                    started_at,
                    expires_at,
                    session_id,
                    loop_id,
                    idempotency_key,
                ),
            ).rowcount
            if updated != 1:
                connection.rollback()
                raise ClaimLoopStoreError("client dispatch reservation CAS failed")
            connection.commit()
        return started_at, expires_at, 1

    def complete_client_request(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_type: str,
        request_sha256: str,
        response: Mapping[str, Any],
        completed_at: str,
    ) -> dict[str, Any]:
        """CAS a request to one immutable, journal-prefix-bound response."""

        # Canonical round-tripping gives the initial response and every replay
        # the same insertion order at the HTTP serialization boundary.
        response_value = json.loads(_json(deepcopy_json(response)))
        response_sha256 = digest_value(response_value)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM claim_loop_client_requests
                WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                (session_id, loop_id, idempotency_key),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ClaimLoopStoreError("client request reservation is absent")
            if (
                row["request_type"] != request_type
                or row["request_sha256"] != request_sha256
                or digest_value(json.loads(row["request_json"])) != request_sha256
            ):
                connection.rollback()
                raise ClaimLoopStoreError("client request reservation diverged")
            if row["status"] == "COMPLETED":
                try:
                    existing_response = json.loads(row["response_json"])
                except (TypeError, json.JSONDecodeError) as exc:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "completed client response is invalid"
                    ) from exc
                if (
                    row["response_sha256"] != digest_value(existing_response)
                    or row["request_sha256"] != request_sha256
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "completed client result binding diverged"
                    )
                connection.commit()
                return existing_response
            if row["status"] != "RESERVED":
                connection.rollback()
                raise ClaimLoopStoreError("client request status is invalid")
            rows = self._event_rows(connection, session_id, loop_id)
            revision = response_value.get("revision")
            state_sha256 = response_value.get("state_sha256")
            if (
                not isinstance(revision, int)
                or isinstance(revision, bool)
                or revision < 1
                or revision > len(rows)
                or not isinstance(state_sha256, str)
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "client response state is not a journal prefix"
                )
            prefix = self._replay_rows(
                rows[:revision], session_id=session_id, loop_id=loop_id
            )
            event_row = rows[revision - 1]
            if prefix.state_sha256 != state_sha256 or prefix.revision != revision:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "client response does not bind its journal prefix"
                )
            updated = connection.execute(
                """UPDATE claim_loop_client_requests SET
                    status='COMPLETED',
                    result_event_idempotency_key=?,
                    result_event_sha256=?,
                    result_revision=?,
                    result_state_sha256=?,
                    response_sha256=?,
                    response_json=?,
                    completed_at=?
                WHERE session_id=? AND loop_id=? AND idempotency_key=?
                    AND status='RESERVED'""",
                (
                    event_row["idempotency_key"],
                    event_row["event_sha256"],
                    revision,
                    state_sha256,
                    response_sha256,
                    _json(response_value),
                    completed_at,
                    session_id,
                    loop_id,
                    idempotency_key,
                ),
            ).rowcount
            if updated != 1:
                connection.rollback()
                raise ClaimLoopStoreError("client request completion CAS failed")
            connection.commit()
        return response_value

    def supersede_client_request(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_type: str,
        request_sha256: str,
        detail: str,
        completed_at: str,
    ) -> dict[str, Any]:
        """Terminalize an abandoned mutation at its original journal prefix."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM claim_loop_client_requests
                WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                (session_id, loop_id, idempotency_key),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ClaimLoopStoreError("client request reservation is absent")
            if (
                row["request_type"] != request_type
                or row["request_sha256"] != request_sha256
            ):
                connection.rollback()
                raise ClaimLoopStoreError("client request reservation diverged")
            if row["status"] == "SUPERSEDED":
                try:
                    failure = json.loads(row["response_json"])
                except (TypeError, json.JSONDecodeError) as exc:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "superseded client response is invalid"
                    ) from exc
                connection.commit()
                return failure
            if row["status"] != "RESERVED":
                connection.rollback()
                raise ClaimLoopStoreError("only a reserved request can be superseded")
            reserved_revision = row["reserved_revision"]
            rows = self._event_rows(connection, session_id, loop_id)
            if (
                not isinstance(reserved_revision, int)
                or isinstance(reserved_revision, bool)
                or reserved_revision < 1
                or reserved_revision > len(rows)
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "client request reservation is not a journal prefix"
                )
            prefix = self._replay_rows(
                rows[:reserved_revision], session_id=session_id, loop_id=loop_id
            )
            event_row = rows[reserved_revision - 1]
            if (
                event_row["idempotency_key"] != row["reserved_event_idempotency_key"]
                or event_row["event_sha256"] != row["reserved_event_sha256"]
                or prefix.state_sha256 != row["reserved_state_sha256"]
            ):
                connection.rollback()
                raise ClaimLoopStoreError("client request reservation prefix diverged")
            child_keys: tuple[str, ...]
            if request_type == "advance":
                child_keys = tuple(
                    claim_loop_internal_event_key_v1(
                        session_id=session_id,
                        loop_id=loop_id,
                        client_idempotency_key=idempotency_key,
                        request_type=request_type,
                        request_sha256=request_sha256,
                        event_kind=kind,
                    )
                    for kind in ("select", "dispatch", "result")
                )
            elif request_type == "insurance_register":
                child_keys = tuple(
                    claim_loop_internal_event_key_v1(
                        session_id=session_id,
                        loop_id=loop_id,
                        client_idempotency_key=idempotency_key,
                        request_type=request_type,
                        request_sha256=request_sha256,
                        event_kind=kind,
                    )
                    for kind in (
                        "dispatch",
                        "execution-started",
                        "action-receipt",
                        "source-observation",
                        "normalized-assertion",
                        "interpretation",
                        "result",
                        "replan-receipt",
                        "dispatch-unknown",
                        "intent-cancelled",
                    )
                )
            elif request_type in {
                "select_action",
                "ingest_observation",
                "tool_unavailable",
                "apply_correction",
                "reuse_correction",
            }:
                child_keys = (idempotency_key,)
            else:
                child_keys = ()
            if child_keys:
                placeholders = ",".join("?" for _ in child_keys)
                child = connection.execute(
                    f"""SELECT 1 FROM claim_loop_events
                    WHERE session_id=? AND loop_id=?
                    AND idempotency_key IN ({placeholders}) LIMIT 1""",
                    (session_id, loop_id, *child_keys),
                ).fetchone()
                if child is not None:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "client request has a recoverable event lineage"
                    )
            failure_payload = {
                "contract": "casepath.claim-loop-client-conflict/1.0.0",
                "error_code": "REQUEST_PREFIX_SUPERSEDED",
                "detail": detail,
                "request_type": request_type,
                "request_sha256": request_sha256,
                "revision": prefix.revision,
                "state_sha256": prefix.state_sha256,
            }
            failure = json.loads(
                _json(
                    {
                        **failure_payload,
                        "failure_sha256": digest_value(failure_payload),
                    }
                )
            )
            updated = connection.execute(
                """UPDATE claim_loop_client_requests SET
                    status='SUPERSEDED',result_event_idempotency_key=?,
                    result_event_sha256=?,result_revision=?,result_state_sha256=?,
                    response_sha256=?,response_json=?,completed_at=?
                WHERE session_id=? AND loop_id=? AND idempotency_key=?
                    AND status='RESERVED'""",
                (
                    event_row["idempotency_key"],
                    event_row["event_sha256"],
                    prefix.revision,
                    prefix.state_sha256,
                    digest_value(failure),
                    _json(failure),
                    completed_at,
                    session_id,
                    loop_id,
                    idempotency_key,
                ),
            ).rowcount
            if updated != 1:
                connection.rollback()
                raise ClaimLoopStoreError("client request supersession CAS failed")
            connection.commit()
        return failure

    def abandon_client_request(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
        request_type: str,
        request_sha256: str,
        detail: str,
        completed_at: str,
    ) -> dict[str, Any]:
        """Terminalize an expired pre-journal reservation without domain writes."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """SELECT * FROM claim_loop_client_requests
                WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                (session_id, loop_id, idempotency_key),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ClaimLoopStoreError("client request reservation is absent")
            if (
                row["request_type"] != request_type
                or row["request_sha256"] != request_sha256
            ):
                connection.rollback()
                raise ClaimLoopStoreError("client request reservation diverged")
            if row["status"] == "ABANDONED":
                failure = json.loads(row["response_json"])
                connection.commit()
                return failure
            if row["status"] != "RESERVED":
                connection.rollback()
                raise ClaimLoopStoreError("only a reserved request can be abandoned")
            if any(
                row[name] is not None
                for name in (
                    "reserved_event_idempotency_key",
                    "reserved_event_sha256",
                    "reserved_revision",
                    "reserved_state_sha256",
                )
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "journal-bound request must be superseded at its prefix"
                )
            event = connection.execute(
                """SELECT 1 FROM claim_loop_events
                WHERE session_id=? AND loop_id=? LIMIT 1""",
                (session_id, loop_id),
            ).fetchone()
            if event is not None:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "pre-journal request unexpectedly has domain lineage"
                )
            failure_payload = {
                "contract": "casepath.claim-loop-client-conflict/1.0.0",
                "error_code": "REQUEST_ABANDONED",
                "detail": detail,
                "request_type": request_type,
                "request_sha256": request_sha256,
                "revision": 0,
                "state_sha256": None,
            }
            failure = json.loads(
                _json(
                    {
                        **failure_payload,
                        "failure_sha256": digest_value(failure_payload),
                    }
                )
            )
            updated = connection.execute(
                """UPDATE claim_loop_client_requests SET
                    status='ABANDONED',response_sha256=?,response_json=?,completed_at=?
                WHERE session_id=? AND loop_id=? AND idempotency_key=?
                    AND status='RESERVED'""",
                (
                    digest_value(failure),
                    _json(failure),
                    completed_at,
                    session_id,
                    loop_id,
                    idempotency_key,
                ),
            ).rowcount
            if updated != 1:
                connection.rollback()
                raise ClaimLoopStoreError("client request abandonment CAS failed")
            connection.commit()
        return failure

    @staticmethod
    def _event_rows(
        connection: sqlite3.Connection, session_id: str, loop_id: str
    ) -> list[sqlite3.Row]:
        return list(
            connection.execute(
                """SELECT * FROM claim_loop_events
                WHERE session_id=? AND loop_id=? ORDER BY sequence""",
                (session_id, loop_id),
            )
        )

    @staticmethod
    def _row_fingerprint(row: sqlite3.Row) -> bytes:
        """Bind every persisted journal column without duplicating event JSON.

        The process-local replay cache is only an optimization.  A direct DB
        mutation changes this fingerprint and therefore forces a complete
        journal replay before any cached state can be trusted again.
        """

        digest = hashlib.sha256()
        for key in (
            "session_id",
            "loop_id",
            "sequence",
            "idempotency_key",
            "command_sha256",
            "event_sha256",
            "event_json",
            "created_at",
        ):
            value = str(row[key]).encode("utf-8")
            digest.update(len(value).to_bytes(8, "big"))
            digest.update(value)
        return digest.digest()

    @staticmethod
    def _replay_rows_uncached(
        rows: list[sqlite3.Row], *, session_id: str, loop_id: str
    ) -> ClaimLoopState:
        if not rows:
            raise ClaimLoopStoreError("claim loop does not exist")
        state: ClaimLoopState | None = None
        previous: str | None = None
        for expected_sequence, row in enumerate(rows, start=1):
            if row["sequence"] != expected_sequence:
                raise ClaimLoopStoreError("claim loop event sequence has a gap")
            try:
                event = load_claim_loop_event_v1(json.loads(row["event_json"]))
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                raise ClaimLoopStoreError("claim loop event is invalid") from exc
            if (
                event.sequence != expected_sequence
                or row["session_id"] != session_id
                or row["loop_id"] != loop_id
                or event.session_id != session_id
                or event.loop_id != loop_id
                or row["idempotency_key"] != event.idempotency_key
                or row["created_at"] != event.created_at
                or event.previous_event_sha256 != previous
                or row["event_sha256"] != event.event_sha256
                or row["command_sha256"] != event.command_sha256
            ):
                raise ClaimLoopStoreError("claim loop event chain diverged")
            try:
                state = reduce_claim_loop_event(
                    state,
                    event_type=event.event_type,
                    command=event.command,
                    sequence=event.sequence,
                    event_sha256=event.event_sha256,
                    timestamp=event.created_at,
                )
            except (ClaimLoopError, KeyError, TypeError, ValueError) as exc:
                raise ClaimLoopStoreError("claim loop replay failed") from exc
            if state.state_sha256 != event.resulting_state_sha256:
                raise ClaimLoopStoreError("event result does not match replayed state")
            previous = event.event_sha256
        if state is None:  # pragma: no cover - guarded by nonempty rows
            raise ClaimLoopStoreError("claim loop replay produced no state")
        return state

    def _replay_rows(
        self, rows: list[sqlite3.Row], *, session_id: str, loop_id: str
    ) -> ClaimLoopState:
        """Replay an append-only suffix after proving the cached prefix bytes.

        Every cold process performs a complete replay.  Warm calls compare a
        digest of every exact persisted row with the previously replayed
        prefix, then reduce only newly appended rows.  Any changed, removed,
        reordered, or inserted row invalidates the optimization and is checked
        by the full authoritative replay path.
        """

        if not rows:
            raise ClaimLoopStoreError("claim loop does not exist")
        fingerprints = tuple(self._row_fingerprint(row) for row in rows)
        cache_key = (session_id, loop_id)
        with self._replay_cache_lock:
            cached = self._replay_cache.get(cache_key)
            if cached is None or fingerprints[: len(cached[0])] != cached[0]:
                state = self._replay_rows_uncached(
                    rows, session_id=session_id, loop_id=loop_id
                )
                state_bytes = canonical_json_bytes(state.model_dump(mode="json"))
                self._replay_cache[cache_key] = (fingerprints, state_bytes)
                return ClaimLoopState.model_validate_json(state_bytes)
            cached_fingerprints, state_bytes = cached
            if len(fingerprints) == len(cached_fingerprints):
                return ClaimLoopState.model_validate_json(state_bytes)
            state = ClaimLoopState.model_validate_json(state_bytes)
            previous = state.last_event_sha256
            for expected_sequence, row in enumerate(
                rows[len(cached_fingerprints) :],
                start=len(cached_fingerprints) + 1,
            ):
                if row["sequence"] != expected_sequence:
                    raise ClaimLoopStoreError("claim loop event sequence has a gap")
                try:
                    event = load_claim_loop_event_v1(json.loads(row["event_json"]))
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    raise ClaimLoopStoreError("claim loop event is invalid") from exc
                if (
                    event.sequence != expected_sequence
                    or row["session_id"] != session_id
                    or row["loop_id"] != loop_id
                    or event.session_id != session_id
                    or event.loop_id != loop_id
                    or row["idempotency_key"] != event.idempotency_key
                    or row["created_at"] != event.created_at
                    or event.previous_event_sha256 != previous
                    or row["event_sha256"] != event.event_sha256
                    or row["command_sha256"] != event.command_sha256
                ):
                    raise ClaimLoopStoreError("claim loop event chain diverged")
                try:
                    state = reduce_claim_loop_event(
                        state,
                        event_type=event.event_type,
                        command=event.command,
                        sequence=event.sequence,
                        event_sha256=event.event_sha256,
                        timestamp=event.created_at,
                    )
                except (ClaimLoopError, KeyError, TypeError, ValueError) as exc:
                    raise ClaimLoopStoreError("claim loop replay failed") from exc
                if state.state_sha256 != event.resulting_state_sha256:
                    raise ClaimLoopStoreError(
                        "event result does not match replayed state"
                    )
                previous = event.event_sha256
            state_bytes = canonical_json_bytes(state.model_dump(mode="json"))
            self._replay_cache[cache_key] = (fingerprints, state_bytes)
            return ClaimLoopState.model_validate_json(state_bytes)

    def _replay(
        self, connection: sqlite3.Connection, session_id: str, loop_id: str
    ) -> ClaimLoopState:
        return self._replay_rows(
            self._event_rows(connection, session_id, loop_id),
            session_id=session_id,
            loop_id=loop_id,
        )

    @classmethod
    def _checkpoint_prefix_state(
        cls,
        row: sqlite3.Row,
        rows: list[sqlite3.Row],
        *,
        session_id: str,
        loop_id: str,
    ) -> ClaimLoopState:
        revision = row["revision"]
        if (
            not isinstance(revision, int)
            or isinstance(revision, bool)
            or revision < 1
            or revision > len(rows)
        ):
            raise ClaimLoopStoreError("claim loop checkpoint is not a journal prefix")
        prefix = cls._replay_rows_uncached(
            rows[:revision], session_id=session_id, loop_id=loop_id
        )
        if (
            row["last_event_sha256"] != prefix.last_event_sha256
            or row["state_sha256"] != prefix.state_sha256
        ):
            raise ClaimLoopStoreError(
                "claim loop checkpoint diverges from its journal prefix"
            )
        # state_json is a derived cache.  Its scalar revision/hash anchors are
        # authoritative only insofar as the journal independently proves them.
        return prefix

    def _write_checkpoint(
        self,
        *,
        session_id: str,
        loop_id: str,
        state: ClaimLoopState,
        timestamp: str,
    ) -> None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = self._event_rows(connection, session_id, loop_id)
            tail_matches_candidate = (
                bool(rows)
                and len(rows) == state.revision
                and rows[-1]["event_sha256"] == state.last_event_sha256
                and rows[-1]["sequence"] == state.revision
            )
            current = (
                state
                if tail_matches_candidate
                else self._replay_rows(
                    rows,
                    session_id=session_id,
                    loop_id=loop_id,
                )
            )
            if current.revision < state.revision:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "checkpoint candidate is ahead of the event tail"
                )
            # The event journal is authoritative.  If another command extends it
            # after this caller commits event N, checkpoint the newer tail rather
            # than turning a successful append into a spurious failure.
            state = current
            # A checkpoint is only a cache of the independently validated event
            # journal.  Every field, including its original creation timestamp,
            # is reconstructed from that journal rather than trusted from a
            # possibly corrupt cache row.
            created_at = rows[0]["created_at"]
            connection.execute(
                """INSERT INTO claim_loop_checkpoints
                (session_id,loop_id,revision,last_event_sha256,state_sha256,state_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(session_id,loop_id) DO UPDATE SET
                    revision=excluded.revision,
                    last_event_sha256=excluded.last_event_sha256,
                    state_sha256=excluded.state_sha256,
                    state_json=excluded.state_json,
                    updated_at=excluded.updated_at""",
                (
                    session_id,
                    loop_id,
                    state.revision,
                    state.last_event_sha256,
                    state.state_sha256,
                    _json(state.model_dump(mode="json")),
                    created_at,
                    timestamp,
                ),
            )
            connection.commit()

    @staticmethod
    def _receipt(
        *,
        loop_id: str,
        idempotency_key: str,
        event_sha256: str,
        state: ClaimLoopState,
    ) -> ClaimLoopCommandReceipt:
        payload = {
            "contract": "casepath.claim-loop-command-receipt/1.0.0",
            "loop_id": loop_id,
            "idempotency_key": idempotency_key,
            "event_sha256": event_sha256,
            "state_sha256": state.state_sha256,
            "revision": state.revision,
        }
        return ClaimLoopCommandReceipt.model_validate(
            {**payload, "receipt_sha256": digest_value(payload)}
        )

    def append(
        self,
        *,
        session_id: str,
        loop_id: str,
        event_type: str,
        idempotency_key: str,
        command: Mapping[str, Any],
        timestamp: str,
        expected_revision: int | None = None,
        after_event_commit: Callable[[], None] | None = None,
        client_dispatch_guard: Mapping[str, Any] | None = None,
    ) -> tuple[ClaimLoopState, ClaimLoopCommandReceipt, bool]:
        command_value = deepcopy_json(command)
        command_sha256 = digest_value(command_value)
        replayed = False
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT event_json, command_sha256 FROM claim_loop_events
                WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                (session_id, loop_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["command_sha256"] != command_sha256:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "idempotency key was reused with different input"
                    )
                event = load_claim_loop_event_v1(json.loads(existing["event_json"]))
                if event.event_type != event_type:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "idempotency key was reused for a different event type"
                    )
                rows = self._event_rows(connection, session_id, loop_id)
                event_rows = rows[: event.sequence]
                if (
                    not event_rows
                    or event_rows[-1]["event_sha256"] != event.event_sha256
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "idempotent event is not in the validated event chain"
                    )
                # A duplicate command returns the exact original state/receipt even
                # after later events have advanced the loop.  The tail checkpoint
                # remains a derived cache and is repaired separately below.
                state = self._replay_rows(
                    event_rows, session_id=session_id, loop_id=loop_id
                )
                replayed = True
                connection.commit()
            else:
                direct_request = connection.execute(
                    """SELECT request_type,status FROM claim_loop_client_requests
                    WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                    (session_id, loop_id, idempotency_key),
                ).fetchone()
                direct_event_types = {
                    "create": "LOOP_CREATED",
                    "select_action": "ACTION_SELECTED",
                    "ingest_observation": "OBSERVATION_INGESTED",
                    "tool_unavailable": "TOOL_UNAVAILABLE",
                    "apply_correction": "CORRECTION_APPLIED",
                    "reuse_correction": "CORRECTION_REUSED",
                }
                if direct_request is not None and (
                    direct_request["status"] != "RESERVED"
                    or direct_event_types.get(direct_request["request_type"])
                    != event_type
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "client request authority ended before journal admission"
                    )
                if client_dispatch_guard is not None:
                    guard = deepcopy_json(client_dispatch_guard)
                    request_type, request_sha256 = _client_request_identity(
                        command_value
                    )
                    if event_type != "ACTION_DISPATCH_STARTED":
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "client dispatch guard is restricted to dispatch start"
                        )
                    request_row = connection.execute(
                        """SELECT * FROM claim_loop_client_requests
                        WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                        (
                            session_id,
                            loop_id,
                            guard.get("client_idempotency_key"),
                        ),
                    ).fetchone()
                    if (
                        request_row is None
                        or request_row["status"] != "RESERVED"
                        or request_row["request_type"] != request_type
                        or request_row["request_sha256"] != guard.get("request_sha256")
                        or request_row["dispatch_started_at"]
                        != guard.get("dispatch_started_at")
                        or request_row["dispatch_expires_at"]
                        != guard.get("dispatch_expires_at")
                        or request_row["dispatch_generation"]
                        != guard.get("dispatch_generation")
                        or command_value.get("client_idempotency_key")
                        != guard.get("client_idempotency_key")
                        or request_sha256 != guard.get("request_sha256")
                        or guard.get("request_type", request_type) != request_type
                        or command_value.get("lease_expires_at")
                        != guard.get("dispatch_expires_at")
                        or command_value.get("dispatch_generation")
                        != guard.get("dispatch_generation")
                        or timestamp != guard.get("dispatch_started_at")
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "dispatch lease generation changed before journal admission"
                        )
                rows = self._event_rows(connection, session_id, loop_id)
                current = (
                    self._replay_rows(rows, session_id=session_id, loop_id=loop_id)
                    if rows
                    else None
                )
                if rows:
                    latest_event = load_claim_loop_event_v1(
                        json.loads(rows[-1]["event_json"])
                    )
                    latest_thin_waist = _thin_waist_record_set(latest_event.command)
                    if (
                        latest_event.event_type == "OBSERVATION_INGESTED"
                        and latest_thin_waist is not None
                        and latest_thin_waist.action_receipt is None
                        and event_type != "PROTOCOL_REPLAN_RECEIPT_RECORDED"
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "pending thin-waist receipt blocks later events"
                        )
                if expected_revision is not None:
                    actual_revision = current.revision if current is not None else 0
                    if expected_revision != actual_revision:
                        connection.rollback()
                        raise ClaimLoopStoreError("claim loop revision changed")
                protocol_records = _protocol_record_set(command_value)
                thin_waist_records = _thin_waist_record_set(command_value)
                prior_protocol_records: InsuranceProtocolRecordSetV1 | None = None
                prior_protocol_event = None
                for prior_row in reversed(rows):
                    prior_event = load_claim_loop_event_v1(
                        json.loads(prior_row["event_json"])
                    )
                    candidate = _protocol_record_set(prior_event.command)
                    if candidate is not None:
                        prior_protocol_records = candidate
                        prior_protocol_event = prior_event
                        break
                active_dispatch_event = None
                if current is not None and current.active_dispatch_sha256 is not None:
                    for active_row in rows:
                        candidate_event = load_claim_loop_event_v1(
                            json.loads(active_row["event_json"])
                        )
                        if (
                            candidate_event.event_sha256
                            == current.active_dispatch_sha256
                        ):
                            active_dispatch_event = candidate_event
                            break
                active_protocol_dispatch = (
                    active_dispatch_event is not None
                    and _protocol_record_set(active_dispatch_event.command) is not None
                )
                if (
                    active_protocol_dispatch
                    and event_type
                    in {
                        "OBSERVATION_INGESTED",
                        "EVIDENCE_PROPOSAL_REJECTED",
                        "TOOL_UNAVAILABLE",
                        "DISPATCH_UNKNOWN",
                    }
                    and protocol_records is None
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "protocol-owned dispatch cannot be closed by a legacy outcome"
                    )
                if protocol_records is not None:
                    command_staging_binding = command_value.get(
                        "adapter_staging_binding"
                    )
                    binding_reader = (
                        getattr(self.protocol_registry, "staging_binding", None)
                        if self.protocol_registry is not None
                        else None
                    )
                    if callable(binding_reader):
                        try:
                            expected_staging_binding = binding_reader(
                                protocol_records.staged_artifact.receipt_sha256
                            ).model_dump(mode="json")
                        except (TypeError, ValueError, RuntimeError) as exc:
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "protocol typed-stage authority is unavailable"
                            ) from exc
                        mapped_event = expected_staging_binding.get("mapped_event")
                        if (
                            command_staging_binding != expected_staging_binding
                            or not isinstance(mapped_event, Mapping)
                            or mapped_event.get("action_id")
                            != protocol_records.decision.compatibility_action.action_id
                            or mapped_event.get("action_sha256")
                            != protocol_records.decision.compatibility_action.action_sha256
                        ):
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "protocol typed-stage lineage diverged"
                            )
                    elif command_staging_binding is not None:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "protocol stage binding is not supported by its adapter"
                        )
                    protocol_events = {
                        "ACTION_DISPATCH_STARTED",
                        "PROTOCOL_EXECUTION_STARTED",
                        "PROTOCOL_ACTION_RECEIPT_RECORDED",
                        "PROTOCOL_SOURCE_OBSERVATION_RECORDED",
                        "PROTOCOL_ASSERTION_NORMALIZED",
                        "PROTOCOL_INTERPRETATION_RECORDED",
                        "PROTOCOL_INTENT_CANCELLED",
                        "DISPATCH_UNKNOWN",
                        "OBSERVATION_INGESTED",
                    }
                    if event_type not in protocol_events:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "insurance records are not allowed on this event"
                        )
                    if event_type == "ACTION_DISPATCH_STARTED":
                        if (
                            current is None
                            or prior_protocol_records is not None
                            or protocol_records.action_receipt is not None
                            or protocol_records.proposal.session_id != session_id
                            or protocol_records.proposal.loop_id != loop_id
                            or protocol_records.proposal.source_revision
                            != current.revision
                            or protocol_records.proposal.source_state_sha256
                            != current.state_sha256
                            or self.protocol_registry is None
                        ):
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "protocol intent is not admitted from the current journal"
                            )
                        try:
                            from .insurance_protocol_runtime import (
                                build_registration_authority_v1,
                            )

                            staged = self.protocol_registry.staged(
                                protocol_records.staged_artifact.receipt_sha256
                            )
                            dry_run = self.protocol_registry.dry_run(
                                intent=protocol_records.intent,
                                staged=protocol_records.staged_artifact,
                                evaluated_at=protocol_records.decision.decided_at,
                            )
                            rebuilt = build_registration_authority_v1(
                                state=current,
                                proposal=protocol_records.proposal,
                                staged=protocol_records.staged_artifact,
                                adapter=self.protocol_registry,
                                decided_at=protocol_records.decision.decided_at,
                                effective_until=(
                                    protocol_records.decision.effective_until
                                ),
                                source_journal_events=tuple(
                                    load_claim_loop_event_v1(
                                        json.loads(source_row["event_json"])
                                    )
                                    for source_row in rows
                                ),
                            )
                        except (TypeError, ValueError, RuntimeError) as exc:
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "protocol registry authority is unavailable"
                            ) from exc
                        if (
                            staged != protocol_records.staged_artifact
                            or dry_run != protocol_records.decision.dry_run_receipt
                            or rebuilt != protocol_records
                        ):
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "protocol stage or dry-run authority diverged"
                            )
                    else:
                        if (
                            prior_protocol_records is None
                            or prior_protocol_event is None
                            or not _same_protocol_authority(
                                prior_protocol_records, protocol_records
                            )
                            or command_value.get("prior_protocol_event_sha256")
                            != prior_protocol_event.event_sha256
                            or command_staging_binding
                            != prior_protocol_event.command.get(
                                "adapter_staging_binding"
                            )
                        ):
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "protocol transition changed authority or predecessor"
                            )
                        prior_receipt = prior_protocol_records.action_receipt
                        receipt = protocol_records.action_receipt
                        if event_type == "PROTOCOL_EXECUTION_STARTED":
                            valid_prefix = (
                                prior_protocol_event.event_type
                                == "ACTION_DISPATCH_STARTED"
                                and prior_receipt is None
                                and receipt is None
                                and protocol_records == prior_protocol_records
                            )
                        elif event_type == "PROTOCOL_ACTION_RECEIPT_RECORDED":
                            valid_prefix = (
                                prior_protocol_event.event_type
                                in {"PROTOCOL_EXECUTION_STARTED", "DISPATCH_UNKNOWN"}
                                and (
                                    prior_receipt is None
                                    or prior_receipt.status
                                    is ActionReceiptStatus.UNKNOWN
                                )
                                and receipt is not None
                                and receipt.status is ActionReceiptStatus.COMMITTED
                                and protocol_records.source_observation is None
                                and _protocol_changes_only(
                                    prior_protocol_records,
                                    protocol_records,
                                    "action_receipt",
                                )
                            )
                        elif event_type == "PROTOCOL_SOURCE_OBSERVATION_RECORDED":
                            valid_prefix = (
                                prior_protocol_event.event_type
                                == "PROTOCOL_ACTION_RECEIPT_RECORDED"
                                and prior_receipt is not None
                                and prior_receipt.status
                                is ActionReceiptStatus.COMMITTED
                                and receipt == prior_receipt
                                and prior_protocol_records.source_observation is None
                                and protocol_records.source_observation is not None
                                and protocol_records.normalized_assertion is None
                                and _protocol_changes_only(
                                    prior_protocol_records,
                                    protocol_records,
                                    "source_observation",
                                )
                            )
                        elif event_type == "PROTOCOL_ASSERTION_NORMALIZED":
                            valid_prefix = (
                                prior_protocol_event.event_type
                                == "PROTOCOL_SOURCE_OBSERVATION_RECORDED"
                                and prior_protocol_records.source_observation
                                is not None
                                and prior_protocol_records.normalized_assertion is None
                                and protocol_records.normalized_assertion is not None
                                and protocol_records.interpretation is None
                                and _protocol_changes_only(
                                    prior_protocol_records,
                                    protocol_records,
                                    "normalized_assertion",
                                )
                            )
                        elif event_type == "PROTOCOL_INTERPRETATION_RECORDED":
                            valid_prefix = (
                                prior_protocol_event.event_type
                                == "PROTOCOL_ASSERTION_NORMALIZED"
                                and prior_protocol_records.normalized_assertion
                                is not None
                                and prior_protocol_records.interpretation is None
                                and protocol_records.interpretation is not None
                                and _protocol_changes_only(
                                    prior_protocol_records,
                                    protocol_records,
                                    "interpretation",
                                )
                            )
                        elif event_type == "OBSERVATION_INGESTED":
                            valid_prefix = (
                                prior_protocol_event.event_type
                                == "PROTOCOL_INTERPRETATION_RECORDED"
                                and prior_protocol_records.interpretation is not None
                                and protocol_records == prior_protocol_records
                            )
                        elif event_type == "DISPATCH_UNKNOWN":
                            valid_prefix = (
                                prior_protocol_event.event_type
                                == "PROTOCOL_EXECUTION_STARTED"
                                and prior_receipt is None
                                and receipt is not None
                                and receipt.status is ActionReceiptStatus.UNKNOWN
                                and protocol_records.source_observation is None
                                and _protocol_changes_only(
                                    prior_protocol_records,
                                    protocol_records,
                                    "action_receipt",
                                )
                            )
                        else:
                            valid_prefix = (
                                prior_protocol_event.event_type
                                in {
                                    "ACTION_DISPATCH_STARTED",
                                    "PROTOCOL_EXECUTION_STARTED",
                                }
                                and prior_receipt is None
                                and receipt is not None
                                and receipt.status is ActionReceiptStatus.CANCELLED
                                and protocol_records.source_observation is None
                                and _protocol_changes_only(
                                    prior_protocol_records,
                                    protocol_records,
                                    "action_receipt",
                                )
                            )
                        if not valid_prefix:
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "protocol records do not form the required transition"
                            )
                        required_epistemic_stage = {
                            "PROTOCOL_SOURCE_OBSERVATION_RECORDED": "source",
                            "PROTOCOL_ASSERTION_NORMALIZED": "assertion",
                            "PROTOCOL_INTERPRETATION_RECORDED": "interpretation",
                            "OBSERVATION_INGESTED": "interpretation",
                        }.get(event_type)
                        if required_epistemic_stage is not None:
                            assert current is not None
                            try:
                                _validate_protocol_epistemic_authority(
                                    connection,
                                    current=current,
                                    records=protocol_records,
                                    require=required_epistemic_stage,
                                )
                            except ClaimLoopStoreError:
                                connection.rollback()
                                raise
                        if receipt is not None:
                            if self.protocol_registry is None:
                                connection.rollback()
                                raise ClaimLoopStoreError(
                                    "protocol receipt lacks registry authority"
                                )
                            try:
                                registry_receipt = self.protocol_registry.status(
                                    intent=protocol_records.intent
                                )
                            except (TypeError, ValueError, RuntimeError) as exc:
                                connection.rollback()
                                raise ClaimLoopStoreError(
                                    "protocol registry receipt is invalid"
                                ) from exc
                            if registry_receipt != receipt:
                                connection.rollback()
                                raise ClaimLoopStoreError(
                                    "protocol action receipt differs from registry"
                                )
                    protocol_event_kinds = {
                        "PROTOCOL_EXECUTION_STARTED": "execution-started",
                        "PROTOCOL_ACTION_RECEIPT_RECORDED": "action-receipt",
                        "PROTOCOL_SOURCE_OBSERVATION_RECORDED": ("source-observation"),
                        "PROTOCOL_ASSERTION_NORMALIZED": "normalized-assertion",
                        "PROTOCOL_INTERPRETATION_RECORDED": "interpretation",
                        "PROTOCOL_INTENT_CANCELLED": "intent-cancelled",
                        "DISPATCH_UNKNOWN": "dispatch-unknown",
                    }
                    event_kind = protocol_event_kinds.get(event_type)
                    if event_kind is not None:
                        origin_key = command_value.get("origin_client_idempotency_key")
                        origin_sha = command_value.get("origin_client_request_sha256")
                        origin_type = command_value.get("origin_client_request_type")
                        expected_key = (
                            claim_loop_internal_event_key_v1(
                                session_id=session_id,
                                loop_id=loop_id,
                                client_idempotency_key=origin_key,
                                request_type=origin_type,
                                request_sha256=origin_sha,
                                event_kind=event_kind,
                            )
                            if isinstance(origin_key, str)
                            and isinstance(origin_sha, str)
                            and isinstance(origin_type, str)
                            else None
                        )
                        origin_row = connection.execute(
                            """SELECT request_type,request_sha256,status
                            FROM claim_loop_client_requests
                            WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                            (session_id, loop_id, origin_key),
                        ).fetchone()
                        if (
                            idempotency_key != expected_key
                            or origin_type != "insurance_register"
                            or origin_row is None
                            or origin_row["request_type"] != origin_type
                            or origin_row["request_sha256"] != origin_sha
                            or origin_row["status"] != "RESERVED"
                        ):
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "protocol event key or parent request is invalid"
                            )
                if (
                    event_type == "OBSERVATION_INGESTED"
                    and protocol_records is not None
                    and thin_waist_records is None
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "protocol replan lacks the canonical thin-waist intent"
                    )
                if thin_waist_records is not None:
                    if current is None:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "thin-waist transition lacks a parent state"
                        )
                    if event_type == "OBSERVATION_INGESTED":
                        try:
                            expected_thin_waist = (
                                build_thin_waist_replan_intent_v2(
                                    session_id=current.session_id,
                                    loop_id=current.loop_id,
                                    claim_id=current.claim_id,
                                    record_version=current.record_version,
                                    source_state_sha256=current.state_sha256,
                                    source_revision=current.revision,
                                    records=protocol_records,
                                    timestamp=timestamp,
                                )
                                if protocol_records is not None
                                else None
                            )
                        except ValueError as exc:
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "thin-waist authority could not be reconstructed"
                            ) from exc
                        if (
                            protocol_records is None
                            or expected_thin_waist is None
                            or thin_waist_records != expected_thin_waist
                        ):
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "thin-waist replan intent is not bound to its epistemic prefix"
                            )
                    elif event_type == "PROTOCOL_REPLAN_RECEIPT_RECORDED":
                        prior_event = (
                            load_claim_loop_event_v1(json.loads(rows[-1]["event_json"]))
                            if rows
                            else None
                        )
                        prior_thin = (
                            _thin_waist_record_set(prior_event.command)
                            if prior_event is not None
                            else None
                        )
                        action_receipt = thin_waist_records.action_receipt
                        if (
                            prior_event is None
                            or prior_event.event_type != "OBSERVATION_INGESTED"
                            or prior_thin is None
                            or prior_thin.action_receipt is not None
                            or action_receipt is None
                            or thin_waist_records.model_dump(
                                mode="json",
                                exclude={"record_set_sha256", "action_receipt"},
                            )
                            != prior_thin.model_dump(
                                mode="json",
                                exclude={"record_set_sha256", "action_receipt"},
                            )
                            or action_receipt.committed_event_sha256
                            != prior_event.event_sha256
                            or action_receipt.resulting_state_sha256
                            != current.state_sha256
                            or action_receipt.resulting_revision != current.revision
                            or command_value.get("committed_replan_event_sha256")
                            != prior_event.event_sha256
                        ):
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "thin-waist replan receipt is not bound to the committed event"
                            )
                        origin_key = command_value.get("origin_client_idempotency_key")
                        origin_sha = command_value.get("origin_client_request_sha256")
                        origin_type = command_value.get("origin_client_request_type")
                        expected_key = (
                            claim_loop_internal_event_key_v1(
                                session_id=session_id,
                                loop_id=loop_id,
                                client_idempotency_key=origin_key,
                                request_type="insurance_register",
                                request_sha256=origin_sha,
                                event_kind="replan-receipt",
                            )
                            if isinstance(origin_key, str)
                            and isinstance(origin_sha, str)
                            else None
                        )
                        origin_row = connection.execute(
                            """SELECT request_type,request_sha256,status
                            FROM claim_loop_client_requests
                            WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                            (session_id, loop_id, origin_key),
                        ).fetchone()
                        if (
                            idempotency_key != expected_key
                            or origin_type != "insurance_register"
                            or origin_row is None
                            or origin_row["request_type"] != origin_type
                            or origin_row["request_sha256"] != origin_sha
                            or origin_row["status"] != "RESERVED"
                            or action_receipt.committed_at != prior_event.created_at
                            or timestamp != prior_event.created_at
                        ):
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "thin-waist receipt origin is invalid"
                            )
                    else:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "thin-waist records are not allowed on this event"
                        )
                if (
                    event_type == "ACTION_SELECTED"
                    and command_value.get("advance_request_sha256") is not None
                ):
                    parent_key = command_value.get("client_idempotency_key")
                    parent_sha = command_value.get("advance_request_sha256")
                    expected_select_key = (
                        claim_loop_internal_event_key_v1(
                            session_id=session_id,
                            loop_id=loop_id,
                            client_idempotency_key=parent_key,
                            request_type="advance",
                            request_sha256=parent_sha,
                            event_kind="select",
                        )
                        if isinstance(parent_key, str) and isinstance(parent_sha, str)
                        else None
                    )
                    parent_row = connection.execute(
                        """SELECT request_type,request_sha256,status
                        FROM claim_loop_client_requests
                        WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                        (session_id, loop_id, parent_key),
                    ).fetchone()
                    if (
                        idempotency_key != expected_select_key
                        or command_value.get("client_select_idempotency_key")
                        != expected_select_key
                        or parent_row is None
                        or parent_row["request_type"] != "advance"
                        or parent_row["request_sha256"] != parent_sha
                        or parent_row["status"] != "RESERVED"
                        or current is None
                        or command_value.get("selected_from_revision")
                        != current.revision
                        or command_value.get("selected_result_revision")
                        != current.revision + 1
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "advance selection internal key or parent binding is invalid"
                        )
                if event_type == "ACTION_DISPATCH_STARTED":
                    parent_key = command_value.get("client_idempotency_key")
                    request_type, parent_sha = _client_request_identity(command_value)
                    if not isinstance(parent_key, str) or not isinstance(
                        parent_sha, str
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "dispatch start lacks its parent client request"
                        )
                    expected_dispatch_key = claim_loop_internal_event_key_v1(
                        session_id=session_id,
                        loop_id=loop_id,
                        client_idempotency_key=parent_key,
                        request_type=request_type,
                        request_sha256=parent_sha,
                        event_kind="dispatch",
                    )
                    expected_result_key = claim_loop_internal_event_key_v1(
                        session_id=session_id,
                        loop_id=loop_id,
                        client_idempotency_key=parent_key,
                        request_type=request_type,
                        request_sha256=parent_sha,
                        event_kind="result",
                    )
                    parent_row = connection.execute(
                        """SELECT request_type,request_sha256,status
                        FROM claim_loop_client_requests
                        WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                        (session_id, loop_id, parent_key),
                    ).fetchone()
                    if (
                        idempotency_key != expected_dispatch_key
                        or command_value.get("client_dispatch_idempotency_key")
                        != expected_dispatch_key
                        or command_value.get("client_result_idempotency_key")
                        != expected_result_key
                        or parent_row is None
                        or parent_row["request_type"] != request_type
                        or parent_row["request_sha256"] != parent_sha
                        or parent_row["status"] != "RESERVED"
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "dispatch start internal key or parent binding is invalid"
                        )
                if (
                    event_type
                    in {
                        "OBSERVATION_INGESTED",
                        "EVIDENCE_PROPOSAL_REJECTED",
                        "TOOL_UNAVAILABLE",
                        "DISPATCH_UNKNOWN",
                    }
                    and _client_request_identity(command_value)[1] is not None
                    and not (
                        event_type == "DISPATCH_UNKNOWN"
                        and protocol_records is not None
                    )
                ):
                    if current is None or current.active_dispatch_sha256 is None:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "advance result lacks an active dispatch"
                        )
                    dispatch_row = connection.execute(
                        """SELECT event_json FROM claim_loop_events
                        WHERE session_id=? AND loop_id=? AND event_sha256=?""",
                        (session_id, loop_id, current.active_dispatch_sha256),
                    ).fetchone()
                    if dispatch_row is None:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "advance result dispatch event is absent"
                        )
                    dispatch_event = load_claim_loop_event_v1(
                        json.loads(dispatch_row["event_json"])
                    )
                    parent_key = dispatch_event.command.get("client_idempotency_key")
                    request_type, parent_sha = _client_request_identity(
                        dispatch_event.command
                    )
                    expected_result_key = (
                        claim_loop_internal_event_key_v1(
                            session_id=session_id,
                            loop_id=loop_id,
                            client_idempotency_key=parent_key,
                            request_type=request_type,
                            request_sha256=parent_sha,
                            event_kind="result",
                        )
                        if isinstance(parent_key, str) and isinstance(parent_sha, str)
                        else None
                    )
                    parent_row = connection.execute(
                        """SELECT request_type,request_sha256,status
                        FROM claim_loop_client_requests
                        WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                        (session_id, loop_id, parent_key),
                    ).fetchone()
                    if (
                        idempotency_key != expected_result_key
                        or _client_request_identity(command_value)[1] != parent_sha
                        or dispatch_event.command.get("client_result_idempotency_key")
                        != expected_result_key
                        or parent_row is None
                        or parent_row["request_type"] != request_type
                        or parent_row["request_sha256"] != parent_sha
                        or parent_row["status"] != "RESERVED"
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "advance result internal key or parent binding is invalid"
                        )
                if event_type == "OBSERVATION_INGESTED":
                    artifact_sha = command_value.get("artifact_receipt_sha256")
                    artifact_row = connection.execute(
                        """SELECT artifact_json FROM claim_loop_tool_artifacts
                        WHERE receipt_sha256=?""",
                        (artifact_sha,),
                    ).fetchone()
                    if artifact_row is None:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "observation is not backed by a registered tool artifact"
                        )
                    try:
                        artifact = ToolArtifactReceipt.model_validate(
                            json.loads(artifact_row["artifact_json"])
                        )
                    except (ValueError, TypeError, json.JSONDecodeError) as exc:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "registered observation artifact is invalid"
                        ) from exc
                    acquisition_row = connection.execute(
                        """SELECT * FROM claim_loop_acquisitions
                        WHERE receipt_sha256=?""",
                        (artifact.acquisition_receipt_sha256,),
                    ).fetchone()
                    if acquisition_row is None:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "observation acquisition receipt is absent"
                        )
                    try:
                        acquisition = self._acquisition_from_row(acquisition_row)
                    except ClaimLoopStoreError:
                        connection.rollback()
                        raise
                    if (
                        current is None
                        or current.selected_action is None
                        or artifact.session_id != session_id
                        or artifact.loop_id != loop_id
                        or artifact.artifact_source_version != current.record_version
                        or artifact.action_id != current.selected_action.action_id
                        or artifact.action_sha256
                        != current.selected_action.action_sha256
                        or artifact.dispatch_sha256 != current.active_dispatch_sha256
                        or command_value.get("action_id") != artifact.action_id
                        or command_value.get("dispatch_sha256")
                        != artifact.dispatch_sha256
                        or command_value.get("tool_artifact_receipt")
                        != artifact.model_dump(mode="json")
                        or command_value.get("observation")
                        != artifact.observation.model_dump(mode="json")
                        or artifact.acquisition_receipt != acquisition
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "observation command differs from its registered artifact"
                        )
                    if protocol_records is not None:
                        source = protocol_records.source_observation
                        assertion = protocol_records.normalized_assertion
                        interpretation = protocol_records.interpretation
                        if (
                            source is None
                            or assertion is None
                            or interpretation is None
                            or source.action_receipt_sha256
                            != protocol_records.action_receipt.receipt_sha256
                            or source.content_sha256
                            != acquisition.sanitized_content_sha256
                            or source.exact_text_sha256
                            != acquisition.sanitized_content_sha256
                            or source.text_end
                            != len(acquisition.sanitized_content or "")
                            or source.artifact_uri
                            != protocol_records.action_receipt.artifact_uri
                            or assertion.source_observation_sha256
                            != source.observation_sha256
                            or assertion.claim_observation != artifact.observation
                            or assertion.claim_observation_sha256
                            != artifact.observation.observation_sha256
                            or assertion.canonical_interpretation
                            != artifact.interpretation
                            or assertion.extraction_method
                            != artifact.interpretation.implementation
                            or assertion.extraction_method_source_sha256
                            != artifact.interpretation.implementation_source_sha256
                            or assertion.fact_id != artifact.interpretation.fact_id
                            or assertion.evidence_item_id
                            != artifact.interpretation.evidence_item_id
                            or assertion.fact_state != artifact.observation.fact_state
                            or assertion.normalized_value
                            != artifact.observation.normalized_value
                            or interpretation.assertion_sha256
                            != assertion.assertion_sha256
                            or interpretation.canonical_interpretation_receipt_sha256
                            != artifact.interpretation.receipt_sha256
                            or interpretation.prior_fact_sha256
                            != artifact.interpretation.prior_fact_sha256
                            or interpretation.assertion_catalog_sha256
                            != artifact.interpretation.assertion_catalog_sha256
                            or interpretation.selected_assertion_id
                            != artifact.interpretation.selected_assertion_id
                            or interpretation.playbook_template_sha256
                            != current.accepted_artifacts.get(
                                "playbook_template", {}
                            ).get("template_sha256")
                            or interpretation.policy_version
                            != "casepath.claim-loop-interpretation-policy/1.0.0"
                            or interpretation.status
                            != (
                                "supported"
                                if artifact.observation.fact_state == "known"
                                and artifact.observation.evidence_status
                                == "provided_sufficient"
                                else (
                                    "disputed"
                                    if artifact.observation.fact_state == "conflicting"
                                    else "insufficient"
                                )
                            )
                        ):
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "protocol epistemic records differ from registered artifact"
                            )
                if event_type == "EVIDENCE_PROPOSAL_REJECTED":
                    acquisition_sha = command_value.get(
                        "acquisition_receipt_sha256"
                    )
                    acquisition_row = connection.execute(
                        """SELECT * FROM claim_loop_acquisitions
                        WHERE receipt_sha256=?""",
                        (acquisition_sha,),
                    ).fetchone()
                    if acquisition_row is None:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "evidence rejection lacks its persisted acquisition"
                        )
                    try:
                        acquisition = self._acquisition_from_row(acquisition_row)
                    except ClaimLoopStoreError:
                        connection.rollback()
                        raise
                    rejection_validator = getattr(
                        self.artifact_interpreter,
                        "validate_recorded_authority_rejection",
                        None,
                    )
                    if (
                        current is None
                        or current.selected_action is None
                        or current.active_dispatch_sha256 is None
                        or acquisition.status.value != "observed"
                        or acquisition.session_id != session_id
                        or acquisition.loop_id != loop_id
                        or acquisition.record_version != current.record_version
                        or acquisition.action_id != current.selected_action.action_id
                        or acquisition.action_sha256
                        != current.selected_action.action_sha256
                        or acquisition.dispatch_sha256
                        != current.active_dispatch_sha256
                        or command_value.get("action_id") != acquisition.action_id
                        or command_value.get("action_sha256")
                        != acquisition.action_sha256
                        or command_value.get("dispatch_sha256")
                        != acquisition.dispatch_sha256
                        or command_value.get("acquisition_receipt")
                        != acquisition.model_dump(mode="json")
                        or not callable(rejection_validator)
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "evidence rejection command differs from its acquisition"
                        )
                    try:
                        rejection_validator(
                            action=current.selected_action,
                            state=current,
                            acquisition=acquisition,
                            rejection_receipt=command_value.get(
                                "authority_rejection_receipt"
                            ),
                        )
                    except (ClaimLoopError, TypeError, ValueError) as exc:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "evidence rejection authority is invalid"
                        ) from exc
                if event_type == "TOOL_UNAVAILABLE":
                    acquisition_sha = command_value.get("acquisition_receipt_sha256")
                    acquisition_row = connection.execute(
                        """SELECT * FROM claim_loop_acquisitions
                        WHERE receipt_sha256=?""",
                        (acquisition_sha,),
                    ).fetchone()
                    if acquisition_row is None:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "tool failure lacks a persisted acquisition receipt"
                        )
                    try:
                        acquisition = self._acquisition_from_row(acquisition_row)
                    except ClaimLoopStoreError:
                        connection.rollback()
                        raise
                    if (
                        current is None
                        or current.selected_action is None
                        or acquisition.status.value not in {"unavailable", "failed"}
                        or acquisition.session_id != session_id
                        or acquisition.loop_id != loop_id
                        or acquisition.record_version != current.record_version
                        or acquisition.action_id != current.selected_action.action_id
                        or acquisition.action_sha256
                        != current.selected_action.action_sha256
                        or acquisition.dispatch_sha256 != current.active_dispatch_sha256
                        or command_value.get("action_id") != acquisition.action_id
                        or command_value.get("dispatch_sha256")
                        != acquisition.dispatch_sha256
                        or command_value.get("outcome") != acquisition.status.value
                        or command_value.get("acquisition_receipt")
                        != acquisition.model_dump(mode="json")
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "tool failure command differs from its acquisition"
                        )
                if event_type == "DISPATCH_UNKNOWN":
                    dispatch_sha256 = command_value.get("dispatch_sha256")
                    if not isinstance(dispatch_sha256, str):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "dispatch unknown event lacks its dispatch identity"
                        )
                    artifact = connection.execute(
                        """SELECT 1 FROM claim_loop_tool_artifacts
                        WHERE session_id=? AND loop_id=? AND dispatch_sha256=?""",
                        (session_id, loop_id, dispatch_sha256),
                    ).fetchone()
                    if artifact is not None:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "durable tool artifact supersedes dispatch expiry"
                        )
                    acquisition = connection.execute(
                        """SELECT 1 FROM claim_loop_acquisitions
                        WHERE session_id=? AND loop_id=? AND dispatch_sha256=?""",
                        (session_id, loop_id, dispatch_sha256),
                    ).fetchone()
                    if acquisition is not None:
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "durable acquisition supersedes dispatch expiry"
                        )
                sequence = 1 if current is None else current.revision + 1
                previous = None if current is None else current.last_event_sha256
                event_material = {
                    "contract": (
                        "casepath.claim-loop-protocol-event/2.0.0"
                        if event_type == "PROTOCOL_REPLAN_RECEIPT_RECORDED"
                        else (
                            "casepath.claim-loop-protocol-event/1.0.0"
                            if protocol_records is not None
                            else "casepath.claim-loop-event/1.0.0"
                        )
                    ),
                    "session_id": session_id,
                    "loop_id": loop_id,
                    "sequence": sequence,
                    "previous_event_sha256": previous,
                    "event_type": event_type,
                    "idempotency_key": idempotency_key,
                    "command_sha256": command_sha256,
                    "command": command_value,
                    "created_at": timestamp,
                }
                event_sha256 = digest_value(event_material)
                try:
                    state = reduce_claim_loop_event(
                        current,
                        event_type=event_type,
                        command=command_value,
                        sequence=sequence,
                        event_sha256=event_sha256,
                        timestamp=timestamp,
                    )
                except (ClaimLoopError, KeyError, TypeError, ValueError) as exc:
                    connection.rollback()
                    raise ClaimLoopStoreError(str(exc)) from exc
                if state.session_id != session_id or state.loop_id != loop_id:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "claim loop state identity differs from its journal envelope"
                    )
                event = load_claim_loop_event_v1(
                    {
                        **event_material,
                        "event_sha256": event_sha256,
                        "resulting_state_sha256": state.state_sha256,
                    }
                )
                if event_type == "OBSERVATION_INGESTED":
                    authority_validator = getattr(
                        self.artifact_interpreter,
                        "validate_recorded_authority_event",
                        None,
                    )
                    if (
                        session_id == "casepath-workspace-claim-loop-v1"
                        and not callable(authority_validator)
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "workspace observation authority verifier is unavailable"
                        )
                    if callable(authority_validator):
                        try:
                            authority_validator(event)
                        except (ClaimLoopError, TypeError, ValueError) as exc:
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "observation authority sidecar is invalid"
                            ) from exc
                connection.execute(
                    """INSERT INTO claim_loop_events
                    (session_id,loop_id,sequence,idempotency_key,command_sha256,event_sha256,event_json,created_at)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        session_id,
                        loop_id,
                        sequence,
                        idempotency_key,
                        command_sha256,
                        event.event_sha256,
                        _json(event.model_dump(mode="json")),
                        timestamp,
                    ),
                )
                if event_type in {"CORRECTION_APPLIED", "CORRECTION_REUSED"}:
                    correction = ScopedCorrection.model_validate(
                        command_value["correction"]
                    )
                    stored = connection.execute(
                        """SELECT correction_json,source_session_id,source_loop_id
                        FROM claim_loop_corrections
                        WHERE correction_id=?""",
                        (correction.correction_id,),
                    ).fetchone()
                    if stored is None or stored["correction_json"] != _json(
                        correction.model_dump(mode="json")
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "correction is not a server-registered immutable receipt"
                        )
                    if event_type == "CORRECTION_APPLIED" and (
                        stored["source_session_id"] != session_id
                        or stored["source_loop_id"] != loop_id
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "local correction source differs from target loop"
                        )
                    if event_type == "CORRECTION_REUSED":
                        reuse = command_value.get("reuse_receipt", {})
                        try:
                            source_application = load_claim_loop_event_v1(
                                command_value.get("source_application_event")
                            )
                        except (ValueError, TypeError) as exc:
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "correction reuse source application is invalid"
                            ) from exc
                        source_event_row = connection.execute(
                            """SELECT * FROM claim_loop_events
                            WHERE session_id=? AND loop_id=? AND event_sha256=?""",
                            (
                                stored["source_session_id"],
                                stored["source_loop_id"],
                                source_application.event_sha256,
                            ),
                        ).fetchone()
                        if (
                            reuse.get("source_loop_id") != stored["source_loop_id"]
                            or command_value.get("source_session_id")
                            != stored["source_session_id"]
                            or source_event_row is None
                            or source_event_row["event_json"]
                            != _json(source_application.model_dump(mode="json"))
                            or source_application.event_type != "CORRECTION_APPLIED"
                            or source_application.command.get("correction", {}).get(
                                "correction_id"
                            )
                            != correction.correction_id
                            or reuse.get("source_application_event_sha256")
                            != source_application.event_sha256
                            or reuse.get("source_application_state_sha256")
                            != source_application.resulting_state_sha256
                        ):
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "correction reuse source binding changed"
                            )
                        source_rows = self._event_rows(
                            connection,
                            stored["source_session_id"],
                            stored["source_loop_id"],
                        )
                        source_prefix = source_rows[: source_application.sequence]
                        if (
                            not source_prefix
                            or source_prefix[-1]["event_sha256"]
                            != source_application.event_sha256
                            or self._replay_rows(
                                source_prefix,
                                session_id=stored["source_session_id"],
                                loop_id=stored["source_loop_id"],
                            ).state_sha256
                            != source_application.resulting_state_sha256
                        ):
                            connection.rollback()
                            raise ClaimLoopStoreError(
                                "correction reuse source journal proof diverged"
                            )
                connection.commit()
        if after_event_commit is not None and not replayed:
            after_event_commit()
        if replayed:
            self.recover(
                session_id=session_id,
                loop_id=loop_id,
                timestamp=timestamp,
            )
        else:
            self._write_checkpoint(
                session_id=session_id,
                loop_id=loop_id,
                state=state,
                timestamp=timestamp,
            )
        receipt = self._receipt(
            loop_id=loop_id,
            idempotency_key=idempotency_key,
            event_sha256=event.event_sha256,
            state=state,
        )
        return state, receipt, replayed

    def append_or_return_protocol_winner(
        self,
        *,
        session_id: str,
        loop_id: str,
        event_type: str,
        event_kind: str,
        client_idempotency_key: str,
        request_sha256: str,
        command: Mapping[str, Any],
        timestamp: str,
        expected_revision: int,
        client_dispatch_guard: Mapping[str, Any] | None = None,
    ) -> tuple[ClaimLoopState, ClaimLoopCommandReceipt | None, bool]:
        """Elect one protocol transition under the journal's strict CAS.

        The store derives the private event key from the complete parent
        request identity.  An existing winner is replayed only after that
        parent binding is revalidated.  Every return carries the current
        canonical journal tail, never a caller-owned or historical snapshot.
        If a different transition advances the journal first, ``receipt`` is
        ``None`` and the caller must rebuild from the returned tail.
        """

        idempotency_key = claim_loop_internal_event_key_v1(
            session_id=session_id,
            loop_id=loop_id,
            client_idempotency_key=client_idempotency_key,
            request_type="insurance_register",
            request_sha256=request_sha256,
            event_kind=event_kind,
        )

        def replay_winner(
            winner: ClaimLoopEvent,
        ) -> tuple[ClaimLoopState, ClaimLoopCommandReceipt | None, bool]:
            if winner.event_type != event_type:
                raise ClaimLoopStoreError(
                    "protocol transition key belongs to another event type"
                )
            winner_command = winner.command
            if event_type in {
                "ACTION_DISPATCH_STARTED",
                "OBSERVATION_INGESTED",
            }:
                bound_key = winner_command.get("client_idempotency_key")
                bound_sha = winner_command.get("client_request_sha256")
                bound_type = winner_command.get("client_request_type")
            else:
                bound_key = winner_command.get("origin_client_idempotency_key")
                bound_sha = winner_command.get("origin_client_request_sha256")
                bound_type = winner_command.get("origin_client_request_type")
            if (
                bound_key != client_idempotency_key
                or bound_sha != request_sha256
                or bound_type != "insurance_register"
            ):
                raise ClaimLoopStoreError(
                    "protocol transition winner changed its parent request"
                )
            _, receipt, replayed = self.append(
                session_id=session_id,
                loop_id=loop_id,
                event_type=event_type,
                idempotency_key=idempotency_key,
                command=winner.command,
                timestamp=winner.created_at,
            )
            canonical, _ = self.snapshot(session_id=session_id, loop_id=loop_id)
            if (
                receipt.loop_id != canonical.loop_id
                or receipt.revision != canonical.revision
                or receipt.state_sha256 != canonical.state_sha256
                or receipt.event_sha256 != canonical.last_event_sha256
            ):
                return canonical, None, False
            return canonical, receipt, replayed

        existing = self.idempotent_event(
            session_id=session_id,
            loop_id=loop_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return replay_winner(existing)
        try:
            appended, receipt, replayed = self.append(
                session_id=session_id,
                loop_id=loop_id,
                event_type=event_type,
                idempotency_key=idempotency_key,
                command=command,
                timestamp=timestamp,
                expected_revision=expected_revision,
                client_dispatch_guard=client_dispatch_guard,
            )
            if replayed:
                canonical, _ = self.snapshot(
                    session_id=session_id,
                    loop_id=loop_id,
                )
                if (
                    receipt.loop_id != canonical.loop_id
                    or receipt.revision != canonical.revision
                    or receipt.state_sha256 != canonical.state_sha256
                    or receipt.event_sha256 != canonical.last_event_sha256
                ):
                    return canonical, None, False
                return canonical, receipt, replayed
            return appended, receipt, replayed
        except ClaimLoopStoreError as exc:
            winner = self.idempotent_event(
                session_id=session_id,
                loop_id=loop_id,
                idempotency_key=idempotency_key,
            )
            if winner is not None:
                try:
                    return replay_winner(winner)
                except ClaimLoopStoreError as replay_exc:
                    raise replay_exc from exc
            if str(exc) == "protocol action receipt differs from registry":
                # A registry outcome can advance between the service's status
                # read and this journal transaction.  In particular, an
                # explicit reconciler may turn COMMIT_CLAIMED/UNKNOWN into a
                # committed receipt while another caller is electing the
                # DISPATCH_UNKNOWN transition.  The stale observation must
                # not become a journal error (or overwrite the winner): return
                # the canonical prefix and force every caller to re-enter from
                # the now-authoritative registry/journal state.
                records = _protocol_record_set(command)
                requested = records.action_receipt if records is not None else None
                canonical = (
                    self.protocol_registry.status(intent=records.intent)
                    if records is not None and self.protocol_registry is not None
                    else None
                )
                outcome_advanced = (
                    requested is not None
                    and canonical is not None
                    and (
                        (
                            requested.status is ActionReceiptStatus.UNKNOWN
                            and canonical.status is ActionReceiptStatus.COMMITTED
                        )
                        or (
                            requested.status is ActionReceiptStatus.CANCELLED
                            and canonical.status
                            in {
                                ActionReceiptStatus.UNKNOWN,
                                ActionReceiptStatus.COMMITTED,
                            }
                        )
                    )
                )
                if outcome_advanced:
                    current, _ = self.snapshot(
                        session_id=session_id,
                        loop_id=loop_id,
                    )
                    return current, None, False
            if str(exc) != "claim loop revision changed":
                raise
            current, _ = self.snapshot(session_id=session_id, loop_id=loop_id)
            return current, None, False

    def recover(
        self, *, session_id: str, loop_id: str, timestamp: str
    ) -> ClaimLoopState:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = self._event_rows(connection, session_id, loop_id)
            state = self._replay_rows(rows, session_id=session_id, loop_id=loop_id)
            self._rebuild_evidence_authority_rows(
                connection,
                rows,
                session_id=session_id,
                loop_id=loop_id,
            )
            self._rebuild_correction_authority_rows(
                connection,
                rows,
                session_id=session_id,
                loop_id=loop_id,
            )
            self._validate_evidence_authority_rows(
                connection,
                rows,
                session_id=session_id,
                loop_id=loop_id,
            )
            row = connection.execute(
                """SELECT * FROM claim_loop_checkpoints
                WHERE session_id=? AND loop_id=?""",
                (session_id, loop_id),
            ).fetchone()
            checkpoint_matches = False
            if row is not None:
                try:
                    prefix = self._checkpoint_prefix_state(
                        row,
                        rows,
                        session_id=session_id,
                        loop_id=loop_id,
                    )
                    checkpoint = ClaimLoopState.model_validate(
                        json.loads(row["state_json"])
                    )
                    checkpoint_json_matches = (
                        checkpoint.state_sha256 == prefix.state_sha256
                        and checkpoint.model_dump(mode="json")
                        == prefix.model_dump(mode="json")
                    )
                except (
                    ClaimLoopStoreError,
                    ValueError,
                    TypeError,
                    json.JSONDecodeError,
                ):
                    checkpoint_json_matches = False
                    prefix = None
                checkpoint_matches = bool(
                    prefix is not None
                    and row["revision"] == state.revision
                    and prefix.state_sha256 == state.state_sha256
                    and checkpoint_json_matches
                )
            connection.commit()
        if row is None or not checkpoint_matches:
            self._write_checkpoint(
                session_id=session_id,
                loop_id=loop_id,
                state=state,
                timestamp=timestamp,
            )
        return state

    def events(self, *, session_id: str, loop_id: str) -> tuple[ClaimLoopEvent, ...]:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = self._event_rows(connection, session_id, loop_id)
            self._replay_rows(rows, session_id=session_id, loop_id=loop_id)
            self._rebuild_evidence_authority_rows(
                connection,
                rows,
                session_id=session_id,
                loop_id=loop_id,
            )
            self._rebuild_correction_authority_rows(
                connection,
                rows,
                session_id=session_id,
                loop_id=loop_id,
            )
            self._validate_evidence_authority_rows(
                connection,
                rows,
                session_id=session_id,
                loop_id=loop_id,
            )
            events = tuple(
                load_claim_loop_event_v1(json.loads(row["event_json"])) for row in rows
            )
            connection.commit()
        return events

    def snapshot(
        self, *, session_id: str, loop_id: str
    ) -> tuple[ClaimLoopState, tuple[ClaimLoopEvent, ...]]:
        """Return one journal-consistent state/event snapshot."""

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = self._event_rows(connection, session_id, loop_id)
            state = self._replay_rows(rows, session_id=session_id, loop_id=loop_id)
            self._rebuild_evidence_authority_rows(
                connection,
                rows,
                session_id=session_id,
                loop_id=loop_id,
            )
            self._rebuild_correction_authority_rows(
                connection,
                rows,
                session_id=session_id,
                loop_id=loop_id,
            )
            self._validate_evidence_authority_rows(
                connection,
                rows,
                session_id=session_id,
                loop_id=loop_id,
            )
            events = tuple(
                load_claim_loop_event_v1(json.loads(row["event_json"])) for row in rows
            )
            connection.commit()
        return state, events

    def snapshots_read_only(
        self,
        *,
        session_id: str,
        loop_ids: tuple[str, ...],
    ) -> dict[str, tuple[ClaimLoopState, tuple[ClaimLoopEvent, ...]]]:
        """Replay several journals in one read transaction without repairing caches.

        Queue projection must never turn a GET into a side-table mutation.  The
        ordinary ``snapshot`` method intentionally rebuilds derived authority
        indexes; this batch surface instead derives exclusively from validated
        append-only event bytes and returns one SQLite-consistent cut.
        """

        if not session_id or any(not value for value in loop_ids):
            raise ClaimLoopStoreError("read-only snapshot identity is invalid")
        unique_loop_ids = tuple(dict.fromkeys(loop_ids))
        if len(unique_loop_ids) != len(loop_ids):
            raise ClaimLoopStoreError("read-only snapshot loop ids are duplicated")
        snapshots: dict[
            str, tuple[ClaimLoopState, tuple[ClaimLoopEvent, ...]]
        ] = {}
        with self.connect() as connection:
            connection.execute("BEGIN")
            for loop_id in unique_loop_ids:
                rows = self._event_rows(connection, session_id, loop_id)
                if not rows:
                    continue
                state = self._replay_rows(
                    rows,
                    session_id=session_id,
                    loop_id=loop_id,
                )
                self._validate_read_only_authority_events(rows)
                events = tuple(
                    load_claim_loop_event_v1(json.loads(row["event_json"]))
                    for row in rows
                )
                snapshots[loop_id] = (state, events)
            connection.commit()
        return snapshots

    def state_prefixes_read_only(
        self,
        *,
        session_id: str,
        loop_ids: tuple[str, ...],
    ) -> dict[str, tuple[ClaimLoopState, dict[str, Any]]]:
        """Return compact validated journal cuts for read-only projections.

        Unlike ``snapshots_read_only`` this surface does not instantiate every
        historical event a second time after replay.  One ordered SQL query
        captures the complete requested roster, the authoritative replay checks
        every row, and the returned prefix contains only the tail facts needed
        by a queue projection.
        """

        if not session_id or any(not value for value in loop_ids):
            raise ClaimLoopStoreError("read-only prefix identity is invalid")
        unique_loop_ids = tuple(dict.fromkeys(loop_ids))
        if len(unique_loop_ids) != len(loop_ids):
            raise ClaimLoopStoreError("read-only prefix loop ids are duplicated")
        if not unique_loop_ids:
            return {}
        with self.connect() as connection:
            connection.execute("BEGIN")
            rows = list(
                connection.execute(
                    """SELECT * FROM claim_loop_events
                    WHERE session_id=? ORDER BY loop_id,sequence""",
                    (session_id,),
                )
            )
            grouped: dict[str, list[sqlite3.Row]] = {
                loop_id: [] for loop_id in unique_loop_ids
            }
            for row in rows:
                loop_id = row["loop_id"]
                if loop_id in grouped:
                    grouped[loop_id].append(row)
            values: dict[str, tuple[ClaimLoopState, dict[str, Any]]] = {}
            for loop_id in unique_loop_ids:
                loop_rows = grouped[loop_id]
                if not loop_rows:
                    continue
                state = self._replay_rows(
                    loop_rows,
                    session_id=session_id,
                    loop_id=loop_id,
                )
                self._validate_read_only_authority_events(loop_rows)
                tail = loop_rows[-1]
                values[loop_id] = (
                    state,
                    {
                        "revision": len(loop_rows),
                        "last_event_sha256": tail["event_sha256"],
                        "last_event_at": tail["created_at"],
                    },
                )
            connection.commit()
        return values

    def state_bytes_prefixes_read_only(
        self,
        *,
        session_id: str,
        loop_ids: tuple[str, ...],
    ) -> dict[str, tuple[bytes, dict[str, Any], str]]:
        """Return exact replayed state bytes and compact journal identities.

        Every call fingerprints every persisted row.  Unchanged fingerprints
        may reuse state bytes produced by an earlier authoritative replay;
        changed bytes force the normal reducer path.  This keeps the 150-claim
        queue read-only and tamper-sensitive without repeatedly constructing
        hundreds of large Pydantic event/state graphs.
        """

        if not session_id or any(not value for value in loop_ids):
            raise ClaimLoopStoreError("read-only state-byte identity is invalid")
        unique_loop_ids = tuple(dict.fromkeys(loop_ids))
        if len(unique_loop_ids) != len(loop_ids):
            raise ClaimLoopStoreError("read-only state-byte loop ids are duplicated")
        if not unique_loop_ids:
            return {}
        with self.connect() as connection:
            connection.execute("BEGIN")
            all_rows = list(
                connection.execute(
                    """SELECT * FROM claim_loop_events
                    WHERE session_id=? ORDER BY loop_id,sequence""",
                    (session_id,),
                )
            )
            grouped: dict[str, list[sqlite3.Row]] = {
                loop_id: [] for loop_id in unique_loop_ids
            }
            for row in all_rows:
                if row["loop_id"] in grouped:
                    grouped[row["loop_id"]].append(row)
            values: dict[str, tuple[bytes, dict[str, Any], str]] = {}
            for loop_id in unique_loop_ids:
                rows = grouped[loop_id]
                if not rows:
                    continue
                fingerprints = tuple(self._row_fingerprint(row) for row in rows)
                roster_digest = hashlib.sha256()
                for fingerprint in fingerprints:
                    roster_digest.update(fingerprint)
                journal_roster_sha256 = roster_digest.hexdigest()
                cache_key = (session_id, loop_id)
                with self._replay_cache_lock:
                    cached = self._replay_cache.get(cache_key)
                    state_bytes = (
                        cached[1]
                        if cached is not None and cached[0] == fingerprints
                        else None
                    )
                if state_bytes is None:
                    state = self._replay_rows(
                        rows,
                        session_id=session_id,
                        loop_id=loop_id,
                    )
                    state_bytes = canonical_json_bytes(state.model_dump(mode="json"))
                self._validate_read_only_authority_events(rows)
                tail = rows[-1]
                values[loop_id] = (
                    state_bytes,
                    {
                        "revision": len(rows),
                        "last_event_sha256": tail["event_sha256"],
                        "last_event_at": tail["created_at"],
                    },
                    journal_roster_sha256,
                )
            connection.commit()
        return values

    def validate_authority_sidecars_read_only(
        self,
        *,
        session_id: str,
        loop_ids: tuple[str, ...],
    ) -> None:
        """Validate external evidence authority for a cached read projection.

        Database-stable queue/detail caches cannot detect a modified external
        admission or rejection receipt. This surface deliberately performs no
        checkpoint or authority-index repair; it only dereferences the
        append-only sidecars named by the requested journals.
        """

        if not session_id or any(not value for value in loop_ids):
            raise ClaimLoopStoreError("read-only authority identity is invalid")
        unique_loop_ids = tuple(dict.fromkeys(loop_ids))
        if len(unique_loop_ids) != len(loop_ids):
            raise ClaimLoopStoreError("read-only authority loop ids are duplicated")
        if not unique_loop_ids:
            return
        requested = frozenset(unique_loop_ids)
        with self.connect() as connection:
            connection.execute("BEGIN")
            rows = [
                row
                for row in connection.execute(
                    """SELECT * FROM claim_loop_events
                    WHERE session_id=? ORDER BY loop_id,sequence""",
                    (session_id,),
                )
                if row["loop_id"] in requested
            ]
            self._validate_read_only_authority_events(rows)
            connection.commit()

    def loop_ids_read_only(self, *, session_id: str) -> tuple[str, ...]:
        """Enumerate the complete fixed-session journal roster without repair."""

        if not session_id:
            raise ClaimLoopStoreError("read-only loop session is invalid")
        with self.connect() as connection:
            connection.execute("BEGIN")
            rows = connection.execute(
                """SELECT DISTINCT loop_id FROM claim_loop_events
                WHERE session_id=? ORDER BY loop_id""",
                (session_id,),
            ).fetchall()
            connection.commit()
        values = tuple(str(row["loop_id"]) for row in rows)
        if any(not value for value in values) or values != tuple(sorted(set(values))):
            raise ClaimLoopStoreError("read-only loop roster is invalid")
        return values

    def state_at_revision(
        self, *, session_id: str, loop_id: str, revision: int
    ) -> ClaimLoopState:
        """Replay one immutable historical journal prefix."""

        if revision < 1:
            raise ClaimLoopStoreError("historical revision must be positive")
        with self.connect() as connection:
            connection.execute("BEGIN")
            rows = self._event_rows(connection, session_id, loop_id)
            if revision > len(rows):
                connection.rollback()
                raise ClaimLoopStoreError("historical revision is outside the journal")
            state = self._replay_rows(
                rows[:revision], session_id=session_id, loop_id=loop_id
            )
            self._validate_evidence_authority_rows(
                connection,
                rows[:revision],
                session_id=session_id,
                loop_id=loop_id,
            )
            connection.commit()
        return state

    def correction(
        self, correction_id: str
    ) -> tuple[ScopedCorrection, str, str] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM claim_loop_corrections WHERE correction_id=?",
                (correction_id,),
            ).fetchone()
        if row is None:
            return None
        correction = ScopedCorrection.model_validate(json.loads(row["correction_json"]))
        if (
            correction.correction_id != row["correction_id"]
            or correction.correction_sha256 != row["correction_sha256"]
        ):
            raise ClaimLoopStoreError("correction database identity diverged")
        return correction, row["source_session_id"], row["source_loop_id"]

    def register_correction_artifact(self, receipt: CorrectionArtifactReceipt) -> None:
        """Admit one server-owned, source-supported correction proposal."""

        raise ClaimLoopStoreError(
            "correction artifacts must be admitted atomically with their correction"
        )

    def correction_artifact(
        self, receipt_sha256: str
    ) -> CorrectionArtifactReceipt | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM claim_loop_correction_artifacts
                WHERE receipt_sha256=?""",
                (receipt_sha256,),
            ).fetchone()
        if row is None:
            return None
        receipt = CorrectionArtifactReceipt.model_validate(
            json.loads(row["artifact_json"])
        )
        if (
            receipt.receipt_sha256 != row["receipt_sha256"]
            or receipt.session_id != row["session_id"]
            or receipt.loop_id != row["loop_id"]
            or receipt.parent_state_sha256 != row["parent_state_sha256"]
        ):
            raise ClaimLoopStoreError("correction artifact database identity diverged")
        return receipt

    def register_correction(
        self,
        *,
        correction_artifact: CorrectionArtifactReceipt,
        correction: ScopedCorrection,
        source_session_id: str,
        source_loop_id: str,
        timestamp: str,
    ) -> None:
        correction_artifact = CorrectionArtifactReceipt.model_validate(
            correction_artifact.model_dump(mode="json")
        )
        correction = ScopedCorrection.model_validate(correction.model_dump(mode="json"))
        value = _json(correction.model_dump(mode="json"))
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                state = self._replay(connection, source_session_id, source_loop_id)
            except ClaimLoopStoreError:
                connection.rollback()
                raise
            correction_artifact_value = _json(
                correction_artifact.model_dump(mode="json")
            )
            correction_artifact_row = connection.execute(
                """SELECT * FROM claim_loop_correction_artifacts
                WHERE receipt_sha256=?""",
                (correction.correction_artifact_receipt_sha256,),
            ).fetchone()
            artifact_row = connection.execute(
                """SELECT artifact_json FROM claim_loop_tool_artifacts
                WHERE receipt_sha256=?""",
                (correction.source_artifact_receipt_sha256,),
            ).fetchone()
            if artifact_row is None:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "correction source artifact is not server-owned"
                )
            if correction_artifact_row is not None and (
                correction_artifact_row["session_id"] != correction_artifact.session_id
                or correction_artifact_row["loop_id"] != correction_artifact.loop_id
                or correction_artifact_row["parent_state_sha256"]
                != correction_artifact.parent_state_sha256
                or correction_artifact_row["artifact_json"] != correction_artifact_value
            ):
                connection.rollback()
                raise ClaimLoopStoreError("correction artifact identity diverged")
            try:
                artifact = ToolArtifactReceipt.model_validate(
                    json.loads(artifact_row["artifact_json"])
                )
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "correction source artifact is invalid"
                ) from exc
            observation = artifact.observation
            effect = correction.effect
            authority_adapter = self.correction_adapters.get(
                correction_artifact.authority_adapter_id
            )
            if (
                authority_adapter is None
                or authority_adapter.adapter_id
                != correction_artifact.authority_adapter_id
                or correction_artifact.issuer_id
                != correction_artifact.authority_adapter_id
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "correction authority adapter is not configured exactly"
                )
            try:
                authority_result = authority_adapter.execute(
                    source_artifact=artifact,
                    state=state,
                    timestamp=correction_artifact.issued_at,
                )
            except (ClaimLoopError, TypeError, ValueError) as exc:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "correction authority cannot reproduce its proposal"
                ) from exc
            if (
                not isinstance(authority_result, CorrectionToolResult)
                or authority_result.effect != effect
                or authority_result.issuer_id != correction_artifact.issuer_id
                or authority_result.issuer_kind != correction_artifact.issuer_kind
                or authority_result.provenance_note
                != correction_artifact.provenance_note
                or authority_result.model_calls != correction_artifact.model_calls
                or authority_result.provider_calls
                != correction_artifact.provider_calls
                or authority_result.provider_credentials_read
                != correction_artifact.provider_credentials_read
                or authority_result.cost_usd != correction_artifact.cost_usd
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "correction authority proposal differs from its configured adapter"
                )
            custom_source_validator = getattr(
                authority_adapter, "validate_correction_source_binding", None
            )
            custom_source_bound = False
            if callable(custom_source_validator):
                try:
                    custom_source_validator(
                        source_artifact=artifact,
                        state=state,
                        correction=correction,
                    )
                except (ClaimLoopError, TypeError, ValueError) as exc:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "correction source binding is invalid"
                    ) from exc
                custom_source_bound = True
            if (
                correction_artifact.receipt_sha256
                != correction.correction_artifact_receipt_sha256
                or correction_artifact.session_id != source_session_id
                or correction_artifact.loop_id != source_loop_id
                or correction_artifact.parent_state_sha256 != state.state_sha256
                or correction_artifact.record_version != state.record_version
                or correction_artifact.source_artifact_receipt_sha256
                != correction.source_artifact_receipt_sha256
                or correction_artifact.source_ref != correction.source_ref
                or correction_artifact.scope != correction.scope
                or correction_artifact.proposed_effect != correction.effect
                or correction_artifact.issued_at != correction.effective_at
                or correction_artifact.expires_at != correction.expires_at
                or correction_artifact.target_claim_id != state.claim_id
                or correction_artifact.target_action_id != artifact.action_id
                or correction_artifact.source_observation_sha256
                != observation.observation_sha256
                or correction_artifact.before_fact_sha256
                != correction_artifact.rollback_fact_sha256
                or correction_artifact.before_evidence_sha256
                != correction_artifact.rollback_evidence_sha256
                or correction_artifact.unrelated_facts_before_sha256
                != correction_artifact.unrelated_facts_after_sha256
                or artifact.receipt_sha256 != correction.source_artifact_receipt_sha256
                or artifact.session_id != source_session_id
                or artifact.loop_id != source_loop_id
                or artifact.artifact_source_version != state.record_version
                or correction.record_version != state.record_version
                or (
                    not custom_source_bound
                    and correction.source_ref not in observation.source_refs
                )
                or correction.scope.claim_ids != (state.claim_id,)
                or correction.scope.fact_ids != (effect.fact_id,)
                or correction.scope.evidence_item_ids != (effect.evidence_item_id,)
                or not any(
                    entry.artifact_receipt_sha256 == artifact.receipt_sha256
                    for entry in state.projection_ledger
                )
                or effect.fact_id != observation.fact_id
                or effect.evidence_item_id != observation.evidence_item_id
                or (
                    effect.fact_state != "known" and effect.normalized_value is not None
                )
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "correction is not derived from its admitted correction artifact"
                )
            projected_ledger = (
                *state.projection_ledger,
                ProjectionLedgerEntry(
                    kind="correction",
                    record_sha256=correction.correction_sha256,
                    artifact_receipt_sha256=(correction.source_artifact_receipt_sha256),
                    recorded_at=correction.effective_at,
                ),
            )
            try:
                projected = project_claim_loop_artifacts_v1(
                    accepted=state.accepted_artifacts,
                    observations=state.observations,
                    corrections=(*state.corrections, correction),
                    projection_ledger=projected_ledger,
                )
                before_fact = next(
                    value
                    for value in state.facts
                    if value.get("fact_id") == effect.fact_id
                )
                before_evidence = next(
                    value
                    for value in state.checklist.get("items", [])
                    if value.get("item_id") == effect.evidence_item_id
                )
                after_fact = next(
                    value
                    for value in projected["facts"]
                    if value.get("fact_id") == effect.fact_id
                )
                after_evidence = next(
                    value
                    for value in projected["checklist"].get("items", [])
                    if value.get("item_id") == effect.evidence_item_id
                )
            except (ClaimLoopError, StopIteration, TypeError, ValueError) as exc:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "correction transition proof cannot be reproduced"
                ) from exc
            unrelated_before = [
                value for value in state.facts if value.get("fact_id") != effect.fact_id
            ]
            unrelated_after = [
                value
                for value in projected["facts"]
                if value.get("fact_id") != effect.fact_id
            ]
            before_fact_sha256 = digest_value(before_fact)
            before_evidence_sha256 = digest_value(before_evidence)
            after_fact_sha256 = digest_value(after_fact)
            after_evidence_sha256 = digest_value(after_evidence)
            if (
                correction_artifact.before_fact_sha256 != before_fact_sha256
                or correction_artifact.before_evidence_sha256 != before_evidence_sha256
                or correction_artifact.expected_after_fact_sha256 != after_fact_sha256
                or correction_artifact.expected_after_evidence_sha256
                != after_evidence_sha256
                or correction_artifact.rollback_fact_sha256 != before_fact_sha256
                or correction_artifact.rollback_evidence_sha256
                != before_evidence_sha256
                or correction_artifact.unrelated_facts_before_sha256
                != digest_value(unrelated_before)
                or correction_artifact.unrelated_facts_after_sha256
                != digest_value(unrelated_after)
                or digest_value(unrelated_before) != digest_value(unrelated_after)
                or (
                    before_fact_sha256 == after_fact_sha256
                    and before_evidence_sha256 == after_evidence_sha256
                )
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "correction transition/locality proof is invalid or a no-op"
                )
            if before_fact.get("controls_process") is True:
                decision_key = before_fact.get("decision_key")
                if effect.fact_state == "known":
                    decision_options = playbook_template_from_accepted_v1(
                        state.accepted_artifacts
                    ).decision_options
                    if effect.normalized_value not in decision_options.get(
                        decision_key, {}
                    ):
                        connection.rollback()
                        raise ClaimLoopStoreError(
                            "correction effect is outside the bounded fact catalog"
                        )
                elif effect.normalized_value is not None:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "non-known correction cannot assert a route value"
                    )
            elif effect.normalized_value is not None:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "non-controlling correction cannot assert a route value"
                )
            if correction.expires_at is not None:
                try:
                    admitted_at = datetime.fromisoformat(
                        timestamp.replace("Z", "+00:00")
                    )
                    expires_at = datetime.fromisoformat(
                        correction.expires_at.replace("Z", "+00:00")
                    )
                except (AttributeError, ValueError) as exc:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "correction admission deadline is invalid"
                    ) from exc
                if (
                    admitted_at.tzinfo is None
                    or expires_at.tzinfo is None
                    or admitted_at >= expires_at
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "correction admission deadline has expired"
                    )
            existing = connection.execute(
                """SELECT correction_json,source_session_id,source_loop_id
                FROM claim_loop_corrections WHERE correction_id=?""",
                (correction.correction_id,),
            ).fetchone()
            if correction_artifact_row is None:
                connection.execute(
                    """INSERT INTO claim_loop_correction_artifacts
                    (receipt_sha256,session_id,loop_id,parent_state_sha256,artifact_json,created_at)
                    VALUES (?,?,?,?,?,?)""",
                    (
                        correction_artifact.receipt_sha256,
                        correction_artifact.session_id,
                        correction_artifact.loop_id,
                        correction_artifact.parent_state_sha256,
                        correction_artifact_value,
                        correction_artifact.issued_at,
                    ),
                )
            if existing is not None:
                if (
                    existing["correction_json"] != value
                    or existing["source_session_id"] != source_session_id
                    or existing["source_loop_id"] != source_loop_id
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError("correction identity changed")
                connection.commit()
                return
            connection.execute(
                """INSERT INTO claim_loop_corrections
                (correction_id,correction_sha256,source_session_id,source_loop_id,correction_json,created_at)
                VALUES (?,?,?,?,?,?)""",
                (
                    correction.correction_id,
                    correction.correction_sha256,
                    source_session_id,
                    source_loop_id,
                    value,
                    timestamp,
                ),
            )
            connection.commit()

    def register_acquisition(
        self,
        receipt: AcquisitionReceiptV1,
        *,
        raw_payload: bytes | None,
    ) -> None:
        """Persist one immutable acquisition before semantic interpretation."""

        receipt = AcquisitionReceiptV1.model_validate(receipt.model_dump(mode="json"))
        value = _json(receipt.model_dump(mode="json"))
        expected_payload = (
            receipt.sanitized_content.encode("utf-8")
            if receipt.status.value == "observed"
            and receipt.sanitized_content is not None
            else None
        )
        if raw_payload != expected_payload:
            raise ClaimLoopStoreError(
                "acquisition raw payload differs from its receipt"
            )
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT * FROM claim_loop_acquisitions
                WHERE receipt_sha256=?""",
                (receipt.receipt_sha256,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["acquisition_json"] != value
                    or existing["raw_payload"] != raw_payload
                    or existing["session_id"] != receipt.session_id
                    or existing["loop_id"] != receipt.loop_id
                    or existing["dispatch_sha256"] != receipt.dispatch_sha256
                    or existing["created_at"] != receipt.acquired_at
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError("acquisition receipt identity changed")
                connection.commit()
                return
            try:
                current = self._replay(connection, receipt.session_id, receipt.loop_id)
            except ClaimLoopStoreError:
                connection.rollback()
                raise
            selected = current.selected_action
            expected_adapter = self.adapter_identities.get(receipt.adapter_id)
            if current.active_dispatch_sha256 != receipt.dispatch_sha256:
                connection.rollback()
                raise ClaimLoopStoreError("acquisition has no active dispatch lease")
            if (
                selected is None
                or selected.action_id != receipt.action_id
                or selected.action_sha256 != receipt.action_sha256
                or selected.bounded_tool_id != receipt.adapter_id
            ):
                connection.rollback()
                raise ClaimLoopStoreError("acquisition selected-action binding changed")
            if receipt.record_version != current.record_version:
                connection.rollback()
                raise ClaimLoopStoreError("acquisition record version changed")
            if expected_adapter != (
                receipt.adapter_implementation_id,
                receipt.adapter_implementation_source_sha256,
                receipt.adapter_implementation_sha256,
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "acquisition adapter implementation is not registered"
                )
            dispatch_row = connection.execute(
                """SELECT created_at,event_json FROM claim_loop_events
                WHERE session_id=? AND loop_id=? AND event_sha256=?""",
                (receipt.session_id, receipt.loop_id, receipt.dispatch_sha256),
            ).fetchone()
            try:
                if dispatch_row is None:
                    raise ValueError("dispatch start event is absent")
                dispatch_event = load_claim_loop_event_v1(
                    json.loads(dispatch_row["event_json"])
                )
                acquired_at = datetime.fromisoformat(
                    receipt.acquired_at.replace("Z", "+00:00")
                )
                dispatched_at = datetime.fromisoformat(
                    dispatch_row["created_at"].replace("Z", "+00:00")
                )
                expires_at = datetime.fromisoformat(
                    current.active_dispatch_expires_at.replace("Z", "+00:00")
                )
            except (AttributeError, TypeError, ValueError) as exc:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "acquisition dispatch timestamp is invalid"
                ) from exc
            if (
                dispatch_event.event_type != "ACTION_DISPATCH_STARTED"
                or dispatch_event.command.get("dispatch_generation")
                != receipt.dispatch_generation
                or dispatch_event.command.get("adapter_id") != receipt.adapter_id
                or any(
                    value.tzinfo is None
                    for value in (acquired_at, dispatched_at, expires_at)
                )
                or acquired_at < dispatched_at
                or acquired_at >= expires_at
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "acquisition is outside its exact dispatch lease"
                )
            dispatch = connection.execute(
                """SELECT acquisition_json FROM claim_loop_acquisitions
                WHERE session_id=? AND loop_id=? AND dispatch_sha256=?""",
                (receipt.session_id, receipt.loop_id, receipt.dispatch_sha256),
            ).fetchone()
            if dispatch is not None:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "dispatch already has a different acquisition receipt"
                )
            connection.execute(
                """INSERT INTO claim_loop_acquisitions
                (receipt_sha256,session_id,loop_id,action_id,dispatch_sha256,
                 status,acquisition_json,raw_payload,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    receipt.receipt_sha256,
                    receipt.session_id,
                    receipt.loop_id,
                    receipt.action_id,
                    receipt.dispatch_sha256,
                    receipt.status.value,
                    value,
                    raw_payload,
                    receipt.acquired_at,
                ),
            )
            connection.commit()

    @staticmethod
    def _acquisition_from_row(row: sqlite3.Row) -> AcquisitionReceiptV1:
        try:
            receipt = AcquisitionReceiptV1.model_validate(
                json.loads(row["acquisition_json"])
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ClaimLoopStoreError("acquisition database row is invalid") from exc
        expected_payload = (
            receipt.sanitized_content.encode("utf-8")
            if receipt.status.value == "observed"
            and receipt.sanitized_content is not None
            else None
        )
        if (
            row["receipt_sha256"] != receipt.receipt_sha256
            or row["session_id"] != receipt.session_id
            or row["loop_id"] != receipt.loop_id
            or row["action_id"] != receipt.action_id
            or row["dispatch_sha256"] != receipt.dispatch_sha256
            or row["status"] != receipt.status.value
            or row["created_at"] != receipt.acquired_at
            or row["raw_payload"] != expected_payload
        ):
            raise ClaimLoopStoreError("acquisition database binding diverged")
        return receipt

    @staticmethod
    def _tool_artifact_from_row(row: sqlite3.Row) -> ToolArtifactReceipt:
        try:
            receipt = ToolArtifactReceipt.model_validate(
                json.loads(row["artifact_json"])
            )
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ClaimLoopStoreError("tool artifact database row is invalid") from exc
        if (
            row["receipt_sha256"] != receipt.receipt_sha256
            or row["session_id"] != receipt.session_id
            or row["loop_id"] != receipt.loop_id
            or row["action_id"] != receipt.action_id
            or row["dispatch_sha256"] != receipt.dispatch_sha256
            or row["created_at"] != receipt.registered_at
        ):
            raise ClaimLoopStoreError("tool artifact row binding diverged")
        return receipt

    def _load_tool_artifact_authority(
        self, connection: sqlite3.Connection, row: sqlite3.Row
    ) -> ToolArtifactReceipt:
        artifact = self._tool_artifact_from_row(row)
        acquisition_row = connection.execute(
            """SELECT * FROM claim_loop_acquisitions
            WHERE receipt_sha256=?""",
            (artifact.acquisition_receipt_sha256,),
        ).fetchone()
        if acquisition_row is None:
            raise ClaimLoopStoreError("tool artifact acquisition authority is absent")
        acquisition = self._acquisition_from_row(acquisition_row)
        if artifact.acquisition_receipt != acquisition:
            raise ClaimLoopStoreError("tool artifact acquisition authority diverged")
        return artifact

    def _validate_read_only_authority_events(
        self, rows: Sequence[sqlite3.Row]
    ) -> None:
        """Dereference external authority sidecars without repairing any row."""

        validator = getattr(
            self.artifact_interpreter,
            "validate_recorded_authority_event",
            None,
        )
        for row in rows:
            try:
                recorded = json.loads(row["event_json"])
                if not isinstance(recorded, dict):
                    raise ClaimLoopStoreError("read-only journal event is invalid")
                if recorded.get("event_type") not in {
                    "OBSERVATION_INGESTED", "EVIDENCE_PROPOSAL_REJECTED"
                }:
                    continue
                event = load_claim_loop_event_v1(recorded)
                if (
                    event.session_id == "casepath-workspace-claim-loop-v1"
                    and event.event_type
                    in {"OBSERVATION_INGESTED", "EVIDENCE_PROPOSAL_REJECTED"}
                    and not callable(validator)
                ):
                    raise ClaimLoopStoreError(
                        "workspace journal authority verifier is unavailable"
                    )
                if not callable(validator):
                    continue
                validator(event)
            except ClaimLoopStoreError:
                raise
            except (ClaimLoopError, TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ClaimLoopStoreError(
                    "read-only journal authority sidecar diverged"
                ) from exc

    def _validate_evidence_authority_rows(
        self,
        connection: sqlite3.Connection,
        rows: Sequence[sqlite3.Row],
        *,
        session_id: str,
        loop_id: str,
    ) -> None:
        """Rejoin every journaled evidence outcome to its raw registry authority."""

        for row in rows:
            try:
                event = load_claim_loop_event_v1(json.loads(row["event_json"]))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ClaimLoopStoreError("claim loop event row is invalid") from exc
            if event.event_type == "OBSERVATION_INGESTED":
                artifact_row = connection.execute(
                    """SELECT * FROM claim_loop_tool_artifacts
                    WHERE receipt_sha256=?""",
                    (event.command.get("artifact_receipt_sha256"),),
                ).fetchone()
                if artifact_row is None:
                    raise ClaimLoopStoreError(
                        "journaled observation artifact authority is absent"
                    )
                artifact = self._load_tool_artifact_authority(connection, artifact_row)
                if (
                    artifact.session_id != session_id
                    or artifact.loop_id != loop_id
                    or event.command.get("action_id") != artifact.action_id
                    or event.command.get("dispatch_sha256") != artifact.dispatch_sha256
                    or event.command.get("tool_artifact_receipt")
                    != artifact.model_dump(mode="json")
                    or event.command.get("observation")
                    != artifact.observation.model_dump(mode="json")
                ):
                    raise ClaimLoopStoreError(
                        "journaled observation authority diverged"
                    )
            elif event.event_type in {
                "EVIDENCE_PROPOSAL_REJECTED",
                "TOOL_UNAVAILABLE",
            }:
                acquisition_row = connection.execute(
                    """SELECT * FROM claim_loop_acquisitions
                    WHERE receipt_sha256=?""",
                    (event.command.get("acquisition_receipt_sha256"),),
                ).fetchone()
                if acquisition_row is None:
                    raise ClaimLoopStoreError(
                        "journaled evidence outcome acquisition authority is absent"
                    )
                acquisition = self._acquisition_from_row(acquisition_row)
                if (
                    acquisition.session_id != session_id
                    or acquisition.loop_id != loop_id
                    or (
                        event.event_type == "TOOL_UNAVAILABLE"
                        and acquisition.status.value == "observed"
                    )
                    or (
                        event.event_type == "EVIDENCE_PROPOSAL_REJECTED"
                        and acquisition.status.value != "observed"
                    )
                    or event.command.get("action_id") != acquisition.action_id
                    or event.command.get("dispatch_sha256")
                    != acquisition.dispatch_sha256
                    or event.command.get("acquisition_receipt")
                    != acquisition.model_dump(mode="json")
                ):
                    raise ClaimLoopStoreError(
                        "journaled evidence outcome authority diverged"
                    )
            if event.event_type in {
                "OBSERVATION_INGESTED",
                "EVIDENCE_PROPOSAL_REJECTED",
            }:
                validator = getattr(
                    self.artifact_interpreter,
                    "validate_recorded_authority_event",
                    None,
                )
                if event.event_type == "EVIDENCE_PROPOSAL_REJECTED" and not callable(
                    validator
                ):
                    raise ClaimLoopStoreError(
                        "journaled evidence rejection authority is unavailable"
                    )
                if (
                    event.session_id == "casepath-workspace-claim-loop-v1"
                    and event.event_type == "OBSERVATION_INGESTED"
                    and not callable(validator)
                ):
                    raise ClaimLoopStoreError(
                        "journaled workspace observation authority is unavailable"
                    )
                if callable(validator):
                    try:
                        validator(event)
                    except (ClaimLoopError, TypeError, ValueError) as exc:
                        raise ClaimLoopStoreError(
                            "journaled evidence authority sidecar diverged"
                        ) from exc

    @staticmethod
    def _rebuild_evidence_authority_rows(
        connection: sqlite3.Connection,
        rows: Sequence[sqlite3.Row],
        *,
        session_id: str,
        loop_id: str,
    ) -> None:
        """Repair derived evidence indexes from the validated event journal.

        Acquisition/tool tables accelerate admission and lookup; once a
        receipt is embedded in a hash-chained event they are no longer a
        second authority.  Missing or corrupted rows are replaced only from
        exact journal bytes after the complete event chain has replayed.
        """

        for row in rows:
            event = load_claim_loop_event_v1(json.loads(row["event_json"]))
            acquisition: AcquisitionReceiptV1 | None = None
            artifact: ToolArtifactReceipt | None = None
            if event.event_type == "OBSERVATION_INGESTED":
                try:
                    artifact = ToolArtifactReceipt.model_validate(
                        event.command.get("tool_artifact_receipt")
                    )
                except (TypeError, ValueError) as exc:
                    raise ClaimLoopStoreError(
                        "journaled observation artifact is invalid"
                    ) from exc
                acquisition = artifact.acquisition_receipt
                if (
                    artifact.session_id != session_id
                    or artifact.loop_id != loop_id
                    or event.command.get("artifact_receipt_sha256")
                    != artifact.receipt_sha256
                    or event.command.get("observation")
                    != artifact.observation.model_dump(mode="json")
                ):
                    raise ClaimLoopStoreError(
                        "journaled observation artifact binding diverged"
                    )
            elif event.event_type in {
                "EVIDENCE_PROPOSAL_REJECTED",
                "TOOL_UNAVAILABLE",
            }:
                try:
                    acquisition = AcquisitionReceiptV1.model_validate(
                        event.command.get("acquisition_receipt")
                    )
                except (TypeError, ValueError) as exc:
                    raise ClaimLoopStoreError(
                        "journaled tool outcome receipt is invalid"
                    ) from exc
                if (
                    acquisition.session_id != session_id
                    or acquisition.loop_id != loop_id
                    or (
                        event.event_type == "EVIDENCE_PROPOSAL_REJECTED"
                        and acquisition.status.value != "observed"
                    )
                    or (
                        event.event_type == "TOOL_UNAVAILABLE"
                        and acquisition.status.value == "observed"
                    )
                    or event.command.get("acquisition_receipt_sha256")
                    != acquisition.receipt_sha256
                ):
                    raise ClaimLoopStoreError("journaled tool outcome binding diverged")
            if acquisition is None:
                continue
            connection.execute(
                """DELETE FROM claim_loop_acquisitions
                WHERE session_id=? AND loop_id=? AND dispatch_sha256=?
                AND receipt_sha256<>?""",
                (
                    session_id,
                    loop_id,
                    acquisition.dispatch_sha256,
                    acquisition.receipt_sha256,
                ),
            )
            connection.execute(
                """INSERT OR REPLACE INTO claim_loop_acquisitions
                (receipt_sha256,session_id,loop_id,action_id,dispatch_sha256,
                 status,acquisition_json,raw_payload,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    acquisition.receipt_sha256,
                    acquisition.session_id,
                    acquisition.loop_id,
                    acquisition.action_id,
                    acquisition.dispatch_sha256,
                    acquisition.status.value,
                    _json(acquisition.model_dump(mode="json")),
                    (
                        acquisition.sanitized_content.encode("utf-8")
                        if acquisition.status.value == "observed"
                        and acquisition.sanitized_content is not None
                        else None
                    ),
                    acquisition.acquired_at,
                ),
            )
            if artifact is None:
                continue
            connection.execute(
                """DELETE FROM claim_loop_tool_artifacts
                WHERE session_id=? AND loop_id=? AND dispatch_sha256=?
                AND receipt_sha256<>?""",
                (
                    session_id,
                    loop_id,
                    artifact.dispatch_sha256,
                    artifact.receipt_sha256,
                ),
            )
            connection.execute(
                """INSERT OR REPLACE INTO claim_loop_tool_artifacts
                (receipt_sha256,session_id,loop_id,action_id,dispatch_sha256,
                 artifact_json,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    artifact.receipt_sha256,
                    artifact.session_id,
                    artifact.loop_id,
                    artifact.action_id,
                    artifact.dispatch_sha256,
                    _json(artifact.model_dump(mode="json")),
                    artifact.registered_at,
                ),
            )

    @staticmethod
    def _rebuild_correction_authority_rows(
        connection: sqlite3.Connection,
        rows: Sequence[sqlite3.Row],
        *,
        session_id: str,
        loop_id: str,
    ) -> None:
        """Repair correction indexes exclusively from hash-chained events."""

        for row in rows:
            event = load_claim_loop_event_v1(json.loads(row["event_json"]))
            if event.event_type not in {"CORRECTION_APPLIED", "CORRECTION_REUSED"}:
                continue
            try:
                correction = ScopedCorrection.model_validate(
                    event.command.get("correction")
                )
                authority = CorrectionArtifactReceipt.model_validate(
                    event.command.get("correction_artifact_receipt")
                )
                source_artifact = ToolArtifactReceipt.model_validate(
                    event.command.get("source_tool_artifact_receipt")
                )
            except (TypeError, ValueError) as exc:
                raise ClaimLoopStoreError(
                    "journaled correction authority is invalid"
                ) from exc
            if event.event_type == "CORRECTION_APPLIED":
                source_session_id = session_id
                source_loop_id = loop_id
            else:
                try:
                    reuse = CorrectionReuseReceipt.model_validate(
                        event.command.get("reuse_receipt")
                    )
                except (TypeError, ValueError) as exc:
                    raise ClaimLoopStoreError(
                        "journaled correction reuse authority is invalid"
                    ) from exc
                source_session_id = reuse.source_session_id
                source_loop_id = reuse.source_loop_id
            if (
                correction.correction_artifact_receipt_sha256
                != authority.receipt_sha256
                or correction.source_artifact_receipt_sha256
                != source_artifact.receipt_sha256
                or authority.source_artifact_receipt_sha256
                != source_artifact.receipt_sha256
                or authority.source_observation_sha256
                != source_artifact.observation.observation_sha256
                or authority.proposed_effect != correction.effect
                or authority.scope != correction.scope
                or authority.source_ref != correction.source_ref
            ):
                raise ClaimLoopStoreError(
                    "journaled correction authority binding diverged"
                )
            acquisition = source_artifact.acquisition_receipt
            connection.execute(
                """DELETE FROM claim_loop_acquisitions
                WHERE session_id=? AND loop_id=? AND dispatch_sha256=?
                AND receipt_sha256<>?""",
                (
                    acquisition.session_id,
                    acquisition.loop_id,
                    acquisition.dispatch_sha256,
                    acquisition.receipt_sha256,
                ),
            )
            connection.execute(
                """INSERT OR REPLACE INTO claim_loop_acquisitions
                (receipt_sha256,session_id,loop_id,action_id,dispatch_sha256,
                 status,acquisition_json,raw_payload,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    acquisition.receipt_sha256,
                    acquisition.session_id,
                    acquisition.loop_id,
                    acquisition.action_id,
                    acquisition.dispatch_sha256,
                    acquisition.status.value,
                    _json(acquisition.model_dump(mode="json")),
                    (
                        acquisition.sanitized_content.encode("utf-8")
                        if acquisition.sanitized_content is not None
                        else None
                    ),
                    acquisition.acquired_at,
                ),
            )
            connection.execute(
                """DELETE FROM claim_loop_tool_artifacts
                WHERE session_id=? AND loop_id=? AND dispatch_sha256=?
                AND receipt_sha256<>?""",
                (
                    source_artifact.session_id,
                    source_artifact.loop_id,
                    source_artifact.dispatch_sha256,
                    source_artifact.receipt_sha256,
                ),
            )
            connection.execute(
                """INSERT OR REPLACE INTO claim_loop_tool_artifacts
                (receipt_sha256,session_id,loop_id,action_id,dispatch_sha256,
                 artifact_json,created_at) VALUES (?,?,?,?,?,?,?)""",
                (
                    source_artifact.receipt_sha256,
                    source_artifact.session_id,
                    source_artifact.loop_id,
                    source_artifact.action_id,
                    source_artifact.dispatch_sha256,
                    _json(source_artifact.model_dump(mode="json")),
                    source_artifact.registered_at,
                ),
            )
            authority_json = _json(authority.model_dump(mode="json"))
            correction_json = _json(correction.model_dump(mode="json"))
            connection.execute(
                """INSERT OR REPLACE INTO claim_loop_correction_artifacts
                (receipt_sha256,session_id,loop_id,parent_state_sha256,
                 artifact_json,created_at) VALUES (?,?,?,?,?,?)""",
                (
                    authority.receipt_sha256,
                    authority.session_id,
                    authority.loop_id,
                    authority.parent_state_sha256,
                    authority_json,
                    authority.issued_at,
                ),
            )
            connection.execute(
                """INSERT OR REPLACE INTO claim_loop_corrections
                (correction_id,correction_sha256,source_session_id,
                 source_loop_id,correction_json,created_at)
                VALUES (?,?,?,?,?,?)""",
                (
                    correction.correction_id,
                    correction.correction_sha256,
                    source_session_id,
                    source_loop_id,
                    correction_json,
                    correction.effective_at,
                ),
            )

    def acquisition(self, receipt_sha256: str) -> AcquisitionReceiptV1 | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM claim_loop_acquisitions
                WHERE receipt_sha256=?""",
                (receipt_sha256,),
            ).fetchone()
        return None if row is None else self._acquisition_from_row(row)

    def acquisition_for_dispatch(
        self, *, session_id: str, loop_id: str, dispatch_sha256: str
    ) -> AcquisitionReceiptV1 | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM claim_loop_acquisitions
                WHERE session_id=? AND loop_id=? AND dispatch_sha256=?""",
                (session_id, loop_id, dispatch_sha256),
            ).fetchone()
        return None if row is None else self._acquisition_from_row(row)

    def register_tool_artifact(self, receipt: ToolArtifactReceipt) -> None:
        receipt = ToolArtifactReceipt.model_validate(receipt.model_dump(mode="json"))
        value = _json(receipt.model_dump(mode="json"))
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT * FROM claim_loop_tool_artifacts
                WHERE receipt_sha256=?""",
                (receipt.receipt_sha256,),
            ).fetchone()
            if existing is not None:
                if (
                    existing["artifact_json"] != value
                    or existing["session_id"] != receipt.session_id
                    or existing["loop_id"] != receipt.loop_id
                    or existing["action_id"] != receipt.action_id
                    or existing["dispatch_sha256"] != receipt.dispatch_sha256
                    or existing["created_at"] != receipt.registered_at
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError("tool artifact receipt identity changed")
                connection.commit()
                return
            try:
                current = self._replay(connection, receipt.session_id, receipt.loop_id)
            except ClaimLoopStoreError:
                connection.rollback()
                raise
            selected = current.selected_action
            acquisition_row = connection.execute(
                """SELECT * FROM claim_loop_acquisitions
                WHERE receipt_sha256=?""",
                (receipt.acquisition_receipt_sha256,),
            ).fetchone()
            if acquisition_row is None:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "tool artifact lacks its persisted acquisition receipt"
                )
            try:
                acquisition = self._acquisition_from_row(acquisition_row)
            except ClaimLoopStoreError:
                connection.rollback()
                raise
            if (
                current.active_dispatch_sha256 != receipt.dispatch_sha256
                or selected is None
                or selected.action_id != receipt.action_id
                or selected.action_sha256 != receipt.action_sha256
                or selected.bounded_tool_id != receipt.adapter_id
                or receipt.artifact_source_version != current.record_version
                or receipt.acquisition_receipt != acquisition
                or acquisition.status.value != "observed"
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "tool artifact is not bound to the active dispatch lease"
                )
            if (
                self.artifact_interpreter is None
                or self.artifact_interpreter.implementation_id
                != receipt.interpretation.implementation
                or self.artifact_interpreter.implementation_source_sha256
                != receipt.interpretation.implementation_source_sha256
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "tool artifact interpreter capability is unavailable"
                )
            try:
                expected_interpretation = self.artifact_interpreter.interpret(
                    action=selected,
                    state=current,
                    acquisition=acquisition,
                )
            except (ClaimLoopError, TypeError, ValueError) as exc:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "tool artifact interpretation is not server-authoritative"
                ) from exc
            if (
                receipt.interpretation != expected_interpretation
                or receipt.observation != expected_interpretation.observation
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "tool artifact interpretation is not server-authoritative"
                )
            observation = receipt.observation
            if (
                observation.fact_id != selected.fact_id
                or observation.evidence_item_id != selected.evidence_item_id
                or observation.evidence_status == "unavailable"
                or not observation.source_refs
            ):
                connection.rollback()
                raise ClaimLoopStoreError(
                    "tool artifact is not bound to the selected obligation"
                )
            custom_source_validator = getattr(
                self.artifact_interpreter,
                "validate_observation_source_binding",
                None,
            )
            if custom_source_validator is not None:
                try:
                    custom_source_validator(
                        action=selected,
                        state=current,
                        acquisition=acquisition,
                        receipt=receipt,
                    )
                except (ClaimLoopError, TypeError, ValueError) as exc:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "tool artifact source binding is invalid"
                    ) from exc
            else:
                if len(observation.source_refs) != 1:
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "default tool artifacts require exactly one source span"
                    )
                source = observation.source_refs[0]
                if (
                    source.adapter_id != receipt.adapter_id
                    or source.locator_kind != "text_quote"
                    or source.source_version != receipt.artifact_source_version
                    or source.page != 1
                    or receipt.artifact_page_count != 1
                    or source.source_sha256
                    != digest_text(receipt.sanitized_content)
                    or source.text_start is None
                    or source.text_end is None
                    or source.text_start < 0
                    or source.text_end > len(receipt.sanitized_content)
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "tool artifact source binding is invalid"
                    )
                span = receipt.sanitized_content[source.text_start : source.text_end]
                if (
                    span != source.sanitized_excerpt
                    or source.span_sha256 != digest_text(span)
                    or observation.value != span
                ):
                    connection.rollback()
                    raise ClaimLoopStoreError(
                        "tool artifact exact span binding is invalid"
                    )
            try:
                registered_at = datetime.fromisoformat(
                    receipt.registered_at.replace("Z", "+00:00")
                )
                expires_at = datetime.fromisoformat(
                    current.active_dispatch_expires_at.replace("Z", "+00:00")
                )
                dispatch_row = connection.execute(
                    """SELECT created_at,event_json FROM claim_loop_events
                    WHERE session_id=? AND loop_id=? AND event_sha256=?""",
                    (
                        receipt.session_id,
                        receipt.loop_id,
                        receipt.dispatch_sha256,
                    ),
                ).fetchone()
                if dispatch_row is None:
                    raise ValueError("dispatch start event is absent")
                dispatch_event = load_claim_loop_event_v1(
                    json.loads(dispatch_row["event_json"])
                )
                if dispatch_event.event_type != "ACTION_DISPATCH_STARTED":
                    raise ValueError("dispatch start event type changed")
                dispatched_at = datetime.fromisoformat(
                    dispatch_row["created_at"].replace("Z", "+00:00")
                )
            except (AttributeError, ValueError) as exc:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "dispatch lease timestamp is invalid"
                ) from exc
            if (
                registered_at.tzinfo is None
                or dispatched_at.tzinfo is None
                or expires_at.tzinfo is None
            ):
                connection.rollback()
                raise ClaimLoopStoreError("dispatch lease timestamp lacks timezone")
            if registered_at < dispatched_at or registered_at >= expires_at:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "tool artifact timestamp is outside the dispatch lease"
                )
            dispatch = connection.execute(
                """SELECT artifact_json FROM claim_loop_tool_artifacts
                WHERE session_id=? AND loop_id=? AND dispatch_sha256=?""",
                (receipt.session_id, receipt.loop_id, receipt.dispatch_sha256),
            ).fetchone()
            if dispatch is not None:
                connection.rollback()
                raise ClaimLoopStoreError(
                    "dispatch already has a different tool artifact"
                )
            connection.execute(
                """INSERT INTO claim_loop_tool_artifacts
                (receipt_sha256,session_id,loop_id,action_id,dispatch_sha256,artifact_json,created_at)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    receipt.receipt_sha256,
                    receipt.session_id,
                    receipt.loop_id,
                    receipt.action_id,
                    receipt.dispatch_sha256,
                    value,
                    receipt.registered_at,
                ),
            )
            connection.commit()

    def tool_artifact(self, receipt_sha256: str) -> ToolArtifactReceipt | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM claim_loop_tool_artifacts
                WHERE receipt_sha256=?""",
                (receipt_sha256,),
            ).fetchone()
            if row is None:
                return None
            receipt = self._load_tool_artifact_authority(connection, row)
            if receipt.receipt_sha256 != receipt_sha256:
                raise ClaimLoopStoreError("tool artifact database identity diverged")
            return receipt

    def tool_artifact_for_dispatch(
        self, *, session_id: str, loop_id: str, dispatch_sha256: str
    ) -> ToolArtifactReceipt | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM claim_loop_tool_artifacts
                WHERE session_id=? AND loop_id=? AND dispatch_sha256=?""",
                (session_id, loop_id, dispatch_sha256),
            ).fetchone()
            if row is None:
                return None
            receipt = self._load_tool_artifact_authority(connection, row)
            if (
                receipt.session_id != session_id
                or receipt.loop_id != loop_id
                or receipt.dispatch_sha256 != dispatch_sha256
            ):
                raise ClaimLoopStoreError("tool artifact row binding diverged")
            return receipt

    def idempotent_event(
        self,
        *,
        session_id: str,
        loop_id: str,
        idempotency_key: str,
    ) -> ClaimLoopEvent | None:
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM claim_loop_events
                WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                (session_id, loop_id, idempotency_key),
            ).fetchone()
        if row is None:
            return None
        event = load_claim_loop_event_v1(json.loads(row["event_json"]))
        if (
            event.session_id != session_id
            or event.loop_id != loop_id
            or event.idempotency_key != idempotency_key
            or event.event_sha256 != row["event_sha256"]
            or event.command_sha256 != row["command_sha256"]
            or event.created_at != row["created_at"]
        ):
            raise ClaimLoopStoreError("idempotent event row binding diverged")
        return event


def deepcopy_json(value: Mapping[str, Any]) -> dict[str, Any]:
    """Reject non-JSON commands and detach caller-owned mutable objects."""

    try:
        return json.loads(canonical_json_bytes(dict(value)))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ClaimLoopStoreError("claim loop command is not canonical JSON") from exc


__all__ = ["ClaimLoopStore", "ClaimLoopStoreError"]
