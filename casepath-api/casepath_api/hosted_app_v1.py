"""Hosted composition of the accepted autonomous engine and durable stores."""
import os
from pathlib import Path
import re
from threading import RLock

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from .agent_work.store import WorkStore
from .autonomous_api_v1 import create_autonomous_router
from .autonomous_corpus_v1 import CanonicalCorpus
from .hosted_lease_v1 import HostedAutonomousController, HostedWorkflowLease
from .hosted_proxy_v1 import HostedReadTiming, ReadTimedJSONResponse, SitesProxyBoundary
from .hosted_read_seed_v1 import load_seed
from .hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources, HostedStorageError, TursoDatabase
from .workspace_corpus import PublicCorpus, default_workspace_corpus_root


def create_hosted_app(*, database=None, environment=None, runtime_directory=None):
    env = os.environ if environment is None else environment
    origin, token = env['CASEPATH_SITE_ORIGIN'], env['CASEPATH_PROXY_TOKEN']
    SitesProxyBoundary(None, site_origin=origin, token=token)  # Validate before opening stores.
    commit = env.get('CASEPATH_SOURCE_COMMIT', '')
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('A sealed source commit is required for hosted deployment.')
    owns_database = database is None
    if owns_database:
        database = TursoDatabase(env['CASEPATH_TURSO_URL'], env['TURSO_AUTH_TOKEN'], reuse_http=True)
    root = Path(runtime_directory or '/tmp/casepath-hosted').resolve()
    state, lock = {}, RLock()
    api = FastAPI(title='CasePath', docs_url=None, redoc_url=None, openapi_url=None)

    def service():
        # This public composition only exposes saved, validated projections.
        with lock:
            if not state:
                raise HostedStorageError('Saved knowledge is not ready.')
            return state['controller']

    def startup():
        with lock:
            controller = work = None
            try:
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
                controller = HostedAutonomousController(store, policy, lease=lease, enforce_intake_gate=True)
                # Close dispatch before exposure. Startup, discovery, callbacks and
                # timers have no execution authority in the public read service.
                controller.shutdown()
                seed = load_seed(env.get('CASEPATH_READ_SEED_PATH') or
                                 Path(__file__).parent / 'artifacts' / 'hosted-read-seed-v1.json',
                                 deployment_commit=commit, expected_sha256=env.get('CASEPATH_READ_SEED_SHA256'))
                if seed is not None:
                    store.admit_read_seed(seed, deployment_commit=commit)
                state.update(controller=controller, work=work, corpus=CanonicalCorpus(corpus))
                # Run the same default read endpoints and response encoding once
                # before readiness. Every later read still performs its own fresh
                # journal/source validation; no response bytes are cached here.
                for name, arguments in (('knowledge', {}),
                        ('claims', {'limit': 200, 'offset': 0, 'q': '', 'domain': ''})):
                    route = read_routes['/api/claim-loops/v1/autonomous/' + name]
                    ReadTimedJSONResponse(jsonable_encoder(route.endpoint(**arguments)))
                state['ready'] = True
            except BaseException:
                state.clear()
                for resource, method in ((controller, 'shutdown'), (work, 'close'),
                                         (database if owns_database else None, 'close')):
                    if resource is not None:
                        try:
                            getattr(resource, method)()
                        except Exception:
                            pass  # Preserve startup failure and close remaining resources.
                raise

    def shutdown():
        with lock:
            try:
                if state.get('controller') is not None:
                    state['controller'].shutdown()
                    state['work'].close()
            finally:
                state.clear()
                if owns_database:
                    database.close()

    @api.exception_handler(HostedStorageError)
    async def unavailable(request, error):
        return JSONResponse({'detail': 'Saved work is temporarily unavailable. Please retry the connection.'}, status_code=503,
                            headers={'Cache-Control': 'no-store'})

    @api.get('/healthz')
    def health():
        with lock:
            if not state.get('ready'):
                raise HostedStorageError('Saved knowledge is not ready.')
            with database.connect() as db:
                db.execute('SELECT 1 AS ready').fetchone()
        return {'status': 'ok', 'component': 'api', 'source_commit': commit,
                'storage': 'remote_primary', 'writable': False, 'read_only': True}

    router = create_autonomous_router(service, lambda: state['work'].external_budget(),
                                     corpus_getter=lambda: state['corpus'],
                                     saved_work_getter=lambda: state['work'], read_only=True)
    read_routes = {route.path: route for route in router.routes if route.methods == {'GET'}}
    api.include_router(router)
    api.add_event_handler('startup', startup)
    api.add_event_handler('shutdown', shutdown)
    api.add_middleware(SitesProxyBoundary, site_origin=origin, token=token)
    api.add_middleware(HostedReadTiming)
    return api
