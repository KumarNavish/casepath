"""Whole-study credit reservation and append-only single-attempt request journal.

This application boundary supplements, never replaces, canonical admission and
account-level coordination. Balance observations are ceilings, not authority.
"""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import json
import sqlite3
from .wire import canonical, digest, save, load, Invalid
from .schedule import money


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Journal:
    def __init__(self, path: Path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
CREATE TABLE IF NOT EXISTS studies(plan_id TEXT PRIMARY KEY, plan_sha TEXT NOT NULL, allocation TEXT NOT NULL, reserved TEXT NOT NULL, origin TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS requests(request_id TEXT PRIMARY KEY,plan_id TEXT NOT NULL,slot_id TEXT NOT NULL,reserved TEXT NOT NULL,state TEXT NOT NULL,actual TEXT, UNIQUE(plan_id,slot_id));
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT,time TEXT NOT NULL,plan_id TEXT NOT NULL,request_id TEXT,kind TEXT NOT NULL,body TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append only'); END;
''')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10);db.row_factory=sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()
    def _event(self,db,plan_id,request_id,kind,body):
        db.execute('INSERT INTO events(time,plan_id,request_id,kind,body) VALUES(?,?,?,?,?)',(now(),plan_id,request_id,kind,canonical(body).decode()))

    def reserve(self, plan: dict, allocation: dict) -> None:
        """Called only after canonical authorization; it cannot grant that authorization.

        Allocation must name independently reconciled outside liabilities and a
        specific existing-credit allocation. All comparison slots are reserved.
        """
        required={'plan_id','canonical_admission_receipt_sha256','credit_authority_receipt_sha256',
            'balance_observed_usd','outside_liabilities_usd','allocated_usd','observed_at','origin','parameter_binding_sha256','token_bound_attestation_sha256'}
        if set(allocation)!=required or allocation['plan_id']!=plan['plan_id']:
            raise Invalid('allocation binding fields missing')
        from ..source_only_runtime_v1 import hash_string
        for key in ['canonical_admission_receipt_sha256','credit_authority_receipt_sha256','parameter_binding_sha256','token_bound_attestation_sha256']:
            if not hash_string(allocation[key]):raise Invalid('missing external authority identity')
        if allocation['origin'] not in {'engineering_fixture','canonical_managed_run'}:
            raise Invalid('unknown authority origin')
        if plan['bindings']['origin']=='engineering_fixture' and allocation['origin']!='engineering_fixture':
            raise Invalid('fixture study cannot be promoted to science')
        observed=datetime.fromisoformat(allocation['observed_at'])
        if observed.tzinfo is None or not 0<=(datetime.now(timezone.utc)-observed).total_seconds()<=300:
            raise Invalid('credit/liability observation must be fresh')
        balance=money(allocation['balance_observed_usd']);outside=money(allocation['outside_liabilities_usd'])
        allowed=money(allocation['allocated_usd']);total=money(plan['summary']['reserved_usd'])
        if balance > money(plan['bindings']['config']['observed_credit_upper_bound_usd']):
            raise Invalid('credit observation cannot exceed the frozen existing-credit ceiling')
        if total>allowed or allowed>balance-outside:
            raise Invalid('complete comparison does not fit reconciled existing-credit allocation')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM studies WHERE plan_id=?',(plan['plan_id'],)).fetchone()
            if row:
                if row['plan_sha']!=digest(plan) or row['allocation']!=canonical(allocation).decode():
                    raise Invalid('existing study reservation differs')
                return
            other=sum((money(r['reserved']) for r in db.execute('SELECT reserved FROM studies')),Decimal(0))
            if other+total>balance-outside:
                raise Invalid('shared local study reservations exceed credit ceiling')
            db.execute('INSERT INTO studies VALUES(?,?,?,?,?)',(plan['plan_id'],digest(plan),canonical(allocation).decode(),str(total),allocation['origin']))
            self._event(db,plan['plan_id'],None,'STUDY_RESERVED',allocation)

    def begin(self, plan: dict, request: dict, authorization: dict) -> None:
        expected={'plan_id':plan['plan_id'],'request_id':request['request_id'],'payload_sha256':request['payload_sha256']}
        if any(authorization.get(k)!=v for k,v in expected.items()) or authorization.get('authorized') is not True:
            raise Invalid('canonical per-send authorization is missing or mismatched')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            study=db.execute('SELECT * FROM studies WHERE plan_id=?',(plan['plan_id'],)).fetchone()
            if not study or study['plan_sha']!=digest(plan):raise Invalid('complete study not reserved')
            if study['origin'] != authorization.get('origin'):raise Invalid('authority/transport origin mismatch')
            if study['origin']=='canonical_managed_run':
                from ..source_only_runtime_v1 import hash_string
                expected_phase='source_preparation' if request['slot_id'].startswith('prep:') else next(c['split'] for c in plan['matrix'] if request['slot_id'] in c.get('requests',[]))
                if authorization.get('phase')!=expected_phase:raise Invalid('canonical phase grant differs')
                if expected_phase=='hidden_test' and (not hash_string(authorization.get('protected_freeze_receipt_sha256')) or not hash_string(authorization.get('target_history_receipt_sha256'))):
                    raise Invalid('protected execution needs actual canonical freeze and access-history verification')
            if db.execute("SELECT 1 FROM requests WHERE plan_id=? AND state IN ('sent','uncertain','cost_unknown','overrun')",(plan['plan_id'],)).fetchone():
                raise Invalid('unreconciled request or charge; do not send another')
            amount=money(request['reserved_usd'])
            spent=sum((max(money(r['reserved']),money(r['actual'] or '0')) for r in db.execute('SELECT reserved,actual FROM requests WHERE plan_id=?',(plan['plan_id'],))),Decimal(0))
            if spent+amount>money(study['reserved']):raise Invalid('whole-study reservation exhausted')
            try:
                db.execute('INSERT INTO requests VALUES(?,?,?,?,?,?)',(request['request_id'],plan['plan_id'],request['slot_id'],str(amount),'sent',None))
            except sqlite3.IntegrityError as exc:
                raise Invalid('request slot already attempted; reconcile, never replay') from exc
            self._event(db,plan['plan_id'],request['request_id'],'REQUEST_STARTED',{'request':request,'authorization':authorization})

    def observe(self, request_id: str, *, state: str, actual_usd: str | None, evidence: dict) -> None:
        if state not in {'completed','failed','uncertain'}:raise Invalid('invalid observation state')
        actual=money(actual_usd) if actual_usd is not None else None
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM requests WHERE request_id=?',(request_id,)).fetchone()
            if row is None:raise Invalid('unknown request')
            if row['state'] not in {'sent','uncertain','cost_unknown'}:raise Invalid('terminal request cannot be overwritten')
            final=state
            if actual is None and state!='uncertain':final='cost_unknown'
            if actual is not None and actual>money(row['reserved']):final='overrun'
            db.execute('UPDATE requests SET state=?,actual=? WHERE request_id=?',(final,str(actual) if actual is not None else None,request_id))
            self._event(db,row['plan_id'],request_id,'OBSERVATION',{'state':state,'ledger_state':final,'actual_usd':str(actual) if actual is not None else None,'evidence':evidence})

    def facts(self,plan_id:str) -> dict:
        with self.connect() as db:
            rows=[dict(r) for r in db.execute('SELECT * FROM requests WHERE plan_id=? ORDER BY rowid',(plan_id,))]
            events=[dict(r) for r in db.execute('SELECT * FROM events WHERE plan_id=? ORDER BY seq',(plan_id,))]
        known=sum((money(r['actual']) for r in rows if r['actual'] is not None),Decimal(0))
        return {'requests':rows,'events':events,'known_cost_usd':str(known),
                'unknown_cost_count':sum(r['actual'] is None for r in rows),
                'complete_cost_known':all(r['actual'] is not None for r in rows)}
