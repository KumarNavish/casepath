"""Durable, fenced ownership for one hosted workflow through knowledge publication."""

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4
from threading import Lock, Timer
from time import monotonic

from .workspace_corpus import digest_value

from .autonomous_controller_v1 import AutonomousController


LEASE_SECONDS = 180
RECOVERY_RETRY_SECONDS = 5.0
RECOVERY_STALLED_SECONDS = LEASE_SECONDS + 2 * RECOVERY_RETRY_SECONDS
_DB_NOW = "CAST(strftime('%s','now') AS INTEGER)"
_CURRENT_OWNER = ContextVar("casepath_hosted_workflow_owner", default=None)


class HostedOwnershipLost(BaseException):
    """Must bypass AutonomousController.run's except Exception/abandon path."""


@dataclass(frozen=True)
class _Owner:
    lease: object
    owner: str
    generation: int


class HostedWorkflowLease:
    """One global owner, a DB clock, and a monotonic fencing generation."""

    def __init__(self, raw_connection_factory):
        self._raw_connect = raw_connection_factory

    def initialize(self):
        # The table is intentionally mutable; it is coordination, not evidence.
        with self._raw_connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS hosted_workflow_lease (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    owner TEXT,
                    generation INTEGER NOT NULL CHECK (generation >= 0),
                    expires_at INTEGER NOT NULL CHECK (expires_at >= 0)
                );
                INSERT OR IGNORE INTO hosted_workflow_lease
                    (singleton, owner, generation, expires_at)
                    VALUES (1, NULL, 0, 0);
            """)

    def acquire(self):
        """Return a committed owner token, or None. Never wait/retry in a loop."""
        owner = uuid4().hex
        try:
            with self._raw_connect() as db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "UPDATE hosted_workflow_lease "
                    f"SET owner=?, generation=generation+1, expires_at={_DB_NOW}+? "
                    f"WHERE singleton=1 AND (owner IS NULL OR expires_at<={_DB_NOW}) "
                    "AND generation<9223372036854775807 RETURNING generation",
                    (owner, LEASE_SECONDS),
                ).fetchone()
                # __exit__ must acknowledge COMMIT before the token escapes.
            return None if row is None else _Owner(self, owner, row["generation"])
        except Exception:
            # An ambiguous acquisition may have left a lease, but grants no
            # local authority. Subsequent polls wait for its natural expiry.
            raise HostedOwnershipLost("Workflow ownership was not confirmed.") from None

    def fence_and_renew(self, db, token):
        """Called after BEGIN IMMEDIATE on that exact store connection."""
        if token.lease is not self:
            raise HostedOwnershipLost("The workflow belongs to another lease boundary.")
        row = db.execute(
            f"UPDATE hosted_workflow_lease SET expires_at={_DB_NOW}+? "
            "WHERE singleton=1 AND owner=? AND generation=? "
            f"AND expires_at>{_DB_NOW} RETURNING generation",
            (LEASE_SECONDS, token.owner, token.generation),
        ).fetchone()
        if row is None or row["generation"] != token.generation:
            raise HostedOwnershipLost("Workflow ownership expired or changed.")

    def release(self, token):
        """Never clear another generation. Failure leaves an expiring lease."""
        try:
            with self._raw_connect() as db:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "UPDATE hosted_workflow_lease SET owner=NULL, expires_at=0 "
                    "WHERE singleton=1 AND owner=? AND generation=?",
                    (token.owner, token.generation),
                )
        except Exception:
            # No retry and no claim mutation. The DB expiry remains the recovery
            # boundary, even when release COMMIT's response was ambiguous.
            pass

    def connect(self):
        try:
            return _FencedConnection(self._raw_connect(), self)
        except Exception:
            if _CURRENT_OWNER.get() is not None:
                raise HostedOwnershipLost("The workflow database is unavailable.") from None
            raise


class _FencedConnection:
    """DB-API wrapper. Only owned workflow transactions gain extra behavior."""

    def __init__(self, connection, lease):
        self._connection = connection
        self._lease = lease
        self._write_owner = None
        self._closed = False

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def _convert_error(self):
        if _CURRENT_OWNER.get() is not None or self._write_owner is not None:
            raise HostedOwnershipLost("Owned workflow storage was not confirmed.") from None

    def execute(self, sql, parameters=()):
        normalized = " ".join(sql.strip().rstrip(";").upper().split())
        first = normalized.split(" ", 1)[0]
        token = _CURRENT_OWNER.get()
        if self._write_owner is not None and token != self._write_owner:
            raise HostedOwnershipLost("Workflow ownership context changed during a transaction.")
        try:
            if first == "BEGIN":
                cursor = self._connection.execute(sql, parameters)
                if token is not None and normalized in {
                    "BEGIN IMMEDIATE", "BEGIN IMMEDIATE TRANSACTION",
                    "BEGIN EXCLUSIVE", "BEGIN EXCLUSIVE TRANSACTION",
                }:
                    try:
                        self._lease.fence_and_renew(self._connection, token)
                    except BaseException:
                        try:
                            self._connection.rollback()
                        except Exception:
                            pass
                        raise
                    self._write_owner = token
                return cursor
            # The current stores explicitly BEGIN IMMEDIATE before mutable
            # journal/budget work. Reject new implicit/autocommit write paths
            # inside owned work instead of silently leaving them unfenced.
            if token is not None and self._write_owner is None and first not in {
                "SELECT", "EXPLAIN", "COMMIT", "END", "ROLLBACK",
            }:
                raise HostedOwnershipLost("Owned writes require a fenced write transaction.")
            cursor = self._connection.execute(sql, parameters)
            if first in {"COMMIT", "END", "ROLLBACK"}:
                self._write_owner = None
            return cursor
        except Exception:
            self._convert_error()
            raise

    def executescript(self, sql):
        if _CURRENT_OWNER.get() is not None:
            raise HostedOwnershipLost("Schema changes cannot run inside a workflow.")
        return self._connection.executescript(sql)

    def prefetch(self, queries):
        try:
            method = getattr(self._connection, 'prefetch', None)
            if method is not None:
                method(queries)
        except Exception:
            self._convert_error()
            raise

    def commit(self):
        if self._write_owner is not None and _CURRENT_OWNER.get() != self._write_owner:
            raise HostedOwnershipLost("Workflow ownership context changed before commit.")
        try:
            self._connection.commit()
            self._write_owner = None
        except Exception:
            self._convert_error()
            raise

    def rollback(self):
        try:
            self._connection.rollback()
            self._write_owner = None
        except Exception:
            self._convert_error()
            raise

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._connection.close()
        except Exception:
            self._convert_error()
            raise

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        try:
            if kind is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()


class HostedAutonomousController(AutonomousController):
    """One leased workflow, with bounded recovery of accepted pending work."""

    def __init__(self, store, policy, model=None, *, lease):
        super().__init__(store, policy, model)
        self._hosted_lease = lease
        self._waiting = {}  # claim_id -> ("run", None) or ("learn", workflow)
        self._learned = set()
        self._discovery_lock = Lock()
        self._next_discovery = 0.0
        self._recovery_timer = None
        self._retry_until = {}

    def _remember(self, claim_id, job):
        with self._lock:
            # New intake/evidence work must not be replaced by an older request
            # to finish deterministic learning only.
            prior = self._waiting.get(claim_id)
            if prior is None or job[0] == "run":
                self._waiting[claim_id] = job
            self._retry_until.setdefault(claim_id, monotonic() + RECOVERY_STALLED_SECONDS)
            self._arm_recovery()

    def _arm_recovery(self):
        # Caller holds _lock. Active executor completion will arm the timer;
        # never poll alongside local work or recursively submit from completion.
        eligible = any(monotonic() < self._retry_until[claim] for claim in self._waiting)
        if self._closed or not eligible:
            if self._recovery_timer is not None:
                self._recovery_timer.cancel()
                self._recovery_timer = None
            return
        if self._recovery_timer is not None or self._jobs:
            return
        timer = Timer(RECOVERY_RETRY_SECONDS, lambda: self._recover_pending(timer))
        timer.daemon = True
        self._recovery_timer = timer
        timer.start()

    def _recover_pending(self, timer):
        with self._lock:
            # Cancellation may race with a callback already entering this lock.
            if self._closed or self._recovery_timer is not timer:
                return
            self._recovery_timer = None
            if not self._jobs:
                for claim in tuple(self._waiting):
                    if monotonic() > self._retry_until[claim]:
                        continue  # Park until an authorized wake or restart.
                    try:
                        job = self._recovery_job(self.store.get(claim))
                    except Exception:
                        continue  # Unconfirmed reads grant no new authority.
                    if job is None:
                        self._waiting.pop(claim, None)
                        self._retry_until.pop(claim, None)
                    else:
                        self._waiting[claim] = job
                        self._start(claim)
            self._arm_recovery()

    def _owned(self, claim_id, job, callback):
        nested = _CURRENT_OWNER.get()
        if nested is not None:
            if nested.lease is not self._hosted_lease:
                raise HostedOwnershipLost("Nested workflow uses a different lease.")
            return callback()
        if self._closed:
            return None
        token = None
        reset = None
        try:
            token = self._hosted_lease.acquire()
            if token is None:
                self._remember(claim_id, job)
                return None  # No journal event, failure, or abandon operation.
            if self._closed:
                return None
            reset = _CURRENT_OWNER.set(token)
            result = callback()
            with self._lock:
                # A long local workflow must not consume the retry window for
                # another accepted job or new evidence waiting behind it.
                for claim in self._waiting:
                    self._retry_until[claim] = monotonic() + RECOVERY_STALLED_SECONDS
            return result
        except HostedOwnershipLost:
            if reset is not None:
                # Owned execution can outlast its original retry window. Start
                # the bounded wait when it loses ownership, including accepted
                # jobs queued behind it. Failed acquisition has no owner context
                # and must keep its existing deadline instead of extending it.
                with self._lock:
                    deadline = monotonic() + RECOVERY_STALLED_SECONDS
                    for claim in self._waiting.keys() | self._jobs.keys() | {claim_id}:
                        self._retry_until[claim] = deadline
            self._remember(claim_id, job)
            return None
        finally:
            if reset is not None:
                _CURRENT_OWNER.reset(reset)
            if token is not None:
                self._hosted_lease.release(token)

    def _recovery_job(self, state):
        code = (state.get('deferral') or {}).get('code')
        if code:
            # Failed/uncertain physical attempts are never automatically retried.
            # The existing model-unavailable exception only enables an unsent job.
            if code == 'model_unavailable' and self.model is not None:
                return ('run', None)
            return None
        workflow = state.get('run_id')
        if state.get('outcome') and workflow:
            with self._lock:
                return None if workflow in self._learned else ('learn', workflow)
        if state['status'] in {'received', 'running'}:
            return ('run', None)
        return None


    def run(self, claim_id):
        def current():
            # Discovery may race with pause, source arrival, another process's
            # outcome or a durable provider deferral. Recheck under ownership.
            state = self.store.get(claim_id)
            job = self._recovery_job(state)
            if job is None:
                return state
            if job[0] == 'learn':
                self._learn(claim_id, job[1])
                return self.store.get(claim_id)
            return AutonomousController.run(self, claim_id)
        return self._owned(claim_id, ('run', None), current)


    def _learn(self, claim_id, workflow):
        def current():
            state = self.store.get(claim_id)
            if self._recovery_job(state) != ('learn', workflow):
                return None
            self._contexts[workflow] = digest_value(state['source_descriptors'])
            result = AutonomousController._learn(self, claim_id, workflow)
            # Only successful return marks completion. Busy ownership, exceptions
            # and ambiguous persistence leave this workflow eligible for recovery.
            with self._lock:
                self._learned.add(workflow)
            return result
        return self._owned(claim_id, ('learn', workflow), current)


    def _start(self, claim_id):
        # Caller holds _lock. Completion never recursively calls submit.
        if self._closed or claim_id not in self._waiting:
            return
        prior = self._jobs.get(claim_id)
        if prior is not None and not prior.done():
            return
        kind, workflow = self._waiting.pop(claim_id)
        if kind == "run":
            future = self._executor.submit(self.run, claim_id)
        else:
            future = self._executor.submit(self._learn, claim_id, workflow)
        self._jobs[claim_id] = future

        def finished(completed):
            with self._lock:
                if self._jobs.get(claim_id) is completed:
                    self._jobs.pop(claim_id, None)
                    if claim_id not in self._waiting:
                        self._retry_until.pop(claim_id, None)
                self._arm_recovery()

        future.add_done_callback(finished)

    def submit(self, claim_id):
        with self._lock:
            if self._closed:
                return
            self._retry_until[claim_id] = monotonic() + RECOVERY_STALLED_SECONDS
            self._remember(claim_id, ("run", None))
            self._start(claim_id)
            self._arm_recovery()

    def wake_pending(self, *, force_discovery=False):
        """Explicitly discover saved work; recovery timers never scan the store."""
        if self._closed or not self._discovery_lock.acquire(blocking=False):
            return
        try:
            states = []
            if force_discovery or monotonic() >= self._next_discovery:
                states = self.store.list()
                self._next_discovery = monotonic() + 10.0
            with self._lock:
                if self._closed:
                    return
                for state in states:
                    claim = state['claim_id']
                    active = self._jobs.get(claim)
                    if active is not None and not active.done():
                        continue
                    job = self._recovery_job(state)
                    if job is None:
                        self._waiting.pop(claim, None)
                        self._retry_until.pop(claim, None)
                    else:
                        self._remember(claim, job)
                for claim in tuple(self._waiting):
                    self._retry_until[claim] = monotonic() + RECOVERY_STALLED_SECONDS
                    self._start(claim)
                self._arm_recovery()
        finally:
            self._discovery_lock.release()


    def resume(self):
        self.wake_pending(force_discovery=True)


    def shutdown(self):
        # The base method closes admission, waits for the active executor job,
        # and cancels jobs not yet started. _owned releases only after its work
        # exits; never release the active lease early while HTTP may settle.
        with self._lock:
            self._closed = True
            if self._recovery_timer is not None:
                self._recovery_timer.cancel()
                self._recovery_timer = None
        super().shutdown()
