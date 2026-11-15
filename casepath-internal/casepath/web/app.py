"""The internal CasePath web service.

Every API call needs a signed-in user. In an operated deployment the platform
gateway authenticates the employee and passes the identity in a trusted header
(``CASEPATH_IDENTITY_HEADER``); in a personal development workspace a fixed
``CASEPATH_DEV_USER`` stands in. With neither, the API refuses to serve.
The browser never receives a model credential.
"""
from contextlib import asynccontextmanager
from datetime import datetime
import hashlib
import os
import re
import secrets
import html
import json
import importlib.util
import threading
from dataclasses import replace
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import Depends, Query, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field

from ..process import casegraph, knowledge as kb, workflows
from ..process.clock import capped, follow_up, historic as historic_file, own_deadlines
from ..agents import core
from ..process import account, letters, review as reviews, screen, verlauf
from ..process.clock import as_of
from ..process.items import ITEM_KINDS, SCREEN_KINDS, kind_title, build_items, item_changes, items_sha256
from . import identity, listing
from ..agents.azure_model import AzureOpenAIModel, entra_token_provider
from ..config import load_settings
from .. import parity
from ..parity import source_tree
from ..read import cut
from ..read.evidence import Evidence
from ..read.pdfread import PdfError
from ..quality.replay import replay
from ..quality.auswertung import auswertung

SERVED_WHOLE_BYTES = 15 * 1024 * 1024  # the Databricks Apps proxy fails on responses of about 18 MB (measured 2026-11-11)
from ..read.extract import attachments, extract
from ..agents.runner import RunService, TooLarge, auto_update_reason, case_state
from .store import CaseStore, Conflict, Duplicate, NotFound

UI = Path(__file__).parent / "ui"
CONTRACT = Path(__file__).parents[2] / "docs" / "contracts" / "case-api.openapi.json"


class ImportRequest(BaseModel):
    path: str
    title: str | None = None
    workflow_id: str | None = None


IMPORTABLE = {".pdf", ".eml", ".msg", ".docx", ".txt", ".png", ".jpg", ".jpeg"}


class NewCase(BaseModel):
    title: str
    intake: dict = {}


class CaseTitle(BaseModel):
    title: str = Field(min_length=1, max_length=300)


EVENT_KINDS = {"filenote.copied", "session.started", "case.opened", "item.exposed", "source.opened", "item.confirmed", "item.corrected",
               "item.dismissed", "item.added", "correction.undone", "item.propagated", "point.settled", "unaided.saved",
               "unaided.frozen", "reveal", "post_reveal.revised", "idle.started", "idle.ended", "letter.copied", "case.closed",
               "cap.reached", "scale.answered", "technical.failure", "session.ended", "note.added", "followup.set", "letter.line", "case.historic",
               "letter.unblocked"}
REASONS = {"1": "Steht anders in den Akten", "2": "Steht nicht in den Akten", "3": "Hier nicht relevant", "4": "Gilt generell so",
           "5": "Weiss ich von ausserhalb der Akten", "6": "Formulierung", "none": "ohne Angabe"}


class OwnAnswer(BaseModel):
    step: str | None = Field(None, max_length=80)
    documents: list[str] = Field(default_factory=list, max_length=60)
    documents_other: str = Field("", max_length=500)
    action_kind: Literal["request", "answer", "advise", "close", "other"] | None = None
    action_other: str = Field("", max_length=500)


SERVER_KINDS = {"run.discarded", "study.frozen", "study.copied", "unaided.saved", "unaided.frozen", "reveal", "item.propagated", "item.corrected", "item.dismissed", "item.added",
                "item.confirmed", "correction.undone", "point.settled", "case.renamed", "case.historic",
                "entry.added", "entry.changed", "entry.removed"}  # written by the server only


class EventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # extras belong in "fields"; a stray top-level key is refused, not dropped
    kind: str = Field(min_length=3, max_length=40)
    item_id: str | None = Field(None, max_length=120, pattern=r"^[a-z_]+:[A-Za-z0-9_.:-]{1,100}$")
    fields: dict = Field(default_factory=dict)


class ActionChoice(BaseModel):
    kind: str = Field(pattern=r"^A\d{1,2}$")
    reason_code: Literal["1", "2", "3", "4", "5", "6"]


class StudyCopyRequest(BaseModel):
    expert: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")  # a pseudonym, never a name


class CutRequest(BaseModel):
    pages: str = Field(min_length=1, max_length=200)  # original page numbers to keep, e.g. "5-10"
    as_of: str | None = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")  # the day the case is looked at ("Stand am")
    file: str | None = Field(None, max_length=80)


class HistoricChoice(BaseModel):
    historic: bool  # a person moves the case into the historic files (true) or out of them (false)


class WorkflowChoice(BaseModel):
    workflow_id: str
    version: str | None = None


class EditRequest(BaseModel):
    op: str
    args: dict
    reason: str
    reason_code: Literal["1", "2", "3", "4", "5", "6", "none"] | None = None  # the one-tap reason; the text above is the note
    use_for_similar: bool = False
    activate: bool = False
    recheck: bool = True


class StatusChange(BaseModel):
    reason: str = ""


class ReviewMark(BaseModel):
    """A jurist's mark on one element of the legal content; «Änderung nötig» and «Frage» say why in a comment."""
    model_config = ConfigDict(extra="forbid")
    mark: Literal["geprueft", "aenderung", "frage"]
    comment: str = Field("", max_length=4000)
    suggestion: str = Field("", max_length=4000)  # the wording the jurist proposes (with «Änderung nötig»)
    sha256: str | None = Field(None, pattern=r"^[0-9a-f]{64}$")  # the content the jurist saw: refused when it changed meanwhile


PARTY = Literal["kunde", "gegenpartei", "kanzlei", "versicherer", "behoerde", "andere"]


class AgreedPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    what: str = Field("", max_length=120)
    amount: str = Field("", max_length=40)
    payer: PARTY | None = None
    by: str = Field("", max_length=20)


class AskedPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    what: str = Field("", max_length=120)
    of: PARTY | None = None
    by: str = Field("", max_length=20)


class NextPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    what: str = Field("", max_length=120)
    by: str = Field("", max_length=20)
    who: PARTY | None = None


class EntryForm(BaseModel):
    """The handler's own entry of the running account («Notiz hinzufügen»): what kind, with whom, when, what was said, and
    at most one row each of what was agreed, asked and the next step."""
    model_config = ConfigDict(extra="forbid")
    kind: Literal["telefon", "gespraech", "notiz", "email"]
    party: Literal["kunde", "gegenpartei", "kanzlei", "behoerde", "andere"] = "kunde"
    name: str = Field("", max_length=120)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    said: str = Field("", max_length=2000)
    agreed: AgreedPart | None = None
    asked: AskedPart | None = None
    next: NextPart | None = None


class Feedback(BaseModel):
    """A case worker's verdict on one result item; target names the item, never its content."""
    target: str = Field(pattern=r"^(answer|(fact|document|summary|timeline|deadline|open_point|reply|point|step|next_action|party|answer):[A-Za-z0-9_.-]{1,80})$")
    verdict: Literal["correct", "wrong", "done"] | None  # "done": a point under Braucht Ihr Urteil a case worker settled
    note: str = Field("", max_length=500)
    reason_code: Literal["1", "2", "3", "4", "5", "6", "none"] | None = None  # the one-tap reason for a correction


def default_model_factory(settings):
    if settings.model is None:
        return lambda: None
    shared = {}

    def factory(user_token=None):
        def workspace_kind():
            if settings.model.api == "messages":
                from ..agents.anthropic_model import AnthropicMessagesModel
                return AnthropicMessagesModel
            from ..agents.chat_model import ChatCompletionsModel
            return ChatCompletionsModel
        if settings.model.auth == "user":  # the person's own token: a fresh client per run, nothing shared
            if not user_token:
                return None
            kind = workspace_kind()
            model = kind(settings.model, lambda: user_token)
            if settings.model.reading_deployment:
                model.reading = kind(replace(settings.model, deployment=settings.model.reading_deployment), lambda: user_token)
            model.agents = {a: kind(replace(settings.model, deployment=d), lambda: user_token) for a, d in settings.model.agent_deployments}
            return model
        if "model" not in shared:
            if settings.model.provider == "databricks":
                from ..agents.chat_model import databricks_token_provider
                token, kind = databricks_token_provider(settings.model.endpoint), workspace_kind()
            else:
                token, kind = entra_token_provider(), AzureOpenAIModel
            shared["model"] = kind(settings.model, token)
            if settings.model.reading_deployment:  # page reading and dossier splitting on another deployment
                shared["model"].reading = kind(replace(settings.model, deployment=settings.model.reading_deployment), token)
            shared["model"].agents = {a: kind(replace(settings.model, deployment=d), token) for a, d in settings.model.agent_deployments}
        return shared["model"]
    return factory


def volume_mirror(settings, env=None):
    """The volume copy of the case store, when CASEPATH_VOLUME names one (a Databricks App's disk does not survive a restart)."""
    import os

    from ..agents.chat_model import databricks_token_provider
    from .mirror import VolumeMirror

    env = os.environ if env is None else env
    host = env.get("DATABRICKS_HOST", "")
    host = host if host.startswith("https://") else "https://" + host
    return VolumeMirror(settings.data_dir, settings.volume, host, databricks_token_provider(host, env))


def volume_files(settings, env=None):
    """The volume's files, for importing case files placed in its ``incoming`` folder."""
    import os

    from ..agents.chat_model import databricks_token_provider
    from .volume import VolumeClient

    env = os.environ if env is None else env
    host = env.get("DATABRICKS_HOST", "")
    host = host if host.startswith("https://") else "https://" + host
    return VolumeClient(host, databricks_token_provider(host, env))


def create_app(settings=None, *, model_factory=None, store=None, catalogue=None, mirror=None, files=None):
    settings = settings or load_settings()
    if files is None and settings.volume:
        files = volume_files(settings)
    if mirror is None and settings.volume and store is None:
        mirror = volume_mirror(settings)
    if mirror is not None:
        mirror.restore()  # before the store opens its database
    store = store or CaseStore(settings.data_dir)
    catalogue = catalogue or workflows.Catalogue.load(settings.catalogue_dir)
    kb.seed(store, {w["id"] for w in catalogue.workflows})
    runs = RunService(store, catalogue, model_factory or default_model_factory(settings), max_workers=settings.run_workers,
                      reading_workers=settings.reading_workers, page_image_side=settings.page_image_side,
                      token_budget=settings.run_token_budget, speed_trials=settings.speed_trials,
                      voice={"organisation": settings.organisation, "writing": settings.writing_language},
                      auto_update=settings.auto_update, auto_update_max_pages=settings.auto_update_max_pages,
                      update_token_budget=settings.update_token_budget, model_as_user=bool(settings.model and settings.model.auth == "user"))

    @asynccontextmanager
    async def lifespan(_):
        if mirror is not None:
            mirror.start()
        yield
        runs.shutdown()
        if mirror is not None:
            mirror.stop()
        store.close()

    app = FastAPI(title="CasePath (internal)", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.store, app.state.catalogue, app.state.runs = store, catalogue, runs

    def user(request: Request):
        if settings.identity_header:
            try:
                who = identity.from_header(request.headers.get(settings.identity_header), fmt=settings.identity_format,
                                           user_claim=settings.identity_user_claim, roles_claim=settings.identity_roles_claim)
            except identity.IdentityError:
                raise HTTPException(401, "Sign-in required.") from None
            if settings.required_role and settings.required_role not in who.roles:
                raise HTTPException(403, "This workspace needs an access role you do not have.")
            if settings.allowed_users and who.user.lower() not in settings.allowed_users:
                raise HTTPException(403, "This CasePath pilot is open to its named pilot group only.")
            return who.user
        if settings.dev_user:
            return settings.dev_user
        raise HTTPException(503, "Sign-in is not configured for this deployment.")

    def found(call, *args):
        try:
            return call(*args)
        except NotFound:
            raise HTTPException(404, "Not found.") from None

    parity_sha = source_tree()[0]
    # The Auswertung's pseudonyms: a salt kept inside Mobiliar, or a random one per start (unlinkable, not stable).
    auswertung_salt = os.environ.get("CASEPATH_SCORECARD_SALT") or secrets.token_hex(16)

    def record(case_id, who, kind, item_id=None, **fields):
        """One event in the case's append-only log (casepath.study.event/1). Outside a study session the session fields stay empty."""
        completed = store.latest_run(case_id, "completed")
        return store.append_case_event(case_id, {"schema": "casepath.study.event/1", "session_id": None, "expert": who, "case_copy": case_id,
                                            "source_case": None, "frozen_run_id": (completed or {}).get("id"), "kind": kind,
                                            "parity_sha": parity_sha, "item_id": item_id, **fields})

    def state(case_id, study=None):
        """The case's state (runner.case_state); ``study`` True: by the account rules of the frozen expert study."""
        found(store.get_case, case_id)
        return case_state(store, catalogue, case_id, study=study)

    # The jurists' review of the legal content (process/review.py): the elements are built once from the data files the
    # catalogue composed, the marks are read from the store on each request
    review_cache = {}

    def review_model():
        if "model" not in review_cache:
            review_cache["model"] = reviews.Model.load(catalogue, settings.catalogue_dir)
        return review_cache["model"]

    def review_marks():
        """The marks that hold for the content as it is now, by element; empty (and nothing built) without any mark."""
        latest = store.latest_reviews()
        return (review_model().current(latest), latest) if latest else ({}, {})

    def may_review(who):
        return not settings.reviewers or str(who).lower() in settings.reviewers

    def area_review(process, latest):
        """The handler's line on the area's review: «aus dem Gesetz abgeleitet, noch nicht freigegeben», «in Prüfung
        (n von m geprüft)» or «freigegeben am … · <reviewer>»."""
        own = (process or {}).get("area")
        if not own:
            return None
        status = review_model().area_label(process["id"], latest) if latest else None
        return {"state": (status or {}).get("state", "offen"), "label": (status or {}).get("label") or own.get("label"),
                "title": process.get("short_title") or own.get("short_title")}

    @app.get("/api/health")
    def health():
        return {"status": "ok", "model_configured": settings.model is not None, "workflows": len(catalogue.workflows),
                "imports": files is not None, "uploads": uploads,
                "pdf_text": "pypdf" if importlib.util.find_spec("pypdf") else "builtin",
                "scanned_pages": "rendered" if importlib.util.find_spec("pypdfium2") and importlib.util.find_spec("PIL") else "embedded images",
                "sign_in": f"gateway ({settings.identity_format})" if settings.identity_header else "dev" if settings.dev_user else "none"}

    incoming = f"{settings.volume.rstrip('/')}/incoming" if settings.volume else None

    def add_with_attachments(case_id, name, declared, data, who, skipped=None):
        """Add the file to the case; an e-mail's attachments become files of the case too, each noting its e-mail. A file
        whose bytes the case already holds is refused before it is read (Duplicate); an attachment the case already holds
        is skipped before it is read, named in ``skipped`` and remembered on its e-mail (``extraction.same_as``: the files
        that hold it), so the account counts that file as delivered with the e-mail."""
        import mimetypes

        def read(file_name, kind, payload):
            result = extract(file_name, kind, payload)
            if len(result["text"]) > settings.max_text_chars:
                result["text"] = result["text"][:settings.max_text_chars]
                result["note"] = ((result["note"] + " ") if result["note"] else "") + "Only the first part of the text is used."
            return result
        same = store.file_by_sha(case_id, hashlib.sha256(data).hexdigest())
        if same:
            raise Duplicate(same["name"], same["created_at"], same["id"])
        result = read(name, declared, data)
        row = store.add_file(case_id, name, result["media_type"], result["kind"], data, result, who, refuse_same=True)
        added, same_as = [], []
        for attached_name, payload in (attachments(name, declared, data) if result["kind"] == "email" else []):
            if not payload or len(payload) > settings.max_upload_bytes:
                continue
            held = store.file_by_sha(case_id, hashlib.sha256(payload).hexdigest())
            try:
                if held:
                    raise Duplicate(held["name"], held["created_at"], held["id"])
                inner = read(attached_name, mimetypes.guess_type(attached_name)[0] or "application/octet-stream", payload)
                inner["attached_to"] = name
                added.append(store.add_file(case_id, attached_name, inner["media_type"], inner["kind"], payload, inner, who, refuse_same=True)["id"])
            except Duplicate as kept:
                same_as.append(kept.file_id)
                if skipped is not None:
                    skipped.append({"name": attached_name, "same_as": kept.file_id, "in_case": kept.name, "at": kept.created_at, "attachment": name})
        if same_as:
            row = store.update_extraction(row["id"], {**store.get_file(row["id"], True)["extraction"], "same_as": list(dict.fromkeys(same_as))})
        return {**row, "attachments": added} if added else row

    def already(skipped):
        """«Bereits in der Akte: «Antwort.eml» vom 05.09.2026»: a file the case holds, by the name it has there and the day it
        came (Swiss time)."""
        when = str(skipped.get("at") or "")
        try:
            from zoneinfo import ZoneInfo
            when = datetime.fromisoformat(when).astimezone(ZoneInfo("Europe/Zurich")).date().isoformat()
        except Exception:  # noqa: BLE001  without the time zone data: the stored day
            when = when[:10]
        return f"Bereits in der Akte: «{skipped.get('in_case') or skipped.get('name')}» vom {account.day(when) or when}"
    uploads_from_bytes = True  # loose PDFs are read by pypdf where installed, else by CasePath's own reader (pdfread)

    summaries = {}

    def prepared_summary(path):
        """Title, files and pages of a prepared case, from its case.json (read once per folder)."""
        if path not in summaries:
            try:
                manifest = json.loads(files.get(f"{path}/case.json") or b"{}")
            except ValueError:
                manifest = {}
            rows = manifest.get("files") or []
            # the name as uploaded: the folder's own name is made safe for storage (an umlaut becomes «-») and never shown
            uploaded = manifest.get("source_name")
            summaries[path] = {"title": manifest.get("title"), "files": len(rows) or None, **({"name": uploaded} if uploaded else {}),
                               "pages": sum(int((r.get("extraction") or {}).get("pages") or 0) for r in rows) or None}
        return summaries[path]

    @app.get("/api/imports")
    def list_imports(who=Depends(user)):
        """Case files placed in the volume's incoming folder (and one level of subfolders), and which are imported."""
        if files is None:
            raise HTTPException(404, "No volume is configured for imports.")
        entries, prepared = [], []
        for entry in files.list(incoming):
            if not entry.get("is_directory"):
                entries.append(entry)
                continue
            inner = files.list(entry["path"])
            if any(e["path"].endswith("/case.json") for e in inner):
                prepared.append(entry)  # a prepared case: one folder, one case
            else:
                entries += [e for e in inner if not e.get("is_directory")]
        imported = {((c.get("intake") or {}).get("import_path") or "").rstrip("/"): c["id"] for c in store.list_cases()}
        rows = [{"path": e["path"], "name": e["path"].rsplit("/", 1)[-1], "size": e.get("file_size"), "prepared": False}
                for e in entries if Path(e["path"]).suffix.lower() in IMPORTABLE and uploads_from_bytes]
        rows += [{"path": e["path"].rstrip("/"), "name": e["path"].rstrip("/").rsplit("/", 1)[-1], "size": None, "prepared": True,
                  **prepared_summary(e["path"].rstrip("/"))} for e in prepared]
        return {"folder": incoming, "files": [{**r, "case": imported.get(r["path"])} for r in sorted(rows, key=lambda r: r["path"])]}

    @app.post("/api/imports", status_code=201)
    async def import_file(body: ImportRequest, who=Depends(user)):
        """One case per file: a dossier placed in the volume becomes a case without passing through the browser."""
        import mimetypes

        if files is None:
            raise HTTPException(404, "No volume is configured for imports.")
        if not body.path.startswith(incoming + "/") or "/../" in body.path:
            raise HTTPException(422, "Only case files in the volume's incoming folder can be imported.")
        if any(((c.get("intake") or {}).get("import_path") or "").rstrip("/") == body.path.rstrip("/") for c in store.list_cases()):
            raise HTTPException(409, "This file is already imported.")
        if Path(body.path).suffix.lower() not in IMPORTABLE:  # a prepared case folder: no PDF library needed here
            from ..read.prepare import PreparedError, load_prepared

            def read(relative):
                data = files.get(f"{body.path}/{relative}")
                if data is None:
                    raise HTTPException(404, f"The prepared case has no {relative}.")
                return data
            try:
                case = await run_in_threadpool(load_prepared, store, read, who, title=body.title, intake={"import_path": body.path})
            except PreparedError as error:
                raise HTTPException(422, str(error)) from None
            if body.workflow_id:
                workflow = catalogue.get(body.workflow_id)
                if workflow:
                    store.select_workflow(case["id"], workflow["id"], workflow["version"], who)
            return {"case": store.get_case(case["id"]), "file": None}
        if not uploads_from_bytes:
            raise HTTPException(422, "This runtime reads prepared cases only; prepare the file first.")
        data = await run_in_threadpool(files.get, body.path)
        if data is None:
            raise HTTPException(404, "Not found.")
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, f"Files up to {settings.max_upload_bytes // (1024 * 1024)} MB are accepted.")
        name = body.path.rsplit("/", 1)[-1]
        case = store.create_case((body.title or Path(name).stem).strip()[:300], {"source": "volume", "import_path": body.path}, who)
        if body.workflow_id:
            workflow = catalogue.get(body.workflow_id)
            if workflow is None:
                raise HTTPException(404, "No such workflow.")
            store.select_workflow(case["id"], workflow["id"], workflow["version"], who)
        skipped = []  # an attachment whose bytes the case already holds (the e-mail itself, an earlier attachment): skipped
        try:
            added = await run_in_threadpool(add_with_attachments, case["id"], name, mimetypes.guess_type(name)[0] or "application/octet-stream",
                                            data, who, skipped)
        except Duplicate as same:  # the target case holds these bytes: refused
            raise HTTPException(409, already({"name": name, "in_case": same.name, "at": same.created_at})) from None
        return {"case": store.get_case(case["id"]), "file": added, "skipped": skipped}

    @app.get("/api/me")
    def me(who=Depends(user)):
        # may_review: the person may mark the legal content and sees «Verwaltung» (Wissen, Auswertung)
        return {"user": who, "may_review": may_review(who)}

    @app.get("/api/workflows")
    def list_workflows(who=Depends(user)):
        return {"workflows": [{**workflows.ref(w), "short_title": w.get("short_title") or w["title"], "area": w.get("area"), "sources": w["sources"], "steps": len(w["steps"]),
                               "documents": len(w["documents"]), "open_questions": len(w.get("open_questions", [])),
                               **({"supersedes": w["supersedes"]} if w.get("supersedes") else {}), **({"example": True} if w.get("example") else {})}
                              for w in catalogue.latest()]}

    @app.get("/api/workflows/{workflow_id}")
    def get_workflow(workflow_id: str, version: str | None = None, who=Depends(user)):
        workflow = catalogue.get(workflow_id, version)
        if workflow is None:
            raise HTTPException(404, "Not found.")
        return workflow

    def prepared_action(current, listed, events):
        """The next action as every screen shows it: the evaluation's, or the one the handler picked instead («andere
        Handlung»), which governs the draft, the date and the case list alike. (action item, options, forms)."""
        action = next((i for i in listed if i["kind"] == "next_action"), None)
        forms = ((catalogue.get((current.get("workflow") or {}).get("id") or "") or {}).get("forms")
                 or (catalogue.get("mietmangel-handler") or {}).get("forms") or letters.SEED_FORMS)  # Protekta's forms for any workflow
        options = letters.action_options(current.get("process") or {}, current.get("evaluation"), forms) if current.get("process") else []
        picked = letters.chosen_action(events)
        if action and picked and picked != action.get("action"):  # "andere Handlung": the handler's pick governs the draft and the date
            option = next((o for o in options if o["kind"] == picked),
                          {"title": kind_title(current.get("process"), picked), "next_in_days": action.get("next_in_days")})
            action.update(action=picked, value=option["title"], label={"de": option["title"], "en": option["title"]},
                          next_in_days=option["next_in_days"], chosen_by_handler=True)
            for k in ("reason", "deadline", "urgency", "template", "then", "settlement", "incoming"):
                action.pop(k, None)  # what led to the prepared action does not lead to the one picked instead
        return action, options, forms

    def _list_run_inputs(row):
        """A row of the case list and its runs: the run its items are built from (``run``: the latest completed run, also
        when a later run failed, was interrupted or runs, so the row keeps «Als Nächstes», «Fällig» and its new files;
        None when there is none), the case's files, the files that run did not read, and the latest run that was not set
        aside, whose status and kind the status reads (``run_status``, ``run_kind``: a failed or interrupted update is
        «Fehlgeschlagen», a stopped full run «angehalten»)."""
        completed = store.latest_run(row["id"], "completed")
        latest = store.latest_run(row["id"], exclude="discarded")
        case_files = store.list_files(row["id"])
        return {"run": completed, "files": case_files, "new_files": len(core.unread(case_files, completed)) if completed else 0,
                "run_status": (latest or {}).get("status"), "run_kind": (latest or {}).get("kind")}

    def _list_completion(row, current, listed, events, files):
        """Where the prepared letter of a row stands after the decision, for its status (Slice B: completion.state(...));
        None so far."""
        return None

    @app.get("/api/cases")
    def list_cases(who=Depends(user)):
        rows = store.list_cases()
        marks = review_marks()[0]  # the jurists' marks: what is only offered while «in Prüfung»
        for row in rows:  # the next date a case is to be looked at: the list sorts by it
            events = store.list_case_events(row["id"])
            row["closed"] = any(e["kind"] == "case.closed" for e in events)
            runs_in = _list_run_inputs(row)
            completed, case_files = runs_in["run"], runs_in["files"]
            row["new_files"] = runs_in["new_files"]  # the files its last run did not read
            cut_day = listing.as_of(case_files)  # a test cut of a historic file: looked at as of its own day, listed apart
            row["as_of"] = cut_day.isoformat() if cut_day else None
            # a historic file (a cut, or a whole old file uploaded for testing, or as a person placed it): listed apart, never overdue
            row["historic"] = historic_file(case_files, row.get("created_at"), events)
            listed, action, current = [], None, None
            if completed:
                try:
                    current = state(row["id"])
                    listed = build_items(current, (current["run"] or {}).get("result"), store.list_files(row["id"]), events,
                                         None if (row.get("intake") or {}).get("study") else marks)
                    action = prepared_action(current, listed, events)[0]
                    clock = follow_up(action.get("next_in_days") if action else None, store.list_files(row["id"]), store.list_case_events(row["id"]),
                                      since=(action or {}).get("since"), until=(action or {}).get("until"))
                    clock = capped(clock, listed, (current.get("process") or {}).get("deadline_margin_days"), store.list_files(row["id"]))
                    row["follow_up"] = clock and clock["due"]
                    row["next_action"] = action and {"action": action.get("action"), "label": action["label"], "text": listing.next_step(action)}
                    row["display_title"] = listing.display_title(row, listed, area_title(current.get("process")),
                                                                 renamed=any(e["kind"] == "case.renamed" for e in events))
                    row["headline"] = listing.headline(row, listed, area_title(current.get("process")),
                                                       renamed=any(e["kind"] == "case.renamed" for e in events))
                    row["parties"] = listing.parties_line(listed)
                    contact = next((i for i in listed if i["kind"] == "contact"), None)  # the first contact the insurer promises (cover.py)
                    row["first_contact"] = contact and {"due": contact["value"], "late": contact.get("late"), "rule": contact.get("rule")}
                    # One next date per case: the follow-up or a deadline stored in the file, whichever comes first (point 4).
                    deadlines = sorted(i["value"] for i in listed if i["kind"] == "deadline" and i.get("direction") != "ab" and i.get("party") != "gegenpartei"
                                       and not (i.get("account") and i.get("party") not in ("kunde", "versicherer")) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(i.get("value") or "")))
                    # The customer's own statutory deadline that set the follow-up before it is what the list shows.
                    own = own_deadlines(listed, store.list_files(row["id"])) if (clock or {}).get("capped") else []
                    dates = [own[0]["value"]] if own else [d for d in [row["follow_up"], deadlines[0] if deadlines else None] if d]
                    row["next_date"] = min(dates) if dates else None
                    row["next_date_kind"] = None if not dates else "frist" if own or (deadlines and row["next_date"] == deadlines[0]) else "wiedervorlage"
                except Exception:  # noqa: BLE001  a case that cannot be evaluated still lists
                    row["follow_up"] = None
            row.setdefault("display_title", row["title"])
            row["stand"] = listing.stand(closed=row["closed"], run_status=runs_in["run_status"], new_files=row["new_files"], items=listed,
                                         follow_up=row.get("follow_up"), events=events, completed_at=(completed or {}).get("created_at"),
                                         files=case_files, historic=row["historic"], run_kind=runs_in["run_kind"],
                                         completion=_list_completion(row, current, listed, events, case_files))
            row["due"] = listing.due(listed, row.get("follow_up"), case_files, row["historic"], closed=row["stand"]["kind"] == "closed")
        return {"cases": rows}

    def area_title(process):
        """The area's short name a prepared case's title starts with («Darlehen»)."""
        return (process or {}).get("short_title") or (process or {}).get("title")

    @app.put("/api/cases/{case_id}/historic")
    def mark_historic(case_id: str, body: HistoricChoice, who=Depends(user)):
        """«Mehr»: move a case into the historic files or out of them; logged, the latest word governs."""
        found(store.get_case, case_id)
        return record(case_id, who, "case.historic", historic=body.historic)

    @app.post("/api/cases", status_code=201)
    def create_case(body: NewCase, who=Depends(user)):
        title = body.title.strip()
        if not title or len(title) > 300:
            raise HTTPException(422, "A title of up to 300 characters is required.")
        return store.create_case(title, body.intake, who)

    @app.put("/api/cases/{case_id}/title")
    def rename_case(case_id: str, body: CaseTitle, who=Depends(user)):
        title = body.title.strip()
        if not title:
            raise HTTPException(422, "A title of up to 300 characters is required.")
        renamed = found(store.rename_case, case_id, title)
        record(case_id, who, "case.renamed", text=title[:300])  # a person's title stands over the one the case gives itself
        return renamed

    # The case view is built in three parts, each one slice's, merged into the view: what arrived and what changed
    # (_arrival_view), the decision brief (_assessment_view) and where the letter stands after the decision
    # (_completion_view). Each returns only its own keys.
    def _arrival_view(case_id, current, prepared, files, logged, listed, marks):
        """Arrival: the files the last preparation did not read (name and the day they came), whether «Aktualisieren» can
        read them alone, and the draft held back until it has; after an update or a new preparation, what changed against
        the run before, with the new entries of the account. Returns (its keys of the case view, the run whose status the
        case shows, as the case list's)."""
        completed = current["run"]
        study = (current["case"].get("intake") or {}).get("study")
        unread = set(core.unread(files, prepared or completed)) if (prepared or completed) and not study else set()  # a study copy reads nothing
        arrived = [{"id": f["id"], "name": f["name"], "added": f.get("created_at")} for f in files if f["id"] in unread]
        new_files = [f["name"] for f in arrived]
        blocked = core.update_blocked(current["case"], files, prepared)
        update = {"available": blocked is None, "reason": blocked[0] if blocked else None, "text": blocked[1] if blocked else None,
                  "needs_full": bool(blocked) and blocked[0] == "full_needed" and bool(arrived)}
        if arrived and not study:  # why the update did not start by itself, for «Aktualisieren»'s title (runner.auto_update_reason)
            update.update(auto=auto_update_reason(store, case_id, settings.auto_update_max_pages) if settings.auto_update else "aus",
                          max_pages=settings.auto_update_max_pages)
        newest = max((str(f["added"] or "") for f in arrived), default="")
        stale = bool(arrived) and not any(e["kind"] == "letter.unblocked" and str(e.get("at") or "") >= newest for e in logged or ())
        changes = None
        done = store.completed_runs(case_id, 2)
        before_run = (store.get_run(done[0]["builds_on"]) if done and done[0].get("kind") == "update" and done[0].get("builds_on")
                      else done[1] if len(done) == 2 else None)
        if before_run and current.get("workflow") and not (current["case"].get("intake") or {}).get("study"):
            workflow = catalogue.get(current["workflow"]["id"], current["workflow"].get("version")) or catalogue.get(current["workflow"]["id"])
            before_state = core.evaluate(workflow, current.get("knowledge") or [], store.list_edits(case_id), before_run.get("result") or {}, case_id, files=files)
            titles = {f: k["title"] + ("" if f == k["fact"] else " (davor)") for k in (current.get("process") or {}).get("incoming") or ()
                      for f in [k["fact"], *(k.get("earlier") or [])]}  # what came in, by its kind's title
            changes = item_changes(build_items(before_state, before_run.get("result"), files, logged, marks), listed, titles)
            if done[0].get("kind") == "update":  # the account's new entries, one line each, as the Verlauf shows them
                done_update = (done[0].get("result") or {}).get("update") or {}
                added = {str(n) for n in done_update.get("entries") or ()}
                changes["entries"] = [f"{account.day(i.get('date')) or 'ohne Datum'} · {i.get('from_title')} → {i.get('to_title')} · "
                                      f"{(i.get('label') or {}).get('de')}: {i.get('value')}" for i in listed if i["kind"] == "entry" and i["key"] in added]
                # how the reply was matched (C7): what the update's entries closed, refused, left partial, promised or opened
                changes["ledger"] = list((done_update.get("ledger") or {}).get("lines") or [])
                changes["update_summary"] = done_update.get("summary")
                changes["updated_at"] = done[0].get("finished_at")
        # the status the case list shows for it, from the same function and the same inputs: a run set aside (a stopped
        # update, a discarded pause) does not count, so the case shows the run it built on, as the list does
        run_now = store.latest_run(case_id, exclude="discarded")
        return {"new_files": new_files, "arrived": arrived, "update": update, "draft_stale": stale, "changes": changes}, run_now

    def _assessment_view(current, completed, listed, files, events, marks):
        """The decision brief of the prepared action (Slice A: {"assessment": assessment.build(...)}), which the letter and
        the screen read; nothing so far."""
        return {}

    def _completion_view(case_id, current, listed, draft, events, files, assessment=None):
        """Where the prepared letter stands after the decision: approved, dispatched, fulfilled (Slice B: {"completion":
        completion.state(...)}), which the status and the screen read; nothing so far."""
        return {}

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str, who=Depends(user)):
        current = state(case_id)
        completed = current["run"]
        study = (current["case"].get("intake") or {}).get("study")
        logged = None if study else store.list_case_events(case_id)  # a study copy shows its frozen run as it was
        # at the mandate and handling stages the files' text is read too: the summary for the firm, the customer's IBAN and
        # the cost check name the page they come from
        stage = ((current.get("evaluation") or {}).get("current") or {}).get("step")
        texts = store.list_files(case_id, with_text=True) if stage in {"mandat", "abwicklung"} else None
        # the jurists' marks on the legal content (a study copy shows its frozen run as it was, without them)
        marks, latest = ({}, {}) if study else review_marks()
        listed = build_items(current, (completed or {}).get("result"), texts or store.list_files(case_id), logged, marks)  # everything the case's screens and exports assert
        held = reviews.flags(current.get("process"), marks)
        action, options, forms = prepared_action(current, listed, store.list_case_events(case_id))
        clock = follow_up(action.get("next_in_days") if action else None, store.list_files(case_id), store.list_case_events(case_id),
                          since=(action or {}).get("since"), until=(action or {}).get("until"))  # a date the party gave: looked at then
        clock = capped(clock, listed, (current.get("process") or {}).get("deadline_margin_days"), store.list_files(case_id))  # before a statutory deadline
        events, files = store.list_case_events(case_id), store.list_files(case_id)
        assessed = _assessment_view(current, completed, listed, files, events, marks)
        # the next action's letter in Protekta's form, from what the case asserts and what the handler changed
        draft = letters.draft(current, listed, events, clock, files, forms, texts=texts, held=held, assessment=assessed.get("assessment"))
        prepared = store.latest_run(case_id, "completed")
        arrival, run_now = _arrival_view(case_id, current, prepared, files, logged, listed, marks)
        renamed = any(e["kind"] == "case.renamed" for e in events)
        shown_case = {**current["case"], "display_title": listing.display_title(
            current["case"], listed if completed else [], area_title(current.get("process")), renamed=renamed)}
        shown_case["headline"] = listing.headline(shown_case, listed if completed else [], area_title(current.get("process")), renamed=renamed)
        shown_case["parties"] = listing.parties_line(listed) if completed else None
        historic = historic_file(files, current["case"].get("created_at"), events)
        closed = any(e["kind"] == "case.closed" for e in events)
        done = _completion_view(case_id, current, listed, draft, events, files, assessed.get("assessment"))
        status = listing.stand(closed=closed, run_status=(run_now or {}).get("status"), new_files=len(arrival["arrived"]) if prepared else 0,
                               items=listed if (run_now or {}).get("status") == "completed" else [], follow_up=(clock or {}).get("due"),
                               events=events, completed_at=(prepared or {}).get("created_at"), files=files, historic=historic,
                               run_kind=(run_now or {}).get("kind"), completion=done.get("completion"))
        stage = ((current.get("evaluation") or {}).get("current") or {})
        cover_edit = next((e for e in reversed(store.list_edits(case_id)) if e.get("op") == "set_fact" and (e.get("args") or {}).get("fact") == "deckung"), None)
        model = screen.build(listed, draft, events, as_of(files), (current.get("process") or {}).get("urgent"), stage=stage.get("step"),
                             via=stage.get("via"), routing=(completed or {}).get("routing"), since=(prepared or {}).get("finished_at"),
                             decided_by=f"{(cover_edit.get('at') or '')[8:10]}.{(cover_edit.get('at') or '')[5:7]}.{(cover_edit.get('at') or '')[:4]} · {cover_edit.get('by')}"
                             if cover_edit and cover_edit.get("at") else None,
                             assessment=assessed.get("assessment"), completion=done.get("completion")) if completed else None
        if model is not None:
            model["title"] = listing.next_step(action) if action else model["title"]  # the same words as the case list's «Als Nächstes»
            model.update(status=status["text"], status_kind=status["kind"],
                         due=listing.due(listed, (clock or {}).get("due"), files, historic, closed=status["kind"] == "closed"))
        return {"items": listed, "items_sha256": items_sha256(listed), "follow_up": clock, "draft": draft, "action_options": options,
                "screen": model, "status": status, "historic": historic,
                **arrival, **assessed, **done,
                "prepared_run": {k: prepared.get(k) for k in ("id", "kind", "builds_on", "created_at", "finished_at")} if prepared else None,
                # the Verlauf: the report, every document, every entry the handler made and every gesture, in time order
                "verlauf": verlauf.rows(listed, files, events if logged is not None else [], store.list_edits(case_id, active_only=False),
                                        current.get("process")),
                "file_note": letters.file_note(current["case"], listed, events, clock, files, package=[(draft["form"], draft["title"])] + [(a["kind"], a["title"]) for a in draft["also"]]
                                               if draft and draft.get("also") else None) if completed else None,
                **{k: current[k] for k in ("run_version", "governing_version") if k in current},
                "case": shown_case, "files": store.list_files(case_id),
                "run": completed if (current["case"].get("intake") or {}).get("study") else store.latest_run(case_id),
                "area_review": area_review(current.get("process"), latest),  # whether a jurist released the area's legal content
                "workflow": current["workflow"], "process": current["process"], "provenance": current.get("provenance"),
                "evaluation": current["evaluation"], "edits": store.list_edits(case_id, active_only=False),
                "feedback": store.list_feedback(completed["id"]) if completed else []}

    def frozen_of(case_id):
        return next((e for e in reversed(store.list_case_events(case_id)) if e["kind"] == "study.frozen"), None)

    def study_mismatch(case_id, expected):
        """Why a study copy must not start, or None: its item list or workflow version differs from the frozen run's. The
        item list is built by the study's frozen account rules, for a copy and for the case it was copied from alike."""
        current = state(case_id, study=True)
        if not current["run"] or current["run"]["id"] != expected["frozen_run_id"]:
            return "Der eingefrorene Lauf fehlt."
        if (current.get("workflow") or {}).get("version") != expected["workflow_version"]:
            return "Die Prozessversion weicht vom eingefrorenen Lauf ab."
        if items_sha256(build_items(current, current["run"].get("result"), store.list_files(case_id))) != expected["items_sha256"]:
            return "Die Punkteliste weicht vom eingefrorenen Lauf ab."
        if sorted(settings.speed_trials) != sorted(expected.get("speed_trials") or []):
            return "Die Geschwindigkeitsversuche dieser Bereitstellung weichen vom eingefrorenen Stand ab."
        return None

    @app.post("/api/cases/{case_id}/freeze", status_code=201)
    def freeze(case_id: str, who=Depends(user)):
        """Fix the case's latest completed run for a study: every expert's copy will show exactly this run."""
        current = state(case_id, study=True)  # its item list by the study's frozen account rules, as the copies build theirs
        if not current["run"] or (current["case"].get("intake") or {}).get("study"):
            raise HTTPException(409, "Nur ein vorbereiteter Fall (keine Studienkopie) kann eingefroren werden.")
        listed = build_items(current, current["run"].get("result"), store.list_files(case_id))
        return record(case_id, who, "study.frozen", frozen_run_id=current["run"]["id"], items_sha256=items_sha256(listed),
                      workflow_version=(current.get("workflow") or {}).get("version"), speed_trials=sorted(settings.speed_trials))

    @app.post("/api/cases/{case_id}/study-copy", status_code=201)
    def study_copy(case_id: str, body: StudyCopyRequest, who=Depends(user)):
        """One expert's own copy of a frozen case: the same files, the frozen run, no run of its own."""
        frozen = frozen_of(case_id)
        if frozen is None:
            raise HTTPException(409, "Der Fall ist nicht eingefroren.")
        expected = {k: frozen.get(k) for k in ("frozen_run_id", "items_sha256", "workflow_version", "speed_trials")}
        if reason := study_mismatch(case_id, expected):
            raise HTTPException(409, reason)
        source = state(case_id)["case"]
        copy = store.create_case(f"{source['title']} · Studie {body.expert}"[:300],
                                 {**(source.get("intake") or {}), "study": {"source_case": case_id, "expert": body.expert, **expected,
                                                                                 "opened": source.get("created_at")}}, who)  # its first contact counts as the source's
        for f in store.list_files(case_id, with_text=True):
            data, row = store.file_bytes(f["id"])
            store.add_file(copy["id"], row["name"], row["media_type"], row["kind"], data, f["extraction"], who)
        record(case_id, who, "study.copied", copy=copy["id"], expert=body.expert)
        return copy

    @app.get("/api/study/plan")
    def study_plan(expert: str = Query(..., pattern=r"^[A-Za-z0-9_-]{1,40}$"), position: int = Query(..., ge=0, le=20), who=Depends(user)):
        """One expert's session: the practice case, then the frozen study cases in an order rotated by the expert's position,
        the own answer first on the first of them (FEEDBACK_DESIGN, review point 5). Built, not used until the study opens."""
        practice = os.environ.get("CASEPATH_STUDY_PRACTICE_CASE")
        frozen = [c["id"] for c in store.list_cases() if not (c.get("intake") or {}).get("study") and frozen_of(c["id"])]
        order = frozen[position % len(frozen):] + frozen[:position % len(frozen)] if frozen else []
        steps = ([{"case": practice, "kind": "practice"}] if practice else []) + [
            {"case": cid, "kind": "study", "own_answer_first": i == 0} for i, cid in enumerate(order)]
        return {"expert": expert, "position": position, "steps": steps, "ready": bool(practice) and len(order) == 3}

    @app.get("/api/cases/{case_id}/study-check")
    def study_check(case_id: str, who=Depends(user)):
        """A session starts only if this is still true; the screen refuses to start otherwise."""
        study = (found(store.get_case, case_id).get("intake") or {}).get("study")
        if not study:
            return {"ok": True, "study": False}
        reason = study_mismatch(case_id, study)
        return {"ok": reason is None, "study": True, "reason": reason}

    @app.delete("/api/cases/{case_id}")
    def delete_case(case_id: str, who=Depends(user)):
        try:
            return {"deleted": case_id, **store.delete_case(case_id, who)}
        except NotFound:
            raise HTTPException(404, "Not found.") from None
        except Conflict as error:
            raise HTTPException(409, str(error)) from None

    @app.post("/api/cases/{case_id}/cut", status_code=201)
    def cut_case(case_id: str, body: CutRequest, who=Depends(user)):
        """'Stand am': a new case holding only the chosen pages of the case's PDF, read text carried over, nothing read again."""
        source = found(store.get_case, case_id)
        pdfs = [f for f in store.list_files(case_id, with_text=True) if f["kind"] == "pdf" and body.file in (None, f["id"])]
        if len(pdfs) != 1:
            raise HTTPException(422, "Name the one PDF to cut.")
        row = pdfs[0]
        data, _ = store.file_bytes(row["id"])
        try:
            keep = cut.parse_pages(body.pages, int(row["extraction"].get("pages") or 0))
            data = cut.extract_pdf(data, keep)  # a new PDF: the later pages are not in it at all
        except (ValueError, PdfError) as error:
            raise HTTPException(422, str(error)) from None
        stand = f" · Stand am {body.as_of[8:10]}.{body.as_of[5:7]}.{body.as_of[:4]}" if body.as_of else ""
        case = store.create_case(f"{source['title']} · Auszug S. {body.pages.replace(' ', '')}{stand}"[:300], source["intake"], who)
        store.add_file(case["id"], row["name"], row["media_type"], row["kind"], data,
                       {**cut.cut_extraction(row["extraction"], keep), "cut_of": {"case": case_id, "file": row["id"], "as_of": body.as_of}}, who)
        return case

    @app.post("/api/cases/{case_id}/action", status_code=201)
    def choose_action(case_id: str, body: ActionChoice, who=Depends(user)):
        """'Andere Handlung': the handler picks another action kind with a one-tap reason; the draft and the date follow."""
        current = state(case_id)
        options = letters.action_options(current.get("process") or {}, current.get("evaluation"),
                                         (catalogue.get((current.get("workflow") or {}).get("id") or "") or {}).get("forms") or letters.SEED_FORMS)
        if body.kind not in {o["kind"] for o in options}:
            raise HTTPException(422, "Diese Handlung gehört nicht zur aktuellen oder einer benachbarten Stufe.")
        return record(case_id, who, "item.corrected", item_id="next_action:0", chosen=body.kind, reason=body.reason_code)

    @app.post("/api/cases/{case_id}/events", status_code=201)
    def add_event(case_id: str, body: EventRequest, who=Depends(user)):
        """A gesture the browser saw (exposure, a source opened, a note, the letter copied, the case closed)."""
        found(store.get_case, case_id)
        if body.kind not in EVENT_KINDS or body.kind in SERVER_KINDS:
            raise HTTPException(422, "Unknown event kind, or one only the server writes.")
        study = (store.get_case(case_id).get("intake") or {}).get("study")
        if body.kind == "session.started" and study and not os.environ.get("CASEPATH_SCORECARD_SALT"):
            raise HTTPException(409, "Eine Studiensitzung braucht ein festes Pseudonym-Salz (CASEPATH_SCORECARD_SALT).")
        if body.kind == "session.started" and study and (reason := study_mismatch(case_id, study)):
            raise HTTPException(409, reason)  # a session starts only on the frozen run's exact item list
        if body.fields.get("reason") is not None and str(body.fields["reason"]) not in REASONS:
            raise HTTPException(422, "Unknown reason.")
        if body.item_id and body.item_id.split(":")[0] not in ITEM_KINDS | SCREEN_KINDS:  # every kind the item list holds (items.py)
            raise HTTPException(422, "Unknown item kind.")
        if len(json.dumps(body.fields, ensure_ascii=False)) > 8000:
            raise HTTPException(422, "Too much in one event.")
        reserved = {"schema", "event_id", "seq", "at", "session_id", "expert", "case_copy", "source_case", "frozen_run_id", "kind", "parity_sha", "item_id"}
        return record(case_id, who, body.kind, item_id=body.item_id, **{k: v for k, v in body.fields.items() if k not in reserved})

    @app.post("/api/cases/{case_id}/own-answer", status_code=201)
    def own_answer(case_id: str, body: OwnAnswer, who=Depends(user)):
        """The own answer before CasePath's result: stored, hashed and frozen with the reveal, once per person and case."""
        found(store.get_case, case_id)
        answer = {"step": body.step, "documents": sorted(set(body.documents)), "documents_free_text_present": bool(body.documents_other.strip()),
                  "action_kind": body.action_kind, "action_free_text_present": bool(body.action_other.strip())}
        digest = hashlib.sha256(json.dumps({**answer, "documents_other": body.documents_other.strip(), "action_other": body.action_other.strip()},
                                           ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        completed = store.latest_run(case_id, "completed")
        base = {"schema": "casepath.study.event/1", "session_id": None, "expert": who, "case_copy": case_id, "source_case": None,
                "frozen_run_id": (completed or {}).get("id"), "parity_sha": parity_sha, "item_id": None}
        written = store.append_case_events(case_id, [
            {**base, "kind": "unaided.saved", **answer, **({"documents_other": body.documents_other.strip()} if body.documents_other.strip() else {}),
             **({"action_other": body.action_other.strip()} if body.action_other.strip() else {})},
            {**base, "kind": "unaided.frozen", "answer_sha256": digest},
            {**base, "kind": "reveal"}], unless=lambda events: any(e["kind"] == "reveal" and e["expert"] == who for e in events))
        if written is None:
            raise HTTPException(409, "Your own answer for this case is already saved and frozen.")
        return {"events": written}

    @app.get("/api/cases/{case_id}/events")
    def list_events(case_id: str, who=Depends(user)):
        found(store.get_case, case_id)
        return {"events": store.list_case_events(case_id), "reasons": REASONS}

    @app.put("/api/cases/{case_id}/workflow")
    def choose_workflow(case_id: str, body: WorkflowChoice, who=Depends(user)):
        workflow = catalogue.get(body.workflow_id, body.version)
        if workflow is None:
            raise HTTPException(404, "No such workflow.")
        return found(store.select_workflow, case_id, workflow["id"], workflow["version"], who)

    uploads = bool(importlib.util.find_spec("python_multipart") or importlib.util.find_spec("multipart"))

    async def upload(case_id: str, request: Request, files: list[UploadFile] | None = File(None), file: UploadFile | None = File(None),
                     who=Depends(user)):
        """Files into a case as one deliberate import (``files``; ``file`` from older clients): each is stored, an e-mail's
        attachments as files of their own. A file the case already holds is refused before it is read and named in
        «skipped» (409 when every file is one), an attachment the case holds is skipped and remembered on its e-mail. Where
        the deployment starts updates by itself (CASEPATH_AUTO_UPDATE), a prepared case then gets one bounded update of
        what came in; «auto» says so («gestartet») or why not («aus», «zu_gross», «lauf_aktiv», or why «Aktualisieren» is
        blocked). A file into a closed case reopens it. An older client's one ``file`` gets its row, these keys added."""
        found(store.get_case, case_id)
        received = []
        for given in list(files or []) + ([file] if file is not None else []):
            data = await given.read(settings.max_upload_bytes + 1)
            if len(data) > settings.max_upload_bytes:
                raise HTTPException(413, f"Files up to {settings.max_upload_bytes // (1024 * 1024)} MB are accepted.")
            if data:
                received.append((Path(given.filename or "file").name[:255], given.content_type, data))
        if not received:
            raise HTTPException(422, "The file is empty.")
        rows, skipped = [], []
        for name, declared, data in received:  # a large PDF must not block the server
            try:
                rows.append(await run_in_threadpool(add_with_attachments, case_id, name, declared, data, who, skipped))
            except Duplicate as same:
                skipped.append({"name": name, "same_as": same.file_id, "in_case": same.name, "at": same.created_at})
        if not rows:
            raise HTTPException(409, "; ".join(already(s) for s in skipped))
        closing = next((e["kind"] for e in reversed(store.list_case_events(case_id)) if e["kind"] in ("case.closed", "case.reopened")), None)
        if closing == "case.closed":  # what arrives after closing reopens the case (its letter, its date, its status follow)
            record(case_id, who, "case.reopened", file=rows[0]["id"], files=[r["id"] for r in rows])
        run, auto = None, "aus"
        if settings.auto_update:
            auto = auto_update_reason(store, case_id, settings.auto_update_max_pages) or "gestartet"
            if auto == "gestartet":
                try:  # the files it reads are admitted now, within the cap: a file coming later waits for the next update
                    run = runs.update(case_id, who, model_token(request), auto=True, budget=settings.update_token_budget,
                                      max_pages=settings.auto_update_max_pages)
                except HTTPException:  # the model is called as the person, who must sign in again: «Aktualisieren» stays
                    auto = "anmelden"
                except TooLarge:  # another upload added pages a moment before
                    auto = "zu_gross"
                except Conflict:  # another upload started one a moment before
                    auto = "lauf_aktiv"
                else:
                    record(case_id, who, "update.started", auto=True, run=run["id"])
        out = {"files": rows, "skipped": skipped, "run": run, "auto": auto}
        return {**rows[0], **out} if file is not None and not files else out

    async def create_from_files(request: Request, files: list[UploadFile] = File(...), who=Depends(user)):
        """A new case from its files in one gesture: named from the first e-mail's subject or the first file's name,
        and its preparation started at once; a file given twice is kept once («skipped»)."""
        received = []
        for file in files:
            data = await file.read(settings.max_upload_bytes + 1)
            if len(data) > settings.max_upload_bytes:
                raise HTTPException(413, f"Files up to {settings.max_upload_bytes // (1024 * 1024)} MB are accepted.")
            if data:
                received.append((Path(file.filename or "file").name[:255], file.content_type, data))
        if not received:
            raise HTTPException(422, "The files are empty.")
        case = store.create_case(Path(received[0][0]).stem[:300] or "Neuer Fall", {"source": "upload"}, who)
        rows, skipped = [], []
        for name, declared, data in received:
            try:
                rows.append(await run_in_threadpool(add_with_attachments, case["id"], name, declared, data, who, skipped))
            except Duplicate as same:
                skipped.append({"name": name, "same_as": same.file_id, "in_case": same.name, "at": same.created_at})
        mails = [r for r in rows if r.get("kind") == "email"]
        subject = _headers(store.get_file(mails[0]["id"], True)["extraction"].get("text", "")).get("Subject", "").strip() if mails else ""
        if subject:
            case = store.rename_case(case["id"], re.sub(r"^((AW|WG|RE|FW|Fwd?)\s*:\s*)+", "", subject, flags=re.I)[:300] or subject[:300])
        try:
            run = runs.start(case["id"], who, model_token(request))
        except Conflict:
            run = None
        return {"case": store.get_case(case["id"]), "files": rows, "skipped": skipped, "run": run}

    if uploads:  # a runtime without the form parser serves prepared cases only (imported from the volume)
        app.post("/api/cases/{case_id}/files", status_code=201)(upload)
        app.post("/api/cases/from-files", status_code=201)(create_from_files)

    @app.get("/api/files/{file_id}/original")
    def original(file_id: str, pages: str | None = None, who=Depends(user)):
        data, row = found(store.file_bytes, file_id)
        pdf = row["media_type"] == "application/pdf"
        total = int(row["extraction"].get("pages") or 0) if pdf else 0
        if pdf and pages:
            try:
                keep = cut.parse_pages(pages, total)
                kept = row["extraction"].get("kept_pages")  # a cut keeps the original numbers; its PDF holds those pages only
                if kept:
                    if not set(keep) <= set(kept):
                        raise ValueError("these pages are not in this file")
                    keep = [kept.index(p) + 1 for p in keep]
                data = cut.extract_pdf(data, keep)
            except (ValueError, PdfError) as error:
                raise HTTPException(422, str(error))
        elif pdf and total > 1 and len(data) > SERVED_WHOLE_BYTES:
            # The Apps proxy returns an error page for a response of about 18 MB or more: offer the file in parts.
            shown = row["extraction"].get("kept_pages") or list(range(1, total + 1))
            step = max(1, int(SERVED_WHOLE_BYTES * 0.5 * total / len(data)))
            parts = [shown[i:i + step] for i in range(0, len(shown), step)]
            links = "".join(f'<li><a href="?pages={p[0]}-{p[-1]}">Seiten {p[0]}–{p[-1]}</a></li>' for p in parts)
            name = html.escape(row["name"])
            return HTMLResponse(f'<!doctype html><meta charset="utf-8"><title>{name}</title><body style="font:15px system-ui;margin:24px">'
                                f"<h1 style=\"font-size:18px\">{name}</h1><p>Die Datei ist zu gross, um sie hier als Ganzes zu öffnen "
                                f"({len(data) // 1048576} MB). Öffnen Sie die Seiten in Teilen:</p><ul>{links}</ul></body>",
                                headers={"Cache-Control": "private, no-store"})
        return Response(data, media_type=row["media_type"],
                        headers={"Content-Disposition": f"inline; filename*=UTF-8''{quote(row['name'], safe='')}",
                                 "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})

    @app.get("/api/files/{file_id}/text")
    def file_text(file_id: str, who=Depends(user)):
        row = found(store.get_file, file_id, True)
        return {"id": row["id"], "name": row["name"], "text": row["extraction"].get("text", ""), "note": row["extraction"].get("note")}

    @app.get("/api/files/{file_id}/pages")
    def file_pages(file_id: str, who=Depends(user)):
        row = found(store.get_file, file_id, True)
        evidence = Evidence([{"id": row["id"], "name": row["name"], "kind": row["kind"], **row["extraction"]}])
        # Raw page text keeps the document's lines; quote offsets refer to its normalised form,
        # which the browser rebuilds with the same rules to place each highlight exactly.
        pages = evidence.files[row["id"]]["pages_raw"]
        return {"id": row["id"], "name": row["name"], "kind": row["kind"], "media_type": row["media_type"],
                "note": row["extraction"].get("note"), "pages_transcribed": row["extraction"].get("pages_transcribed") or [],
                "pages_without_text": row["extraction"].get("pages_without_text") or [],
                "unread_reasons": row["extraction"].get("unread_reasons") or {},
                "headers": _headers(row["extraction"].get("text", "")) if row["kind"] == "email" else None,
                "pages": [{"page": page, "text": text} for page, text in pages]}

    def model_token(request):
        """The signed-in person's model token, when the model is called as that person."""
        if settings.model is None or settings.model.auth != "user":
            return None
        token = request.headers.get("x-forwarded-access-token")
        if not token:
            raise HTTPException(401, "Sign in again: CasePath calls the model as you.")
        return token

    @app.post("/api/cases/{case_id}/runs", status_code=202)
    def start_run(case_id: str, request: Request, who=Depends(user)):
        if (found(store.get_case, case_id).get("intake") or {}).get("study"):
            raise HTTPException(409, "Eine Studienkopie wird nicht neu vorbereitet: sie zeigt den eingefrorenen Lauf.")
        try:
            return runs.start(case_id, who, model_token(request))
        except NotFound:
            raise HTTPException(404, "Not found.") from None
        except Conflict as error:
            raise HTTPException(409, str(error)) from None

    @app.post("/api/cases/{case_id}/update", status_code=202)
    def update_case(case_id: str, request: Request, who=Depends(user)):
        """«Aktualisieren»: a run that reads only the files the latest completed run did not read, and builds on it."""
        if (found(store.get_case, case_id).get("intake") or {}).get("study"):
            raise HTTPException(409, "Eine Studienkopie wird nicht aktualisiert: sie zeigt den eingefrorenen Lauf.")
        try:
            return runs.update(case_id, who, model_token(request))
        except Conflict as error:
            raise HTTPException(409, str(error)) from None

    entries_lock = threading.Lock()  # one number per entry, also when two handlers save at once

    def entry_form(case_id, body):
        if (found(store.get_case, case_id).get("intake") or {}).get("study"):
            raise HTTPException(409, "Eine Studienkopie zeigt den eingefrorenen Lauf; Einträge gehören in den Fall selbst.")
        try:
            return account.check_form(body.model_dump())
        except account.FormError as error:
            raise HTTPException(422, str(error)) from None

    def entry_in_force(case_id, n):
        found_edit = next((e for e in store.list_edits(case_id) if e["op"] == "add_entry" and (e.get("args") or {}).get("n") == n), None)
        if found_edit is None:
            raise HTTPException(404, "Kein solcher Eintrag.")
        return found_edit

    def entry_event(form):
        return {"entry_kind": form["kind"], "party": form["party"], "text": form["said"][:2000], "parts": [k for k in ("agreed", "asked", "next") if form[k]]}

    @app.post("/api/cases/{case_id}/entries", status_code=201)
    def add_entry(case_id: str, body: EntryForm, who=Depends(user)):
        """«Notiz hinzufügen»: the handler's own entry of the running account (a call, a conversation, a note, an e-mail
        outside the file). It counts at once, without a model: the account, «Stand», the dates and the next action are
        recomputed from it. Kept as an edit of the case and logged like every handler gesture."""
        form = entry_form(case_id, body)
        with entries_lock:
            n = account.next_handler_number(store.list_edits(case_id, active_only=False))
            edit = store.add_edit(case_id, "add_entry", {**form, "n": n}, who, "Eintrag der Fallbearbeitung")
        record(case_id, who, "entry.added", item_id=f"entry:{n}", edit_id=edit["id"], **entry_event(form))
        return {"entry": account.handler_entry(form, n, by=who, at=edit["at"], edit=edit["id"]), "edit": edit}

    @app.put("/api/cases/{case_id}/entries/{n}")
    def change_entry(case_id: str, n: int, body: EntryForm, who=Depends(user)):
        """A handler's entry changed: the one in force is replaced by a new edit with the same number; logged."""
        form = entry_form(case_id, body)
        with entries_lock:
            current = entry_in_force(case_id, n)
            store.set_edit_status(current["id"], "replaced", who)
            edit = store.add_edit(case_id, "add_entry", {**form, "n": n}, who, "Eintrag der Fallbearbeitung geändert")
        record(case_id, who, "entry.changed", item_id=f"entry:{n}", edit_id=edit["id"], replaces=current["id"], **entry_event(form))
        return {"entry": account.handler_entry(form, n, by=who, at=edit["at"], edit=edit["id"]), "edit": edit}

    @app.delete("/api/cases/{case_id}/entries/{n}")
    def remove_entry(case_id: str, n: int, who=Depends(user)):
        """A handler's entry removed: it no longer counts; the edit stays in the store and the removal is logged."""
        found(store.get_case, case_id)
        with entries_lock:
            current = entry_in_force(case_id, n)
            store.set_edit_status(current["id"], "removed", who)
        args = current.get("args") or {}
        record(case_id, who, "entry.removed", item_id=f"entry:{n}", edit_id=current["id"], entry_kind=args.get("kind"),
               party=args.get("party"), text=str(args.get("said") or "")[:2000])
        return {"removed": n}

    @app.post("/api/runs/{run_id}/discard")
    def discard_run(run_id: str, who=Depends(user)):
        """'Verwerfen': a paused run is set aside (kept in the store and the log, never deleted); the case shows its last
        completed result again, or is not yet prepared."""
        run = found(store.get_run, run_id)
        if run["status"] != "paused":
            raise HTTPException(409, "Nur ein angehaltener Lauf kann verworfen werden.")
        store.update_run(run_id, status="discarded")
        record(run["case_id"], who, "run.discarded", run=run_id)
        return {"id": run_id, "status": "discarded"}

    @app.post("/api/runs/{run_id}/continue", status_code=202)
    def continue_run(run_id: str, request: Request, who=Depends(user)):
        """'Weiter': continue a paused run from what it established; finished steps are not done again."""
        run = found(store.get_run, run_id)
        latest = store.latest_run(run["case_id"])
        if run["status"] != "paused" or (latest and latest["id"] != run_id):
            raise HTTPException(409, "Nur der letzte, angehaltene Lauf kann fortgesetzt werden.")
        return runs.resume(run, who, model_token(request))

    @app.post("/api/runs/{run_id}/stop", status_code=202)
    def stop_run(run_id: str, who=Depends(user)):
        """'Anhalten': the run ends before its next model turn and keeps what is established (status "paused")."""
        run = found(store.get_run, run_id)
        if run["status"] not in ("queued", "running"):
            raise HTTPException(409, "Der Lauf läuft nicht.")
        runs.stop(run_id)
        return {"id": run_id, "stopping": True}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, after: int = 0, who=Depends(user)):
        return found(store.get_run, run_id, after)

    @app.put("/api/runs/{run_id}/feedback")
    def feedback(run_id: str, body: Feedback, who=Depends(user)):
        listed = found(store.set_feedback, run_id, body.target, body.verdict, body.note, who)
        run = store.get_run(run_id)
        target = body.target if ":" in body.target else f"{body.target}:0"
        if body.target.startswith("point:"):
            record(run["case_id"], who, "point.settled" if body.verdict else "correction.undone", item_id=target)
        else:
            kind = {"correct": "item.confirmed", "wrong": "item.corrected", None: "correction.undone"}.get(body.verdict, "item.confirmed")
            record(run["case_id"], who, kind, item_id=target, **({"reason": body.reason_code or "none", "note_present": bool(body.note)} if kind == "item.corrected" else {}))
        return {"feedback": listed}

    def _report_package(case_id, view):
        """The approved package the exports serve once the letter is approved ({title, to, text, by, at}; Slice B fills
        this from its stored bundle); None so far."""
        return None

    @app.get("/api/cases/{case_id}/report.docx")
    def report_docx(case_id: str, lang: str = "de", who=Depends(user)):
        """The case report for the case file: what the last prepared run found, each finding with its source. After an
        update the result checker's fields stand under the full preparation's date; the letter is the one the case shows."""
        from .report import build

        current = state(case_id)
        view = get_case(case_id, who) if current.get("run") else {}
        draft = view.get("draft") or {}
        shown = {"title": draft.get("title"), "to": draft.get("to"), "text": draft.get("text")} if draft.get("text") else None
        data = build(current["case"], current, store.list_files(case_id), lang=lang if lang in ("de", "en") else "de",
                     knowledge=store.list_knowledge(), current=shown, package=_report_package(case_id, view))
        name = "Fallbericht.docx" if lang != "en" else "Case-report.docx"
        return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename={name}", "Cache-Control": "private, no-store"})

    @app.get("/api/runs/{run_id}/draft.docx")
    def draft_docx(run_id: str, who=Depends(user)):
        """The result checker's reply draft of a full preparation; an update inherited it (409)."""
        run = found(store.get_run, run_id)
        reply = ((run.get("result") or {}).get("reply")) or {}
        if not reply.get("clauses"):
            raise HTTPException(404, "This run has no draft.")
        if (run.get("result") or {}).get("stale_since"):
            raise HTTPException(409, "Der Entwurf stammt aus einer früheren Vorbereitung")
        data = _docx(reply.get("subject") or "Entwurf", [c["text"] for c in reply["clauses"]])
        return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": "attachment; filename=Entwurf.docx", "Cache-Control": "private, no-store"})

    # One correction repairs the whole package (C9): what the handler reviews is the difference, not the whole case
    def _package(view):
        """What a correction can change in the prepared package, as the handler reviews it: the step and its letter (form,
        recipient line, text), the documents still asked, what is open in the account, the date it is awaited by, the case
        note, the status in the queue and, with Slice B, the approval."""
        items = view.get("items") or []
        label = lambda i: (i.get("label") or {}).get("de") or str(i.get("key"))
        draft = view.get("draft") or {}
        text = draft.get("text") or ""
        open_ = []
        for i in items:
            if i["kind"] == "stand" and i.get("key") != "kontakt":
                open_ += [f"{label(i)}: {r}" for r in ([x.get("text") for x in i.get("rows") or ()] or ([i["value"]] if i.get("value") else []))]
        done = view.get("completion") or {}
        return {"Schritt": (view.get("screen") or {}).get("title"), "Brief": draft.get("title"),
                "Empfänger": next((line for line in text.splitlines() if line.startswith(("Sehr geehrte", "Guten Tag"))), None),
                "Unterlagen": sorted(label(i) for i in items if i["kind"] == "document" and i.get("status") == "missing" and i.get("ask") == "now"),
                "Offen": open_, "Wiedervorlage": account.day((view.get("follow_up") or {}).get("due")),
                "Status": (view.get("status") or {}).get("text"), "Freigabe": done.get("status") or done.get("state"),
                "text": text, "note": view.get("file_note") or ""}

    def _consequences(before, after):
        """Each part of the package the correction changed, before and after: lists by what left and what came, the
        letter's text and the case note by the paragraphs and sentences that changed."""
        out = []
        for key in ("Schritt", "Brief", "Empfänger", "Unterlagen", "Offen", "Wiedervorlage", "Status", "Freigabe"):
            b, a = before.get(key), after.get(key)
            if b == a:
                continue
            if isinstance(b, list) or isinstance(a, list):
                out.append({"what": key, "before": [x for x in b or () if x not in (a or ())], "after": [x for x in a or () if x not in (b or ())]})
            else:
                out.append({"what": key, "before": b, "after": a})
        for key, what, split in (("text", "Brieftext", "\n\n"), ("note", "Aktennotiz", ". ")):
            b, a = [x.strip() for x in before[key].split(split) if x.strip()], [x.strip() for x in after[key].split(split) if x.strip()]
            if b != a:
                out.append({"what": what, "before": [x for x in b if x not in a][:4], "after": [x for x in a if x not in b][:4]})
        return out

    def _basis(op, args, reason, current, who):
        """Why the package changed, in the handler's words: the correction itself, with its reason and who made it."""
        if op == "set_fact":
            fact = next((f for f in (current.get("process") or {}).get("facts") or () if f["id"] == args.get("fact")), {})
            value = lambda v: "ja" if v is True else "nein" if v is False else "offen" if v in (None, "") else str(v)
            what = f"{fact.get('question') or args.get('fact')}: {value((current.get('facts') or {}).get(args.get('fact')))} → {value(args.get('value'))}"
        elif op == "settle_request":
            row = next((r for r in (current.get("account") or {}).get("requests") or () if r["id"] == args.get("request")), {})
            what = f"«{row.get('what') or args.get('request')}»: " + {"erledigt": "erledigt", "nicht_mehr_noetig": "nicht mehr nötig",
                                                                       "beantwortet": f"beantwortet durch Nr. {args.get('entry')}"}.get(args.get("how"), "")
        elif op == "set_party":
            what = f"{'Kundschaft' if args.get('role') == 'kunde' else 'Gegenpartei'}: {' '.join(x for x in (args.get('salutation'), args.get('name')) if x)}"
        else:
            what = {"add_document": f"Unterlage verlangt: {args.get('title')}", "remove_document": "Unterlage nicht mehr nötig"}.get(op, "Prozess angepasst")
        return f"{what} ({reason}; {who})" if reason else f"{what} ({who})"

    # Editing the case's process
    @app.post("/api/cases/{case_id}/edits", status_code=201)
    def edit_process(case_id: str, body: EditRequest, request: Request, who=Depends(user)):
        before = state(case_id)
        if before["process"] is None:
            raise HTTPException(409, "Choose or route a workflow before editing the process.")
        if not body.reason.strip() and not body.reason_code:
            raise HTTPException(422, "Say why the process changes.")
        reason_text = body.reason.strip() or REASONS[body.reason_code]
        if body.op == "add_entry":
            raise HTTPException(422, "Einträge der Fallbearbeitung über /entries.")
        if body.op == "add_dispatch":  # written only when a dispatch is confirmed (store.dispatch_once, Slice B), never here
            raise HTTPException(422, "Ein Versand wird mit «Versandt am» bestätigt, nicht hier.")
        if (before["case"].get("intake") or {}).get("study") and body.op in ("settle_request", "set_party"):
            raise HTTPException(409, "Eine Studienkopie bleibt, wie sie eingefroren wurde.")
        if body.activate:  # shared Knowledge is activated in «Wissen» only, after a replay of its version (HANDLER_BAR L3)
            raise HTTPException(422, "Freigabe im Wissen erst nach dem Nachspielen")
        try:
            casegraph.check_edit(before["process"], {"op": body.op, "args": body.args})
        except casegraph.Derived as error:  # a fact code computes: said where it follows from (C9)
            raise HTTPException(422, str(error)) from None
        except (casegraph.EditError, workflows.CatalogueError, KeyError, TypeError) as error:
            raise HTTPException(422, f"This change cannot be applied: {error}") from None
        if body.op == "settle_request" and not any(r["id"] == body.args.get("request") and r["answered"] is None
                                                   for r in (before.get("account") or {}).get("requests") or ()):
            raise HTTPException(422, "Diese Anforderung ist nicht mehr offen.")
        package_before = _package(get_case(case_id, who)) if before.get("run") else None
        edit = store.add_edit(case_id, body.op, body.args, who, reason_text)
        learned = None
        # "gilt generell so" (reason 4), or the same correction made in two other cases, becomes a proposal by itself;
        # it is only proposed: a person activates it, after seeing its replayed effect on the stored cases.
        repeated = len({e["case_id"] for e in store.similar_edits(body.op, body.args, case_id)}) >= 2
        if not body.use_for_similar and (body.reason_code == "4" or repeated):
            try:
                item = kb.from_edit(before["workflow"]["id"], edit, before["process"], by=who)
                learned = store.save_knowledge(replayed(item, who, "gilt generell" if body.reason_code == "4" else "wiederholt"))
            except kb.KnowledgeError:
                learned = None  # not every correction can be said in general terms; the case keeps its edit
        if body.use_for_similar:  # a candidate with the replay of its version: activated in «Wissen», never here
            try:
                item = kb.from_edit(before["workflow"]["id"], edit, before["process"], by=who)
            except kb.KnowledgeError as error:
                raise HTTPException(422, str(error)) from None
            learned = store.save_knowledge(replayed(item, who, "für ähnliche Fälle"))
        after = state(case_id)
        change = casegraph.diff(before["evaluation"], after["evaluation"])
        args = body.args
        target = (f"fact:{args['fact']}" if body.op == "set_fact" and args.get("fact") else f"document:{args.get('document')}" if args.get("document")
                  else f"step:{args.get('step')}" if args.get("step") else None)
        values = {"before": before["facts"].get(args.get("fact")), "after": after["facts"].get(args.get("fact"))} if body.op == "set_fact" else {}
        kind = {"remove_document": "item.dismissed", "add_document": "item.added", "add_step": "item.added", "add_question": "item.added",
                "settle_request": "entry.corrected"}.get(body.op, "item.corrected")
        if body.op == "settle_request":
            target, values = f"request:{args.get('request')}", {"request": args.get("request"), "how": args.get("how")}
        what = {"add_document": "document", "add_step": "step", "add_question": "question"}.get(body.op)
        cause = record(case_id, who, kind, item_id=target, edit_id=edit["id"], op=body.op, reason=body.reason_code or "none",
                       note_present=bool(body.reason.strip()), **values, **({"what": what, "free_text_present": True} if what else {}))
        for row in change["documents_added"]:
            record(case_id, who, "item.propagated", item_id=f"document:{row['document']}", caused_by=cause["event_id"], change="appeared", before=None, after=row["status"])
        for row in change["documents_removed"]:
            record(case_id, who, "item.propagated", item_id=f"document:{row['document']}", caused_by=cause["event_id"], change="vanished", before=row["status"], after=None)
        for row in change["documents_changed"]:
            record(case_id, who, "item.propagated", item_id=f"document:{row['document']}", caused_by=cause["event_id"], change="changed",
                   before=f"{row['before']}/{row['required_before']}", after=f"{row['after']}/{row['required_after']}")
        if change["current_step"]["before"] != change["current_step"]["after"] and change["current_step"]["after"]:
            record(case_id, who, "item.propagated", item_id=f"step:{change['current_step']['after']}", caused_by=cause["event_id"], change="changed",
                   before=change["current_step"]["before"], after=change["current_step"]["after"])
        recheck = None
        added = [d["document"] for d in change["documents_added"]]
        if body.recheck and added and before["run"] is not None and not (before["case"].get("intake") or {}).get("study"):  # no model call in a study copy
            try:
                recheck = runs.recheck(case_id, added, who, model_token(request))
            except Conflict:
                recheck = None
        consequences = None
        if package_before is not None:  # the package before and after, with the correction as its basis (C9)
            consequences = {"basis": _basis(body.op, body.args, body.reason.strip() or ("" if body.reason_code in (None, "none") else reason_text), before, who),
                            "changes": _consequences(package_before, _package(get_case(case_id, who)))}
        return {"edit": edit, "diff": change, "knowledge": learned, "recheck": recheck, "evaluation": after["evaluation"], "consequences": consequences}

    def _undo_limits(edit):
        """What undoing a correction cannot undo: a letter copied, approved or dispatched since (it went out, or may have,
        with the corrected state: it stays as it was, to check), and Knowledge proposed from it (retired in «Wissen»)."""
        out, events = [], store.list_case_events(edit["case_id"])
        start = next((e["seq"] for e in events if e.get("edit_id") == edit["id"]), None)  # the correction's own event: after it
        for e in events:
            if (e.get("seq") or 0) <= start if start is not None else str(e.get("at") or "") <= str(edit.get("at") or ""):
                continue
            when = account.day(str(e.get("at") or "")[:10])
            if e["kind"] == "action.dispatched":
                out.append(f"Versandt am {account.day(e.get('date')) or when}: der versandte Brief bleibt, wie er war; prüfen, ob er zu berichtigen ist")
            elif e["kind"] == "letter.copied":
                out.append(f"Brief am {when} kopiert: der kopierte Text bleibt, wie er war; prüfen, ob er so versandt wurde")
            elif e["kind"] == "action.approved":
                out.append(f"Freigabe vom {when}: sie galt dem korrigierten Stand und gilt nicht mehr")
        if any((k.get("origin") or {}).get("edit_id") == edit["id"] and k.get("status") != "retired" for k in store.list_knowledge()):
            out.append("Der Vorschlag im Wissen bleibt; dort zurückziehen")
        return list(dict.fromkeys(out))

    @app.post("/api/edits/{edit_id}/undo")
    def undo(edit_id: str, who=Depends(user)):
        """Undo a correction: everything that follows from the case's state follows back (the package's before and after);
        what already left CasePath cannot be undone and is named (``limits``)."""
        edit = found(store.get_edit, edit_id)
        before = state(edit["case_id"])
        package_before = _package(get_case(edit["case_id"], who)) if before.get("run") else None
        store.set_edit_status(edit_id, "undone", who)
        undoes = next((e["event_id"] for e in reversed(store.list_case_events(edit["case_id"])) if e.get("edit_id") == edit_id), None)
        record(edit["case_id"], who, "correction.undone", undoes=undoes, edit_id=edit_id)
        after = state(edit["case_id"])
        changes = _consequences(package_before, _package(get_case(edit["case_id"], who))) if package_before is not None else None
        return {"edit": store.get_edit(edit_id), "diff": casegraph.diff(before["evaluation"], after["evaluation"]),
                "consequences": {"basis": "Rückgängig gemacht", "changes": changes} if changes is not None else None, "limits": _undo_limits(edit)}

    # Knowledge
    STAGES = {"lesen": {"reader"}, "prozess": {"router", "process_builder"}, "fakten": {"claim_reader"},
              "unterlagen": {"document_finder"}, "pruefung": {"source_checker", "result_checker"}}

    def case_pages(case_id):
        return sum(len((f.get("extraction") or {}).get("kept_pages") or ()) or int((f.get("extraction") or {}).get("pages") or 1)
                   for f in store.list_files(case_id))

    band = lambda pages: "klein" if pages <= 10 else "mittel" if pages <= 30 else "gross"  # case size, in pages read

    @app.get("/api/run-profile")
    def run_profile(pages: int | None = Query(None, ge=0, le=5000), kind: Literal["full", "update"] = "full", who=Depends(user)):
        """Median seconds per stage over this deployment's recent completed runs of cases of the same size (pages);
        all recent runs when there are fewer than three of that size. ``kind``: full preparations or updates, never the
        two mixed; an update's time comes from updates alone, whatever the case's size."""
        trials = sorted(settings.speed_trials)  # a band never mixes runs made with different speed trials
        runs = [r for r in store.recent_runs(60, kind=kind) if not (r.get("result") or {}).get("resumed_from")  # a continued run times only its rest
                and sorted((r.get("result") or {}).get("speed_trials") or []) == trials]
        same = [r for r in runs if pages is not None and kind == "full" and band(case_pages(r["case_id"])) == band(pages)]
        chosen = same if len(same) >= 3 else runs[:30]
        spans = {stage: [] for stage in STAGES}
        for run in chosen:
            events = run.get("events") or []
            for stage, agents in STAGES.items():
                times = [datetime.fromisoformat(e["at"]) for e in events if e.get("agent") in agents and e.get("at")]
                if times:
                    spans[stage].append((max(times) - min(times)).total_seconds())
        median = lambda xs: sorted(xs)[len(xs) // 2] if xs else None
        totals = [(datetime.fromisoformat(r["finished_at"]) - datetime.fromisoformat(r["created_at"])).total_seconds()
                  for r in chosen if r.get("finished_at") and r.get("created_at")]
        return {"runs": len(chosen), "kind": kind, "band": band(pages) if pages is not None and chosen is same else "alle",
                "median_seconds": {s: median(v) for s, v in spans.items()}, "median_total": median(totals)}

    @app.get("/api/manifest")
    def running_manifest(who=Depends(user)):
        """What this running app is: code tree, workflows and Knowledge, each hashed by content."""
        return parity.manifest(settings, knowledge=store.list_knowledge())

    @app.get("/api/auswertung")
    def evaluation_page(who=Depends(user)):
        """Content-free and pseudonymous: counts, ratios and durations from the event log, tied to the manifest."""
        man = parity.manifest(settings, knowledge=store.list_knowledge())
        return auswertung(store, auswertung_salt, hashlib.sha256(json.dumps(man, sort_keys=True).encode()).hexdigest())

    # Decision points (quality/points.py): the insurer's real actions in a case file, labelled inside the insurer, each
    # replayed from the case's stored run as the case stood on its day, without a model; the table is content-free
    # unless detail is asked for.
    from ..quality import points as decision_points

    @app.get("/api/cases/{case_id}/labels-template")
    def labels_template(case_id: str, who=Depends(user)):
        """The file's documents in time order from the stored run, the insurer's own marked, and labels to complete. Inside only."""
        found(store.get_case, case_id)
        try:
            return decision_points.template(store, catalogue, case_id)
        except decision_points.LabelsError as error:
            raise HTTPException(409, str(error)) from None

    @app.post("/api/cases/{case_id}/labels", status_code=201)
    def save_labels(case_id: str, labels: dict, who=Depends(user)):
        """A casepath.labels/1 file for this case, checked against its process and kept in the case store (replaced whole)."""
        found(store.get_case, case_id)
        try:
            return store.save_labels(case_id, decision_points.check_case(store, catalogue, case_id, labels), who)
        except decision_points.LabelsError as error:
            raise HTTPException(422, str(error)) from None

    @app.get("/api/cases/{case_id}/labels")
    def get_labels(case_id: str, who=Depends(user)):
        return found(store.get_labels, case_id)

    @app.get("/api/replay-points")
    def replay_points(detail: bool = False, case: list[str] = Query(default=[]), who=Depends(user)):
        """Every labelled point replayed from its case's stored run: one row per point and the summary table."""
        return decision_points.table(store, catalogue, set(case) or None, detail=detail)

    @app.get("/api/knowledge")
    def list_knowledge(family: str | None = None, status: str | None = None, who=Depends(user)):
        items = store.list_knowledge(family, {status} if status else None)
        return {"knowledge": items, "uses": store.knowledge_uses()}

    @app.get("/api/knowledge/{knowledge_id}")
    def get_knowledge(knowledge_id: str, who=Depends(user)):
        return {"item": found(store.get_knowledge, knowledge_id), "uses": store.knowledge_uses(knowledge_id)}

    def activation(item, who, reason=None):
        """What «Freigeben» makes of an item, the one transformation both the replay and the activation apply: (the items
        it saves, the item it refines as it is now, or None). A plain item becomes active; a refinement is merged into the
        item it refines (a new version of it, keeping that item's status) and is itself retired."""
        if not item.get("refines"):
            return [kb.set_status(item, "active", by=who, reason=reason or "")], None
        target = found(store.get_knowledge, item["refines"])
        merged = kb.refine(target, content=item["content"], applies_when=item["applies_when"], applies_when_text=item["applies_when_text"],
                           by=who, case_id=(item.get("origin") or {}).get("case_id"), reason=reason or "refined from a later case")
        return [merged, kb.set_status(item, "retired", by=who, reason=f"merged into {target['id']} v{merged['version']}")], target

    def replayed(item, who, because=None):
        """The item with the model-free replay of its current version on the stored cases (quality/replay.py): the active
        Knowledge as its activation would leave it (activation: a refinement merged into the item it refines, which it
        replaces), how many cases were replayed and what it changes in each (the changed outputs, before and after), kept on
        the item (``replay.version``; for a refinement also the refined item and the version it was replayed on, so a
        change of either makes the replay stale) and logged (``knowledge.replayed``)."""
        saved, target = activation(item, who)
        rows = replay(store, catalogue, [k for k in saved if k["status"] == "active"])
        changed = [{"case": r["case"], "title": r["title"], "changed": sorted(r["changed"]), "after": {k: v["after"] for k, v in r["changed"].items()}}
                   for r in rows if r["changed"]]
        item = {**item, "replay": {"version": item["version"], "cases": len(rows), "changed": changed, "by": who,
                                   "at": datetime.now().astimezone().isoformat(timespec="seconds"), **({"because": because} if because else {}),
                                   **({"target": target["id"], "target_version": target["version"]} if target else {})}}
        store.append_workspace_event({"schema": "casepath.knowledge.event/1", "kind": "knowledge.replayed", "item": item["id"],
                                      "version": item["version"], "cases": len(rows), "changed": len(changed), "by": who,
                                      **({"target": target["id"], "target_version": target["version"]} if target else {})})
        return item

    @app.post("/api/knowledge/{knowledge_id}/replay")
    def replay_knowledge(knowledge_id: str, who=Depends(user)):
        """«Nachspielen»: the item's current version applied to every prepared case without a model; what it would change
        is kept on the item, and only then can it be activated («Freigeben»)."""
        return store.save_knowledge(replayed(found(store.get_knowledge, knowledge_id), who))

    @app.post("/api/knowledge/{knowledge_id}/activate")
    def activate(knowledge_id: str, body: StatusChange, who=Depends(user)):
        """«Freigeben»: only an item whose replay is of its current version and, for a refinement, of the version of the
        item it refines as it is now; it then applies exactly the transformation the replay applied (activation)."""
        item = found(store.get_knowledge, knowledge_id)
        played = item.get("replay") or {}
        if played.get("version") != item.get("version"):
            raise HTTPException(409, "Zuerst nachspielen: die Wirkung dieser Fassung ist nicht bekannt")
        saved, target = activation(item, who, body.reason)
        if target is not None and (played.get("target"), played.get("target_version")) != (target["id"], target["version"]):
            raise HTTPException(409, "Zuerst nachspielen: der verfeinerte Eintrag hat sich seither geändert")
        for row in saved:
            store.save_knowledge(row)
        return saved[0]

    @app.post("/api/knowledge/{knowledge_id}/retire")
    def retire(knowledge_id: str, body: StatusChange, who=Depends(user)):
        item = found(store.get_knowledge, knowledge_id)
        return store.save_knowledge(kb.set_status(item, "retired", by=who, reason=body.reason))

    # A jurist's review of the legal content: one row per area (and the cover check, the letters with prescribed content)
    @app.get("/api/review")
    def review_overview(who=Depends(user)):
        """The rows of «Rechtsgebiete», each with its state and counts, and whether the signed-in person may mark."""
        latest = store.latest_reviews()
        return {"may_review": may_review(who), "reviewers_named": bool(settings.reviewers), "rows": review_model().overview(latest)}

    @app.get("/api/review/export")
    def review_export(format: Literal["json", "md"] = "json", who=Depends(user)):
        """The requested changes and questions for the developers: element id, mark, comment, suggested wording. No case content."""
        rows = review_model().changes(store.latest_reviews())
        if format == "md":
            return Response(reviews.changes_markdown(rows), media_type="text/markdown; charset=utf-8",
                            headers={"Content-Disposition": "attachment; filename=pruefung-aenderungen.md", "Cache-Control": "no-store"})
        return Response(json.dumps({"format": "casepath.review.changes/1", "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                                    "items": rows}, ensure_ascii=False, indent=1), media_type="application/json",
                        headers={"Content-Disposition": "attachment; filename=pruefung-aenderungen.json", "Cache-Control": "no-store"})

    @app.get("/api/review/{row_id}")
    def review_row(row_id: str, who=Depends(user)):
        """One area (or the cover check, the letters): every element with its content, passages, source and open question."""
        detail = review_model().detail(row_id, store.latest_reviews())
        if detail is None:
            raise HTTPException(404, "Not found.")
        return {**detail, "may_review": may_review(who)}

    @app.get("/api/review/{row_id}/pruefpaket")
    def review_pack(row_id: str, who=Depends(user)):
        """The same content as one plain page, to print."""
        detail = review_model().detail(row_id, store.latest_reviews())
        if detail is None:
            raise HTTPException(404, "Not found.")
        return HTMLResponse(reviews.pruefpaket(detail), headers={"Cache-Control": "no-store"})

    @app.post("/api/review/{file}/{element}", status_code=201)
    def review_mark(file: str, element: str, body: ReviewMark, who=Depends(user)):
        """«geprüft», «Änderung nötig» or «Frage» on one element, for the content as it is now; stored and logged."""
        if not may_review(who):
            raise HTTPException(403, "Markieren dürfen nur die für die Prüfung bestimmten Personen.")
        model = review_model()
        target = model.elements.get(f"{file}:{element}")
        if target is None:
            raise HTTPException(404, "Not found.")
        if body.sha256 and body.sha256 != target["sha256"]:
            raise HTTPException(409, "Das Element wurde seit dem Laden geändert; bitte neu laden.")
        comment, suggestion = body.comment.strip(), body.suggestion.strip() if body.mark == "aenderung" else ""
        if body.mark != "geprueft" and not comment:
            raise HTTPException(422, "Bitte sagen Sie, was zu ändern oder zu klären ist.")
        row = store.add_review(file, element, target["sha256"], body.mark, comment, suggestion, who)
        return {"mark": row, "element": model.view(target["key"], store.latest_reviews())}

    if UI.is_dir():
        page = (UI / "index.html").read_text()
        if (UI / "assets").is_dir():
            # Each asset's URL carries its content hash, so a browser never keeps last deploy's script or styles.
            for asset in sorted((UI / "assets").glob("*.*")):
                version = hashlib.sha256(asset.read_bytes()).hexdigest()[:12]
                page = page.replace(f'"/assets/{asset.name}"', f'"/assets/{asset.name}?v={version}"')
            app.mount("/assets", _Revalidated(directory=UI / "assets"), name="assets")

        @app.get("/")
        def index():
            return Response(page, media_type="text/html", headers={"Cache-Control": "no-store"})

    return app


class _Revalidated(StaticFiles):
    """Static files a browser must check before reuse (an unchanged file costs one 304)."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response


def _headers(text):
    """The From/To/Date/Subject lines the e-mail reader put first."""
    fields = {}
    for line in text.split("\n\n", 1)[0].split("\n"):
        key, _, value = line.partition(": ")
        if key in {"From", "To", "Date", "Subject"} and value:
            fields[key] = value
    return fields


def _docx(subject, paragraphs):
    """A minimal Word document: the draft, clearly marked as not sent."""
    import io
    import zipfile
    from xml.sax.saxutils import escape

    def para(text_value, bold=False):
        run = f"<w:r>{'<w:rPr><w:b/></w:rPr>' if bold else ''}<w:t xml:space=\"preserve\">{escape(text_value)}</w:t></w:r>"
        return f"<w:p>{run}</w:p>"
    body = para("Entwurf — nicht versendet. Eine Person prüft und entscheidet.", True) + para(subject, True) + "".join(para(p) for p in paragraphs)
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + "</w:body></w:document>")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                         '<Default Extension="xml" ContentType="application/xml"/>'
                         '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                         '<Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr("word/document.xml", document)
    return out.getvalue()


def case_api_contract():
    """The case API as OpenAPI JSON, stable across runs, for docs/contracts/."""
    import json
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        app = create_app(load_settings({"CASEPATH_DATA_DIR": directory, "CASEPATH_DEV_USER": "contract"}), model_factory=lambda: None)
        spec = app.openapi()
        app.state.runs.shutdown()
        app.state.store.close()
    spec["info"] = {"title": "CasePath case API", "version": "1"}
    return json.dumps(spec, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
