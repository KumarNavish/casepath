import hashlib,json,os,pathlib,subprocess,time
R=pathlib.Path('/workspace/casepath-touch-target-gate-4bf9b439-20261018')
assert 'all_six_terminal_and_pushed' in (R/'serial-driver-events.jsonl').read_text().splitlines()[-1]
assert (R/'STOP_RESOURCE_WATCH').exists()
for n in range(1,7):
 result=json.loads((R/f'shard{n}/result.json').read_text());assert result['exit_code']==0 and result['after_status']==''
transport=['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','SSL_CERT_FILE','REQUESTS_CA_BUNDLE','CURL_CA_BUNDLE','NODE_EXTRA_CA_CERTS'];env={k:os.environ[k] for k in transport if k in os.environ};env.update(HOME='/workspace/tt4h0',TMPDIR='/workspace/tt4t0',TMP='/workspace/tt4t0',TEMP='/workspace/tt4t0',PATH='/usr/local/bin:/usr/bin:/bin',LANG='C.UTF-8',LC_ALL='C.UTF-8',PYTHONDONTWRITEBYTECODE='1');commands=[]
for script,log in [('reconcile.py','reconciliation.log'),('summarize.py','summary.log'),('qualify_final.py','qualify-final.log'),('finish_audit.py','finish-audit.log')]:
 command=['/usr/bin/python3',str(R/'coordinator'/script)];start=time.time()
 with (R/log).open('x') as f:result=subprocess.run(command,cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT)
 commands.append({'command':command,'env_names':sorted(env),'inherited_transport_variable_names':[k for k in transport if k in env],'started_epoch':start,'finished_epoch':time.time(),'exit_code':result.returncode,'log':str(R/log)})
 (R/'finalization-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 assert result.returncode==0,(script,result.returncode)
shared=json.loads((R/'pinned-shared-tool-identities.json').read_text())
for row in shared['tools']:assert hashlib.sha256(pathlib.Path(row['path']).read_bytes()).hexdigest()==row['sha256']
(R/'pinned-shared-tool-identities-after.json').write_text(json.dumps({'versions_and_hashes_receipt':'pinned-shared-tool-identities.json','all_existing_shared_executable_bytes_unchanged':True,'epoch':time.time()},indent=2)+'\n')
x=json.loads((R/'aggregate.json').read_text());print(json.dumps({'candidate':x['candidate'],'cloud_passed':x['cloud_passed'],'cloud_skipped':x['cloud_skipped'],'cloud_failed':x['cloud_failed'],'combined_passed_using_actual_mac_owner_attestation':x['combined_passed_using_actual_mac_owner_attestation'],'actual_max_heavy':x['maximum_actual_prepare_or_pytest_concurrency'],'configured_cap':x['configured_gate_heavy_cap'],'global_cap':x['global_heavy_cap'],'minimum_free':x['minimum_observed_workspace_free_bytes']}),flush=True)
