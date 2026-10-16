"""Capture exact native query construction without opening a database/network."""
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from casepath_api.hosted_storage_v1 import HostedAutonomousStore
root=Path('/workspace/knowledge-read-repair-20261016/projection/e')
spec=importlib.util.spec_from_file_location('casepath_api._baseline_sql_capture',root/'baseline_hosted_storage_84.py')
old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
class Captured(Exception):pass
class Capture:
    def connect(self):return self
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,parameters=()):
        if sql.startswith('SELECT'):
            self.sql,self.parameters=sql,parameters
            raise Captured
        assert sql=='BEGIN'
for name,kind in [('baseline-84',old.HostedAutonomousStore),('metadata-window',HostedAutonomousStore)]:
    capture=Capture();store=object.__new__(kind);store.journal=capture
    try:store._knowledge_rows()
    except Captured:pass
    root.joinpath(name+'.sql').write_text(capture.sql)
    parameters=[int(value) if isinstance(value,bool) else value for value in capture.parameters]
    receipt={'name':name,'sql_sha256':sha256(capture.sql.encode()).hexdigest(),'sql_bytes':len(capture.sql.encode()),
             'parameters':parameters,'parameter_schema':[
                 {'position':1,'name':'session_id','type':'text'},
                 {'position':2,'name':'first_page','type':'integer','description':'1 on first page; 0 thereafter'},
                 {'position':3,'name':'after_loop','type':'text'},
                 {'position':4,'name':'after_loop_repeat','type':'text'},
                 {'position':5,'name':'after_sequence','type':'integer'},
                 {'position':6,'name':'candidate_row_limit','type':'integer'},
                 {'position':7,'name':'page_bytes','type':'integer'}],
             'notes':'Read-only SELECT; use existing native BEGIN/page validation/COMMIT. All journal SQL columns retained. No UDF/probe or credentials.'}
    root.joinpath(name+'.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,sort_keys=True))
