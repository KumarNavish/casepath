"""A fresh case store: cases, original files, runs, run progress, results, Knowledge, case workers' feedback, and a
jurist's marks on the legal content (reviews), each also logged.

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
  routing text, result text, error text, created_by text not null, created_at text not null, finished_at text,
  kind text not null default 'full', builds_on text);
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
create table if not exists feedback(
  run_id text not null references runs(id), target text not null, by text not null, verdict text not null,
  note text not null, at text not null, primary key(run_id, target, by));
create table if not exists events(
  event_id text primary key, case_id text not null references cases(id), seq integer not null, at text not null, data text not null);
create index if not exists events_case on events(case_id, seq);
create table if not exists deletions(
  case_id text primary key, deleted_at text not null, deleted_by text not null, reason text not null, removed text not null);
create table if not exists reviews(
  id text primary key, file text not null, element text not null, content_sha256 text not null, mark text not null,
  comment text not null, suggestion text not null, reviewer text not null, at text not null);
create index if not exists reviews_element on reviews(file, element);
create table if not exists workspace_events(
  event_id text primary key, seq integer not null, at text not null, data text not null);
create table if not exists labels(
  case_id text primary key references cases(id), data text not null, saved_by text not null, saved_at text not null);
create table if not exists drafts(
  id text not null, case_id text not null references cases(id), form text not null, part text not null,
  base_sha256 text not null, base text not null, text text not null, parent_id text, by text not null, at text not null,
  op_id text, primary key(id, part));
create index if not exists drafts_case on drafts(case_id, form);
create table if not exists translations(
  lang text not null, sha256 text not null, translation text not null, case_id text, at text not null,
  primary key(lang, sha256));
create table if not exists translation_spend(day text primary key, tokens integer not null);
create table if not exists case_ticks(
  case_id text primary key references cases(id), digest text not null, state text not null, at text not null);
"""
REVIEW_MARKS = ("geprueft", "aenderung", "frage")
ACTIVE = ("queued", "running")
INTERRUPTED = "interrupted: Der Dienst wurde neu gestartet, bevor der Lauf fertig war."


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class Conflict(RuntimeError):
    pass


class NotFound(KeyError):
    pass


class Duplicate(Conflict):
    """A file whose bytes the case already holds: the file that holds them (its name, when it came, its id)."""

    def __init__(self, name, created_at, file_id):
        super().__init__(f"Bereits in der Akte: «{name}»")
        self.name, self.created_at, self.file_id = name, created_at, file_id


class CaseStore:
    def __init__(self, data_dir):
        self.root = Path(data_dir)
        (self.root / "files").mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.root / "casepath.db", check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("pragma journal_mode=wal")
        self._db.execute("pragma foreign_keys=on")
        self._db.execute("pragma secure_delete=on")  # what is deleted is overwritten, not left in the file's freed pages
        self._db.executescript(SCHEMA)
        self._lock = threading.RLock()
        # a store made before updates: its runs are full preparations
        columns = {r["name"] for r in self._all("pragma table_info(runs)")}
        if "kind" not in columns:
            self._db.execute("alter table runs add column kind text not null default 'full'")
        if "builds_on" not in columns:
            self._db.execute("alter table runs add column builds_on text")
        # a store made before a case had its reference number and its owner: both empty (the owner then reads as its creator)
        columns = {r["name"] for r in self._all("pragma table_info(cases)")}
        for name in ("reference", "owner", "deputy"):
            if name not in columns:
                self._db.execute(f"alter table cases add column {name} text")

    def close(self):
        with self._lock:
            self._db.close()

    # What the model translated for a reader in another language (web/translate.py): the translation by the hash of its
    # original line, with the case it came from, so it is deleted with that case; and the tokens spent on it per day.
    def translation(self, lang, sha256):
        row = self._one("select translation from translations where lang=? and sha256=?", lang, sha256)
        return row["translation"] if row else None

    def translations_put(self, lang, rows, tokens=0):
        with self._lock:
            for sha256, translation, case_id in rows:
                self._db.execute("insert or replace into translations values(?,?,?,?,?)", (lang, sha256, translation, case_id, now()))
            if tokens:
                day = now()[:10]
                self._db.execute("insert into translation_spend values(?,?) on conflict(day) do update set tokens=tokens+excluded.tokens", (day, tokens))

    def translation_spent(self, day):
        row = self._one("select tokens from translation_spend where day=?", day)
        return row["tokens"] if row else 0

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
            self._db.execute("insert into cases(id,title,intake,created_by,created_at,updated_at,owner) values(?,?,?,?,?,?,?)",
                             (case_id, title, json.dumps(intake or {}, ensure_ascii=False), user, at, at, user))
        return self.get_case(case_id)

    def set_identity(self, case_id, **fields):
        """The case's reference number, its owner and the owner's deputy (only the fields given; None empties one)."""
        names = [k for k in ("reference", "owner", "deputy") if k in fields]
        with self._lock:
            self.get_case(case_id)
            if names:
                self._db.execute(f"update cases set {', '.join(f'{k}=?' for k in names)}, updated_at=? where id=?",
                                 (*[fields[k] or None for k in names], now(), case_id))
        return self.get_case(case_id)

    def case_with_reference(self, reference, other_than=None):
        """A case that already carries this reference number, or None."""
        row = self._one("select id, title from cases where reference=? and id<>?", reference, other_than or "")
        return row

    def get_case(self, case_id):
        row = self._one("select * from cases where id=?", case_id)
        if row is None:
            raise NotFound(case_id)
        row["intake"] = json.loads(row["intake"])
        return row

    def list_cases(self):
        rows = self._all("select c.*, (select count(*) from files f where f.case_id=c.id) as file_count,"
                         " (select status from runs r where r.case_id=c.id and r.status<>'discarded' order by created_at desc, rowid desc limit 1) as run_status,"
                         " (select workflow_id from runs r where r.case_id=c.id and status='completed' order by created_at desc, rowid desc limit 1) as run_workflow_id"
                         " from cases c order by updated_at desc, rowid desc")  # the newest first, also within one second
        for row in rows:
            row["intake"] = json.loads(row["intake"])
        return rows

    def rename_case(self, case_id, title):
        with self._lock:
            self.get_case(case_id)
            self._db.execute("update cases set title=?, updated_at=? where id=?", (title, now(), case_id))
        return self.get_case(case_id)

    def select_workflow(self, case_id, workflow_id, version, user):
        with self._lock:
            self.get_case(case_id)
            self._db.execute("update cases set workflow_id=?, workflow_version=?, workflow_selected_by=?, updated_at=? where id=?",
                             (workflow_id, version, user, now(), case_id))
        return self.get_case(case_id)

    # Files
    def put_blob(self, data):
        """Keep bytes by their SHA-256 (originals and prepared page images); returns the digest."""
        digest = sha256(data).hexdigest()
        path = self.root / "files" / digest[:2] / digest
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".part")
            temporary.write_bytes(data)
            temporary.replace(path)
        return digest

    def blob(self, digest):
        return (self.root / "files" / digest[:2] / digest).read_bytes()

    def add_file(self, case_id, name, media_type, kind, data, extraction, user, refuse_same=False):
        """``refuse_same``: raise Duplicate when the case already holds these bytes (an upload); checked under the store
        lock, so two uploads of one file at once keep one. Without it a file is kept as given (a study copy, a cut, a
        prepared case: copied whole, also where an older store holds the same bytes twice; there is no unique index)."""
        self.get_case(case_id)
        digest = self.put_blob(data)
        file_id, at = new_id("file"), now()
        with self._lock:
            same = self.file_by_sha(case_id, digest) if refuse_same else None
            if same:
                raise Duplicate(same["name"], same["created_at"], same["id"])
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
    def create_run(self, case_id, user, kind="full", builds_on=None):
        """A run of the case: a full preparation, or an update (``kind`` «update») that builds on a completed run."""
        if kind not in ("full", "update"):
            raise ValueError("a run is full or an update")
        with self._lock:
            self.get_case(case_id)
            if self._one(f"select id from runs where case_id=? and status in {ACTIVE}", case_id):
                raise Conflict("this case already has a run in progress")
            run_id = new_id("run")
            self._db.execute("insert into runs(id,case_id,status,files_sha256,created_by,created_at,kind,builds_on) values(?,?,?,?,?,?,?,?)",
                             (run_id, case_id, "queued", self.files_digest(case_id), user, now(), kind, builds_on))
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

    def run_statuses(self, run_ids):
        """{run id: status} of the given runs that exist; nothing else of them."""
        ids = [str(i) for i in run_ids][:50]
        if not ids:
            return {}
        rows = self._all(f"select id, status from runs where id in ({','.join('?' for _ in ids)})", *ids)
        return {r["id"]: r["status"] for r in rows}

    def get_run(self, run_id, after=0):
        row = self._one("select * from runs where id=?", run_id)
        if row is None:
            raise NotFound(run_id)
        for key in ("routing", "result"):
            row[key] = json.loads(row[key]) if row[key] else None
        row["events"] = [{"seq": e["seq"], "at": e["at"], **json.loads(e["data"])}
                         for e in self._all("select * from run_events where run_id=? and seq>? order by seq", run_id, after)]
        return row

    def recent_runs(self, limit=30, kind=None):
        """The latest completed runs of any case, newest first (for the stage times a run line expects); ``kind``: only
        full preparations or only updates, never the two mixed."""
        if kind:
            rows = self._all("select id from runs where status='completed' and kind=? order by created_at desc, rowid desc limit ?", kind, limit)
        else:
            rows = self._all("select id from runs where status='completed' order by created_at desc, rowid desc limit ?", limit)
        return [self.get_run(r["id"]) for r in rows]

    def completed_runs(self, case_id, limit=2):
        """The case's latest completed runs, newest first (for what changed between two preparations)."""
        rows = self._all("select id from runs where case_id=? and status='completed' order by created_at desc, rowid desc limit ?", case_id, limit)
        return [self.get_run(r["id"]) for r in rows]

    def latest_run(self, case_id, status=None, exclude=None):
        """The case's newest run (of a status; ``exclude``: not of this status, as a run set aside)."""
        sql = ("select id from runs where case_id=?" + (" and status=?" if status else "") + (" and status<>?" if exclude else "")
               + " order by created_at desc, rowid desc limit 1")
        row = self._one(sql, case_id, *([status] if status else []), *([exclude] if exclude else []))
        return self.get_run(row["id"]) if row else None

    def append_event(self, run_id, data):
        with self._lock:
            seq = (self._one("select max(seq) as s from run_events where run_id=?", run_id)["s"] or 0) + 1
            self._db.execute("insert into run_events values(?,?,?,?)", (run_id, seq, now(), json.dumps(data, ensure_ascii=False, default=str)))
        return seq

    def interrupt_unfinished(self):
        """After a restart, say plainly that unfinished runs stopped; the ids of those runs."""
        with self._lock:
            ids = [r["id"] for r in self._all(f"select id from runs where status in {ACTIVE}")]
            for run_id in ids:
                self._db.execute("update runs set status='interrupted', error=?, finished_at=? where id=?",
                                 (INTERRUPTED, now(), run_id))
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

    # Deleting a case removes everything derived from it: files (and their bytes when no other case shares them), runs,
    # progress, feedback, edits, Knowledge uses, Knowledge learned from it, and its quotes in other Knowledge.
    def delete_case(self, case_id, user="", reason="request"):
        """Delete the case and everything derived from it; keep a content-free record that it existed and was deleted."""
        self.get_case(case_id)
        with self._lock:
            if self._one("select 1 as busy from runs where case_id=? and status in ('queued','running')", case_id):
                raise Conflict("A run is in progress for this case.")
            runs = [r["id"] for r in self._all("select id from runs where case_id=?", case_id)]
            rows = self._all("select sha256, extraction from files where case_id=?", case_id)
            digests = [r["sha256"] for r in rows]
            images = {d for r in rows for d in (json.loads(r["extraction"]).get("page_images") or {}).values()}
            images |= {json.loads(r["extraction"]).get("photo_image") for r in rows} - {None}
            removed = {"runs": len(runs), "files": len(digests), "knowledge": 0, "knowledge_quotes": 0}
            for run_id in runs:
                self._db.execute("delete from feedback where run_id=?", (run_id,))
                self._db.execute("delete from run_events where run_id=?", (run_id,))
            # the Versandpakete the case's approvals stored (bundle.saved): its own record, deleted with it
            bundles = {json.loads(r["data"]).get("sha256") for r in self._all("select data from events where case_id=?", case_id)
                       if json.loads(r["data"]).get("kind") == "bundle.saved"}
            for table in ("runs", "case_edits", "knowledge_uses", "files", "events", "labels", "drafts", "case_ticks", "translations"):
                self._db.execute(f"delete from {table} where case_id=?", (case_id,))
            for row in self._all("select id, data from knowledge"):
                item = json.loads(row["data"])
                if (item.get("origin") or {}).get("case_id") == case_id:
                    self._db.execute("delete from knowledge where id=?", (row["id"],))
                    self._db.execute("delete from knowledge_uses where knowledge_id=?", (row["id"],))
                    removed["knowledge"] += 1
                elif any(e.get("case_id") == case_id for e in item.get("evidence", [])):
                    kept = [e for e in item["evidence"] if e.get("case_id") != case_id]
                    removed["knowledge_quotes"] += len(item["evidence"]) - len(kept)
                    self._db.execute("update knowledge set data=? where id=?", (json.dumps({**item, "evidence": kept}, ensure_ascii=False), row["id"]))
            self._db.execute("delete from cases where id=?", (case_id,))
            self._db.execute("insert or replace into deletions values(?,?,?,?,?)", (case_id, now(), user or "", reason, json.dumps(removed)))
            for digest in set(digests):
                if not self._one("select 1 as used from files where sha256=?", digest):
                    (self.root / "files" / digest[:2] / digest).unlink(missing_ok=True)
            for digest in images:  # page images of the case's files, unless another file still points to them
                if not self._one("select 1 as used from files where extraction like ?", f"%{digest}%"):
                    (self.root / "files" / digest[:2] / digest).unlink(missing_ok=True)
            for digest in bundles - {None}:  # its Versandpakete, unless a file or another case's package is the same bytes
                if not self._one("select 1 as used from files where sha256=?", digest) and \
                        not self._one("select 1 as used from events where data like ?", f"%{digest}%"):
                    (self.root / "files" / digest[:2] / digest).unlink(missing_ok=True)
        return removed

    def sweep_blobs(self):
        """Remove stored bytes no case refers to any more (a file, a page image or a Versandpaket whose case was deleted
        while its removal did not complete, or a copy restored from the volume after it); returns how many. A file is
        kept whenever its SHA-256 stands anywhere in a file's row or a case's log."""
        import re
        with self._lock:
            kept = {r["sha256"] for r in self._all("select sha256 from files")}
            for table, column in (("files", "extraction"), ("events", "data")):
                for r in self._all(f"select {column} as text from {table}"):
                    kept.update(re.findall(r"[0-9a-f]{64}", r["text"] or ""))
            removed = 0
            for path in (self.root / "files").glob("*/*"):
                if path.suffix != ".part" and path.name not in kept:
                    path.unlink(missing_ok=True)
                    removed += 1
        return removed

    def deletions(self):
        rows = self._all("select * from deletions order by deleted_at")
        for row in rows:
            row["removed"] = json.loads(row["removed"])
        return rows

    def purge(self, before, user="retention", dry_run=False):
        """Delete every case last changed before ``before`` (ISO time), for a retention period; runs in progress wait."""
        due = [r["id"] for r in self._all("select id from cases where updated_at < ? order by updated_at", before)]
        if dry_run:
            return {"due": len(due), "deleted": 0, "busy": 0}
        deleted = busy = 0
        for case_id in due:
            try:
                self.delete_case(case_id, user, "retention")
                deleted += 1
            except Conflict:
                busy += 1
        return {"due": len(due), "deleted": deleted, "busy": busy}

    # Case workers' feedback on a run's results: one verdict per person and item, the latest kept
    def set_feedback(self, run_id, target, verdict, note, user):
        self.get_run(run_id)
        with self._lock:
            if verdict is None:
                self._db.execute("delete from feedback where run_id=? and target=? and by=?", (run_id, target, user))
            else:
                self._db.execute("insert or replace into feedback values(?,?,?,?,?,?)", (run_id, target, user, verdict, note or "", now()))
        return self.list_feedback(run_id)

    def list_feedback(self, run_id):
        return self._all("select target, by, verdict, note, at from feedback where run_id=? order by at", run_id)

    # The append-only event log: every gesture on a case, never updated or removed except with the case itself
    def append_case_event(self, case_id, record):
        with self._lock:
            seq = (self._one("select max(seq) as seq from events where case_id=?", case_id) or {}).get("seq") or 0
            event = {**record, "event_id": new_id("ev"), "seq": seq + 1, "at": now()}
            self._db.execute("insert into events values(?,?,?,?,?)",
                             (event["event_id"], case_id, event["seq"], event["at"], json.dumps(event, ensure_ascii=False)))
        return event

    def append_case_events(self, case_id, records, unless=None):
        """Several events in one transaction; ``unless(existing)`` true refuses them all (returns None)."""
        with self._lock:
            existing = self.list_case_events(case_id)
            if unless and unless(existing):
                return None
            return [self.append_case_event(case_id, r) for r in records]

    # The daily pass's memory of a case (web/app.py tick): how its row read when it was last looked at
    def get_tick(self, case_id):
        row = self._one("select digest, state, at from case_ticks where case_id=?", case_id)
        return {**row, "state": json.loads(row["state"])} if row else None

    def set_tick(self, case_id, digest, state):
        with self._lock:
            self._db.execute("insert or replace into case_ticks values(?,?,?,?)", (case_id, digest, json.dumps(state, ensure_ascii=False), now()))

    def list_case_events(self, case_id):
        return [json.loads(r["data"]) for r in self._all("select data from events where case_id=? order by seq", case_id)]

    # The event log of what happens outside a case (a jurist's mark on an element of the legal content): append-only too
    def append_workspace_event(self, record):
        with self._lock:
            seq = (self._one("select max(seq) as seq from workspace_events") or {}).get("seq") or 0
            event = {**record, "event_id": new_id("ev"), "seq": seq + 1, "at": record.get("at") or now()}
            self._db.execute("insert into workspace_events values(?,?,?,?)", (event["event_id"], event["seq"], event["at"],
                                                                              json.dumps(event, ensure_ascii=False)))
        return event

    def list_workspace_events(self, kind=None):
        rows = [json.loads(r["data"]) for r in self._all("select data from workspace_events order by seq")]
        return [r for r in rows if kind is None or r.get("kind") == kind]

    # A jurist's review of the legal content (process/review.py): one row per mark, never updated; the latest mark of an
    # element is its mark, and it holds only for the content (hash) it was given on
    def add_review(self, file, element, content_sha256, mark, comment, suggestion, reviewer):
        if mark not in REVIEW_MARKS:
            raise ValueError("unknown mark")
        row = {"id": new_id("rv"), "file": file, "element": element, "content_sha256": content_sha256, "mark": mark,
               "comment": comment or "", "suggestion": suggestion or "", "reviewer": reviewer, "at": now()}
        with self._lock:
            self._db.execute("insert into reviews values(:id,:file,:element,:content_sha256,:mark,:comment,:suggestion,:reviewer,:at)", row)
            self.append_workspace_event({"schema": "casepath.review.event/1", "kind": "review.marked", "review_id": row["id"],
                                         **{k: row[k] for k in ("file", "element", "content_sha256", "mark", "comment", "suggestion", "reviewer")},
                                         "at": row["at"]})
        return row

    def list_reviews(self, file=None, element=None):
        sql, args = "select * from reviews where 1=1", []
        if file:
            sql, args = sql + " and file=?", args + [file]
        if element:
            sql, args = sql + " and element=?", args + [element]
        return self._all(sql + " order by rowid", *args)

    def latest_reviews(self):
        """{"<file>:<element>": its latest mark}."""
        return {f"{r['file']}:{r['element']}": r for r in self.list_reviews()}

    # The insurer's own decision points in a case file (casepath.labels/1, quality/points.py): one set per case, replaced whole
    def save_labels(self, case_id, labels, user):
        self.get_case(case_id)
        with self._lock:
            self._db.execute("insert into labels values(?,?,?,?) on conflict(case_id) do update set data=excluded.data, "
                             "saved_by=excluded.saved_by, saved_at=excluded.saved_at",
                             (case_id, json.dumps(labels, ensure_ascii=False), user, now()))
        return self.get_labels(case_id)

    def get_labels(self, case_id):
        row = self._one("select data from labels where case_id=?", case_id)
        if row is None:
            raise NotFound(case_id)
        return json.loads(row["data"])

    def list_labels(self):
        return [json.loads(r["data"]) for r in self._all("select data from labels order by case_id")]

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

    def similar_edits(self, op, args, case_id):
        """Active edits in other cases that are the same correction: the same operation on the same thing. What «the
        same» is depends on the operation: an added document, question or step is the same by what it is called (its
        title, without case or spacing; the step it hangs on does not make two different documents one), a struck
        document by its id, a fact by the fact and the value set; anything else by its named target."""
        named = {"add_document": "title", "add_step": "title", "add_question": "question"}.get(op)
        fold = lambda v: " ".join(str(v or "").casefold().split())
        if named:
            want = fold(args.get(named))
            same = lambda r: bool(want) and fold(r["args"].get(named)) == want
        else:
            key = {k: args.get(k) for k in ("fact", "document", "step", "value", "request", "how") if args.get(k) is not None}
            same = lambda r: bool(key) and {k: r["args"].get(k) for k in key} == key
        rows = [json.loads(r["data"]) for r in self._all("select data from case_edits where status='active' and case_id<>?", case_id)]
        return [r for r in rows if r["op"] == op and same(r)]

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

    # Each slice's own methods go in its section below.
    # -- assessment (Slice A) ----------------------------------------------------------------------------------------------

    # -- completion (Slice B): the drafts per letter part, numbered edits, the dispatch ---------------------------------------
    def add_draft(self, case_id, form, parts, user, parent_id=None, op_id=None):
        """One save of the handler's text of a letter or an enclosure (``form``): one row per part {part, base_sha256, base,
        text} under one id, never updated. Refused (Conflict, its ``latest`` the save {id, by, at} it missed) when
        ``parent_id`` is not the form's latest save; an ``op_id`` already stored returns that first save. Returns {id, by,
        at, parts, repeated}."""
        with self._lock:
            self.get_case(case_id)
            if op_id:
                done = self._all("select * from drafts where case_id=? and form=? and op_id=? order by rowid", case_id, form, op_id)
                if done:
                    return {"id": done[0]["id"], "by": done[0]["by"], "at": done[0]["at"], "repeated": True,
                            "parts": [{k: r[k] for k in ("part", "base_sha256", "base", "text")} for r in done]}
            latest = self._one("select id, by, at from drafts where case_id=? and form=? order by rowid desc limit 1", case_id, form)
            if (latest or {}).get("id") != (parent_id or None):
                error = Conflict(f"Inzwischen von {(latest or {}).get('by') or 'einer anderen Person'} geändert: neu laden")
                error.latest = latest or {}
                raise error
            draft_id, at = new_id("dr"), now()
            for p in parts:
                self._db.execute("insert into drafts(id,case_id,form,part,base_sha256,base,text,parent_id,by,at,op_id) values(?,?,?,?,?,?,?,?,?,?,?)",
                                 (draft_id, case_id, form, p["part"], p["base_sha256"], p["base"], p["text"], parent_id, user, at, op_id))
            self._db.execute("update cases set updated_at=? where id=?", (at, case_id))
        return {"id": draft_id, "by": user, "at": at, "parts": [dict(p) for p in parts], "repeated": False}

    def latest_drafts(self, case_id):
        """The handler's text of each letter and enclosure as last saved: {form: {"id": the latest save, "by", "at", "parts":
        {part: {id, base_sha256, base, text, by, at}}}}, each part's latest row (a part saved earlier keeps its row)."""
        out = {}
        for r in self._all("select rowid, * from drafts where case_id=? order by rowid", case_id):
            form = out.setdefault(r["form"], {"parts": {}})
            form.update(id=r["id"], by=r["by"], at=r["at"])
            form["parts"][r["part"]] = {k: r[k] for k in ("id", "base_sha256", "base", "text", "by", "at")}
        return out

    def draft_saves(self, case_id, since=None):
        """How often the handler's text was saved since ``since`` (each save once, whatever parts it held): their effort."""
        rows = self._all("select count(distinct id) as n from drafts where case_id=? and at>?", case_id, str(since or ""))
        return int((rows[0] if rows else {}).get("n") or 0)

    def add_numbered_edit(self, case_id, op, args, user, reason):
        """An edit that carries the next number of the handler's entries and the dispatches (account.next_number), drawn
        and written under the store lock, so two writers never share a number. ``args``: the edit's arguments without
        «n», or a function of the number that returns them."""
        from ..process.account import next_number
        with self._lock:
            n = next_number(self.list_edits(case_id, active_only=False))
            return self.add_edit(case_id, op, args(n) if callable(args) else {**args, "n": n}, user, reason)

    def dispatch_once(self, case_id, version, recipient, args, user, reason, event):
        """One approved version dispatched to one recipient, once: an active «add_dispatch» edit of that version and
        recipient is returned as it is, (edit, None); otherwise the numbered edit and its event (``event`` with the edit's
        id: «action.dispatched») are written under one lock, (edit, event)."""
        with self._lock:
            same = next((e for e in self.list_edits(case_id) if e["op"] == "add_dispatch" and (e.get("args") or {}).get("version") == version
                         and (e.get("args") or {}).get("recipient") == recipient), None)
            if same:
                return same, None
            edit = self.add_numbered_edit(case_id, "add_dispatch", dict(args), user, reason)
            return edit, self.append_case_event(case_id, {**event, "edit_id": edit["id"], "n": edit["args"]["n"]})

    # -- arrival (Slice C): files by their content -----------------------------------------------------------------------
    def file_by_sha(self, case_id, sha):
        """The case's first file with these bytes (SHA-256), or None: an upload of it again is refused, an attachment of
        it skipped and remembered on its e-mail."""
        row = self._one("select id from files where case_id=? and sha256=? order by created_at, rowid limit 1", case_id, sha)
        return self.get_file(row["id"]) if row else None
