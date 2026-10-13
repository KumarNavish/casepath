import collections, hashlib, json, shutil, time
from pathlib import Path
ROOT=Path('/workspace/casepath-smooth-stage-gate-3a02880a-20261013')
SHA='3a02880abc3f824e06e5e31a888dc91edf1bcb9d'
REPO=Path('/workspace/casepath-release-ae0-inventory')
BASE=Path('/workspace/casepath-quiet-completion-recheck-0d9f9e22-20261013/selected')
rows=json.loads((ROOT/'inventory/collected.json').read_text())
ids=[row['id'] for row in rows]
assert len(ids)==len(set(ids))==2571
macfiles={'casepath-api/tests/test_cli_v1.py':69,'casepath-api/tests/test_local_data_root.py':52,'casepath-api/tests/test_journal_corpus_restart.py':6}
mac=[row['id'] for row in rows if row['file'] in macfiles]
assert collections.Counter(row['file'] for row in rows if row['file'] in macfiles)==macfiles
assert len(mac)==len(set(mac))==127
cloud=set(ids)-set(mac)
prior=json.loads((ROOT/'prior-shard-map.json').read_text())
shards=prior['shards']
assigned=[item for values in shards.values() for item in values]
assert len(assigned)==len(set(assigned))==2444 and set(assigned)==cloud
assert set(assigned).isdisjoint(mac) and set(assigned)|set(mac)==set(ids)
def save_ids(name,values):
    raw=('\n'.join(sorted(values))+'\n').encode()
    (ROOT/name).write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()
hashes={'full_ids_sha256':save_ids('collected-ids.txt',ids),'cloud_ids_sha256':save_ids('cloud-assigned-ids.txt',assigned),'mac_ids_sha256':save_ids('mac-ids.txt',mac)}
counts={key:len(value) for key,value in shards.items()}
record=dict(prior)
record.update(candidate=SHA,sealed_sha=SHA,provisional=False,basis='Exact prior successful six-shard assignments retained; fresh2571 collection verified; prior actual per-test/file timing evidence retained',shards=shards,counts=counts,prior_candidate=prior['candidate'],fresh_inventory_verified_epoch=time.time())
(ROOT/'shard-map.json').write_text(json.dumps(record,indent=2))
proof={'candidate':SHA,'full_inventory':2571,'cloud_assigned':2444,'mac_excluded':127,'mac_per_file':macfiles,'counts':counts,'unique_shard_assignments':True,'cloud_mac_disjoint':True,'union_equals_full':True,'missing':[],'extra':[],'duplicates':[],'deselected':[],'tests_launched':False,**hashes}
(ROOT/'proof-disjoint-union-before.json').write_text(json.dumps(proof,indent=2))
baseline=json.loads((BASE/'known-skip-source-comparison.json').read_text())
skips=[]
for row in baseline['records']:
    raw=(REPO/row['source']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==row['source_sha256']
    assert raw.decode().splitlines()[row['line']-1]==row['source_line_text']
    assert row['id'] in cloud
    skips.append(dict(row,source_bytes_unchanged=True))
assert len(skips)==10
(ROOT/'known-skip-source-comparison.json').write_text(json.dumps({'candidate':SHA,'baseline_candidate':baseline['candidate'],'count':10,'equal_ids_phases_source_lines_reasons_by_unchanged_source':True,'all_ids_collected_and_assigned':True,'added_skip_or_deselection_directives':[],'records':skips},indent=2))
shutil.copy2(REPO/'casepath/source-manifest.json',ROOT/'source-manifest.json')
assert hashlib.sha256((ROOT/'source-manifest.json').read_bytes()).hexdigest()=='ead2ad3ddd10000737985f7db5d704b5e7366da72b54e371624f1a0709ac5c39'
print(json.dumps(proof))
