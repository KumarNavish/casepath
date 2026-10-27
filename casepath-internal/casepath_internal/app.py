"""The internal CasePath web service.

Every API call needs a signed-in user. In an operated deployment the platform
gateway authenticates the employee and passes the identity in a trusted header
(``CASEPATH_IDENTITY_HEADER``); in a personal development workspace a fixed
``CASEPATH_DEV_USER`` stands in. With neither, the API refuses to serve.
The browser never receives a model credential.
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import workflows
from .azure_model import AzureOpenAIModel, entra_token_provider
from .config import load_settings
from .extract import extract, media_type
from .runner import RunService
from .store import CaseStore, Conflict, NotFound

UI = Path(__file__).parent / "ui"


class NewCase(BaseModel):
    title: str
    intake: dict = {}


class WorkflowChoice(BaseModel):
    workflow_id: str
    version: str | None = None


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
    runs = RunService(store, catalogue, model_factory or default_model_factory(settings))

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

    def evaluation_for(case, run):
        workflow_ref = (run or {}).get("routing", {}) or {}
        workflow = None
        if case.get("workflow_id"):
            workflow = catalogue.get(case["workflow_id"], case.get("workflow_version"))
        elif workflow_ref.get("workflow"):
            workflow = catalogue.get(workflow_ref["workflow"]["id"], workflow_ref["workflow"]["version"])
        if workflow is None:
            return None
        if run and run.get("result") and run["result"].get("evaluation") and run["workflow_id"] == workflow["id"]:
            return run["result"]["evaluation"]
        return workflows.evaluate(workflow, {}, {}, checked=False)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "model_configured": settings.model is not None,
                "workflows": len(catalogue.workflows), "sign_in": "gateway" if settings.identity_header else "dev" if settings.dev_user else "none"}

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
        case = found(store.get_case, case_id)
        run = store.latest_run(case_id)
        return {"case": case, "files": store.list_files(case_id), "run": run,
                "evaluation": evaluation_for(case, store.latest_run(case_id, "completed"))}

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
                        headers={"Content-Disposition": f"inline; filename*=UTF-8''{_quote(row['name'])}",
                                 "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})

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

    @app.get("/api/knowledge")
    def knowledge(workflow_id: str | None = None, status: str | None = None, who=Depends(user)):
        return {"knowledge": store.list_knowledge(workflow_id, status)}

    @app.post("/api/knowledge/{knowledge_id}/publish")
    def publish(knowledge_id: str, who=Depends(user)):
        try:
            return found(store.publish_knowledge, knowledge_id, who)
        except Conflict as error:
            raise HTTPException(409, str(error)) from None

    if UI.is_dir():
        app.mount("/assets", StaticFiles(directory=UI / "assets"), name="assets")

        @app.get("/")
        def index():
            return FileResponse(UI / "index.html", headers={"Cache-Control": "no-store"})

    return app


def _quote(name):
    from urllib.parse import quote
    return quote(name, safe="")
