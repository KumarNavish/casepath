from pathlib import Path
import json,hashlib,time,subprocess,ast
R=Path('/workspace/casepath-read-seed-gate-addc5a77-20261018');P=Path('/workspace/casepath-outcome-wait-gate-8f230fd4-20261018');SHA='addc5a77748ebb7cb534ca1b31ac37cd0a3bfa59';MAN='0d713ebe1ea45681c139ac8ed39b5d9c811cdfb6ea08af55617e155ecf60c2b8';G=Path('/workspace/casepath-transport-gate-evidence-git-20261015')
def save(n,x):(R/n).write_text(json.dumps(x,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
mac=json.loads((R/'mac-owner-attestation.json').read_text());mac.update(owner='Mac integration owner via root',partition='test_cli_v1.py69/test_local_data_root.py52/test_journal_corpus_restart.py6',raw_receipts_inspected_in_cloud=False,attempt_count=1,raw_phase_rows_owner_reported=381,execution='Once-only unchanged127 partition; current candidate',source_clean_before_after_owner_reported=True,source_all1718_manifest_verified_owner_reported=True,raw_receipts_retained_by_owner=True,qualification='Current exact addc owner attestation; Cloud did not execute or inspect Mac raw evidence');save('mac-owner-attestation.json',mac)
pinned=json.loads((P/'pinned-shared-tool-identities.json').read_text())
for row in pinned['tools']:assert sha(Path(row['path']))==row['sha256']
pinned.update(epoch=time.time(),versions_reused_from_prior_verified_identical_executable_bytes=True,prior_receipt=str(P/'pinned-shared-tool-identities.json'));save('pinned-shared-tool-identities.json',pinned)
audit=json.loads((P/'migration-process-audit.json').read_text());audit.update(candidate=SHA,prior_observation_candidate=audit['candidate'],prior_observation_receipt=str(P/'migration-process-audit.json'),observed_in_current_gate=False,current_mac127_owner_attestation_received=True,qualification='Prior supported-host limitation preserved; no new proc1 maps or environment probe attempted. Guard source unchanged and current exact Mac127 partition passed by owner attestation.');save('migration-process-audit.json',audit)
full=set((R/'collected-ids.txt').read_text().splitlines());baselines=[]
for name in ['prior-collected-ids.txt','4bf-collected-ids.txt','a89-collected-ids.txt','b861-collected-ids.txt']:
 p=R/'coordinator'/name;ids=p.read_text().splitlines();assert len(ids)==len(set(ids)) and set(ids)<=full;baselines.append({'file':str(p),'count':len(ids),'sha256':sha(p),'exact_subset':True})
save('baseline-inclusion-proof.json',{'candidate':SHA,'full_count':len(full),'baselines':baselines,'renames':[],'removed_ids':[]})
repo=Path(json.loads((R/'clone-map.json').read_text())['repos']['1']);bindings=[]
for commit,paths in [('af78642d485e050674b462718517f6e2cadaa308',['casepath-api/casepath_api/hosted_read_seed_v1.py','casepath-api/casepath_api/hosted_storage_v1.py','casepath-api/casepath_api/hosted_app_v1.py','casepath-api/tests/test_hosted_read_seed_v1.py','casepath-api/tests/test_public_hosted_read_only_v1.py']),('8b92084acd150783b5f728893fed47d9e2b71f5c',['casepath-api/tools/export_read_seed.py','casepath-api/tests/test_hosted_read_seed_export_v1.py','docs/HOSTED_CASEPATH.md','.gitignore','casepath-api/pyproject.toml'])]:
 for rel in paths:
  raw=subprocess.check_output(['git','-C',('/workspace/casepath-release-ae0-shard3' if commit.startswith('af786') else '/workspace/casepath-release-ae0-shard4'),'show',commit+':'+rel]);assert raw==(repo/rel).read_bytes();bindings.append({'path':rel,'focused_source_commit':commit,'candidate_byte_equal':True,'sha256':hashlib.sha256(raw).hexdigest()})
save('focused-read-seed-binding.json',{'candidate':SHA,'focused_evidence_commit':'81919a0beceab6672f72daf1e823120e9046e2cc','focused_subtree':'qa-evidence/read-seed-startup-8f230fd4-20261018','focused_evidence_checksums_verified':18,'source_bindings':bindings,'focused_commands_reexecuted_separately_by_gate':False,'fresh_full_pytest_includes_all_new_tests_once':True,'synthetic_only':True,'actual_seed_loaded_by_gate':False})
p=R/'coordinator/qualify_final.py';s=p.read_text().replace('all2777_prior_4bf_ids_retained_unchanged=True,','all2777_prior_8f_ids_retained_unchanged=True, all2777_prior_4bf_ids_retained_unchanged=True,').replace('pytest_added_ids=0','pytest_added_ids=len(read(R / \'fresh-inventory-delta.json\')[\'added_ids\'])');a=s.index('                 existing_outcome_focused_node_cases=62');b=s.index('                 minimum_observed_workspace_free_bytes=minimum',a);s=s[:a]+"                 focused_read_seed_evidence_commit='81919a0beceab6672f72daf1e823120e9046e2cc',\n                 focused_read_seed_source_bindings=10, prior_language62_and_touch14_commands_reexecuted_separately=False,\n"+s[b:];s=s.replace("'existing62_outcome_and14_touch_cases_reexecuted':False","'focused_commands_reexecuted_separately':False");ast.parse(s);p.write_text(s)
p=R/'coordinator/reconcile.py';s=p.read_text().replace("assert env['TMPDIR']==", "assert 'CASEPATH_READ_SEED_PATH' not in env\n assert env['TMPDIR']==");ast.parse(s);p.write_text(s)
p=R/'coordinator/summarize.py';s=p.read_text().replace('preparation_failures=0,','preparation_failures=0, approved_runtime_retirement_permission_failures=1,');p.write_text(s)
p=R/'coordinator/finish_audit.py';s=p.read_text()+'''
branch_proof=json.loads((R/'approved-retirement-proof.json').read_text());preserved=[]
for row in branch_proof['source_branches_preserved']:
 actual=subprocess.check_output(['git','rev-parse',row['branch']],cwd=row['path'],text=True).strip();assert actual==row['head']
 remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/'+row['branch']],cwd=G,text=True).split()[0];assert remote==row['remote']
 preserved.append({'path':row['path'],'branch':row['branch'],'local':actual,'remote':remote})
(R/'focused-source-branches-after.json').write_text(json.dumps({'branches':preserved,'focused_evidence_commit':'81919a0beceab6672f72daf1e823120e9046e2cc','no_source_branch_rewritten':True,'epoch':time.time()},indent=2)+'\\n')
''';ast.parse(s);p.write_text(s)
print(json.dumps({'current_mac_attestation_fixed_schema':True,'all_baselines_verified':True,'focused_source_bindings':len(bindings),'no_product_tests_executed_by_metadata':True}))
