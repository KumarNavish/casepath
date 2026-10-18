from pathlib import Path
import json,collections,ast,xml.etree.ElementTree as ET,hashlib
R=Path('/workspace/scratch/casepath-final-gate-4f8269c1-20261018');m=json.loads((R/'shard-map.json').read_text());known={x['id']:x for x in json.loads((R/'known-skips.json').read_text())};totals=collections.Counter();summ=[];allids=[];allskips=set()
for n in range(1,7):
 p=R/f'shard{n}';expected=m['shards'][str(n)];ids=[x['id'] for x in json.loads((p/'collected.json').read_text())];assert ids==expected
 rows=[json.loads(x) for x in (p/'reports.jsonl').read_text().splitlines()];by=collections.defaultdict(list)
 for r in rows:by[r['id']].append(r)
 assert set(by)==set(ids)
 statuses={}
 for ident,rs in by.items():
  phases=[r['when'] for r in rs];assert len(phases)==len(set(phases)) and 'setup' in phases and 'teardown' in phases
  bad=[r for r in rs if r['outcome']=='failed'];skip=[r for r in rs if r['outcome']=='skipped']
  if bad:
   assert len(bad)==1 and not skip;statuses[ident]='error' if bad[0]['when']=='setup' else 'failure'
  elif skip:
   assert len(skip)==1 and ident in known; a=ast.literal_eval(skip[0]['skip_reason']);b=ast.literal_eval(known[ident]['skip_reason']);assert skip[0]['when']==known[ident]['when'] and Path(a[0]).name==Path(b[0]).name and a[1:]==b[1:]
   statuses[ident]='skip';allskips.add(ident)
  else:assert set(phases)=={'setup','call','teardown'} and all(r['outcome']=='passed' for r in rs);statuses[ident]='pass'
 cases=ET.parse(p/'junit.xml').findall('.//testcase');assert len(cases)==len(ids)
 matched=[]
 for c in cases:
  ms=[]
  for i in ids:
   parts=i.split('::');suffix=Path(parts[0]).stem+('.'+'.'.join(parts[1:-1]) if len(parts)>2 else '')
   if c.attrib['name']==parts[-1] and (not c.attrib['classname'] or c.attrib['classname']==suffix or c.attrib['classname'].endswith('.'+suffix)):ms.append(i)
  assert len(ms)==1;ident=ms[0];matched.append(ident)
  actual='error' if c.find('error') is not None else 'failure' if c.find('failure') is not None else 'skip' if c.find('skipped') is not None else 'pass';assert actual==statuses[ident]
 assert len(matched)==len(set(matched)) and set(matched)==set(ids)
 before=json.loads((p/'source-before/capsule-verification.json').read_text());after=json.loads((p/'source-after/capsule-verification.json').read_text());assert before['capsule_receipt']==after['capsule_receipt'] and before['head']==after['head']==m['candidate'] and before['status']==after['status']=='' and before['sealed_files_verified']==after['sealed_files_verified']==1719
 count=collections.Counter(statuses.values());totals.update(count);allids+=ids;summ.append({'shard':n,'counts':dict(count),'raw_phases':len(rows),'junit_cases':len(cases),'source_capsule_before_after_equal':True,'result':json.loads((p/'worker-terminal.json').read_text())})
assert len(allids)==len(set(allids))==2715 and allskips==set(known)
out={'candidate':m['candidate'],'original_attempts_only':True,'gate_passed':False,'Cloud_unique_ids':2715,'full_inventory_with_Mac127':2842,'counts':dict(totals),'same10_skip_reasons_lines_and_phases':True,'all_raw_phase_and_JUnit_outcomes_reconciled':True,'no_missing_or_duplicate_assigned_ids':True,'shards':summ,'qualification':'50 historical-object setup errors +1 reassessment deadline failure retained. Original shard1 derived runtime bytecode cache delta documented separately. Recovery whole-shard attempts3/4 explicitly authorized; diagnostic6 is not admission.'}
(R/'coordinator/original-terminal-reconciliation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'counts':dict(totals),'Cloud_unique_ids':2715,'gate_passed':False}))
