"""Offline native synthetic size diagnosis; no production/provider access."""
import base64
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from time import perf_counter
import httpx
from casepath_api.autonomous_store_v1 import AutonomousStore, SESSION_ID
from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources
from hosted_hrana_fixture import MockHrana

root=Path('/workspace/knowledge-read-repair-20261016/projection/t/large-native')
root.mkdir(exist_ok=False)
seed=AutonomousStore(root/'seed.sqlite3')
states=[]
def append(state,kind,payload,key):
    return seed.append(state['claim_id'],kind,payload,expected_revision=state['revision'],
                       expected_state_sha256=state['state_sha256'],idempotency_key=key)
started=perf_counter()
for index in range(24):
    message=(f'Isolated synthetic original claim {index}. Original customer statement. '*700)[:40000]
    files=[]
    for document in range(6):
        raw=(f'Isolated synthetic supporting original claim {index}, document {document}. '*800).encode()[:40000]
        files.append({'file_name':f'original-{document}.txt','media_type':'text/plain',
                      'content_base64':base64.b64encode(raw).decode()})
    state=seed.intake({'title':f'Large native read fixture {index}','message':message,'files':files},f'large.intake.{index}')
    receipts=[seed.acquire(state['claim_id'],source['artifact_id']) for source in state['source_descriptors'][1:]]
    state=append(state,'sources.acquired',{'sources':receipts},f'large.acquire.{index}')
    for workflow in range(8):
        state=append(state,'work.context',{'workflow_id':f'large.workflow.{index}.{workflow}',
                     'context':{'claim_id':state['claim_id'],'sources':state['acquired_sources'],
                                'compatible_knowledge':[]}},f'large.context.{index}.{workflow}')
    states.append(state)
print('native_fixture_ready',round(perf_counter()-started,6),flush=True)

class MeasuredHrana(MockHrana):
    def __init__(self,path):
        super().__init__(path)
        self.pages=[];self.response_bytes=[]
    def _statement(self,connection,stmt):
        if 'claim_loop_events' not in stmt['sql'] or not stmt['sql'].startswith('SELECT * FROM ('):
            return super()._statement(connection,stmt)
        from casepath_api.hosted_sql_v1 import _decode
        started=perf_counter()
        cursor=connection.execute(stmt['sql'],tuple(_decode(arg) for arg in stmt.get('args',[])))
        rows=cursor.fetchall();elapsed=perf_counter()-started
        columns=[col[0] for col in cursor.description or ()]
        raw=sum(len(row[columns.index('event_json')].encode()) for row in rows)
        candidates=rows[0][columns.index('__read_candidates')] if rows else 0
        self.pages.append({'rows':len(rows),'candidate_rows':candidates,'event_bytes':raw,'sqlite_seconds':round(elapsed,6)})
        return {'cols':[{'name':name,'decltype':None} for name in columns],
                'rows':[[self._value(value) for value in row] for row in rows],
                'affected_row_count':max(0,cursor.rowcount),'last_insert_rowid':str(cursor.lastrowid) if cursor.lastrowid is not None else None}
    def handle(self,request):
        response=super().handle(request)
        self.response_bytes.append(len(response.content))
        return response

server=MeasuredHrana(root/'hosted.sqlite3')
journal=HostedJournal(root/'unused-hosted',server.connection)
with sqlite3.connect(seed.path) as original,sqlite3.connect(server.path) as target:
    rows=original.execute('SELECT * FROM claim_loop_events WHERE session_id=?',(SESSION_ID,)).fetchall()
    target.executemany('INSERT INTO claim_loop_events VALUES (?,?,?,?,?,?,?,?)',rows)
    for source in seed.source_root.iterdir():
        raw=source.read_bytes()
        target.execute('INSERT INTO autonomous_source_chunks VALUES (?,?,?)',(source.name,0,raw))
    candidates={str(count):original.execute('SELECT count(*),sum(length(CAST(event_json AS BLOB))) FROM '
                 '(SELECT event_json FROM claim_loop_events WHERE session_id=? ORDER BY loop_id,sequence LIMIT ?)',
                 (SESSION_ID,count)).fetchone() for count in (128,2048)}

def forbidden(*args,**kwargs):
    raise AssertionError('Unexpected provider/network dispatch')
httpx.HTTPTransport.handle_request=forbidden
measurements=[]
try:
    for count in (128,2048):
        store=HostedAutonomousStore(journal.path,journal=journal,source_store=HostedSources(server.connection))
        store.KNOWLEDGE_PAGE_ROWS=count
        server.requests.clear();server.pages.clear();server.response_bytes.clear()
        started=perf_counter()
        result=store._knowledge_rows()
        measurements.append({'candidate_row_limit':count,'read_rows':len(result),'wall_seconds':round(perf_counter()-started,6),
                   'http_requests':len(server.requests),'response_bytes':sum(server.response_bytes),
                   'largest_response_bytes':max(server.response_bytes),'sqlite_seconds':round(sum(page['sqlite_seconds'] for page in server.pages),6),
                   'pages':list(server.pages)})
        assert len(result)==len(rows) and sum(len(row['event_json'].encode()) for row in result)==sum(len(row[6].encode()) for row in rows)
        assert server.open_streams==0
        del result
    sources=HostedSources(server.connection)
    digests={source['sha256'] for state in states for source in state['source_descriptors']}
    server.requests.clear();server.response_bytes.clear()
    started=perf_counter();sources.verify_many(digests,page_chunks=128)
    source_measure={'digests':len(digests),'wall_seconds':round(perf_counter()-started,6),'http_requests':len(server.requests),
                   'response_bytes':sum(server.response_bytes),'largest_response_bytes':max(server.response_bytes)}
finally:
    server.close()
print(json.dumps({'source_commit':'84f972c86fe556ccf5cac7e2aacddc6e154fdbb9','fixture':'24 native intakes with six original supporting files and eight frozen contexts each',
       'limitations':'MockHrana has no hosted transaction expiry or remote latency; these are offline size/SQL measurements, not a production cause determination',
       'first_candidate_count_and_event_bytes':candidates,'journal':measurements,'fresh_source_verification':source_measure},indent=2),flush=True)
