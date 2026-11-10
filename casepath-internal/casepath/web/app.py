"""The internal CasePath web service.

Every API call needs a signed-in user. In an operated deployment the platform
gateway authenticates the employee and passes the identity in a trusted header
(``CASEPATH_IDENTITY_HEADER``); in a personal development workspace a fixed
``CASEPATH_DEV_USER`` stands in. With neither, the API refuses to serve.
The browser never receives a model credential.
"""
from contextlib import asynccontextmanager
import hashlib
import json
import importlib.util
from dataclasses import replace
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from ..process import casegraph, knowledge as kb, workflows
from . import identity
from ..agents.azure_model import AzureOpenAIModel, entra_token_provider
from ..config import load_settings
from ..read.evidence import Evidence
from ..read.extract import attachments, extract
from ..agents.runner import RunService, case_state
from .store import CaseStore, Conflict, NotFound

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


class WorkflowChoice(BaseModel):
    workflow_id: str
    version: str | None = None


class EditRequest(BaseModel):
    op: str
    args: dict
    reason: str
    use_for_similar: bool = False
    activate: bool = False
    recheck: bool = True


class StatusChange(BaseModel):
    reason: str = ""


class Feedback(BaseModel):
    """A case worker's verdict on one result item; target names the item, never its content."""
    target: str = Field(pattern=r"^(answer|(fact|document|summary|timeline|deadline|open_point|reply|point):[A-Za-z0-9_.-]{1,80})$")
    verdict: Literal["correct", "wrong", "done"] | None  # "done": a point under Braucht Ihr Urteil a case worker settled
    note: str = Field("", max_length=500)


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
                      token_budget=settings.run_token_budget,
                      voice={"organisation": settings.organisation, "writing": settings.writing_language})

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

    def state(case_id):
        found(store.get_case, case_id)
        return case_state(store, catalogue, case_id)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "model_configured": settings.model is not None, "workflows": len(catalogue.workflows),
                "imports": files is not None, "uploads": uploads,
                "pdf_text": "pypdf" if importlib.util.find_spec("pypdf") else "builtin",
                "scanned_pages": "rendered" if importlib.util.find_spec("pypdfium2") and importlib.util.find_spec("PIL") else "embedded images",
                "sign_in": f"gateway ({settings.identity_format})" if settings.identity_header else "dev" if settings.dev_user else "none"}

    incoming = f"{settings.volume.rstrip('/')}/incoming" if settings.volume else None

    def add_with_attachments(case_id, name, declared, data, who):
        """Add the file to the case; an e-mail's attachments become files of the case too, each noting its e-mail."""
        import mimetypes

        def read(file_name, kind, payload):
            result = extract(file_name, kind, payload)
            if len(result["text"]) > settings.max_text_chars:
                result["text"] = result["text"][:settings.max_text_chars]
                result["note"] = ((result["note"] + " ") if result["note"] else "") + "Only the first part of the text is used."
            return result
        result = read(name, declared, data)
        row = store.add_file(case_id, name, result["media_type"], result["kind"], data, result, who)
        added = []
        for attached_name, payload in (attachments(name, declared, data) if result["kind"] == "email" else []):
            if not payload or len(payload) > settings.max_upload_bytes:
                continue
            inner = read(attached_name, mimetypes.guess_type(attached_name)[0] or "application/octet-stream", payload)
            inner["attached_to"] = name
            added.append(store.add_file(case_id, attached_name, inner["media_type"], inner["kind"], payload, inner, who)["id"])
        return {**row, "attachments": added} if added else row
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
            summaries[path] = {"title": manifest.get("title"), "files": len(rows) or None,
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
        added = await run_in_threadpool(add_with_attachments, case["id"], name, mimetypes.guess_type(name)[0] or "application/octet-stream", data, who)
        return {"case": store.get_case(case["id"]), "file": added}

    @app.get("/api/me")
    def me(who=Depends(user)):
        return {"user": who}

    @app.get("/api/workflows")
    def list_workflows(who=Depends(user)):
        return {"workflows": [{**workflows.ref(w), "sources": w["sources"], "steps": len(w["steps"]),
                               "documents": len(w["documents"]), "open_questions": len(w.get("open_questions", []))}
                              for w in catalogue.latest()]}

    @app.get("/api/workflows/{workflow_id}")
    def get_workflow(workflow_id: str, version: str | None = None, who=Depends(user)):
        workflow = catalogue.get(workflow_id, version)
        if workflow is None:
            raise HTTPException(404, "Not found.")
        return workflow

    @app.get("/api/cases")
    def list_cases(who=Depends(user)):
        return {"cases": store.list_cases()}

    @app.post("/api/cases", status_code=201)
    def create_case(body: NewCase, who=Depends(user)):
        title = body.title.strip()
        if not title or len(title) > 300:
            raise HTTPException(422, "A title of up to 300 characters is required.")
        return store.create_case(title, body.intake, who)

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str, who=Depends(user)):
        current = state(case_id)
        completed = current["run"]
        return {"case": current["case"], "files": store.list_files(case_id), "run": store.latest_run(case_id),
                "workflow": current["workflow"], "process": current["process"], "provenance": current.get("provenance"),
                "evaluation": current["evaluation"], "edits": store.list_edits(case_id, active_only=False),
                "feedback": store.list_feedback(completed["id"]) if completed else []}

    @app.delete("/api/cases/{case_id}")
    def delete_case(case_id: str, who=Depends(user)):
        try:
            return {"deleted": case_id, **store.delete_case(case_id, who)}
        except NotFound:
            raise HTTPException(404, "Not found.") from None
        except Conflict as error:
            raise HTTPException(409, str(error)) from None

    @app.put("/api/cases/{case_id}/workflow")
    def choose_workflow(case_id: str, body: WorkflowChoice, who=Depends(user)):
        workflow = catalogue.get(body.workflow_id, body.version)
        if workflow is None:
            raise HTTPException(404, "No such workflow.")
        return found(store.select_workflow, case_id, workflow["id"], workflow["version"], who)

    uploads = bool(importlib.util.find_spec("python_multipart") or importlib.util.find_spec("multipart"))

    async def upload(case_id: str, file: UploadFile = File(...), who=Depends(user)):
        found(store.get_case, case_id)
        data = await file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, f"Files up to {settings.max_upload_bytes // (1024 * 1024)} MB are accepted.")
        if not data:
            raise HTTPException(422, "The file is empty.")
        name = Path(file.filename or "file").name[:255]
        return await run_in_threadpool(add_with_attachments, case_id, name, file.content_type, data, who)  # a large PDF must not block the server

    if uploads:  # a runtime without the form parser serves prepared cases only (imported from the volume)
        app.post("/api/cases/{case_id}/files", status_code=201)(upload)

    @app.get("/api/files/{file_id}/original")
    def original(file_id: str, who=Depends(user)):
        data, row = found(store.file_bytes, file_id)
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
        try:
            return runs.start(case_id, who, model_token(request))
        except NotFound:
            raise HTTPException(404, "Not found.") from None
        except Conflict as error:
            raise HTTPException(409, str(error)) from None

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, after: int = 0, who=Depends(user)):
        return found(store.get_run, run_id, after)

    @app.put("/api/runs/{run_id}/feedback")
    def feedback(run_id: str, body: Feedback, who=Depends(user)):
        return {"feedback": found(store.set_feedback, run_id, body.target, body.verdict, body.note, who)}

    @app.get("/api/cases/{case_id}/report.docx")
    def report_docx(case_id: str, lang: str = "de", who=Depends(user)):
        """The case report for the case file: what the last prepared run found, each finding with its source."""
        from .report import build

        current = state(case_id)
        data = build(current["case"], current, store.list_files(case_id), lang=lang if lang in ("de", "en") else "de",
                     knowledge=store.list_knowledge())
        name = "Fallbericht.docx" if lang != "en" else "Case-report.docx"
        return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": f"attachment; filename={name}", "Cache-Control": "private, no-store"})

    @app.get("/api/runs/{run_id}/draft.docx")
    def draft_docx(run_id: str, who=Depends(user)):
        run = found(store.get_run, run_id)
        reply = ((run.get("result") or {}).get("reply")) or {}
        if not reply.get("clauses"):
            raise HTTPException(404, "This run has no draft.")
        data = _docx(reply.get("subject") or "Entwurf", [c["text"] for c in reply["clauses"]])
        return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": "attachment; filename=Entwurf.docx", "Cache-Control": "private, no-store"})

    # Editing the case's process
    @app.post("/api/cases/{case_id}/edits", status_code=201)
    def edit_process(case_id: str, body: EditRequest, request: Request, who=Depends(user)):
        before = state(case_id)
        if before["process"] is None:
            raise HTTPException(409, "Choose or route a workflow before editing the process.")
        if not body.reason.strip():
            raise HTTPException(422, "Say why the process changes.")
        try:
            casegraph.check_edit(before["process"], {"op": body.op, "args": body.args})
        except (casegraph.EditError, workflows.CatalogueError, KeyError, TypeError) as error:
            raise HTTPException(422, f"This change cannot be applied: {error}") from None
        edit = store.add_edit(case_id, body.op, body.args, who, body.reason.strip())
        learned = None
        if body.use_for_similar:
            try:
                item = kb.from_edit(before["workflow"]["id"], edit, before["process"], by=who)
            except kb.KnowledgeError as error:
                raise HTTPException(422, str(error)) from None
            if body.activate:
                item = kb.set_status(item, "active", by=who, reason="activated by the case worker who made the change")
            learned = store.save_knowledge(item)
        after = state(case_id)
        change = casegraph.diff(before["evaluation"], after["evaluation"])
        recheck = None
        added = [d["document"] for d in change["documents_added"]]
        if body.recheck and added and before["run"] is not None:
            try:
                recheck = runs.recheck(case_id, added, who, model_token(request))
            except Conflict:
                recheck = None
        return {"edit": edit, "diff": change, "knowledge": learned, "recheck": recheck, "evaluation": after["evaluation"]}

    @app.post("/api/edits/{edit_id}/undo")
    def undo(edit_id: str, who=Depends(user)):
        edit = found(store.get_edit, edit_id)
        before = state(edit["case_id"])
        store.set_edit_status(edit_id, "undone", who)
        after = state(edit["case_id"])
        return {"edit": store.get_edit(edit_id), "diff": casegraph.diff(before["evaluation"], after["evaluation"])}

    # Knowledge
    @app.get("/api/knowledge")
    def list_knowledge(family: str | None = None, status: str | None = None, who=Depends(user)):
        items = store.list_knowledge(family, {status} if status else None)
        return {"knowledge": items, "uses": store.knowledge_uses()}

    @app.get("/api/knowledge/{knowledge_id}")
    def get_knowledge(knowledge_id: str, who=Depends(user)):
        return {"item": found(store.get_knowledge, knowledge_id), "uses": store.knowledge_uses(knowledge_id)}

    @app.post("/api/knowledge/{knowledge_id}/activate")
    def activate(knowledge_id: str, body: StatusChange, who=Depends(user)):
        item = found(store.get_knowledge, knowledge_id)
        if item.get("refines"):
            target = found(store.get_knowledge, item["refines"])
            merged = kb.refine(target, content=item["content"], applies_when=item["applies_when"],
                               applies_when_text=item["applies_when_text"], by=who,
                               case_id=item["origin"].get("case_id"), reason=body.reason or "refined from a later case")
            store.save_knowledge(merged)
            store.save_knowledge(kb.set_status(item, "retired", by=who, reason=f"merged into {target['id']} v{merged['version']}"))
            return merged
        return store.save_knowledge(kb.set_status(item, "active", by=who, reason=body.reason))

    @app.post("/api/knowledge/{knowledge_id}/retire")
    def retire(knowledge_id: str, body: StatusChange, who=Depends(user)):
        item = found(store.get_knowledge, knowledge_id)
        return store.save_knowledge(kb.set_status(item, "retired", by=who, reason=body.reason))

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
