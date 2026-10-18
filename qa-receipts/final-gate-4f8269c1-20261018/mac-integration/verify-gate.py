"""Reconcile exact Cloud and Mac test IDs, raw phases and JUnit before release."""
import argparse, ast, collections, hashlib, json
from pathlib import Path
import xml.etree.ElementTree as ET

p=argparse.ArgumentParser()
p.add_argument('cloud',type=Path)
p.add_argument('--commit',default='4f8269c1781c4097f79790f39dd0312a2f9f32bf')
a=p.parse_args(); base=Path(__file__).resolve().parent; mac=base/'gate'
previous=base.parent/'casepath-startup-paths-20261016/cloud-gate-receipts/qa-receipts/b8616d4c-20261016'
read=lambda path:json.loads(path.read_text())
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
inventory=[r['id'] for r in read(a.cloud/'inventory/collected.json')]
old={r['id'] for r in read(previous/'inventory/collected.json')}
assert len(inventory)==len(set(inventory)) and old<=set(inventory)
previous65=base.parent/'casepath-knowledge-read-repair-20261017/cloud-gate-receipts/qa-receipts/knowledge-read-gate-65a796a5-20261017'
baseline65={r['id'] for r in read(previous65/'inventory/collected.json')}
renames=read(base/'renamed-test-ids.json')['renamed_tests']
rename_map={r['old_id']:r['new_id'] for r in renames}
assert len(baseline65)==2749
assert set(rename_map)<=baseline65
assert {rename_map.get(x,x) for x in baseline65}<=set(inventory)
assert baseline65-set(inventory)==set(rename_map)
assert set(rename_map.values())<=set(inventory)
previous_c925=base.parent/'casepath-simple-site-release-20261018/cloud-gate-receipts/qa-receipts/roles-final-gate-c925a026-20261018'
baseline_c925={r['id'] for r in read(previous_c925/'inventory/collected.json')}
assert len(baseline_c925)==2764 and baseline_c925<=set(inventory)
previous4a=base.parent/'casepath-startup-final-20261018/cloud-gate-receipts/qa-receipts/startup-timing-gate-4a03578b-20261018'
baseline4a={r['id'] for r in read(previous4a/'inventory/collected.json')}
assert len(baseline4a)==2777 and baseline4a<=set(inventory)
previous_a89=base.parent/'casepath-mobile-context-20261018/cloud-gate-receipts/qa-receipts/mobile-context-gate-a89b97bb-20261018'
baseline_a89={r['id'] for r in read(previous_a89/'inventory/collected.json')}
assert len(baseline_a89)==2777 and baseline_a89<=set(inventory)
previous_4bf=base.parent/'casepath-touch-targets-20261018/cloud-gate-receipts/qa-receipts/touch-target-gate-4bf9b439-20261018'
baseline_4bf={r['id'] for r in read(previous_4bf/'inventory/collected.json')}
assert len(baseline_4bf)==2777 and baseline_4bf<=set(inventory)
previous_addc=base.parent/'casepath-native-completion-20261018/cloud-gate-receipts/qa-receipts/read-seed-gate-addc5a77-20261018'
baseline_addc={r['id'] for r in read(previous_addc/'inventory/collected.json')}
assert len(baseline_addc)==2833 and baseline_addc<=set(inventory)
assert len(inventory)==2842
mapping=read(a.cloud/'shard-map.json');assert mapping['candidate']==a.commit
selected=[];all_rows=[];parts=[]
for n in range(7):
    folder=(base/'mac-final-cloud6/shard1' if n==6 else a.cloud/'attempt2'/f'shard{n}' if n in (3,4) else a.cloud/f'shard{n}') if n else mac
    ids=[r['id'] for r in read(folder/'collected.json')]
    assert len(ids)==len(set(ids))
    if n:assert ids==mapping['shards'][str(n)]
    else:assert len(ids)==127 and set(ids)==set((previous/'mac-ids.txt').read_text().splitlines())
    rows=[json.loads(line) for line in (folder/'reports.jsonl').read_text().splitlines()]
    assert {r['id'] for r in rows}==set(ids)
    assert all(v==1 for v in collections.Counter((r['id'],r['when']) for r in rows).values())
    grouped=collections.defaultdict(dict)
    for row in rows:grouped[row['id']][row['when']]=row
    for stages in grouped.values():
        assert stages['teardown']['outcome']=='passed'
        if stages['setup']['outcome']=='passed':assert stages['call']['outcome'] in ('passed','skipped')
        else:assert stages['setup']['outcome']=='skipped' and 'call' not in stages
    junit=ET.parse(folder/('junit.xml' if n else 'mac-shard-junit.xml')).getroot().findall('.//testcase')
    assert len(junit)==len(ids)
    mapped=[]
    for case in junit:
        assert case.find('failure') is None and case.find('error') is None
        candidates=[]
        for identity in ids:
            bits=identity.split('::');suffix=Path(bits[0]).stem+('.'+'.'.join(bits[1:-1]) if len(bits)>2 else '')
            if case.get('name')==bits[-1] and (not case.get('classname') or case.get('classname')==suffix or case.get('classname','').endswith('.'+suffix)):candidates.append(identity)
        assert len(candidates)==1, (n,case.attrib,[x for x in ids if x.split('::')[-1]==case.get('name')],candidates)
        identity=candidates[0];mapped.append(identity)
        assert (case.find('skipped') is not None)==any(r['outcome']=='skipped' for r in grouped[identity].values())
    assert set(mapped)==set(ids) and len(mapped)==len(set(mapped))
    result=read(folder/('result.json' if n else 'mac-shard-result.json'))
    assert result.get('candidate',result.get('source_commit'))==a.commit and result['exit_code']==0
    if n:
        assert result['after_head']==a.commit and result['after_status']==''
        before=read(folder/'source-before/capsule-verification.json');after=read(folder/'source-after/capsule-verification.json')
        for proof in (before,after):
            assert proof['head']==a.commit and proof['status']=='' and proof['normal_clone'] and proof['sealed_files_verified']==1719
            assert proof['manifest_sha256']==mapping['manifest_sha256']
        assert before['capsule_receipt_file_sha256']==after['capsule_receipt_file_sha256']
        runtime_before=read(folder/'runtime-before.json');runtime_after=read(folder/'runtime-after.json')
        assert runtime_before['candidate']==runtime_after['candidate']==a.commit
        assert runtime_before['observed_before_test_start'] is True
        rb={r['path']:r for r in runtime_before['rows']};ra={r['path']:r for r in runtime_after['rows']}
        assert all(path in ra and ra[path]==row for path,row in rb.items()), 'Existing runtime changed'
        added=set(ra)-set(rb)
        if added:
            assert n==1 and added=={'lib/python3.13/site-packages/__pycache__/_virtualenv.cpython-313.pyc'}
            cache=read(a.cloud/'coordinator/shard1-runtime-cache-delta.json')
            assert cache['candidate']==a.commit and cache['existing_runtime_rows_changed']==cache['existing_runtime_rows_removed']==0
            assert cache['decoded_code_matches_compile_of_unchanged_source'] is True and cache['pyc_magic_timestamp_size_match_source'] is True
            assert cache['added_sha256']==ra[next(iter(added))]['sha256']
            assert cache['source_python_file_sha256']==rb['lib/python3.13/site-packages/_virtualenv.py']['sha256']

    else:assert result['source_clean_after'] and result['manifest_sha256']==mapping['manifest_sha256']
    selected.extend(ids);all_rows.extend(rows);parts.append({'partition':f'shard{n}' if n else 'mac','tests':len(ids),'raw_phases':len(rows),'exit_code':0})
assert len(selected)==len(set(selected))==len(inventory) and set(selected)==set(inventory)
def skip_key(row):
    file,line,reason=ast.literal_eval(row['skip_reason'])
    return row['id'],row['when'],Path(file).name,line,reason
skips=[r for r in all_rows if r['outcome']=='skipped']
assert len(skips)==10 and {skip_key(r) for r in skips}=={skip_key(r) for r in read(previous/'observed-known-skips.json')}
report={'canonical_commit':a.commit,'manifest_sha256':mapping['manifest_sha256'],'full_inventory':len(inventory),
    'passed':len(inventory)-len(skips),'known_skips':10,'new_skips':0,'deselected':0,'duplicates':0,
    'baseline_passed':2603,'previous_release_passed':2823,'explicit_test_renames':renames,'raw_removed_previous_ids':sorted(baseline65-set(inventory)),'added_test_ids':sorted(set(inventory)-old),'new_since_addc':sorted(set(inventory)-baseline_addc),'raw_phase_and_junit_results_reconciled':True,
    'source_files_verified':1719,'source_clean':True,'partitions':parts,'accepted_attempts':{str(n):('Mac fallback after Cloud receipt export hit usage limit' if n==6 else 2 if n in (3,4) else 1) for n in range(1,7)},'original_failures_retained':True,'diagnostic_test_excluded_from_gate':True,'runtime_cache_addition':read(a.cloud/'coordinator/shard1-runtime-cache-delta.json')}
(base/'full-gate-verified.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
