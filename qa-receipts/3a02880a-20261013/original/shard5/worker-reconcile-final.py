import collections, json, time, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path('/workspace/casepath-smooth-stage-gate-3a02880a-20261013')
OUT=ROOT/'shard5'
SHA='3a02880abc3f824e06e5e31a888dc91edf1bcb9d'
assigned=json.loads((ROOT/'shard-map.json').read_text())['shards']['5']
collected_rows=json.loads((OUT/'collected.json').read_text())
collected=[x['id'] for x in collected_rows]
rows=[json.loads(x) for x in (OUT/'reports.jsonl').read_text().splitlines()]
result=json.loads((OUT/'result.json').read_text())
xml=ET.parse(OUT/'junit.xml')
tests=xml.findall('.//testcase')
from _pytest.junitxml import mangle_test_address, bin_xml_escape
def junit_key(row):
    names=mangle_test_address(row['pytest_nodeid'])
    return ('.'.join(names[:-1]),bin_xml_escape(names[-1]))
keys={junit_key(x):x['id'] for x in collected_rows}
unmatched=[]
junit_ids=[]
junit_rows=[]
for testcase in tests:
    key=(testcase.get('classname'),testcase.get('name'))
    nodeid=keys.get(key)
    if nodeid is None: unmatched.append({'classname':key[0],'name':key[1]})
    else: junit_ids.append(nodeid)
    outcome='passed'
    for tag in ('skipped','failure','error'):
        child=testcase.find(tag)
        if child is not None:
            outcome=tag
            break
    junit_rows.append({'id':nodeid,'outcome':outcome,'duration_seconds':float(testcase.get('time','0'))})
phase_counts=collections.Counter((x['id'],x['when']) for x in rows)
phase_anomalies=[]
for nodeid in assigned:
    for phase in ('setup','call','teardown'):
        count=phase_counts[(nodeid,phase)]
        if count!=1: phase_anomalies.append({'id':nodeid,'when':phase,'count':count})
raw_ids={x['id'] for x in rows}
known_skip='casepath-api/tests/test_document_lifecycle_shadow_v1.py::test_frozen_base27_prefix_replay_reproduces_all_six_workflows'
skips=[x for x in rows if x['outcome']=='skipped']
known_skips_only=not skips  # No known fixture-skip node is assigned to shard 5.
failed=[x for x in rows if x['outcome']=='failed']
log=(OUT/'pytest.log').read_text()
checks={'assigned_unique':len(set(assigned))==len(assigned),'collected_exact':collections.Counter(assigned)==collections.Counter(collected),'junit_exact':collections.Counter(assigned)==collections.Counter(junit_ids) and not unmatched,'junit_unique':len(set(junit_ids))==len(junit_ids),'raw_ids_exact':set(assigned)==raw_ids,'raw_setup_call_teardown_exact':not phase_anomalies,'no_deselections':'deselected' not in log,'known_fixture_skips_only':known_skips_only,'clean_exact_source_after':result['after_head']==SHA and not result['after_status']}
record={'candidate':SHA,'shard':5,'verified_epoch':time.time(),'counts':{'assigned':len(assigned),'collected':len(collected),'junit':len(tests),'raw_rows':len(rows),'passed':sum(x['outcome']=='passed' for x in junit_rows),'failed':sum(x['outcome']=='failure' for x in junit_rows),'errors':sum(x['outcome']=='error' for x in junit_rows),'skipped':sum(x['outcome']=='skipped' for x in junit_rows),'raw_phase_outcomes':dict(collections.Counter(x['when']+':'+x['outcome'] for x in rows))},'checks':checks,'all_checks_pass':all(checks.values()),'missing_collected':sorted(set(assigned)-set(collected)),'extra_collected':sorted(set(collected)-set(assigned)),'missing_junit':sorted(set(assigned)-set(junit_ids)),'unmatched_junit':unmatched,'missing_raw_ids':sorted(set(assigned)-raw_ids),'extra_raw_ids':sorted(raw_ids-set(assigned)),'raw_phase_anomalies':phase_anomalies,'failure_nodeids':sorted({x['id'] for x in failed}),'failures':failed,'skips':skips,'known_fixture_skip_nodeids_assigned':[],'junit_mapping':'pytest collected nodeid via _pytest.junitxml.mangle_test_address and bin_xml_escape','supersedes_evidence_mapper_only':'worker-reconciliation.json','runner_exit_code':result['exit_code'],'runner_duration_seconds':result['duration_seconds'],'junit_suite_attributes':[dict(x.attrib) for x in xml.findall('.//testsuite')],'raw_total_duration_seconds':sum(x['duration'] for x in rows),'slowest_cases':sorted(junit_rows,key=lambda x:x['duration_seconds'],reverse=True)[:10]}
with (OUT/'worker-reconciliation-final.json').open('x') as f: json.dump(record,f,indent=2)
print(json.dumps({k:record[k] for k in ['candidate','shard','counts','checks','all_checks_pass','failure_nodeids','skips','runner_exit_code','runner_duration_seconds','junit_suite_attributes','raw_total_duration_seconds','slowest_cases']},indent=2))
raise SystemExit(0 if record['all_checks_pass'] else 1)
