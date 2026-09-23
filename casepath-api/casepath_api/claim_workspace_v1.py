from __future__ import annotations

import base64
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import quote

from .claim_loop_store import ClaimLoopStore
from .claim_workspace_intake_v1 import (
    IntakeCompilationError,
    compile_intake_assessment,
    validate_recorded_intake_assessment,
)
from .storage import Storage
from .workspace_corpus import (
    PublicCorpus,
    WorkspaceCorpusError,
    canonical_json_bytes,
    default_public_corpus_root,
    digest_value,
)


WORKSPACE_SESSION_ID = "casepath-workspace-local"
WORKSPACE_LOOP_PREFIX = "workspace."
EVENT_CONTRACT = "casepath.claim-workspace-journal-event/1.0.0"
STATE_CONTRACT = "casepath.claim-workspace-state/1.0.0"
QUEUE_CONTRACT = "casepath.claim-queue-projection/1.0.0"
QUEUE_CONTRACT_V2 = "casepath.claim-queue-projection/2.0.0"
SEED_RECEIPT_CONTRACT = "casepath.claim-workspace-seed/1.0.0"
REBUILD_RECEIPT_CONTRACT = "casepath.claim-queue-rebuild/1.0.0"
EVENT_TYPES = {
    "WORKSPACE_CLAIM_IMPORTED",
    "WORKSPACE_OWNER_ASSIGNED",
    "WORKSPACE_PROCESSING_STARTED",
    "WORKSPACE_UNKNOWN_RECONCILED",
}
SORT_MODES = {
    "priority",
    "urgency",
    "oldest_waiting",
    "nearest_deadline",
    "most_decision_ready",
    "latest_update",
}


class ClaimWorkspaceError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ClaimWorkspaceError("workspace timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise ClaimWorkspaceError("workspace timestamp lacks a timezone")
    return parsed.astimezone(timezone.utc)


def _state_material(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "state_sha256"}


def _validated_state(value: Mapping[str, Any]) -> dict[str, Any]:
    state = dict(value)
    required = {
        "contract",
        "claim_id",
        "loop_id",
        "binding",
        "static_template_sha256",
        "intake_assessment",
        "owner",
        "workflow_state",
        "readiness_state",
        "claim_type",
        "deadline_at",
        "principal_blocker",
        "pending_evidence_count",
        "next_safe_action",
        "failure_or_unknown_effect",
        "revision",
        "last_event_sha256",
        "last_authoritative_update",
        "state_sha256",
    }
    if (
        set(state) != required
        or state.get("contract") != STATE_CONTRACT
        or not isinstance(state.get("claim_id"), str)
        or state.get("loop_id") != WORKSPACE_LOOP_PREFIX + state["claim_id"]
        or not isinstance(state.get("binding"), dict)
        or state["binding"].get("claim_id") != state["claim_id"]
        or state.get("static_template_sha256")
        != state["binding"].get("static_template_sha256")
        or state.get("workflow_state")
        not in {"received", "in_review", "waiting", "failed"}
        or state.get("readiness_state")
        not in {"not_assessed", "blocked", "decision_ready", "safe_abstention"}
        or state.get("claim_type")
        not in {
            "unclassified_intake",
            "defect_mold_heating",
            "lease_termination_dispute",
            "rent_increase_dispute",
        }
        or (
            state.get("intake_assessment") is None
            and state.get("claim_type") != "unclassified_intake"
        )
        or (
            state.get("intake_assessment") is not None
            and (
                not isinstance(state["intake_assessment"], dict)
                or state["intake_assessment"].get("claim_type")
                != state.get("claim_type")
                or state["intake_assessment"].get("assessment_sha256")
                != digest_value(
                    {
                        key: item
                        for key, item in state["intake_assessment"].items()
                        if key != "assessment_sha256"
                    }
                )
            )
        )
        or state.get("deadline_at") is not None
        or (
            state.get("pending_evidence_count") is not None
            and (
                type(state["pending_evidence_count"]) is not int
                or state["pending_evidence_count"] < 0
            )
        )
        or type(state.get("failure_or_unknown_effect")) is not bool
        or type(state.get("revision")) is not int
        or state["revision"] < 1
        or state.get("state_sha256") != digest_value(_state_material(state))
    ):
        raise ClaimWorkspaceError("workspace state is invalid")
    _parse_time(state["last_authoritative_update"])
    return state


def _with_hash(material: Mapping[str, Any]) -> dict[str, Any]:
    value = _copy(material)
    return {**value, "state_sha256": digest_value(value)}


def _reduce(
    current: Mapping[str, Any] | None,
    *,
    event_type: str,
    command: Mapping[str, Any],
    sequence: int,
    event_sha256: str,
    timestamp: str,
    corpus: PublicCorpus,
    expected_claim_id: str,
    expected_loop_id: str,
) -> dict[str, Any]:
    if event_type not in EVENT_TYPES:
        raise ClaimWorkspaceError("workspace event type is invalid")
    _parse_time(timestamp)
    if current is None:
        if event_type != "WORKSPACE_CLAIM_IMPORTED" or sequence != 1:
            raise ClaimWorkspaceError("workspace journal must begin with import")
        if set(command) != {"binding", "corpus_identity", "request_expected_revision"}:
            raise ClaimWorkspaceError("workspace import command is invalid")
        binding = command.get("binding")
        corpus_identity = command.get("corpus_identity")
        try:
            expected_binding = corpus.binding(expected_claim_id)
        except WorkspaceCorpusError as exc:
            raise ClaimWorkspaceError("workspace import binding is invalid") from exc
        if (
            not isinstance(binding, dict)
            or not isinstance(corpus_identity, dict)
            or binding.get("binding_sha256")
            != digest_value(
                {key: item for key, item in binding.items() if key != "binding_sha256"}
            )
            or binding.get("static_template_sha256")
            != corpus_identity.get("static_template_sha256")
            or command.get("request_expected_revision") != 0
            or binding != expected_binding
            or corpus_identity != corpus.identity
            or binding.get("claim_id") != expected_claim_id
        ):
            raise ClaimWorkspaceError("workspace import binding is invalid")
        material = {
            "contract": STATE_CONTRACT,
            "claim_id": binding["claim_id"],
            "loop_id": expected_loop_id,
            "binding": _copy(binding),
            "static_template_sha256": binding["static_template_sha256"],
            "intake_assessment": None,
            "owner": None,
            "workflow_state": "received",
            "readiness_state": "not_assessed",
            "claim_type": "unclassified_intake",
            "deadline_at": None,
            "principal_blocker": "Deterministic assessment has not started",
            "pending_evidence_count": None,
            "next_safe_action": "Start deterministic assessment",
            "failure_or_unknown_effect": False,
            "revision": sequence,
            "last_event_sha256": event_sha256,
            "last_authoritative_update": timestamp,
        }
        return _validated_state(_with_hash(material))

    state = _validated_state(current)
    if state["claim_id"] != expected_claim_id or state["loop_id"] != expected_loop_id:
        raise ClaimWorkspaceError("workspace state belongs to another journal")
    if sequence != state["revision"] + 1:
        raise ClaimWorkspaceError("workspace journal sequence is discontinuous")
    if (
        type(command.get("request_expected_revision")) is not int
        or command["request_expected_revision"] != state["revision"]
    ):
        raise ClaimWorkspaceError("workspace mutation is not bound to its parent revision")
    material = _state_material(state)
    material.update(
        {
            "revision": sequence,
            "last_event_sha256": event_sha256,
            "last_authoritative_update": timestamp,
        }
    )
    if event_type == "WORKSPACE_OWNER_ASSIGNED":
        if set(command) != {"owner", "request_expected_revision"}:
            raise ClaimWorkspaceError("owner command is invalid")
        owner = command.get("owner")
        if not isinstance(owner, str) or not 1 <= len(owner.strip()) <= 80:
            raise ClaimWorkspaceError("owner is invalid")
        material["owner"] = owner.strip()
    elif event_type == "WORKSPACE_PROCESSING_STARTED":
        if set(command) != {
            "expected_binding_sha256",
            "intake_assessment",
            "request_expected_revision",
        } or command.get(
            "expected_binding_sha256"
        ) != state["binding"]["binding_sha256"]:
            raise ClaimWorkspaceError("processing command is stale")
        if state["failure_or_unknown_effect"]:
            raise ClaimWorkspaceError("unknown effect must be reconciled before processing")
        if state["workflow_state"] == "in_review":
            raise ClaimWorkspaceError("deterministic assessment already started")
        try:
            assessment = validate_recorded_intake_assessment(
                command["intake_assessment"],
                corpus=corpus,
                claim_id=state["claim_id"],
            )
        except (IntakeCompilationError, WorkspaceCorpusError) as exc:
            raise ClaimWorkspaceError("processing assessment is not source-bound") from exc
        node = assessment["current_node"]
        material.update(
            {
                "workflow_state": "in_review",
                "readiness_state": "blocked",
                "claim_type": assessment["claim_type"],
                "intake_assessment": assessment,
                "principal_blocker": (
                    f"{node['label']} is not yet established from admitted evidence"
                ),
                "next_safe_action": node["label"],
            }
        )
    elif event_type == "WORKSPACE_UNKNOWN_RECONCILED":
        if set(command) != {"prior_state_sha256", "request_expected_revision"} or command.get(
            "prior_state_sha256"
        ) != state["state_sha256"]:
            raise ClaimWorkspaceError("reconciliation command is stale")
        if not state["failure_or_unknown_effect"]:
            raise ClaimWorkspaceError("claim has no unknown effect to reconcile")
        material["failure_or_unknown_effect"] = False
        material["workflow_state"] = "waiting"
        material["principal_blocker"] = "Unknown effect reconciled; review required"
        material["next_safe_action"] = "Resume deterministic assessment"
    elif event_type == "WORKSPACE_CLAIM_IMPORTED":
        raise ClaimWorkspaceError("claim import cannot repeat inside one journal")
    return _validated_state(_with_hash(material))


class ClaimWorkspaceStore:
    """Workspace events in the existing ClaimLoop journal table.

    The queue is deliberately computed from this hash chain. No workspace table,
    browser state, or cached row can authorize a claim mutation.
    """

    def __init__(self, storage: Storage, corpus: PublicCorpus):
        self.storage = storage
        self.journal = ClaimLoopStore(storage.path)
        self.corpus = corpus
        self._replay_cache_lock = RLock()
        self._replay_cache: dict[str, tuple[tuple[bytes, ...], bytes]] = {}
        self._state_roster_cache: tuple[tuple[bytes, ...], str, bytes] | None = None

    @classmethod
    def open_read_only(
        cls, path: str | Path, corpus: PublicCorpus
    ) -> ClaimWorkspaceStore:
        """Open an existing journal without initialization or repair writes."""

        supplied_path = Path(path)
        if supplied_path.is_symlink():
            raise ClaimWorkspaceError("read-only replay database is not a regular file")
        database_path = supplied_path.resolve()
        if database_path.is_symlink() or not database_path.is_file():
            raise ClaimWorkspaceError("read-only replay database is not a regular file")

        class _ReadOnlyJournal:
            def __init__(self, value: Path):
                self.path = value

            def connect(self) -> sqlite3.Connection:
                uri = f"file:{quote(str(self.path), safe='/')}?mode=ro"
                connection = sqlite3.connect(
                    uri,
                    uri=True,
                    timeout=30,
                    isolation_level=None,
                )
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA query_only=ON")
                return connection

        value = cls.__new__(cls)
        value.storage = None
        value.journal = _ReadOnlyJournal(database_path)
        value.corpus = corpus
        value._replay_cache_lock = RLock()
        value._replay_cache = {}
        value._state_roster_cache = None
        return value

    @staticmethod
    def _row_fingerprint(row: sqlite3.Row) -> bytes:
        """Bind every persisted workspace-journal column for cache reuse."""

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

    def _rows(
        self, connection: sqlite3.Connection, *, loop_id: str | None = None
    ) -> list[sqlite3.Row]:
        if loop_id is None:
            return list(
                connection.execute(
                    """SELECT * FROM claim_loop_events
                    WHERE session_id=? AND loop_id LIKE ?
                    ORDER BY loop_id,sequence""",
                    (WORKSPACE_SESSION_ID, WORKSPACE_LOOP_PREFIX + "%"),
                )
            )
        return list(
            connection.execute(
                """SELECT * FROM claim_loop_events
                WHERE session_id=? AND loop_id=? ORDER BY sequence""",
                (WORKSPACE_SESSION_ID, loop_id),
            )
        )

    @staticmethod
    def _event_material(event: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: item
            for key, item in event.items()
            if key not in {"event_sha256", "resulting_state_sha256"}
        }

    def _replay_rows(self, rows: Iterable[sqlite3.Row]) -> dict[str, Any]:
        state: dict[str, Any] | None = None
        previous: str | None = None
        expected_sequence = 1
        for row in rows:
            try:
                event = json.loads(row["event_json"])
            except (TypeError, json.JSONDecodeError) as exc:
                raise ClaimWorkspaceError("workspace journal JSON is invalid") from exc
            required = {
                "contract",
                "session_id",
                "loop_id",
                "sequence",
                "previous_event_sha256",
                "event_type",
                "idempotency_key",
                "command_sha256",
                "command",
                "created_at",
                "event_sha256",
                "resulting_state_sha256",
            }
            if (
                not isinstance(event, dict)
                or set(event) != required
                or event.get("contract") != EVENT_CONTRACT
                or event.get("session_id") != WORKSPACE_SESSION_ID
                or event.get("loop_id") != row["loop_id"]
                or event.get("sequence") != expected_sequence
                or event.get("previous_event_sha256") != previous
                or event.get("event_type") not in EVENT_TYPES
                or event.get("command_sha256") != digest_value(event.get("command"))
                or event.get("event_sha256")
                != digest_value(self._event_material(event))
                or row["event_sha256"] != event["event_sha256"]
                or row["command_sha256"] != event["command_sha256"]
                or row["sequence"] != event["sequence"]
                or row["idempotency_key"] != event["idempotency_key"]
            ):
                raise ClaimWorkspaceError("workspace journal chain is invalid")
            state = _reduce(
                state,
                event_type=event["event_type"],
                command=event["command"],
                sequence=event["sequence"],
                event_sha256=event["event_sha256"],
                timestamp=event["created_at"],
                corpus=self.corpus,
                expected_claim_id=event["loop_id"][len(WORKSPACE_LOOP_PREFIX) :],
                expected_loop_id=event["loop_id"],
            )
            if state["state_sha256"] != event["resulting_state_sha256"]:
                raise ClaimWorkspaceError("workspace journal state hash differs")
            previous = event["event_sha256"]
            expected_sequence += 1
        if state is None:
            raise ClaimWorkspaceError("workspace claim does not exist")
        return state

    def recover(self, claim_id: str) -> dict[str, Any]:
        loop_id = WORKSPACE_LOOP_PREFIX + claim_id
        with self.journal.connect() as connection:
            return self._replay_rows(self._rows(connection, loop_id=loop_id))

    def state_at_revision(self, claim_id: str, revision: int) -> dict[str, Any]:
        """Replay one immutable workspace-journal prefix without repair."""

        if type(revision) is not int or revision < 1:
            raise ClaimWorkspaceError("workspace historical revision is invalid")
        loop_id = WORKSPACE_LOOP_PREFIX + claim_id
        with self.journal.connect() as connection:
            rows = self._rows(connection, loop_id=loop_id)
            if revision > len(rows):
                raise ClaimWorkspaceError("workspace historical revision is absent")
            return self._replay_rows(rows[:revision])

    def replay_processing_start(
        self,
        *,
        claim_id: str,
        idempotency_key: str,
        expected_revision: int,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        """Return an accepted start before invoking today's compiler.

        Server-derived assessment bytes are deliberately not part of the
        caller's request identity. A later compiler version therefore cannot
        invalidate an exact retry of an already accepted request.
        """

        if type(expected_revision) is not int or expected_revision < 1:
            raise ClaimWorkspaceError("workspace expected revision is required")
        loop_id = WORKSPACE_LOOP_PREFIX + claim_id
        with self.journal.connect() as connection:
            existing = connection.execute(
                """SELECT * FROM claim_loop_events
                WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                (WORKSPACE_SESSION_ID, loop_id, idempotency_key),
            ).fetchone()
            if existing is None:
                return None
            event = json.loads(existing["event_json"])
            command = event.get("command")
            if (
                event.get("event_type") != "WORKSPACE_PROCESSING_STARTED"
                or not isinstance(command, dict)
                or command.get("request_expected_revision") != expected_revision
            ):
                raise ClaimWorkspaceError(
                    "idempotency key was reused with different input"
                )
            rows = self._rows(connection, loop_id=loop_id)[: existing["sequence"]]
            return self._replay_rows(rows), event

    def all_states(self) -> list[dict[str, Any]]:
        # Corpus bytes were fully hashed at admission.  This closed-inventory
        # token is checked before and after the SQLite snapshot, so cached
        # semantic states never conceal source replacement or path drift.
        corpus_identity = getattr(
            self.corpus, "observed_runtime_identity_token", self.corpus.runtime_identity_token
        )
        corpus_token = corpus_identity()
        with self.journal.connect() as connection:
            connection.execute("BEGIN")
            grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
            for row in self._rows(connection):
                grouped[row["loop_id"]].append(row)
            roster_fingerprints = tuple(
                self._row_fingerprint(row)
                for loop_id in sorted(grouped)
                for row in grouped[loop_id]
            )
            with self._replay_cache_lock:
                roster_cached = self._state_roster_cache
                roster_bytes = (
                    roster_cached[2]
                    if roster_cached is not None
                    and roster_cached[0] == roster_fingerprints
                    and roster_cached[1] == corpus_token
                    else None
                )
            if roster_bytes is not None:
                connection.commit()
                if corpus_identity() != corpus_token:  # pragma: no cover
                    raise ClaimWorkspaceError(
                        "public corpus changed during workspace replay"
                    )
                return json.loads(roster_bytes)
            values: list[dict[str, Any]] = []
            for loop_id in sorted(grouped):
                rows = grouped[loop_id]
                fingerprints = tuple(self._row_fingerprint(row) for row in rows)
                with self._replay_cache_lock:
                    cached = self._replay_cache.get(loop_id)
                    state_bytes = (
                        cached[1]
                        if cached is not None and cached[0] == fingerprints
                        else None
                    )
                if state_bytes is None:
                    state = self._replay_rows(rows)
                    state_bytes = canonical_json_bytes(state)
                    with self._replay_cache_lock:
                        self._replay_cache[loop_id] = (fingerprints, state_bytes)
                values.append(json.loads(state_bytes))
            connection.commit()
        if corpus_identity() != corpus_token:  # pragma: no cover
            raise ClaimWorkspaceError("public corpus changed during workspace replay")
        with self._replay_cache_lock:
            self._state_roster_cache = (
                roster_fingerprints,
                corpus_token,
                canonical_json_bytes(values),
            )
        return values

    def append(
        self,
        *,
        claim_id: str,
        event_type: str,
        idempotency_key: str,
        command: Mapping[str, Any],
        timestamp: str,
        expected_revision: int | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any], bool]:
        if not isinstance(idempotency_key, str) or not 8 <= len(idempotency_key) <= 128:
            raise ClaimWorkspaceError("idempotency key is invalid")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ClaimWorkspaceError("workspace expected revision is required")
        loop_id = WORKSPACE_LOOP_PREFIX + claim_id
        command_value = _copy(command)
        command_sha256 = digest_value(command_value)
        with self.journal.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """SELECT * FROM claim_loop_events
                WHERE session_id=? AND loop_id=? AND idempotency_key=?""",
                (WORKSPACE_SESSION_ID, loop_id, idempotency_key),
            ).fetchone()
            if existing is not None:
                if existing["command_sha256"] != command_sha256:
                    connection.rollback()
                    raise ClaimWorkspaceError(
                        "idempotency key was reused with different input"
                    )
                event = json.loads(existing["event_json"])
                if event.get("event_type") != event_type:
                    connection.rollback()
                    raise ClaimWorkspaceError(
                        "idempotency key was reused for a different event type"
                    )
                rows = self._rows(connection, loop_id=loop_id)[: existing["sequence"]]
                state = self._replay_rows(rows)
                connection.commit()
                return state, event, True
            rows = self._rows(connection, loop_id=loop_id)
            current = self._replay_rows(rows) if rows else None
            current_revision = current["revision"] if current else 0
            if expected_revision != current_revision:
                connection.rollback()
                raise ClaimWorkspaceError("workspace revision is stale")
            sequence = current_revision + 1
            previous = current["last_event_sha256"] if current else None
            event_material = {
                "contract": EVENT_CONTRACT,
                "session_id": WORKSPACE_SESSION_ID,
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
            state = _reduce(
                current,
                event_type=event_type,
                command=command_value,
                sequence=sequence,
                event_sha256=event_sha256,
                timestamp=timestamp,
                corpus=self.corpus,
                expected_claim_id=claim_id,
                expected_loop_id=loop_id,
            )
            if state["loop_id"] != loop_id or state["claim_id"] != claim_id:
                connection.rollback()
                raise ClaimWorkspaceError("workspace event produced a foreign state")
            event = {
                **event_material,
                "event_sha256": event_sha256,
                "resulting_state_sha256": state["state_sha256"],
            }
            connection.execute(
                """INSERT INTO claim_loop_events
                (session_id,loop_id,sequence,idempotency_key,command_sha256,
                 event_sha256,event_json,created_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    WORKSPACE_SESSION_ID,
                    loop_id,
                    sequence,
                    idempotency_key,
                    command_sha256,
                    event_sha256,
                    canonical_json_bytes(event).decode("utf-8"),
                    timestamp,
                ),
            )
            connection.commit()
            return state, event, False


def _urgency(received_at: str, now: str) -> tuple[str, int, int]:
    age_days = max(0, int((_parse_time(now) - _parse_time(received_at)).total_seconds() // 86400))
    if age_days >= 30:
        return "high", 3, age_days
    if age_days >= 14:
        return "elevated", 2, age_days
    return "normal", 1, age_days


def _row(
    state: Mapping[str, Any],
    *,
    now: str,
    operational_projection: Mapping[str, Any] | None = None,
    validate_projection_hash: bool = True,
) -> dict[str, Any]:
    binding = state["binding"]
    if operational_projection is not None:
        projection = dict(operational_projection)
        projection_material = {
            key: item for key, item in projection.items() if key != "projection_sha256"
        }
        workspace_prefix = projection.get("workspace_prefix")
        next_state = projection.get("next_state")
        if (
            projection.get("contract")
            != "casepath.workspace-operational-projection/1.0.0"
            or projection.get("claim_id") != state["claim_id"]
            or not isinstance(workspace_prefix, Mapping)
            or workspace_prefix.get("loop_id") != state["loop_id"]
            or workspace_prefix.get("revision") != state["revision"]
            or workspace_prefix.get("state_sha256") != state["state_sha256"]
            or workspace_prefix.get("last_event_sha256")
            != state["last_event_sha256"]
            or not isinstance(next_state, Mapping)
            or (
                validate_projection_hash
                and projection.get("projection_sha256")
                != digest_value(projection_material)
            )
        ):
            raise ClaimWorkspaceError(
                "operational projection differs from the workspace journal"
            )
        workflow_state = projection["workflow_state"]
        readiness_state = projection["readiness_state"]
        principal_blocker = projection["principal_blocker"]
        pending_evidence_count = projection["pending_evidence_count"]
        next_safe_action = next_state["title"]
        failure_or_unknown_effect = projection["failure_or_unknown_effect"]
        last_authoritative_update = projection["last_authoritative_update"]
    else:
        projection = None
        workflow_state = state["workflow_state"]
        readiness_state = state["readiness_state"]
        principal_blocker = state["principal_blocker"]
        pending_evidence_count = state["pending_evidence_count"]
        next_safe_action = state["next_safe_action"]
        failure_or_unknown_effect = state["failure_or_unknown_effect"]
        last_authoritative_update = state["last_authoritative_update"]
    urgency, urgency_rank, age_days = _urgency(binding["received_at"], now)
    failure_rank = 0 if failure_or_unknown_effect else 1
    unresolved_rank = 0 if readiness_state != "decision_ready" else 1
    readiness_rank = {
        "decision_ready": 3,
        "safe_abstention": 2,
        "blocked": 1,
        "not_assessed": 0,
    }[readiness_state]
    priority_tuple = [
        {
            "dimension": "safety",
            "value": 0
            if workflow_state in {"failed", "typed_failure"}
            else 1,
        },
        {"dimension": "deadline", "value": state["deadline_at"] or "unknown"},
        {"dimension": "failed_or_unknown_effect", "value": failure_rank},
        {"dimension": "unresolved_critical_obligation", "value": unresolved_rank},
        {"dimension": "waiting_age_days", "value": age_days},
        {"dimension": "customer_burden", "value": "unknown"},
        {"dimension": "closeness_to_readiness", "value": readiness_rank},
    ]
    row = {
        "claim_id": state["claim_id"],
        "subject": binding["subject"],
        "language": binding["language"],
        "owner": state["owner"],
        "received_at": binding["received_at"],
        "received_age_days": age_days,
        "deadline_at": state["deadline_at"],
        "urgency": urgency,
        "workflow_state": workflow_state,
        "readiness_state": readiness_state,
        "claim_type": state["claim_type"],
        "principal_blocker": principal_blocker,
        "pending_evidence_count": pending_evidence_count,
        "next_safe_action": next_safe_action,
        "failure_or_unknown_effect": failure_or_unknown_effect,
        "last_authoritative_update": last_authoritative_update,
        "revision": state["revision"],
        "state_sha256": state["state_sha256"],
        "priority_tuple": priority_tuple,
        "_sort": {
            "safety": priority_tuple[0]["value"],
            "deadline": state["deadline_at"] or "9999-12-31T23:59:59+00:00",
            "failure": failure_rank,
            "unresolved": unresolved_rank,
            "waiting": -age_days,
            "burden": 1,
            "readiness": -readiness_rank,
            "urgency": -urgency_rank,
        },
    }
    if projection is not None:
        row["_operational_projection"] = projection
    return row


def _sort_key(row: Mapping[str, Any], mode: str) -> tuple[Any, ...]:
    sort = row["_sort"]
    claim_id = row["claim_id"]
    if mode == "priority":
        return (
            sort["safety"],
            sort["deadline"],
            sort["failure"],
            sort["unresolved"],
            sort["waiting"],
            sort["burden"],
            sort["readiness"],
            claim_id,
        )
    if mode == "urgency":
        return (sort["urgency"], row["received_at"], claim_id)
    if mode == "oldest_waiting":
        return (row["received_at"], claim_id)
    if mode == "nearest_deadline":
        return (sort["deadline"], row["received_at"], claim_id)
    if mode == "most_decision_ready":
        return (sort["readiness"], row["received_at"], claim_id)
    if mode == "latest_update":
        timestamp = _parse_time(row["last_authoritative_update"]).timestamp()
        return (-timestamp, claim_id)
    raise ClaimWorkspaceError("queue sort mode is invalid")


def _cursor_encode(material: Mapping[str, Any]) -> str:
    value = {**_copy(material), "cursor_sha256": digest_value(material)}
    return base64.urlsafe_b64encode(canonical_json_bytes(value)).decode("ascii").rstrip("=")


def _cursor_decode(token: str) -> dict[str, Any]:
    try:
        padding = "=" * (-len(token) % 4)
        value = json.loads(base64.urlsafe_b64decode(token + padding))
    except (ValueError, json.JSONDecodeError) as exc:
        raise ClaimWorkspaceError("queue cursor is invalid") from exc
    if not isinstance(value, dict):
        raise ClaimWorkspaceError("queue cursor is invalid")
    material = dict(value)
    stated = material.pop("cursor_sha256", None)
    if stated != digest_value(material):
        raise ClaimWorkspaceError("queue cursor was tampered")
    return material


class ClaimWorkspaceService:
    def __init__(self, storage: Storage, corpus: PublicCorpus | None = None):
        self.storage = storage
        self.corpus = corpus or PublicCorpus(default_public_corpus_root())
        self.store = ClaimWorkspaceStore(storage, self.corpus)

    @classmethod
    def open_read_only(
        cls,
        database_path: str | Path,
        corpus: PublicCorpus | None = None,
    ) -> ClaimWorkspaceService:
        """Construct the replay surface without creating or migrating a database."""

        value = cls.__new__(cls)
        value.storage = None
        value.corpus = corpus or PublicCorpus(default_public_corpus_root())
        value.store = ClaimWorkspaceStore.open_read_only(database_path, value.corpus)
        return value

    def seed(self, *, timestamp: str | None = None) -> dict[str, Any]:
        timestamp = timestamp or utc_now()
        imported = 0
        replayed = 0
        event_hashes: list[str] = []
        for claim_id in sorted(self.corpus.bindings):
            binding = self.corpus.binding(claim_id)
            state, event, was_replayed = self.store.append(
                claim_id=claim_id,
                event_type="WORKSPACE_CLAIM_IMPORTED",
                idempotency_key="seed." + binding["binding_sha256"],
                command={
                    "binding": binding,
                    "corpus_identity": self.corpus.identity,
                    "request_expected_revision": 0,
                },
                timestamp=timestamp,
                expected_revision=0,
            )
            if state["binding"]["binding_sha256"] != binding["binding_sha256"]:
                raise ClaimWorkspaceError("seed replay binding differs")
            event_hashes.append(event["event_sha256"])
            replayed += int(was_replayed)
            imported += int(not was_replayed)
        material = {
            "contract": SEED_RECEIPT_CONTRACT,
            "corpus_identity": self.corpus.identity,
            "claim_count": len(event_hashes),
            "new_import_count": imported,
            "replayed_import_count": replayed,
            "event_roster_sha256": digest_value(event_hashes),
            "timestamp": timestamp,
            "model_calls": 0,
            "provider_calls": 0,
            "credential_reads": 0,
            "cost_usd": 0,
        }
        return {**material, "receipt_sha256": digest_value(material)}

    def states(self) -> list[dict[str, Any]]:
        return self.store.all_states()

    def queue(
        self,
        *,
        now: str | None = None,
        query: str | None = None,
        state: str | None = None,
        readiness: str | None = None,
        claim_type: str | None = None,
        owner: str | None = None,
        urgency: str | None = None,
        failure: bool | None = None,
        pending_evidence: str | None = None,
        sort: str = "priority",
        cursor: str | None = None,
        limit: int = 25,
        operational_projections: Mapping[str, Mapping[str, Any]] | None = None,
        _states_snapshot: Sequence[Mapping[str, Any]] | None = None,
        _validated_operational_snapshot: bool = False,
    ) -> dict[str, Any]:
        cursor_value = _cursor_decode(cursor) if cursor is not None else None
        if cursor_value is not None:
            if set(cursor_value) != {
                "request_sha256",
                "last_claim_id",
                "as_of",
                "state_roster_sha256",
                "limit",
            }:
                raise ClaimWorkspaceError("queue cursor schema is invalid")
            if now is not None and now != cursor_value["as_of"]:
                raise ClaimWorkspaceError("queue cursor belongs to another snapshot")
            now = cursor_value["as_of"]
        now = now or utc_now()
        _parse_time(now)
        if sort not in SORT_MODES or type(limit) is not int or not 1 <= limit <= 100:
            raise ClaimWorkspaceError("queue request is invalid")
        filters = {
            "query": query or None,
            "state": state,
            "readiness": readiness,
            "claim_type": claim_type,
            "owner": owner,
            "urgency": urgency,
            "failure": failure,
            "pending_evidence": pending_evidence,
            "sort": sort,
            "now": now,
            "limit": limit,
        }
        request_sha256 = digest_value(filters)
        # The product facade captures workspace and ClaimLoop authorities as one
        # logical read cut. Reusing that already validated workspace roster here
        # avoids a second full journal replay while the ordinary public method
        # remains journal-derived by default.
        states = (
            [dict(value) for value in _states_snapshot]
            if _states_snapshot is not None
            else self.states()
        )
        if operational_projections is not None and set(operational_projections) != {
            item["claim_id"] for item in states
        }:
            raise ClaimWorkspaceError(
                "operational projection roster differs from the workspace"
            )
        state_roster_sha256 = digest_value(
            [
                {
                    "claim_id": item["claim_id"],
                    "revision": item["revision"],
                    "state_sha256": item["state_sha256"],
                    "operational_projection_sha256": (
                        operational_projections[item["claim_id"]][
                            "projection_sha256"
                        ]
                        if operational_projections is not None
                        else None
                    ),
                }
                for item in states
            ]
        )
        rows = [
            _row(
                item,
                now=now,
                operational_projection=(
                    operational_projections[item["claim_id"]]
                    if operational_projections is not None
                    else None
                ),
                validate_projection_hash=not _validated_operational_snapshot,
            )
            for item in states
        ]
        facets = {
            "owners": sorted(
                {row["owner"] for row in rows if isinstance(row["owner"], str)}
            ),
            "workflow_states": sorted({row["workflow_state"] for row in rows}),
            "readiness_states": sorted({row["readiness_state"] for row in rows}),
            "claim_types": sorted({row["claim_type"] for row in rows}),
            "urgencies": sorted({row["urgency"] for row in rows}),
        }
        if query:
            needle = query.casefold()
            rows = [
                row
                for row in rows
                if needle
                in " ".join(
                    (row["claim_id"], row["subject"], row["owner"] or "")
                ).casefold()
            ]
        if state is not None:
            rows = [row for row in rows if row["workflow_state"] == state]
        if readiness is not None:
            rows = [row for row in rows if row["readiness_state"] == readiness]
        if claim_type is not None:
            rows = [row for row in rows if row["claim_type"] == claim_type]
        if owner is not None:
            rows = [
                row
                for row in rows
                if (row["owner"] or "unassigned") == owner
            ]
        if urgency is not None:
            rows = [row for row in rows if row["urgency"] == urgency]
        if failure is not None:
            rows = [
                row for row in rows if row["failure_or_unknown_effect"] is failure
            ]
        if pending_evidence is not None:
            predicates = {
                "unknown": lambda value: value is None,
                "none": lambda value: value == 0,
                "some": lambda value: isinstance(value, int) and value > 0,
            }
            if pending_evidence not in predicates:
                raise ClaimWorkspaceError("pending-evidence filter is invalid")
            rows = [
                row
                for row in rows
                if predicates[pending_evidence](row["pending_evidence_count"])
            ]
        rows.sort(key=lambda row: _sort_key(row, sort))
        start = 0
        if cursor_value is not None:
            if (
                cursor_value["request_sha256"] != request_sha256
                or cursor_value["state_roster_sha256"] != state_roster_sha256
                or cursor_value["limit"] != limit
            ):
                raise ClaimWorkspaceError(
                    "queue cursor is stale or belongs to another request"
                )
            ids = [row["claim_id"] for row in rows]
            try:
                start = ids.index(cursor_value["last_claim_id"]) + 1
            except ValueError as exc:
                raise ClaimWorkspaceError("queue cursor row is stale") from exc
        page = rows[start : start + limit]
        next_cursor = None
        if start + limit < len(rows) and page:
            next_cursor = _cursor_encode(
                {
                    "request_sha256": request_sha256,
                    "last_claim_id": page[-1]["claim_id"],
                    "as_of": now,
                    "state_roster_sha256": state_roster_sha256,
                    "limit": limit,
                }
            )
        public_rows = []
        for row in page:
            public = {
                key: item
                for key, item in row.items()
                if key not in {"_sort", "_operational_projection"}
            }
            projection = row.get("_operational_projection")
            if projection is not None:
                # Detach the returned page from any process-local projection
                # cache so a direct caller cannot poison a later queue read.
                public["operational_projection"] = _copy(projection)
                public["row_sha256"] = digest_value(public)
            public_rows.append(public)
        material = {
            "contract": (
                QUEUE_CONTRACT_V2
                if operational_projections is not None
                else QUEUE_CONTRACT
            ),
            "generated_at": now,
            "corpus_identity": self.corpus.identity,
            "request_sha256": request_sha256,
            "state_roster_sha256": state_roster_sha256,
            "total_count": len(rows),
            "page_count": len(public_rows),
            "items": public_rows,
            "next_cursor": next_cursor,
            "facets": facets,
            "authority": "claim_loop_events",
        }
        return {**material, "projection_sha256": digest_value(material)}

    def detail(self, claim_id: str) -> dict[str, Any]:
        state = self.store.recover(claim_id)
        claim = self.corpus.claim(claim_id)
        binding = self.corpus.binding(claim_id)
        message = claim["customer_message"]
        artifacts = []
        for artifact in binding["observable_artifacts"]:
            artifacts.append(
                {
                    key: item
                    for key, item in artifact.items()
                    if key not in {"path"}
                }
                | {
                    "download_url": (
                        f"/api/claim-loops/v1/workspace/claims/{claim_id}/artifacts/"
                        f"{artifact['artifact_id']}"
                    )
                }
            )
        material = {
            "contract": "casepath.claim-workspace-detail/1.0.0",
            "state": state,
            "message": {
                "message_id": message["message_id"],
                "subject": message["subject"],
                "body": message["body"],
                "sent_at": message["sent_at"],
                "from_role": message["from_role"],
                "to_role": message["to_role"],
            },
            "artifacts": artifacts,
            "authority": "claim_loop_events",
        }
        return {**material, "detail_sha256": digest_value(material)}

    def assign(
        self,
        claim_id: str,
        *,
        owner: str,
        idempotency_key: str,
        expected_revision: int | None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        state, event, replayed = self.store.append(
            claim_id=claim_id,
            event_type="WORKSPACE_OWNER_ASSIGNED",
            idempotency_key=idempotency_key,
            command={"owner": owner, "request_expected_revision": expected_revision},
            timestamp=timestamp or utc_now(),
            expected_revision=expected_revision,
        )
        return self._mutation_response(state, event, replayed)

    def start(
        self,
        claim_id: str,
        *,
        idempotency_key: str,
        expected_revision: int | None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        replay = self.store.replay_processing_start(
            claim_id=claim_id,
            idempotency_key=idempotency_key,
            expected_revision=expected_revision,
        )
        if replay is not None:
            state, event = replay
            return self._mutation_response(state, event, True)
        binding = self.corpus.binding(claim_id)
        assessment = compile_intake_assessment(self.corpus, claim_id)
        state, event, replayed = self.store.append(
            claim_id=claim_id,
            event_type="WORKSPACE_PROCESSING_STARTED",
            idempotency_key=idempotency_key,
            command={
                "expected_binding_sha256": binding["binding_sha256"],
                "intake_assessment": assessment,
                "request_expected_revision": expected_revision,
            },
            timestamp=timestamp or utc_now(),
            expected_revision=expected_revision,
        )
        return self._mutation_response(state, event, replayed)

    def reconcile(
        self,
        claim_id: str,
        *,
        idempotency_key: str,
        expected_revision: int | None,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        prior = self.store.recover(claim_id)
        state, event, replayed = self.store.append(
            claim_id=claim_id,
            event_type="WORKSPACE_UNKNOWN_RECONCILED",
            idempotency_key=idempotency_key,
            command={
                "prior_state_sha256": prior["state_sha256"],
                "request_expected_revision": expected_revision,
            },
            timestamp=timestamp or utc_now(),
            expected_revision=expected_revision,
        )
        return self._mutation_response(state, event, replayed)

    @staticmethod
    def _mutation_response(
        state: Mapping[str, Any], event: Mapping[str, Any], replayed: bool
    ) -> dict[str, Any]:
        # Append ownership is transport history, not command semantics. Omitting
        # it makes an accepted retry return the original canonical response bytes.
        del replayed
        material = {
            "contract": "casepath.claim-workspace-command-response/1.0.0",
            "state": _copy(state),
            "event_sha256": event["event_sha256"],
            "event_type": event["event_type"],
            "idempotency_scope": "workspace_event",
        }
        return {**material, "response_sha256": digest_value(material)}

    def rebuild(self, *, timestamp: str | None = None) -> dict[str, Any]:
        timestamp = timestamp or utc_now()
        states = self.states()
        roster = [
            {
                "claim_id": state["claim_id"],
                "revision": state["revision"],
                "state_sha256": state["state_sha256"],
            }
            for state in states
        ]
        material = {
            "contract": REBUILD_RECEIPT_CONTRACT,
            "authority": "claim_loop_events",
            "claim_count": len(roster),
            "state_roster_sha256": digest_value(roster),
            "timestamp": timestamp,
        }
        return {**material, "receipt_sha256": digest_value(material)}

    def export(self, claim_id: str) -> dict[str, Any]:
        state = self.store.recover(claim_id)
        material = {
            "contract": "casepath.claim-status-export/1.0.0",
            "claim_id": claim_id,
            "state_sha256": state["state_sha256"],
            "workflow_state": state["workflow_state"],
            "readiness_state": state["readiness_state"],
            "principal_blocker": state["principal_blocker"],
            "next_safe_action": state["next_safe_action"],
            "last_authoritative_update": state["last_authoritative_update"],
        }
        return {**material, "export_sha256": digest_value(material)}
