"""Bind the extension to an existing CasePath app without changing its authority."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
from threading import RLock
import json,os

from .authority import ExistingCasePathAuthority
from .api import create_agent_work_router
from .service import AgentWorkService
from .store import WorkStore,WorkStoreError
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
    demo=os.getenv('CASEPATH_AGENT_WORK_DEMO')=='1'
    selected=choose_model(packet['catalogue'], model=os.environ['CASEPATH_AGENT_WORK_MODEL'] if demo else os.getenv('CASEPATH_AGENT_WORK_MODEL'))
    config=OpenRouterConfig(model=selected['model'],canonical_model=selected.get('canonical_model'),prompt_price=Decimal(selected['prompt_price']),
            completion_price=Decimal(selected['completion_price']),request_price=Decimal(selected['request_price']),
            catalogue_entry_sha256=selected['catalogue_entry_sha256'],context_length=selected['context_length'],
            reasoning_supported=selected['reasoning_supported'],
            total_cost_limit=Decimal(os.environ['CASEPATH_AGENT_WORK_RUN_COST_USD']) if demo else Decimal('0.02'))
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
                store=WorkStore(Path(work_database))
                max_runs=1
                try:
                    external=configured_external_worker()
                    if external is not None:
                        if os.getenv('CASEPATH_AGENT_WORK_DEMO')=='1':
                            max_runs=int(os.environ['CASEPATH_AGENT_WORK_MAX_EXTERNAL_RUNS'])
                            store.configure_external_budget({'max_runs':max_runs,
                                'max_provider_calls':int(os.environ['CASEPATH_AGENT_WORK_MAX_PROVIDER_CALLS']),
                                'total_cost_limit_usd':os.environ['CASEPATH_AGENT_WORK_TOTAL_COST_USD'],
                                'run_cost_limit_usd':os.environ['CASEPATH_AGENT_WORK_RUN_COST_USD']})
                        external_status='ready'
                except (ValueError,KeyError,TypeError,OSError,WorkBlocked,WorkStoreError):
                    # Configuration failure disables this optional choice only.
                    # A requested external run is rejected, never substituted.
                    external_status='rejected'
                    external=None
                    max_runs=1
                state['service']=AgentWorkService(store,authority,
                    facts_worker=external,max_external_runs=max_runs,
                    external_configuration_status=external_status)
                def require_handler(claim_id,context):
                    current=workspace_getter().store.recover(claim_id)
                    if not isinstance(current.get('owner'),str) or not current['owner'].strip():
                        raise WorkStoreError('Assign an accountable handler before requesting model review')
                    if current['state_sha256']!=context['state_sha256']:
                        raise WorkStoreError('The saved claim changed before model review was admitted')
                    from ..agent_desk_v1 import DelegateJournal
                    if DelegateJournal(workspace_getter()).state(claim_id)['paused']:
                        raise WorkStoreError('Resume the paused delegate before requesting model review')
                state['service'].external_start_guard=require_handler
            return state['service']
    app.include_router(create_agent_work_router(service))
    def shutdown():
        if state['service'] is not None:state['service'].shutdown()
    app.add_event_handler('shutdown',shutdown)
    app.state.casepath_agent_work_installed=True
    return service
