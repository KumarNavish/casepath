from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .common import canonical_json_bytes, digest_value


class FoundationPersistenceError(RuntimeError):
    pass


def _json(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def _load(value: str | None) -> Any:
    return None if value is None else json.loads(value)


class PersistentFoundationStore:
    """SQLite authority store for the live foundation lifecycle."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS foundation_sessions (
                    session_id TEXT PRIMARY KEY,
                    active_version_id TEXT,
                    active_snapshot_json TEXT,
                    active_index_sha256 TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS foundation_lifecycles (
                    session_id TEXT NOT NULL,
                    lifecycle_id TEXT NOT NULL,
                    case_id TEXT NOT NULL,
                    candidate_version_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    canonical_json TEXT NOT NULL,
                    canonical_sha256 TEXT NOT NULL,
                    authority_receipt_json TEXT NOT NULL,
                    scan_receipt_json TEXT NOT NULL,
                    boundary_receipt_json TEXT NOT NULL,
                    validation_receipt_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, lifecycle_id)
                );
                CREATE TABLE IF NOT EXISTS foundation_versions (
                    session_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    lifecycle_id TEXT,
                    state TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    provenance_json TEXT NOT NULL,
                    rollback_target TEXT,
                    review_receipt_json TEXT,
                    regression_receipt_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, version_id)
                );
                CREATE TABLE IF NOT EXISTS foundation_state_history (
                    session_id TEXT NOT NULL,
                    history_id TEXT NOT NULL,
                    version_id TEXT NOT NULL,
                    lifecycle_id TEXT,
                    state_before TEXT,
                    state_after TEXT NOT NULL,
                    action TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, history_id)
                );
                CREATE TABLE IF NOT EXISTS foundation_review_nonces (
                    session_id TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    lifecycle_id TEXT NOT NULL,
                    artifact_version TEXT NOT NULL,
                    corrections_sha256 TEXT NOT NULL,
                    principal_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    issued_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    status TEXT NOT NULL,
                    PRIMARY KEY(session_id, nonce)
                );
                CREATE TABLE IF NOT EXISTS foundation_events (
                    session_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    input_sha256 TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    receipt_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, event_id),
                    UNIQUE(session_id, action, idempotency_key)
                );
                CREATE TABLE IF NOT EXISTS foundation_ui_traces (
                    session_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    lifecycle_id TEXT NOT NULL,
                    trace_json TEXT NOT NULL,
                    trace_sha256 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, trace_id)
                );
                CREATE INDEX IF NOT EXISTS foundation_lifecycle_case
                    ON foundation_lifecycles(session_id, case_id);
                CREATE INDEX IF NOT EXISTS foundation_history_version
                    ON foundation_state_history(session_id, version_id);
                """
            )

    def run_idempotent(
        self,
        *,
        session_id: str,
        action: str,
        idempotency_key: str,
        inputs: dict[str, Any],
        timestamp: str,
        operation: Callable[[sqlite3.Connection], dict[str, Any]],
    ) -> tuple[dict[str, Any], bool]:
        input_sha256 = digest_value(inputs)
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT input_sha256, response_json FROM foundation_events
                WHERE session_id=? AND action=? AND idempotency_key=?
                """,
                (session_id, action, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["input_sha256"] != input_sha256:
                    connection.rollback()
                    raise FoundationPersistenceError(
                        "idempotency key was reused with different input"
                    )
                response = _load(existing["response_json"])
                connection.commit()
                return response, True
            response = operation(connection)
            event_payload = {
                "contract": "casepath.foundation-transaction-receipt/1.0.0",
                "session_id": session_id,
                "action": action,
                "idempotency_key": idempotency_key,
                "input_sha256": input_sha256,
                "output_sha256": digest_value(response),
                "timestamp": timestamp,
                "atomic": True,
            }
            event_receipt = {
                **event_payload,
                "receipt_sha256": digest_value(event_payload),
            }
            response = {**response, "transaction_receipt": event_receipt}
            event_id = f"event.{digest_value(event_payload)}"
            connection.execute(
                """
                INSERT INTO foundation_events
                (session_id,event_id,action,idempotency_key,input_sha256,response_json,receipt_sha256,created_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    session_id,
                    event_id,
                    action,
                    idempotency_key,
                    input_sha256,
                    _json(response),
                    event_receipt["receipt_sha256"],
                    timestamp,
                ),
            )
            connection.commit()
            return response, False

    @staticmethod
    def session(
        connection: sqlite3.Connection, session_id: str
    ) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT * FROM foundation_sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return {
            "session_id": row["session_id"],
            "active_version_id": row["active_version_id"],
            "active_snapshot": _load(row["active_snapshot_json"]),
            "active_index_sha256": row["active_index_sha256"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def lifecycle(
        connection: sqlite3.Connection, session_id: str, lifecycle_id: str
    ) -> dict[str, Any] | None:
        row = connection.execute(
            """SELECT * FROM foundation_lifecycles
            WHERE session_id=? AND lifecycle_id=?""",
            (session_id, lifecycle_id),
        ).fetchone()
        if row is None:
            return None
        return {
            "session_id": row["session_id"],
            "lifecycle_id": row["lifecycle_id"],
            "case_id": row["case_id"],
            "candidate_version_id": row["candidate_version_id"],
            "state": row["state"],
            "canonical": _load(row["canonical_json"]),
            "canonical_sha256": row["canonical_sha256"],
            "authority_receipt": _load(row["authority_receipt_json"]),
            "scan_receipt": _load(row["scan_receipt_json"]),
            "boundary_receipt": _load(row["boundary_receipt_json"]),
            "validation_receipt": _load(row["validation_receipt_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    @staticmethod
    def version(
        connection: sqlite3.Connection, session_id: str, version_id: str
    ) -> dict[str, Any] | None:
        row = connection.execute(
            """SELECT * FROM foundation_versions
            WHERE session_id=? AND version_id=?""",
            (session_id, version_id),
        ).fetchone()
        if row is None:
            return None
        return {
            "session_id": row["session_id"],
            "version_id": row["version_id"],
            "lifecycle_id": row["lifecycle_id"],
            "state": row["state"],
            "content": _load(row["content_json"]),
            "content_sha256": row["content_sha256"],
            "provenance": _load(row["provenance_json"]),
            "rollback_target": row["rollback_target"],
            "review_receipt": _load(row["review_receipt_json"]),
            "regression_receipt": _load(row["regression_receipt_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def read_lifecycle(
        self, session_id: str, lifecycle_id: str
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            return self.lifecycle(connection, session_id, lifecycle_id)

    def read_session(self, session_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            return self.session(connection, session_id)

    def audit_export(self, session_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            session = self.session(connection, session_id)
            lifecycles = [
                {
                    "lifecycle_id": row["lifecycle_id"],
                    "case_id": row["case_id"],
                    "candidate_version_id": row["candidate_version_id"],
                    "state": row["state"],
                    "canonical_sha256": row["canonical_sha256"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in connection.execute(
                    """SELECT * FROM foundation_lifecycles
                    WHERE session_id=? ORDER BY lifecycle_id""",
                    (session_id,),
                )
            ]
            versions = [
                {
                    "version_id": row["version_id"],
                    "lifecycle_id": row["lifecycle_id"],
                    "state": row["state"],
                    "content_sha256": row["content_sha256"],
                    "provenance_sha256": digest_value(_load(row["provenance_json"])),
                    "rollback_target": row["rollback_target"],
                    "review_receipt_sha256": (
                        (_load(row["review_receipt_json"]) or {}).get("receipt_sha256")
                    ),
                    "regression_receipt_sha256": (
                        (_load(row["regression_receipt_json"]) or {}).get(
                            "receipt_sha256"
                        )
                    ),
                }
                for row in connection.execute(
                    """SELECT * FROM foundation_versions
                    WHERE session_id=? ORDER BY version_id""",
                    (session_id,),
                )
            ]
            history = [
                _load(row["receipt_json"])
                for row in connection.execute(
                    """SELECT receipt_json FROM foundation_state_history
                    WHERE session_id=? ORDER BY rowid""",
                    (session_id,),
                )
            ]
            events = [
                {
                    "event_id": row["event_id"],
                    "action": row["action"],
                    "idempotency_key": row["idempotency_key"],
                    "input_sha256": row["input_sha256"],
                    "receipt_sha256": row["receipt_sha256"],
                    "created_at": row["created_at"],
                }
                for row in connection.execute(
                    """SELECT * FROM foundation_events
                    WHERE session_id=? ORDER BY rowid""",
                    (session_id,),
                )
            ]
            nonces = [
                {
                    "nonce": row["nonce"],
                    "lifecycle_id": row["lifecycle_id"],
                    "artifact_version": row["artifact_version"],
                    "principal_id": row["principal_id"],
                    "role": row["role"],
                    "status": row["status"],
                }
                for row in connection.execute(
                    """SELECT * FROM foundation_review_nonces
                    WHERE session_id=? ORDER BY nonce""",
                    (session_id,),
                )
            ]
            ui_traces = [
                {
                    "trace_id": row["trace_id"],
                    "lifecycle_id": row["lifecycle_id"],
                    "trace": _load(row["trace_json"]),
                    "trace_sha256": row["trace_sha256"],
                    "created_at": row["created_at"],
                }
                for row in connection.execute(
                    """SELECT * FROM foundation_ui_traces
                    WHERE session_id=? ORDER BY trace_id""",
                    (session_id,),
                )
            ]
        payload = {
            "contract": "casepath.foundation-audit-export/1.0.0",
            "session": session,
            "lifecycles": lifecycles,
            "versions": versions,
            "state_history": history,
            "transactions": events,
            "review_nonces": nonces,
            "ui_api_traces": ui_traces,
        }
        return {**payload, "receipt_sha256": digest_value(payload)}

    def table_counts(self, session_id: str) -> dict[str, int]:
        tables = (
            "foundation_sessions",
            "foundation_lifecycles",
            "foundation_versions",
            "foundation_state_history",
            "foundation_review_nonces",
            "foundation_events",
            "foundation_ui_traces",
        )
        with self.connect() as connection:
            return {
                table: int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE session_id=?",  # noqa: S608
                        (session_id,),
                    ).fetchone()[0]
                )
                for table in tables
            }
