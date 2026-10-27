"""A fresh case store: cases, original files, runs, run progress, results, Knowledge.

SQLite and a content-addressed file folder serve the development workspace.
The same operations are what an operated business service will expose; no
caller depends on SQL. Original bytes are kept exactly as uploaded.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import threading
import uuid

SCHEMA = """
create table if not exists cases(
  id text primary key, title text not null, intake text not null,
  workflow_id text, workflow_version text, workflow_selected_by text,
  created_by text not null, created_at text not null, updated_at text not null);
create table if not exists files(
  id text primary key, case_id text not null references cases(id), name text not null,
  media_type text not null, kind text not null, sha256 text not null, size integer not null,
  extraction text not null, uploaded_by text not null, created_at text not null);
create table if not exists runs(
  id text primary key, case_id text not null references cases(id), status text not null,
  files_sha256 text not null, workflow_id text, workflow_version text, deployment text,
  routing text, result text, error text, created_by text not null, created_at text not null, finished_at text);
create table if not exists run_events(
  run_id text not null references runs(id), seq integer not null, at text not null, data text not null,
  primary key(run_id, seq));
create table if not exists knowledge(
  id text primary key, family text not null, status text not null, data text not null, updated_at text not null);
create table if not exists knowledge_uses(
  knowledge_id text not null, run_id text not null, case_id text not null, at text not null, outcome text not null,
  primary key(knowledge_id, run_id));
create table if not exists case_edits(
  id text primary key, case_id text not null references cases(id), data text not null, status text not null,
  created_at text not null);
"""
ACTIVE = ("queued", "running")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class Conflict(RuntimeError):
    pass


class NotFound(KeyError):
    pass


class CaseStore:
    def __init__(self, data_dir):
        self.root = Path(data_dir)
        (self.root / "files").mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.root / "casepath.db", check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("pragma journal_mode=wal")
        self._db.execute("pragma foreign_keys=on")
        self._db.executescript(SCHEMA)
        self._lock = threading.RLock()

    def close(self):
        with self._lock:
            self._db.close()

    # One connection serves the web requests and the run threads, so every
    # statement, including reads, runs under the same lock.
    def _one(self, sql, *args):
        with self._lock:
            row = self._db.execute(sql, args).fetchone()
        return dict(row) if row else None

    def _all(self, sql, *args):
        with self._lock:
            return [dict(r) for r in self._db.execute(sql, args).fetchall()]

    # Cases
    def create_case(self, title, intake, user):
        case_id, at = new_id("case"), now()
        with self._lock:
            self._db.execute("insert into cases(id,title,intake,created_by,created_at,updated_at) values(?,?,?,?,?,?)",
                             (case_id, title, json.dumps(intake or {}, ensure_ascii=False), user, at, at))
        return self.get_case(case_id)

    def get_case(self, case_id):
        row = self._one("select * from cases where id=?", case_id)
        if row is None:
            raise NotFound(case_id)
        row["intake"] = json.loads(row["intake"])
        return row

    def list_cases(self):
        rows = self._all("select c.*, (select count(*) from files f where f.case_id=c.id) as file_count,"
                         " (select status from runs r where r.case_id=c.id order by created_at desc, rowid desc limit 1) as run_status"
                         " from cases c order by updated_at desc")
        for row in rows:
            row["intake"] = json.loads(row["intake"])
        return rows

    def select_workflow(self, case_id, workflow_id, version, user):
        with self._lock:
            self.get_case(case_id)
            self._db.execute("update cases set workflow_id=?, workflow_version=?, workflow_selected_by=?, updated_at=? where id=?",
                             (workflow_id, version, user, now(), case_id))
        return self.get_case(case_id)

    # Files
    def add_file(self, case_id, name, media_type, kind, data, extraction, user):
        self.get_case(case_id)
        digest = sha256(data).hexdigest()
        path = self.root / "files" / digest[:2] / digest
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".part")
            temporary.write_bytes(data)
            temporary.replace(path)
        file_id, at = new_id("file"), now()
        with self._lock:
            self._db.execute("insert into files values(?,?,?,?,?,?,?,?,?,?)",
                             (file_id, case_id, name, media_type, kind, digest, len(data),
                              json.dumps(extraction, ensure_ascii=False), user, at))
            self._db.execute("update cases set updated_at=? where id=?", (at, case_id))
        return self.get_file(file_id)

    def get_file(self, file_id, with_text=False):
        row = self._one("select * from files where id=?", file_id)
        if row is None:
            raise NotFound(file_id)
        extraction = json.loads(row.pop("extraction"))
        if not with_text:
            extraction.pop("text", None)
        row["extraction"] = extraction
        return row

    def update_extraction(self, file_id, extraction):
        with self._lock:
            self._db.execute("update files set extraction=? where id=?", (json.dumps(extraction, ensure_ascii=False), file_id))
        return self.get_file(file_id)

    def list_files(self, case_id, with_text=False):
        return [self.get_file(r["id"], with_text) for r in self._all("select id from files where case_id=? order by created_at, rowid", case_id)]

    def file_bytes(self, file_id):
        row = self.get_file(file_id)
        return (self.root / "files" / row["sha256"][:2] / row["sha256"]).read_bytes(), row

    def files_digest(self, case_id):
        rows = self._all("select sha256 from files where case_id=? order by sha256", case_id)
        return sha256("\n".join(r["sha256"] for r in rows).encode()).hexdigest()

    # Runs
    def create_run(self, case_id, user):
        with self._lock:
            self.get_case(case_id)
            if self._one(f"select id from runs where case_id=? and status in {ACTIVE}", case_id):
                raise Conflict("this case already has a run in progress")
            run_id = new_id("run")
            self._db.execute("insert into runs(id,case_id,status,files_sha256,created_by,created_at) values(?,?,?,?,?,?)",
                             (run_id, case_id, "queued", self.files_digest(case_id), user, now()))
        return self.get_run(run_id)

    def update_run(self, run_id, **fields):
        allowed = {"status", "workflow_id", "workflow_version", "deployment", "routing", "result", "error", "finished_at"}
        if set(fields) - allowed:
            raise ValueError("unknown run field")
        values = [json.dumps(v, ensure_ascii=False, default=str) if k in {"routing", "result"} and v is not None else v
                  for k, v in fields.items()]
        with self._lock:
            self._db.execute(f"update runs set {', '.join(k + '=?' for k in fields)} where id=?", (*values, run_id))
        return self.get_run(run_id)

    def get_run(self, run_id, after=0):
        row = self._one("select * from runs where id=?", run_id)
        if row is None:
            raise NotFound(run_id)
        for key in ("routing", "result"):
            row[key] = json.loads(row[key]) if row[key] else None
        row["events"] = [{"seq": e["seq"], "at": e["at"], **json.loads(e["data"])}
                         for e in self._all("select * from run_events where run_id=? and seq>? order by seq", run_id, after)]
        return row

    def latest_run(self, case_id, status=None):
        sql = "select id from runs where case_id=?" + (" and status=?" if status else "") + " order by created_at desc, rowid desc limit 1"
        row = self._one(sql, *((case_id, status) if status else (case_id,)))
        return self.get_run(row["id"]) if row else None

    def append_event(self, run_id, data):
        with self._lock:
            seq = (self._one("select max(seq) as s from run_events where run_id=?", run_id)["s"] or 0) + 1
            self._db.execute("insert into run_events values(?,?,?,?)", (run_id, seq, now(), json.dumps(data, ensure_ascii=False, default=str)))
        return seq

    def interrupt_unfinished(self):
        """After a restart, say plainly that unfinished runs stopped."""
        with self._lock:
            ids = [r["id"] for r in self._all(f"select id from runs where status in {ACTIVE}")]
            for run_id in ids:
                self._db.execute("update runs set status='interrupted', error=?, finished_at=? where id=?",
                                 ("The service restarted before this run finished.", now(), run_id))
        return ids

    # Knowledge: whole items, versioned by the knowledge module
    def save_knowledge(self, item):
        with self._lock:
            self._db.execute("insert into knowledge values(?,?,?,?,?) on conflict(id) do update set "
                             "family=excluded.family, status=excluded.status, data=excluded.data, updated_at=excluded.updated_at",
                             (item["id"], item["family"], item["status"], json.dumps(item, ensure_ascii=False), now()))
        return item

    def get_knowledge(self, knowledge_id):
        row = self._one("select data from knowledge where id=?", knowledge_id)
        if row is None:
            raise NotFound(knowledge_id)
        return json.loads(row["data"])

    def list_knowledge(self, family=None, statuses=None):
        sql, args = "select data from knowledge where 1=1", []
        if family:
            sql, args = sql + " and family=?", args + [family]
        rows = [json.loads(r["data"]) for r in self._all(sql + " order by rowid", *args)]
        return [r for r in rows if statuses is None or r["status"] in statuses]

    def record_use(self, knowledge_id, run_id, case_id, outcome):
        with self._lock:
            self._db.execute("insert or replace into knowledge_uses values(?,?,?,?,?)", (knowledge_id, run_id, case_id, now(), outcome))

    def knowledge_uses(self, knowledge_id=None):
        if knowledge_id:
            return self._all("select * from knowledge_uses where knowledge_id=? order by at", knowledge_id)
        return self._all("select * from knowledge_uses order by at")

    # Edits to a case's process
    def add_edit(self, case_id, op, args, user, reason):
        self.get_case(case_id)
        edit = {"id": new_id("ed"), "case_id": case_id, "op": op, "args": args, "by": user, "reason": reason,
                "status": "active", "at": now()}
        with self._lock:
            self._db.execute("insert into case_edits values(?,?,?,?,?)",
                             (edit["id"], case_id, json.dumps(edit, ensure_ascii=False), "active", edit["at"]))
            self._db.execute("update cases set updated_at=? where id=?", (edit["at"], case_id))
        return edit

    def list_edits(self, case_id, active_only=True):
        rows = [json.loads(r["data"]) | {"status": r["status"]} for r in
                self._all("select data, status from case_edits where case_id=? order by created_at, rowid", case_id)]
        return [r for r in rows if r["status"] == "active" or not active_only]

    def get_edit(self, edit_id):
        row = self._one("select data, status from case_edits where id=?", edit_id)
        if row is None:
            raise NotFound(edit_id)
        return json.loads(row["data"]) | {"status": row["status"]}

    def set_edit_status(self, edit_id, status, user):
        edit = self.get_edit(edit_id)
        with self._lock:
            self._db.execute("update case_edits set status=? where id=?", (status, edit_id))
            self._db.execute("update cases set updated_at=? where id=?", (now(), edit["case_id"]))
        return self.get_edit(edit_id) | {"changed_by": user}
