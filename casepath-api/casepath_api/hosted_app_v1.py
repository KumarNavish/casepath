"""Hosted composition of the accepted autonomous engine and durable stores."""
import os
from pathlib import Path
import re
from threading import RLock

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .agent_work.store import WorkStore
from .autonomous_api_v1 import create_autonomous_router
from .autonomous_corpus_v1 import CanonicalCorpus
from .hosted_lease_v1 import HostedAutonomousController, HostedWorkflowLease
from .hosted_model_v1 import HostedModel
from .hosted_proxy_v1 import SitesProxyBoundary
from .hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources, HostedStorageError, TursoDatabase
from .workspace_corpus import PublicCorpus, default_workspace_corpus_root


def create_hosted_app(*, database=None, environment=None, runtime_directory=None):
    env = os.environ if environment is None else environment
    origin, token = env['CASEPATH_SITE_ORIGIN'], env['CASEPATH_PROXY_TOKEN']
    SitesProxyBoundary(None, site_origin=origin, token=token)  # Validate before opening stores.
    commit = env.get('CASEPATH_SOURCE_COMMIT', '')
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('A sealed source commit is required for hosted deployment.')
    database = database or TursoDatabase(env['CASEPATH_TURSO_URL'], env['TURSO_AUTH_TOKEN'])
    writable = env.get('CASEPATH_HOSTED_WRITABLE') == '1'
    root = Path(runtime_directory or '/tmp/casepath-hosted').resolve()
    state, lock = {}, RLock()
    api = FastAPI(title='CasePath', docs_url=None, redoc_url=None, openapi_url=None)

    def service():
        # Reads must never wake or dispatch work. Startup resume and explicit
        # mutation commands retain the existing single-worker scheduler.
        return state['controller']

    def startup():
        with lock:
            lease = HostedWorkflowLease(database.connect)
            lease.initialize()
            journal = HostedJournal(root / 'remote-claim-journal', lease.connect)
            work = WorkStore(root / 'remote-work-journal', connection_factory=lease.connect)
            sources = HostedSources(lease.connect)
            store = HostedAutonomousStore(journal.path, journal=journal, source_store=sources)
            model = None
            if env.get('CASEPATH_AUTONOMOUS_ENABLED') == '1':
                if not writable or not work.external_budget():
                    raise ValueError('Inference requires an imported allowance and writable cloud ownership.')
                model = HostedModel(work, env['CASEPATH_AGENT_WORK_MODEL'], env['OPENROUTER_API_KEY'])
            corpus = PublicCorpus(default_workspace_corpus_root())
            policy = corpus.static_policy()
            controller = HostedAutonomousController(store, policy, model, lease=lease)
            state.update(controller=controller, work=work, corpus=CanonicalCorpus(corpus))
            if writable:
                controller.resume()

    def shutdown():
        if state.get('controller') is not None:
            state['controller'].shutdown()
            state['work'].close()

    @api.exception_handler(HostedStorageError)
    async def unavailable(request, error):
        return JSONResponse({'detail': 'Saved work is temporarily unavailable. Please retry the connection.'}, status_code=503,
                            headers={'Cache-Control': 'no-store'})

    @api.middleware('http')
    async def migration_guard(request, call_next):
        if request.method not in ('GET', 'HEAD') and not writable:
            return JSONResponse({'detail': 'The hosted workspace is being connected. Saved work remains protected.'}, status_code=503)
        return await call_next(request)

    @api.get('/healthz')
    def health():
        with database.connect() as db:
            db.execute('SELECT 1 AS ready').fetchone()
        return {'status': 'ok', 'component': 'api', 'source_commit': commit,
                'storage': 'remote_primary', 'writable': writable}

    api.include_router(create_autonomous_router(service, lambda: state['work'].external_budget(),
                                               corpus_getter=lambda: state['corpus']))
    api.add_event_handler('startup', startup)
    api.add_event_handler('shutdown', shutdown)
    api.add_middleware(SitesProxyBoundary, site_origin=origin, token=token)
    return api
