"""Append-only work journal with exact-call replay and single-run leases.

The claim database remains authoritative. This store contains work history,
source quotations, proposals, gate checks, and observed claim-state identities.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Any
import json
import os
import sqlite3
import time
import uuid

from .contracts import WorkEvent, Operation, Role, ROLE_ORDER, canonical, digest, utcnow


class WorkStoreError(RuntimeError):
    pass


class ConflictError(WorkStoreError):
    pass


class ReconciliationRequired(WorkStoreError):
    pass


ACTIVE = ("queued", "running", "interrupted")
SCHEMA = """
CREATE TABLE IF NOT EXISTS work_runs (
 run_id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
 request_sha256 TEXT NOT NULL, request_json TEXT NOT NULL,
 created_at TEXT NOT NULL, status TEXT NOT NULL,
 owner TEXT, lease_until REAL,
 UNIQUE(claim_id,idempotency_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_work_run_per_claim
 ON work_runs(claim_id) WHERE status IN ('queued','running','interrupted');
CREATE TABLE IF NOT EXISTS work_external_permits (
 run_id TEXT PRIMARY KEY REFERENCES work_runs(run_id)
);
CREATE TABLE IF NOT EXISTS work_events (
 run_id TEXT NOT NULL REFERENCES work_runs(run_id), sequence INTEGER NOT NULL,
 event_json TEXT NOT NULL, event_sha256 TEXT NOT NULL,
 PRIMARY KEY(run_id,sequence), UNIQUE(run_id,event_sha256)
);
CREATE TRIGGER IF NOT EXISTS work_events_no_update BEFORE UPDATE ON work_events
 BEGIN SELECT RAISE(ABORT,'work events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS work_events_no_delete BEFORE DELETE ON work_events
 BEGIN SELECT RAISE(ABORT,'work events are immutable'); END;
CREATE TABLE IF NOT EXISTS work_calls (
 run_id TEXT NOT NULL REFERENCES work_runs(run_id), role TEXT NOT NULL, call_id TEXT NOT NULL,
 request_sha256 TEXT NOT NULL, tool_name TEXT NOT NULL, status TEXT NOT NULL,
 result_json TEXT, started_at TEXT NOT NULL,
 PRIMARY KEY(run_id,role,call_id)
);
CREATE TABLE IF NOT EXISTS work_objects (
 run_id TEXT NOT NULL REFERENCES work_runs(run_id), object_id TEXT NOT NULL,
 kind TEXT NOT NULL, value_json TEXT NOT NULL, value_sha256 TEXT NOT NULL,
 event_sequence INTEGER NOT NULL,
 PRIMARY KEY(run_id,object_id)
);
"""


class WorkStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise WorkStoreError("work journal path cannot be a symlink")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._lock = RLock()
        self._validated_event_cache: dict[str, tuple[str, tuple[tuple[int, str, bytes], ...], list[dict]]] = {}
        with self.connect() as db:
            db.executescript(SCHEMA)
            db.execute("PRAGMA journal_mode=WAL")
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA busy_timeout=10000")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self._lock, self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def _run(db, run_id):
        row = db.execute("SELECT * FROM work_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None:
            raise WorkStoreError("work run does not exist")
        return dict(row)

    def get_run(self, run_id):
        with self.connect() as db:
            run = self._run(db, run_id)
        return self._decode_run(run)

    @staticmethod
    def _decode_run(run):
        run["request"] = json.loads(run.pop("request_json"))
        if digest(run["request"]) != run["request_sha256"]:
            raise WorkStoreError("run request identity is invalid")
        return run

    def create(self, claim_id: str, idempotency_key: str, request: dict, *, external_limit: int | None = None, max_active: int | None = None) -> tuple[dict, bool]:
        if not isinstance(idempotency_key, str) or not 8 <= len(idempotency_key) <= 128:
            raise WorkStoreError("a bounded idempotency key is required")
        if not isinstance(claim_id, str) or not 1 <= len(claim_id) <= 180:
            raise WorkStoreError("invalid claim identity")
        request_json, request_hash = canonical(request).decode(), digest(request)
        with self.transaction() as db:
            existing = db.execute("SELECT * FROM work_runs WHERE claim_id=? AND idempotency_key=?", (claim_id, idempotency_key)).fetchone()
            if existing:
                if existing["request_sha256"] != request_hash:
                    raise ConflictError("this idempotency key already binds different work")
                run_id, created = existing["run_id"], False
            else:
                if max_active is not None:
                    if type(max_active) is not int or not 1 <= max_active <= 1000:
                        raise WorkStoreError("invalid active-work queue limit")
                    active_count = db.execute("SELECT COUNT(*) FROM work_runs WHERE status IN ('queued','running','interrupted')").fetchone()[0]
                    if active_count >= max_active:
                        raise ConflictError("the bounded work queue is full")
                active = db.execute("SELECT run_id FROM work_runs WHERE claim_id=? AND status IN ('queued','running','interrupted')", (claim_id,)).fetchone()
                if active:
                    raise ConflictError("this claim already has unfinished work")
                if request.get("facts_worker") == "external_facts":
                    if type(external_limit) is not int or not 1 <= external_limit <= 3:
                        raise WorkStoreError("external work requires an explicit bounded permit")
                    used = db.execute("SELECT COUNT(*) FROM work_external_permits").fetchone()[0]
                    if used >= external_limit:
                        raise ConflictError("external-role proof budget is exhausted")
                run_id, created = "work." + uuid.uuid4().hex, True
                db.execute("INSERT INTO work_runs VALUES(?,?,?,?,?,?,?,NULL,NULL)",
                           (run_id, claim_id, idempotency_key, request_hash, request_json, utcnow(), "queued"))
                if request.get("facts_worker") == "external_facts":
                    db.execute("INSERT INTO work_external_permits VALUES(?)", (run_id,))
                self._append(db, run_id, operation=Operation.RUN_QUEUED, object_kind="run", object_id=run_id,
                             status="queued", message="Six-role review queued", worker_kind="kernel",
                             after={"roles": [r.value for r in ROLE_ORDER], "facts_worker": request.get("facts_worker", "reference")})
        return self.get_run(run_id), created

    def _append(self, db, run_id, **event):
        run = self._run(db, run_id)
        last = db.execute("SELECT sequence,event_sha256 FROM work_events WHERE run_id=? ORDER BY sequence DESC LIMIT 1", (run_id,)).fetchone()
        material = dict(contract="casepath.agent-work/1.0.0", claim_id=run["claim_id"], run_id=run_id,
                        sequence=last["sequence"] + 1 if last else 1, role=None, before=None, after=None,
                        sources=[], links=[], parent_event=None, gate=None, timestamp=utcnow(),
                        previous_sha256=last["event_sha256"] if last else "0" * 64)
        material.update(event)
        # Use JSON mode before hashing so enum and tuple normalization is stable.
        material = json.loads(canonical(material))
        material["event_sha256"] = digest(material)
        parsed = WorkEvent.model_validate(material)
        record = parsed.model_dump(mode="json")
        db.execute("INSERT INTO work_events VALUES(?,?,?,?)", (run_id, record["sequence"], canonical(record).decode(), record["event_sha256"]))
        return record

    @staticmethod
    def _require_owner(db, run_id, owner):
        run = WorkStore._run(db, run_id)
        if run["status"] != "running" or run["owner"] != owner or not run["lease_until"] or run["lease_until"] <= time.time():
            raise ConflictError("work lease expired or belongs to another executor")
        return run

    def append(self, run_id, owner, **event):
        with self.transaction() as db:
            self._require_owner(db, run_id, owner)
            return self._append(db, run_id, **event)

    def acquire(self, run_id: str, owner: str, lease_seconds: int = 180):
        self.events(run_id)  # Reject altered history before claiming work.
        with self.transaction() as db:
            run = self._run(db, run_id)
            if run["status"] in {"completed", "blocked", "failed"}:
                return False
            if run["status"] == "running" and run["lease_until"] > time.time():
                raise ConflictError("work is already executing")
            pending = db.execute("SELECT 1 FROM work_calls WHERE run_id=? AND status='started' LIMIT 1", (run_id,)).fetchone()
            if pending:
                raise ReconciliationRequired("an unfinished tool or provider call must be reconciled before resume")
            db.execute("UPDATE work_runs SET status='running',owner=?,lease_until=? WHERE run_id=?", (owner, time.time() + lease_seconds, run_id))
            self._append(db, run_id, operation=Operation.RUN_STARTED, object_kind="run", object_id=run_id,
                         status="started", message="Review execution started", worker_kind="kernel")
            return True

    def heartbeat(self, run_id, owner, seconds=180):
        with self.transaction() as db:
            self._require_owner(db, run_id, owner)
            db.execute("UPDATE work_runs SET lease_until=? WHERE run_id=?", (time.time() + seconds, run_id))

    def begin_call(self, run_id, owner, role, call_id, tool, arguments):
        request_hash = digest({"tool": tool, "arguments": arguments})
        if not isinstance(call_id, str) or not 1 <= len(call_id) <= 160:
            raise WorkStoreError("invalid tool call identity")
        with self.transaction() as db:
            self._require_owner(db, run_id, owner)
            existing = db.execute("SELECT * FROM work_calls WHERE run_id=? AND role=? AND call_id=?", (run_id, str(role), call_id)).fetchone()
            if existing:
                if existing["request_sha256"] != request_hash:
                    raise ConflictError("tool call identity was reused with different arguments")
                if existing["status"] != "completed":
                    raise ReconciliationRequired("tool outcome is unfinished; no blind retry")
                return json.loads(existing["result_json"])
            db.execute("INSERT INTO work_calls VALUES(?,?,?,?,?,'started',NULL,?)", (run_id, str(role), call_id, request_hash, tool, utcnow()))
            return None

    def complete_call(self, run_id, owner, role, call_id, result, events, objects=()):
        with self.transaction() as db:
            self._require_owner(db, run_id, owner)
            row = db.execute("SELECT status FROM work_calls WHERE run_id=? AND role=? AND call_id=?", (run_id, str(role), call_id)).fetchone()
            if row is None or row["status"] != "started":
                raise ConflictError("tool completion has no pending call")
            written = [self._append(db, run_id, **event) for event in events]
            sequence = written[-1]["sequence"] if written else 0
            for obj in objects:
                anchor = self._append(db, run_id, role=str(role), operation=Operation.WORK_PRODUCT_RECORDED,
                                      object_kind=obj["kind"], object_id=obj["id"], status="observed",
                                      message="Persisted checked work product", worker_kind="kernel",
                                      after={"value":obj["value"], "value_sha256":digest(obj["value"])})
                sequence=anchor["sequence"]
                value = canonical(obj["value"]).decode()
                db.execute("INSERT INTO work_objects VALUES(?,?,?,?,?,?) ON CONFLICT(run_id,object_id) DO UPDATE SET kind=excluded.kind,value_json=excluded.value_json,value_sha256=excluded.value_sha256,event_sequence=excluded.event_sequence",
                           (run_id, obj["id"], obj["kind"], value, digest(obj["value"]), sequence))
            response = {**result, "event_sequences": [e["sequence"] for e in written]}
            db.execute("UPDATE work_calls SET status='completed',result_json=? WHERE run_id=? AND role=? AND call_id=?",
                       (canonical(response).decode(), run_id, str(role), call_id))
            return response

    @staticmethod
    def _validate_events(run, rows, *, start=0, previous="0" * 64):
        result = []
        for index, row in enumerate(rows, start + 1):
            try:
                event = WorkEvent.model_validate(json.loads(row["event_json"])).model_dump(mode="json")
            except ValueError as exc:
                raise WorkStoreError("event history is corrupt") from exc
            if (event["run_id"] != run["run_id"] or event["claim_id"] != run["claim_id"]
                    or row["sequence"] != index or event["sequence"] != index
                    or event["previous_sha256"] != previous or event["event_sha256"] != row["event_sha256"]):
                raise WorkStoreError("event chain is incomplete or crossed")
            previous = event["event_sha256"]
            result.append(event)
        return result

    def snapshot(self, run_id):
        """One read transaction binds run status, events, products and pending calls."""
        with self.connect() as db:
            db.execute("BEGIN")
            run = self._run(db, run_id)
            rows = db.execute("SELECT * FROM work_events WHERE run_id=? ORDER BY sequence", (run_id,)).fetchall()
            products = db.execute("SELECT * FROM work_objects WHERE run_id=? ORDER BY event_sequence,object_id", (run_id,)).fetchall()
            pending = db.execute("SELECT role,call_id,tool_name,started_at FROM work_calls WHERE run_id=? AND status='started' ORDER BY started_at", (run_id,)).fetchall()
            db.commit()
        run["request"] = json.loads(run.pop("request_json"))
        if digest(run["request"]) != run["request_sha256"]:
            raise WorkStoreError("run request identity is invalid")
        # Fingerprint persisted bytes on every read. Pydantic replay is needed
        # only for the suffix; an altered prefix forces full validation.
        fingerprints = tuple(
            (row["sequence"], row["event_sha256"], sha256(row["event_json"].encode()).digest())
            for row in rows
        )
        with self._lock:
            cached = self._validated_event_cache.get(run_id)
        if (cached is not None and cached[0] == run["claim_id"]
                and len(cached[1]) <= len(fingerprints)
                and fingerprints[:len(cached[1])] == cached[1]):
            prefix = cached[2]
            history = prefix + self._validate_events(
                run, rows[len(prefix):], start=len(prefix),
                previous=prefix[-1]["event_sha256"] if prefix else "0" * 64,
            ) if len(prefix) < len(rows) else prefix
        else:
            history = self._validate_events(run, rows)
        with self._lock:
            self._validated_event_cache[run_id] = (run["claim_id"], fingerprints, history)
            if len(self._validated_event_cache) > 256:
                self._validated_event_cache.pop(next(iter(self._validated_event_cache)))
        anchors = {e["sequence"]: e for e in history}
        objects = []
        for row in products:
            value = json.loads(row["value_json"])
            anchor = anchors.get(row["event_sequence"], {})
            if (digest(value) != row["value_sha256"] or anchor.get("operation") != "WORK_PRODUCT_RECORDED"
                    or anchor.get("object_id") != row["object_id"] or anchor.get("object_kind") != row["kind"]
                    or anchor.get("after") != {"value":value,"value_sha256":row["value_sha256"]}):
                raise WorkStoreError("work object differs from its immutable event")
            objects.append({"id":row["object_id"],"kind":row["kind"],"value":value,"sha256":row["value_sha256"],"event_sequence":row["event_sequence"]})
        terminal = {"completed":"RUN_COMPLETED", "blocked":"RUN_BLOCKED", "failed":"RUN_FAILED", "interrupted":"RUN_INTERRUPTED"}
        if run["status"] in terminal and (not history or history[-1]["operation"] != terminal[run["status"]]):
            raise WorkStoreError("run status differs from its immutable history")
        if run["status"] == "queued" and (len(history)!=1 or history[0]["operation"]!="RUN_QUEUED"):
            raise WorkStoreError("queued status differs from work history")
        return {"run":run,"events":history,"objects":objects,"pending_calls":[dict(p) for p in pending]}

    def objects(self, run_id, kind=None):
        return [o for o in self.snapshot(run_id)["objects"] if kind is None or o["kind"]==kind]

    def object(self, run_id, object_id):
        found=next((o for o in self.objects(run_id) if o["id"]==object_id),None)
        if found is None:raise WorkStoreError("work object is unavailable")
        return found

    def events(self, run_id, after=0, limit=5000):
        if type(after) is not int or after<0 or type(limit) is not int or not 1<=limit<=5000:
            raise WorkStoreError("invalid event window")
        return self.snapshot(run_id)["events"][after:after+limit]

    def finish(self, run_id, owner, status, message, after=None):
        operations = {"completed": Operation.RUN_COMPLETED, "blocked": Operation.RUN_BLOCKED, "failed": Operation.RUN_FAILED}
        if status not in operations:
            raise WorkStoreError("invalid terminal work status")
        with self.transaction() as db:
            self._require_owner(db, run_id, owner)
            self._append(db, run_id, operation=operations[status], object_kind="run", object_id=run_id,
                         status="completed" if status == "completed" else "blocked", message=message,
                         worker_kind="kernel", after=after)
            db.execute("UPDATE work_runs SET status=?,owner=NULL,lease_until=NULL WHERE run_id=?", (status, run_id))

    def mark_expired_interrupted(self):
        """A vanished executor is unconfirmed work, not a scientific/model failure."""
        with self.transaction() as db:
            rows = db.execute("SELECT run_id FROM work_runs WHERE status='running' AND lease_until<?", (time.time(),)).fetchall()
            for row in rows:
                self._append(db, row["run_id"], operation=Operation.RUN_INTERRUPTED, object_kind="run", object_id=row["run_id"],
                             status="unknown", message="Execution lease expired; inspect the saved work before resuming", worker_kind="kernel")
                db.execute("UPDATE work_runs SET status='interrupted',owner=NULL,lease_until=NULL WHERE run_id=?", (row["run_id"],))
        return len(rows)

    def pending_calls(self, run_id):
        with self.connect() as db:
            self._run(db, run_id)
            rows = db.execute("SELECT role,call_id,tool_name,started_at FROM work_calls WHERE run_id=? AND status='started' ORDER BY started_at", (run_id,)).fetchall()
        return [dict(row) for row in rows]

    def list_runs(self, claim_id=None, limit=150):
        if not 1 <= limit <= 500:
            raise WorkStoreError("run limit is invalid")
        with self.connect() as db:
            sql = "SELECT * FROM work_runs" + (" WHERE claim_id=?" if claim_id else "") + " ORDER BY created_at DESC,run_id LIMIT ?"
            rows = db.execute(sql, (claim_id, limit) if claim_id else (limit,)).fetchall()
        return [self._decode_run(dict(row)) for row in rows]


    def find_request(self, claim_id, idempotency_key):
        """Exact index lookup: a display window may not define idempotency."""
        with self.connect() as db:
            row = db.execute("SELECT run_id FROM work_runs WHERE claim_id=? AND idempotency_key=?",
                             (claim_id, idempotency_key)).fetchone()
        return self.get_run(row["run_id"]) if row else None

    def latest_claim_runs(self, limit=150):
        """One latest run per claim, with complete count metadata from one read snapshot."""
        if type(limit) is not int or not 1 <= limit <= 500:
            raise WorkStoreError("run limit is invalid")
        with self.connect() as db:
            db.execute("BEGIN")
            totals = db.execute("SELECT COUNT(*) AS runs,COUNT(DISTINCT claim_id) AS claims FROM work_runs").fetchone()
            rows = db.execute("""
                WITH ranked AS (
                    SELECT run_id,claim_id,status,created_at,
                           ROW_NUMBER() OVER (PARTITION BY claim_id ORDER BY created_at DESC,run_id DESC) AS position
                    FROM work_runs
                )
                SELECT work_runs.* FROM ranked JOIN work_runs USING(run_id)
                WHERE position=1
                ORDER BY CASE WHEN ranked.status IN ('queued','running','interrupted') THEN 0 ELSE 1 END,
                         ranked.created_at DESC,ranked.run_id DESC LIMIT ?
                """, (limit,)).fetchall()
            db.commit()
        runs = [self._decode_run(dict(row)) for row in rows]
        return runs, {"kind":"latest_per_claim", "total_runs":totals["runs"],
                      "total_claims":totals["claims"], "returned_claims":len(runs),
                      "has_more":totals["claims"] > len(runs)}
