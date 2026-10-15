import json,time
from pathlib import Path
R=Path('/workspace/casepath-saved-history-gate-5086624c-20261015')
SHA='5086624c8a024ba298819e5e27d749efbd0cc7fc'
original=(R/'all-shard-terminal.json').read_bytes(); prior=json.loads(original)
assert prior['candidate']==SHA and not prior['all_executed'] and not prior['all_green']
assert len(prior['results'])==6 and [x for x in prior['results'] if 'blocked' in x]==[next(x for x in prior['results'] if x['shard']==6)]
assert next(x for x in prior['results'] if x['shard']==6)['blocked']=='resource headroom'
last=json.loads((R/'shard6-terminal.json').read_text()); assert last['shard']==6 and last['attempt_count']==1
actual=[x if x['shard']!=6 else last for x in prior['results']]
assert all('exit_code' in x and 'source_after_exit_code' in x and x['attempt_count']==1 for x in actual)
assert all((R/f'shard{x["shard"]}/result.json').exists() and (R/f'shard{x["shard"]}/source-after/capsule-verification.json').exists() for x in actual)
with (R/'all-shard-terminal-initial-resource-block.json').open('xb') as f:f.write(original)
out={'candidate':SHA,'epoch':time.time(),'results':actual,'all_executed':True,'all_green':all(x['exit_code']==0 and x['source_after_exit_code']==0 for x in actual),'preserved_original_dispatcher_resource_block_record':'all-shard-terminal-initial-resource-block.json','shard6_test_execution_was_initial_attempt_not_retry':True}
(R/'all-shard-terminal.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
