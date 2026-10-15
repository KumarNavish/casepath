import ast,hashlib,json,re,sys,time
from pathlib import Path
R=Path('/workspace/casepath-startup-gate-28247cbc-20261015');REPO=Path('/workspace/casepath-release-ae0-inventory')
pattern=re.compile(r'(?i)Bearer\s+[A-Za-z0-9._~+/=-]{16,}|\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16})\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
allowed={'ded144673eb432bbf8016c59507b47046a77932cffe21508eed4fcd60cfa9126':('casepath-api/tests/test_multi_agent_v15.py','test_response_bridge_classifies_sdk_429_once_without_raw_provider_material',2718),'1dbe343edf6cc7e5cf913289c6d6f679ccba13f3aa60476d7c76d1970f40f126':('casepath-api/tests/test_multi_agent_v15.py','test_response_bridge_classifies_top_level_upstream_rejection_without_raw',2663),'f75950e910c3440ad709f67cfdbec066352808f62e8111d13e7e2957f9915c8a':('casepath/tools/test_casepath_release.py','test_dynamic_runtime_acceptance_rejects_unsafe_successful_provenance',6599)}
manifest=json.loads((REPO/'casepath/source-manifest.json').read_text());sealed={x['path']:x for x in manifest['files']};collected=json.loads((R/'inventory/collected.json').read_text());occurrences={};values={}
files=[R/line.split('  ',1)[1] for line in (R/'raw-evidence-files-SHA256SUMS.txt').read_text().splitlines()]
for p in files:
 try:text=p.read_text()
 except UnicodeDecodeError:continue
 for m in pattern.finditer(text):
  sha=hashlib.sha256(m.group().encode()).hexdigest();assert sha in allowed,('Unproven credential pattern',p.relative_to(R).as_posix(),sha)
  values[sha]=m.group();occurrences.setdefault(sha,[]).append({'file':p.relative_to(R).as_posix(),'line':text.count('\n',0,m.start())+1})
rows=[]
for sha,value in values.items():
 file,function,line=allowed[sha];source=(REPO/file).read_text();sourcehash=hashlib.sha256((REPO/file).read_bytes()).hexdigest();assert sourcehash==sealed[file]['sha256'];tree=ast.parse(source);fn=next(x for x in ast.walk(tree) if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name==function)
 decorators=[x for d in fn.decorator_list for x in ast.walk(d)]
 if sha.startswith('f759'):
  expr=next(x for x in decorators if isinstance(x,ast.BinOp) and x.lineno==line and isinstance(x.op,ast.Add));literal=ast.literal_eval(expr.left)+ast.literal_eval(expr.right);assert literal==value and 'unit-test-placeholder' in literal;kind='Explicit unit-test-placeholder constant concatenation in negative provenance fixture'
 else:
  expr=next(x for x in decorators if isinstance(x,ast.Constant) and x.lineno==line and isinstance(x.value,str) and x.value.startswith('Bearer '));literal=expr.value;assert hashlib.sha256(literal.encode()).hexdigest()=='ac8b02ada5f1996a9e3fcddf3c654f2e4ac3d3d083eadc85db84735ee69f000b' and value.startswith(literal+'-');kind='Explicit RAW_HEADER_SENTINEL negative provider fixture plus exact pytest-generated parameter-ID suffix'
 matching_ids=[x['id'] for x in collected if x['id'].startswith(file+'::'+function+'[') and value in x['id']];assert len(matching_ids)==1
 rows.append({'candidate_sha256':sha,'candidate_length':len(value),'source_file':file,'source_line':line,'source_sha256':sourcehash,'source_expression_sha256':hashlib.sha256(ast.get_source_segment(source,expr).encode()).hexdigest(),'source_literal_sha256':hashlib.sha256(literal.encode()).hexdigest(),'fixture_test':function,'exact_collected_id_sha256':hashlib.sha256(matching_ids[0].encode()).hexdigest(),'classification':kind,'exact_occurrences':occurrences[sha]})
assert set(values)==set(allowed)
record={'candidate':'28247cbc87785b366fa542bb0aa0bd5f37e6c2e3','epoch':time.time(),'scan_pattern':pattern.pattern,'export_files_scanned':len(files),'exact_fixture_matches':len(rows),'unproven_matches':0,'real_credential_values_exported':False,'all_original_test_ids_preserved':True,'allowlist_scope':'Only these three exact observed match SHA256 values, each bound to an explicit sealed negative-test sentinel/placeholder expression and the exact current collected parameter ID; no broad prefix or file allowlist','source_manifest_sha256':hashlib.sha256((REPO/'casepath/source-manifest.json').read_bytes()).hexdigest(),'fixtures':rows}
if '--check-only' not in sys.argv:(R/'coordinator/export-secret-pattern-review.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k not in ['fixtures','scan_pattern']}))
