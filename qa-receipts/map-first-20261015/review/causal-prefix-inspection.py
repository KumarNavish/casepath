import hashlib,json
from pathlib import Path
p=Path('/workspace/operation-runtime-evidence/native-sidecars/clm_314f2d309fea25e6.json');j=json.loads(p.read_text());ops=[r for r in j['frames'] if r['type']=='operation'];by={r['id']:r for r in ops}
def ancestors(row,prior):
    found=set();todo=list(row['cause_ids'])
    while todo:
        identity=todo.pop()
        if identity in found:continue
        assert identity in prior
        found.add(identity);todo.extend(prior[identity]['cause_ids'])
    return [prior[x] for x in found]
rows=[]
for seq in (12,13,36,37,38,39,40,41):
    row=ops[seq-1];prior={r['id']:r for r in ops[:seq-1]};chain=ancestors(row,prior);opens={r['id'] for r in chain if r['kind']=='source.open'};candidates=[]
    for other in prior.values():
        if other['kind']!='fact.extract' or not other['input'].get('document_type'):continue
        if any(other['source'].get(k)!=row['source'].get(k) for k in ('artifact_id','sha256','text_sha256')):continue
        shared=[a for a in ancestors(other,prior) if a['id'] in opens]
        if shared:candidates.append({'seq':other['seq'],'document_type':other['input']['document_type'],'shared_source_open_seq':[r['seq'] for r in shared],'same_direct_cause':bool(set(other['cause_ids'])&set(row['cause_ids']))})
    rows.append({'seq':seq,'fact_id':row['object']['id'],'native_operation_id':row['id'],'native_operation_sha256':row['operation_sha256'],'native_source_pin':{k:row['source'][k] for k in ('artifact_id','sha256','text_sha256','start_char','end_char')},'source_open_ancestor_seq':[r['seq'] for r in chain if r['kind']=='source.open'],'prior_document_fact_associations':candidates})
node_conditions={};expressions=set()
for row in ops:
    if row['kind']=='process.inspect':
        for node in row['result']['graph']['nodes']:node_conditions.setdefault(node['node_id'],set()).add(json.dumps({k:v for k,v in node.items() if 'condition' in k},sort_keys=True))
    if row['kind']=='condition.evaluate':expressions.add(json.dumps(row['input']['expression'],sort_keys=True))
print(json.dumps({'scope':'Read-only existing synthetic native1.1 trace. Relation extraction uses only actual operation causes and preceding document-fact operations. Source-context association is provisional and does not claim a unique legal consumer, accepted evidence sufficiency, requirement activation, or completion. No current/future head facts are used for association.','native_sidecar_file_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows':rows,'all_native_node_condition_fields':{k:sorted(v) for k,v in node_conditions.items()},'unique_condition_evaluate_expressions':sorted(expressions)},indent=2))
