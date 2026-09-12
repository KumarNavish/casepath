from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from collections.abc import Iterator
from typing import Any

from .live_events import (
    LIVE_EVENT_CONTRACT,
    activity_event,
    terminal_event,
    validate_event_draft,
)


_OPENROUTER_GENERATION_ID_PATTERN = re.compile(r"^gen-[0-9]{10}-[A-Za-z0-9]{20}$")


# These namespaces are owned by server-side product controllers.  Legacy
# caller-scoped reset must never be able to erase them.  Storage accepts
# additional registrations so a future protected controller gets the same
# deletion boundary without another route-specific exception.
SYSTEM_OWNED_SESSION_IDS = frozenset(
    {
        "casepath-workspace-local",
        "casepath-workspace-claim-loop-v1",
    }
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActiveRunResetError(RuntimeError):
    """Raised when session state cannot be reset without orphaning a worker."""

    def __init__(self) -> None:
        super().__init__("Cannot reset session state while a run is active")


class ReservedSessionResetError(RuntimeError):
    """Raised when a legacy reset targets a system-owned journal namespace."""

    def __init__(self) -> None:
        super().__init__("Cannot reset a system-owned session namespace")


class Storage:
    def __init__(
        self,
        path: str | None = None,
        *,
        protected_session_ids: Iterable[str] = (),
    ):
        self.path = Path(
            path
            or os.getenv("CASEPATH_DB_PATH", "/tmp/casepath-useful-demo/casepath.db")
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.stream_condition = threading.Condition()
        self.stream_revisions: dict[str, int] = {}
        self.protected_session_ids = frozenset(
            {*SYSTEM_OWNED_SESSION_IDS, *protected_session_ids}
        )
        self._owned_session_capabilities: dict[str, object] = {}
        self._active_owned_session_writes: ContextVar[frozenset[str]] = ContextVar(
            f"casepath-owned-session-writes-{id(self)}",
            default=frozenset(),
        )
        self.init()

    def connect(self):
        con = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        con.row_factory = sqlite3.Row
        return con

    def init(self):
        with self.connect() as con:
            # State tables created before session isolation cannot safely preserve
            # tenant boundaries. This is generated demo state, so reset only those
            # legacy tables while deliberately retaining the global paid-call ledger.
            state_tables = (
                "runs",
                "events",
                "reviews",
                "memories",
                "candidates",
                "run_stream_events",
            )
            reset_legacy_state = False
            for table in state_tables:
                exists = con.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if exists:
                    columns = {
                        row["name"]
                        for row in con.execute(f"PRAGMA table_info({table})")
                    }
                    if "session_id" not in columns:
                        reset_legacy_state = True
                        break
            if reset_legacy_state:
                con.executescript(
                    "DROP TABLE IF EXISTS events; DROP TABLE IF EXISTS reviews; "
                    "DROP TABLE IF EXISTS memories; DROP TABLE IF EXISTS candidates; "
                    "DROP TABLE IF EXISTS run_stream_events; "
                    "DROP TABLE IF EXISTS runs;"
                )
            con.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    claim_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    claim_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memories (
                    memory_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    claim_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(session_id, claim_id)
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    session_id TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(session_id, candidate_id)
                );
                CREATE TABLE IF NOT EXISTS model_calls (
                    call_id TEXT PRIMARY KEY,
                    run_id TEXT,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    call_count INTEGER NOT NULL,
                    estimated_cost_usd REAL NOT NULL,
                    actual_cost_usd REAL,
                    outcome TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_stream_events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    dedupe_key TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(session_id, run_id, sequence),
                    UNIQUE(session_id, run_id, dedupe_key)
                );
                CREATE INDEX IF NOT EXISTS runs_session ON runs(session_id, updated_at);
                CREATE INDEX IF NOT EXISTS events_session_run ON events(session_id, run_id, ordinal);
                CREATE INDEX IF NOT EXISTS stream_events_session_run ON run_stream_events(session_id, run_id, sequence);
                CREATE INDEX IF NOT EXISTS reviews_session_run ON reviews(session_id, run_id);
                CREATE INDEX IF NOT EXISTS model_calls_cache ON model_calls(cache_key, outcome, updated_at);
                """
            )

    @staticmethod
    def ident(prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(8)}"

    def assert_unowned_session(self, session_id: str) -> None:
        """Reject generic product writes into a server-owned namespace."""

        if (
            session_id in self.protected_session_ids
            and session_id not in self._active_owned_session_writes.get()
        ):
            raise ReservedSessionResetError()

    def _issue_owned_session_write_capability(self, session_id: str) -> object:
        """Bind one opaque writer capability before request handling begins."""

        if (
            session_id not in self.protected_session_ids
            or session_id in self._owned_session_capabilities
        ):
            raise ReservedSessionResetError()
        capability = object()
        self._owned_session_capabilities[session_id] = capability
        return capability

    @contextmanager
    def _owned_session_write_scope(
        self, session_id: str, capability: object
    ) -> Iterator[None]:
        """Activate a construction-bound writer only in this execution context."""

        if self._owned_session_capabilities.get(session_id) is not capability:
            raise ReservedSessionResetError()
        current = self._active_owned_session_writes.get()
        token = self._active_owned_session_writes.set(current | {session_id})
        try:
            yield
        finally:
            self._active_owned_session_writes.reset(token)

    def create_run(
        self,
        claim_id: str,
        *,
        session_id: str = "public",
        run_id: str | None = None,
        source_request_sha256: str | None = None,
        return_existing: bool = False,
    ) -> str:
        self.assert_unowned_session(session_id)
        run_id = run_id or self.ident("run")
        payload = {
            "run_id": run_id,
            "claim_id": claim_id,
            "status": "queued",
            "events": [],
        }
        if source_request_sha256 is not None:
            if not re.fullmatch(r"[0-9a-f]{64}", source_request_sha256):
                raise ValueError("source request identity is invalid")
            payload["source_request_sha256"] = source_request_sha256
        created = False
        with self.lock, self.connect() as con:
            existing = con.execute(
                "SELECT session_id, claim_id, payload FROM runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            if existing is not None:
                existing_payload = json.loads(existing["payload"])
                if (
                    not return_existing
                    or existing["session_id"] != session_id
                    or existing["claim_id"] != claim_id
                    or existing_payload.get("source_request_sha256")
                    != source_request_sha256
                ):
                    raise ValueError("run identity is already bound to another request")
                return run_id
            created_at = now()
            con.execute(
                "INSERT INTO runs (run_id, session_id, claim_id, status, payload, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (
                    run_id,
                    session_id,
                    claim_id,
                    "queued",
                    json.dumps(payload),
                    created_at,
                    created_at,
                ),
            )
            created = True
            self._append_stream_events(
                con,
                run_id=run_id,
                session_id=session_id,
                drafts=[
                    {
                        "dedupe_key": "run:queued",
                        "type": "run.queued",
                        "stage": "queued",
                        "actor": {
                            "type": "deterministic_tool",
                            "id": "run_queue",
                            "label": "Run queue",
                            "model": None,
                        },
                        "acceptance": {"state": "queued"},
                        "entity": {"kind": "run", "id": run_id, "status": "queued"},
                        "links": {"claim_id": claim_id},
                    }
                ],
            )
        if created:
            self._notify_stream(run_id)
        return run_id

    def patch_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        patch: dict[str, Any] | None = None,
        stream_events: list[dict[str, Any]] | None = None,
    ):
        stream_changed = False
        with self.lock, self.connect() as con:
            row = con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            self.assert_unowned_session(str(row["session_id"]))
            payload = json.loads(row["payload"])
            if patch:
                payload.update(patch)
            if status:
                payload["status"] = status
            con.execute(
                "UPDATE runs SET status=?, payload=?, updated_at=? WHERE run_id=?",
                (
                    status or row["status"],
                    json.dumps(payload, ensure_ascii=False),
                    now(),
                    run_id,
                ),
            )
            drafts = list(stream_events or [])
            if status in {"complete", "failed"}:
                drafts.append(terminal_event(status))
            if drafts:
                stream_changed = bool(
                    self._append_stream_events(
                        con,
                        run_id=run_id,
                        session_id=row["session_id"],
                        drafts=drafts,
                    )
                )
        if stream_changed:
            self._notify_stream(run_id)

    def add_event(self, run_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock, self.connect() as con:
            run = con.execute(
                "SELECT session_id FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if not run:
                raise KeyError(run_id)
            session_id = run["session_id"]
            self.assert_unowned_session(str(session_id))
            ordinal = (
                con.execute(
                    "SELECT COUNT(*) FROM events WHERE session_id=? AND run_id=?",
                    (session_id, run_id),
                ).fetchone()[0]
                + 1
            )
            event = {
                "event_id": self.ident("evt"),
                "ordinal": ordinal,
                "created_at": now(),
                **payload,
            }
            con.execute(
                "INSERT INTO events (event_id, session_id, run_id, ordinal, payload, created_at) VALUES (?,?,?,?,?,?)",
                (
                    event["event_id"],
                    session_id,
                    run_id,
                    ordinal,
                    json.dumps(event, ensure_ascii=False),
                    event["created_at"],
                ),
            )
            self._append_stream_events(
                con,
                run_id=run_id,
                session_id=session_id,
                drafts=[activity_event(event)],
            )
        self._notify_stream(run_id)
        return event

    def add_stream_events(
        self, run_id: str, drafts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not drafts:
            return []
        with self.lock, self.connect() as con:
            run = con.execute(
                "SELECT session_id FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if not run:
                raise KeyError(run_id)
            self.assert_unowned_session(str(run["session_id"]))
            persisted = self._append_stream_events(
                con,
                run_id=run_id,
                session_id=run["session_id"],
                drafts=drafts,
            )
        if persisted:
            self._notify_stream(run_id)
        return persisted

    def _append_stream_events(
        self,
        con: sqlite3.Connection,
        *,
        run_id: str,
        session_id: str,
        drafts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        self.assert_unowned_session(session_id)
        if con.execute(
            "SELECT 1 FROM run_stream_events WHERE session_id=? AND run_id=? AND event_type IN ('run.completed', 'run.failed') LIMIT 1",
            (session_id, run_id),
        ).fetchone():
            return []
        sequence = con.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM run_stream_events WHERE session_id=? AND run_id=?",
            (session_id, run_id),
        ).fetchone()[0]
        persisted: list[dict[str, Any]] = []
        for draft in drafts:
            validate_event_draft(draft)
            dedupe_key = draft["dedupe_key"]
            if con.execute(
                "SELECT 1 FROM run_stream_events WHERE session_id=? AND run_id=? AND dedupe_key=?",
                (session_id, run_id, dedupe_key),
            ).fetchone():
                continue
            sequence += 1
            stamp = now()
            event_id = self.ident("liveevt")
            event = {
                "contract": LIVE_EVENT_CONTRACT,
                "event_id": event_id,
                "sequence": sequence,
                "run_id": run_id,
                "occurred_at": stamp,
                **{key: value for key, value in draft.items() if key != "dedupe_key"},
            }
            if (
                event.get("entity", {}).get("kind") == "run"
                and event["entity"].get("id") is None
            ):
                event["entity"]["id"] = run_id
            con.execute(
                "INSERT INTO run_stream_events (event_id, session_id, run_id, sequence, dedupe_key, event_type, payload, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    event_id,
                    session_id,
                    run_id,
                    sequence,
                    dedupe_key,
                    event["type"],
                    json.dumps(event, ensure_ascii=False),
                    stamp,
                ),
            )
            persisted.append(event)
        return persisted

    def stream_events(
        self,
        run_id: str,
        *,
        session_id: str = "public",
        after: int = 0,
    ) -> list[dict[str, Any]]:
        with self.connect() as con:
            return [
                json.loads(row["payload"])
                for row in con.execute(
                    "SELECT payload FROM run_stream_events WHERE session_id=? AND run_id=? AND sequence>? ORDER BY sequence",
                    (session_id, run_id, after),
                )
            ]

    def run_stream_state(
        self, run_id: str, *, session_id: str = "public"
    ) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute(
                "SELECT status, updated_at FROM runs WHERE run_id=? AND session_id=?",
                (run_id, session_id),
            ).fetchone()
            return dict(row) if row else None

    def stream_revision(self, run_id: str) -> int:
        with self.stream_condition:
            return self.stream_revisions.get(run_id, 0)

    def wait_for_stream_change(self, run_id: str, revision: int, timeout: float) -> int:
        with self.stream_condition:
            self.stream_condition.wait_for(
                lambda: self.stream_revisions.get(run_id, 0) != revision,
                timeout=timeout,
            )
            return self.stream_revisions.get(run_id, 0)

    def _notify_stream(self, run_id: str) -> None:
        with self.stream_condition:
            self.stream_revisions[run_id] = self.stream_revisions.get(run_id, 0) + 1
            self.stream_condition.notify_all()

    def get_run(
        self, run_id: str, *, session_id: str = "public"
    ) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute(
                "SELECT * FROM runs WHERE run_id=? AND session_id=?",
                (run_id, session_id),
            ).fetchone()
            if not row:
                return None
            payload = json.loads(row["payload"])
            events = [
                json.loads(r["payload"])
                for r in con.execute(
                    "SELECT payload FROM events WHERE session_id=? AND run_id=? ORDER BY ordinal",
                    (session_id, run_id),
                )
            ]
            return {
                **payload,
                "events": events,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    def save_review(
        self,
        run_id: str,
        claim_id: str,
        payload: dict[str, Any],
        *,
        session_id: str = "public",
    ) -> str:
        self.assert_unowned_session(session_id)
        review_id = self.ident("review")
        with self.lock, self.connect() as con:
            con.execute(
                "INSERT INTO reviews (review_id, session_id, run_id, claim_id, payload, created_at) VALUES (?,?,?,?,?,?)",
                (
                    review_id,
                    session_id,
                    run_id,
                    claim_id,
                    json.dumps(payload, ensure_ascii=False),
                    now(),
                ),
            )
        return review_id

    def get_review_for_run(
        self, run_id: str, *, session_id: str = "public"
    ) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute(
                "SELECT * FROM reviews WHERE run_id=? AND session_id=?",
                (run_id, session_id),
            ).fetchone()
            if not row:
                return None
            return {
                "review_id": row["review_id"],
                "run_id": row["run_id"],
                "claim_id": row["claim_id"],
                **json.loads(row["payload"]),
                "created_at": row["created_at"],
            }

    def update_review(
        self, review_id: str, payload: dict[str, Any], *, session_id: str = "public"
    ) -> None:
        self.assert_unowned_session(session_id)
        with self.lock, self.connect() as con:
            changed = con.execute(
                "UPDATE reviews SET payload=? WHERE review_id=? AND session_id=?",
                (json.dumps(payload, ensure_ascii=False), review_id, session_id),
            ).rowcount
            if changed != 1:
                raise KeyError(review_id)

    def save_memory(
        self, claim_id: str, payload: dict[str, Any], *, session_id: str = "public"
    ) -> str:
        self.assert_unowned_session(session_id)
        with self.lock, self.connect() as con:
            row = con.execute(
                "SELECT memory_id FROM memories WHERE session_id=? AND claim_id=?",
                (session_id, claim_id),
            ).fetchone()
            if row:
                con.execute(
                    "UPDATE memories SET payload=?, updated_at=? WHERE session_id=? AND claim_id=?",
                    (
                        json.dumps(payload, ensure_ascii=False),
                        now(),
                        session_id,
                        claim_id,
                    ),
                )
                return row["memory_id"]
            memory_id = self.ident("memory")
            stamp = now()
            con.execute(
                "INSERT INTO memories (memory_id, session_id, claim_id, payload, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                (
                    memory_id,
                    session_id,
                    claim_id,
                    json.dumps(payload, ensure_ascii=False),
                    stamp,
                    stamp,
                ),
            )
            return memory_id

    def memories(self, *, session_id: str = "public") -> list[dict[str, Any]]:
        with self.connect() as con:
            return [
                {
                    "memory_id": r["memory_id"],
                    "claim_id": r["claim_id"],
                    **json.loads(r["payload"]),
                    "updated_at": r["updated_at"],
                }
                for r in con.execute(
                    "SELECT * FROM memories WHERE session_id=? ORDER BY updated_at DESC",
                    (session_id,),
                )
            ]

    def save_candidate(
        self, candidate_id: str, payload: dict[str, Any], *, session_id: str = "public"
    ):
        self.assert_unowned_session(session_id)
        with self.lock, self.connect() as con:
            row = con.execute(
                "SELECT candidate_id FROM candidates WHERE session_id=? AND candidate_id=?",
                (session_id, candidate_id),
            ).fetchone()
            stamp = now()
            if row:
                con.execute(
                    "UPDATE candidates SET payload=?, updated_at=? WHERE session_id=? AND candidate_id=?",
                    (
                        json.dumps(payload, ensure_ascii=False),
                        stamp,
                        session_id,
                        candidate_id,
                    ),
                )
            else:
                con.execute(
                    "INSERT INTO candidates (session_id, candidate_id, payload, created_at, updated_at) VALUES (?,?,?,?,?)",
                    (
                        session_id,
                        candidate_id,
                        json.dumps(payload, ensure_ascii=False),
                        stamp,
                        stamp,
                    ),
                )

    def persist_review_learning_bundle(
        self,
        *,
        run_id: str,
        claim_id: str,
        session_id: str,
        review_id: str,
        review_payload: dict[str, Any],
        memory_id: str,
        memory_payload: dict[str, Any],
        candidate_id: str,
        candidate_payload: dict[str, Any],
        run_patch: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Commit the accepted review and its learning effects as one transaction."""

        self.assert_unowned_session(session_id)
        with self.lock, self.connect() as con:
            run = con.execute(
                "SELECT * FROM runs WHERE run_id=? AND session_id=?",
                (run_id, session_id),
            ).fetchone()
            if not run or run["claim_id"] != claim_id:
                raise KeyError(run_id)
            stamp = now()
            con.execute(
                "INSERT INTO reviews (review_id, session_id, run_id, claim_id, payload, created_at) VALUES (?,?,?,?,?,?)",
                (
                    review_id,
                    session_id,
                    run_id,
                    claim_id,
                    json.dumps(review_payload, ensure_ascii=False),
                    stamp,
                ),
            )
            existing_memory = con.execute(
                "SELECT memory_id FROM memories WHERE session_id=? AND claim_id=?",
                (session_id, claim_id),
            ).fetchone()
            if existing_memory:
                if existing_memory["memory_id"] != memory_id:
                    raise ValueError("memory_identity_conflict")
                con.execute(
                    "UPDATE memories SET payload=?, updated_at=? WHERE memory_id=?",
                    (json.dumps(memory_payload, ensure_ascii=False), stamp, memory_id),
                )
            else:
                con.execute(
                    "INSERT INTO memories (memory_id, session_id, claim_id, payload, created_at, updated_at) VALUES (?,?,?,?,?,?)",
                    (
                        memory_id,
                        session_id,
                        claim_id,
                        json.dumps(memory_payload, ensure_ascii=False),
                        stamp,
                        stamp,
                    ),
                )
            existing_candidate = con.execute(
                "SELECT candidate_id FROM candidates WHERE session_id=? AND candidate_id=?",
                (session_id, candidate_id),
            ).fetchone()
            if existing_candidate:
                con.execute(
                    "UPDATE candidates SET payload=?, updated_at=? WHERE session_id=? AND candidate_id=?",
                    (
                        json.dumps(candidate_payload, ensure_ascii=False),
                        stamp,
                        session_id,
                        candidate_id,
                    ),
                )
            else:
                con.execute(
                    "INSERT INTO candidates (session_id, candidate_id, payload, created_at, updated_at) VALUES (?,?,?,?,?)",
                    (
                        session_id,
                        candidate_id,
                        json.dumps(candidate_payload, ensure_ascii=False),
                        stamp,
                        stamp,
                    ),
                )
            run_payload = json.loads(run["payload"])
            run_payload.update(run_patch)
            con.execute(
                "UPDATE runs SET payload=?, updated_at=? WHERE run_id=? AND session_id=?",
                (
                    json.dumps(run_payload, ensure_ascii=False),
                    stamp,
                    run_id,
                    session_id,
                ),
            )
            ordinal = con.execute(
                "SELECT COUNT(*) FROM events WHERE session_id=? AND run_id=?",
                (session_id, run_id),
            ).fetchone()[0]
            persisted_events: list[dict[str, Any]] = []
            for payload in events:
                ordinal += 1
                event = {
                    "event_id": self.ident("evt"),
                    "ordinal": ordinal,
                    "created_at": stamp,
                    **payload,
                }
                con.execute(
                    "INSERT INTO events (event_id, session_id, run_id, ordinal, payload, created_at) VALUES (?,?,?,?,?,?)",
                    (
                        event["event_id"],
                        session_id,
                        run_id,
                        ordinal,
                        json.dumps(event, ensure_ascii=False),
                        stamp,
                    ),
                )
                persisted_events.append(event)
                self._append_stream_events(
                    con,
                    run_id=run_id,
                    session_id=session_id,
                    drafts=[activity_event(event)],
                )
        if persisted_events:
            self._notify_stream(run_id)
        return persisted_events

    def candidates(self, *, session_id: str = "public") -> list[dict[str, Any]]:
        with self.connect() as con:
            return [
                {"candidate_id": r["candidate_id"], **json.loads(r["payload"])}
                for r in con.execute(
                    "SELECT * FROM candidates WHERE session_id=? ORDER BY updated_at DESC",
                    (session_id,),
                )
            ]

    def create_model_call(
        self,
        *,
        run_id: str | None,
        provider: str,
        model: str,
        cache_key: str,
        purpose: str,
        call_count: int,
        estimated_cost_usd: float,
        outcome: str,
        provider_endpoint: str | None = None,
        implementation: str | None = None,
        orchestration_id: str | None = None,
        agent_id: str | None = None,
        agent_role: str | None = None,
        parent_call_id: str | None = None,
        delegation_id: str | None = None,
    ) -> str:
        call_id = self.ident("modelcall")
        stamp = now()
        payload = {
            "call_id": call_id,
            "run_id": run_id,
            "provider": provider,
            "provider_endpoint": provider_endpoint,
            "model": model,
            "implementation": implementation,
            "orchestration_id": orchestration_id,
            "agent_id": agent_id,
            "agent_role": agent_role,
            "parent_call_id": parent_call_id,
            "delegation_id": delegation_id,
            "cache_key": cache_key,
            "purpose": purpose,
            "call_count": call_count,
            "estimated_cost_usd": estimated_cost_usd,
            "actual_cost_usd": None,
            "outcome": outcome,
        }
        with self.lock, self.connect() as con:
            con.execute(
                "INSERT INTO model_calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    call_id,
                    run_id,
                    provider,
                    model,
                    cache_key,
                    purpose,
                    call_count,
                    estimated_cost_usd,
                    None,
                    outcome,
                    json.dumps(payload, ensure_ascii=False),
                    stamp,
                    stamp,
                ),
            )
        return call_id

    def finish_model_call(self, call_id: str, *, outcome: str, **patch: Any) -> None:
        with self.lock, self.connect() as con:
            row = con.execute(
                "SELECT * FROM model_calls WHERE call_id=?", (call_id,)
            ).fetchone()
            if not row:
                raise KeyError(call_id)
            payload = json.loads(row["payload"])
            payload.update(patch)
            payload["outcome"] = outcome
            actual_cost = patch.get("actual_cost_usd", row["actual_cost_usd"])
            call_count = patch.get("call_count", row["call_count"])
            if (
                not isinstance(call_count, int)
                or isinstance(call_count, bool)
                or call_count < 0
            ):
                raise ValueError("model call_count must be a nonnegative integer")
            con.execute(
                "UPDATE model_calls SET call_count=?, actual_cost_usd=?, outcome=?, payload=?, updated_at=? WHERE call_id=?",
                (
                    call_count,
                    actual_cost,
                    outcome,
                    json.dumps(payload, ensure_ascii=False),
                    now(),
                    call_id,
                ),
            )

    def model_calls(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            return [
                {
                    **json.loads(row["payload"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
                for row in con.execute(
                    "SELECT payload, created_at, updated_at FROM model_calls ORDER BY created_at, call_id"
                )
            ]

    def sanitized_model_ledger(self) -> list[dict[str, Any]]:
        allowed = {
            "call_id",
            "provider",
            "provider_endpoint",
            "upstream_provider",
            "model",
            "implementation",
            "orchestration_id",
            "agent_id",
            "agent_role",
            "parent_call_id",
            "delegation_id",
            "call_count",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "estimated_cost_usd",
            "actual_cost_usd",
            "latency_ms",
            "cache_key",
            "purpose",
            "outcome",
            "error_type",
            "error_agent_id",
            "error_fact_id",
            "error_invariant",
            "provider_error_code",
            "provider_boundary",
            "expected_upstream_provider",
            "invalid_provenance_field",
            "invalid_provenance_value_hash",
            "ignored_noncontrolling_normalized_proposals",
            "authority_mode",
            "accepted_fact_ids",
            "accepted_fact_count",
            "rejected_facts",
            "rejected_fact_count",
            "source_reference_projection_fact_ids",
            "source_reference_projection_count",
            "accepted_item_ids",
            "accepted_item_count",
            "rejected_items",
            "rejected_item_count",
            "ignored_proposal_count",
            "deterministic_fallback_applied",
            "response_id",
            "origin_call_id",
            "origin_usage",
            "origin_finish_reason",
            "response_model",
            "generation_model",
            "usage_source",
            "metadata_poll_count",
            "metadata_latency_ms",
            "finish_reason",
            "created_at",
            "updated_at",
        }
        sanitized: list[dict[str, Any]] = []
        for call in self.model_calls():
            item = {key: value for key, value in call.items() if key in allowed}
            provider_error_code = item.get("provider_error_code")
            if (
                item.get("error_invariant") != "provider_upstream_rejection"
                or not isinstance(provider_error_code, int)
                or isinstance(provider_error_code, bool)
                or not 0 <= provider_error_code <= 9_999
            ):
                item.pop("provider_error_code", None)
            if item.get("error_invariant") == "provider_upstream_rejection" and (
                not isinstance(item.get("response_id"), str)
                or _OPENROUTER_GENERATION_ID_PATTERN.fullmatch(item["response_id"])
                is None
            ):
                item.pop("response_id", None)
            if (
                item.get("error_invariant") != "provider_upstream_rejection"
                or item.get("provider_boundary") != "openrouter"
            ):
                item.pop("provider_boundary", None)
            if (
                item.get("error_invariant") != "provider_upstream_rejection"
                or item.get("expected_upstream_provider") != "Together"
            ):
                item.pop("expected_upstream_provider", None)
            sanitized.append(item)
        return sanitized

    def cached_model_output(self, cache_key: str) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute(
                """
                SELECT payload FROM model_calls
                WHERE cache_key=? AND outcome IN ('succeeded', 'succeeded_with_guarded_fallback')
                ORDER BY updated_at DESC LIMIT 1
                """,
                (cache_key,),
            ).fetchone()
            if not row:
                return None
            payload = json.loads(row["payload"])
            value = payload.get("canonical_output")
            return value if isinstance(value, dict) else None

    def model_actual_cost_total(self) -> float:
        with self.connect() as con:
            value = con.execute(
                "SELECT COALESCE(SUM(actual_cost_usd), 0) FROM model_calls"
            ).fetchone()[0]
            return float(value or 0)

    def model_cost_committed_or_reserved(self) -> float:
        with self.connect() as con:
            value = con.execute(
                """
                SELECT COALESCE(SUM(
                    CASE
                        WHEN actual_cost_usd IS NOT NULL THEN actual_cost_usd
                        WHEN call_count > 0 AND outcome IN ('started', 'failed', 'succeeded') THEN estimated_cost_usd
                        ELSE 0
                    END
                ), 0)
                FROM model_calls
                """
            ).fetchone()[0]
            return float(value or 0)

    def model_call_summary(self) -> dict[str, Any]:
        calls = self.model_calls()
        unknown_cost_call_count = sum(
            1
            for item in calls
            if int(item.get("call_count", 0)) > 0
            and (
                not isinstance(item.get("actual_cost_usd"), (int, float))
                or isinstance(item.get("actual_cost_usd"), bool)
                or not math.isfinite(float(item["actual_cost_usd"]))
            )
        )
        confirmed_costs = [
            float(item["actual_cost_usd"])
            for item in calls
            if isinstance(item.get("actual_cost_usd"), (int, float))
            and not isinstance(item.get("actual_cost_usd"), bool)
            and math.isfinite(float(item["actual_cost_usd"]))
        ]
        return {
            "records": len(calls),
            "network_calls": sum(int(item.get("call_count", 0)) for item in calls),
            "prompt_tokens": sum(int(item.get("prompt_tokens", 0)) for item in calls),
            "completion_tokens": sum(
                int(item.get("completion_tokens", 0)) for item in calls
            ),
            "total_tokens": sum(int(item.get("total_tokens", 0)) for item in calls),
            "actual_cost_usd": round(sum(confirmed_costs), 8),
            "actual_cost_complete": unknown_cost_call_count == 0,
            "unknown_cost_call_count": unknown_cost_call_count,
            "outcomes": {
                outcome: sum(item.get("outcome") == outcome for item in calls)
                for outcome in sorted({str(item.get("outcome")) for item in calls})
            },
        }

    def reset(self, *, session_id: str = "public") -> dict[str, int]:
        # Enforce this before opening the database or inspecting any row.  The
        # invariant therefore covers every current/future table swept below.
        self.assert_unowned_session(session_id)
        with self.lock, self.connect() as con:
            active_run = con.execute(
                """
                SELECT 1 FROM runs
                WHERE session_id=? AND status IN ('queued', 'running')
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()
            if active_run:
                raise ActiveRunResetError()
            # The model-call ledger is intentionally retained so reset cannot bypass
            # cumulative cost controls or erase model provenance.
            counts = {
                "events": con.execute(
                    "SELECT COUNT(*) FROM events WHERE session_id=?", (session_id,)
                ).fetchone()[0],
                "runs": con.execute(
                    "SELECT COUNT(*) FROM runs WHERE session_id=?", (session_id,)
                ).fetchone()[0],
                "reviews": con.execute(
                    "SELECT COUNT(*) FROM reviews WHERE session_id=?", (session_id,)
                ).fetchone()[0],
                "memories": con.execute(
                    "SELECT COUNT(*) FROM memories WHERE session_id=?", (session_id,)
                ).fetchone()[0],
                "candidates": con.execute(
                    "SELECT COUNT(*) FROM candidates WHERE session_id=?", (session_id,)
                ).fetchone()[0],
            }
            loop_tables = {
                row["name"]
                for row in con.execute(
                    """SELECT name FROM sqlite_master WHERE type='table' AND
                    name IN ('claim_loop_events','claim_loop_checkpoints',
                    'claim_loop_corrections','claim_loop_correction_artifacts',
                    'claim_loop_acquisitions',
                    'claim_loop_tool_artifacts',
                    'claim_loop_client_requests')"""
                )
            }
            for table in sorted(loop_tables):
                column = (
                    "source_session_id"
                    if table == "claim_loop_corrections"
                    else "session_id"
                )
                counts[table] = con.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {column}=?",  # noqa: S608 - closed table/column set
                    (session_id,),
                ).fetchone()[0]
            con.execute(
                "DELETE FROM run_stream_events WHERE session_id=?", (session_id,)
            )
            con.execute("DELETE FROM events WHERE session_id=?", (session_id,))
            con.execute("DELETE FROM runs WHERE session_id=?", (session_id,))
            con.execute("DELETE FROM reviews WHERE session_id=?", (session_id,))
            con.execute("DELETE FROM memories WHERE session_id=?", (session_id,))
            con.execute("DELETE FROM candidates WHERE session_id=?", (session_id,))
            # Claim-loop journals are durable during normal operation but remain
            # session-owned product state.  A session reset must not orphan them.
            if "claim_loop_client_requests" in loop_tables:
                con.execute(
                    "DELETE FROM claim_loop_client_requests WHERE session_id=?",
                    (session_id,),
                )
            if "claim_loop_correction_artifacts" in loop_tables:
                con.execute(
                    "DELETE FROM claim_loop_correction_artifacts WHERE session_id=?",
                    (session_id,),
                )
            if "claim_loop_tool_artifacts" in loop_tables:
                con.execute(
                    "DELETE FROM claim_loop_tool_artifacts WHERE session_id=?",
                    (session_id,),
                )
            if "claim_loop_acquisitions" in loop_tables:
                con.execute(
                    "DELETE FROM claim_loop_acquisitions WHERE session_id=?",
                    (session_id,),
                )
            if "claim_loop_corrections" in loop_tables:
                con.execute(
                    "DELETE FROM claim_loop_corrections WHERE source_session_id=?",
                    (session_id,),
                )
            if "claim_loop_checkpoints" in loop_tables:
                con.execute(
                    "DELETE FROM claim_loop_checkpoints WHERE session_id=?",
                    (session_id,),
                )
            if "claim_loop_events" in loop_tables:
                con.execute(
                    "DELETE FROM claim_loop_events WHERE session_id=?",
                    (session_id,),
                )
            return counts
