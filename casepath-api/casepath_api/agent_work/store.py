"""Append-only work journal with exact-call replay and single-run leases.

The claim database remains authoritative. This store contains work history,
source quotations, proposals, gate checks, and observed claim-state identities.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
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


class WorkCancelled(WorkStoreError):
    pass


class WorkPaused(WorkStoreError):
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
CREATE TABLE IF NOT EXISTS work_external_budget (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), policy_json TEXT NOT NULL, policy_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS work_external_permits (
 run_id TEXT PRIMARY KEY REFERENCES work_runs(run_id)
);
CREATE TABLE IF NOT EXISTS work_cancellation_requests (
 run_id TEXT PRIMARY KEY REFERENCES work_runs(run_id)
);
CREATE TABLE IF NOT EXISTS work_pause_requests (
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
        self._validated_object_cache: dict[str, tuple[tuple, tuple, bytes]] = {}
        with self.connect() as db:
            db.executescript(SCHEMA)
            db.execute("PRAGMA journal_mode=WAL")
        # Keep one reader open so short tool-call connections do not checkpoint
        # the WAL after every durable commit. FULL synchronous still protects it.
        self._keeper = sqlite3.connect(self.path, timeout=10, isolation_level=None, check_same_thread=False)
        self._keeper.execute("PRAGMA journal_mode").fetchone()
        os.chmod(self.path, 0o600)

    def close(self):
        with self._lock:
            if self._keeper is not None:
                self._keeper.close()
                self._keeper = None

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

    @staticmethod
    def _money(value):
        try:
            if isinstance(value, bool):
                raise ValueError
            amount = Decimal(str(value))
            if not amount.is_finite() or amount < 0:
                raise ValueError
            return amount
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise WorkStoreError("provider budget contains an invalid amount") from exc

    def configure_external_budget(self, policy):
        """Bind a persistent demo allowance; process restart cannot refill it."""
        fields = {"max_runs", "max_provider_calls", "total_cost_limit_usd", "run_cost_limit_usd"}
        if set(policy) != fields or type(policy["max_runs"]) is not int or not 1 <= policy["max_runs"] <= 3:
            raise WorkStoreError("invalid explicit provider budget")
        if type(policy["max_provider_calls"]) is not int or not 1 <= policy["max_provider_calls"] <= 18:
            raise WorkStoreError("invalid explicit provider call budget")
        total, per_run = (self._money(policy[k]) for k in ("total_cost_limit_usd", "run_cost_limit_usd"))
        if not 0 < per_run <= Decimal("0.02") or not per_run <= total <= Decimal("0.10"):
            raise WorkStoreError("invalid explicit provider cost budget")
        policy = {**policy, "total_cost_limit_usd": str(total), "run_cost_limit_usd": str(per_run)}
        with self.transaction() as db:
            prior = db.execute("SELECT * FROM work_external_budget WHERE singleton=1").fetchone()
            if prior:
                if prior["policy_sha256"] != digest(policy) or prior["policy_json"] != canonical(policy).decode():
                    raise ConflictError("the persisted demo budget differs; it cannot be reset by configuration")
            else:
                db.execute("INSERT INTO work_external_budget VALUES(1,?,?)", (canonical(policy).decode(), digest(policy)))

    def _external_usage(self, db):
        """Derive spend from validated journals within the admission transaction."""
        rows = db.execute("SELECT * FROM work_runs WHERE run_id IN (SELECT run_id FROM work_external_permits)").fetchall()
        runs, calls = {}, []
        for row in rows:
            run = self._decode_run(dict(row))
            run_id = run["run_id"]
            events = self._validate_events(run, db.execute("SELECT * FROM work_events WHERE run_id=? ORDER BY sequence", (run_id,)).fetchall())
            responses = {e["object_id"]: e for e in events if e["operation"] == Operation.PROVIDER_RESPONSE_RECEIVED}
            run_calls = []
            for event in events:
                if event["operation"] != Operation.PROVIDER_REQUEST_STARTED:
                    continue
                response = responses.get(event["object_id"], {})
                usage = (response.get("after") or {}).get("usage") or {}
                cost = self._money(usage["cost"]) if usage.get("cost") is not None else None
                reserved = self._money(event["after"]["maximum_cost_usd"])
                record = {"run_id": run_id, "cost": cost, "reserved": reserved}
                calls.append(record); run_calls.append(record)
            runs[run_id] = {"run": run, "calls": run_calls}
        pending = db.execute("SELECT 1 FROM work_calls WHERE tool_name='provider_request' AND status='started' LIMIT 1").fetchone() is not None
        return runs, calls, pending

    def _external_budget(self, db, usage=None):
        row = db.execute("SELECT * FROM work_external_budget WHERE singleton=1").fetchone()
        if row is None:
            return None
        policy = json.loads(row["policy_json"])
        if digest(policy) != row["policy_sha256"]:
            raise WorkStoreError("persisted demo budget identity differs")
        runs, calls, pending = usage or self._external_usage(db)
        actual = sum((c["cost"] for c in calls if c["cost"] is not None), Decimal(0))
        reserved = sum((c["reserved"] for c in calls if c["cost"] is None), Decimal(0))
        for record in runs.values():
            if record["run"]["status"] in ACTIVE:
                config = record["run"]["request"].get("worker_config") or {}
                limit = self._money(config.get("cost_limit_usd", policy["run_cost_limit_usd"]))
                committed = sum((c["cost"] if c["cost"] is not None else c["reserved"] for c in record["calls"]), Decimal(0))
                reserved += max(Decimal(0), limit - committed)
        available = max(Decimal(0), self._money(policy["total_cost_limit_usd"]) - actual - reserved)
        exceeded = any(c["cost"] is not None and c["cost"] > c["reserved"] for c in calls)
        reason = ("provider_cost_bound_exceeded" if exceeded else "provider_outcome_pending" if pending else
                  "run_limit_reached" if len(runs) >= policy["max_runs"] else
                  "call_limit_reached" if len(calls) >= policy["max_provider_calls"] else
                  "cost_limit_reached" if available < self._money(policy["run_cost_limit_usd"]) else None)
        return {"scope": "persistent_local_demo", **policy, "runs_used": len(runs), "provider_calls_used": len(calls),
                "actual_cost_usd": str(actual), "reserved_cost_usd": str(reserved), "remaining_cost_usd": str(available),
                "unknown_calls": sum(c["cost"] is None for c in calls), "in_flight": pending,
                "can_start": reason is None, "reason": reason, "automatic_retry": False}

    def external_budget(self):
        with self.connect() as db:
            db.execute("BEGIN")
            return self._external_budget(db)

    def begin_provider_call(self, run_id, owner, call_id, request_sha256, *, model, maximum_cost_usd, parent_event=None):
        """Reserve one physical call and journal its intent atomically before send."""
        with self.transaction() as db:
            run = self._decode_run(self._require_owner(db, run_id, owner))
            if run["request"].get("facts_worker") != "external_facts":
                raise ConflictError("provider call requires an explicit external run")
            cfg = run["request"].get("worker_config") or {}
            if digest(cfg) != run["request"].get("worker_config_sha256") or cfg.get("model") != model:
                raise ConflictError("provider configuration differs from the admitted run")
            expected = (self._money(cfg["prompt_price"]) * cfg["max_request_bytes"] +
                        self._money(cfg["completion_price"]) * cfg["max_output_tokens"] + self._money(cfg["request_price"]))
            maximum = self._money(maximum_cost_usd)
            if maximum != expected:
                raise ConflictError("provider reservation differs from the frozen prices")
            if db.execute("SELECT 1 FROM work_cancellation_requests WHERE run_id=?", (run_id,)).fetchone():
                raise WorkCancelled("The review was stopped at a safe checkpoint")
            if db.execute("SELECT 1 FROM work_pause_requests WHERE run_id=?", (run_id,)).fetchone():
                raise WorkPaused("The review was paused at a safe checkpoint")
            if db.execute("SELECT 1 FROM work_calls WHERE run_id=? AND role=? AND call_id=?", (run_id, Role.FACTS.value, call_id)).fetchone():
                raise ReconciliationRequired("provider attempt already exists; it cannot be resent")
            usage = self._external_usage(db)
            runs, calls, pending = usage
            if pending:
                raise ConflictError("another provider outcome is pending; no concurrent inference")
            run_calls = runs[run_id]["calls"]
            committed = sum((c["cost"] if c["cost"] is not None else c["reserved"] for c in run_calls), Decimal(0))
            if len(run_calls) >= cfg["max_requests"] or committed + maximum > self._money(cfg["cost_limit_usd"]):
                raise ConflictError("the per-run provider budget is exhausted")
            budget = self._external_budget(db, usage)
            if budget and (len(calls) >= budget["max_provider_calls"] or
                           budget["reason"] == "provider_cost_bound_exceeded"):
                raise ConflictError("the aggregate provider call or cost budget is exhausted")
            request_hash = digest({"tool": "provider_request", "arguments": {"sha256": request_sha256}})
            db.execute("INSERT INTO work_calls VALUES(?,?,?,?,?,'started',NULL,?)",
                       (run_id, Role.FACTS.value, call_id, request_hash, "provider_request", utcnow()))
            self._append(db, run_id, role=Role.FACTS, operation=Operation.PROVIDER_REQUEST_STARTED,
                         object_kind="provider_request", object_id=call_id, status="started", worker_kind="external",
                         message="Started a bounded provider request attempt", parent_event=parent_event, after={"model": model,
                         "request_number": len(run_calls) + 1, "request_sha256": request_sha256,
                         "maximum_cost_usd": str(maximum)})

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
                    if db.execute("SELECT 1 FROM work_calls c JOIN work_runs r ON r.run_id=c.run_id WHERE r.claim_id=? AND c.status='started' LIMIT 1", (claim_id,)).fetchone():
                        raise ConflictError("an unfinished claim operation requires reconciliation before external review")
                    if type(external_limit) is not int or not 1 <= external_limit <= 3:
                        raise WorkStoreError("external work requires an explicit bounded permit")
                    budget = self._external_budget(db)
                    if budget:
                        if not budget["can_start"]:
                            raise ConflictError("external demo budget unavailable: " + budget["reason"])
                        if self._money((request.get("worker_config") or {}).get("cost_limit_usd")) != self._money(budget["run_cost_limit_usd"]):
                            raise ConflictError("external run cost differs from the persisted demo budget")
                        external_limit = min(external_limit, budget["max_runs"])
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
            if run["status"] in {"completed", "blocked", "failed", "cancelled"}:
                return False
            if db.execute("SELECT 1 FROM work_pause_requests WHERE run_id=?", (run_id,)).fetchone():
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
            if db.execute("SELECT 1 FROM work_cancellation_requests WHERE run_id=?", (run_id,)).fetchone():
                raise WorkCancelled("The review was stopped at a safe checkpoint")
            if db.execute("SELECT 1 FROM work_pause_requests WHERE run_id=?", (run_id,)).fetchone():
                raise WorkPaused("The review was paused at a safe checkpoint")
            db.execute("UPDATE work_runs SET lease_until=? WHERE run_id=?", (time.time() + seconds, run_id))

    def begin_call(self, run_id, owner, role, call_id, tool, arguments):
        request_hash = digest({"tool": tool, "arguments": arguments})
        if not isinstance(call_id, str) or not 1 <= len(call_id) <= 160:
            raise WorkStoreError("invalid tool call identity")
        with self.transaction() as db:
            self._require_owner(db, run_id, owner)
            if db.execute("SELECT 1 FROM work_cancellation_requests WHERE run_id=?", (run_id,)).fetchone():
                raise WorkCancelled("The review was stopped at a safe checkpoint")
            if db.execute("SELECT 1 FROM work_pause_requests WHERE run_id=?", (run_id,)).fetchone():
                raise WorkPaused("The review was paused at a safe checkpoint")
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
            return self._complete_call(db, run_id, role, call_id, result, events, objects)

    def _complete_call(self, db, run_id, role, call_id, result, events, objects):
        row = db.execute("SELECT status FROM work_calls WHERE run_id=? AND role=? AND call_id=?", (run_id, str(role), call_id)).fetchone()
        if row is None or row["status"] != "started":
            raise ConflictError("tool completion has no pending call")
        written = [self._append(db, run_id, **event) for event in events]
        for obj in objects:
            anchor = self._append(db, run_id, role=str(role), operation=Operation.WORK_PRODUCT_RECORDED,
                                  object_kind=obj["kind"], object_id=obj["id"], status="observed",
                                  message="Persisted checked work product", worker_kind="kernel",
                                  after={"value":obj["value"], "value_sha256":digest(obj["value"])})
            value = canonical(obj["value"]).decode()
            db.execute("INSERT INTO work_objects VALUES(?,?,?,?,?,?) ON CONFLICT(run_id,object_id) DO UPDATE SET kind=excluded.kind,value_json=excluded.value_json,value_sha256=excluded.value_sha256,event_sequence=excluded.event_sequence",
                       (run_id, obj["id"], obj["kind"], value, digest(obj["value"]), anchor["sequence"]))
        response = {**result, "event_sequences": [e["sequence"] for e in written]}
        db.execute("UPDATE work_calls SET status='completed',result_json=? WHERE run_id=? AND role=? AND call_id=?",
                   (canonical(response).decode(), run_id, str(role), call_id))
        return response

    def reconcile_process_node(self, run_id, command, result, events, objects, verify_authority):
        """Commit a reconstructed local buffer; never clear or resend an unknown call."""
        self.snapshot(run_id)  # Reject a corrupt request, event chain or product first.
        with self.transaction() as db:
            run = self._decode_run(self._run(db, run_id))
            rows = db.execute("SELECT * FROM work_events WHERE run_id=? ORDER BY sequence", (run_id,)).fetchall()
            history = self._validate_events(run, rows)
            prior = self.reconciliation_receipt(history, command)
            if prior:
                return {"event_sha256": prior["event_sha256"], "replayed": True, "reconciled": True, "claim_state_changed": False}
            if run["request"].get("facts_worker") != "reference" or any(e["operation"].startswith("PROVIDER_") for e in history):
                raise ConflictError("provider work cannot use local proposal reconciliation")
            if (run["status"] not in {"running", "interrupted", "blocked"}
                    or (run.get("lease_until") or 0) > time.time()):
                raise ConflictError("the executor has not reached an inactive recovery state")
            if db.execute("SELECT 1 FROM work_cancellation_requests WHERE run_id=?", (run_id,)).fetchone():
                raise ConflictError("a cancelled review cannot be reconstructed")
            if history[-1]["event_sha256"] != command["expected_last_event_sha256"]:
                raise ConflictError("saved work changed; inspect the latest checkpoint")
            pending = db.execute("SELECT * FROM work_calls WHERE run_id=? AND status='started'", (run_id,)).fetchall()
            request_sha = digest({"tool": "propose_process_node", "arguments": {"object_id": command["object_id"]}})
            if (len(pending) != 1 or pending[0]["role"] != Role.PROCESS.value
                    or pending[0]["call_id"] != command["call_id"] or pending[0]["tool_name"] != "propose_process_node"
                    or pending[0]["request_sha256"] != request_sha):
                raise ConflictError("the unfinished operation is not the reviewed local node proposal")
            verify_authority()
            self._complete_call(db, run_id, Role.PROCESS, command["call_id"], result, events, objects)
            receipt = self._append(db, run_id, role=Role.PROCESS, operation=Operation.LOCAL_PROPOSAL_RECONCILED,
                object_kind="local_proposal", object_id=command["call_id"], status="accepted", worker_kind="kernel",
                message="Handler reviewed the unchanged saved node; reconstructed its local proposal without repeating an effect",
                after={"command": command, "request_sha256": request_sha, "node_sha256": digest(objects[0]["value"]),
                       "claim_state_changed": False, "provider_requests": 0})
            self._append(db, run_id, operation=Operation.RUN_INTERRUPTED, object_kind="run", object_id=run_id,
                status="unknown", message="Local proposal reconciled; remaining review awaits explicit resume", worker_kind="kernel")
            db.execute("UPDATE work_runs SET status='interrupted',owner=NULL,lease_until=NULL WHERE run_id=?", (run_id,))
            return {"event_sha256": receipt["event_sha256"], "replayed": False, "reconciled": True, "claim_state_changed": False}

    @staticmethod
    def reconciliation_receipt(history, command):
        for event in history:
            if event["operation"] == "LOCAL_PROPOSAL_RECONCILED" and event["object_id"] == command["call_id"]:
                if (event.get("after") or {}).get("command") != command:
                    raise ConflictError("the reconciliation identity binds a different reviewed command")
                return event
        return None

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
            pending = db.execute("SELECT role,call_id,tool_name,request_sha256,started_at FROM work_calls WHERE run_id=? AND status='started' ORDER BY started_at", (run_id,)).fetchall()
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
        product_fingerprints = tuple(
            (row["object_id"], row["kind"], row["value_sha256"], row["event_sequence"], sha256(row["value_json"].encode()).digest())
            for row in products
        )
        with self._lock:
            cached_objects = self._validated_object_cache.get(run_id)
        if (cached_objects is not None
                and len(cached_objects[0]) <= len(fingerprints)
                and fingerprints[:len(cached_objects[0])] == cached_objects[0]
                and len(cached_objects[1]) <= len(product_fingerprints)
                and product_fingerprints[:len(cached_objects[1])] == cached_objects[1]):
            objects = json.loads(cached_objects[2])
        else:
            objects = []
        for row in products[len(objects):]:
            value = json.loads(row["value_json"])
            anchor = anchors.get(row["event_sequence"], {})
            if (digest(value) != row["value_sha256"] or anchor.get("operation") != "WORK_PRODUCT_RECORDED"
                    or anchor.get("object_id") != row["object_id"] or anchor.get("object_kind") != row["kind"]
                    or anchor.get("after") != {"value":value,"value_sha256":row["value_sha256"]}):
                raise WorkStoreError("work object differs from its immutable event")
            objects.append({"id":row["object_id"],"kind":row["kind"],"value":value,"sha256":row["value_sha256"],"event_sequence":row["event_sequence"]})
        with self._lock:
            self._validated_object_cache[run_id] = (fingerprints, product_fingerprints, canonical(objects))
            if len(self._validated_object_cache) > 256:
                self._validated_object_cache.pop(next(iter(self._validated_object_cache)))
        terminal = {"completed":"RUN_COMPLETED", "blocked":"RUN_BLOCKED", "failed":"RUN_FAILED", "interrupted":"RUN_INTERRUPTED", "cancelled":"RUN_CANCELLED"}
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
        operations = {"completed": Operation.RUN_COMPLETED, "blocked": Operation.RUN_BLOCKED, "failed": Operation.RUN_FAILED,
                      "cancelled": Operation.RUN_CANCELLED, "interrupted": Operation.RUN_INTERRUPTED}
        if status not in operations:
            raise WorkStoreError("invalid terminal work status")
        with self.transaction() as db:
            self._require_owner(db, run_id, owner)
            if status == "completed" and db.execute("SELECT 1 FROM work_cancellation_requests WHERE run_id=?", (run_id,)).fetchone():
                status, message = "cancelled", "Review stopped after the current source check"
            elif status == "completed" and db.execute("SELECT 1 FROM work_pause_requests WHERE run_id=?", (run_id,)).fetchone():
                status, message = "interrupted", "Review paused after its final safe checkpoint; saved work can resume"
            self._append(db, run_id, operation=operations[status], object_kind="run", object_id=run_id,
                         status="unknown" if status == "interrupted" else "completed" if status in {"completed", "cancelled"} else "blocked", message=message,
                         worker_kind="kernel", after=after)
            db.execute("UPDATE work_runs SET status=?,owner=NULL,lease_until=NULL WHERE run_id=?", (status, run_id))

    def request_pause(self, run_id):
        with self.transaction() as db:
            run = self._run(db, run_id)
            if json.loads(run["request_json"]).get("facts_worker") != "reference":
                raise ConflictError("Only the local reference review can pause safely")
            if run["status"] not in ACTIVE:
                raise ConflictError("this review has already finished")
            if db.execute("SELECT 1 FROM work_pause_requests WHERE run_id=?", (run_id,)).fetchone():
                return
            db.execute("INSERT INTO work_pause_requests VALUES(?)", (run_id,))
            self._append(db, run_id, operation=Operation.RUN_PAUSE_REQUESTED, object_kind="run", object_id=run_id,
                         status="observed", message="Pause requested by the handler", worker_kind="kernel")
            if run["status"] in {"queued", "interrupted"}:
                self._append(db, run_id, operation=Operation.RUN_INTERRUPTED, object_kind="run", object_id=run_id,
                             status="unknown", message="Review paused before its next source check", worker_kind="kernel")
                db.execute("UPDATE work_runs SET status='interrupted',owner=NULL,lease_until=NULL WHERE run_id=?", (run_id,))

    def clear_pause(self, run_id):
        with self.transaction() as db:
            self._run(db, run_id)
            db.execute("DELETE FROM work_pause_requests WHERE run_id=?", (run_id,))

    def request_cancel(self, run_id, *, message="Stop requested by the handler", after=None):
        with self.transaction() as db:
            run = self._run(db, run_id)
            external = json.loads(run["request_json"]).get("facts_worker") == "external_facts"
            # Stopping further work never clears or retries an in-flight provider
            # request. Its response can still be receipted before the checkpoint.
            if external and run["status"] in {"completed", "blocked", "failed", "cancelled"}:
                return
            if run["status"] == "cancelled":
                return
            if run["status"] not in ACTIVE:
                raise ConflictError("this review has already finished")
            if not db.execute("SELECT 1 FROM work_cancellation_requests WHERE run_id=?", (run_id,)).fetchone():
                db.execute("INSERT INTO work_cancellation_requests VALUES(?)", (run_id,))
                self._append(db, run_id, operation=Operation.RUN_CANCEL_REQUESTED, object_kind="run", object_id=run_id,
                             status="observed", message="Stop requested after the current provider request" if external else message, worker_kind="kernel", after=after)
            if run["status"] in {"queued", "interrupted"}:
                pending = db.execute("SELECT 1 FROM work_calls WHERE run_id=? AND status='started' LIMIT 1", (run_id,)).fetchone()
                self._append(db, run_id, operation=Operation.RUN_CANCELLED, object_kind="run", object_id=run_id,
                             status="completed", message="Further work stopped; the prior operation still needs reconciliation" if pending else "Review stopped before the next source check", worker_kind="kernel")
                db.execute("UPDATE work_runs SET status='cancelled',owner=NULL,lease_until=NULL WHERE run_id=?", (run_id,))

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
