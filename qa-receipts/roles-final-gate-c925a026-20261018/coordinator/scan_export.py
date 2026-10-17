import hashlib,json,re,subprocess,tarfile,time
from pathlib import Path
R=Path('/workspace/casepath-roles-final-gate-c925a026-20261018');repo=Path(json.loads((R/'clone-map.json').read_text())['repos']['1'])
excluded={'home','tmp','pycache','uv-cache','artifact-registry','pytest-tmp','__pycache__'}
patterns={'bearer':r'(?i)Bearer\s+[A-Za-z0-9._~+/-]{8,}','private_key':r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----','openai_style':r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}','aws_access':r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b','github_token':r'\b(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}'}
allow=json.loads((R/'secret-scan-exact-allowlist.json').read_text());approved={}
ids=set((R/'collected-ids.txt').read_text().splitlines())
for row in allow:
 raw=(repo/row['source']).read_bytes();assert hashlib.sha256(raw).hexdigest()==row['source_sha256'] and raw==subprocess.check_output(['git','show','65a796a5dfb21f4cdbe0a3d1a4925b931710b30c:'+row['source']],cwd=repo)
 assert row['exact_parameterized_id'] in ids and hashlib.sha256(row['literal'].encode()).hexdigest()==row['match_sha256']
 approved[(row['kind'],row['match_sha256'])]=row['literal']
unknown=[];counts={};files=0;members=0
def scan(label,raw):
 global files
 files+=1;text=raw.decode(errors='replace')
 for kind,pattern in patterns.items():
  for m in re.finditer(pattern,text):
   value=m.group();sha=hashlib.sha256(value.encode()).hexdigest();key=(kind,sha)
   if key not in approved or approved[key]!=value:unknown.append({'file':label,'kind':kind,'sha256':sha,'line':text[:m.start()].count('\n')+1})
   else:counts[kind+':'+sha]=counts.get(kind+':'+sha,0)+1
for p in sorted(R.rglob('*')):
 if not p.is_file() or p.is_symlink() or any(x in excluded for x in p.relative_to(R).parts):continue
 if p.suffix in {'.py','.json','.jsonl','.txt','.log','.xml'}:scan(p.relative_to(R).as_posix(),p.read_bytes())
 elif p.name.endswith('.tar.gz'):
  with tarfile.open(p,'r:gz') as t:
   for member in t.getmembers():
    if member.isfile() and not member.name.endswith('.tar.gz'):
     members+=1;scan(p.relative_to(R).as_posix()+'::'+member.name,t.extractfile(member).read())
record={'candidate':json.loads((R/'clone-map.json').read_text())['candidate'],'files_and_archive_members_scanned':files,'archive_members_scanned':members,'unknown_matches':unknown,'unknown_match_count':len(unknown),'exact_allowlisted_matches':counts,'allowlist_file_sha256':hashlib.sha256((R/'secret-scan-exact-allowlist.json').read_bytes()).hexdigest(),'source_literals_or_names_verified_byte_unchanged_against_baseline':True,'raw_ids_redacted':False,'generic_patterns_disabled':False,'scan_scope':'Selected QA receipts and raw archive text members; no runtime environment or credential files read','epoch':time.time()}
(R/'export-secret-scan.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));assert not unknown,'Unclassified secret-like export match'
