"""Bind the extension to an existing CasePath app without changing its authority."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
from threading import RLock
import json,os

from .authority import ExistingCasePathAuthority
from .api import create_agent_work_router
from .service import AgentWorkService
from .store import WorkStore
from .openrouter import OpenRouterConfig,OpenRouterFactsWorker,choose_model
from .contracts import digest
from .runtime import WorkBlocked


def configured_external_worker():
    """Explicit opt-in; no API request is sent by configuration or application startup."""
    if os.getenv('CASEPATH_AGENT_WORK_EXTERNAL_FACTS')!='1':return None
    selection=Path(os.environ['CASEPATH_AGENT_WORK_CATALOGUE'])
    if selection.is_symlink() or not selection.is_file() or selection.stat().st_size>2_000_000:
        raise ValueError('External worker requires a regular bounded catalogue snapshot')
    packet=json.loads(selection.read_text())
    age=datetime.now(timezone.utc)-datetime.fromisoformat(packet['fetched_at'])
    if not 0<=age.total_seconds()<=86400:raise ValueError('Model catalogue snapshot must be from the preceding 24 hours')
    if packet.get('catalogue_sha256')!=digest(packet.get('catalogue')):
        raise ValueError('Catalogue identity differs from its recorded snapshot')
    selected=choose_model(packet['catalogue'])
    config=OpenRouterConfig(model=selected['model'],canonical_model=selected.get('canonical_model'),prompt_price=Decimal(selected['prompt_price']),
            completion_price=Decimal(selected['completion_price']),request_price=Decimal(selected['request_price']),
            catalogue_entry_sha256=selected['catalogue_entry_sha256'])
    key=os.getenv('OPENROUTER_API_KEY')
    if not key:raise ValueError('Server-side OpenRouter credential is not configured')
    return OpenRouterFactsWorker(config,key)


def install_agent_work(app,workspace_getter,loop_getter,work_database):
    """Install once. Uses the same six semantic roles and original start/ensure gates."""
    if getattr(app.state,'casepath_agent_work_installed',False):
        raise ValueError('Agent-work routes are already installed')
    state={'service':None};lock=RLock()
    def service():
        with lock:
            if state['service'] is None:
                authority=ExistingCasePathAuthority(workspace_getter,loop_getter)
                external=None
                external_status='disabled'
                try:
                    external=configured_external_worker()
                    if external is not None:external_status='ready'
                except (ValueError,KeyError,TypeError,OSError,WorkBlocked):
                    # Configuration failure disables this optional choice only.
                    # A requested external run is rejected, never substituted.
                    external_status='rejected'
                state['service']=AgentWorkService(WorkStore(Path(work_database)),authority,
                    facts_worker=external,max_external_runs=1,
                    external_configuration_status=external_status)
            return state['service']
    app.include_router(create_agent_work_router(service))
    def shutdown():
        if state['service'] is not None:state['service'].shutdown()
    app.add_event_handler('shutdown',shutdown)
    app.state.casepath_agent_work_installed=True
    return service
