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
    root = Path(runtime_directory or '/tmp/casepath-hosted').resolve()
    state, lock = {}, RLock()
    api = FastAPI(title='CasePath', docs_url=None, redoc_url=None, openapi_url=None)

    def service():
        # This public composition only exposes saved, validated projections.
        return state['controller']

    def startup():
        with lock:
            lease = HostedWorkflowLease(database.connect)
            lease.initialize()
            journal = HostedJournal(root / 'remote-claim-journal', lease.connect)
            work = WorkStore(root / 'remote-work-journal', connection_factory=lease.connect,
                             validated_source_commit=commit)
            sources = HostedSources(lease.connect)
            store = HostedAutonomousStore(journal.path, journal=journal, source_store=sources)
            # Existing store guards reject both source publication and journal
            # admission even if an internal caller reaches a mutation method.
            store._read_only = True
            corpus = PublicCorpus(default_workspace_corpus_root())
            policy = corpus.static_policy()
            controller = HostedAutonomousController(store, policy, lease=lease)
            # Close dispatch before exposure. Startup, discovery, callbacks and
            # timers have no execution authority in the public read service.
            controller.shutdown()
            state.update(controller=controller, work=work, corpus=CanonicalCorpus(corpus))

    def shutdown():
        if state.get('controller') is not None:
            state['controller'].shutdown()
            state['work'].close()

    @api.exception_handler(HostedStorageError)
    async def unavailable(request, error):
        return JSONResponse({'detail': 'Saved work is temporarily unavailable. Please retry the connection.'}, status_code=503,
                            headers={'Cache-Control': 'no-store'})

    @api.get('/healthz')
    def health():
        with database.connect() as db:
            db.execute('SELECT 1 AS ready').fetchone()
        return {'status': 'ok', 'component': 'api', 'source_commit': commit,
                'storage': 'remote_primary', 'writable': False, 'read_only': True}

    api.include_router(create_autonomous_router(service, lambda: state['work'].external_budget(),
                                               corpus_getter=lambda: state['corpus'],
                                               saved_work_getter=lambda: state['work'], read_only=True))
    api.add_event_handler('startup', startup)
    api.add_event_handler('shutdown', shutdown)
    api.add_middleware(SitesProxyBoundary, site_origin=origin, token=token)
    return api
