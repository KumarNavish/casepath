"""Temporary SQL comparison only; authored source stays unchanged at 84."""
import json
from pathlib import Path
import sqlite3
from time import perf_counter
import httpx
from casepath_api.autonomous_store_v1 import SESSION_ID
from casepath_api.hosted_storage_v1 import HostedAutonomousStore, HostedJournal, HostedSources
from casepath_api.hosted_sql_v1 import _decode
from hosted_hrana_fixture import MockHrana

root=Path('/workspace/knowledge-read-repair-20261016/projection/t/metadata-window')
root.mkdir(exist_ok=False)
source=Path('/workspace/knowledge-read-repair-20261016/projection/t/large-native/hosted.sqlite3')
with sqlite3.connect(source) as original,sqlite3.connect(root/'probe.sqlite3') as target:
    original.backup(target)
    target.execute('ALTER TABLE claim_loop_events RENAME TO accepted_fixture_events')
    target.execute('CREATE VIEW claim_loop_events AS SELECT *, observe_payload(event_json) AS payload_probe FROM accepted_fixture_events')
columns=('session_id','loop_id','sequence','idempotency_key','command_sha256','event_sha256','event_json','created_at')
size='+'.join('COALESCE(length(CAST('+key+' AS BLOB)),0)' for key in columns)+'+1024'
late_query=('SELECT j.*,p.__read_size,p.__read_total,p.__read_position,p.__read_candidates FROM '
 '(SELECT *,sum(__read_size) OVER (ORDER BY loop_id,sequence) AS __read_total,'
 'row_number() OVER (ORDER BY loop_id,sequence) AS __read_position,count(*) OVER () AS __read_candidates FROM '
 '(SELECT session_id,loop_id,sequence,('+size+') AS __read_size FROM claim_loop_events WHERE session_id=? '
 'AND (? OR loop_id>? OR (loop_id=? AND sequence>?)) ORDER BY loop_id,sequence LIMIT ?)) AS p '
 'CROSS JOIN claim_loop_events AS j WHERE (p.__read_total<=? OR p.__read_position=1) '
 'AND j.session_id=p.session_id AND j.loop_id=p.loop_id AND j.sequence=p.sequence ORDER BY p.loop_id,p.sequence')

class Probe(MockHrana):
    def __init__(self,path):
        super().__init__(path)
        self.variant='original';self.pages=[];self.response_bytes=[]
    def _statement(self,connection,stmt):
        observations=[]
        connection.create_function('observe_payload',1,lambda value:(observations.append(len(value.encode())),1)[1])
        if not stmt['sql'].startswith('SELECT * FROM ('):
            return super()._statement(connection,stmt)
        sql=late_query if self.variant=='metadata_join' else stmt['sql']
        started=perf_counter()
        cursor=connection.execute(sql,tuple(_decode(arg) for arg in stmt.get('args',[])))
        rows=cursor.fetchall();elapsed=perf_counter()-started
        names=[col[0] for col in cursor.description or ()]
        self.pages.append({'returned_rows':len(rows),'candidate_rows':rows[0][names.index('__read_candidates')] if rows else 0,
              'returned_event_bytes':sum(len(row[names.index('event_json')].encode()) for row in rows),
              'full_payload_evaluations':len(observations),'evaluated_event_bytes':sum(observations),
              'sqlite_seconds':round(elapsed,6)})
        return {'cols':[{'name':name,'decltype':None} for name in names],
                'rows':[[self._value(value) for value in row] for row in rows],
                'affected_row_count':max(0,cursor.rowcount),'last_insert_rowid':str(cursor.lastrowid) if cursor.lastrowid is not None else None}
    def handle(self,request):
        result=super().handle(request);self.response_bytes.append(len(result.content));return result

server=Probe(root/'probe.sqlite3')
class ReadOnlyJournal:
    path=root/'unused'
    connect=server.connection
expected=None;measurements=[]
httpx.HTTPTransport.handle_request=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Unexpected network/provider dispatch'))
try:
    for variant in ('original','metadata_join'):
        server.variant=variant
        for count in (128,2048):
            store=HostedAutonomousStore(ReadOnlyJournal.path,journal=ReadOnlyJournal(),source_store=HostedSources(server.connection))
            store.KNOWLEDGE_PAGE_ROWS=count
            server.requests.clear();server.pages.clear();server.response_bytes.clear()
            started=perf_counter();rows=store._knowledge_rows();elapsed=perf_counter()-started
            # Equality checks every returned SQL column, including the extra authority column.
            identity=store._journal_snapshot(rows)
            if expected is None:expected=identity
            assert identity==expected and all(row['payload_probe']==1 for row in rows)
            measurements.append({'variant':variant,'candidate_limit':count,'returned_rows':len(rows),
                  'sqlite_seconds':round(sum(page['sqlite_seconds'] for page in server.pages),6),
                  'wall_seconds':round(elapsed,6),'http_requests':len(server.requests),
                  'response_bytes':sum(server.response_bytes),'largest_response_bytes':max(server.response_bytes),
                  'full_payload_evaluations':sum(page['full_payload_evaluations'] for page in server.pages),
                  'evaluated_event_bytes':sum(page['evaluated_event_bytes'] for page in server.pages),
                  'first_page':server.pages[0]})
            assert server.open_streams==0
            del rows,identity
finally:server.close()
print(json.dumps({'source_commit':'84f972c86fe556ccf5cac7e2aacddc6e154fdbb9','purpose':'temporary SQL probe; no authored source changes or hosted calls',
      'same_snapshot_and_all_column_identity':True,'measurements':measurements},indent=2))
