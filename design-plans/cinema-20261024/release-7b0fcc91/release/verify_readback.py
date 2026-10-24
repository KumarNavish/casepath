if not __debug__:
    raise RuntimeError('Release helpers require Python assertions enabled.')
from pathlib import Path
import json,sys,hashlib
B=Path(sys.argv[1]);sha=sys.argv[2]
before=json.loads((B/'readback-before.json').read_text());after=json.loads((B/'readback-after.json').read_text())
health=after['health']
r={'canonical_commit':sha,'api_commit':health['source_commit'],'frontend_commit':after['frontend']['source_commit'],'read_only':health.get('read_only'),'writable':health.get('writable'),'storage':health.get('storage'),'claims':after['summary']['claims'],'collection_unchanged':before['collection']==after['collection'],'knowledge_unchanged':before['knowledge']==after['knowledge'],'ledger_unchanged':before['summary']['limits']==after['summary']['limits'],'collection_sha256':after['summary']['collection_sha256'],'knowledge_sha256':after['summary']['knowledge_sha256'],'provider_calls':after['summary']['limits']['provider_calls_used'],'actual_cost_usd':after['summary']['limits']['actual_cost_usd'],'original_nine_workflows':after['summary']['limits']['original_nine_workflows_used'],'original_nine_calls':after['summary']['limits']['original_nine_provider_calls_used'],'original_nine_repeated':False}
primary_prefix='https://casepath-agent.fastapicloud.dev/api/claim-loops/v1/autonomous'
r['primary_reads_verified']=after.get('primary_reads_required') is True and all(after.get('read_sources',{}).get(primary_prefix+route)=='primary' for route in ['/knowledge','/claims?limit=500'])
assert r['primary_reads_verified'], 'Final primary readback evidence is required'
assert r['api_commit']==r['frontend_commit']==sha and health.get('status')=='ok'
assert r['read_only'] is True and r['writable'] is False and r['storage']=='remote_primary'
assert r['claims']==159 and r['collection_unchanged'] and r['knowledge_unchanged'] and r['ledger_unchanged']
assert r['provider_calls']==42 and r['original_nine_workflows']==9 and r['original_nine_calls']==18
with (B/'readback-verified.json').open('x') as f:
    json.dump(r,f,indent=2);f.write('\n')
print(json.dumps(r,indent=1))

