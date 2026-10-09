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

# Identity pins from the non-authorizing Mac execution-candidates packet.
# These restrict a later operator application; they never activate allowance.
ORIGINAL_NINE_CANDIDATES = [
    {
        "claim_id": "clm_e262801f9368bc12",
        "binding_sha256": "0846d88797534edb24b46340ac5d596d5fd952c1d85ed482661e5f9b8000d373",
        "original_binding_sha256": "6229c4e2c1084f234a27ed9c3fa4f1716b94fb8cc7ba1dd662aff05020b6a3ad",
        "identity": {
            "claim_id": "clm_e262801f9368bc12",
            "policy_id": "casepath.autonomous-local/1.0.0",
            "rule_set_sha256": "986bf411784ada0524f03d06ef5038d2fb90e27422ee12300a713c644d849343",
            "source_roster_sha256": "bfd762e5a7c569f30be4245ab0c8a161b82506fbada4330f634de2a8357dc7ae",
            "workflow_id": "autonomy.3f2638d4faf538af641c98bc"
        }
    },
    {
        "claim_id": "clm_521c20913f4e0f9b",
        "binding_sha256": "68bd7b4cc0ec8d59abcdeaf578d92e662dd79c7cd8fd8af63cfad11f10c36213",
        "original_binding_sha256": "891c905267ac6825bd03aa61c80f25d4c830d9b29d7a132a9976d8f424c293a7",
        "identity": {
            "claim_id": "clm_521c20913f4e0f9b",
            "policy_id": "casepath.autonomous-local/1.0.0",
            "rule_set_sha256": "986bf411784ada0524f03d06ef5038d2fb90e27422ee12300a713c644d849343",
            "source_roster_sha256": "eedda3aeeebe51660c572e8a8a9dcee123dd10a4b995def5c0377996bd2412a7",
            "workflow_id": "autonomy.5c02a7df9e603ad36ef048f6"
        }
    },
    {
        "claim_id": "clm_ee29ac770b1bf7b9",
        "binding_sha256": "289f28194f74ecfb7144e2b17e3d0e5b46c54cff4056b08e55aca8df3e8a04dd",
        "original_binding_sha256": "370ffc087137cd80afb9e896a861567fbcee34701202fadcb461eac77f2e1ddb",
        "identity": {
            "claim_id": "clm_ee29ac770b1bf7b9",
            "policy_id": "casepath.autonomous-local/1.0.0",
            "rule_set_sha256": "986bf411784ada0524f03d06ef5038d2fb90e27422ee12300a713c644d849343",
            "source_roster_sha256": "2b6257ef0e839436c5b26976c900d1a275d906146f671948f9a723b67b70da68",
            "workflow_id": "autonomy.edfa74ca44fb9f65c5701b4c"
        }
    },
    {
        "claim_id": "clm_f69b1747447bc221",
        "binding_sha256": "770f57ec0de6073f1d1009abf8a768c4abe4fbf45148cce8e4826373cbcb9c09",
        "original_binding_sha256": "7f55bdba8605f6147551782d125d0e434827698e99f86499f8651cc4e2c13278",
        "identity": {
            "claim_id": "clm_f69b1747447bc221",
            "policy_id": "casepath.autonomous-local/1.0.0",
            "rule_set_sha256": "986bf411784ada0524f03d06ef5038d2fb90e27422ee12300a713c644d849343",
            "source_roster_sha256": "e273c8501100b8fce897c33ec7afa6951c8abd116d82dec8e488505bd886f0af",
            "workflow_id": "autonomy.82b74a59b4b0261007edb9c4"
        }
    },
    {
        "claim_id": "clm_0c5e7c7723a3c694",
        "binding_sha256": "974ff199d11c260d0bc923e675d9c79bbb3bd75ffbf861f68999702bc717758c",
        "original_binding_sha256": "7efcb9de6e711e299818ee575411b7c4996f184e7d4cbbc5ea3784f6b1f3213f",
        "identity": {
            "claim_id": "clm_0c5e7c7723a3c694",
            "policy_id": "casepath.autonomous-local/1.0.0",
            "rule_set_sha256": "986bf411784ada0524f03d06ef5038d2fb90e27422ee12300a713c644d849343",
            "source_roster_sha256": "a6763a11101c5683fe2c0f9f028d6bad77243fef37d6629e115641d6f047c674",
            "workflow_id": "autonomy.86061008d180f70727c4f23c"
        }
    },
    {
        "claim_id": "clm_2a9c260c26afaa34",
        "binding_sha256": "62bef9011eab6221fbedc03387f2805a39a56b27956d7864e757f6932a3a7082",
        "original_binding_sha256": "e1e9a7c4c63c1e721ba604c7a1aa12bb9056deb7f627b616a65371a1c4efaf0b",
        "identity": {
            "claim_id": "clm_2a9c260c26afaa34",
            "policy_id": "casepath.autonomous-local/1.0.0",
            "rule_set_sha256": "986bf411784ada0524f03d06ef5038d2fb90e27422ee12300a713c644d849343",
            "source_roster_sha256": "73a0c0eeb5699b7080be310c2fecd8abbcb533526d422c39e2537c01d2e3f85a",
            "workflow_id": "autonomy.2de798f221d3ecaf5bbc7916"
        }
    },
    {
        "claim_id": "clm_c44ddc0914ba9298",
        "binding_sha256": "ecc52d165d8784124fd301a68198cf7f74a72e1051ef83713fff356b41e130ad",
        "original_binding_sha256": "e91da0c18f43791ec9882b654c520dd99e72ec16920b54264e2625fb914634af",
        "identity": {
            "claim_id": "clm_c44ddc0914ba9298",
            "policy_id": "casepath.autonomous-local/1.0.0",
            "rule_set_sha256": "986bf411784ada0524f03d06ef5038d2fb90e27422ee12300a713c644d849343",
            "source_roster_sha256": "5c05cb6bc5f0ebad8a649f6565aeb6a74abffc6fbfe41711dcdccb843eb51d9f",
            "workflow_id": "autonomy.91d09441d92b69e3f6d6b692"
        }
    },
    {
        "claim_id": "clm_7dbd7c7d1c4ddf90",
        "binding_sha256": "2464f5bb86f065e9c7ecbca0027966e68eb047936e2f3c98f3bfa7ce133768d6",
        "original_binding_sha256": "08e2798cbc1121de5c43d9cf1b76367ae885a170b81f4c3d7c14e78726500ecf",
        "identity": {
            "claim_id": "clm_7dbd7c7d1c4ddf90",
            "policy_id": "casepath.autonomous-local/1.0.0",
            "rule_set_sha256": "986bf411784ada0524f03d06ef5038d2fb90e27422ee12300a713c644d849343",
            "source_roster_sha256": "c615f63d7b60a7aec55b3bcd5d607c9b7aefbae9e68de82d0c785cccbba82f50",
            "workflow_id": "autonomy.02621d905b30706c1fb4f7d2"
        }
    },
    {
        "claim_id": "clm_9a179a4481767d43",
        "binding_sha256": "c168703d5ae2669ab15e045d2736ceca0c22e0f8a19483cbc00406bc787c4270",
        "original_binding_sha256": "0921c6729ccfd1bd655507b9fd3daa06fd9cee70c3d7b6544bb111a5fe5cc6e9",
        "identity": {
            "claim_id": "clm_9a179a4481767d43",
            "policy_id": "casepath.autonomous-local/1.0.0",
            "rule_set_sha256": "986bf411784ada0524f03d06ef5038d2fb90e27422ee12300a713c644d849343",
            "source_roster_sha256": "5e866440a03d6d14a4f32dcf862d238ff3aef58e299e67545bb064953eb9e83c",
            "workflow_id": "autonomy.caf321179cc7b4cc4f7bf27e"
        }
    }
]
ORIGINAL_NINE_CONFIG = {
    "adapter_version": "casepath.autonomous-model/1.0.0",
    "canonical_model": "openai/gpt-6-luna-20260922",
    "catalogue_entry_sha256": "9aff2d6e3996eeb35eb5dd22a26904b6fcea7f610312b98c4222812f185720d9",
    "completion_price": "5E-7",
    "context_length": 1050000,
    "free": False,
    "max_calls_per_workflow": 2,
    "max_output_tokens": 3500,
    "max_request_bytes": 64000,
    "model": "openai/gpt-6-luna",
    "prompt_price": "1.25E-7",
    "protocol": "strict_json_schema",
    "reasoning_supported": True,
    "request_price": "0",
    "timeout_seconds": 60
}
ORIGINAL_NINE_SELECTION_SHA256 = "7d70edaf6e886ace18ea55f6b41ab3e44dd5760431bcf8f844ee47ab30b9537e"
ORIGINAL_NINE_CORPUS_SHA256 = "7c885d3fd112dfc7314719d661fa73449f72b7bdf5b83159da9fa3e0b9a1b7eb"

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
CREATE TRIGGER IF NOT EXISTS work_external_budget_no_update BEFORE UPDATE ON work_external_budget
 BEGIN SELECT RAISE(ABORT,'external budget policy is immutable'); END;
CREATE TRIGGER IF NOT EXISTS work_external_budget_no_delete BEFORE DELETE ON work_external_budget
 BEGIN SELECT RAISE(ABORT,'external budget policy is immutable'); END;
CREATE TRIGGER IF NOT EXISTS work_external_budget_no_replace BEFORE INSERT ON work_external_budget
 WHEN EXISTS(SELECT 1 FROM work_external_budget)
 BEGIN SELECT RAISE(ABORT,'external budget policy is immutable'); END;
CREATE TABLE IF NOT EXISTS work_external_run_grant (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1), receipt_json TEXT NOT NULL, receipt_sha256 TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS work_external_run_grant_no_update BEFORE UPDATE ON work_external_run_grant
 BEGIN SELECT RAISE(ABORT,'external run grant is immutable'); END;
CREATE TRIGGER IF NOT EXISTS work_external_run_grant_no_delete BEFORE DELETE ON work_external_run_grant
 BEGIN SELECT RAISE(ABORT,'external run grant is immutable'); END;
CREATE TRIGGER IF NOT EXISTS work_external_run_grant_no_replace BEFORE INSERT ON work_external_run_grant
 WHEN EXISTS(SELECT 1 FROM work_external_run_grant)
 BEGIN SELECT RAISE(ABORT,'external run grant is immutable'); END;
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
CREATE INDEX IF NOT EXISTS work_calls_tool_status ON work_calls(tool_name,status);
CREATE TABLE IF NOT EXISTS work_objects (
 run_id TEXT NOT NULL REFERENCES work_runs(run_id), object_id TEXT NOT NULL,
 kind TEXT NOT NULL, value_json TEXT NOT NULL, value_sha256 TEXT NOT NULL,
 event_sequence INTEGER NOT NULL,
 PRIMARY KEY(run_id,object_id)
);
"""

# This ledger shares the original budget, but never rewrites historical permits.
for _table, _keys in (("work_autonomous_policy", "singleton INTEGER PRIMARY KEY CHECK(singleton=1)"),
                     ("work_original_nine_grant", "singleton INTEGER PRIMARY KEY CHECK(singleton=1)"),
                     ("work_autonomous_capacity_grant", "singleton INTEGER PRIMARY KEY CHECK(singleton=1)"),
                     ("work_autonomous_workflows", "workflow_id TEXT PRIMARY KEY"),
                     ("work_autonomous_calls", "workflow_id TEXT NOT NULL, stage TEXT NOT NULL, PRIMARY KEY(workflow_id,stage)"),
                     ("work_autonomous_outcomes", "workflow_id TEXT NOT NULL, stage TEXT NOT NULL, PRIMARY KEY(workflow_id,stage)"),
                     ("work_autonomous_terminals", "workflow_id TEXT PRIMARY KEY")):
    # Table constraints must follow the record columns.
    _columns, _separator, _constraint = _keys.partition(", PRIMARY KEY")
    SCHEMA += f"CREATE TABLE IF NOT EXISTS {_table} ({_columns}, record_json TEXT NOT NULL, record_sha256 TEXT NOT NULL{', PRIMARY KEY' + _constraint if _separator else ''});\n"
    for _action in ("UPDATE", "DELETE"):
        SCHEMA += f"CREATE TRIGGER IF NOT EXISTS {_table}_no_{_action.lower()} BEFORE {_action} ON {_table} BEGIN SELECT RAISE(ABORT,'autonomous records are immutable'); END;\n"
    _match = "singleton=NEW.singleton" if _keys.startswith("singleton") else "workflow_id=NEW.workflow_id"
    if _table.endswith(("calls", "outcomes")):
        _match += " AND stage=NEW.stage"
    SCHEMA += f"CREATE TRIGGER IF NOT EXISTS {_table}_no_replace BEFORE INSERT ON {_table} WHEN EXISTS(SELECT 1 FROM {_table} WHERE {_match}) BEGIN SELECT RAISE(ABORT,'autonomous records are immutable'); END;\n"


class WorkStore:
    def __init__(self, path: Path, *, connection_factory=None, validated_source_commit=None):
        self.path = Path(path)
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise WorkStoreError("work journal path cannot be a symlink")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._connection_factory = connection_factory
        # Only server/operator composition supplies this value. It is never
        # accepted from a workflow request, model config or approval string.
        self._validated_source_commit = validated_source_commit
        self._lock = RLock()
        self._validated_event_cache: dict[str, tuple[str, tuple[tuple[int, str, bytes], ...], list[dict]]] = {}
        self._validated_object_cache: dict[str, tuple[tuple, tuple, bytes]] = {}
        with self.connect() as db:
            db.executescript(SCHEMA)
            if connection_factory is None:
                db.execute("PRAGMA journal_mode=WAL")
        # Keep one reader open so short tool-call connections do not checkpoint
        # the WAL after every durable commit. FULL synchronous still protects it.
        self._keeper = None
        if connection_factory is None:
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
        if self._connection_factory is None:
            db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA busy_timeout=10000")
        else:
            db = self._connection_factory()
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

    @staticmethod
    def _validate_grant_command(expected_budget_sha256, actor, reason, idempotency_key):
        if (not isinstance(expected_budget_sha256, str) or len(expected_budget_sha256) != 64
                or any(c not in "0123456789abcdef" for c in expected_budget_sha256)):
            raise WorkStoreError("a valid expected budget snapshot hash is required")
        for name, value, minimum, maximum in (("actor", actor, 1, 180), ("reason", reason, 1, 2000),
                                               ("idempotency key", idempotency_key, 8, 128)):
            if (not isinstance(value, str) or not minimum <= len(value) <= maximum
                    or value != value.strip() or not value.isprintable()):
                raise WorkStoreError("invalid external run grant " + name)

    def _external_run_grant(self, db, policy):
        row = db.execute("SELECT * FROM work_external_run_grant WHERE singleton=1").fetchone()
        if row is None:
            return None
        try:
            receipt = json.loads(row["receipt_json"])
            material = {k: v for k, v in receipt.items() if k != "grant_sha256"}
            prior = receipt["prior_budget"]
            self._validate_grant_command(receipt["prior_budget_sha256"], receipt["actor"],
                                         receipt["reason"], receipt["idempotency_key"])
            if (set(material) != {"contract", "additional_runs", "base_policy_sha256", "prior_budget_sha256",
                                  "prior_budget", "actor", "reason", "idempotency_key", "granted_at"}
                    or receipt["contract"] != "casepath.external-run-grant/1.0.0"
                    or type(receipt["additional_runs"]) is not int or receipt["additional_runs"] != 1
                    or policy is None or policy["max_runs"] != 3
                    or receipt["base_policy_sha256"] != digest(policy)
                    or receipt["grant_sha256"] != row["receipt_sha256"] or digest(material) != row["receipt_sha256"]
                    or canonical(receipt).decode() != row["receipt_json"]
                    or digest(prior) != receipt["prior_budget_sha256"]
                    or any(prior[k] != v for k, v in policy.items())
                    or prior["base_policy_sha256"] != digest(policy)
                    or type(prior["runs_used"]) is not int or prior["runs_used"] != 3
                    or type(prior["effective_max_runs"]) is not int or prior["effective_max_runs"] != 3
                    or prior["run_grant"] is not None or prior["in_flight"] is not False
                    or prior["automatic_retry"] is not False or prior["can_start"] is not False
                    or datetime.fromisoformat(receipt["granted_at"]).utcoffset() != timezone.utc.utcoffset(None)):
                raise ValueError
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise WorkStoreError("persisted external run grant identity is invalid") from exc
        return receipt

    def grant_one_external_run(self, expected_budget_sha256, actor, reason, idempotency_key):
        """Record explicit approval for one fourth run; never send or reset work."""
        self._validate_grant_command(expected_budget_sha256, actor, reason, idempotency_key)
        with self.transaction() as db:
            budget = self._external_budget(db)
            if budget is None:
                raise WorkStoreError("an existing external budget policy is required")
            prior = budget["run_grant"]
            if prior:
                if (prior["prior_budget_sha256"], prior["actor"], prior["reason"], prior["idempotency_key"]) != (
                        expected_budget_sha256, actor, reason, idempotency_key):
                    raise ConflictError("the single external run grant already binds a different approval")
                return prior
            if digest(budget) != expected_budget_sha256:
                raise ConflictError("the external budget snapshot changed; inspect it before approval")
            active = db.execute("SELECT 1 FROM work_runs WHERE run_id IN (SELECT run_id FROM work_external_permits) "
                                "AND status IN ('queued','running','interrupted') LIMIT 1").fetchone()
            if budget["in_flight"] or active:
                raise ConflictError("active or pending provider work must finish before a grant")
            if budget["max_runs"] != 3 or budget["runs_used"] != 3:
                raise ConflictError("the original three-run budget must be exhausted before a grant")
            receipt = {"contract": "casepath.external-run-grant/1.0.0", "additional_runs": 1,
                       "base_policy_sha256": budget["base_policy_sha256"],
                       "prior_budget_sha256": expected_budget_sha256, "prior_budget": budget,
                       "actor": actor, "reason": reason, "idempotency_key": idempotency_key, "granted_at": utcnow()}
            receipt["grant_sha256"] = digest(receipt)
            db.execute("INSERT INTO work_external_run_grant VALUES(1,?,?)",
                       (canonical(receipt).decode(), receipt["grant_sha256"]))
            return receipt

    def _external_usage(self, db):
        """Derive spend from validated journals within the admission transaction."""
        rows = db.execute("SELECT * FROM work_runs WHERE run_id IN (SELECT run_id FROM work_external_permits)").fetchall()
        event_rows = db.execute("SELECT * FROM work_events WHERE run_id IN (SELECT run_id FROM work_external_permits) ORDER BY run_id,sequence").fetchall()
        events_by_run = {}
        for event_row in event_rows:
            events_by_run.setdefault(event_row['run_id'], []).append(event_row)
        runs, calls = {}, []
        for row in rows:
            run = self._decode_run(dict(row))
            run_id = run["run_id"]
            events = self._validate_events(run, events_by_run.get(run_id, []))
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
            runs[run_id] = {"run": run, "calls": run_calls,
                            "grant_sha256": (events[0].get("after") or {}).get("external_run_grant_sha256") if events else None}
        pending = db.execute("SELECT 1 FROM work_calls WHERE tool_name='provider_request' AND status='started' LIMIT 1").fetchone() is not None
        return runs, calls, pending

    def _external_budget(self, db, usage=None):
        # The remote adapter fetches these in one transaction-scoped batch.
        # Local SQLite keeps ordinary reads; nothing is cached across commits.
        prefetch = getattr(db, 'prefetch', None)
        if prefetch is not None:
            prefetch([(sql, ()) for sql in (
                "SELECT * FROM work_external_budget WHERE singleton=1",
                "SELECT * FROM work_external_run_grant WHERE singleton=1",
                "SELECT * FROM work_autonomous_policy WHERE singleton=1",
                "SELECT * FROM work_autonomous_capacity_grant WHERE singleton=1",
                "SELECT * FROM work_original_nine_grant WHERE singleton=1",
                "SELECT * FROM work_runs WHERE run_id IN (SELECT run_id FROM work_external_permits)",
                "SELECT * FROM work_events WHERE run_id IN (SELECT run_id FROM work_external_permits) ORDER BY run_id,sequence",
                "SELECT 1 FROM work_calls WHERE tool_name='provider_request' AND status='started' LIMIT 1",
                "SELECT * FROM work_autonomous_workflows ORDER BY workflow_id",
                "SELECT * FROM work_autonomous_calls ORDER BY workflow_id,stage",
                "SELECT * FROM work_autonomous_outcomes ORDER BY workflow_id,stage",
                "SELECT * FROM work_autonomous_terminals ORDER BY workflow_id",
            )])
        row = db.execute("SELECT * FROM work_external_budget WHERE singleton=1").fetchone()
        if row is None:
            self._external_run_grant(db, None)  # An orphaned allowance cannot become a permit.
            self._autonomous_policy(db, None)
            return None
        policy = json.loads(row["policy_json"])
        if digest(policy) != row["policy_sha256"]:
            raise WorkStoreError("persisted demo budget identity differs")
        grant = self._external_run_grant(db, policy)
        autonomous_policy = self._autonomous_policy(db, policy)
        capacity_grant = self._autonomous_capacity_grant(db, policy, autonomous_policy)
        effective_max_runs = policy["max_runs"] + (grant["additional_runs"] if grant else 0)
        runs, calls, pending = usage or self._external_usage(db)
        granted_runs = [r for r in runs.values() if r["grant_sha256"] is not None]
        if (len(runs) > effective_max_runs or len(granted_runs) > 1
                or len(runs) > policy["max_runs"] and not granted_runs
                or any(not grant or r["grant_sha256"] != grant["grant_sha256"] for r in granted_runs)):
            raise WorkStoreError("external run grant does not bind the admitted allowance")
        autonomous = self._autonomous_usage(db, autonomous_policy)
        nine = self._original_nine_grant(db, policy, autonomous_policy, capacity_grant)
        old_autonomous, nine_works, nine_actual, nine_reserved = self._original_nine_usage(db, nine, autonomous)
        granted_workflows, granted_calls = self._autonomous_capacity_usage(capacity_grant, runs, calls, old_autonomous)
        calls = [*calls, *autonomous["calls"]]
        pending = pending or autonomous["pending"]
        actual = sum((c["cost"] for c in calls if c["cost"] is not None), Decimal(0))
        reserved = sum((c["reserved"] for c in calls if c["cost"] is None), Decimal(0)) + autonomous["unspent_reserved"]
        for record in runs.values():
            if record["run"]["status"] in ACTIVE:
                config = record["run"]["request"].get("worker_config") or {}
                limit = self._money(config.get("cost_limit_usd", policy["run_cost_limit_usd"]))
                committed = sum((c["cost"] if c["cost"] is not None else c["reserved"] for c in record["calls"]), Decimal(0))
                reserved += max(Decimal(0), limit - committed)
        effective_total = nine["effective_total_cost_limit_usd"] if nine else policy["total_cost_limit_usd"]
        available = max(Decimal(0), self._money(effective_total) - actual - reserved)
        exceeded = any(c["cost"] is not None and c["cost"] > c["reserved"] for c in calls)
        reason = ("provider_cost_bound_exceeded" if exceeded else "provider_outcome_pending" if pending else
                  "run_limit_reached" if len(runs) >= effective_max_runs else
                  "call_limit_reached" if len(calls) >= policy["max_provider_calls"] else
                  "cost_limit_reached" if available < self._money(policy["run_cost_limit_usd"]) else None)
        result = {"scope": "persistent_local_demo", **policy, "runs_used": len(runs), "provider_calls_used": len(calls),
                "base_policy_sha256": row["policy_sha256"], "effective_max_runs": effective_max_runs, "run_grant": grant,
                "actual_cost_usd": str(actual), "reserved_cost_usd": str(reserved), "remaining_cost_usd": str(available),
                "unknown_calls": sum(c["cost"] is None for c in calls), "in_flight": pending,
                "can_start": reason is None, "reason": reason, "automatic_retry": False}
        if autonomous_policy:
            effective_calls = policy["max_provider_calls"] + (capacity_grant["additional_provider_calls"] if capacity_grant else 0)
            if nine:
                effective_calls += 18
            slots_exhausted = len(nine_works) >= 9 if nine else bool(capacity_grant and granted_workflows >= capacity_grant["additional_workflows"])
            nine_remaining = Decimal("0.18") - nine_actual - nine_reserved
            nine_workflow_pending = any(work["terminal"] is None for work in nine_works.values())
            auto_reason = ("provider_cost_bound_exceeded" if exceeded else "provider_outcome_pending" if pending else
                           "workflow_in_progress" if nine_workflow_pending else
                           "call_limit_reached" if len(calls) + 2 > effective_calls or slots_exhausted else
                           "cost_limit_reached" if available < self._money(autonomous_policy["workflow_cost_limit_usd"])
                           or nine and nine_remaining < Decimal("0.02") else None)
            result.update(autonomous_policy=autonomous_policy, autonomous_workflows_used=len(autonomous["workflows"]),
                          autonomous_provider_calls_used=len(autonomous["calls"]),
                          autonomous_capacity_grant=capacity_grant, effective_autonomous_max_provider_calls=effective_calls,
                          autonomous_grant_workflows_used=granted_workflows, autonomous_grant_provider_calls_used=granted_calls,
                          autonomous_can_start=auto_reason is None, autonomous_reason=auto_reason)
            if nine:
                result.update(original_nine_grant=nine, effective_total_cost_limit_usd=effective_total,
                    original_nine_workflow_pending=nine_workflow_pending,
                    original_nine_workflows_used=len(nine_works), original_nine_provider_calls_used=sum(len(w["calls"]) for w in nine_works.values()),
                    original_nine_actual_cost_usd=str(nine_actual), original_nine_reserved_cost_usd=str(nine_reserved),
                    original_nine_committed_cost_usd=str(nine_actual + nine_reserved),
                    original_nine_remaining_cost_usd=str(max(Decimal(0),nine_remaining)))
        return result

    @staticmethod
    def _autonomous_decode(row, field):
        if row is None:
            return None
        try:
            value = json.loads(row["record_json"])
            material = {k: v for k, v in value.items() if k != field}
            if (value[field] != row["record_sha256"] or digest(material) != value[field]
                    or canonical(value).decode() != row["record_json"]):
                raise ValueError
            return value
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise WorkStoreError("autonomous record identity is invalid") from exc

    @staticmethod
    def _autonomous_insert(db, table, keys, material, field):
        record = {**material, field: digest(material)}
        names = [*keys, "record_json", "record_sha256"]
        db.execute(f"INSERT INTO {table} ({','.join(names)}) VALUES({','.join('?' for _ in names)})",
                   (*keys.values(), canonical(record).decode(), record[field]))
        return record

    @staticmethod
    def _autonomous_hash(value):
        return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)

    @staticmethod
    def _autonomous_time(value):
        return isinstance(value, str) and datetime.fromisoformat(value).utcoffset() == timezone.utc.utcoffset(None)

    def _autonomous_inputs(self, identity, config):
        """The same bounds apply at admission and after a process reload."""
        try:
            if not isinstance(identity, dict) or len(canonical(identity)) > 8000 or not isinstance(config, dict):
                raise ValueError
            for key in ("workflow_id", "claim_id"):
                value = identity.get(key)
                if not isinstance(value, str) or not 1 <= len(value) <= 180 or value != value.strip() or not value.isprintable():
                    raise ValueError
            if (type(config["max_request_bytes"]) is not int or not 1 <= config["max_request_bytes"] <= 64000
                    or type(config["max_output_tokens"]) is not int or not 1 <= config["max_output_tokens"] <= 3500
                    or config["max_calls_per_workflow"] != 2 or type(config["max_calls_per_workflow"]) is not int
                    or type(config["context_length"]) is not int or config["context_length"] < 8192
                    or config["protocol"] != "strict_json_schema" or config["adapter_version"] != "casepath.autonomous-model/1.0.0"
                    or not self._autonomous_hash(config["catalogue_entry_sha256"])
                    or not isinstance(config["model"], str) or not 3 <= len(config["model"]) <= 181
                    or config["model"].startswith("openrouter/")
                    or type(config["reasoning_supported"]) is not bool or type(config["free"]) is not bool
                    or type(config["timeout_seconds"]) not in (int, float) or not 1 <= config["timeout_seconds"] <= 60):
                raise ValueError
            prices = [self._money(config[k]) for k in ("prompt_price", "completion_price", "request_price")]
            if config["free"] != all(p == 0 for p in prices):
                raise ValueError
            canonical(config)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise WorkStoreError("autonomous identity or frozen provider bounds are invalid") from exc

    def _autonomous_policy(self, db, base):
        value = self._autonomous_decode(db.execute("SELECT * FROM work_autonomous_policy WHERE singleton=1").fetchone(), "policy_sha256")
        if value is None:
            if any(db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() for table in
                   ("work_autonomous_workflows", "work_autonomous_calls", "work_autonomous_outcomes", "work_autonomous_terminals", "work_autonomous_capacity_grant", "work_original_nine_grant")):
                raise WorkStoreError("autonomous work has no sealed policy")
            return None
        try:
            prior = value["prior_budget"]
            self._validate_grant_command(value["prior_budget_sha256"], value["actor"], value["reason"], value["idempotency_key"])
            if (set(value) != {"contract", "base_policy_sha256", "prior_budget_sha256", "prior_budget", "actor", "reason",
                               "idempotency_key", "activated_at", "max_calls_per_workflow", "workflow_cost_limit_usd", "policy_sha256"}
                    or value["contract"] != "casepath.autonomous-budget-policy/1.0.0" or base is None
                    or value["base_policy_sha256"] != digest(base)
                    or prior["base_policy_sha256"] != digest(base) or digest(prior) != value["prior_budget_sha256"]
                    or any(prior[k] != v for k, v in base.items()) or "autonomous_policy" in prior
                    or type(value["max_calls_per_workflow"]) is not int or value["max_calls_per_workflow"] != 2
                    or value["workflow_cost_limit_usd"] != base["run_cost_limit_usd"]
                    or self._money(value["workflow_cost_limit_usd"]) > Decimal("0.02")
                    or prior["in_flight"] is not False
                    or datetime.fromisoformat(value["activated_at"]).utcoffset() != timezone.utc.utcoffset(None)):
                raise ValueError
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise WorkStoreError("autonomous policy does not preserve the original budget") from exc
        return value

    def activate_autonomous_policy(self, expected_budget_sha256, actor, reason, idempotency_key):
        """One durable mode activation; no inference, per-run grant or budget reset."""
        self._validate_grant_command(expected_budget_sha256, actor, reason, idempotency_key)
        with self.transaction() as db:
            budget = self._external_budget(db)
            if budget is None:
                raise WorkStoreError("the existing external budget is required")
            prior = budget.get("autonomous_policy")
            if prior:
                if (prior["prior_budget_sha256"], prior["actor"], prior["reason"], prior["idempotency_key"]) != (
                        expected_budget_sha256, actor, reason, idempotency_key):
                    raise ConflictError("autonomous policy already binds a different activation")
                return prior
            if digest(budget) != expected_budget_sha256:
                raise ConflictError("the expected external budget changed")
            active = db.execute("SELECT 1 FROM work_runs WHERE run_id IN (SELECT run_id FROM work_external_permits) "
                                "AND status IN ('queued','running','interrupted') LIMIT 1").fetchone()
            if budget["in_flight"] or active:
                raise ConflictError("active provider work must settle before policy activation")
            return self._autonomous_insert(db, "work_autonomous_policy", {"singleton": 1}, {
                "contract": "casepath.autonomous-budget-policy/1.0.0", "base_policy_sha256": budget["base_policy_sha256"],
                "prior_budget_sha256": expected_budget_sha256, "prior_budget": budget, "actor": actor, "reason": reason,
                "idempotency_key": idempotency_key, "activated_at": utcnow(), "max_calls_per_workflow": 2,
                "workflow_cost_limit_usd": budget["run_cost_limit_usd"]}, "policy_sha256")

    def _autonomous_capacity_grant(self, db, base, policy):
        value = self._autonomous_decode(db.execute("SELECT * FROM work_autonomous_capacity_grant WHERE singleton=1").fetchone(), "grant_sha256")
        if value is None:
            return None
        try:
            prior, roster = value["prior_budget"], value["prior_workflows"]
            self._validate_grant_command(value["prior_budget_sha256"], value["actor"], value["reason"], value["idempotency_key"])
            if (set(value) != {"contract", "additional_workflows", "additional_provider_calls", "base_policy_sha256",
                               "autonomous_policy_sha256", "prior_budget_sha256", "prior_budget", "prior_workflows",
                               "actor", "reason", "idempotency_key", "granted_at", "grant_sha256"}
                    or value["contract"] != "casepath.autonomous-capacity-grant/1.0.0" or base is None or policy is None
                    or base != {"max_runs": 3, "max_provider_calls": 18, "total_cost_limit_usd": "0.10", "run_cost_limit_usd": "0.02"}
                    or type(value["additional_workflows"]) is not int or value["additional_workflows"] != 3
                    or type(value["additional_provider_calls"]) is not int or value["additional_provider_calls"] != 6
                    or value["base_policy_sha256"] != digest(base) or value["autonomous_policy_sha256"] != policy["policy_sha256"]
                    or digest(prior) != value["prior_budget_sha256"] or prior["base_policy_sha256"] != digest(base)
                    or any(prior[k] != v for k, v in base.items()) or prior["autonomous_policy"] != policy
                    or prior["autonomous_capacity_grant"] is not None or prior["effective_autonomous_max_provider_calls"] != 18
                    or type(prior["provider_calls_used"]) is not int or prior["provider_calls_used"] not in (17, 18)
                    or any(type(prior[k]) is not int or prior[k] != v for k, v in
                           (("autonomous_grant_workflows_used", 0), ("autonomous_grant_provider_calls_used", 0)))
                    or any(type(prior[k]) is not int or not 0 <= prior[k] <= limit for k, limit in
                           (("runs_used", 4), ("autonomous_provider_calls_used", 18), ("unknown_calls", 18)))
                    or prior["in_flight"] is not False or prior["automatic_retry"] is not False
                    or prior["autonomous_can_start"] is not False or prior["autonomous_reason"] != "call_limit_reached"
                    or self._money(prior["remaining_cost_usd"]) < Decimal("0.06")
                    or self._money(prior["actual_cost_usd"]) + self._money(prior["reserved_cost_usd"]) + self._money(prior["remaining_cost_usd"]) != Decimal("0.10")
                    or not isinstance(roster, list) or type(prior["autonomous_workflows_used"]) is not int
                    or len(roster) != prior["autonomous_workflows_used"] or len(roster) > 18
                    or not len(roster) <= prior["autonomous_provider_calls_used"] <= 2 * len(roster)
                    or any(set(item) != {"workflow_id", "workflow_sha256"}
                           or not isinstance(item["workflow_id"], str) or not 1 <= len(item["workflow_id"]) <= 180
                           or not self._autonomous_hash(item["workflow_sha256"]) for item in roster)
                    or [item["workflow_id"] for item in roster] != sorted({item["workflow_id"] for item in roster})
                    or not self._autonomous_time(value["granted_at"])):
                raise ValueError
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise WorkStoreError("autonomous capacity grant does not preserve the original allowance") from exc
        return value

    def _autonomous_capacity_usage(self, grant, runs, legacy_calls, autonomous):
        """Bind the extension to new workflows; historical records never move into it."""
        works = autonomous["workflows"]
        if grant is None:
            if any("capacity_grant_sha256" in work["record"] for work in works.values()):
                raise WorkStoreError("autonomous workflow has no capacity grant")
            return 0, 0
        prior = grant["prior_budget"]
        roster = {row["workflow_id"]: row["workflow_sha256"] for row in grant["prior_workflows"]}
        try:
            if (any(key not in works or works[key]["record"]["workflow_sha256"] != value
                    or works[key]["terminal"] is None or "capacity_grant_sha256" in works[key]["record"]
                    for key, value in roster.items())
                    or len(legacy_calls) != prior["provider_calls_used"] - prior["autonomous_provider_calls_used"]
                    or len(runs) != prior["runs_used"] or any(r["run"]["status"] in ACTIVE for r in runs.values())
                    or sum(len(works[key]["calls"]) for key in roster) != prior["autonomous_provider_calls_used"]):
                raise ValueError
            added = [work for key, work in works.items() if key not in roster]
            call_count = sum(len(work["calls"]) for work in added)
            if (len(added) > grant["additional_workflows"] or call_count > grant["additional_provider_calls"]
                    or any(work["record"].get("capacity_grant_sha256") != grant["grant_sha256"] for work in added)):
                raise ValueError
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise WorkStoreError("autonomous capacity grant does not bind the preserved workflow roster") from exc
        return len(added), call_count

    def grant_three_autonomous_workflows(self, expected_budget_sha256, actor, reason, idempotency_key):
        """One offline extension: three workflows, six calls, unchanged dollar limits."""
        self._validate_grant_command(expected_budget_sha256, actor, reason, idempotency_key)
        with self.transaction() as db:
            budget = self._external_budget(db)
            if budget is None or budget.get("autonomous_policy") is None:
                raise WorkStoreError("an existing autonomous budget policy is required")
            prior = budget["autonomous_capacity_grant"]
            if prior:
                if (prior["prior_budget_sha256"], prior["actor"], prior["reason"], prior["idempotency_key"]) != (
                        expected_budget_sha256, actor, reason, idempotency_key):
                    raise ConflictError("the single autonomous capacity grant already binds a different approval")
                return prior
            if digest(budget) != expected_budget_sha256:
                raise ConflictError("the autonomous budget snapshot changed; inspect it before approval")
            if any(budget[k] != v for k, v in {"max_runs": 3, "max_provider_calls": 18, "total_cost_limit_usd": "0.10", "run_cost_limit_usd": "0.02"}.items()):
                raise ConflictError("the original bounded demo policy is required for this grant")
            usage = self._autonomous_usage(db, budget["autonomous_policy"])
            active = db.execute("SELECT 1 FROM work_runs WHERE run_id IN (SELECT run_id FROM work_external_permits) "
                                "AND status IN ('queued','running','interrupted') LIMIT 1").fetchone()
            if budget["in_flight"] or active or any(work["terminal"] is None for work in usage["workflows"].values()):
                raise ConflictError("active or pending provider work must finish before a capacity grant")
            if budget["provider_calls_used"] not in (17, 18) or budget["autonomous_reason"] != "call_limit_reached":
                raise ConflictError("the original eighteen-call allowance must be exhausted for a two-call workflow before a capacity grant")
            if self._money(budget["remaining_cost_usd"]) < Decimal("0.06"):
                raise ConflictError("three workflow ceilings must fit within the remaining original dollar allowance")
            return self._autonomous_insert(db, "work_autonomous_capacity_grant", {"singleton": 1}, {
                "contract": "casepath.autonomous-capacity-grant/1.0.0", "additional_workflows": 3, "additional_provider_calls": 6,
                "base_policy_sha256": budget["base_policy_sha256"], "autonomous_policy_sha256": budget["autonomous_policy"]["policy_sha256"],
                "prior_budget_sha256": expected_budget_sha256, "prior_budget": budget,
                "prior_workflows": [{"workflow_id": key, "workflow_sha256": work["record"]["workflow_sha256"]}
                                    for key, work in sorted(usage["workflows"].items())],
                "actor": actor, "reason": reason, "idempotency_key": idempotency_key, "granted_at": utcnow()}, "grant_sha256")

    @staticmethod
    def validate_original_nine_budget_snapshot(value):
        fields = {"scope","max_runs","max_provider_calls","total_cost_limit_usd","run_cost_limit_usd",
            "runs_used","provider_calls_used","base_policy_sha256","effective_max_runs","run_grant",
            "actual_cost_usd","reserved_cost_usd","remaining_cost_usd","unknown_calls","in_flight",
            "can_start","reason","automatic_retry","autonomous_policy","autonomous_workflows_used",
            "autonomous_provider_calls_used","autonomous_capacity_grant","effective_autonomous_max_provider_calls",
            "autonomous_grant_workflows_used","autonomous_grant_provider_calls_used","autonomous_can_start","autonomous_reason"}
        if not isinstance(value,dict) or set(value) != fields:
            raise WorkStoreError("a complete saved old-epoch WorkStore budget projection is required")

    @staticmethod
    def validate_original_nine_preflight(value):
        """Validate identity and bounds, never infer human approval from a seal."""
        try:
            if (not isinstance(value, dict) or value["preflight_sha256"] != digest({k:v for k,v in value.items() if k != "preflight_sha256"})
                    or value["contract"] != "casepath.original-nine-preflight/1.0.0"
                    or value["inactive"] is not True or value["allowance_applied"] is not False
                    or value["execution_authorized"] is not False or value["automatic_retry"] is not False
                    or type(value["provider_calls_sent"]) is not int or value["provider_calls_sent"] != 0
                    or type(value["source_admissions"]) is not int or value["source_admissions"] != 0
                    or value["selection_file_sha256"] != ORIGINAL_NINE_SELECTION_SHA256
                    or value["corpus_manifest_file_sha256"] != ORIGINAL_NINE_CORPUS_SHA256
                    or canonical(value["frozen_model_config"]) != canonical(ORIGINAL_NINE_CONFIG)
                    or value["max_new_workflows"] != 9 or type(value["max_new_workflows"]) is not int
                    or value["max_new_physical_calls"] != 18 or type(value["max_new_physical_calls"]) is not int
                    or value["max_request_bytes"] != 64000 or value["max_output_tokens"] != 3500
                    or not isinstance(value["source_commit"], str) or len(value["source_commit"]) != 40
                    or any(c not in "0123456789abcdef" for c in value["source_commit"])
                    or len(value["eligible_originals"]) != 9):
                raise ValueError
            from ..autonomous_policy_v1 import INTERPRET_SCHEMA, VERIFY_SCHEMA
            for row, candidate in zip(value["eligible_originals"], ORIGINAL_NINE_CANDIDATES):
                binding, identity, request = row["original_binding"], row["identity"], row["interpretation"]
                expected = {**candidate["identity"], "original_binding_sha256":candidate["original_binding_sha256"],
                    "claim_binding_sha256":candidate["binding_sha256"], "corpus_manifest_sha256":binding["corpus_manifest_sha256"]}
                if (canonical(identity) != canonical(expected) or binding["claim_id"] != candidate["claim_id"]
                        or binding["corpus_id"] != "synthetic-150"
                        or binding["original_binding_sha256"] != candidate["original_binding_sha256"]
                        or binding["original_binding_sha256"] != digest({k:v for k,v in binding.items() if k != "original_binding_sha256"})
                        or binding["claim_binding_sha256"] != candidate["binding_sha256"]
                        or type(request["request_bytes"]) is not int or not 0 < request["request_bytes"] <= 64000
                        or request["schema_sha256"] != digest(INTERPRET_SCHEMA)
                        or row["verification"]["schema_sha256"] != digest(VERIFY_SCHEMA)
                        or not WorkStore._autonomous_hash(request["request_sha256"])
                        or not WorkStore._autonomous_hash(request["context_sha256"])
                        or not WorkStore._autonomous_hash(row["semantic_context_sha256"])
                        or Decimal(request["maximum_cost_usd"]) != Decimal("1.25E-7") * request["request_bytes"] + Decimal("5E-7") * 3500):
                    raise ValueError
            if (value["current_budget_cas_ready"] is not True or not isinstance(value["prior_budget"],dict)
                    or digest(value["prior_budget"]) != value["prior_budget_sha256"]):
                raise ValueError
            WorkStore.validate_original_nine_budget_snapshot(value["prior_budget"])
        except (KeyError, TypeError, ValueError, AttributeError, InvalidOperation) as exc:
            raise WorkStoreError("exact-nine preflight identity or full budget snapshot is invalid") from exc

    @staticmethod
    def _original_nine_roster(usage):
        return [{"workflow_id":key, "workflow_sha256":work["record"]["workflow_sha256"],
            "calls":[{"stage":stage,"intent_sha256":call["intent"]["intent_sha256"],
                      "receipt_sha256":call["outcome"]["receipt_sha256"] if call["outcome"] else None}
                     for stage,call in sorted(work["calls"].items())],
            "terminal_sha256":work["terminal"]["terminal_sha256"] if work["terminal"] else None}
            for key,work in sorted(usage["workflows"].items())]

    @staticmethod
    def _original_nine_legacy_seal(db):
        queries = ["SELECT * FROM work_external_budget WHERE singleton=1",
                   "SELECT * FROM work_external_run_grant WHERE singleton=1",
                   "SELECT * FROM work_autonomous_policy WHERE singleton=1",
                   "SELECT * FROM work_autonomous_capacity_grant WHERE singleton=1",
                   "SELECT * FROM work_runs WHERE run_id IN (SELECT run_id FROM work_external_permits)",
                   "SELECT * FROM work_events WHERE run_id IN (SELECT run_id FROM work_external_permits) ORDER BY run_id,sequence"]
        # Query plans may traverse an unchanged table in a different order.
        # Bind every raw column/byte without binding that incidental traversal.
        return digest([sorted((dict(row) for row in db.execute(sql)),key=canonical) for sql in queries])

    def _original_nine_grant(self, db, base, policy, capacity):
        value = self._autonomous_decode(db.execute("SELECT * FROM work_original_nine_grant WHERE singleton=1").fetchone(), "grant_sha256")
        if value is None:
            return None
        try:
            self.validate_original_nine_preflight(value["preflight"])
            prior, command = value["prior_budget"], value["approval_command"]
            self._validate_grant_command(command["expected_budget_sha256"],command["actor"],command["reason"],command["idempotency_key"])
            self._validate_grant_command(command["acknowledged_preflight_sha256"],command["human_approval_reference"],command["reason"],command["idempotency_key"])
            option = command["monetary_option"]
            if (set(value) != {"contract","base_policy_sha256","autonomous_policy_sha256","old_capacity_grant_sha256",
                    "prior_budget","prior_budget_sha256","prior_workflows","prior_external_sha256","preflight","approval_command",
                    "effective_total_cost_limit_usd","max_new_workflow_reservations_usd","granted_at","grant_sha256"}
                    or value["contract"] != "casepath.original-nine-capacity-grant/1.0.0"
                    or base is None or policy is None or capacity is None
                    or value["base_policy_sha256"] != digest(base) or value["autonomous_policy_sha256"] != policy["policy_sha256"]
                    or value["old_capacity_grant_sha256"] != capacity["grant_sha256"]
                    or prior["autonomous_capacity_grant"] != capacity or prior["autonomous_policy"] != policy
                    or value["prior_budget_sha256"] != digest(prior) or prior != value["preflight"]["prior_budget"]
                    or command["expected_budget_sha256"] != digest(prior)
                    or command["acknowledged_preflight_sha256"] != value["preflight"]["preflight_sha256"]
                    or option not in {"existing_010","new_018_total_022"}
                    or value["effective_total_cost_limit_usd"] != ("0.10" if option == "existing_010" else "0.22")
                    or value["max_new_workflow_reservations_usd"] != "0.18"
                    or value["prior_external_sha256"] != self._original_nine_legacy_seal(db)
                    or any(prior[k] != v for k,v in {"max_provider_calls":18,"total_cost_limit_usd":"0.10","run_cost_limit_usd":"0.02",
                            "provider_calls_used":24,"effective_autonomous_max_provider_calls":24,
                            "autonomous_grant_workflows_used":3,"autonomous_grant_provider_calls_used":6,"in_flight":False}.items())
                    or "original_nine_grant" in prior or not self._autonomous_time(value["granted_at"])):
                raise ValueError
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise WorkStoreError("exact-nine grant does not preserve the original allowance") from exc
        return value

    def _original_nine_usage(self, db, grant, usage):
        works = usage["workflows"]
        added = {key:work for key,work in works.items() if "original_nine_grant_sha256" in work["record"]}
        old = {key:work for key,work in works.items() if key not in added}
        old_usage = {**usage,"workflows":old,"calls":[call for work in old.values() for call in work["calls"].values()]}
        if grant is None:
            if added:
                raise WorkStoreError("an exact-nine workflow has no immutable grant")
            return old_usage, added, Decimal(0), Decimal(0)
        expected = {r["identity"]["workflow_id"]:r["identity"] for r in grant["preflight"]["eligible_originals"]}
        try:
            if (self._original_nine_roster(old_usage) != grant["prior_workflows"]
                    or any(w["terminal"] is None for w in old.values())
                    or len(added) > 9 or sum(len(w["calls"]) for w in added.values()) > 18
                    or any(key not in expected or work["record"]["identity"] != expected[key]
                        or work["record"]["config"] != ORIGINAL_NINE_CONFIG
                        or work["record"]["original_nine_grant_sha256"] != grant["grant_sha256"]
                        or "capacity_grant_sha256" in work["record"] for key,work in added.items())):
                raise ValueError
            own = [c for work in added.values() for c in work["calls"].values()]
            rows = {r["identity"]["workflow_id"]:r for r in grant["preflight"]["eligible_originals"]}
            if any(call["intent"]["schema_sha256"] != rows[key]["interpretation" if stage == "interpret" else "verification"]["schema_sha256"]
                   for key,work in added.items() for stage,call in work["calls"].items()):
                raise ValueError
            if any(call["intent"].get("source_commit") != grant["preflight"]["source_commit"]
                   for work in added.values() for call in work["calls"].values()):
                raise ValueError
            actual = sum((c["cost"] for c in own if c["cost"] is not None),Decimal(0))
            reserved = sum((c["reserved"] for c in own if c["cost"] is None),Decimal(0))
            for work in added.values():
                if work["terminal"] is None:
                    committed = sum((c["cost"] if c["cost"] is not None else c["reserved"] for c in work["calls"].values()),Decimal(0))
                    reserved += max(Decimal(0),Decimal("0.02") - committed)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise WorkStoreError("exact-nine epoch differs from its immutable original roster") from exc
        return old_usage, added, actual, reserved

    def apply_original_nine_grant(self, *, preflight, expected_budget_sha256, actor, reason, idempotency_key,
                                 human_approval_reference, monetary_option, acknowledged_preflight_sha256):
        """Operator-only application; this method never sends or starts work.

        Caller authentication belongs to the explicitly invoked remote-primary
        operator transport. Strings/hashes are audit identities, never proof of
        direct human approval. There is deliberately no API/startup caller.
        """
        self.validate_original_nine_preflight(preflight)
        self._validate_grant_command(expected_budget_sha256,actor,reason,idempotency_key)
        self._validate_grant_command(acknowledged_preflight_sha256,human_approval_reference,reason,idempotency_key)
        if (expected_budget_sha256 != preflight["prior_budget_sha256"]
                or acknowledged_preflight_sha256 != preflight["preflight_sha256"]
                or monetary_option not in {"existing_010","new_018_total_022"}):
            raise ConflictError("the exact-nine approval differs from the supplied preflight")
        command = {"expected_budget_sha256":expected_budget_sha256,"actor":actor,"reason":reason,
            "idempotency_key":idempotency_key,"human_approval_reference":human_approval_reference,
            "monetary_option":monetary_option,"acknowledged_preflight_sha256":acknowledged_preflight_sha256}
        with self.transaction() as db:
            budget = self._external_budget(db)
            if budget is None or budget.get("autonomous_capacity_grant") is None:
                raise WorkStoreError("the exhausted original and three-workflow policies are required")
            prior = budget.get("original_nine_grant")
            if prior:
                if prior["approval_command"] != command or prior["preflight"] != preflight:
                    raise ConflictError("the immutable exact-nine grant already binds a different approval")
                return prior
            if digest(budget) != expected_budget_sha256:
                raise ConflictError("the exact current budget snapshot changed before operator application")
            usage = self._autonomous_usage(db,budget["autonomous_policy"])
            if (budget["in_flight"] or any(w["terminal"] is None for w in usage["workflows"].values())
                    or budget["provider_calls_used"] != 24 or budget["effective_autonomous_max_provider_calls"] != 24
                    or budget["autonomous_grant_workflows_used"] != 3 or budget["autonomous_grant_provider_calls_used"] != 6):
                raise ConflictError("the old 24-call allowance must be exhausted and every workflow settled")
            if any(cid in {w["record"]["identity"]["claim_id"] for w in usage["workflows"].values()}
                   for cid in (c["claim_id"] for c in ORIGINAL_NINE_CANDIDATES)):
                raise ConflictError("an eligible original already consumed a historical workflow")
            if budget["reason"] == "provider_cost_bound_exceeded":
                raise ConflictError("a provider overrun cannot receive a new grant")
            approvals = [budget.get("run_grant"),budget.get("autonomous_policy"),budget.get("autonomous_capacity_grant")]
            if any(value and value.get("idempotency_key") == idempotency_key for value in approvals):
                raise ConflictError("this approval command identity already belongs to an old epoch")
            total = "0.10" if monetary_option == "existing_010" else "0.22"
            if (self._money(budget["actual_cost_usd"]) + self._money(budget["reserved_cost_usd"]) +
                    (Decimal("0.02") if monetary_option == "existing_010" else Decimal("0.18")) > Decimal(total)):
                raise ConflictError("the proposed workflow reservations exceed the chosen aggregate ceiling")
            return self._autonomous_insert(db,"work_original_nine_grant",{"singleton":1},{
                "contract":"casepath.original-nine-capacity-grant/1.0.0","base_policy_sha256":budget["base_policy_sha256"],
                "autonomous_policy_sha256":budget["autonomous_policy"]["policy_sha256"],
                "old_capacity_grant_sha256":budget["autonomous_capacity_grant"]["grant_sha256"],
                "prior_budget":budget,"prior_budget_sha256":expected_budget_sha256,
                "prior_workflows":self._original_nine_roster(usage),"prior_external_sha256":self._original_nine_legacy_seal(db),
                "preflight":preflight,"approval_command":command,
                "effective_total_cost_limit_usd":total,"max_new_workflow_reservations_usd":"0.18","granted_at":utcnow()},"grant_sha256")

    def bind_original_nine_identity(self, identity, source_context):
        """Bind the existing controller identity to current canonical originals."""
        with self.connect() as db:
            db.execute("BEGIN")
            budget = self._external_budget(db)
            grant = (budget or {}).get("original_nine_grant")
            if grant is None:
                return identity
            usage = self._autonomous_usage(db,budget["autonomous_policy"])
            work = usage["workflows"].get(identity["workflow_id"])
            if work and "original_nine_grant_sha256" not in work["record"]:
                return identity
        from ..autonomous_corpus_v1 import CanonicalCorpus
        from ..workspace_corpus import PublicCorpus, default_workspace_corpus_root
        from ..autonomous_policy_v1 import INTERPRET_INSTRUCTIONS, VERIFY_INSTRUCTIONS
        corpus = CanonicalCorpus()
        public = PublicCorpus(default_workspace_corpus_root())
        if public.manifest_file_sha256 != ORIGINAL_NINE_CORPUS_SHA256:
            raise ConflictError("the canonical corpus changed after approval")
        cid = identity["claim_id"]
        row = next((r for r in grant["preflight"]["eligible_originals"] if r["identity"]["claim_id"] == cid),None)
        if row is None or identity != {k:v for k,v in row["identity"].items() if k not in {"original_binding_sha256","claim_binding_sha256","corpus_manifest_sha256"}}:
            raise ConflictError("the workflow is outside the exact-nine original identity allowlist")
        state = corpus.preview_state(cid)
        sources = [corpus.source_preview(cid,d["artifact_id"]) for d in state["source_descriptors"]]
        expected_sources = [{k:s[k] for k in ("artifact_id","file_name","media_type","role","sha256","text","complete","coverage")} for s in sources]
        if (state["original_binding"] != row["original_binding"] or digest(public.static_policy()) != identity["rule_set_sha256"]
                or source_context.get("sources") != expected_sources or source_context.get("claim_id") != cid
                or source_context.get("instructions") != {"interpret":INTERPRET_INSTRUCTIONS,"verify":VERIFY_INSTRUCTIONS}
                or digest({k:v for k,v in source_context.items() if k != "compatible_knowledge"}) != row["semantic_context_sha256"]):
            raise ConflictError("the original binding, source extraction or instructions changed after approval")
        return row["identity"]

    def _autonomous_usage(self, db, policy):
        workflows, calls, pending, unused = {}, [], False, Decimal(0)
        if policy is None:
            return {"workflows": workflows, "calls": calls, "pending": pending, "unspent_reserved": unused}
        try:
            for row in db.execute("SELECT * FROM work_autonomous_workflows ORDER BY workflow_id"):
                work = self._autonomous_decode(row, "workflow_sha256")
                self._autonomous_inputs(work["identity"], work["config"])
                if (work["workflow_id"] != row["workflow_id"] or work["identity"]["workflow_id"] != row["workflow_id"]
                        or work["identity_sha256"] != digest(work["identity"]) or work["config_sha256"] != digest(work["config"])
                        or work["policy_sha256"] != policy["policy_sha256"] or work["contract"] != "casepath.autonomous-workflow/1.0.0"
                        or not self._autonomous_time(work["created_at"])):
                    raise ValueError
                workflows[row["workflow_id"]] = {"record": work, "calls": {}, "terminal": None}
            for row in db.execute("SELECT * FROM work_autonomous_calls ORDER BY workflow_id,stage"):
                intent = self._autonomous_decode(row, "intent_sha256")
                work = workflows[row["workflow_id"]]
                cfg = work["record"]["config"]
                maximum = self._money(cfg["prompt_price"]) * intent["request_bytes"] + self._money(cfg["completion_price"]) * cfg["max_output_tokens"] + self._money(cfg["request_price"])
                if (row["stage"] not in {"interpret", "verify"} or intent["stage"] != row["stage"]
                        or intent["workflow_id"] != row["workflow_id"] or intent["workflow_sha256"] != work["record"]["workflow_sha256"]
                        or intent["maximum_cost_usd"] != str(maximum) or type(intent["request_bytes"]) is not int
                        or not 0 < intent["request_bytes"] <= cfg["max_request_bytes"]
                        or intent["request_bytes"] + cfg["max_output_tokens"] > cfg["context_length"]
                        or any(not self._autonomous_hash(intent[k]) for k in ("request_sha256", "context_sha256", "schema_sha256"))
                        or (intent["proposal_sha256"] is not None if row["stage"] == "interpret" else not self._autonomous_hash(intent["proposal_sha256"]))
                        or not self._autonomous_time(intent["started_at"])
                        or intent["contract"] != "casepath.autonomous-provider-intent/1.0.0"):
                    raise ValueError
                work["calls"][row["stage"]] = {"intent": intent, "outcome": None, "cost": None, "reserved": maximum}
            for row in db.execute("SELECT * FROM work_autonomous_outcomes ORDER BY workflow_id,stage"):
                outcome = self._autonomous_decode(row, "receipt_sha256")
                call = workflows[row["workflow_id"]]["calls"][row["stage"]]
                intent = call["intent"]
                if (outcome["workflow_id"] != row["workflow_id"] or outcome["stage"] != row["stage"]
                        or outcome["intent_sha256"] != intent["intent_sha256"]
                        or outcome["policy_sha256"] != policy["policy_sha256"]
                        or outcome["model"] != workflows[row["workflow_id"]]["record"]["config"]["model"]
                        or outcome["maximum_cost_usd"] != intent["maximum_cost_usd"]
                        or any(outcome[k] != intent[k] for k in ("request_sha256", "context_sha256", "schema_sha256"))
                        or outcome["result_sha256"] != (digest(outcome["result"]) if outcome["result"] is not None else None)
                        or outcome["status"] not in {"completed", "rejected", "unknown"}
                        or (outcome["status"] == "completed") != isinstance(outcome["result"], dict)
                        or (outcome["status"] != "completed" and outcome["result"] is not None)
                        or not isinstance(outcome["metadata"], dict) or not self._autonomous_time(outcome["recorded_at"])
                        or outcome["contract"] != "casepath.autonomous-provider-result/1.0.0"):
                    raise ValueError
                call["outcome"] = outcome
                call["cost"] = self._money(outcome["cost_usd"]) if outcome["cost_usd"] is not None else None
            for row in db.execute("SELECT * FROM work_autonomous_terminals ORDER BY workflow_id"):
                terminal = self._autonomous_decode(row, "terminal_sha256")
                work = workflows[row["workflow_id"]]
                last = work["calls"].get("verify", work["calls"].get("interpret", {})).get("outcome")
                abandoned = terminal["status"] == "abandoned"
                if (terminal["workflow_id"] != row["workflow_id"] or terminal["workflow_sha256"] != work["record"]["workflow_sha256"]
                        or terminal["contract"] != "casepath.autonomous-workflow-terminal/1.0.0" or not last
                        or terminal["receipt_sha256"] != last["receipt_sha256"]
                        or (not abandoned and (terminal["status"] != last["status"] or last["stage"] == "interpret" and last["status"] == "completed"))
                        or (abandoned and (last["stage"] != "interpret" or last["status"] != "completed"
                                           or terminal["reason"] not in {"superseded_or_paused", "execution_deferred"}))
                        or not self._autonomous_time(terminal["recorded_at"])):
                    raise ValueError
                work["terminal"] = terminal
            for work in workflows.values():
                own = list(work["calls"].values())
                if not own or len(own) > policy["max_calls_per_workflow"]:
                    raise ValueError
                if "verify" in work["calls"]:
                    prior = work["calls"].get("interpret", {}).get("outcome")
                    verify = work["calls"]["verify"]["intent"]
                    if not prior or prior["status"] != "completed" or verify["proposal_sha256"] != prior["result_sha256"] or verify["context_sha256"] != prior["context_sha256"]:
                        raise ValueError
                last = work["calls"].get("verify", work["calls"].get("interpret", {})).get("outcome")
                terminal_expected = last is not None and (last["stage"] == "verify" or last["status"] != "completed"
                                                          or (work["terminal"] or {}).get("status") == "abandoned")
                if terminal_expected != (work["terminal"] is not None):
                    raise ValueError
                committed = sum((c["cost"] if c["cost"] is not None else c["reserved"] for c in own), Decimal(0))
                if work["terminal"] is None:
                    unused += max(Decimal(0), self._money(policy["workflow_cost_limit_usd"]) - committed)
                pending = pending or any(c["outcome"] is None or c["outcome"]["status"] == "unknown" for c in own)
                calls.extend(own)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise WorkStoreError("autonomous provider ledger is invalid") from exc
        return {"workflows": workflows, "calls": calls, "pending": pending, "unspent_reserved": unused}

    def begin_autonomous_call(self, stage, identity, config, *, request_sha256, request_bytes, context_sha256, schema_sha256, proposal_sha256=None, allow_send=True):
        """Reserve before send, or return the exact persisted outcome without send."""
        self._autonomous_inputs(identity, config)
        if stage not in {"interpret", "verify"} or type(allow_send) is not bool:
            raise WorkStoreError("invalid autonomous call identity")
        for value in (request_sha256, context_sha256, schema_sha256, *([proposal_sha256] if stage == "verify" else [])):
            if not self._autonomous_hash(value):
                raise WorkStoreError("invalid autonomous input hash")
        if (type(request_bytes) is not int or not 0 < request_bytes <= config["max_request_bytes"]
                or request_bytes + config["max_output_tokens"] > config["context_length"]
                or (stage == "interpret" and proposal_sha256 is not None)):
            raise WorkStoreError("autonomous provider bounds are invalid")
        maximum = self._money(config["prompt_price"]) * request_bytes + self._money(config["completion_price"]) * config["max_output_tokens"] + self._money(config["request_price"])
        workflow_id = identity["workflow_id"]
        command = {"stage": stage, "workflow_id": workflow_id, "request_sha256": request_sha256, "request_bytes": request_bytes,
                   "context_sha256": context_sha256, "schema_sha256": schema_sha256, "proposal_sha256": proposal_sha256}
        with self.transaction() as db:
            budget = self._external_budget(db)
            policy = (budget or {}).get("autonomous_policy")
            if policy is None:
                raise WorkStoreError("an explicitly activated autonomous budget policy is required")
            usage = self._autonomous_usage(db, policy)
            work = usage["workflows"].get(workflow_id)
            if work:
                if work["record"]["identity"] != identity or work["record"]["config"] != config:
                    raise ConflictError("workflow identity or frozen model configuration changed")
                prior = work["calls"].get(stage)
                if prior:
                    if any(prior["intent"][k] != v for k, v in command.items()):
                        raise ConflictError("this autonomous stage already binds different input")
                    if prior["outcome"] is None:
                        raise ReconciliationRequired("the provider intent has no confirmed outcome; it cannot be resent")
                    return {"result": prior["outcome"]["result"], "receipt": prior["outcome"]}
                if work["terminal"]:
                    raise ConflictError("the autonomous workflow already ended")
            elif stage != "interpret":
                raise ConflictError("verification requires a persisted interpretation")
            nine = budget.get("original_nine_grant")
            if nine and (work is None or "original_nine_grant_sha256" in work["record"]):
                row = next((row for row in nine["preflight"]["eligible_originals"] if row["identity"] == identity),None)
                if (row is None or canonical(config) != canonical(nine["preflight"]["frozen_model_config"])
                        or schema_sha256 != row["interpretation" if stage == "interpret" else "verification"]["schema_sha256"]):
                    raise ConflictError("the original identity, frozen config or stage schema is outside the exact-nine allowlist")
                # Exact recorded outcomes returned above remain readable across
                # deployment changes. Every new physical intent must belong to
                # the approved server-owned deployed source, including verify.
                if self._validated_source_commit != nine["preflight"]["source_commit"]:
                    raise ConflictError("the validated runtime source commit differs from the exact-nine preflight")
            if not allow_send:
                raise ConflictError("the autonomous provider profile is not explicitly enabled; no request was reserved")
            if budget["in_flight"]:
                raise ConflictError("another provider outcome is pending; no concurrent inference")
            if budget["reason"] == "provider_cost_bound_exceeded" or budget["provider_calls_used"] >= budget["effective_autonomous_max_provider_calls"]:
                raise ConflictError("the shared provider budget is exhausted")
            if work is None:
                if not budget["autonomous_can_start"]:
                    raise ConflictError("autonomous budget unavailable: " + budget["autonomous_reason"])
                capacity = budget["autonomous_capacity_grant"]
                if nine:
                    candidate = next((row for row in nine["preflight"]["eligible_originals"] if row["identity"] == identity),None)
                    if candidate is None or canonical(config) != canonical(nine["preflight"]["frozen_model_config"]):
                        raise ConflictError("the original identity or provider configuration is outside the exact-nine allowlist")
                record = self._autonomous_insert(db, "work_autonomous_workflows", {"workflow_id": workflow_id}, {
                    "contract": "casepath.autonomous-workflow/1.0.0", "workflow_id": workflow_id, "identity": identity,
                    "identity_sha256": digest(identity), "config": config, "config_sha256": digest(config),
                    **({"original_nine_grant_sha256":nine["grant_sha256"]} if nine else
                       {"capacity_grant_sha256": capacity["grant_sha256"]} if capacity else {}),
                    "policy_sha256": policy["policy_sha256"], "created_at": utcnow()}, "workflow_sha256")
                work = {"record": record, "calls": {}}
            if stage == "verify":
                prior = work["calls"].get("interpret", {}).get("outcome")
                if not prior or prior["status"] != "completed" or prior["result_sha256"] != proposal_sha256 or prior["context_sha256"] != context_sha256:
                    raise ConflictError("verification must bind the exact saved interpretation and original context")
            committed = sum((c["cost"] if c["cost"] is not None else c["reserved"] for c in work["calls"].values()), Decimal(0))
            if committed + maximum > self._money(policy["workflow_cost_limit_usd"]):
                raise ConflictError("the autonomous workflow cost ceiling is exhausted")
            intent = self._autonomous_insert(db, "work_autonomous_calls", {"workflow_id": workflow_id, "stage": stage}, {
                "contract": "casepath.autonomous-provider-intent/1.0.0", **command,
                **({"source_commit":self._validated_source_commit} if nine else {}),
                "workflow_sha256": work["record"]["workflow_sha256"], "maximum_cost_usd": str(maximum), "started_at": utcnow()}, "intent_sha256")
            return {"intent": intent, "policy_sha256": policy["policy_sha256"]}

    def complete_autonomous_call(self, workflow_id, stage, *, intent_sha256, status, result, cost_usd, metadata):
        """Persist the typed outcome before any controller can apply it."""
        if (status not in {"completed", "rejected", "unknown"} or (status == "completed") != isinstance(result, dict)
                or (status != "completed" and result is not None) or not isinstance(metadata, dict)):
            raise WorkStoreError("invalid autonomous provider outcome")
        if len(canonical({"result": result, "metadata": metadata})) > 128000:
            raise WorkStoreError("autonomous result exceeds its persistence bound")
        cost = str(self._money(cost_usd)) if cost_usd is not None else None
        with self.transaction() as db:
            budget = self._external_budget(db)
            policy = (budget or {}).get("autonomous_policy")
            if policy is None:
                raise WorkStoreError("autonomous policy is unavailable")
            usage = self._autonomous_usage(db, policy)
            try:
                work = usage["workflows"][workflow_id]
                call = work["calls"][stage]
            except KeyError as exc:
                raise WorkStoreError("autonomous provider intent is absent") from exc
            intent = call["intent"]
            if intent["intent_sha256"] != intent_sha256:
                raise ConflictError("autonomous outcome binds a different intent")
            material = {"contract": "casepath.autonomous-provider-result/1.0.0", "workflow_id": workflow_id, "stage": stage,
                "intent_sha256": intent_sha256, "policy_sha256": policy["policy_sha256"], "model": work["record"]["config"]["model"],
                **{k: intent[k] for k in ("request_sha256", "context_sha256", "schema_sha256")},
                "status": status, "result": result, "result_sha256": digest(result) if result is not None else None,
                "cost_usd": cost, "maximum_cost_usd": intent["maximum_cost_usd"], "metadata": metadata}
            if call["outcome"]:
                if any(call["outcome"][k] != v for k, v in material.items()):
                    raise ConflictError("autonomous provider outcome cannot be replaced")
                return {"result": call["outcome"]["result"], "receipt": call["outcome"]}
            receipt = self._autonomous_insert(db, "work_autonomous_outcomes", {"workflow_id": workflow_id, "stage": stage},
                {**material, "recorded_at": utcnow()}, "receipt_sha256")
            if stage == "verify" or status != "completed":
                self._autonomous_insert(db, "work_autonomous_terminals", {"workflow_id": workflow_id}, {
                    "contract": "casepath.autonomous-workflow-terminal/1.0.0", "workflow_id": workflow_id,
                    "workflow_sha256": work["record"]["workflow_sha256"], "receipt_sha256": receipt["receipt_sha256"],
                    "status": status, "recorded_at": utcnow()}, "terminal_sha256")
            return {"result": result, "receipt": receipt}

    def close_autonomous_workflow(self, workflow_id, reason):
        """Release only unsent work; retain every physical call and its cost."""
        if reason not in {"superseded_or_paused", "execution_deferred"}:
            raise WorkStoreError("invalid autonomous close reason")
        with self.transaction() as db:
            budget = self._external_budget(db)
            policy = (budget or {}).get("autonomous_policy")
            if policy is None:
                return None
            work = self._autonomous_usage(db, policy)["workflows"].get(workflow_id)
            if work is None:
                return None
            if work["terminal"]:
                return work["terminal"]
            # An uncertain physical attempt is never treated as unused work.
            # Its original reservation and no-resend requirement remain intact.
            if "verify" in work["calls"]:
                return None
            prior = work["calls"].get("interpret", {}).get("outcome")
            if not prior or prior["status"] != "completed":
                return None
            return self._autonomous_insert(db, "work_autonomous_terminals", {"workflow_id": workflow_id}, {
                "contract": "casepath.autonomous-workflow-terminal/1.0.0", "workflow_id": workflow_id,
                "workflow_sha256": work["record"]["workflow_sha256"], "receipt_sha256": prior["receipt_sha256"],
                "status": "abandoned", "reason": reason, "recorded_at": utcnow()}, "terminal_sha256")

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
            if budget and (budget["provider_calls_used"] >= budget["max_provider_calls"] or budget["in_flight"] or
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
                run_grant_sha256 = None
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
                        external_limit = min(external_limit, budget["max_runs"]) + (1 if budget["run_grant"] else 0)
                        if budget["runs_used"] >= budget["max_runs"] and budget["run_grant"]:
                            run_grant_sha256 = budget["run_grant"]["grant_sha256"]
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
                             after={"roles": [r.value for r in ROLE_ORDER], "facts_worker": request.get("facts_worker", "reference"),
                                    **({"external_run_grant_sha256": run_grant_sha256} if run_grant_sha256 else {})})
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
