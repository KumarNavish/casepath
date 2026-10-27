"""The internal CasePath web service.

Every API call needs a signed-in user. In an operated deployment the platform
gateway authenticates the employee and passes the identity in a trusted header
(``CASEPATH_IDENTITY_HEADER``); in a personal development workspace a fixed
``CASEPATH_DEV_USER`` stands in. With neither, the API refuses to serve.
The browser never receives a model credential.
"""
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import casegraph, knowledge as kb, workflows
from .azure_model import AzureOpenAIModel, entra_token_provider
from .config import load_settings
from .evidence import Evidence
from .extract import extract
from .runner import RunService, case_state
from .store import CaseStore, Conflict, NotFound

UI = Path(__file__).parent / "ui"


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


def default_model_factory(settings):
    if settings.model is None:
        return lambda: None
    shared = {}

    def factory():
        if "model" not in shared:
            shared["model"] = AzureOpenAIModel(settings.model, entra_token_provider())
        return shared["model"]
    return factory


def create_app(settings=None, *, model_factory=None, store=None, catalogue=None):
    settings = settings or load_settings()
    store = store or CaseStore(settings.data_dir)
    catalogue = catalogue or workflows.Catalogue.load(settings.catalogue_dir)
    runs = RunService(store, catalogue, model_factory or default_model_factory(settings), reading_workers=settings.reading_workers)

    @asynccontextmanager
    async def lifespan(_):
        yield
        runs.shutdown()
        store.close()

    app = FastAPI(title="CasePath (internal)", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.store, app.state.catalogue, app.state.runs = store, catalogue, runs

    def user(request: Request):
        if settings.identity_header:
            value = request.headers.get(settings.identity_header)
            if not value:
                raise HTTPException(401, "Sign-in required.")
            return value[:200]
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
                "sign_in": "gateway" if settings.identity_header else "dev" if settings.dev_user else "none"}

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
        return {"case": current["case"], "files": store.list_files(case_id), "run": store.latest_run(case_id),
                "workflow": current["workflow"], "process": current["process"], "provenance": current.get("provenance"),
                "evaluation": current["evaluation"], "edits": store.list_edits(case_id, active_only=False)}

    @app.put("/api/cases/{case_id}/workflow")
    def choose_workflow(case_id: str, body: WorkflowChoice, who=Depends(user)):
        workflow = catalogue.get(body.workflow_id, body.version)
        if workflow is None:
            raise HTTPException(404, "No such workflow.")
        return found(store.select_workflow, case_id, workflow["id"], workflow["version"], who)

    @app.post("/api/cases/{case_id}/files", status_code=201)
    async def upload(case_id: str, file: UploadFile = File(...), who=Depends(user)):
        found(store.get_case, case_id)
        data = await file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, f"Files up to {settings.max_upload_bytes // (1024 * 1024)} MB are accepted.")
        if not data:
            raise HTTPException(422, "The file is empty.")
        name = Path(file.filename or "file").name[:255]
        result = extract(name, file.content_type, data)
        if len(result["text"]) > settings.max_text_chars:
            result["text"] = result["text"][:settings.max_text_chars]
            result["note"] = ((result["note"] + " ") if result["note"] else "") + "Only the first part of the text is used."
        return store.add_file(case_id, name, result["media_type"], result["kind"], data, result, who)

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
                "headers": _headers(row["extraction"].get("text", "")) if row["kind"] == "email" else None,
                "pages": [{"page": page, "text": text} for page, text in pages]}

    @app.post("/api/cases/{case_id}/runs", status_code=202)
    def start_run(case_id: str, who=Depends(user)):
        try:
            return runs.start(case_id, who)
        except NotFound:
            raise HTTPException(404, "Not found.") from None
        except Conflict as error:
            raise HTTPException(409, str(error)) from None

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, after: int = 0, who=Depends(user)):
        return found(store.get_run, run_id, after)

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
    def edit_process(case_id: str, body: EditRequest, who=Depends(user)):
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
                recheck = runs.recheck(case_id, added, who)
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
        if (UI / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=UI / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(UI / "index.html", headers={"Cache-Control": "no-store"})

    return app


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
