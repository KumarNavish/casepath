"""Compare exact base and authored Knowledge reads on the same native fixture."""
import importlib.util
import json
from pathlib import Path
from time import perf_counter
import httpx
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.autonomous_knowledge_v1 import AutonomousKnowledge
from casepath_api.workspace_corpus import PublicCorpus, default_workspace_corpus_root
from test_autonomous_knowledge_reads_v1 import hosted_copy, statements

root=Path('/workspace/klp/e')
def baseline_module(name,path):
    spec=importlib.util.spec_from_file_location('casepath_api.'+name,root/path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
oldknowledge=baseline_module('_profile_base_knowledge','base_autonomous_knowledge_v1.py')
oldhosted=baseline_module('_profile_base_hosted','base_hosted_storage_v1.py')
fixture=Path('/workspace/klp/t/baseline/knowledge-processed-roster0')
readonly=AutonomousStore.open_read_only(fixture/'claims.sqlite3')
states=readonly.validated_states()
policy=PublicCorpus(default_workspace_corpus_root()).static_policy()
roster=(readonly.path,readonly.source_root,policy,states)

def forbidden(*args,**kwargs):
    raise AssertionError('Profile attempted provider/network dispatch')
httpx.HTTPTransport.handle_request=forbidden
results=[]
expected=None
for variant in ('exact_base','authored'):
    target=Path('/workspace/klp/t')/('profile-'+variant)
    target.mkdir(exist_ok=False)
    server,store,_,_=hosted_copy(roster,target)
    if variant=='exact_base':
        store=oldhosted.HostedAutonomousStore(store.path,journal=store.journal,
                       source_store=oldhosted.HostedSources(server.connection))
        knowledge=oldknowledge.AutonomousKnowledge(store,policy)
    else:
        knowledge=AutonomousKnowledge(store,policy)
    try:
        for temperature in ('cold','warm'):
            server.reset_counts()
            started=perf_counter()
            projection=knowledge.view() if variant=='exact_base' else knowledge.learning_view()
            elapsed=perf_counter()-started
            native={key:projection[key] for key in ('versions','uses','quarantined')}
            if expected is None: expected=native
            assert native==expected
            sql=list(statements(server.requests))
            assert all(statement.strip().split()[0].upper() in {'SELECT','BEGIN','COMMIT','ROLLBACK','PRAGMA'} for statement in sql)
            results.append({'variant':variant,'temperature':temperature,'http_requests':len(server.requests),
                 'response_bytes':sum(server.response_bytes),'largest_response_bytes':max(server.response_bytes),
                 'journal_pages':len(server.journal_pages),'journal_event_bytes':sum(size for _,size in server.journal_pages),
                 'source_pages':sum('FROM autonomous_source_chunks' in statement for statement in sql),
                 'mock_elapsed_seconds':round(elapsed,6),'projection_bytes':len(json.dumps(projection,separators=(',',':')).encode())})
            assert server.open_streams==0
    finally:
        server.close()
print(json.dumps({'fixture':'isolated native deterministic 18-claim roster','network':'MockHrana only; timings are not hosted TTFB',
                  'exact_base':'b8616d4cfd5bf5667587dd1a0bf4ed58e9436d2b','measurements':results},indent=2))
