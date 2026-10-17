"""Check whether the visitor's SELECTs are genuinely unused during startup."""
from pathlib import Path
import hashlib,json,sys
REPO=Path('/workspace/casepath-release-ae0-shard6')
OUT=Path('/workspace/knowledge-first-read-20261018/e')
sys.path[:0]=[str(REPO/'casepath-api'),str(REPO/'casepath-api/tests')]
import httpx
from casepath_api.autonomous_knowledge_v1 import AutonomousKnowledge
from casepath_api.autonomous_store_v1 import AutonomousStore
from casepath_api.workspace_corpus import PublicCorpus,default_workspace_corpus_root
from test_autonomous_knowledge_reads_v1 import hosted_copy
def forbidden(*a,**k):raise AssertionError('No real network permitted')
httpx.HTTPTransport.handle_request=forbidden
original=Path('/workspace/atomic-proof-20261017/writer/t/reads/knowledge-processed-roster0/claims.sqlite3')
native=AutonomousStore.open_read_only(original)
policy=PublicCorpus(default_workspace_corpus_root()).static_policy()
fixture=OUT/'query-shape-fixture';fixture.mkdir()
server,store,_,_=hosted_copy((original,native.source_root,policy,None),fixture)
knowledge=AutonomousKnowledge(store,policy)
def statements(requests):
 return [x['stmt'] for request in requests for x in request['requests'] if x['type']=='execute']
def identity(stmt):return json.dumps(stmt,sort_keys=True,separators=(',',':'))
try:
 server.reset_counts();initial=knowledge.learning_view();cold=list(server.requests)
 server.reset_counts();assert knowledge.learning_view()==initial;warm=list(server.requests)
 prior={identity(x) for x in statements(cold)}
 rows=[]
 for stmt in statements(warm):
  if not stmt['sql'].startswith('SELECT'):continue
  rows.append({'query_sha256':hashlib.sha256(stmt['sql'].encode()).hexdigest(),
   'exact_sql_and_typed_parameters_used_during_cold':identity(stmt) in prior,
   'domain':'journal' if 'claim_loop_events' in stmt['sql'] else 'source',
   'schema_query':'pragma_table_info' in stmt['sql']})
 result={'candidate':'c925a0267971edb52fea5f2bd9653a2495b7ac15',
  'qualification':'Local unchanged native fixture only; no remote query-plan-cache or native network timing claim.',
  'cold_http_requests':len(cold),'warm_http_requests':len(warm),'warm_selects':rows,
  'all_warm_selects_already_executed_exactly_during_cold':all(x['exact_sql_and_typed_parameters_used_during_cold'] for x in rows),
  'combined_atomic_envelope_used_during_cold':warm[0] in cold}
 (OUT/'query-coverage.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
finally:server.close()
