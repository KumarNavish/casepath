"""Read models built only from the verified work journal, never invented activity."""
from datetime import datetime
import time
from .contracts import ROLE_ORDER, ROLE_LABELS, Operation


def summarize(store, run, snapshot=None):
    frozen=snapshot or store.snapshot(run['run_id'])
    run=frozen['run'];events=frozen['events']
    role_states=[]
    for role in ROLE_ORDER:
        relevant=[e for e in events if e['role']==role.value]
        started=next((e for e in relevant if e['operation']=='AGENT_STARTED'),None)
        complete=next((e for e in reversed(relevant) if e['operation']=='AGENT_COMPLETED'),None)
        blocked=next((e for e in reversed(relevant) if e['operation']=='AGENT_BLOCKED'),None)
        status='completed' if complete else 'blocked' if blocked else 'working' if started else 'not_started'
        if status=='working' and (run['status']!='running' or (run.get('lease_until') or 0)<=time.time()):status='unconfirmed'
        end=complete or blocked
        seconds=(datetime.fromisoformat(end['timestamp'])-datetime.fromisoformat(started['timestamp'])).total_seconds() if started and end else None
        completion=next((e.get('after',{}).get('value',{}) for e in reversed(relevant) if e['operation']=='WORK_PRODUCT_RECORDED' and e['object_kind']=='role_completion'),{})
        role_states.append({'coverage':completion.get('coverage'), 'coverage_contract':completion.get('coverage_contract'), 'limited_source_extractions':completion.get('limited_source_extractions',[]),'id':role.value,'label':ROLE_LABELS[role], 'status':status,
            'started_at':started['timestamp'] if started else None, 'finished_at':end['timestamp'] if end else None,
            'seconds':seconds, 'worker_kind':started['worker_kind'] if started else None,
            'last_operation':relevant[-1]['message'] if relevant else None,
            'rejected_proposals':sum(e['operation']=='GATE_REJECTED' for e in relevant)})
    active=next((r for r in role_states if r['status'] in ('working','unconfirmed','blocked')),None)
    provider=[e for e in events if e['operation']=='PROVIDER_RESPONSE_RECEIVED']
    started_requests=[e for e in events if e['operation']=='PROVIDER_REQUEST_STARTED']
    usage_known=len(provider)==len(started_requests) and all(((e.get('after') or {}).get('usage') or {}).get('cost') is not None for e in provider)
    # An absent or timed-out provider response is not a zero-cost call.
    total_cost=sum((e['after']['usage']['cost'] for e in provider),0) if usage_known else None
    result={'run_id':run['run_id'],'claim_id':run['claim_id'],'subject':run['request']['context'].get('subject','Claim'),
        'status':'unconfirmed' if run['status']=='running' and (run.get('lease_until') or 0)<=time.time() else run['status'],
        'created_at':run['created_at'],'last_event_at':events[-1]['timestamp'] if events else run['created_at'],
        'last_sequence':events[-1]['sequence'] if events else 0,'last_event_sha256':events[-1]['event_sha256'] if events else None,
        'roles':role_states,'completed_roles':sum(r['status']=='completed' for r in role_states),'role_count':6,
        'current_role':active,'last_message':events[-1]['message'] if events else None,
        'facts_worker':run['request']['facts_worker'],'provider_requests':len(started_requests),'provider_cost_usd':total_cost,
        'pending_calls':frozen['pending_calls']}
    return result
